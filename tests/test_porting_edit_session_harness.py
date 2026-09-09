"""Full-harness tests for the EditSession surface (render → apply_batch → done).

Exercises the EditSession across corpus graphs with 5 canonical edit cases
plus empty-done regression.  Verifies Gate A (byte-identity for untouched
nodes), Gate B (compile-isomorphism over touched region), and Gate C
(human-readable summary).

RuneXX-dependent cases adapt to available corpus graphs or skip gracefully.
"""

from __future__ import annotations

import json
from copy import deepcopy
from pathlib import Path
from typing import Any, Mapping

import pytest

from vibecomfy.ingest.normalize import from_ui
from vibecomfy.porting.edit.session import EditSession
from vibecomfy.porting.edit._session_types import CompactDiagnostic, OperationTransition
from vibecomfy.porting.reorganise.graph_facts import UiGraphIndex
from vibecomfy.schema import InputSpec, NodeSchema, OutputSpec
from vibecomfy.schema.types import (
    FrozenSchemaSnapshotProvider,
    capture_schema_snapshot,
    schema_payload_from_node_schema,
)
from vibecomfy.workflow import VibeEdge, VibeNode, VibeWorkflow, WorkflowSource
from vibecomfy.workflow_bundle import WorkflowBundleError, validate_sidecar
from tests.support.corpus_schema import (
    GraphInferredSchemaProvider,
    graph_inferred_schema_provider,
)

# ── paths ───────────────────────────────────────────────────────────────

_FIXTURE_DIR = Path("tests/fixtures/agent_edit")
_FLAT_PATH = _FIXTURE_DIR / "flat.json"
_SUBGRAPHED_WAN_PATH = _FIXTURE_DIR / "subgraphed_wan_i2v.json"
_CORPUS_ROOT = Path("ready_templates/sources/official/video")
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
                    {
                        "ckpt_name": InputSpec(type="STRING", required=True),
                        "widget_1": InputSpec(type="STRING"),
                    },
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
                        "seed": InputSpec("INT"),
                        "control_after_generate": InputSpec("STRING"),
                        "steps": InputSpec("INT"), "cfg": InputSpec("FLOAT"),
                        "sampler_name": InputSpec("STRING"), "scheduler": InputSpec("STRING"),
                        "denoise": InputSpec("FLOAT"),
                        "model": InputSpec("MODEL", required=True),
                        "positive": InputSpec("CONDITIONING", required=True),
                        "negative": InputSpec("CONDITIONING", required=True),
                        "latent_image": InputSpec("LATENT", required=True),
                    },
                    [OutputSpec("LATENT", "LATENT")],
                    widget_input_order=(
                        "seed", "control_after_generate", "steps", "cfg",
                        "sampler_name", "scheduler", "denoise",
                    ),
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

    source = SP()
    class_types = (
        "CheckpointLoaderSimple",
        "CLIPTextEncode",
        "EmptyLatentImage",
        "KSampler",
        "VAEDecode",
        "SaveImage",
        "PrimitiveInt",
        "Reroute",
    )
    payloads = {
        class_type: schema_payload_from_node_schema(
            class_type, source.get_schema(class_type)
        )
        for class_type in class_types
    }
    snapshot = capture_schema_snapshot(
        class_types=class_types,
        request_snapshot={
            "contract_version": "schema_snapshot_v1",
            "schemas": payloads,
            "missing_classes": [],
        },
        # Explicit fixture identity is part of the captured authority.  It is
        # declared from the flat fixture contract, never inferred from UI
        # widgets or recovered through a live provider lookup.
        node_classes={
            "1": "CheckpointLoaderSimple",
            "2": "CLIPTextEncode",
            "3": "CLIPTextEncode",
            "4": "EmptyLatentImage",
            "5": "KSampler",
            "6": "VAEDecode",
            "7": "SaveImage",
        },
    )
    return FrozenSchemaSnapshotProvider(snapshot)


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
    """Build a dict mapping (scope_path, uid) → stamped node dict."""
    import copy
    index = UiGraphIndex.ingest(ui)
    return {
        (scope_path, uid): copy.deepcopy(node)
        for (scope_path, uid), node in index.node_index.items()
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
    index = UiGraphIndex.ingest(ui)
    for scope in index.scopes.values():
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
    """Native boundary markers are rejected before an empty session opens."""
    with pytest.raises(
        ValueError,
        match=(
            "unsupported_boundary_encoding.*native inputNode/outputNode markers"
            ".*explicit Python-owned boundary mapping"
        ),
    ):
        EditSession(subgraphed_wan_ui, schema_provider=_wan_schema_provider())


def test_empty_done_on_ltx_t2v(ltx_t2v_ui: dict[str, Any], ltx_t2v_provider: GraphInferredSchemaProvider) -> None:
    """Native boundary markers are rejected before an empty session opens."""
    with pytest.raises(
        ValueError,
        match=(
            "unsupported_boundary_encoding.*native inputNode/outputNode markers"
            ".*explicit Python-owned boundary mapping"
        ),
    ):
        EditSession(ltx_t2v_ui, schema_provider=ltx_t2v_provider)


def test_empty_done_on_ltx_i2v(ltx_i2v_ui: dict[str, Any], ltx_i2v_provider: GraphInferredSchemaProvider) -> None:
    """Native boundary markers are rejected before an empty session opens."""
    with pytest.raises(
        ValueError,
        match=(
            "unsupported_boundary_encoding.*native inputNode/outputNode markers"
            ".*explicit Python-owned boundary mapping"
        ),
    ):
        EditSession(ltx_i2v_ui, schema_provider=ltx_i2v_provider)


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
    code = 'cliptextencode.text = "a faithful edited prompt"'
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
    code = "ksampler.positive = cliptextencode_2.CONDITIONING_0"
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


def test_recovery_add_nodes_anchor_to_downstream_rewire_after_failed_replacement_batch(
    flat_ui: dict[str, Any],
) -> None:
    """Recovery nodes should not be dumped past the graph right edge.

    This reproduces the SDXL replacement failure shape while preserving atomic
    batch rollback: a first batch tries an invalid replacement loader and must
    leave the original graph untouched. A subsequent valid removal batch then
    constructs the intended post-removal state, after which recovery adds a
    loader/text-encode cluster and wires it back into the sampler/decoder.
    Placement must infer the downstream rewire anchors from that explicit state.
    """
    import copy

    ui = copy.deepcopy(flat_ui)
    session = EditSession(ui, schema_provider=_flat_schema_provider())
    session.render()
    before_failed_batch = copy.deepcopy(session.working_ui)

    failed = session.apply_batch(
        "dualclip = DualCLIPLoader(ckpt_name='juggernautXL_v8Rundiffusion.safetensors')\n"
        "emptylatentimage.height = 1024\n"
        "emptylatentimage.width = 1024\n"
        "ksampler.latent_image = emptylatentimage.LATENT_0\n"
        "del cliptextencode\n"
        "del cliptextencode_2\n"
        "del checkpointloadersimple\n"
        "done()\n"
    )
    assert failed.ok is False
    assert failed.landed_ops == ()
    assert session.working_ui == before_failed_batch
    assert {node["type"] for node in session.working_ui["nodes"]} >= {
        "CheckpointLoaderSimple",
        "CLIPTextEncode",
    }

    removed = session.apply_batch(
        "del cliptextencode\n"
        "del cliptextencode_2\n"
        "del checkpointloadersimple\n"
        "done()\n"
    )
    assert removed.ok is True
    assert len(removed.landed_ops) == 3

    recovered = session.apply_batch(
        "checkpointloader = CheckpointLoaderSimple(ckpt_name='juggernautXL_v8Rundiffusion.safetensors')\n"
        "positive = CLIPTextEncode(clip=checkpointloader.CLIP_1, text='a beautiful landscape, masterpiece, best quality')\n"
        "negative = CLIPTextEncode(clip=checkpointloader.CLIP_1, text='bad quality, worst quality, text, watermark')\n"
        "ksampler.model = checkpointloader.MODEL_0\n"
        "ksampler.positive = positive.CONDITIONING_0\n"
        "ksampler.negative = negative.CONDITIONING_0\n"
        "ksampler.latent_image = emptylatentimage.LATENT_0\n"
        "vaedecode.vae = checkpointloader.VAE_2\n"
        "done()\n"
    )
    assert recovered.ok is True

    by_type = {}
    for node in session.working_ui["nodes"]:
        by_type.setdefault(node["type"], []).append(node)
    sampler = by_type["KSampler"][0]
    decoder = by_type["VAEDecode"][0]
    loader = by_type["CheckpointLoaderSimple"][0]
    text_nodes = by_type["CLIPTextEncode"]

    assert loader["pos"][0] < sampler["pos"][0]
    assert all(node["pos"][0] < decoder["pos"][0] for node in text_nodes)
    assert max(node["pos"][0] for node in [loader, *text_nodes]) < decoder["pos"][0]


# ═══════════════════════════════════════════════════════════════════════
# Case (d): Native subgraph boundary fails closed
# ═══════════════════════════════════════════════════════════════════════


def test_case_d_native_subgraph_boundary_fails_closed(
    subgraphed_wan_ui: dict[str, Any],
) -> None:
    """Native ``-10/-20`` carriers cannot masquerade as Python-owned scope."""
    with pytest.raises(
        ValueError,
        match=(
            "unsupported_boundary_encoding.*native inputNode/outputNode markers"
            ".*explicit Python-owned boundary mapping"
        ),
    ):
        from_ui(
            subgraphed_wan_ui,
            schema_provider=_wan_schema_provider(),
            use_comfy_converter=False,
        )


# ═══════════════════════════════════════════════════════════════════════
# Case (e): Native-boundary Reroute graph fails closed
# ═══════════════════════════════════════════════════════════════════════


def test_case_e_reroute_analysis_ltx_i2v(
    ltx_i2v_ui: dict[str, Any], ltx_i2v_provider: GraphInferredSchemaProvider
) -> None:
    """A native-boundary Reroute graph is rejected before a session opens."""
    with pytest.raises(
        ValueError,
        match=(
            "unsupported_boundary_encoding.*native inputNode/outputNode markers"
            ".*explicit Python-owned boundary mapping"
        ),
    ):
        EditSession(ltx_i2v_ui, schema_provider=ltx_i2v_provider)


# ═══════════════════════════════════════════════════════════════════════
# Gate verification: touched region byte-identity
# ═══════════════════════════════════════════════════════════════════════


def test_gate_a_byte_identity_untouched(flat_ui: dict[str, Any]) -> None:
    """Gate A: Untouched nodes are byte-identical after a field edit."""
    import copy
    original = copy.deepcopy(flat_ui)

    session = EditSession(flat_ui, schema_provider=_flat_schema_provider())
    session.render()
    session.apply_batch('cliptextencode.text = "gate a test"')

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
    session.apply_batch("cliptextencode.text = 'gate b test'")

    done = session.done()
    assert done.ok, f"Gate B should pass: {done.summary}"
    assert "Gate B passed" in done.summary


def test_gate_c_human_readable_summary(flat_ui: dict[str, Any]) -> None:
    """Gate C: done() produces a human-readable summary of operations."""
    session = EditSession(flat_ui, schema_provider=_flat_schema_provider())
    session.render()
    session.apply_batch("cliptextencode.text = 'summary test'")

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
    """Native boundary markers are rejected before describe() can run."""
    with pytest.raises(
        ValueError,
        match=(
            "unsupported_boundary_encoding.*native inputNode/outputNode markers"
            ".*explicit Python-owned boundary mapping"
        ),
    ):
        EditSession(ltx_t2v_ui, schema_provider=ltx_t2v_provider)


def test_working_ui_unchanged_after_describe(flat_ui: dict[str, Any]) -> None:
    """describe() is side-effect-free: working_ui is unchanged."""
    import copy
    session = EditSession(flat_ui, schema_provider=_flat_schema_provider())
    session.render()
    before = copy.deepcopy(session.working_ui)

    for name in list(session.uid_by_name.keys())[:3]:
        _ = session.describe(name)

    assert session.working_ui == before, "describe() mutated working_ui!"


def test_session_snapshot_includes_render_caches_and_journal_surface(
    flat_ui: dict[str, Any],
) -> None:
    session = EditSession(flat_ui, schema_provider=_flat_schema_provider())
    session.render()
    snapshot = session._snapshot_mutable_state()
    assert set(snapshot) >= {
        "workflow",
        "history",
        "landed_ops",
        "touched_uids",
        "touched_node_ids",
        "uid_by_name",
        "name_by_uid",
        "unbound_names",
        "value_default_context",
        "render_count",
        "last_rendered_source",
        "last_rendered_workflow",
        "last_render_diagnostics",
    }
    assert "working_ui" not in snapshot
    assert snapshot["render_count"] == 1
    assert isinstance(snapshot["last_rendered_source"], str)
    assert snapshot["last_rendered_source"]


def test_apply_batch_unexpected_exception_restores_session_journal(
    flat_ui: dict[str, Any],
) -> None:
    session = EditSession(flat_ui, schema_provider=_flat_schema_provider())
    session.render()
    before_ui = json.loads(json.dumps(session.working_ui))
    before = session._snapshot_mutable_state()
    import vibecomfy.porting.edit._interpret as interpret_mod

    original_interpret = interpret_mod.interpret

    def _raise(*args, **kwargs):
        # ``working_ui`` is a read-only projection.  Dirty the retained IR
        # itself through the real interpretation seam, then verify the
        # unexpected-exception journal restores it from the snapshot.
        assert session.workflow is not None
        session.workflow.nodes.clear()
        session.workflow.edges.clear()
        session.landed_ops.append("dirty")
        session.touched_uids.add("dirty")
        session.render_count += 7
        session.last_rendered_source = "mutated"
        raise RuntimeError("apply exploded")

    interpret_mod.interpret = _raise  # type: ignore[method-assign]
    try:
        with pytest.raises(RuntimeError, match="apply exploded"):
            session.apply_batch('cliptextencode.text = "journal restore"')
    finally:
        interpret_mod.interpret = original_interpret

    assert session.working_ui == before_ui
    assert session.landed_ops == before["landed_ops"]
    assert session.touched_uids == before["touched_uids"]
    assert session.touched_node_ids == before["touched_node_ids"]
    assert dict(session.uid_by_name)
    assert dict(session.name_by_uid)
    assert session.unbound_names == before["unbound_names"]
    assert session.value_default_context == before["value_default_context"]
    assert session.render_count == before["render_count"]
    assert session.last_rendered_source == before["last_rendered_source"]
    assert session.last_rendered_workflow is before["last_rendered_workflow"]
    assert session.last_render_diagnostics == before["last_render_diagnostics"]
    assert "2" in session.name_by_uid
    assert any(
        isinstance(node, dict) and node.get("id") == 2
        for node in session.working_ui.get("nodes") or []
    )


def test_apply_batch_validation_rollback_unchanged_on_later_edit_failure(
    flat_ui: dict[str, Any],
) -> None:
    session = EditSession(flat_ui, schema_provider=_flat_schema_provider())
    session.render()
    before_ui = json.loads(json.dumps(session.working_ui))
    before_names = dict(session.uid_by_name)

    result = session.apply_batch(
        'cliptextencode.text = "journal should not see this"\n'
        "missing = CompletelyUnknownNode()\n"
    )

    assert result.ok is False
    assert result.landed_ops == ()
    assert session.working_ui == before_ui
    assert session.uid_by_name == before_names
    assert any(
        diagnostic.code == "batch_transaction_rolled_back"
        for diagnostic in result.diagnostics
    )


def test_interpret_python_view_isomorphism_on_flat(flat_ui: dict[str, Any]) -> None:
    """emit(wf) → interpret(∅, source) equals π_edit(wf) on the flat fixture."""
    from vibecomfy.ingest.normalize import from_ui
    from vibecomfy.porting.edit._interpret import interpret
    from vibecomfy.porting.emit.emit_agent_edit import emit_agent_edit_python
    from vibecomfy.workflow import VibeWorkflow, WorkflowSource
    from tests.test_ir_laws import pi_edit

    workflow = from_ui(
        flat_ui, schema_provider=_flat_schema_provider(), use_comfy_converter=False
    )
    emitted = emit_agent_edit_python(workflow)
    result = interpret(
        VibeWorkflow("empty", WorkflowSource("law")),
        emitted,
        schema_provider=_flat_schema_provider(),
    )
    assert result.ok or result.landed_ops
    assert pi_edit(result.workflow, schema_provider=_flat_schema_provider()) == pi_edit(
        workflow, schema_provider=_flat_schema_provider()
    )


def test_session_history_is_workflow_delta_pairs(flat_ui: dict[str, Any]) -> None:
    session = EditSession(flat_ui, schema_provider=_flat_schema_provider())
    wf0 = session.workflow
    session.apply_batch('cliptextencode.text = "history-1"')
    session.apply_batch('cliptextencode.text = "history-2"')
    assert len(session.history) == 2
    assert session.history[0][0] == wf0
    assert session.history[0][0] is not session.workflow
    assert "history-1" in session.history[0][1]
    assert session.history[1][0] is not wf0
    assert session.rollback()
    assert len(session.history) == 1


def test_t20_batch_transition_report_does_not_change_public_history_shape(
    flat_ui: dict[str, Any],
) -> None:
    session = EditSession(flat_ui, schema_provider=_flat_schema_provider())
    result = session.apply_batch('cliptextencode.text = "transition-report"')

    assert result.ok
    assert result.transitions
    assert result.transitions[0].occurrence == 0
    assert result.transitions[0].outcome == "staged"
    # Transition diagnostics are not a fourth history column or an authority
    # credential.  Existing replay/history callers retain their tuple API.
    assert all(len(entry) == 3 for entry in session.history)
    assert session.history[0][2] == result.landed_ops


def test_t20_public_results_and_history_do_not_alias_committed_workflow(
    flat_ui: dict[str, Any],
) -> None:
    """Published evidence may be inspected or copied without mutating commit state."""
    from dataclasses import FrozenInstanceError

    from vibecomfy.porting.edit.ops import NodeFieldTarget, SetNodeFieldOp

    session = EditSession(flat_ui, schema_provider=_flat_schema_provider())
    result = session.apply_ops(
        (
            SetNodeFieldOp(
                op="set_node_field",
                target=NodeFieldTarget("", "5", "steps"),
                value=42,
            ),
        )
    )

    assert result.ok
    assert result.workflow is not session.workflow
    assert session.history[0][0] is not session.workflow
    assert session.history[0][2][0] is not result.landed_ops[0]
    public_history = session.history
    assert isinstance(public_history, tuple)
    with pytest.raises(AttributeError):
        session.history = ()  # type: ignore[misc]
    with pytest.raises(AttributeError):
        public_history.append(public_history[0])  # type: ignore[attr-defined]
    with pytest.raises(TypeError):
        public_history[0] = public_history[0]  # type: ignore[index]
    with pytest.raises(TypeError):
        del public_history[0]  # type: ignore[misc]
    with pytest.raises(TypeError):
        list.append(public_history, public_history[0])
    with pytest.raises(FrozenInstanceError):
        result.landed_ops[0].value = 99  # type: ignore[misc]
    with pytest.raises(FrozenInstanceError):
        session.history[0][2][0].value = 99  # type: ignore[misc]

    result.workflow.nodes["5"].inputs["steps"] = 99
    history_pre_steps = public_history[0][0].nodes["5"].inputs["steps"]
    public_history[0][0].nodes["5"].inputs["steps"] = 100
    assert session.workflow.nodes["5"].inputs["steps"] == 42
    assert session.history[0][0].nodes["5"].inputs["steps"] == history_pre_steps

    second = session.apply_ops(
        (
            SetNodeFieldOp(
                op="set_node_field",
                target=NodeFieldTarget("", "5", "steps"),
                value=43,
            ),
        )
    )
    assert second.ok
    assert len(session.history) == 2
    assert session.rollback()
    assert len(session.history) == 1
    assert session.workflow.nodes["5"].inputs["steps"] == 42


def test_t20_shared_evaluator_finalizes_add_node_before_projection(
    flat_ui: dict[str, Any],
) -> None:
    """The shared evaluator, not the Python runner, owns output-port stamping."""
    from vibecomfy.porting.edit._interpret import _evaluate_operation
    from vibecomfy.porting.edit.ops import AddNodeOp, LinkSourceRef

    provider = _flat_schema_provider()
    workflow = from_ui(dict(flat_ui), schema_provider=provider, use_comfy_converter=False)
    operation = AddNodeOp(
        op="add_node",
        scope_path="",
        class_type="VAEDecode",
        fields={},
        inputs={
            "samples": LinkSourceRef("", "4", "LATENT"),
            "vae": LinkSourceRef("", "1", "VAE"),
        },
        uid="evaluator-added",
        node_id="8",
    )

    result = _evaluate_operation(
        workflow,
        operation,
        schema_provider=provider,
        source="added = VAEDecode(samples=emptylatentimage.LATENT, vae=checkpointloadersimple.VAE)",
    )

    assert result.outcome == "staged", result.diagnostics
    node = result.workflow.nodes["8"]
    assert node.uid == "evaluator-added"
    assert node.metadata["output_names"] == ["IMAGE"]
    assert node.metadata["output_types"] == ["IMAGE"]
    assert result.presentation_ui is not None
    emitted = next(
        item for item in result.presentation_ui["nodes"]
        if item.get("properties", {}).get("vibecomfy_uid") == "evaluator-added"
    )
    assert emitted["outputs"][0]["name"] == "IMAGE"


@pytest.mark.parametrize("forgery", ("order", "topology"))
def test_t20_shared_evaluator_rejects_forged_projection(
    flat_ui: dict[str, Any],
    monkeypatch: pytest.MonkeyPatch,
    forgery: str,
) -> None:
    """Projection furniture cannot authorize forged order or topology."""
    import copy

    import vibecomfy.porting.emit.ui as ui_module
    from vibecomfy.porting.edit._interpret import _evaluate_operation
    from vibecomfy.porting.edit.ops import (
        LinkTargetRef,
        NodeFieldTarget,
        RemoveLinkOp,
        SetNodeFieldOp,
    )

    provider = _flat_schema_provider()
    workflow = from_ui(dict(flat_ui), schema_provider=provider, use_comfy_converter=False)
    operation = (
        SetNodeFieldOp(
            op="set_node_field",
            target=NodeFieldTarget("", "5", "steps"),
            value=42,
        )
        if forgery == "order"
        else RemoveLinkOp(
            op="remove_link",
            target=LinkTargetRef("", "5", "latent_image"),
        )
    )
    original_emit = ui_module.emit_ui_json

    def forged_emit(*args: Any, **kwargs: Any) -> dict[str, Any]:
        payload = original_emit(*args, **kwargs)
        if kwargs.get("prior_ui_payload") is None:
            return payload
        forged = copy.deepcopy(payload)
        if forgery == "order":
            forged["nodes"] = list(reversed(forged.get("nodes", [])))
        else:
            forged.setdefault("links", []).append([999, 1, 0, 7, 0, "IMAGE"])
        return forged

    monkeypatch.setattr(ui_module, "emit_ui_json", forged_emit)
    result = _evaluate_operation(workflow, operation, schema_provider=provider)

    assert result.outcome == "rejected"
    codes = {diagnostic.code for diagnostic in result.diagnostics}
    assert (
        "full_ui_node_order_changed_unattributed" in codes
        or "full_ui_link_added_unattributed" in codes
    )
    assert result.workflow == workflow


def test_t20_lg_id_normalization_lowers_canonical_uid(
    flat_ui: dict[str, Any],
) -> None:
    """A LiteGraph id is normalized before the shared lowerer applies it."""
    import copy

    from vibecomfy.porting.edit._interpret import _interpret_ops
    from vibecomfy.porting.edit.ops import NodeFieldTarget, SetNodeFieldOp
    from vibecomfy.schema.types import FrozenSchemaSnapshotProvider, capture_schema_snapshot

    ui = copy.deepcopy(flat_ui)
    for node in ui["nodes"]:
        if node.get("id") == 5:
            node.setdefault("properties", {})["vibecomfy_uid"] = "my_custom"
    base = _flat_schema_provider().snapshot
    schemas = {name: dict(payload) for name, payload in base.schemas.items()}
    provider = FrozenSchemaSnapshotProvider(
        capture_schema_snapshot(
            class_types=tuple(schemas),
            request_snapshot={
                "contract_version": "schema_snapshot_v1",
                "schemas": schemas,
                "missing_classes": [],
            },
            node_classes={**dict(base.node_classes), "my_custom": "KSampler"},
        )
    )
    workflow = from_ui(dict(ui), schema_provider=provider, use_comfy_converter=False)
    submitted = SetNodeFieldOp(
        op="set_node_field",
        target=NodeFieldTarget("", "5", "steps"),
        value=42,
    )

    result = _interpret_ops(workflow, (submitted,), schema_provider=provider)

    assert result.ok
    assert result.transitions[0].submitted == submitted
    assert result.transitions[0].normalized.target.uid == "my_custom"
    assert result.transitions[0].lowered[0].target.uid == "my_custom"
    assert result.workflow.nodes["5"].inputs["steps"] == 42


def test_t20_genuine_lint_rejection_never_reaches_lowering_or_commit(
    flat_ui: dict[str, Any], monkeypatch: pytest.MonkeyPatch,
) -> None:
    """A rejected orphan add is report evidence, never mutation authority."""
    import vibecomfy.porting.edit._ir_utils as ir_utils
    from vibecomfy.porting.edit._interpret import _evaluate_operation
    from vibecomfy.porting.edit.ops import AddNodeOp

    provider = _flat_schema_provider()
    workflow = from_ui(dict(flat_ui), schema_provider=provider, use_comfy_converter=False)
    operation = AddNodeOp(
        op="add_node",
        scope_path="",
        class_type="KSampler",
        fields={"steps": 30},
        inputs={},
        uid="orphan-probe",
        node_id="8",
    )
    lower_calls: list[object] = []
    original_lower = ir_utils.lower_edit_operation

    def observed_lower(*args: Any, **kwargs: Any) -> Any:
        lower_calls.append(args[1])
        return original_lower(*args, **kwargs)

    monkeypatch.setattr(ir_utils, "lower_edit_operation", observed_lower)
    evaluated = _evaluate_operation(
        workflow, operation, schema_provider=provider,
    )

    assert evaluated.outcome == "rejected"
    assert evaluated.lint_disposition == "rejected"
    assert evaluated.diagnostics[0].code == "orphan_add_node"
    assert evaluated.lowered == ()
    assert evaluated.workflow == workflow
    assert lower_calls == []

    session = EditSession(flat_ui, schema_provider=provider)
    before = session.workflow
    result = session.apply_ops((operation,))

    assert result.ok is False
    assert result.lint_result is not None
    assert result.lint_result.apply_eligible is False
    assert result.transitions[0].outcome == "rejected"
    assert result.transitions[0].lint_disposition == "rejected"
    assert result.transitions[0].diagnostics[0].code == "orphan_add_node"
    assert result.landed_ops == ()
    assert session.workflow == before
    assert session.revision == 0
    assert session.history == ()
    assert lower_calls == []


def test_t20_complete_typed_batch_preserves_future_orphan_wiring_intent(
    flat_ui: dict[str, Any],
) -> None:
    """Future syntax informs orphan lint without granting future graph authority."""
    from vibecomfy.porting.edit._interpret import _interpret_ops
    from vibecomfy.porting.edit.ops import (
        AddNodeOp,
        LinkSourceRef,
        LinkTargetRef,
        UpsertLinkOp,
    )

    provider = _flat_schema_provider()
    workflow = from_ui(dict(flat_ui), schema_provider=provider, use_comfy_converter=False)
    add = AddNodeOp(
        op="add_node",
        scope_path="",
        class_type="EmptyLatentImage",
        fields={"width": 768, "height": 768, "batch_size": 1},
        inputs={},
        uid="wired-probe",
        node_id="8",
    )
    wire = UpsertLinkOp(
        op="upsert_link",
        source=LinkSourceRef("", "wired-probe", "LATENT"),
        target=LinkTargetRef("", "5", "latent_image"),
    )

    result = _interpret_ops(workflow, (add, wire), schema_provider=provider)

    assert result.ok, result.diagnostics
    assert [item.outcome for item in result.transitions] == ["staged", "staged"]
    assert [item.lint_disposition for item in result.transitions] == ["passed", "passed"]
    assert result.workflow.nodes["8"].uid == "wired-probe"
    assert any(
        edge.from_node == "8" and edge.to_node == "5" and edge.to_input == "latent_image"
        for edge in result.workflow.edges
    )


def test_t20_raw_and_canonical_output_aliases_replay_to_identical_links() -> None:
    """Authored ``IMAGE`` and replay ``IMAGE_0`` share one output identity."""
    from vibecomfy.porting.edit.ops import (
        AddNodeOp,
        LinkSourceRef,
        LinkTargetRef,
        UpsertLinkOp,
    )

    schemas = {
        "KSampler": NodeSchema(
            "KSampler", "test", {}, [OutputSpec("IMAGE", "IMAGE")]
        ),
        "PreviewImage": NodeSchema(
            "PreviewImage",
            "test",
            {"images": InputSpec("IMAGE", required=True)},
            [],
        ),
    }
    snapshot = capture_schema_snapshot(
        class_types=tuple(schemas),
        request_snapshot={
            "contract_version": "schema_snapshot_v1",
            "schemas": {
                class_type: schema_payload_from_node_schema(class_type, schema)
                for class_type, schema in schemas.items()
            },
            "missing_classes": [],
        },
        node_classes={
            "sampler": "KSampler",
            "existing_preview": "PreviewImage",
            "preview": "PreviewImage",
        },
    )
    provider = FrozenSchemaSnapshotProvider(snapshot)
    ui = {
        "last_node_id": 2,
        "last_link_id": 0,
        "nodes": [
            {
                "id": 1,
                "type": "KSampler",
                "properties": {"vibecomfy_uid": "sampler"},
                "inputs": [],
                "outputs": [
                    {"name": "IMAGE", "type": "IMAGE", "links": []}
                ],
            },
            {
                "id": 2,
                "type": "PreviewImage",
                "properties": {"vibecomfy_uid": "existing_preview"},
                "inputs": [
                    {"name": "images", "type": "IMAGE", "link": None}
                ],
                "outputs": [],
            },
        ],
        "links": [],
        "groups": [],
    }
    posts: list[VibeWorkflow] = []
    for authored_slot in ("IMAGE", "IMAGE_0"):
        session = EditSession(ui, schema_provider=provider)
        result = session.apply_ops(
            (
                AddNodeOp(
                    op="add_node",
                    scope_path="",
                    class_type="PreviewImage",
                    fields={},
                    inputs={
                        "images": LinkSourceRef(
                            "", "sampler", authored_slot
                        )
                    },
                    uid="preview",
                    node_id="3",
                ),
                UpsertLinkOp(
                    op="upsert_link",
                    source=LinkSourceRef("", "sampler", authored_slot),
                    target=LinkTargetRef("", "existing_preview", "images"),
                ),
            )
        )

        assert result.ok, result.diagnostics
        assert session.revision == 1
        assert len(result.landed_ops) == 2
        assert result.landed_ops[0].inputs["images"].output_slot == "IMAGE_0"
        assert result.landed_ops[1].source.output_slot == "IMAGE_0"
        assert {
            (edge.from_node, edge.from_output, edge.to_node, edge.to_input)
            for edge in session.workflow.edges
        } == {
            ("1", "0", "2", "images"),
            ("1", "0", "3", "images"),
        }
        posts.append(session.workflow)

    assert posts[0] == posts[1]


@pytest.mark.parametrize(
    ("marked_missing", "expected_code"),
    (
        (False, "missing_touched_schema"),
        (True, "missing_touched_schema"),
    ),
)
def test_t20_frozen_unknown_class_never_queries_advisory_provider(
    flat_ui: dict[str, Any], marked_missing: bool, expected_code: str,
) -> None:
    """Touched-schema diagnostics are derived only from frozen catalog evidence."""
    frozen = _flat_schema_provider()
    retained_snapshot = frozen.snapshot
    if marked_missing:
        retained_snapshot = capture_schema_snapshot(
            class_types=(*tuple(frozen.snapshot.schemas), "LiveOnlyAfterIngress"),
            request_snapshot={
                "contract_version": "schema_snapshot_v1",
                "schemas": {
                    class_type: dict(payload)
                    for class_type, payload in frozen.snapshot.schemas.items()
                },
                "missing_classes": ["LiveOnlyAfterIngress"],
            },
            node_classes=dict(frozen.snapshot.node_classes),
        )
    live_calls: list[str] = []

    class PoisonAdvisoryProvider:
        snapshot = retained_snapshot

        def get_schema(self, class_type: str) -> NodeSchema | None:
            live_calls.append(class_type)
            # If consulted, this would make the class appear live-only.  A
            # frozen session must neither call it nor let it affect the code.
            return NodeSchema(class_type, "live-only", {}, [])

    session = EditSession(flat_ui, schema_provider=PoisonAdvisoryProvider())
    before = session.workflow
    result = session.apply_batch("late = LiveOnlyAfterIngress()")

    assert result.ok is False
    assert result.apply_eligible is False
    assert live_calls == []
    assert result.diagnostics[0].code == expected_code
    assert len(result.transitions) == 1
    assert result.transitions[0].outcome == "rejected"
    assert result.transitions[0].diagnostics[0].code == expected_code
    assert session.workflow == before
    assert session.revision == 0
    assert session.history == ()


def test_t20_source_and_typed_adapters_cross_the_identical_evaluator_boundary(
    flat_ui: dict[str, Any], monkeypatch: pytest.MonkeyPatch,
) -> None:
    """Neither adapter can apply an operation around the shared evaluator."""
    import vibecomfy.porting.edit._interpret as interpret_module
    from vibecomfy.porting.edit._interpret import OperationEvaluation, interpret
    from vibecomfy.porting.edit.ops import NodeTarget, SetModeOp

    provider = _flat_schema_provider()
    workflow = from_ui(dict(flat_ui), schema_provider=provider, use_comfy_converter=False)
    typed = SetModeOp(op="set_mode", target=NodeTarget("", "5"), mode=2)
    calls: list[object] = []

    def reject_at_shared_boundary(
        cursor: VibeWorkflow,
        operation: object,
        **_kwargs: Any,
    ) -> OperationEvaluation:
        calls.append(operation)
        return OperationEvaluation(
            workflow=cursor,
            normalized=operation,  # type: ignore[arg-type]
            outcome="rejected",
            diagnostics=(
                CompactDiagnostic(
                    "shared_boundary_probe",
                    "the one evaluator rejected this operation",
                    "error",
                ),
            ),
            lint_disposition="rejected",
        )

    monkeypatch.setattr(
        interpret_module, "_evaluate_operation", reject_at_shared_boundary
    )
    source_result = interpret(
        workflow, "ksampler.mode = 2", schema_provider=provider,
    )
    typed_result = interpret(workflow, (typed,), schema_provider=provider)

    assert calls == [typed, typed]
    for result in (source_result, typed_result):
        assert result.ok is False
        assert result.workflow == workflow
        assert result.landed_ops == ()
        assert len(result.transitions) == 1
        assert result.transitions[0].outcome == "rejected"
        assert result.transitions[0].lint_disposition == "rejected"
        assert result.transitions[0].diagnostics[0].code == "shared_boundary_probe"


def test_t20_initial_refused_projection_rejects_without_publication(
    flat_ui: dict[str, Any], monkeypatch: pytest.MonkeyPatch,
) -> None:
    """No synthetic lint pass is allowed when initial UI projection refuses."""
    from vibecomfy.porting.edit._interpret import _interpret_ops
    from vibecomfy.porting.edit.ops import NodeFieldTarget, SetNodeFieldOp
    from vibecomfy.porting.refuse import RefusedEmit

    provider = _flat_schema_provider()
    workflow = from_ui(dict(flat_ui), schema_provider=provider, use_comfy_converter=False)
    submitted = SetNodeFieldOp(
        op="set_node_field",
        target=NodeFieldTarget("", "5", "steps"),
        value=42,
    )

    def refuse(*_args: Any, **_kwargs: Any) -> Any:
        raise RefusedEmit("initial projection refused", {})

    monkeypatch.setattr("vibecomfy.porting.emit.ui.emit_ui_json", refuse)
    result = _interpret_ops(workflow, (submitted,), schema_provider=provider)

    assert result.ok is False
    assert result.landed_ops == ()
    assert result.workflow == workflow
    assert result.diagnostics[0].code == "presentation_rejected"


def test_t20_candidate_refused_projection_rejects_atomically(
    flat_ui: dict[str, Any], monkeypatch: pytest.MonkeyPatch,
) -> None:
    """A refused post-edit projection cannot publish the detached cursor."""
    from vibecomfy.porting.edit._interpret import _interpret_ops
    from vibecomfy.porting.edit.ops import NodeFieldTarget, SetNodeFieldOp
    from vibecomfy.porting.refuse import RefusedEmit

    provider = _flat_schema_provider()
    workflow = from_ui(dict(flat_ui), schema_provider=provider, use_comfy_converter=False)
    submitted = SetNodeFieldOp(
        op="set_node_field",
        target=NodeFieldTarget("", "5", "steps"),
        value=42,
    )
    original_emit = __import__("vibecomfy.porting.emit.ui", fromlist=["emit_ui_json"]).emit_ui_json
    calls = 0

    def refuse_candidate(*args: Any, **kwargs: Any) -> Any:
        nonlocal calls
        calls += 1
        if calls == 1:
            return original_emit(*args, **kwargs)
        raise RefusedEmit("candidate projection refused", {})

    monkeypatch.setattr("vibecomfy.porting.emit.ui.emit_ui_json", refuse_candidate)
    result = _interpret_ops(workflow, (submitted,), schema_provider=provider)

    assert calls == 2
    assert result.ok is False
    assert result.landed_ops == ()
    assert result.workflow == workflow
    assert any(item.code == "presentation_rejected" for item in result.diagnostics)


def test_t20_missing_interpretation_report_fails_closed_without_commit(
    flat_ui: dict[str, Any], monkeypatch: pytest.MonkeyPatch,
) -> None:
    """The route cannot fabricate lint evidence when interpretation omits it."""
    from dataclasses import replace

    import vibecomfy.porting.edit._interpret as interpret_mod

    session = EditSession(flat_ui, schema_provider=_flat_schema_provider())
    before = session.workflow
    before_revision = session.revision
    before_history = tuple(session.history)
    original_interpret = interpret_mod.interpret

    def _missing_report(*args: Any, **kwargs: Any) -> Any:
        interpreted = original_interpret(*args, **kwargs)
        return replace(interpreted, lint_result=None)

    monkeypatch.setattr(interpret_mod, "interpret", _missing_report)
    result = session.apply_batch('cliptextencode.text = "missing-report"')

    assert result.ok is False
    assert result.apply_eligible is False
    assert result.landed_ops == ()
    assert any(
        diagnostic.code == "internal_interpretation_contract"
        for diagnostic in result.diagnostics
    )
    assert session.workflow == before
    assert session.revision == before_revision
    assert session.history == before_history
    assert session.landed_ops == []


def test_t20_failed_batch_discards_provisional_transition_authority(
    flat_ui: dict[str, Any],
) -> None:
    session = EditSession(flat_ui, schema_provider=_flat_schema_provider())
    before_workflow = session.workflow
    before_history = tuple(session.history)
    result = session.apply_batch(
        'cliptextencode.text = "provisional"\n'
        "missing = CompletelyUnknownNode()\n"
    )

    assert result.ok is False
    assert session.workflow == before_workflow
    assert session.history == before_history
    assert session.landed_ops == []
    # A failed transaction may report diagnostics, but never exposes staged
    # operations as committed transition evidence.
    assert not result.apply_eligible


def test_t20_lint_rejected_transition_blocks_batch_commit(
    flat_ui: dict[str, Any], monkeypatch: pytest.MonkeyPatch,
) -> None:
    """Canonical operation rejection is a transaction rejection, never report-only."""
    import vibecomfy.porting.edit._interpret as interpret_mod
    from vibecomfy.porting.edit._interpret import OperationEvaluation

    session = EditSession(flat_ui, schema_provider=_flat_schema_provider())
    before = session.workflow
    before_revision = session.revision
    canonical_calls: list[object] = []
    original_evaluate = interpret_mod._evaluate_operation

    def _reject_canonical(workflow, operation, *, schema_provider, **kwargs):
        canonical_calls.append(operation)
        evaluated = original_evaluate(
            workflow, operation, schema_provider=schema_provider, **kwargs
        )
        return OperationEvaluation(
            workflow=workflow,
            normalized=evaluated.normalized,
            lowered=evaluated.lowered,
            outcome="rejected",
            diagnostics=(
                CompactDiagnostic(
                    "forced_rejection",
                    "canonical operation boundary rejected this operation",
                    "error",
                ),
            ),
        )

    monkeypatch.setattr(interpret_mod, "_evaluate_operation", _reject_canonical)
    result = session.apply_batch('cliptextencode.text = "T20-probe"')

    assert canonical_calls
    assert result.ok is False
    assert not result.apply_eligible
    assert result.landed_ops == ()
    assert result.transitions[0].outcome == "rejected"
    assert result.transitions[0].diagnostics[0].code == "forced_rejection"
    assert session.workflow == before
    assert session.revision == before_revision
    assert session.history == ()


def test_t20_apply_rollback_restores_transient_name_maps(
    flat_ui: dict[str, Any], monkeypatch: pytest.MonkeyPatch,
) -> None:
    session = EditSession(flat_ui, schema_provider=_flat_schema_provider())
    before_names = dict(getattr(session, "_transient_name_index", {}))
    before_uids = dict(getattr(session, "_transient_uid_index", {}))

    def _raise_after_interpret(*args, **kwargs):
        raise RuntimeError("field changes injected failure")

    monkeypatch.setattr(session, "_build_field_changes", _raise_after_interpret)
    with pytest.raises(RuntimeError, match="field changes"):
        session.apply_batch(
            'newnode = CLIPTextEncode(clip=checkpointloadersimple.CLIP, text="new")'
        )

    assert dict(getattr(session, "_transient_name_index", {})) == before_names
    assert dict(getattr(session, "_transient_uid_index", {})) == before_uids
    assert "newnode" not in session.uid_by_name


def test_t20_unclaimed_list_valued_mutation_fails_final_agreement(
    flat_ui: dict[str, Any], monkeypatch: pytest.MonkeyPatch,
) -> None:
    import vibecomfy.porting.edit._interpret as interpret_mod

    session = EditSession(flat_ui, schema_provider=_flat_schema_provider())
    original_interpret = interpret_mod.interpret

    def _tamper(*args, **kwargs):
        result = original_interpret(*args, **kwargs)
        result.workflow.nodes["2"].inputs["unattributed_list"] = [123]
        return result

    monkeypatch.setattr(interpret_mod, "interpret", _tamper)
    result = session.apply_batch('cliptextencode.text = "T20-probe"')

    assert result.ok is False
    assert not result.apply_eligible
    assert result.landed_ops == ()
    assert "unattributed_list" not in session.workflow.nodes["2"].inputs


def test_t20_nested_transition_and_diagnostic_details_are_deeply_immutable(
    flat_ui: dict[str, Any], monkeypatch: pytest.MonkeyPatch,
) -> None:
    del flat_ui, monkeypatch
    details = {"nested": ["diagnostic"]}
    diagnostic = CompactDiagnostic("forced_rejection", "forced", "error", detail=details)
    report = OperationTransition(
        occurrence=0,
        submitted={"value": {"nested": ["submitted"]}},
        normalized={"value": {"nested": ["normalized"]}},
        outcome="rejected",
        diagnostics=(diagnostic,),
    )

    details["nested"].append("mutated")
    with pytest.raises((TypeError, AttributeError)):
        report.diagnostics[0].detail["nested"].append("alias")
    assert "mutated" not in repr(report.diagnostics[0].detail)
    with pytest.raises((TypeError, AttributeError)):
        report.submitted["value"]["nested"].append("alias")


def test_t20_original_ui_has_no_mutable_builtin_container_storage(
    flat_ui: dict[str, Any],
) -> None:
    """Builtin descriptors and caller aliases cannot rewrite presentation custody."""
    source = deepcopy(flat_ui)
    expected = deepcopy(flat_ui)
    session = EditSession(source, schema_provider=_flat_schema_provider())
    exposed = session.original_ui
    working_before = session.working_ui

    with pytest.raises(TypeError):
        exposed["nodes"][0]["title"] = "ordinary mutation"
    with pytest.raises(TypeError):
        dict.__setitem__(exposed["nodes"][0], "pos", [9876, 5432])
    with pytest.raises(TypeError):
        list.append(exposed["nodes"], {"id": 999, "type": "Forged"})

    source["nodes"][0]["pos"] = [1234, 5678]
    source["nodes"].append({"id": 999, "type": "Forged"})

    assert session.original_ui == expected
    assert deepcopy(session.original_ui) == expected
    assert session.working_ui == working_before
    assert session.revision == 0


# ── T20 / R3 strict sidecar boundary fixtures ─────────────────────────────────


def _t20_connected_workflow() -> VibeWorkflow:
    workflow = VibeWorkflow("t20-sidecar", WorkflowSource("t20-sidecar"))
    workflow.nodes["a"] = VibeNode(
        "a", "Source", uid="source", native_output_names=["out"]
    )
    workflow.nodes["b"] = VibeNode(
        "b", "Target", uid="target", native_input_names=["in"]
    )
    workflow.edges.append(VibeEdge("a", "0", "b", "0"))
    return workflow


def _t20_connected_sidecar(workflow: VibeWorkflow) -> dict[str, Any]:
    return {
        "format_version": 1,
        "bind": {
            "workflow_identity": workflow.id,
            "semantic_digest": workflow.semantic_digest(),
        },
        "nodes": {"source": {}, "target": {}},
        "links": [
            {
                "edge_ref": {
                    "scope_path": "",
                    "from_uid": "source",
                    "from_port": 0,
                    "to_uid": "target",
                    "to_port": 0,
                },
                "occurrence_index": 0,
            }
        ],
        "groups": [],
        "canvas": {},
    }


@pytest.mark.parametrize("foreign_keys", [("edge_ref", "virtual_wire_ref"), ()])
def test_t20_sidecar_link_requires_exactly_one_semantic_foreign_key(
    foreign_keys: tuple[str, ...],
) -> None:
    workflow = _t20_connected_workflow()
    valid = _t20_connected_sidecar(workflow)

    # The valid control proves that the fixture reaches the link boundary.
    assert len(validate_sidecar(valid, workflow)["links"]) == 1

    invalid = json.loads(json.dumps(valid))
    link = invalid["links"][0]
    edge_ref = link.pop("edge_ref")
    if "edge_ref" in foreign_keys:
        link["edge_ref"] = edge_ref
    if "virtual_wire_ref" in foreign_keys:
        link["virtual_wire_ref"] = {
            "scope_path": "",
            "name": "wire",
            "leg_index": 0,
        }

    with pytest.raises(
        WorkflowBundleError, match="exactly one semantic foreign key"
    ):
        validate_sidecar(invalid, workflow)


def test_t20_sidecar_rejects_ordinary_edge_across_structural_scopes() -> None:
    from vibecomfy.identity.scope import compose_scope_path, sg_key
    from vibecomfy.identity.uid import make_uid

    workflow = VibeWorkflow("t20-cross-scope", WorkflowSource("t20-cross-scope"))
    left_definition = {
        "name": "left-definition",
        "nodes": [{"id": 10, "uid": "left", "class_type": "Source"}],
        "links": [],
    }
    right_definition = {
        "name": "right-definition",
        "nodes": [{"id": 20, "uid": "right", "class_type": "Target"}],
        "links": [],
    }
    workflow.definitions = {
        "left": left_definition,
        "right": right_definition,
    }
    left_scope = compose_scope_path((sg_key(left_definition),))
    right_scope = compose_scope_path((sg_key(right_definition),))
    sidecar = {
        "format_version": 1,
        "bind": {
            "workflow_identity": workflow.id,
            "semantic_digest": workflow.semantic_digest(),
        },
        "nodes": {
            make_uid(left_scope, "left"): {},
            make_uid(right_scope, "right"): {},
        },
        "links": [],
        "groups": [],
        "canvas": {},
    }

    # The valid control proves identity, digest, scopes, and node custody.
    assert validate_sidecar(sidecar, workflow)["links"] == []

    sidecar["links"] = [
        {
            "edge_ref": {
                "scope_path": left_scope,
                "from_uid": "left",
                "from_port": 0,
                "to_uid": "right",
                "to_port": 0,
            },
            "occurrence_index": 0,
        }
    ]
    with pytest.raises(WorkflowBundleError, match="semantic edge"):
        validate_sidecar(sidecar, workflow)
