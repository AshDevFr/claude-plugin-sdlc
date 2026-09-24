"""`specs new`: create a spec directory from the templates.

Two kinds of spec. An intent spec (the default) is named `<date>-<slug>`, gets an `intent.md`
from the intent template or a given file, and records that file's hash, so a later change to
the intent can be reported. A ticket spec (`--key`) is named after the ticket and has no
snapshot until one is taken; `lint` reports `L010` for it until then.
"""

import argparse
import datetime
import os
import re
import shutil
import subprocess
from pathlib import Path
from string import Template

from . import cli
from .config import Config
from .errors import CheckFailed, UsageError
from .frontmatter import scalar, set_top_level
from .keys import Keys, slugify
from .output import Output
from .snapshot import intent_sha256
from .spec import SpecParseError, parse_spec_text

TEMPLATES = Path(__file__).resolve().parent / "templates"
INTENT_FILE = "intent.md"
_DATE = re.compile(r"^\d{4}-\d{2}-\d{2}$")


def _author(root: Path) -> str:
    result = subprocess.run(
        ["git", "-C", str(root), "config", "user.name"], capture_output=True, text=True, check=False
    )
    name = result.stdout.strip() or os.environ.get("USER", "") or "unknown"
    # A revision entry is `(date, author)`, so the name must not close the parenthesis.
    return name.replace("(", "").replace(")", "")


def _now() -> datetime.datetime:
    return datetime.datetime.now(datetime.timezone.utc)


def _today() -> str:
    """The engineer's local date: an id names the day they started, as their calendar shows it.
    Recorded timestamps stay UTC."""
    return datetime.date.today().isoformat()


def template_text(config: Config, root: Path, name: str) -> str:
    """The team's copy in `<specs_dir>/templates/` when there is one, else the helper's."""
    custom = config.specs_path(root) / "templates" / name
    return (custom if custom.is_file() else TEMPLATES / name).read_text(encoding="utf-8")


def render_body(template: str, title: str, intent: str, date: str, author: str) -> str:
    # safe_substitute: a team's template may contain a `$` that is not a placeholder.
    return Template(template).safe_substitute(title=title, intent=intent, date=date, author=author)


def render_frontmatter(
    spec_id: str,
    title: str,
    *,
    intent: dict[str, str] | None = None,
    ticket: dict[str, str] | None = None,
    supersedes: list[str] = (),
) -> str:
    """Frontmatter in a fixed key order, written as text so every spec reads the same."""
    lines = ["---", f"id: {scalar(spec_id)}", f"title: {scalar(title)}"]
    if intent:
        lines += [
            "intent:",
            f"  file: {scalar(intent['file'])}",
            f"  content_sha256: {scalar(intent['content_sha256'])}",
            f"  recorded_at: {intent['recorded_at']}",
            f"  recorded_by: {scalar(intent['recorded_by'])}",
        ]
    if ticket:
        lines += ["ticket:", f"  system: {ticket['system']}", f"  ref: {scalar(ticket['ref'])}", '  url: ""']
    lines += [
        "revision: 1",
        "state: active",
        "supersedes: [" + ", ".join(scalar(s) for s in supersedes) + "]",
        "superseded_by: null",
        "---",
        "",
        "",
    ]
    return "\n".join(lines)


def _parse_date(value: str | None) -> str:
    if value is None:
        return _today()
    try:
        if not _DATE.match(value):
            raise ValueError
        return datetime.date.fromisoformat(value).isoformat()
    except ValueError:
        raise UsageError(f"--date {value!r}: expected a real date as YYYY-MM-DD") from None


def intent_spec_id(date: str | None, slug_or_title: str) -> str:
    """`YYYY-MM-DD-<slug>`: the id of a spec, or of an intent written before its spec."""
    slug = slugify(slug_or_title)
    if not slug:
        raise UsageError(f"{slug_or_title!r} gives an empty slug; pass --slug")
    return f"{_parse_date(date)}-{slug}"


def intent_only(path: Path) -> bool:
    """A spec directory holding an intent written ahead of its spec (`/sdlc:intent`)."""
    return (path / INTENT_FILE).is_file() and not (path / "spec.md").exists()


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
    parser.add_argument("--title", required=True, help="the spec title")
    parser.add_argument("--slug", help="directory slug (default: from the title)")
    parser.add_argument("--date", help="intent specs: the id's date, YYYY-MM-DD (default: today, local date)")
    parser.add_argument("--intent-file", metavar="PATH", help="intent specs: copy this file as intent.md")
    parser.add_argument("--key", help="ticket specs: #123, group/project#123 or ENG-123")
    parser.add_argument("--supersedes", metavar="ID", help="id of the spec this one replaces")


def _write(target: Path, files: dict[str, bytes], old_edit: tuple[Path, str] | None) -> None:
    target.mkdir(parents=True)
    try:
        for name, content in files.items():
            (target / name).write_bytes(content)
        if old_edit:
            old_path, old_text = old_edit
            old_path.write_text(old_text, encoding="utf-8")
    except BaseException:
        shutil.rmtree(target, ignore_errors=True)
        raise


def _write_beside(target: Path, spec: bytes, old_edit: tuple[Path, str] | None) -> None:
    (target / "spec.md").write_bytes(spec)
    try:
        if old_edit:
            old_path, old_text = old_edit
            old_path.write_text(old_text, encoding="utf-8")
    except BaseException:
        (target / "spec.md").unlink()
        raise


@cli.command(
    "new", help="create a spec directory from the templates", configure=_configure, needs_config=True
)
def run(args: argparse.Namespace, out: Output) -> cli.Result:
    root, config = args.repo_root, args.config
    specs = config.specs_path(root)
    author = _author(root)
    today = _today()

    if args.key:
        if args.date or args.intent_file:
            raise UsageError("--date and --intent-file are for intent specs; drop them or drop --key")
        keys = Keys(config, root)
        key = keys.parse(args.key)
        existing = keys.find_spec_dir(key)
        if existing is not None:
            raise CheckFailed(f"{key.ref()} already has a spec: {existing.relative_to(root).as_posix()}")
        spec_id = keys.dir_name(key, args.slug or args.title)
        intent_label, intent_block, extra = key.ref(), None, {}
        ticket = {"system": config.tracker_system, "ref": key.ref()}
    else:
        spec_id = intent_spec_id(args.date, args.slug or args.title)
        existing = specs / spec_id / INTENT_FILE
        adopt = intent_only(specs / spec_id)
        if adopt and args.intent_file and Path(args.intent_file).resolve() != existing.resolve():
            raise CheckFailed(
                f"{existing.relative_to(root).as_posix()} already holds this id's intent; "
                "drop --intent-file to write the spec beside it"
            )
        if adopt:
            intent_bytes = existing.read_bytes()
        elif args.intent_file:
            source = Path(args.intent_file)
            if not source.is_file():
                raise UsageError(f"--intent-file {args.intent_file}: no such file")
            intent_bytes = source.read_bytes()
        else:
            intent_bytes = render_body(
                template_text(config, root, INTENT_FILE), args.title, "", today, author
            ).encode("utf-8")
        intent_label = f"[{INTENT_FILE}]({INTENT_FILE})"
        intent_block = {
            "file": INTENT_FILE,
            "content_sha256": intent_sha256(intent_bytes.decode("utf-8")),
            "recorded_at": _now().strftime("%Y-%m-%dT%H:%M:%SZ"),
            "recorded_by": author,
        }
        extra = {INTENT_FILE: intent_bytes}
        ticket = None

    target = specs / spec_id
    if target.exists() and not (ticket is None and intent_only(target)):
        raise CheckFailed(f"{target.relative_to(root).as_posix()} already exists; pick another --slug")
    old_edit = (
        _superseding_edit(specs / args.supersedes, args.supersedes, spec_id) if args.supersedes else None
    )
    text = render_frontmatter(
        spec_id,
        args.title,
        intent=intent_block,
        ticket=ticket,
        supersedes=[args.supersedes] if args.supersedes else [],
    ) + render_body(template_text(config, root, "spec.md"), args.title, intent_label, today, author)
    if target.exists():  # an intent written ahead of its spec: add the spec beside it
        _write_beside(target, text.encode("utf-8"), old_edit)
    else:
        _write(target, {"spec.md": text.encode("utf-8"), **extra}, old_edit)

    rel = target.relative_to(root).as_posix()
    out.print(rel)
    return cli.Result(data={"path": rel, "id": spec_id})
