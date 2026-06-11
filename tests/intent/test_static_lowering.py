"""Tests for static lowering: data model and loop extraction (T3).

Covers:
- LoweringResult, LoweringEvidence, LoopLoweringPlan, LoweringDiagnostic data shapes
- Loop node discovery (vibecomfy.loop only)
- Loop plan extraction for bounded literal seed/prompt/text loops
- Rejection of unsupported variables, dynamic counts, non-literal over values
- Atomic failure: any invalid loop fails the full LoweringResult
"""

from __future__ import annotations

import warnings
from typing import Any

from vibecomfy.contracts.intent_nodes import (
    INTENT_LOOP_MAX_ITERATIONS,
    intent_node_properties,
)
from vibecomfy.porting.lowering import (
    HORIZONTAL_STRIDE,
    LAYOUT_POLICY_DESCRIPTOR,
    LoopBodyBoundary,
    LoopLoweringPlan,
    LoweringBoundaryInput,
    LoweringBoundaryOutput,
    LoweringDiagnostic,
    LoweringEvidence,
    LoweringResult,
    discover_body_boundary,
    SUPPORTED_LOOP_VARIABLES,
    discover_loop_nodes,
    extract_loop_plan,
    lower_workflow,
)
from vibecomfy.porting.emit.ui import emit_ui_json
from vibecomfy.schema.provider import InputSpec, NodeSchema, OutputSpec
from vibecomfy.workflow import VibeNode, VibeWorkflow, WorkflowSource


# ---------------------------------------------------------------------------
# Helpers
# ---------------------------------------------------------------------------


def _make_workflow(name: str = "test-lower") -> VibeWorkflow:
    """Create an empty workflow for testing."""
    return VibeWorkflow(name, WorkflowSource(name))


def _make_loop_node(
    node_id: str,
    *,
    uid: str = "",
    var: str = "seed",
    count: int = 3,
    over: list | None = None,
    extra_intent: dict | None = None,
) -> VibeNode:
    """Create a vibecomfy.loop node with standard loop intent."""
    intent: dict[str, object] = {"var": var}
    if over is not None:
        intent["over"] = over
    else:
        intent["count"] = count
    if extra_intent:
        intent.update(extra_intent)

    properties = intent_node_properties(
        kind="loop",
        uid=uid or f"loop-{node_id}",
        intent=intent,
        inputs=[("image", "IMAGE")],
        outputs=[("image", "IMAGE")],
    )
    return VibeNode(
        id=node_id,
        class_type="vibecomfy.loop",
        uid=uid or f"loop-{node_id}",
        metadata={"_ui": {"properties": properties}},
    )


def _make_ksample_node(node_id: str) -> VibeNode:
    """Create a minimal KSampler node."""
    return VibeNode(
        id=node_id,
        class_type="KSampler",
        inputs={
            "seed": 42,
            "steps": 20,
            "cfg": 7.0,
            "sampler_name": "euler",
            "scheduler": "normal",
            "denoise": 1.0,
            "model": ["4", 0],
            "positive": ["5", 0],
            "negative": ["6", 0],
            "latent_image": ["7", 0],
        },
    )


def _make_clip_text_node(node_id: str, *, text: str = "prompt") -> VibeNode:
    return VibeNode(
        id=node_id,
        class_type="CLIPTextEncode",
        inputs={"text": text, "clip": ["99", 0]},
    )


def _make_save_image_node(node_id: str, *, filename_prefix: str = "out/test") -> VibeNode:
    return VibeNode(
        id=node_id,
        class_type="SaveImage",
        inputs={"filename_prefix": filename_prefix},
    )


class _Provider:
    def __init__(self, schemas: dict[str, NodeSchema]) -> None:
        self._schemas = schemas

    def get_schema(self, class_type: str) -> NodeSchema | None:
        return self._schemas.get(class_type)


# ---------------------------------------------------------------------------
# Data model smoke tests
# ---------------------------------------------------------------------------


def test_lowering_result_success_defaults() -> None:
    """Successful LoweringResult has ok=True and sensible defaults."""
    wf = _make_workflow()
    result = LoweringResult(ok=True, workflow=wf)
    assert result.ok is True
    assert result.unsuccessful is False
    assert result.workflow is wf
    assert result.evidence == ()
    assert result.diagnostics == ()
    assert result.lowered_count == 0


def test_lowering_result_failure_has_no_workflow() -> None:
    """Failed LoweringResult must have no workflow (no partial lowering)."""
    result = LoweringResult(ok=False, workflow=None, lowered_count=0)
    assert result.ok is False
    assert result.unsuccessful is True
    assert result.workflow is None


def test_lowering_diagnostic_structure() -> None:
    """LoweringDiagnostic carries code, message, loop_node_id, and optional detail."""
    diag = LoweringDiagnostic(
        code="unsupported_loop_variable",
        message="Loop variable 'foo' not supported.",
        loop_node_id="2",
        loop_uid="loop-2",
        detail={"variable": "foo", "supported": ["seed", "prompt", "text"]},
    )
    assert diag.code == "unsupported_loop_variable"
    assert diag.loop_node_id == "2"
    assert diag.loop_uid == "loop-2"
    assert diag.detail["variable"] == "foo"


def test_loop_lowering_plan_over_values() -> None:
    """LoopLoweringPlan with over_values captures the literal sequence."""
    plan = LoopLoweringPlan(
        loop_node_id="1",
        loop_uid="loop-1",
        variable="seed",
        iterations=3,
        over_values=(101, 202, 303),
        is_over=True,
    )
    assert plan.iterations == 3
    assert plan.over_values == (101, 202, 303)
    assert plan.is_over is True


def test_loop_lowering_plan_count() -> None:
    """LoopLoweringPlan with count path has empty over_values."""
    plan = LoopLoweringPlan(
        loop_node_id="1",
        loop_uid="loop-1",
        variable="seed",
        iterations=5,
    )
    assert plan.iterations == 5
    assert plan.over_values == ()
    assert plan.is_over is False


def test_lowering_evidence_shape() -> None:
    """LoweringEvidence carries all required audit fields."""
    ev = LoweringEvidence(
        loop_uid="loop-1",
        loop_node_id="1",
        original_intent_hash="abc123",
        variable="seed",
        iterations=3,
        lowered_node_count=0,
    )
    assert ev.loop_uid == "loop-1"
    assert ev.variable == "seed"
    assert ev.iterations == 3
    assert ev.iteration_values == ()
    assert ev.lowered_node_count == 0
    assert ev.source_to_lowered_node_map == {}
    assert ev.lowered_fragment_hash is None


# ---------------------------------------------------------------------------
# Loop discovery
# ---------------------------------------------------------------------------


def test_discover_loop_nodes_finds_vibecomfy_loop() -> None:
    """discover_loop_nodes returns vibecomfy.loop nodes with valid payload."""
    wf = _make_workflow()
    wf.nodes["1"] = _make_loop_node("1", var="seed", count=3)
    wf.nodes["2"] = _make_ksample_node("2")

    found = discover_loop_nodes(wf)
    assert len(found) == 1
    node_id, node, payload = found[0]
    assert node_id == "1"
    assert node.class_type == "vibecomfy.loop"
    assert payload["kind"] == "loop"


def test_discover_loop_nodes_ignores_non_loop_intent() -> None:
    """discover_loop_nodes skips vibecomfy.code nodes."""
    wf = _make_workflow()
    wf.nodes["1"] = VibeNode(
        id="1",
        class_type="vibecomfy.code",
        metadata={
            "_ui": {
                "properties": intent_node_properties(
                    kind="code",
                    uid="code-1",
                    intent={"source": "value = 1"},
                    inputs=[("prompt", "STRING")],
                    outputs=[("image", "IMAGE")],
                )
            }
        },
    )

    found = discover_loop_nodes(wf)
    assert len(found) == 0


def test_discover_loop_nodes_ignores_node_without_payload() -> None:
    """discover_loop_nodes skips vibecomfy.loop nodes with missing payload."""
    wf = _make_workflow()
    wf.nodes["1"] = VibeNode(
        id="1",
        class_type="vibecomfy.loop",
        metadata={},
    )

    found = discover_loop_nodes(wf)
    assert len(found) == 0


def test_discover_loop_nodes_empty_workflow() -> None:
    """discover_loop_nodes returns empty for workflow with no loop nodes."""
    wf = _make_workflow()
    wf.nodes["1"] = _make_ksample_node("1")

    found = discover_loop_nodes(wf)
    assert len(found) == 0


# ---------------------------------------------------------------------------
# Loop plan extraction — success cases
# ---------------------------------------------------------------------------


def test_extract_loop_plan_seed_count() -> None:
    """Bounded seed count loop extracts successfully."""
    node = _make_loop_node("1", uid="loop-1", var="seed", count=3)
    payload = node.metadata["_ui"]["properties"]["vibecomfy"]

    plan, diagnostics = extract_loop_plan("1", node, payload)
    assert diagnostics == []
    assert plan is not None
    assert plan.variable == "seed"
    assert plan.iterations == 3
    assert plan.is_over is False


def test_extract_loop_plan_prompt_count() -> None:
    """Bounded prompt count loop extracts successfully."""
    node = _make_loop_node("2", uid="loop-2", var="prompt", count=5)
    payload = node.metadata["_ui"]["properties"]["vibecomfy"]

    plan, diagnostics = extract_loop_plan("2", node, payload)
    assert diagnostics == []
    assert plan is not None
    assert plan.variable == "prompt"
    assert plan.iterations == 5


def test_extract_loop_plan_text_count() -> None:
    """Bounded text count loop extracts successfully."""
    node = _make_loop_node("3", uid="loop-3", var="text", count=2)
    payload = node.metadata["_ui"]["properties"]["vibecomfy"]

    plan, diagnostics = extract_loop_plan("3", node, payload)
    assert diagnostics == []
    assert plan is not None
    assert plan.variable == "text"
    assert plan.iterations == 2


def test_extract_loop_plan_iterations_alias() -> None:
    """Loop using `intent.iterations` instead of `intent.count` works."""
    node = VibeNode(
        id="4",
        class_type="vibecomfy.loop",
        uid="loop-4",
        metadata={
            "_ui": {
                "properties": intent_node_properties(
                    kind="loop",
                    uid="loop-4",
                    intent={"var": "seed", "iterations": 7},
                    inputs=[("image", "IMAGE")],
                    outputs=[("image", "IMAGE")],
                )
            }
        },
    )
    payload = node.metadata["_ui"]["properties"]["vibecomfy"]

    plan, diagnostics = extract_loop_plan("4", node, payload)
    assert diagnostics == []
    assert plan is not None
    assert plan.iterations == 7


def test_extract_loop_plan_over_literal_values() -> None:
    """Loop with intent.over of literal values extracts successfully."""
    node = _make_loop_node("5", uid="loop-5", var="seed", over=[42, 99, 777])
    payload = node.metadata["_ui"]["properties"]["vibecomfy"]

    plan, diagnostics = extract_loop_plan("5", node, payload)
    assert diagnostics == []
    assert plan is not None
    assert plan.variable == "seed"
    assert plan.iterations == 3
    assert plan.over_values == (42, 99, 777)
    assert plan.is_over is True


def test_extract_loop_plan_over_prompt_values() -> None:
    """Loop with intent.over of string values extracts successfully."""
    node = _make_loop_node("6", uid="loop-6", var="prompt", over=["a cat", "a dog", "a bird"])
    payload = node.metadata["_ui"]["properties"]["vibecomfy"]

    plan, diagnostics = extract_loop_plan("6", node, payload)
    assert diagnostics == []
    assert plan is not None
    assert plan.variable == "prompt"
    assert plan.over_values == ("a cat", "a dog", "a bird")


# ---------------------------------------------------------------------------
# Loop plan extraction — rejection cases
# ---------------------------------------------------------------------------


def test_extract_loop_plan_rejects_unsupported_variable() -> None:
    """Loop with unsupported variable (e.g. 'steps') returns None with diagnostics."""
    node = _make_loop_node("1", var="steps", count=3)
    payload = node.metadata["_ui"]["properties"]["vibecomfy"]

    plan, diagnostics = extract_loop_plan("1", node, payload)
    assert plan is None
    assert len(diagnostics) == 1
    assert diagnostics[0].code == "unsupported_loop_variable"
    assert "steps" in diagnostics[0].message


def test_extract_loop_plan_rejects_missing_var() -> None:
    """Loop without var field returns None with diagnostics."""
    node = VibeNode(
        id="1",
        class_type="vibecomfy.loop",
        uid="loop-1",
        metadata={
            "_ui": {
                "properties": intent_node_properties(
                    kind="loop",
                    uid="loop-1",
                    intent={"count": 3},
                    inputs=[("image", "IMAGE")],
                    outputs=[("image", "IMAGE")],
                )
            }
        },
    )
    payload = node.metadata["_ui"]["properties"]["vibecomfy"]

    plan, diagnostics = extract_loop_plan("1", node, payload)
    assert plan is None
    assert len(diagnostics) == 1
    assert diagnostics[0].code == "missing_loop_var"


def test_extract_loop_plan_rejects_missing_bound() -> None:
    """Loop with no count/iterations/over returns None with diagnostics."""
    node = VibeNode(
        id="1",
        class_type="vibecomfy.loop",
        uid="loop-1",
        metadata={
            "_ui": {
                "properties": intent_node_properties(
                    kind="loop",
                    uid="loop-1",
                    intent={"var": "seed"},
                    inputs=[("image", "IMAGE")],
                    outputs=[("image", "IMAGE")],
                )
            }
        },
    )
    payload = node.metadata["_ui"]["properties"]["vibecomfy"]

    plan, diagnostics = extract_loop_plan("1", node, payload)
    assert plan is None
    assert len(diagnostics) == 1
    assert diagnostics[0].code == "missing_loop_bound"


def test_extract_loop_plan_rejects_zero_count() -> None:
    """Loop with count=0 returns None with diagnostics."""
    node = _make_loop_node("1", var="seed", count=0)
    payload = node.metadata["_ui"]["properties"]["vibecomfy"]

    plan, diagnostics = extract_loop_plan("1", node, payload)
    assert plan is None
    assert len(diagnostics) == 1
    assert diagnostics[0].code == "loop_bound_out_of_range"


def test_extract_loop_plan_rejects_negative_count() -> None:
    """Loop with negative count returns None with diagnostics."""
    node = _make_loop_node("1", var="seed", count=-5)
    payload = node.metadata["_ui"]["properties"]["vibecomfy"]

    plan, diagnostics = extract_loop_plan("1", node, payload)
    assert plan is None
    assert len(diagnostics) == 1
    assert diagnostics[0].code == "loop_bound_out_of_range"


def test_extract_loop_plan_rejects_exceeds_max_iterations() -> None:
    """Loop with count > INTENT_LOOP_MAX_ITERATIONS returns None."""
    node = _make_loop_node("1", var="seed", count=INTENT_LOOP_MAX_ITERATIONS + 1)
    payload = node.metadata["_ui"]["properties"]["vibecomfy"]

    plan, diagnostics = extract_loop_plan("1", node, payload)
    assert plan is None
    assert len(diagnostics) == 1
    assert diagnostics[0].code == "loop_bound_out_of_range"


def test_extract_loop_plan_rejects_over_exceeds_max() -> None:
    """Loop with over list exceeding max iterations returns None."""
    node = _make_loop_node("1", var="seed", over=list(range(INTENT_LOOP_MAX_ITERATIONS + 1)))
    payload = node.metadata["_ui"]["properties"]["vibecomfy"]

    plan, diagnostics = extract_loop_plan("1", node, payload)
    assert plan is None
    assert any(d.code == "loop_bound_out_of_range" for d in diagnostics)


def test_extract_loop_plan_rejects_empty_over() -> None:
    """Loop with empty over list returns None."""
    node = _make_loop_node("1", var="seed", over=[])
    payload = node.metadata["_ui"]["properties"]["vibecomfy"]

    plan, diagnostics = extract_loop_plan("1", node, payload)
    assert plan is None
    assert any(d.code == "empty_over_sequence" for d in diagnostics)


def test_extract_loop_plan_rejects_non_literal_over_values() -> None:
    """Loop with non-literal over values (e.g. dict) returns None."""
    node = VibeNode(
        id="1",
        class_type="vibecomfy.loop",
        uid="loop-1",
        metadata={
            "_ui": {
                "properties": intent_node_properties(
                    kind="loop",
                    uid="loop-1",
                    intent={"var": "seed", "over": [{"dynamic": True}]},
                    inputs=[("image", "IMAGE")],
                    outputs=[("image", "IMAGE")],
                )
            }
        },
    )
    payload = node.metadata["_ui"]["properties"]["vibecomfy"]

    plan, diagnostics = extract_loop_plan("1", node, payload)
    assert plan is None
    assert any(d.code == "unsupported_over_values" for d in diagnostics)


def test_extract_loop_plan_rejects_missing_intent() -> None:
    """Loop without intent mapping returns None."""
    node = VibeNode(
        id="1",
        class_type="vibecomfy.loop",
        uid="loop-1",
        metadata={
            "_ui": {
                "properties": {
                    "vibecomfy_uid": "loop-1",
                    "vibecomfy": {
                        "kind": "loop",
                        "io": {"inputs": [["image", "IMAGE"]], "outputs": [["image", "IMAGE"]]},
                    },
                }
            }
        },
    )
    payload = node.metadata["_ui"]["properties"]["vibecomfy"]

    plan, diagnostics = extract_loop_plan("1", node, payload)
    assert plan is None
    assert any(d.code == "missing_loop_intent" for d in diagnostics)


# ---------------------------------------------------------------------------
# Atomic lowering: all-or-nothing
# ---------------------------------------------------------------------------


def test_discover_body_boundary_for_clip_ksampler_saveimage_graph() -> None:
    """Loop body discovery keeps CLIP/KSampler in-body and duplicates SaveImage."""
    wf = _make_workflow()
    wf.nodes["10"] = _make_loop_node("10", uid="loop-10", var="prompt", count=3)
    wf.nodes["20"] = _make_clip_text_node("20")
    wf.nodes["30"] = VibeNode("30", "CheckpointLoaderSimple")
    wf.nodes["40"] = _make_clip_text_node("40", text="negative")
    wf.nodes["50"] = VibeNode("50", "EmptyLatentImage")
    wf.nodes["60"] = _make_ksample_node("60")
    wf.nodes["70"] = _make_save_image_node("70")

    wf.connect("10.0", "20.text")
    wf.connect("30.0", "20.clip")
    wf.connect("30.0", "60.model")
    wf.connect("20.0", "60.positive")
    wf.connect("40.0", "60.negative")
    wf.connect("50.0", "60.latent_image")
    wf.connect("60.0", "70.images")

    plan, diagnostics = extract_loop_plan(
        "10",
        wf.nodes["10"],
        wf.nodes["10"].metadata["_ui"]["properties"]["vibecomfy"],
    )
    assert diagnostics == []
    assert plan is not None

    boundary, diagnostics = discover_body_boundary(wf, plan)
    assert diagnostics == []
    assert boundary == LoopBodyBoundary(
        loop_node_id="10",
        loop_uid="loop-10",
        body_node_ids=("20", "60"),
        shared_inputs=(
            LoweringBoundaryInput("30", "0", "20", "clip"),
            LoweringBoundaryInput("30", "0", "60", "model"),
            LoweringBoundaryInput("40", "0", "60", "negative"),
            LoweringBoundaryInput("50", "0", "60", "latent_image"),
        ),
        boundary_outputs=(
            LoweringBoundaryOutput(
                source_node_id="60",
                source_output="0",
                consumer_node_id="70",
                consumer_input="images",
                consumer_class_type="SaveImage",
                duplication_kind="duplicate_terminal_sink",
                shared_inputs=(),
            ),
        ),
    )


def test_discover_body_boundary_records_shared_sink_inputs() -> None:
    """Duplicable terminal sinks retain their shared non-loop inputs deterministically."""
    wf = _make_workflow()
    wf.nodes["1"] = _make_loop_node("1", uid="loop-1", var="seed", count=2)
    wf.nodes["2"] = VibeNode("2", "KSampler")
    wf.nodes["3"] = _make_save_image_node("3")
    wf.nodes["4"] = VibeNode("4", "MetadataProvider")

    wf.connect("1.0", "2.seed")
    wf.connect("2.0", "3.images")
    wf.connect("4.0", "3.caption")

    plan, diagnostics = extract_loop_plan(
        "1",
        wf.nodes["1"],
        wf.nodes["1"].metadata["_ui"]["properties"]["vibecomfy"],
    )
    assert diagnostics == []
    assert plan is not None

    boundary, diagnostics = discover_body_boundary(wf, plan)
    assert diagnostics == []
    assert boundary is not None
    assert boundary.boundary_outputs == (
        LoweringBoundaryOutput(
            source_node_id="2",
            source_output="0",
            consumer_node_id="3",
            consumer_input="images",
            consumer_class_type="SaveImage",
            duplication_kind="duplicate_terminal_sink",
            shared_inputs=(LoweringBoundaryInput("4", "0", "3", "caption"),),
        ),
    )


def test_discover_body_boundary_rejects_terminal_non_sink_fan_in_deterministically() -> None:
    """Terminal non-output consumers are rejected instead of being implicitly duplicated."""
    wf = _make_workflow()
    wf.nodes["1"] = _make_loop_node("1", uid="loop-1", var="text", count=2)
    wf.nodes["2"] = _make_clip_text_node("2")
    wf.nodes["3"] = VibeNode("3", "ImageScale")

    wf.connect("1.0", "2.text")
    wf.connect("2.0", "3.image")

    plan, diagnostics = extract_loop_plan(
        "1",
        wf.nodes["1"],
        wf.nodes["1"].metadata["_ui"]["properties"]["vibecomfy"],
    )
    assert diagnostics == []
    assert plan is not None

    boundary, diagnostics = discover_body_boundary(wf, plan)
    assert boundary is None
    assert [diag.code for diag in diagnostics] == ["unsupported_scalar_fan_in"]
    assert diagnostics[0].detail == {
        "consumer_node_id": "3",
        "consumer_class_type": "ImageScale",
    }


def test_lower_workflow_no_loops_returns_success_noop() -> None:
    """lower_workflow on a loop-free workflow returns ok=True with 0 count."""
    wf = _make_workflow()
    wf.nodes["1"] = _make_ksample_node("1")

    result = lower_workflow(wf)
    assert result.ok is True
    assert result.lowered_count == 0
    assert result.evidence == ()
    assert result.diagnostics == ()


def test_lower_workflow_single_seed_loop_plans_successfully() -> None:
    """A single valid seed loop produces a successful plan."""
    wf = _make_workflow()
    wf.nodes["1"] = _make_loop_node("1", var="seed", count=3)
    wf.nodes["2"] = _make_ksample_node("2")

    result = lower_workflow(wf)
    assert result.ok is True
    assert result.lowered_count == 1
    assert len(result.evidence) == 1
    assert result.evidence[0].variable == "seed"
    assert result.evidence[0].iterations == 3


def test_lower_workflow_single_iteration_clones_and_removes_loop_nodes() -> None:
    """One-iteration lowering operates on a clone and emits only native nodes."""
    wf = _make_workflow()
    wf.nodes["10"] = _make_loop_node("10", uid="loop-10", var="prompt", count=1)
    wf.nodes["20"] = _make_clip_text_node("20", text="hello world")
    wf.nodes["30"] = VibeNode("30", "CheckpointLoaderSimple")
    wf.nodes["40"] = _make_clip_text_node("40", text="negative")
    wf.nodes["50"] = VibeNode("50", "EmptyLatentImage")
    wf.nodes["60"] = _make_ksample_node("60")
    wf.nodes["70"] = _make_save_image_node("70")

    wf.connect("10.0", "20.text")
    wf.connect("30.0", "20.clip")
    wf.connect("30.0", "60.model")
    wf.connect("20.0", "60.positive")
    wf.connect("40.0", "60.negative")
    wf.connect("50.0", "60.latent_image")
    wf.connect("60.0", "70.images")
    original_api = wf.compile("api")

    first = lower_workflow(wf)
    second = lower_workflow(wf)

    assert first.ok is True
    assert first.workflow is not None
    assert first.workflow is not wf
    assert second.ok is True
    assert second.workflow is not None

    lowered_api = first.workflow.compile("api")
    assert "10" not in first.workflow.nodes
    assert all(node["class_type"] != "vibecomfy.loop" for node in lowered_api.values())
    assert set(lowered_api) == {"1", "2", "3", "30", "40", "50"}
    assert lowered_api["1"]["class_type"] == "CLIPTextEncode"
    assert lowered_api["2"]["class_type"] == "KSampler"
    assert lowered_api["3"]["class_type"] == "SaveImage"

    cloned_nodes = [
        (node.id, node.uid, node.metadata["vibecomfy.lowering"]["clone_role"])
        for node in first.workflow.nodes.values()
        if "vibecomfy.lowering" in node.metadata
    ]
    cloned_nodes_second = [
        (node.id, node.uid, node.metadata["vibecomfy.lowering"]["clone_role"])
        for node in second.workflow.nodes.values()
        if "vibecomfy.lowering" in node.metadata
    ]
    assert sorted(cloned_nodes) == sorted(cloned_nodes_second)
    assert sorted(cloned_nodes) == [
        ("1", "loop-10:iter0:20", "body"),
        ("2", "loop-10:iter0:60", "body"),
        ("3", "loop-10:iter0:70", "terminal_sink"),
    ]
    assert first.evidence[0].lowered_node_count == 3
    assert first.evidence[0].iteration_values == ("hello world",)
    assert first.evidence[0].source_to_lowered_node_map == {
        "20": ("loop-10:iter0:20",),
        "60": ("loop-10:iter0:60",),
        "70": ("loop-10:iter0:70",),
    }

    assert wf.nodes["10"].class_type == "vibecomfy.loop"
    assert wf.compile("api") == original_api


def test_lower_workflow_emits_api_and_ui_graphs_without_loop_nodes() -> None:
    wf = _make_workflow()
    wf.nodes["10"] = _make_loop_node("10", uid="loop-10", var="prompt", count=1)
    wf.nodes["20"] = _make_clip_text_node("20", text="hello world")
    wf.nodes["30"] = VibeNode("30", "CheckpointLoaderSimple")
    wf.nodes["40"] = _make_clip_text_node("40", text="negative")
    wf.nodes["50"] = VibeNode("50", "EmptyLatentImage")
    wf.nodes["60"] = _make_ksample_node("60")
    wf.nodes["70"] = _make_save_image_node("70")

    wf.connect("10.0", "20.text")
    wf.connect("30.0", "20.clip")
    wf.connect("30.0", "60.model")
    wf.connect("20.0", "60.positive")
    wf.connect("40.0", "60.negative")
    wf.connect("50.0", "60.latent_image")
    wf.connect("60.0", "70.images")

    result = lower_workflow(wf)

    assert result.ok is True
    assert result.workflow is not None
    assert all(node["class_type"] != "vibecomfy.loop" for node in result.workflow.compile("api").values())
    with warnings.catch_warnings():
        warnings.simplefilter("ignore", UserWarning)
        emitted = emit_ui_json(result.workflow)
    assert all(node["type"] != "vibecomfy.loop" for node in emitted["nodes"])


def test_lower_workflow_atomic_failure_on_unsupported_variable() -> None:
    """One unsupported loop fails the entire lowering result."""
    wf = _make_workflow()
    wf.nodes["1"] = _make_loop_node("1", var="seed", count=3)
    wf.nodes["2"] = _make_loop_node("2", var="steps", count=3)  # Unsupported

    result = lower_workflow(wf)
    assert result.ok is False
    assert result.workflow is None
    assert result.lowered_count == 0
    assert result.evidence == ()
    assert any(d.code == "unsupported_loop_variable" for d in result.diagnostics)


def test_lower_workflow_atomic_failure_on_missing_bound() -> None:
    """One loop with missing bound fails the entire lowering."""
    wf = _make_workflow()
    wf.nodes["1"] = _make_loop_node("1", var="seed", count=3)
    # Node 2 has no count/iterations/over
    wf.nodes["2"] = VibeNode(
        id="2",
        class_type="vibecomfy.loop",
        uid="loop-2",
        metadata={
            "_ui": {
                "properties": intent_node_properties(
                    kind="loop",
                    uid="loop-2",
                    intent={"var": "prompt"},
                    inputs=[("image", "IMAGE")],
                    outputs=[("image", "IMAGE")],
                )
            }
        },
    )

    result = lower_workflow(wf)
    assert result.ok is False
    assert result.workflow is None


def test_lower_workflow_multiple_valid_loops_succeed() -> None:
    """Multiple valid loops all produce plans."""
    wf = _make_workflow()
    wf.nodes["1"] = _make_loop_node("1", var="seed", count=3)
    wf.nodes["2"] = _make_loop_node("2", var="prompt", count=2)
    wf.nodes["3"] = _make_loop_node("3", var="text", count=4)

    result = lower_workflow(wf)
    assert result.ok is True
    assert result.lowered_count == 3
    assert len(result.evidence) == 3


def test_lower_workflow_multi_iteration_seed_loop_concretizes_fields_deterministically() -> None:
    """Count-based seed loops expand to concrete incremented seed values."""
    wf = _make_workflow()
    wf.nodes["10"] = _make_loop_node("10", uid="loop-10", var="seed", count=3)
    wf.nodes["20"] = _make_ksample_node("20")
    wf.nodes["30"] = _make_save_image_node("30")

    wf.connect("10.0", "20.seed")
    wf.connect("20.0", "30.images")

    first = lower_workflow(wf)
    second = lower_workflow(wf)

    assert first.ok is True
    assert first.workflow is not None
    assert second.ok is True
    assert second.workflow is not None

    first_api = first.workflow.compile("api")
    second_api = second.workflow.compile("api")
    assert first_api == second_api
    assert set(first_api) == {"1", "2", "3", "4", "5", "6"}
    assert [first_api[node_id]["inputs"]["seed"] for node_id in ("1", "3", "5")] == [42, 43, 44]
    assert [first_api[node_id]["class_type"] for node_id in ("1", "3", "5")] == [
        "KSampler",
        "KSampler",
        "KSampler",
    ]
    assert [first_api[node_id]["class_type"] for node_id in ("2", "4", "6")] == [
        "SaveImage",
        "SaveImage",
        "SaveImage",
    ]
    assert first.evidence == second.evidence
    assert first.evidence[0].iteration_values == (42, 43, 44)
    assert first.evidence[0].lowered_node_count == 6
    assert first.evidence[0].source_to_lowered_node_map == {
        "20": ("loop-10:iter0:20", "loop-10:iter1:20", "loop-10:iter2:20"),
        "30": ("loop-10:iter0:30", "loop-10:iter1:30", "loop-10:iter2:30"),
    }
    assert list(first_api) == ["1", "2", "3", "4", "5", "6"]
    assert list(second_api) == ["1", "2", "3", "4", "5", "6"]


def test_lower_workflow_multi_iteration_prompt_over_concretizes_text_fields() -> None:
    """Prompt/text loops lower to concrete string values from intent.over."""
    wf = _make_workflow()
    wf.nodes["10"] = _make_loop_node(
        "10",
        uid="loop-10",
        var="prompt",
        over=["a glass teapot", "a brass kettle", "a stone vase"],
    )
    wf.nodes["20"] = _make_clip_text_node("20", text="placeholder")
    wf.nodes["30"] = VibeNode("30", "CheckpointLoaderSimple")
    wf.nodes["40"] = _make_ksample_node("40")
    wf.nodes["50"] = _make_save_image_node("50")
    wf.nodes["60"] = _make_clip_text_node("60", text="negative")
    wf.nodes["70"] = VibeNode("70", "EmptyLatentImage")

    wf.connect("10.0", "20.text")
    wf.connect("30.0", "20.clip")
    wf.connect("30.0", "40.model")
    wf.connect("20.0", "40.positive")
    wf.connect("60.0", "40.negative")
    wf.connect("70.0", "40.latent_image")
    wf.connect("40.0", "50.images")

    first = lower_workflow(wf)
    second = lower_workflow(wf)

    assert first.ok is True
    assert first.workflow is not None
    assert second.ok is True
    assert second.workflow is not None

    first_api = first.workflow.compile("api")
    second_api = second.workflow.compile("api")
    assert first_api == second_api
    assert set(first_api) == {"1", "2", "3", "4", "5", "6", "7", "8", "9", "30", "60", "70"}
    assert [first_api[node_id]["inputs"]["text"] for node_id in ("1", "4", "7")] == [
        "a glass teapot",
        "a brass kettle",
        "a stone vase",
    ]
    assert [first_api[node_id]["inputs"]["negative"] for node_id in ("2", "5", "8")] == [
        ["60", 0],
        ["60", 0],
        ["60", 0],
    ]
    assert first.evidence == second.evidence
    assert first.evidence[0].iteration_values == (
        "a glass teapot",
        "a brass kettle",
        "a stone vase",
    )
    assert first.evidence[0].source_to_lowered_node_map == {
        "20": ("loop-10:iter0:20", "loop-10:iter1:20", "loop-10:iter2:20"),
        "40": ("loop-10:iter0:40", "loop-10:iter1:40", "loop-10:iter2:40"),
        "50": ("loop-10:iter0:50", "loop-10:iter1:50", "loop-10:iter2:50"),
    }
    assert first.evidence[0].lowered_fragment_hash == second.evidence[0].lowered_fragment_hash
    assert first.evidence[0].validation_result == {
        "ok": True,
        "issue_count": 0,
        "error_count": 0,
        "warning_count": 0,
        "issues": [],
    }


def test_lower_workflow_fails_when_lowered_copy_breaks_schema_link_shapes() -> None:
    wf = _make_workflow()
    wf.nodes["10"] = _make_loop_node(
        "10",
        uid="loop-10",
        var="prompt",
        over=["first", "second"],
    )
    wf.nodes["20"] = _make_clip_text_node("20", text="placeholder")
    wf.nodes["30"] = _make_save_image_node("30")
    wf.nodes["20"].inputs["clip"] = {"node_id": "99", "output": 0}

    wf.connect("10.0", "20.text")
    wf.connect("20.0", "30.images")

    provider = _Provider(
        {
            "CLIPTextEncode": NodeSchema(
                class_type="CLIPTextEncode",
                pack=None,
                inputs={
                    "text": InputSpec(type="STRING", required=True, default=None),
                    "clip": InputSpec(type="CLIP", required=False, default=None),
                },
                outputs=[OutputSpec("CONDITIONING", "conditioning")],
                source_provider="test",
                confidence=1.0,
            ),
            "SaveImage": NodeSchema(
                class_type="SaveImage",
                pack=None,
                inputs={
                    "images": InputSpec(type="IMAGE", required=True, default=None),
                    "filename_prefix": InputSpec(type="STRING", required=False, default=None),
                },
                outputs=[],
                source_provider="test",
                confidence=1.0,
            ),
        }
    )

    result = lower_workflow(wf, schema_provider=provider)

    assert result.ok is False
    assert result.workflow is None
    assert result.evidence == ()
    assert result.lowered_count == 0
    assert any(diag.code == "lowered_copy_validation_failed" for diag in result.diagnostics)
    validation_issue = next(
        diag.detail["validation_issue"]
        for diag in result.diagnostics
        if diag.code == "lowered_copy_validation_failed"
    )
    assert validation_issue["code"] == "invalid_link_shape"


def test_lower_workflow_fails_atomically_on_inconsistent_seed_source_values() -> None:
    wf = _make_workflow()
    wf.nodes["10"] = _make_loop_node("10", uid="loop-10", var="seed", count=3)
    wf.nodes["20"] = _make_ksample_node("20")
    wf.nodes["30"] = _make_ksample_node("30")
    wf.nodes["20"].inputs["seed"] = 42
    wf.nodes["30"].inputs["seed"] = 99

    wf.connect("10.0", "20.seed")
    wf.connect("10.0", "30.seed")

    result = lower_workflow(wf)

    assert result.ok is False
    assert result.workflow is None
    assert result.evidence == ()
    assert result.lowered_count == 0
    assert [diag.code for diag in result.diagnostics] == ["inconsistent_seed_source_values"]
    assert result.diagnostics[0].detail == {"values": [42, 99]}


def test_lower_workflow_fails_atomically_on_inconsistent_prompt_source_values() -> None:
    wf = _make_workflow()
    wf.nodes["10"] = _make_loop_node("10", uid="loop-10", var="prompt", count=2)
    wf.nodes["20"] = _make_clip_text_node("20", text="first prompt")
    wf.nodes["30"] = _make_clip_text_node("30", text="second prompt")

    wf.connect("10.0", "20.text")
    wf.connect("10.0", "30.text")

    result = lower_workflow(wf)

    assert result.ok is False
    assert result.workflow is None
    assert result.evidence == ()
    assert result.lowered_count == 0
    assert [diag.code for diag in result.diagnostics] == ["inconsistent_text_source_values"]
    assert result.diagnostics[0].detail == {"values": ["first prompt", "second prompt"]}


def test_lower_workflow_supported_variables_all_accepted() -> None:
    """Every variable in SUPPORTED_LOOP_VARIABLES produces a valid plan."""
    for var in SUPPORTED_LOOP_VARIABLES:
        node = _make_loop_node("1", var=var, count=2)
        payload = node.metadata["_ui"]["properties"]["vibecomfy"]
        plan, diagnostics = extract_loop_plan("1", node, payload)
        assert plan is not None, f"Variable {var!r} should be supported"
        assert diagnostics == []


def test_lower_workflow_original_workflow_untouched() -> None:
    """lower_workflow does not mutate the original workflow."""
    wf = _make_workflow()
    wf.nodes["1"] = _make_loop_node("1", var="seed", count=3)
    original_node_count = len(wf.nodes)

    result = lower_workflow(wf)
    assert result.ok is True
    # Original workflow should not be mutated
    assert len(wf.nodes) == original_node_count
    assert "1" in wf.nodes
    assert wf.nodes["1"].class_type == "vibecomfy.loop"


def test_lower_workflow_non_loop_nodes_ignored() -> None:
    """Non-loop and non-intent nodes don't affect lowering."""
    wf = _make_workflow()
    wf.nodes["1"] = _make_ksample_node("1")
    wf.nodes["2"] = VibeNode(id="2", class_type="CheckpointLoaderSimple")
    wf.nodes["3"] = VibeNode(id="3", class_type="CLIPTextEncode")

    result = lower_workflow(wf)
    assert result.ok is True
    assert result.lowered_count == 0


def test_lower_workflow_over_takes_precedence() -> None:
    """When both count and over are present, over wins."""
    node = VibeNode(
        id="1",
        class_type="vibecomfy.loop",
        uid="loop-1",
        metadata={
            "_ui": {
                "properties": intent_node_properties(
                    kind="loop",
                    uid="loop-1",
                    intent={"var": "seed", "count": 100, "over": [1, 2, 3]},
                    inputs=[("image", "IMAGE")],
                    outputs=[("image", "IMAGE")],
                )
            }
        },
    )
    payload = node.metadata["_ui"]["properties"]["vibecomfy"]
    plan, diagnostics = extract_loop_plan("1", node, payload)
    assert plan is not None
    assert plan.iterations == 3
    assert plan.over_values == (1, 2, 3)
    assert plan.is_over is True


# ---------------------------------------------------------------------------
# T8 — Deterministic clone layout policy
# ---------------------------------------------------------------------------


def _node_with_ui(node_id: str, class_type: str, *, pos: tuple[float, float], size: tuple[float, float] | None = None, inputs: dict | None = None) -> VibeNode:
    """Create a node with explicit _ui pos/size metadata."""
    md: dict[str, Any] = {"_ui": {"pos": list(pos)}}
    if size is not None:
        md["_ui"]["size"] = list(size)
    node = VibeNode(id=node_id, class_type=class_type, metadata=md)
    if inputs is not None:
        node.inputs = dict(inputs)
    return node


def test_clone_nodes_have_horizontal_stride_positions() -> None:
    """Each iteration's clones are offset by HORIZONTAL_STRIDE pixels horizontally."""
    wf = _make_workflow()
    wf.nodes["10"] = _make_loop_node("10", uid="loop-10", var="seed", count=3)
    wf.nodes["20"] = _node_with_ui("20", "KSampler", pos=(100.0, 200.0), size=(315.0, 262.0), inputs={"seed": 42, "steps": 20, "cfg": 7.0, "sampler_name": "euler", "scheduler": "normal", "denoise": 1.0})
    wf.nodes["30"] = _node_with_ui("30", "SaveImage", pos=(100.0, 500.0), size=(315.0, 270.0), inputs={"filename_prefix": "out/test"})

    wf.connect("10.0", "20.seed")
    wf.connect("20.0", "30.images")

    result = lower_workflow(wf)
    assert result.ok is True
    assert result.workflow is not None

    # Check that clones have exactly the expected positions
    # Iter 0: same x as source (100 + 300*0 = 100), same y
    # Iter 1: x = 100 + 300*1 = 400
    # Iter 2: x = 100 + 300*2 = 700
    for node_id, node in result.workflow.nodes.items():
        ui = node.metadata.get("_ui", {})
        pos = ui.get("pos")
        lowering = node.metadata.get("vibecomfy.lowering", {})
        source_id = lowering.get("source_node_id")
        iter_idx = lowering.get("iteration_index")

        if source_id == "20":
            # KSampler clones
            expected_x = int(100 + HORIZONTAL_STRIDE * iter_idx)
            assert pos == [expected_x, 200], f"KSampler clone at iter {iter_idx}: expected {[expected_x, 200]}, got {pos}"
        elif source_id == "30":
            # SaveImage clones
            expected_x = int(100 + HORIZONTAL_STRIDE * iter_idx)
            assert pos == [expected_x, 500], f"SaveImage clone at iter {iter_idx}: expected {[expected_x, 500]}, got {pos}"


def test_clone_positions_are_snapped_to_whole_integers() -> None:
    """snap_pos() ensures clone positions are always whole integers."""
    wf = _make_workflow()
    wf.nodes["10"] = _make_loop_node("10", uid="loop-10", var="seed", count=2)
    wf.nodes["20"] = _node_with_ui("20", "KSampler", pos=(10.5, 20.3), size=(315.0, 262.0), inputs={"seed": 42, "steps": 20, "cfg": 7.0, "sampler_name": "euler", "scheduler": "normal", "denoise": 1.0})
    wf.nodes["30"] = _node_with_ui("30", "SaveImage", pos=(10.5, 500.7), size=(315.0, 270.0), inputs={"filename_prefix": "out/test"})

    wf.connect("10.0", "20.seed")
    wf.connect("20.0", "30.images")

    result = lower_workflow(wf)
    assert result.ok is True
    assert result.workflow is not None

    for node_id, node in result.workflow.nodes.items():
        ui = node.metadata.get("_ui", {})
        pos = ui.get("pos")
        if pos is None:
            continue
        assert isinstance(pos[0], int), f"Node {node_id}: pos[0] should be int, got {pos[0]} ({type(pos[0]).__name__})"
        assert isinstance(pos[1], int), f"Node {node_id}: pos[1] should be int, got {pos[1]} ({type(pos[1]).__name__})"
        assert pos[0] == round(pos[0]), f"Node {node_id}: pos[0] should be rounded integer"
        assert pos[1] == round(pos[1]), f"Node {node_id}: pos[1] should be rounded integer"


def test_clone_positions_deterministic_across_repeated_lowerings() -> None:
    """Clone positions are bit-identical across repeated lowering calls."""
    wf = _make_workflow()
    wf.nodes["10"] = _make_loop_node("10", uid="loop-10", var="seed", count=3)
    wf.nodes["20"] = _node_with_ui("20", "KSampler", pos=(50.0, 100.0), size=(315.0, 262.0), inputs={"seed": 42, "steps": 20, "cfg": 7.0, "sampler_name": "euler", "scheduler": "normal", "denoise": 1.0})
    wf.nodes["30"] = _node_with_ui("30", "SaveImage", pos=(50.0, 400.0), size=(315.0, 270.0), inputs={"filename_prefix": "out/test"})

    wf.connect("10.0", "20.seed")
    wf.connect("20.0", "30.images")

    first = lower_workflow(wf)
    second = lower_workflow(wf)

    assert first.ok is True
    assert second.ok is True
    assert first.workflow is not None
    assert second.workflow is not None

    first_positions: dict[str, list[int]] = {}
    second_positions: dict[str, list[int]] = {}

    for node_id, node in first.workflow.nodes.items():
        ui = node.metadata.get("_ui", {})
        pos = ui.get("pos")
        if pos is not None:
            first_positions[node.uid] = list(pos)

    for node_id, node in second.workflow.nodes.items():
        ui = node.metadata.get("_ui", {})
        pos = ui.get("pos")
        if pos is not None:
            second_positions[node.uid] = list(pos)

    assert first_positions == second_positions, (
        f"Positions differ across lowering calls:\n"
        f"first:  {first_positions}\n"
        f"second: {second_positions}"
    )


def test_clone_layout_policy_descriptor_in_evidence() -> None:
    """LoweringEvidence records the layout_policy descriptor."""
    wf = _make_workflow()
    wf.nodes["10"] = _make_loop_node("10", uid="loop-10", var="seed", count=2)
    wf.nodes["20"] = _node_with_ui("20", "KSampler", pos=(0.0, 0.0), size=(315.0, 262.0), inputs={"seed": 42, "steps": 20, "cfg": 7.0, "sampler_name": "euler", "scheduler": "normal", "denoise": 1.0})
    wf.nodes["30"] = _node_with_ui("30", "SaveImage", pos=(0.0, 300.0), size=(315.0, 270.0), inputs={"filename_prefix": "out/test"})

    wf.connect("10.0", "20.seed")
    wf.connect("20.0", "30.images")

    result = lower_workflow(wf)
    assert result.ok is True
    assert len(result.evidence) == 1
    assert result.evidence[0].layout_policy == LAYOUT_POLICY_DESCRIPTOR
    assert "horizontal_stride_clone" in result.evidence[0].layout_policy
    assert f"offset={HORIZONTAL_STRIDE}" in result.evidence[0].layout_policy


def test_clone_positions_default_to_zero_when_no_source_ui() -> None:
    """Clones of nodes without _ui metadata default to (0, 0) base position."""
    wf = _make_workflow()
    wf.nodes["10"] = _make_loop_node("10", uid="loop-10", var="seed", count=2)
    # Nodes without _ui metadata
    wf.nodes["20"] = VibeNode("20", "KSampler", inputs={"seed": 42, "steps": 20, "cfg": 7.0, "sampler_name": "euler", "scheduler": "normal", "denoise": 1.0})
    wf.nodes["30"] = _make_save_image_node("30")

    wf.connect("10.0", "20.seed")
    wf.connect("20.0", "30.images")

    result = lower_workflow(wf)
    assert result.ok is True
    assert result.workflow is not None

    for node_id, node in result.workflow.nodes.items():
        ui = node.metadata.get("_ui", {})
        pos = ui.get("pos")
        if pos is None:
            continue
        lowering = node.metadata.get("vibecomfy.lowering", {})
        iter_idx = lowering.get("iteration_index", 0)
        # Default base position is (0, 0), so x = HORIZONTAL_STRIDE * iter_idx
        expected_x = int(0 + HORIZONTAL_STRIDE * iter_idx)
        assert pos[0] == expected_x, f"Node {node_id} at iter {iter_idx}: expected x={expected_x}, got {pos[0]}"
        assert pos[1] == 0  # Default y = 0


def test_clone_positions_honor_source_y_offset() -> None:
    """Clone y positions preserve the source node's y coordinate."""
    wf = _make_workflow()
    wf.nodes["10"] = _make_loop_node("10", uid="loop-10", var="seed", count=2)
    wf.nodes["20"] = _node_with_ui("20", "KSampler", pos=(50.0, 350.0), size=(315.0, 262.0), inputs={"seed": 42, "steps": 20, "cfg": 7.0, "sampler_name": "euler", "scheduler": "normal", "denoise": 1.0})
    wf.nodes["30"] = _node_with_ui("30", "SaveImage", pos=(50.0, 700.0), size=(315.0, 270.0), inputs={"filename_prefix": "out/test"})

    wf.connect("10.0", "20.seed")
    wf.connect("20.0", "30.images")

    result = lower_workflow(wf)
    assert result.ok is True
    assert result.workflow is not None

    for node_id, node in result.workflow.nodes.items():
        ui = node.metadata.get("_ui", {})
        pos = ui.get("pos")
        if pos is None:
            continue
        lowering = node.metadata.get("vibecomfy.lowering", {})
        source_id = lowering.get("source_node_id")
        if source_id == "20":
            assert pos[1] == 350, f"KSampler clone: expected y=350, got {pos[1]}"
        elif source_id == "30":
            assert pos[1] == 700, f"SaveImage clone: expected y=700, got {pos[1]}"


# ---------------------------------------------------------------------------
# T9: opt-in native subgraph grouping metadata
# ---------------------------------------------------------------------------


def test_emit_native_groups_defaults_to_flat() -> None:
    """Default lowering (emit_native_groups=False) produces no subgraph definitions."""
    wf = _make_workflow()
    wf.nodes["10"] = _make_loop_node("10", uid="loop-10", var="seed", count=2)
    wf.nodes["20"] = _node_with_ui(
        "20", "KSampler", pos=(0.0, 0.0), size=(315.0, 262.0),
        inputs={"seed": 42, "steps": 20, "cfg": 7.0, "sampler_name": "euler", "scheduler": "normal", "denoise": 1.0},
    )
    wf.nodes["30"] = _node_with_ui(
        "30", "SaveImage", pos=(0.0, 300.0), size=(315.0, 270.0),
        inputs={"filename_prefix": "out/test"},
    )

    wf.connect("10.0", "20.seed")
    wf.connect("20.0", "30.images")

    result = lower_workflow(wf, emit_native_groups=False)
    assert result.ok is True
    assert result.workflow is not None

    metadata = result.workflow.metadata
    definitions = metadata.get("definitions") if isinstance(metadata, dict) else None
    # Flat emission: no definitions key or empty subgraphs.
    if definitions is not None:
        subgraphs = definitions.get("subgraphs")
        assert not subgraphs, (
            f"Flat lowering should not produce subgraph definitions, got: {subgraphs}"
        )


def test_emit_native_groups_opt_in_produces_subgraph_definitions() -> None:
    """Opt-in emit_native_groups=True stores per-iteration subgraph definitions."""
    wf = _make_workflow()
    wf.nodes["10"] = _make_loop_node("10", uid="loop-10", var="seed", count=2)
    wf.nodes["20"] = _node_with_ui(
        "20", "KSampler", pos=(0.0, 0.0), size=(315.0, 262.0),
        inputs={"seed": 42, "steps": 20, "cfg": 7.0, "sampler_name": "euler", "scheduler": "normal", "denoise": 1.0},
    )
    wf.nodes["30"] = _node_with_ui(
        "30", "SaveImage", pos=(0.0, 300.0), size=(315.0, 270.0),
        inputs={"filename_prefix": "out/test"},
    )

    wf.connect("10.0", "20.seed")
    wf.connect("20.0", "30.images")

    result = lower_workflow(wf, emit_native_groups=True)
    assert result.ok is True
    assert result.workflow is not None

    metadata = result.workflow.metadata
    assert isinstance(metadata, dict), "Workflow metadata must be a dict"

    definitions = metadata.get("definitions")
    assert isinstance(definitions, dict), (
        f"emit_native_groups=True should produce definitions, got: {type(definitions)}"
    )

    subgraphs = definitions.get("subgraphs")
    assert isinstance(subgraphs, list), (
        f"definitions.subgraphs should be a list, got: {type(subgraphs)}"
    )
    assert len(subgraphs) == 2, (
        f"Expected 2 iteration subgraphs, got {len(subgraphs)}"
    )

    # Collect all node uids from the lowered workflow for cross-check.
    lowered_uids: set[str] = set()
    for node in result.workflow.nodes.values():
        if node.uid:
            lowered_uids.add(node.uid)

    for iter_idx, sg in enumerate(subgraphs):
        assert isinstance(sg, dict)
        title = sg.get("name", "")
        assert f"Iteration {iter_idx}" in title, (
            f"Subgraph title should contain iteration index, got: {title!r}"
        )
        assert "seed" in title, f"Subgraph title should mention variable, got: {title!r}"

        inner = sg.get("nodes")
        assert isinstance(inner, list), f"Subgraph nodes should be a list, got: {type(inner)}"
        # Should have at least KSampler + SaveImage = 2 nodes per iteration
        assert len(inner) >= 2, (
            f"Expected >= 2 nodes per iteration subgraph, got {len(inner)}"
        )

        for inner_node in inner:
            assert isinstance(inner_node, dict)
            # Must have type and properties.vibecomfy_uid
            assert "type" in inner_node, f"Inner node missing 'type': {inner_node}"
            props = inner_node.get("properties")
            assert isinstance(props, dict), (
                f"Inner node missing 'properties': {inner_node}"
            )
            uid = props.get("vibecomfy_uid")
            assert isinstance(uid, str) and uid, (
                f"Inner node missing non-empty vibecomfy_uid: {inner_node}"
            )
            assert uid in lowered_uids, (
                f"Inner node uid {uid!r} not found in lowered workflow nodes"
            )
