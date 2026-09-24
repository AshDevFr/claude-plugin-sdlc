"""Rendering of the files `/sdlc:init` writes into a product repo.

The templates live in the plugin's `templates/` directory, next to `tools/`; the helper is run
from inside the plugin, so they are always found at the same relative place.
"""

import argparse
import difflib
import hashlib
from dataclasses import dataclass
from pathlib import Path
from string import Template

from . import cli
from .config import find_repo_root, load_config
from .errors import CheckFailed, UsageError
from .frontmatter import scalar
from .output import Output

PLUGIN_TEMPLATES = Path(__file__).resolve().parents[3] / "templates"
HELPER_TEMPLATES = Path(__file__).resolve().parent / "templates"
# sha256 of every spec/intent template version the plugin has shipped. `--upgrade` replaces a
# repo template only when it is one of these, i.e. the team never edited it. Add a line
# whenever a template changes; a test fails until you do.
TEMPLATE_HISTORY = HELPER_TEMPLATES / "HISTORY"
REPO_TEMPLATES = ("spec.md", "intent.md")
DEFAULT_SPECS_DIR = "specs"
BEGIN, END = "<!-- sdlc:begin -->", "<!-- sdlc:end -->"
GITIGNORE_MARKER = "# sdlc:"


def _template(rel: str) -> Template:
    return Template((PLUGIN_TEMPLATES / rel).read_text(encoding="utf-8"))


def _block(lines: list[str]) -> str:
    return "\n".join(lines)


def _render_dropping_empty(template: Template, values: dict[str, str]) -> str:
    """Substitute, then drop the lines that held only a placeholder whose value was empty."""
    out = []
    for line in template.template.split("\n"):
        stripped = line.strip()
        if stripped.startswith("$") and stripped[1:] in values and not values[stripped[1:]]:
            continue
        out.append(Template(line).substitute(values))
    return "\n".join(out)


def render_config(
    tracker: str,
    host: str,
    project: str | None = None,
    team_key: str | None = None,
    approvers: str | list[str] | None = None,
    specs_dir: str | None = None,
) -> str:
    tracker_options = []
    if project:
        tracker_options += [
            "  # tickets live in this project rather than the code repo",
            f"  project: {scalar(project)}",
        ]
    if team_key:
        tracker_options += ["  # Linear team key, as in ENG-123", f"  team_key: {scalar(team_key)}"]
    host_options = []
    if approvers:
        value = (
            scalar(approvers)
            if isinstance(approvers, str)
            else "[" + ", ".join(scalar(a) for a in approvers) + "]"
        )
        host_options += [
            "  # suggested CODEOWNERS for the specs directory: a group, or usernames",
            f"  spec_approvers: {value}",
        ]
    top_options = []
    if specs_dir and specs_dir != DEFAULT_SPECS_DIR:
        top_options += ["# must be the directory holding this file", f"specs_dir: {scalar(specs_dir)}"]
    return _render_dropping_empty(
        _template("specs/config.yml.tmpl"),
        {
            "tracker": tracker,
            "host": host,
            "tracker_options": _block(tracker_options),
            "host_options": _block(host_options),
            "top_options": _block(top_options),
        },
    )


def render_claude_section(specs_dir: str = DEFAULT_SPECS_DIR) -> str:
    return _template("CLAUDE.section.md").substitute(specs_dir=specs_dir)


def render_gitignore(specs_dir: str = DEFAULT_SPECS_DIR) -> str:
    return _template("gitignore.snippet").substitute(specs_dir=specs_dir)


@dataclass
class Item:
    path: str
    outcome: str  # written, appended, present, updated, customised
    content: str | None = None  # what to write, when something is to be written
    diff: str | None = None


def _sha(text: str) -> str:
    return hashlib.sha256(text.encode("utf-8")).hexdigest()


def _shipped_hashes() -> set[str]:
    return {
        line.split()[0] for line in TEMPLATE_HISTORY.read_text(encoding="utf-8").splitlines() if line.strip()
    }


def _append(existing: str, block: str) -> str:
    if not existing:
        return block
    sep = "" if existing.endswith("\n\n") else ("\n" if existing.endswith("\n") else "\n\n")
    return existing + sep + block


def _claude_item(root: Path, section: str, upgrade: bool) -> Item:
    path = root / "CLAUDE.md"
    if not path.exists():
        return Item("CLAUDE.md", "written", section)
    text = path.read_text(encoding="utf-8")
    if BEGIN not in text or END not in text:
        return Item("CLAUDE.md", "appended", _append(text, section))
    start = text.index(BEGIN)
    end = text.index(END) + len(END)
    current = text[start:end]
    wanted = section.rstrip("\n")
    if current == wanted or not upgrade:
        return Item("CLAUDE.md", "present")
    return Item("CLAUDE.md", "updated", text[:start] + wanted + text[end:])


def _gitignore_item(root: Path, snippet: str) -> Item:
    path = root / ".gitignore"
    if not path.exists():
        return Item(".gitignore", "written", snippet)
    text = path.read_text(encoding="utf-8")
    if any(line.startswith(GITIGNORE_MARKER) for line in text.splitlines()):
        return Item(".gitignore", "present")
    return Item(".gitignore", "appended", _append(text, snippet))


def _template_item(rel: str, target: Path, upgrade: bool) -> Item:
    shipped = (HELPER_TEMPLATES / target.name).read_text(encoding="utf-8")
    if not target.exists():
        return Item(rel, "written", shipped)
    current = target.read_text(encoding="utf-8")
    if current == shipped or not upgrade:
        return Item(rel, "present")
    if _sha(current) in _shipped_hashes():
        return Item(rel, "updated", shipped)
    diff = "".join(
        difflib.unified_diff(
            shipped.splitlines(keepends=True),
            current.splitlines(keepends=True),
            fromfile=f"plugin/{target.name}",
            tofile=rel,
        )
    )
    return Item(rel, "customised", diff=diff)


def plan(root: Path, args: argparse.Namespace) -> list[Item]:
    """What `specs init` would do, computed before anything is written."""
    if args.upgrade:
        _, config = load_config(root)
        specs_dir = config.specs_dir
        items = []
    else:
        if not args.tracker or not args.host:
            raise UsageError("--tracker and --host are required (or --upgrade in an initialised repo)")
        specs_dir = args.specs_dir or DEFAULT_SPECS_DIR
        approvers = None
        if args.approvers:
            approvers = (
                args.approvers
                if args.approvers.startswith("@")
                else [a.strip() for a in args.approvers.split(",")]
            )
        config_text = render_config(
            args.tracker, args.host, args.project, args.team_key, approvers, specs_dir
        )
        config_rel = f"{specs_dir}/config.yml"
        config_path = root / config_rel
        if config_path.exists():
            if config_path.read_text(encoding="utf-8") != config_text:
                raise CheckFailed(
                    f"{config_rel} already exists with other settings; edit it by hand or remove it first"
                )
            items = [Item(config_rel, "present")]
        else:
            items = [Item(config_rel, "written", config_text)]
        items.append(_gitignore_item(root, render_gitignore(specs_dir)))
    items.append(_claude_item(root, render_claude_section(specs_dir), args.upgrade))
    for name in REPO_TEMPLATES:
        rel = f"{specs_dir}/templates/{name}"
        items.append(_template_item(rel, root / rel, args.upgrade))
    return items


def apply(root: Path, items: list[Item]) -> None:
    for item in items:
        if item.content is None:
            continue
        path = root / item.path
        path.parent.mkdir(parents=True, exist_ok=True)
        path.write_text(item.content, encoding="utf-8")


def _configure(parser: argparse.ArgumentParser) -> None:
    parser.add_argument("--tracker", choices=("gitlab", "github", "linear"))
    parser.add_argument("--host", choices=("gitlab", "github"))
    parser.add_argument(
        "--project", help="gitlab/github: the project tickets live in, when not the code repo"
    )
    parser.add_argument("--team-key", help="linear: the team key, as in ENG-123")
    parser.add_argument("--approvers", help='a group ("@org/team") or comma-separated usernames')
    parser.add_argument("--specs-dir", choices=("specs", ".specs"))
    parser.add_argument(
        "--upgrade", action="store_true", help="refresh the CLAUDE.md section and untouched templates"
    )
    parser.add_argument("--dry-run", action="store_true", help="report what would change, write nothing")


@cli.command("init", help="set this repo up for the sdlc workflow", configure=_configure)
def run(args: argparse.Namespace, out: Output) -> cli.Result:
    root = find_repo_root(Path.cwd())
    items = plan(root, args)
    if not args.dry_run:
        apply(root, items)
    for item in items:
        out.print(f"{item.outcome:<10} {item.path}")
        if item.diff:
            out.print(item.diff.rstrip("\n"))
    return cli.Result(
        data={
            "items": [
                {"path": i.path, "outcome": i.outcome, **({"diff": i.diff} if i.diff else {})} for i in items
            ]
        }
    )
