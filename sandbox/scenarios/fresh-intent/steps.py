"""Scenario: fresh-intent. See README.md."""

from pathlib import Path

INTENTS = Path(__file__).resolve().parents[2] / "intents"
INTENT = (INTENTS / "webhook-retries.md").read_text(encoding="utf-8")
SPEC = "2026-09-23-webhook-retries"

EXPECTED = {"lint_exit": 0, "spec": None}


def apply(sb):
    sb.write("intent.md", INTENT)
    sb.commit("Add the webhook retries request")
