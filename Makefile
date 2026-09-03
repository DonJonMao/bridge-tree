.PHONY: install test lint data run main-table ablation effect-first effect-first-background effect-first-status tune tune-32k train-32k-background train-32k-status preflight-32k validate-32k-offline package-server smoke

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

effect-first:
	./scripts/run_effect_first_validation.sh

effect-first-background:
	./scripts/start_effect_first_background.sh

effect-first-status:
	./scripts/start_effect_first_background.sh status

main-table:
	./scripts/main_table.sh

tune:
	./scripts/train.sh

tune-32k:
	./scripts/train_32k.sh

train-32k-background:
	./scripts/start_train_32k_background.sh

train-32k-status:
	./scripts/start_train_32k_background.sh status

preflight-32k:
	PREFLIGHT_ONLY=true ./scripts/train_32k.sh

validate-32k-offline:
	./scripts/validate_full_32k_offline.sh

package-server:
	./scripts/package_server.sh

smoke:
	./scripts/smoke_synthetic.sh
