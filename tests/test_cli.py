import os
import subprocess
import sys
from pathlib import Path

from bridgetree.cli import _resolved_config, _resolved_tuning_config, build_parser, main


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


def test_chain_plan_freezes_all_methods_for_each_query(tmp_path):
    queries = tmp_path / "queries.jsonl"
    queries.write_text(
        '{"persona_id":"p1","question_id":"q1","split":"seen"}\n'
        '{"persona_id":"p2","question_id":"q2","split":"confirmation"}\n',
        encoding="utf-8",
    )
    output = tmp_path / "planned.jsonl"
    assert main(["chain-plan", "--queries", str(queries), "--output", str(output)]) == 0
    assert len(output.read_text(encoding="utf-8").splitlines()) == 18


def test_tune_has_a_legacy_train_alias():
    parser = build_parser()
    assert parser.parse_args(["tune"]).command == "tune"
    assert parser.parse_args(["train"]).command == "train"


def test_tune_can_require_the_formal_completion_audit():
    args = build_parser().parse_args(["tune", "--audit-full-32k", "--max-parse-failure-rate", "0.01"])
    assert args.audit_full_32k is True
    assert args.max_parse_failure_rate == 0.01


def test_completed_tuning_run_has_an_independent_audit_command():
    args = build_parser().parse_args(
        ["audit-tuning-run", "--run-dir", "outputs/example", "--require-full-32k"]
    )
    assert args.command == "audit-tuning-run"
    assert args.run_dir == "outputs/example"
    assert args.require_full_32k is True


def test_preflight_tuning_exposes_full_32k_and_service_gates():
    args = build_parser().parse_args(
        ["preflight-tuning", "--require-full-32k", "--check-services"]
    )
    assert args.command == "preflight-tuning"
    assert args.require_full_32k is True
    assert args.check_services is True


def test_configured_data_command_can_disable_downloads():
    args = build_parser().parse_args(["prepare-configured-data", "--no-download-missing"])
    assert args.command == "prepare-configured-data"
    assert args.download_missing is False


def test_package_server_enables_extracted_launcher_verification_by_default():
    args = build_parser().parse_args(["package-server", "--output-dir", "bundle-output"])
    assert args.command == "package-server"
    assert args.output_dir == "bundle-output"
    assert args.verify_offline_launcher is True


def test_full_32k_offline_validation_has_a_distinct_command():
    args = build_parser().parse_args(["validate-full-32k-offline"])
    assert args.command == "validate-full-32k-offline"
    assert args.output_dir == "outputs/offline-full-32k-validation"


def test_effect_first_cli_exposes_all_guided_overrides():
    args = build_parser().parse_args(
        [
            "validate-effect-first",
            "--dense-pool-width",
            "24",
            "--anchor-width",
            "10",
            "--expand-branch-count",
            "2",
            "--branch-overfetch-width",
            "6",
            "--branch-keep-width",
            "3",
            "--probe-mode",
            "centroid",
            "--no-path-filter",
            "--no-rerank-use-options",
            "--no-rerank-include-time",
        ]
    )
    config = _resolved_config(args)

    assert args.command == "validate-effect-first"
    assert config.bridge_rerank.dense_pool_width == 24
    assert config.bridge_rerank.anchor_width == 10
    assert config.bridge_rerank.branch_keep_width == 3
    assert config.bridge_rerank.probe_mode == "centroid"
    assert not config.bridge_rerank.path_filter
    assert not config.bridge_rerank.use_answer_options
    assert not config.bridge_rerank.include_time_metadata


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


def test_effect_first_script_runs_the_pinned_validation_matrix():
    script = Path("scripts/run_effect_first_validation.sh").read_text(encoding="utf-8")
    for method in (
        "dense_rerank_20",
        "dense_rerank_28",
        "bridgetree_union_rerank",
        "bridgetree_guided_rerank",
        "bridgetree_guided_pathfilter",
        "full_pool_rerank",
    ):
        assert f"--method {method}" in script
    assert "set -euo pipefail" in script
    assert "validate-effect-first" in script


def test_background_launchers_have_fixed_logs_status_and_result_files():
    effect = Path("scripts/start_effect_first_background.sh").read_text(encoding="utf-8")
    training = Path("scripts/start_train_32k_background.sh").read_text(encoding="utf-8")

    assert "scripts/background_entrypoint.py" in effect
    assert '"$manager_script" start' in effect
    assert "effect_first.summary.json" in effect
    assert "effect_first.results.csv" in effect
    assert "effect_first.log" in effect
    assert "scripts/background_entrypoint.py" in training
    assert '"$manager_script" start' in training
    assert "train_32k.summary.json" in training
    assert "train_32k.audit.json" in training
    assert "train_32k.log" in training


def test_full_32k_launcher_is_portable_and_runs_all_preflight_gates():
    script = Path("scripts/train_32k.sh").read_text(encoding="utf-8")
    assert "-m pip install" in script
    assert "-m pytest -q" in script
    assert "-m ruff check" in script
    assert "smoke-synthetic" in script
    assert "prepare-configured-data" in script
    assert "preflight-tuning" in script
    assert "--require-full-32k" in script
    assert "--check-services" in script
    assert "-m bridgetree.cli tune" in script
    assert "--audit-full-32k" in script
    offline_script = Path("scripts/validate_full_32k_offline.sh").read_text(encoding="utf-8")
    assert "validate-full-32k-offline" in offline_script


def test_full_32k_launcher_executes_offline_preflight_without_starting_tuning():
    environment = {
        **os.environ,
        "BRIDGETREE_PYTHON": sys.executable,
        "BOOTSTRAP": "false",
        "RUN_CHECKS": "false",
        "CHECK_SERVICES": "false",
        "PREFLIGHT_ONLY": "true",
    }
    completed = subprocess.run(
        ["bash", "scripts/train_32k.sh"],
        check=True,
        capture_output=True,
        text=True,
        env=environment,
    )

    assert '"status": "ready"' in completed.stdout
    assert "preflight complete" in completed.stdout
    assert "starting full PersonaMem-v1 32K tuning" not in completed.stdout
