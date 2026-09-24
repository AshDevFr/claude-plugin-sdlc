"""/sdlc:sync on a reworded intent, resolved as no impact."""

from fixtures import SPEC_DIR, filled_spec
from harness import Step

COMMANDS = ["sync"]
SANDBOX = "intent-changed-no-impact"


def setup(repo):
    filled_spec(repo, commit="spec: filled in")


STEPS = [
    Step(
        "/sdlc:sync",
        "The spec has been reviewed and approved. The impact of the intent change: no impact. "
        "Confirm every edit: yes.",
    )
]


def check(c, repo, runs):
    spec = repo.read(f"{SPEC_DIR}/spec.md")
    c.that("revision: 2" in spec, "revision wasn't bumped to 2")
    c.that("- **r2**" in spec, "no r2 revision entry")
    c.that(
        "unchanged" in repo.specs("intent", "check", SPEC_DIR).stdout, "the intent hash wasn't re-recorded"
    )
    c.that(
        repo.specs("lint", "--base", "main", SPEC_DIR).returncode == 0, "lint --base main reports findings"
    )
    c.that(repo.head() == repo.start_head, "sync committed something")
