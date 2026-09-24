"""/sdlc:check on a spec whose intent changed: reports it and points at /sdlc:sync."""

from harness import Step

COMMANDS = ["check"]
SANDBOX = "intent-changed-impact"
STEPS = [Step("/sdlc:check")]


def check(c, repo, runs):
    report = runs[-1].final
    c.that("/sdlc:sync" in report, "/sdlc:sync isn't named")
    c.that("L016" in report or "changed" in report.lower(), "the intent change isn't reported")
    c.that(repo.unchanged(), "check changed the repository")
