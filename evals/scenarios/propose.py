"""/sdlc:propose on a filled, uncommitted spec: readiness, a spec commit message, draft PR text."""

from fixtures import filled_spec
from harness import Step, fenced_blocks, parse_trailers

COMMANDS = ["propose"]
SANDBOX = "open-questions"


def setup(repo):
    repo.git("reset", "-q", "--soft", "HEAD~1")  # the spec is new: never committed
    filled_spec(repo)


STEPS = [Step("/sdlc:propose")]


def check(c, repo, runs):
    report = runs[-1].final
    c.that("Draft: Spec for Webhook retries" in report, "no draft PR title")
    trailers = [parse_trailers(block) for block in fenced_blocks(report)]
    c.that(
        any("Spec-Change: initial" in t and "Spec: 2026-09-23-webhook-retries@r1" in t for t in trailers),
        "no commit message ending with Spec and Spec-Change: initial",
    )
    c.that(repo.unchanged(), "propose changed the repository")
