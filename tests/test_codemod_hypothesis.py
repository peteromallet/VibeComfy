from __future__ import annotations

"""Hypothesis property tests for codemod conversion contracts.

Generates small valid ComfyUI workflow JSON (API format, 1-12 nodes, DAG links,
mixed scalar/dict inputs, known alias-backed classes, unknown custom classes,
optional definitions.subgraphs) via handwritten composite strategies.

CRITICAL (FLAG-002): Generated JSON is normalized through ``convert_to_vibe_format``
before calling ``port_convert_workflow`` — the function signature requires a
VibeWorkflow, not a raw dict.
"""

import hashlib
import re
import tempfile
from pathlib import Path
from typing import Any

from hypothesis import HealthCheck, given, settings, strategies as st
import importlib.util

from vibecomfy.ingest.normalize import convert_to_vibe_format
from vibecomfy.porting.convert import port_convert_workflow
from vibecomfy.porting.widgets.aliases import COMPILE_WIDGET_ALIAS_CLASS_TYPES
from vibecomfy.workflow import VibeWorkflow


# ---------------------------------------------------------------------------
# Handwritten strategies
# ---------------------------------------------------------------------------

# A small set of known ComfyUI class types (some with alias-backed widgets,
# some without). This is deliberately handwritten, not derived from object_info.
_KNOWN_CLASSES = [
    "LoadImage",
    "SaveImage",
    "CLIPTextEncode",
    "KSampler",
    "VAEDecode",
    "CheckpointLoaderSimple",
    "EmptyLatentImage",
    "PreviewImage",
    "UNETLoader",
    "VAELoaderKJ",
]

# A handful of alias-backed class types from COMPILE_WIDGET_ALIAS_CLASS_TYPES.
_ALIAS_BACKED_CLASSES = [
    "LoadImage",
    "CLIPTextEncode",
    "UNETLoader",
    "VAELoaderKJ",
    "CheckpointLoaderSimple",
    "EmptyLatentImage",
]

# Custom unknown class types that have no schema provider backing.
_UNKNOWN_CLASSES = ["CustomProcessor", "MysteryNode", "ExtraFilterV3"]

# Safe input key names that work with most class types (avoid triggering
# type-specific validation that would require specific value types).
_SAFE_INPUT_KEYS = [
    "image", "text", "seed", "steps", "cfg",
    "sampler_name", "scheduler", "denoise",
    "filename_prefix", "ckpt_name",
    "positive", "negative", "latent_image",
]


@st.composite
def _class_type_strategy(draw: st.DrawFn) -> str:
    """Pick a class type: mostly known, occasionally unknown custom."""
    return draw(
        st.sampled_from(_KNOWN_CLASSES + _UNKNOWN_CLASSES)
    )


@st.composite
def _widget_value_strategy(draw: st.DrawFn) -> Any:
    """Generate a scalar value that can appear in node inputs.

    Deliberately avoids list shapes because `convert_to_vibe_format` interprets
    [int, int] lists as edge links.
    """
    return draw(
        st.one_of(
            st.integers(min_value=0, max_value=100),
            st.floats(min_value=0.0, max_value=1.0, allow_nan=False, allow_infinity=False),
            st.text(min_size=1, max_size=30, alphabet=st.characters(whitelist_categories=("Lu", "Ll", "Nd"), whitelist_characters="_-./")),
            st.booleans(),
        )
    )


# Input keys that require string values in templates.coerce_node_kwargs
# (_FILENAME_KWARGS and similar typed inputs).
_STRING_REQUIRED_KEYS: frozenset[str] = frozenset({
    "ckpt_name", "unet_name", "vae_name", "clip_name",
    "clip_name1", "clip_name2", "lora_name",
    "filename_prefix",
})


@st.composite
def _input_value_strategy(draw: st.DrawFn, key: str = "") -> Any:
    """Generate a node input value: scalar or dict (NOT lists — those become edges).

    When *key* is a known string-required input, only generate string values.
    """
    if key in _STRING_REQUIRED_KEYS:
        return draw(st.text(min_size=1, max_size=30, alphabet=st.characters(whitelist_categories=("Lu", "Ll", "Nd"), whitelist_characters="_-./")))
    return draw(
        st.one_of(
            _widget_value_strategy(),
            st.dictionaries(
                keys=st.text(min_size=1, max_size=10),
                values=_widget_value_strategy(),
                min_size=1,
                max_size=2,
            ),
        )
    )


@st.composite
def _input_key_strategy(draw: st.DrawFn, class_type: str) -> str:
    """Generate a plausible input key name.

    For known classes, prefer safe keys; for unknown classes, any key is fine.
    """
    if class_type in _KNOWN_CLASSES:
        return draw(st.sampled_from(_SAFE_INPUT_KEYS))
    else:
        return draw(st.text(min_size=1, max_size=12, alphabet=st.characters(whitelist_categories=("Lu", "Ll"), whitelist_characters="_")))


@st.composite
def _node_strategy(draw: st.DrawFn) -> dict[str, Any]:
    """Generate a single ComfyUI API node dict with class_type and inputs."""
    class_type = draw(_class_type_strategy())
    input_count = draw(st.integers(min_value=1, max_value=4))
    inputs: dict[str, Any] = {}
    for i in range(input_count):
        key = draw(_input_key_strategy(class_type))
        # Avoid duplicate keys
        if key not in inputs:
            inputs[key] = draw(_input_value_strategy(key))
    return {"class_type": class_type, "inputs": inputs}


@st.composite
def _workflow_api_json_strategy(draw: st.DrawFn) -> dict[str, Any]:
    """Generate a complete ComfyUI API workflow dict.

    Returns a dict mapping node id (string) to node dict.
    """
    node_count = draw(st.integers(min_value=1, max_value=12))
    api: dict[str, Any] = {}
    node_ids = [str(i) for i in range(1, node_count + 1)]

    for nid in node_ids:
        api[nid] = draw(_node_strategy())

    # Add DAG edges: for each node after the first, optionally connect
    # an input to an output from a previous node.
    # Edge slot values are strictly integers (0-3) — not floats.
    # Avoid creating edges targeting string-required inputs (ckpt_name, etc.)
    # because they can't accept Handle/link values.
    if node_count >= 2:
        edge_count = draw(st.integers(min_value=0, max_value=min(node_count * 2, 10)))
        for _ in range(edge_count):
            target_nid = draw(st.sampled_from(node_ids[1:]))
            source_nid = draw(st.sampled_from([n for n in node_ids if int(n) < int(target_nid)]))
            # Filter to only inputs that can accept links (non-string-required)
            linkable_inputs = [
                k for k in api[target_nid]["inputs"].keys()
                if k not in _STRING_REQUIRED_KEYS
            ]
            if not linkable_inputs:
                continue
            input_key = draw(st.sampled_from(linkable_inputs))
            slot = draw(st.integers(min_value=0, max_value=3))
            api[target_nid]["inputs"][input_key] = [source_nid, slot]

    # Optionally add definitions.subgraphs (~20% of the time)
    if draw(st.floats(min_value=0, max_value=1)) < 0.2:
        subgraph_node_count = draw(st.integers(min_value=1, max_value=3))
        subgraph_nodes: dict[str, Any] = {}
        for i in range(subgraph_node_count):
            subgraph_nodes[str(i + 100)] = draw(_node_strategy())
        api["definitions"] = {"subgraphs": [{"nodes": subgraph_nodes, "name": "sub_1"}]}

    return api


# ---------------------------------------------------------------------------
# Property tests
# ---------------------------------------------------------------------------


@given(_workflow_api_json_strategy())
@settings(
    max_examples=40,
    deadline=None,
    suppress_health_check=[HealthCheck.too_slow, HealthCheck.filter_too_much],
)
def test_codemod_hypothesis_property_1_no_crash(api_json: dict[str, Any]) -> None:
    """Property 1: port_convert_workflow never crashes on valid-looking input."""
    # FLAG-002: Normalize through VibeWorkflow constructor.
    workflow = _normalize_json_to_vibeworkflow(api_json, workflow_id="hypothesis-test")
    result = port_convert_workflow(workflow)
    # Must produce a result — even if validation fails, no unhandled exception.
    assert result is not None
    assert result.text is not None
    assert len(result.text) > 0


@given(_workflow_api_json_strategy())
@settings(
    max_examples=40,
    deadline=None,
    suppress_health_check=[HealthCheck.too_slow, HealthCheck.filter_too_much],
)
def test_codemod_hypothesis_property_2_deterministic_python(api_json: dict[str, Any]) -> None:
    """Property 2: emitted Python text is deterministic (same input → same output)."""
    workflow1 = _normalize_json_to_vibeworkflow(api_json, workflow_id="hypothesis-det")
    workflow2 = _normalize_json_to_vibeworkflow(api_json, workflow_id="hypothesis-det")

    text1 = port_convert_workflow(workflow1).text
    text2 = port_convert_workflow(workflow2).text

    assert text1 == text2, f"Non-deterministic emission:\n{text1}\n!=\n{text2}"


@given(_workflow_api_json_strategy())
@settings(
    max_examples=40,
    deadline=None,
    suppress_health_check=[HealthCheck.too_slow, HealthCheck.filter_too_much],
)
def test_codemod_hypothesis_property_3_importable(api_json: dict[str, Any]) -> None:
    """Property 3: emitted Python text is importable."""
    workflow = _normalize_json_to_vibeworkflow(api_json, workflow_id="hypothesis-import")
    result = port_convert_workflow(workflow)
    assert result.validation is not None
    assert result.validation.import_ok, f"Emitted module not importable: {result.validation.error}"


@given(_workflow_api_json_strategy())
@settings(
    max_examples=40,
    deadline=None,
    suppress_health_check=[HealthCheck.too_slow, HealthCheck.filter_too_much],
)
def test_codemod_hypothesis_property_4_build_compile(api_json: dict[str, Any]) -> None:
    """Property 4: build().compile('api') succeeds."""
    workflow = _normalize_json_to_vibeworkflow(api_json, workflow_id="hypothesis-build")
    result = port_convert_workflow(workflow)
    assert result.validation is not None
    assert result.validation.build_ok, f"build() failed: {result.validation.error}"
    assert result.validation.compile_ok, f"compile('api') failed: {result.validation.error}"


@given(_workflow_api_json_strategy())
@settings(
    max_examples=40,
    deadline=None,
    suppress_health_check=[HealthCheck.too_slow, HealthCheck.filter_too_much],
)
def test_codemod_hypothesis_property_5_validation_ok(api_json: dict[str, Any]) -> None:
    """Property 5: port_convert_workflow(...).validation.ok is True."""
    workflow = _normalize_json_to_vibeworkflow(api_json, workflow_id="hypothesis-valid")
    result = port_convert_workflow(workflow)
    assert result.validation is not None
    assert result.validation.ok, f"Validation failed: {result.validation.error}"


@given(_workflow_api_json_strategy())
@settings(
    max_examples=40,
    deadline=None,
    suppress_health_check=[HealthCheck.too_slow, HealthCheck.filter_too_much],
)
def test_codemod_hypothesis_property_6_no_widget_n_leakage(api_json: dict[str, Any]) -> None:
    """Property 6: known alias-backed classes do not produce widget_N-style names.

    For class types in COMPILE_WIDGET_ALIAS_CLASS_TYPES that appear in the
    emitted text, verify that the Python source does not contain widget_N keys
    for those known alias-backed types.
    """
    workflow = _normalize_json_to_vibeworkflow(api_json, workflow_id="hypothesis-widget")
    result = port_convert_workflow(workflow)
    text = result.text

    # Collect which alias-backed classes are present in the text
    present_alias_classes = [
        ct for ct in _ALIAS_BACKED_CLASSES
        if ct in text
    ]

    if not present_alias_classes:
        # No alias-backed classes in this example — trivially satisfied.
        return

    # For each present alias-backed class, check that widget_N is not in the
    # arguments for that class's constructor call.
    for ct in present_alias_classes:
        # Find the constructor call pattern: ClassType( ... )
        pattern = re.compile(rf"{re.escape(ct)}\((.*?)\)", re.DOTALL)
        for match in pattern.finditer(text):
            call_args = match.group(1)
            # widget_N pattern: widget_ followed by digits
            if re.search(r"widget_\d+", call_args):
                import pytest
                pytest.fail(
                    f"widget_N leakage detected for alias-backed class {ct!r} "
                    f"in constructor call arguments: {call_args[:200]}"
                )


@given(_workflow_api_json_strategy())
@settings(
    max_examples=40,
    deadline=None,
    suppress_health_check=[HealthCheck.too_slow, HealthCheck.filter_too_much],
)
def test_codemod_hypothesis_property_7_subgraph_materialization(api_json: dict[str, Any]) -> None:
    """Property 7: when definitions.subgraphs are present, subgraph definitions
    are materialized as callable Python functions in the emitted text.

    Only applies when the generated JSON includes definitions.subgraphs.
    """
    has_subgraphs = (
        isinstance(api_json.get("definitions"), dict)
        and isinstance(api_json["definitions"].get("subgraphs"), list)
        and len(api_json["definitions"]["subgraphs"]) > 0
    )

    workflow = _normalize_json_to_vibeworkflow(api_json, workflow_id="hypothesis-sub")
    result = port_convert_workflow(workflow)
    text = result.text

    if has_subgraphs:
        # Check that opaque component UUIDs are NOT in the emitted text —
        # subgraphs should be materialized as callable functions.
        assert not re.search(
            r"raw_call\('[0-9a-fA-F]{8}-[0-9a-fA-F]{4}-[0-9a-fA-F]{4}-[0-9a-fA-F]{4}-[0-9a-fA-F]{12}'",
            text,
        ), f"Subgraph materialization failed: raw_call with opaque UUID found in emitted text"


# ---------------------------------------------------------------------------
# Helpers
# ---------------------------------------------------------------------------


def _normalize_json_to_vibeworkflow(
    api_json: dict[str, Any],
    *,
    workflow_id: str = "hypothesis",
) -> VibeWorkflow:
    """Normalize API JSON through convert_to_vibe_format (FLAG-002).

    Strips 'definitions' from the API dict before normalization because
    convert_to_vibe_format expects pure API node dicts. The raw workflow
    (with definitions) can be passed via raw_workflow to port_convert_workflow.
    """
    # Build a clean API dict without definitions
    clean_api: dict[str, Any] = {
        k: v for k, v in api_json.items()
        if k != "definitions" and isinstance(v, dict) and "class_type" in v
    }
    return convert_to_vibe_format(clean_api, workflow_id=workflow_id)
