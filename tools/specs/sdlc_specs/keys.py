"""Ticket references, spec directory names and branch-to-ticket resolution.

Directory names are committed in product repos and match branch names, so the rules here are
settled once:

- A ref in the tracker's home project uses the short prefix (`billing/api#123` is `123` when
  the home project is `billing/api`), so one ticket always has one directory.
- A ref to another project keeps it (`acme/api#123` is `acme-api-123`).
- Linear keys are lowercased (`ENG-123` is `eng-123`).
"""

import re
import subprocess
import unicodedata
from dataclasses import dataclass
from functools import cached_property
from pathlib import Path
from urllib.parse import urlsplit

from .config import Config
from .errors import CheckFailed, ConfigError, UsageError

SLUG_MAX = 50

_NUMBER = r"[1-9][0-9]*"
_SEGMENT = r"[A-Za-z0-9_.][A-Za-z0-9_.-]*"
_HOST_REF = re.compile(rf"^(?:(?P<project>{_SEGMENT}(?:/{_SEGMENT})+))?#(?P<number>{_NUMBER})$")
_BARE_NUMBER = re.compile(rf"^(?P<number>{_NUMBER})$")
_LINEAR_REF = re.compile(rf"^(?P<team>[A-Za-z][A-Za-z0-9]*)-(?P<number>{_NUMBER})$")
_HOST_BRANCH = re.compile(rf"^(?P<number>{_NUMBER})(?:-|$)")
_LINEAR_BRANCH = re.compile(rf"^(?P<team>[A-Za-z][A-Za-z0-9]*)-(?P<number>{_NUMBER})(?:-|$)")
_SCP_REMOTE = re.compile(r"^[^/@:]+@[^/:]+:(?P<path>.+)$")


@dataclass(frozen=True)
class TicketKey:
    system: str  # the tracker kind whose rules apply: gitlab | github | linear
    project: str | None  # lowercased; None for the home project and for linear
    number: int
    team: str | None  # linear team key, uppercased

    def ref(self) -> str:
        """Canonical written form: `#123`, `acme/api#123` or `ENG-123`."""
        if self.team:
            return f"{self.team}-{self.number}"
        if self.project:
            return f"{self.project}#{self.number}"
        return f"#{self.number}"

    def dir_prefix(self) -> str:
        """Spec directory prefix: `123`, `acme-api-123` or `eng-123`."""
        if self.team:
            return f"{self.team.lower()}-{self.number}"
        if self.project:
            return f"{self.project.replace('/', '-')}-{self.number}"
        return str(self.number)


def slugify(text: str) -> str:
    """Lowercase ASCII kebab-case, at most 50 chars. Characters with no ASCII base are dropped."""
    ascii_text = unicodedata.normalize("NFKD", text).encode("ascii", "ignore").decode("ascii")
    slug = re.sub(r"[^a-z0-9]+", "-", ascii_text.lower()).strip("-")
    return slug[:SLUG_MAX].strip("-")


def parse_remote_url(url: str) -> str | None:
    """The `group/project` path of a git remote URL (SSH, scp-like or HTTPS), or None."""
    url = url.strip()
    scp = _SCP_REMOTE.match(url)
    if scp and "://" not in url:
        path = scp["path"]
    else:
        parts = urlsplit(url)
        if parts.scheme not in ("ssh", "git", "http", "https") or not parts.hostname:
            return None
        path = parts.path
    path = path.strip("/")
    if path.endswith(".git"):
        path = path[: -len(".git")]
    segments = path.split("/")
    if len(segments) < 2 or not all(re.fullmatch(_SEGMENT, s) for s in segments):
        return None
    return path


class Keys:
    """Key rules for one repo: its tracker kind, home project and specs directory."""

    def __init__(self, config: Config, root: Path):
        self.config = config
        self.root = root
        self.kind = config.tracker_system

    @cached_property
    def home_project(self) -> str | None:
        if self.config.tracker_project:
            return self.config.tracker_project.lower()
        try:
            result = subprocess.run(
                ["git", "-C", str(self.root), "remote", "get-url", "origin"],
                capture_output=True,
                text=True,
                check=False,
            )
        except OSError:
            return None
        if result.returncode != 0:
            return None
        project = parse_remote_url(result.stdout)
        return project.lower() if project else None

    def parse(self, ref: str) -> TicketKey:
        text = ref.strip()
        if self.kind == "linear":
            match = _LINEAR_REF.match(text)
            if not match:
                raise UsageError(f"{ref!r} is not a Linear issue key (expected e.g. ENG-123)")
            return TicketKey("linear", None, int(match["number"]), match["team"].upper())

        match = _HOST_REF.match(text) or _BARE_NUMBER.match(text)
        if not match:
            raise UsageError(
                f"{ref!r} is not a {self.kind} issue reference (expected #123, 123 or group/project#123)"
            )
        number = int(match["number"])
        project = match.groupdict().get("project")
        if project is None:
            return TicketKey(self.kind, None, number, None)
        if self.kind == "github" and project.count("/") != 1:
            raise UsageError(f"{ref!r}: a GitHub repository is owner/repo")
        return TicketKey(self.kind, self._qualify(project.lower(), ref), number, None)

    def _qualify(self, project: str, ref: str) -> str | None:
        home = self.home_project
        if home is None:
            # Guessing here could put one ticket under two directory names.
            raise ConfigError(
                f"cannot tell whether {ref!r} is in this repo's project: set tracker.project in the "
                "config, or add an 'origin' remote"
            )
        return None if project == home else project

    def dir_name(self, key: TicketKey, title_or_slug: str) -> str:
        slug = slugify(title_or_slug)
        if not slug:
            raise UsageError(f"{title_or_slug!r} gives an empty slug; pass an explicit ASCII slug")
        return f"{key.dir_prefix()}-{slug}"

    def resolve_branch(self, branch: str) -> TicketKey | None:
        """The ticket a branch is for, from its last path segment; None if it names none."""
        name = branch.strip().rsplit("/", 1)[-1]
        if self.kind == "linear":
            match = _LINEAR_BRANCH.match(name)
            if match:
                return TicketKey("linear", None, int(match["number"]), match["team"].upper())
            return None
        match = _HOST_BRANCH.match(name)
        return TicketKey(self.kind, None, int(match["number"]), None) if match else None

    def find_spec_dir(self, key: TicketKey) -> Path | None:
        """The one spec directory for a ticket, None if there is none, CheckFailed if two."""
        specs = self.config.specs_path(self.root)
        if not specs.is_dir():
            return None
        prefix = key.dir_prefix()
        # The trailing dash keeps prefix 12 from matching 123-...
        matches = sorted(
            p for p in specs.iterdir() if p.is_dir() and (p.name == prefix or p.name.startswith(prefix + "-"))
        )
        if len(matches) > 1:
            listed = ", ".join(p.relative_to(self.root).as_posix() for p in matches)
            raise CheckFailed(f"{key.ref()} has more than one spec directory: {listed}")
        return matches[0] if matches else None
