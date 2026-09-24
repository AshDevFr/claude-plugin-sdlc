"""Which spec the current git branch is for."""

import subprocess
from pathlib import Path

from .config import Config
from .errors import CheckFailed
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
        return Keys(config, root).find_spec_dir(key)
    except CheckFailed:
        return None  # two specs for one ticket: lint reports it; a status line shouldn't guess
