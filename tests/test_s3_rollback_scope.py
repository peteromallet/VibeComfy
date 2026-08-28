"""S3 rollback scope — Liberating Structure."""
import pytest
from vibecomfy.schema import InputSpec, NodeSchema, OutputSpec, capture_schema_snapshot, FrozenSchemaSnapshotProvider
from vibecomfy.porting import EditSession
from vibecomfy.porting.edit._interpret import interpret
from vibecomfy.workflow import VibeWorkflow

def _make_provider_and_snapshot():
    # Known schemas
    object_info = {
        "SourceOne": {"input": {"required": {}}, "output": ["IMAGE"]},
        "Dest": {"input": {"required": {"value": ["IMAGE", {}]}}, "output": []},
        "AudioFilter": {"input": {"required": {"image": ["IMAGE", {}]}}, "output": ["AUDIO"]},
        "PassThroughImage": {"input": {"required": {"image": ["IMAGE", {}]}}, "output": ["IMAGE"]},
        "SaveImage": {"input": {"required": {"images": ["IMAGE", {}]}}, "output": []},
    }
    class_types = ["SourceOne", "Dest", "AudioFilter", "PassThroughImage", "SaveImage"]
    # Also include SVDSimpleImg2Vid as known for read-only test? We'll handle separately
    node_classes = {
        "src": "SourceOne",
        "dst": "Dest",
        "audiosep": "AudioSeparation",
        "svd": "SVDSimpleImg2Vid",
        "save": "SaveImage",
    }
    # Mark AudioSeparation and SVDSimpleImg2Vid as missing
    class_types_with_missing = class_types + ["AudioSeparation", "SVDSimpleImg2Vid"]
    # But we need to tell snapshot which are missing vs known
    # capture_schema_snapshot takes class_types and object_info; missing are those not in object_info?
    # Actually we need to pass node_classes that includes missing, and object_info only for known.
    # The snapshot will compute missing as those in node_classes but not in object_info or those in missing_classes.
    # Let's use the helper that directly marks missing by including them in node_classes but not in object_info
    # and also ensure they are in missing set via not providing their schema.
    snapshot = capture_schema_snapshot(
        class_types=class_types_with_missing,
        connected_object_info=object_info,
        connected_object_info_verified=True,
        node_classes=node_classes,
    )
    provider = FrozenSchemaSnapshotProvider(snapshot)
    return provider, snapshot

def _make_workflow():
    # Create a simple workflow via EditSession then extract workflow
    raw = {
        "last_node_id": 10,
        "last_link_id": 0,
        "nodes": [
            {"id": 1, "type": "SourceOne", "mode": 0, "pos": [0,0], "size": [210,58], "outputs": [{"name": "IMAGE", "type": "IMAGE"}], "properties": {"vibecomfy_uid": "src"}},
            {"id": 2, "type": "Dest", "mode": 0, "pos": [250,0], "size": [210,58], "inputs": [{"name": "value", "type": "IMAGE"}], "properties": {"vibecomfy_uid": "dst"}},
            {"id": 3, "type": "AudioSeparation", "mode": 0, "pos": [500,0], "size": [210,58], "inputs": [{"name": "audio", "type": "AUDIO"}], "properties": {"vibecomfy_uid": "audiosep"}},
            {"id": 4, "type": "SVDSimpleImg2Vid", "mode": 0, "pos": [600,0], "size": [210,58], "outputs": [{"name": "IMAGE", "type": "IMAGE"}], "properties": {"vibecomfy_uid": "svd"}},
            {"id": 5, "type": "SaveImage", "mode": 0, "pos": [750,0], "size": [210,58], "inputs": [{"name": "images", "type": "IMAGE"}], "properties": {"vibecomfy_uid": "save"}},
        ],
        "links": [],
        "groups": [],
    }
    # Use a simple provider to create workflow via EditSession, then return workflow
    # We need a provider that at least knows SourceOne etc. to ingest
    from vibecomfy.schema import NodeSchema as NS, OutputSpec as OS, InputSpec as IS
    class DummyProvider:
        def get_schema(self, ct):
            return None
        def get(self, ct):
            return None
    sess = EditSession(raw, schema_provider=DummyProvider())
    return sess.workflow

def test_add_node_persists_despite_downstream_missing_schema():
    provider, snap = _make_provider_and_snapshot()
    wf = _make_workflow()
    # Batch: add AudioFilter then wire to missing AudioSeparation
    batch = "flt = AudioFilter(image=src.IMAGE)\naudiosep.audio = flt.AUDIO_0\n"
    res = interpret(wf, batch, schema_provider=provider)
    # Should preserve add, not rollback
    assert res.landed_ops, "landed should preserve add"
    assert any(getattr(op, "op", None) == "add_node" for op in res.landed_ops), "add_node must be landed"
    assert res.ok is False, f"should be not ok, got {res.ok} diagnostics {[(d.code, d.detail) for d in res.diagnostics]}"
    diag_codes = {d.code for d in res.diagnostics}
    assert "requires_custom_nodes" in diag_codes, f"expected requires_custom_nodes, got {diag_codes}"
    # Wire should be typed refusal
    wire = next((s for s in res.statements if s.op_kind == "upsert_link"), None)
    assert wire is not None
    assert wire.reason == "requires_custom_nodes"
    # Workflow should contain AudioFilter
    assert any(n.class_type == "AudioFilter" for n in res.workflow.nodes.values())
    # Ensure add not rolled back
    for stmt in res.statements:
        if stmt.op_kind == "node_call":
            assert stmt.status == "applied", "add should stay applied"

def test_readonly_source_missing_edge_is_skipped():
    provider, snap = _make_provider_and_snapshot()
    wf = _make_workflow()
    # Wire from missing source SVD to known SaveImage -> should be allowed (read-only skip)
    batch = "save.images = svd.IMAGE\n"
    res = interpret(wf, batch, schema_provider=provider)
    # Should be ok (allowed)
    assert res.ok is True, f"read-only edge should be allowed, got ok={res.ok} diags {res.diagnostics} stmts {[(s.op_kind, s.reason, s.status) for s in res.statements]}"
    assert res.landed_ops, "wire should land"
    assert any(getattr(op, "op", None) == "upsert_link" for op in res.landed_ops)

def test_pure_missing_target_still_typed_not_rollback_via_interpret():
    provider, snap = _make_provider_and_snapshot()
    wf = _make_workflow()
    batch = "flt = AudioFilter(image=src.IMAGE)\naudiosep.audio = flt.AUDIO_0\n"
    res = interpret(wf, batch, schema_provider=provider)
    assert res.landed_ops
    assert any(getattr(op, "op", None) == "add_node" for op in res.landed_ops)
    assert res.ok is False
    assert any(d.code == "requires_custom_nodes" for d in res.diagnostics)
    wire = next((s for s in res.statements if s.op_kind == "upsert_link"), None)
    assert wire.reason == "requires_custom_nodes"
    assert any(n.class_type == "AudioFilter" for n in res.workflow.nodes.values())
