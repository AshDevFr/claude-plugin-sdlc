import json
import shutil
import tempfile
from pathlib import Path

from sdlc_specs.config import DEFAULT_TEST_GLOBS, find_repo_root, load_config
from sdlc_specs.errors import ConfigError

from tests.base import OfflineTestCase

FIXTURES = Path(__file__).resolve().parent / "fixtures" / "config"


class RepoTestCase(OfflineTestCase):
    """Each test gets an empty git-looking repo in a temp dir."""

    def setUp(self):
        super().setUp()
        self.root = Path(tempfile.mkdtemp())
        self.addCleanup(shutil.rmtree, self.root)
        (self.root / ".git").mkdir()

    def install(self, fixture: str, specs_dir: str = "specs") -> Path:
        target = self.root / specs_dir / "config.yml"
        target.parent.mkdir(parents=True, exist_ok=True)
        shutil.copy(FIXTURES / fixture, target)
        return target


class ValidConfigTest(RepoTestCase):
    def test_minimal_config_gets_documented_defaults(self):
        self.install("minimal.yml")
        root, config = load_config(self.root)
        self.assertEqual(root, self.root)
        self.assertEqual(config.tracker_system, "github")
        self.assertIsNone(config.tracker_project)
        self.assertIsNone(config.tracker_team_key)
        self.assertIsNone(config.tracker_base_url)
        self.assertIsNone(config.tracker_fake_of)
        self.assertEqual(config.spec_label, "spec-required")
        self.assertEqual(config.host_system, "github")
        self.assertIsNone(config.host_base_url)
        self.assertEqual(config.spec_approvers, "@acme/spec-approvers")
        self.assertEqual(config.specs_dir, "specs")
        self.assertEqual(config.test_globs, DEFAULT_TEST_GLOBS)
        self.assertEqual(DEFAULT_TEST_GLOBS, ["**/test*/**", "**/*_test.*", "**/*.test.*", "**/*.spec.*"])

    def test_every_field_set(self):
        self.install("full-gitlab.yml")
        _, config = load_config(self.root)
        self.assertEqual(config.tracker_project, "billing/api")
        self.assertEqual(config.tracker_base_url, "https://gitlab.example.com")
        self.assertEqual(config.spec_label, "needs-spec")
        self.assertEqual(config.host_base_url, "https://gitlab.example.com")
        self.assertEqual(config.spec_approvers, ["alice", "bob"])
        self.assertEqual(config.test_globs, ["tests/**"])

    def test_linear(self):
        self.install("linear.yml")
        _, config = load_config(self.root)
        self.assertEqual(config.tracker_team_key, "ENG")

    def test_fake_systems_need_only_fake_of_and_approvers(self):
        self.install("fake.yml")
        _, config = load_config(self.root)
        self.assertEqual(config.tracker_system, "fake")
        self.assertEqual(config.tracker_fake_of, "github")
        self.assertEqual(config.host_system, "fake")

    def test_fake_linear_validates_as_linear(self):
        self.install("fake-linear.yml")
        _, config = load_config(self.root)
        self.assertEqual(config.tracker_fake_of, "linear")
        self.assertEqual(config.tracker_team_key, "ENG")

    def test_config_found_from_a_subdirectory(self):
        self.install("minimal.yml")
        deep = self.root / "src" / "pkg"
        deep.mkdir(parents=True)
        root, _ = load_config(deep)
        self.assertEqual(root, self.root)

    def test_git_file_marks_the_root_too(self):
        # Worktrees and submodules have a .git file, not a directory.
        (self.root / ".git").rmdir()
        (self.root / ".git").write_text("gitdir: /elsewhere\n")
        self.install("minimal.yml")
        root, _ = load_config(self.root)
        self.assertEqual(root, self.root)
        self.assertEqual(find_repo_root(self.root), self.root)


class SpecsDirTest(RepoTestCase):
    def test_hidden_specs_dir_is_the_default_when_config_lives_there(self):
        self.install("minimal.yml", specs_dir=".specs")
        _, config = load_config(self.root)
        self.assertEqual(config.specs_dir, ".specs")
        self.assertEqual(config.specs_path(self.root), self.root / ".specs")

    def test_specs_dir_must_match_the_directory_holding_the_config(self):
        path = self.install("minimal.yml", specs_dir=".specs")
        path.write_text(path.read_text() + "specs_dir: specs\n")
        with self.assertRaises(ConfigError) as ctx:
            load_config(self.root)
        self.assertIn(".specs/config.yml", ctx.exception.message)
        self.assertIn("specs_dir", ctx.exception.message)

    def test_visible_dir_wins_when_both_exist(self):
        self.install("minimal.yml", specs_dir="specs")
        self.install("linear.yml", specs_dir=".specs")
        _, config = load_config(self.root)
        self.assertEqual(config.specs_dir, "specs")
        self.assertEqual(config.tracker_system, "github")


class InvalidConfigTest(RepoTestCase):
    # fixture -> text that must appear in the error after "specs/config.yml: "
    CASES = {
        "linear-missing-team-key.yml": "tracker.team_key",
        "fake-linear-missing-team-key.yml": "tracker.team_key",
        "fake-missing-fake-of.yml": "tracker.fake_of",
        "fake-of-on-real-tracker.yml": "tracker.fake_of",
        "unknown-key.yml": "tracker.sytem",
        "unknown-top-level-key.yml": "test_globs",
        "unknown-tracker-system.yml": "tracker.system",
        "unknown-host-system.yml": "code_host.system",
        "project-on-linear.yml": "tracker.project",
        "team-key-on-gitlab.yml": "tracker.team_key",
        "base-url-on-fake-host.yml": "code_host.base_url",
        "missing-approvers.yml": "code_host.spec_approvers",
        "approvers-not-a-group.yml": "code_host.spec_approvers",
        "approvers-empty-list.yml": "code_host.spec_approvers",
        "missing-tracker.yml": "tracker",
        "tracker-not-mapping.yml": "tracker",
        "empty-test-globs.yml": "coverage.test_globs",
        "spec-label-wrong-type.yml": "tracker.spec_label",
    }

    def test_each_invalid_fixture_names_its_field(self):
        for fixture, field in self.CASES.items():
            with self.subTest(fixture=fixture):
                self.install(fixture)
                with self.assertRaises(ConfigError) as ctx:
                    load_config(self.root)
                self.assertTrue(
                    ctx.exception.message.startswith(f"specs/config.yml: {field}:"),
                    ctx.exception.message,
                )

    def test_stray_field_message_names_the_system(self):
        self.install("project-on-linear.yml")
        with self.assertRaises(ConfigError) as ctx:
            load_config(self.root)
        self.assertIn("linear", ctx.exception.message)

    def test_whole_file_errors(self):
        for fixture in ("empty.yml", "not-a-mapping.yml", "invalid-yaml.yml"):
            with self.subTest(fixture=fixture):
                self.install(fixture)
                with self.assertRaises(ConfigError) as ctx:
                    load_config(self.root)
                self.assertTrue(ctx.exception.message.startswith("specs/config.yml:"))

    def test_no_config_file(self):
        with self.assertRaises(ConfigError) as ctx:
            load_config(self.root)
        self.assertIn("specs/config.yml", ctx.exception.message)

    def test_not_in_a_git_repo(self):
        (self.root / ".git").rmdir()
        with self.assertRaises(ConfigError):
            find_repo_root(self.root)


class CliConfigTest(RepoTestCase):
    def test_config_error_exits_2_naming_file_and_field(self):
        self.install("linear-missing-team-key.yml")
        result = self.run_cli("_test-config", cwd=self.root)
        self.assertEqual(result.returncode, 2)
        self.assertIn("specs/config.yml", result.stderr)
        self.assertIn("tracker.team_key", result.stderr)

    def test_config_error_with_json(self):
        self.install("unknown-tracker-system.yml")
        result = self.run_cli("--json", "_test-config", cwd=self.root)
        self.assertEqual(result.returncode, 2)
        doc = json.loads(result.stdout)
        self.assertEqual(doc["error"]["code"], 2)
        self.assertIn("tracker.system", doc["error"]["message"])

    def test_valid_config_reaches_the_handler(self):
        self.install("linear.yml")
        result = self.run_cli("--json", "_test-config", cwd=self.root)
        self.assertEqual(result.returncode, 0, result.stderr)
        self.assertEqual(json.loads(result.stdout), {"ok": True, "tracker": "linear"})

    def test_commands_without_config_do_not_load_it(self):
        self.install("unknown-tracker-system.yml")
        result = self.run_cli("_test-ok", cwd=self.root)
        self.assertEqual(result.returncode, 0, result.stderr)
