---
name: receiving-review
description: What to do with review feedback on a spec or on code, including feedback that is wrong, by verifying each finding before acting, separating a defect from a preference, and saying plainly when a finding does not hold. Use when receiving a review from a person, a review agent or a tool, before changing anything it suggests.
---

# Receiving a review

A review is evidence, not instructions. The default response to criticism is to agree and
comply, and a session that does that turns a review into a way of **introducing** defects the
reviewer only suggested.

The rule: **check the finding against the code, or the spec, before you touch anything.**

## Why this needs saying

A finding arrives with the authority of a reviewer. It usually names a line, a value or a
behaviour, so it can be checked in seconds. Almost nothing checks it. What happens instead: the
code is changed to match, the reviewer is thanked, and nobody learns that the finding was about
a branch that can't be reached, or an argument already validated upstream. The change is a net
loss that looks like collaboration.

## Three verdicts, not two

Sort every finding into one of these, and say which:

| Verdict | What it means | What to do |
|---|---|---|
| **Wrong** | It doesn't hold against the code or the spec | Say so, cite the line that shows it, change nothing |
| **Right** | A real defect | Fix it |
| **Right, but a preference** | Not a defect; a different way of doing it | Say it's a preference, then follow it unless it conflicts with the team's conventions |

The third row is where the friction lives. Collapsing it into "right" produces silent churn;
collapsing it into "wrong" produces an argument about taste. Name it and usually follow it.

## Verify first, and specifically

For each finding, before changing anything:

1. **Read what it names**, with enough context to see what reaches it.
2. **Decide whether the claim holds** on that reading.
3. **If it doesn't, say why, with the evidence.** Naming the line that refutes it is the whole
   answer.

A finding you can't evaluate isn't one to implement: **ask.** Guessing at an unclear finding and
implementing the guess is the worst outcome, because it's then attributed to the reviewer.

## Reviews of a spec

On a spec PR, reviewers comment on the contract itself. Verify those the same way, against the
intent and the code, and route what holds:

- **A wording or clarity fix** that doesn't change what a criterion means: edit it, and the
  commit is a `clarify`.
- **A change to what a criterion requires**, a new criterion, or a struck one: that's an
  amendment. Make it through `/sdlc:sync` (the spec-wrong path), so it gets a revision entry
  with the reviewer as the source, rather than a quiet edit.
- **A question the spec can't answer yet**: add it under `## Open questions` with who must
  answer it, and work it with `/sdlc:clarify`.
- **Scope the intent never asked for**: that's for the intent's author, not the spec; the
  scope-found path of `/sdlc:sync` drafts the note.

Record a decision a review settles in `## Decisions`, with the review as its source: a decision
that lives only in a PR thread is invisible to the next reader.

## Disagreeing is an expected outcome

If a session reports every finding on every review as right, it isn't getting good reviews; it
isn't checking. Reporting a finding as wrong, with the evidence, is normal. Say it plainly, once.
If the reviewer comes back with something new, re-evaluate; repeating the same claim isn't new
information.

## Where this sits

- **`/sdlc:bug`** is the lane for a defect a review uncovers that's bigger than the review.
- **A code finding that contradicts an acceptance criterion** is a question for the spec, not a
  change to make quietly: raise it, and use `/sdlc:sync` if the spec is what's wrong.
- **Nothing here is enforced.** It's a discipline, which is why it's written down: the behaviour
  it corrects is the comfortable one.

---

The three-verdict split and the verify-before-acting rule follow
`superpowers:receiving-code-review` (MIT, Copyright (c) 2025 Jesse Vincent). This is a
reimplementation, not a copy, extended to reviews of a spec.
