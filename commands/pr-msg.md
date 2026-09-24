---
argument-hint: "[<base-branch>] [<spec-dir>]"
description: Write a pull request title and description from the branch's spec, the criteria its commits implement and whether the spec changed
disable-model-invocation: true
---

Write a PR title and description: `$ARGUMENTS`

Read the arguments only from `$ARGUMENTS`: an optional base branch (default: the repository's
default branch, `git symbolic-ref --short refs/remotes/origin/HEAD` without the `origin/`
prefix, else `main`), then an optional spec directory (default: the branch's). Load the
`sdlc:commit-conventions` skill first.

The helper is `"${CLAUDE_PLUGIN_ROOT}/tools/specs/specs"`. This command prints text only: it
never pushes, opens or edits a pull request.

## Step 1: read the branch

```sh
git log --format='%h %s%n%b' <base>..HEAD
git diff --stat <base>...HEAD
```

## Step 2: read the spec

Use the spec directory from `$ARGUMENTS`, otherwise the one `status` names:

```sh
"${CLAUDE_PLUGIN_ROOT}/tools/specs/specs" --json status
```

Read `spec.md` in full: its title, revision, criteria, Decisions, and the `ticket` block in the
frontmatter if there is one. With no spec, write a plain description (Summary, Changes, Notes)
and say the PR isn't tied to a spec.

## Step 3: the facts the helper gives

```sh
"${CLAUDE_PLUGIN_ROOT}/tools/specs/specs" trailers <spec-dir> --from-log <base>
```

It prints `Spec: <id>@r<n>` and, when this branch's commits implement any, `Implements:` with
the criteria in the order they were first implemented. A warning names a criterion a commit
claimed that has since been struck; mention it under Notes. Exit 2 means it couldn't run: say
so and write the description without the trailers.

Whether the spec changed in this PR:

```sh
git diff --quiet <base>...HEAD -- <spec-dir>
```

Exit 1 means it did; the `Spec-Change` trailers in the branch's commits say how.

## Step 4: write it

**Title**: `Draft: Spec for <spec title>` when only the spec directory changed; otherwise a
conventional-commit title for the change, imperative, under about 72 characters.

**Description**, in this order:

```
## Summary
<2-4 sentences: what the PR delivers, in behaviour, not code layout.>

## Spec
<spec-id> at r<n>. <One line: spec-only, or which criteria this PR implements (from the
helper), and any not yet implemented.>
<When the spec changed in this PR: say so, name the kinds (amend means reviewers re-read the
criteria), and that reviewers must review the spec change too.>

## Changes
<3-8 bullets grouped by what users or operators notice: endpoints, config keys, behaviour,
migrations. No internal module or function names.>

## Notes
<Optional: breaking changes, defaults, follow-ups, struck criteria. Omit when empty.>

<closing line, see below>

<the helper's trailer lines, exactly as printed>
```

**Closing line**: only when the spec's frontmatter has a `ticket` and the PR carries code:
`Closes <ticket.ref>` (GitHub, GitLab and Linear all read it). A spec-only PR references the
ticket without closing it: `Refs <ticket.ref>`. A spec without a ticket gets no closing line.

**Trailers last**: they're the end of the description so a squash merge that uses the
description keeps them (the skill's per-system settings).

Never include `Co-Authored-By:` or any attribution footer, a count of anything, or links to
planning documents outside the repository.

## Output

Two fenced `markdown` blocks, each copyable on its own: first under a `## Title` heading, then
under `## Description`. Anything else you want to say (the spec changed, a struck criterion,
the helper couldn't run) goes after them, briefly. Then stop: don't offer to push or open the PR.
