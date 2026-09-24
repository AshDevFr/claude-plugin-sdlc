import re
import unittest
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent
DOC = ROOT / "docs" / "adoption.md"
WORKFLOW = ROOT / "docs" / "workflow.md"
# The order a first change meets the commands in.
FIRST_CHANGE = ["start", "clarify", "propose", "plan", "implement", "check", "converge", "pr-msg"]


class AdoptionDocTest(unittest.TestCase):
    def setUp(self):
        self.text = DOC.read_text(encoding="utf-8")

    def test_getting_started(self):
        for needle in ("claude plugin install", "/sdlc:init", "docs/workflow.md"):
            with self.subTest(needle=needle):
                self.assertIn(needle, self.text)

    def test_first_change_in_order(self):
        section = self.text[self.text.index("## Your first change") :]
        positions = [section.find(f"/sdlc:{name}") for name in FIRST_CHANGE]
        self.assertNotIn(-1, positions, dict(zip(FIRST_CHANGE, positions, strict=True)))
        self.assertEqual(positions, sorted(positions))

    def test_every_workflow_metric_has_a_way_to_measure_it(self):
        # The metrics are the workflow's section 12; the guide says how to read each by hand.
        workflow = WORKFLOW.read_text(encoding="utf-8")
        metrics = re.findall(r"^- \*\*(.+?):\*\*", workflow[workflow.index("## 12.") :], flags=re.M)
        self.assertGreaterEqual(len(metrics), 5)
        section = self.text[self.text.index("## Is it working?") :]
        for metric in metrics:
            with self.subTest(metric=metric):
                self.assertIn(metric, section)

    def test_nothing_enforced_and_no_ci_jobs(self):
        self.assertIn("enforce", self.text)
        for word in ("nightly", "spec-approval", "spec-required", "pipeline", "pilot team"):
            with self.subTest(word=word):
                self.assertNotIn(word, self.text.lower())
