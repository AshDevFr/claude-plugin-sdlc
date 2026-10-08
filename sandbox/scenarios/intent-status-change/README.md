# Scenario: intent-status-change

On branch `2026-09-23-webhook-retries`, the spec was written, then the intent's author moved
the intent's `status` in its frontmatter from `ready-for-spec` to `ready-for-code` and committed
it. Nothing in the request changed. Use it to see that `/sdlc:check` and the session status line
don't report the intent changed, and that nobody is sent to `/sdlc:sync`.

- `specs lint`: nothing to report (exit 0).
- `specs intent check`: intent `unchanged`: the recorded `sha256v2:` hash leaves the frontmatter
  out.
- `specs status`: `status ready-for-code`.
