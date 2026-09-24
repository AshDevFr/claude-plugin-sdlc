"""Parse a `spec.md` into frontmatter, sections, acceptance criteria, revisions and open questions.

This is the only reader of the spec format. It reports structure and warnings with line numbers
and never judges: required sections, duplicates and field types are the linter's business.

Parsing is line-based, not CommonMark. Fenced code blocks are tracked so headings and list
items inside them are not mistaken for structure.
"""

import re
from dataclasses import dataclass, field
from pathlib import Path
from typing import Any

import yaml

AC_SECTION = "Acceptance criteria"
REVISIONS_SECTION = "Revisions"
OPEN_QUESTIONS_SECTION = "Open questions"

_FENCE = re.compile(r"^\s{0,3}(```|~~~)")
_H1 = re.compile(r"^#\s+(.*?)\s*#*\s*$")
_H2 = re.compile(r"^##\s+(.*?)\s*#*\s*$")
_AC = re.compile(r"^- \*\*AC-(\d+)\*\*\s+(.*)$")
_AC_STRUCK = re.compile(r"^- ~~\*\*AC-(\d+)\*\*\s+(.*?)~~\s*(.*)$")
_REVISION = re.compile(r"^- \*\*r(\d+)\*\* \((\d{4}-\d{2}-\d{2}), ([^)]+)\):\s*(.*)$")
_LIST_ITEM = re.compile(r"^(?:[-*+]|\d+[.)])\s+(.*)$")
# What a line "looks like an AC" means: after quote markers, a list marker and emphasis, it
# starts with an AC id. A mention in the middle of a sentence is a citation, not a criterion.
_AC_LIKE = re.compile(r"^[\s>]*(?:(?:[-*+]|\d+[.)])\s+)?[~*_]*\s*(AC-\d+)\b")


@dataclass
class ParseWarning:
    line: int
    message: str


@dataclass
class AcceptanceCriterion:
    number: int
    text: str
    struck: bool
    line: int
    reason: str | None = None  # why a struck criterion was dropped


@dataclass
class RevisionEntry:
    number: int
    date: str
    author: str
    text: str
    line: int


@dataclass
class OpenQuestion:
    text: str
    line: int


@dataclass
class Section:
    title: str
    start_line: int  # the heading line
    end_line: int  # last line before the next H2 or end of file
    lines: list[tuple[int, str, bool]] = field(default_factory=list)  # (line, text, in_fence)


@dataclass
class Spec:
    path: Path | None
    frontmatter: dict[str, Any]
    frontmatter_end_line: int  # the closing ---
    key_lines: dict[str, int]  # dotted frontmatter key -> line of the key
    title: str | None  # the H1
    sections: dict[str, Section]  # by H2 title, first occurrence
    criteria: list[AcceptanceCriterion]
    revisions: list[RevisionEntry]
    open_questions: list[OpenQuestion]
    warnings: list[ParseWarning]


class SpecParseError(Exception):
    def __init__(self, path: Path | None, line: int, message: str):
        self.path = path
        self.line = line
        self.message = message
        super().__init__(f"{path if path is not None else '<spec>'}:{line}: {message}")


def parse_spec(path: Path) -> Spec:
    return parse_spec_text(path.read_text(encoding="utf-8"), path)


def parse_spec_text(text: str, path: Path | None = None) -> Spec:
    lines = text.replace("\r\n", "\n").replace("\r", "\n").split("\n")
    frontmatter, end, key_lines = _frontmatter(lines, path)
    title, sections, all_sections = _sections(lines, start=end + 1)

    warnings: list[ParseWarning] = []
    criteria: list[AcceptanceCriterion] = []
    revisions: list[RevisionEntry] = []
    questions: list[OpenQuestion] = []
    for section in all_sections:
        if section.title == AC_SECTION:
            criteria.extend(_criteria(section, warnings))
        else:
            _warn_stray_criteria(section, warnings)
        if section.title == REVISIONS_SECTION:
            revisions.extend(
                RevisionEntry(int(m[1]), m[2], m[3].strip(), text, line)
                for line, m, text in _items(section, _REVISION)
            )
        if section.title == OPEN_QUESTIONS_SECTION:
            questions.extend(OpenQuestion(text, line) for line, _, text in _items(section, _LIST_ITEM))

    warnings.sort(key=lambda w: w.line)
    return Spec(
        path=path,
        frontmatter=frontmatter,
        frontmatter_end_line=end,
        key_lines=key_lines,
        title=title,
        sections=sections,
        criteria=criteria,
        revisions=revisions,
        open_questions=questions,
        warnings=warnings,
    )


def _frontmatter(lines: list[str], path: Path | None) -> tuple[dict[str, Any], int, dict[str, int]]:
    if not lines or lines[0].rstrip() != "---":
        raise SpecParseError(path, 1, "missing frontmatter (--- on the first line)")
    end = next((i for i in range(1, len(lines)) if lines[i].rstrip() in ("---", "...")), None)
    if end is None:
        raise SpecParseError(path, 1, "unterminated frontmatter (no closing ---)")
    source = "\n".join(lines[1:end]) + "\n"
    # YAML line 0 is file line 2.
    try:
        node = yaml.compose(source, Loader=yaml.SafeLoader)
        data = yaml.safe_load(source)
    except yaml.YAMLError as exc:
        mark = getattr(exc, "problem_mark", None) or getattr(exc, "context_mark", None)
        line = mark.line + 2 if mark is not None else 2
        problem = getattr(exc, "problem", None) or str(exc)
        raise SpecParseError(path, line, f"invalid frontmatter YAML: {problem}") from None
    if not isinstance(data, dict):
        raise SpecParseError(path, 2, "frontmatter must be a mapping")
    key_lines: dict[str, int] = {}
    _collect_key_lines(node, "", key_lines)
    return data, end + 1, key_lines


def _collect_key_lines(node: Any, prefix: str, out: dict[str, int]) -> None:
    if not isinstance(node, yaml.MappingNode):
        return
    for key_node, value_node in node.value:
        name = f"{prefix}{key_node.value}"
        out[name] = key_node.start_mark.line + 2
        _collect_key_lines(value_node, name + ".", out)


def _sections(lines: list[str], start: int) -> tuple[str | None, dict[str, Section], list[Section]]:
    title = None
    ordered: list[Section] = []
    current: Section | None = None
    fence: str | None = None
    for index in range(start, len(lines)):
        number = index + 1
        text = lines[index]
        fence_match = _FENCE.match(text)
        if fence_match:
            marker = fence_match[1]
            fence = None if fence == marker else (fence or marker)
            in_fence = True
        else:
            in_fence = fence is not None
        if not in_fence:
            h2 = _H2.match(text)
            if h2:
                current = Section(h2[1], number, number)
                ordered.append(current)
                continue
            h1 = _H1.match(text)
            if h1 and title is None and current is None:
                title = h1[1]
                continue
        if current is not None:
            current.lines.append((number, text, in_fence))
            current.end_line = number
    # A trailing newline leaves one empty element that is not a line of the file.
    if ordered and lines and lines[-1] == "" and ordered[-1].lines and ordered[-1].lines[-1][0] == len(lines):
        ordered[-1].lines.pop()
        ordered[-1].end_line = len(lines) - 1
    sections: dict[str, Section] = {}
    for section in ordered:
        sections.setdefault(section.title, section)
    return title, sections, ordered


def _items(section: Section, pattern: re.Pattern) -> list[tuple[int, re.Match, str]]:
    """Top-level list items matching `pattern`, with indented continuation lines folded in.

    The last capture group is the item's text; continuation lines are appended to it.
    """
    items: list[tuple[int, re.Match, list[str]]] = []
    current: list[str] | None = None
    for number, text, in_fence in section.lines:
        if in_fence or not text.strip():
            current = None
            continue
        if text[0].isspace():
            if current is not None:
                current.append(text.strip())
            continue
        match = pattern.match(text)
        if match:
            current = [match[match.re.groups].strip()]
            items.append((number, match, current))
        else:
            current = None
    return [(number, match, " ".join(p for p in parts if p)) for number, match, parts in items]


def _criteria(section: Section, warnings: list[ParseWarning]) -> list[AcceptanceCriterion]:
    found: list[AcceptanceCriterion] = []
    for number, match, text in _items(section, _AC):
        found.append(AcceptanceCriterion(int(match[1]), text, False, number))
    for number, match, reason in _items(section, _AC_STRUCK):
        found.append(AcceptanceCriterion(int(match[1]), match[2].strip(), True, number, reason or None))
    found.sort(key=lambda c: c.line)
    canonical_lines = {c.line for c in found}
    for number, text, in_fence in section.lines:
        ac = _AC_LIKE.match(text)
        if not ac or number in canonical_lines:
            continue
        warnings.append(ParseWarning(number, _stray_message(ac[1], text, in_fence, section.title)))
    return found


def _warn_stray_criteria(section: Section, warnings: list[ParseWarning]) -> None:
    for number, text, in_fence in section.lines:
        ac = _AC_LIKE.match(text)
        if ac:
            warnings.append(ParseWarning(number, _stray_message(ac[1], text, in_fence, section.title)))


def _stray_message(ac_id: str, text: str, in_fence: bool, section: str) -> str:
    if in_fence:
        return f"{ac_id} inside a code block is not an acceptance criterion"
    if text.lstrip().startswith(">"):
        return f"{ac_id} inside a block quote is not an acceptance criterion"
    if section != AC_SECTION:
        return f"{ac_id} under '## {section}': acceptance criteria belong under '## {AC_SECTION}'"
    return f"{ac_id} is not in the canonical form '- **{ac_id}** <text>'"
