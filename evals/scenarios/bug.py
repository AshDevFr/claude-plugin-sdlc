"""/sdlc:bug assess records a diagnosis and changes no source."""

from harness import Step

COMMANDS = ["bug"]
SANDBOX = ""


def setup(repo):
    repo.write("webhooks.py", repo.read("webhooks.py").replace("500 <= status < 600", "500 < status < 600"))
    repo.commit("refactor: tidy the retry check")


STEPS = [
    Step(
        "/sdlc:bug assess retry-500 Partners report that a delivery answered with HTTP 500 is "
        "dropped without a retry, while 503 is retried."
    )
]


def check(c, repo, runs):
    path = "specs/bugs/retry-500.local.md"
    if not c.that(repo.exists(path), "no bug record"):
        return
    c.that(repo.ignored(path), "the bug record isn't ignored by git")
    c.that("webhooks.py:6" in repo.read(path), "the root cause isn't located at webhooks.py:6")
    c.that(repo.unchanged(), "assess changed source or committed")
