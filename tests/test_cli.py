import os
import subprocess
from pathlib import Path

from bridgetree.cli import _resolved_config, _resolved_tuning_config, build_parser


def test_explicit_cli_values_override_yaml():
    args = build_parser().parse_args(
        [
            "run",
            "--config",
            "configs/default.yaml",
            "--initial-width",
            "7",
            "--cluster-mode",
            "effective_rank",
        ]
    )
    config = _resolved_config(args)
    assert config.retrieval.initial_width == 7
    assert config.retrieval.cluster_mode == "effective_rank"


def test_tune_has_a_legacy_train_alias():
    parser = build_parser()
    assert parser.parse_args(["tune"]).command == "tune"
    assert parser.parse_args(["train"]).command == "train"


def test_tune_cli_pins_search_space_and_seed_over_tuning_yaml():
    args = build_parser().parse_args(
        ["tune", "--initial-width", "7", "--branch-width", "3", "--search-budget", "20", "--seed", "9"]
    )
    tuning = _resolved_tuning_config(args)
    assert tuning.search_space.initial_width == (7,)
    assert tuning.search_space.branch_width == (3,)
    assert tuning.search_space.search_budget == (20,)
    assert tuning.seed == 9


def test_script_environment_is_forwarded_and_trailing_cli_wins():
    environment = {
        **os.environ,
        "BRIDGETREE_PYTHON": "/bin/echo",
        "FEATURE_MODE": "path_conditioned",
        "SELECTION_MODE": "path_logdet",
    }
    completed = subprocess.run(
        ["bash", "scripts/run_personamem.sh", "--feature-mode", "rho"],
        check=True,
        capture_output=True,
        text=True,
        env=environment,
    )
    arguments = completed.stdout.split()
    feature_positions = [index for index, value in enumerate(arguments) if value == "--feature-mode"]
    assert arguments[feature_positions[0] + 1] == "path_conditioned"
    assert arguments[feature_positions[-1] + 1] == "rho"
    assert feature_positions[-1] > feature_positions[0]


def test_ablation_script_is_a_parameter_matrix_not_python_profiles():
    script = Path("scripts/ablation.sh").read_text(encoding="utf-8")
    for label in (
        "core",
        "path",
        "certificate",
        "full_current",
        "no_cluster",
        "effective_rank",
        "bfs",
        "rho_topk",
        "mmr",
        "depth1",
        "depth2",
        "depth3",
    ):
        assert f'run_config "{label}"' in script
    assert "BridgeTreeMVP" not in script
