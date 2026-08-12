"""P4: new envelope writes carry the format version and rich nodes, no compiled_api twin.

The envelope is the serialized IR; compile("api") is a derived function, not
stored data. New envelopes written by the ingest script therefore omit the
compiled_api sidecar while remaining losslessly decodable.
"""

from __future__ import annotations

import json
from pathlib import Path

from scripts import ingest_external_workflows as ingest

_CORPUS_90A1D5 = (
    Path(__file__).resolve().parent.parent
    / "external_workflows/corpus/90a1d5ff9044902e.json"
)


def _load_90a1d5() -> dict:
    return json.loads(_CORPUS_90A1D5.read_text(encoding="utf-8"))


def test_vibe_workflow_to_dict_omits_compiled_api() -> None:
    """New envelopes are the serialized IR: version + rich nodes, no sidecar."""
    workflow = ingest.convert_to_vibe_format(_load_90a1d5())
    envelope = ingest._vibe_workflow_to_dict(workflow)

    assert envelope["vibecomfy_format_version"] == ingest.VIBECOMFY_FORMAT_VERSION
    assert isinstance(envelope["nodes"], dict)
    assert len(envelope["nodes"]) == 15
    assert "compiled_api" not in envelope
    assert "compiled_api" not in envelope.get("metadata", {})

    # The sidecar-less envelope round-trips losslessly back through the decoder.
    round_tripped = ingest.convert_to_vibe_format(envelope)
    assert len(round_tripped.nodes) == 15
    assert round_tripped.nodes["10"].class_type == "TripoRefineNode"
