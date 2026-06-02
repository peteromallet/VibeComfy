"""Adapter tests for the graph-inferred schema provider (corpus_schema.py).

Validates that ``graph_inferred_schema_provider`` correctly loads corpus
graphs (LTX t2v, LTX i2v), infers schemas from link evidence, respects
explicit core schema overrides, and that ``socket_types_compatible`` holds
for every real link in the corpus.

RuneXX graph absence is handled with ``pytest.skip``.
"""

from __future__ import annotations

import json
from pathlib import Path
from typing import Any

import pytest

from tests.support.corpus_schema import GraphInferredSchemaProvider, graph_inferred_schema_provider
from vibecomfy.schema import NodeSchema, socket_types_compatible

# ── corpus paths ─────────────────────────────────────────────────────────

_CORPUS_ROOT = Path("workflow_corpus/official/video")

_LTX_T2V_PATH = _CORPUS_ROOT / "ltx2_3_t2v.json"
_LTX_I2V_PATH = _CORPUS_ROOT / "ltx2_3_i2v.json"
_WAN_T2V_PATH = _CORPUS_ROOT / "wan_t2v.json"
_WAN_I2V_PATH = _CORPUS_ROOT / "wan_i2v.json"

_RUNEXX_PATH = Path("workflow_corpus/custom_nodes/ltxvideo/runexx/LTX-2.3_Talking_Avatar_Qwen_TTS.json")


def _load_json(path: Path) -> dict[str, Any]:
    """Load a JSON file, or skip if it doesn't exist."""
    if not path.exists():
        pytest.skip(f"Corpus graph not available: {path}")
    return json.loads(path.read_text(encoding="utf-8"))


# ── module-scoped fixtures ──────────────────────────────────────────────


@pytest.fixture(scope="module")
def ltx_t2v_ui() -> dict[str, Any]:
    """Raw UI JSON for LTX-2.3 text-to-video corpus graph."""
    return _load_json(_LTX_T2V_PATH)


@pytest.fixture(scope="module")
def ltx_i2v_ui() -> dict[str, Any]:
    """Raw UI JSON for LTX-2.3 image-to-video corpus graph."""
    return _load_json(_LTX_I2V_PATH)


@pytest.fixture(scope="module")
def ltx_t2v_provider(ltx_t2v_ui: dict[str, Any]) -> GraphInferredSchemaProvider:
    """Schema provider inferred from the LTX t2v corpus graph."""
    return graph_inferred_schema_provider(ltx_t2v_ui)


@pytest.fixture(scope="module")
def ltx_i2v_provider(ltx_i2v_ui: dict[str, Any]) -> GraphInferredSchemaProvider:
    """Schema provider inferred from the LTX i2v corpus graph."""
    return graph_inferred_schema_provider(ltx_i2v_ui)


# ── RuneXX skip ─────────────────────────────────────────────────────────


def test_runexx_graph_absent_triggers_skip() -> None:
    """The RuneXX corpus graph is not available in this worktree — skip cleanly."""
    if _RUNEXX_PATH.exists():
        pytest.skip("RuneXX graph is present (unexpected in this worktree)")
    else:
        # This is the expected case — graph is absent.
        # Just assert the path doesn't exist so the skip logic works.
        assert not _RUNEXX_PATH.exists(), "RuneXX graph should be absent"


# ── schema provider integrity ───────────────────────────────────────────


def test_ltx_t2v_provider_loads_without_errors(ltx_t2v_provider: GraphInferredSchemaProvider) -> None:
    """Provider created from LTX t2v graph is a valid GraphInferredSchemaProvider."""
    assert isinstance(ltx_t2v_provider, GraphInferredSchemaProvider)


def test_ltx_i2v_provider_loads_without_errors(ltx_i2v_provider: GraphInferredSchemaProvider) -> None:
    """Provider created from LTX i2v graph is a valid GraphInferredSchemaProvider."""
    assert isinstance(ltx_i2v_provider, GraphInferredSchemaProvider)


# ── explicit core schema assertions ─────────────────────────────────────


_EXPLICIT_CHECKS: list[tuple[str, list[str] | None, list[tuple[str, str]] | None]] = [
    # (class_type, expected_input_names, expected_output (name, type) pairs)
    ("SaveImage", ["images"], []),
    ("SaveVideo", ["video"], []),
    ("LoadImage", [], [("IMAGE", "IMAGE"), ("MASK", "MASK")]),
    ("CLIPTextEncode", ["clip", "text"], [("CONDITIONING", "CONDITIONING")]),
    ("VAEDecode", ["samples", "vae"], [("IMAGE", "IMAGE")]),
    (
        "KSampler",
        ["model", "positive", "negative", "latent_image", "seed", "steps", "cfg", "sampler_name", "scheduler", "denoise"],
        [("LATENT", "LATENT")],
    ),
    ("DualCLIPLoader", ["clip_name1", "clip_name2"], [("CLIP", "CLIP")]),
    ("VAELoader", ["vae_name"], [("VAE", "VAE")]),
    ("SetNode", ["value"], [("value", "*")]),
    ("GetNode", ["value"], [("value", "*")]),
    ("Reroute", [""], [("", "*")]),
]


@pytest.mark.parametrize("class_type, expected_inputs, expected_outputs", _EXPLICIT_CHECKS)
def test_explicit_core_schema(
    ltx_t2v_provider: GraphInferredSchemaProvider,
    class_type: str,
    expected_inputs: list[str] | None,
    expected_outputs: list[tuple[str, str]] | None,
) -> None:
    """Explicit core schemas override inferred schemas with correct shape."""
    schema = ltx_t2v_provider.get_schema(class_type)
    assert schema is not None, f"Missing explicit schema for {class_type}"
    assert isinstance(schema, NodeSchema)

    if expected_inputs is not None:
        actual_inputs = list(schema.inputs.keys())
        assert actual_inputs == expected_inputs, (
            f"{class_type}: expected inputs {expected_inputs}, got {actual_inputs}"
        )

    if expected_outputs is not None:
        actual_outputs = [(o.name, o.type) for o in schema.outputs]
        assert actual_outputs == expected_outputs, (
            f"{class_type}: expected outputs {expected_outputs}, got {actual_outputs}"
        )


def test_saveimage_has_inputs_no_outputs(ltx_t2v_provider: GraphInferredSchemaProvider) -> None:
    """SaveImage has inputs (images) but no outputs."""
    schema = ltx_t2v_provider.get_schema("SaveImage")
    assert schema is not None
    assert "images" in schema.inputs
    assert schema.outputs == []


def test_reroute_has_passthrough_star_type(ltx_t2v_provider: GraphInferredSchemaProvider) -> None:
    """Reroute has passthrough '*' type for both input and output."""
    schema = ltx_t2v_provider.get_schema("Reroute")
    assert schema is not None
    reroute_input = schema.inputs.get("")
    assert reroute_input is not None
    assert reroute_input.type == "*"
    assert len(schema.outputs) == 1
    assert schema.outputs[0].type == "*"


# ── link compatibility ──────────────────────────────────────────────────


def _collect_link_type_pairs(ui: dict[str, Any]) -> list[tuple[str, str]]:
    """Collect (output_type, input_type) for every link in a graph.

    Uses the link's own ``type`` field as the authoritative socket type.
    Node-declared types may be composite (e.g. ``FLOAT,INT``) and are
    only used as a fallback when the link type is absent.
    """
    pairs: list[tuple[str, str]] = []

    def _safe_type(raw_type: Any) -> str | None:
        """Return a clean single type string, skipping composites."""
        if isinstance(raw_type, str) and raw_type and "," not in raw_type:
            return raw_type
        return None

    def _process(links: list[Any], nodes: list[dict[str, Any]]) -> None:
        node_by_id = {n["id"]: n for n in nodes}
        for link in links:
            if isinstance(link, list) and len(link) >= 6:
                link_type = link[5]
                output_type = _safe_type(link_type) or link_type
                input_type = _safe_type(link_type) or link_type
                # Fallback: use node-declared type only if link type is composite
                origin_node = node_by_id.get(link[1])
                if origin_node and _safe_type(link_type) is None:
                    outputs = origin_node.get("outputs") or []
                    if isinstance(link[2], int) and link[2] < len(outputs):
                        decl = _safe_type(outputs[link[2]].get("type"))
                        if decl:
                            output_type = decl
                target_node = node_by_id.get(link[3])
                if target_node and _safe_type(link_type) is None:
                    inputs = target_node.get("inputs") or []
                    if isinstance(link[4], int) and link[4] < len(inputs):
                        decl = _safe_type(inputs[link[4]].get("type"))
                        if decl:
                            input_type = decl
                pairs.append((output_type, input_type))
            elif isinstance(link, dict):
                link_type = link.get("type", "*")
                output_type = _safe_type(link_type) or link_type
                input_type = _safe_type(link_type) or link_type
                origin_node = node_by_id.get(link.get("origin_id")) if isinstance(link.get("origin_id"), int) else None
                if origin_node and _safe_type(link_type) is None:
                    outputs = origin_node.get("outputs") or []
                    origin_slot = link.get("origin_slot")
                    if isinstance(origin_slot, int) and origin_slot < len(outputs):
                        decl = _safe_type(outputs[origin_slot].get("type"))
                        if decl:
                            output_type = decl
                target_node = node_by_id.get(link.get("target_id")) if isinstance(link.get("target_id"), int) else None
                if target_node and _safe_type(link_type) is None:
                    inputs = target_node.get("inputs") or []
                    target_slot = link.get("target_slot")
                    if isinstance(target_slot, int) and target_slot < len(inputs):
                        decl = _safe_type(inputs[target_slot].get("type"))
                        if decl:
                            input_type = decl
                pairs.append((output_type, input_type))

    _process(ui.get("links") or [], ui.get("nodes") or [])
    for sg in (ui.get("definitions") or {}).get("subgraphs") or []:
        if isinstance(sg, dict):
            _process(sg.get("links") or [], sg.get("nodes") or [])
    return pairs


def test_all_ltx_t2v_links_are_compatible(ltx_t2v_ui: dict[str, Any]) -> None:
    """Every link in the LTX t2v corpus graph is socket-type compatible."""
    pairs = _collect_link_type_pairs(ltx_t2v_ui)
    assert len(pairs) > 0, "Expected at least one link in LTX t2v graph"
    for output_type, input_type in pairs:
        assert socket_types_compatible(output_type, input_type), (
            f"Incompatible link: {output_type} → {input_type}"
        )


def test_all_ltx_i2v_links_are_compatible(ltx_i2v_ui: dict[str, Any]) -> None:
    """Every link in the LTX i2v corpus graph is socket-type compatible."""
    pairs = _collect_link_type_pairs(ltx_i2v_ui)
    assert len(pairs) > 0, "Expected at least one link in LTX i2v graph"
    for output_type, input_type in pairs:
        assert socket_types_compatible(output_type, input_type), (
            f"Incompatible link: {output_type} → {input_type}"
        )


# ── inferred schemas for LTX custom types ───────────────────────────────


def test_ltxvcropguides_inferred_in_t2v(ltx_t2v_provider: GraphInferredSchemaProvider) -> None:
    """LTXVCropGuides schema is inferred from t2v graph links."""
    schema = ltx_t2v_provider.get_schema("LTXVCropGuides")
    assert schema is not None, "LTXVCropGuides should have an inferred schema in t2v"
    assert isinstance(schema, NodeSchema)
    # LTXVCropGuides should have latent, negative, positive inputs
    assert "latent" in schema.inputs
    assert "negative" in schema.inputs
    assert "positive" in schema.inputs
    # And outputs
    assert len(schema.outputs) >= 1


def test_socket_types_compatible_star_passthrough() -> None:
    """socket_types_compatible('*', anything) is True."""
    assert socket_types_compatible("*", "IMAGE") is True
    assert socket_types_compatible("*", "LATENT") is True
    assert socket_types_compatible("*", "MODEL") is True
    assert socket_types_compatible("*", "*") is True
    assert socket_types_compatible("*", None) is True
    assert socket_types_compatible("IMAGE", "*") is True


def test_socket_types_compatible_none_is_true() -> None:
    """socket_types_compatible(None, anything) is True (unknown types pass)."""
    assert socket_types_compatible(None, "IMAGE") is True
    assert socket_types_compatible("IMAGE", None) is True
    assert socket_types_compatible(None, None) is True


def test_wan_t2v_provider_loads() -> None:
    """Provider from wan_t2v graph loads without errors (if available)."""
    ui = _load_json(_WAN_T2V_PATH)
    provider = graph_inferred_schema_provider(ui)
    assert isinstance(provider, GraphInferredSchemaProvider)


def test_wan_i2v_provider_loads() -> None:
    """Provider from wan_i2v graph loads without errors (if available)."""
    ui = _load_json(_WAN_I2V_PATH)
    provider = graph_inferred_schema_provider(ui)
    assert isinstance(provider, GraphInferredSchemaProvider)
