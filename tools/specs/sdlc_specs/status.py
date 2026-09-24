"""`specs status`: a one-line summary of the current branch's spec, fast and offline."""

import argparse

from . import cli
from .branch import current_branch, spec_for_branch
from .intent import state_of
from .lint import LintOptions, lint
from .output import Output
from .spec import SpecParseError, parse_spec


@cli.command("status", help="one-line summary of the current branch's spec", needs_config=True)
def run(args: argparse.Namespace, out: Output) -> cli.Result:
    root, config = args.repo_root.resolve(), args.config
    branch = current_branch(root)
    if branch is None:
        out.print("no branch")
        return cli.Result(data={"branch": None, "spec": None})
    spec_dir = spec_for_branch(root, config, branch)
    if spec_dir is None:
        out.print("no spec for this branch")
        return cli.Result(data={"branch": branch, "spec": None})

    findings = lint(root, config, [spec_dir], LintOptions())
    try:
        fm = parse_spec(spec_dir / "spec.md").frontmatter
    except SpecParseError:
        fm = {}
    revision = fm.get("revision") if isinstance(fm.get("revision"), int) else None
    intent = state_of(spec_dir).state if "intent" in fm else "n/a"
    rev = f"r{revision}" if revision is not None else "r?"
    out.print(f"{spec_dir.name} {rev}: {len(findings)} lint finding(s), intent {intent}")
    return cli.Result(
        data={
            "branch": branch,
            "spec": spec_dir.name,
            "revision": revision,
            "lint_findings": len(findings),
            "intent": intent,
        }
    )
