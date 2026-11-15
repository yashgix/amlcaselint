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
	$(PYTHON) -m examcheck failures --out results/failures.json
	$(PYTHON) -m examcheck gold-v2 --out results/gold-v2.json
	$(PYTHON) demo.py --readme README.md --out README.md
	$(PYTHON) demo.py --failures results/failures.json --failures-out docs/FAILURES.md
