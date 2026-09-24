# Scenario: weak-intent

A request as `intent.md` at the repository root with gaps: no `## Problem` section, an empty
`## Constraints`, and an outcome nobody could check ("more reliable"). Use it to try the
improve-or-proceed offer of `/sdlc:start`.

- `specs lint`: nothing to report (exit 0); no spec yet.
- `specs intent assess --file intent.md`: Problem `missing`, Constraints `empty`.
