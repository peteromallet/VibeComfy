from __future__ import annotations

import pytest

from scripts import runpod_acceptance


def test_main_hard_fails_before_any_live_work(capsys: pytest.CaptureFixture[str]) -> None:
    assert runpod_acceptance.main([]) == 1
    captured = capsys.readouterr()
    assert captured.out == ""
    assert captured.err == runpod_acceptance._FAILURE_TEXT + "\n"


def test_main_rejects_model_phase_without_template() -> None:
    with pytest.raises(SystemExit):
        runpod_acceptance.main(["--model-phase", "core"])


def test_remote_script_is_fail_closed_and_has_no_raw_queue() -> None:
    script = runpod_acceptance._remote_script()
    assert "exit 1" in script
    assert "queue_prompt" not in script
    assert "api_direct_queue" not in script
    assert "API_JSON=" not in script
    assert "pip install" not in script
    assert "vibecomfy.cli run" not in script


def test_remote_script_ignores_live_options() -> None:
    assert runpod_acceptance._remote_script() == runpod_acceptance._remote_script(
        model_template="image/z_image", model_phase="core"
    )
