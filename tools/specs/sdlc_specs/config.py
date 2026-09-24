"""Load and validate `specs/config.yml`, the one place a repo names its tracker and code host.

Every error names the file and the dotted field, and unknown keys are errors, so a typo fails
the first run instead of silently falling back to a default.
"""

from dataclasses import dataclass
from pathlib import Path
from typing import Any

import yaml

from .errors import ConfigError

CONFIG_NAME = "config.yml"
# Searched in this order; the first one that exists is the config.
SPECS_DIR_CANDIDATES = ("specs", ".specs")

TRACKER_SYSTEMS = ("gitlab", "github", "linear")
HOST_SYSTEMS = ("gitlab", "github")

DEFAULT_SPEC_LABEL = "spec-required"
DEFAULT_TEST_GLOBS = ["**/test*/**", "**/*_test.*", "**/*.test.*", "**/*.spec.*"]

# Fields that only mean something for some systems. Anything else in the section is unknown.
_TRACKER_FIELDS_BY_SYSTEM = {
    "gitlab": {"project"},
    "github": {"project"},
    "linear": {"team_key"},
}
_TRACKER_COMMON = {"system", "spec_label"}
_HOST_FIELDS = {"system", "spec_approvers"}
_TOP_LEVEL = {"tracker", "code_host", "specs_dir", "coverage"}
_COVERAGE = {"test_globs"}


@dataclass(frozen=True)
class Config:
    tracker_system: str  # gitlab | github | linear
    tracker_project: str | None  # gitlab/github: "group/project"; None = the code host repo
    tracker_team_key: str | None  # linear
    spec_label: str
    host_system: str  # gitlab | github
    spec_approvers: str | list[str] | None  # "@group" or ["user", ...]; only suggests CODEOWNERS
    specs_dir: str
    test_globs: list[str]

    def specs_path(self, root: Path) -> Path:
        return root / self.specs_dir


def find_repo_root(start: Path) -> Path:
    """The nearest directory at or above `start` holding `.git` (a directory, or a file in worktrees)."""
    start = start.resolve()
    for candidate in (start, *start.parents):
        if (candidate / ".git").exists():
            return candidate
    raise ConfigError(f"{start}: not inside a git repository")


def load_config(start: Path) -> tuple[Path, Config]:
    """Find the repo root from `start`, then load and validate its config."""
    root = find_repo_root(start)
    for dirname in SPECS_DIR_CANDIDATES:
        path = root / dirname / CONFIG_NAME
        if path.is_file():
            return root, _load_file(path, root)
    tried = " or ".join(f"{d}/{CONFIG_NAME}" for d in SPECS_DIR_CANDIDATES)
    raise ConfigError(f"{tried}: no config file found in {root}")


def _load_file(path: Path, root: Path) -> Config:
    label = path.relative_to(root).as_posix()
    try:
        data = yaml.safe_load(path.read_text(encoding="utf-8"))
    except yaml.YAMLError as exc:
        mark = getattr(exc, "problem_mark", None)
        where = f"line {mark.line + 1}: " if mark is not None else ""
        problem = getattr(exc, "problem", None) or str(exc)
        raise ConfigError(f"{label}: {where}invalid YAML: {problem}") from None
    if data is None:
        raise ConfigError(f"{label}: the file is empty")
    if not isinstance(data, dict):
        raise ConfigError(f"{label}: the top level must be a mapping")
    return _Validator(label).config(data, found_in=path.parent.name)


class _Validator:
    def __init__(self, label: str):
        self.label = label

    def fail(self, field: str, message: str):
        raise ConfigError(f"{self.label}: {field}: {message}")

    def section(self, data: dict, key: str, required: bool) -> dict:
        if key not in data:
            if required:
                self.fail(key, "required")
            return {}
        value = data[key]
        if not isinstance(value, dict):
            self.fail(key, "must be a mapping")
        return value

    def unknown_keys(self, data: dict, allowed: set[str], prefix: str = "") -> None:
        for key in data:
            if key not in allowed:
                self.fail(f"{prefix}{key}", "unknown key")

    def string(self, data: dict, key: str, field: str, required: bool = False) -> str | None:
        if key not in data or data[key] is None:
            if required:
                self.fail(field, "required")
            return None
        value = data[key]
        if not isinstance(value, str) or not value.strip():
            self.fail(field, "must be a non-empty string")
        return value

    def choice(self, data: dict, key: str, field: str, choices: tuple[str, ...]) -> str:
        value = self.string(data, key, field, required=True)
        if value not in choices:
            self.fail(field, f"must be one of {', '.join(choices)} (got {value!r})")
        return value

    def not_for_system(self, data: dict, allowed: set[str], prefix: str, system: str) -> None:
        for key in data:
            if key not in allowed:
                self.fail(f"{prefix}{key}", f"not valid for {system}")

    def config(self, data: dict, found_in: str) -> Config:
        self.unknown_keys(data, _TOP_LEVEL)
        tracker = self.section(data, "tracker", required=True)
        host = self.section(data, "code_host", required=True)
        coverage = self.section(data, "coverage", required=False)

        # Tracker: reject keys no system knows before blaming the selected system.
        all_tracker = _TRACKER_COMMON.union(*_TRACKER_FIELDS_BY_SYSTEM.values())
        self.unknown_keys(tracker, all_tracker, "tracker.")
        system = self.choice(tracker, "system", "tracker.system", TRACKER_SYSTEMS)
        self.not_for_system(tracker, _TRACKER_COMMON | _TRACKER_FIELDS_BY_SYSTEM[system], "tracker.", system)
        team_key = self.string(tracker, "team_key", "tracker.team_key", required=system == "linear")

        self.unknown_keys(host, _HOST_FIELDS, "code_host.")
        host_system = self.choice(host, "system", "code_host.system", HOST_SYSTEMS)

        # specs_dir defaults to where the config was found and may not point elsewhere, or
        # the checks would scan a directory other than the one holding the specs.
        specs_dir = self.string(data, "specs_dir", "specs_dir") or found_in
        if specs_dir != found_in:
            self.fail(
                "specs_dir", f"must be {found_in!r}, the directory holding this file (got {specs_dir!r})"
            )

        self.unknown_keys(coverage, _COVERAGE, "coverage.")

        return Config(
            tracker_system=system,
            tracker_project=self.string(tracker, "project", "tracker.project"),
            tracker_team_key=team_key,
            spec_label=self.string(tracker, "spec_label", "tracker.spec_label") or DEFAULT_SPEC_LABEL,
            host_system=host_system,
            spec_approvers=self.approvers(host),
            specs_dir=specs_dir,
            test_globs=self.test_globs(coverage),
        )

    def approvers(self, host: dict) -> str | list[str] | None:
        field = "code_host.spec_approvers"
        if host.get("spec_approvers") is None:
            return None
        value: Any = host["spec_approvers"]
        if isinstance(value, str):
            if not value.startswith("@") or len(value) < 2:
                self.fail(field, f"a group must start with '@' (got {value!r}); use a list for usernames")
            return value
        if isinstance(value, list) and value and all(isinstance(v, str) and v.strip() for v in value):
            return list(value)
        self.fail(field, "must be a group string or a non-empty list of usernames")

    def test_globs(self, coverage: dict) -> list[str]:
        if "test_globs" not in coverage:
            return list(DEFAULT_TEST_GLOBS)
        value = coverage["test_globs"]
        if isinstance(value, list) and value and all(isinstance(v, str) and v.strip() for v in value):
            return list(value)
        self.fail("coverage.test_globs", "must be a non-empty list of glob strings")
