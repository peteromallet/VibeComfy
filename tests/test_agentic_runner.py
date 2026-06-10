from __future__ import annotations

import pytest

pytest.importorskip("sisypy")

import sisypy.runner

from agentic import runner as agentic_runner
from sisypy import RunMode


def test_runner_help_exposes_repo_local_options(capsys: pytest.CaptureFixture[str]) -> None:
    parser = agentic_runner.build_parser()

    with pytest.raises(SystemExit) as exc_info:
        agentic_runner.main(["--help"])

    captured = capsys.readouterr()
    assert exc_info.value.code == 0
    assert "--name" in captured.out
    assert "--tag" in captured.out
    assert "--actor" in captured.out
    assert parser.get_default("scenarios_dir") == agentic_runner._default_scenarios_dir()
    assert parser.get_default("briefs_dir") == agentic_runner._default_briefs_dir()
    assert parser.get_default("reports_dir") == agentic_runner._default_reports_root()


def test_main_forwards_actor_tag_defaults_and_filters(monkeypatch: pytest.MonkeyPatch) -> None:
    captured: dict[str, object] = {}

    def fake_run_chaining_family(**kwargs: object) -> dict[str, object]:
        captured.update(kwargs)
        return {"status": "ok"}

    monkeypatch.setattr(agentic_runner, "run_chaining_family", fake_run_chaining_family)

    result = agentic_runner.main(
        [
            "--actor",
            "hermes",
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
    assert captured["actor"] == "hermes"
    assert captured["tag"] == "batch-2"
    assert captured["names"] == ["alpha", "beta"]
    assert captured["tags"] == ["chaining", "structural"]
    assert captured["variables"] == {"seed": "7"}
    assert captured["parallel"] is True
    assert captured["capture_interval_sec"] == 2.5
    assert captured["scenarios_dir"] == agentic_runner._default_scenarios_dir()
    assert captured["briefs_dir"] == agentic_runner._default_briefs_dir()
    assert captured["reports_root"] == agentic_runner._default_reports_root()


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

    result = agentic_runner.run_chaining_family(
        actor="hermes",
        tag="compat",
        names=["one"],
        tags=["ignored"],
        variables={"seed": "7"},
        parallel=True,
        capture_interval_sec=1.5,
        dry_run=True,
    )

    assert result == {"status": "ok"}
    assert captured["reports_dir"] == agentic_runner._default_reports_root()
    assert captured["actor"] == "hermes"
    assert captured["tag"] == "compat"
    assert captured["names"] == ["one"]
    assert captured["dry_run"] is True
    assert captured["mode"] is RunMode.STRUCTURAL
