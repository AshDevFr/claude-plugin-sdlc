import json
import os
import shutil
import subprocess
import tempfile
from pathlib import Path

from tests.base import OfflineTestCase

FIXTURES = Path(__file__).resolve().parent / "fixtures" / "intent"
CONFIG = """tracker:
  system: github
code_host:
  system: github
"""
GIT_ENV = {"GIT_CONFIG_GLOBAL": os.devnull, "GIT_CONFIG_NOSYSTEM": "1"}
TEMPLATE_SECTIONS = [
    "Problem",
    "Proposed outcome",
    "Affected users and systems",
    "Constraints",
    "Open questions",
]


class AssessTestCase(OfflineTestCase):
    def setUp(self):
        super().setUp()
        self.root = Path(tempfile.mkdtemp())
        self.addCleanup(shutil.rmtree, self.root)
        subprocess.run(["git", "init", "-q", str(self.root)], check=True, env={**os.environ, **GIT_ENV})
        subprocess.run(["git", "-C", str(self.root), "config", "user.name", "jdoe"], check=True)
        (self.root / "specs").mkdir()
        (self.root / "specs" / "config.yml").write_text(CONFIG)

    def specs(self, *args: str):
        return self.run_shim(*args, cwd=self.root, env=GIT_ENV)

    def assess_text(self, text: str) -> dict:
        path = self.root / "request.md"
        path.write_text(text)
        result = self.specs("--json", "intent", "assess", "--file", str(path))
        self.assertEqual(result.returncode, 0, result.stderr)
        return json.loads(result.stdout)

    @staticmethod
    def states(doc: dict) -> dict:
        return {entry["section"]: entry["state"] for entry in doc["sections"]}


class AssessTest(AssessTestCase):
    def test_missing_and_empty_sections_are_listed_and_exit_is_zero(self):
        text = (FIXTURES / "claims-status.md").read_text()
        text = text.replace(
            "## Problem\nCustomers phone the contact center to ask where their claim is.\n"
            "Handlers spend roughly a third of call time on status-only queries.\n",
            "",
        )
        text = text.replace(
            "## Constraints\nNo new PII in the portal session. Existing authentication only.\n",
            "## Constraints\n",
        )
        path = self.root / "request.md"
        path.write_text(text)
        result = self.specs("intent", "assess", "--file", str(path))
        self.assertEqual(result.returncode, 0, result.stderr)
        self.assertIn("Problem: missing", result.stdout)
        self.assertIn("Constraints: empty", result.stdout)

    def test_fresh_template_is_all_template(self):
        self.assertEqual(self.specs("new", "--date", "2026-09-23", "--title", "Retries").returncode, 0)
        result = self.specs("--json", "intent", "assess", str(self.root / "specs" / "2026-09-23-retries"))
        self.assertEqual(result.returncode, 0, result.stderr)
        states = self.states(json.loads(result.stdout))
        self.assertEqual({states[s] for s in TEMPLATE_SECTIONS}, {"template"})

    def test_playbook_example_is_complete_with_one_open_question(self):
        doc = self.assess_text((FIXTURES / "claims-status.md").read_text())
        states = self.states(doc)
        self.assertEqual({states[s] for s in TEMPLATE_SECTIONS}, {"ok"})
        self.assertEqual(states["Title"], "ok")
        self.assertEqual(states["Author"], "ok")
        self.assertEqual(doc["open_questions"], ["Do third-party loss adjusters need access too?"])

    def test_json_shape(self):
        doc = self.assess_text((FIXTURES / "claims-status.md").read_text())
        self.assertEqual(set(doc), {"ok", "sections", "open_questions"})
        for entry in doc["sections"]:
            self.assertEqual(set(entry), {"section", "state"})
            self.assertIn(entry["state"], {"missing", "empty", "template", "ok"})

    def test_team_template_adds_sections(self):
        templates = self.root / "specs" / "templates"
        templates.mkdir()
        template = (
            Path(__file__).resolve().parent.parent / "sdlc_specs" / "templates" / "intent.md"
        ).read_text()
        (templates / "intent.md").write_text(template + "\n## Success signals\nHow we will know it worked.\n")
        states = self.states(self.assess_text((FIXTURES / "claims-status.md").read_text()))
        self.assertEqual(states["Success signals"], "missing")

    def test_open_questions_forms(self):
        base = (
            (FIXTURES / "claims-status.md")
            .read_text()
            .replace(
                "## Open questions\nDo third-party loss adjusters need access too?\n", "## Open questions\n{}"
            )
        )
        cases = {
            "- One? (PM)\n- Two? (Legal)\n": ["One? (PM)", "Two? (Legal)"],
            "First question,\nstill the first.\n\nSecond question.\n": [
                "First question, still the first.",
                "Second question.",
            ],
            "None.\n": [],
            "": [],
        }
        for body, expected in cases.items():
            with self.subTest(body=body):
                self.assertEqual(self.assess_text(base.format(body))["open_questions"], expected)

    def test_missing_file_is_a_usage_error(self):
        self.assertEqual(self.specs("intent", "assess", "--file", "nope.md").returncode, 2)
