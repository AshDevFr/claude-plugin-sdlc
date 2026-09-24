"""Scenario: open-questions. See README.md."""

from pathlib import Path

INTENTS = Path(__file__).resolve().parents[2] / "intents"
INTENT = (INTENTS / "webhook-retries.md").read_text(encoding="utf-8")
SPEC = "2026-09-23-webhook-retries"

EXPECTED = {"lint_exit": 0, "spec": SPEC, "intent": "unchanged"}


def apply(sb):
    sb.switch(SPEC, create=True)
    sb.new_spec("Webhook retries", "webhook-retries", INTENT)
    sb.replace(
        f"specs/{SPEC}/spec.md",
        "Each one names who must answer it. The spec is not approvable with open questions left.\n",
        "- How many retries before a delivery fails for good? (integrations lead)\n"
        "- Do partners see failed deliveries in the dashboard or by email? (product)\n",
    )
    sb.commit("spec(2026-09-23-webhook-retries): r1 initial spec")
