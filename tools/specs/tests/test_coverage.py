import json
import os
import shutil
import subprocess
import tempfile
from pathlib import Path

from sdlc_specs.config import DEFAULT_TEST_GLOBS
from sdlc_specs.coverage import glob_to_regex

from tests.base import OfflineTestCase

CONFIG = """tracker:
  system: github
code_host:
  system: github
"""
GIT_ENV = {"GIT_CONFIG_GLOBAL": os.devnull, "GIT_CONFIG_NOSYSTEM": "1"}
SPEC_ID = "2026-09-23-webhook-retries"


class CoverageTestCase(OfflineTestCase):
    def setUp(self):
        super().setUp()
        self.root = Path(tempfile.mkdtemp())
        self.addCleanup(shutil.rmtree, self.root)
        subprocess.run(["git", "init", "-q", str(self.root)], check=True, env={**os.environ, **GIT_ENV})
        subprocess.run(["git", "-C", str(self.root), "config", "user.name", "jdoe"], check=True)
        (self.root / "specs").mkdir()
        (self.root / "specs" / "config.yml").write_text(CONFIG)
        self.new_spec(SPEC_ID, ["AC-1", "AC-2"])

    def new_spec(self, spec_id: str, criteria: list[str], struck: list[str] = ()) -> None:
        date, slug = spec_id[:10], spec_id[11:]
        result = self.run_shim(
            "new", "--date", date, "--title", slug, "--slug", slug, cwd=self.root, env=GIT_ENV
        )
        self.assertEqual(result.returncode, 0, result.stderr)
        spec = self.root / "specs" / spec_id / "spec.md"
        lines = [f"- **{ac}** Criterion {ac}." for ac in criteria]
        lines += [f"- ~~**{ac}** Dropped {ac}.~~ Out of scope." for ac in struck]
        text = spec.read_text()
        start = text.index("- **AC-1**")
        end = text.index("\n", start)
        spec.write_text(text[:start] + "\n".join(lines) + text[end:])

    def write(self, rel: str, text: str) -> None:
        path = self.root / rel
        path.parent.mkdir(parents=True, exist_ok=True)
        path.write_text(text)

    def coverage(self, *args: str):
        result = self.run_shim("--json", "coverage", *args, cwd=self.root, env=GIT_ENV)
        return result.returncode, json.loads(result.stdout)

    @staticmethod
    def spec_report(doc: dict, spec_id: str = SPEC_ID) -> dict:
        return next(s for s in doc["specs"] if s["spec"] == spec_id)


class CoverageTest(CoverageTestCase):
    def test_cited_and_uncited(self):
        self.write("tests/test_retries.py", "\n" * 11 + f"def test_backoff():  # {SPEC_ID}:AC-1\n")
        code, doc = self.coverage()
        self.assertEqual(code, 1)
        report = self.spec_report(doc)
        by_ac = {c["ac"]: c for c in report["criteria"]}
        self.assertEqual(by_ac[1]["state"], "cited")
        self.assertEqual(by_ac[1]["at"], ["tests/test_retries.py:12"])
        self.assertEqual(by_ac[2]["state"], "uncited")

    def test_all_cited_exits_zero(self):
        self.write("tests/test_retries.py", f"# {SPEC_ID}:AC-1\n# {SPEC_ID}:AC-2\n")
        code, doc = self.coverage()
        self.assertEqual(code, 0, doc)

    def test_unknown_and_struck_citations_are_reported(self):
        shutil.rmtree(self.root / "specs" / SPEC_ID)
        self.new_spec(SPEC_ID, ["AC-1"], struck=["AC-2"])
        self.write("tests/test_retries.py", f"# {SPEC_ID}:AC-1\n# {SPEC_ID}:AC-2\n# {SPEC_ID}:AC-9\n")
        code, doc = self.coverage()
        self.assertEqual(code, 0)
        report = self.spec_report(doc)
        self.assertEqual([c["ac"] for c in report["criteria"]], [1])
        self.assertEqual(report["struck_citations"], [{"ac": 2, "at": "tests/test_retries.py:2"}])
        self.assertEqual(report["unknown_citations"], [{"ac": 9, "at": "tests/test_retries.py:3"}])

    def test_other_specs_ids_do_not_count(self):
        self.new_spec("2026-09-23-webhook-retries-v2", ["AC-1"])
        self.write(
            "tests/test_retries.py",
            "# 2026-09-23-webhook-retries-v2:AC-1\n"
            "# X2026-09-23-webhook-retries:AC-1 and ref_2026-09-23-webhook-retries:AC-1\n"
            "# 2026-09-23-webhook-retries:AC-12\n",
        )
        _, doc = self.coverage()
        by_ac = {c["ac"]: c for c in self.spec_report(doc)["criteria"]}
        self.assertEqual(by_ac[1]["state"], "uncited")
        self.assertEqual(
            self.spec_report(doc, "2026-09-23-webhook-retries-v2")["criteria"][0]["state"], "cited"
        )
        self.assertEqual(
            self.spec_report(doc)["unknown_citations"], [{"ac": 12, "at": "tests/test_retries.py:3"}]
        )

    def test_only_test_files_that_git_would_see(self):
        self.write(".gitignore", "tests/ignored_test.py\n")
        self.write("src/retries.py", f"# {SPEC_ID}:AC-1\n")  # not a test file
        self.write("tests/ignored_test.py", f"# {SPEC_ID}:AC-1\n")  # ignored
        self.write("pkg/retries_test.go", f"// {SPEC_ID}:AC-2\n")  # untracked but visible
        _, doc = self.coverage()
        by_ac = {c["ac"]: c for c in self.spec_report(doc)["criteria"]}
        self.assertEqual(by_ac[1]["state"], "uncited")
        self.assertEqual(by_ac[2]["at"], ["pkg/retries_test.go:1"])

    def test_one_spec_by_directory(self):
        self.new_spec("2026-09-23-other", ["AC-1"])
        _, doc = self.coverage(str(self.root / "specs" / "2026-09-23-other"))
        self.assertEqual([s["spec"] for s in doc["specs"]], ["2026-09-23-other"])

    def test_text_output(self):
        self.write("tests/test_retries.py", f"# {SPEC_ID}:AC-1\n")
        result = self.run_shim("coverage", cwd=self.root, env=GIT_ENV)
        self.assertEqual(result.returncode, 1)
        self.assertIn("AC-1 cited: tests/test_retries.py:1", result.stdout)
        self.assertIn("AC-2 uncited", result.stdout)


class GlobTest(OfflineTestCase):
    def test_default_globs(self):
        patterns = [glob_to_regex(g) for g in DEFAULT_TEST_GLOBS]

        def matched(path: str) -> bool:
            return any(p.fullmatch(path) for p in patterns)

        for path in (
            "tests/test_x.py",
            "a/b/test/helpers.rb",
            "x_test.go",
            "pkg/x_test.go",
            "web/x.test.ts",
            "x.spec.js",
        ):
            with self.subTest(path=path):
                self.assertTrue(matched(path))
        for path in ("src/x.py", "src/contest.py", "latest/x.py", "x.py"):
            with self.subTest(path=path):
                self.assertFalse(matched(path))

    def test_single_star_stays_in_one_directory(self):
        self.assertFalse(glob_to_regex("tests/*.py").fullmatch("tests/sub/x.py"))
        self.assertTrue(glob_to_regex("tests/**/*.py").fullmatch("tests/sub/x.py"))
        self.assertTrue(glob_to_regex("tests/**/*.py").fullmatch("tests/x.py"))
