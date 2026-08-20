from __future__ import annotations

import pytest

pytest.importorskip("runpod_lifecycle", reason="requires sibling runpod-lifecycle package")

from scripts import runpod_acceptance


def test_remote_script_covers_core_representations() -> None:
    script = runpod_acceptance._remote_script()

    assert "API_JSON=tests/snapshots/empty_image_red_smoke_required.api.json" in script
    assert "run_step api_direct_queue api_json" in script
    assert "vibecomfy.cli port check \"$API_JSON\" --json" in script
    assert "vibecomfy.cli port convert \"$API_JSON\" --out \"$SCRATCHPAD\" --json" in script
    assert "run_step run_ready_python_embedded python_ready" in script
    assert "run_step run_converted_json_embedded json_python" in script
    assert "vibecomfy.cli session start --id \"$SERVER_ID\"" in script
    assert "run_step run_ready_python_existing_server python_ready_server" in script
    assert "run_step run_converted_json_existing_server json_python_server" in script
    assert "direct_api_json" in script
    assert "existing_server_json_derived_python" in script


def test_remote_script_model_template_is_optional() -> None:
    default_script = runpod_acceptance._remote_script()
    model_script = runpod_acceptance._remote_script(
        model_template="image/z_image",
        model_phase="core",
    )

    assert "unset VIBECOMFY_ACCEPTANCE_MODEL_TEMPLATE" in default_script
    assert "export VIBECOMFY_ACCEPTANCE_MODEL_TEMPLATE=image/z_image" in model_script
    assert "export VIBECOMFY_ACCEPTANCE_MODEL_PHASE=core" in model_script
    assert "run_step model_stage model" in model_script
    assert "run_step run_model_template model" in model_script


def test_main_rejects_model_phase_without_template() -> None:
    with pytest.raises(SystemExit):
        runpod_acceptance.main(["--model-phase", "core"])
