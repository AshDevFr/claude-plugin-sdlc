---
argument-hint: "[<spec-dir>]"
description: Work a spec's open questions down to decisions, one question at a time, and write each answer where the next reader looks
disable-model-invocation: true
---

Clarify a spec: `$ARGUMENTS`

Read the arguments only from `$ARGUMENTS`: an optional spec directory. Without one, clarify the
current branch's spec. Load the `sdlc:workflow` and `sdlc:spec-template` skills first.

The helper is `"${CLAUDE_PLUGIN_ROOT}/tools/specs/specs"`. Nothing here commits, pushes or
posts; every edit is shown before it's written.

## Step 1: find the spec

```sh
"${CLAUDE_PLUGIN_ROOT}/tools/specs/specs" --json status
```

Use the spec directory from `$ARGUMENTS` if given, otherwise the spec `status` names. If there
is none, say so, suggest `/sdlc:start`, and stop. Read `spec.md` and `intent.md` in full.

## Step 2: choose the questions

**The spec's own open questions come first.** Each item under `## Open questions` is a question
someone already decided was worth asking; it outranks anything you'd propose.

Then scan the spec for what is genuinely undecided, and keep your ratings to yourself: scope and
non-goals, data and state, error and empty states, non-functional targets (an adjective with no
number behind it counts as missing), integrations and what happens when they fail, edge cases,
terminology, and whether each acceptance criterion could be judged the same way by two people.

Ask a question only if its answer would change what gets built or how anyone would check it.
Not implementation preferences, not sequencing (that's `/sdlc:plan`), not anything the spec
already answers. **At most five questions in the session**, open questions included. If more
survive, take the ones with the most impact and say at the end which you dropped.

**Intent gaps are offered, not demanded.** Run
`"${CLAUDE_PLUGIN_ROOT}/tools/specs/specs" intent assess <spec-dir>`. If the intent has gaps,
offer once to work them too, alongside the spec's questions; if the engineer declines, note
them in the report and move on. They never block this command.

If nothing needs asking, say the scan is clean and stop: that's a good outcome.

## Step 3: ask one at a time

One question per turn; never show the queue. Prefer the `AskUserQuestion` tool. Each question:

- is a full sentence ending in `?`, understandable without the spec open;
- says in one sentence what goes wrong if it stays open;
- carries a recommended answer and why. You've read the spec and the code; the engineer is
  partly asking for that judgement.

Don't limit how long an answer may be. If an answer is ambiguous, ask about the same question
again. Stop early when answers have made the remaining questions moot, or when told to stop.

## Step 4: write each answer back as you get it

After each answer, not at the end:

1. **Record it** under `## Decisions`:
   `- YYYY-MM-DD: <the decision, with its reason>. Decided by <who>.` The date is today; the
   person is whoever decided (the engineer, or the person they name as having answered).
2. **Apply it where it belongs.** A scope answer edits Goals or Non-goals; a number edits the
   criterion it makes measurable; a new behaviour becomes a new criterion with the next free
   `AC-n`. Never renumber a criterion; strike one through with a reason if the answer drops it.
3. **Remove what it resolves**: the question leaves `## Open questions`, and an alternative the
   answer rejected leaves the text.
4. **If the answer changes scope**, remind the engineer that `intent.md` should say so too,
   since truth flows from the intent to the spec, and offer to add it. Adding it is their call;
   if they do, `"${CLAUDE_PLUGIN_ROOT}/tools/specs/specs" intent record <spec-dir>` records the
   new version.

Show each edit and write it on confirmation. Leave decisions recorded in earlier sessions
exactly as they are.

## Step 5: report

```sh
"${CLAUDE_PLUGIN_ROOT}/tools/specs/specs" lint --ready <spec-dir>
```

Report the decisions recorded, the sections changed, the questions you dropped and why, any
intent gaps left, and the lint result as advice. When nothing is left open, suggest
`/sdlc:propose`. A commit of these changes carries `Spec-Change: clarify`; nothing has been
committed.
