import shutil
import subprocess
import tempfile
from pathlib import Path

from sdlc_specs.config import DEFAULT_TEST_GLOBS, Config
from sdlc_specs.errors import CheckFailed, ConfigError, UsageError
from sdlc_specs.keys import Keys, TicketKey, parse_remote_url, slugify

from tests.base import OfflineTestCase


def make_config(system: str, project: str | None = None, fake_of: str | None = None) -> Config:
    return Config(
        tracker_system=system,
        tracker_fake_of=fake_of,
        tracker_project=project,
        tracker_team_key="ENG" if (fake_of or system) == "linear" else None,
        tracker_base_url=None,
        spec_label="spec-required",
        host_system="github",
        host_base_url=None,
        spec_approvers="@acme/spec-approvers",
        specs_dir="specs",
        test_globs=list(DEFAULT_TEST_GLOBS),
    )


class TempRepoTestCase(OfflineTestCase):
    def setUp(self):
        super().setUp()
        self.root = Path(tempfile.mkdtemp())
        self.addCleanup(shutil.rmtree, self.root)
        (self.root / ".git").mkdir()

    def keys(self, system: str, project: str | None = None, fake_of: str | None = None) -> Keys:
        return Keys(make_config(system, project, fake_of), self.root)


class DirectoryNameTest(TempRepoTestCase):
    def test_success_criterion_examples(self):
        host = self.keys("github", project="shop/web")
        cases = {
            "123": "123-prorate-plan-changes",
            "billing/api#123": "billing-api-123-prorate-plan-changes",
            "acme/api#123": "acme-api-123-prorate-plan-changes",
        }
        for ref, expected in cases.items():
            with self.subTest(ref=ref):
                self.assertEqual(host.dir_name(host.parse(ref), "prorate plan changes!"), expected)
        linear = self.keys("linear")
        self.assertEqual(
            linear.dir_name(linear.parse("ENG-123"), "prorate plan changes!"),
            "eng-123-prorate-plan-changes",
        )

    def test_title_without_ascii_needs_an_explicit_slug(self):
        keys = self.keys("github")
        with self.assertRaises(UsageError):
            keys.dir_name(keys.parse("#1"), "日本語")


class ParseTest(TempRepoTestCase):
    def test_host_tracker_forms(self):
        keys = self.keys("gitlab", project="billing/api")
        cases = {
            "#123": TicketKey("gitlab", None, 123, None),
            "123": TicketKey("gitlab", None, 123, None),
            "billing/api#123": TicketKey("gitlab", None, 123, None),
            "Billing/API#123": TicketKey("gitlab", None, 123, None),
            "group/sub/project#7": TicketKey("gitlab", "group/sub/project", 7, None),
            " acme/api#9 ": TicketKey("gitlab", "acme/api", 9, None),
        }
        for ref, expected in cases.items():
            with self.subTest(ref=ref):
                self.assertEqual(keys.parse(ref), expected)

    def test_refs(self):
        keys = self.keys("github", project="shop/web")
        self.assertEqual(keys.parse("shop/web#5").ref(), "#5")
        self.assertEqual(keys.parse("Acme/Api#5").ref(), "acme/api#5")
        self.assertEqual(self.keys("linear").parse("eng-12").ref(), "ENG-12")

    def test_linear_forms_are_case_insensitive(self):
        keys = self.keys("linear")
        for ref in ("ENG-123", "eng-123", "Eng-123"):
            with self.subTest(ref=ref):
                self.assertEqual(keys.parse(ref), TicketKey("linear", None, 123, "ENG"))

    def test_any_linear_team_is_accepted(self):
        self.assertEqual(self.keys("linear").parse("OPS-5").team, "OPS")

    def test_parsing_depends_on_the_tracker(self):
        with self.assertRaises(UsageError):
            self.keys("linear").parse("123")
        with self.assertRaises(UsageError):
            self.keys("linear").parse("#123")
        with self.assertRaises(UsageError):
            self.keys("gitlab").parse("ENG-123")

    def test_fake_tracker_parses_like_the_system_it_mimics(self):
        self.assertEqual(self.keys("fake", fake_of="linear").parse("ENG-1").ref(), "ENG-1")
        with self.assertRaises(UsageError):
            self.keys("fake", fake_of="linear").parse("#1")
        self.assertEqual(self.keys("fake", fake_of="gitlab").parse("#1").ref(), "#1")

    def test_malformed_refs(self):
        host = self.keys("gitlab", project="billing/api")
        linear = self.keys("linear")
        for ref in ("", "#", "#0", "#-1", "#012", "foo#bar", "api#12", "a/b#", "#12a", "a//b#1"):
            with self.subTest(ref=ref, tracker="gitlab"):
                with self.assertRaises(UsageError):
                    host.parse(ref)
        for ref in ("", "ENG-0", "ENG", "-12", "E NG-1", "1ENG-2"):
            with self.subTest(ref=ref, tracker="linear"):
                with self.assertRaises(UsageError):
                    linear.parse(ref)

    def test_github_projects_are_owner_and_repo(self):
        with self.assertRaises(UsageError):
            self.keys("github", project="shop/web").parse("a/b/c#1")


class HomeProjectTest(TempRepoTestCase):
    def git(self, *args):
        subprocess.run(["git", "-C", str(self.root), *args], check=True, capture_output=True)

    def init_repo_with_origin(self, url: str):
        (self.root / ".git").rmdir()
        self.git("init", "-q")
        self.git("remote", "add", "origin", url)

    def test_configured_project_is_home(self):
        keys = self.keys("gitlab", project="billing/api")
        self.assertEqual(keys.parse("billing/api#123").dir_prefix(), "123")
        self.assertEqual(keys.parse("#123").dir_prefix(), "123")

    def test_origin_remote_is_home_when_no_project_is_configured(self):
        self.init_repo_with_origin("git@gitlab.example.com:billing/api.git")
        keys = self.keys("gitlab")
        self.assertEqual(keys.parse("billing/api#123").dir_prefix(), "123")
        self.assertEqual(keys.parse("#123").dir_prefix(), "123")
        self.assertEqual(keys.parse("acme/api#123").dir_prefix(), "acme-api-123")

    def test_qualified_ref_without_a_home_project_is_a_config_error(self):
        keys = self.keys("gitlab")
        with self.assertRaises(ConfigError) as ctx:
            keys.parse("billing/api#123")
        self.assertIn("tracker.project", ctx.exception.message)

    def test_local_ref_needs_no_home_project(self):
        self.assertEqual(self.keys("gitlab").parse("#123").dir_prefix(), "123")


class RemoteUrlTest(OfflineTestCase):
    def test_forms(self):
        cases = {
            "git@gitlab.example.com:billing/api.git": "billing/api",
            "git@github.com:acme/api": "acme/api",
            "ssh://git@gitlab.example.com:2222/group/sub/project.git": "group/sub/project",
            "https://gitlab.example.com/group/sub/project.git": "group/sub/project",
            "https://github.com/acme/api/": "acme/api",
            "https://user:token@github.com/acme/api.git": "acme/api",
            "https://gitlab.example.com/gitlab/billing/api.git": "gitlab/billing/api",
        }
        for url, expected in cases.items():
            with self.subTest(url=url):
                self.assertEqual(parse_remote_url(url), expected)

    def test_unparsable(self):
        for url in ("", "/srv/git/api.git", "file:///srv/git/api.git", "https://github.com/acme"):
            with self.subTest(url=url):
                self.assertIsNone(parse_remote_url(url))


class ResolveBranchTest(TempRepoTestCase):
    def test_linear_branches(self):
        keys = self.keys("linear")
        self.assertEqual(keys.resolve_branch("jdoe/eng-123-webhook-retries").ref(), "ENG-123")
        self.assertEqual(keys.resolve_branch("eng-123-webhook-retries").ref(), "ENG-123")
        self.assertEqual(keys.resolve_branch("ENG-123").ref(), "ENG-123")
        self.assertIsNone(keys.resolve_branch("main"))
        self.assertIsNone(keys.resolve_branch("123-prorate"))

    def test_host_branches(self):
        keys = self.keys("github")
        self.assertEqual(keys.resolve_branch("feature/123-prorate").ref(), "#123")
        self.assertEqual(keys.resolve_branch("jdoe/feature/123-prorate").ref(), "#123")
        self.assertEqual(keys.resolve_branch("123-prorate-plan-changes").ref(), "#123")
        for branch in ("main", "release-2026", "2fa-login", "0-foo", "eng-123-x", "", "feature/"):
            with self.subTest(branch=branch):
                self.assertIsNone(keys.resolve_branch(branch))


class FindSpecDirTest(TempRepoTestCase):
    def make_dirs(self, *names):
        for name in names:
            (self.root / "specs" / name).mkdir(parents=True)

    def test_single_match(self):
        self.make_dirs("123-a", "1234-b", "12-3-ways")
        keys = self.keys("github")
        self.assertEqual(keys.find_spec_dir(keys.parse("#123")), self.root / "specs" / "123-a")
        self.assertEqual(keys.find_spec_dir(keys.parse("#12")), self.root / "specs" / "12-3-ways")

    def test_two_matches_is_a_finding_naming_both(self):
        self.make_dirs("123-a", "123-c")
        keys = self.keys("github")
        with self.assertRaises(CheckFailed) as ctx:
            keys.find_spec_dir(keys.parse("#123"))
        self.assertIn("specs/123-a", ctx.exception.message)
        self.assertIn("specs/123-c", ctx.exception.message)

    def test_no_match(self):
        self.make_dirs("123-a")
        (self.root / "specs" / "999-not-a-dir").write_text("")
        keys = self.keys("github")
        self.assertIsNone(keys.find_spec_dir(keys.parse("#999")))

    def test_missing_specs_dir(self):
        keys = self.keys("github")
        self.assertIsNone(keys.find_spec_dir(keys.parse("#1")))


class SlugifyTest(OfflineTestCase):
    def test_accents_fold_to_ascii(self):
        self.assertEqual(slugify("Crédit à l'échéance"), "credit-a-l-echeance")

    def test_rules(self):
        cases = {
            "prorate plan changes!": "prorate-plan-changes",
            "  Leading and trailing  ": "leading-and-trailing",
            "Multiple---dashes__and  spaces": "multiple-dashes-and-spaces",
            "Straße": "strae",
            "日本語": "",
        }
        for title, expected in cases.items():
            with self.subTest(title=title):
                self.assertEqual(slugify(title), expected)

    def test_long_titles_are_cut_without_a_trailing_dash(self):
        title = "word " * 24  # 120 chars
        slug = slugify(title)
        self.assertLessEqual(len(slug), 50)
        self.assertFalse(slug.endswith("-"))
        self.assertTrue(slug.startswith("word-word"))
