"""`specs check`: one report per spec, the local lint before committing.

It combines what the other commands establish (lint findings, criteria no test cites, whether
the intent changed since the spec recorded it) and, with `--ready`, whether the spec is ready
for review. Everything it reports is advice.
"""

import argparse
from dataclasses import asdict
from pathlib import Path

from . import cli
from .branch import current_branch, spec_for_branch
from .config import Config
from .coverage import citations, coverage_of, test_files
from .errors import EXIT_CHECK_FAILED, EXIT_OK, UsageError
from .intent import CHANGED, NOT_RECORDED, UNCHANGED, state_of
from .lint import LintOptions, _all_spec_dirs, lint
from .output import Output
from .spec import SpecParseError, parse_spec

NOT_APPLICABLE = "n/a"  # a ticket spec, which has no intent file
# Rules that --ready reports under their own reason rather than as "lint findings".
_OWN_REASON = {"L008": "open questions", "L017": "template text", "L016": "intent changed"}


def _spec_dirs(root: Path, config: Config, args: argparse.Namespace) -> list[Path]:
    if args.paths:
        dirs = []
        for raw in args.paths:
            path = Path(raw).resolve()
            path = path.parent if path.is_file() else path
            if not (path / "spec.md").is_file():
                raise UsageError(f"{raw}: not a spec directory")
            dirs.append(path)
        return dirs
    if args.all:
        return sorted(p for p in _all_spec_dirs(config.specs_path(root)) if (p / "spec.md").is_file())
    branch = current_branch(root)
    found = spec_for_branch(root, config, branch) if branch else None
    if found is None:
        raise UsageError("no spec for this branch; pass SPEC_DIR, or --all for every spec")
    return [found]


def _intent_state(spec_dir: Path) -> str:
    try:
        has_intent = "intent" in parse_spec(spec_dir / "spec.md").frontmatter
    except SpecParseError:
        return NOT_RECORDED
    return state_of(spec_dir).state if has_intent else NOT_APPLICABLE


def _reasons(findings: list[dict], intent: str) -> list[str]:
    reasons = []
    for rule, reason in _OWN_REASON.items():
        if any(f["rule"] == rule for f in findings) and reason not in reasons:
            reasons.append(reason)
    if any(f["rule"] not in _OWN_REASON for f in findings):
        reasons.append("lint findings")
    if intent == CHANGED and "intent changed" not in reasons:
        reasons.append("intent changed")
    if intent == NOT_RECORDED:
        reasons.append("intent not recorded")
    return reasons


def report(root: Path, config: Config, spec_dirs: list[Path], ready: bool) -> list[dict]:
    findings = [asdict(f) for f in lint(root, config, spec_dirs, LintOptions(ready=ready))]
    cited = citations(root, test_files(root, config.test_globs))
    reports = []
    for spec_dir in spec_dirs:
        prefix = spec_dir.relative_to(root).as_posix() + "/"
        own = [f for f in findings if f["path"].startswith(prefix)]
        try:
            uncited = [f"AC-{n}" for n in coverage_of(spec_dir, cited).uncited]
        except SpecParseError:
            uncited = []  # lint reports the parse error
        intent = _intent_state(spec_dir)
        entry = {"spec": spec_dir.name, "lint": own, "uncited": uncited, "intent": intent}
        if ready:
            # Readiness is for spec review, before code: uncited criteria don't count against it.
            entry["reasons"] = _reasons(own, intent)
            entry["ready"] = not entry["reasons"]
        reports.append(entry)
    return reports


def _configure(parser: argparse.ArgumentParser) -> None:
    parser.add_argument("paths", nargs="*", metavar="SPEC_DIR", help="default: the current branch's spec")
    parser.add_argument("--all", action="store_true", help="every spec in the repository")
    parser.add_argument("--ready", action="store_true", help="also say whether each spec is ready for review")


@cli.command(
    "check", help="lint, citations and intent state for specs", configure=_configure, needs_config=True
)
def run(args: argparse.Namespace, out: Output) -> cli.Result:
    root, config = args.repo_root.resolve(), args.config
    reports = report(root, config, _spec_dirs(root, config, args), args.ready)
    for entry in reports:
        out.print(f"{entry['spec']}:")
        for finding in entry["lint"]:
            where = f":{finding['line']}" if finding["line"] else ""
            out.print(f"  {finding['rule']}{where} {finding['message']}")
        if entry["uncited"]:
            out.print(f"  uncited: {', '.join(entry['uncited'])}")
        out.print(f"  intent {entry['intent']}")
        if args.ready:
            verdict = "yes" if entry["ready"] else "no (" + ", ".join(entry["reasons"]) + ")"
            out.print(f"  ready: {verdict}")
    if args.ready:
        ok = all(entry["ready"] for entry in reports)
    else:
        ok = all(
            not e["lint"] and not e["uncited"] and e["intent"] in (UNCHANGED, NOT_APPLICABLE) for e in reports
        )
    return cli.Result(exit_code=EXIT_OK if ok else EXIT_CHECK_FAILED, data={"specs": reports})
