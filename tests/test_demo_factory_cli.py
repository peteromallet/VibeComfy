"""Freeze the demo_factory invocation surface and exit codes (T-018 / S18).

Pins the contract documented in resolution S18:
- ``python -m vibecomfy.demo_factory`` and ``python -m vibecomfy.demo_factory.cli``
  both dispatch to the Click group ``cli()`` in ``vibecomfy/demo_factory/cli.py``.
- The Click group exposes ``run-case``, ``run-creative``, and ``stats`` commands.
- ``run_campaign.main()`` exits 0 when pass-rate >= 0.5, otherwise 1.
- ``scripts/run_one_additive.py`` exits 0 on success and 2 on usage/out-of-range.
- ``cli()`` exits 1 on missing-arg / no-campaign / failed-export.

Nothing heavy runs: every campaign runner is replaced with a stub, and module
entries are executed in-process the way ``python -m`` does (as ``__main__``)
instead of spawning subprocesses.
"""
from __future__ import annotations

import sys
from pathlib import Path
from types import SimpleNamespace
from typing import Any

import pytest
from click.testing import CliRunner

from vibecomfy.demo_factory import case as case_module
from vibecomfy.demo_factory import cli as cli_module
from vibecomfy.demo_factory import ledger as ledger_module
from vibecomfy.demo_factory import run_campaign
from vibecomfy.demo_factory.cli import cli

_REPO_ROOT = Path(__file__).resolve().parents[1]
_DEMO_FACTORY_DIR = _REPO_ROOT / "vibecomfy" / "demo_factory"
_RUN_ONE_ADDITIVE = _REPO_ROOT / "scripts" / "run_one_additive.py"


def _exec_as_main(path: Path, monkeypatch: pytest.MonkeyPatch, argv: list[str]) -> None:
    """Execute a file the way ``python -m`` does: as a module named ``__main__``."""
    monkeypatch.setattr(sys, "argv", argv)
    source = path.read_text(encoding="utf-8")
    code = compile(source, str(path), "exec")
    exec(code, {"__name__": "__main__", "__file__": str(path)})


# --- Module entry dispatch ---------------------------------------------------


def test_python_m_demo_factory_dispatches_to_cli(monkeypatch: pytest.MonkeyPatch) -> None:
    """``python -m vibecomfy.demo_factory`` runs the Click group from cli.py."""
    called: list[str] = []
    monkeypatch.setattr(cli_module, "cli", lambda: called.append("cli"))
    _exec_as_main(_DEMO_FACTORY_DIR / "__main__.py", monkeypatch, ["demo_factory"])
    assert called == ["cli"]


def test_python_m_demo_factory_cli_dispatches_to_click_group(
    monkeypatch: pytest.MonkeyPatch, capsys: pytest.CaptureFixture[str]
) -> None:
    """``python -m vibecomfy.demo_factory.cli`` invokes the real Click group."""
    with pytest.raises(SystemExit) as exc:
        _exec_as_main(_DEMO_FACTORY_DIR / "cli.py", monkeypatch, ["demo_factory.cli", "--help"])
    assert exc.value.code == 0
    out = capsys.readouterr().out
    assert "demo scenario factory CLI" in out
    assert "run-case" in out


# --- Click group surface -----------------------------------------------------


def test_click_group_exposes_expected_commands() -> None:
    assert set(cli.commands) == {"run-case", "run-creative", "stats"}


# --- run_campaign.main() exit code -------------------------------------------


@pytest.mark.parametrize(
    ("verdict", "expected"),
    [
        ("accepted", 0),
        ("alternative_repair", 0),
        ("rejected", 1),
    ],
)
def test_run_campaign_main_exit_code_tracks_pass_rate(
    verdict: str, expected: int, monkeypatch: pytest.MonkeyPatch, tmp_path: Path
) -> None:
    def fake_repair_case(workflow_id: str, idx: int, output_base: Path) -> dict:
        return {"workflow": workflow_id, "scenario_type": "REPAIR", "verdict": verdict}

    monkeypatch.setattr(run_campaign, "run_repair_case", fake_repair_case)
    monkeypatch.setattr(
        sys,
        "argv",
        [
            "run_campaign",
            "--output", str(tmp_path),
            "--repair-count", "1",
            "--additive-count", "0",
            "--multinode-count", "0",
            "--debug-count", "0",
        ],
    )
    with pytest.raises(SystemExit) as exc:
        run_campaign.main()
    assert exc.value.code == expected


def test_run_campaign_main_without_cases_exits_1(
    monkeypatch: pytest.MonkeyPatch, tmp_path: Path
) -> None:
    args = ["run_campaign", "--output", str(tmp_path)]
    for name in ("repair", "additive", "multinode", "debug"):
        args += [f"--{name}-count", "0"]
    monkeypatch.setattr(sys, "argv", args)
    with pytest.raises(SystemExit) as exc:
        run_campaign.main()
    assert exc.value.code == 1


# --- scripts/run_one_additive.py exit codes ----------------------------------


def test_run_one_additive_usage_error_exits_2(monkeypatch: pytest.MonkeyPatch) -> None:
    with pytest.raises(SystemExit) as exc:
        _exec_as_main(_RUN_ONE_ADDITIVE, monkeypatch, ["run_one_additive.py"])
    assert exc.value.code == 2


def test_run_one_additive_out_of_range_exits_2(
    monkeypatch: pytest.MonkeyPatch, tmp_path: Path
) -> None:
    with pytest.raises(SystemExit) as exc:
        _exec_as_main(
            _RUN_ONE_ADDITIVE, monkeypatch, ["run_one_additive.py", "9999", str(tmp_path)]
        )
    assert exc.value.code == 2


def test_run_one_additive_success_exits_0(
    monkeypatch: pytest.MonkeyPatch, tmp_path: Path
) -> None:
    monkeypatch.setattr(
        run_campaign,
        "run_additive_case",
        lambda workflow_id, feature_type, idx, output_base: {
            "verdict": "accepted",
            "scenario_type": "ADDITIVE",
        },
    )
    with pytest.raises(SystemExit) as exc:
        _exec_as_main(
            _RUN_ONE_ADDITIVE, monkeypatch, ["run_one_additive.py", "0", str(tmp_path)]
        )
    assert exc.value.code == 0
    assert (tmp_path / "results" / "case00.json").exists()


# --- cli() exit-code contract -------------------------------------------------


@pytest.fixture
def campaign_dir(tmp_path: Path) -> Path:
    d = tmp_path / "campaign"
    d.mkdir()
    (d / "campaign.json").write_text("{}", encoding="utf-8")
    return d


def test_cli_run_case_missing_args_exits_1(campaign_dir: Path) -> None:
    result = CliRunner().invoke(cli, ["run-case", "--campaign", str(campaign_dir)])
    assert result.exit_code == 1
    assert "Either --transcript or (--ready + --fault) must be provided" in result.output


def test_cli_run_case_no_campaign_exits_1(tmp_path: Path) -> None:
    result = CliRunner().invoke(cli, ["run-case", "--campaign", str(tmp_path)])
    assert result.exit_code == 1
    assert "No campaign found under" in result.output


def test_cli_run_case_failed_export_exits_1(
    campaign_dir: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    monkeypatch.setattr(cli_module, "_export_ready_ui", lambda ready_id: None)
    result = CliRunner().invoke(
        cli,
        [
            "run-case",
            "--campaign", str(campaign_dir),
            "--ready", "image/basic_image_upscale",
            "--fault", "final-output-bypass",
        ],
    )
    assert result.exit_code == 1
    assert "Failed to export ready template" in result.output


def test_cli_run_creative_missing_args_exits_1(campaign_dir: Path) -> None:
    result = CliRunner().invoke(cli, ["run-creative", "--campaign", str(campaign_dir)])
    assert result.exit_code == 1
    assert "Either --ready or --workflow-list must be provided" in result.output


def _fake_case() -> SimpleNamespace:
    return SimpleNamespace(
        case_id="test-case-1",
        stage=SimpleNamespace(value="baseline"),
        verdict=SimpleNamespace(value="accepted"),
        oracle_result=None,
    )


class _FakeLedger:
    def __init__(self, campaign_root: Path) -> None:
        self.campaign_root = campaign_root

    def register_case(self, case: object) -> None:
        pass

    def get_campaign_stats(self) -> dict[str, Any]:
        return {"total": 1, "by_verdict": {"accepted": 1}, "by_stage": {"baseline": 1}}


def test_cli_run_case_success_exits_0(
    campaign_dir: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    monkeypatch.setattr(cli_module, "_export_ready_ui", lambda ready_id: {"nodes": []})
    monkeypatch.setattr(case_module, "run_synthetic_case", lambda **kwargs: _fake_case())
    monkeypatch.setattr(ledger_module, "CampaignLedger", _FakeLedger)
    result = CliRunner().invoke(
        cli,
        [
            "run-case",
            "--campaign", str(campaign_dir),
            "--ready", "image/basic_image_upscale",
            "--fault", "final-output-bypass",
        ],
    )
    assert result.exit_code == 0
    assert "Using campaign root:" in result.output


def test_cli_run_creative_success_exits_0(
    campaign_dir: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    monkeypatch.setattr(cli_module, "_export_ready_ui", lambda ready_id: {"nodes": []})
    monkeypatch.setattr(case_module, "run_creative_case", lambda **kwargs: _fake_case())
    monkeypatch.setattr(ledger_module, "CampaignLedger", _FakeLedger)
    result = CliRunner().invoke(
        cli,
        ["run-creative", "--campaign", str(campaign_dir), "--ready", "image/basic_image_upscale"],
    )
    assert result.exit_code == 0
    assert "Running creative case for: image/basic_image_upscale" in result.output


def test_cli_stats_success_exits_0(
    campaign_dir: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    monkeypatch.setattr(ledger_module, "CampaignLedger", _FakeLedger)
    result = CliRunner().invoke(cli, ["stats", "--campaign", str(campaign_dir)])
    assert result.exit_code == 0
    assert "Total cases: 1" in result.output
