"""`specs status`: a one-line summary of the current branch's spec, fast and offline."""

import argparse

from . import cli
from .branch import current_branch, intent_only_for_branch, spec_for_branch
from .intent import state_of
from .lint import LintOptions, lint
from .output import Output
from .spec import SpecParseError, parse_spec

# Where /sdlc:handoff leaves a paused session; `*.local.md` keeps it out of git.
HANDOFF_FILE = "handoff.local.md"


def _waiting(line: str, handoff: bool) -> str:
    return f"{line}, handoff waiting" if handoff else line


@cli.command("status", help="one-line summary of the current branch's spec", needs_config=True)
def run(args: argparse.Namespace, out: Output) -> cli.Result:
    root, config = args.repo_root.resolve(), args.config
    branch = current_branch(root)
    if branch is None:
        out.print("no branch")
        return cli.Result(data={"branch": None, "spec": None})
    spec_dir = spec_for_branch(root, config, branch)
    if spec_dir is None and (waiting := intent_only_for_branch(root, config, branch)) is not None:
        handoff = (waiting / HANDOFF_FILE).is_file()
        out.print(_waiting(f"{waiting.name}: intent only, no spec yet", handoff))
        return cli.Result(
            data={"branch": branch, "spec": waiting.name, "intent": "intent only", "handoff": handoff}
        )
    if spec_dir is None:
        handoff = (config.specs_path(root) / HANDOFF_FILE).is_file()
        out.print(_waiting("no spec for this branch", handoff))
        return cli.Result(data={"branch": branch, "spec": None, "handoff": handoff})

    findings = lint(root, config, [spec_dir], LintOptions())
    try:
        fm = parse_spec(spec_dir / "spec.md").frontmatter
    except SpecParseError:
        fm = {}
    revision = fm.get("revision") if isinstance(fm.get("revision"), int) else None
    intent = state_of(spec_dir).state if "intent" in fm else "n/a"
    rev = f"r{revision}" if revision is not None else "r?"
    handoff = (spec_dir / HANDOFF_FILE).is_file()
    out.print(_waiting(f"{spec_dir.name} {rev}: {len(findings)} lint finding(s), intent {intent}", handoff))
    return cli.Result(
        data={
            "branch": branch,
            "spec": spec_dir.name,
            "revision": revision,
            "lint_findings": len(findings),
            "intent": intent,
            "handoff": handoff,
        }
    )
