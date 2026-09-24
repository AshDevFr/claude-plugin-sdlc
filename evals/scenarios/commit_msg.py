"""/sdlc:commit-msg for staged code: trailers from the helper, nothing committed."""

from fixtures import filled_spec, implemented
from harness import Step, fenced_blocks, parse_trailers

COMMANDS = ["commit-msg"]
SANDBOX = "open-questions"


def setup(repo):
    filled_spec(repo, commit="spec: criteria")
    implemented(repo)
    repo.git("add", "-A")


STEPS = [Step("/sdlc:commit-msg")]


def check(c, repo, runs):
    trailers = [parse_trailers(block) for block in fenced_blocks(runs[-1].final)]
    ok = [t for t in trailers if "Spec: 2026-09-23-webhook-retries@r1" in t and "Implements:" in t]
    c.that(ok, "no message ending with Spec and Implements trailers")
    c.that(any("AC-1" in t and "AC-2" in t for t in ok), "Implements doesn't name AC-1 and AC-2")
    c.that(repo.unchanged(), "commit-msg changed the repository")
