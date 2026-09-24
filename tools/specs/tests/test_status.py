import json
import os
import shutil
import subprocess
import tempfile
import time
import unittest
from pathlib import Path

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


class StatusTestCase(OfflineTestCase):
    def setUp(self):
        super().setUp()
        self.root = Path(tempfile.mkdtemp())
        self.addCleanup(shutil.rmtree, self.root)
        self.git("init", "-q", "-b", "main")
        self.git("config", "user.name", "jdoe")
        (self.root / "specs").mkdir()
        (self.root / "specs" / "config.yml").write_text(CONFIG)
        self.git("add", "-A")
        self.git("commit", "-q", "-m", "init")

    def git(self, *args: str) -> str:
        result = subprocess.run(
            ["git", "-C", str(self.root), *args],
            env={**os.environ, **GIT_ENV},
            capture_output=True,
            text=True,
            check=True,
        )
        return result.stdout

    def specs(self, *args: str):
        return self.run_shim(*args, cwd=self.root, env=GIT_ENV)

    def new(self, slug: str, date: str = "2026-09-23") -> str:
        result = self.specs("new", "--date", date, "--title", slug, "--slug", slug)
        self.assertEqual(result.returncode, 0, result.stderr)
        return f"{date}-{slug}"

    def status(self) -> dict:
        result = self.specs("--json", "status")
        self.assertEqual(result.returncode, 0, result.stderr)
        return json.loads(result.stdout)


class StatusTest(StatusTestCase):
    def test_one_line_for_the_branch_spec(self):
        spec_id = self.new("webhook-retries")
        self.git("switch", "-q", "-c", f"jdoe/{spec_id}")
        result = self.specs("status")
        self.assertEqual(result.returncode, 0, result.stderr)
        self.assertEqual(result.stdout.strip(), f"{spec_id} r1: 0 lint finding(s), intent unchanged")
        doc = self.status()
        self.assertEqual(
            {k: doc[k] for k in ("spec", "revision", "lint_findings", "intent")},
            {"spec": spec_id, "revision": 1, "lint_findings": 0, "intent": "unchanged"},
        )

    def test_intent_change_and_lint_findings_show(self):
        spec_id = self.new("webhook-retries")
        self.git("switch", "-q", "-c", spec_id)
        intent = self.root / "specs" / spec_id / "intent.md"
        intent.write_text(intent.read_text() + "\nMore.\n")
        doc = self.status()
        self.assertEqual(doc["intent"], "changed")
        self.assertEqual(doc["lint_findings"], 1)  # L016

    def test_no_spec_for_the_branch(self):
        self.new("webhook-retries")
        self.git("switch", "-q", "-c", "chore/bump-deps")
        result = self.specs("status")
        self.assertEqual(result.returncode, 0)
        self.assertEqual(result.stdout.strip(), "no spec for this branch")

    def test_branch_with_no_commits_yet(self):
        fresh = Path(tempfile.mkdtemp())
        self.addCleanup(shutil.rmtree, fresh)
        subprocess.run(
            ["git", "init", "-q", "-b", "2026-09-23-first", str(fresh)],
            check=True,
            env={**os.environ, **GIT_ENV},
        )
        (fresh / "specs").mkdir()
        (fresh / "specs" / "config.yml").write_text(CONFIG)
        result = self.run_shim("status", cwd=fresh, env=GIT_ENV)
        self.assertEqual(result.stdout.strip(), "no spec for this branch")

    def test_detached_head(self):
        self.git("switch", "-q", "--detach")
        self.assertEqual(self.specs("status").stdout.strip(), "no branch")

    def test_longest_matching_id_wins(self):
        self.new("retries")
        longer = self.new("retries-v2")
        self.git("switch", "-q", "-c", longer)
        self.assertEqual(self.status()["spec"], longer)

    def test_ticket_spec_found_by_key(self):
        result = self.specs("new", "--key", "123", "--title", "Prorate plan changes")
        self.assertEqual(result.returncode, 0, result.stderr)
        self.git("switch", "-q", "-c", "123-prorate")
        doc = self.status()
        self.assertEqual(doc["spec"], "123-prorate-plan-changes")
        self.assertEqual(doc["intent"], "n/a")

    @unittest.skipIf(os.environ.get("SDLC_SKIP_TIMING"), "timing checks disabled")
    def test_fast_on_a_large_repo(self):
        spec_id = self.new("webhook-retries")
        source = (self.root / "specs" / spec_id / "spec.md").read_text()
        intent = (self.root / "specs" / spec_id / "intent.md").read_text()
        for n in range(199):
            other = f"2026-01-01-spec-{n:03d}"
            d = self.root / "specs" / other
            d.mkdir()
            (d / "spec.md").write_text(source.replace(spec_id, other))
            (d / "intent.md").write_text(intent)
        self.git("switch", "-q", "-c", spec_id)
        start = time.monotonic()
        result = self.specs("status")
        elapsed = time.monotonic() - start
        self.assertEqual(result.returncode, 0, result.stderr)
        self.assertTrue(result.stdout.startswith(f"{spec_id} r1:"), result.stdout)
        self.assertLess(elapsed, 1.0)


class IntentDefaultTest(StatusTestCase):
    def test_intent_commands_default_to_the_branch_spec(self):
        spec_id = self.new("webhook-retries")
        self.git("switch", "-q", "-c", spec_id)
        result = self.specs("intent", "check")
        self.assertEqual(result.returncode, 0, result.stderr)
        self.assertIn(f"specs/{spec_id}: intent unchanged", result.stdout)
        self.assertEqual(self.specs("intent", "assess").returncode, 0)

    def test_no_branch_spec_is_a_usage_error(self):
        self.new("webhook-retries")
        result = self.specs("intent", "check")
        self.assertEqual(result.returncode, 2)
        self.assertIn("SPEC_DIR", result.stderr)
