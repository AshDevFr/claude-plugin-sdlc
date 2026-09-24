"""`specs coverage`: which acceptance criteria the tests cite.

A test cites a criterion as `<spec-id>:AC-<n>` anywhere in a line (a test name, a comment, a
string). The spec id qualifies the number because every spec has an AC-1. This only proves a
citation exists; whether the test exercises the criterion is a reviewer's call.
"""

import argparse
import re
import subprocess
from dataclasses import dataclass, field
from pathlib import Path

from . import cli
from .config import Config
from .errors import EXIT_CHECK_FAILED, EXIT_OK, UsageError
from .lint import _all_spec_dirs
from .output import Output
from .spec import SpecParseError, parse_spec

# Spec ids are lowercase letters, digits and dashes (date ids and ticket directory names both).
# The lookbehind keeps `x2026-09-23-a:AC-1` or `pre-2026-09-23-a:AC-1` from counting for
# `2026-09-23-a`; the lookahead keeps AC-12 from reading as AC-1.
_CITATION = re.compile(r"(?<![A-Za-z0-9_.-])([a-z0-9][a-z0-9-]*):AC-(\d+)(?!\d)")


def glob_to_regex(glob: str) -> re.Pattern:
    """`**/` matches any number of directories (including none), `*` stays within one."""
    out, i = [], 0
    while i < len(glob):
        if glob.startswith("**/", i):
            out.append("(?:.*/)?")
            i += 3
        elif glob.startswith("**", i):
            out.append(".*")
            i += 2
        elif glob[i] == "*":
            out.append("[^/]*")
            i += 1
        elif glob[i] == "?":
            out.append("[^/]")
            i += 1
        else:
            out.append(re.escape(glob[i]))
            i += 1
    return re.compile("".join(out))


def test_files(root: Path, globs: list[str]) -> list[str]:
    """Repo-relative paths git would show (tracked, or untracked and not ignored) matching a glob."""
    result = subprocess.run(
        ["git", "-C", str(root), "ls-files", "-co", "--exclude-standard", "-z"],
        capture_output=True,
        text=True,
        check=False,
    )
    if result.returncode != 0:
        raise UsageError(f"{root}: cannot list files with git")
    patterns = [glob_to_regex(g) for g in globs]
    return sorted({p for p in result.stdout.split("\0") if p and any(r.fullmatch(p) for r in patterns)})


def citations(root: Path, files: list[str]) -> dict[str, dict[int, list[str]]]:
    """spec id -> AC number -> ["path:line", ...]"""
    found: dict[str, dict[int, list[str]]] = {}
    for rel in files:
        try:
            text = (root / rel).read_text(encoding="utf-8")
        except (UnicodeDecodeError, OSError):
            continue  # binary or unreadable: nothing to cite in
        for number, line in enumerate(text.splitlines(), start=1):
            for match in _CITATION.finditer(line):
                found.setdefault(match[1], {}).setdefault(int(match[2]), []).append(f"{rel}:{number}")
    return found


@dataclass
class SpecCoverage:
    spec: str
    criteria: list[dict] = field(default_factory=list)  # {"ac", "state", "at"}
    struck_citations: list[dict] = field(default_factory=list)  # {"ac", "at"}
    unknown_citations: list[dict] = field(default_factory=list)

    @property
    def uncited(self) -> list[int]:
        return [c["ac"] for c in self.criteria if c["state"] == "uncited"]


def coverage_of(spec_dir: Path, cited: dict[str, dict[int, list[str]]]) -> SpecCoverage:
    spec = parse_spec(spec_dir / "spec.md")
    spec_id = spec.frontmatter.get("id") if isinstance(spec.frontmatter.get("id"), str) else spec_dir.name
    report = SpecCoverage(spec_id)
    live = sorted({c.number for c in spec.criteria if not c.struck})
    struck = {c.number for c in spec.criteria if c.struck} - set(live)
    mine = cited.get(spec_id, {})
    for number in live:
        at = mine.get(number, [])
        report.criteria.append({"ac": number, "state": "cited" if at else "uncited", "at": at})
    for number in sorted(set(mine) - set(live)):
        bucket = report.struck_citations if number in struck else report.unknown_citations
        bucket.extend({"ac": number, "at": at} for at in mine[number])
    return report


def _spec_dirs(root: Path, config: Config, paths: list[str]) -> list[Path]:
    if not paths:
        return sorted(p for p in _all_spec_dirs(config.specs_path(root)) if (p / "spec.md").is_file())
    dirs = []
    for raw in paths:
        path = Path(raw).resolve()
        path = path.parent if path.is_file() else path
        if not (path / "spec.md").is_file():
            raise UsageError(f"{raw}: not a spec directory")
        dirs.append(path)
    return dirs


def _configure(parser: argparse.ArgumentParser) -> None:
    parser.add_argument("paths", nargs="*", metavar="SPEC_DIR", help="spec directories (default: every spec)")


@cli.command("coverage", help="which acceptance criteria tests cite", configure=_configure, needs_config=True)
def run(args: argparse.Namespace, out: Output) -> cli.Result:
    root, config = args.repo_root.resolve(), args.config
    cited = citations(root, test_files(root, config.test_globs))
    reports = []
    for spec_dir in _spec_dirs(root, config, args.paths):
        try:
            reports.append(coverage_of(spec_dir, cited))
        except SpecParseError as exc:
            out.warn(f"{exc}: skipped (run lint)")
    for report in reports:
        for c in report.criteria:
            detail = ", ".join(c["at"]) if c["at"] else ""
            out.print(f"{report.spec}: AC-{c['ac']} {c['state']}" + (f": {detail}" if detail else ""))
        for c in report.struck_citations:
            out.print(f"{report.spec}: AC-{c['ac']} is struck but cited at {c['at']}")
        for c in report.unknown_citations:
            out.print(f"{report.spec}: AC-{c['ac']} does not exist but is cited at {c['at']}")
    uncited = any(r.uncited for r in reports)
    return cli.Result(
        exit_code=EXIT_CHECK_FAILED if uncited else EXIT_OK,
        data={"specs": [r.__dict__ for r in reports]},
    )
