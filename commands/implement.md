---
argument-hint: "[<spec-dir>] [<step or criterion to start from>]"
description: Implement a spec step by step from its plan, failing test first, with tests citing the criteria and a commit per step carrying the spec's trailers; stops and hands over when the spec turns out wrong
disable-model-invocation: true
---

Implement: `$ARGUMENTS`

Read the arguments only from `$ARGUMENTS`: an optional spec directory (default: the branch's
spec), then optionally the plan step or criterion to start from. Load the `sdlc:test-first`,
`sdlc:commit-conventions` and `sdlc:finishing-work` skills first.

The helper is `"${CLAUDE_PLUGIN_ROOT}/tools/specs/specs"`. This command writes code and tests
and commits each step, but **only after showing the commit message and getting a yes**. It
never pushes.

## Step 1: where things stand

```sh
"${CLAUDE_PLUGIN_ROOT}/tools/specs/specs" --json check <spec-dir>
git status --short
git log --oneline -10
```

Read `spec.md` in full and `<spec-dir>/plan.local.md` (or `plan.md`) if there is one. Without
a plan, work from the spec's criteria in order and say so; `/sdlc:plan` writes one.

- **Open questions or a changed intent** in the check: say so before writing code; building
  against a spec that's still moving builds the wrong thing. Continue only if the engineer
  wants to.
- **Not ready to implement** (`ready_to_implement` is false in the check): a spec in its
  `depends_on` isn't `done`, so the code this spec builds on may not exist yet. Say so before
  writing code, and name each blocking spec from `blocked_by` with its status, for example
  "`2026-09-20-delivery-log` is `ready-for-code`, not `done`". This is a warning, not a
  refusal: continue only if the engineer wants to, and never change an intent's `status`
  yourself.
  A dependency whose status is `unknown (tracker)` is a ticket spec: whether it's done lives in
  the tracker, which the plugin doesn't read. Ask the engineer to confirm it there. With nobody to
  ask (an unattended run), check the code instead: run
  `"${CLAUDE_PLUGIN_ROOT}/tools/specs/specs" coverage <specs_dir>/<dependency-id>` and read
  the code its criteria describe; treat it as done only if the code shows every criterion is
  built, and say what you found.
- **Uncommitted changes** that aren't yours: ask before building on top of them.
- **Steps already done**: commits whose `Implements:` trailers cover a step's criteria, with
  their tests in place, are done. Start at the first step that isn't, or where `$ARGUMENTS`
  says.

## Step 2: each step, test first

For each plan step (or criterion), per the `test-first` skill:

1. **Write the failing test** the step names. It cites its criterion as `<spec-id>:AC-n` in its
   name or a comment beside it. Run it and see it fail for the right reason: an assertion,
   not an import error. If it passes before any code exists, stop and find out why.
2. **Write the smallest change** that makes it pass. Run it and the tests near it.
3. **Tidy** with the tests green.
4. **Commit the step.** Get the message the way `/sdlc:commit-msg` writes it in code mode,
   with the trailers from
   `"${CLAUDE_PLUGIN_ROOT}/tools/specs/specs" trailers <spec-dir> --implements AC-n[,...]`.
   Show the files and the message, and commit only on a yes. On a no, leave the changes
   staged and ask what to change.

One step at a time; don't start the next until this one is committed or the engineer says to
keep going without committing.

## When the spec is wrong

Sometimes the code shows a criterion can't be met as written: it contradicts another
criterion, the Design, a Decision, or what the codebase can do. **Stop.** Don't pick a side,
don't bend the test to pass, and don't quietly build something else. Make no further commit
until the engineer has resolved it.

Say, in a few lines:

- the criterion (quote it) and what it contradicts (quote that too, with its line);
- what you found in the code that shows it, with the file and line;
- the options you see, and which you'd recommend.

Then hand it over: `/sdlc:sync`, the spec-wrong path, amends the spec with a revision entry.
Once the spec is amended and committed, `/sdlc:implement` picks up again from this step.

The same goes for scope the spec never asked for that the work turns out to need: stop and
name it; it's for the spec, through `/sdlc:sync`, not a quiet addition.

## Step 3: at the end

```sh
"${CLAUDE_PLUGIN_ROOT}/tools/specs/specs" check <spec-dir>
```

Report the commits made, the criteria each implements, and any criterion still uncited. Then
point at the rest of `finishing-work`: `/sdlc:converge` to check every criterion and changed
file against the spec, `/sdlc:pr-msg` for the PR description. Marking the PR ready is the
engineer's call.
