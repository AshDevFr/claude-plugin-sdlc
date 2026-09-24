import json
import os
import runpy
import shutil
import subprocess
import sys
import tempfile
import time
import unittest
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent
SANDBOX = ROOT / "bin" / "sdlc-sandbox"
HELPER = ROOT / "tools" / "specs" / "specs"
SCENARIOS = ROOT / "sandbox" / "scenarios"
NAMES = (
    "fresh-intent",
    "weak-intent",
    "open-questions",
    "intent-changed-no-impact",
    "intent-changed-impact",
    "merged-spec-intent-change",
)
ENV = {**os.environ, "GIT_CONFIG_GLOBAL": os.devnull, "GIT_CONFIG_NOSYSTEM": "1"}


def run(*argv, cwd=None):
    return subprocess.run([sys.executable, *map(str, argv)], cwd=cwd, env=ENV, capture_output=True, text=True)


class SandboxTestCase(unittest.TestCase):
    def setUp(self):
        self.parent = Path(tempfile.mkdtemp())
        self.addCleanup(shutil.rmtree, self.parent)
        self.dir = self.parent / "sb"

    def build(self, scenario=None):
        argv = [SANDBOX, self.dir] + (["--scenario", scenario] if scenario else [])
        result = run(*argv)
        self.assertEqual(result.returncode, 0, result.stderr)
        return result

    def git(self, *args):
        return subprocess.run(["git", "-C", str(self.dir), *args], env=ENV, capture_output=True, text=True)

    def helper(self, *args):
        return run(HELPER, *args, cwd=self.dir)


class ScenarioTest(SandboxTestCase):
    def test_every_scenario_has_steps_and_a_readme(self):
        self.assertEqual(sorted(p.name for p in SCENARIOS.iterdir() if p.is_dir()), sorted(NAMES))
        for name in NAMES:
            with self.subTest(scenario=name):
                self.assertTrue((SCENARIOS / name / "steps.py").is_file())
                self.assertTrue((SCENARIOS / name / "README.md").is_file())

    def test_scenarios_report_what_they_promise(self):
        for name in NAMES:
            with self.subTest(scenario=name):
                self.setUp()
                expected = runpy.run_path(str(SCENARIOS / name / "steps.py"))["EXPECTED"]
                start = time.monotonic()
                self.build(name)
                self.assertLess(time.monotonic() - start, 5.0)

                lint = self.helper("--json", "lint")
                self.assertEqual(lint.returncode, expected["lint_exit"], lint.stdout)
                rules = sorted({f["rule"] for f in json.loads(lint.stdout)["findings"]})
                self.assertEqual(rules, expected.get("lint_rules", []))

                spec = expected.get("spec")
                if spec is None:
                    self.assertEqual(
                        [p.name for p in (self.dir / "specs").iterdir() if p.is_dir()], ["templates"]
                    )
                    continue
                check = self.helper("--json", "intent", "check", f"specs/{spec}")
                self.assertEqual(json.loads(check.stdout)["state"], expected["intent"])

    def test_readme_states_the_expected_intent_state(self):
        for name in NAMES:
            with self.subTest(scenario=name):
                expected = runpy.run_path(str(SCENARIOS / name / "steps.py"))["EXPECTED"]
                readme = (SCENARIOS / name / "README.md").read_text()
                if expected.get("intent"):
                    self.assertIn(f"intent `{expected['intent']}`", readme)


class RepoTest(SandboxTestCase):
    def test_push_goes_to_the_local_bare_repo_only(self):
        self.build("fresh-intent")
        remotes = self.git("remote").stdout.split()
        self.assertEqual(remotes, ["origin"])
        url = self.git("remote", "get-url", "origin").stdout.strip()
        self.assertTrue(Path(url).is_dir() and url.endswith(".git"), url)
        (self.dir / "NOTES.md").write_text("x\n")
        self.git("add", "NOTES.md")
        self.git("-c", "user.name=t", "-c", "user.email=t@e", "commit", "-q", "-m", "note")
        push = self.git("push", "-q", "origin", "HEAD")
        self.assertEqual(push.returncode, 0, push.stderr)
        head = self.git("rev-parse", "HEAD").stdout.strip()
        remote_head = subprocess.run(
            ["git", "--git-dir", url, "rev-parse", "main"], env=ENV, capture_output=True, text=True
        ).stdout.strip()
        self.assertEqual(remote_head, head)

    def test_the_app_and_its_tests_are_there(self):
        self.build()
        self.assertTrue((self.dir / "specs" / "config.yml").is_file())
        tests = subprocess.run(
            [sys.executable, "-m", "unittest", "discover", "-s", "tests"],
            cwd=self.dir,
            capture_output=True,
            text=True,
        )
        self.assertEqual(tests.returncode, 0, tests.stderr)

    def test_refuses_a_non_empty_directory(self):
        self.dir.mkdir()
        (self.dir / "keep.txt").write_text("mine\n")
        result = run(SANDBOX, self.dir)
        self.assertEqual(result.returncode, 2)
        self.assertEqual((self.dir / "keep.txt").read_text(), "mine\n")


class MutateTest(SandboxTestCase):
    def test_edit_intent_changes_the_intent_state(self):
        self.build("open-questions")
        spec = runpy.run_path(str(SCENARIOS / "open-questions" / "steps.py"))["EXPECTED"]["spec"]
        before = json.loads(self.helper("--json", "intent", "check", f"specs/{spec}").stdout)["state"]
        self.assertEqual(before, "unchanged")
        result = run(SANDBOX, "mutate", self.dir, "edit-intent")
        self.assertEqual(result.returncode, 0, result.stderr)
        after = json.loads(self.helper("--json", "intent", "check", f"specs/{spec}").stdout)["state"]
        self.assertEqual(after, "changed")

    def test_commit_and_new_branch(self):
        self.build("fresh-intent")
        (self.dir / "x.txt").write_text("x\n")
        self.assertEqual(run(SANDBOX, "mutate", self.dir, "commit").returncode, 0)
        self.assertEqual(self.git("status", "--porcelain").stdout, "")
        self.assertEqual(run(SANDBOX, "mutate", self.dir, "new-branch", "feature-x").returncode, 0)
        self.assertEqual(self.git("branch", "--show-current").stdout.strip(), "feature-x")
