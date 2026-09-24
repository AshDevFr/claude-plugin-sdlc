"""/sdlc:init in a repository that has never seen the plugin."""

from harness import Step

COMMANDS = ["init"]
SANDBOX = None
STEPS = [
    Step(
        "/sdlc:init",
        "Tracker: GitHub Issues. Code host: GitHub. Specs directory: specs. No spec approvers group. "
        "Write the files: yes.",
    )
]


def check(c, repo, runs):
    c.that(repo.exists("specs/config.yml"), "no specs/config.yml")
    c.that(repo.exists("specs/templates/spec.md"), "no specs/templates/spec.md")
    c.that(repo.exists("specs/templates/intent.md"), "no specs/templates/intent.md")
    c.that(
        repo.exists(".gitignore") and "*.local.md" in repo.read(".gitignore"), ".gitignore lacks *.local.md"
    )
    c.that(repo.exists("CLAUDE.md") and "/sdlc:start" in repo.read("CLAUDE.md"), "CLAUDE.md section missing")
    c.that(repo.specs("lint").returncode == 0, "specs lint fails after init")
    c.that(repo.head() == repo.start_head, "init committed something")
    c.that("CODEOWNERS" in runs[-1].final, "the CODEOWNERS entry isn't printed")
