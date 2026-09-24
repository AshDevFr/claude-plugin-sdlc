"""/sdlc:analyze finds a criterion contradicting a non-goal and a system the spec forgets."""

from fixtures import AC_1, AC_2, filled_spec
from harness import Step

COMMANDS = ["analyze"]
SANDBOX = "open-questions"
AC_3 = (
    "- **AC-3** Given a delivery that fails for good, when retries stop, then the partner is"
    " emailed the event id."
)


def setup(repo):
    filled_spec(
        repo,
        criteria=f"{AC_1}\n{AC_2}\n{AC_3}",
        extra={"Non-goals": "- Notifying partners about failed deliveries, by email or otherwise."},
        commit="spec: filled in",
    )


STEPS = [Step("/sdlc:analyze")]


def check(c, repo, runs):
    report = runs[-1].final
    c.that("AC-3" in report and "Non-goal" in report, "the AC-3 / Non-goals contradiction isn't named")
    c.that("support" in report.lower(), "the support team the intent names isn't mentioned")
    c.that(repo.unchanged(), "analyze changed the repository")
