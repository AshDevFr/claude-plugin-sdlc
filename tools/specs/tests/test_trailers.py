import json
import os
import re
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
SPEC_ID = "2026-09-23-retries"
CRITERIA = (
    "- **AC-1** Given a 503, when delivering, then the delivery is retried.\n"
    "- **AC-2** Given a 400, when delivering, then the delivery is not retried.\n"
    "- ~~**AC-3** Retries are capped at five.~~ Dropped: the backoff already bounds them.\n"
)
REPO = Path(__file__).resolve().parents[3]


class TrailersTestCase(OfflineTestCase):
    def setUp(self):
        super().setUp()
        self.root = Path(tempfile.mkdtemp())
        self.addCleanup(shutil.rmtree, self.root)
        self.git("init", "-q", "-b", "main")
        (self.root / "specs").mkdir()
        (self.root / "specs" / "config.yml").write_text(CONFIG)
        result = self.specs("new", "--date", "2026-09-23", "--title", "Retries", "--slug", "retries")
        self.assertEqual(result.returncode, 0, result.stderr)
        path = self.root / "specs" / SPEC_ID / "spec.md"
        text = path.read_text().replace("revision: 1", "revision: 2")
        start = text.index("- **AC-1**")
        text = text[:start] + CRITERIA + text[text.index("\n", start) + 1 :]
        path.write_text(text)
        self.git("add", "-A")
        self.git("commit", "-q", "-m", "base")

    def git(self, *args) -> str:
        return subprocess.run(
            ["git", "-C", str(self.root), *args],
            env={**os.environ, **GIT_ENV},
            check=True,
            capture_output=True,
            text=True,
        ).stdout

    def specs(self, *args):
        return self.run_shim(*args, cwd=self.root, env=GIT_ENV)

    def trailers(self, *args):
        return self.specs("trailers", f"specs/{SPEC_ID}", *args)

    def commit(self, message: str) -> None:
        self.git("commit", "-q", "--allow-empty", "-m", message)


class BuildTest(TrailersTestCase):
    def test_spec_and_implements(self):
        result = self.trailers("--implements", "AC-1,AC-2")
        self.assertEqual(result.returncode, 0, result.stderr)
        self.assertEqual(result.stdout, f"Spec: {SPEC_ID}@r2\nImplements: AC-1, AC-2\n")

    def test_spec_alone(self):
        result = self.trailers()
        self.assertEqual(result.stdout, f"Spec: {SPEC_ID}@r2\n")

    def test_spec_change(self):
        result = self.trailers("--spec-change", "clarify")
        self.assertEqual(result.stdout, f"Spec: {SPEC_ID}@r2\nSpec-Change: clarify\n")

    def test_struck_criterion_is_refused(self):
        result = self.trailers("--implements", "AC-1,AC-3")
        self.assertEqual(result.returncode, 1)
        self.assertIn("AC-3", result.stderr)
        self.assertIn("struck", result.stderr)
        self.assertEqual(result.stdout, "")

    def test_unknown_criterion_is_refused(self):
        result = self.trailers("--implements", "AC-9")
        self.assertEqual(result.returncode, 1)
        self.assertIn("AC-9", result.stderr)

    def test_malformed_criterion_is_a_usage_error(self):
        result = self.trailers("--implements", "first one")
        self.assertEqual(result.returncode, 2)

    def test_unknown_kind_is_refused(self):
        result = self.trailers("--spec-change", "bogus")
        self.assertEqual(result.returncode, 1)
        self.assertIn("bogus", result.stderr)

    def test_branch_spec_is_the_default(self):
        self.git("switch", "-q", "-c", SPEC_ID)
        result = self.specs("trailers")
        self.assertEqual(result.stdout, f"Spec: {SPEC_ID}@r2\n")

    def test_json(self):
        result = self.trailers("--json", "--implements", "AC-2")
        doc = json.loads(result.stdout)
        self.assertEqual(doc["spec"], SPEC_ID)
        self.assertEqual(doc["revision"], 2)
        self.assertEqual(doc["implements"], ["AC-2"])
        self.assertEqual(doc["trailers"], [f"Spec: {SPEC_ID}@r2", "Implements: AC-2"])

    def test_git_parses_every_trailer(self):
        printed = self.trailers("--implements", "AC-1,AC-2", "--spec-change", "amend").stdout
        message = f"feat: retry deliveries\n\nWhy it changed.\n\n{printed}"
        parsed = subprocess.run(
            ["git", "interpret-trailers", "--parse"],
            input=message,
            capture_output=True,
            text=True,
            check=True,
        ).stdout
        self.assertEqual(parsed, printed)


class FromLogTest(TrailersTestCase):
    def test_criteria_from_this_specs_commits(self):
        base = self.git("rev-parse", "HEAD").strip()
        self.commit(f"feat: one\n\nSpec: {SPEC_ID}@r2\nImplements: AC-1\n")
        self.commit(f"feat: two\n\nSpec: {SPEC_ID}@r2\nImplements: AC-2, AC-1\n")
        self.commit("feat: other\n\nSpec: 2026-09-01-other@r1\nImplements: AC-3\n")
        result = self.trailers("--from-log", base)
        self.assertEqual(result.returncode, 0, result.stderr)
        self.assertEqual(result.stdout, f"Spec: {SPEC_ID}@r2\nImplements: AC-1, AC-2\n")

    def test_criterion_struck_since_is_left_out_with_a_warning(self):
        base = self.git("rev-parse", "HEAD").strip()
        self.commit(f"feat: cap\n\nSpec: {SPEC_ID}@r1\nImplements: AC-3, AC-1\n")
        result = self.trailers("--from-log", base)
        self.assertEqual(result.returncode, 0, result.stderr)
        self.assertEqual(result.stdout, f"Spec: {SPEC_ID}@r2\nImplements: AC-1\n")
        self.assertIn("AC-3 is struck", result.stderr)

    def test_no_commits_means_no_implements(self):
        result = self.trailers("--from-log", "HEAD")
        self.assertEqual(result.stdout, f"Spec: {SPEC_ID}@r2\n")

    def test_unknown_base_is_a_usage_error(self):
        result = self.trailers("--from-log", "no-such-ref")
        self.assertEqual(result.returncode, 2)


class KindsTest(OfflineTestCase):
    def test_kinds_match_the_commit_conventions_skill(self):
        from sdlc_specs.trailers import SPEC_CHANGE_KINDS

        skill = (REPO / "skills" / "commit-conventions" / "SKILL.md").read_text()
        section = skill[skill.index("## Spec-Change kinds") :]
        section = section[: section.index("\n## ", 1)]
        listed = re.findall(r"^- `([a-z]+)`:", section, re.MULTILINE)
        self.assertEqual(sorted(listed), sorted(SPEC_CHANGE_KINDS))
