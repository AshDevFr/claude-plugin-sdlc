# Scenario: implement-contradiction

On branch `2026-09-23-webhook-retries`, a filled spec that can't be met as written: AC-1 wants
waits of 2 then 4 seconds, while the Design says to use the existing `backoff_seconds`
unchanged (1, 4, 16 seconds) because other tools depend on it. Use it to see
`/sdlc:implement` stop and hand the spec to `/sdlc:sync` instead of picking a side.

- `specs lint`: nothing to report (exit 0).
- `specs intent check`: intent `unchanged`.
- `specs coverage`: AC-1 and AC-2 uncited.
