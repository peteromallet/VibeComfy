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
any violation. ``run_comparison`` — the paid-call lane — runs the declaration
preflight always AND the schema-resolution preflight unconditionally
(G5-B4-MUST-006): ``VIBECOMFY_OBLIGATION_SCHEMA_CHECK`` cannot defer or
disable it there. Discovery happens before paid calls, never after. A safe
refusal is useful behavior but never satisfies a scenario whose obligations
require an edit; descriptors granting ``allow_safe_refusal`` on edit scenarios
are a coverage conflict, and an accepted refusal grades ``undetermined``.
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
        },
        {
            "class_type": "IndexTTSEmotionOptionsNode",
            "pack": "ComfyUI-IndexTTS",
            "source": "authoritative_object_info",
            "required_field_evidence": ("emotion_control",),
        },
    ),
    "multi-video-based-character-replacement-using": (
        {
            "class_type": "LayerMask: LoadSegmentAnythingModels",
            "pack": "ComfyUI_LayerStyle_Advance",
            "source": "authoritative_object_info",
        },
        {
            "class_type": "LayerMask: SegmentAnythingUltra V3",
            "pack": "ComfyUI_LayerStyle_Advance",
            "source": "authoritative_object_info",
        },
    ),
}

#: Class-type families that trigger the exact-schema-evidence gate wherever
#: they appear in a scenario's source workflow.
_GATED_CLASS_RE = re.compile(r"IndexTTS|LayerMask|SegmentAnything", re.IGNORECASE)


#: Structured ``no_candidate_reason`` labels the executor emits only for an
#: honest nothing-authorable terminal state (mirrors assessor.GROUNDED_NO_CANDIDATE_REASONS).
GROUNDED_NO_CANDIDATE_REASONS = frozenset({"no_changes", "no_graph"})


def expected_no_candidate_contract(
    descriptor: Mapping[str, Any],
) -> Mapping[str, Any] | None:
    """Return the declared grounded no-candidate contract, or ``None``.

    DEEP-AUDIT-FIX-4-REVISION finding 001: a scenario declares
    expected-no-candidate ONLY through a non-empty
    ``assessment.expected_no_candidate_reason``, and that declaration opts it
    into the assessor's grounded no-candidate adjudication.  ``apply=false``
    plus ``assessment.expect_graph_changed=false`` alone are NOT a no-candidate
    designation — they are two bare flags and derive nothing here.

    The returned contract carries the declared absence premise (``reason``),
    the refusal outcome kinds the envelope must use (``refusal_kinds``, read
    from ``assessment.allow_safe_refusal_outcome_kinds``), and the optional
    declared-absent class tokens (``absent_classes``, from
    ``assessment.expected_no_candidate_absent_classes``) that structured
    evidence must cite for named-class absence premises.
    """
    assessment = (
        descriptor.get("assessment")
        if isinstance(descriptor.get("assessment"), Mapping)
        else {}
    )
    reason = assessment.get("expected_no_candidate_reason")
    if not isinstance(reason, str) or not reason.strip():
        return None
    kinds_raw = assessment.get("allow_safe_refusal_outcome_kinds")
    if isinstance(kinds_raw, str):
        refusal_kinds = (kinds_raw,) if kinds_raw.strip() else ()
    elif isinstance(kinds_raw, list):
        refusal_kinds = tuple(
            kind for kind in kinds_raw if isinstance(kind, str) and kind.strip()
        )
    else:
        refusal_kinds = ()
    absent_raw = assessment.get("expected_no_candidate_absent_classes")
    if isinstance(absent_raw, str):
        absent_classes = (absent_raw,) if absent_raw.strip() else ()
    elif isinstance(absent_raw, list):
        absent_classes = tuple(
            token.strip()
            for token in absent_raw
            if isinstance(token, str) and token.strip()
        )
    else:
        absent_classes = ()
    return {
        "reason": reason.strip(),
        "refusal_kinds": refusal_kinds,
        "absent_classes": absent_classes,
    }


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
        # DEEP-AUDIT-FIX-4-REVISION finding 001: "none" here derives from the
        # DECLARED no-candidate refusal contract (adjudicated by the assessor
        # against structured absence evidence), not from two bare false flags.
        expected_change = "none"
    else:
        expected_change = "none"

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

        # DEEP-AUDIT-FIX-4-REVISION finding 001: the declared no-candidate
        # contract must be coherent. It can never coexist with an edit
        # expectation, and without declared refusal kinds the assessor's
        # grounded adjudication would fail closed on every leg.
        if obligation.expected_no_candidate is not None:
            if obligation.requires_edit:
                violations.append(
                    f"{scenario_id}: expected_no_candidate contract contradicts "
                    "an edit expectation (apply/expect_graph_changed true); an "
                    "annotation cannot loosen an edit obligation"
                )
            if not obligation.expected_no_candidate["refusal_kinds"]:
                violations.append(
                    f"{scenario_id}: expected_no_candidate contract declares no "
                    "allow_safe_refusal_outcome_kinds; grounded no-candidate "
                    "adjudication would fail closed on every leg"
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


def _resolve_schema_locally(
    requirement: Mapping[str, Any],
) -> tuple[bool, list[str]]:
    """LOCAL-ONLY authoritative resolution of one declared schema evidence
    requirement. Never touches the network.

    Proves (G5-B4-MUST-006), beyond bare ``provider.get(...)`` existence:
    * the declaring ``source`` kind is ``authoritative_object_info``;
    * the class resolves from a local object_info cache ROOT whose
      provenance attests the DECLARED owning ``pack``;
    * the backing cache file carries real provenance (a repo or a locked
      commit — never an unattested/stub capture);
    * every ``required_field_evidence`` field name is visible in the
      resolved schema inputs (e.g. ``emotion_control``).
    """
    class_type = str(requirement.get("class_type") or "").strip()
    if not class_type or class_type.startswith("<"):
        return False, [f"requirement names no resolvable class ({class_type!r})"]
    declared_pack = str(requirement.get("pack") or "").strip()
    source_kind = str(requirement.get("source") or "").strip()
    if source_kind != "authoritative_object_info":
        return False, [
            f"{class_type!r} declares source {source_kind!r}; only "
            "'authoritative_object_info' is authoritative"
        ]
    if not declared_pack:
        return False, [f"{class_type!r} declares no owning pack"]
    required_fields = [
        str(field_name)
        for field_name in (requirement.get("required_field_evidence") or ())
        if str(field_name)
    ]

    from vibecomfy.schema.provider import ObjectInfoIndexSchemaProvider

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
        return True, []
    if not failures:
        failures.append("no local authoritative object_info cache root found")
    return False, failures


def preflight_scenario_obligations(
    manifest_path: Path | None = None,
    *,
    require_schema_resolution: bool | None = None,
) -> dict[str, Any]:
    """Fail-closed preflight over scenario obligations.

    ``require_schema_resolution``: None defers to
    ``VIBECOMFY_OBLIGATION_SCHEMA_CHECK`` (truthy enables). When enabled, every
    gated class must resolve through a LOCAL authoritative schema source before
    paid calls; otherwise the declaration-level check still runs and the
    result records the deferral explicitly.
    """
    if require_schema_resolution is None:
        raw = os.environ.get(SCHEMA_RESOLUTION_ENV_VAR, "")
        require_schema_resolution = raw.strip().lower() in {"1", "true", "yes", "on"}
    violations, warnings = validate_obligation_coverage(manifest_path)

    resolution_results: dict[str, dict[str, bool]] = {}
    if require_schema_resolution:
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
            for req in obligation.schema_evidence_requirements:
                class_type = str(req.get("class_type") or "")
                if not class_type or class_type.startswith("<") or req.get(
                    "undeclared"
                ):
                    continue
                resolved, resolution_failures = _resolve_schema_locally(req)
                per_class[class_type] = resolved
                if not resolved:
                    violations.append(
                        f"{scenario_id}: exact schema evidence for "
                        f"{class_type!r} is not available from any local "
                        "authoritative source; refusing paid calls "
                        "(fail-closed): " + "; ".join(resolution_failures)
                    )
            if per_class:
                resolution_results[scenario_id] = per_class

    if violations:
        raise ScenarioObligationError(
            "scenario obligation preflight failed:\n- " + "\n- ".join(violations)
        )
    return {
        "ok": True,
        "schema_resolution_enforced": bool(require_schema_resolution),
        "warnings": warnings,
        "safe_refusal_policy": (
            "a safe refusal is useful behavior but never satisfies an "
            "edit-requiring final scenario"
        ),
        "resolution": resolution_results,
        "violations": [],
    }


__all__ = [
    "ADMISSIBLE_INFRA_FAILURES",
    "SCHEMA_EVIDENCE_REQUIREMENTS",
    "SCHEMA_RESOLUTION_ENV_VAR",
    "ScenarioObligation",
    "ScenarioObligationError",
    "load_scenario_obligation",
    "preflight_scenario_obligations",
    "validate_obligation_coverage",
    "GROUNDED_NO_CANDIDATE_REASONS",
    "expected_no_candidate_contract",
]
