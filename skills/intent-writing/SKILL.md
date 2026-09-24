---
name: intent-writing
description: How to write and assess an intent.md, the original request behind a spec, covering its sections, how to spot the gaps that make a weak spec, and how to offer help without turning the intent into a gate. Use when starting a spec from a request, when an intent looks thin or overgrown, or when someone asks how to write one.
---

# Writing and assessing an intent

## What an intent is

`intent.md` is the original request, in the words of whoever has the problem: usually a product
person, sometimes an engineer. It says what hurts and what should be true afterwards. It isn't a
spec and shouldn't try to be one: the spec is the contract and gets written from the intent.

Keep the originator's language. Rewording an intent into engineering terms loses exactly what
it exists to keep.

## The sections

The template in use is the team's `<specs_dir>/templates/intent.md` when it exists, otherwise
the plugin's own at `${CLAUDE_PLUGIN_ROOT}/tools/specs/sdlc_specs/templates/intent.md`. After a
`# Intent: <name>` title and an `Author: ... Status: ...` line:

- **Problem**: the current situation and what hurts, concretely. "Customers phone the contact
  center to ask where their claim is" beats "improve claim visibility".
- **Proposed outcome**: the end state as the people affected will see it, not a solution
  design.
- **Affected users and systems**: who and what this touches.
- **Constraints**: limits the solution must respect: security, data, compatibility, dates.
- **Open questions**: what is still unknown, and who can answer it.

## Writing one before the spec

`/sdlc:intent` is the way to write an intent with whoever has the problem, before any spec
exists: an interview in their words, one question at a time, that fills the template and
writes one file. `/sdlc:start` then picks the file up and keeps its id.

## Assessing an intent

Start with the facts the helper can establish:

```sh
"${CLAUDE_PLUGIN_ROOT}/tools/specs/specs" intent assess <spec-dir>        # or --file <path>
```

It reports each section as `missing`, `empty`, `template` (still the guidance text) or `ok`, and
lists the open questions. Then judge what it can't:

- **A vague outcome**: nothing anyone could check ("better", "faster", "improved").
- **Unclear scope**: nothing that says where the change stops.
- **Over-specification**: a solution written as the problem ("add a Redis cache"), which hides
  the real need and closes off better designs.
- **Missing constraints** that the domain obviously has: personal data, money, auth.
- **Unanswered questions that block the spec**, as opposed to ones the spec can carry.

## Offering help, never gating

List what you found, briefly, then offer: improve it into a local `intent.md` together, or
proceed as it is. Both answers are fine. An intent that stays thin produces a spec with more
open questions, which `/sdlc:clarify` works down later.

When improving an intent:

- Ask the originator's questions of the engineer; don't invent requirements to fill a section.
- Keep the problem in the originator's words; add, don't rephrase.
- Move solution detail out of the problem and into a note for the spec's Design section.
- Leave an honest `Open questions` section rather than a confident guess.
