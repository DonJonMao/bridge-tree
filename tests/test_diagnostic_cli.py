"""Executable entry points retain no-network defaults and PR4 opt-in wiring."""
from __future__ import annotations

import json

import pytest

from bridgetree import clients, diagnostic_runner as runner
from bridgetree.cli import main
from test_diagnostic_runner import _fixture


def test_cli_plan_analyze_dryrun_roots_and_report_are_offline(tmp_path, monkeypatch, capsys):
    def forbidden(*args, **kwargs):
        pytest.fail("CLI preflight attempted a network request")
    monkeypatch.setattr(clients.urllib.request, "build_opener", forbidden)
    monkeypatch.setattr(runner, "source_identity", lambda: "cli-fixture-revision")
    fixture = _fixture(tmp_path)
    assert main(["diagnostic-plan", "--config", str(fixture.config), "--output-dir", str(fixture.run)]) == 0
    plan = json.loads(capsys.readouterr().out)
    assert plan["network_calls"] == 0
    for phase in ("score", "generate", "roots"):
        assert main(["diagnostic-" + phase, "--run-dir", str(fixture.run), "--config", str(fixture.config)]) == 0
        result = json.loads(capsys.readouterr().out)
        assert result["execute"] is False and result["network_calls"] == 0
    assert main(["diagnostic-analyze", "--run-dir", str(fixture.run)]) == 0
    assert json.loads(capsys.readouterr().out)["network_calls"] == 0
    assert main(["diagnostic-report", "--run-dir", str(fixture.run)]) == 0
    result = json.loads(capsys.readouterr().out)
    assert result["physical_attempt_reservations"] == 0
    assert result["sections"]["generation_summary"] is None
    assert not (fixture.run / "requests.jsonl").exists()


@pytest.mark.parametrize("command", ["plan", "analyze", "score", "generate", "roots", "evaluate", "report"])
def test_diagnostic_help_entries_are_executable(command, capsys):
    with pytest.raises(SystemExit) as exc:
        main(["diagnostic-" + command, "--help"])
    assert exc.value.code == 0
    assert "diagnostic-" + command in capsys.readouterr().out
