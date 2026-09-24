"""/sdlc:converge on code that meets its spec unevenly."""

import re

from harness import Step

COMMANDS = ["converge"]
SANDBOX = "converge-partial"
STEPS = [Step('/sdlc:converge --test "python3 -m unittest"')]


def check(c, repo, runs):
    report = runs[-1].final
    c.that(re.search(r"AC-2[^\n]*`?(MISSING|CONTRADICTED)", report), "AC-2 isn't MISSING or CONTRADICTED")
    c.that(re.search(r"AC-1[^\n]*`?(COVERED|UNTESTED)", report), "AC-1 isn't COVERED or UNTESTED")
    c.that(re.search(r"logging_setup\.py[^\n]*UNJUSTIFIED", report), "logging_setup.py isn't UNJUSTIFIED")
    c.that(repo.unchanged(), "converge changed the repository")
