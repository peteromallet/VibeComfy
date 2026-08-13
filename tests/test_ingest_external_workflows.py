"""P4/P5: new envelope writes go through VibeWorkflow.to_envelope.

The envelope is the serialized IR; compile("api") is a derived function, not
stored data. New envelopes therefore omit the compiled_api sidecar while
remaining losslessly decodable. Format version lives on the IR.
"""

from __future__ import annotations

import json
from pathlib import Path

from scripts import ingest_external_workflows as ingest
from vibecomfy.workflow import FORMAT_VERSION, VibeWorkflow

_CORPUS_90A1D5 = (
    Path(__file__).resolve().parent
    / "fixtures/b02_corpus_mini/90a1d5ff9044902e.json"
)


def _load_90a1d5() -> dict:
    return json.loads(_CORPUS_90A1D5.read_text(encoding="utf-8"))


def test_vibe_workflow_to_dict_omits_compiled_api() -> None:
    """New envelopes are the serialized IR: version + rich nodes, no sidecar."""
    workflow = ingest.from_envelope(_load_90a1d5())
    envelope = workflow.to_envelope()

    assert envelope["vibecomfy_format_version"] == FORMAT_VERSION
    assert envelope["vibecomfy_format_version"] == ingest.VIBECOMFY_FORMAT_VERSION
    assert ingest.VIBECOMFY_FORMAT_VERSION == FORMAT_VERSION
    assert isinstance(envelope["nodes"], dict)
    assert len(envelope["nodes"]) == 15
    assert "compiled_api" not in envelope
    assert "compiled_api" not in envelope.get("metadata", {})

    # The sidecar-less envelope round-trips losslessly back through the decoder.
    round_tripped = VibeWorkflow.from_envelope(envelope)
    assert len(round_tripped.nodes) == 15
    assert round_tripped.nodes["10"].class_type == "TripoRefineNode"


def test_ingest_helper_is_to_envelope() -> None:
    """The ingest script writer is a one-line wrap of to_envelope, not a twin."""
    workflow = ingest.from_envelope(_load_90a1d5())
    assert ingest._vibe_workflow_to_dict(workflow) == workflow.to_envelope()


def test_fixer_envelope_uses_to_envelope_then_workflow_id_stamp() -> None:
    """Fixer writes via to_envelope; workflow_id is stamped after, not by the IR."""
    from vibecomfy.demo_factory.fixer import _ui_graph_to_ir_envelope

    workflow_id = "aaaaaaaa-bbbb-4ccc-8ddd-eeeeeeeeeeee"
    ui_graph = {
        "id": workflow_id,
        "nodes": [
            {
                "id": 1,
                "type": "PreviewImage",
                "pos": [0, 0],
                "size": [140, 80],
                "flags": {},
                "order": 0,
                "mode": 0,
                "inputs": [{"name": "images", "type": "IMAGE", "link": None}],
                "outputs": [],
                "properties": {"Node name for S&R": "PreviewImage"},
                "widgets_values": [],
            }
        ],
        "links": [],
    }
    envelope = _ui_graph_to_ir_envelope(ui_graph)
    assert "compiled_api" not in envelope
    assert envelope["vibecomfy_format_version"] == FORMAT_VERSION
    assert envelope["workflow_id"] == workflow_id
    decoded = VibeWorkflow.from_envelope(envelope)
    assert "1" in decoded.nodes
    assert decoded.nodes["1"].class_type == "PreviewImage"
