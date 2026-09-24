import ast
import json
import runpy
import socket
import sys

from tests.base import SHIM, TOOL_DIR, NetworkBlocked, OfflineTestCase


class VersionTest(OfflineTestCase):
    def test_version_prints_version_file_and_exits_zero(self):
        expected = (TOOL_DIR / "VERSION").read_text().strip()
        result = self.run_shim("--version")
        self.assertEqual(result.returncode, 0, result.stderr)
        self.assertEqual(result.stdout.strip(), expected)

    def test_version_as_json(self):
        result = self.run_shim("--json", "--version")
        self.assertEqual(result.returncode, 0, result.stderr)
        doc = json.loads(result.stdout)
        self.assertEqual(doc, {"ok": True, "version": (TOOL_DIR / "VERSION").read_text().strip()})


class UsageTest(OfflineTestCase):
    def test_unknown_subcommand_exits_2_with_usage_on_stderr(self):
        result = self.run_shim("bogus")
        self.assertEqual(result.returncode, 2)
        self.assertEqual(result.stdout, "")
        self.assertIn("usage:", result.stderr)
        self.assertIn("bogus", result.stderr)

    def test_no_subcommand_exits_2(self):
        result = self.run_shim()
        self.assertEqual(result.returncode, 2)
        self.assertIn("usage:", result.stderr)
        self.assertEqual(result.stdout, "")

    def test_unknown_subcommand_with_json_emits_one_error_document(self):
        result = self.run_shim("--json", "bogus")
        self.assertEqual(result.returncode, 2)
        doc = json.loads(result.stdout)
        self.assertIs(doc["ok"], False)
        self.assertEqual(doc["error"]["code"], 2)
        self.assertIn("bogus", doc["error"]["message"])
        self.assertIn("usage:", result.stderr)

    def test_help_with_json_keeps_stdout_a_single_document(self):
        result = self.run_shim("--json", "--help")
        self.assertEqual(result.returncode, 0)
        self.assertEqual(json.loads(result.stdout), {"ok": True})
        self.assertIn("usage:", result.stderr)


class ErrorMappingTest(OfflineTestCase):
    def test_specs_error_maps_to_its_exit_code(self):
        result = self.run_cli("_test-fail")
        self.assertEqual(result.returncode, 1)
        self.assertIn("the check failed", result.stderr)
        self.assertEqual(result.stdout, "")

    def test_unexpected_exception_exits_2_with_one_line(self):
        result = self.run_cli("_test-crash")
        self.assertEqual(result.returncode, 2)
        lines = result.stderr.strip().splitlines()
        self.assertEqual(len(lines), 1, result.stderr)
        self.assertIn("boom", lines[0])
        self.assertNotIn("Traceback", result.stderr)

    def test_verbose_shows_traceback(self):
        result = self.run_cli("--verbose", "_test-crash")
        self.assertEqual(result.returncode, 2)
        self.assertIn("Traceback", result.stderr)
        self.assertIn("boom", result.stderr)

    def test_handler_exit_code_is_returned(self):
        result = self.run_cli("_test-findings")
        self.assertEqual(result.returncode, 1)
        self.assertIn("one finding", result.stdout)


class JsonModeTest(OfflineTestCase):
    def assert_single_json(self, result):
        return json.loads(result.stdout)  # raises if there is anything but one document

    def test_success_is_one_document_and_human_text_goes_to_stderr(self):
        for argv in (["--json", "_test-ok"], ["_test-ok", "--json"]):
            with self.subTest(argv=argv):
                result = self.run_cli(*argv)
                self.assertEqual(result.returncode, 0, result.stderr)
                self.assertEqual(self.assert_single_json(result), {"ok": True, "answer": 42})
                self.assertIn("human text for the ok command", result.stderr)

    def test_text_mode_prints_human_text_on_stdout(self):
        result = self.run_cli("_test-ok")
        self.assertEqual(result.returncode, 0, result.stderr)
        self.assertIn("human text for the ok command", result.stdout)

    def test_nonzero_result_sets_ok_false(self):
        result = self.run_cli("--json", "_test-findings")
        self.assertEqual(result.returncode, 1)
        self.assertEqual(self.assert_single_json(result), {"ok": False, "findings": ["f1"]})

    def test_specs_error_is_an_error_document(self):
        result = self.run_cli("--json", "_test-fail")
        self.assertEqual(result.returncode, 1)
        doc = self.assert_single_json(result)
        self.assertEqual(doc, {"ok": False, "error": {"code": 1, "message": "the check failed"}})

    def test_unexpected_exception_is_an_error_document(self):
        result = self.run_cli("--json", "_test-crash")
        self.assertEqual(result.returncode, 2)
        doc = self.assert_single_json(result)
        self.assertIs(doc["ok"], False)
        self.assertEqual(doc["error"]["code"], 2)
        self.assertIn("boom", doc["error"]["message"])


class SocketGuardTest(OfflineTestCase):
    def test_in_process_socket_creation_fails(self):
        with self.assertRaises(NetworkBlocked):
            socket.socket()
        with self.assertRaises(NetworkBlocked):
            socket.create_connection(("example.com", 80))

    def test_cli_subprocess_socket_creation_fails(self):
        result = self.run_cli("_test-net")
        self.assertEqual(result.returncode, 2)
        self.assertIn("tests must not open network sockets", result.stderr)


class PreflightTest(OfflineTestCase):
    """The shim checks its environment before importing anything that needs it."""

    def run_without_site_packages(self, *args):
        # -S skips site-packages, so PyYAML is unimportable while the stdlib still works.
        return self._run([sys.executable, "-S", str(SHIM), *args], cwd=None, env=None)

    def test_missing_pyyaml_is_one_line_and_exit_2(self):
        for argv in (["--version"], ["lint"]):
            with self.subTest(argv=argv):
                result = self.run_without_site_packages(*argv)
                self.assertEqual(result.returncode, 2)
                self.assertEqual(result.stdout, "")
                self.assertEqual(
                    result.stderr.strip().splitlines(),
                    ["specs: PyYAML is not installed (pip install pyyaml)"],
                )

    def test_missing_pyyaml_with_json_still_emits_one_document(self):
        result = self.run_without_site_packages("--json", "lint")
        self.assertEqual(result.returncode, 2)
        doc = json.loads(result.stdout)
        self.assertEqual(doc["ok"], False)
        self.assertEqual(doc["error"]["code"], 2)
        self.assertIn("PyYAML", doc["error"]["message"])

    def test_old_python_is_named(self):
        preflight = runpy.run_path(str(SHIM), run_name="preflight_check")["preflight"]
        self.assertEqual(preflight((3, 9, 7, "final", 0)), "specs: needs Python 3.10 or newer, found 3.9.7")
        self.assertIsNone(preflight(sys.version_info))

    def test_shim_parses_without_modern_syntax(self):
        # The guard only helps if an old interpreter can parse the file it lives in.
        tree = ast.parse(SHIM.read_text(), feature_version=(3, 4))
        self.assertFalse(
            [n for n in ast.walk(tree) if isinstance(n, ast.JoinedStr)], "no f-strings in the shim"
        )
