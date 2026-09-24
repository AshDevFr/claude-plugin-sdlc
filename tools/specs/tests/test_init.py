import hashlib
import json
import os
import shutil
import subprocess
import tempfile
from pathlib import Path

from sdlc_specs.init import PLUGIN_TEMPLATES, TEMPLATE_HISTORY

from tests.base import TOOL_DIR, OfflineTestCase

HELPER_TEMPLATES = TOOL_DIR / "sdlc_specs" / "templates"
PLUGIN_ROOT = TOOL_DIR.parent.parent
GIT_ENV = {"GIT_CONFIG_GLOBAL": os.devnull, "GIT_CONFIG_NOSYSTEM": "1"}


def tree(root: Path) -> dict[str, str]:
    return {
        p.relative_to(root).as_posix(): hashlib.sha256(p.read_bytes()).hexdigest()
        for p in sorted(root.rglob("*"))
        if p.is_file() and ".git" not in p.relative_to(root).parts
    }


class InitTestCase(OfflineTestCase):
    def setUp(self):
        super().setUp()
        self.repo = Path(tempfile.mkdtemp())
        self.addCleanup(shutil.rmtree, self.repo)
        subprocess.run(["git", "init", "-q", str(self.repo)], check=True, env={**os.environ, **GIT_ENV})

    def init(self, *args: str, json_out: bool = True):
        argv = (["--json"] if json_out else []) + ["init", *args]
        result = self.run_shim(*argv, cwd=self.repo, env=GIT_ENV)
        doc = json.loads(result.stdout) if json_out and result.stdout.strip() else None
        return result, doc

    @staticmethod
    def outcomes(doc: dict) -> dict[str, str]:
        return {item["path"]: item["outcome"] for item in doc["items"]}


class FirstRunTest(InitTestCase):
    def test_empty_repo(self):
        result, doc = self.init("--tracker", "github", "--host", "github")
        self.assertEqual(result.returncode, 0, result.stderr)
        self.assertEqual(
            self.outcomes(doc),
            {
                "specs/config.yml": "written",
                ".gitignore": "written",
                "CLAUDE.md": "written",
                "specs/templates/spec.md": "written",
                "specs/templates/intent.md": "written",
            },
        )
        for name in ("spec.md", "intent.md"):
            self.assertEqual(
                (self.repo / "specs" / "templates" / name).read_bytes(),
                (HELPER_TEMPLATES / name).read_bytes(),
            )
        lint = self.run_shim("lint", cwd=self.repo, env=GIT_ENV)
        self.assertEqual(lint.returncode, 0, lint.stdout + lint.stderr)

    def test_answers_reach_the_config(self):
        self.init(
            "--tracker",
            "linear",
            "--host",
            "gitlab",
            "--team-key",
            "ENG",
            "--approvers",
            "@acme/specs",
            "--specs-dir",
            ".specs",
        )
        text = (self.repo / ".specs" / "config.yml").read_text()
        self.assertIn("team_key: ENG", text)
        self.assertIn('spec_approvers: "@acme/specs"', text)
        self.assertIn(".specs/**/*.local.md", (self.repo / ".gitignore").read_text())

    def test_approver_usernames(self):
        self.init("--tracker", "github", "--host", "github", "--approvers", "alice,bob")
        self.assertIn("spec_approvers: [alice, bob]", (self.repo / "specs" / "config.yml").read_text())

    def test_tracker_and_host_are_required_on_a_first_run(self):
        result, _ = self.init("--tracker", "github")
        self.assertEqual(result.returncode, 2)
        self.assertEqual(tree(self.repo), {})

    def test_dry_run_writes_nothing(self):
        result, doc = self.init("--tracker", "github", "--host", "github", "--dry-run")
        self.assertEqual(result.returncode, 0, result.stderr)
        self.assertEqual(set(self.outcomes(doc).values()), {"written"})
        self.assertEqual(tree(self.repo), {})


class IdempotencyTest(InitTestCase):
    def test_second_run_changes_nothing(self):
        self.init("--tracker", "github", "--host", "github")
        before = tree(self.repo)
        result, doc = self.init("--tracker", "github", "--host", "github")
        self.assertEqual(result.returncode, 0, result.stderr)
        self.assertEqual(tree(self.repo), before)
        self.assertEqual(set(self.outcomes(doc).values()), {"present"})

    def test_existing_files_keep_their_content(self):
        (self.repo / "CLAUDE.md").write_text("# Project\n\nOur rules.\n")
        (self.repo / ".gitignore").write_text("node_modules/")  # no trailing newline
        _, doc = self.init("--tracker", "github", "--host", "github")
        self.assertEqual(self.outcomes(doc)["CLAUDE.md"], "appended")
        self.assertEqual(self.outcomes(doc)[".gitignore"], "appended")
        claude = (self.repo / "CLAUDE.md").read_text()
        self.assertTrue(claude.startswith("# Project\n\nOur rules.\n"))
        self.assertEqual(claude.count("<!-- sdlc:begin -->"), 1)
        gitignore = (self.repo / ".gitignore").read_text()
        self.assertTrue(gitignore.startswith("node_modules/\n"))
        self.init("--tracker", "github", "--host", "github")
        self.assertEqual((self.repo / "CLAUDE.md").read_text().count("<!-- sdlc:begin -->"), 1)

    def test_a_different_existing_config_stops_the_run(self):
        self.init("--tracker", "github", "--host", "github")
        before = tree(self.repo)
        result, _ = self.init("--tracker", "gitlab", "--host", "gitlab")
        self.assertEqual(result.returncode, 1)
        self.assertIn("specs/config.yml", result.stderr)
        self.assertEqual(tree(self.repo), before)


class UpgradeTest(InitTestCase):
    def setUp(self):
        super().setUp()
        self.init("--tracker", "github", "--host", "github")
        self.templates = self.repo / "specs" / "templates"

    def test_an_untouched_old_template_is_replaced(self):
        old = "# $title\n\nAn older shipped version.\n"
        (self.templates / "spec.md").write_text(old)
        history = TEMPLATE_HISTORY.read_text()
        TEMPLATE_HISTORY.write_text(history + f"{hashlib.sha256(old.encode()).hexdigest()}  spec.md\n")
        self.addCleanup(TEMPLATE_HISTORY.write_text, history)
        _, doc = self.init("--upgrade")
        self.assertEqual(self.outcomes(doc)["specs/templates/spec.md"], "updated")
        self.assertEqual(
            (self.templates / "spec.md").read_bytes(), (HELPER_TEMPLATES / "spec.md").read_bytes()
        )

    def test_a_customised_template_is_never_overwritten(self):
        custom = (self.templates / "intent.md").read_text() + "\n## Success signals\nHow we'll know.\n"
        (self.templates / "intent.md").write_text(custom)
        _, doc = self.init("--upgrade")
        item = next(i for i in doc["items"] if i["path"] == "specs/templates/intent.md")
        self.assertEqual(item["outcome"], "customised")
        self.assertIn("+## Success signals", item["diff"])
        self.assertEqual((self.templates / "intent.md").read_text(), custom)

    def test_the_claude_section_is_refreshed_between_its_markers(self):
        claude = self.repo / "CLAUDE.md"
        claude.write_text(
            "# Project\n\n" + claude.read_text().replace("## Specs", "## Specs (old wording)") + "\nAfter.\n"
        )
        _, doc = self.init("--upgrade")
        self.assertEqual(self.outcomes(doc)["CLAUDE.md"], "updated")
        text = claude.read_text()
        self.assertNotIn("(old wording)", text)
        self.assertTrue(text.startswith("# Project\n\n"))
        self.assertTrue(text.rstrip().endswith("After."))

    def test_upgrade_needs_an_existing_config(self):
        shutil.rmtree(self.repo / "specs")
        result, _ = self.init("--upgrade")
        self.assertEqual(result.returncode, 2)


class SafetyTest(InitTestCase):
    def test_never_writes_codeowners(self):
        self.init("--tracker", "github", "--host", "github")
        self.assertFalse(any("CODEOWNERS" in p for p in tree(self.repo)))

    def test_history_lists_the_current_templates(self):
        # A template edit must add its new hash, or --upgrade would call the shipped version customised.
        listed = {line.split()[0] for line in TEMPLATE_HISTORY.read_text().splitlines() if line.strip()}
        for name in ("spec.md", "intent.md"):
            self.assertIn(hashlib.sha256((HELPER_TEMPLATES / name).read_bytes()).hexdigest(), listed)

    def test_plugin_templates_are_found(self):
        self.assertEqual(PLUGIN_TEMPLATES, PLUGIN_ROOT / "templates")


class CommandFileTest(OfflineTestCase):
    def test_init_command_uses_the_plugin_helper_and_prints_the_guidance(self):
        text = (PLUGIN_ROOT / "commands" / "init.md").read_text()
        # Quoted: the plugin's install path may contain spaces.
        self.assertIn('"${CLAUDE_PLUGIN_ROOT}/tools/specs/specs" init', text)
        self.assertIn('"${CLAUDE_PLUGIN_ROOT}/tools/specs/specs" lint', text)
        for needle in (
            "CODEOWNERS",
            "Dismiss stale pull request approvals",
            "Remove all approvals when commits are added",
        ):
            with self.subTest(needle=needle):
                self.assertIn(needle, text)
