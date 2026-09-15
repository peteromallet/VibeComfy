"""Keep the MiniMax H3 AV decoder's audio in the workflow outputs."""
from __future__ import annotations

import importlib.util
from pathlib import Path


BUILDER = Path(__file__).parents[1] / "comfy-inspection/MiniMax_H3_AV_EncodeDecode_Inpaint.py"


def _workflow():
    spec = importlib.util.spec_from_file_location("h3_av_candidate", BUILDER)
    assert spec and spec.loader
    module = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(module)
    return module.build()


def test_h3_saves_decoded_video_and_audio_as_distinct_outputs() -> None:
    workflow = _workflow()
    api = workflow.compile("api")

    assert api["92"]["class_type"] == "SaveVideo"
    assert api["92"]["inputs"]["video"] == ["105::168", 0]
    assert api["93"]["class_type"] == "SaveAudio"
    assert api["93"]["inputs"]["audio"] == ["105::168", 1]

    video_output = next(output for output in workflow.outputs if output.node_id == "92")
    audio_output = next(output for output in workflow.outputs if output.node_id == "93")
    assert video_output.output_type == "SaveVideo"
    assert audio_output.output_type == "SaveAudio"
    assert audio_output.artifact_kind == "audio"
    assert audio_output.mime_type == "audio/flac"
    assert audio_output.filename_prefix == "audio/MiniMax_H3"
