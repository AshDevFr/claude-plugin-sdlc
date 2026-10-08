# Scenario: blocked-spec

Two specs. `2026-09-20-delivery-log` records every delivery attempt; its intent is
`ready-for-code`, but it isn't built yet. `2026-09-23-webhook-retries` is filled in, its intent
is `ready-for-code`, and it lists `depends_on: [2026-09-20-delivery-log]`, because retries are
recorded in that log. The branch is `2026-09-23-webhook-retries`. Use it to see `/sdlc:plan` and
`/sdlc:implement` warn that the spec is blocked, naming the delivery log, before any code.

- `specs lint`: nothing to report (exit 0).
- `specs intent check`: intent `unchanged`.
- `specs status`: `status ready-for-code, blocked by 2026-09-20-delivery-log`.
- `specs deps`: the delivery log first, then the retries, `blocked`.
- `specs coverage`: AC-1 and AC-2 uncited.
