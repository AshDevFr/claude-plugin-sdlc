"""/sdlc:intent without an intents/ directory: a spec directory holding only the intent."""

from fixtures import AUTHOR_ANSWERS, intent_sections_filled
from harness import Step

COMMANDS = ["intent"]
SANDBOX = ""
STEPS = [Step("/sdlc:intent partners keep losing webhook events", AUTHOR_ANSWERS)]


def check(c, repo, runs):
    dirs = sorted(p.name for p in (repo.path / "specs").glob("*-webhook-retries"))
    if not c.that(len(dirs) == 1, f"expected one intent-only spec dir, found {dirs}"):
        return
    spec_dir = f"specs/{dirs[0]}"
    c.that(sorted(p.name for p in (repo.path / spec_dir).iterdir()) == ["intent.md"], "not intent only")
    c.that(not intent_sections_filled(repo, f"{spec_dir}/intent.md"), "intent sections not filled")
    c.that(repo.specs("lint").returncode == 0, "lint reports the intent-only dir")
    c.that(repo.head() == repo.start_head, "intent committed something")
