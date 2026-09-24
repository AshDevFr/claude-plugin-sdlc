"""Spec states the scenarios share, built on the sandbox's webhook-retries spec."""

from harness import Repo, fill_sections

SPEC_ID = "2026-09-23-webhook-retries"
SPEC_DIR = f"specs/{SPEC_ID}"
QUESTIONS = (
    "- How many retries before a delivery fails for good? (integrations lead)\n"
    "- Do partners see failed deliveries in the dashboard or by email? (product)\n"
)
AC_1 = (
    "- **AC-1** Given a partner endpoint answering 503 twice then 200, when a delivery is sent, then"
    " it succeeds on the third attempt after waiting 1 second, then 4 seconds."
)
AC_2 = "- **AC-2** Given a partner endpoint answering 400, when a delivery is sent, then it is not retried."
SECTIONS = {
    "Context": "Each webhook is sent once; any error drops it.",
    "Goals": "- Retry failed deliveries long enough to ride out a short outage.",
    "Non-goals": "- Changing the payload format.",
    "Acceptance criteria": f"{AC_1}\n{AC_2}",
    "Design": "`deliver(send, event, sleep)` in `webhooks.py` retries with the existing `backoff_seconds`.",
    "Risks and security": "Retries make delivery at-least-once; partners dedupe on the event id.",
}


def filled_spec(
    repo: Repo, *, criteria: str | None = None, extra: dict | None = None, commit: str | None = None
):
    """The sandbox spec with real content in every section and no open questions."""
    sections = dict(SECTIONS, **(extra or {}))
    if criteria is not None:
        sections["Acceptance criteria"] = criteria
    fill_sections(repo, SPEC_DIR, sections)
    spec = repo.read(f"{SPEC_DIR}/spec.md").replace(QUESTIONS, "")
    repo.write(f"{SPEC_DIR}/spec.md", spec)
    if commit:
        repo.commit(commit)


DELIVER = '''

def deliver(send, event, sleep, max_attempts: int = 5) -> bool:
    """Send an event, retrying server errors with backoff; a client error is final."""
    for attempt in range(1, max_attempts + 1):
        status = send(event)
        if status < 400:
            return True
        if not should_retry(status) or attempt == max_attempts:
            return False
        sleep(backoff_seconds(attempt))
    return False
'''
DELIVER_TEST = """import unittest

from webhooks import deliver


class DeliverTest(unittest.TestCase):
    def test_503_twice_then_200(self):  # 2026-09-23-webhook-retries:AC-1
        answers, waits = iter([503, 503, 200]), []
        self.assertTrue(deliver(lambda e: next(answers), {"id": 1}, waits.append))
        self.assertEqual(waits, [1, 4])

    def test_400_is_not_retried(self):  # 2026-09-23-webhook-retries:AC-2
        calls = []
        self.assertFalse(deliver(lambda e: calls.append(e) or 400, {"id": 1}, lambda s: None))
        self.assertEqual(len(calls), 1)
"""


def implemented(repo: Repo) -> None:
    """Code and tests meeting AC-1 and AC-2, not committed."""
    repo.write("webhooks.py", repo.read("webhooks.py") + DELIVER)
    repo.write("tests/test_deliver.py", DELIVER_TEST)


# What an intent's author says when interviewed, for the /sdlc:intent scenarios.
AUTHOR_ANSWERS = (
    "You are interviewing Priya Shah (partner success), the intent's author. Her answers: "
    "Problem: partners lose webhook events whenever their endpoint is briefly down, because we "
    "send each event once and drop it on any error; partner success handles about ten tickets a "
    "week asking us to resend events by hand. Outcome: failed deliveries are retried "
    "automatically long enough to ride out a short outage, and partners can see which "
    "deliveries failed for good. Affected: partners receiving webhooks, the partner success "
    "team, the webhook sender. Constraints: no change to the payload format; deliveries stay in "
    "order per partner. Open question: how long to keep retrying, which the integrations lead "
    "should answer. The title: Webhook retries. Confirm writing the file: yes."
)


def intent_sections_filled(repo: Repo, path: str) -> list[str]:
    """The intent template sections that are missing, empty or still template text."""
    import json

    doc = json.loads(repo.specs("--json", "intent", "assess", "--file", path).stdout)
    return [s["section"] for s in doc["sections"] if s["state"] != "ok"]
