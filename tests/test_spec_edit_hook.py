import json
import os
import shutil
import subprocess
import sys
import tempfile
import unittest
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent
HOOK = ROOT / "hooks" / "spec-edit-reminder.sh"
HELPER = ROOT / "tools" / "specs" / "specs"
CONFIG = "tracker:\n  system: github\ncode_host:\n  system: github\n"
SPEC_ID = "2026-09-23-retries"
ENV = {
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


class SpecEditHookTest(unittest.TestCase):
    def setUp(self):
        self.tmp = Path(tempfile.mkdtemp())
        self.addCleanup(shutil.rmtree, self.tmp)
        self.repo = self.tmp / "repo"
        self.repo.mkdir()
        self.git("init", "-q", "-b", "main")
        (self.repo / "specs").mkdir()
        (self.repo / "specs" / "config.yml").write_text(CONFIG)
        (self.repo / "app.py").write_text("x = 1\n")
        self.git("add", "-A")
        self.git("commit", "-q", "-m", "init")
        self.git("switch", "-q", "-c", SPEC_ID)
        result = subprocess.run(
            [str(HELPER), "new", "--date", "2026-09-23", "--title", "Retries"],
            cwd=self.repo,
            env=ENV,
            capture_output=True,
            text=True,
        )
        self.assertEqual(result.returncode, 0, result.stderr)
        self.git("add", "-A")
        self.git("commit", "-q", "-m", "spec r1")
        self.spec = self.repo / "specs" / SPEC_ID / "spec.md"

    def git(self, *args: str) -> None:
        subprocess.run(["git", "-C", str(self.repo), *args], check=True, env=ENV, capture_output=True)

    def push(self) -> None:
        origin = self.tmp / "origin.git"
        subprocess.run(["git", "init", "-q", "--bare", str(origin)], check=True, env=ENV)
        self.git("remote", "add", "origin", str(origin))
        self.git("push", "-q", "-u", "origin", SPEC_ID)

    def edit_body(self) -> None:
        text = self.spec.read_text()
        self.spec.write_text(text.replace("## Goals\n", "## Goals\n- Retry failed deliveries.\n"))

    def hook(self, path: Path, plugin_root: Path = ROOT):
        event = {"hook_event_name": "PostToolUse", "tool_name": "Edit"}
        event["tool_input"] = {"file_path": str(path)}
        env = {**ENV, "CLAUDE_PLUGIN_ROOT": str(plugin_root), "CLAUDE_PROJECT_DIR": str(self.repo)}
        return subprocess.run(
            ["sh", str(HOOK)],
            input=json.dumps(event),
            cwd=self.repo,
            env=env,
            capture_output=True,
            text=True,
            timeout=15,
        )

    def test_reviewed_spec_edited_without_a_bump_gets_a_reminder(self):
        self.push()
        self.edit_body()
        result = self.hook(self.spec)
        self.assertEqual(result.returncode, 0, result.stderr)
        out = json.loads(result.stdout)
        self.assertIn("revision", out["systemMessage"])
        self.assertIn("## Revisions", out["hookSpecificOutput"]["additionalContext"])

    def test_bumped_revision_is_quiet(self):
        self.push()
        self.edit_body()
        text = self.spec.read_text().replace("revision: 1", "revision: 2")
        text = text.replace("## Revisions\n", "## Revisions\n- **r2** (2026-09-24, jdoe): goals filled in.\n")
        self.spec.write_text(text)
        result = self.hook(self.spec)
        self.assertEqual((result.returncode, result.stdout), (0, ""), result.stderr)

    def test_spec_not_pushed_is_quiet(self):
        self.edit_body()
        result = self.hook(self.spec)
        self.assertEqual((result.returncode, result.stdout), (0, ""), result.stderr)

    def test_other_files_never_call_the_helper(self):
        # A stand-in plugin whose helper records every call.
        plugin = self.tmp / "plugin"
        (plugin / "tools" / "specs").mkdir(parents=True)
        calls = self.tmp / "calls"
        stub = plugin / "tools" / "specs" / "specs"
        stub.write_text(f'#!/bin/sh\necho "$@" >> "{calls}"\nexit 1\n')
        stub.chmod(0o755)
        self.push()
        result = self.hook(self.repo / "app.py", plugin_root=plugin)
        self.assertEqual((result.returncode, result.stdout), (0, ""))
        self.assertFalse(calls.exists())
        self.hook(self.spec, plugin_root=plugin)
        self.assertTrue(calls.exists(), "the stub should be called for a spec, or this test proves nothing")

    def test_helper_failure_is_silent(self):
        self.push()
        self.edit_body()
        (self.repo / "specs" / "config.yml").write_text("tracker: [\n")
        result = self.hook(self.spec)
        self.assertEqual((result.returncode, result.stdout), (0, ""))


class HooksJsonTest(unittest.TestCase):
    def test_post_tool_use_entry_on_edits(self):
        hooks = json.loads((ROOT / "hooks" / "hooks.json").read_text())["hooks"]
        entry = hooks["PostToolUse"][0]
        self.assertEqual(entry["matcher"], "Edit|Write")
        command = entry["hooks"][0]
        self.assertEqual(command["command"], '"${CLAUDE_PLUGIN_ROOT}/hooks/spec-edit-reminder.sh"')
        self.assertLessEqual(command["timeout"], 10)
