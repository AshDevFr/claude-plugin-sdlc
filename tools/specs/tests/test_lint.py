import json
import os
import shutil
import subprocess
import tempfile
from pathlib import Path

from sdlc_specs.config import load_config
from sdlc_specs.lint import RULES, LintOptions, lint, select_spec_dirs

from tests.base import OfflineTestCase

FIXTURES = Path(__file__).resolve().parent / "fixtures"
LINT = FIXTURES / "lint"
EXAMPLE = FIXTURES / "specs" / "123-prorate-plan-changes"

DEFAULT_CONFIG = """tracker:
  system: gitlab
  project: billing/api
code_host:
  system: gitlab
  spec_approvers: "@acme/spec-approvers"
"""

GIT_ENV = {
    "GIT_CONFIG_GLOBAL": os.devnull,
    "GIT_CONFIG_NOSYSTEM": "1",
    "GIT_AUTHOR_NAME": "test",
    "GIT_AUTHOR_EMAIL": "test@example.com",
    "GIT_COMMITTER_NAME": "test",
    "GIT_COMMITTER_EMAIL": "test@example.com",
}


class LintRepoTestCase(OfflineTestCase):
    """A throwaway git repo with a config and a specs/ directory. Git is local, not network."""

    def setUp(self):
        super().setUp()
        self.root = Path(tempfile.mkdtemp())
        self.addCleanup(shutil.rmtree, self.root)
        self.specs = self.root / "specs"
        self.specs.mkdir()
        self.git("init", "-q")
        self.write_config(DEFAULT_CONFIG)

    def git(self, *args: str) -> str:
        env = {**os.environ, **GIT_ENV}
        result = subprocess.run(
            ["git", "-C", str(self.root), *args], env=env, capture_output=True, text=True, check=True
        )
        return result.stdout

    def commit(self, message: str = "commit") -> None:
        self.git("add", "-A")
        self.git("commit", "-q", "--allow-empty", "-m", message)

    def write_config(self, text: str) -> None:
        (self.specs / "config.yml").write_text(text)

    def copy_spec_dirs(self, source: Path) -> None:
        for spec_dir in source.iterdir():
            target = self.specs / spec_dir.name
            if target.exists():
                shutil.rmtree(target)
            shutil.copytree(spec_dir, target)

    def load_fixture(self, name: str) -> str | None:
        """Install a lint fixture; returns the base ref when the fixture has a base version."""
        fixture = LINT / name
        if (fixture / "config.yml").exists():
            self.write_config((fixture / "config.yml").read_text())
        base = None
        if (fixture / "base").is_dir():
            self.copy_spec_dirs(fixture / "base")
            self.commit("base")
            base = "HEAD"
        self.copy_spec_dirs(fixture / "head")
        return base

    def run_lint(self, ready: bool = True, base: str | None = None, paths=()):
        root, config = load_config(self.root)
        dirs = select_spec_dirs(root, config, [str(p) for p in paths], None)
        return lint(root, config, dirs, LintOptions(ready=ready, base=base))


class RuleFixtureTest(LintRepoTestCase):
    def test_every_rule_has_a_passing_and_a_failing_fixture(self):
        for rule in RULES:
            with self.subTest(rule=rule):
                self.assertTrue((LINT / f"{rule}-pass" / "head").is_dir())
                self.assertTrue((LINT / f"{rule}-fail" / "expected.json").is_file())

    def test_passing_fixtures_are_clean(self):
        for rule in RULES:
            with self.subTest(rule=rule):
                self.setUp()
                base = self.load_fixture(f"{rule}-pass")
                findings = self.run_lint(ready=True, base=base)
                self.assertEqual(findings, [], [f.render() for f in findings])

    def test_failing_fixtures_report_exactly_their_rule_at_their_line(self):
        for rule in RULES:
            with self.subTest(rule=rule):
                self.setUp()
                expected = json.loads((LINT / f"{rule}-fail" / "expected.json").read_text())
                base = self.load_fixture(f"{rule}-fail")
                findings = self.run_lint(ready=True, base=base)
                self.assertEqual({f.rule for f in findings}, {rule}, [f.render() for f in findings])
                located = [(f.rule, f.path, f.line) for f in findings]
                self.assertIn((expected["rule"], expected["path"], expected["line"]), located)
                rendered = [f.render() for f in findings]
                self.assertTrue(
                    any(r.startswith(f"{expected['path']}:{expected['line']}: {rule} ") for r in rendered),
                    rendered,
                )


class RuleDetailTest(LintRepoTestCase):
    def lint_example_with(self, old: str, new: str, **kwargs):
        self.copy_spec_dirs(EXAMPLE.parent)
        for extra in ("struck-ac", "noncanonical-ac", "no-frontmatter", "bad-frontmatter"):
            shutil.rmtree(self.specs / extra)
        spec = self.specs / EXAMPLE.name / "spec.md"
        text = spec.read_text()
        self.assertEqual(text.count(old), 1, old)
        spec.write_text(text.replace(old, new))
        return self.run_lint(**kwargs)

    def assert_one(self, findings, rule, fragment):
        self.assertEqual([f.rule for f in findings], [rule], [f.render() for f in findings])
        self.assertIn(fragment, findings[0].message)

    def test_missing_spec_file_has_no_line(self):
        (self.specs / "123-empty").mkdir()
        (self.specs / "123-empty" / "notes.md").write_text("x\n")
        findings = self.run_lint()
        self.assertEqual(
            [(f.rule, f.path, f.line) for f in findings], [("L001", "specs/123-empty/spec.md", None)]
        )

    def test_field_types(self):
        cases = [
            ("revision: 2 ", "revision: '2' ", "'revision' must be an integer"),
            ("system: gitlab ", "system: fake   ", "'ticket.system' must be one of"),
            ("state: active ", "state: frozen ", "'state' must be one of"),
            ("related:\n", "owner: jdoe\nrelated:\n", "unknown field 'owner'"),
            ("  url: https", "  pr: 12\n  url: https", "unknown field 'ticket.pr'"),
        ]
        for old, new, fragment in cases:
            with self.subTest(new=new):
                self.setUp()
                findings = [f for f in self.lint_example_with(old, new) if f.rule == "L002"]
                self.assertEqual(len(findings), 1, [f.render() for f in findings])
                self.assertIn(fragment, findings[0].message)

    def test_forbidden_fields_say_why(self):
        findings = self.lint_example_with("state: active", "approvers: [a]\nstate: active")
        self.assert_one(findings, "L002", "read from the code host")

    def test_unquoted_all_digit_hash_is_rejected(self):
        findings = self.lint_example_with(
            "content_sha256: 5cee61d26ee90c1b7d0fb397ba26f6857b0c91b1c4e275b1a0a89d304ff477d3",
            "content_sha256: 1234567890123456789012345678901234567890123456789012345678901234",
        )
        self.assertIn("L002", [f.rule for f in findings])

    def test_no_snapshot_yet(self):
        findings = self.lint_example_with(
            "  snapshot:\n"
            "    content_sha256: 5cee61d26ee90c1b7d0fb397ba26f6857b0c91b1c4e275b1a0a89d304ff477d3"
            " # sha256 of normalised title + description\n"
            "    updated_at: 2026-09-23T10:14:00Z # informational only, see 5.1\n"
            "    taken_by: jdoe\n    taken_at: 2026-09-23T11:02:00Z\n",
            "",
        )
        self.assert_one(findings, "L010", "no snapshot yet")

    def test_attachment_outside_the_directory(self):
        findings = self.lint_example_with("  - sequence.png", "  - ../sequence.png")
        self.assert_one(findings, "L009", "inside the spec directory")

    def test_open_questions_only_matter_when_ready(self):
        old = "Each one names who must answer it. The spec is not approvable with open questions left.\n"
        new = "- Do credits expire? (PM)\n"
        self.assertEqual(self.lint_example_with(old, new, ready=False), [])
        self.setUp()
        self.assert_one(self.lint_example_with(old, new, ready=True), "L008", "Do credits expire?")

    def test_spec_new_since_base_skips_base_rules(self):
        # Each head fails its rule against its own base; against a base without the spec, neither
        # a removed criterion nor a missing revision bump can be judged.
        for fixture in ("L007-fail", "L011-fail"):
            with self.subTest(fixture=fixture):
                self.setUp()
                self.commit("base without the spec")
                self.copy_spec_dirs(LINT / fixture / "head")
                self.assertEqual(self.run_lint(base="HEAD"), [])


class CliTest(LintRepoTestCase):
    def test_workflow_example_lints_clean(self):
        self.copy_spec_dirs(LINT / "L001-pass" / "head")
        result = self.run_shim("lint", str(self.specs / EXAMPLE.name), cwd=self.root)
        self.assertEqual(result.returncode, 0, result.stdout + result.stderr)
        self.assertEqual(result.stdout, "")
        self.assertIn("1 spec clean", result.stderr)

    def test_duplicate_criterion_exits_1_naming_rule_and_line(self):
        expected = json.loads((LINT / "L006-fail" / "expected.json").read_text())
        self.load_fixture("L006-fail")
        result = self.run_shim("lint", cwd=self.root)
        self.assertEqual(result.returncode, 1)
        self.assertIn(f"{expected['path']}:{expected['line']}: L006 AC-2 is defined twice", result.stdout)

    def test_invalid_config_exits_2(self):
        self.write_config(DEFAULT_CONFIG.replace("system: gitlab\n  project", "system: jira\n  project"))
        result = self.run_shim("lint", cwd=self.root)
        self.assertEqual(result.returncode, 2)
        self.assertIn("tracker.system", result.stderr)

    def test_bad_base_ref_exits_2(self):
        self.copy_spec_dirs(LINT / "L001-pass" / "head")
        result = self.run_shim("lint", "--base", "no-such-ref", cwd=self.root, env=GIT_ENV)
        self.assertEqual(result.returncode, 2)
        self.assertIn("no-such-ref", result.stderr)

    def test_json_shape(self):
        self.load_fixture("L006-fail")
        result = self.run_shim("lint", "--json", cwd=self.root)
        self.assertEqual(result.returncode, 1)
        doc = json.loads(result.stdout)
        self.assertIs(doc["ok"], False)
        self.assertEqual(set(doc), {"ok", "findings"})
        for finding in doc["findings"]:
            self.assertEqual(set(finding), {"rule", "path", "line", "message"})

    def test_json_clean(self):
        self.copy_spec_dirs(LINT / "L001-pass" / "head")
        result = self.run_shim("--json", "lint", cwd=self.root)
        self.assertEqual(result.returncode, 0, result.stderr)
        self.assertEqual(json.loads(result.stdout), {"ok": True, "findings": []})

    def test_changed_since_lints_only_changed_directories(self):
        self.load_fixture("L006-fail")  # one broken spec, committed below
        self.copy_spec_dirs(LINT / "L003-pass" / "head")
        self.commit("two specs")
        changed = self.specs / "acme-api-123-prorate-plan-changes" / "spec.md"
        changed.write_text(changed.read_text().replace("## Context\n", "## Context\nEdited.\n"))
        self.commit("edit one")
        result = self.run_shim("--json", "lint", "--changed-since", "HEAD~1", cwd=self.root, env=GIT_ENV)
        self.assertEqual(result.returncode, 0, result.stdout + result.stderr)
        self.assertIn("1 spec clean", result.stderr)
        # Without the filter, the committed broken spec is found.
        self.assertEqual(self.run_shim("lint", cwd=self.root).returncode, 1)

    def test_changed_since_includes_uncommitted_and_untracked(self):
        self.commit("empty")
        self.load_fixture("L006-fail")  # untracked
        result = self.run_shim("lint", "--changed-since", "HEAD", cwd=self.root, env=GIT_ENV)
        self.assertEqual(result.returncode, 1)
        self.assertIn("L006", result.stdout)


class IntentSpecLintTest(LintRepoTestCase):
    """Specs whose intent is a local intent.md and whose id is a creation date."""

    def make(self, date="2026-09-23", title="Webhook retries"):
        result = self.run_shim("new", "--date", date, "--title", title, cwd=self.root, env=GIT_ENV)
        self.assertEqual(result.returncode, 0, result.stderr)
        return self.specs / f"{date}-webhook-retries"

    def rules(self, **kwargs):
        # A spec fresh from `specs new` still holds template guidance; it isn't review-ready.
        return [f.rule for f in self.run_lint(ready=False, **kwargs)]

    def test_a_new_intent_spec_is_clean(self):
        self.make()
        self.assertEqual(self.run_lint(ready=False), [])

    def test_date_id_must_be_a_real_date_matching_the_directory(self):
        spec_dir = self.make()
        spec = spec_dir / "spec.md"
        spec.write_text(
            spec.read_text().replace("id: 2026-09-23-webhook-retries", "id: 2026-09-24-webhook-retries")
        )
        self.assertEqual(self.rules(), ["L003"])
        bad = self.specs / "2026-13-40-webhook-retries"
        spec_dir.rename(bad)
        (bad / "spec.md").write_text(
            (bad / "spec.md")
            .read_text()
            .replace("id: 2026-09-24-webhook-retries", "id: 2026-13-40-webhook-retries")
        )
        findings = self.run_lint(ready=False)
        self.assertEqual([f.rule for f in findings], ["L003"])
        self.assertIn("date", findings[0].message)

    def test_ticket_rules_do_not_apply_without_a_ticket(self):
        self.make()
        self.assertNotIn("L010", self.rules())
        self.assertNotIn("L004", self.rules())
