"""/sdlc:start on a spec directory holding only its intent: the spec is written beside it."""

from harness import PLUGIN, Step

COMMANDS = ["start"]
SANDBOX = ""
ID = "2026-09-20-webhook-retries"
INTENT = (PLUGIN / "sandbox" / "intents" / "webhook-retries.md").read_text(encoding="utf-8")


def setup(repo):
    repo.write(f"specs/{ID}/intent.md", INTENT)
    repo.commit("intent: webhook retries")


STEPS = [
    Step(
        f"/sdlc:start specs/{ID}",
        "Improve the intent first: no, proceed as it is. Create a branch: yes. "
        "Confirm every draft and edit: yes.",
    )
]


def check(c, repo, runs):
    spec_dir = f"specs/{ID}"
    c.that(repo.exists(f"{spec_dir}/spec.md"), "no spec.md beside the intent")
    c.that(repo.read(f"{spec_dir}/intent.md") == INTENT, "the intent was changed")
    c.that("unchanged" in repo.specs("intent", "check", spec_dir).stdout, "the intent's hash isn't recorded")
    c.that(repo.specs("lint", spec_dir).returncode == 0, "the new spec has lint findings")
    c.that(repo.head() == repo.start_head, "start committed something")
