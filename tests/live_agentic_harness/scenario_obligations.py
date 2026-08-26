"""T5.3 scenario obligations and fail-closed preflight.

Every finale scenario (the locked 50-entry manifest plus the final5 r5 core)
declares, before any paid model work:

* purpose and expected change;
* invariants that must survive the edit;
* research requirements (typed, from the descriptor's assessment contract);
* custom-node classes touched by the scenario's source workflow;
* schema/runtime provenance requirements — audio and multi-video scenarios
  require EXACT TTS / LayerMask schema evidence before paid calls;
* the prompt/tool contract identity (profile + orchestration modes);
* admissible infrastructure failure classes (T3.1 vocabulary only).

``validate_obligation_coverage`` returns typed violations;
``preflight_scenario_obligations`` raises :class:`ScenarioObligationError` on
any violation. RR1-FIX-REV2: schema resolution AND declaration enforcement
run unconditionally — registered-unproven gated classes are declaration-level
violations, not warnings, and no environment variable or caller flag can
defer or disable the gate. Discovery happens before paid calls, never after.
A safe refusal is useful behavior but never satisfies a scenario whose
obligations require an edit; descriptors granting ``allow_safe_refusal`` on
edit scenarios are a coverage conflict, and an accepted refusal grades
``undetermined``.
"""

from __future__ import annotations

import json
import os
import re
from dataclasses import dataclass, field
from pathlib import Path
from typing import Any, Mapping

from .compare_pipeline_modes import (
    REPO,
    _authoritative_entries,
    _load_json,
)

SCHEMA_RESOLUTION_ENV_VAR = "VIBECOMFY_OBLIGATION_SCHEMA_CHECK"

# Declaration tokens. ``on_demand_runtime`` is not admissible.
ON_DEMAND_SOURCE_KINDS = frozenset(
    {"on_demand_static", "on_demand_import", "on_demand_embedded"}
)
DECLARED_SCHEMA_SOURCES = frozenset({"authoritative_object_info"}) | ON_DEMAND_SOURCE_KINDS
# Explicit False wins over this env var. Independent of SCHEMA_RESOLUTION_ENV_VAR.
RUNTIME_ONLY_ENV_VAR = "VIBECOMFY_OBLIGATION_RUNTIME_ONLY"

#: Admissible infrastructure-failure vocabulary (T3.1 retry-owner freeze).
ADMISSIBLE_INFRA_FAILURES: tuple[str, ...] = (
    "infra_timeout",
    "infra_empty_response",
)

#: Exact schema-evidence requirements for gated scenarios. Audio requires
#: exact IndexTTS schema evidence; multi-video requires exact LayerMask schema
#: evidence — each entry names the exact class_type, its owning pack, the
#: authoritative source kind that must attest it, and (when pinned by the r5
#: regression fixtures) field-level visibility evidence.
SCHEMA_EVIDENCE_REQUIREMENTS: dict[str, tuple[Mapping[str, Any], ...]] = {
    "audio-tts-narration-using-indextts-2": (
        {
            "class_type": "IndexTTSEngineNode",
            "pack": "ComfyUI-IndexTTS",
            "source": "authoritative_object_info",
            # RR1-FIX-REV: exact ports validated against the frozen captured
            # schema before paid calls.
            "required_inputs": ("model_path", "temperature", "top_p"),
            "required_widgets": ("model_path",),
            "required_outputs": ("TTS_engine",),
        },
        {
            "class_type": "IndexTTSEmotionOptionsNode",
            "pack": "ComfyUI-IndexTTS",
            "source": "authoritative_object_info",
            # Real per-emotion slider inputs on the regenerated cache (the
            # former 2-input stub fabricated an ``emotion_control`` input;
            # reality: eight named FLOAT sliders, ``emotion_control`` is the
            # node OUTPUT). Leg edits target these sliders by name.
            "required_field_evidence": ("Sad", "Disgusted", "Calm"),
            "required_widgets": ("Sad", "Disgusted", "Calm"),
            "required_outputs": ("emotion_control",),
        },
    ),
    "multi-video-based-character-replacement-using": (
        {
            "class_type": "LayerMask: LoadSegmentAnythingModels",
            "pack": "ComfyUI_LayerStyle_Advance",
            "source": "authoritative_object_info",
            "required_outputs": ("sam_models",),
        },
        {
            "class_type": "LayerMask: SegmentAnythingUltra V3",
            "pack": "ComfyUI_LayerStyle_Advance",
            "source": "authoritative_object_info",
            "required_outputs": ("image", "mask"),
        },
    ),
    # RRSYN-4 / RR1-FIX-REV: the four provider captures this wave once cited
    # (audio-separation-nodes-comfyui@local-ac33956, ComfyUI-Easy-Use@local-
    # 4de1ab3, ComfyUI-Inspire-Pack@local-d23db9a,
    # ComfyUI-llama-cpp_vlm@local-f2209cc) were OFFLINE stub-extraction
    # products, never live /object_info surfaces.  They are now removed and
    # unindexed; every class they carried is recorded honestly below as
    # UNPROVEN — the enforced preflight refuses paid calls instead of grading
    # an impossible leg as product failure.
    # Exact port expectations stay encoded here so that when a same-pack LIVE
    # capture lands, the declaration can be restored WITH its ports:
    #   audio-acestep-audio-latent-workflow-with-vocal-separ-0eb676 /
    #     audio-acestep-audio-generation-and-processing-workfl-1b1360:
    #     AudioCombine/AudioSeparation (pack audio-separation-nodes-comfyui);
    #   image-generates-a-2x2-seed-variation: ImageBatchSplitter //Inspire
    #     (ComfyUI-Inspire-Pack), easy forLoopStart/easy forLoopEnd
    #     (ComfyUI-Easy-Use, incl. dynamic loop outputs);
    #   multi-wan-vace-video-retargeting-driven: easy forLoopStart/End;
    #   image-llama-cpp-instruct-image-preview-and-save-5b54bf:
    #     llama_cpp_model_loader / llama_cpp_instruct_adv /
    #     llama_cpp_parameters (ComfyUI-llama-cpp_vlm).
}

#: Class-type families that trigger the exact-schema-evidence gate wherever
#: they appear in a scenario's source workflow.  RRSYN-4 adds the audio
#: family, Inspire, Easy-Use loop/type nodes, LLaMA-CPP and
#: Advanced-ControlNet: any gated class without a declared requirement
#: above fails setup (never graded as a product failure).
_GATED_CLASS_RE = re.compile(
    r"IndexTTS|LayerMask|SegmentAnything"
    r"|AudioCombine|AudioSeparation|AudioFilter|AudioVolumeNormalization"
    r"|VocalAndSoundRemover|VibeVoice"
    r"|//Inspire|easy forLoop|\beasy int\b"
    r"|llama_cpp|ACN_AdvancedControlNet",
    re.IGNORECASE,
)


#: RRSYN-4 honest-gap registry.  Gated classes whose owning pack could NOT
#: be proven by a same-pack runtime capture are recorded here per locked
#: scenario instead of being declared with guessed provenance.
#: RR1-FIX-REV / RR1-FIX-REV2: every edit-required gated class in this
#: registry is a typed VIOLATION at BOTH the declaration level and the
#: (now unconditional) preflight resolution pass: setup fails before any
#: paid call, never a laundered or warned-only pass.
#:
#: RRSYN-4 classes DEMOTED here by RR1-FIX-REV (their ``local-*`` captures
#: were offline stub extraction, now removed/unindexed):
#:   * AudioCombine / AudioSeparation (audio-separation-nodes-comfyui);
#:   * ImageBatchSplitter //Inspire (ComfyUI-Inspire-Pack);
#:   * easy forLoopStart / easy forLoopEnd (ComfyUI-Easy-Use);
#:   * llama_cpp_model_loader / llama_cpp_instruct_adv /
#:     llama_cpp_parameters (ComfyUI-llama-cpp_vlm).
UNPROVEN_PROVIDER_CLASSES: dict[str, tuple[str, ...]] = {
    "audio-acestep-audio-generation-and-processing-workfl-1b1360": (
        "AudioCombine",
        "AudioSeparation",
        "AudioFilter",
        "AudioVolumeNormalization",
        "VocalAndSoundRemoverNode",
    ),
    "audio-acestep-audio-latent-workflow-with-vocal-separ-0eb676": (
        "AudioCombine",
        "AudioSeparation",
        "AudioFilter",
        "AudioVolumeNormalization",
        "VocalAndSoundRemoverNode",
    ),
    "audio-audio-processing-with-voice-tts-and-noise-remo-b80848": (
        "VibeVoiceTTS",
    ),
    # comfy_api v3-schema node: INPUT_TYPES is a shim object, not faithfully
    # observable by the offline stub extractor at this commit.
    # RR1-FIX-REV: ImageBatchSplitter //Inspire + easy forLoopStart/End join
    # ``easy int`` — their Inspire/Easy-Use captures were simulated imports,
    # not live object_info.
    "image-generates-a-2x2-seed-variation": (
        "easy int",
        "ImageBatchSplitter //Inspire",
        "easy forLoopStart",
        "easy forLoopEnd",
    ),
    # Easy-Use loop nodes: dynamic outputs were the motivation for the
    # original obligation; without a LIVE capture the output surface is
    # unproven and stays honestly blocked.
    "multi-wan-vace-video-retargeting-driven": (
        "easy forLoopStart",
        "easy forLoopEnd",
    ),
    "image-llama-cpp-instruct-image-preview-and-save-5b54bf": (
        "llama_cpp_model_loader",
        "llama_cpp_instruct_adv",
        "llama_cpp_parameters",
    ),
    # ACN_AdvancedControlNetApply extraction fails under offline stubs;
    # provider (ComfyUI-Advanced-ControlNet) is known but UNPROVEN here.
    "image-sd3-image-generation-with-controlnet-19d221": (
        "ACN_AdvancedControlNetApply",
    ),
}


#: Terminal-state ``no_candidate_reason`` vocabulary.  These labels classify
#: HOW a scoped diff ended without an eligible candidate; they carry ZERO
#: adjudicative authority over a declared expected-no-candidate premise
#: (ADJUDICATION-4 ruling 1.1c): ``no_changes`` is emitted by
#: ``_frag_revision_stages.py`` whenever the scoped diff has no eligible
#: candidate, regardless of why, so it can never prove a named class or a
#: structural feature is absent.  Evidence always comes from the typed
#: blocker carriers, never from these labels.
TERMINAL_NO_CANDIDATE_REASONS = frozenset({"no_changes", "no_graph"})

#: Member kinds admissible in declared structural-feature checks.
STRUCTURAL_MEMBER_KINDS = ("input", "widget", "output")

#: Refusal-kind compatibility (ADJUDICATION-4 rulings 1.1b/1.1d, RRSYN2-1):
#: a proven named-schema absence terminates in ONE OF THE RUBRIC'S SAFE-
#: REFUSAL TERMINALS — ``requires_custom_nodes`` or ``clarify``.  Which of
#: the two the agent closes with is terminal substance, not a descriptor
#: law: forcing ``requires_custom_nodes`` failed honest ``clarify`` stops
#: whose typed evidence was complete (hotshot-16-frames-agent-edit).  A
#: typed structural-feature absence still asks the operator a question and
#: terminates in ``clarify``.  Foreign kinds stay rejected (fail closed).
_SAFE_REFUSAL_TERMINAL_KINDS = frozenset({"clarify", "requires_custom_nodes"})
_NAMED_CLASS_REQUIRED_KINDS = _SAFE_REFUSAL_TERMINAL_KINDS
_STRUCTURAL_REQUIRED_KIND = "clarify"


def _string_tuple(raw: Any) -> tuple[str, ...]:
    """Normalize a declared JSON string/list field to stripped non-empty tokens."""
    if isinstance(raw, str):
        return (raw.strip(),) if raw.strip() else ()
    if isinstance(raw, list):
        return tuple(
            token.strip()
            for token in raw
            if isinstance(token, str) and token.strip()
        )
    return ()


def _parse_structural_features(raw: Any) -> tuple[dict[str, Any], ...]:
    """Parse ``expected_no_candidate_absent_features`` declarations.

    Well-formedness only (non-empty names, checks, member kinds); semantic
    validation lives in :func:`descriptor_contract_violations` so synthetic
    tests never need to monkeypatch authoritative entries.
    """
    if not isinstance(raw, list):
        return ()
    features: list[dict[str, Any]] = []
    for raw_feature in raw:
        if not isinstance(raw_feature, Mapping):
            continue
        feature = str(raw_feature.get("feature") or "").strip()
        raw_checks = raw_feature.get("checks")
        if not isinstance(raw_checks, list):
            continue
        checks: list[dict[str, str]] = []
        for raw_check in raw_checks:
            if not isinstance(raw_check, Mapping):
                continue
            check = {
                "class_type": str(raw_check.get("class_type") or "").strip(),
                "member_kind": str(raw_check.get("member_kind") or "").strip(),
                "member": str(raw_check.get("member") or "").strip(),
            }
            if all(check.values()):
                checks.append(check)
        if feature and checks:
            features.append({"feature": feature, "checks": checks})
    return tuple(features)


def expected_no_candidate_contract(
    descriptor: Mapping[str, Any],
) -> Mapping[str, Any] | None:
    """Return the declared grounded no-candidate contract, or ``None``.

    ADJUDICATION-4 ruling 1.1: this is the SINGLE canonical parser for the
    expected-no-candidate contract — the assessor delegates here and must not
    re-implement permissive parsing.  A scenario declares the contract ONLY
    through a non-empty ``assessment.expected_no_candidate_reason``;
    ``apply=false`` plus ``assessment.expect_graph_changed=false`` alone are
    two bare flags and derive nothing.

    The returned contract carries:

    * ``reason`` — the declared absence premise;
    * ``refusal_kinds`` — outcome kinds accepted from the envelope;
    * ``absent_classes`` — declared absent-class tokens for named-class
      premises (logical AND);
    * ``absent_features`` — declared typed structural checks for
      feature-absence premises;
    * ``evidence_mode`` — exactly one of ``named_class`` /
      ``structural_feature`` / ``none``.
    """
    assessment = (
        descriptor.get("assessment")
        if isinstance(descriptor.get("assessment"), Mapping)
        else {}
    )
    reason = assessment.get("expected_no_candidate_reason")
    if not isinstance(reason, str) or not reason.strip():
        return None
    refusal_kinds = _string_tuple(assessment.get("allow_safe_refusal_outcome_kinds"))
    absent_classes = _string_tuple(
        assessment.get("expected_no_candidate_absent_classes")
    )
    absent_features = _parse_structural_features(
        assessment.get("expected_no_candidate_absent_features")
    )
    if absent_classes and not absent_features:
        evidence_mode = "named_class"
    elif absent_features and not absent_classes:
        evidence_mode = "structural_feature"
    elif absent_classes and absent_features:
        evidence_mode = "contradictory"
    else:
        evidence_mode = "none"
    return {
        "reason": reason.strip(),
        "refusal_kinds": refusal_kinds,
        "absent_classes": absent_classes,
        "absent_features": absent_features,
        "evidence_mode": evidence_mode,
    }


def descriptor_contract_violations(
    descriptor: Mapping[str, Any],
) -> tuple[str, ...]:
    """Pure descriptor-level validation of a declared no-candidate contract.

    ADJUDICATION-4 §2 (scenario_obligations 2/5): all semantic validation of
    the contract lives here so synthetic validation tests can call this
    directly on a descriptor mapping — no manifest, no authoritative entries,
    no monkeypatching.  Returns human-readable violation strings; empty means
    the descriptor's contract (if any) is coherent.
    """
    contract = expected_no_candidate_contract(descriptor)
    violations: list[str] = []
    if contract is None:
        bare_non_edit = descriptor_is_bare_untyped_non_edit(descriptor)
        if bare_non_edit:
            violations.append(
                "bare apply=false + expect_graph_changed=false without an "
                "explicit non-edit lane (health_control / answer rubric / "
                "answer_only / executed research) or a declared "
                "expected-no-candidate contract"
            )
        return tuple(violations)

    assessment = (
        descriptor.get("assessment")
        if isinstance(descriptor.get("assessment"), Mapping)
        else {}
    )
    if bool(descriptor.get("apply")) or bool(assessment.get("expect_graph_changed")):
        violations.append(
            "expected_no_candidate contract contradicts an edit expectation "
            "(apply/expect_graph_changed true); an annotation cannot loosen "
            "an edit obligation"
        )
    if not contract["refusal_kinds"]:
        violations.append(
            "expected_no_candidate contract declares no "
            "allow_safe_refusal_outcome_kinds; grounded no-candidate "
            "adjudication would fail closed on every leg"
        )
    mode = contract["evidence_mode"]
    if mode == "contradictory":
        violations.append(
            "expected_no_candidate contract declares both absent classes and "
            "absent features; exactly one evidence mode is required"
        )
    elif mode == "none":
        violations.append(
            "expected_no_candidate contract declares neither "
            "expected_no_candidate_absent_classes nor "
            "expected_no_candidate_absent_features; exactly one typed "
            "evidence mode is required"
        )
    elif mode == "structural_feature":
        if _STRUCTURAL_REQUIRED_KIND not in contract["refusal_kinds"]:
            violations.append(
                "structural-feature absence contracts require the clarify "
                f"terminal outcome kind {_STRUCTURAL_REQUIRED_KIND!r}"
            )
        for feature in contract["absent_features"]:
            for check in feature["checks"]:
                if check["member_kind"] not in STRUCTURAL_MEMBER_KINDS:
                    violations.append(
                        "structural check "
                        f"{feature['feature']}/{check['class_type']}."
                        f"{check['member']!r} declares unknown member_kind "
                        f"{check['member_kind']!r}; expected one of "
                        f"{list(STRUCTURAL_MEMBER_KINDS)!r}"
                    )
    elif mode == "named_class":
        declared = set(contract["refusal_kinds"])
        foreign = sorted(declared - _NAMED_CLASS_REQUIRED_KINDS)
        if foreign:
            violations.append(
                "named-class absence contracts accept only the rubric's "
                f"safe-refusal terminals {sorted(_NAMED_CLASS_REQUIRED_KINDS)!r} "
                f"but also declare {foreign!r}"
            )
        elif not (declared & _NAMED_CLASS_REQUIRED_KINDS):
            violations.append(
                "named-class absence contracts require at least one "
                "recognized safe-refusal terminal outcome kind in "
                f"{sorted(_NAMED_CLASS_REQUIRED_KINDS)!r}"
            )
    return tuple(violations)


def explicit_non_edit_lane(descriptor: Mapping[str, Any]) -> str | None:
    """Return the explicitly typed non-edit lane name, or ``None``.

    ADJUDICATION-4 ruling 1.1f: these lanes — and only these — make bare
    non-edit expectations legal:
    health_control classification, an answer-rubric semantic lane,
    ``interaction_mode="answer_only"``, or required executed research.
    """
    classification = (
        descriptor.get("classification")
        if isinstance(descriptor.get("classification"), Mapping)
        else {}
    )
    if classification.get("kind") == "health_control":
        return "health_control"
    if isinstance(descriptor.get("answer_rubric"), Mapping):
        return "answer_rubric"
    if descriptor.get("interaction_mode") == "answer_only":
        return "answer_only"
    assessment = (
        descriptor.get("assessment")
        if isinstance(descriptor.get("assessment"), Mapping)
        else {}
    )
    if assessment.get("require_executed_research"):
        return "research"
    return None


def descriptor_is_bare_untyped_non_edit(descriptor: Mapping[str, Any]) -> bool:
    """True for an edit-kind scenario that merely sets both flags false."""
    if descriptor.get("apply") is not False:
        return False
    assessment = (
        descriptor.get("assessment")
        if isinstance(descriptor.get("assessment"), Mapping)
        else {}
    )
    if assessment.get("expect_graph_changed") is not False:
        return False
    if expected_no_candidate_contract(descriptor) is not None:
        return False
    return explicit_non_edit_lane(descriptor) is None


class ScenarioObligationError(ValueError):
    """Fail-closed preflight refusal: scenario setup is incomplete."""


@dataclass(frozen=True)
class ScenarioObligation:
    """Declared obligations for one final scenario."""

    scenario_id: str
    purpose: str
    expected_change: str  # "edit" | "none" | "research_answer" | ...
    invariants: tuple[str, ...]
    research_requirements: tuple[str, ...]
    custom_node_classes: tuple[str, ...]
    schema_evidence_requirements: tuple[Mapping[str, Any], ...]
    prompt_tool_contract: Mapping[str, Any]
    admissible_infra_failures: tuple[str, ...] = ADMISSIBLE_INFRA_FAILURES
    requires_edit: bool = False
    safe_refusal_cannot_satisfy: bool = True
    #: Declared grounded no-candidate contract (None when the scenario does
    #: not declare ``assessment.expected_no_candidate_reason``).  Presence of
    #: this contract — never the two bare edit-expectation flags — is what
    #: designates a scenario as expected-no-candidate.
    expected_no_candidate: Mapping[str, Any] | None = None


def _workflow_class_types(descriptor: Mapping[str, Any]) -> tuple[str, ...]:
    """Collect every node class type from the scenario's source workflow."""
    workflow_path = descriptor.get("workflow_path")
    if not isinstance(workflow_path, str) or not workflow_path.strip():
        return ()
    path = REPO / workflow_path
    if not path.is_file():
        return ("<missing_source_workflow>",)
    try:
        graph = json.loads(path.read_text(encoding="utf-8"))
    except (OSError, json.JSONDecodeError):
        return ("<unreadable_source_workflow>",)
    classes: set[str] = set()

    def walk(node: Any) -> None:
        if isinstance(node, Mapping):
            class_type = node.get("class_type")
            if isinstance(class_type, str) and class_type:
                classes.add(class_type)
            node_type = node.get("type")
            if (
                isinstance(node_type, str)
                and node_type
                and "widgets_values" in node
            ):
                classes.add(node_type)
            for value in node.values():
                walk(value)
        elif isinstance(node, (list, tuple)):
            for value in node:
                walk(value)

    walk(graph)
    return tuple(sorted(classes))


def load_scenario_obligation(scenario_id: str) -> ScenarioObligation | None:
    """Derive one scenario's obligations from its locked descriptor.

    The descriptor is the locked authority (byte-digested by the manifests);
    obligations are read additively from it so they can never drift from what
    the finale actually runs. Returns None when no descriptor exists.
    """
    canonical = _authoritative_entries()
    entry = canonical.get(scenario_id)
    if entry is None:
        return None
    descriptor = _load_json(REPO / str(entry["path"])) or {}

    assessment = (
        descriptor.get("assessment")
        if isinstance(descriptor.get("assessment"), Mapping)
        else {}
    )
    classification = (
        descriptor.get("classification")
        if isinstance(descriptor.get("classification"), Mapping)
        else {}
    )
    tags = descriptor.get("_tags") if isinstance(descriptor.get("_tags"), Mapping) else {}
    no_candidate = expected_no_candidate_contract(descriptor)
    expect_change = bool(assessment.get("expect_graph_changed"))
    apply_requested = bool(descriptor.get("apply"))
    research_required = bool(assessment.get("require_executed_research"))
    interaction_mode = str(descriptor.get("interaction_mode") or "")

    if expect_change or apply_requested:
        expected_change = "edit"
    elif research_required:
        expected_change = "research_answer"
    elif interaction_mode == "answer_only":
        expected_change = "inspect_answer"
    elif no_candidate is not None:
        # ADJUDICATION-4 ruling 1.1: "none" derives ONLY from the DECLARED
        # no-candidate refusal contract (adjudicated by the assessor against
        # typed absence evidence), never from two bare false flags.
        expected_change = "none"
    elif explicit_non_edit_lane(descriptor) is not None:
        # Ruling 1.1f: an explicitly typed non-edit lane (health_control or
        # answer-rubric semantic product) legitimately expects no edit.
        expected_change = "none"
    else:
        # ADJUDICATION-4 §2 (obligations 3/4): the unconditional
        # ``else: "none"`` fall-through is REMOVED. An edit-kind scenario
        # that merely sets apply=false + expect_graph_changed=false is an
        # untyped non-edit obligation; coverage flags it and the assessor
        # grades it undetermined.
        expected_change = "untyped_none"

    classes = _workflow_class_types(descriptor)
    gated_classes = tuple(c for c in classes if _GATED_CLASS_RE.search(c))
    declared_requirements = SCHEMA_EVIDENCE_REQUIREMENTS.get(scenario_id, ())
    # Fail-closed completeness: every gated class present in the workflow must
    # be covered by a declared requirement.
    declared_classes = {
        str(req.get("class_type")) for req in declared_requirements
    }
    undeclared = tuple(c for c in gated_classes if c not in declared_classes)

    invariants = [
        "accepted_batch_is_sole_mutation_authority",
        "untouched_nodes_survive_unmodified",
        "terminal_state_from_frozen_table_only",
    ]
    desired = (
        descriptor.get("desired") if isinstance(descriptor.get("desired"), Mapping) else {}
    )
    if desired.get("quality"):
        invariants.append("pipeline_function_preserved")

    return ScenarioObligation(
        scenario_id=scenario_id,
        purpose=str(
            classification.get("purpose")
            or desired.get("outcome")
            or descriptor.get("query")
            or ""
        ),
        expected_change=expected_change,
        invariants=tuple(invariants),
        research_requirements=(
            ("require_executed_research",) if research_required else ()
        ),
        custom_node_classes=classes,
        schema_evidence_requirements=(
            tuple(dict(req) for req in declared_requirements) + tuple(
                {"class_type": c, "undeclared": True} for c in undeclared
            )
        ),
        prompt_tool_contract={
            "profile": descriptor.get("profile"),
            "modes": ["staged", "threaded"],
            "interaction_mode": interaction_mode or None,
        },
        requires_edit=expected_change == "edit",
        safe_refusal_cannot_satisfy=expected_change == "edit",
        expected_no_candidate=no_candidate,
    )


def validate_obligation_coverage(
    manifest_path: Path | None = None,
) -> tuple[list[str], list[str]]:
    """Return ``(violations, warnings)`` for a comparison manifest.

    Violations fail the preflight closed. Warnings record policy conflicts
    that need adjudication without blocking the whole lane.
    """
    from .compare_pipeline_modes import DEFAULT_COMPARISON_MANIFEST

    path = manifest_path or DEFAULT_COMPARISON_MANIFEST
    manifest = _load_json(Path(path)) or {}
    entries = manifest.get("entries")
    if not isinstance(entries, list):
        return (
            [f"manifest {path} has no entries list"],
            [],
        )
    canonical = _authoritative_entries()

    violations: list[str] = []
    warnings: list[str] = []
    for item in entries:
        scenario_id = str(item.get("id") or "")
        obligation = load_scenario_obligation(scenario_id)
        if obligation is None:
            violations.append(
                f"{scenario_id}: no authoritative descriptor; obligations cannot be derived"
            )
            continue
        for req in obligation.schema_evidence_requirements:
            if req.get("undeclared"):
                continue
            req_source = str(req.get("source") or "").strip()
            if req_source and req_source not in DECLARED_SCHEMA_SOURCES:
                violations.append(
                    f"{scenario_id}: {str(req.get('class_type') or '')!r} "
                    f"declares source {req_source!r}; admissible declared "
                    f"sources are {sorted(DECLARED_SCHEMA_SOURCES)}"
                )
        descriptor = _load_json(REPO / str(canonical[scenario_id]["path"])) or {}
        assessment = (
            descriptor.get("assessment")
            if isinstance(descriptor.get("assessment"), Mapping)
            else {}
        )

        # Safe refusal is useful behavior but cannot satisfy an edit-requiring
        # final scenario (T5.3). A locked descriptor that grants refusal
        # outcome kinds on an edit scenario is recorded as a policy-conflict
        # warning for adjudication — the finale aggregation must never score a
        # refusal pass as product success for these scenarios.
        allowed_refusals = assessment.get("allow_safe_refusal_outcome_kinds")
        if obligation.requires_edit and allowed_refusals:
            warnings.append(
                f"{scenario_id}: edit-requiring scenario grants "
                f"allow_safe_refusal_outcome_kinds={allowed_refusals!r}; a safe "
                "refusal must not be scored as satisfying this scenario"
            )

        # ADJUDICATION-4 §2 (obligations 2/4): the declared no-candidate
        # contract must be coherent — validated by the PURE descriptor
        # validator (no manifest/authoritative-entry coupling), and a bare
        # untyped non-edit obligation is itself a coverage violation.
        violations.extend(
            f"{scenario_id}: {violation}"
            for violation in descriptor_contract_violations(descriptor)
        )
        if obligation.expected_change == "untyped_none":
            violations.append(
                f"{scenario_id}: bare apply=false + expect_graph_changed=false "
                "without an explicit non-edit lane or declared expected-no-"
                "candidate contract is an invalid untyped non-edit obligation"
            )

        # Audio/multi-video gate: exact schema evidence must be declared for
        # every gated class present in the workflow. Auto-added
        # ``undeclared`` marker rows are placeholders, not declarations.
        declared = {
            str(req.get("class_type"))
            for req in obligation.schema_evidence_requirements
            if not req.get("undeclared")
        }
        for class_type in obligation.custom_node_classes:
            if not _GATED_CLASS_RE.search(class_type):
                continue
            if class_type.startswith("<"):
                violations.append(
                    f"{scenario_id}: source workflow could not be read "
                    f"({class_type}); cannot verify schema provenance"
                )
                continue
            if class_type not in declared:
                # RR1-FIX-REV2: registered-unproven classes are no longer a
                # warning-and-continue bypass — every gated class without a
                # DECLARED exact-provenance requirement is a declaration-level
                # violation, unconditionally.
                violations.append(
                    f"{scenario_id}: gated class {class_type!r} has no exact "
                    "schema provenance requirement (audio/multi-video require "
                    "exact TTS/LayerMask schema evidence before paid calls)"
                )
                continue
            req = next(
                (
                    r
                    for r in obligation.schema_evidence_requirements
                    if str(r.get("class_type")) == class_type
                ),
                {},
            )
            missing = [
                key
                for key in ("pack", "source")
                if not str(req.get(key) or "").strip()
            ]
            if missing:
                violations.append(
                    f"{scenario_id}: gated class {class_type!r} requirement "
                    "is missing " + "/".join(missing)
                )
    return violations, warnings


def _authoritative_cache_roots() -> list[Path]:
    """Local object_info cache roots eligible as authoritative sources."""
    roots: list[Path] = []
    env_cache = os.environ.get("VIBECOMFY_OBJECT_INFO_CACHE_DIR")
    if env_cache:
        roots.append(Path(env_cache))
    roots.append(REPO / "vibecomfy" / "porting" / "cache" / "object_info")
    return roots


def _provenance_row(
    root: Path,
    class_type: str,
) -> tuple[bool, str]:
    """Return whether *class_type*'s cache file carries real provenance."""
    try:
        index = json.loads((root / "index.json").read_text(encoding="utf-8"))
    except (OSError, json.JSONDecodeError):
        return False, f"unreadable cache index at {root}"
    filename = index.get(class_type) if isinstance(index, Mapping) else None
    if not isinstance(filename, str) or not filename:
        return False, f"{class_type!r} has no cache-file row in {root}/index.json"
    prov_path = root / "provenance.json"
    try:
        provenance = (
            json.loads(prov_path.read_text(encoding="utf-8"))
            if prov_path.is_file()
            else {}
        )
    except (OSError, json.JSONDecodeError):
        return False, f"unreadable provenance attestation at {prov_path}"
    packs = (
        provenance.get("packs")
        if isinstance(provenance, Mapping)
        else None
    )
    entry = packs.get(filename) if isinstance(packs, Mapping) else None
    if not isinstance(entry, Mapping):
        return False, (
            f"no provenance attestation for {filename!r}; an unattested cache "
            "is not an authoritative source"
        )
    if not (entry.get("repo") or entry.get("locked_commit")):
        return False, (
            f"provenance for {filename!r} carries neither repo nor locked_commit"
        )
    return True, ""



def _pack_entry(
    root: Path,
    class_type: str,
) -> tuple[str, dict[str, Any] | None]:
    """Index filename + pack-JSON entry. Never ``NodeSchema.source_provider``."""
    from vibecomfy.porting.object_info.serialize import _read_existing_index
    from vibecomfy.schema.ensure_capture import _read_cache_entry

    filename = _read_existing_index(root).get(class_type) or ""
    if not filename:
        return "", None
    return filename, _read_cache_entry(root, filename, class_type)


def _entry_source_kind(entry: Mapping[str, Any] | None) -> str:
    """The pack-JSON entry's ``source_kind`` stamp ('' when unstamped)."""
    return str((entry or {}).get("source_kind") or "").strip()


def _is_runtime_family_entry(
    filename: str,
    entry: dict[str, Any] | None,
) -> bool:
    """Runtime-family evidence: runtime stamp, runpod/runtime_core filename, or unstamped legacy ingest.

    On-demand-shaped filenames and stubs never qualify, even if the pack JSON
    stamp claims otherwise (no masquerade).
    """
    from vibecomfy.schema.ensure_capture import (
        RUNTIME_SOURCE_KINDS,
        _is_stub_index_row,
    )

    if entry is None:
        return False
    if "@on_demand_" in filename or _is_stub_index_row(filename, entry):
        return False
    source_kind = _entry_source_kind(entry)
    if source_kind in ON_DEMAND_SOURCE_KINDS:
        return False
    if source_kind in RUNTIME_SOURCE_KINDS:
        return True
    lowered = filename.lower()
    if "@runpod-snapshot" in lowered or "runtime_core" in lowered:
        return True
    return not source_kind and not lowered.endswith("@stub.json")


def _declaration_matches_entry(
    declared: str,
    filename: str,
    entry: dict[str, Any] | None,
) -> tuple[bool, str]:
    """Batch D two-vocabulary match: declaration token vs cache stamp.

    On-demand declarations match their EXACT pack-JSON ``source_kind`` (no
    upgrades, no downgrades); ``authoritative_object_info`` requires the
    runtime-family recognizer above. Returns ``(matched, failure_text)``.
    """
    actual = _entry_source_kind(entry)
    if declared in ON_DEMAND_SOURCE_KINDS:
        if actual == declared:
            return True, ""
        return False, (
            f"{filename} attests source_kind {actual or '<none>'!r}; the "
            f"requirement declares {declared!r} and on-demand declarations "
            "match their exact tier with no upgrades or downgrades"
        )
    if _is_runtime_family_entry(filename, entry):
        return True, ""
    return False, (
        f"local capture {filename} is not a runtime-family object_info dump "
        f"(source_kind {actual or '<none>'!r}) so it cannot satisfy an "
        "'authoritative_object_info' declaration"
    )


def _runtime_only_violation(declared: str) -> str | None:
    """Rejection text when the strict flag forbids an on-demand declaration."""
    if declared not in ON_DEMAND_SOURCE_KINDS:
        return None
    return (
        f"the {RUNTIME_ONLY_ENV_VAR}=1 strict flag forbids on-demand schema "
        f"evidence, but this requirement declares {declared!r}; provide a "
        "genuine runtime object_info capture instead"
    )


def _resolution_tier(requirement: Mapping[str, Any]) -> dict[str, str]:
    """Cache stamp + provenance facts for a just-resolved requirement.

    Records the CACHE stamp (never the declaration token) as ``source_kind``
    plus provenance ``extraction_rung`` / ``locked_commit``; empty strings
    where unstamped (legacy pins carry no extraction_rung).
    """
    from vibecomfy.schema.ensure_capture import (
        _load_provenance,
        _provenance_pack_row,
    )

    class_type = str(requirement.get("class_type") or "").strip()
    declared_pack = str(requirement.get("pack") or "").strip()
    declared_source = str(requirement.get("source") or "").strip()
    for root in _authoritative_cache_roots():
        filename, entry = _pack_entry(root, class_type)
        if entry is None:
            continue
        if str(entry.get("pack") or "") != declared_pack:
            continue
        matched, _ = _declaration_matches_entry(declared_source, filename, entry)
        if not matched:
            continue
        row = _provenance_pack_row(_load_provenance(root), filename) or {}
        return {
            "source_kind": _entry_source_kind(entry),
            "extraction_rung": str(row.get("extraction_rung") or ""),
            "locked_commit": str(row.get("locked_commit") or ""),
        }
    return {}



def _resolve_schema_locally(
    requirement: Mapping[str, Any],
    *,
    runtime_only: bool = False,
) -> tuple[bool, list[str]]:
    """LOCAL-ONLY authoritative resolution of one declared schema evidence
    requirement. Never touches the network.

    Proves (G5-B4-MUST-006, Batch D), beyond bare ``provider.get(...)``
    existence:
    * the declared ``source`` kind is inside ``DECLARED_SCHEMA_SOURCES``
      (on-demand tiers are accepted AS THEMSELVES);
    * under ``runtime_only``, on-demand declarations are rejected outright;
    * the class resolves from a local object_info cache ROOT whose
      provenance attests the DECLARED owning ``pack``;
    * the backing cache file carries real provenance (a repo or a locked
      commit — never an unattested/stub capture), and provenance and pack
      file agree on ``source_kind``;
    * the resolved capture is not stub-shaped (belt and suspenders on top of
      the index's ``@stub.json`` filter) and matches the declaration per the
      two-vocabulary table;
    * every ``required_field_evidence`` field name is visible in the
      resolved schema inputs (e.g. ``emotion_control``).
    """
    class_type = str(requirement.get("class_type") or "").strip()
    if not class_type or class_type.startswith("<"):
        return False, [f"requirement names no resolvable class ({class_type!r})"]
    declared_pack = str(requirement.get("pack") or "").strip()
    source_kind = str(requirement.get("source") or "").strip()
    if source_kind not in DECLARED_SCHEMA_SOURCES:
        return False, [
            f"{class_type!r} declares source {source_kind!r}; admissible "
            f"declared sources are {sorted(DECLARED_SCHEMA_SOURCES)}"
        ]
    strict_violation = _runtime_only_violation(source_kind)
    if runtime_only and strict_violation:
        return False, [f"{class_type}: {strict_violation}"]
    if not declared_pack:
        return False, [f"{class_type!r} declares no owning pack"]
    required_fields = [
        str(field_name)
        for field_name in (requirement.get("required_field_evidence") or ())
        if str(field_name)
    ]
    # RR1-FIX-REV: exact required input/widget/output ports per obligation,
    # each validated against the frozen captured schema before paid calls.
    required_inputs = [
        str(name)
        for name in (requirement.get("required_inputs") or ())
        if str(name)
    ]
    required_widgets = [
        str(name)
        for name in (requirement.get("required_widgets") or ())
        if str(name)
    ]
    required_outputs = [
        str(name)
        for name in (requirement.get("required_outputs") or ())
        if str(name)
    ]

    from vibecomfy.schema.ensure_capture import (
        STUB_SOURCE_KIND,
        _is_stub_index_row,
        _load_provenance,
        _provenance_pack_row,
    )
    from vibecomfy.schema.provider import (
        ObjectInfoIndexSchemaProvider,
        is_workflow_stub_schema,
    )

    failures: list[str] = []
    for root in _authoritative_cache_roots():
        if not (root / "index.json").is_file():
            continue
        try:
            provider = ObjectInfoIndexSchemaProvider(str(root))
            schema = provider.get(class_type)
        except Exception:  # noqa: BLE001 - unreadable cache is simply not evidence
            failures.append(f"cache root {root} could not be read")
            continue
        if schema is None:
            failures.append(f"{class_type!r} absent from cache root {root}")
            continue
        resolved_pack = str(getattr(schema, "pack", "") or "")
        if resolved_pack != declared_pack:
            failures.append(
                f"local cache attests pack {resolved_pack!r} for "
                f"{class_type!r}; requirement declares {declared_pack!r}"
            )
            continue
        attested, detail = _provenance_row(root, class_type)
        if not attested:
            failures.append(detail)
            continue
        # Batch D: read the pack FILE directly (never NodeSchema.source_provider).
        filename, entry = _pack_entry(root, class_type)
        prov_row = (
            _provenance_pack_row(_load_provenance(root), filename)
            if filename
            else None
        )
        # Ledger/file agreement: provenance ``source_kind`` must equal the
        # pack-JSON entry stamp whenever both exist; a stamped ledger row over
        # an unstamped entry fails closed.
        prov_kind = str((prov_row or {}).get("source_kind") or "").strip()
        entry_kind = _entry_source_kind(entry)
        if prov_kind and (not entry_kind or prov_kind != entry_kind):
            failures.append(
                f"provenance attests source_kind {prov_kind!r} for "
                f"{filename!r} but its pack-file entry carries "
                f"{entry_kind or '<none>'!r}; refusing the disagreement"
            )
            continue
        # Stub rejection belt-and-suspenders ON TOP of the index suffix filter.
        if (
            _is_stub_index_row(filename, entry)
            or entry_kind == STUB_SOURCE_KIND
            or is_workflow_stub_schema(schema)
        ):
            failures.append(
                f"resolved cache file {filename!r} is workflow-stub-shaped; "
                "stubs never attest schema evidence"
            )
            continue
        matched, mismatch = _declaration_matches_entry(source_kind, filename, entry)
        if not matched:
            failures.append(mismatch)
            continue
        schema_inputs = getattr(schema, "inputs", None) or {}
        missing_fields = [
            field_name for field_name in required_fields
            if field_name not in schema_inputs
        ]
        if missing_fields:
            failures.append(
                f"required field evidence missing from resolved schema: "
                f"{', '.join(missing_fields)}"
            )
            continue
        port_failures = _port_evidence_failures(
            schema,
            required_inputs=required_inputs,
            required_widgets=required_widgets,
            required_outputs=required_outputs,
        )
        if port_failures:
            failures.extend(port_failures)
            continue
        return True, []
    if not failures:
        failures.append("no local authoritative object_info cache root found")
    return False, failures


def _port_evidence_failures(
    schema: Any,
    *,
    required_inputs: list[str],
    required_widgets: list[str],
    required_outputs: list[str],
) -> list[str]:
    """Typed RR1-FIX-REV port checks against one resolved frozen schema."""
    failures: list[str] = []
    schema_inputs = getattr(schema, "inputs", None) or {}
    for name in required_inputs:
        if name not in schema_inputs:
            failures.append(
                f"required input port {name!r} missing from resolved schema"
            )
    from vibecomfy.porting.authoring_surface import input_spec_is_literal_widget

    for name in required_widgets:
        spec = schema_inputs.get(name)
        if spec is None:
            failures.append(
                f"required widget {name!r} missing from resolved schema inputs"
            )
        elif not input_spec_is_literal_widget(spec):
            failures.append(
                f"required widget {name!r} resolves to a socket, not a "
                "literal widget"
            )
    outputs = [
        item
        for item in (getattr(schema, "outputs", None) or ())
        if item is not None
    ]
    output_names = {
        str(getattr(item, "name", "") or "") or str(getattr(item, "type", "") or "")
        for item in outputs
    }
    output_types = {str(getattr(item, "type", "") or "") for item in outputs}
    for name in required_outputs:
        if name not in output_names and name not in output_types:
            failures.append(
                f"required output port {name!r} missing from resolved schema "
                f"(outputs: {sorted(n for n in output_names if n)})"
            )
    return failures


def preflight_scenario_obligations(
    manifest_path: Path | None = None,
    *,
    require_schema_resolution: bool | None = None,
    runtime_only: bool | None = None,
) -> dict[str, Any]:
    """Fail-closed preflight over scenario obligations.

    RR1-FIX-REV2: schema resolution and declaration enforcement are
    UNCONDITIONAL.  Every gated class must resolve through a LOCAL
    authoritative schema source before paid calls, AND every gated
    edit-required class without a declared requirement
    (unproven/undeclared) is a hard violation.  The
    ``require_schema_resolution`` parameter is retained as a no-op for
    caller compatibility only; neither it nor ``SCHEMA_RESOLUTION_ENV_VAR``
    can defer or disable the gate anymore.

    Batch D: on-demand tiers satisfy their own declarations (never the
    ``authoritative_object_info`` one).  ``runtime_only=True`` (or
    ``RUNTIME_ONLY_ENV_VAR=1``; an explicit ``False`` wins over the env
    var) additionally rejects on-demand declarations even where matched —
    paid-call lanes then demand runtime-family captures.  The payload adds
    ``resolution_tiers[scenario_id][class_type]`` with the CACHE stamp and
    provenance facts of each resolved capture.
    """
    del require_schema_resolution
    if runtime_only is None:
        runtime_only = os.environ.get(RUNTIME_ONLY_ENV_VAR) == "1"
    violations, warnings = validate_obligation_coverage(manifest_path)
    resolution_results: dict[str, dict[str, bool]] = {}
    resolution_tiers: dict[str, dict[str, dict[str, str]]] = {}
    path = manifest_path or __import__(
        "tests.live_agentic_harness.compare_pipeline_modes",
        fromlist=["DEFAULT_COMPARISON_MANIFEST"],
    ).DEFAULT_COMPARISON_MANIFEST
    manifest = _load_json(Path(path)) or {}
    for item in manifest.get("entries", []) or []:
        scenario_id = str(item.get("id") or "")
        obligation = load_scenario_obligation(scenario_id)
        if obligation is None:
            continue
        per_class: dict[str, bool] = {}
        per_tier: dict[str, dict[str, str]] = {}
        declared_names = {
            str(req.get("class_type"))
            for req in obligation.schema_evidence_requirements
            if not req.get("undeclared")
        }
        for req in obligation.schema_evidence_requirements:
            class_type = str(req.get("class_type") or "")
            if not class_type or class_type.startswith("<") or req.get(
                "undeclared"
            ):
                continue
            resolved, resolution_failures = _resolve_schema_locally(
                req, runtime_only=bool(runtime_only)
            )
            per_class[class_type] = resolved
            if resolved:
                tier = _resolution_tier(req)
                if tier:
                    per_tier[class_type] = tier
                continue
            detail = "; ".join(resolution_failures)
            declared_source = str(req.get("source") or "").strip()
            hint = ""
            if (
                declared_source in ON_DEMAND_SOURCE_KINDS
                and not (runtime_only and _runtime_only_violation(declared_source))
            ):
                hint = (
                    "; provision the on-demand tier with "
                    f"`vibecomfy schemas ensure --manifest {path}`"
                )
            violations.append(
                f"{scenario_id}: exact schema evidence for "
                f"{class_type!r} is not available from any local "
                "authoritative source; refusing paid calls "
                f"(fail-closed): {detail}{hint}"
            )
        # RRSYN-4 / RR1-FIX-REV / RR1-FIX-REV2: every gated, edit-required
        # class without a DECLARED requirement — i.e. every
        # UNPROVEN_PROVIDER_CLASSES entry and every undeclared marker row —
        # is a hard preflight violation here, never a warning-only bypass.
        if obligation.requires_edit:
            for class_type in obligation.custom_node_classes:
                if not _GATED_CLASS_RE.search(class_type):
                    continue
                if class_type.startswith("<"):
                    continue  # already a declaration-level violation above
                if class_type not in declared_names:
                    violations.append(
                        f"{scenario_id}: gated edit-required class "
                        f"{class_type!r} has no proven same-pack provider "
                        "evidence (unproven/undeclared); refusing paid "
                        "calls (fail-closed)"
                    )
        if per_class:
            resolution_results[scenario_id] = per_class
        if per_tier:
            resolution_tiers[scenario_id] = per_tier

    if violations:
        raise ScenarioObligationError(
            "scenario obligation preflight failed:\n- " + "\n- ".join(violations)
        )
    return {
        "ok": True,
        "schema_resolution_enforced": True,
        "warnings": warnings,
        "safe_refusal_policy": (
            "a safe refusal is useful behavior but never satisfies an "
            "edit-requiring final scenario"
        ),
        "resolution": resolution_results,
        "resolution_tiers": resolution_tiers,
        "violations": [],
    }


__all__ = [
    "ADMISSIBLE_INFRA_FAILURES",
    "DECLARED_SCHEMA_SOURCES",
    "ON_DEMAND_SOURCE_KINDS",
    "RUNTIME_ONLY_ENV_VAR",
    "SCHEMA_EVIDENCE_REQUIREMENTS",
    "SCHEMA_RESOLUTION_ENV_VAR",
    "STRUCTURAL_MEMBER_KINDS",
    "TERMINAL_NO_CANDIDATE_REASONS",
    "ScenarioObligation",
    "ScenarioObligationError",
    "UNPROVEN_PROVIDER_CLASSES",
    "load_scenario_obligation",
    "preflight_scenario_obligations",
    "validate_obligation_coverage",
    "descriptor_contract_violations",
    "expected_no_candidate_contract",
]
