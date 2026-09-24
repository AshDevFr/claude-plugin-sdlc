---
argument-hint: "[<existing intent file>] [a few words on the request]"
description: Write an intent with whoever has the problem, before any spec exists, through an interview in their words that fills the intent template and writes one file
disable-model-invocation: true
---

Write an intent: `$ARGUMENTS`

Read the arguments only from `$ARGUMENTS`: an optional path to an existing intent to improve,
and optionally a few words on the request. Load the `sdlc:intent-writing` skill first: it holds
the sections, what makes an intent strong or weak, and why its author's words matter.

You're working with whoever has the problem: a product manager, an engineer, a staff engineer.
The intent is theirs: it says what hurts and what should be true afterwards, **in their words**.
Your job is to draw it out and write it down, not to design the solution. **No spec, no branch,
no commit**: this writes one file and stops.

## Step 1: where the intent goes

- **No `specs/config.yml`** in this repository: it isn't set up for sdlc, and may be a
  repository kept for intents. Follow its own guidance: read its `CLAUDE.md`, `README` and
  `CONTRIBUTING` for where intents go and how they're named. If they don't say, ask. Use the
  template at `${CLAUDE_PLUGIN_ROOT}/tools/specs/sdlc_specs/templates/intent.md`.
- **An sdlc repository**: once you know the title (Step 2), let the helper place it:

  ```sh
  "${CLAUDE_PLUGIN_ROOT}/tools/specs/specs" --json intent new --title "<title>"
  ```

  With an `intents/` directory at the root it creates `intents/YYYY-MM-DD-<slug>.md`;
  otherwise a spec directory holding only the intent, `specs/YYYY-MM-DD-<slug>/intent.md`.
  Either way the file starts from the team's intent template. Pass `--slug` when the title
  makes a poor one. Exit 1 means the id is taken: propose another slug.
- **An existing intent** (a path in `$ARGUMENTS`): work on that file where it is. In an sdlc
  repository, start with
  `"${CLAUDE_PLUGIN_ROOT}/tools/specs/specs" intent assess --file <path>` to see which sections
  are missing, empty or still template text.

## Step 2: the interview

**One question per turn.** Prefer the `AskUserQuestion` tool when there are a few likely
answers; ask openly when the answer is theirs to tell. Start with what they already said in
`$ARGUMENTS`, and don't ask for what they've told you.

Follow the template's sections, in this order, one or two questions each:

1. **Problem**: what happens today, and to whom? What does it cost (time, money, tickets,
   churn)? A concrete example beats a summary. From the answer, propose a short title and
   confirm it.
2. **Proposed outcome**: when this is done, what will people see or be able to do? Push gently
   on anything nobody could check ("faster", "better"): faster than what, for whom?
3. **Affected users and systems**: who uses it, who supports it, what it touches.
4. **Constraints**: what the solution must respect (data, security, money, compatibility,
   dates). Ask about the ones the domain obviously has.
5. **Open questions**: what they don't know yet, and who could answer it.

As you go:

- **Keep their language.** Tidy grammar, not meaning. Don't translate a problem into an
  engineering task.
- **When they describe a solution** ("add a Redis cache"), ask what problem it solves and
  write that problem down; the solution can stay as a note under Constraints or Open
  questions if they care about it.
- **Stop asking** when every section says something real, or when they want to stop. An
  intent with gaps is still an intent: the spec will carry more open questions.

## Step 3: write it

Write the file section by section in the template's shape: the `# Intent: <title>` heading, an
`Author: <name> (<role or team>). Status: draft.` line, then the sections. Show it, and change
what they want changed.

Then name what's still weak, in a few lines, using the skill's checks (a vague outcome, unclear
scope, a solution written as the problem, a missing obvious constraint). Offer to work on them;
never refuse to finish because of them.

## Step 4: hand it over

Say where the file is and that nothing has been committed. Then the next step, depending on
who carries on:

- **An engineer starts the spec**: `/sdlc:start <path>`. It keeps the intent's id, so the spec
  and the intent share it.
- **Someone else will**: commit the file and open a PR so the intent can be reviewed on its
  own, or hand the file over however the team does.
