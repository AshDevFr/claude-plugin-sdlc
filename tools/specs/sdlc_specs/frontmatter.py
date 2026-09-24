"""Edit spec frontmatter as text.

A YAML round trip would reorder keys and drop comments, and specs are reviewed as diffs, so
edits replace only the lines of the value that changes.
"""

import json
import re

import yaml

_FIELD = re.compile(r"^(?P<indent>\s*)(?P<key>[A-Za-z_][\w-]*):(?P<rest>.*)$")
_TRAILING_COMMENT = re.compile(r"(?P<comment>\s+#.*)$")


def scalar(value: str) -> str:
    """Plain YAML when it reads back as the same string, double-quoted otherwise (an all-digit
    hash would load as an int, a username like `yes` as a bool, `#123` as a comment)."""
    try:
        plain_ok = yaml.safe_load(f"k: {value}") == {"k": value}
    except yaml.YAMLError:
        plain_ok = False
    return value if plain_ok and value == value.strip() else json.dumps(value)


def indent_of(line: str) -> int:
    return len(line) - len(line.lstrip(" "))


def block_end(lines: list[str], start: int, stop: int) -> int:
    """Index of the last line of the value whose key is `lines[start]`, looking no further than `stop`."""
    key_indent = indent_of(lines[start])
    end = start
    for index in range(start + 1, stop):
        line = lines[index]
        if not line.strip():
            continue
        if indent_of(line) <= key_indent:
            break
        end = index
    return end


def trailing_comment(rest: str) -> str:
    """The ` # comment` after a value, with its leading gap, or "" (ignored when the value is quoted)."""
    match = _TRAILING_COMMENT.search(rest)
    if not match or '"' in rest[: match.start()] or "'" in rest[: match.start()]:
        return ""
    return match["comment"]


def field_comments(block: list[str]) -> dict[str, str]:
    comments = {}
    for line in block:
        field = _FIELD.match(line)
        if field:
            comment = trailing_comment(field["rest"])
            if comment:
                comments[field["key"]] = comment
    return comments


def split_lines(text: str) -> tuple[list[str], str]:
    newline = "\r\n" if "\r\n" in text else "\n"
    return text.replace("\r\n", "\n").split("\n"), newline


def closing_index(lines: list[str]) -> int:
    if not lines or lines[0].rstrip() != "---":
        raise ValueError("no frontmatter")
    for index in range(1, len(lines)):
        if lines[index].rstrip() in ("---", "..."):
            return index
    raise ValueError("unterminated frontmatter")


def set_top_level(text: str, key: str, value: str) -> str:
    """Set top-level `key` to the already-rendered YAML `value`, keeping a trailing comment and its
    gap; a missing key is added just before the closing `---`."""
    lines, newline = split_lines(text)
    end = closing_index(lines)
    for index in range(1, end):
        field = _FIELD.match(lines[index])
        if field and field["key"] == key and not field["indent"]:
            last = block_end(lines, index, end)
            lines[index : last + 1] = [f"{key}: {value}{trailing_comment(field['rest'])}"]
            break
    else:
        lines.insert(end, f"{key}: {value}")
    return newline.join(lines)
