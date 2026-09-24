import json
import os
import shutil
import stat
import subprocess
import sys
import tempfile
import unittest
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent
HOOK = ROOT / "hooks" / "session-status.sh"
CONFIG = "tracker:\n  system: github\ncode_host:\n  system: github\n"
BASE_ENV = {
    **os.environ,
    # The helper's shim runs `python3`; put the interpreter running the tests first so it has PyYAML.
    "PATH": f"{Path(sys.executable).parent}{os.pathsep}{os.environ.get('PATH', '')}",
    "GIT_CONFIG_GLOBAL": os.devnull,
    "GIT_CONFIG_NOSYSTEM": "1",
    "GIT_AUTHOR_NAME": "jdoe",
    "GIT_AUTHOR_EMAIL": "jdoe@example.com",
    "GIT_COMMITTER_NAME": "jdoe",
    "GIT_COMMITTER_EMAIL": "jdoe@example.com",
}


class HookTestCase(unittest.TestCase):
    def setUp(self):
        self.repo = Path(tempfile.mkdtemp())
        self.addCleanup(shutil.rmtree, self.repo)

    def git(self, *args: str) -> None:
        subprocess.run(["git", "-C", str(self.repo), *args], check=True, env=BASE_ENV, capture_output=True)

    def hook(self, plugin_root: Path = ROOT, cwd: Path | None = None):
        env = {
            **BASE_ENV,
            "CLAUDE_PLUGIN_ROOT": str(plugin_root),
            "CLAUDE_PROJECT_DIR": str(cwd or self.repo),
        }
        return subprocess.run(
            ["sh", str(HOOK)], cwd=cwd or self.repo, env=env, capture_output=True, text=True, timeout=10
        )

    def make_specs_repo(self) -> None:
        self.git("init", "-q", "-b", "main")
        (self.repo / "specs").mkdir()
        (self.repo / "specs" / "config.yml").write_text(CONFIG)
        new = subprocess.run(
            [str(ROOT / "tools" / "specs" / "specs"), "new", "--date", "2026-09-23", "--title", "Retries"],
            cwd=self.repo,
            env=BASE_ENV,
            capture_output=True,
            text=True,
        )
        self.assertEqual(new.returncode, 0, new.stderr)
        self.git("add", "-A")
        self.git("commit", "-q", "-m", "spec")
        self.git("switch", "-q", "-c", "2026-09-23-retries")


class SessionHookTest(HookTestCase):
    def test_one_status_line_in_a_specs_repo(self):
        self.make_specs_repo()
        result = self.hook()
        self.assertEqual(result.returncode, 0, result.stderr)
        lines = result.stdout.splitlines()
        self.assertEqual(len(lines), 1, result.stdout)
        self.assertTrue(lines[0].startswith("sdlc: 2026-09-23-retries r1:"), lines[0])

    def test_silent_in_a_repo_without_specs(self):
        self.git("init", "-q")
        result = self.hook()
        self.assertEqual((result.returncode, result.stdout, result.stderr), (0, "", ""))

    def test_silent_outside_git(self):
        result = self.hook()
        self.assertEqual((result.returncode, result.stdout, result.stderr), (0, "", ""))

    def test_silent_when_the_helper_fails(self):
        self.make_specs_repo()
        stub_root = Path(tempfile.mkdtemp())
        self.addCleanup(shutil.rmtree, stub_root)
        stub = stub_root / "tools" / "specs" / "specs"
        stub.parent.mkdir(parents=True)
        stub.write_text("#!/bin/sh\necho 'specs: PyYAML is not installed' >&2\nexit 2\n")
        stub.chmod(stub.stat().st_mode | stat.S_IXUSR)
        result = self.hook(plugin_root=stub_root)
        self.assertEqual((result.returncode, result.stdout, result.stderr), (0, "", ""))


class RegistrationTest(unittest.TestCase):
    def test_session_start_runs_the_hook_with_a_timeout(self):
        config = json.loads((ROOT / "hooks" / "hooks.json").read_text())
        entries = config["hooks"]["SessionStart"]
        commands = [h for e in entries for h in e["hooks"]]
        self.assertEqual(len(commands), 1)
        self.assertEqual(commands[0]["type"], "command")
        self.assertIn("${CLAUDE_PLUGIN_ROOT}/hooks/session-status.sh", commands[0]["command"])
        self.assertLessEqual(commands[0]["timeout"], 5)
        self.assertEqual(set(config["hooks"]), {"SessionStart", "PostToolUse"})
