# tools/specs

The checks behind the spec-driven workflow in `docs/workflow.md`. The pipeline, the nightly
job and the Claude plugin all run this tool, so every rule has exactly one implementation.

It is vendored into each product repo and run in place:

```sh
tools/specs/specs <command> [options]
```

Requirements: Python 3.10+ and PyYAML (`tools/specs/requirements.txt`). Nothing else is installed.

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

## Development

From the repository root:

```sh
make venv   # .venv with PyYAML and ruff
make test   # unittest suite; any test that opens a network socket fails
make lint   # ruff check and format check
make fmt    # ruff format and autofix
```
