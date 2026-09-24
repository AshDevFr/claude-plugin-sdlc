---
argument-hint: "[<spec-dir>...] [--all] [--ready]"
description: The local check before committing spec changes, covering lint, criteria no test cites yet, and whether the intent changed since the spec
disable-model-invocation: true
---

Check specs: `$ARGUMENTS`

Read the arguments only from `$ARGUMENTS`: optional spec directories, `--all`, `--ready`.
Without a directory, the current branch's spec is checked.

Everything this reports is advice. It never blocks a commit and fixes nothing by itself.

## Step 1: run the helper

```sh
"${CLAUDE_PLUGIN_ROOT}/tools/specs/specs" --json check $ARGUMENTS
```

- **Exit 0**: nothing to report.
- **Exit 1**: there are findings. That's the normal "here's what to look at" case, not an error.
- **Exit 2**: the helper couldn't run the check (a usage or configuration problem, a missing
  Python or PyYAML). Show its message and say you **couldn't check**; never present this as a
  pass. If the message says there's no spec for the branch, suggest passing the spec directory
  or `--all`.

## Step 2: present it

One short block per spec:

- **Lint findings**, grouped by rule, each with its line and a one-line explanation of what to do.
- **Criteria no test cites yet** (`AC-n`): tests cite them as `<spec-id>:AC-n`. Before code
  exists this is expected; it matters once the implementation is underway.
- **The intent**: `unchanged`, `changed`, `not recorded`, or `n/a` for a ticket spec. When it's
  `changed`, the intent was edited after the spec was written: name `/sdlc:sync` as the next
  step, which shows the change and walks through acknowledging or amending.
- With `--ready`: whether the spec is ready for review, and the reasons when it isn't (open
  questions: `/sdlc:clarify`; template text left in a section; lint findings; the intent).

End with the one or two most useful next steps. Don't edit anything.
