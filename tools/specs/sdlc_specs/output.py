"""Where output goes.

In text mode, results go to stdout and diagnostics to stderr. In JSON mode, stdout carries exactly
one JSON document and every human-readable line goes to stderr, so a caller can always parse
stdout.
"""

import json
import sys
from typing import Any, TextIO


class Output:
    def __init__(self, json_mode: bool, stdout: TextIO | None = None, stderr: TextIO | None = None):
        self.json_mode = json_mode
        self._stdout = stdout or sys.stdout
        self._stderr = stderr or sys.stderr

    def print(self, text: str = "") -> None:
        """A result line for humans: stdout in text mode, stderr in JSON mode."""
        print(text, file=self._stderr if self.json_mode else self._stdout)

    def warn(self, text: str) -> None:
        """A diagnostic. Always stderr."""
        print(text, file=self._stderr)

    def emit_document(self, doc: dict[str, Any]) -> None:
        """The one JSON document of a run. Only meaningful in JSON mode."""
        if self.json_mode:
            json.dump(doc, self._stdout, indent=2, sort_keys=False)
            self._stdout.write("\n")

    def emit_error(self, code: int, message: str) -> None:
        self.emit_document({"ok": False, "error": {"code": code, "message": message}})
