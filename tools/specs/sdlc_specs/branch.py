"""Which spec the current git branch is for."""

import subprocess
from pathlib import Path

from .config import Config
from .errors import CheckFailed, UsageError
from .keys import Keys


def current_branch(root: Path) -> str | None:
    """The checked-out branch name, or None on a detached HEAD.

    `symbolic-ref` rather than `rev-parse --abbrev-ref`: it also names a branch with no commits
    yet, as in a repo that was just initialised.
    """
    result = subprocess.run(
        ["git", "-C", str(root), "symbolic-ref", "--short", "-q", "HEAD"],
        capture_output=True,
        text=True,
        check=False,
    )
    name = result.stdout.strip()
    return name if result.returncode == 0 and name else None


def spec_for_branch(root: Path, config: Config, branch: str) -> Path | None:
    """The spec whose id appears in the branch name (the longest when several do), else the spec
    of the ticket the branch names."""
    specs = config.specs_path(root)
    if not specs.is_dir():
        return None
    candidates = [p for p in specs.iterdir() if (p / "spec.md").is_file() and p.name in branch]
    if candidates:
        return max(candidates, key=lambda p: len(p.name))
    key = Keys(config, root).resolve_branch(branch)
    if key is None:
        return None
    try:
        found = Keys(config, root).find_spec_dir(key)
    except CheckFailed:
        return None  # two specs for one ticket: lint reports it; a status line shouldn't guess
    # A date id can parse as a ticket number (2026-...); only a directory holding a spec counts.
    return found if found is not None and (found / "spec.md").is_file() else None


def spec_dir_arg(root: Path, config: Config, raw: str | None) -> Path:
    """The spec directory a command was given (a spec.md path counts), else the branch's spec."""
    if raw is not None:
        path = Path(raw).resolve()
        path = path.parent if path.is_file() else path
        if not (path / "spec.md").is_file():
            raise UsageError(f"{raw}: not a spec directory")
        return path
    branch = current_branch(root)
    found = spec_for_branch(root, config, branch) if branch else None
    if found is None:
        raise UsageError("no spec for this branch; pass SPEC_DIR")
    return found


def intent_only_for_branch(root: Path, config: Config, branch: str) -> Path | None:
    """A spec directory named in the branch that holds only an intent, written ahead of its spec."""
    specs = config.specs_path(root)
    if not specs.is_dir():
        return None
    candidates = [
        p
        for p in specs.iterdir()
        if p.name in branch and (p / "intent.md").is_file() and not (p / "spec.md").exists()
    ]
    return max(candidates, key=lambda p: len(p.name)) if candidates else None
