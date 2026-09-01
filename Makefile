.PHONY: install test lint data smoke

install:
	python3 -m pip install -e '.[test]'

test:
	pytest

lint:
	ruff check src tests

data:
	bridgetree download-personamem --split 32k
	bridgetree prepare-personamem --split 32k

smoke:
	bridgetree run --method bridgetree --limit 1

