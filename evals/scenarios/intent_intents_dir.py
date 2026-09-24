"""/sdlc:intent in a repository that keeps intents in intents/."""

from fixtures import AUTHOR_ANSWERS, intent_sections_filled
from harness import Step

COMMANDS = ["intent"]
SANDBOX = ""


def setup(repo):
    repo.write("intents/.gitkeep", "")
    repo.commit("Keep intents apart from specs")


STEPS = [Step("/sdlc:intent partners keep losing webhook events", AUTHOR_ANSWERS)]


def check(c, repo, runs):
    files = sorted(p.name for p in (repo.path / "intents").glob("*.md"))
    if not c.that(len(files) == 1 and files[0].endswith("-webhook-retries.md"), f"intents/: {files}"):
        return
    path = f"intents/{files[0]}"
    c.that(repo.read(path).startswith("# Intent: Webhook retries"), "no '# Intent:' title")
    c.that(
        not intent_sections_filled(repo, path), f"sections not filled: {intent_sections_filled(repo, path)}"
    )
    c.that(
        not [p for p in (repo.path / "specs").iterdir() if p.is_dir() and p.name != "templates"],
        "a spec dir was created",
    )
    c.that(repo.head() == repo.start_head, "intent committed something")
