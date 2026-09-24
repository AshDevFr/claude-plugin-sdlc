import hashlib
import json
import os
import shutil
import subprocess
import tempfile
from pathlib import Path

from sdlc_specs.frontmatter import set_top_level
from sdlc_specs.snapshot import intent_sha256
from sdlc_specs.spec import parse_spec

from tests.base import OfflineTestCase

EXAMPLE = Path(__file__).resolve().parent / "fixtures" / "specs" / "123-prorate-plan-changes"

LINEAR_CONFIG = """tracker:
  system: linear
  team_key: ENG
code_host:
  system: github
  spec_approvers: "@acme/spec-approvers"
"""
GITHUB_CONFIG = """tracker:
  system: github
code_host:
  system: github
  spec_approvers: "@acme/spec-approvers"
"""
GIT_ENV = {"GIT_CONFIG_GLOBAL": os.devnull, "GIT_CONFIG_NOSYSTEM": "1"}


def tree_digest(path: Path) -> dict[str, str]:
    return {
        p.relative_to(path).as_posix(): hashlib.sha256(p.read_bytes()).hexdigest()
        for p in sorted(path.rglob("*"))
        if p.is_file()
    }


class NewRepoTestCase(OfflineTestCase):
    def setUp(self):
        super().setUp()
        self.root = Path(tempfile.mkdtemp())
        self.addCleanup(shutil.rmtree, self.root)
        subprocess.run(["git", "init", "-q", str(self.root)], check=True, env={**os.environ, **GIT_ENV})
        subprocess.run(["git", "-C", str(self.root), "config", "user.name", "jdoe"], check=True)
        self.specs = self.root / "specs"
        self.specs.mkdir()

    def config(self, text: str) -> None:
        (self.specs / "config.yml").write_text(text)

    def specs_cmd(self, *args: str):
        return self.run_shim(*args, cwd=self.root, env=GIT_ENV)

    def add_old_spec(self) -> Path:
        """A lint-clean spec for #88 under a GitHub tracker, built from the workflow example."""
        old = self.specs / "88-plan-change-billing"
        shutil.copytree(EXAMPLE, old)
        spec = old / "spec.md"
        text = spec.read_text()
        text = text.replace("id: 123-prorate-plan-changes", "id: 88-plan-change-billing")
        text = text.replace("system: gitlab ", "system: github ")
        text = text.replace("ref: billing/api#123 ", 'ref: "#88"          ')
        spec.write_text(text)
        snapshot = old / "ticket.snapshot.md"
        snapshot.write_text(snapshot.read_text().replace("ticket: billing/api#123 ", "ticket: #88 "))
        return old


class NewTest(NewRepoTestCase):
    def test_new_spec_lints_except_for_the_missing_snapshot(self):
        self.config(LINEAR_CONFIG)
        result = self.specs_cmd("new", "--key", "ENG-123", "--title", "Webhook retries")
        self.assertEqual(result.returncode, 0, result.stderr)
        spec_dir = self.specs / "eng-123-webhook-retries"
        self.assertTrue((spec_dir / "spec.md").is_file())
        self.assertIn("specs/eng-123-webhook-retries", result.stdout)

        lint = self.specs_cmd("--json", "lint", str(spec_dir))
        self.assertEqual(lint.returncode, 1, lint.stdout + lint.stderr)
        findings = json.loads(lint.stdout)["findings"]
        self.assertEqual(
            [(f["rule"], f["message"].split(":")[0]) for f in findings], [("L010", "no snapshot yet")]
        )

    def test_frontmatter_and_body(self):
        self.config(GITHUB_CONFIG)
        result = self.specs_cmd("new", "--key", "#131", "--title", "Plan change: v2 #fast")
        self.assertEqual(result.returncode, 0, result.stderr)
        spec = parse_spec(self.specs / "131-plan-change-v2-fast" / "spec.md")
        fm = spec.frontmatter
        self.assertEqual(fm["id"], "131-plan-change-v2-fast")
        self.assertEqual(fm["title"], "Plan change: v2 #fast")
        self.assertEqual(fm["ticket"], {"system": "github", "ref": "#131", "url": ""})
        self.assertEqual(
            (fm["revision"], fm["state"], fm["supersedes"], fm["superseded_by"]), (1, "active", [], None)
        )
        self.assertEqual(spec.title, "Plan change: v2 #fast")
        self.assertEqual([c.number for c in spec.criteria], [1])
        self.assertEqual([(r.number, r.author) for r in spec.revisions], [(1, "jdoe")])
        self.assertEqual(spec.open_questions, [])

    def test_slug_override(self):
        self.config(GITHUB_CONFIG)
        result = self.specs_cmd("new", "--key", "7", "--title", "Something long", "--slug", "Short Name")
        self.assertEqual(result.returncode, 0, result.stderr)
        self.assertTrue((self.specs / "7-short-name" / "spec.md").is_file())

    def test_json_output(self):
        self.config(GITHUB_CONFIG)
        result = self.specs_cmd("--json", "new", "--key", "7", "--title", "Seven")
        self.assertEqual(result.returncode, 0, result.stderr)
        self.assertEqual(json.loads(result.stdout), {"ok": True, "path": "specs/7-seven", "id": "7-seven"})

    def test_running_twice_changes_nothing(self):
        self.config(LINEAR_CONFIG)
        self.assertEqual(
            self.specs_cmd("new", "--key", "ENG-123", "--title", "Webhook retries").returncode, 0
        )
        before = tree_digest(self.specs)
        again = self.specs_cmd("new", "--key", "eng-123", "--title", "Another title")
        self.assertEqual(again.returncode, 1)
        self.assertIn("specs/eng-123-webhook-retries", again.stderr)
        self.assertEqual(tree_digest(self.specs), before)

    def test_bad_key_is_a_usage_error(self):
        self.config(LINEAR_CONFIG)
        result = self.specs_cmd("new", "--key", "123", "--title", "x")
        self.assertEqual(result.returncode, 2)


class IntentSpecTest(NewRepoTestCase):
    """Specs whose intent is a local intent.md, named by creation date and slug."""

    def new(self, *args: str):
        return self.specs_cmd("new", *args)

    def test_creates_a_date_named_spec_that_lints_clean(self):
        self.config(GITHUB_CONFIG)
        result = self.new("--date", "2026-09-23", "--title", "Webhook retries")
        self.assertEqual(result.returncode, 0, result.stderr)
        spec_dir = self.specs / "2026-09-23-webhook-retries"
        self.assertTrue((spec_dir / "spec.md").is_file())
        self.assertTrue((spec_dir / "intent.md").is_file())
        lint = self.specs_cmd("--json", "lint", str(spec_dir))
        self.assertEqual(lint.returncode, 0, lint.stdout + lint.stderr)
        self.assertEqual(json.loads(lint.stdout)["findings"], [])

    def test_frontmatter_records_the_intent(self):
        self.config(GITHUB_CONFIG)
        self.assertEqual(self.new("--date", "2026-09-23", "--title", "Webhook retries").returncode, 0)
        spec_dir = self.specs / "2026-09-23-webhook-retries"
        spec = parse_spec(spec_dir / "spec.md")
        fm = spec.frontmatter
        self.assertEqual(fm["id"], "2026-09-23-webhook-retries")
        self.assertNotIn("ticket", fm)
        self.assertEqual(fm["intent"]["file"], "intent.md")
        self.assertEqual(fm["intent"]["content_sha256"], intent_sha256((spec_dir / "intent.md").read_text()))
        self.assertEqual(fm["intent"]["recorded_by"], "jdoe")
        self.assertIn("recorded_at", fm["intent"])
        self.assertEqual((fm["revision"], fm["state"]), (1, "active"))
        self.assertEqual([c.number for c in spec.criteria], [1])

    def test_intent_comes_from_the_template(self):
        self.config(GITHUB_CONFIG)
        self.new("--date", "2026-09-23", "--title", "Webhook retries")
        intent = (self.specs / "2026-09-23-webhook-retries" / "intent.md").read_text()
        self.assertTrue(intent.startswith("# Intent: Webhook retries\n"))
        for section in (
            "Problem",
            "Proposed outcome",
            "Affected users and systems",
            "Constraints",
            "Open questions",
        ):
            self.assertIn(f"\n## {section}\n", intent)

    def test_same_day_same_slug_is_refused(self):
        self.config(GITHUB_CONFIG)
        self.assertEqual(self.new("--date", "2026-09-23", "--title", "Webhook retries").returncode, 0)
        before = tree_digest(self.specs)
        again = self.new("--date", "2026-09-23", "--title", "Webhook retries")
        self.assertEqual(again.returncode, 1)
        self.assertIn("specs/2026-09-23-webhook-retries", again.stderr)
        self.assertEqual(tree_digest(self.specs), before)
        other = self.new("--date", "2026-09-23", "--title", "Webhook retries", "--slug", "retries-v2")
        self.assertEqual(other.returncode, 0, other.stderr)
        self.assertTrue((self.specs / "2026-09-23-retries-v2" / "spec.md").is_file())

    def test_intent_file_is_copied_byte_for_byte(self):
        self.config(GITHUB_CONFIG)
        source = self.root / "notes" / "request.md"
        source.parent.mkdir()
        source.write_bytes(b"# Intent: from a file\r\n\r\n## Problem\r\nIt is slow.  \r\n")
        result = self.new("--date", "2026-09-23", "--title", "Faster", "--intent-file", str(source))
        self.assertEqual(result.returncode, 0, result.stderr)
        spec_dir = self.specs / "2026-09-23-faster"
        self.assertEqual((spec_dir / "intent.md").read_bytes(), source.read_bytes())
        fm = parse_spec(spec_dir / "spec.md").frontmatter
        self.assertEqual(fm["intent"]["content_sha256"], intent_sha256(source.read_text()))

    def test_repo_templates_win_over_the_helpers(self):
        self.config(GITHUB_CONFIG)
        templates = self.specs / "templates"
        templates.mkdir()
        (templates / "spec.md").write_text(
            "# $title\n\nCUSTOM BODY costs $$5\n\n## Acceptance criteria\n- **AC-1** Something.\n"
        )
        (templates / "intent.md").write_text("# Intent: $title\n\nCUSTOM INTENT\n")
        self.assertEqual(self.new("--date", "2026-09-23", "--title", "Custom").returncode, 0)
        spec_dir = self.specs / "2026-09-23-custom"
        self.assertIn("CUSTOM BODY costs $5", (spec_dir / "spec.md").read_text())
        self.assertEqual((spec_dir / "intent.md").read_text(), "# Intent: Custom\n\nCUSTOM INTENT\n")

    def test_date_defaults_to_the_local_date(self):
        import datetime

        self.config(GITHUB_CONFIG)
        # A zone whose date differs from UTC's right now: UTC-12 before noon UTC, UTC+14 after.
        utc = datetime.datetime.now(datetime.timezone.utc)
        hours = -12 if utc.hour < 12 else 14
        env = {**GIT_ENV, "TZ": f"Etc/GMT{-hours:+d}"}  # POSIX zone names invert the sign
        result = self.run_shim("new", "--title", "Today", cwd=self.root, env=env)
        self.assertEqual(result.returncode, 0, result.stderr)
        now = utc + datetime.timedelta(hours=hours)
        spec_dir = self.specs / f"{now.date().isoformat()}-today"
        self.assertTrue(spec_dir.is_dir(), list(self.specs.iterdir()))
        self.assertRegex((spec_dir / "spec.md").read_text(), r"recorded_at: \S+Z\n")

    def test_bad_date_and_mixed_modes_are_usage_errors(self):
        self.config(GITHUB_CONFIG)
        self.assertEqual(self.new("--date", "2026-02-30", "--title", "x").returncode, 2)
        self.assertEqual(self.new("--key", "7", "--date", "2026-09-23", "--title", "x").returncode, 2)
        self.assertEqual(self.new("--key", "7", "--intent-file", "x.md", "--title", "x").returncode, 2)
        missing = self.new("--title", "x", "--intent-file", "nope.md")
        self.assertEqual(missing.returncode, 2)
        self.assertEqual([p.name for p in self.specs.iterdir()], ["config.yml"])


class SupersedesTest(NewRepoTestCase):
    def test_supersedes_updates_both_specs(self):
        self.config(GITHUB_CONFIG)
        old = self.add_old_spec()
        self.assertEqual(self.specs_cmd("lint", str(old)).returncode, 0, "the old spec must start clean")
        before = (old / "spec.md").read_text().splitlines()

        result = self.specs_cmd(
            "new", "--key", "131", "--title", "Plan change v2", "--supersedes", "88-plan-change-billing"
        )
        self.assertEqual(result.returncode, 0, result.stderr)

        new = parse_spec(self.specs / "131-plan-change-v2" / "spec.md")
        self.assertEqual(new.frontmatter["supersedes"], ["88-plan-change-billing"])
        old_spec = parse_spec(old / "spec.md")
        self.assertEqual(old_spec.frontmatter["state"], "superseded")
        self.assertEqual(old_spec.frontmatter["superseded_by"], "131-plan-change-v2")

        after = (old / "spec.md").read_text().splitlines()
        self.assertEqual(len(before), len(after))
        changed = [(b, a) for b, a in zip(before, after, strict=True) if b != a]
        self.assertEqual(
            changed,
            [
                (
                    "state: active                        # active | superseded",
                    "state: superseded                        # active | superseded",
                ),
                (
                    "superseded_by: null                  # set by the PR that supersedes this spec",
                    "superseded_by: 131-plan-change-v2                  "
                    "# set by the PR that supersedes this spec",
                ),
            ],
        )
        lint = self.specs_cmd("lint", str(old))
        self.assertEqual(lint.returncode, 0, lint.stdout + lint.stderr)

    def test_missing_superseded_spec_writes_nothing(self):
        self.config(GITHUB_CONFIG)
        before = tree_digest(self.specs)
        result = self.specs_cmd(
            "new", "--key", "131", "--title", "Plan change v2", "--supersedes", "999-missing"
        )
        self.assertEqual(result.returncode, 1)
        self.assertIn("999-missing", result.stderr)
        self.assertEqual(tree_digest(self.specs), before)

    def test_already_superseded_spec_is_refused(self):
        self.config(GITHUB_CONFIG)
        old = self.add_old_spec()
        spec = old / "spec.md"
        spec.write_text(
            spec.read_text()
            .replace("state: active ", "state: superseded ")
            .replace("superseded_by: null ", "superseded_by: 100-x ")
        )
        before = tree_digest(self.specs)
        result = self.specs_cmd(
            "new", "--key", "131", "--title", "v2", "--supersedes", "88-plan-change-billing"
        )
        self.assertEqual(result.returncode, 1)
        self.assertIn("100-x", result.stderr)
        self.assertEqual(tree_digest(self.specs), before)


class SetTopLevelTest(OfflineTestCase):
    def test_replaces_value_and_keeps_the_comment_gap(self):
        text = "---\nid: x\nstate: active   # note\nrevision: 1\n---\nbody\n"
        self.assertEqual(
            set_top_level(text, "state", "superseded"),
            "---\nid: x\nstate: superseded   # note\nrevision: 1\n---\nbody\n",
        )

    def test_replaces_a_block_value(self):
        text = "---\nsupersedes:\n  - a\n  - b\nstate: active\n---\n"
        self.assertEqual(
            set_top_level(text, "supersedes", "[c]"), "---\nsupersedes: [c]\nstate: active\n---\n"
        )

    def test_inserts_a_missing_key_before_the_closing_marker(self):
        text = "---\nid: x\n---\nbody\n"
        self.assertEqual(
            set_top_level(text, "superseded_by", "y"), "---\nid: x\nsuperseded_by: y\n---\nbody\n"
        )

    def test_nested_keys_are_not_matched(self):
        text = "---\nticket:\n  state: nested\nstate: top\n---\n"
        self.assertEqual(
            set_top_level(text, "state", "changed"), "---\nticket:\n  state: nested\nstate: changed\n---\n"
        )

    def test_crlf_is_kept(self):
        text = "---\r\nstate: active\r\n---\r\n"
        self.assertEqual(set_top_level(text, "state", "superseded"), "---\r\nstate: superseded\r\n---\r\n")
