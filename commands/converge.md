---
argument-hint: "[<base-branch>] [<spec-dir>] [--test \"<command>\"]"
description: Read-only report of the branch's code against its spec, giving each acceptance criterion a verdict with evidence and flagging changes no criterion explains
disable-model-invocation: true
---

Converge the code with its spec: `$ARGUMENTS`

Read the arguments only from `$ARGUMENTS`: an optional base branch (default: the repository's
default branch, `git symbolic-ref --short refs/remotes/origin/HEAD` without `origin/`, else
`main`), an optional spec directory (default: the branch's), and `--test "<command>"` if the
engineer wants the tests run. Load the `sdlc:workflow` skill first.

**This command is read-only.** It edits no file, stages nothing and runs nothing that changes
state; it doesn't fix code or spec. The only command it may run beyond reading is the test
command the engineer passed with `--test`: never guess how to run the tests.

A commit saying `Implements: AC-2` is a claim, and so is a green check mark. This command
turns claims into evidence: every verdict points at the lines behind it.

## Step 1: gather the facts

```sh
"${CLAUDE_PLUGIN_ROOT}/tools/specs/specs" --json check <spec-dir>
"${CLAUDE_PLUGIN_ROOT}/tools/specs/specs" --json coverage <spec-dir>
git log --format='%h %s%n%(trailers:key=Implements)' <base>..HEAD
git diff --stat <base>...HEAD
git diff <base>...HEAD -- . ':!<spec-dir>'
```

Exit 2 from the helper: say what couldn't be checked and carry on with what you have; a
missing fact is reported, never assumed. Read `spec.md` in full at HEAD: the criteria, Goals,
Non-goals, Design and Decisions. Struck criteria are skipped.

If `--test` was given, run it once and keep the result per test.

## Step 2: a verdict per criterion

For each criterion that isn't struck, find the code that implements it, or establish that
nothing does. Read the code, not only the commit messages: an `Implements:` trailer is where to
start looking, not the verdict.

| Verdict | Meaning |
|---|---|
| `COVERED` | Implemented, and a test cites it (`<spec-id>:AC-n`) and exercises it |
| `UNTESTED` | Implemented, but no test cites it, or the citing test doesn't exercise it |
| `MISSING` | Nothing implements it, or only part of it: say which part is absent |
| `CONTRADICTED` | The code does something the criterion, a Non-goal or a Decision rules out |
| `UNCHECKED` | You couldn't establish it either way (say why). Not the same as `MISSING` |

- **Evidence for every verdict**: `file:line` for the code, the citing test, or, for
  `MISSING`, where you looked and what's absent. `MISSING` and `CONTRADICTED` quote the
  criterion's words that aren't met.
- A citation only proves a test names the criterion; if the test doesn't exercise what the
  criterion says, the verdict is `UNTESTED` and the reason says so.
- A failing test from `--test` that cites the criterion makes it `CONTRADICTED` or `MISSING`,
  whichever the failure shows.

## Step 3: changes no criterion explains

Go through the changed files outside the spec directory. A change is justified when a
criterion, a Goal or the Design needs it, or it's the plumbing one of those needs (a test for
a criterion, an import, a config entry). Anything else is `UNJUSTIFIED`: name the file, what
it changes, and that nothing in the spec asks for it. That's a question, not an accusation: it
may be a missing criterion, or it may belong in another change.

## Step 4: report

One table, criteria first in AC order, then the unjustified changes:

| Item | Verdict | Evidence |
|---|---|---|
| AC-1 | `COVERED` | `webhooks.py:14-24`; `tests/test_deliver.py:7` cites and exercises it |
| `logging_setup.py` | `UNJUSTIFIED` | new log format; no criterion or Design element mentions logging |

Before the table, one line: the spec, its revision, the base, and whether tests were run.
After it, the next steps, most useful first: a criterion to implement, a test to add, a
change to justify with `/sdlc:sync` (the spec was wrong or incomplete) or to move out.

Then a short summary block the engineer can paste into the PR description or give to
`/sdlc:pr-msg`, in a fenced block:

```
Converge (<spec-id>@r<n>, against <base>): AC-1 COVERED, AC-2 MISSING, AC-3 UNTESTED; 1 unjustified change.
```

Write it to a file only if the engineer asks. Never mark, tick or change anything to match
what you found.
