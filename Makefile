PYTHON ?= .venv/bin/python
TESTS := -m unittest discover -s tools/specs/tests -t tools/specs

.PHONY: venv test lint fmt

venv:
	python3 -m venv .venv
	.venv/bin/pip install -r requirements-dev.txt

test:
	$(PYTHON) $(TESTS)

lint:
	$(PYTHON) -m ruff check .
	$(PYTHON) -m ruff format --check .

fmt:
	$(PYTHON) -m ruff format .
	$(PYTHON) -m ruff check --fix .
