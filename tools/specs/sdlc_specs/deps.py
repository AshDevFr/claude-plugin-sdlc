"""Dependencies between specs: `depends_on`, and whether a spec is ready to implement.

`related` only links specs; `depends_on` says a spec can't be built until the specs it names
are. A spec is ready to implement when every spec it depends on has an intent that is `done`.
Its own intent's status is shown but never decides: whether work can start is about what it
builds on. A ticket spec's status is in its tracker, which the helper never reads: as a
dependency it is `unknown (tracker)` and never counts as done, so someone (or, unattended, a
look at the code) has to confirm it.

Everything here is advice: a blocked spec is reported, never refused.

Specs are read lazily, only those reachable from the spec asked about, so the session status
line stays fast in a repository with hundreds of specs.
"""

import argparse
from dataclasses import dataclass, field
from pathlib import Path

import yaml

from . import cli
from .intent_status import (
    DONE,
    INVALID,
    MISSING,
    UNKNOWN_TRACKER,
    split_frontmatter,
    status_of_file,
)
from .new import INTENT_FILE
from .output import Output

READY = "ready"
BLOCKED = "blocked"
DROPPED = "dropped"


@dataclass(frozen=True)
class Node:
    id: str
    status: str  # an intent status, UNKNOWN_TRACKER, INVALID, or MISSING
    depends_on: tuple[str, ...] = ()
    ticket: bool = False  # status lives in a tracker


@dataclass(frozen=True)
class Readiness:
    spec: str
    status: str
    depends_on: tuple[str, ...]
    blocked_by: tuple[Node, ...] = field(default_factory=tuple)  # dependencies not done

    @property
    def ready_to_implement(self) -> bool:
        return not self.blocked_by

    @property
    def verdict(self) -> str:
        if self.status in (DONE, DROPPED):
            return self.status
        return BLOCKED if self.blocked_by else READY


def _frontmatter(path: Path) -> dict | None:
    """A spec's frontmatter, or None when it can't be read (lint reports why)."""
    source, _ = split_frontmatter(path.read_text(encoding="utf-8"))
    if source is None:
        return None
    try:
        data = yaml.safe_load(source)
    except yaml.YAMLError:
        return None
    return data if isinstance(data, dict) else None


def depends_on_of(frontmatter: dict) -> tuple[str, ...]:
    value = frontmatter.get("depends_on")
    if not isinstance(value, list):
        return ()
    return tuple(v for v in value if isinstance(v, str) and v.strip())


class Graph:
    def __init__(self, specs: Path):
        self.specs = specs
        self._nodes: dict[str, Node] = {}

    def node(self, spec_id: str) -> Node:
        if spec_id not in self._nodes:
            self._nodes[spec_id] = self._read(spec_id)
        return self._nodes[spec_id]

    def _read(self, spec_id: str) -> Node:
        from .lint import TEMPLATES_DIR  # lint imports this module

        directory = self.specs / spec_id
        if spec_id in ("", ".", "..", TEMPLATES_DIR) or "/" in spec_id or not directory.is_dir():
            return Node(spec_id, MISSING)
        spec = directory / "spec.md"
        if not spec.is_file():  # an intent written ahead of its spec, or nothing at all
            status = status_of_file(directory / INTENT_FILE)
            return Node(spec_id, status.value if status else MISSING)
        fm = _frontmatter(spec)
        if fm is None:
            return Node(spec_id, INVALID)
        deps = depends_on_of(fm)
        intent = fm.get("intent")
        if "intent" not in fm and "ticket" in fm:
            return Node(spec_id, UNKNOWN_TRACKER, deps, ticket=True)
        name = intent.get("file") if isinstance(intent, dict) else None
        status = status_of_file(directory / (name if isinstance(name, str) else INTENT_FILE))
        return Node(spec_id, status.value if status else MISSING, deps)

    def readiness(self, spec_id: str) -> Readiness:
        node = self.node(spec_id)
        blocked = tuple(self.node(d) for d in node.depends_on if self.node(d).status != DONE)
        return Readiness(spec_id, node.status, node.depends_on, blocked)

    def cycle_through(self, spec_id: str) -> list[str] | None:
        """The shortest dependency path from `spec_id` back to itself, e.g. [a, b, a], or None.
        A spec naming itself is a different finding and isn't followed here."""
        paths = {d: [spec_id, d] for d in self.node(spec_id).depends_on if d != spec_id}
        queue, seen = list(paths), set(paths)
        while queue:
            current = queue.pop(0)
            for dep in self.node(current).depends_on:
                if dep == spec_id:
                    return paths[current] + [spec_id]
                if dep not in seen and dep != current:
                    seen.add(dep)
                    paths[dep] = paths[current] + [dep]
                    queue.append(dep)
        return None

    def order(self, spec_ids: list[str]) -> tuple[list[str], list[str]]:
        """(the specs with each after the ones it depends on, ties by id; the specs on or after a
        cycle, which have no such order, by id)."""
        wanted = set(spec_ids)
        pending = {s: {d for d in self.node(s).depends_on if d in wanted and d != s} for s in wanted}
        ordered = []
        while True:
            free = sorted(s for s, deps in pending.items() if not deps)
            if not free:
                break
            for spec in free:
                ordered.append(spec)
                del pending[spec]
            for deps in pending.values():
                deps.difference_update(free)
        return ordered, sorted(pending)


def all_spec_ids(specs: Path) -> list[str]:
    """Every spec directory holding a spec or an intent written ahead of it."""
    from .lint import _all_spec_dirs

    return sorted(
        p.name for p in _all_spec_dirs(specs) if (p / "spec.md").is_file() or (p / INTENT_FILE).is_file()
    )


def _line(readiness: Readiness) -> str:
    verdict = readiness.verdict
    if verdict in (DONE, DROPPED):
        return f"{readiness.spec}: {readiness.status}"
    line = f"{readiness.spec}: {readiness.status}, {verdict}"
    if readiness.blocked_by:
        return f"{line} by " + ", ".join(f"{n.id} ({n.status})" for n in readiness.blocked_by)
    if readiness.depends_on:
        line += " (after " + ", ".join(readiness.depends_on) + ")"
    return line


@cli.command(
    "deps", help="every spec in dependency order: its intent status, ready or blocked", needs_config=True
)
def run(args: argparse.Namespace, out: Output) -> cli.Result:
    specs = args.config.specs_path(args.repo_root.resolve())
    graph = Graph(specs)
    ordered, unordered = graph.order(all_spec_ids(specs))
    cycles = [s for s in unordered if graph.cycle_through(s)]
    reports = []
    for spec_id in ordered + unordered:
        readiness = graph.readiness(spec_id)
        out.print(_line(readiness))
        reports.append(
            {
                "spec": spec_id,
                "status": readiness.status,
                "verdict": readiness.verdict,
                "depends_on": list(readiness.depends_on),
                "blocked_by": [{"spec": n.id, "status": n.status} for n in readiness.blocked_by],
            }
        )
    if cycles:
        out.print(f"cycle: {', '.join(cycles)} depend on each other (lint L020); listed last")
    return cli.Result(data={"specs": reports, "cycles": cycles})
