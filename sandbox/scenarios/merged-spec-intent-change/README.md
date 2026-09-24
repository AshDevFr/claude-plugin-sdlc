# Scenario: merged-spec-intent-change

The spec was merged to `main`, then its intent was edited on `main`. A merged spec is frozen:
use it to see `/sdlc:sync` point to a follow-up spec (`--supersedes`) instead of amending.

- `specs lint`: `L016` (exit 1).
- `specs intent check`: intent `changed`.
