"""`specs trailers`: the git trailers that tie a commit or a PR to a spec.

The helper builds and validates them; which criteria a change addresses is the author's call.
"""

import argparse
import re
import subprocess
from pathlib import Path

from . import cli
from .branch import spec_dir_arg
from .errors import CheckFailed, UsageError
from .output import Output
from .spec import Spec, SpecParseError, parse_spec

# The single list of kinds; the commit-conventions skill documents the same set, and a test
# keeps the two from drifting.
SPEC_CHANGE_KINDS = ("initial", "clarify", "amend", "acknowledge", "supersede")

_CRITERION = re.compile(r"AC-(\d+)")
# Separators git log can't produce inside a trailer value.
_RECORD, _FIELD, _VALUE = "\x1e", "\x1d", "\x1f"


def _criteria_arg(raw: str) -> list[int]:
    numbers: list[int] = []
    for item in filter(None, re.split(r"[,\s]+", raw)):
        match = _CRITERION.fullmatch(item)
        if not match:
            raise UsageError(f"--implements: '{item}' is not a criterion (AC-<n>)")
        numbers.append(int(match[1]))
    return numbers


def _problems(spec: Spec, numbers: list[int]) -> dict[int, str]:
    """Criterion number -> why it can't be implemented, for those that can't."""
    by_number = {c.number: c for c in spec.criteria}
    problems = {}
    for number in numbers:
        criterion = by_number.get(number)
        if criterion is None:
            problems[number] = f"AC-{number} does not exist in the spec"
        elif criterion.struck:
            problems[number] = f"AC-{number} is struck"
    return problems


def from_log(root: Path, spec_id: str, base: str) -> list[int]:
    """Criteria in the `Implements:` trailers of `base..HEAD` commits whose `Spec:` names spec_id,
    oldest commit first, each once."""
    verify = subprocess.run(
        ["git", "-C", str(root), "rev-parse", "--verify", "--quiet", f"{base}^{{commit}}"],
        capture_output=True,
        text=True,
        check=False,
    )
    if verify.returncode != 0:
        raise UsageError(f"--from-log: '{base}' is not a commit")
    fmt = (
        "%x1e%(trailers:key=Spec,valueonly,separator=%x1f)"
        "%x1d%(trailers:key=Implements,valueonly,separator=%x1f)"
    )
    log = subprocess.run(
        ["git", "-C", str(root), "log", "--reverse", f"--format={fmt}", f"{base}..HEAD"],
        capture_output=True,
        text=True,
        check=False,
    )
    if log.returncode != 0:
        raise UsageError(f"--from-log: cannot read the log since '{base}'")
    found: list[int] = []
    for record in log.stdout.split(_RECORD)[1:]:
        specs, _, implements = record.partition(_FIELD)
        if spec_id not in (v.split("@")[0].strip() for v in specs.split(_VALUE)):
            continue
        for number in (int(n) for n in _CRITERION.findall(implements)):
            if number not in found:
                found.append(number)
    return found


def _configure(parser: argparse.ArgumentParser) -> None:
    parser.add_argument("path", nargs="?", metavar="SPEC_DIR", help="default: the current branch's spec")
    parser.add_argument("--implements", metavar="AC-n,...", help="the criteria the change implements")
    parser.add_argument(
        "--spec-change",
        metavar="KIND",
        help="for a commit changing the spec: " + ", ".join(SPEC_CHANGE_KINDS),
    )
    parser.add_argument(
        "--from-log", metavar="BASE", help="also the criteria implemented by this spec's commits since BASE"
    )


@cli.command(
    "trailers",
    help="the Spec, Implements and Spec-Change trailers for a commit or PR",
    configure=_configure,
    needs_config=True,
)
def run(args: argparse.Namespace, out: Output) -> cli.Result:
    root, config = args.repo_root.resolve(), args.config
    spec_dir = spec_dir_arg(root, config, args.path)
    try:
        spec = parse_spec(spec_dir / "spec.md")
    except SpecParseError as err:
        raise CheckFailed(str(err)) from None
    spec_id = spec.frontmatter.get("id") or spec_dir.name
    revision = spec.frontmatter.get("revision")
    if isinstance(revision, bool) or not isinstance(revision, int) or revision < 1:
        raise CheckFailed(f"{spec_id}: the spec has no valid 'revision'; run `specs lint`")

    requested = _criteria_arg(args.implements) if args.implements else []
    messages = list(_problems(spec, requested).values())
    if args.spec_change is not None and args.spec_change not in SPEC_CHANGE_KINDS:
        messages.append(
            f"unknown Spec-Change kind '{args.spec_change}' (one of: {', '.join(SPEC_CHANGE_KINDS)})"
        )
    if messages:
        raise CheckFailed("; ".join(messages))

    numbers: list[int] = []
    if args.from_log:
        logged = from_log(root, spec_id, args.from_log)
        # History may name a criterion struck since; the trailers speak for the current revision.
        stale = _problems(spec, logged)
        for number in logged:
            if number in stale:
                out.warn(f"left out: {stale[number]} at r{revision}")
            else:
                numbers.append(number)
    numbers += [n for n in requested if n not in numbers]

    implements = [f"AC-{n}" for n in numbers]
    trailers = [f"Spec: {spec_id}@r{revision}"]
    if implements:
        trailers.append("Implements: " + ", ".join(implements))
    if args.spec_change:
        trailers.append(f"Spec-Change: {args.spec_change}")
    for line in trailers:
        out.print(line)
    return cli.Result(
        data={
            "spec": spec_id,
            "revision": revision,
            "implements": implements,
            "spec_change": args.spec_change,
            "trailers": trailers,
        }
    )
