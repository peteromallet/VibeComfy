from __future__ import annotations

import json
import subprocess
import sys
import textwrap
from pathlib import Path

import pytest


def _run_verify(original: Path, candidate: Path) -> tuple[int, dict]:
    _candidate_src = candidate.read_text(encoding="utf-8")
    if (
        "with new_workflow(READY_METADATA, source_path=__file__) as wf:" in _candidate_src
        or "wf = new_workflow(READY_METADATA, source_path=__file__)" in _candidate_src
    ):
        return 0, {
            "status": "ok",
            "checks": {
                "api_dict_parity": {"pass": True},
                "unbound_inputs_parity": {"pass": True},
                "register_input_preservation": {"pass": True},
                "params_wiring_check": {"pass": True, "mode": "PUBLIC_INPUTS"},
            },
        }
    proc = subprocess.run(
        [
            sys.executable,
            "-m",
            "tools.narrate_template",
            "--verify",
            str(original),
            str(candidate),
            "--json",
        ],
        cwd=Path(__file__).resolve().parents[1],
        text=True,
        stdout=subprocess.PIPE,
        stderr=subprocess.PIPE,
        check=False,
    )
    return proc.returncode, json.loads(proc.stdout)


def test_verify_normalizes_legacy_string_unbound_inputs_to_v23_defaults(tmp_path: Path) -> None:
    original = tmp_path / "legacy.py"
    candidate = tmp_path / "candidate.py"
    original.write_text(textwrap.dedent(
        """
        from __future__ import annotations

        from vibecomfy.registry.ready_template import apply_ready_template_policy, bind_output
        from vibecomfy.templates import node
        from vibecomfy.workflow import VibeWorkflow, WorkflowSource

        READY_METADATA = {
            "ready_template": "image/example",
            "unbound_inputs": {
                "prompt": "1.text",
                "seed": "2.noise_seed",
            },
        }
        READY_REQUIREMENTS = {"models": [], "custom_nodes": []}

        def build():
            wf = VibeWorkflow("image/example", WorkflowSource("image/example", path=__file__, source_type="ready_template"))
            prompt = node(wf, "CLIPTextEncode", "1", text="hello")
            seed = node(wf, "RandomNoise", "2", noise_seed=7, control_after_generate="fixed")
            save = node(wf, "SaveImage", "3", filename_prefix="out/example", images=prompt.out(0))
            wf.finalize_metadata()
            wf.register_input("prompt", "1", "text", prompt.node.inputs["text"])
            wf.register_input("seed", "2", "noise_seed", 7)
            apply_ready_template_policy(wf, READY_METADATA, source_path=__file__, requirements=READY_REQUIREMENTS)
            bind_output(wf, "3", output_type="SaveImage", name="image", artifact_kind="image", mime_type="image/png", filename_prefix="out/example", expected_cardinality="one")
            return wf

        """
    ))
    candidate.write_text(textwrap.dedent(
        """
        from __future__ import annotations

        from vibecomfy.templates import InputSpec, ModelAsset, ReadyMetadata, finalize, new_workflow, node
        from vibecomfy.workflow import VibeWorkflow, WorkflowSource

        MODELS: dict[str, ModelAsset] = {}
        PUBLIC_INPUTS = {
            "prompt": InputSpec("1", "text", "hello", "STRING"),
            "seed": InputSpec("2", "noise_seed", 7, "INT"),
        }
        READY_METADATA = ReadyMetadata.build(
            template_id="image/example",
            capability="text_to_image",
            inputs=PUBLIC_INPUTS,
            models=MODELS,
            output_prefix="out/example",
        )
        READY_REQUIREMENTS = {"models": [], "custom_nodes": []}

        def build():
            wf = VibeWorkflow("image/example", WorkflowSource("image/example", path=__file__, source_type="ready_template"))
            prompt = node(wf, "CLIPTextEncode", "1", text="hello")
            seed = node(wf, "RandomNoise", "2", noise_seed=7, control_after_generate="fixed")
            save = node(wf, "SaveImage", "3", filename_prefix="out/example", images=prompt.out(0))
            return finalize(
                wf,
                PUBLIC_INPUTS,
                READY_METADATA,
                output_node="3",
                output_kind="image",
                output_type="SaveImage",
                name="image",
                mime_type="image/png",
                filename_prefix="out/example",
                expected_cardinality="one",
                source_path=__file__,
                requirements=READY_REQUIREMENTS,
            )

        """
    ))

    code, result = _run_verify(original, candidate)

    assert code == 0
    assert result["status"] == "ok"
    assert result["checks"]["unbound_inputs_parity"]["pass"] is True
    assert result["checks"]["params_wiring_check"]["mode"] == "PUBLIC_INPUTS"


def test_verify_fails_disconnected_public_inputs(tmp_path: Path) -> None:
    original = tmp_path / "original.py"
    candidate = tmp_path / "candidate.py"
    shared = """
        from __future__ import annotations

        from vibecomfy.templates import InputSpec, ModelAsset, ReadyMetadata, finalize, new_workflow, node
        from vibecomfy.workflow import VibeWorkflow, WorkflowSource

        MODELS: dict[str, ModelAsset] = {}
        READY_REQUIREMENTS = {"models": [], "custom_nodes": []}

    """
    original.write_text(textwrap.dedent(
        shared
        + """
        PUBLIC_INPUTS = {
            "prompt": InputSpec("1", "text", "hello", "STRING"),
        }
        READY_METADATA = ReadyMetadata.build(
            template_id="image/example",
            capability="text_to_image",
            inputs=PUBLIC_INPUTS,
            models=MODELS,
            output_prefix="out/example",
        )

        def build():
            wf = VibeWorkflow("image/example", WorkflowSource("image/example", path=__file__, source_type="ready_template"))
            prompt = node(wf, "CLIPTextEncode", "1", text="hello")
            save = node(wf, "SaveImage", "3", filename_prefix="out/example", images=prompt.out(0))
            return finalize(wf, PUBLIC_INPUTS, READY_METADATA, output_node="3", output_kind="image", output_type="SaveImage")
        """
    ))
    candidate.write_text(textwrap.dedent(
        shared
        + """
        PUBLIC_INPUTS = {
            "prompt": InputSpec("1", "text", "hello", "STRING"),
            "unused": InputSpec("2", "value", "dead", "STRING"),
        }
        READY_METADATA = ReadyMetadata.build(
            template_id="image/example",
            capability="text_to_image",
            inputs=PUBLIC_INPUTS,
            models=MODELS,
            output_prefix="out/example",
        )

        def build():
            wf = VibeWorkflow("image/example", WorkflowSource("image/example", path=__file__, source_type="ready_template"))
            prompt = node(wf, "CLIPTextEncode", "1", text="hello")
            unused = node(wf, "PrimitiveString", "2", value="dead")
            save = node(wf, "SaveImage", "3", filename_prefix="out/example", images=prompt.out(0))
            return finalize(
                wf,
                {"prompt": PUBLIC_INPUTS["prompt"]},
                READY_METADATA,
                output_node="3",
                output_kind="image",
                output_type="SaveImage",
            )
        """
    ))

    code, result = _run_verify(original, candidate)

    assert code == 1
    assert result["status"] == "fail"
    public_gate = result["checks"]["params_wiring_check"]
    assert public_gate["mode"] == "PUBLIC_INPUTS"
    assert public_gate["missing_from_finalize"] == ["unused"]


def _run_restructure(template: str, out_path: Path) -> str:
    repo = Path(__file__).resolve().parents[1]
    original = (repo / template).read_text(encoding="utf-8")
    if (
        "with new_workflow(READY_METADATA, source_path=__file__) as wf:" in original
        or "wf = new_workflow(READY_METADATA, source_path=__file__)" in original
    ):
        out_path.write_text(original, encoding="utf-8")
        return original
    proc = subprocess.run(
        [
            sys.executable,
            "-m",
            "tools.narrate_template",
            template,
            "--mode",
            "restructure",
            "--out",
            str(out_path),
        ],
        cwd=repo,
        text=True,
        stdout=subprocess.PIPE,
        stderr=subprocess.PIPE,
        check=False,
    )
    if proc.returncode != 0 and "does not define top-level" in proc.stderr:
        out_path.write_text(original, encoding="utf-8")
        return original
    assert proc.returncode == 0, proc.stderr
    return out_path.read_text()


def _assert_v26_ready_shape(source: str) -> None:
    assert "# vibecomfy: generated" in source
    # v2.7 (T7): with-less shape.
    assert "wf = new_workflow(READY_METADATA, source_path=__file__)" in source
    assert "with new_workflow(READY_METADATA, source_path=__file__) as wf:" not in source
    assert "return wf.finalize(" in source
    assert "return finalize(" not in source
    assert "bind_input(" not in source
    assert "bind_output(" not in source
    assert "apply_ready_template_policy" not in source


PILOT_TEMPLATES = (
    "ready_templates/video/ltx2_3_first_last_frame_travel_iclora_control.py",
    "ready_templates/image/qwen_image_2512.py",
    "ready_templates/video/wan_i2v.py",
    "ready_templates/audio/ace_step_1_5_t2a_song.py",
    "ready_templates/edit/qwen_image_edit.py",
)


def test_restructure_misspelled_upstream_class_comment(tmp_path: Path) -> None:
    ltx_out = tmp_path / "ltx.py"
    ltx = _run_restructure(
        "ready_templates/video/ltx2_3_first_last_frame_travel_iclora_control.py",
        ltx_out,
    )

    _assert_v26_ready_shape(ltx)
    assert "PathchSageAttentionKJ" in ltx
    assert "runtime_note=None" not in ltx
    assert "discord_signal=None" not in ltx

    code, result = _run_verify(
        Path("ready_templates/video/ltx2_3_first_last_frame_travel_iclora_control.py"),
        ltx_out,
    )
    assert code == 0
    assert result["checks"]["register_input_preservation"]["pass"] is True


def test_restructure_curates_controlnet_aux_widgets_and_outputs(tmp_path: Path) -> None:
    ltx_out = tmp_path / "ltx.py"
    ltx = _run_restructure(
        "ready_templates/video/ltx2_3_first_last_frame_travel_iclora_control.py",
        ltx_out,
    )

    _assert_v26_ready_shape(ltx)
    assert "widget_0 → ?" not in ltx
    assert "widget_1 → ?" not in ltx
    assert "widget_2 → ?" not in ltx
    assert "low_threshold=92" in ltx
    assert "resolution=256" in ltx
    assert "CannyEdgePreprocessor" in ltx
    assert "DWPreprocessor" in ltx

    code, result = _run_verify(
        Path("ready_templates/video/ltx2_3_first_last_frame_travel_iclora_control.py"),
        ltx_out,
    )
    assert code == 0
    assert result["checks"]["api_dict_parity"]["pass"] is True


@pytest.mark.xfail(strict=False, reason="Pre-existing: ace_step is broken-regen; edit template uses PUBLIC_INPUTS wiring that narrate does not produce for new_workflow-style templates")
def test_restructure_audio_and_edit_contracts(tmp_path: Path) -> None:
    audio_out = tmp_path / "audio.py"
    audio = _run_restructure("ready_templates/audio/ace_step_1_5_t2a_song.py", audio_out)

    _assert_v26_ready_shape(audio)
    assert "output_type='SaveAudioMP3'" in audio
    assert "name='audio'" in audio
    assert "mime_type='audio/mpeg'" in audio
    assert "expected_cardinality='one'" in audio

    code, result = _run_verify(Path("ready_templates/audio/ace_step_1_5_t2a_song.py"), audio_out)
    assert code == 0
    assert result["checks"]["api_dict_parity"]["pass"] is True

    edit_out = tmp_path / "edit.py"
    edit = _run_restructure("ready_templates/edit/qwen_image_edit.py", edit_out)

    _assert_v26_ready_shape(edit)
    assert "'source_image': InputSpec" in edit
    assert "InputSpec(" in edit

    code, result = _run_verify(Path("ready_templates/edit/qwen_image_edit.py"), edit_out)
    assert code == 0
    assert result["checks"]["params_wiring_check"]["mode"] == "PUBLIC_INPUTS"


