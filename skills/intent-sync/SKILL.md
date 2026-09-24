---
name: intent-sync
description: What to do when a spec and its intent drift apart, covering what the intent hash records, the cases from no spec yet to a merged spec, which /sdlc:sync path and Spec-Change kind each takes, and what never to do. Use when intent.md changed after the spec was written, when the spec turns out wrong during implementation, or when an engineer finds scope the intent didn't ask for.
---

# Keeping a spec in step with its intent

The spec is the contract; `intent.md` is the original request. Either can move after the spec
is written: the intent's author edits the request, or the engineer finds the spec wrong while
building it. `/sdlc:sync` is the one command for both, and it follows the same discipline
either way: show the change, decide its impact, record the decision in the spec.

## What the hash records

When a spec is written, the helper stores `intent.md`'s SHA-256 in the spec's frontmatter
(`intent.content_sha256`). The hash is of the normalised text: line endings unified, trailing
whitespace and leading or trailing blank lines dropped. Nothing else is forgiven, so a
reworded line counts as a change even if its meaning didn't move.

- `"${CLAUDE_PLUGIN_ROOT}/tools/specs/specs" intent check <spec-dir>` says `unchanged`,
  `changed` or `not recorded`; `--diff` shows what changed since the recorded version (found in
  git history by its hash).
- `"${CLAUDE_PLUGIN_ROOT}/tools/specs/specs" intent record <spec-dir>` stores the current hash.
  It is the last step of a resolution, never the first.

A changed hash only says the text moved. Whether the spec is affected is a judgement, and it's
the engineer's.

## The cases

"Merged" is a local fact: the spec's `spec.md` exists on the default branch
(`git cat-file -e <default>:<spec-dir>/spec.md`).

| Case | Where the work is | Path | Commit |
|---|---|---|---|
| **A** | No spec yet | n/a: `/sdlc:start` records the intent as it is | `Spec-Change: initial` |
| **B** | Spec written, still in its first review | `/sdlc:sync`: show the diff, update the spec to match, re-record the hash. A revision bump is optional while nobody has approved it | `Spec-Change: clarify` or `amend` |
| **C1** | Spec reviewed, intent changed, **no impact** | `/sdlc:sync`, no impact: a `## Revisions` entry with the reason, `revision` + 1, re-record the hash | `Spec-Change: acknowledge` |
| **C2** | Spec reviewed, intent changed, **impact** | `/sdlc:sync`, impact: amend the touched criteria and sections, a `## Revisions` entry, `revision` + 1, re-record the hash; then `/sdlc:converge` shows what the code must follow | `Spec-Change: amend` |
| **D** | Spec merged: frozen | `/sdlc:sync` refuses to edit it and offers `/sdlc:start <intent> --supersedes <id>`: a follow-up spec that marks the old one superseded | `Spec-Change: supersede` |
| **Spec wrong** | The intent is right, the spec isn't (a criterion is impossible, a design assumption fails) | `/sdlc:sync`, spec wrong: handled like C2, with the reason in the revision entry; the hash is untouched because the intent didn't change | `Spec-Change: amend` |
| **Scope found** | The engineer finds something the intent didn't ask for | `/sdlc:sync`, scope found: draft wording for the intent's author, with the reason. Nothing is edited; once the author changes `intent.md`, continue as C2 | none yet |

## Amending a spec

- **Strike, never delete or renumber.** A dropped criterion becomes
  `- ~~**AC-n** text~~ reason`; tests and commits cite criteria by number, so a number is never
  reused. A new criterion takes the next free number.
- **One revision entry per change**, dated, with who decided and why:
  `- **r3** (2026-09-26, jdoe): internal webhooks excluded by the intent; AC-4 struck.`
- **Check afterwards, as advice:** `specs lint --base <default>` covers a criterion removed
  instead of struck (`L007`) and a changed body without a revision bump (`L011`).

## Merged specs are frozen

Once a spec has shipped, its criteria describe what the code on the default branch does.
Editing it afterwards rewrites history that tests, commits and reviewers already rely on.
A later change is a new spec that supersedes the old one, and the old one keeps saying what
was true when it shipped.

## Offer, don't enforce

Nothing here blocks a commit or a merge. The status line and `/sdlc:check` say the intent
changed; `/sdlc:sync` offers the resolution and shows every edit before writing it. The
engineer can decline and carry on, and that is their call.

## Never

- **Re-record the hash without reading the diff.** The hash is a claim that someone checked
  the spec against this version of the intent. Recording it blind makes the check lie, which
  is worse than having no check. A status is a claim; measure it before believing it.
- **Edit a merged spec.** Supersede it.
- **Widen the spec on the engineer's own authority.** Scope the intent didn't ask for goes to
  the intent's author first, as a draft they can accept or refuse.
- **Edit `intent.md` for its author.** It's their words; the plugin drafts, they decide.
