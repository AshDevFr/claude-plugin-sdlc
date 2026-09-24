---
argument-hint: "[<spec-dir>] [--commit]"
description: Write the working implementation plan for a spec as plan.local.md, with test-first steps each naming the criteria they serve, kept out of git unless committed on purpose
disable-model-invocation: true
---

Plan the implementation: `$ARGUMENTS`

Read the arguments only from `$ARGUMENTS`: an optional spec directory (default: the branch's
spec), and `--commit`. Load the `sdlc:spec-template` and `sdlc:test-first` skills first.

The helper is `"${CLAUDE_PLUGIN_ROOT}/tools/specs/specs"`. Nothing here stages, commits or
pushes.

## `--commit`: keep the plan in the repository

Some plans deserve review (a migration across several PRs, say). With `--commit`, show the
plan's Approach and step titles, and ask whether to rename `<spec-dir>/plan.local.md` to
`<spec-dir>/plan.md`. Only on a yes, rename it, and replace the plan's opening note about being
local with "Committed with the change, for review."; `plan.md` then shows in `git status` for
the engineer to commit. Then stop. Without a `plan.local.md`, say there's nothing to rename.

## Step 1: read

```sh
"${CLAUDE_PLUGIN_ROOT}/tools/specs/specs" --json check <spec-dir>
```

Read `spec.md` and `intent.md` in full, then the code the Design touches and its tests. Note
the spec's id and revision.

If `check` reports open questions or an intent that changed, say so first: planning against a
spec that's still moving plans the wrong thing. Suggest `/sdlc:clarify` or `/sdlc:sync`, and
continue only if the engineer wants to.

If `<spec-dir>/plan.local.md` already exists, read it: update it rather than starting over,
and keep what's still true.

## Step 2: write the plan

Follow the template at `${CLAUDE_PLUGIN_ROOT}/skills/spec-template/plan.md` and write it to
`<spec-dir>/plan.local.md`:

- **Steps ordered test first**: each one names the criteria it serves as `<spec-id>:AC-n`, the
  failing test to write first, the files it changes, and what "done" looks like. Small steps:
  each should end in a commit.
- **The criteria map**: every criterion that isn't struck has at least one step. Struck
  criteria are left out.
- **Grounded in the code**: file paths that exist, functions by their real names. Where the
  code turns out to disagree with the spec's Design, write it under Risks and unknowns; if it
  changes what a criterion requires, that's for `/sdlc:sync`.
- No task files, phases or progress tables: the spec is the contract and the commits are the
  progress.

## Step 3: check it's out of git

```sh
git check-ignore -q <spec-dir>/plan.local.md
```

Exit 0: ignored, as intended. Otherwise warn that the repository's `.gitignore` lacks the
`*.local.md` rule `/sdlc:init` writes, suggest running `/sdlc:init` (or adding
`<specs_dir>/**/*.local.md`), and don't stage anything.

## Step 4: report

Where the plan is, how many steps, the criteria map in one line (`AC-1: 1, 3; AC-2: 2`), any
risk that may need `/sdlc:sync`, and the next step: `/sdlc:implement` works through it.
`/sdlc:plan --commit` keeps it in the repository if the team wants it reviewed.
