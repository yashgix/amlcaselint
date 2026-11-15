PYTHON ?= python

.PHONY: lint test experiment

lint:
	ruff check .
	ruff format --check .

test:
	$(PYTHON) -m unittest discover -s tests
	$(PYTHON) -m unittest discover -s tests/acceptance

experiment:
	$(PYTHON) experiment.py --out results/metrics.json
	$(PYTHON) demo.py --readme README.md --out README.md
