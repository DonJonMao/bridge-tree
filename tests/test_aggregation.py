import json

from bridgetree.aggregation import aggregate_runs


def _write_run(root, label, seed, values):
    run = root / f"{label}_{seed}"
    run.mkdir()
    (run / "run_manifest.json").write_text(
        json.dumps({"run_label": f"{label}_seed{seed}", "seed": seed}),
        encoding="utf-8",
    )
    (run / "summary.json").write_text(
        json.dumps({"cost": {"mean": {"ann_calls_core": 2.0}}}),
        encoding="utf-8",
    )
    (run / "predictions.jsonl").write_text(
        "".join(
            json.dumps({"question_id": f"q{index}", "outcome": {"answer_accuracy": value}}) + "\n"
            for index, value in enumerate(values)
        ),
        encoding="utf-8",
    )


def test_multi_seed_aggregation_reports_paired_query_bootstrap(tmp_path):
    for seed in (41, 42, 43):
        _write_run(tmp_path, "core", seed, [0.0, 1.0])
        _write_run(tmp_path, "path", seed, [1.0, 1.0])
    result = aggregate_runs(tmp_path, reference_label="core", bootstrap_resamples=100)
    assert result["outcome_metric"] == "answer_accuracy"
    assert result["labels"]["path"]["seed_requirement_met"]
    paired = result["labels"]["path"]["paired_vs_reference"]
    assert paired["mean_difference"] == 0.5
    assert (tmp_path / "aggregate_summary.json").is_file()
