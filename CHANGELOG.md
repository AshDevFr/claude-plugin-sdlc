# Changelog

## 0.3.0

- **Intent status.** An intent file (`specs/<id>/intent.md` or `intents/<id>.md`) can say where
  its request stands, in its frontmatter: `status: draft | ready-for-spec | ready-for-code |
  done | dropped`. For a team keeping intents as files, the intent is the ticket; no tracker
  knows this state. A person sets it; the plugin only writes `draft` when it creates an intent.
  No frontmatter means `draft`. Ticket specs keep taking their status from the tracker.
- The intent template carries the frontmatter; its `Author:` line no longer says `Status:`.
  `/sdlc:init --upgrade` replaces an unedited copy in `specs/templates/`.
- **The intent hash leaves the frontmatter out**, so a status change never reports the intent
  changed. New records are `sha256v2:<hex>`; a bare hex record from before is still compared
  the old way, and also matches once a frontmatter is added, so existing specs don't report a
  change when their intent gets a status.
- **`depends_on`** in a spec's frontmatter: spec ids that must be implemented first. A spec is
  ready to implement when every dependency's intent is `done`; its own status doesn't count. A
  ticket-spec dependency (`unknown (tracker)`) is confirmed by the engineer, or by the code in
  an unattended run. `/sdlc:start` asks for them and passes `specs new --depends-on`.
  Lint rules `L018` (each id names a spec directory), `L019` (no self-reference) and
  `L020` (no cycle).
- The session status line shows the intent's status and `blocked by <id>`; `specs check`
  reports `status`, `blocked_by` and `ready_to_implement`; `/sdlc:propose` lists unmet
  dependencies, and `/sdlc:plan` and `/sdlc:implement` warn before starting a spec that isn't
  ready to implement. Dependencies never affect whether a spec is ready for review. Advice only:
  nothing is refused.
- Helper: `specs deps` prints every spec in dependency order with its status and whether it is
  ready, blocked or done; `specs intent assess` reports the status and an invalid value.
- Commands, all: `/sdlc:init`, `/sdlc:intent`, `/sdlc:start`, `/sdlc:clarify`, `/sdlc:analyze`,
  `/sdlc:check`, `/sdlc:propose`, `/sdlc:plan`, `/sdlc:implement`, `/sdlc:bug`, `/sdlc:sync`,
  `/sdlc:converge`, `/sdlc:commit-msg`, `/sdlc:pr-msg`, `/sdlc:handoff`.

## 0.2.0

- `/sdlc:intent`: whoever has the problem writes the intent with Claude before any spec
  exists, through an interview in their words. The file goes where the repository says:
  `intents/<id>.md` when there's an `intents/` directory, otherwise a spec directory holding
  only the intent; in a repository not set up for sdlc, wherever its own guidance says.
- `/sdlc:start` keeps the id of an intent written ahead of its spec.
- Helper: `specs intent new`; a spec directory holding only `intent.md` is a valid "intent, no
  spec yet" state for `lint`, `check`, `coverage` and `status`; `specs new` writes the spec
  beside it.
- The `CLAUDE.md` section `/sdlc:init` writes now mentions `/sdlc:intent`; in a repository set
  up with 0.1.0, `/sdlc:init` with `--upgrade` refreshes it.
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
