"""/sdlc:handoff pauses to a git-ignored file, warning about unpushed commits."""

from fixtures import SPEC_DIR
from harness import Step

COMMANDS = ["handoff"]
SANDBOX = "converge-partial"
EARLIER = (
    "Earlier in this session (summarised, since this is a fresh process): we worked on AC-2. We "
    "decided with the integrations lead that the last status code of a failed delivery is stored "
    "as the integer HTTP status, and as 0 when the connection itself failed; this isn't written "
    "down anywhere yet. We tried storing the whole response object and abandoned it because "
    "responses hold open sockets. Nothing is running now.\n\n/sdlc:handoff"
)
STEPS = [Step(EARLIER, "When asked whether to push: no.")]


def check(c, repo, runs):
    path = f"{SPEC_DIR}/handoff.local.md"
    if not c.that(repo.exists(path), "no handoff.local.md"):
        return
    c.that(repo.ignored(path), "the handoff isn't ignored by git")
    text = repo.read(path)
    c.that("integer" in text and "socket" in text, "the decision or the dead end is missing")
    c.that("handoff waiting" in repo.specs("status").stdout, "status doesn't say handoff waiting")
    c.that(
        "upstream" in runs[-1].final
        or "unpushed" in runs[-1].final.lower()
        or "only on this machine" in runs[-1].final,
        "no warning about unpushed commits",
    )
    c.that(repo.unchanged(), "handoff changed tracked files or committed")
