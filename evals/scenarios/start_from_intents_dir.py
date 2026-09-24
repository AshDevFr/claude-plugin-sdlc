"""/sdlc:start on an intent written ahead in intents/: the spec keeps the intent's id."""

from pathlib import Path

from harness import PLUGIN, Step

COMMANDS = ["start"]
SANDBOX = ""
ID = "2026-09-20-webhook-retries"
INTENT = (PLUGIN / "sandbox" / "intents" / "webhook-retries.md").read_text(encoding="utf-8")
ANSWERS = (
    "Improve the intent first: no, proceed as it is. Create a branch: yes. Remove the intents/ "
    "copy now that the spec has its own: yes. Confirm every draft and edit: yes."
)


def setup(repo):
    repo.write(f"intents/{ID}.md", INTENT)
    repo.commit("intent: webhook retries")


STEPS = [Step(f"/sdlc:start intents/{ID}.md", ANSWERS)]


def check(c, repo, runs):
    spec_dir = f"specs/{ID}"
    c.that(repo.exists(f"{spec_dir}/spec.md"), f"no {spec_dir}/spec.md: the id wasn't kept")
    c.that(
        repo.exists(f"{spec_dir}/intent.md") and repo.read(f"{spec_dir}/intent.md") == INTENT,
        "intent not copied as is",
    )
    c.that(not repo.exists(f"intents/{ID}.md"), "the intents/ copy is still there")
    c.that("unchanged" in repo.specs("intent", "check", spec_dir).stdout, "the intent's hash isn't recorded")
    c.that(repo.specs("lint", spec_dir).returncode == 0, "the new spec has lint findings")
    c.that(repo.head() == repo.start_head, "start committed something")
    c.that(not list(Path(repo.path / "specs").glob("2026-09-24-*")), "a spec was created under today's date")
