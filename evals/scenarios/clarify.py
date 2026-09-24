"""/sdlc:clarify works the spec's two open questions down to decisions."""

import re

from fixtures import SPEC_DIR
from harness import Step

COMMANDS = ["clarify"]
SANDBOX = "open-questions"
STEPS = [
    Step(
        "/sdlc:clarify",
        '"How many retries before a delivery fails for good?": 5 retries, decided by Ana Silva '
        '(integrations lead). "Do partners see failed deliveries in the dashboard or by email?": in '
        "the partner dashboard, decided by Omar (product). If offered to work on gaps in the intent: "
        "no. Confirm every edit: yes. If asked whether to add a scope change to intent.md: no.",
    )
]


def section(text: str, title: str) -> str:
    body = text[text.index(f"## {title}\n") + len(f"## {title}\n") :]
    return body[: body.find("\n## ")]


def check(c, repo, runs):
    spec = repo.read(f"{SPEC_DIR}/spec.md")
    decisions = re.findall(r"^- \d{4}-\d{2}-\d{2}: ", section(spec, "Decisions"), flags=re.M)
    c.that(len(decisions) >= 2, f"expected two dated decisions, found {len(decisions)}")
    c.that(not re.search(r"^- ", section(spec, "Open questions"), flags=re.M), "open questions remain")
    c.that(repo.head() == repo.start_head, "clarify committed something")
    c.that("unchanged" in repo.specs("intent", "check", SPEC_DIR).stdout, "the intent changed")
