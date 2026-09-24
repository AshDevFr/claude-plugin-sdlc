# Scenario: intent-changed-no-impact

On branch `2026-09-23-webhook-retries`, the spec was written, then the intent was reworded
without changing what it asks for (a ticket count). Use it to try `/sdlc:check` and the
acknowledge path of `/sdlc:sync`.

- `specs lint`: `L016` (exit 1), the intent changed since the spec recorded it.
- `specs intent check`: intent `changed`; `--diff` shows the one reworded line.
