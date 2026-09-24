---
name: workflow
description: How the sdlc workflow fits together, covering what an intent and a spec are, which is the contract, where they live, which command to run when, what to do when the intent changes, and how to call the plugin's helper. Use when starting any sdlc command, when unsure which command fits the situation, or when a helper call fails.
---

# The sdlc workflow

## The model

- **The intent is the original request**: `intent.md`, in the words of whoever has the problem.
  It is allowed to be imperfect. The plugin assesses it and offers to fill its gaps; it never
  refuses to proceed because of it.
- **The spec is the contract**: `spec.md`. It is what the team reviews in the pull request, what
  the code is built against, and what tests cite. Its acceptance criteria are numbered `AC-1`,
  `AC-2`, ... and a number is never reused or renumbered, because commits, tests and review
  comments point at it.
- **Truth flows intent → spec → code.** Code is never the reason to change a spec silently: when
  the code shows the spec is wrong, the spec is amended on purpose, with a new revision.

## Offer, don't enforce

Every check here is advice. The plugin reports and suggests; the engineer decides. It never
blocks a commit, never gates on an intent's quality, and never edits a spec to match the code
without asking. Teams that want enforcement add it to their own CI; that is their choice.

## Where things live

```
specs/
├── config.yml                    # tracker, code host, specs directory
├── templates/                    # the team's spec and intent templates
└── 2026-09-23-webhook-retries/   # one directory per change: <date>-<slug>
    ├── intent.md
    ├── spec.md
    └── ...                       # attachments, and plan.local.md (not committed)
```

- The id is the directory name, `YYYY-MM-DD-<slug>`, fixed at creation. It never changes, even
  if a ticket is linked later.
- Never store in a file what the code host already knows: approvals, PR numbers, merge state.
- A change earns a spec when it is substantial: new behaviour, a contract others depend on, a
  risky migration. Small fixes don't need one. That call is a team convention, not a check.

## Which command when

| Situation | Command |
|---|---|
| Setting a repository up | `/sdlc:init` |
| A new request to turn into a spec | `/sdlc:start` |
| The spec has open questions | `/sdlc:clarify` |
| Checking a spec against itself and its intent | `/sdlc:analyze` |
| The spec is ready for review, before code | `/sdlc:propose` |
| Before committing spec changes | `/sdlc:check` |
| `intent.md` changed, or the spec turned out wrong | `/sdlc:sync` |
| Planning the implementation | `/sdlc:plan` |
| Implementing against the spec | `/sdlc:implement` |
| A bug with a reproduction | `/sdlc:bug` |
| Does the diff do what the spec says? | `/sdlc:converge` |
| Commit and PR text | `/sdlc:commit-msg`, `/sdlc:pr-msg` |

## When the intent changes, or the spec turns out wrong

The spec records a hash of `intent.md` when it is written, so a later edit is noticed.
`/sdlc:sync` handles every spec change the same way:

| What happened | What to do |
|---|---|
| `intent.md` changed, the spec still holds | Acknowledge: record the new intent hash, add a revision note |
| `intent.md` changed and the spec must follow | Amend: bump the revision, strike criteria that no longer apply (never delete them), add new ones, record the new hash |
| The intent is the same, but the spec is wrong | Amend, with the reason in the revision entry |
| The engineer finds scope the intent didn't ask for | Draft a note for the intent's author; don't widen the spec on your own |

Either way the change is visible in the diff and gets reviewed again.

## Calling the helper

The plugin's helper does the parts that must be exact: parsing, lint, hashes, ids, coverage.
Always call it by its full path inside the plugin, quoted:

```sh
"${CLAUDE_PLUGIN_ROOT}/tools/specs/specs" <command> [options]
```

Never call a bare `specs`, and never look for a copy in the product repository: there isn't
one. Use `--json` when you need to read its output.

Exit codes: 0 means nothing to report, 1 means findings to show the engineer as advice, 2 means
a usage or configuration problem. When the helper exits 2, it has printed one line saying what
is wrong (a missing Python 3.10+ or PyYAML, a broken `specs/config.yml`). Show that line to the
user and stop; don't retry or work around it.
