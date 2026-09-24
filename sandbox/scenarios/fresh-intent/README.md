# Scenario: fresh-intent

A request has just arrived as `intent.md` at the repository root; no spec exists yet. Use it to
try `/sdlc:start` with an existing intent file.

- `specs lint`: nothing to report (exit 0); the only directory under `specs/` is `templates/`.
- The intent is complete: every template section is filled in.
