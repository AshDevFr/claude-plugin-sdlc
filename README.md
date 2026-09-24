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

Then, in a product repository, run `/sdlc:init`.

Requirements: Python 3.10+ and PyYAML on the machine running Claude Code.

## Layout

| Path | What |
|---|---|
| `.claude-plugin/` | Plugin manifest and marketplace |
| `tools/specs/` | The helper: parsing, lint, hashing, `new`, `intent`, `coverage`, `status` (see its README) |
| `docs/workflow.md` | The workflow, as guidance and best practices |

## Development

```sh
make venv   # .venv with PyYAML and ruff
make test   # the helper's tests and the plugin's tests
make lint
```
