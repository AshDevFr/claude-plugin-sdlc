import re
import shutil
import tempfile
import unittest
from pathlib import Path

import yaml

ROOT = Path(__file__).resolve().parent.parent
COMMANDS = ROOT / "commands"

# Every command file, and whether it takes arguments. A command task adds its entry first, so
# this test fails until the command exists.
EXPECTED = {
    "init": True,
    "start": True,
    "clarify": True,
    "check": True,
}
# Commands advise and print; none of them changes git state for the engineer.
_GIT_WRITE = re.compile(r"\bgit\s+(commit|push|add)\b")


def problems(path: Path, takes_arguments: bool) -> list[str]:
    text = path.read_text(encoding="utf-8")
    found = []
    if not text.startswith("---\n"):
        return [f"{path.name}: no frontmatter"]
    front, body = text[4:].split("\n---\n", 1)
    try:
        meta = yaml.safe_load(front)
    except yaml.YAMLError as exc:
        return [f"{path.name}: frontmatter is not valid YAML ({exc.problem})"]
    if not isinstance(meta, dict) or not str(meta.get("description", "")).strip():
        found.append(f"{path.name}: no description")
    if takes_arguments:
        if "argument-hint" not in meta:
            found.append(f"{path.name}: no argument-hint")
        if "$ARGUMENTS" not in body:
            found.append(f"{path.name}: doesn't read $ARGUMENTS")
    in_block = False
    for number, line in enumerate(body.splitlines(), start=1):
        if line.lstrip().startswith("```"):
            in_block = not in_block
        elif in_block and _GIT_WRITE.search(line):
            found.append(f"{path.name}:{number}: runs `{_GIT_WRITE.search(line).group(0)}`")
    return found


class CommandFilesTest(unittest.TestCase):
    def test_every_expected_command_exists_and_is_well_formed(self):
        for name, takes_arguments in EXPECTED.items():
            with self.subTest(command=name):
                path = COMMANDS / f"{name}.md"
                self.assertTrue(path.is_file(), f"{path} is missing")
                self.assertEqual(problems(path, takes_arguments), [])

    def test_no_unlisted_command(self):
        # A command file nobody listed here has no test.
        self.assertEqual(sorted(p.stem for p in COMMANDS.glob("*.md")), sorted(EXPECTED))


class CheckCommandTest(unittest.TestCase):
    def test_check_never_reads_a_failure_as_a_pass(self):
        text = (COMMANDS / "check.md").read_text(encoding="utf-8")
        self.assertIn("couldn't check", text)
        self.assertIn("/sdlc:sync", text)


class CheckerTest(unittest.TestCase):
    def setUp(self):
        self.dir = Path(tempfile.mkdtemp())
        self.addCleanup(shutil.rmtree, self.dir)

    def write(self, name: str, text: str) -> Path:
        path = self.dir / name
        path.write_text(text)
        return path

    def test_catches_what_it_should(self):
        good = self.write(
            "good.md", "---\nargument-hint: [x]\ndescription: Does a thing\n---\nUse `$ARGUMENTS`.\n"
        )
        self.assertEqual(problems(good, True), [])
        pushes = self.write("pushes.md", "---\ndescription: d\n---\n```sh\ngit push origin HEAD\n```\n")
        self.assertEqual(len(problems(pushes, False)), 1)
        prose = self.write("prose.md", "---\ndescription: d\n---\nNever run git commit for them.\n")
        self.assertEqual(problems(prose, False), [])
        colon = self.write("colon.md", "---\ndescription: Does: a thing\n---\nx\n")
        self.assertEqual(len(problems(colon, False)), 1)
        no_args = self.write("no-args.md", "---\nargument-hint: [x]\ndescription: d\n---\nx\n")
        self.assertIn("no-args.md: doesn't read $ARGUMENTS", problems(no_args, True))
