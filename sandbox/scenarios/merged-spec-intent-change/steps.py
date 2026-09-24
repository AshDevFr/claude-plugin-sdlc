"""Scenario: merged-spec-intent-change. See README.md."""

from pathlib import Path

INTENTS = Path(__file__).resolve().parents[2] / "intents"
INTENT = (INTENTS / "webhook-retries.md").read_text(encoding="utf-8")
SPEC = "2026-09-23-webhook-retries"

EXPECTED = {"lint_exit": 1, "lint_rules": ["L016"], "spec": SPEC, "intent": "changed"}


def apply(sb):
    sb.switch(SPEC, create=True)
    sb.new_spec("Webhook retries", "webhook-retries", INTENT)
    sb.commit("spec(2026-09-23-webhook-retries): r1 initial spec")
    sb.switch("main")
    sb.git("merge", "-q", "--no-ff", "-m", "Merge the webhook retries spec", SPEC)
    sb.replace(
        f"specs/{SPEC}/intent.md",
        "Deliveries stay in order per partner.",
        "Deliveries stay in order per partner and per event type.",
    )
    sb.commit("Intent: order per event type too")
