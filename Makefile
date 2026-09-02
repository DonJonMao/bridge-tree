.PHONY: install test lint data run ablation tune smoke

install:
	python3 -m pip install -e '.[test]'

test:
	pytest

lint:
	ruff check src tests

data:
	bridgetree download-personamem --split 32k
	bridgetree prepare-personamem --split 32k

run:
	./scripts/run_personamem.sh

ablation:
	./scripts/ablation.sh

tune:
	./scripts/train.sh

smoke:
	bridgetree run --method bridgetree --limit 1
