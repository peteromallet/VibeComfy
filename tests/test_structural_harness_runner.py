from __future__ import annotations

from types import SimpleNamespace

import pytest

pytest.importorskip("sisypy")

import sisypy.runner

from tests.structural_harness import runner as structural_runner
from sisypy import RunMode


def test_runner_help_exposes_repo_local_options(capsys: pytest.CaptureFixture[str]) -> None:
    parser = structural_runner.build_parser()

    with pytest.raises(SystemExit) as exc_info:
        structural_runner.main(["--help"])

    captured = capsys.readouterr()
    assert exc_info.value.code == 0
    assert "--name" in captured.out
    assert "--tag" in captured.out
    assert "--actor" in captured.out
    assert parser.get_default("scenarios_dir") == structural_runner._default_scenarios_dir()
    assert parser.get_default("briefs_dir") == structural_runner._default_briefs_dir()
    assert parser.get_default("reports_dir") == structural_runner._default_reports_root()


def test_main_forwards_actor_tag_defaults_and_filters(monkeypatch: pytest.MonkeyPatch) -> None:
    captured: dict[str, object] = {}

    def fake_run_chaining_family(**kwargs: object) -> dict[str, object]:
        captured.update(kwargs)
        return {"status": "ok"}

    monkeypatch.setattr(structural_runner, "run_chaining_family", fake_run_chaining_family)

    result = structural_runner.main(
        [
            "--actor",
            "faking",
            "--tag",
            "batch-2",
            "--name",
            "alpha",
            "--tags",
            "chaining",
            "structural",
            "--var",
            "seed=7",
            "--capture-interval-sec",
            "2.5",
            "--parallel",
            "beta",
        ]
    )

    assert result == {"status": "ok"}
    assert captured["actor"] == "faking"
    assert captured["tag"] == "batch-2"
    assert captured["names"] == ["alpha", "beta"]
    assert captured["tags"] == ["chaining", "structural"]
    assert captured["variables"] == {"seed": "7"}
    assert captured["parallel"] is True
    assert captured["capture_interval_sec"] == 2.5
    assert captured["scenarios_dir"] == structural_runner._default_scenarios_dir()
    assert captured["briefs_dir"] == structural_runner._default_briefs_dir()
    assert captured["reports_root"] == structural_runner._default_reports_root()


def test_run_chaining_family_adapts_to_reports_dir_api_shape(monkeypatch: pytest.MonkeyPatch) -> None:
    captured: dict[str, object] = {}

    def fake_run_all(
        adapter: object,
        *,
        scenarios_dir=None,
        briefs_dir=None,
        reports_dir=None,
        mode=None,
        actor="fake",
        tag="run",
        names=None,
        dry_run=False,
    ) -> dict[str, object]:
        captured.update(
            {
                "adapter": adapter,
                "scenarios_dir": scenarios_dir,
                "briefs_dir": briefs_dir,
                "reports_dir": reports_dir,
                "mode": mode,
                "actor": actor,
                "tag": tag,
                "names": names,
                "dry_run": dry_run,
            }
        )
        return {"status": "ok"}

    monkeypatch.setattr(sisypy.runner, "run_all", fake_run_all)

    result = structural_runner.run_chaining_family(
        actor="faking",
        tag="compat",
        names=["one"],
        tags=["ignored"],
        variables={"seed": "7"},
        parallel=True,
        capture_interval_sec=1.5,
        dry_run=True,
    )

    assert result == {"status": "ok"}
    assert captured["reports_dir"] == structural_runner._default_reports_root()
    assert captured["actor"] == "faking"
    assert captured["tag"] == "compat"
    assert captured["names"] == ["one"]
    assert captured["dry_run"] is True
    assert captured["mode"] is RunMode.STRUCTURAL


def test_structural_runner_rejects_live_agent_actors() -> None:
    with pytest.raises(ValueError, match="only supports fake/faking"):
        structural_runner.run_chaining_family(actor="hermes")


def test_structural_runner_rejects_live_mode() -> None:
    with pytest.raises(ValueError, match="only runs structural"):
        structural_runner.run_chaining_family(mode="live")


def _parse_failure_result() -> dict[str, object]:
    return {
        "overall_passed": False,
        "summary": "Failed to parse assessor response.",
        "weaknesses": ["LLM response was not valid JSON."],
    }


def test_assessor_parse_failure_is_retried_once() -> None:
    responses = iter([_parse_failure_result(), {"overall_passed": True}])
    calls = 0

    def fake_assess(*_args: object, **_kwargs: object) -> dict[str, object]:
        nonlocal calls
        calls += 1
        return next(responses)

    sisypy_runner = SimpleNamespace(assess=fake_assess)
    with structural_runner._retry_assessor_parse_failure_once(sisypy_runner):
        result = sisypy_runner.assess()

    assert result == {"overall_passed": True}
    assert calls == 2
    assert sisypy_runner.assess is fake_assess


def test_assessor_parse_failure_retry_is_bounded() -> None:
    calls = 0

    def fake_assess(*_args: object, **_kwargs: object) -> dict[str, object]:
        nonlocal calls
        calls += 1
        return _parse_failure_result()

    sisypy_runner = SimpleNamespace(assess=fake_assess)
    with structural_runner._retry_assessor_parse_failure_once(sisypy_runner):
        result = sisypy_runner.assess()

    assert result == _parse_failure_result()
    assert calls == 2


def test_assessor_rubric_failure_is_not_retried() -> None:
    calls = 0
    rubric_failure = {
        "overall_passed": False,
        "summary": "Evidence violates an enforced rule.",
        "weaknesses": ["Missing required artifact."],
    }

    def fake_assess(*_args: object, **_kwargs: object) -> dict[str, object]:
        nonlocal calls
        calls += 1
        return rubric_failure

    sisypy_runner = SimpleNamespace(assess=fake_assess)
    with structural_runner._retry_assessor_parse_failure_once(sisypy_runner):
        result = sisypy_runner.assess()

    assert result == rubric_failure
    assert calls == 1
