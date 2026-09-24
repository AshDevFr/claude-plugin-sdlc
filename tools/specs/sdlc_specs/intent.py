"""`specs intent`: the spec's record of its intent, and whether the intent has moved since.

A spec records the hash of its `intent.md` when it is written. `check` compares that record
with the file now and, with `--diff`, shows what changed since the recorded version, found by
walking the file's git history for the newest committed version with the recorded hash.
`record` takes a new record once the engineer has dealt with the change.
"""

import argparse
import datetime
import difflib
import subprocess
from dataclasses import dataclass
from pathlib import Path

from . import cli
from .branch import current_branch, spec_for_branch
from .errors import EXIT_CHECK_FAILED, EXIT_OK, UsageError
from .frontmatter import scalar, set_top_level_block
from .new import INTENT_FILE, _author, template_text
from .output import Output
from .snapshot import intent_sha256, normalise
from .spec import _LIST_ITEM, Section, SpecParseError, _items, _sections, parse_spec_text

UNCHANGED = "unchanged"
CHANGED = "changed"
NOT_RECORDED = "not recorded"

OPEN_QUESTIONS = "Open questions"
_NO_QUESTIONS = {"none", "none.", "n/a", "no open questions", "no open questions."}


@dataclass(frozen=True)
class IntentState:
    state: str
    intent_path: Path | None
    recorded: str | None  # the recorded hash
    current: str | None  # the file's hash now


def _spec_text(spec_dir: Path) -> str:
    spec = spec_dir / "spec.md"
    if not spec.is_file():
        raise UsageError(f"{spec_dir}: no spec.md")
    return spec.read_text(encoding="utf-8")


def _intent_block(spec_dir: Path, text: str) -> dict:
    try:
        fm = parse_spec_text(text, spec_dir / "spec.md").frontmatter
    except SpecParseError as exc:
        raise UsageError(str(exc)) from None
    block = fm.get("intent")
    return block if isinstance(block, dict) else {}


def state_of(spec_dir: Path) -> IntentState:
    block = _intent_block(spec_dir, _spec_text(spec_dir))
    name = block.get("file") if isinstance(block.get("file"), str) else INTENT_FILE
    path = spec_dir / name
    current = intent_sha256(path.read_text(encoding="utf-8")) if path.is_file() else None
    recorded = block.get("content_sha256") if isinstance(block.get("content_sha256"), str) else None
    if recorded is None:
        return IntentState(NOT_RECORDED, path, None, current)
    return IntentState(UNCHANGED if recorded == current else CHANGED, path, recorded, current)


def _git(root: Path, *args: str) -> subprocess.CompletedProcess:
    return subprocess.run(["git", "-C", str(root), *args], capture_output=True, text=True, check=False)


def recorded_version(root: Path, path: Path, recorded: str) -> tuple[str, str] | None:
    """(commit, text) of the newest committed version of `path` whose hash is `recorded`."""
    rel = path.relative_to(root).as_posix()
    log = _git(root, "log", "--format=%H", "--", rel)
    for sha in log.stdout.split():
        shown = _git(root, "show", f"{sha}:{rel}")
        if shown.returncode == 0 and intent_sha256(shown.stdout) == recorded:
            return sha, shown.stdout
    return None


def diff_since(root: Path, state: IntentState) -> tuple[str | None, str]:
    """The unified diff from the recorded version to the file now, or (None, reason)."""
    found = recorded_version(root, state.intent_path, state.recorded)
    if found is None:
        return None, "no recorded version of the intent was found in git history"
    sha, old = found
    rel = state.intent_path.relative_to(root).as_posix()
    new = state.intent_path.read_text(encoding="utf-8") if state.intent_path.is_file() else ""
    diff = difflib.unified_diff(
        old.splitlines(keepends=True),
        new.splitlines(keepends=True),
        fromfile=f"a/{rel}@{sha[:8]}",
        tofile=f"b/{rel}",
    )
    return "".join(diff), f"since {sha[:8]}"


def record(spec_dir: Path, root: Path) -> str:
    """Record the intent file's current hash in the spec; returns the hash."""
    text = _spec_text(spec_dir)
    block = _intent_block(spec_dir, text)
    name = block.get("file") if isinstance(block.get("file"), str) else INTENT_FILE
    path = spec_dir / name
    if not path.is_file():
        raise UsageError(f"{path.relative_to(root).as_posix()}: no intent file to record")
    digest = intent_sha256(path.read_text(encoding="utf-8"))
    now = datetime.datetime.now(datetime.timezone.utc).strftime("%Y-%m-%dT%H:%M:%SZ")
    children = [
        f"file: {scalar(name)}",
        f"content_sha256: {scalar(digest)}",
        f"recorded_at: {now}",
        f"recorded_by: {scalar(_author(root))}",
    ]
    (spec_dir / "spec.md").write_text(
        set_top_level_block(text, "intent", children, after="title"), encoding="utf-8"
    )
    return digest


def _section_text(section: Section) -> str:
    return normalise("\n".join(text for _, text, _ in section.lines))


def _questions(section: Section | None, guidance: str) -> list[str]:
    """List items when there are any; otherwise each paragraph is one question."""
    if section is None:
        return []
    items = [text for _, _, text in _items(section, _LIST_ITEM)]
    if not items:
        paragraphs, current = [], []
        for _, text, in_fence in section.lines:
            if text.strip() and not in_fence:
                current.append(text.strip())
            elif current:
                paragraphs.append(" ".join(current))
                current = []
        if current:
            paragraphs.append(" ".join(current))
        items = paragraphs
    return [q for q in items if q.lower() not in _NO_QUESTIONS and normalise(q) != guidance]


def assess(text: str, template: str) -> tuple[list[tuple[str, str]], list[str]]:
    """Per-section state (`missing`, `empty`, `template`, `ok`) against the template, and the
    open questions. Judges presence only; what the content says is for a person to judge."""
    template_lines = template.replace("\r\n", "\n").split("\n")
    _, template_sections, _ = _sections(template_lines, 0)
    guidance = {name: _section_text(section) for name, section in template_sections.items()}

    lines = text.replace("\r\n", "\n").replace("\r", "\n").split("\n")
    title, sections, _ = _sections(lines, 0)
    preamble = [
        line for line in lines[: next((i for i, ln in enumerate(lines) if ln.startswith("## ")), len(lines))]
    ]
    states = [
        ("Title", "ok" if title else "missing"),
        ("Author", "ok" if any(line.startswith("Author:") for line in preamble) else "missing"),
    ]
    for name in template_sections:
        section = sections.get(name)
        if section is None:
            state = "missing"
        else:
            content = _section_text(section)
            if not content:
                state = "empty"
            elif guidance[name] and content == guidance[name]:
                state = "template"
            else:
                state = "ok"
        states.append((name, state))
    return states, _questions(sections.get(OPEN_QUESTIONS), guidance.get(OPEN_QUESTIONS, ""))


def _spec_dir(root: Path, raw: str | None, config=None) -> Path:
    if raw is None:
        branch = current_branch(root)
        found = spec_for_branch(root, config, branch) if branch else None
        if found is None:
            raise UsageError("no spec for this branch; pass SPEC_DIR")
        return found
    path = Path(raw).resolve()
    if path.is_file():
        path = path.parent
    if not path.is_dir():
        raise UsageError(f"{raw}: no such spec directory")
    return path


def _configure(parser: argparse.ArgumentParser) -> None:
    sub = parser.add_subparsers(dest="intent_command", metavar="<intent command>", required=True)
    check = sub.add_parser("check", help="has intent.md changed since the spec recorded it?")
    check.add_argument("spec_dir", metavar="SPEC_DIR", nargs="?", help="default: the current branch's spec")
    check.add_argument("--diff", action="store_true", help="show the change since the recorded version")
    rec = sub.add_parser("record", help="record intent.md's current hash in the spec")
    rec.add_argument("spec_dir", metavar="SPEC_DIR", nargs="?", help="default: the current branch's spec")
    ass = sub.add_parser("assess", help="which intent template sections are missing, empty or untouched")
    ass.add_argument("spec_dir", metavar="SPEC_DIR", nargs="?")
    ass.add_argument("--file", metavar="PATH", help="assess this file instead of a spec's intent")


@cli.command("intent", help="the spec's record of its intent", configure=_configure, needs_config=True)
def run(args: argparse.Namespace, out: Output) -> cli.Result:
    root = args.repo_root.resolve()
    if args.intent_command == "assess":
        return _run_assess(args, out, root)
    spec_dir = _spec_dir(root, args.spec_dir, args.config)
    rel = spec_dir.relative_to(root).as_posix()

    if args.intent_command == "record":
        digest = record(spec_dir, root)
        out.print(f"{rel}: intent recorded ({digest[:12]})")
        return cli.Result(data={"spec": rel, "content_sha256": digest})

    state = state_of(spec_dir)
    data = {"spec": rel, "state": state.state, "recorded": state.recorded, "current": state.current}
    out.print(f"{rel}: intent {state.state}")
    if state.state == CHANGED and args.diff:
        diff, note = diff_since(root, state)
        data["diff"] = diff
        if diff is None:
            out.print(f"({note})")
        else:
            out.print(diff.rstrip("\n"))
    return cli.Result(exit_code=EXIT_OK if state.state == UNCHANGED else EXIT_CHECK_FAILED, data=data)


def _run_assess(args: argparse.Namespace, out: Output, root: Path) -> cli.Result:
    if args.file and args.spec_dir:
        raise UsageError("give either SPEC_DIR or --file, not both")
    if args.file:
        path = Path(args.file)
    else:
        spec_dir = _spec_dir(root, args.spec_dir, args.config)
        block = _intent_block(spec_dir, _spec_text(spec_dir))
        path = spec_dir / (block.get("file") if isinstance(block.get("file"), str) else INTENT_FILE)
    if not path.is_file():
        raise UsageError(f"{args.file or path}: no such intent file")
    states, questions = assess(
        path.read_text(encoding="utf-8"), template_text(args.config, root, INTENT_FILE)
    )
    for name, state in states:
        out.print(f"{name}: {state}")
    out.print(f"Open questions: {len(questions)}")
    for question in questions:
        out.print(f"  - {question}")
    return cli.Result(
        data={"sections": [{"section": n, "state": st} for n, st in states], "open_questions": questions}
    )
