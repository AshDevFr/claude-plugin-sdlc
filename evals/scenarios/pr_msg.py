"""/sdlc:pr-msg on a branch with implemented criteria and a spec that references a ticket."""

from fixtures import SPEC_DIR, filled_spec, implemented
from harness import Step

COMMANDS = ["pr-msg"]
SANDBOX = "open-questions"
TICKET = (
    "ticket:\n  system: github\n  ref: acme/webhooks#42\n  url: https://github.com/acme/webhooks/issues/42\n"
)


def setup(repo):
    filled_spec(repo)
    spec = repo.read(f"{SPEC_DIR}/spec.md").replace("revision: 1\n", TICKET + "revision: 1\n", 1)
    repo.write(f"{SPEC_DIR}/spec.md", spec)
    repo.commit(
        "spec(2026-09-23-webhook-retries): r1 criteria\n\n"
        "Spec: 2026-09-23-webhook-retries@r1\nSpec-Change: clarify"
    )
    implemented(repo)
    repo.commit("feat: retry deliveries\n\nSpec: 2026-09-23-webhook-retries@r1\nImplements: AC-1, AC-2")


STEPS = [Step("/sdlc:pr-msg main")]


def check(c, repo, runs):
    report = runs[-1].final
    c.that("Closes acme/webhooks#42" in report, "no closing keyword for the spec's ticket")
    c.that("Implements: AC-1, AC-2" in report, "the trailers from the branch's commits are missing")
    c.that("Spec: 2026-09-23-webhook-retries@r1" in report, "no Spec trailer")
    c.that(repo.unchanged(), "pr-msg changed the repository")
