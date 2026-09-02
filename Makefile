.PHONY: install test lint data run main-table ablation tune smoke

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

main-table:
	./scripts/main_table.sh

tune:
	./scripts/train.sh

smoke:
	./scripts/smoke_synthetic.sh
