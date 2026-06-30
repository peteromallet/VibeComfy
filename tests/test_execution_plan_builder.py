from __future__ import annotations

import json
import sys
from pathlib import Path
from types import SimpleNamespace

import pytest

_TESTS_DIR = Path(__file__).resolve().parent
if str(_TESTS_DIR) not in sys.path:
    sys.path.insert(0, str(_TESTS_DIR))

from execution_plan_hotshotxl_fixtures import (
    disconnected_sidecar_graph,
    missing_active_8_frame_path_graph,
    missing_connected_video_terminal_graph,
    structurally_complete_video_graph,
)
from vibecomfy.comfy_nodes.agent.execution_plan import (
    ExecutionPlan,
    PlanEvaluation,
    evaluate_execution_plan,
)
from vibecomfy.executor.contracts import (
    ClassifyDecision,
    GraphFacts,
    PrecedentOption,
    PrecedentPacket,
    ResearchResult,
    SelectedPrecedent,
)
from vibecomfy.executor.execution_plan_builder import (
    _normalize_precedent_evidence,
    build_execution_plan,
    detect_named_external_technologies,
    needs_precedent_plan,
)


_FIXTURES_DIR = Path(__file__).parent / "fixtures" / "execution_plans"


@pytest.mark.parametrize("route", ["revise", "respond", "inspect", "research", "clarify"])
def test_needs_precedent_plan_effective_non_adapt_route_wins_over_stale_fields(route: str) -> None:
    stale_classifier = SimpleNamespace(
        effective_route=route,
        research=True,
        implement=True,
        task="research_precedent",
        research_goal="Find HotShotXL workflow precedent templates.",
        search_directions=("HotShotXL custom workflow examples",),
        source_preferences=("workflows",),
        model_families=("HotShotXL",),
    )

    assert needs_precedent_plan(stale_classifier, task="adapt using a HotShotXL template") is False


@pytest.mark.parametrize(
    "task",
    [
        "adapt this graph from a workflow precedent",
        "use a community workflow template for this conversion",
        "port the external workflow pattern into the current graph",
        "add the custom node workflow shown in the reference",
    ],
)
def test_needs_precedent_plan_accepts_adapt_with_workflow_precedent_signals(task: str) -> None:
    plan = ClassifyDecision(
        route="adapt",
        task="edit_graph",
        research_goal="Find matching ComfyUI workflow examples.",
        source_preferences=("workflows", "messages"),
    )

    assert needs_precedent_plan(plan, task=task) is True


@pytest.mark.parametrize(
    ("text", "expected"),
    [
        ("Switch this to generate 8 frames with HotShotXL.", ("HotShotXL",)),
        ("Use a Wan2.2 video workflow.", ("Wan",)),
        ("Convert it to LTX-2.3 image-to-video.", ("LTX",)),
        ("Add AnimateDiff motion handling.", ("AnimateDiff",)),
        ("Style transfer with IP-Adapter.", ("IPAdapter",)),
        ("Wire in ControlNet depth guidance.", ("ControlNet",)),
    ],
)
def test_named_external_technology_detector_preserves_user_terms(
    text: str,
    expected: tuple[str, ...],
) -> None:
    assert detect_named_external_technologies(text) == expected
    assert needs_precedent_plan(ClassifyDecision(route="adapt", task="edit_graph"), task=text)


def test_needs_precedent_plan_uses_classifier_and_graph_fact_signals() -> None:
    classifier_signal = ClassifyDecision(
        route="adapt",
        task="edit_graph",
        model_families=("AnimateDiff",),
    )
    graph_signal = GraphFacts(
        unknown_class_types=("HotshotXLLoader",),
        missing_node_packs=("ComfyUI-ControlNet",),
    )

    assert needs_precedent_plan(classifier_signal) is True
    assert needs_precedent_plan(
        ClassifyDecision(route="adapt", task="edit_graph"),
        graph_facts=graph_signal,
    ) is True


@pytest.mark.parametrize(
    "task",
    [
        "change the prompt to a rainy city street",
        "set seed to 42",
        "increase CFG to 7.5",
        "change sampler steps to 20",
        "switch the checkpoint model name to dreamshaper",
        "rewire the existing VAE decode output locally",
        "add a SaveImage output node",
    ],
)
def test_simple_local_edits_bypass_precedent_planning(task: str) -> None:
    assert needs_precedent_plan(ClassifyDecision(route="revise", task="edit_graph"), task=task) is False
    assert needs_precedent_plan(ClassifyDecision(route="adapt", task="edit_graph"), task=task) is False


def test_legacy_route_alias_normalizes_before_precedent_plan_decision() -> None:
    adapt_alias = ClassifyDecision(
        route="precedent_research",
        task="edit_graph",
        research_goal="Find HotShotXL workflow precedent.",
    )
    revise_alias = ClassifyDecision(
        route="direct_edit",
        task="edit_graph",
        research_goal="Find HotShotXL workflow precedent.",
    )

    assert adapt_alias.effective_route == "adapt"
    assert needs_precedent_plan(adapt_alias) is True
    assert revise_alias.effective_route == "revise"
    assert needs_precedent_plan(revise_alias) is False


def test_executor_package_exports_execution_plan_builder_api() -> None:
    import vibecomfy.executor as executor

    assert executor.build_execution_plan is build_execution_plan
    assert executor.needs_precedent_plan is needs_precedent_plan
    assert executor.detect_named_external_technologies is detect_named_external_technologies


def _role(payload: dict, role_name: str) -> dict:
    return next(role for role in payload["roles"] if role["role"] == role_name)


def _binding(payload: dict, role_name: str) -> dict:
    return next(binding for binding in payload["role_bindings"] if binding["role"] == role_name)


def _hotshotxl_research_result() -> ResearchResult:
    return ResearchResult(
        selected_precedent=SelectedPrecedent(
            name="AnimateDiff HotShotXL video workflow",
            source="hivemind_workflow",
            source_workflow_path="workflows/hotshotxl_8f.json",
            requested_terms=("HotShotXL", "video"),
            implementation_ecosystems=("animatediff",),
            models=("hotshotxl_mm_v1.pth", "sd_xl_base_1.0.safetensors"),
            minimal_spine=(
                "CheckpointLoaderSimple",
                "HotshotXLLoader",
                "ADE_AnimateDiffLoaderWithContext",
                "EmptyLatentImage",
                "KSampler",
                "VAEDecode",
                "VHS_VideoCombine",
            ),
            terminal_output_path=("VHS_VideoCombine",),
        ),
        precedent_packet=PrecedentPacket(
            options=(
                PrecedentOption(
                    source_class_type="video/hotshot_i2v",
                    node_types=("HotshotXLLoader", "VHS_VideoCombine"),
                ),
            ),
        ),
        precedent_sources=(
            {
                "source": "hivemind_workflow",
                "source_workflow_path": "workflows/hotshotxl_8f.json",
                "workflow_semantics": {
                    "node_types": [
                        "HotshotXLLoader",
                        "ADE_AnimateDiffLoaderWithContext",
                        "EmptyLatentImage",
                        "KSampler",
                        "VAEDecode",
                        "VHS_VideoCombine",
                    ],
                    "models": ["hotshotxl_mm_v1.pth"],
                },
                "workflow_schema": {
                    "ADE_AnimateDiffLoaderWithContext": {
                        "input": {
                            "required": {
                                "model": {"type": "MODEL"},
                                "motion_model": {"type": "MOTION_MODEL"},
                            },
                            "optional": {},
                        },
                        "outputs": [{"name": "MODEL", "type": "MODEL"}],
                    },
                    "VHS_VideoCombine": {
                        "input": {"required": {"images": {"type": "IMAGE"}}, "optional": {}},
                        "outputs": [],
                    },
                },
            },
        ),
    )


def test_hotshotxl_evidence_normalization_derives_roles_edges_sockets_and_provenance() -> None:
    research = _hotshotxl_research_result()

    normalized = _normalize_precedent_evidence(
        research,
        classify_result=ClassifyDecision(route="adapt", task="edit_graph"),
        task="Switch this to generate 8 frames of video using HotShotXL.",
        graph_facts=GraphFacts(unknown_class_types=("HotshotXLLoader",)),
    )

    assert normalized is not None
    payload = normalized.to_dict()
    assert payload == json.loads(json.dumps(payload, sort_keys=True))
    assert payload["technologies"] == ["HotShotXL", "AnimateDiff"]
    assert payload["media_domains"] == ["video"]
    assert payload["terminal_role"] == "video_terminal"
    assert payload["required_classes"] == [
        "HotshotXLLoader",
        "ADE_AnimateDiffLoaderWithContext",
        "EmptyLatentImage",
        "KSampler",
        "VAEDecode",
        "VHS_VideoCombine",
    ]

    animatediff = _role(payload, "animatediff_context")
    assert animatediff["input_sockets"]["motion_model"] == "MOTION_MODEL"
    assert animatediff["output_sockets"]["MODEL"] == "MODEL"
    terminal = _role(payload, "video_terminal")
    assert terminal["input_sockets"]["images"] == "IMAGE"
    latent = _role(payload, "latent_source")
    assert latent["widgets"]["batch_size_value"] == 8
    assert payload["widget_evidence"]["latent_source.batch_size"] == {
        "required": True,
        "source": "task",
        "value": 8,
    }
    assert "hotshotxl_mm_v1.pth" in _role(payload, "hotshotxl_motion_model")["models"]
    assert {
        "source_role": "decoder",
        "target_role": "video_terminal",
        "source_socket": "images",
        "target_socket": "images",
        "required": True,
        "evidence_refs": ["role:decoder", "role:video_terminal"],
    } in payload["pattern_edges"]
    assert payload["schema_provenance"]["ADE_AnimateDiffLoaderWithContext"] == (
        "precedent_sources[0].workflow_schema"
    )
    assert payload["schema_provenance"]["HotshotXLLoader"] == "not_available"
    assert payload["runtime_provenance"]["HotshotXLLoader"] == "graph_facts.unknown_class_types"
    assert {
        "class_type": "HotshotXLLoader",
        "kind": "schema_unavailable",
        "role": "hotshotxl_motion_model",
    } in payload["unresolved_evidence"]


def test_build_execution_plan_returns_m1_hotshotxl_plan_matching_golden() -> None:
    plan = build_execution_plan(
        research_result=_hotshotxl_research_result(),
        classify_result=ClassifyDecision(route="adapt", task="edit_graph"),
        task="Switch this to generate 8 frames of video using HotShotXL.",
        graph_facts=GraphFacts(unknown_class_types=("HotshotXLLoader",)),
    )

    assert isinstance(plan, ExecutionPlan)
    payload = plan.to_dict()
    rendered = json.dumps(payload, indent=2, sort_keys=True) + "\n"
    assert rendered == (
        _FIXTURES_DIR / "hotshotxl_8f_execution_plan.json"
    ).read_text(encoding="utf-8")
    assert rendered == json.dumps(plan.to_dict(), indent=2, sort_keys=True) + "\n"

    done_ids = {condition["id"] for condition in payload["done_conditions"]}
    step_ids = {step["id"] for step in payload["required_steps"]}
    active_ids = {condition["id"] for condition in payload["active_path_conditions"]}
    blocked_ids = {condition["id"] for condition in payload["blocked_if"]}

    assert {
        "animatediff.context.present",
        "animatediff.motion_model.edge",
        "sampler.uses_animatediff_model",
        "hotshotxl.active_8_frame_latent_path",
        "video.decoded_frames",
        "video.terminal.consumes_decoded_frames",
    } <= done_ids
    assert {
        "step.hotshotxl_motion_model",
        "step.animatediff_context",
        "step.sampler_model_path",
        "step.active_8_frame_latent_path",
        "step.decoded_frames",
        "step.video_terminal_consumption",
    } <= step_ids
    assert active_ids == {"video.output_domain.active"}
    assert blocked_ids == {"video.image_terminal.active"}


def test_ambiguous_current_graph_roles_are_serialized_as_low_confidence() -> None:
    graph = structurally_complete_video_graph()
    graph["nodes"].extend(
        [
            {
                "id": 101,
                "type": "EmptyLatentImage",
                "class_type": "EmptyLatentImage",
                "widgets_values": [512, 512, 8],
            },
            {"id": 102, "type": "KSampler", "class_type": "KSampler"},
            {"id": 103, "type": "VAEDecode", "class_type": "VAEDecode"},
            {"id": 104, "type": "VHS_VideoCombine", "class_type": "VHS_VideoCombine"},
        ]
    )
    plan = build_execution_plan(
        research_result=_hotshotxl_research_result(),
        classify_result=ClassifyDecision(route="adapt", task="edit_graph"),
        task="Switch this to generate 8 frames of video using HotShotXL.",
        graph=graph,
    )

    assert isinstance(plan, ExecutionPlan)
    payload = json.loads(json.dumps(plan.to_dict(), sort_keys=True))
    for role_name in ("latent_source", "sampler", "decoder", "video_terminal"):
        binding = _binding(payload, role_name)
        assert binding["confidence"] == "low"
        assert binding["node_ref"]["role"] == role_name
        assert "node_id" not in binding["node_ref"]
        assert binding["evidence"]["binding_source"] == "current_graph"
        assert binding["evidence"]["candidate_count"] == 2
        assert binding["evidence"]["ambiguity"].startswith("multiple current graph nodes")
        assert len(binding["evidence"]["candidates"]) == 2

    conditions = list(payload["done_conditions"])
    for step in payload["required_steps"]:
        conditions.extend(step["conditions"])
    for condition in conditions:
        for endpoint in ("source", "target"):
            ref = condition.get(endpoint) or {}
            if ref.get("role") in {"latent_source", "sampler", "decoder", "video_terminal"}:
                assert "node_id" not in ref


def test_missing_current_graph_role_is_serialized_as_blocked() -> None:
    graph = structurally_complete_video_graph()
    graph["nodes"] = [
        node for node in graph["nodes"] if node.get("class_type") != "VHS_VideoCombine"
    ]
    plan = build_execution_plan(
        research_result=_hotshotxl_research_result(),
        classify_result=ClassifyDecision(route="adapt", task="edit_graph"),
        task="Switch this to generate 8 frames of video using HotShotXL.",
        graph=graph,
    )

    assert isinstance(plan, ExecutionPlan)
    payload = json.loads(json.dumps(plan.to_dict(), sort_keys=True))
    binding = _binding(payload, "video_terminal")
    assert binding["confidence"] == "blocked"
    assert binding["node_ref"] == {
        "class_type": "VHS_VideoCombine",
        "role": "video_terminal",
    }
    assert binding["evidence"]["binding_source"] == "current_graph"
    assert binding["evidence"]["candidate_count"] == 0
    assert binding["evidence"]["ambiguity"].startswith("no current graph node")


def _generated_hotshotxl_execution_plan() -> ExecutionPlan:
    plan = build_execution_plan(
        research_result=_hotshotxl_research_result(),
        classify_result=ClassifyDecision(route="adapt", task="edit_graph"),
        task="Switch this to generate 8 frames of video using HotShotXL.",
        graph_facts=GraphFacts(unknown_class_types=("HotshotXLLoader",)),
    )
    assert isinstance(plan, ExecutionPlan)
    return plan


def _failed_condition_ids(evaluation: PlanEvaluation) -> set[str]:
    return {str(condition["condition_id"]) for condition in evaluation.failed_conditions}


def _assert_generated_plan_blocked_by(
    evaluation: PlanEvaluation,
    expected_condition_ids: set[str],
) -> None:
    assert evaluation.ok is False
    assert evaluation.blocking is True
    assert expected_condition_ids <= _failed_condition_ids(evaluation)
    assert evaluation.feedback.startswith("plan evaluation failed:")


def test_generated_hotshotxl_plan_evaluates_reusable_hotshotxl_fixtures() -> None:
    plan = _generated_hotshotxl_execution_plan()

    complete = evaluate_execution_plan(structurally_complete_video_graph(), plan)
    assert complete.ok is True
    assert complete.blocking is False
    assert complete.failed_conditions == ()
    assert complete.feedback == "plan evaluation passed."

    _assert_generated_plan_blocked_by(
        evaluate_execution_plan(disconnected_sidecar_graph(), plan),
        {
            "sampler.uses_animatediff_model",
            "hotshotxl.active_8_frame_latent_path",
            "video.decoded_frames",
            "video.terminal.consumes_decoded_frames",
            "video.output_domain.active",
            "video.image_terminal.active",
        },
    )
    _assert_generated_plan_blocked_by(
        evaluate_execution_plan(missing_active_8_frame_path_graph(), plan),
        {"hotshotxl.active_8_frame_latent_path"},
    )
    _assert_generated_plan_blocked_by(
        evaluate_execution_plan(missing_connected_video_terminal_graph(), plan),
        {
            "video.terminal.consumes_decoded_frames",
            "video.output_domain.active",
            "video.image_terminal.active",
        },
    )


def test_build_execution_plan_returns_none_for_unsupported_or_non_8_frame_evidence() -> None:
    assert (
        build_execution_plan(
            research_result=ResearchResult(
                selected_precedent=SelectedPrecedent(
                    name="Wan video workflow",
                    requested_terms=("Wan", "video"),
                    minimal_spine=("WanVideoSampler", "SaveVideo"),
                    terminal_output_path=("SaveVideo",),
                ),
            ),
            classify_result=ClassifyDecision(route="adapt", task="edit_graph"),
            task="Adapt this to Wan 2.2 video.",
        )
        is None
    )
    assert (
        build_execution_plan(
            research_result=_hotshotxl_research_result(),
            classify_result=ClassifyDecision(route="adapt", task="edit_graph"),
            task="Switch this to generate 16 frames of video using HotShotXL.",
        )
        is None
    )


def test_hotshotxl_evidence_normalization_records_missing_schema_without_blocking() -> None:
    research = ResearchResult(
        selected_precedent=SelectedPrecedent(
            name="HotShotXL minimal video precedent",
            requested_terms=("HotShotXL", "video"),
            minimal_spine=(
                "HotshotXLLoader",
                "ADE_AnimateDiffLoaderWithContext",
                "EmptyLatentImage",
                "KSampler",
                "VAEDecode",
                "VHS_VideoCombine",
            ),
            terminal_output_path=("VHS_VideoCombine",),
        ),
        precedent_sources=(
            {
                "source": "external_workflow",
                "node_types": [
                    "HotshotXLLoader",
                    "ADE_AnimateDiffLoaderWithContext",
                    "VHS_VideoCombine",
                ],
            },
        ),
    )

    normalized = _normalize_precedent_evidence(
        research,
        classify_result=ClassifyDecision(route="adapt", task="edit_graph"),
        task="Use a HotShotXL workflow template for 8 frame video.",
    )

    assert normalized is not None
    payload = normalized.to_dict()
    assert payload["terminal_role"] == "video_terminal"
    assert payload["schema_provenance"]["VHS_VideoCombine"] == "not_available"
    assert payload["runtime_provenance"]["VHS_VideoCombine"] == "not_checked"
    assert _role(payload, "sampler")["input_sockets"]["latent_image"] == "LATENT"
    assert any(item["kind"] == "schema_unavailable" for item in payload["unresolved_evidence"])


def test_packet_only_hotshotxl_evidence_contributes_required_roles() -> None:
    research = ResearchResult(
        precedent_packet=PrecedentPacket(
            options=(
                PrecedentOption(
                    source_class_type="workflow/hotshotxl",
                    node_types=(
                        "HotshotXLLoader",
                        "ADE_AnimateDiffLoaderWithContext",
                        "EmptyLatentImage",
                        "KSampler",
                        "VAEDecode",
                        "VHS_VideoCombine",
                    ),
                ),
            ),
        ),
    )

    normalized = _normalize_precedent_evidence(
        research,
        classify_result=ClassifyDecision(route="adapt", task="edit_graph"),
        task="Adapt this from a HotShotXL 8 frames video precedent.",
    )

    assert normalized is not None
    payload = normalized.to_dict()
    assert payload["required_classes"][0] == "HotshotXLLoader"
    assert "precedent_packet.options[0].node_types" in _role(
        payload,
        "hotshotxl_motion_model",
    )["evidence_refs"]


def test_evidence_normalization_does_not_fabricate_broad_unsupported_video_roles() -> None:
    research = ResearchResult(
        selected_precedent=SelectedPrecedent(
            name="Wan video workflow",
            requested_terms=("Wan", "video"),
            minimal_spine=("WanVideoSampler", "SaveVideo"),
            terminal_output_path=("SaveVideo",),
        ),
        precedent_sources=(
            {
                "source": "external_workflow",
                "node_types": ["WanVideoSampler", "SaveVideo"],
            },
        ),
    )

    assert _normalize_precedent_evidence(
        research,
        classify_result=ClassifyDecision(route="adapt", task="edit_graph"),
        task="Adapt this to Wan 2.2 video.",
    ) is None
