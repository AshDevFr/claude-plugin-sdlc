"""Scenario: implement-contradiction. See README.md."""

from pathlib import Path

INTENTS = Path(__file__).resolve().parents[2] / "intents"
INTENT = (INTENTS / "webhook-retries.md").read_text(encoding="utf-8")
SPEC = "2026-09-23-webhook-retries"
SPEC_DIR = f"specs/{SPEC}"

EXPECTED = {"lint_exit": 0, "spec": SPEC, "intent": "unchanged", "uncited": [1, 2]}

SECTIONS = {
    "Context": "Each webhook is sent once; any error drops it.",
    "Goals": "- Retry failed deliveries long enough to ride out a short outage.",
    "Non-goals": "- Changing the payload format.",
    "Acceptance criteria": (
        "- **AC-1** Given a partner endpoint answering 503 twice then 200, when a delivery is sent,"
        " then it succeeds on the third attempt after waiting 2 seconds, then 4 seconds.\n"
        "- **AC-2** Given a partner endpoint answering 400, when a delivery is sent, then it is"
        " not retried."
    ),
    "Design": "`deliver(send, event, sleep)` retries with the existing `backoff_seconds`, unchanged:"
    " the metrics exporter and the replay tool call it and depend on its 1, 4, 16 second schedule.",
    "Risks and security": "Retries make delivery at-least-once; partners dedupe on the event id.",
}


def fill(text: str) -> str:
    for title, body in SECTIONS.items():
        start = text.index(f"## {title}\n") + len(f"## {title}\n")
        end = text.index("\n## ", start) + 1
        text = text[:start] + body + "\n\n" + text[end:]
    return text


def apply(sb):
    sb.switch(SPEC, create=True)
    sb.new_spec("Webhook retries", "webhook-retries", INTENT)
    sb.write(f"{SPEC_DIR}/spec.md", fill(sb.read(f"{SPEC_DIR}/spec.md")))
    sb.commit("spec(2026-09-23-webhook-retries): r1 initial spec")
