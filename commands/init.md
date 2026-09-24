---
argument-hint: [--upgrade]
description: Set this repository up for the sdlc workflow (config, CLAUDE.md section, spec and intent templates)
disable-model-invocation: true
---

Set up this repository for spec-driven development: `$ARGUMENTS`

Read the arguments only from `$ARGUMENTS`. The only one this command knows is `--upgrade`.

Every file write goes through the plugin's helper, `specs init`, which is idempotent: running
this command again changes nothing and reports each item as already present. This command runs
the interview, shows what will change before changing it, and reports. It never commits, never
writes a `CODEOWNERS` file, never touches CI, and never asks for a token.

## Step 1: check the machine and the repository

```sh
"${CLAUDE_PLUGIN_ROOT}/tools/specs/specs" --version
```

If it exits 2, it has printed one line saying what's missing (Python 3.10+ or PyYAML). Show that
line to the user and stop: every later step needs the helper.

The helper needs a git repository. If the working directory isn't inside one, say so and stop.

## Step 2: `--upgrade`

If `$ARGUMENTS` contains `--upgrade`, the repository is already set up. Show what an upgrade
would do, ask for confirmation, then run it:

```sh
"${CLAUDE_PLUGIN_ROOT}/tools/specs/specs" init --upgrade --dry-run
"${CLAUDE_PLUGIN_ROOT}/tools/specs/specs" init --upgrade
```

It refreshes the `CLAUDE.md` section and replaces a spec or intent template only when the team
never edited it. A template reported `customised` is left exactly as it is; show its diff so the
team can decide whether to merge the plugin's changes by hand. Then go to step 6.

## Step 3: the interview

Ask one question at a time, proposing an answer wherever one can be inferred:

1. **Code host.** Infer it from `git remote get-url origin` (`github.com` or a GitHub Enterprise
   host means `github`; a GitLab host means `gitlab`) and ask the user to confirm.
2. **Tracker**: `gitlab`, `github` or `linear`. It only sets how ticket keys and ticket-named
   spec directories look; the plugin doesn't connect to it.
3. If the tracker is `gitlab` or `github` and tickets live in a project other than this
   repository: that project (`group/project`). Otherwise skip.
4. If the tracker is `linear`: the team key (`ENG` in `ENG-123`).
5. **Spec approvers**, optional: a group (`@org/team`) or usernames. Used only to suggest the
   `CODEOWNERS` entry in step 6.
6. **Specs directory**: `specs` (default, visible) or `.specs` (out of the way; some tools skip
   hidden paths).

## Step 4: show the plan, then apply it

Run the same command with `--dry-run` first and show the user the list of files and what will
happen to each, then ask for confirmation:

```sh
"${CLAUDE_PLUGIN_ROOT}/tools/specs/specs" init --tracker <tracker> --host <host> [--project <p>] [--team-key <k>] [--approvers <a>] [--specs-dir <d>] --dry-run
```

On confirmation, run it again without `--dry-run`.

If it exits 1, a `config.yml` already exists with other settings. Show the user the message and
the existing file; don't delete or edit it for them. They can edit it by hand, or remove it and
run this command again.

## Step 5: lint, as advice

```sh
"${CLAUDE_PLUGIN_ROOT}/tools/specs/specs" lint
```

On a new setup there are no specs yet and this reports nothing. In a repository that already had
specs, show any findings as advice; they never stop the setup.

## Step 6: report, and the settings the team applies

Report the files by outcome: written, appended, already present, updated, customised.

Then print this guidance as text. Don't write it anywhere: the team decides whether to apply it.

**Spec review through CODEOWNERS.** Suggest this line for the repository's `CODEOWNERS` file,
using the approvers from the config (or a placeholder when none were given), and the specs
directory chosen:

```
/specs/ @org/spec-approvers
```

**Re-approval when a spec changes.** Print only the section for the configured code host. The
aim: a push of code keeps the spec approval, and an edit to the spec resets it.

For **GitLab** (`CODEOWNERS` in `.gitlab/`, the root or `docs/`):

- Settings > Repository > Protected branches: turn on "Code owner approval" for the default
  branch.
- Settings > Merge requests > Approval settings: turn on
  "Remove approvals by Code Owners if their files changed", and leave
  "Remove all approvals when commits are added to the source branch" off. Only the spec
  reviewers' approvals reset, and only when the spec changes.
- Both settings need GitLab Premium or above; without them, spec approval is a convention.

For **GitHub** (`CODEOWNERS` in `.github/`, the root or `docs/`), in the branch protection rule
or ruleset for the default branch:

- "Require a pull request before merging", with "Require review from Code Owners".
- GitHub can't reset approvals per path, so the team chooses. Either turn on
  "Dismiss stale pull request approvals when new commits are pushed": a spec edit resets the
  approval, but so does every code push. Or leave it off and have reviewers check spec diffs.

Finish by suggesting `/sdlc:start` to write the first spec, and remind the user that nothing has
been committed.
