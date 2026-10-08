# tools/specs

The `sdlc` plugin's internal helper. Plugin commands call it for the parts of the spec-driven
workflow that must be exact rather than judged: parsing specs, numbering acceptance criteria,
hashing, and the lint rules. It ships inside the plugin and runs against the product repo in
the current directory; nothing is copied into the product repo.

```sh
${CLAUDE_PLUGIN_ROOT}/tools/specs/specs <command> [options]
```

**Its findings are advice.** The plugin shows them to the engineer, typically as a local lint
before committing; nothing here gates a merge. A team that wants checks in its own CI can run
the same command from a checkout of the plugin; that is the team's choice, not part of the
plugin.

It never makes network calls. Requirements: Python 3.10+ and PyYAML
(`tools/specs/requirements.txt`).

## Configuration

Read from `specs/config.yml`, or `.specs/config.yml` if there is no `specs/`, at the root of the
git repository. Unknown keys, and keys that don't apply to the selected system, are errors.

```yaml
tracker:
  system: github            # gitlab | github | linear
  project: billing/api      # gitlab/github: when tickets live in another project
  team_key: ENG             # linear: required
  spec_label: spec-required # default
code_host:
  system: github            # gitlab | github
  spec_approvers: "@acme/spec-approvers"   # optional: a group, or a list of usernames
specs_dir: specs            # defaults to, and must equal, the directory holding this file
coverage:
  test_globs: ["**/test*/**", "**/*_test.*", "**/*.test.*", "**/*.spec.*"]   # default
```

## Global options

| Option | Effect |
|---|---|
| `--json` | Print exactly one JSON document on stdout; all human-readable text goes to stderr. Accepted before or after the command name. |
| `--verbose` | Show a traceback when the tool fails unexpectedly. |
| `--version` | Print the tool version (the `VERSION` file) and exit. |

## Exit codes

Stable: the plugin's commands branch on them.

| Code | Meaning |
|---|---|
| 0 | Nothing to report, or the command succeeded |
| 1 | There are findings (advice to show the engineer), not an error in the tool |
| 2 | Usage or configuration error, or an unexpected internal error |

Code 3 is reserved and not produced.

## JSON output

On success, the command's own fields next to `ok`:

```json
{"ok": true, "...": "..."}
```

A command that ran and found problems exits 1 and reports `"ok": false` with its own fields
(for example a list of findings).

On any error:

```json
{"ok": false, "error": {"code": 2, "message": "..."}}
```

## Commands

### `check`

```sh
tools/specs/specs check [<spec-dir>...] [--all] [--ready]
```

The local check before committing: per spec, lint findings, criteria no test cites yet, and the
intent state (`unchanged`, `changed`, `not recorded`, `n/a` for a ticket spec). Without a
directory, the current branch's spec. Exits 1 when there is anything to report.

Each spec's report also carries its intent's `status` (see `deps`), the specs in its
`depends_on` that aren't `done` (`blocked_by`, each with its status), and `ready_to_implement`.
Unmet dependencies are information: they never change the exit code or readiness.

With `--ready`, it also says whether each spec is ready for review, with reasons: open
questions, template text left in a section, other lint findings, the intent changed or not
recorded. Uncited criteria and unmet dependencies don't count against readiness: spec review
comes before code, and a spec can be reviewed whatever its dependencies' state. It exits 0 only when every spec is ready.

### `init`

```sh
tools/specs/specs init --tracker <gitlab|github|linear> --host <gitlab|github> [--project P] [--team-key K] [--approvers A] [--specs-dir specs|.specs] [--dry-run]
tools/specs/specs init --upgrade [--dry-run]
```

The file writes behind `/sdlc:init`; the only command that runs without a config. It writes
`<specs_dir>/config.yml`, a `.gitignore` entry and a `CLAUDE.md` section (between marker
comments), and copies the spec and intent templates to `<specs_dir>/templates/`. Each item is
reported as `written`, `appended`, `present`, `updated` or `customised`; a second run changes
nothing. An existing config with other settings stops the run (exit 1) before anything is
written.

`--upgrade` refreshes the `CLAUDE.md` section and replaces a repo template only when it is a
version the plugin shipped unchanged (`sdlc_specs/templates/HISTORY`); an edited template is
reported `customised`, with its diff, and left alone. It never writes `CODEOWNERS`.

### `lint`

```sh
tools/specs/specs lint [paths...] [--changed-since REF] [--ready] [--base REF] [--only RULE[,RULE]]
```

Checks spec directories against the rules below. With no paths, every directory under the specs
directory. Findings print as `path:line: RULE message` on stdout; exit 1 if there are any.

| Option | Effect |
|---|---|
| `--changed-since REF` | Only spec directories with a file changed since `REF` (committed, uncommitted or untracked) |
| `--ready` | Also apply the rules for a spec that is out of draft (`L008`) |
| `--base REF` | Compare each spec with its version at `REF` (`L007`, `L011`); a spec absent at `REF` is skipped |
| `--only RULE[,RULE]` | Report only these rules (the revision reminder hook uses `--only L011`); an unknown rule exits 2 |

| Rule | Checks |
|---|---|
| `L001` | `spec.md` exists and its frontmatter parses |
| `L002` | Required frontmatter fields and types (`depends_on` a list of strings, `intent.content_sha256` bare hex or `sha256v2:` hex); no unknown fields; no `approved`, `approvers`, `pr` or `status` |
| `L003` | `id` equals the directory name; a spec with an intent file has a `YYYY-MM-DD-<slug>` id with a real date, even with a ticket linked; a ticket-only spec's directory starts with the `ticket.ref` prefix, and a ref whose project can't be resolved (no `tracker.project`, no `origin`) is reported here |
| `L004` | Ticket specs: `ticket.system` matches the configured tracker |
| `L005` | All template sections present, in any order |
| `L006` | `AC-n` numbers unique; at least one criterion not struck |
| `L007` | With `--base`: no criterion removed (strike it through instead) |
| `L008` | With `--ready`: no open questions |
| `L009` | Every `attachments` entry exists inside the spec directory |
| `L010` | Ticket-only specs: `ticket.snapshot.md` exists, is unedited, and matches `ticket.snapshot.content_sha256` |
| `L011` | With `--base`: a changed body bumps `revision` and adds a matching `## Revisions` entry |
| `L012` | `state: superseded` requires `superseded_by` |
| `L013` | A line that looks like an acceptance criterion but isn't one (wrong form, wrong section, in a code block) |
| `L014` | The spec names its intent: an `intent` block, a `ticket`, or both |
| `L015` | The file named by `intent.file` exists in the spec directory |
| `L016` | The intent file hasn't changed since the spec recorded its hash (otherwise: `/sdlc:sync`) |
| `L017` | With `--ready`: no section still holds the template's guidance text (the team's template when it has one) |
| `L018` | Every `depends_on` entry names a spec directory in this repository (one holding only an intent counts) |
| `L019` | A spec doesn't list itself in `depends_on` |
| `L020` | No `depends_on` cycle across the repository's specs; reported on every spec on the cycle |

JSON output:

```json
{"ok": false, "findings": [{"rule": "L006", "path": "specs/123-x/spec.md", "line": 14, "message": "..."}]}
```

`line` is `null` when a finding has no line (a missing `spec.md`).

### `new`

```sh
tools/specs/specs new --title <title> [--slug <slug>] [--date YYYY-MM-DD] [--intent-file <path>] [--supersedes <id>] [--depends-on <id>[,<id>]]
tools/specs/specs new --key <ticket> --title <title> [--slug <slug>] [--supersedes <id>] [--depends-on <id>[,<id>]]
```

Creates a spec directory. Exits 1 without writing anything when the directory already exists.

- **Intent spec** (the default): `<specs_dir>/<date>-<slug>/` with `spec.md` and `intent.md`.
  The date is today (local date) unless `--date` is given; the slug comes from the title unless
  `--slug` is given. `intent.md` is the intent template filled with the title, or a byte copy
  of `--intent-file`. The spec's frontmatter records the intent file's hash:

  ```yaml
  intent:
    file: intent.md
    content_sha256: sha256v2:4f1c... # sha256 of the normalised intent, frontmatter left out
    recorded_at: 2026-09-23T11:02:00Z
    recorded_by: jdoe
  ```

  **The intent hash.** v2, written by `new` and `intent record`, is `sha256v2:` and the sha256 of
  the normalised intent without its leading frontmatter block, so changing the intent's
  `status` doesn't read as a change. v1, a bare hex sha256 of the whole normalised file, is what
  specs recorded before; it is never written now, but a v1 record is still compared with v1,
  so committed specs keep working. Since those records were taken before intents had a
  frontmatter, a v1 record also matches the intent with its frontmatter left out: adding one,
  or changing the status in it, isn't a change. Both algorithms are frozen (`sdlc_specs/snapshot.py`).

- **Ticket spec** (`--key`): named after the ticket; `lint` reports only `L010` until a ticket
  snapshot is taken.

Templates come from `<specs_dir>/templates/spec.md` and `intent.md` when a team has them,
else from the helper's own. The spec template is the body only; `new` writes the frontmatter
itself. Placeholders: `$title`, `$intent`, `$date`, `$author`.

With `--depends-on <id>[,<id>]`, the new spec lists those ids under `depends_on`. Each must be
an existing spec directory other than the new spec's own; otherwise it exits 1 and writes
nothing.

With `--supersedes <id>`, the new spec lists `<id>` under `supersedes`, and the old spec gets
`state: superseded` and `superseded_by: <new id>`, edited in place so the rest of the file is
unchanged.

JSON output: `{"ok": true, "path": "specs/2026-09-23-webhook-retries", "id": "2026-09-23-webhook-retries"}`.

### `intent`

```sh
tools/specs/specs intent check [<spec-dir>] [--diff]
tools/specs/specs intent record [<spec-dir>]
tools/specs/specs intent assess [<spec-dir> | --file <path>]
tools/specs/specs intent new --title <title> [--slug <slug>] [--date YYYY-MM-DD]
```

Without `<spec-dir>`, each uses the current branch's spec (see `status`).

`check` compares the intent file with the hash the spec recorded: `unchanged` (exit 0),
`changed` or `not recorded` (exit 1). With `--diff` it prints the change since the recorded
version, found as the newest committed version of the file with that hash; uncommitted edits
are included. If no committed version matches, it says so instead of guessing a base.

`record` stores the intent file's current hash in the spec's `intent` block (with who and
when), rewriting only that block, and adds the block after `title` if the spec has none. It is
what `/sdlc:sync` runs once the spec has been reviewed against the change.

`assess` reports the intent's `status` from its frontmatter (`invalid`, with the reason, for a
value other than `draft`, `ready-for-spec`, `ready-for-code`, `done`, `dropped`; `draft` when
there is none), each intent template section as `missing`, `empty`, `template` (still the
template's guidance) or `ok`, plus the title and Author line, and lists the open questions
(list items, or one per paragraph when there are none). The frontmatter is never read as
sections. The sections come from the team's
`specs/templates/intent.md` when it has one. It always exits 0: gaps are for the plugin to
offer help with, never a failure.

`new` starts an intent before its spec, the file `/sdlc:intent` then fills in. Its id is
`YYYY-MM-DD-<slug>` (local date, as `new`). With an `intents/` directory at the repository root it
writes `intents/<id>.md`; otherwise a spec directory holding only the intent,
`<specs_dir>/<id>/intent.md`. Both start from the intent template in use, which marks the intent
`status: draft`; an id already taken exits 1.

**Intent status.** An intent file's frontmatter may hold `status`: `draft`, `ready-for-spec`,
`ready-for-code`, `done` or `dropped`. A person sets it; the helper only reads it, and the
templates start it at `draft`. No frontmatter or no `status` means `draft`.

**Intent only.** A spec directory with `intent.md` and no `spec.md` is an intent waiting for its
spec: `lint` has nothing to report for it, `check --all` and `coverage` skip it, and `status` on
its branch says `<id>: intent only, no spec yet`. `new` with the same id writes `spec.md`
beside it and records the existing intent's hash.

### `coverage`

```sh
tools/specs/specs coverage [<spec-dir>...]
```

Reports, per spec, which non-struck acceptance criteria are cited by a test file, as
`<spec-id>:AC-<n>` anywhere in a line, and where. Test files are those git would show (tracked,
or untracked and not ignored) matching `coverage.test_globs`; `**/` spans directories, `*`
stays within one. Citations of a struck or nonexistent criterion are listed separately. Exits
1 when a criterion is uncited: advice that a test may be missing, not proof either way.

### `status`

```sh
tools/specs/specs status
```

One line for the current branch's spec:
`<id> r<revision>: <n> lint finding(s), intent <state>, status <status>[, blocked by <id>, ...]`
(intent `n/a` and no status for a ticket spec), `<id>: intent only, no spec yet, status
<status>`, or `no spec for this branch`, or `no branch` on a detached HEAD.
The spec is the one whose id appears in the branch name (the longest when several do), else
the spec of the ticket the branch names. Always exits 0; fast enough for a status line.
`, handoff waiting` is appended when `/sdlc:handoff` left a `handoff.local.md` in the spec's
directory (in `<specs_dir>/` for a branch without a spec).

### `deps`

```sh
tools/specs/specs deps
```

Every spec directory, each after the specs in its `depends_on`, with its intent's status and a
verdict: `done` or `dropped` (its own status), else `blocked` (a dependency isn't `done`, named
with its status) or `ready` (every dependency is `done`). The spec's own status never decides
`ready`. A ticket spec's status is `unknown (tracker)`: as a dependency it never counts as done. Specs on a cycle (lint `L020`) are listed last and named. Read-only; always exits
0.

JSON output: `{"ok": true, "specs": [{"spec", "status", "verdict", "depends_on": [...],
"blocked_by": [{"spec", "status"}]}], "cycles": [...]}`.

### `trailers`

```sh
tools/specs/specs trailers [<spec-dir>] [--implements AC-1,AC-3] [--spec-change <kind>] [--from-log <base>]
```

The git trailers that tie a commit or PR to a spec, one per line, ready to append to a message:
`Spec: <id>@r<revision>`, then `Implements:` and `Spec-Change:` when they apply. Without a
directory, the current branch's spec. Exits 1 naming a criterion that doesn't exist or is
struck, or a kind other than `initial`, `clarify`, `amend`, `acknowledge`, `supersede`.

`--from-log <base>` adds the criteria in the `Implements:` trailers of the `<base>..HEAD`
commits whose `Spec:` names this spec, oldest first, each once: the PR's "criteria implemented".
A criterion struck since the commit is left out with a warning, since the trailers speak for the
current revision.

## Development

From the repository root:

```sh
make venv   # .venv with PyYAML and ruff
make test   # unittest suite; any test that opens a network socket fails
make lint   # ruff check and format check
make fmt    # ruff format and autofix
```
