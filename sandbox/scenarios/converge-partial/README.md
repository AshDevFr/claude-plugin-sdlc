# Scenario: converge-partial

On branch `2026-09-23-webhook-retries`, a filled spec with three criteria and code that meets
them unevenly. Use it to try `/sdlc:converge`.

- AC-1 (503 retried, at most 5 attempts): implemented, and `tests/test_deliver.py` cites it.
- AC-2 (a final failure recorded with its event id **and last status code**): partly
  implemented; `FAILED` gets the event id only, and no test cites it.
- AC-3 (400 not retried): implemented, no test cites it.
- `logging_setup.py`: a change no criterion or Design element asks for.

- `specs lint`: nothing to report (exit 0).
- `specs intent check`: intent `unchanged`.
- `specs coverage`: AC-2 and AC-3 uncited.
