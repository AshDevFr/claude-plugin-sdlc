# Changelog

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
