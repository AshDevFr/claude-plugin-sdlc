"""The whole lane: start, then plan, implement and check, the spec committed in between."""

import subprocess

from harness import Step, env

COMMANDS = ["start", "plan", "implement", "check"]
SANDBOX = "fresh-intent"
YES = (
    "Improve the intent first: no, proceed as it is. Create a branch: yes. Remove the root intent.md: "
    "yes. Confirm every draft, edit and commit: yes. When asked whether to keep going: yes. If there "
    "are open questions, pick your recommended answer and record it as a decision by Ana Silva. "
    "Keep the spec small: two or three acceptance criteria about retrying failed deliveries."
)


def commit_spec(repo):
    repo.commit("spec: initial")


STEPS = [
    Step("/sdlc:start intent.md --slug webhook-retries", YES),
    Step("/sdlc:plan", YES, before=commit_spec),
    Step("/sdlc:implement", YES),
    Step("/sdlc:check", YES),
]


def check(c, repo, runs):
    dirs = sorted(p.name for p in (repo.path / "specs").glob("*-webhook-retries") if p.is_dir())
    if not c.that(len(dirs) == 1, f"expected one spec, found {dirs}"):
        return
    spec_dir = f"specs/{dirs[0]}"
    c.that(
        repo.ignored(f"{spec_dir}/plan.local.md") and repo.exists(f"{spec_dir}/plan.local.md"),
        "no ignored plan",
    )
    commits = [x for x in repo.trailers(repo.start_head) if x["Implements"]]
    c.that(commits, "no commit implements a criterion")
    c.that(
        all(x["Spec"].startswith(dirs[0] + "@r") for x in commits),
        "an implementing commit lacks its Spec trailer",
    )
    c.that(repo.specs("coverage", spec_dir).returncode == 0, "criteria left uncited")
    c.that(repo.specs("lint", spec_dir).returncode == 0, "the spec has lint findings")
    tests = subprocess.run(["python3", "-m", "unittest"], cwd=repo.path, env=env(), capture_output=True)
    c.that(tests.returncode == 0, "the app's tests fail")
