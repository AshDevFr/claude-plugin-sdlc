---
name: commit-conventions
description: The commit and pull request conventions that tie code to specs, covering the Spec, Implements and Spec-Change trailers, which Spec-Change kind to use, and how trailers survive a squash merge. Use when writing a commit message or PR description for a change that has a spec.
---

# Commit and PR conventions

## Trailers

A commit on a change that has a spec ends with git trailers, so `git log` can answer "which spec,
which revision, which criteria":

```
feat: retry failed webhooks with backoff

Spec: 2026-09-23-webhook-retries@r2
Implements: AC-1, AC-3
```

- `Spec: <spec-id>@r<revision>`: the spec and the revision the commit was written against.
- `Implements: AC-n, ...`: the criteria this commit implements or tests. Only existing,
  non-struck criteria; omit the trailer when the commit implements none (a refactor on the way).
- `Spec-Change: <kind>`: only on commits that change `spec.md` or `intent.md`.

Read them back with `git log --format='%h %s%n%(trailers)'`.

## Spec-Change kinds

- `initial`: the first version of the spec.
- `clarify`: open questions answered or wording tightened, criteria unchanged in meaning.
- `amend`: criteria added, struck or changed in meaning, with a revision bump.
- `acknowledge`: the intent changed and the spec still holds; the intent hash is re-recorded.
- `supersede`: the spec is replaced by another (`state: superseded`).

Choose by what a reviewer needs to re-check: `amend` means read the criteria again; `clarify`
and `acknowledge` mean the criteria's meaning didn't move.

A spec-only commit's subject reads `spec(<spec-id>): r<n> <summary>`.

## Pull requests

The PR description names the spec and its revision, lists the criteria the PR implements, and
says whether the spec changed in this PR (a reviewer must then review the spec change too).

## Per-system: squash merges

When a team squashes on merge, the trailers must end up in the squashed commit.

| Code host | What to set |
|---|---|
| GitHub | Default squash commit message: "Pull request title and description"; keep the trailers at the end of the PR description |
| GitLab | Squash commit template containing `%{description}` (or the commit messages); keep the trailers at the end of the MR description |
