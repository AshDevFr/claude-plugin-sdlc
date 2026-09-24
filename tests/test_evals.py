import re
import subprocess
import sys
import unittest
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent
EVALS = ROOT / "evals"
COMMANDS = sorted(p.stem for p in (ROOT / "commands").glob("*.md"))
SKILLS = sorted(p.name for p in (ROOT / "skills").iterdir() if (p / "SKILL.md").is_file())


def table_names(text: str, heading: str, pattern: str) -> list[str]:
    """Names in the first column of the table under `## heading`."""
    section = text[text.index(f"## {heading}\n") :]
    section = section[: section.find("\n## ", 1)] if "\n## " in section[1:] else section
    return sorted(re.findall(pattern, section, flags=re.M))


class ReleaseDocsTest(unittest.TestCase):
    def test_readme_lists_every_command(self):
        readme = (ROOT / "README.md").read_text(encoding="utf-8")
        self.assertEqual(table_names(readme, "Commands", r"^\| `/sdlc:([a-z-]+)`"), COMMANDS)

    def test_readme_lists_every_skill(self):
        readme = (ROOT / "README.md").read_text(encoding="utf-8")
        self.assertEqual(table_names(readme, "Skills", r"^\| `([a-z-]+)`"), SKILLS)

    def test_changelog_has_the_release_naming_every_command(self):
        version = (ROOT / "tools" / "specs" / "VERSION").read_text().strip()
        changelog = (ROOT / "CHANGELOG.md").read_text(encoding="utf-8")
        entry = changelog[changelog.index(f"## {version}") :]
        entry = entry[: entry.find("\n## ", 1)] if "\n## " in entry[1:] else entry
        for command in COMMANDS:
            with self.subTest(command=command):
                self.assertIn(f"/sdlc:{command}", entry)


class ScenarioSuiteTest(unittest.TestCase):
    def setUp(self):
        sys.path.insert(0, str(EVALS))
        self.addCleanup(sys.path.remove, str(EVALS))
        import run

        self.run_module = run

    def test_every_command_has_a_scenario(self):
        covered = set()
        for name in self.run_module.names():
            covered |= set(self.run_module.load(name).COMMANDS)
        self.assertEqual(sorted(covered), COMMANDS)

    def test_every_scenario_is_complete(self):
        for name in self.run_module.names():
            with self.subTest(scenario=name):
                scenario = self.run_module.load(name)
                self.assertTrue(scenario.STEPS)
                self.assertTrue(callable(scenario.check))
                self.assertTrue(scenario.SANDBOX is None or isinstance(scenario.SANDBOX, str))

    def test_every_sandbox_and_setup_builds(self):
        # The same run without calling Claude: a broken setup fails here, for free.
        result = subprocess.run(
            [sys.executable, str(EVALS / "run.py"), "--dry-run"], capture_output=True, text=True, timeout=300
        )
        self.assertEqual(result.returncode, 0, result.stdout + result.stderr)
