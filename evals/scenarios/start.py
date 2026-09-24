"""/sdlc:start from an intent.md at the repository root."""

from harness import Step

COMMANDS = ["start"]
SANDBOX = "fresh-intent"
STEPS = [
    Step(
        "/sdlc:start intent.md --slug webhook-retries",
        "Improve the intent first: no, proceed as it is. Create a branch: yes. Remove the root "
        "intent.md now that the spec has its own copy: yes. Confirm every draft and edit: yes.",
    )
]


def check(c, repo, runs):
    dirs = sorted(p for p in (repo.path / "specs").glob("*-webhook-retries") if p.is_dir())
    if not c.that(len(dirs) == 1, f"expected one webhook-retries spec, found {[p.name for p in dirs]}"):
        return
    spec_dir = f"specs/{dirs[0].name}"
    c.that(repo.exists(f"{spec_dir}/intent.md"), "the spec has no intent.md")
    c.that(repo.specs("lint", spec_dir).returncode == 0, "specs lint reports findings on the new spec")
    state = repo.specs("intent", "check", spec_dir).stdout
    c.that("unchanged" in state, f"intent state: {state.strip()}")
    c.that("**AC-1**" in repo.read(f"{spec_dir}/spec.md"), "no AC-1 drafted")
    c.that(repo.head() == repo.start_head, "start committed something")
