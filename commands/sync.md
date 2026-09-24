---
argument-hint: "[<spec-dir>]"
description: Bring a spec back in step after its intent.md changed or the spec turned out wrong, by showing the change, deciding its impact with the engineer and recording the decision; a merged spec gets a follow-up spec instead
disable-model-invocation: true
---

Sync a spec: `$ARGUMENTS`

Read the arguments only from `$ARGUMENTS`: an optional spec directory. Without one, use the
current branch's spec. Load the `sdlc:intent-sync` and `sdlc:spec-template` skills first: the
cases, the kinds and the "never" list live there.

The helper is `"${CLAUDE_PLUGIN_ROOT}/tools/specs/specs"`. Everything here is offered, not
enforced: every edit is shown before it's written, and nothing is committed, pushed or sent
anywhere.

## Step 1: find the spec and what changed

```sh
"${CLAUDE_PLUGIN_ROOT}/tools/specs/specs" --json status
"${CLAUDE_PLUGIN_ROOT}/tools/specs/specs" --json intent check <spec-dir>
```

Use the spec directory from `$ARGUMENTS`, otherwise the one `status` names. With neither, ask
which spec and stop. Exit 2 from the helper: show its message and stop; never guess the state.

- **`changed`**: the intent moved since the spec recorded it. Go on.
- **`unchanged`**: ask what brings the engineer here. If the spec turned out wrong while the
  intent is right (a criterion that can't be met, a design assumption that failed), go on with
  the **spec wrong** path in Step 4. Otherwise there is nothing to sync: say so and stop.
- **`not recorded`**: the spec never stored its intent's hash. Offer to record it now, after
  the engineer confirms the spec reflects the current intent.
- **`n/a`**: a spec with only a ticket; there's no intent file to sync against. Offer the spec
  wrong path if that's what they need, otherwise stop.

## Step 2: is the spec merged?

A merged spec is frozen. Find the default branch (`git symbolic-ref --short
refs/remotes/origin/HEAD` without `origin/`, else `main`, else `master`), then:

```sh
git cat-file -e <default>:<spec-dir>/spec.md
```

If that succeeds, the spec has shipped. **Don't edit it.** Explain in two sentences why
(its criteria describe code already on the default branch), show the intent change briefly,
and offer the follow-up spec:

`/sdlc:start <spec-dir>/intent.md --supersedes <spec-id>`

which starts a new spec from the current intent and marks this one superseded. Then stop.

## Step 3: show the change and what it touches

```sh
"${CLAUDE_PLUGIN_ROOT}/tools/specs/specs" intent check --diff <spec-dir>
```

Show the diff. Then read `spec.md` and list the criteria and sections the change plausibly
touches, each with the diff line that touches it and one sentence on how. Be concrete: "the
added line `Internal webhooks are out of scope` excludes what AC-3 requires". Say plainly when
nothing seems touched.

Then ask the engineer to choose, with your recommendation and its reason:

- **No impact**: the intent was reworded or clarified; the spec still says the right thing.
- **Impact**: the spec has to change.

Don't decide for them, and don't record anything before they've seen the diff and chosen.

## Step 4: apply the resolution

Show each edit before writing it. Today's date and the engineer's name go in the revision
entry.

**Has the spec been reviewed yet?** If it's still in its first review (nobody has approved
it), the engineer may prefer updating it in place without a new revision; offer that, and
otherwise bump as below.

**No impact** (`Spec-Change: acknowledge`):

1. `revision` + 1 in the frontmatter.
2. Under `## Revisions`: `- **r<n>** (<date>, <who>): intent reviewed, no change to the spec:
   <why>.`
3. Record the new intent version:
   `"${CLAUDE_PLUGIN_ROOT}/tools/specs/specs" intent record <spec-dir>`

**Impact** (`Spec-Change: amend`):

1. Propose each edit: criteria changed or added, sections (Goals, Non-goals, Design) brought
   in line. **Strike, never delete or renumber**: `- ~~**AC-n** text~~ <reason>`; a new
   criterion takes the next free number. Apply the ones the engineer accepts.
2. `revision` + 1, and under `## Revisions`: `- **r<n>** (<date>, <who>): <what the intent
   changed>; <which criteria moved>.`
3. Record the new intent version:
   `"${CLAUDE_PLUGIN_ROOT}/tools/specs/specs" intent record <spec-dir>`

**Spec wrong** (the intent didn't change; `Spec-Change: amend`): as Impact, except the
revision entry gives the reason the spec was wrong, and the intent hash is left alone.

## Step 5: check and hand over

```sh
"${CLAUDE_PLUGIN_ROOT}/tools/specs/specs" lint --base <default> <spec-dir>
```

Report findings as advice: `L007` means a criterion was removed instead of struck, `L011` a
body change without a revision entry. Then:

- summarise what changed and why, in two or three lines;
- after an amend, suggest `/sdlc:converge` once there is code: it shows what now contradicts
  the spec;
- offer `/sdlc:commit-msg`, which writes the spec commit with the `Spec-Change` trailer.
  Nothing has been committed.
