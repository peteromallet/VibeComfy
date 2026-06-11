"""Full-harness tests for the EditSession surface (render → apply_batch → done).

Exercises the EditSession across corpus graphs with 5 canonical edit cases
plus empty-done regression.  Verifies Gate A (byte-identity for untouched
nodes), Gate B (compile-isomorphism over touched region), and Gate C
(human-readable summary).

RuneXX-dependent cases adapt to available corpus graphs or skip gracefully.
"""

from __future__ import annotations

import json
from pathlib import Path
from typing import Any, Mapping

import pytest

from vibecomfy.porting.edit.apply import apply_delta
from vibecomfy.porting.edit.ledger import EditLedger
from vibecomfy.porting.edit.session import EditSession
from vibecomfy.schema import InputSpec, NodeSchema, OutputSpec, socket_types_compatible
from vibecomfy.porting.edit.normalize import normalize_ui_json
from tests.support.corpus_schema import (
    GraphInferredSchemaProvider,
    graph_inferred_schema_provider,
)

# ── paths ───────────────────────────────────────────────────────────────

_FIXTURE_DIR = Path("tests/fixtures/agent_edit")
_FLAT_PATH = _FIXTURE_DIR / "flat.json"
_SUBGRAPHED_WAN_PATH = _FIXTURE_DIR / "subgraphed_wan_i2v.json"
_CORPUS_ROOT = Path("workflow_corpus/official/video")
_LTX_T2V_PATH = _CORPUS_ROOT / "ltx2_3_t2v.json"
_LTX_I2V_PATH = _CORPUS_ROOT / "ltx2_3_i2v.json"


# ── schema providers ────────────────────────────────────────────────────


def _flat_schema_provider() -> Any:
    """Return a minimal schema provider for the flat.json fixture."""

    class SP:
        def get_schema(self, ct: str) -> NodeSchema | None:
            return {
                "CheckpointLoaderSimple": NodeSchema(
                    "CheckpointLoaderSimple", "core",
                    {"ckpt_name": InputSpec(type="STRING", required=True)},
                    [OutputSpec("MODEL", "MODEL"), OutputSpec("CLIP", "CLIP"), OutputSpec("VAE", "VAE")],
                ),
                "CLIPTextEncode": NodeSchema(
                    "CLIPTextEncode", "core",
                    {"text": InputSpec("STRING", required=True), "clip": InputSpec("CLIP", required=True)},
                    [OutputSpec("CONDITIONING", "CONDITIONING")],
                ),
                "EmptyLatentImage": NodeSchema(
                    "EmptyLatentImage", "core",
                    {"width": InputSpec("INT"), "height": InputSpec("INT"), "batch_size": InputSpec("INT")},
                    [OutputSpec("LATENT", "LATENT")],
                ),
                "KSampler": NodeSchema(
                    "KSampler", "core",
                    {
                        "seed": InputSpec("INT"), "steps": InputSpec("INT"), "cfg": InputSpec("FLOAT"),
                        "sampler_name": InputSpec("STRING"), "scheduler": InputSpec("STRING"),
                        "denoise": InputSpec("FLOAT"),
                        "model": InputSpec("MODEL", required=True),
                        "positive": InputSpec("CONDITIONING", required=True),
                        "negative": InputSpec("CONDITIONING", required=True),
                        "latent_image": InputSpec("LATENT", required=True),
                    },
                    [OutputSpec("LATENT", "LATENT")],
                ),
                "VAEDecode": NodeSchema(
                    "VAEDecode", "core",
                    {"samples": InputSpec("LATENT", required=True), "vae": InputSpec("VAE", required=True)},
                    [OutputSpec("IMAGE", "IMAGE")],
                ),
                "SaveImage": NodeSchema(
                    "SaveImage", "core",
                    {"images": InputSpec("IMAGE", required=True), "filename_prefix": InputSpec("STRING", required=True)},
                    [],
                ),
                "PrimitiveInt": NodeSchema(
                    "PrimitiveInt", "core",
                    {"value": InputSpec("INT")},
                    [OutputSpec("INT", "value")],
                ),
                "Reroute": NodeSchema(
                    "Reroute", "core",
                    {"": InputSpec("*")},
                    [OutputSpec("*", "")],
                ),
            }.get(ct)

    return SP()


def _wan_schema_provider() -> Any:
    """Return a minimal schema provider for the subgraphed_wan_i2v.json fixture."""

    class SP:
        def get_schema(self, ct: str) -> NodeSchema | None:
            return {
                "LoadImage": NodeSchema("LoadImage", "core", {},
                    [OutputSpec("IMAGE", "IMAGE"), OutputSpec("MASK", "MASK")]),
                "SaveVideo": NodeSchema("SaveVideo", "core",
                    {"video": InputSpec("VIDEO", required=True)}, []),
                "CLIPTextEncode": NodeSchema("CLIPTextEncode", "core",
                    {"text": InputSpec("STRING", required=True), "clip": InputSpec("CLIP", required=True)},
                    [OutputSpec("CONDITIONING", "CONDITIONING")]),
                "CLIPLoader": NodeSchema("CLIPLoader", "core",
                    {"clip_name": InputSpec("STRING"), "type": InputSpec("STRING")},
                    [OutputSpec("CLIP", "CLIP")]),
                "UNETLoader": NodeSchema("UNETLoader", "core",
                    {"unet_name": InputSpec("STRING"), "weight_dtype": InputSpec("STRING")},
                    [OutputSpec("MODEL", "MODEL")]),
                "VAELoader": NodeSchema("VAELoader", "core",
                    {"vae_name": InputSpec("STRING")},
                    [OutputSpec("VAE", "VAE")]),
                "KSamplerAdvanced": NodeSchema("KSamplerAdvanced", "core",
                    {
                        "model": InputSpec("MODEL", required=True),
                        "positive": InputSpec("CONDITIONING", required=True),
                        "negative": InputSpec("CONDITIONING", required=True),
                        "latent_image": InputSpec("LATENT", required=True),
                        "seed": InputSpec("INT"), "steps": InputSpec("INT"), "cfg": InputSpec("FLOAT"),
                        "sampler_name": InputSpec("STRING"), "scheduler": InputSpec("STRING"),
                        "start_at_step": InputSpec("INT"), "end_at_step": InputSpec("INT"),
                        "return_with_leftover_noise": InputSpec("STRING"),
                        "noise": InputSpec("NOISE"), "add_noise": InputSpec("STRING"),
                    },
                    [OutputSpec("LATENT", "LATENT")],
                ),
                "VAEDecode": NodeSchema("VAEDecode", "core",
                    {"samples": InputSpec("LATENT", required=True), "vae": InputSpec("VAE", required=True)},
                    [OutputSpec("IMAGE", "IMAGE")]),
                "WanImageToVideo": NodeSchema("WanImageToVideo", "custom",
                    {
                        "model": InputSpec("MODEL", required=True), "vae": InputSpec("VAE", required=True),
                        "image": InputSpec("IMAGE", required=True), "clip": InputSpec("CLIP", required=True),
                        "positive": InputSpec("CONDITIONING", required=True),
                        "negative": InputSpec("CONDITIONING", required=True),
                    },
                    [OutputSpec("LATENT", "LATENT")]),
                "ModelSamplingSD3": NodeSchema("ModelSamplingSD3", "custom",
                    {"model": InputSpec("MODEL", required=True), "shift": InputSpec("FLOAT")},
                    [OutputSpec("MODEL", "MODEL")]),
                "LoraLoaderModelOnly": NodeSchema("LoraLoaderModelOnly", "custom",
                    {"model": InputSpec("MODEL", required=True), "lora_name": InputSpec("STRING"),
                     "strength_model": InputSpec("FLOAT")},
                    [OutputSpec("MODEL", "MODEL")]),
                "CreateVideo": NodeSchema("CreateVideo", "custom",
                    {"latent": InputSpec("LATENT", required=True), "vae": InputSpec("VAE", required=True)},
                    [OutputSpec("VIDEO", "VIDEO")]),
            }.get(ct)

    return SP()


# ── fixtures ────────────────────────────────────────────────────────────


def _load_json(path: Path) -> dict[str, Any]:
    if not path.exists():
        pytest.skip(f"Fixture not available: {path}")
    return json.loads(path.read_text(encoding="utf-8"))


@pytest.fixture(scope="module")
def flat_ui() -> dict[str, Any]:
    return _load_json(_FLAT_PATH)


@pytest.fixture(scope="module")
def subgraphed_wan_ui() -> dict[str, Any]:
    return _load_json(_SUBGRAPHED_WAN_PATH)


@pytest.fixture(scope="module")
def ltx_t2v_ui() -> dict[str, Any]:
    return _load_json(_LTX_T2V_PATH)


@pytest.fixture(scope="module")
def ltx_i2v_ui() -> dict[str, Any]:
    return _load_json(_LTX_I2V_PATH)


@pytest.fixture(scope="module")
def ltx_t2v_provider(ltx_t2v_ui: dict[str, Any]) -> GraphInferredSchemaProvider:
    return graph_inferred_schema_provider(ltx_t2v_ui)


@pytest.fixture(scope="module")
def ltx_i2v_provider(ltx_i2v_ui: dict[str, Any]) -> GraphInferredSchemaProvider:
    return graph_inferred_schema_provider(ltx_i2v_ui)


# ── helper: byte-identity for untouched nodes ──────────────────────────


def _nodes_by_scope_and_uid(ui: Mapping[str, Any]) -> dict[tuple[str, str], dict[str, Any]]:
    """Build a dict mapping (scope_path, uid) → normalized node dict."""
    import copy
    normalized = normalize_ui_json(ui)
    ledger = EditLedger.ingest(normalized)
    return {
        (scope_path, uid): copy.deepcopy(node)
        for (scope_path, uid), node in ledger.node_index.items()
    }


def _assert_preserves_out_of_delta_nodes(
    before_ui: Mapping[str, Any],
    after_ui: Mapping[str, Any],
    *,
    touched: set[tuple[str, str]],
) -> None:
    """Assert that nodes NOT in *touched* are byte-identical before and after."""
    before_nodes = _nodes_by_scope_and_uid(before_ui)
    after_nodes = _nodes_by_scope_and_uid(after_ui)
    for key, before_node in before_nodes.items():
        if key in touched:
            continue
        assert after_nodes.get(key) == before_node, (
            f"Untouched node {key} was modified!"
        )


# ── helper: subgraph scope path ─────────────────────────────────────────


def _scope_path_by_name(ui: Mapping[str, Any], name: str) -> str:
    """Find the scope_path for a subgraph by its display name."""
    ledger = EditLedger.ingest(ui)
    for scope in ledger.scopes.values():
        if scope.kind == "subgraph" and scope.graph.get("name") == name:
            return scope.scope_path
    raise AssertionError(f"Missing subgraph scope {name!r}")


# ═══════════════════════════════════════════════════════════════════════
# Empty-done regression
# ═══════════════════════════════════════════════════════════════════════


def test_empty_done_on_flat(flat_ui: dict[str, Any]) -> None:
    """Empty-done on flat.json: render + done produces no changes."""
    session = EditSession(flat_ui, schema_provider=_flat_schema_provider())
    session.render()
    result = session.done()
    assert result.ok, f"Empty-done failed: {result.summary}"
    assert "identity verified" in result.summary.lower() or "no edits" in result.summary.lower()


def test_empty_done_on_subgraphed_wan(subgraphed_wan_ui: dict[str, Any]) -> None:
    """Empty-done on subgraphed_wan_i2v.json: render + done produces no changes."""
    session = EditSession(subgraphed_wan_ui, schema_provider=_wan_schema_provider())
    session.render()
    result = session.done()
    assert result.ok, f"Empty-done failed: {result.summary}"


def test_empty_done_on_ltx_t2v(ltx_t2v_ui: dict[str, Any], ltx_t2v_provider: GraphInferredSchemaProvider) -> None:
    """Empty-done on LTX t2v: normalization+render path doesn't disturb byte-identity."""
    session = EditSession(ltx_t2v_ui, schema_provider=ltx_t2v_provider)
    session.render()
    result = session.done()
    assert result.ok, f"Empty-done failed: {result.summary}"


def test_empty_done_on_ltx_i2v(ltx_i2v_ui: dict[str, Any], ltx_i2v_provider: GraphInferredSchemaProvider) -> None:
    """Empty-done on LTX i2v: normalization+render path doesn't disturb byte-identity."""
    session = EditSession(ltx_i2v_ui, schema_provider=ltx_i2v_provider)
    session.render()
    result = session.done()
    assert result.ok, f"Empty-done failed: {result.summary}"


# ═══════════════════════════════════════════════════════════════════════
# Case (a): Simple field edit — set_node_field
# ═══════════════════════════════════════════════════════════════════════


def test_case_a_set_node_field_prompt(flat_ui: dict[str, Any]) -> None:
    """Case (a): Set a prompt text on the positive CLIPTextEncode node."""
    import copy
    original = copy.deepcopy(flat_ui)

    session = EditSession(flat_ui, schema_provider=_flat_schema_provider())
    session.render()

    # The positive node is named 'positive' (uid '2') by render
    code = 'positive.text = "a faithful edited prompt"'
    batch = session.apply_batch(code)
    assert batch.ok, f"Batch failed: {[d.message for d in batch.diagnostics]}"
    assert len(batch.landed_ops) == 1

    # Verify the widget value changed
    for node in session.working_ui["nodes"]:
        if node["id"] == 2:
            assert node["widgets_values"] == ["a faithful edited prompt"]

    # Gate A/B/C verification
    done = session.done()
    assert done.ok, f"Done failed: {done.summary}"
    assert "Gate A passed" in done.summary
    assert "Gate B passed" in done.summary

    # Byte-identity for untouched nodes
    _assert_preserves_out_of_delta_nodes(
        original, session.working_ui, touched={("", "2")}
    )


def test_case_a_set_node_field_seed(flat_ui: dict[str, Any]) -> None:
    """Case (a): Set the seed value on KSampler node."""
    import copy
    original = copy.deepcopy(flat_ui)

    session = EditSession(flat_ui, schema_provider=_flat_schema_provider())
    session.render()

    code = 'ksampler.seed = 12345'
    batch = session.apply_batch(code)
    assert batch.ok, f"Batch failed: {[d.message for d in batch.diagnostics]}"

    # Verify the widget value changed
    for node in session.working_ui["nodes"]:
        if node["id"] == 5:
            wv = node.get("widgets_values", [])
            assert wv[0] == 12345

    done = session.done()
    assert done.ok, f"Done failed: {done.summary}"
    _assert_preserves_out_of_delta_nodes(
        original, session.working_ui, touched={("", "5")}
    )


# ═══════════════════════════════════════════════════════════════════════
# Case (b): Splice / upsert-link — rewire a connection
# ═══════════════════════════════════════════════════════════════════════


def test_case_b_upsert_link_rewire(flat_ui: dict[str, Any]) -> None:
    """Case (b): Rewire ksampler.positive from 'positive' to 'negative' conditioning."""
    import copy
    original = copy.deepcopy(flat_ui)

    session = EditSession(flat_ui, schema_provider=_flat_schema_provider())
    session.render()

    # Rewire: ksampler.positive → negative.conditioning (swap positive/negative)
    code = "ksampler.positive = negative.conditioning"
    batch = session.apply_batch(code)
    assert batch.ok, f"Batch failed: {[d.message for d in batch.diagnostics]}"
    assert len(batch.landed_ops) == 1

    done = session.done()
    assert done.ok, f"Done failed: {done.summary}"
    # ksampler, positive, and negative all touched (link rewiring changes output links)
    _assert_preserves_out_of_delta_nodes(
        original, session.working_ui, touched={("", "5"), ("", "3"), ("", "2")}
    )


# ═══════════════════════════════════════════════════════════════════════
# Case (c): Add node with link and placement
# ═══════════════════════════════════════════════════════════════════════


def test_case_c_add_node_with_link(flat_ui: dict[str, Any]) -> None:
    """Case (c): Add a new SaveImage node after vaedecode."""
    import copy

    # Ensure last_node_id is high enough for a new node
    ui = copy.deepcopy(flat_ui)
    ui["last_node_id"] = 8
    original = copy.deepcopy(ui)

    session = EditSession(ui, schema_provider=_flat_schema_provider())
    session.render()

    code = (
        "extra_save = SaveImage(\n"
        '    images=vaedecode.image,\n'
        '    filename_prefix="agent-edit/harness",\n'
        "    near=vaedecode,\n"
        '    relation="right_of",\n'
        ")"
    )
    batch = session.apply_batch(code)
    assert batch.ok, f"Batch failed: {[d.message for d in batch.diagnostics]}"
    assert len(batch.landed_ops) == 1

    # Verify the new node exists
    save_nodes = [n for n in session.working_ui["nodes"] if n["type"] == "SaveImage"]
    assert len(save_nodes) >= 2, "Expected at least 2 SaveImage nodes after add"

    done = session.done()
    assert done.ok, f"Done failed: {done.summary}"

    # The new node (id 8) is touched; vaedecode output links changed
    _assert_preserves_out_of_delta_nodes(
        original, session.working_ui,
        touched={("", "8"), ("", "6")},
    )


# ═══════════════════════════════════════════════════════════════════════
# Case (d): Subgraph internal edit — set_mode on subgraph node
# ═══════════════════════════════════════════════════════════════════════


def test_case_d_subgraph_set_mode(subgraphed_wan_ui: dict[str, Any]) -> None:
    """Case (d): Edit a node inside a subgraph using the correct scope_path.

    Uses apply_delta directly with a scope_path since subgraph nodes are not
    accessible via EditSession.apply_batch (they don't receive top-level variable
    names from render).
    """
    import copy
    from vibecomfy.porting.edit.ops import parse_edit_delta

    original = copy.deepcopy(subgraphed_wan_ui)
    scope_path = _scope_path_by_name(original, "Image to Video (Wan 2.2)")

    # Find a subgraph node to target
    sg = original["definitions"]["subgraphs"][0]
    target_node = sg["nodes"][0]  # Pick the first subgraph node
    target_uid = str(target_node["id"])

    stamped_before = EditLedger.ingest(original).stamped_copy()

    delta = parse_edit_delta(
        [{"op": "set_mode", "target": [scope_path, target_uid], "mode": 2}]
    )
    result = apply_delta(original, delta, schema_provider=_wan_schema_provider())

    assert result.ok, f"apply_delta failed: {[str(d) for d in result.diagnostics]}"
    assert result.candidate is not None

    # Verify mode changed
    updated_node = next(
        n for n in result.candidate["definitions"]["subgraphs"][0]["nodes"]
        if str(n["id"]) == target_uid
    )
    assert updated_node["mode"] == 2

    _assert_preserves_out_of_delta_nodes(
        stamped_before, result.candidate, touched={(scope_path, target_uid)}
    )


# ═══════════════════════════════════════════════════════════════════════
# Case (e): Reroute graph analysis — describe() + link tracing
# ═══════════════════════════════════════════════════════════════════════


def test_case_e_reroute_analysis_ltx_i2v(
    ltx_i2v_ui: dict[str, Any], ltx_i2v_provider: GraphInferredSchemaProvider
) -> None:
    """Case (e): Use describe() to inspect Reroute nodes and trace output links.

    The LTX i2v graph has a Reroute node (id 293) in its subgraph.
    Since subgraph nodes don't get top-level names, we trace links manually.
    """
    session = EditSession(ltx_i2v_ui, schema_provider=ltx_i2v_provider)
    session.render()

    # Use describe() on named top-level nodes
    # The LTX i2v graph should have at least a savevideo node
    assert "savevideo" in session.uid_by_name, (
        f"Expected 'savevideo' in names; got {list(session.uid_by_name.keys())}"
    )

    savevideo_desc = session.describe("savevideo")
    assert savevideo_desc.class_type == "SaveVideo"
    assert savevideo_desc.outputs == ()  # SaveVideo has no outputs
    assert len(savevideo_desc.fields) > 0  # Has at least video input

    # Find the Reroute node in the subgraph by searching the raw data
    sg = ltx_i2v_ui["definitions"]["subgraphs"][0]
    reroute_nodes = [n for n in sg["nodes"] if n["type"] == "Reroute"]
    if not reroute_nodes:
        pytest.skip("No Reroute nodes found in LTX i2v subgraph")
    reroute = reroute_nodes[0]
    reroute_id = reroute["id"]

    # Verify Reroute schema
    schema = ltx_i2v_provider.get_schema("Reroute")
    assert schema is not None
    assert schema.outputs[0].type == "*", "Reroute output type must be '*'"
    assert socket_types_compatible("*", "VAE"), "socket_types_compatible('*', 'VAE') must be True"

    # Trace the Reroute's output links
    reroute_outputs = reroute.get("outputs", [])
    assert len(reroute_outputs) > 0, "Reroute should have at least one output"
    output_links = reroute_outputs[0].get("links", [])
    assert len(output_links) > 0, f"Reroute {reroute_id} has no output links"

    # For each output link, verify the target node receives the link
    sg_links = sg.get("links", [])
    for link_id in output_links:
        found = False
        for link in sg_links:
            if isinstance(link, dict) and link.get("id") == link_id:
                found = True
                # Verify link type compatibility
                link_type = link.get("type", "*")
                target_node = next(
                    (n for n in sg["nodes"] if n["id"] == link.get("target_id")), None
                )
                if target_node:
                    target_inputs = target_node.get("inputs", [])
                    if isinstance(link.get("target_slot"), int):
                        slot = link["target_slot"]
                        if slot < len(target_inputs):
                            input_type = target_inputs[slot].get("type", "*")
                            assert socket_types_compatible(link_type, input_type), (
                                f"Reroute link {link_id}: {link_type} → {input_type} incompatible"
                            )
                break
        assert found, f"Reroute output link {link_id} not found in subgraph links"


# ═══════════════════════════════════════════════════════════════════════
# Gate verification: touched region byte-identity
# ═══════════════════════════════════════════════════════════════════════


def test_gate_a_byte_identity_untouched(flat_ui: dict[str, Any]) -> None:
    """Gate A: Untouched nodes are byte-identical after a field edit."""
    import copy
    original = copy.deepcopy(flat_ui)

    session = EditSession(flat_ui, schema_provider=_flat_schema_provider())
    session.render()
    session.apply_batch('positive.text = "gate a test"')

    # Verify working_ui differs from original
    assert session.working_ui != session.original_ui, (
        "working_ui should differ from original_ui after edit"
    )

    done = session.done()
    assert done.ok, f"Gate A should pass: {done.summary}"
    assert "Gate A passed" in done.summary


def test_gate_b_compile_isomorphism(flat_ui: dict[str, Any]) -> None:
    """Gate B: Touched compile region is isomorphic after an edit."""
    import copy
    original = copy.deepcopy(flat_ui)

    session = EditSession(flat_ui, schema_provider=_flat_schema_provider())
    session.render()
    session.apply_batch("positive.text = 'gate b test'")

    done = session.done()
    assert done.ok, f"Gate B should pass: {done.summary}"
    assert "Gate B passed" in done.summary


def test_gate_c_human_readable_summary(flat_ui: dict[str, Any]) -> None:
    """Gate C: done() produces a human-readable summary of operations."""
    session = EditSession(flat_ui, schema_provider=_flat_schema_provider())
    session.render()
    session.apply_batch("positive.text = 'summary test'")

    done = session.done()
    assert done.ok
    # Gate C summary should mention the operation
    assert "positive" in done.summary.lower() or "text" in done.summary.lower(), (
        f"Summary should mention changed field: {done.summary}"
    )


# ═══════════════════════════════════════════════════════════════════════
# describe() coverage
# ═══════════════════════════════════════════════════════════════════════


def test_describe_named_nodes_flat(flat_ui: dict[str, Any]) -> None:
    """describe() returns correct NodeDescriptors for all named flat nodes."""
    session = EditSession(flat_ui, schema_provider=_flat_schema_provider())
    session.render()

    # Verify each named node can be described
    for name in session.uid_by_name:
        desc = session.describe(name)
        assert desc.name == name
        assert desc.uid is not None
        assert desc.class_type is not None
        assert desc.scope_path == ""  # All top-level nodes have empty scope_path


def test_describe_ltx_t2v_top_level(
    ltx_t2v_ui: dict[str, Any], ltx_t2v_provider: GraphInferredSchemaProvider
) -> None:
    """describe() returns correct information for top-level LTX t2v nodes."""
    session = EditSession(ltx_t2v_ui, schema_provider=ltx_t2v_provider)
    session.render()

    for name in session.uid_by_name:
        desc = session.describe(name)
        assert desc.name == name
        assert desc.uid is not None
        assert desc.class_type is not None
        # Top-level nodes have empty scope_path
        assert desc.scope_path == ""


def test_working_ui_unchanged_after_describe(flat_ui: dict[str, Any]) -> None:
    """describe() is side-effect-free: working_ui is unchanged."""
    import copy
    session = EditSession(flat_ui, schema_provider=_flat_schema_provider())
    session.render()
    before = copy.deepcopy(session.working_ui)

    for name in list(session.uid_by_name.keys())[:3]:
        _ = session.describe(name)

    assert session.working_ui == before, "describe() mutated working_ui!"
