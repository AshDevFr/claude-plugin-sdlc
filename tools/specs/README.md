# tools/specs

The checks behind the spec-driven workflow in `docs/workflow.md`. The pipeline, the nightly
job and the Claude plugin all run this tool, so every rule has exactly one implementation.

It is vendored into each product repo and run in place:

```sh
tools/specs/specs <command> [options]
```

Requirements: Python 3.10+ and PyYAML (`tools/specs/requirements.txt`). Nothing else is installed.

## Configuration

Read from `specs/config.yml`, or `.specs/config.yml` if there is no `specs/`, at the root of the
git repository. Unknown keys, and keys that don't apply to the selected system, are errors.

```yaml
tracker:
  system: github            # gitlab | github | linear | fake
  project: billing/api      # gitlab/github: when tickets live in another project
  base_url: https://...     # gitlab/github: self-hosted instance
  team_key: ENG             # linear: required
  fake_of: linear           # fake: required, the system the fake behaves as
  spec_label: spec-required # default
code_host:
  system: github            # gitlab | github | fake
  base_url: https://...     # gitlab/github: self-hosted instance
  spec_approvers: "@acme/spec-approvers"   # a group, or a list of usernames
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

Stable: scripts may branch on them.

| Code | Meaning |
|---|---|
| 0 | The check passed, or the command succeeded |
| 1 | The check failed: a finding, not an error in the tool |
| 2 | Usage or configuration error, or an unexpected internal error |
| 3 | Platform error: network, authentication or rate limit on the tracker or code host |

A platform error never reads as a pass or as a finding; it has its own code.

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
| `L003` | `id` equals the directory name; the directory name starts with the `ticket.ref` prefix |
| `L004` | `ticket.system` matches the configured tracker (for a fake tracker, the system it mimics) |
| `L005` | All template sections present, in any order |
| `L006` | `AC-n` numbers unique; at least one criterion not struck |
| `L007` | With `--base`: no criterion removed (strike it through instead) |
| `L008` | With `--ready`: no open questions |
| `L009` | Every `attachments` entry exists inside the spec directory |
| `L010` | `ticket.snapshot.md` exists, is unedited, and matches `ticket.snapshot.content_sha256` |
| `L011` | With `--base`: a changed body bumps `revision` and adds a matching `## Revisions` entry |
| `L012` | `state: superseded` requires `superseded_by` |
| `L013` | A line that looks like an acceptance criterion but isn't one (wrong form, wrong section, in a code block) |

JSON output:

```json
{"ok": false, "findings": [{"rule": "L006", "path": "specs/123-x/spec.md", "line": 14, "message": "..."}]}
```

`line` is `null` when a finding has no line (a missing `spec.md`).

### `new`

```sh
tools/specs/specs new --key <ticket> --title <title> [--slug <slug>] [--supersedes <id>]
```

Creates `<specs_dir>/<ticket-prefix>-<slug>/spec.md` from the template, with `revision: 1`,
`state: active` and a placeholder `AC-1`. The ticket snapshot is not taken yet, so `lint` reports
only `L010` until it is. Exits 1 without writing anything when the ticket already has a spec
directory.

With `--supersedes <id>`, the new spec lists `<id>` under `supersedes`, and the old spec gets
`state: superseded` and `superseded_by: <new id>`, edited in place so the rest of the file is
unchanged. A missing or already superseded spec exits 1 without writing anything.

JSON output: `{"ok": true, "path": "specs/eng-123-webhook-retries", "id": "eng-123-webhook-retries"}`.

## Development

From the repository root:

```sh
make venv   # .venv with PyYAML and ruff
make test   # unittest suite; any test that opens a network socket fails
make lint   # ruff check and format check
make fmt    # ruff format and autofix
```
