"""Tests for static lowering: data model and loop extraction (T3).

Covers:
- LoweringResult, LoweringEvidence, LoopLoweringPlan, LoweringDiagnostic data shapes
- Loop node discovery (vibecomfy.loop only)
- Loop plan extraction for bounded literal seed/prompt/text loops
- Rejection of unsupported variables, dynamic counts, non-literal over values
- Atomic failure: any invalid loop fails the full LoweringResult
"""

from __future__ import annotations

import pytest

from vibecomfy.contracts.intent_nodes import (
    INTENT_LOOP_MAX_ITERATIONS,
    intent_node_properties,
)
from vibecomfy.porting.lowering import (
    LoopLoweringPlan,
    LoweringDiagnostic,
    LoweringEvidence,
    LoweringResult,
    SUPPORTED_LOOP_VARIABLES,
    discover_loop_nodes,
    extract_loop_plan,
    lower_workflow,
)
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
