PYTHON ?= python

.PHONY: lint test experiment page

lint:
	ruff check .
	ruff format --check .

test:
	$(PYTHON) -m unittest discover -s tests
	$(PYTHON) -m unittest discover -s tests/acceptance

experiment:
	$(PYTHON) experiment.py --out results/metrics.json
	$(PYTHON) -m amlcaselint failures --out results/failures.json
	$(PYTHON) -m amlcaselint gold-v2 --out results/gold-v2.json
	$(PYTHON) demo.py --readme README.md --out README.md
	$(PYTHON) demo.py --failures results/failures.json --failures-out docs/FAILURES.md
	$(PYTHON) tools/render_page.py

page:
	$(PYTHON) tools/render_page.py
