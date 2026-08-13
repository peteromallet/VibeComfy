"""S4 ingest provenance — every ingested node tagged untrusted_source.

Synthetic in-test ComfyUI API JSON; no dependency on ready_templates/sources/.
"""

from __future__ import annotations

from vibecomfy.ingest.normalize import convert_to_vibe_format
from vibecomfy.security.gate import requesting_provenance
from vibecomfy.security.provenance import PROVENANCE_KEY


def _synthetic_api_workflow() -> dict:
    # ComfyUI API shape: {node_id: {"class_type": ..., "inputs": {...}}}
    return {
        "1": {
            "class_type": "CLIPTextEncode",
            "inputs": {"text": "hello", "clip": ["2", 0]},
        },
        "2": {"class_type": "CheckpointLoaderSimple", "inputs": {"ckpt_name": "x.safetensors"}},
        "3": {"class_type": "SaveImage", "inputs": {"images": ["1", 0], "filename_prefix": "out"}},
    }


def test_every_node_tagged_untrusted_source():
    wf = convert_to_vibe_format(_synthetic_api_workflow(), workflow_id="t")
    assert wf.nodes, "expected at least one ingested node"
    for node in wf.nodes.values():
        assert node.metadata.get(PROVENANCE_KEY) == "untrusted_source", (
            f"node {node.id} ({node.class_type}) provenance="
            f"{node.metadata.get(PROVENANCE_KEY)!r}"
        )


def test_schema_derived_metadata_untouched():
    # Schema-derived fields are only set when a schema_provider supplies them.
    # Without a provider, those keys must not appear; tagging provenance must
    # not invent them.
    wf = convert_to_vibe_format(_synthetic_api_workflow(), workflow_id="t")
    for node in wf.nodes.values():
        for forbidden in ("output_names", "output_types", "input_aliases", "schema_source"):
            assert forbidden not in node.metadata, (
                f"node {node.id} unexpectedly has schema-derived field "
                f"{forbidden!r}={node.metadata.get(forbidden)!r}"
            )


def test_requesting_provenance_restored_after_call():
    assert requesting_provenance.get() == "agent_authored"
    convert_to_vibe_format(_synthetic_api_workflow(), workflow_id="t")
    assert requesting_provenance.get() == "agent_authored", (
        "requesting_provenance ContextVar leaked out of convert_to_vibe_format"
    )


def test_requesting_provenance_restored_even_on_exception():
    # Pass shape that detect_workflow_shape will accept but then trigger an
    # error in normalize_to_api path. We mimic by passing a non-API/UI shape
    # that explodes — easiest is to monkey nothing and simply confirm that
    # if the inner call raises, the ContextVar is still restored.
    import pytest

    class _Boom(Exception):
        pass

    from vibecomfy.ingest import normalize as _norm

    original = _norm._from_api_impl

    def _raise(*_a, **_kw):
        raise _Boom("synthetic")

    _norm._from_api_impl = _raise  # type: ignore[assignment]
    try:
        with pytest.raises(_Boom):
            convert_to_vibe_format({}, workflow_id="t")
        assert requesting_provenance.get() == "agent_authored"
    finally:
        _norm._from_api_impl = original  # type: ignore[assignment]
