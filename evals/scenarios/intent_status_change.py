"""/sdlc:check after the intent's status moved on: the request didn't change, so no /sdlc:sync."""

from fixtures import SPEC_DIR
from harness import Step

COMMANDS = ["check"]
SANDBOX = "intent-status-change"
STEPS = [Step("/sdlc:check")]


def check(c, repo, runs):
    report = runs[-1].final
    c.that("/sdlc:sync" not in report, "a status change sent the engineer to /sdlc:sync")
    c.that("L016" not in report, "a status change was reported as L016")
    c.that("intent changed" not in report.lower(), "a status change was reported as an intent change")
    c.that("ready-for-code" in report, "the intent's status isn't shown")
    c.that(
        "unchanged" in repo.specs("intent", "check", SPEC_DIR).stdout, "the helper says the intent changed"
    )
    c.that(repo.unchanged(), "check changed the repository")
