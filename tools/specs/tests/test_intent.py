import json
import os
import shutil
import subprocess
import tempfile
from pathlib import Path

from sdlc_specs.frontmatter import set_top_level_block
from sdlc_specs.spec import parse_spec

from tests.base import OfflineTestCase

CONFIG = """tracker:
  system: github
code_host:
  system: github
"""
GIT_ENV = {
    "GIT_CONFIG_GLOBAL": os.devnull,
    "GIT_CONFIG_NOSYSTEM": "1",
    "GIT_AUTHOR_NAME": "jdoe",
    "GIT_AUTHOR_EMAIL": "jdoe@example.com",
    "GIT_COMMITTER_NAME": "jdoe",
    "GIT_COMMITTER_EMAIL": "jdoe@example.com",
}
SPEC_ID = "2026-09-23-webhook-retries"


class IntentRepoTestCase(OfflineTestCase):
    def setUp(self):
        super().setUp()
        self.root = Path(tempfile.mkdtemp())
        self.addCleanup(shutil.rmtree, self.root)
        self.git("init", "-q")
        self.git("config", "user.name", "jdoe")
        (self.root / "specs").mkdir()
        (self.root / "specs" / "config.yml").write_text(CONFIG)
        result = self.specs("new", "--date", "2026-09-23", "--title", "Webhook retries")
        self.assertEqual(result.returncode, 0, result.stderr)
        self.spec_dir = self.root / "specs" / SPEC_ID
        self.intent = self.spec_dir / "intent.md"
        self.commit("spec")

    def git(self, *args: str) -> str:
        result = subprocess.run(
            ["git", "-C", str(self.root), *args],
            env={**os.environ, **GIT_ENV},
            capture_output=True,
            text=True,
            check=True,
        )
        return result.stdout

    def commit(self, message: str) -> None:
        self.git("add", "-A")
        self.git("commit", "-q", "-m", message)

    def specs(self, *args: str):
        return self.run_shim(*args, cwd=self.root, env=GIT_ENV)

    def check(self, *args: str):
        return self.specs("intent", "check", str(self.spec_dir), *args)

    def edit_intent(self, old: str, new: str) -> None:
        text = self.intent.read_text()
        self.assertEqual(text.count(old), 1, old)
        self.intent.write_text(text.replace(old, new))


class CheckTest(IntentRepoTestCase):
    def test_unchanged_then_changed(self):
        result = self.check()
        self.assertEqual(result.returncode, 0, result.stderr)
        self.assertIn("unchanged", result.stdout)
        self.edit_intent("## Constraints\n", "## Constraints\nNo new PII.\n")
        result = self.check()
        self.assertEqual(result.returncode, 1)
        self.assertIn("changed", result.stdout)

    def test_diff_shows_exactly_the_committed_edit(self):
        self.edit_intent("## Constraints\n", "## Constraints\nNo new PII.\n")
        self.commit("edit intent")
        result = self.check("--diff")
        self.assertEqual(result.returncode, 1)
        removed = [ln for ln in result.stdout.splitlines() if ln.startswith("-") and not ln.startswith("---")]
        added = [ln for ln in result.stdout.splitlines() if ln.startswith("+") and not ln.startswith("+++")]
        self.assertEqual(added, ["+No new PII."])
        self.assertEqual(removed, [])

    def test_diff_includes_uncommitted_edits(self):
        self.edit_intent("## Constraints\n", "## Constraints\nUncommitted.\n")
        result = self.check("--diff")
        self.assertIn("+Uncommitted.", result.stdout)

    def test_recorded_version_missing_from_history(self):
        spec = self.spec_dir / "spec.md"
        text = spec.read_text()
        recorded = parse_spec(spec).frontmatter["intent"]["content_sha256"]
        spec.write_text(text.replace(recorded, "ab" * 32))
        result = self.check("--diff")
        self.assertEqual(result.returncode, 1)
        self.assertIn("changed", result.stdout)
        self.assertIn("no recorded version", result.stdout)
        self.assertNotIn("@@", result.stdout)

    def test_not_recorded(self):
        spec = self.spec_dir / "spec.md"
        text = spec.read_text()
        start, end = text.index("intent:\n"), text.index("revision: 1")
        spec.write_text(text[:start] + text[end:])
        result = self.check()
        self.assertEqual(result.returncode, 1)
        self.assertIn("not recorded", result.stdout)

    def test_json(self):
        self.edit_intent("## Constraints\n", "## Constraints\nX.\n")
        doc = json.loads(self.specs("--json", "intent", "check", str(self.spec_dir)).stdout)
        self.assertIs(doc["ok"], False)
        self.assertEqual(doc["state"], "changed")
        self.assertEqual(doc["spec"], f"specs/{SPEC_ID}")


class RecordTest(IntentRepoTestCase):
    def test_record_then_unchanged_and_only_the_intent_block_moves(self):
        self.edit_intent("## Constraints\n", "## Constraints\nNo new PII.\n")
        spec = self.spec_dir / "spec.md"
        before = spec.read_text()
        result = self.specs("intent", "record", str(self.spec_dir))
        self.assertEqual(result.returncode, 0, result.stderr)
        self.assertEqual(self.check().returncode, 0)
        after = spec.read_text()

        def outside_intent(text):
            lines = text.splitlines()
            start = lines.index("intent:")
            end = next(i for i in range(start + 1, len(lines)) if not lines[i].startswith(" "))
            return lines[:start] + lines[end:]

        self.assertEqual(outside_intent(before), outside_intent(after))
        self.assertNotEqual(before, after)
        fm = parse_spec(spec).frontmatter["intent"]
        self.assertEqual((fm["file"], fm["recorded_by"]), ("intent.md", "jdoe"))

    def test_record_adds_a_missing_block(self):
        spec = self.spec_dir / "spec.md"
        text = spec.read_text()
        start, end = text.index("intent:\n"), text.index("revision: 1")
        spec.write_text(text[:start] + text[end:])
        self.assertEqual(self.specs("intent", "record", str(self.spec_dir)).returncode, 0)
        self.assertEqual(self.check().returncode, 0)

    def test_record_without_an_intent_file_is_a_usage_error(self):
        self.intent.unlink()
        self.assertEqual(self.specs("intent", "record", str(self.spec_dir)).returncode, 2)


class LintTest(IntentRepoTestCase):
    def test_changed_intent_is_reported_by_lint(self):
        self.assertEqual(self.specs("lint", str(self.spec_dir)).returncode, 0)
        self.edit_intent("## Constraints\n", "## Constraints\nX.\n")
        result = self.specs("lint", str(self.spec_dir))
        self.assertEqual(result.returncode, 1)
        self.assertIn("L016", result.stdout)
        self.assertIn("/sdlc:sync", result.stdout)


class SetTopLevelBlockTest(OfflineTestCase):
    def test_replaces_a_block_in_place(self):
        text = "---\nid: x\nintent:\n  file: a\n  old: 1\nrevision: 1\n---\nbody\n"
        self.assertEqual(
            set_top_level_block(text, "intent", ["file: a", "new: 2"]),
            "---\nid: x\nintent:\n  file: a\n  new: 2\nrevision: 1\n---\nbody\n",
        )

    def test_inserts_after_a_given_key_when_missing(self):
        text = "---\nid: x\ntitle: T\nrevision: 1\n---\n"
        self.assertEqual(
            set_top_level_block(text, "intent", ["file: a"], after="title"),
            "---\nid: x\ntitle: T\nintent:\n  file: a\nrevision: 1\n---\n",
        )

    def test_crlf_is_kept(self):
        text = "---\r\nintent:\r\n  file: a\r\n---\r\n"
        self.assertEqual(
            set_top_level_block(text, "intent", ["file: b"]), "---\r\nintent:\r\n  file: b\r\n---\r\n"
        )
