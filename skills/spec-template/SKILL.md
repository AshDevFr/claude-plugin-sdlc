---
name: spec-template
description: What goes in a spec.md, covering the frontmatter fields and who writes them, what each section is for, and how to write acceptance criteria that two people would judge the same way. Use when drafting, reviewing or amending a spec.
---

# Writing a spec

## The template

The template in use is the team's `<specs_dir>/templates/spec.md` when it exists, otherwise the
plugin's own at `${CLAUDE_PLUGIN_ROOT}/tools/specs/sdlc_specs/templates/spec.md`. Read it rather
than working from memory: teams customise it. `specs new` fills it in; never write the
frontmatter by hand.

## Frontmatter

| Field | Meaning | Written by |
|---|---|---|
| `id` | The directory name, `YYYY-MM-DD-<slug>`; never changes | `specs new` |
| `title` | Short human title | `specs new` |
| `intent` | `file`, and the intent's hash with when and by whom it was recorded | `specs new`, `specs intent record` |
| `revision` | Bumped on every content change after the spec was first reviewed | the engineer, through `/sdlc:sync` |
| `state` | `active` or `superseded` | `specs new --supersedes` |
| `supersedes`, `superseded_by` | Links between a spec and the one that replaces it | `specs new --supersedes` |
| `related`, `attachments` | Other specs or tickets; files in the directory | the engineer |

Never add approval, reviewer or PR fields: the code host knows those, and a copy would drift.

## Sections

- **Context**: what exists today, and what the intent leaves out that the implementation needs.
  Don't restate the intent; link it.
- **Goals / Non-goals**: non-goals are where scope arguments are settled before code exists.
- **Acceptance criteria**: see below.
- **Design**: the approach, data and API changes, alternatives considered and why they lost.
- **Risks and security**: link a threat model kept in the directory when the change crosses a
  trust boundary.
- **Rollout and migration**: flags, backfills, ordering, how to undo.
- **Open questions**: each names who must answer it. A spec with open questions isn't ready for
  review; `/sdlc:clarify` works them down.
- **Decisions**: answers that came from outside the spec, with their source, so the next reader
  doesn't have to find the thread.
- **Revisions**: `- **rN** (YYYY-MM-DD, author): what changed and why`, newest first.

## Acceptance criteria

Write each as `- **AC-n** <criterion>`, one observable outcome per criterion.

Where people could disagree, say it as Given / When / Then with real values, so two readers
would judge it the same way:

- `- **AC-2** Given a plan changed on day 10 of a 30-day cycle, when the invoice is issued,
  then it charges 20/30 of the price difference.`

"Downgrades are handled correctly" passes against anything; that's the failure this prevents.
Not every criterion needs the form: "no new PII in the portal session" is already clear.

Numbers are permanent. A new criterion takes the next free number. A dropped one is struck
through with the reason after it, never deleted:

- `- ~~**AC-3** Annual plans are prorated.~~ Out of scope: annual plans are handled by finance.`

Tests cite criteria as `<spec-id>:AC-<n>` in a test name or comment; `specs coverage` reports
which are cited.

## Assumptions

When the intent is silent and a default was chosen, say so in the Design or Decisions section,
with what would overturn it. A guess written as a fact becomes load-bearing without anyone
having agreed to it.

## The plan

`/sdlc:plan` writes the engineer's working plan from the spec, using the template beside this
skill, `${CLAUDE_PLUGIN_ROOT}/skills/spec-template/plan.md`: test-first steps, each naming the
criteria it serves, and a map showing every criterion has a step. It lives in
`<spec-dir>/plan.local.md`, ignored by git, unless the team renames it `plan.md` to commit it.
