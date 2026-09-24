import os
import shutil
import subprocess
import sys
import tempfile
import unittest
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(ROOT / "tools" / "specs"))

from sdlc_specs.config import load_config  # noqa: E402
from sdlc_specs.init import render_claude_section, render_config, render_gitignore  # noqa: E402

TEMPLATES = ROOT / "templates"
GIT_ENV = {**os.environ, "GIT_CONFIG_GLOBAL": os.devnull, "GIT_CONFIG_NOSYSTEM": "1"}


class TempRepoCase(unittest.TestCase):
    def setUp(self):
        self.repo = Path(tempfile.mkdtemp())
        self.addCleanup(shutil.rmtree, self.repo)
        subprocess.run(["git", "init", "-q", str(self.repo)], check=True, env=GIT_ENV)


class ConfigTemplateTest(TempRepoCase):
    CASES = {
        "github pair": dict(tracker="github", host="github"),
        "linear and gitlab": dict(
            tracker="linear",
            host="gitlab",
            team_key="ENG",
            approvers="@acme/spec-approvers",
            specs_dir=".specs",
        ),
        "tickets in another project": dict(tracker="gitlab", host="gitlab", project="billing/api"),
        "approvers as users": dict(tracker="github", host="github", approvers=["alice", "bob"]),
    }

    def test_rendered_configs_load(self):
        for name, answers in self.CASES.items():
            with self.subTest(name=name):
                text = render_config(**answers)
                self.assertNotIn("$", text)
                specs_dir = answers.get("specs_dir", "specs")
                target = self.repo / specs_dir / "config.yml"
                target.parent.mkdir(exist_ok=True)
                target.write_text(text)
                _, config = load_config(self.repo)
                self.assertEqual(config.tracker_system, answers["tracker"])
                self.assertEqual(config.host_system, answers["host"])
                self.assertEqual(config.tracker_team_key, answers.get("team_key"))
                self.assertEqual(config.tracker_project, answers.get("project"))
                self.assertEqual(config.spec_approvers, answers.get("approvers"))
                self.assertEqual(config.specs_dir, specs_dir)
                shutil.rmtree(target.parent)

    def test_absent_answers_leave_no_empty_keys(self):
        text = render_config(tracker="github", host="github")
        for key in ("project:", "team_key:", "spec_approvers:", "specs_dir:"):
            self.assertNotIn(key, text)


class ClaudeSectionTest(unittest.TestCase):
    def test_content(self):
        text = render_claude_section(specs_dir="specs")
        self.assertTrue(text.startswith("<!-- sdlc:begin -->\n"))
        self.assertTrue(text.rstrip().endswith("<!-- sdlc:end -->"))
        for needle in ("intent.md", "spec.md", "/sdlc:check", "Spec:", "Implements:", "Spec-Change:"):
            with self.subTest(needle=needle):
                self.assertIn(needle, text)

    def test_names_no_platform(self):
        text = render_claude_section(specs_dir="specs").lower()
        for platform in ("gitlab", "github", "linear"):
            self.assertNotIn(platform, text)


class GitignoreTest(TempRepoCase):
    def ignored(self, path: str) -> bool:
        result = subprocess.run(
            ["git", "-C", str(self.repo), "check-ignore", "-q", path], env=GIT_ENV, check=False
        )
        return result.returncode == 0

    def test_only_local_working_files_are_ignored(self):
        for specs_dir in ("specs", ".specs"):
            with self.subTest(specs_dir=specs_dir):
                (self.repo / ".gitignore").write_text(render_gitignore(specs_dir=specs_dir))
                self.assertTrue(self.ignored(f"{specs_dir}/2026-09-23-x/plan.local.md"))
                for kept in ("spec.md", "intent.md", "threat-model.md"):
                    self.assertFalse(self.ignored(f"{specs_dir}/2026-09-23-x/{kept}"))
                self.assertFalse(self.ignored(f"{specs_dir}/config.yml"))
                self.assertFalse(self.ignored(f"{specs_dir}/templates/spec.md"))

    def test_marker(self):
        self.assertTrue(render_gitignore(specs_dir="specs").startswith("# sdlc:"))


class TemplateFilesTest(unittest.TestCase):
    def test_every_template_exists(self):
        for rel in ("specs/config.yml.tmpl", "CLAUDE.section.md", "gitignore.snippet"):
            with self.subTest(rel=rel):
                self.assertTrue((TEMPLATES / rel).is_file())
