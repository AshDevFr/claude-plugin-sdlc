"""Scenario: converge-partial. See README.md."""

from pathlib import Path

INTENTS = Path(__file__).resolve().parents[2] / "intents"
INTENT = (INTENTS / "webhook-retries.md").read_text(encoding="utf-8")
SPEC = "2026-09-23-webhook-retries"
SPEC_DIR = f"specs/{SPEC}"

EXPECTED = {
    "lint_exit": 0,
    "spec": SPEC,
    "intent": "unchanged",
    "uncited": [2, 3],
    "changed_files": [
        f"{SPEC_DIR}/intent.md",
        f"{SPEC_DIR}/spec.md",
        "logging_setup.py",
        "tests/test_deliver.py",
        "webhooks.py",
    ],
}

SECTIONS = {
    "Context": "Each webhook is sent once; any error drops it.",
    "Goals": "- Retry failed deliveries long enough to ride out a short outage.\n"
    "- Let partners see which deliveries failed for good.",
    "Non-goals": "- Changing the payload format.",
    "Acceptance criteria": (
        "- **AC-1** Given a partner endpoint answering 503, when a delivery is sent, then it is"
        " retried with backoff, at most 5 attempts in all.\n"
        "- **AC-2** Given a delivery whose last attempt fails, when retries stop, then it is"
        " recorded as failed for good with its event id and the last status code.\n"
        "- **AC-3** Given a partner endpoint answering 400, when a delivery is sent, then it is"
        " not retried."
    ),
    "Design": "`deliver()` loops over attempts with `backoff_seconds`; a final failure is appended"
    " to `FAILED`, which the partner dashboard reads.",
    "Risks and security": "Retries make delivery at-least-once; partners dedupe on the event id.",
}

DELIVER = '''

FAILED: list[dict] = []


def deliver(send, event: dict, max_attempts: int = 5, sleep=None) -> bool:
    """Send an event, retrying server errors with backoff; a client error is final."""
    for attempt in range(1, max_attempts + 1):
        status = send(event)
        if status < 400:
            return True
        if not should_retry(status):
            break
        if sleep and attempt < max_attempts:
            sleep(backoff_seconds(attempt))
    FAILED.append({"event_id": event["id"]})
    return False
'''

TEST = """import unittest

from webhooks import deliver


class DeliverTest(unittest.TestCase):
    def test_503_is_retried(self):  # 2026-09-23-webhook-retries:AC-1
        answers = iter([503, 503, 200])
        self.assertTrue(deliver(lambda e: next(answers), {"id": 1}))
"""

LOGGING = '''"""Log setup for the sender."""

import logging

FORMAT = "%(asctime)s %(levelname)s %(name)s %(message)s"


def configure() -> None:
    logging.basicConfig(format=FORMAT, level=logging.INFO)
'''


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
    sb.write("webhooks.py", sb.read("webhooks.py") + DELIVER)
    sb.write("tests/test_deliver.py", TEST)
    sb.commit("feat: retry webhook deliveries\n\nSpec: 2026-09-23-webhook-retries@r1\nImplements: AC-1, AC-3")
    sb.write("logging_setup.py", LOGGING)
    sb.commit("chore: log format for the sender")
