"""/sdlc:implement follows a plan: tests cite criteria, each commit carries the trailers."""

import subprocess

from fixtures import SPEC_DIR, filled_spec
from harness import Step, env

COMMANDS = ["implement"]
SANDBOX = "open-questions"
PLAN = """# Plan: Webhook retries

Spec: `2026-09-23-webhook-retries` at r1. A local working plan.

## Steps

### 1. deliver() retries server errors with backoff
- **Criteria:** `2026-09-23-webhook-retries:AC-1`
- **Test first:** `tests/test_deliver.py` with a fake `send` and a recording `sleep`.
- **Change:** `webhooks.py`: add `deliver(send, event, sleep)`.
- **Done when:** the test passes; waits recorded are [1, 4].

### 2. client errors are final
- **Criteria:** `2026-09-23-webhook-retries:AC-2`
- **Test first:** `tests/test_deliver.py`: `send` called once on a 400.
- **Done when:** the test passes.

## Criteria map

| Criterion | Steps |
|---|---|
| AC-1 | 1 |
| AC-2 | 2 |
"""


def setup(repo):
    filled_spec(repo, commit="spec: filled in")
    repo.write(f"{SPEC_DIR}/plan.local.md", PLAN)


STEPS = [
    Step("/sdlc:implement", "When asked to confirm a commit: yes. When asked whether to keep going: yes.")
]


def check(c, repo, runs):
    commits = repo.trailers(repo.start_head)
    c.that(commits, "no commits")
    c.that(
        all(x["Spec"] == "2026-09-23-webhook-retries@r1" for x in commits),
        f"a commit lacks the Spec trailer: {commits}",
    )
    implemented = ",".join(x["Implements"] for x in commits)
    c.that(
        "AC-1" in implemented and "AC-2" in implemented,
        f"Implements trailers miss a criterion: {implemented}",
    )
    c.that(repo.specs("coverage", SPEC_DIR).returncode == 0, "specs coverage reports uncited criteria")
    tests = subprocess.run(["python3", "-m", "unittest"], cwd=repo.path, env=env(), capture_output=True)
    c.that(tests.returncode == 0, "the app's tests fail")
    c.that(repo.porcelain() == "", "uncommitted changes left behind")
