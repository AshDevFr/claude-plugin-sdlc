---
argument-hint: "[resume] [what matters most, in a few words]"
description: Pause work by writing what dies with this session to a local handoff.local.md next to the spec, or resume from one and see what changed since. Never committed, never sent anywhere
disable-model-invocation: true
---

Handoff: `$ARGUMENTS`

Read the arguments only from `$ARGUMENTS`. If the first word is `resume`, go to **Resume**.
Otherwise this is a pause, and the rest of the arguments, if any, say what matters most: use
them to choose what goes in, not to change the shape.

The file is `<spec-dir>/handoff.local.md` for the branch's spec, or
`<specs_dir>/handoff.local.md` (usually `specs/handoff.local.md`) on a branch without one. The
`*.local.md` rule `/sdlc:init` put in `.gitignore` keeps it out of git: it's for pausing and
resuming, on this machine, not a record. Nothing here commits or sends anything.

## Pause

A session ends for reasons unrelated to the work: a restart, a context limit, the end of the
day. The spec, the code and `git log` survive it. What was decided in conversation doesn't, and
neither does what was tried and abandoned, which is the most expensive thing to lose because
the next session will try it again.

**Capture only what dies with the session.** Don't restate the spec, criteria, commit subjects
or anything else the next session can read: a copy drifts from the moment it's written. Write
from what actually happened in this session, not from what the plan was, and never record as
done anything whose tests haven't run: if they haven't, say so.

### Step 1: what's at risk

```sh
"${CLAUDE_PLUGIN_ROOT}/tools/specs/specs" --json status
git status --short
git log --oneline @{upstream}..HEAD
```

- **Uncommitted changes**: list them; say they survive on disk but nowhere else.
- **Unpushed commits** (or no upstream at all: the branch exists only on this machine): warn
  before finishing, name how many and what they are, and offer to push the branch. Push only if
  the engineer says yes; otherwise record in the handoff that it's unpushed.
- **Anything still running** in this session (a background command, a subagent): it won't
  survive. Name it, and ask once whether to wait for it or stop now. For a subagent, copy its
  brief verbatim into the handoff so the next session can dispatch it again.

### Step 2: write it

If a handoff file already exists, show its "Where I am" and "Next action" and say it will be
replaced. Then write, in this order, omitting any empty section:

```markdown
# Handoff: <what this session was doing>

**Paused:** <date and time>, branch `<branch>` at `<short sha>`, spec `<id>` r<n>

## At risk
<Uncommitted files, unpushed commits, anything that was running and how to restart it.>

## Where I am
<One paragraph: the criterion or step in hand and how far into it.>

## Decided, not yet written down
<Decisions the next session would otherwise re-open, each with its reason.>

## Tried and abandoned
<What didn't work, and why.>

## Next action
<One concrete step.>

## Read these
<Paths, each with what it answers. Check each exists.>
```

Keep the narrative (Where I am to Read these) under 60 lines: the reasons are what matter, not
a transcript.

**Decisions that matter beyond this session belong in the spec.** For each one under "Decided,
not yet written down" that changes what gets built or how it's checked, suggest recording it in
the spec's `## Decisions` (through `/sdlc:sync` if it changes a criterion) rather than leaving it
only in a file git ignores.

### Step 3: tell the engineer

Say where the file is, that git ignores it, and print the prompt for the next session:

```
Resume work on <branch>: run /sdlc:handoff resume, then <the next action>.
```

The status line at the next session start also says `handoff waiting`.

## Resume

1. Read the handoff file (the branch's spec directory, else `<specs_dir>/`). If there's none,
   say so and suggest `/sdlc:check` to see where the spec stands.
2. Compare it with the branch as it is now:

   ```sh
   git log --oneline <sha from the handoff>..HEAD
   git status --short
   "${CLAUDE_PLUGIN_ROOT}/tools/specs/specs" --json status
   ```

   Report the commits made since, files changed, whether the spec's revision or intent state
   moved, and whether what was "At risk" is still at risk.
3. Give the handoff's next action, adjusted if what changed makes it stale, and the decisions
   and dead ends worth keeping in mind. Offer to delete the file once the work has resumed; a
   stale handoff misleads the next pause.
