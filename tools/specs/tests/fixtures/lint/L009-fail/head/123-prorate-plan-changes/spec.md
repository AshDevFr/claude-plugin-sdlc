---
id: 123-prorate-plan-changes
title: Prorate plan changes mid-cycle
ticket:
  system: gitlab                     # gitlab | github | linear
  ref: billing/api#123               # or org/repo#123, or ENG-123
  url: https://gitlab.example.com/billing/api/-/issues/123
  snapshot:
    content_sha256: 5cee61d26ee90c1b7d0fb397ba26f6857b0c91b1c4e275b1a0a89d304ff477d3 # sha256 of normalised title + description
    updated_at: 2026-09-23T10:14:00Z # informational only, see 5.1
    taken_by: jdoe
    taken_at: 2026-09-23T11:02:00Z
revision: 2                          # bumped on every content change after first review
state: active                        # active | superseded
supersedes: []                       # e.g. [88-plan-change-billing]
superseded_by: null                  # set by the PR that supersedes this spec
related:
  - billing/api#117
attachments:
  - threat-model.md
  - sequence.png
---

# Prorate plan changes mid-cycle

> Intent: [billing/api#123](https://gitlab.example.com/billing/api/-/issues/123).
> This spec does not restate the ticket; read it first.

## Context
What exists today and why the ticket needs more than the ticket says.

## Goals
## Non-goals

## Acceptance criteria
- **AC-1** Upgrading mid-cycle charges the prorated difference immediately.
- **AC-2** Downgrading mid-cycle issues a credit applied to the next invoice.
- **AC-3** Proration uses the subscription's billing anchor, not the calendar month.

## Design
Proration uses the billing anchor and posts an invoice line; credits use the balance ledger.

## Risks and security
Link `threat-model.md` when the change crosses a trust boundary.

## Rollout and migration

## Open questions
Each one names who must answer it. The spec is not approvable with open questions left.

## Decisions
- 2026-09-24: Credits never expire. Source: [comment on the ticket](https://...)

## Revisions
- **r2** (2026-09-26, jdoe): Ticket updated to exclude annual plans. Non-goals and AC-3
  updated. Trigger: ticket-updated.
- **r1** (2026-09-23, jdoe): Initial spec.
