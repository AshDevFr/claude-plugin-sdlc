"""`specs lint`: every spec rule that can be decided from the repo alone.

Each rule has a stable ID so pipelines, reviewers and suppressions can name it. A finding
names the rule, the file and the line.
"""

import argparse
import datetime
import re
import subprocess
from dataclasses import asdict, dataclass
from pathlib import Path
from typing import Any

from . import cli
from .config import Config
from .errors import EXIT_CHECK_FAILED, EXIT_OK, UsageError
from .keys import Keys
from .output import Output
from .snapshot import content_sha256, intent_sha256, parse_snapshot_file
from .spec import AC_SECTION, REVISIONS_SECTION, SpecParseError, parse_spec_text

SPEC_FILE = "spec.md"
SNAPSHOT_FILE = "ticket.snapshot.md"

RULES = {
    "L001": "Frontmatter present and parses",
    "L002": "Required frontmatter fields and types; no unknown or approval/PR fields",
    "L003": "id equals the directory name; a ticket spec's directory has the ticket prefix, "
    "an intent spec's is YYYY-MM-DD-<slug>",
    "L004": "ticket.system matches the configured tracker (ticket specs)",
    "L005": "Required sections present, in any order",
    "L006": "AC-n unique; at least one criterion not struck",
    "L007": "No acceptance criterion removed compared to --base (strike it instead)",
    "L008": "With --ready: no open questions",
    "L009": "Every attachment exists in the spec directory",
    "L010": "ticket.snapshot.md exists, parses, and matches ticket.snapshot.content_sha256 (ticket specs)",
    "L011": "With --base: a changed body bumps revision and adds a matching Revisions entry",
    "L012": "state: superseded requires superseded_by",
    "L013": "Acceptance-criterion-like lines that are not canonical criteria",
    "L014": "The spec names its intent: an intent block, a ticket, or both",
    "L015": "The intent file named by intent.file exists in the spec directory",
    "L016": "The intent file has not changed since the spec recorded its hash",
}

REQUIRED_SECTIONS = (
    "Context",
    "Goals",
    "Non-goals",
    AC_SECTION,
    "Design",
    "Risks and security",
    "Rollout and migration",
    "Open questions",
    "Decisions",
    REVISIONS_SECTION,
)

TICKET_SYSTEMS = ("gitlab", "github", "linear")
STATES = ("active", "superseded")
# W§3.1 leaves these out on purpose: approval and PR state live in the code host.
FORBIDDEN_FIELDS = ("approved", "approvers", "pr", "status")
_TOP_FIELDS = {
    "id",
    "title",
    "intent",
    "ticket",
    "revision",
    "state",
    "supersedes",
    "superseded_by",
    "related",
    "attachments",
}
_TICKET_FIELDS = {"system", "ref", "url", "snapshot"}
_SNAPSHOT_FIELDS = {"content_sha256", "updated_at", "taken_by", "taken_at"}
_INTENT_FIELDS = {"file", "content_sha256", "recorded_at", "recorded_by"}
_DATE_ID = re.compile(r"^(?P<date>\d{4}-\d{2}-\d{2})-[a-z0-9]+(?:-[a-z0-9]+)*$")
_SHA = re.compile(r"^[0-9a-f]{64}$")
_TIMESTAMP = re.compile(r"^\d{4}-\d{2}-\d{2}T\d{2}:\d{2}:\d{2}Z$")


@dataclass(frozen=True)
class Finding:
    rule: str
    path: str
    line: int | None
    message: str

    def render(self) -> str:
        where = f"{self.path}:{self.line}" if self.line is not None else self.path
        return f"{where}: {self.rule} {self.message}"


@dataclass(frozen=True)
class LintOptions:
    ready: bool = False
    base: str | None = None


class _SpecLinter:
    def __init__(self, spec_dir: Path, root: Path, config: Config, keys: Keys, options: LintOptions):
        self.dir = spec_dir
        self.root = root
        self.config = config
        self.keys = keys
        self.options = options
        self.spec_path = spec_dir / SPEC_FILE
        self.rel = self.spec_path.relative_to(root).as_posix()
        self.findings: list[Finding] = []

    def add(self, rule: str, line: int | None, message: str, path: str | None = None) -> None:
        self.findings.append(Finding(rule, path or self.rel, line, message))

    def run(self) -> list[Finding]:
        if not self.spec_path.is_file():
            self.add("L001", None, f"no {SPEC_FILE} in the spec directory")
            return self.findings
        text = self.spec_path.read_text(encoding="utf-8")
        try:
            spec = parse_spec_text(text, self.spec_path)
        except SpecParseError as exc:
            self.add("L001", exc.line, exc.message)
            return self.findings
        self.spec = spec
        fm = spec.frontmatter
        self.fields(fm)
        self.naming(fm)
        self.intent_source(fm)
        self.system(fm)
        self.sections()
        self.criteria()
        if self.options.ready:
            for question in spec.open_questions:
                self.add("L008", question.line, f"open question left: {question.text}")
        self.attachments(fm)
        self.snapshot(fm)
        self.superseded(fm)
        for warning in spec.warnings:
            self.add("L013", warning.line, warning.message)
        if self.options.base:
            self.against_base(text)
        return self.findings

    def line_of(self, key: str) -> int:
        return self.spec.key_lines.get(key, 1)

    # L002
    def fields(self, fm: dict[str, Any]) -> None:
        for key in fm:
            if key in FORBIDDEN_FIELDS:
                self.add(
                    "L002",
                    self.line_of(key),
                    f"'{key}' must not be stored in the spec: "
                    "approval and PR state are read from the code host",
                )
            elif key not in _TOP_FIELDS:
                self.add("L002", self.line_of(key), f"unknown field '{key}'")
        self.require_str(fm, "id")
        self.require_str(fm, "title")
        revision = fm.get("revision")
        if "revision" not in fm:
            self.add("L002", 1, "missing required field 'revision'")
        elif isinstance(revision, bool) or not isinstance(revision, int) or revision < 1:
            self.add("L002", self.line_of("revision"), "'revision' must be an integer of at least 1")
        if "state" not in fm:
            self.add("L002", 1, "missing required field 'state'")
        elif fm["state"] not in STATES:
            self.add("L002", self.line_of("state"), f"'state' must be one of {', '.join(STATES)}")
        for key in ("supersedes", "related", "attachments"):
            if key in fm and not _str_list(fm[key]):
                self.add("L002", self.line_of(key), f"'{key}' must be a list of strings")
        if fm.get("superseded_by") is not None and not _nonempty_str(fm["superseded_by"]):
            self.add("L002", self.line_of("superseded_by"), "'superseded_by' must be a spec id or null")

        if "intent" in fm:
            self.intent_fields(fm["intent"])
        if "ticket" not in fm:
            return
        ticket = fm["ticket"]
        if not isinstance(ticket, dict):
            self.add("L002", self.line_of("ticket"), "'ticket' must be a mapping with system and ref")
            return
        for key in ticket:
            if key not in _TICKET_FIELDS:
                self.add("L002", self.line_of(f"ticket.{key}"), f"unknown field 'ticket.{key}'")
        if ticket.get("system") not in TICKET_SYSTEMS:
            self.add(
                "L002",
                self.line_of("ticket.system"),
                f"'ticket.system' must be one of {', '.join(TICKET_SYSTEMS)}",
            )
        self.require_str(ticket, "ref", "ticket.")
        if ticket.get("url") is not None and not isinstance(ticket["url"], str):
            self.add("L002", self.line_of("ticket.url"), "'ticket.url' must be a string")
        if "snapshot" in ticket:
            self.snapshot_fields(ticket["snapshot"])

    def intent_fields(self, intent: Any) -> None:
        if not isinstance(intent, dict):
            self.add(
                "L002", self.line_of("intent"), "'intent' must be a mapping with file and content_sha256"
            )
            return
        for key in intent:
            if key not in _INTENT_FIELDS:
                self.add("L002", self.line_of(f"intent.{key}"), f"unknown field 'intent.{key}'")
        self.require_str(intent, "file", "intent.")
        if not (isinstance(intent.get("content_sha256"), str) and _SHA.match(intent["content_sha256"])):
            self.add(
                "L002",
                self.line_of("intent.content_sha256")
                if "content_sha256" in intent
                else self.line_of("intent"),
                "'intent.content_sha256' must be 64 lowercase hex characters",
            )
        if "recorded_at" in intent and not _timestamp(intent["recorded_at"]):
            self.add(
                "L002", self.line_of("intent.recorded_at"), "'intent.recorded_at' must be a UTC timestamp"
            )
        if "recorded_by" in intent and not _nonempty_str(intent["recorded_by"]):
            self.add("L002", self.line_of("intent.recorded_by"), "'intent.recorded_by' must be a name")

    def snapshot_fields(self, snap: Any) -> None:
        if not isinstance(snap, dict):
            self.add("L002", self.line_of("ticket.snapshot"), "'ticket.snapshot' must be a mapping")
            return
        for key in snap:
            if key not in _SNAPSHOT_FIELDS:
                self.add(
                    "L002", self.line_of(f"ticket.snapshot.{key}"), f"unknown field 'ticket.snapshot.{key}'"
                )
        if not (isinstance(snap.get("content_sha256"), str) and _SHA.match(snap["content_sha256"])):
            self.add(
                "L002",
                self.line_of("ticket.snapshot.content_sha256"),
                "'ticket.snapshot.content_sha256' must be 64 lowercase hex characters",
            )
        for key in ("taken_at", "updated_at"):
            if key in snap and not _timestamp(snap[key]):
                self.add(
                    "L002",
                    self.line_of(f"ticket.snapshot.{key}"),
                    f"'ticket.snapshot.{key}' must be a UTC timestamp",
                )
        if "taken_at" not in snap:
            self.add("L002", self.line_of("ticket.snapshot"), "missing 'ticket.snapshot.taken_at'")
        if not _nonempty_str(snap.get("taken_by")):
            self.add("L002", self.line_of("ticket.snapshot"), "'ticket.snapshot.taken_by' must be a username")

    def require_str(self, data: dict, key: str, prefix: str = "") -> None:
        if key not in data:
            self.add(
                "L002",
                self.line_of(prefix.rstrip(".")) if prefix else 1,
                f"missing required field '{prefix}{key}'",
            )
        elif not _nonempty_str(data[key]):
            self.add("L002", self.line_of(prefix + key), f"'{prefix}{key}' must be a non-empty string")

    # L003
    def naming(self, fm: dict[str, Any]) -> None:
        if _nonempty_str(fm.get("id")) and fm["id"] != self.dir.name:
            self.add(
                "L003",
                self.line_of("id"),
                f"id '{fm['id']}' does not match the directory name '{self.dir.name}'",
            )
        if "ticket" not in fm:
            self.date_id(fm)
            return
        ticket = fm.get("ticket")
        if not isinstance(ticket, dict) or not _nonempty_str(ticket.get("ref")):
            return
        try:
            key = self.keys.parse(ticket["ref"])
        except UsageError as exc:
            self.add("L003", self.line_of("ticket.ref"), exc.message)
            return
        prefix = key.dir_prefix()
        if self.dir.name != prefix and not self.dir.name.startswith(prefix + "-"):
            self.add(
                "L003",
                self.line_of("ticket.ref"),
                f"directory '{self.dir.name}' does not start with '{prefix}-', the prefix of {key.ref()}",
            )

    def date_id(self, fm: dict[str, Any]) -> None:
        if not _nonempty_str(fm.get("id")):
            return
        match = _DATE_ID.match(fm["id"])
        valid = bool(match)
        if match:
            try:
                datetime.date.fromisoformat(match["date"])
            except ValueError:
                valid = False
        if not valid:
            self.add(
                "L003",
                self.line_of("id"),
                f"id '{fm['id']}' must be YYYY-MM-DD-<slug> with a real date when the spec has no ticket",
            )

    # L014, L015
    def intent_source(self, fm: dict[str, Any]) -> None:
        if "intent" not in fm and "ticket" not in fm:
            self.add("L014", self.line_of("id"), "the spec names no intent: add an intent block or a ticket")
            return
        intent = fm.get("intent")
        if not isinstance(intent, dict) or not _nonempty_str(intent.get("file")):
            return  # L002 reports the shape
        name = intent["file"]
        if name.startswith("/") or ".." in Path(name).parts:
            self.add(
                "L015", self.line_of("intent.file"), f"intent file '{name}' must be inside the spec directory"
            )
        elif not (self.dir / name).is_file():
            self.add(
                "L015",
                self.line_of("intent.file"),
                f"intent file '{name}' does not exist in the spec directory",
            )
        elif isinstance(intent.get("content_sha256"), str) and _SHA.match(intent["content_sha256"]):
            current = intent_sha256((self.dir / name).read_text(encoding="utf-8"))
            if current != intent["content_sha256"]:
                self.add(
                    "L016",
                    self.line_of("intent.content_sha256"),
                    f"{name} changed since the spec recorded it: review the spec with /sdlc:sync",
                )

    # L004
    def system(self, fm: dict[str, Any]) -> None:
        ticket = fm.get("ticket")
        if not isinstance(ticket, dict) or "system" not in ticket:
            return
        expected = self.config.tracker_system
        if ticket["system"] != expected:
            self.add(
                "L004",
                self.line_of("ticket.system"),
                f"ticket.system is '{ticket['system']}' but this repo's tracker is '{expected}'",
            )

    # L005
    def sections(self) -> None:
        anchor = self.spec.frontmatter_end_line
        for title in REQUIRED_SECTIONS:
            if title not in self.spec.sections:
                self.add("L005", anchor, f"missing section '## {title}'")

    # L006
    def criteria(self) -> None:
        first_seen: dict[int, int] = {}
        for criterion in self.spec.criteria:
            if criterion.number in first_seen:
                self.add(
                    "L006",
                    criterion.line,
                    f"AC-{criterion.number} is defined twice (first at line {first_seen[criterion.number]})",
                )
            else:
                first_seen[criterion.number] = criterion.line
        if not any(not c.struck for c in self.spec.criteria):
            section = self.spec.sections.get(AC_SECTION)
            self.add(
                "L006",
                section.start_line if section else self.spec.frontmatter_end_line,
                "no acceptance criterion that is not struck",
            )

    # L009
    def attachments(self, fm: dict[str, Any]) -> None:
        entries = fm.get("attachments")
        if not _str_list(entries):
            return
        line = self.line_of("attachments")
        for entry in entries:
            if entry.startswith("/") or ".." in Path(entry).parts:
                self.add("L009", line, f"attachment '{entry}' must be a path inside the spec directory")
            elif not (self.dir / entry).is_file():
                self.add(
                    "L009",
                    line,
                    f"attachment '{entry}' does not exist in {self.dir.relative_to(self.root).as_posix()}",
                )

    # L010
    def snapshot(self, fm: dict[str, Any]) -> None:
        if "ticket" not in fm:
            return  # intent specs have no ticket receipt
        ticket = fm.get("ticket")
        snap = ticket.get("snapshot") if isinstance(ticket, dict) else None
        if not isinstance(snap, dict):
            self.add("L010", self.line_of("ticket"), "no snapshot yet: take one before the spec is reviewed")
            return
        path = self.dir / SNAPSHOT_FILE
        rel = path.relative_to(self.root).as_posix()
        if not path.is_file():
            self.add("L010", self.line_of("ticket.snapshot"), f"{SNAPSHOT_FILE} is missing")
            return
        try:
            parsed = parse_snapshot_file(path.read_text(encoding="utf-8"))
        except ValueError as exc:
            self.add("L010", 1, f"not a valid snapshot file: {exc}", path=rel)
            return
        if content_sha256(parsed.title, parsed.description) != parsed.sha256:
            self.add(
                "L010", 3, "the snapshot body does not match its own hash: it was edited by hand", path=rel
            )
        if parsed.sha256 != snap.get("content_sha256"):
            self.add(
                "L010",
                self.line_of("ticket.snapshot.content_sha256"),
                f"content_sha256 does not match {SNAPSHOT_FILE} ({parsed.sha256[:12]}...)",
            )
        if isinstance(ticket.get("ref"), str) and parsed.ref != ticket["ref"]:
            self.add("L010", 2, f"snapshot is of {parsed.ref}, but ticket.ref is {ticket['ref']}", path=rel)

    # L012
    def superseded(self, fm: dict[str, Any]) -> None:
        if fm.get("state") == "superseded" and not _nonempty_str(fm.get("superseded_by")):
            self.add("L012", self.line_of("state"), "state is superseded but superseded_by is not set")

    # L007, L011
    def against_base(self, text: str) -> None:
        base_text = _git_show(self.root, self.options.base, self.rel)
        if base_text is None:
            return  # new since base: nothing to compare against
        try:
            base = parse_spec_text(base_text)
        except SpecParseError:
            return
        current = {c.number for c in self.spec.criteria}
        section = self.spec.sections.get(AC_SECTION)
        anchor = section.start_line if section else self.spec.frontmatter_end_line
        for number in sorted({c.number for c in base.criteria} - current):
            self.add("L007", anchor, f"AC-{number} was removed; strike it through with a reason instead")

        if _body(base_text) == _body(text):
            return
        revision = self.spec.frontmatter.get("revision")
        base_revision = base.frontmatter.get("revision")
        if not isinstance(revision, int) or not isinstance(base_revision, int):
            return  # L002 reports the type problem
        if revision <= base_revision:
            self.add(
                "L011",
                self.line_of("revision"),
                f"the body changed since {self.options.base} but revision is still {revision}",
            )
        elif not any(r.number == revision for r in self.spec.revisions):
            revisions = self.spec.sections.get(REVISIONS_SECTION)
            self.add(
                "L011",
                revisions.start_line if revisions else self.line_of("revision"),
                f"revision is {revision} but '## Revisions' has no r{revision} entry",
            )


def _nonempty_str(value: Any) -> bool:
    return isinstance(value, str) and bool(value.strip())


def _str_list(value: Any) -> bool:
    return isinstance(value, list) and all(_nonempty_str(v) for v in value)


def _timestamp(value: Any) -> bool:
    return isinstance(value, datetime.datetime) or (isinstance(value, str) and bool(_TIMESTAMP.match(value)))


def _body(text: str) -> str:
    """Everything after the frontmatter, line endings normalised."""
    lines = text.replace("\r\n", "\n").split("\n")
    for index in range(1, len(lines)):
        if lines[index].rstrip() in ("---", "..."):
            return "\n".join(lines[index + 1 :])
    return ""


def _git(root: Path, *args: str) -> subprocess.CompletedProcess:
    return subprocess.run(["git", "-C", str(root), *args], capture_output=True, text=True, check=False)


def _verify_ref(root: Path, ref: str) -> None:
    if _git(root, "rev-parse", "--verify", "--quiet", f"{ref}^{{commit}}").returncode != 0:
        raise UsageError(f"'{ref}' is not a commit in this repository")


def _git_show(root: Path, ref: str, rel: str) -> str | None:
    result = _git(root, "show", f"{ref}:{rel}")
    return result.stdout if result.returncode == 0 else None


def changed_spec_dirs(root: Path, specs_dir: Path, ref: str) -> set[Path]:
    """Spec directories with a file changed between `ref` and the working tree, or untracked."""
    _verify_ref(root, ref)
    diff = _git(root, "diff", "--name-only", ref, "--")
    untracked = _git(root, "ls-files", "--others", "--exclude-standard")
    prefix = specs_dir.relative_to(root).as_posix() + "/"
    dirs = set()
    for name in (diff.stdout + untracked.stdout).splitlines():
        if name.startswith(prefix) and "/" in name[len(prefix) :]:
            candidate = specs_dir / name[len(prefix) :].split("/", 1)[0]
            if candidate.is_dir():
                dirs.add(candidate)
    return dirs


def select_spec_dirs(root: Path, config: Config, paths: list[str], changed_since: str | None) -> list[Path]:
    specs = config.specs_path(root)
    if paths:
        selected = set()
        for raw in paths:
            path = Path(raw).resolve()
            if not path.exists():
                raise UsageError(f"{raw}: no such file or directory")
            if path.is_file():
                path = path.parent
            if path == specs.resolve():
                selected |= _all_spec_dirs(specs)
            else:
                selected.add(path)
    else:
        selected = _all_spec_dirs(specs)
    if changed_since:
        changed = {p.resolve() for p in changed_spec_dirs(root, specs, changed_since)}
        selected = {p for p in selected if p.resolve() in changed}
    return sorted(selected)


def _all_spec_dirs(specs: Path) -> set[Path]:
    return {p for p in specs.iterdir() if p.is_dir()} if specs.is_dir() else set()


def lint(root: Path, config: Config, spec_dirs: list[Path], options: LintOptions) -> list[Finding]:
    if options.base:
        _verify_ref(root, options.base)
    keys = Keys(config, root)
    findings: list[Finding] = []
    for spec_dir in spec_dirs:
        findings += _SpecLinter(spec_dir.resolve(), root.resolve(), config, keys, options).run()
    return sorted(findings, key=lambda f: (f.path, f.line if f.line is not None else 0, f.rule))


def _configure(parser: argparse.ArgumentParser) -> None:
    parser.add_argument("paths", nargs="*", help="spec directories (default: every one under the specs dir)")
    parser.add_argument("--changed-since", metavar="REF", help="only spec directories changed since REF")
    parser.add_argument(
        "--ready", action="store_true", help="also apply the rules for a spec ready for review"
    )
    parser.add_argument(
        "--base", metavar="REF", help="compare with the spec at REF (removed ACs, revision bumps)"
    )


@cli.command("lint", help="check specs against the spec rules", configure=_configure, needs_config=True)
def run(args: argparse.Namespace, out: Output) -> cli.Result:
    spec_dirs = select_spec_dirs(args.repo_root, args.config, args.paths, args.changed_since)
    findings = lint(args.repo_root, args.config, spec_dirs, LintOptions(ready=args.ready, base=args.base))
    for finding in findings:
        out.print(finding.render())
    count = len(spec_dirs)
    noun = "spec" if count == 1 else "specs"
    out.warn(f"{len(findings)} finding(s) in {count} {noun}" if findings else f"{count} {noun} clean")
    return cli.Result(
        exit_code=EXIT_CHECK_FAILED if findings else EXIT_OK,
        data={"findings": [asdict(f) for f in findings]},
    )
