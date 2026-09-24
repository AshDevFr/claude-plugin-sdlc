"""/sdlc:plan writes a local plan covering every live criterion."""

from fixtures import AC_1, AC_2, SPEC_DIR, filled_spec
from harness import Step

COMMANDS = ["plan"]
SANDBOX = "open-questions"
STRUCK = (
    "- ~~**AC-3** Partners are emailed when a delivery fails for good.~~"
    " Out of scope: the dashboard shows it."
)


def setup(repo):
    filled_spec(repo, criteria=f"{AC_1}\n{AC_2}\n{STRUCK}", commit="spec: filled in")


STEPS = [Step("/sdlc:plan")]


def check(c, repo, runs):
    path = f"{SPEC_DIR}/plan.local.md"
    if not c.that(repo.exists(path), "no plan.local.md"):
        return
    c.that(repo.ignored(path), "plan.local.md isn't ignored by git")
    plan = repo.read(path)
    mapping = plan[plan.find("## Criteria map") :]
    c.that("AC-1" in mapping and "AC-2" in mapping, "the criteria map misses AC-1 or AC-2")
    c.that("2026-09-23-webhook-retries:AC-1" in plan, "steps don't cite <spec-id>:AC-n")
    c.that(repo.unchanged(), "plan changed tracked files or committed")
