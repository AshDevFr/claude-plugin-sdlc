import re
import unittest
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent
DOC = ROOT / "docs" / "workflow.md"

MVP_COMMANDS = {
    "/sdlc:init",
    "/sdlc:start",
    "/sdlc:clarify",
    "/sdlc:analyze",
    "/sdlc:check",
    "/sdlc:sync",
    "/sdlc:plan",
    "/sdlc:implement",
    "/sdlc:bug",
    "/sdlc:converge",
    "/sdlc:handoff",
    "/sdlc:propose",
    "/sdlc:commit-msg",
    "/sdlc:pr-msg",
}
# Checks the first version of the workflow shipped as CI jobs. None ships now; teams may add
# their own, which is the only section allowed to discuss CI checks.
WITHDRAWN = ("nightly", "spec-approval", "spec-staleness", "spec-gate", "spec-required", "ac-coverage")


def top_sections(text: str) -> dict[str, str]:
    parts = re.split(r"^## ", text, flags=re.M)
    return {part.split("\n", 1)[0]: part for part in parts[1:]}


class WorkflowDocTest(unittest.TestCase):
    def setUp(self):
        self.text = DOC.read_text(encoding="utf-8")
        self.sections = top_sections(self.text)

    def optional_ci_heading(self) -> str:
        headings = [h for h in self.sections if "own CI" in h]
        self.assertEqual(len(headings), 1, list(self.sections))
        return headings[0]

    def test_no_shipped_ci_checks_outside_the_optional_ci_section(self):
        optional = self.optional_ci_heading()
        for heading, body in self.sections.items():
            if heading == optional:
                continue
            for word in WITHDRAWN:
                with self.subTest(section=heading, word=word):
                    self.assertNotIn(word, body)

    def test_command_table_is_the_mvp_surface(self):
        plugin = next(body for heading, body in self.sections.items() if heading.startswith("9."))
        table = re.search(r"^\| Command \|.*?(?=\n\n)", plugin, flags=re.M | re.S)
        self.assertIsNotNone(table)
        first_cells = [row.split("|")[1] for row in table.group(0).splitlines()[2:]]
        commands = {m for cell in first_cells for m in re.findall(r"/sdlc:[a-z-]+", cell)}
        self.assertEqual(commands, MVP_COMMANDS)

    def test_codeowners_guidance_is_applied_by_the_team(self):
        self.assertIn("The team applies", self.text)
        self.assertIn("`/sdlc:init` only prints", self.text)

    def test_the_model(self):
        self.assertIn("`spec.md` is the contract", self.text)
        self.assertIn("`intent.md` is the original request", self.text)
        self.assertIn("Nothing gates on the quality of an intent", self.text)

    def test_section_numbers_are_stable(self):
        numbers = [h.split(".", 1)[0] for h in self.sections if re.match(r"\d+\.", h)]
        self.assertEqual(numbers, [str(n) for n in range(1, 13)])
