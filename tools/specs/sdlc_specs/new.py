"""`specs new`: create a spec directory and `spec.md` from the template.

The snapshot is left out: taking it needs the tracker, and until then `lint` reports `L010`
("no snapshot yet") and nothing else.
"""

import argparse
import datetime
import os
import shutil
import subprocess
from pathlib import Path
from string import Template

from . import cli
from .errors import CheckFailed
from .frontmatter import scalar, set_top_level
from .keys import Keys
from .output import Output
from .spec import SpecParseError, parse_spec_text

TEMPLATE = Path(__file__).resolve().parent / "templates" / "spec.md"


def _author(root: Path) -> str:
    result = subprocess.run(
        ["git", "-C", str(root), "config", "user.name"], capture_output=True, text=True, check=False
    )
    name = result.stdout.strip() or os.environ.get("USER", "") or "unknown"
    # A revision entry is `(date, author)`, so the name must not close the parenthesis.
    return name.replace("(", "").replace(")", "")


def render_spec(spec_id: str, title: str, system: str, ref: str, supersedes: list[str], author: str) -> str:
    return Template(TEMPLATE.read_text(encoding="utf-8")).substitute(
        id=scalar(spec_id),
        title=scalar(title),
        system=system,
        ref=scalar(ref),
        supersedes="[" + ", ".join(scalar(s) for s in supersedes) + "]",
        heading=title,
        intent=ref,
        date=datetime.datetime.now(datetime.timezone.utc).date().isoformat(),
        author=author,
    )


def _superseding_edit(old_dir: Path, old_id: str, new_id: str) -> tuple[Path, str]:
    """The old spec's new text, computed before anything is written."""
    spec_path = old_dir / "spec.md"
    if not spec_path.is_file():
        raise CheckFailed(f"--supersedes {old_id}: no spec at {old_dir.name}/spec.md")
    text = spec_path.read_text(encoding="utf-8")
    try:
        spec = parse_spec_text(text, spec_path)
    except SpecParseError as exc:
        raise CheckFailed(f"--supersedes {old_id}: {exc}") from None
    if spec.frontmatter.get("state") == "superseded":
        by = spec.frontmatter.get("superseded_by")
        raise CheckFailed(f"--supersedes {old_id}: already superseded by {by}")
    text = set_top_level(text, "state", "superseded")
    return spec_path, set_top_level(text, "superseded_by", scalar(new_id))


def _configure(parser: argparse.ArgumentParser) -> None:
    parser.add_argument("--key", required=True, help="the ticket: #123, group/project#123 or ENG-123")
    parser.add_argument("--title", required=True, help="the spec title, usually the ticket title")
    parser.add_argument("--slug", help="directory slug (default: from the title)")
    parser.add_argument("--supersedes", metavar="ID", help="id of the spec this one replaces")


@cli.command("new", help="create a spec directory from the template", configure=_configure, needs_config=True)
def run(args: argparse.Namespace, out: Output) -> cli.Result:
    root, config = args.repo_root, args.config
    keys = Keys(config, root)
    key = keys.parse(args.key)
    existing = keys.find_spec_dir(key)
    if existing is not None:
        raise CheckFailed(f"{key.ref()} already has a spec: {existing.relative_to(root).as_posix()}")

    spec_id = keys.dir_name(key, args.slug or args.title)
    specs = config.specs_path(root)
    target = specs / spec_id
    old_edit = (
        _superseding_edit(specs / args.supersedes, args.supersedes, spec_id) if args.supersedes else None
    )

    text = render_spec(
        spec_id,
        args.title,
        config.tracker_kind,
        key.ref(),
        [args.supersedes] if args.supersedes else [],
        _author(root),
    )
    target.mkdir(parents=True)
    try:
        (target / "spec.md").write_text(text, encoding="utf-8")
        if old_edit:
            old_path, old_text = old_edit
            old_path.write_text(old_text, encoding="utf-8")
    except BaseException:
        shutil.rmtree(target, ignore_errors=True)
        raise

    rel = target.relative_to(root).as_posix()
    out.print(rel)
    return cli.Result(data={"path": rel, "id": spec_id})
