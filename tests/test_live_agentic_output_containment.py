from __future__ import annotations

from pathlib import Path

import pytest

from tests.live_agentic_harness.adapter import run_headless_scenario
from tests.live_agentic_harness.output_paths import authorized_output_dir
from tests.live_agentic_harness.runner import (
    _persist_run_summary,
    _persist_scenario_summary,
)


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

    assert (output_base / "safe-tag" / "scenario" / "agentic_summary.json").is_file()
    assert not outside.exists()
