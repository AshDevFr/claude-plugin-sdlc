"""Rendering of the files `/sdlc:init` writes into a product repo.

The templates live in the plugin's `templates/` directory, next to `tools/`; the helper is run
from inside the plugin, so they are always found at the same relative place.
"""

from pathlib import Path
from string import Template

from .frontmatter import scalar

PLUGIN_TEMPLATES = Path(__file__).resolve().parents[3] / "templates"
DEFAULT_SPECS_DIR = "specs"


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
