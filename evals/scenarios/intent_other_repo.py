"""/sdlc:intent in a repository not set up for sdlc, following that repository's own guidance."""

from harness import Step

COMMANDS = ["intent"]
SANDBOX = None
GUIDANCE = "# Requests\n\nProduct requests go in `requests/<short-name>.md`, one file per request.\n"


def setup(repo):
    repo.write("CLAUDE.md", GUIDANCE)
    repo.commit("Say where requests go")


STEPS = [Step("/sdlc:intent partners keep losing webhook events", __import__("fixtures").AUTHOR_ANSWERS)]


def check(c, repo, runs):
    files = sorted((repo.path / "requests").glob("*.md")) if repo.exists("requests") else []
    if not c.that(len(files) == 1, f"expected one file in requests/, found {[p.name for p in files]}"):
        return
    text = files[0].read_text(encoding="utf-8")
    for section in ("## Problem", "## Proposed outcome", "## Affected users and systems", "## Constraints"):
        c.that(section in text, f"no {section}")
    c.that(not repo.exists("specs"), "a specs/ directory was created")
    c.that(repo.head() == repo.start_head, "intent committed something")
