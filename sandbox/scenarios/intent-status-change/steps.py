"""Scenario: intent-status-change. See README.md."""

from pathlib import Path

INTENTS = Path(__file__).resolve().parents[2] / "intents"
INTENT = (INTENTS / "webhook-retries.md").read_text(encoding="utf-8")
SPEC = "2026-09-23-webhook-retries"

EXPECTED = {"lint_exit": 0, "spec": SPEC, "intent": "unchanged", "status": "ready-for-code"}


def apply(sb):
    sb.switch(SPEC, create=True)
    sb.new_spec("Webhook retries", "webhook-retries", INTENT)
    sb.commit("spec(2026-09-23-webhook-retries): r1 initial spec")
    sb.replace(f"specs/{SPEC}/intent.md", "status: ready-for-spec", "status: ready-for-code")
    sb.commit("Intent: the spec is approved, ready for code")
