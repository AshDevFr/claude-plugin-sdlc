"""/sdlc:implement on a spec whose dependency isn't done: warns, names it, and builds nothing."""

from harness import Step

COMMANDS = ["implement"]
SANDBOX = "blocked-spec"
DEPENDENCY = "2026-09-20-delivery-log"

STEPS = [
    Step(
        "/sdlc:implement",
        "When told the spec isn't ready to implement or is blocked by another spec: stop, and "
        "don't write any code until that spec is done.",
    )
]


def check(c, repo, runs):
    report = runs[-1].final
    c.that(DEPENDENCY in report, f"the blocking spec {DEPENDENCY} isn't named")
    c.that(not repo.trailers(repo.start_head), "implement committed despite the blocked spec")
    c.that(repo.unchanged(), "implement changed files despite the blocked spec")
    c.that(
        "status: ready-for-code" in repo.read(f"specs/{DEPENDENCY}/intent.md"),
        "an intent's status was changed",
    )
