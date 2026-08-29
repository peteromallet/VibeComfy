from __future__ import annotations

import json

from pathlib import Path

import pytest

from tests.live_agentic_harness.adapter import run_headless_scenario
from tests.live_agentic_harness.output_paths import authorized_output_dir
from tests.live_agentic_harness.runner import (
    _persist_run_summary,
    _persist_scenario_summary,
    run_single,
    run_tag,
)
from tests.live_agentic_harness.scenario_manifest import write_manifest


@pytest.mark.parametrize("tag", ["../escape", "safe/../../escape"])
def test_runner_rejects_traversing_tag_without_partial_artifacts(
    tmp_path: Path,
    tag: str,
) -> None:
    output_base = tmp_path / "out"

    with pytest.raises(ValueError, match="invalid path component"):
        _persist_run_summary(
            tag,
            [],
            output_base,
            total_scenarios=0,
            complete=False,
        )

    assert not output_base.exists()


def test_runner_rejects_absolute_tag_without_partial_artifacts(tmp_path: Path) -> None:
    output_base = tmp_path / "out"
    outside = tmp_path / "outside"

    with pytest.raises(ValueError, match="must be relative"):
        _persist_run_summary(
            str(outside),
            [],
            output_base,
            total_scenarios=0,
            complete=False,
        )

    assert not output_base.exists()
    assert not outside.exists()


@pytest.mark.parametrize("scenario_id", ["../escape", "safe/../../escape"])
def test_adapter_rejects_traversing_scenario_id_before_execution(
    tmp_path: Path,
    monkeypatch: pytest.MonkeyPatch,
    scenario_id: str,
) -> None:
    output_base = tmp_path / "out"

    def unexpected_run(*args: object, **kwargs: object) -> None:
        raise AssertionError(
            f"headless service ran before output authorization: {args!r}, {kwargs!r}"
        )

    monkeypatch.setenv("VIBECOMFY_HEADLESS", "1")
    monkeypatch.setattr("vibecomfy.agent.service.run_headless", unexpected_run)

    with pytest.raises(ValueError, match="invalid path component"):
        run_headless_scenario(
            {"id": scenario_id, "query": "inspect the graph"},
            output_base=output_base,
            tag="safe-tag",
        )

    assert not output_base.exists()


def test_adapter_rejects_absolute_scenario_id_without_partial_artifacts(
    tmp_path: Path,
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    output_base = tmp_path / "out"
    outside = tmp_path / "outside"

    def unexpected_run(*args: object, **kwargs: object) -> None:
        raise AssertionError(
            f"headless service ran before output authorization: {args!r}, {kwargs!r}"
        )

    monkeypatch.setenv("VIBECOMFY_HEADLESS", "1")
    monkeypatch.setattr("vibecomfy.agent.service.run_headless", unexpected_run)

    with pytest.raises(ValueError, match="must be relative"):
        run_headless_scenario(
            {"id": str(outside), "query": "inspect the graph"},
            output_base=output_base,
            tag="safe-tag",
        )

    assert not output_base.exists()
    assert not outside.exists()


def test_existing_symlink_parent_escape_is_rejected_without_outside_write(
    tmp_path: Path,
) -> None:
    output_base = tmp_path / "out"
    outside = tmp_path / "outside"
    output_base.mkdir()
    outside.mkdir()
    (output_base / "redirect").symlink_to(outside, target_is_directory=True)

    with pytest.raises(ValueError, match="escapes output_base"):
        authorized_output_dir(output_base, "redirect", "scenario")

    assert list(outside.iterdir()) == []


@pytest.mark.parametrize(
    ("tag", "scenario_id"),
    [
        ("release..candidate", "..lookalike"),
        ("nested/attempts/scenario/attempt_1", "scenario..json"),
        (".hidden/run", "..."),
    ],
)
def test_safe_nested_and_dot_lookalikes_remain_in_root(
    tmp_path: Path,
    tag: str,
    scenario_id: str,
) -> None:
    output_base = tmp_path / "out"

    result = authorized_output_dir(output_base, tag, scenario_id)

    assert result == output_base / tag / scenario_id
    result.resolve(strict=False).relative_to(output_base.resolve(strict=False))
def test_relative_output_base_remains_bound_after_cwd_change(
    tmp_path: Path,
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    first = tmp_path / "first"
    second = tmp_path / "second"
    first.mkdir()
    second.mkdir()

    monkeypatch.chdir(first)
    result = authorized_output_dir(Path("out"), "tag", "scenario")

    monkeypatch.chdir(second)
    result.mkdir(parents=True)
    (result / "probe.json").write_text("{}", encoding="utf-8")

    assert (first / "out" / "tag" / "scenario" / "probe.json").is_file()
    assert not (second / "out").exists()



def test_runner_ignores_reported_output_dir_and_persists_canonically(
    tmp_path: Path,
) -> None:
    output_base = tmp_path / "out"
    outside = tmp_path / "outside"
    summary = {
        "scenario_id": "scenario",
        "output_dir": str(outside),
        "guard": {"live_agentic_success": False},
    }

    _persist_scenario_summary(summary, output_base, "safe-tag")
    persisted = json.loads(
        (output_base / "safe-tag" / "scenario" / "agentic_summary.json").read_text(
            encoding="utf-8"
        )
    )
    assert persisted["scenario_id"] == "scenario"
    assert persisted["output_dir"] == str(output_base / "safe-tag" / "scenario")
    assert summary["output_dir"] == str(output_base / "safe-tag" / "scenario")
    assert not outside.exists()

def test_run_single_overwrites_child_output_identity_before_guard_and_persist(
    tmp_path: Path,
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    output_base = tmp_path / "out"
    outside = tmp_path / "outside"
    scenario_path = tmp_path / "scenario.json"
    scenario_path.write_text(
        json.dumps({"id": "scenario", "query": "inspect the graph"}),
        encoding="utf-8",
    )
    guard_inputs: list[str] = []

    def fake_headless(*args: object, **kwargs: object) -> dict[str, object]:
        return {
            "scenario_id": "spoofed",
            "output_dir": str(outside),
            "status": "success",
            "ok": True,
            "model_attempts": [],
        }

    def fake_guard(output_dir: str | Path, *, scenario: object) -> dict[str, object]:
        guard_inputs.append(str(output_dir))
        return {"live_agentic_success": True, "score_class": "pass"}

    monkeypatch.setattr(
        "tests.live_agentic_harness.adapter.run_headless_scenario", fake_headless
    )
    monkeypatch.setattr(
        "tests.live_agentic_harness.runner._guard_scenario_output", fake_guard
    )

    summary = run_single(str(scenario_path), "safe-tag", output_base, None)
    canonical = output_base / "safe-tag" / "scenario"

    assert guard_inputs == [str(canonical)]
    assert summary["scenario_id"] == "scenario"
    assert summary["output_dir"] == str(canonical)
    persisted = json.loads((canonical / "agentic_summary.json").read_text())
    assert persisted["output_dir"] == str(canonical)
    assert not outside.exists()

def test_parent_rebinds_recovered_child_summary_to_attempt_authority(
    tmp_path: Path,
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    scenarios_dir = tmp_path / "scenarios"
    scenarios_dir.mkdir()
    (scenarios_dir / "scenario.json").write_text(
        json.dumps({"id": "scenario", "query": "inspect the graph"}),
        encoding="utf-8",
    )
    write_manifest(scenarios_dir)

    parent_cwd = tmp_path / "parent"
    parent_cwd.mkdir()
    monkeypatch.chdir(parent_cwd)
    output_base = Path("relative-out")
    outside = tmp_path / "outside"
    def fake_run(cmd: list[str], **kwargs: object) -> tuple[int, str, str]:
        assert cmd[cmd.index("--output-base") + 1] == str(parent_cwd / "relative-out")
        assert kwargs["cwd"] != str(parent_cwd)
        out_file = Path(cmd[cmd.index("--single-out") + 1])
        out_file.write_text(
            json.dumps(
                {
                    "scenario_id": "spoofed",
                    "output_dir": str(outside),
                    "status": "success",
                    "ok": True,
                    "guard": {"live_agentic_success": True, "output_dir": str(outside)},
                    "model_attempts": [],
                    "deepseek_usage": {},
                    "deepseek_est_cost_usd": 0.0,
                    "deepseek_cost_basis": "not_available",
                }
            ),
            encoding="utf-8",
        )
        return (0, "", "")

    monkeypatch.setattr(
        "tests.live_agentic_harness.runner._run_scenario_subprocess", fake_run
    )

    result = run_tag(
        "tag",
        scenarios_dir=scenarios_dir,
        output_base=output_base,
        max_workers=1,
        infra_retries=0,
        progress_every=0,
    )
    canonical = output_base / "tag" / "attempts" / "scenario" / "attempt_1" / "scenario"
    scenario = result["scenarios"][0]

    canonical = parent_cwd / "relative-out" / "tag" / "attempts" / "scenario" / "attempt_1" / "scenario"
    assert scenario["output_dir"] == str(canonical)
    assert scenario["attempts"][0]["scenario_id"] == "scenario"
    assert scenario["attempts"][0]["output_dir"] == str(canonical)
    persisted = json.loads(
        (output_base / "tag" / "scenario" / "agentic_summary.json").read_text()
    )
    assert persisted["output_dir"] == str(canonical)
    assert not outside.exists()


def test_default_output_base_is_bound_to_child_repo_from_neutral_cwd(
    tmp_path: Path,
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    scenarios_dir = tmp_path / "scenarios"
    scenarios_dir.mkdir()
    (scenarios_dir / "scenario.json").write_text(
        json.dumps({"id": "scenario", "query": "inspect the graph"}),
        encoding="utf-8",
    )
    write_manifest(scenarios_dir)

    repo = tmp_path / "repo"
    repo.mkdir()
    parent_cwd = tmp_path / "parent"
    parent_cwd.mkdir()
    monkeypatch.setattr("tests.live_agentic_harness.runner.REPO", repo)
    monkeypatch.chdir(parent_cwd)

    def fake_run(cmd: list[str], **kwargs: object) -> tuple[int, str, str]:
        output_base = Path(cmd[cmd.index("--output-base") + 1])
        assert output_base == repo / "out" / "agentic"
        assert kwargs["cwd"] == str(repo)
        attempt_dir = (
            output_base
            / "tag"
            / "attempts"
            / "scenario"
            / "attempt_1"
            / "scenario"
        )
        out_file = Path(cmd[cmd.index("--single-out") + 1])
        out_file.write_text(
            json.dumps(
                {
                    "scenario_id": "scenario",
                    "output_dir": str(attempt_dir),
                    "status": "success",
                    "ok": True,
                    "guard": {
                        "live_agentic_success": True,
                        "output_dir": str(attempt_dir),
                    },
                    "model_attempts": [],
                    "deepseek_usage": {},
                    "deepseek_est_cost_usd": 0.0,
                    "deepseek_cost_basis": "not_available",
                }
            ),
            encoding="utf-8",
        )
        return (0, "", "")

    monkeypatch.setattr(
        "tests.live_agentic_harness.runner._run_scenario_subprocess", fake_run
    )

    result = run_tag(
        "tag",
        scenarios_dir=scenarios_dir,
        output_base=None,
        max_workers=1,
        infra_retries=0,
        progress_every=0,
    )

    output_base = repo / "out" / "agentic"
    attempt_dir = output_base / "tag" / "attempts" / "scenario" / "attempt_1" / "scenario"
    scenario = result["scenarios"][0]
    assert scenario["output_dir"] == str(attempt_dir)
    assert scenario["attempts"][0]["output_dir"] == str(attempt_dir)
    persisted = json.loads(
        (output_base / "tag" / "scenario" / "agentic_summary.json").read_text()
    )
    assert persisted["output_dir"] == str(attempt_dir)
    assert not (parent_cwd / "out").exists()
