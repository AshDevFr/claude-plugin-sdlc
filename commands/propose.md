---
argument-hint: "[<spec-dir>]"
description: Get a spec ready for review before any code, with a readiness check as advice, the spec commit message and the draft spec-only PR text. Nothing is committed, pushed or opened
disable-model-invocation: true
---

Propose a spec for review: `$ARGUMENTS`

Read the arguments only from `$ARGUMENTS`: an optional spec directory. Without one, use the
current branch's spec. Load the `sdlc:workflow` and `sdlc:commit-conventions` skills first.

This is the step between writing a spec and writing code: the spec goes up for review on its
own. **This command prints text only.** It never stages, commits, pushes or opens a PR; the
engineer runs those, and the output ends with the commands to do so.

## Step 1: readiness, as advice

```sh
"${CLAUDE_PLUGIN_ROOT}/tools/specs/specs" --json check --ready $ARGUMENTS
```

- **Exit 0**: the spec is ready. Say so in one line.
- **Exit 1**: list each reason with its next step: open questions, `/sdlc:clarify`; template
  text left in a section, the section to fill; the intent changed since the spec recorded it,
  name the change (`"${CLAUDE_PLUGIN_ROOT}/tools/specs/specs" intent check --diff <spec-dir>`)
  and `/sdlc:sync`; intent not recorded, `specs intent record`; other lint findings, briefly.
  Uncited criteria are expected before code; don't list them as a problem.
- **Exit 2**: say readiness couldn't be checked, show the message, and don't call the spec
  ready. If there's no spec for the branch, ask for the directory and stop.

**Whatever the result, carry on to Steps 2 and 3.** Readiness is advice: the engineer may
want reviewers to see a spec with open questions on purpose. Say which reasons they'll want
to resolve first, and suggest `/sdlc:analyze` for a deeper read if they haven't run it.

## Step 2: the spec commit message

```sh
git status --porcelain -- <spec-dir>
```

If the spec directory has no uncommitted change, there is nothing to commit: say the spec is
already committed and skip to Step 3. Otherwise write the message as `/sdlc:commit-msg` does
in spec mode:

- subject `spec(<spec-id>): r<n> <summary>`;
- a body that says why: what the spec sets out to do and, for a revision, what changed;
- the trailers from the helper, never written by hand. The kind is `initial` when the spec
  doesn't exist in `HEAD` yet (`git cat-file -e HEAD:<spec-dir>/spec.md` fails), otherwise the
  one the change calls for (the skill's Spec-Change kinds):

```sh
"${CLAUDE_PLUGIN_ROOT}/tools/specs/specs" trailers <spec-dir> --spec-change initial
```

## Step 3: the draft PR text

- **Title**: `Draft: Spec for <spec title>`.
- **Description**:

```
## Summary
<2-3 sentences: the problem from the intent, and what the spec commits to.>

## Spec
<spec-id> at r<n>. Spec only: no code yet. The intent is `<spec-dir>/intent.md`; the spec
is the contract.

## What to review
<The acceptance criteria, as a short list with their AC numbers; the Decisions a reviewer
should agree with; any open questions left on purpose, and who should answer them.>

<`Refs <ticket.ref>` when the spec has a ticket; a spec-only PR never closes it.>

<the helper's trailer lines>
```

Reviewers approve the spec, not code: say so in "What to review" when the team uses code
owners on `specs/`.

## Output

Print, in order: the readiness summary, the commit message in one fenced block, the PR title
and description in two fenced `markdown` blocks, then the commands the engineer would run,
as prose, not run by you: stage the spec directory (`git add <spec-dir>`), commit with the
message, push the branch, and open a draft PR with the title and description. Then stop.
