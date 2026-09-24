# Scenario: intent-changed-impact

On branch `2026-09-23-webhook-retries`, the spec was written, then the intent gained a
constraint that changes scope (internal webhooks are excluded). Use it to try the amend path
of `/sdlc:sync`.

- `specs lint`: `L016` (exit 1).
- `specs intent check`: intent `changed`; `--diff` shows the added constraint.
