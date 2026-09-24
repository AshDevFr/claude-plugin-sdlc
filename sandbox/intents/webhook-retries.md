# Intent: webhook retries
Author: P. Martin (integrations). Status: draft.
## Problem
Partners miss events when their endpoint is briefly down: we send each webhook once and drop
it on any error. Support handles about ten tickets a week asking us to resend events by hand.
## Proposed outcome
A failed delivery is retried automatically for long enough to ride out a short outage, and
partners can see which deliveries failed for good.
## Affected users and systems
Partners receiving webhooks, the support team, the webhooks sender.
## Constraints
No change to the payload format. Deliveries stay in order per partner.
## Open questions
How long should we keep retrying before giving up?
