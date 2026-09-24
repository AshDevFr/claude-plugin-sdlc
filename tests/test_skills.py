import re
import unittest
from pathlib import Path

import yaml

ROOT = Path(__file__).resolve().parent.parent
SKILLS = ROOT / "skills"
HELPER_TEMPLATES = ROOT / "tools" / "specs" / "sdlc_specs" / "templates"
NAMES = (
    "workflow",
    "spec-template",
    "commit-conventions",
    "intent-writing",
    "intent-sync",
    "test-first",
    "receiving-review",
    "finishing-work",
)
PLATFORMS = ("GitLab", "GitHub", "Linear")
SPEC_CHANGE_KINDS = ("initial", "clarify", "amend", "acknowledge", "supersede")


def read(name: str) -> tuple[dict, str]:
    text = (SKILLS / name / "SKILL.md").read_text(encoding="utf-8")
    _, front, body = text.split("---\n", 2)
    return yaml.safe_load(front), body


def sections(body: str) -> list[tuple[str, str]]:
    """(heading, text) pairs; text before the first heading has an empty heading."""
    parts = re.split(r"^(#{1,6} .*)$", body, flags=re.M)
    out = [("", parts[0])]
    out += [(parts[i].lstrip("# ").strip(), parts[i + 1]) for i in range(1, len(parts), 2)]
    return out


class SkillFrontmatterTest(unittest.TestCase):
    def test_every_skill_says_when_to_load_it(self):
        for name in NAMES:
            with self.subTest(skill=name):
                front, body = read(name)
                self.assertEqual(front["name"], name)
                self.assertIn("Use when", front["description"])
                self.assertTrue(body.strip())


class TemplateReferenceTest(unittest.TestCase):
    def test_templates_are_referenced_not_copied(self):
        for name, template in (("spec-template", "spec.md"), ("intent-writing", "intent.md")):
            with self.subTest(skill=name):
                _, body = read(name)
                self.assertIn(f"tools/specs/sdlc_specs/templates/{template}", body)
                self.assertIn(f"templates/{template}", body)
                self.assertTrue((HELPER_TEMPLATES / template).is_file())
                self.assertFalse((SKILLS / name / template).exists())

    def test_intent_sections_follow_the_template_order(self):
        template_headings = re.findall(r"^## (.+)$", (HELPER_TEMPLATES / "intent.md").read_text(), flags=re.M)
        _, body = read("intent-writing")
        positions = [body.find(f"**{h}**") for h in template_headings]
        self.assertNotIn(-1, positions, template_headings)
        self.assertEqual(positions, sorted(positions))


class PlatformNeutralTest(unittest.TestCase):
    def test_platforms_only_in_per_system_sections(self):
        for name in NAMES:
            _, body = read(name)
            for heading, text in sections(body):
                if "per-system" in heading.lower():
                    continue
                for platform in PLATFORMS:
                    with self.subTest(skill=name, section=heading, platform=platform):
                        self.assertNotIn(platform, text)


class ConventionsTest(unittest.TestCase):
    def test_each_spec_change_kind_is_defined_once(self):
        _, body = read("commit-conventions")
        for kind in SPEC_CHANGE_KINDS:
            with self.subTest(kind=kind):
                self.assertEqual(len(re.findall(rf"^- `{kind}`:", body, flags=re.M)), 1)

    def test_workflow_names_the_helper_and_its_exit_2_rule(self):
        _, body = read("workflow")
        self.assertIn('"${CLAUDE_PLUGIN_ROOT}/tools/specs/specs"', body)
        self.assertIn("exits 2", body)


class IntentSyncTest(unittest.TestCase):
    CASES = ("**A**", "**B**", "**C1**", "**C2**", "**D**", "**Spec wrong**", "**Scope found**")

    def test_every_case_has_a_row_naming_its_path(self):
        _, body = read("intent-sync")
        rows = [line for line in body.splitlines() if line.startswith("| **")]
        for case in self.CASES:
            with self.subTest(case=case):
                row = next((r for r in rows if r.startswith(f"| {case} |")), None)
                self.assertIsNotNone(row, f"no table row for {case}")
                self.assertRegex(row, r"/sdlc:(sync|start)|n/a")

    def test_kinds_named_are_known(self):
        _, body = read("intent-sync")
        for kind in re.findall(r"`Spec-Change: ([a-z]+)`", body):
            self.assertIn(kind, SPEC_CHANGE_KINDS)

    def test_offline_and_advisory_only(self):
        # The change lane needs nothing beyond git; nothing is sent anywhere.
        _, body = read("intent-sync")
        for word in (r"ticket", r"tracker", r"\bMCP\b", r"\bCI\b", r"nightly", r"\bpost(s|ed|ing)?\b"):
            with self.subTest(word=word):
                self.assertIsNone(re.search(word, body, flags=re.I))


class PortedSkillsTest(unittest.TestCase):
    PORTED = ("test-first", "receiving-review")

    def test_no_sdd_workflow_left(self):
        # Ported from a personal workflow with task files and a spec repo; none of it applies here.
        for name in self.PORTED:
            _, body = read(name)
            for pattern in (r"task file", r"\.specs/docs", r"phase-[0-9]", r"/sdd:", r"ticket"):
                with self.subTest(skill=name, pattern=pattern):
                    self.assertIsNone(re.search(pattern, body, flags=re.I))

    def test_test_first_shows_the_citation_form(self):
        _, body = read("test-first")
        self.assertRegex(body, r"\b\d{4}-\d{2}-\d{2}-[a-z0-9-]+:AC-\d+\b")
        self.assertIn("<spec-id>:AC-n", body)


class FinishingWorkTest(unittest.TestCase):
    CHECK = ROOT / "tools" / "specs" / "sdlc_specs" / "check.py"
    CONVERGE = ROOT / "commands" / "converge.md"

    def test_checklist_covers_every_check_and_verdict(self):
        # The checklist must not drift from the tools it describes: a new readiness reason or
        # verdict without a checklist line fails here.
        source = self.CHECK.read_text(encoding="utf-8")
        own = re.search(r"_OWN_REASON = \{(.*?)\}", source, flags=re.S).group(1)
        reasons = set(re.findall(r'"L\d+": "([^"]+)"', own)) | set(
            re.findall(r'reasons\.append\("([^"]+)"\)', source)
        )
        # Verdicts are the backticked capitalised words; UNJUSTIFIED lives outside the table.
        verdicts = set(re.findall(r"`([A-Z]{5,})`", self.CONVERGE.read_text(encoding="utf-8")))
        self.assertGreaterEqual(len(reasons), 5)
        self.assertGreaterEqual(len(verdicts), 6)
        _, body = read("finishing-work")
        for item in sorted(reasons) + ["uncited"]:
            with self.subTest(reason=item):
                self.assertIn(item, body)
        for verdict in sorted(verdicts):
            with self.subTest(verdict=verdict):
                self.assertIn(f"`{verdict}`", body)

    def test_no_pipeline_or_approval_query(self):
        _, body = read("finishing-work")
        for pattern in (r"\bCI\b", r"pipeline", r"worktree", r"\bAPI\b", r"\.specs"):
            with self.subTest(pattern=pattern):
                self.assertIsNone(re.search(pattern, body))
