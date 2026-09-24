PYTHON ?= .venv/bin/python
# Two suites, two runs: both directories are packages named `tests`.
HELPER_TESTS := -m unittest discover -s tools/specs/tests -t tools/specs
PLUGIN_TESTS := -m unittest discover -s tests -t .

.PHONY: venv test lint fmt

venv:
	python3 -m venv .venv
	.venv/bin/pip install -r requirements-dev.txt

test:
	$(PYTHON) $(HELPER_TESTS)
	$(PYTHON) $(PLUGIN_TESTS)

lint:
	$(PYTHON) -m ruff check .
	$(PYTHON) -m ruff format --check .

fmt:
	$(PYTHON) -m ruff format .
	$(PYTHON) -m ruff check --fix .
