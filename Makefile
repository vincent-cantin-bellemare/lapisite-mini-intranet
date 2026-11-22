PYTHON ?= python3

.PHONY: test lint
test:
	$(PYTHON) -m unittest discover -s tests -v

lint:
	$(PYTHON) -m py_compile mini_intranet/*.py tests/*.py
