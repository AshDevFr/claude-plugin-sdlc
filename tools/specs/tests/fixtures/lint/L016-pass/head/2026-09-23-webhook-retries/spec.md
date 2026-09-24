---
id: 2026-09-23-webhook-retries
title: Webhook retries
intent:
  file: intent.md
  content_sha256: 17cb36c866de7fccf4a5aa1281496bb2a9b4ed4348094c66f0237833aadafb07
  recorded_at: 2026-09-23T11:02:00Z
  recorded_by: jdoe
revision: 1
state: active
supersedes: []
superseded_by: null
---

# Webhook retries

> Intent: [intent.md](intent.md). The spec is the contract; the intent is the original request.

## Context
Deliveries are sent once and dropped on any error.

## Goals

## Non-goals

## Acceptance criteria
- **AC-1** Given a 503, when delivering, then it is retried.

## Design
Failed deliveries go to a retry queue per partner, using the existing backoff.

## Risks and security
Retries make delivery at-least-once; partners dedupe on the event id.

## Rollout and migration

## Open questions
Each one names who must answer it. The spec is not approvable with open questions left.

## Decisions

## Revisions
- **r1** (2026-09-23, jdoe): Initial spec.
