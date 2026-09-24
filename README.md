# sdlc

A Claude Code plugin for spec-driven development in a team that shares one repository.

A change starts from an **intent**: the original request, in the words of whoever has the
problem. The plugin helps turn it into a **spec**: the contract the team reviews in the pull
request, builds against, and cites from tests through numbered acceptance criteria (`AC-1`,
`AC-2`, ...). Plans, commits and PR descriptions then point back at the spec, so `git log` can
say which criteria a change implements.

## What it is, and what it isn't

The plugin **advises; it doesn't enforce.** It assesses an intent and offers to fill its gaps,
drafts and checks specs, and writes commit and PR text. It never blocks anything.

- It ships **no CI integration**. A team that wants checks in its own pipeline can run the
  same helper there; that is the team's choice. See `docs/workflow.md`.
- It needs **no credentials** and makes no network calls: it doesn't talk to a tracker or a
  code host.
- Its helper is **never copied into** a product repository. Commands run it from the plugin.

Those limits are deliberate. Enforcement and platform access are where this kind of tool
becomes a burden to install and maintain; the MVP proves the workflow first. Reading tickets
from GitLab, GitHub or Linear through their MCP servers is planned as a later alternative to
`intent.md`.

## Install

```sh
claude plugin marketplace add <path-or-url-of-this-repo>
claude plugin install sdlc@sdlc
```

Then, in a product repository, run `/sdlc:init`. `docs/adoption.md` walks a team through the
first change.

Requirements: Python 3.10+ and PyYAML on the machine running Claude Code.

## Commands

In the order a change usually meets them:

| Command | What it does |
|---|---|
| `/sdlc:init` | Once per repository: config, templates, `.gitignore` entry, `CLAUDE.md` section; prints the code owner and code host settings to apply |
| `/sdlc:start` | Turns a request (an `intent.md`, a file, pasted text) into a spec: assesses the intent, offers help with its gaps, drafts `spec.md` |
| `/sdlc:clarify` | Works a spec's open questions down to decisions, one question at a time |
| `/sdlc:analyze` | Read-only review of a spec against itself and its intent |
| `/sdlc:check` | The local check before committing: lint, criteria no test cites, whether the intent changed; `--ready` for review readiness |
| `/sdlc:propose` | Readiness as advice, then the spec commit message and the text for a spec-only draft PR |
| `/sdlc:plan` | Writes the working plan, `plan.local.md`: test-first steps naming the criteria they serve |
| `/sdlc:implement` | Works through the plan test first, a commit per step; stops when the spec turns out wrong |
| `/sdlc:bug` | Assess, fix and test a bug as separate stages, the diagnosis written before any repair |
| `/sdlc:sync` | Brings a spec back in step when its intent changed or it turned out wrong; supersedes a merged spec |
| `/sdlc:converge` | Read-only verdict per criterion (covered, untested, missing, contradicted) and changes no criterion explains |
| `/sdlc:commit-msg` | A commit message with the `Spec`, `Implements` and `Spec-Change` trailers |
| `/sdlc:pr-msg` | A PR title and description from the spec and the criteria the branch implements |
| `/sdlc:handoff` | Pause and resume a session through a local, git-ignored `handoff.local.md` |

## Skills

Loaded by the commands, or by Claude when the task matches:

| Skill | What it holds |
|---|---|
| `workflow` | The model in brief, which command when, how to call the helper |
| `spec-template` | The spec's frontmatter and sections, with guidance per section; the plan template |
| `intent-writing` | The intent's sections, assessing an intent, offering help without gating |
| `intent-sync` | What to do when a spec and its intent drift apart, case by case |
| `commit-conventions` | The trailers, the `Spec-Change` kinds, squash settings per code host |
| `test-first` | The failing-test-first loop, and how tests cite criteria |
| `receiving-review` | Verifying review findings on a spec or code before acting on them |
| `finishing-work` | What must be true before a PR is marked ready, in terms of `/sdlc:check` and `/sdlc:converge` |

## Hooks

Both advisory and silent outside a repository set up with `/sdlc:init`: a status line for the
branch's spec at session start, and a reminder when Claude edits a pushed spec without bumping
its revision.

## Layout

| Path | What |
|---|---|
| `.claude-plugin/` | Plugin manifest and marketplace |
| `tools/specs/` | The helper: parsing, lint, hashing, `new`, `intent`, `coverage`, `status`, `check`, `trailers` (see its README) |
| `docs/workflow.md` | The workflow, as guidance and best practices |
| `docs/adoption.md` | Adopting the plugin: install, a first change, and how to tell whether it's working |
| `bin/sdlc-sandbox`, `sandbox/` | Disposable repositories in scripted states, for trying the commands |

## Development

```sh
make venv   # .venv with PyYAML and ruff
make test   # the helper's tests and the plugin's tests
make lint
make evals  # every command headless on Opus in throwaway repos: slow and billed (about $8), run before a release
```

`make evals SCENARIOS="plan sync" MODEL=sonnet` runs a subset or another model. Each scenario
builds a sandbox, runs the command with scripted answers and checks the repository afterwards
(files, commits and trailers, `git status`); transcripts of failures land in `evals/results/`.

To try the commands on something disposable, build a sandbox repository in one of the scripted
states described under `sandbox/scenarios/`:

```sh
bin/sdlc-sandbox /tmp/sb --scenario weak-intent   # pushes go to /tmp/sb.origin.git
```
