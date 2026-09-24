import re
import shutil
import tempfile
import unittest
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent
HELPER = '"${CLAUDE_PLUGIN_ROOT}/tools/specs/specs"'
# A helper call is `specs <subcommand>` at the start of a command line or after the path.
_BARE = re.compile(r"(^|[\s`$(])specs (init|lint|new|intent|coverage|status|--version)\b")


def problems(commands_dir: Path) -> list[str]:
    """Places where a command calls the helper by anything other than its quoted plugin path."""
    found = []
    for path in sorted(commands_dir.glob("*.md")):
        in_block = False
        for number, line in enumerate(path.read_text(encoding="utf-8").splitlines(), start=1):
            if line.lstrip().startswith("```"):
                in_block = not in_block
                continue
            if not in_block:
                continue  # prose may name a subcommand; only commands in code blocks are calls
            stripped = line.replace(HELPER, "HELPER")
            if "tools/specs/specs" in stripped or _BARE.search(stripped):
                found.append(f"{path.name}:{number}: {line.strip()}")
    return found


class CommandPathTest(unittest.TestCase):
    def test_shipped_commands_call_the_plugin_helper(self):
        self.assertEqual(problems(ROOT / "commands"), [])

    def test_a_bare_call_is_caught(self):
        tmp = Path(tempfile.mkdtemp())
        self.addCleanup(shutil.rmtree, tmp)
        (tmp / "good.md").write_text(f"```sh\n{HELPER} lint\n```\n")
        (tmp / "bare.md").write_text("```sh\nspecs lint\n```\n")
        (tmp / "unquoted.md").write_text("```sh\n${CLAUDE_PLUGIN_ROOT}/tools/specs/specs status\n```\n")
        (tmp / "repo-copy.md").write_text("```sh\ntools/specs/specs new --title x\n```\n")
        (tmp / "prose.md").write_text("The helper's `specs init` is idempotent.\n")
        self.assertEqual([p.split(":")[0] for p in problems(tmp)], ["bare.md", "repo-copy.md", "unquoted.md"])
