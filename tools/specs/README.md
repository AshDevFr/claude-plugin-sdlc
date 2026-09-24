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
tools/specs/specs lint [paths...] [--changed-since REF] [--ready] [--base REF]
```

Checks spec directories against the rules below. With no paths, every directory under the specs
directory. Findings print as `path:line: RULE message` on stdout; exit 1 if there are any.

| Option | Effect |
|---|---|
| `--changed-since REF` | Only spec directories with a file changed since `REF` (committed, uncommitted or untracked) |
| `--ready` | Also apply the rules for a spec that is out of draft (`L008`) |
| `--base REF` | Compare each spec with its version at `REF` (`L007`, `L011`); a spec absent at `REF` is skipped |

| Rule | Checks |
|---|---|
| `L001` | `spec.md` exists and its frontmatter parses |
| `L002` | Required frontmatter fields and types; no unknown fields; no `approved`, `approvers`, `pr` or `status` |
| `L003` | `id` equals the directory name; a ticket spec's directory starts with the `ticket.ref` prefix, an intent spec's id is `YYYY-MM-DD-<slug>` with a real date |
| `L004` | Ticket specs: `ticket.system` matches the configured tracker |
| `L005` | All template sections present, in any order |
| `L006` | `AC-n` numbers unique; at least one criterion not struck |
| `L007` | With `--base`: no criterion removed (strike it through instead) |
| `L008` | With `--ready`: no open questions |
| `L009` | Every `attachments` entry exists inside the spec directory |
| `L010` | Ticket specs: `ticket.snapshot.md` exists, is unedited, and matches `ticket.snapshot.content_sha256` |
| `L011` | With `--base`: a changed body bumps `revision` and adds a matching `## Revisions` entry |
| `L012` | `state: superseded` requires `superseded_by` |
| `L013` | A line that looks like an acceptance criterion but isn't one (wrong form, wrong section, in a code block) |
| `L014` | The spec names its intent: an `intent` block, a `ticket`, or both |
| `L015` | The file named by `intent.file` exists in the spec directory |
| `L016` | The intent file hasn't changed since the spec recorded its hash (otherwise: `/sdlc:sync`) |

JSON output:

```json
{"ok": false, "findings": [{"rule": "L006", "path": "specs/123-x/spec.md", "line": 14, "message": "..."}]}
```

`line` is `null` when a finding has no line (a missing `spec.md`).

### `new`

```sh
tools/specs/specs new --title <title> [--slug <slug>] [--date YYYY-MM-DD] [--intent-file <path>] [--supersedes <id>]
tools/specs/specs new --key <ticket> --title <title> [--slug <slug>] [--supersedes <id>]
```

Creates a spec directory. Exits 1 without writing anything when the directory already exists.

- **Intent spec** (the default): `<specs_dir>/<date>-<slug>/` with `spec.md` and `intent.md`.
  The date is today in UTC unless `--date` is given; the slug comes from the title unless
  `--slug` is given. `intent.md` is the intent template filled with the title, or a byte copy
  of `--intent-file`. The spec's frontmatter records the intent file's hash:

  ```yaml
  intent:
    file: intent.md
    content_sha256: 4f1c...          # sha256 of the normalised intent file
    recorded_at: 2026-09-23T11:02:00Z
    recorded_by: jdoe
  ```

- **Ticket spec** (`--key`): named after the ticket; `lint` reports only `L010` until a ticket
  snapshot is taken.

Templates come from `<specs_dir>/templates/spec.md` and `intent.md` when a team has them,
else from the helper's own. The spec template is the body only; `new` writes the frontmatter
itself. Placeholders: `$title`, `$intent`, `$date`, `$author`.

With `--supersedes <id>`, the new spec lists `<id>` under `supersedes`, and the old spec gets
`state: superseded` and `superseded_by: <new id>`, edited in place so the rest of the file is
unchanged.

JSON output: `{"ok": true, "path": "specs/2026-09-23-webhook-retries", "id": "2026-09-23-webhook-retries"}`.

### `intent`

```sh
tools/specs/specs intent check [<spec-dir>] [--diff]
tools/specs/specs intent record [<spec-dir>]
tools/specs/specs intent assess [<spec-dir> | --file <path>]
```

Without `<spec-dir>`, each uses the current branch's spec (see `status`).

`check` compares the intent file with the hash the spec recorded: `unchanged` (exit 0),
`changed` or `not recorded` (exit 1). With `--diff` it prints the change since the recorded
version, found as the newest committed version of the file with that hash; uncommitted edits
are included. If no committed version matches, it says so instead of guessing a base.

`record` stores the intent file's current hash in the spec's `intent` block (with who and
when), rewriting only that block, and adds the block after `title` if the spec has none. It is
what `/sdlc:sync` runs once the spec has been reviewed against the change.

`assess` reports each intent template section as `missing`, `empty`, `template` (still the
template's guidance) or `ok`, plus the title and Author line, and lists the open questions
(list items, or one per paragraph when there are none). The sections come from the team's
`specs/templates/intent.md` when it has one. It always exits 0: gaps are for the plugin to
offer help with, never a failure.

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

One line for the current branch's spec: `<id> r<revision>: <n> lint finding(s), intent <state>`
(`n/a` for a ticket spec), or `no spec for this branch`, or `no branch` on a detached HEAD.
The spec is the one whose id appears in the branch name (the longest when several do), else
the spec of the ticket the branch names. Always exits 0; fast enough for a status line.

## Development

From the repository root:

```sh
make venv   # .venv with PyYAML and ruff
make test   # unittest suite; any test that opens a network socket fails
make lint   # ruff check and format check
make fmt    # ruff format and autofix
```
