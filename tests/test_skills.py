import re
import unittest
from pathlib import Path

import yaml

ROOT = Path(__file__).resolve().parent.parent
SKILLS = ROOT / "skills"
HELPER_TEMPLATES = ROOT / "tools" / "specs" / "sdlc_specs" / "templates"
NAMES = ("workflow", "spec-template", "commit-conventions", "intent-writing")
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
