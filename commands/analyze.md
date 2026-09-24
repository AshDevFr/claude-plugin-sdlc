---
argument-hint: "[<spec-dir>]"
description: Read-only review of one spec against itself and its intent, covering contradictions, untestable criteria, gaps and anything the intent asks for that the spec misses
disable-model-invocation: true
---

Analyze a spec: `$ARGUMENTS`

Read the arguments only from `$ARGUMENTS`: an optional spec directory. Without one, analyze the
current branch's spec. Load the `sdlc:workflow` and `sdlc:spec-template` skills first.

**This command is read-only.** It edits no file, stages nothing and runs no git command that
changes state. Every finding is a suggestion; fixing is the engineer's call (`/sdlc:clarify`
for open questions, `/sdlc:sync` for an intent change, or a plain edit).

## Step 1: the mechanical checks

```sh
"${CLAUDE_PLUGIN_ROOT}/tools/specs/specs" --json check --ready $ARGUMENTS
```

Exit 0 or 1: keep the lint findings, uncited criteria and intent state for the report; don't
repeat what they already say in your own findings. Exit 2: say the checks couldn't run, show
the message, and go on with the reading below. If the message says there is no spec for the
branch, ask for the spec directory and stop.

Then read `spec.md` and its intent file (`intent.file` in the frontmatter, usually
`intent.md`) in full. A spec with only a ticket has no intent file: say so, and skip Step 3.

## Step 2: the spec against itself

Look for, and only report what you can point at:

- **Contradictions**: a criterion that does something a Non-goal rules out; a Design choice a
  Decision rejected; two criteria that can't both hold.
- **Untestable criteria**: an outcome two people could judge differently (an adjective with no
  number, "fast", "user-friendly", "handles errors"), or one no test could observe.
- **Unsupported criteria and orphan design**: a criterion the Design never explains how to
  meet; a Design element no criterion needs.
- **Open questions already answered** elsewhere in the spec (they belong in Decisions), and
  Decisions that silently changed a criterion's meaning without the criterion being edited.

## Step 3: the spec against its intent

The intent is the original request; the spec is the contract. Look for:

- **Missing scope**: something the intent's Proposed outcome asks for that no criterion or
  Goal covers.
- **Extra scope**: criteria or Goals the intent never asked for, with no Decision explaining
  them.
- **Constraints dropped**: an intent constraint the spec neither honours in a criterion or the
  Design nor rejects in a Decision.
- **Affected users or systems** the intent names that the spec never mentions.

An intent's own vagueness is not a spec finding; mention it in one line at most.

## Step 4: report

One table, most severe first:

| Location | Finding | Suggestion |
|---|---|---|
| `spec.md:24` (AC-3) and `spec.md:12` (Non-goals) | AC-3 emails partners; Non-goals rule out notifications | Strike AC-3 or move notifications out of Non-goals, with a Decision |

- **Location** names the line(s) in `spec.md` or `intent.md` (`file:line`, and the `AC-n` or
  section). A contradiction names both sides.
- **Suggestion** is one concrete edit or the command to run.

Before the table, one line with the mechanical results (lint findings by rule, uncited
criteria, intent state, ready or not). After it, the one or two most useful next steps. If
nothing is found, say the spec reads consistently with its intent; that's a good outcome.
