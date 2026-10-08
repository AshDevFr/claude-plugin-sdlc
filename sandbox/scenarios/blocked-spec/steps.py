"""Scenario: blocked-spec. See README.md."""

from pathlib import Path

INTENTS = Path(__file__).resolve().parents[2] / "intents"
INTENT = (INTENTS / "webhook-retries.md").read_text(encoding="utf-8")
SPEC = "2026-09-23-webhook-retries"
SPEC_DIR = f"specs/{SPEC}"
LOG = "2026-09-20-delivery-log"

EXPECTED = {
    "lint_exit": 0,
    "spec": SPEC,
    "intent": "unchanged",
    "uncited": [1, 2],
    "status": "ready-for-code",
    "blocked_by": [LOG],
}

LOG_INTENT = """---
status: ready-for-code
---
# Intent: delivery log
Author: P. Martin (integrations).
## Problem
When a partner says an event never arrived, support can't tell whether we sent it.
## Proposed outcome
Every delivery attempt is recorded with its time, status code and the event id.
## Affected users and systems
Partner support, the webhook sender.
## Constraints
No payload contents in the log: event ids only.
## Open questions
None.
"""

SECTIONS = {
    "Context": "Each webhook is sent once; any error drops it. Attempts go to the delivery log.",
    "Goals": "- Retry failed deliveries long enough to ride out a short outage.",
    "Non-goals": "- Changing the payload format.",
    "Acceptance criteria": (
        "- **AC-1** Given a partner endpoint answering 503 twice then 200, when a delivery is sent,"
        " then it succeeds on the third attempt after waiting 1 second, then 4 seconds.\n"
        "- **AC-2** Given a partner endpoint answering 400, when a delivery is sent, then it is"
        " not retried."
    ),
    "Design": "`deliver(send, event, sleep)` retries with the existing `backoff_seconds`, and"
    " writes each attempt to the delivery log from 2026-09-20-delivery-log.",
    "Risks and security": "Retries make delivery at-least-once; partners dedupe on the event id.",
}


def fill(text: str) -> str:
    for title, body in SECTIONS.items():
        start = text.index(f"## {title}\n") + len(f"## {title}\n")
        end = text.index("\n## ", start) + 1
        text = text[:start] + body + "\n\n" + text[end:]
    return text


def apply(sb):
    sb.new_spec("Delivery log", "delivery-log", LOG_INTENT, date="2026-09-20")
    sb.commit("spec(2026-09-20-delivery-log): r1 initial spec")
    sb.switch(SPEC, create=True)
    sb.new_spec("Webhook retries", "webhook-retries", INTENT)
    sb.replace(f"specs/{SPEC}/intent.md", "status: ready-for-spec", "status: ready-for-code")
    spec = fill(sb.read(f"{SPEC_DIR}/spec.md"))
    spec = spec.replace("superseded_by: null\n", f"superseded_by: null\ndepends_on: [{LOG}]\n", 1)
    sb.write(f"{SPEC_DIR}/spec.md", spec)
    sb.commit("spec(2026-09-23-webhook-retries): r1 initial spec")
