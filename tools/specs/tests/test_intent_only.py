import json
import os
import shutil
import subprocess
import tempfile
from pathlib import Path

from tests.base import OfflineTestCase

CONFIG = "tracker:\n  system: github\ncode_host:\n  system: github\n"
GIT_ENV = {
    "GIT_CONFIG_GLOBAL": os.devnull,
    "GIT_CONFIG_NOSYSTEM": "1",
    "GIT_AUTHOR_NAME": "jdoe",
    "GIT_AUTHOR_EMAIL": "jdoe@example.com",
    "GIT_COMMITTER_NAME": "jdoe",
    "GIT_COMMITTER_EMAIL": "jdoe@example.com",
}
ID = "2026-09-24-webhook-retries"


class IntentOnlyTestCase(OfflineTestCase):
    def setUp(self):
        super().setUp()
        self.root = Path(tempfile.mkdtemp())
        self.addCleanup(shutil.rmtree, self.root)
        self.git("init", "-q", "-b", "main")
        (self.root / "specs").mkdir()
        (self.root / "specs" / "config.yml").write_text(CONFIG)
        self.git("add", "-A")
        self.git("commit", "-q", "-m", "init")

    def git(self, *args):
        subprocess.run(
            ["git", "-C", str(self.root), *args],
            env={**os.environ, **GIT_ENV},
            check=True,
            capture_output=True,
        )

    def specs(self, *args):
        return self.run_shim(*args, cwd=self.root, env=GIT_ENV)

    def intent_new(self, *extra):
        return self.specs(
            "--json", "intent", "new", "--title", "Webhook retries", "--date", "2026-09-24", *extra
        )


class IntentNewTest(IntentOnlyTestCase):
    def test_into_the_intents_directory_when_there_is_one(self):
        (self.root / "intents").mkdir()
        result = self.intent_new()
        self.assertEqual(result.returncode, 0, result.stderr)
        doc = json.loads(result.stdout)
        self.assertEqual((doc["path"], doc["id"], doc["location"]), (f"intents/{ID}.md", ID, "intents"))
        self.assertTrue(
            (self.root / "intents" / f"{ID}.md").read_text().startswith("# Intent: Webhook retries")
        )
        self.assertFalse((self.root / "specs" / ID).exists())

    def test_into_an_intent_only_spec_directory_otherwise(self):
        result = self.intent_new()
        self.assertEqual(result.returncode, 0, result.stderr)
        doc = json.loads(result.stdout)
        self.assertEqual((doc["path"], doc["location"]), (f"specs/{ID}/intent.md", "spec-dir"))
        self.assertEqual(sorted(p.name for p in (self.root / "specs" / ID).iterdir()), ["intent.md"])

    def test_an_existing_intent_is_never_overwritten(self):
        self.assertEqual(self.intent_new().returncode, 0)
        again = self.intent_new()
        self.assertEqual(again.returncode, 1)
        self.assertIn("already exists", again.stderr)


class IntentOnlyStateTest(IntentOnlyTestCase):
    def setUp(self):
        super().setUp()
        self.assertEqual(self.intent_new().returncode, 0)

    def test_lint_has_nothing_to_say(self):
        result = self.specs("lint")
        self.assertEqual(result.returncode, 0, result.stdout + result.stderr)
        explicit = self.specs("lint", f"specs/{ID}")
        self.assertEqual(explicit.returncode, 0, explicit.stdout + explicit.stderr)

    def test_check_all_and_coverage_skip_it(self):
        check = self.specs("--json", "check", "--all")
        self.assertEqual(json.loads(check.stdout)["specs"], [])
        self.assertEqual(self.specs("coverage").returncode, 0)

    def test_status_on_its_branch(self):
        self.git("switch", "-q", "-c", ID)
        self.assertEqual(self.specs("status").stdout.strip(), f"{ID}: intent only, no spec yet")
        doc = json.loads(self.specs("--json", "status").stdout)
        self.assertEqual((doc["spec"], doc["intent"]), (ID, "intent only"))


class AdoptTest(IntentOnlyTestCase):
    def test_new_writes_the_spec_beside_the_existing_intent(self):
        self.assertEqual(self.intent_new().returncode, 0)
        intent = self.root / "specs" / ID / "intent.md"
        intent.write_text(intent.read_text() + "\nPartners miss events when their endpoint is down.\n")
        before = intent.read_bytes()
        result = self.specs(
            "new", "--title", "Webhook retries", "--date", "2026-09-24", "--slug", "webhook-retries"
        )
        self.assertEqual(result.returncode, 0, result.stderr)
        self.assertEqual(intent.read_bytes(), before)
        self.assertTrue((self.root / "specs" / ID / "spec.md").is_file())
        self.assertIn("unchanged", self.specs("intent", "check", f"specs/{ID}").stdout)

    def test_a_different_intent_file_is_still_refused(self):
        self.assertEqual(self.intent_new().returncode, 0)
        other = self.root / "other.md"
        other.write_text("# Intent: other\n")
        result = self.specs(
            "new",
            "--title",
            "x",
            "--date",
            "2026-09-24",
            "--slug",
            "webhook-retries",
            "--intent-file",
            str(other),
        )
        self.assertEqual(result.returncode, 1)
        self.assertFalse((self.root / "specs" / ID / "spec.md").exists())

    def test_a_full_spec_directory_is_still_refused(self):
        result = self.specs("new", "--title", "x", "--date", "2026-09-24", "--slug", "webhook-retries")
        self.assertEqual(result.returncode, 0, result.stderr)
        again = self.specs("new", "--title", "x", "--date", "2026-09-24", "--slug", "webhook-retries")
        self.assertEqual(again.returncode, 1)


class TicketFallbackTest(IntentOnlyTestCase):
    def test_a_date_branch_isnt_read_as_a_ticket_pointing_at_an_intent(self):
        # On a GitHub tracker, "2026-..." also parses as ticket #2026, whose prefix matches any
        # date-named directory; only a directory with a spec may come back from that fallback.
        self.assertEqual(self.intent_new().returncode, 0)
        self.git("switch", "-q", "-c", "2026-other-work")
        result = self.specs("status")
        self.assertEqual(result.returncode, 0, result.stderr)
        self.assertEqual(result.stdout.strip(), "no spec for this branch")
