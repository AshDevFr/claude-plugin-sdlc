# Changelog

## 0.2.0

- `/sdlc:intent`: whoever has the problem writes the intent with Claude before any spec
  exists, through an interview in their words. The file goes where the repository says:
  `intents/<id>.md` when there's an `intents/` directory, otherwise a spec directory holding
  only the intent; in a repository not set up for sdlc, wherever its own guidance says.
- `/sdlc:start` keeps the id of an intent written ahead of its spec.
- Helper: `specs intent new`; a spec directory holding only `intent.md` is a valid "intent, no
  spec yet" state for `lint`, `check`, `coverage` and `status`; `specs new` writes the spec
  beside it.
- Fixed: a date-named branch could be read as a ticket number and point `status` at the wrong
  directory.
- Commands, all: `/sdlc:init`, `/sdlc:intent`, `/sdlc:start`, `/sdlc:clarify`, `/sdlc:analyze`,
  `/sdlc:check`, `/sdlc:propose`, `/sdlc:plan`, `/sdlc:implement`, `/sdlc:bug`, `/sdlc:sync`,
  `/sdlc:converge`, `/sdlc:commit-msg`, `/sdlc:pr-msg`, `/sdlc:handoff`.

## 0.1.0

The first release: spec-driven development for a team sharing one repository, advising and
never enforcing, with no tracker or code host access.

- Commands: `/sdlc:init`, `/sdlc:start`, `/sdlc:clarify`, `/sdlc:analyze`, `/sdlc:check`,
  `/sdlc:propose`, `/sdlc:plan`, `/sdlc:implement`, `/sdlc:bug`, `/sdlc:sync`,
  `/sdlc:converge`, `/sdlc:commit-msg`, `/sdlc:pr-msg`, `/sdlc:handoff`.
- Skills: `workflow`, `spec-template`, `intent-writing`, `intent-sync`, `commit-conventions`,
  `test-first`, `receiving-review`, `finishing-work`.
- Hooks: a session status line for the branch's spec, and a reminder to bump the revision
  when a pushed spec is edited.
- The `specs` helper, shipped inside the plugin: spec parsing, lint rules L001 to L017, `init`,
  `new`, `intent check/record/assess`, `coverage`, `status`, `check`, `trailers`.
- `sdlc-sandbox`: disposable repositories in scripted states for trying the commands.
