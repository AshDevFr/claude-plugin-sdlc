---
argument-hint: "[<spec-dir>] [<note on the change>]"
description: Write a commit message for the staged change, with the Spec, Implements and Spec-Change trailers that tie it to its spec
disable-model-invocation: true
---

Write a commit message: `$ARGUMENTS`

Read the arguments only from `$ARGUMENTS`: an optional spec directory, then an optional note
from the engineer about the change (use it for the "why"). Load the `sdlc:commit-conventions`
skill first.

The helper is `"${CLAUDE_PLUGIN_ROOT}/tools/specs/specs"`. This command writes text only: it
never stages, commits or pushes.

## Step 1: read the change

```sh
git diff --cached --stat
git diff --cached
git log --oneline -20
```

If nothing is staged, use `git diff` and say the message is for the unstaged changes. Match the
subject style of recent commits for the same work.

## Step 2: find the spec

The spec directory from `$ARGUMENTS`, otherwise the branch's:

```sh
"${CLAUDE_PLUGIN_ROOT}/tools/specs/specs" --json status
```

With no spec, write an ordinary conventional commit without trailers and say so: a change
without a spec is allowed.

## Step 3: pick the mode

- **Spec mode**: everything staged is inside the spec's directory (`spec.md`, `intent.md`,
  attachments).
- **Code mode**: anything else is staged. If `spec.md` or `intent.md` is staged too, the
  message also carries a `Spec-Change` trailer.

## Step 4: when `specs/` is staged, check it first

```sh
"${CLAUDE_PLUGIN_ROOT}/tools/specs/specs" check <spec-dir>
```

Show the findings briefly, as advice. **Write the message anyway**: the check never blocks a
commit. Exit 2 means the check couldn't run; say so and carry on.

## Step 5: choose the trailers

**Spec mode, or code mode touching the spec**: pick the `Spec-Change` kind from what a reviewer
has to re-check, per the skill:

- `initial` when the spec didn't exist before this commit
  (`git cat-file -e HEAD:<spec-dir>/spec.md` fails);
- `amend` when criteria were added, struck or changed in meaning (the revision should have
  been bumped; if it wasn't, say so);
- `clarify` when questions were answered or wording tightened without moving any criterion's
  meaning;
- `acknowledge` when the intent changed and the spec still holds (the recorded intent hash
  changed, the criteria didn't);
- `supersede` when the spec's `state` became `superseded`.

**Code mode**: decide which criteria this change implements or tests. Tests citing
`<spec-id>:AC-n` are the strongest evidence; otherwise judge from the diff. Claim only what the
diff does: a refactor on the way implements none, and then the `Implements` trailer is left out.

Then let the helper build and validate the trailers; never write them by hand:

```sh
"${CLAUDE_PLUGIN_ROOT}/tools/specs/specs" trailers <spec-dir> --implements AC-1,AC-2 --spec-change clarify
```

(pass only the options that apply). Exit 1 names a criterion that doesn't exist or is struck,
or an unknown kind: fix the choice and run it again. Exit 2 means it couldn't run; write the
message without trailers and say why.

## Step 6: write the message

- **Spec mode** subject: `spec(<spec-id>): r<n> <summary>`. **Code mode**: a conventional
  commit subject (`feat:`, `fix:`, `refactor:`, `test:`, `docs:`, `chore:`).
- The body says **why**. The reader has the diff; what they lack is the reason. When a Decision
  in the spec explains a choice, say it in a sentence.
- The helper's trailer lines last, after a blank line, exactly as printed.

Never include:

- `Co-Authored-By:` or any other attribution trailer or footer.
- A count of anything ("four tests", "3 files changed"). Say what the tests cover.
- Links to planning documents that live outside the repository.

Print the message inside a single fenced code block and nothing else inside it. Anything you
want to say about the change, the check's findings or the criteria you left out goes outside
the fence. Then stop: don't offer to commit.
