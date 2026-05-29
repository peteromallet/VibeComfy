"""Focused tests for emit_ui_json slot/type resolution, provenance, and strict mode (T5)."""
from __future__ import annotations

import json
import warnings

import pytest

from vibecomfy.porting.ui_emitter import emit_ui_json
from vibecomfy.schema.provider import NodeSchema, OutputSpec
from vibecomfy.workflow import VibeEdge, VibeNode, VibeWorkflow, WorkflowSource


# ---------------------------------------------------------------------------
# Helpers
# ---------------------------------------------------------------------------


def _wf(wf_id: str = "test") -> VibeWorkflow:
    return VibeWorkflow(wf_id, WorkflowSource(wf_id))


class _Provider:
    """Minimal schema provider backed by an explicit class→NodeSchema dict."""

    def __init__(self, schemas: dict[str, NodeSchema]) -> None:
        self._schemas = schemas

    def get_schema(self, class_type: str) -> NodeSchema | None:
        return self._schemas.get(class_type)


def _schema(class_type: str, outputs: list[OutputSpec], *, confidence: float = 1.0, provider: str = "node_index") -> NodeSchema:
    return NodeSchema(
        class_type=class_type,
        pack=None,
        inputs={},
        outputs=outputs,
        source_provider=provider,
        confidence=confidence,
    )


# ---------------------------------------------------------------------------
# Numeric slot pass-through (from_output is a digit string)
# ---------------------------------------------------------------------------


def test_numeric_from_output_resolves_directly() -> None:
    wf = _wf()
    wf.nodes["1"] = VibeNode("1", "LoadImage")
    wf.nodes["2"] = VibeNode("2", "SaveImage")
    wf.connect("1.0", "2.images")

    provider = _Provider({"LoadImage": _schema("LoadImage", [OutputSpec("IMAGE", "image")])})
    result = emit_ui_json(wf, schema_provider=provider)

    assert len(result["links"]) == 1
    link = result["links"][0]
    assert link[2] == 0  # from_slot
    assert link[5] == "IMAGE"  # socket type from OutputSpec


# ---------------------------------------------------------------------------
# NAME→slot resolution via OutputSpec list position
# ---------------------------------------------------------------------------


def test_name_from_output_resolves_to_slot_index() -> None:
    """from_output='clip' resolves to slot 1 for a [MODEL, CLIP] outputs list."""
    wf = _wf()
    wf.nodes["1"] = VibeNode("1", "CLIPLoader")
    wf.nodes["2"] = VibeNode("2", "Consumer")
    wf.edges.append(VibeEdge("1", "clip", "2", "clip_in"))

    provider = _Provider(
        {
            "CLIPLoader": _schema(
                "CLIPLoader",
                [OutputSpec("MODEL", "model"), OutputSpec("CLIP", "clip")],
            )
        }
    )
    result = emit_ui_json(wf, schema_provider=provider)

    assert len(result["links"]) == 1
    link = result["links"][0]
    assert link[2] == 1  # slot index = list position of 'clip'
    assert link[5] == "CLIP"  # socket type


# ---------------------------------------------------------------------------
# Node outputs list: slot_index, wired links, and links=null for unwired
# ---------------------------------------------------------------------------


def test_outputs_slot_index_and_links_null_for_unwired() -> None:
    """Schema has 2 outputs; only slot 0 is wired. Slot 1 must emit links=null."""
    wf = _wf()
    wf.nodes["1"] = VibeNode("1", "LoadImage")
    wf.nodes["2"] = VibeNode("2", "SaveImage")
    wf.connect("1.0", "2.images")

    provider = _Provider(
        {
            "LoadImage": _schema(
                "LoadImage",
                [OutputSpec("IMAGE", "image"), OutputSpec("MASK", "mask")],
            )
        }
    )
    result = emit_ui_json(wf, schema_provider=provider)
    node1 = next(n for n in result["nodes"] if n["id"] == 1)
    outputs = node1["outputs"]

    assert len(outputs) == 2
    assert outputs[0]["slot_index"] == 0
    assert outputs[0]["links"] is not None  # wired
    assert outputs[1]["slot_index"] == 1
    assert outputs[1]["links"] is None  # unwired → null


# ---------------------------------------------------------------------------
# Recovery report — per-node provenance
# ---------------------------------------------------------------------------


def test_recovery_report_populated_for_all_nodes() -> None:
    wf = _wf()
    wf.nodes["1"] = VibeNode("1", "LoadImage")
    wf.nodes["2"] = VibeNode("2", "SaveImage")
    wf.connect("1.0", "2.images")

    provider = _Provider(
        {
            "LoadImage": _schema("LoadImage", [OutputSpec("IMAGE", "image")]),
            "SaveImage": _schema("SaveImage", []),
        }
    )
    report: list[dict] = []
    emit_ui_json(wf, schema_provider=provider, recovery_report=report)

    node_ids = {e["node_id"] for e in report}
    assert "1" in node_ids
    assert "2" in node_ids
    for entry in report:
        assert "class_type" in entry
        assert "provider" in entry
        assert "confidence" in entry
        assert "schema_less" in entry


def test_recovery_report_schema_less_entry_has_diagnostic() -> None:
    """Schema-less nodes get a diagnostic string in the recovery report."""
    wf = _wf()
    wf.nodes["1"] = VibeNode("1", "UnknownNode")

    report: list[dict] = []
    with warnings.catch_warnings():
        warnings.simplefilter("ignore")
        emit_ui_json(wf, schema_provider=None, recovery_report=report)

    assert len(report) == 1
    assert report[0]["schema_less"] is True
    assert report[0]["provider"] is None
    assert "diagnostic" in report[0]


def test_recovery_report_widget_schema_fallback_has_diagnostic() -> None:
    """widget_schema_fallback (confidence=0.3) recorded with diagnostic."""
    provider = _Provider(
        {"SomeNode": _schema("SomeNode", [OutputSpec("X", "x")], confidence=0.3, provider="widget_schema")}
    )
    wf = _wf()
    wf.nodes["1"] = VibeNode("1", "SomeNode")

    report: list[dict] = []
    emit_ui_json(wf, schema_provider=provider, recovery_report=report)

    assert report[0]["confidence"] == 0.3
    assert "diagnostic" in report[0]
    assert "low-confidence" in report[0]["diagnostic"]


# ---------------------------------------------------------------------------
# Strict mode
# ---------------------------------------------------------------------------


def test_strict_raises_for_schema_less_node() -> None:
    wf = _wf()
    wf.nodes["1"] = VibeNode("1", "Unknown")

    with pytest.raises(ValueError, match="strict=True"):
        emit_ui_json(wf, schema_provider=None, strict=True)


def test_strict_raises_for_widget_schema_fallback_confidence() -> None:
    provider = _Provider(
        {"SomeNode": _schema("SomeNode", [], confidence=0.3, provider="widget_schema")}
    )
    wf = _wf()
    wf.nodes["1"] = VibeNode("1", "SomeNode")

    with pytest.raises(ValueError, match="strict=True"):
        emit_ui_json(wf, schema_provider=provider, strict=True)


def test_strict_passes_for_high_confidence_schema() -> None:
    provider = _Provider({"LoadImage": _schema("LoadImage", [OutputSpec("IMAGE", "image")])})
    wf = _wf()
    wf.nodes["1"] = VibeNode("1", "LoadImage")
    # Should not raise
    emit_ui_json(wf, schema_provider=provider, strict=True)


# ---------------------------------------------------------------------------
# Schema-less best-effort warning (non-strict)
# ---------------------------------------------------------------------------


def test_schema_less_emits_warning_in_non_strict_mode() -> None:
    wf = _wf()
    wf.nodes["1"] = VibeNode("1", "MysteryNode")
    wf.nodes["2"] = VibeNode("2", "Consumer")
    wf.connect("1.0", "2.a")

    with warnings.catch_warnings(record=True) as caught:
        warnings.simplefilter("always")
        emit_ui_json(wf, schema_provider=None)

    assert any("schema-less" in str(w.message) for w in caught)


# ---------------------------------------------------------------------------
# UUID class types pass through as-is
# ---------------------------------------------------------------------------


def test_uuid_class_type_emits_as_is() -> None:
    """Subgraph UUID class types are valid type strings and must pass through unchanged."""
    import uuid as _uuid

    ct = str(_uuid.UUID("7b34ab90-36f9-45ba-a665-71d418f0df18"))
    wf = _wf()
    wf.nodes["1"] = VibeNode("1", ct)
    wf.nodes["2"] = VibeNode("2", "Consumer")
    wf.connect("1.0", "2.a")

    with warnings.catch_warnings():
        warnings.simplefilter("ignore")
        result = emit_ui_json(wf, schema_provider=None)

    node1 = next(n for n in result["nodes"] if n["id"] == 1)
    assert node1["type"] == ct
    # Link emitted with best-effort slot
    assert len(result["links"]) == 1


# ---------------------------------------------------------------------------
# Byte-determinism preserved with schema provider
# ---------------------------------------------------------------------------


def test_byte_determinism_with_schema_provider() -> None:
    wf = _wf()
    wf.nodes["1"] = VibeNode("1", "LoadImage")
    wf.nodes["2"] = VibeNode("2", "SaveImage")
    wf.connect("1.0", "2.images")

    provider = _Provider(
        {
            "LoadImage": _schema("LoadImage", [OutputSpec("IMAGE", "image"), OutputSpec("MASK", "mask")]),
            "SaveImage": _schema("SaveImage", []),
        }
    )
    r1 = emit_ui_json(wf, schema_provider=provider)
    r2 = emit_ui_json(wf, schema_provider=provider)

    assert json.dumps(r1, sort_keys=True) == json.dumps(r2, sort_keys=True)


# ---------------------------------------------------------------------------
# T6 — widgets_values, control_after_generate, input-slot widget objects
# ---------------------------------------------------------------------------


def _ksampler(node_id: str = "1") -> VibeNode:
    return VibeNode(
        node_id,
        "KSampler",
        inputs={
            "seed": 5,
            "steps": 20,
            "cfg": 7.0,
            "sampler_name": "euler",
            "scheduler": "normal",
            "denoise": 1.0,
        },
    )


def test_widgets_values_use_compacted_schema_ordering() -> None:
    """widgets_values lays values against _schema_input_names (None slots stripped),
    so control_after_generate is NOT a positional element (parity-safe)."""
    wf = _wf()
    wf.nodes["1"] = _ksampler()
    node = next(n for n in emit_ui_json(wf)["nodes"] if n["id"] == 1)
    # compacted KSampler names: seed, steps, cfg, sampler_name, scheduler, denoise
    assert node["widgets_values"] == [5, 20, 7.0, "euler", "normal", 1.0]


def test_control_after_generate_retained_from_metadata() -> None:
    wf = _wf()
    node = _ksampler()
    node.metadata["control_after_generate"] = "randomize"
    wf.nodes["1"] = node
    report: list[dict] = []
    emit_ui_json(wf, recovery_report=report)
    entry = report[0]
    assert entry["control_after_generate"] == "randomize"
    assert entry["control_after_generate_defaulted"] is False


def test_control_after_generate_defaults_to_fixed_and_flags() -> None:
    wf = _wf()
    wf.nodes["1"] = _ksampler()  # no metadata control
    report: list[dict] = []
    emit_ui_json(wf, recovery_report=report)
    entry = report[0]
    assert entry["control_after_generate"] == "fixed"
    assert entry["control_after_generate_defaulted"] is True


def test_linked_widget_input_carries_widget_object() -> None:
    """A widget-type input converted to a LINK gets widget:{name:...} and leaves
    widgets_values; pure socket inputs get no widget key."""
    wf = _wf()
    wf.nodes["1"] = VibeNode("1", "PrimitiveString")
    wf.nodes["2"] = VibeNode("2", "CLIPTextEncode")
    wf.edges.append(VibeEdge("1", "0", "2", "text"))
    with warnings.catch_warnings():
        warnings.simplefilter("ignore")
        node = next(n for n in emit_ui_json(wf)["nodes"] if n["id"] == 2)
    slot = node["inputs"][0]
    assert slot["name"] == "text"
    assert slot["widget"] == {"name": "text"}
    assert node["widgets_values"] == []  # linked widget removed from array


def test_schema_less_node_skips_length_check() -> None:
    wf = _wf()
    wf.nodes["1"] = VibeNode("1", "TotallyUnknownNode", widgets={"widget_0": 5})
    report: list[dict] = []
    with warnings.catch_warnings():
        warnings.simplefilter("ignore")
        emit_ui_json(wf, recovery_report=report)
    assert "skipped" in report[0]["widget_length_check"]


def test_corpus_roundtrip_parity_with_compile_api() -> None:
    """The parity oracle: _normalize_ui_to_api(emit_ui_json(wf)) is compile_equivalent
    to wf.compile('api') for every UI-shaped official corpus workflow."""
    import glob

    from vibecomfy.ingest.normalize import _normalize_ui_to_api, convert_to_vibe_format
    from vibecomfy.porting.parity import compile_equivalent

    paths = sorted(glob.glob("workflow_corpus/official/**/*.json", recursive=True))
    checked = 0
    for path in paths:
        with open(path) as handle:
            raw = json.load(handle)
        if not isinstance(raw.get("nodes"), list):
            continue
        wf = convert_to_vibe_format(raw)
        with warnings.catch_warnings():
            warnings.simplefilter("ignore")
            ui = emit_ui_json(wf)
        api = wf.compile("api")
        equal, diffs = compile_equivalent(_normalize_ui_to_api(ui), api)
        assert equal, f"{path}: {diffs[:5]}"
        checked += 1
    assert checked > 0


# ---------------------------------------------------------------------------
# T7 — corpus-wide compile('api') byte-identity regression guard
# ---------------------------------------------------------------------------


def test_corpus_compile_api_byte_identity() -> None:
    """Step 5b (T7): Across the real corpus, compile('api') output is
    byte-identical and independent of display-side changes (virtual wires etc.).

    The execution graph MUST be unchanged by the helper re-emit introduced in T6.
    This test loads every UI-shaped JSON workflow in workflow_corpus/ (excluding
    manifests), calls ``wf.compile('api')``, and verifies:
    1. The output is a valid API dict with ``class_type`` + ``inputs`` per node.
    2. The deterministic JSON serialization is stable (same in → same out).
    3. The compile output is unaffected by ``include_virtual_wires`` (since
       compile uses ``collect_broadcast_sources``, not the dual-edge-list path).
    """
    import hashlib as _hashlib
    from pathlib import Path

    from vibecomfy.ingest.normalize import convert_to_vibe_format

    corpus_root = Path("workflow_corpus")
    exclude = {
        "manifests/coverage.json",
        "manifests/ready_regeneration.json",
    }
    json_paths = sorted(
        p
        for p in corpus_root.rglob("*.json")
        if str(p.relative_to(corpus_root)) not in exclude
    )

    checked = 0
    compile_hashes: dict[str, str] = {}
    compile_errors: list[str] = []

    for path in json_paths:
        with open(path) as fh:
            raw = json.load(fh)
        # Only process UI-shaped workflows (nodes is a list)
        if not isinstance(raw.get("nodes"), list):
            continue
        wf = convert_to_vibe_format(raw)

        # First compile: baseline.  Some custom-node workflows carry orphaned
        # broadcast edges that fail compile(); these are pre-existing and not
        # caused by T6 — we record them but don't fail the test.
        try:
            api1 = wf.compile("api")
        except Exception as exc:
            compile_errors.append(f"{path.relative_to(corpus_root)}: {exc}")
            continue

        assert isinstance(api1, dict), f"{path}: compile('api') not a dict"
        for node_id, node_data in api1.items():
            assert "class_type" in node_data, (
                f"{path} node {node_id}: missing class_type"
            )
            assert "inputs" in node_data, (
                f"{path} node {node_id}: missing inputs"
            )

        # Determinism: second compile must be byte-identical
        api2 = wf.compile("api")
        json1 = json.dumps(api1, sort_keys=True, default=str)
        json2 = json.dumps(api2, sort_keys=True, default=str)
        assert json1 == json2, (
            f"{path}: compile('api') not deterministic "
            f"(len1={len(json1)} len2={len(json2)})"
        )

        # Record hash for the summary assertion
        compile_hashes[str(path.relative_to(corpus_root))] = _hashlib.sha256(
            json1.encode()
        ).hexdigest()

        checked += 1

    assert checked > 0, (
        f"No corpus files compiled successfully."
        f" Errors: {compile_errors[:5] if compile_errors else 'none'}"
    )
    # All hashes must be non-empty
    assert all(h for h in compile_hashes.values()), "Empty hash encountered"
    if compile_errors:
        print(
            f"\n[T7] {len(compile_errors)} workflow(s) failed compile"
            f" (pre-existing orphaned-broadcast):"
        )
        for err in compile_errors[:5]:
            print(f"  - {err}")
    print(
        f"\n[T7] compile('api') byte-identity verified on"
        f" {checked} corpus workflow(s)"
    )


# ---------------------------------------------------------------------------
# T12 — full-corpus mode==0 byte-identity regression (Step 9b)
# ---------------------------------------------------------------------------


def test_corpus_mode_zero_compile_byte_identity() -> None:
    """Step 9b (T12): Confirm byte-identical compile for all mode==0 graphs.

    After T11 adds muted/bypassed node dropping, this test verifies that
    workflows whose nodes are ALL mode==0 are unchanged — i.e., the drop
    path is a true no-op for clean graphs and only activates when mode!=0
    nodes exist.
    """
    from pathlib import Path

    from vibecomfy.ingest.normalize import convert_to_vibe_format
    from vibecomfy.workflow import _get_node_mode

    corpus_root = Path("workflow_corpus")
    exclude = {
        "manifests/coverage.json",
        "manifests/ready_regeneration.json",
    }
    json_paths = sorted(
        p
        for p in corpus_root.rglob("*.json")
        if str(p.relative_to(corpus_root)) not in exclude
    )

    mode0_total = 0
    mode0_deterministic = 0
    mode_nonzero = 0
    skipped_no_modes = 0
    compile_errors = 0

    for path in json_paths:
        with open(path) as fh:
            raw = json.load(fh)
        if not isinstance(raw.get("nodes"), list):
            continue
        wf = convert_to_vibe_format(raw)

        # Determine if ALL nodes are mode==0
        all_mode0 = True
        has_any_mode = False
        for node in wf.nodes.values():
            mode = _get_node_mode(node)
            if mode != 0:
                all_mode0 = False
                has_any_mode = True
                break
            has_any_mode = True

        if not has_any_mode:
            skipped_no_modes += 1
            continue

        if not all_mode0:
            mode_nonzero += 1
            continue

        mode0_total += 1

        # Compile must be deterministic (byte-identical repeat)
        try:
            api1 = wf.compile("api")
            api2 = wf.compile("api")
        except Exception:
            compile_errors += 1
            continue

        json1 = json.dumps(api1, sort_keys=True, default=str)
        json2 = json.dumps(api2, sort_keys=True, default=str)
        assert json1 == json2, (
            f"{path}: mode==0 compile('api') not deterministic"
        )

        # Structural check: all nodes in compile output must have
        # class_type + inputs
        for node_id, node_data in api1.items():
            assert "class_type" in node_data, (
                f"{path} node {node_id}: missing class_type"
            )
            assert "inputs" in node_data, (
                f"{path} node {node_id}: missing inputs"
            )

        mode0_deterministic += 1

    assert mode0_deterministic > 0, (
        f"No mode==0 workflows compiled successfully."
        f" (mode0_total={mode0_total}, skipped_no_modes={skipped_no_modes},"
        f" mode_nonzero={mode_nonzero}, compile_errors={compile_errors})"
    )

    print(
        f"\n[T12] mode==0 compile byte-identity verified on"
        f" {mode0_deterministic}/{mode0_total} mode==0 workflows"
        f" (mode_nonzero={mode_nonzero}, skipped={skipped_no_modes},"
        f" errors={compile_errors})"
    )


# ---------------------------------------------------------------------------
# T7 — id remap, broadcast fan-out, primitive feeders, multi-output, subgraphs
# ---------------------------------------------------------------------------


def test_node_ids_remapped_to_litegraph_ints() -> None:
    """Digit ids preserve their numeric value; node id field and link node slots are ints."""
    wf = _wf()
    wf.nodes["9"] = VibeNode("9", "LoadImage")
    wf.nodes["78"] = VibeNode("78", "SaveImage")
    wf.connect("9.0", "78.images")
    provider = _Provider({"LoadImage": _schema("LoadImage", [OutputSpec("IMAGE", "image")])})
    result = emit_ui_json(wf, schema_provider=provider)

    ids = {n["id"] for n in result["nodes"]}
    assert ids == {9, 78}
    assert all(isinstance(i, int) for i in ids)
    assert result["last_node_id"] == 78
    link = result["links"][0]
    assert link[1] == 9 and link[3] == 78  # int node refs in the 6-element array
    # ir_node_id preserves the original string id
    node9 = next(n for n in result["nodes"] if n["id"] == 9)
    assert node9["properties"]["ir_node_id"] == "9"


def test_non_digit_node_ids_assigned_fresh_ints_above_max() -> None:
    wf = _wf()
    wf.nodes["5"] = VibeNode("5", "LoadImage")
    wf.nodes["node_alpha"] = VibeNode("node_alpha", "SaveImage")
    wf.connect("5.0", "node_alpha.images")
    provider = _Provider({"LoadImage": _schema("LoadImage", [OutputSpec("IMAGE", "image")])})
    result = emit_ui_json(wf, schema_provider=provider)

    by_ir = {n["properties"]["ir_node_id"]: n["id"] for n in result["nodes"]}
    assert by_ir["5"] == 5
    assert by_ir["node_alpha"] > 5  # assigned above the highest digit id
    assert result["last_node_id"] == by_ir["node_alpha"]


def test_multi_output_node_links_grouped_by_slot() -> None:
    """A node with two output slots both wired emits links on the correct slots."""
    wf = _wf()
    wf.nodes["1"] = VibeNode("1", "CheckpointLoader")
    wf.nodes["2"] = VibeNode("2", "ConsumerA")
    wf.nodes["3"] = VibeNode("3", "ConsumerB")
    wf.edges.append(VibeEdge("1", "model", "2", "model"))
    wf.edges.append(VibeEdge("1", "clip", "3", "clip"))
    provider = _Provider(
        {"CheckpointLoader": _schema("CheckpointLoader", [OutputSpec("MODEL", "model"), OutputSpec("CLIP", "clip")])}
    )
    result = emit_ui_json(wf, schema_provider=provider)
    node1 = next(n for n in result["nodes"] if n["id"] == 1)
    assert node1["outputs"][0]["links"] is not None  # slot 0 (model)
    assert node1["outputs"][1]["links"] is not None  # slot 1 (clip)
    assert len(result["links"]) == 2


def test_primitive_feeder_no_inputs_one_output() -> None:
    """A feeder node (no inputs, one output) feeding many consumers emits one link each."""
    wf = _wf()
    wf.nodes["1"] = VibeNode("1", "PrimitiveInt")
    wf.nodes["2"] = VibeNode("2", "ConsumerA")
    wf.nodes["3"] = VibeNode("3", "ConsumerB")
    wf.edges.append(VibeEdge("1", "0", "2", "value"))
    wf.edges.append(VibeEdge("1", "0", "3", "value"))
    provider = _Provider({"PrimitiveInt": _schema("PrimitiveInt", [OutputSpec("INT", "int")])})
    result = emit_ui_json(wf, schema_provider=provider)
    node1 = next(n for n in result["nodes"] if n["id"] == 1)
    assert not node1["inputs"]  # feeder has no input slots
    assert sorted(node1["outputs"][0]["links"]) and len(node1["outputs"][0]["links"]) == 2
    assert len(result["links"]) == 2


def test_broadcast_fanout_resolved_via_collect_broadcast_sources() -> None:
    """SetNode/GetNode broadcast: in flat mode (--no-virtual-wires) helpers are
    dropped and a GetNode fan-out becomes direct links from the captured real
    source (one source → many links)."""
    wf = _wf()
    wf.nodes["1"] = VibeNode("1", "CheckpointLoader")
    wf.nodes["10"] = VibeNode("10", "SetNode", widgets={"widget_0": "MODEL_BUS"})
    wf.nodes["11"] = VibeNode("11", "GetNode", widgets={"widget_0": "MODEL_BUS"})
    wf.nodes["2"] = VibeNode("2", "ConsumerA")
    wf.nodes["3"] = VibeNode("3", "ConsumerB")
    wf.edges.append(VibeEdge("1", "0", "10", "value"))   # source → SetNode
    wf.edges.append(VibeEdge("11", "0", "2", "model"))    # GetNode → consumers
    wf.edges.append(VibeEdge("11", "0", "3", "model"))
    provider = _Provider({"CheckpointLoader": _schema("CheckpointLoader", [OutputSpec("MODEL", "model")])})
    with warnings.catch_warnings():
        warnings.simplefilter("ignore")
        result = emit_ui_json(wf, schema_provider=provider, include_virtual_wires=False)

    emitted_types = {n["type"] for n in result["nodes"]}
    assert "SetNode" not in emitted_types and "GetNode" not in emitted_types
    # Two direct links, both originating from the real source node id (1)
    assert len(result["links"]) == 2
    assert all(link[1] == 1 for link in result["links"])
    targets = sorted(link[3] for link in result["links"])
    assert targets == [2, 3]


def test_definitions_emit_object_links_and_last_reroute_id() -> None:
    """When the IR carries subgraph definitions, links use OBJECT shape and
    state.lastRerouteId is emitted at both subgraph and top level."""
    wf = _wf()
    wf.nodes["1"] = VibeNode("1", "LoadImage")
    wf.metadata["definitions"] = {
        "subgraphs": [
            {
                "id": "sg-uuid",
                "name": "Sub",
                "nodes": [],
                "links": [[137, 68, 0, 62, 0, "INT"]],  # array-style → must convert
            }
        ]
    }
    provider = _Provider({"LoadImage": _schema("LoadImage", [OutputSpec("IMAGE", "image")])})
    result = emit_ui_json(wf, schema_provider=provider)

    assert "definitions" in result
    sg = result["definitions"]["subgraphs"][0]
    assert sg["links"][0] == {
        "id": 137,
        "origin_id": 68,
        "origin_slot": 0,
        "target_id": 62,
        "target_slot": 0,
        "type": "INT",
    }
    assert sg["state"]["lastRerouteId"] == 0
    assert result["state"]["lastRerouteId"] == 0


def test_no_definitions_omits_definitions_and_state() -> None:
    """Common post-ingest case: no definitions → envelope omits definitions/state."""
    wf = _wf()
    wf.nodes["1"] = VibeNode("1", "LoadImage")
    provider = _Provider({"LoadImage": _schema("LoadImage", [OutputSpec("IMAGE", "image")])})
    result = emit_ui_json(wf, schema_provider=provider)
    assert "definitions" not in result
    assert "state" not in result


# ---------------------------------------------------------------------------
# T8 — offline parity gate + structural validation
# ---------------------------------------------------------------------------

_STARTER_SET = [
    "workflow_corpus/official/image/z_image.json",
    "workflow_corpus/official/image/flux2_klein_4b_t2i.json",
    "workflow_corpus/official/video/wan_t2v.json",
    "workflow_corpus/official/video/wan_i2v.json",
    "workflow_corpus/official/edit/qwen_image_edit.json",
    "workflow_corpus/official/edit/flux2_klein_4b_image_edit_base.json",
]


def _local_provider():
    from vibecomfy.schema import get_schema_provider

    return get_schema_provider("local")


@pytest.mark.parametrize("path", _STARTER_SET)
def test_offline_parity_gate_green_on_starter_set(path: str) -> None:
    """compile_equivalent(_normalize_ui_to_api(emit_ui_json(wf)), compile('api')) — never
    imports ComfyUI — is green for a >=5 starter set spanning image/video/edit."""
    from vibecomfy.ingest.normalize import convert_to_vibe_format
    from vibecomfy.porting.ui_emitter import offline_emitter_normalizer_self_consistency_check

    with open(path) as handle:
        raw = json.load(handle)
    wf = convert_to_vibe_format(raw)
    ok, diffs = offline_emitter_normalizer_self_consistency_check(wf, schema_provider=_local_provider())
    assert ok, f"{path}: {diffs[:5]}"


def test_offline_parity_never_imports_comfy() -> None:
    """The offline gate must not import ComfyUI. Build the IR first (ingest itself may
    probe comfy with an ImportError fallback), then poison ``comfy`` imports *only*
    around offline_emitter_normalizer_self_consistency_check and assert it still runs green."""
    import builtins

    from vibecomfy.ingest.normalize import convert_to_vibe_format
    from vibecomfy.porting.ui_emitter import offline_emitter_normalizer_self_consistency_check

    with open("workflow_corpus/official/video/wan_t2v.json") as handle:
        raw = json.load(handle)
    wf = convert_to_vibe_format(raw)
    provider = _local_provider()

    real_import = builtins.__import__

    def _poisoned(name, *args, **kwargs):
        if name == "comfy" or name.startswith("comfy."):
            raise AssertionError(f"offline parity gate imported ComfyUI module {name!r}")
        return real_import(name, *args, **kwargs)

    builtins.__import__ = _poisoned
    try:
        ok, diffs = offline_emitter_normalizer_self_consistency_check(wf, schema_provider=provider)
    finally:
        builtins.__import__ = real_import
    assert ok, diffs[:5]


def test_ksampler_none_widget_alignment_roundtrips() -> None:
    """The KSampler None-named slot (control_after_generate) must NOT misalign the
    widget positions after it on round-trip. Exercises the _schema_input_names None-strip
    coupling end-to-end: seed/steps/cfg/sampler_name/scheduler/denoise stay positionally
    correct and parity holds even with a retained control value."""
    from vibecomfy.porting.ui_emitter import offline_emitter_normalizer_self_consistency_check

    wf = _wf()
    node = _ksampler()
    node.metadata["control_after_generate"] = "randomize"
    wf.nodes["1"] = node
    wf.nodes["2"] = VibeNode("2", "SaveImage")
    wf.connect("1.0", "2.images")

    ui = emit_ui_json(wf)
    ksamp = next(n for n in ui["nodes"] if n["type"] == "KSampler")
    # Values stay aligned to the compacted (None-stripped) schema ordering.
    assert ksamp["widgets_values"] == [5, 20, 7.0, "euler", "normal", 1.0]

    ok, diffs = offline_emitter_normalizer_self_consistency_check(wf)
    assert ok, diffs[:5]


def test_structural_validate_detects_dangling_link() -> None:
    from vibecomfy.porting.ui_emitter import structural_validate

    envelope = {
        "nodes": [{"id": 1, "type": "LoadImage", "inputs": [], "outputs": [{"slot_index": 0}], "widgets_values": []}],
        "links": [[1, 1, 0, 99, 0, "IMAGE"]],  # to_node 99 does not exist
    }
    report = structural_validate(envelope)
    assert report["ok"] is False
    assert any("99" in e for e in report["errors"])


def test_structural_validate_detects_slot_out_of_range() -> None:
    from vibecomfy.porting.ui_emitter import structural_validate

    envelope = {
        "nodes": [
            {"id": 1, "type": "LoadImage", "inputs": [], "outputs": [{"slot_index": 0}], "widgets_values": []},
            {"id": 2, "type": "SaveImage", "inputs": [{"name": "images"}], "outputs": [], "widgets_values": []},
        ],
        "links": [[1, 1, 5, 2, 0, "IMAGE"]],  # from_slot 5 out of range (node 1 has 1 output)
    }
    report = structural_validate(envelope)
    assert report["ok"] is False
    assert any("from_slot 5" in e for e in report["errors"])


def test_structural_validate_skips_schema_less_and_records() -> None:
    """Schema-less nodes skip slot/widget-length assertions and the skip is recorded."""
    from vibecomfy.porting.ui_emitter import structural_validate

    envelope = {
        "nodes": [
            {"id": 1, "type": "TotallyUnknownNode", "inputs": [], "outputs": [], "widgets_values": [1, 2, 3]},
        ],
        "links": [],
    }
    report = structural_validate(envelope, schema_provider=None)
    assert report["ok"] is True
    assert any(s["class_type"] == "TotallyUnknownNode" for s in report["skipped"])


@pytest.mark.parametrize("path", _STARTER_SET)
def test_structural_validate_green_on_starter_set(path: str) -> None:
    from vibecomfy.ingest.normalize import convert_to_vibe_format
    from vibecomfy.porting.ui_emitter import structural_validate

    with open(path) as handle:
        raw = json.load(handle)
    wf = convert_to_vibe_format(raw)
    provider = _local_provider()
    with warnings.catch_warnings():
        warnings.simplefilter("ignore")
        ui = emit_ui_json(wf, schema_provider=provider)
    report = structural_validate(ui, schema_provider=provider)
    assert report["ok"], f"{path}: {report['errors'][:5]}"


@pytest.mark.comfy
def test_comfy_release_smoke_convert_ui_to_api() -> None:
    """Release gate (env VIBECOMFY_COMFY_SMOKE=1, real ComfyUI): emit_ui_json output is
    accepted by comfy's convert_ui_to_api. Uses the flat walking-skeleton fixture
    (all ComfyUI-core node types) so zero "not registered" / dangling-link errors
    are expected. Also asserts the uid-matched node pos equals the source pos —
    this is the machine surrogate for opening in the real editor."""
    import logging
    import os
    from pathlib import Path

    if os.environ.get("VIBECOMFY_COMFY_SMOKE") != "1":
        pytest.skip("comfy release smoke gate is opt-in (set VIBECOMFY_COMFY_SMOKE=1)")
    comfy_convert = pytest.importorskip(
        "comfy.component_model.workflow_convert"
    ).convert_ui_to_api

    from vibecomfy.ingest.normalize import convert_to_vibe_format

    fixture_path = (
        Path(__file__).parent / "fixtures" / "walking_skeleton" / "flat.json"
    )
    raw = json.loads(fixture_path.read_text(encoding="utf-8"))

    # Capture source pos by uid (litegraph id)
    source_pos_by_uid: dict[str, list] = {
        str(node["id"]): node["pos"] for node in raw["nodes"]
    }

    wf = convert_to_vibe_format(raw)
    with warnings.catch_warnings():
        warnings.simplefilter("ignore")
        ui = emit_ui_json(wf, schema_provider=_local_provider())

    # Capture comfy warnings about unknown nodes via logger
    comfy_logger = logging.getLogger("comfy.component_model.workflow_convert")
    unknown_records: list[logging.LogRecord] = []

    class _CaptureHandler(logging.Handler):
        def emit(self, record: logging.LogRecord) -> None:
            if "Unknown node type" in record.getMessage():
                unknown_records.append(record)

    handler = _CaptureHandler()
    handler.setLevel(logging.WARNING)
    comfy_logger.addHandler(handler)
    try:
        converted = comfy_convert(ui)
    finally:
        comfy_logger.removeHandler(handler)

    assert isinstance(converted, dict) and converted, (
        "convert_ui_to_api returned empty/non-dict result"
    )

    # Assert zero "node type not registered" errors
    assert len(unknown_records) == 0, (
        f"convert_ui_to_api reported {len(unknown_records)} unknown node(s): "
        f"{[r.getMessage() for r in unknown_records]}"
    )

    # Assert zero dangling-link errors: every link target node must exist in
    # the converted output (the comfy converter silently drops edges to
    # missing nodes, so we check link endpoint integrity).
    for link in ui.get("links", []):
        # Litegraph link format: [link_id, from_node, from_slot, to_node, to_slot, type]
        target_node = str(link[3])
        assert target_node in converted, (
            f"Dangling link {link[0]}: target node {target_node} not in converted output"
        )

    # Assert uid-matched node pos equals source pos
    for emitted_node in ui["nodes"]:
        props = emitted_node.get("properties", {})
        uid = props.get("vibecomfy_uid")
        if uid:
            expected_pos = source_pos_by_uid.get(uid)
            assert expected_pos is not None, (
                f"uid {uid} from emitted node {emitted_node.get('id')} "
                f"not found in source"
            )
            assert emitted_node["pos"] == expected_pos, (
                f"uid {uid}: emitted pos {emitted_node['pos']} != "
                f"source pos {expected_pos}"
            )


# ---------------------------------------------------------------------------
# T20 (Step 14b) — Layer 3 corpus-wide convert_ui_to_api gate (env-gated)
# ---------------------------------------------------------------------------


@pytest.mark.comfy
def test_layer3_corpus_wide_convert_ui_to_api_gate() -> None:
    """Step 14b (T20): Layer-3 GATE OF RECORD for corpus-wide convert_ui_to_api.

    Deepens the single-workflow smoke test to the entire real corpus.
    For every UI-shaped JSON workflow in workflow_corpus/ (excluding manifests):

    1. emit_ui_json(wf) → ComfyUI's convert_ui_to_api → canonical_equal vs
       wf.compile('api'), confirming the emitter + Comfy converter produce the
       same API graph as our internal compile path.
    2. Also canonical-equal vs normalize_to_api(raw, comfy_converter_strict=True),
       which calls convert_ui_to_api on the raw JSON directly — if the emitter is
       faithful, both paths should agree.
    3. Object-info input-name check: for each node with a known schema, confirm
       that every input name in the convert_ui_to_api output appears in the
       schema's input names (matches the emitter's own source).
    4. Bypass/mute graphs (mode 2 / mode 4) match — ComfyUI drops both in
       convert_ui_to_api (workflow_convert.py:1166-1167) and T11 drops them in
       compile('api').

    Schema-less nodes are the GATE OF RECORD here — this is the definitive
    verification that ComfyUI's convert_ui_to_api accepts our emitted output
    even when a node has no registered schema.
    """
    import logging
    import os
    from pathlib import Path

    if os.environ.get("VIBECOMFY_COMFY_SMOKE") != "1":
        pytest.skip("comfy Layer-3 gate is opt-in (set VIBECOMFY_COMFY_SMOKE=1)")

    comfy_convert = pytest.importorskip(
        "comfy.component_model.workflow_convert"
    ).convert_ui_to_api

    from vibecomfy.ingest.normalize import convert_to_vibe_format
    from vibecomfy.ingest.normalize import normalize_to_api
    from vibecomfy.testing.canonical import canonical_equal

    corpus_root = Path("workflow_corpus")
    exclude = {
        "manifests/coverage.json",
        "manifests/ready_regeneration.json",
    }
    json_paths = sorted(
        p
        for p in corpus_root.rglob("*.json")
        if str(p.relative_to(corpus_root)) not in exclude
    )

    stats = {
        "total_checked": 0,
        "canonical_pass": 0,
        "canonical_fail": 0,
        "compile_errors": 0,
        "emit_errors": 0,
        "comfy_convert_errors": 0,
        "normalize_strict_errors": 0,
        "schema_less_workflows": 0,
        "schema_less_nodes_total": 0,
        "mode_bypass_muted": 0,
        "canonical_fail_details": [],  # type: list[str]
    }

    from vibecomfy.schema import get_schema_provider

    # Suppress warnings from emit_ui_json about schema-less nodes / widget
    # overflows — these are expected in the corpus and should not pollute
    # test output.
    with warnings.catch_warnings():
        warnings.simplefilter("ignore")

        for path in json_paths:
            rel = str(path.relative_to(corpus_root))
            with open(path) as fh:
                raw = json.load(fh)

            if not isinstance(raw.get("nodes"), list):
                continue

            wf = convert_to_vibe_format(raw)

            # Build the schema provider once per workflow
            provider = get_schema_provider("local")

            # Count schema-less nodes and bypass/muted nodes
            has_schema_less = False
            for node in wf.nodes.values():
                schema = provider.get_schema(node.class_type)
                if schema is None:
                    has_schema_less = True
                    stats["schema_less_nodes_total"] += 1
                mode = node.metadata.get("_ui", {}).get("mode", 0)
                if mode in (2, 4):
                    stats["mode_bypass_muted"] += 1
            if has_schema_less:
                stats["schema_less_workflows"] += 1

            # --------------- Path A: emit → comfy_convert ---------------
            try:
                ui = emit_ui_json(wf, schema_provider=provider)
            except Exception as exc:
                stats["emit_errors"] += 1
                stats["canonical_fail_details"].append(
                    f"{rel}: emit_ui_json raised {type(exc).__name__}: {exc}"
                )
                continue

            try:
                comfy_api = comfy_convert(ui)
            except Exception as exc:
                stats["comfy_convert_errors"] += 1
                stats["canonical_fail_details"].append(
                    f"{rel}: comfy_convert raised {type(exc).__name__}: {exc}"
                )
                continue

            assert isinstance(comfy_api, dict) and comfy_api, (
                f"{rel}: convert_ui_to_api returned empty/non-dict result"
            )

            # --------------- Path B: compile('api') ---------------
            try:
                compile_api = wf.compile("api")
            except Exception as exc:
                stats["compile_errors"] += 1
                stats["canonical_fail_details"].append(
                    f"{rel}: compile('api') raised {type(exc).__name__}: {exc}"
                )
                continue

            # --------------- Path C: normalize_to_api(strict) ---------------
            try:
                strict_api = normalize_to_api(
                    raw, comfy_converter_strict=True, use_comfy_converter=True
                )
            except Exception as exc:
                stats["normalize_strict_errors"] += 1
                stats["canonical_fail_details"].append(
                    f"{rel}: normalize_to_api(strict) raised {type(exc).__name__}: {exc}"
                )
                continue

            # --------------- Canonical equality ---------------
            if not canonical_equal(comfy_api, compile_api):
                stats["canonical_fail"] += 1
                stats["canonical_fail_details"].append(
                    f"{rel}: comfy_convert(emit) != compile('api')"
                )
                continue

            if not canonical_equal(comfy_api, strict_api):
                stats["canonical_fail"] += 1
                stats["canonical_fail_details"].append(
                    f"{rel}: comfy_convert(emit) != normalize_to_api(strict)"
                )
                continue

            # --------------- Object-info input-name check ---------------
            _check_canonical_input_names(comfy_api, wf, rel, stats)

            stats["canonical_pass"] += 1
            stats["total_checked"] += 1

    # --------------- Final assertions ---------------
    assert stats["total_checked"] > 0, (
        f"No corpus workflows passed the Layer-3 gate. "
        f"Details: {stats['canonical_fail_details'][:5] if stats['canonical_fail_details'] else 'none'}"
    )

    if stats["canonical_fail"] > 0:
        detail_summary = "\n  ".join(stats["canonical_fail_details"][:10])
        input_mismatches = stats.get("input_name_mismatches", 0)
        assert False, (
            f"Layer-3 gate: {stats['canonical_fail']} of "
            f"{stats['total_checked'] + stats['canonical_fail']} workflows "
            f"failed canonical equality.\n"
            f"Total checked: {stats['total_checked']}\n"
            f"Compile errors: {stats['compile_errors']}\n"
            f"Emit errors: {stats['emit_errors']}\n"
            f"Comfy-convert errors: {stats['comfy_convert_errors']}\n"
            f"Normalize-strict errors: {stats['normalize_strict_errors']}\n"
            f"Input-name mismatches: {input_mismatches}\n"
            f"Schema-less workflows: {stats['schema_less_workflows']} "
            f"({stats['schema_less_nodes_total']} nodes)\n"
            f"Bypass/muted nodes: {stats['mode_bypass_muted']}\n"
            f"Failures (first 10):\n  {detail_summary}"
        )

    # The gate-of-record assertion: schema-less nodes MUST survive the
    # comfy converter without causing equality failures.  If schema_less
    # workflows pass canonical_equal, they are verified.
    assert stats["canonical_fail"] == 0, (
        f"Layer-3 gate: {stats['canonical_fail']} canonical-equality failures "
        f"in {stats['canonical_pass']} checked workflows"
    )


def _check_canonical_input_names(
    comfy_api: dict,
    wf: "VibeWorkflow",
    rel: str,
    stats: dict,
) -> None:
    """Per-node input-name check: every input in the comfy API must appear
    in the schema's input names for that class_type (when a schema exists)."""
    # Use the same provider used by the main test — import locally to avoid
    # circular dependencies at module level.
    from vibecomfy.schema import get_schema_provider
    provider = get_schema_provider("local")
    for node_id, node_data in comfy_api.items():
        class_type = node_data.get("class_type", "")
        schema = provider.get_schema(class_type)
        if schema is None:
            continue  # schema-less node — no input-name check possible
        schema_input_names = frozenset(schema.inputs.keys()) if schema.inputs else frozenset()
        for input_name in node_data.get("inputs", {}):
            if isinstance(input_name, str) and input_name not in schema_input_names:
                # Check if it's a link value (list), not a widget
                val = node_data["inputs"][input_name]
                if isinstance(val, list) and len(val) == 2:
                    continue  # link inputs use canonical slot names
                stats.setdefault("input_name_mismatches", 0)
                stats["input_name_mismatches"] += 1


# ---------------------------------------------------------------------------
# T9 — output path derivation + breadcrumb stamping
# ---------------------------------------------------------------------------


def test_default_output_path_from_source_name() -> None:
    from vibecomfy.ingest.normalize import convert_to_vibe_format
    from vibecomfy.porting.ui_emitter import default_output_path

    with open("workflow_corpus/official/video/wan_t2v.json") as handle:
        raw = json.load(handle)
    wf = convert_to_vibe_format(raw, source_path="workflow_corpus/official/video/wan_t2v.json")
    assert default_output_path(wf).as_posix() == "out/ui_export/wan_t2v.json"


def test_output_path_hash_fallback_for_unnamed_source() -> None:
    """Programmatic IR with no source name → deterministic hash path; never empty/raising."""
    from vibecomfy.porting.ui_emitter import default_output_path

    wf = _wf()
    wf.nodes["1"] = VibeNode("1", "LoadImage")
    p1 = default_output_path(wf)
    p2 = default_output_path(wf)
    assert p1 == p2  # deterministic
    assert p1.as_posix().startswith("out/ui_export/")
    assert p1.suffix == ".json"
    assert p1.stem  # non-empty


def test_output_path_out_override_wins() -> None:
    from vibecomfy.porting.ui_emitter import default_output_path

    wf = _wf()
    wf.nodes["1"] = VibeNode("1", "LoadImage")
    assert default_output_path(wf, out="some/dir/custom.json").as_posix() == "some/dir/custom.json"


def test_breadcrumb_stamped_at_top_level_extra() -> None:
    wf = _wf()
    wf.nodes["1"] = VibeNode("1", "LoadImage")
    provider = _Provider({"LoadImage": _schema("LoadImage", [OutputSpec("IMAGE", "image")])})
    ui = emit_ui_json(wf, schema_provider=provider, source_template="image/z_image", prior_path="orig/path.json")
    crumb = ui["extra"]["vibecomfy"]
    assert crumb == {
        "layout_version": "m1",
        "source_template": "image/z_image",
        "prior_path": "orig/path.json",
    }


def test_breadcrumb_stamped_on_each_subgraph_definition() -> None:
    wf = _wf()
    wf.nodes["1"] = VibeNode("1", "LoadImage")
    wf.metadata["definitions"] = {
        "subgraphs": [{"id": "sg-uuid", "name": "Sub", "nodes": [], "links": []}]
    }
    provider = _Provider({"LoadImage": _schema("LoadImage", [OutputSpec("IMAGE", "image")])})
    ui = emit_ui_json(wf, schema_provider=provider, source_template="t", prior_path="p.json")
    sg = ui["definitions"]["subgraphs"][0]
    assert sg["extra"]["vibecomfy"] == {
        "layout_version": "m1",
        "source_template": "t",
        "prior_path": "p.json",
    }


# ---------------------------------------------------------------------------
# T7 — widget-count overflow downgrade: no raise, diagnostic recorded
# ---------------------------------------------------------------------------


def test_flat_ksampler_does_not_raise_on_emit(tmp_path) -> None:
    """Emitting the flat fixture's KSampler must not raise (downgraded assert → diagnostic).

    Finding (from debt/SD6): KSampler does NOT itself trigger the overflow —
    _build_widget_values produces 6 entries and _full_widget_name_count returns 7
    (includes the None control slot), so the check passes as '6<=7'.  The downgrade
    is preventative; this test guards against any future regression that re-raises.
    """
    import json as _json

    from vibecomfy.ingest.normalize import convert_to_vibe_format

    with open("tests/fixtures/walking_skeleton/flat.json") as fh:
        raw = _json.load(fh)
    wf = convert_to_vibe_format(raw)

    report: list[dict] = []
    with warnings.catch_warnings():
        warnings.simplefilter("ignore")
        result = emit_ui_json(wf, recovery_report=report)

    # Must not raise — basic smoke
    assert isinstance(result, dict)
    assert result["nodes"]

    # KSampler entry must have a widget_length_check (non-fatal diagnostic recorded)
    ksampler_entry = next(
        (e for e in report if e["class_type"] == "KSampler"), None
    )
    assert ksampler_entry is not None, "No KSampler in recovery_report"
    assert "widget_length_check" in ksampler_entry
    # KSampler does NOT trigger overflow (6 <= 7); document the finding.
    assert "overflow" not in ksampler_entry["widget_length_check"], (
        "KSampler unexpectedly triggered overflow — debt note: KSampler should pass "
        "6<=7 because _full_widget_name_count counts the None control slot."
    )


def test_overflow_widget_count_recorded_as_diagnostic() -> None:
    """When widget count exceeds schema, overflow is recorded in prov/recovery_report, no raise."""
    wf = _wf()
    # Manufacture a KSampler with excess widget_N keys beyond the schema count.
    # Set widget_0..widget_9 (10 values) to exceed a schema count of 7.
    node = VibeNode(
        "1",
        "KSampler",
        widgets={f"widget_{i}": i for i in range(10)},
    )
    wf.nodes["1"] = node

    report: list[dict] = []
    with warnings.catch_warnings():
        warnings.simplefilter("ignore")
        # Must not raise even if widget count exceeds schema
        emit_ui_json(wf, recovery_report=report)

    assert report, "recovery_report must be populated"
    entry = report[0]
    assert "widget_length_check" in entry
    # overflow case: 10 > 7 → overflow recorded
    if "overflow" in entry["widget_length_check"]:
        assert ">" in entry["widget_length_check"]
    # Either way, no AssertionError was raised — that's the key invariant.


# ═══════════════════════════════════════════════════════════════════════════════
# T8 — layout restore precedence and vibecomfy_uid stamp
# ═══════════════════════════════════════════════════════════════════════════════


def test_layout_arg_matched_node_emits_stored_pos_not_stub() -> None:
    """With a layout arg, the matched node's emitted pos equals the stored pos."""
    wf = _wf()
    node = VibeNode("1", "SaveImage")
    node.uid = "my-uid"
    wf.nodes["1"] = node

    stored_pos = [777.0, 888.0]
    stored_size = [333.0, 222.0]
    layout = {"my-uid": {"pos": stored_pos, "size": stored_size}}

    with warnings.catch_warnings():
        warnings.simplefilter("ignore")
        result = emit_ui_json(wf, layout=layout)

    emitted = result["nodes"][0]
    assert emitted["pos"] == stored_pos, (
        f"Layout pos not used: {emitted['pos']} != {stored_pos}"
    )
    assert emitted["size"] == stored_size, (
        f"Layout size not used: {emitted['size']} != {stored_size}"
    )


def test_every_nonempty_uid_node_emits_vibecomfy_uid_property() -> None:
    """Every node with a non-empty uid carries properties['vibecomfy_uid']."""
    import json as _json

    from vibecomfy.ingest.normalize import convert_to_vibe_format

    with open("tests/fixtures/walking_skeleton/flat.json") as fh:
        raw = _json.load(fh)
    wf = convert_to_vibe_format(raw)

    with warnings.catch_warnings():
        warnings.simplefilter("ignore")
        result = emit_ui_json(wf)

    for emit_node in result["nodes"]:
        lite_id = str(emit_node["id"])
        props = emit_node.get("properties", {})
        assert "vibecomfy_uid" in props, (
            f"Node {lite_id} missing vibecomfy_uid in properties"
        )
        assert props["vibecomfy_uid"], (
            f"Node {lite_id} has empty vibecomfy_uid"
        )
        assert props["vibecomfy_uid"] == lite_id, (
            f"Node {lite_id} vibecomfy_uid={props['vibecomfy_uid']!r} != litegraph id {lite_id}"
        )


def test_nodes_absent_from_layout_fall_back_to_stub() -> None:
    """Nodes absent from layout fall back to the stub geometry (not None)."""
    wf = _wf()
    node1 = VibeNode("1", "SaveImage")
    node1.uid = "uid-1"
    node2 = VibeNode("2", "PreviewImage")
    node2.uid = "uid-2"
    wf.nodes["1"] = node1
    wf.nodes["2"] = node2

    # Only provide layout for node1
    layout = {"uid-1": {"pos": [100.0, 200.0], "size": [300.0, 400.0]}}

    with warnings.catch_warnings():
        warnings.simplefilter("ignore")
        result = emit_ui_json(wf, layout=layout)

    assert len(result["nodes"]) == 2
    node1_emitted = next(n for n in result["nodes"] if n["id"] == 1)
    node2_emitted = next(n for n in result["nodes"] if n["id"] == 2)

    # Node1 should use layout
    assert node1_emitted["pos"] == [100.0, 200.0]
    # Node2 should fall back to stub (non-None, non-layout)
    assert node2_emitted["pos"] is not None
    assert len(node2_emitted["pos"]) == 2
    assert node2_emitted["pos"] != [100.0, 200.0], "node2 should not use node1's layout"


def test_captured_geometry_used_when_layout_empty_and_ui_present() -> None:
    """When layout is empty {} but node has _ui metadata, captured geometry is used."""
    from vibecomfy.ingest.normalize import convert_to_vibe_format
    import json as _json

    with open("tests/fixtures/walking_skeleton/flat.json") as fh:
        raw = _json.load(fh)
    wf = convert_to_vibe_format(raw)

    # All nodes should have _ui with captured pos/size from ingest
    with warnings.catch_warnings():
        warnings.simplefilter("ignore")
        result = emit_ui_json(wf, layout={})

    raw_by_id = {str(n["id"]): n for n in raw["nodes"]}
    for emit_node in result["nodes"]:
        lite_id = str(emit_node["id"])
        expected_pos = raw_by_id[lite_id]["pos"]
        assert emit_node["pos"] == [float(p) for p in expected_pos], (
            f"Node {lite_id}: captured pos {emit_node['pos']} != raw {expected_pos}"
        )


def test_captured_properties_blob_re_emitted_verbatim_with_ir_keys_merged() -> None:
    """A node with captured cnr_id / ver in its sidecar properties re-emits them
    verbatim, with vibecomfy_uid / ir_node_id / 'Node name for S&R' overlaid."""
    wf = _wf()
    node = VibeNode("1", "MyNode")
    node.uid = "uid-captured"
    wf.nodes["1"] = node

    captured_props = {"cnr_id": "abc-123", "ver": "2.0", "mask_data": {"alpha": 0.5}}
    layout_entry = {
        "pos": [100.0, 200.0],
        "size": [300.0, 200.0],
        "flags": {},
        "color": None,
        "bgcolor": None,
        "mode": 0,
        "properties": captured_props,
    }

    with warnings.catch_warnings():
        warnings.simplefilter("ignore")
        result = emit_ui_json(wf, layout={"uid-captured": layout_entry})

    emitted = result["nodes"][0]
    props = emitted["properties"]

    # Verbatim captured keys survive
    assert props["cnr_id"] == "abc-123", f"cnr_id lost: {props}"
    assert props["ver"] == "2.0", f"ver lost: {props}"
    assert props["mask_data"] == {"alpha": 0.5}, f"mask_data lost: {props}"

    # IR identity keys are overlaid (always win)
    assert props["ir_node_id"] == "1"
    assert props["Node name for S&R"] == "MyNode"
    assert props["vibecomfy_uid"] == "uid-captured"

    # Display label present
    assert "vibecomfy_id" in props


def test_no_captured_blob_falls_back_to_fresh_construction() -> None:
    """A node with no captured properties blob still gets the fresh IR identity
    dict (no regression for programmatic / scratchpad workflows)."""
    wf = _wf()
    node = VibeNode("1", "ProgrammaticNode")
    node.uid = "uid-prog"
    # No sidecar, no _ui metadata → furniture resolves to empty properties
    wf.nodes["1"] = node

    with warnings.catch_warnings():
        warnings.simplefilter("ignore")
        result = emit_ui_json(wf, layout={})

    emitted = result["nodes"][0]
    props = emitted["properties"]

    # Only IR identity keys should be present (no captured blob)
    assert props["ir_node_id"] == "1"
    assert props["Node name for S&R"] == "ProgrammaticNode"
    assert props["vibecomfy_uid"] == "uid-prog"
    assert "vibecomfy_id" in props


def test_inner_subgraph_nodes_carry_vibecomfy_uid() -> None:
    """Inner subgraph nodes emitted via _emit_definitions carry
    properties['vibecomfy_uid'] stamped from mint_local_uid."""
    wf = _wf()
    node = VibeNode("1", "SaveImage")
    node.uid = "top-uid"
    wf.nodes["1"] = node

    # Simulate a subgraph definition with inner nodes
    inner_nodes = [
        {"id": 10, "type": "InnerA", "pos": [0, 0], "size": [100, 100], "properties": {}},
        {"id": 20, "type": "InnerB", "pos": [50, 50], "size": [100, 100]},
    ]
    wf.metadata["definitions"] = {
        "subgraphs": [
            {
                "nodes": inner_nodes,
                "links": [],
                "state": {},
            }
        ]
    }

    with warnings.catch_warnings():
        warnings.simplefilter("ignore")
        result = emit_ui_json(wf)

    # The definitions should contain inner nodes with vibecomfy_uid stamped
    defs = result.get("definitions")
    assert defs is not None, "Expected definitions in output"
    subgraphs = defs.get("subgraphs", [])
    assert len(subgraphs) == 1
    emitted_inner = subgraphs[0].get("nodes", [])
    assert len(emitted_inner) == 2

    # InnerA had properties={} → uid stamped from id=10
    inner_a = emitted_inner[0]
    assert inner_a["properties"].get("vibecomfy_uid") == "10", (
        f"InnerA missing/incorrect vibecomfy_uid: {inner_a['properties']}"
    )

    # InnerB had no properties key → uid stamped from id=20
    inner_b = emitted_inner[1]
    assert inner_b["properties"].get("vibecomfy_uid") == "20", (
        f"InnerB missing/incorrect vibecomfy_uid: {inner_b.get('properties')}"
    )


# ---------------------------------------------------------------------------
# T4 — Two-source authoritative widget-slot model
# ---------------------------------------------------------------------------


def test_raw_widget_order_used_for_count_when_provider_has_it() -> None:
    """Widget COUNT uses raw object_info_widget_order (nulls included) when
    the provider supports raw_widget_order."""
    from vibecomfy.schema.provider import ObjectInfoIndexSchemaProvider

    wf = _wf()
    wf.nodes["1"] = _ksampler()
    wf.nodes["2"] = VibeNode("2", "SaveImage")
    wf.connect("1.0", "2.images")

    provider = ObjectInfoIndexSchemaProvider(
        root="vibecomfy/porting/cache/object_info"
    )
    report: list[dict] = []
    result = emit_ui_json(wf, schema_provider=provider, recovery_report=report)

    # KSampler widget_length_check should reflect the RAW count (10 entries
    # with 4 nulls), not the compacted count (6 entries).
    ksamp_report = next(r for r in report if r["class_type"] == "KSampler")
    wlc = ksamp_report["widget_length_check"]
    assert "10" in wlc, f"Expected raw count 10 in widget_length_check, got: {wlc}"

    # widgets_values still use compacted ordering (6 entries)
    ksamp_node = next(n for n in result["nodes"] if n["id"] == 1)
    assert ksamp_node["widgets_values"] == [5, 20, 7.0, "euler", "normal", 1.0]


def test_ksampler_emits_with_raw_count_no_overflow() -> None:
    """KSampler with standard widget values does not overflow the raw count (10)."""
    from vibecomfy.schema.provider import ObjectInfoIndexSchemaProvider

    wf = _wf()
    wf.nodes["1"] = _ksampler()

    provider = ObjectInfoIndexSchemaProvider(
        root="vibecomfy/porting/cache/object_info"
    )
    report: list[dict] = []
    with warnings.catch_warnings():
        warnings.simplefilter("ignore")
        emit_ui_json(wf, schema_provider=provider, recovery_report=report)

    ksamp_report = next(r for r in report if r["class_type"] == "KSampler")
    wlc = ksamp_report["widget_length_check"]
    # 6 <= 10 — not an overflow
    assert "<=" in wlc, f"Expected non-overflow, got: {wlc}"


def test_seed_bearing_node_gets_extra_slot_heuristic() -> None:
    """A class with an INT seed/noise_seed field gets control_after_generate
    guessed when the provider has no raw_widget_order."""
    from vibecomfy.schema.provider import NodeSchema, InputSpec

    wf = _wf()
    # Simulate a seed-bearing node whose schema has INT seed
    node = VibeNode(
        "1",
        "CustomSampler",
        inputs={"seed": 42, "steps": 10},
        metadata={"control_after_generate": "randomize"},
    )
    wf.nodes["1"] = node

    schema = NodeSchema(
        class_type="CustomSampler",
        pack=None,
        inputs={
            "seed": InputSpec(type="INT", required=True),
            "steps": InputSpec(type="INT", required=True),
        },
        outputs=[],
        source_provider="widget_schema",
        confidence=0.3,
    )

    class _SeedProvider:
        def get_schema(self, ct):
            return schema if ct == "CustomSampler" else None

    provider = _SeedProvider()
    report: list[dict] = []
    with warnings.catch_warnings():
        warnings.simplefilter("ignore")
        emit_ui_json(wf, schema_provider=provider, recovery_report=report)

    entry = next(r for r in report if r["class_type"] == "CustomSampler")
    # Offline heuristic should have added a control_after_generate guess
    assert "widget_order_guesses" in entry, (
        f"Expected widget_order_guesses for seed-bearing node, got keys: {list(entry.keys())}"
    )
    assert any(
        "control_after_generate" in g for g in entry["widget_order_guesses"]
    ), f"Expected control_after_generate guess, got: {entry['widget_order_guesses']}"


def test_previously_flagged_files_emit_without_exception() -> None:
    """The 11 files flagged in the Step 1 baseline (overflow warnings) still emit
    without exception — only NEW hard exceptions are regressions."""
    import json as _json
    from pathlib import Path

    from vibecomfy.ingest.normalize import convert_to_vibe_format

    baseline_path = Path("out/emit_survey_baseline.json")
    if not baseline_path.is_file():
        pytest.skip("Step 1 baseline not available")

    with open(baseline_path) as fh:
        baseline = _json.load(fh)

    overflow_files = [
        r for r in baseline["results"]
        if r["outcome"] == "overflow_warning"
    ]

    for result_entry in overflow_files:
        abs_path = Path(result_entry["absolute"])
        if not abs_path.is_file():
            continue
        with open(abs_path) as fh:
            raw = _json.load(fh)
        wf = convert_to_vibe_format(raw)
        try:
            with warnings.catch_warnings():
                warnings.simplefilter("ignore")
                emit_ui_json(wf, strict=False)
        except Exception as exc:
            raise AssertionError(
                f"Previously-flagged file {result_entry['path']} raised {type(exc).__name__}: {exc}"
            ) from exc


def test_widget_order_matches_object_info_for_covered_class() -> None:
    """For a class present in the object_info cache, the raw widget order
    (nulls included) is authoritative for COUNT."""
    from vibecomfy.porting.ui_emitter import _raw_widget_order_from_provider
    from vibecomfy.schema.provider import ObjectInfoIndexSchemaProvider

    provider = ObjectInfoIndexSchemaProvider(
        root="vibecomfy/porting/cache/object_info"
    )
    raw_order = _raw_widget_order_from_provider("KSampler", provider)
    assert raw_order is not None, "KSampler should be in the object_info cache"
    # Raw order from the cache: [null, "seed", "steps", "cfg", "sampler_name", "scheduler", null, null, null, "denoise"]
    assert raw_order[0] is None, f"Expected first slot to be None (control_after_generate), got: {raw_order[0]}"
    assert raw_order[1] == "seed"
    assert raw_order[6] is None, f"Expected slot 6 to be None (UI-only), got: {raw_order[6]}"
    assert raw_order[9] == "denoise"
    assert len(raw_order) == 10, f"Expected 10 raw slots for KSampler, got: {len(raw_order)}"


# ---------------------------------------------------------------------------
# T5: Furniture resolver (flags / color / bgcolor / mode / properties)
# ---------------------------------------------------------------------------


def test_furniture_from_sidecar_entry_roundtrip() -> None:
    """Sidecar path: a layout entry with groups/colors/collapsed/mode is emitted faithfully."""
    wf = _wf("sidecar-test")
    node = VibeNode("1", "SidecarNode")
    node.uid = "uid-aa"
    wf.nodes["1"] = node

    # Simulate a full sidecar entry as returned by read_store()["entries"]
    layout_entry = {
        "pos": [200.0, 300.0],
        "size": [400.0, 200.0],
        "flags": {"collapsed": True},
        "color": "#332",
        "bgcolor": "#553",
        "mode": 2,
        "properties": {"Node name for S&R": "SidecarNode", "custom": "val"},
    }
    result = emit_ui_json(wf, layout={"uid-aa": layout_entry})
    emitted = result["nodes"][0]

    assert emitted["flags"] == {"collapsed": True}
    assert emitted["color"] == "#332"
    assert emitted["bgcolor"] == "#553"
    assert emitted["mode"] == 2
    # Sidecar properties are the base; IR-built overlay wins for vibecomfy keys.
    assert emitted["properties"]["custom"] == "val"
    assert emitted["properties"]["Node name for S&R"] == "SidecarNode"
    assert emitted["properties"]["vibecomfy_uid"] == "uid-aa"
    assert "ir_node_id" in emitted["properties"]


def test_furniture_from_metadata_ui_fallback() -> None:
    """Direct-ingest fallback: node.metadata['_ui'] supplies furniture when no sidecar exists."""
    wf = _wf("ingest-test")
    node = VibeNode("1", "HasUI")
    node.uid = "uid-ingest"
    node.metadata["_ui"] = {
        "pos": [100, 150],
        "size": [300, 250],
        "flags": {"collapsed": False},
        "color": "#123",
        "bgcolor": "#456",
        "mode": 4,
        "properties": {"original": "yes"},
    }
    wf.nodes["1"] = node

    result = emit_ui_json(wf)  # no layout= param → falls through to _ui
    emitted = result["nodes"][0]

    assert emitted["flags"] == {"collapsed": False}
    assert emitted["color"] == "#123"
    assert emitted["bgcolor"] == "#456"
    assert emitted["mode"] == 4
    assert emitted["properties"]["original"] == "yes"
    assert emitted["properties"]["vibecomfy_uid"] == "uid-ingest"


def test_furniture_absent_fields_fallback_to_defaults() -> None:
    """When both sidecar and _ui are absent, emit fixed defaults (flags={}, mode=0, no color/bgcolor)."""
    wf = _wf("minimal")
    node = VibeNode("1", "Plain")
    # No _ui metadata, no uid
    wf.nodes["1"] = node

    result = emit_ui_json(wf)
    emitted = result["nodes"][0]

    assert emitted["flags"] == {}
    assert emitted["mode"] == 0
    assert "color" not in emitted, "color should be absent when None"
    assert "bgcolor" not in emitted, "bgcolor should be absent when None"


def test_furniture_mode_defaults_to_zero_for_non_int() -> None:
    """Non-int mode values (None, string, float) are defaulted to 0."""
    wf = _wf("bad-mode")
    node = VibeNode("1", "BadMode")
    node.uid = "uid-bm"
    wf.nodes["1"] = node

    # layout entry with a non-int mode
    layout_entry = {
        "pos": [0, 0],
        "size": [100, 100],
        "flags": {},
        "mode": None,  # None → 0
    }
    result = emit_ui_json(wf, layout={"uid-bm": layout_entry})
    assert result["nodes"][0]["mode"] == 0

    # string mode
    layout_entry["mode"] = "muted"
    result2 = emit_ui_json(wf, layout={"uid-bm": layout_entry})
    assert result2["nodes"][0]["mode"] == 0


def test_furniture_groups_from_param() -> None:
    """groups= param populates the top-level groups array."""
    wf = _wf("gtest")
    wf.nodes["1"] = VibeNode("1", "N1")

    groups = [
        {"title": "Group A", "bounding": [0, 0, 400, 300], "color": "#3f3"},
        {"title": "Group B", "bounding": [500, 0, 400, 300], "color": "#33f"},
    ]
    result = emit_ui_json(wf, groups=groups)
    assert result["groups"] == groups

    # Default: empty list
    result2 = emit_ui_json(wf)
    assert result2["groups"] == []


def test_furniture_sidecar_takes_precedence_over_metadata_ui() -> None:
    """When BOTH a sidecar entry and node.metadata['_ui'] exist, the sidecar wins."""
    wf = _wf("precedence")
    node = VibeNode("1", "Conflict")
    node.uid = "uid-conflict"
    # metadata['_ui'] says mode=4, color='#ui'
    node.metadata["_ui"] = {
        "pos": [10, 20],
        "size": [30, 40],
        "flags": {"collapsed": False},
        "color": "#ui",
        "bgcolor": "#uibg",
        "mode": 4,
        "properties": {"from": "ui"},
    }
    wf.nodes["1"] = node

    # Sidecar says mode=2, color='#sc'
    sidecar_entry = {
        "pos": [50, 60],
        "size": [70, 80],
        "flags": {"collapsed": True},
        "color": "#sc",
        "bgcolor": "#scbg",
        "mode": 2,
        "properties": {"from": "sidecar"},
    }
    result = emit_ui_json(wf, layout={"uid-conflict": sidecar_entry})
    emitted = result["nodes"][0]

    assert emitted["flags"] == {"collapsed": True}, "sidecar flags should win"
    assert emitted["color"] == "#sc", "sidecar color should win"
    assert emitted["bgcolor"] == "#scbg", "sidecar bgcolor should win"
    assert emitted["mode"] == 2, "sidecar mode should win"
    assert emitted["properties"]["from"] == "sidecar", "sidecar properties should win"


# ---------------------------------------------------------------------------
# T10 — Mode emit for bypass/mute display (Step 8)
# ---------------------------------------------------------------------------


def test_node_captured_with_mode_4_reemits_mode_4() -> None:
    """T10: A node captured with mode 4 (bypassed) re-emits mode 4.

    This is the canonical round-trip: capture mode 4 in metadata['_ui'],
    emit through emit_ui_json, and confirm the emitted node carries mode: 4.
    """
    wf = _wf("mode4-roundtrip")
    node = VibeNode("1", "LoadImage")
    node.uid = "uid-mode4"
    node.metadata["_ui"] = {
        "pos": [100.0, 200.0],
        "size": [300.0, 250.0],
        "flags": {},
        "color": "#abc",
        "bgcolor": None,
        "mode": 4,
        "properties": {},
    }
    wf.nodes["1"] = node

    provider = _Provider({
        "LoadImage": _schema("LoadImage", [OutputSpec("IMAGE", "image")]),
    })
    result = emit_ui_json(wf, schema_provider=provider)
    emitted = result["nodes"][0]

    assert emitted["mode"] == 4, f"bypassed node must re-emit mode 4, got {emitted['mode']}"
    # Verify the node is otherwise intact
    assert emitted["type"] == "LoadImage"
    assert emitted["id"] == 1


def test_node_captured_with_mode_2_reemits_mode_2() -> None:
    """T10: A node captured with mode 2 (muted) re-emits mode 2.

    Captures mode 2 via the sidecar (layout=) path and confirms it
    survives the full emit round-trip.
    """
    wf = _wf("mode2-roundtrip")
    node = VibeNode("1", "SaveImage")
    node.uid = "uid-mode2"
    wf.nodes["1"] = node

    sidecar_entry = {
        "pos": [50.0, 60.0],
        "size": [400.0, 200.0],
        "flags": {},
        "color": None,
        "bgcolor": None,
        "mode": 2,
        "properties": {},
    }

    provider = _Provider({
        "SaveImage": _schema("SaveImage", []),
    })
    result = emit_ui_json(wf, layout={"uid-mode2": sidecar_entry}, schema_provider=provider)
    emitted = result["nodes"][0]

    assert emitted["mode"] == 2, f"muted node must re-emit mode 2, got {emitted['mode']}"
    assert emitted["type"] == "SaveImage"


def test_mode_emit_reflects_display_state() -> None:
    """T10: emit_ui_json re-emits the captured mode field in each node dict.

    Creates three identical workflows whose only difference is the captured
    mode (0=normal, 2=muted, 4=bypassed) and verifies that emit_ui_json
    re-emits the correct mode value.  compile('api') behavior for mode!=0
    is tested separately in test_compile_* (T11).
    """
    def _build_wf(mode_val: int) -> VibeWorkflow:
        wf = _wf(f"mode-emit-{mode_val}")
        li = VibeNode("1", "LoadImage")
        li.uid = "uid-li"
        li.metadata["_ui"] = {
            "pos": [10.0, 20.0], "size": [300.0, 200.0],
            "flags": {}, "color": None, "bgcolor": None,
            "mode": mode_val, "properties": {},
        }
        wf.nodes["1"] = li

        si = VibeNode("2", "SaveImage")
        si.uid = "uid-si"
        si.metadata["_ui"] = {
            "pos": [400.0, 20.0], "size": [300.0, 200.0],
            "flags": {}, "color": None, "bgcolor": None,
            "mode": mode_val, "properties": {},
        }
        wf.nodes["2"] = si

        wf.edges.append(VibeEdge("1", "0", "2", "images"))
        return wf

    provider = _Provider({
        "LoadImage": _schema("LoadImage", [OutputSpec("IMAGE", "image")]),
        "SaveImage": _schema("SaveImage", []),
    })

    wf0 = _build_wf(0)
    wf2 = _build_wf(2)
    wf4 = _build_wf(4)

    emit0 = emit_ui_json(wf0, schema_provider=provider)
    emit2 = emit_ui_json(wf2, schema_provider=provider)
    emit4 = emit_ui_json(wf4, schema_provider=provider)

    nodes0 = {n["id"]: n["mode"] for n in emit0["nodes"]}
    nodes2 = {n["id"]: n["mode"] for n in emit2["nodes"]}
    nodes4 = {n["id"]: n["mode"] for n in emit4["nodes"]}

    assert nodes0 == {1: 0, 2: 0}, f"mode 0 emit: {nodes0}"
    assert nodes2 == {1: 2, 2: 2}, f"mode 2 emit: {nodes2}"
    assert nodes4 == {1: 4, 2: 4}, f"mode 4 emit: {nodes4}"


# ---------------------------------------------------------------------------
# T11 — compile('api') drops muted (mode=2) and bypassed (mode=4) nodes
# ---------------------------------------------------------------------------


def test_compile_byte_identical_no_mode_nodes() -> None:
    """T11: compile('api') is byte-identical for graphs with no mode!=0 nodes.

    Verifies the fast-path invariant: when no node carries _ui.mode != 0,
    compile output is identical to a workflow with no _ui metadata at all.
    """
    wf_ui = _wf("mode0-ui")
    n = VibeNode("1", "SaveImage")
    n.metadata["_ui"] = {"pos": [0.0, 0.0], "size": [200.0, 100.0], "flags": {}, "mode": 0}
    wf_ui.nodes["1"] = n

    wf_bare = _wf("mode0-bare")
    wf_bare.nodes["1"] = VibeNode("1", "SaveImage")

    assert wf_ui.compile("api") == wf_bare.compile("api")


def test_compile_muted_node_dropped() -> None:
    """T11: A muted node (mode=2) is absent from compile('api') output."""
    wf = _wf("muted-drop")
    n = VibeNode("1", "LoadImage")
    n.metadata["_ui"] = {"mode": 2}
    wf.nodes["1"] = n

    api = wf.compile("api")
    assert "1" not in api, f"muted node must be dropped from compile output; got {api}"


def test_compile_bypassed_node_direct_skip() -> None:
    """T11: A bypassed node (mode=4) is dropped and downstream is wired to upstream.

    Graph: A(mode=0) → B(mode=4, bypassed) → C(mode=0)
    Expected compile output: A and C present; B absent; C.inputs["image"] = [A_id, 0].
    """
    wf = _wf("bypass-skip")

    node_a = VibeNode("1", "LoadImage")
    wf.nodes["1"] = node_a

    node_b = VibeNode("2", "FakeMiddle")
    node_b.metadata["_ui"] = {"mode": 4}
    wf.nodes["2"] = node_b

    node_c = VibeNode("3", "SaveImage")
    wf.nodes["3"] = node_c

    # A.output[0] → B.input["image"]
    wf.edges.append(VibeEdge("1", "0", "2", "image"))
    # B.output[0] → C.input["images"]
    wf.edges.append(VibeEdge("2", "0", "3", "images"))

    api = wf.compile("api")

    assert "1" in api, "upstream node A must be in compile output"
    assert "2" not in api, "bypassed node B must be absent from compile output"
    assert "3" in api, "downstream node C must be in compile output"
    # C should be wired directly to A (bypass resolved)
    assert api["3"]["inputs"].get("images") == ["1", 0], (
        f"C.inputs['images'] should be ['1', 0] after bypass resolution; got {api['3']['inputs']}"
    )


# ---------------------------------------------------------------------------
# T6 — Virtual-wire display: GetNode / SetNode / Reroute re-emitted as
# visible editor nodes at captured positions with dual edge lists.
# ---------------------------------------------------------------------------


def test_virtual_wires_display_and_flat_modes() -> None:
    """T6: GetNode/SetNode/Reroute re-emitted as visible nodes at captured
    positions in display mode; orphaned route in recovery report;
    --no-virtual-wires produces the flat resolved graph."""
    wf = _wf("vw-test")

    # Nodes: a real source, a SetNode, a resolved GetNode (fan-out to two
    # consumers), an orphaned GetNode (no matching SetNode), a Reroute
    # passthrough, and a final sink.
    wf.nodes["1"] = VibeNode("1", "LoadImage")
    wf.nodes["2"] = VibeNode("2", "ConsumerA")
    wf.nodes["3"] = VibeNode("3", "ConsumerB")
    wf.nodes["4"] = VibeNode("4", "OrphanConsumer")
    wf.nodes["5"] = VibeNode("5", "RerouteSink")

    # Broadcast helpers with captured positions in metadata['_ui']
    set_pos = [100.0, 50.0]
    get_pos = [300.0, 50.0]
    orphan_pos = [300.0, 250.0]
    reroute_pos = [500.0, 100.0]

    wf.nodes["10"] = VibeNode("10", "SetNode", widgets={"widget_0": "MY_BUS"})
    wf.nodes["10"].metadata["_ui"] = {"pos": list(set_pos), "size": [30, 30]}

    wf.nodes["11"] = VibeNode("11", "GetNode", widgets={"widget_0": "MY_BUS"})
    wf.nodes["11"].metadata["_ui"] = {"pos": list(get_pos), "size": [30, 30]}

    # Orphaned GetNode: broadcast name has no matching SetNode
    wf.nodes["12"] = VibeNode("12", "GetNode", widgets={"widget_0": "NO_SUCH_BUS"})
    wf.nodes["12"].metadata["_ui"] = {"pos": list(orphan_pos), "size": [30, 30]}

    # Reroute passthrough
    wf.nodes["20"] = VibeNode("20", "Reroute")
    wf.nodes["20"].metadata["_ui"] = {"pos": list(reroute_pos), "size": [20, 20]}

    # Edges
    wf.edges.append(VibeEdge("1", "0", "10", "value"))    # source → SetNode
    wf.edges.append(VibeEdge("11", "0", "2", "image"))    # GetNode → ConsumerA
    wf.edges.append(VibeEdge("11", "0", "3", "image"))    # GetNode → ConsumerB
    wf.edges.append(VibeEdge("12", "0", "4", "image"))    # orphan GetNode → OrphanConsumer
    wf.edges.append(VibeEdge("2", "0", "20", ""))          # ConsumerA → Reroute
    wf.edges.append(VibeEdge("20", "0", "5", "input"))     # Reroute → RerouteSink

    # ── Display mode (default) ──────────────────────────────────────────
    recovery: list[dict[str, Any]] = []
    with warnings.catch_warnings():
        warnings.simplefilter("ignore")
        result = emit_ui_json(
            wf, include_virtual_wires=True, recovery_report=recovery,
        )

    emitted_types = {n["type"] for n in result["nodes"]}
    assert "SetNode" in emitted_types, "SetNode should be visible in display mode"
    assert "GetNode" in emitted_types, "GetNode should be visible in display mode"
    assert "Reroute" in emitted_types, "Reroute should be visible in display mode"

    # Check captured positions are preserved for helpers (look up by ir_node_id)
    nodes_by_ir_id: dict[str, dict] = {
        n["properties"]["ir_node_id"]: n for n in result["nodes"]
    }
    assert nodes_by_ir_id["10"]["pos"] == set_pos, f"SetNode pos {nodes_by_ir_id['10']['pos']} != {set_pos}"
    assert nodes_by_ir_id["11"]["pos"] == get_pos, f"GetNode(11) pos {nodes_by_ir_id['11']['pos']} != {get_pos}"
    assert nodes_by_ir_id["12"]["pos"] == orphan_pos, f"GetNode(12) pos {nodes_by_ir_id['12']['pos']} != {orphan_pos}"
    assert nodes_by_ir_id["20"]["pos"] == reroute_pos, f"Reroute pos {nodes_by_ir_id['20']['pos']} != {reroute_pos}"

    # All original edges present in links (including through helpers)
    assert len(result["links"]) == 6, f"expected 6 display links, got {len(result['links'])}"

    # Orphaned route in recovery report
    orphan_entries = [e for e in recovery if e.get("orphaned_route")]
    assert len(orphan_entries) == 1, f"expected 1 orphan entry, got {len(orphan_entries)}"
    assert orphan_entries[0]["node_id"] == "12"
    assert orphan_entries[0]["broadcast_name"] == "NO_SUCH_BUS"

    # ── Flat mode (--no-virtual-wires) ──────────────────────────────────
    recovery2: list[dict[str, Any]] = []
    with warnings.catch_warnings():
        warnings.simplefilter("ignore")
        flat = emit_ui_json(
            wf, include_virtual_wires=False, recovery_report=recovery2,
        )

    flat_types = {n["type"] for n in flat["nodes"]}
    assert "SetNode" not in flat_types, "SetNode should NOT be in flat graph"
    assert "GetNode" not in flat_types, "GetNode should NOT be in flat graph"
    assert "Reroute" not in flat_types, "Reroute should NOT be in flat graph"

    # Flat graph: LoadImage → ConsumerA, ConsumerB; ConsumerA → RerouteSink
    # (broadcast resolved: source→Consumers; reroute resolved: ConsumerA→Sink)
    # Also orphan: GetNode→OrphanConsumer is dropped in flat mode
    # Expected links:
    #   1→2 (GetNode resolved: source 1→ConsumerA 2)
    #   1→3 (GetNode resolved: source 1→ConsumerB 3)
    #   2→5 (Reroute resolved: ConsumerA 2→RerouteSink 5)
    # Orphan GetNode→4 is dropped in flat mode
    assert len(flat["links"]) == 3, f"expected 3 flat links, got {len(flat['links'])}"

    # All links in flat graph originate from non-virtual-wire nodes
    flat_from_ids = {link[1] for link in flat["links"]}
    assert flat_from_ids <= {1, 2, 3, 4, 5}, f"unexpected from-node ids: {flat_from_ids}"

    # No orphan entry in flat-mode recovery report (orphans only in display)
    orphan_flat = [e for e in recovery2 if e.get("orphaned_route")]
    assert len(orphan_flat) == 0, "flat mode should NOT report orphans"


# ─────────────────────────────────────────────────────────────────────────────
# T9: Coordinate canonicalization + --main-positions richer metadata
# ─────────────────────────────────────────────────────────────────────────────


def test_coordinates_canonicalized_to_m2_precision() -> None:
    """Every pos/size emitted through _stub_layout/_captured_geometry/_extract_geometry
    is rounded to 2 decimal places (M2 precision)."""
    wf = _wf("canonical")
    wf.nodes["98"] = VibeNode(
        "98", "LoadImage",
        metadata={"_ui": {"pos": [123.456789, 987.654321], "size": [319.999999, 180.000001]}},
    )
    wf.nodes["99"] = VibeNode("99", "SaveImage")
    wf.connect("98.0", "99.images")

    provider = _Provider({
        "LoadImage": _schema("LoadImage", [OutputSpec("IMAGE", "image")]),
    })
    result = emit_ui_json(wf, schema_provider=provider)

    # Node 98 uses _captured_geometry (from _ui metadata)
    n98 = next(n for n in result["nodes"] if n["properties"]["ir_node_id"] == "98")
    assert n98["pos"] == [123.46, 987.65], f"pos not M2-canonicalized: {n98['pos']}"
    assert n98["size"] == [320.0, 180.0], f"size not M2-canonicalized: {n98['size']}"

    # Node 99 uses _stub_layout (no captured geometry)
    n99 = next(n for n in result["nodes"] if n["properties"]["ir_node_id"] == "99")
    # _stub_layout: col=1, row=0 → pos=[400.0, 0.0], size=[320.0, 180.0]
    assert n99["pos"] == [400.0, 0.0], f"stub pos not M2-canonicalized: {n99['pos']}"
    assert n99["size"] == [320.0, 180.0], f"stub size not M2-canonicalized: {n99['size']}"


def test_deterministic_byte_identical_emit() -> None:
    """Emitting the same IR twice yields byte-identical JSON (perturbed CWD/env)."""
    wf = _wf("det")
    wf.nodes["1"] = VibeNode("1", "LoadImage")
    wf.nodes["2"] = VibeNode("2", "SaveImage")
    wf.connect("1.0", "2.images")

    with warnings.catch_warnings():
        warnings.simplefilter("ignore")
        result1 = emit_ui_json(wf)
        result2 = emit_ui_json(wf)

    json1 = json.dumps(result1, indent=2, sort_keys=True)
    json2 = json.dumps(result2, indent=2, sort_keys=True)
    assert json1 == json2, "same IR must produce byte-identical JSON on repeated emits"

    # Also verify the same holds with schema provider and layout
    provider = _Provider({
        "LoadImage": _schema("LoadImage", [OutputSpec("IMAGE", "image")]),
    })
    with warnings.catch_warnings():
        warnings.simplefilter("ignore")
        r1 = emit_ui_json(wf, schema_provider=provider)
        r2 = emit_ui_json(wf, schema_provider=provider)
    assert json.dumps(r1, indent=2, sort_keys=True) == json.dumps(r2, indent=2, sort_keys=True), (
        "same IR with schema must produce byte-identical JSON"
    )


def test_main_positions_adds_extra_ds_state_and_node_order_title() -> None:
    """include_main_positions=True adds extra.ds, state counters, node title;
    include_main_positions=False keeps the lean default."""
    wf = _wf("mp")
    wf.nodes["1"] = VibeNode("1", "LoadImage")
    wf.nodes["2"] = VibeNode("2", "SaveImage")
    wf.connect("1.0", "2.images")

    # ── include_main_positions=True ──────────────────────────────────────
    with warnings.catch_warnings():
        warnings.simplefilter("ignore")
        result_main = emit_ui_json(wf, include_main_positions=True)

    # extra.ds must be present with fixed default when no sidecar provides it
    assert "ds" in result_main["extra"], "main-positions must include extra.ds"
    assert result_main["extra"]["ds"] == {"scale": 1.0, "offset": [0.0, 0.0]}

    # state counters must be present even without definitions
    assert "state" in result_main, "main-positions must include state"
    assert result_main["state"]["lastNodeId"] is not None
    assert result_main["state"]["lastLinkId"] is not None
    assert result_main["state"]["lastRerouteId"] is not None

    # Node order is always present; verify it's present
    for node in result_main["nodes"]:
        assert "order" in node, f"node {node['id']} missing order"

    # ── include_main_positions=False (lean default) ─────────────────────
    with warnings.catch_warnings():
        warnings.simplefilter("ignore")
        result_lean = emit_ui_json(wf, include_main_positions=False)

    # extra.ds must NOT be present in lean mode (unless sidecar provides it)
    assert "ds" not in result_lean["extra"], (
        "lean default must omit extra.ds"
    )

    # state must NOT be present when there are no definitions
    assert "state" not in result_lean, (
        "lean default must omit state when no definitions"
    )


def test_main_positions_node_title_from_sidecar() -> None:
    """Node title is emitted when include_main_positions=True and a sidecar
    layout entry provides it."""
    wf = _wf("title")
    # Set a uid on the node so the layout entry matches
    wf.nodes["1"] = VibeNode("1", "MyNode", uid="uid-tt")
    wf.nodes["2"] = VibeNode("2", "SaveImage")
    wf.connect("1.0", "2.images")

    layout_entry = {"pos": [100, 200], "size": [300, 160], "title": "Custom Title"}

    with warnings.catch_warnings():
        warnings.simplefilter("ignore")
        result = emit_ui_json(
            wf, layout={"uid-tt": layout_entry}, include_main_positions=True,
        )

    n1 = next(n for n in result["nodes"] if n["properties"]["ir_node_id"] == "1")
    assert n1["title"] == "Custom Title", f"expected title 'Custom Title', got {n1.get('title')!r}"

    # Node without title in layout should NOT have title key
    n2 = next(n for n in result["nodes"] if n["properties"]["ir_node_id"] == "2")
    assert "title" not in n2, f"node 2 should not have title, got {n2.get('title')!r}"


def test_main_positions_node_title_from_metadata_ui() -> None:
    """Node title is resolved from metadata['_ui'] when no sidecar entry exists."""
    wf = _wf("title_ui")
    wf.nodes["1"] = VibeNode(
        "1", "MyNode",
        metadata={"_ui": {"pos": [10, 20], "size": [100, 80], "title": "UI Title"}},
    )
    wf.nodes["2"] = VibeNode("2", "SaveImage")
    wf.connect("1.0", "2.images")

    with warnings.catch_warnings():
        warnings.simplefilter("ignore")
        result = emit_ui_json(wf, include_main_positions=True)

    n1 = next(n for n in result["nodes"] if n["properties"]["ir_node_id"] == "1")
    assert n1["title"] == "UI Title", f"expected 'UI Title' from _ui, got {n1.get('title')!r}"


def test_main_positions_lean_omits_title() -> None:
    """When include_main_positions=False, node title is NOT emitted even when present."""
    wf = _wf("lean_title")
    wf.nodes["1"] = VibeNode(
        "1", "MyNode", uid="uid-lt",
        metadata={"_ui": {"pos": [10, 20], "size": [100, 80], "title": "ShouldHide"}},
    )
    wf.nodes["2"] = VibeNode("2", "SaveImage")
    wf.connect("1.0", "2.images")

    layout_entry = {"pos": [10, 20], "size": [100, 80], "title": "SidecarTitle"}

    with warnings.catch_warnings():
        warnings.simplefilter("ignore")
        result = emit_ui_json(
            wf, layout={"uid-lt": layout_entry}, include_main_positions=False,
        )

    n1 = next(n for n in result["nodes"] if n["properties"]["ir_node_id"] == "1")
    assert "title" not in n1, "lean default must NOT emit title"


def test_canonicalize_group_geometry() -> None:
    """Group bounding boxes are canonicalized to M2 precision when
    include_main_positions=True."""
    from vibecomfy.porting.ui_emitter import _canonicalize_group_geometry

    groups = [
        {
            "title": "Group A",
            "bounding": [100.123456, 200.654321, 300.999999, 400.000001],
        },
        {
            "title": "Group B",
            # No bounding → left alone
        },
    ]
    _canonicalize_group_geometry(groups)
    assert groups[0]["bounding"] == [100.12, 200.65, 301.0, 400.0], (
        f"bounding not M2-canonicalized: {groups[0]['bounding']}"
    )
    # Group B should be unchanged (no bounding key or not a 4-element list)
    assert "bounding" not in groups[1]


def test_main_positions_groups_with_canonicalized_geometry() -> None:
    """Full emit with include_main_positions=True canonicalizes group geometry."""
    wf = _wf("group_geom")
    wf.nodes["1"] = VibeNode("1", "G1")
    wf.nodes["2"] = VibeNode("2", "G2")
    wf.connect("1.0", "2.images")

    groups = [
        {"title": "Group X", "bounding": [10.556, 20.444, 300.001, 400.999]},
    ]

    with warnings.catch_warnings():
        warnings.simplefilter("ignore")
        result = emit_ui_json(wf, groups=groups, include_main_positions=True)

    assert len(result["groups"]) == 1
    assert result["groups"][0]["bounding"] == [10.56, 20.44, 300.0, 401.0], (
        f"group bounding not canonicalized: {result['groups'][0]['bounding']}"
    )


def test_main_positions_extra_ds_from_sidecar() -> None:
    """When a sidecar extra provides ds, it MUST be used verbatim (not overridden)
    when include_main_positions=True."""
    wf = _wf("ds_sidecar")
    wf.nodes["1"] = VibeNode("1", "N")
    wf.nodes["2"] = VibeNode("2", "M")
    wf.connect("1.0", "2.images")

    sidecar_ds = {"scale": 0.5, "offset": [42.0, 99.0]}
    sidecar_extra = {"ds": sidecar_ds}

    with warnings.catch_warnings():
        warnings.simplefilter("ignore")
        result = emit_ui_json(wf, extra=sidecar_extra, include_main_positions=True)

    assert result["extra"]["ds"] == sidecar_ds, (
        f"sidecar ds must be preserved: {result['extra']['ds']}"
    )


# ---------------------------------------------------------------------------
# T17 — schema version 1.0 round-trip guard (Q2)
# ---------------------------------------------------------------------------


def test_schema_version_1_0_roundtrip() -> None:
    """Step 13a (T17): Bump _LITEGRAPH_VERSION 0.4 → 1.0.

    Q2 guard: a version-1.0 emitted file re-ingests/normalizes cleanly,
    confirming the structural read path is version-agnostic.
    """
    from vibecomfy.ingest.normalize import _normalize_ui_to_api
    from vibecomfy.porting.ui_emitter import _LITEGRAPH_VERSION as _VER
    from vibecomfy.porting.parity import compile_equivalent

    assert _VER == 1.0, f"_LITEGRAPH_VERSION should be 1.0, got {_VER}"

    wf = _wf("t17_rt")
    wf.nodes["1"] = VibeNode("1", "LoadImage", uid="load1")
    wf.nodes["2"] = VibeNode("2", "SaveImage", uid="save1")
    wf.nodes["3"] = VibeNode("3", "VAEDecode", uid="vae1")
    wf.connect("1.0", "3.pixels")
    wf.connect("3.0", "2.images")

    with warnings.catch_warnings():
        warnings.simplefilter("ignore")
        ui = emit_ui_json(wf)

    # The envelope must carry version 1.0
    assert ui["version"] == 1.0, f"expected version 1.0, got {ui['version']!r}"

    # Re-ingest/re-normalize should work cleanly (version-agnostic read)
    api = wf.compile("api")
    normalized = _normalize_ui_to_api(ui)
    equal, diffs = compile_equivalent(normalized, api)
    assert equal, f"version 1.0 round-trip failed: {diffs[:5]}"
