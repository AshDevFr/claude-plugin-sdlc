---
argument-hint: <intent.md path | file path | pasted request> [--slug <slug>] [--supersedes <spec-id>]
description: Turn a request into a spec, assessing the intent and offering help with its gaps, then drafting spec.md with the engineer
disable-model-invocation: true
---

Start a spec from this request: `$ARGUMENTS`

Read the arguments only from `$ARGUMENTS`. Load the `sdlc:workflow`, `sdlc:intent-writing` and
`sdlc:spec-template` skills before starting: they hold the model (the intent is the original
request, the spec is the contract), how to assess an intent, and how to write each section.

The helper is `"${CLAUDE_PLUGIN_ROOT}/tools/specs/specs"`; call it by that full path. Nothing
in this command commits, pushes or posts anything, and nothing gates on the intent's quality:
gaps are offered, never required.

## Step 1: preflight

```sh
"${CLAUDE_PLUGIN_ROOT}/tools/specs/specs" --version
git status --porcelain --untracked-files=no
```

- If the helper exits 2, show its one line and stop.
- If the repository has no `specs/config.yml` (or `.specs/config.yml`), say so and point to
  `/sdlc:init`; stop.
- If `git status` lists tracked changes, stop before writing anything and ask the engineer to
  commit or stash them first. Untracked files are fine: a request dropped into the repository
  as a new `intent.md` is the usual case.

## Step 2: find the intent

Split `$ARGUMENTS` into the options (`--slug <slug>`, `--supersedes <spec-id>`) and the rest.

- **The rest is an intent written ahead of its spec** (by `/sdlc:intent`, or by hand under the
  same names): `intents/YYYY-MM-DD-<slug>.md`, or a spec directory holding only `intent.md`
  (`specs/YYYY-MM-DD-<slug>/` or its `intent.md`). **Its id is the spec's id**: take the date
  and slug from the name, and don't propose a new slug.
- **The rest is a path to another existing file**: that file is the intent. Don't offer to save
  it again.
- **The rest is text**: it's a request pasted in. Write it to a temporary file outside the
  repository (for example with `mktemp`) so the helper can read it, and remember that it isn't
  saved yet.
- **Nothing**: if `"${CLAUDE_PLUGIN_ROOT}/tools/specs/specs" --json status` says the branch's
  spec is `intent only`, that spec directory's intent is the one to start from. Otherwise ask the
  engineer to paste the request or name a file, and wait.

The spec's title comes from the intent's `# Intent: <name>` heading, or ask for one. The slug
comes from `--slug`, or propose a short one from the title (it becomes part of every test
citation, `<id>:AC-n`, so shorter is better) and let the engineer change it.

## Step 3: assess the intent, and offer

```sh
"${CLAUDE_PLUGIN_ROOT}/tools/specs/specs" intent assess --file <intent file>
```

It reports each template section as `missing`, `empty`, `template` or `ok`. Add the judgement
it can't make, as the `sdlc:intent-writing` skill describes: an outcome nobody could check,
unclear scope, a solution written as the problem, missing constraints the domain obviously has.

List the gaps briefly. Then offer, in one question:

- **improve it together** into a local `intent.md`: work the gaps with the engineer, keeping the
  originator's words, adding rather than rephrasing, and leaving honest open questions instead
  of invented answers; or
- **proceed as it is**.

Both answers are fine. Wait for the answer before writing anything. When the intent has no
gaps, say so in a line and go on.

## Step 4: branch, then create the spec directory

The spec id is the intent's own id when it was written ahead of its spec; otherwise today's
local date and the slug (`date +%F`, then `-<slug>`). If the current
branch is the default branch (`main`, `master`, or what `origin/HEAD` points to), offer to create
and switch to a branch named after the id; on any other branch, stay.

When the intent was pasted, show the text that will become `intent.md` (improved or not) and ask
to confirm saving it. Then create the directory through the helper, which copies the intent and
records its hash:

```sh
"${CLAUDE_PLUGIN_ROOT}/tools/specs/specs" new --title "<title>" --slug <slug> --intent-file <intent file> [--supersedes <spec-id>]
```

For an intent written ahead of its spec, pass its id's date and slug:

- from `intents/`: `new --title "<title>" --date <date> --slug <slug> --intent-file intents/<id>.md`;
- from a spec directory holding only the intent: `new --title "<title>" --date <date> --slug <slug>`,
  with no `--intent-file`: the helper writes `spec.md` beside the existing `intent.md` and
  records its hash.

If it exits 1, a spec with that id already exists: for a new request, propose another slug and
try again; for an intent written ahead, stop and say which spec already has the id.

When the intent was a file inside the repository but outside the specs directory (an
`intents/` file included), it now exists twice. Offer to remove the original so the spec
directory holds the only copy, and remove it only if the engineer agrees; a removed tracked file
shows as deleted, for the engineer to commit with the spec.

## Step 5: draft the spec with the engineer

`specs new` wrote `spec.md` from the template: keep its frontmatter as it is and replace the
body's guidance with real content, section by section, following the `sdlc:spec-template` skill:

- **Context**: what exists today (read the code it touches) and what the intent leaves out.
  Don't restate the intent; the spec links it.
- **Goals / Non-goals**: settle scope here.
- **Acceptance criteria**: `- **AC-n** ...`, numbered from 1, one observable outcome each;
  Given / When / Then with real values wherever two readers could disagree.
- **Design, Risks and security, Rollout and migration**: as much as is known now.
- **Open questions**: anything undecided, each naming who must answer it. An honest open
  question is better than a guessed answer.
- **Revisions**: keep the `r1` entry.

Ask about direction before writing the full body (one question at a time, only what changes the
spec), then show the complete draft and write it to `specs/<id>/spec.md` only when the engineer
confirms.

## Step 6: re-record, lint, and hand over

If `intent.md` was edited after step 4, record the new version:

```sh
"${CLAUDE_PLUGIN_ROOT}/tools/specs/specs" intent record specs/<id>
```

Then lint the spec as advice:

```sh
"${CLAUDE_PLUGIN_ROOT}/tools/specs/specs" lint specs/<id>
```

Report the spec directory, the gaps the intent still has (if the engineer chose to proceed),
and any lint findings. Suggest `/sdlc:clarify` when open questions remain, or `/sdlc:propose`
when the spec is ready for review. Remind the engineer that nothing has been committed.
