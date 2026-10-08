"""An intent's status: where a request stands, kept in the intent file's own frontmatter.

For an intent kept as a file, the intent is the ticket: no tracker or code host knows whether it
is still being written, ready for a spec, ready for code, done or dropped, so the file says.
A person sets the value; nothing here ever writes it. A ticket spec's status lives in its
tracker, which the helper doesn't read.
"""

from dataclasses import dataclass
from pathlib import Path

import yaml

STATUSES = ("draft", "ready-for-spec", "ready-for-code", "done", "dropped")
DEFAULT_STATUS = "draft"  # no frontmatter, or no status in it: intents from before the field
READY_FOR_CODE = "ready-for-code"
DONE = "done"
INVALID = "invalid"
UNKNOWN_TRACKER = "unknown (tracker)"  # a ticket spec: its tracker knows, the helper doesn't
MISSING = "missing"  # a dependency naming no spec directory


@dataclass(frozen=True)
class IntentStatus:
    value: str  # one of STATUSES, or INVALID
    problem: str | None = None  # why the value is INVALID


def split_frontmatter(text: str) -> tuple[str | None, list[str]]:
    """(the frontmatter's YAML, or None when there is none; the body's lines).

    The same block `snapshot.intent_body` leaves out of the v2 hash: after any blank lines, a
    `---` line, up to the next `---` or `...` line. Without a closing line there is no block.
    """
    lines = text.replace("\r\n", "\n").replace("\r", "\n").split("\n")
    start = 0
    while start < len(lines) and not lines[start].strip():
        start += 1
    if start < len(lines) and lines[start].rstrip() == "---":
        for index in range(start + 1, len(lines)):
            if lines[index].rstrip() in ("---", "..."):
                return "\n".join(lines[start + 1 : index]), lines[index + 1 :]
    return None, lines


def status_of_text(text: str) -> IntentStatus:
    source, _ = split_frontmatter(text)
    if source is None:
        return IntentStatus(DEFAULT_STATUS)
    try:
        data = yaml.safe_load(source)
    except yaml.YAMLError as exc:
        problem = getattr(exc, "problem", None) or str(exc)
        return IntentStatus(INVALID, f"the frontmatter is not valid YAML: {problem}")
    if data is None:
        return IntentStatus(DEFAULT_STATUS)
    if not isinstance(data, dict):
        return IntentStatus(INVALID, "the frontmatter must be a mapping")
    value = data.get("status")
    if value is None:
        return IntentStatus(DEFAULT_STATUS)
    if isinstance(value, str) and value in STATUSES:
        return IntentStatus(value)
    shown = f"'{value}'" if isinstance(value, (str, int, float)) else f"a {type(value).__name__}"
    return IntentStatus(INVALID, f"{shown} is not one of {', '.join(STATUSES)}")


def status_of_file(path: Path) -> IntentStatus | None:
    return status_of_text(path.read_text(encoding="utf-8")) if path.is_file() else None
