---
name: finishing-work
description: What must be true before a spec'd change's PR is marked ready, what happens at merge, and when to throw a branch away instead, in terms of the checks /sdlc:check and /sdlc:converge actually run. Use when the implementation is done and tests pass, before marking a PR ready for review.
---

# Finishing work

The code is written and the tests pass. Before the PR is marked ready, the spec, the code and
the PR description have to agree, and the plugin's two checks say whether they do. Their
findings are advice: answering one can mean fixing it, or saying in the PR why it stands.

## Before marking the PR ready

### The spec: `/sdlc:check`

```sh
"${CLAUDE_PLUGIN_ROOT}/tools/specs/specs" check --ready <spec-dir>
```

Each finding, and what answers it:

| Finding | Answered by |
|---|---|
| **lint findings** | Fixing the spec, or knowing why a finding doesn't apply |
| **open questions** | None left: each one decided (`/sdlc:clarify`) or moved out of scope with a Decision |
| **template text** | Every section says something about this change, or is empty on purpose |
| **intent changed** | `/sdlc:sync`: acknowledged or amended, so the spec matches the intent as it reads now |
| **intent not recorded** | `specs intent record`, once the spec reflects the current intent |
| **uncited** criteria | A test citing each one as `<spec-id>:AC-n`; a criterion nothing tests is a claim |

A spec changed after reviewers approved it needs a revision entry, and on most code hosts a new
approval: the PR description should say it changed.

### The code: `/sdlc:converge`

Every criterion and every changed file, with evidence. Before ready:

| Verdict | Answered by |
|---|---|
| `COVERED` | Nothing: implemented and a citing test exercises it |
| `UNTESTED` | A test that exercises the criterion, or a reason in the PR why it can't be tested |
| `MISSING` | Implementing it, or amending the spec through `/sdlc:sync` if it shouldn't be built |
| `CONTRADICTED` | Fixing the code, or amending the spec through `/sdlc:sync` if the spec is what's wrong |
| `UNCHECKED` | Checking it by hand, and saying what you found |
| `UNJUSTIFIED` | Removing the change, moving it to its own PR, or a criterion that asks for it |

Never edit the spec to match the code without saying so: that's an amendment, and it goes
through `/sdlc:sync` with a revision entry.

### The PR

- **The description is current**: `/sdlc:pr-msg` after the last commit, with the criteria
  implemented, whether the spec changed in the PR, and the converge summary.
- **The trailers are at the end of the description**, so a squash merge keeps `Spec` and
  `Implements`.
- **Nothing is uncommitted or unpushed**, and the full test suite has run, not only the tests
  near the change.

### Approval

Reviewers approve in the code host's own review view: spec reviewers (code owners on `specs/`)
for the spec, the usual reviewers for the code. The plugin never reads approval state and
never marks anything approved.

## At merge

The spec on the default branch is now the frozen record of what shipped. Nothing more to do in
it. A later change to the same behaviour starts from a new or updated intent and a new spec
that supersedes this one (`/sdlc:start ... --supersedes <spec-id>`). Delete the branch.

## Or throw it away

A spike that answered its question has no reason to survive: keeping it costs review attention
and invites someone to build on code never meant to be kept. Delete the branch deliberately. If
it taught something, put the answer where the next person will look: the spec's `## Decisions`,
or the intent's author, if it changes what's being asked. **The answer is the artifact, not the
code.**

---

The three-outcome shape follows `superpowers:finishing-a-development-branch` (MIT, Copyright
(c) 2025 Jesse Vincent). This is a reimplementation, not a copy, built around a spec and the
plugin's checks.
