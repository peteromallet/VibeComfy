from __future__ import annotations

import json
from pathlib import Path
from typing import Any, Callable, Mapping

from vibecomfy.porting.reorganise import (
    LayoutCompileOptions,
    ReorganisePreviewOptions,
    apply_layout_candidate_patch_to_ui,
    preview_reorganise_workflow,
)

from .contracts import (
    ApplyCandidate,
    ApplyEligibility,
    ArtifactRef,
    StageResult,
    TurnContext,
    TurnIdentity,
    TurnOutcome,
    build_legacy_agent_edit_v1,
    derive_apply_eligibility,
    public_outcome_from_turn_outcome,
    success_envelope,
    turn_envelope,
)
from .gates import update_state_match_gate
from .session import payload_hash, structural_graph_hash

_SKILL_TRIGGER = "/reorganise_comfy_workflow"
_ROUTE_ALIASES = {
    "reorganise",
    "reorganize",
    "reorganise_comfy_workflow",
    "reorganize_comfy_workflow",
    "/reorganise_comfy_workflow",
    "/reorganize_comfy_workflow",
}

_PLAN_ARTIFACT = "reorganisation_plan.json"
_REPORT_ARTIFACT = "reorganisation_report.md"
_METRICS_ARTIFACT = "reorganisation_metrics.json"
_EVIDENCE_ARTIFACT = "structural_noop_evidence.json"


def is_reorganise_agent_request(task: str, route: str | None) -> bool:
    if isinstance(route, str) and route.strip().casefold() in _ROUTE_ALIASES:
        return True
    first_token = task.strip().split(maxsplit=1)[0].casefold() if task.strip() else ""
    return first_token in _ROUTE_ALIASES or first_token == _SKILL_TRIGGER


def build_reorganise_agent_response(
    state: Any,
    context: TurnContext,
    *,
    model_plan_provider: Callable[[Any], Any] | None = None,
) -> dict[str, Any]:
    """Run explicit reorganise preview inside an already allocated edit turn."""
    write_json_artifact = _artifact_writer()
    request_ref = write_json_artifact(state.request_path, state.request_payload)
    original_ui_ref = write_json_artifact(state.original_ui_path, state.graph)

    update_state_match_gate(
        context,
        baseline_graph_hash=None,
        client_graph_hash=state.submit_structural_graph_hash,
        client_graph_hash_label="submit_structural_graph_hash",
    )

    options = ReorganisePreviewOptions(
        compile_options=_compile_options_from_payload(state.request_payload)
    )
    plan_payload = _explicit_plan_payload(state.request_payload)
    semantic_provider = model_plan_provider if plan_payload is None else None
    result = preview_reorganise_workflow(
        state.graph,
        sidecar_envelope=_sidecar_from_payload(state.request_payload),
        plan_payload=plan_payload,
        semantic_plan_provider=semantic_provider,
        options=options,
    )

    state.projection_text = result.projection.text
    state.projection_path.write_text(result.projection.text, encoding="utf-8")

    plan_path = state.turn_dir / _PLAN_ARTIFACT
    report_path = state.turn_dir / _REPORT_ARTIFACT
    metrics_path = state.turn_dir / _METRICS_ARTIFACT
    evidence_path = state.turn_dir / _EVIDENCE_ARTIFACT

    write_json_artifact(plan_path, _plan_payload(result))
    write_json_artifact(metrics_path, _metrics_payload(result))

    patch_apply = None
    patch_apply_error: dict[str, Any] | None = None
    candidate_payload: dict[str, Any] | None = None
    has_candidate = False
    if result.ok and result.candidate_patch is not None:
        try:
            patch_apply = apply_layout_candidate_patch_to_ui(state.graph, result.candidate_patch)
        except Exception as exc:  # noqa: BLE001 - layout apply must fail closed.
            patch_apply_error = {
                "code": "layout_candidate_patch_apply_failed",
                "severity": "error",
                "message": "Layout candidate patch could not be applied without structural drift.",
                "detail": {"exception_type": type(exc).__name__},
            }
            state.ui_payload = None
        else:
            state.ui_payload = dict(patch_apply.ui_json)
            has_candidate = _layout_candidate_has_effect(
                original_ui=state.graph,
                candidate_ui=state.ui_payload,
                result=result,
                patch_apply=patch_apply,
            )
            if has_candidate:
                write_json_artifact(state.candidate_ui_path, patch_apply.ui_json)
            else:
                state.ui_payload = None
    else:
        state.ui_payload = None

    evidence_payload = _evidence_payload(
        result,
        patch_apply,
        original_ui=state.graph,
        patch_apply_error=patch_apply_error,
        has_candidate=has_candidate,
    )
    write_json_artifact(evidence_path, evidence_payload)
    report_text = _render_report(result, candidate_written=has_candidate)
    report_path.write_text(report_text, encoding="utf-8")

    artifact_paths: dict[str, str] = {
        "request": str(state.request_path),
        "original_ui": str(state.original_ui_path),
        "projection": str(state.projection_path),
        "reorganisation_plan": str(plan_path),
        "reorganisation_report": str(report_path),
        "reorganisation_metrics": str(metrics_path),
        "structural_noop_evidence": str(evidence_path),
    }
    if has_candidate:
        artifact_paths["candidate_ui"] = str(state.candidate_ui_path)
    if state.model_request_path.exists():
        artifact_paths["model_request"] = str(state.model_request_path)
    if state.model_response_path.exists():
        artifact_paths["model_response"] = str(state.model_response_path)
    state.artifacts = artifact_paths

    _record_reorganise_stage_results(
        context,
        result=result,
        patch_apply=patch_apply,
        patch_apply_error=patch_apply_error,
        has_candidate=has_candidate,
        artifacts=(
            request_ref,
            original_ui_ref,
            _artifact_ref(state.projection_path),
            _artifact_ref(plan_path),
            _artifact_ref(metrics_path),
            _artifact_ref(evidence_path),
            _artifact_ref(report_path),
            *(
                (_artifact_ref(state.candidate_ui_path),)
                if has_candidate and state.candidate_ui_path.exists()
                else ()
            ),
        ),
    )

    state.report = {
        "kind": "reorganise",
        "status": "ok" if has_candidate else "failed",
        "report": report_text,
        "apply_data": result.apply_data.to_json(),
        "metrics": _metrics_payload(result),
        "evidence": evidence_payload,
    }

    eligibility = derive_apply_eligibility(
        context,
        has_candidate=has_candidate,
        candidate_state="candidate" if has_candidate else None,
    )
    if not has_candidate:
        eligibility = ApplyEligibility(
            applyable=False,
            reason="no_candidate",
            message="No reorganise candidate is available to apply.",
        )

    turn_identity = TurnIdentity.from_context(context)
    if has_candidate and state.ui_payload is not None:
        compatibility_fields = _compatibility_fields(state)
        candidate_payload = ApplyCandidate(
            state="candidate",
            graph=state.ui_payload,
            graph_hash=compatibility_fields["candidate_graph_hash"],
            structural_graph_hash=compatibility_fields["candidate_structural_graph_hash"],
            baseline_graph_hash=compatibility_fields["baseline_graph_hash"],
            submit_graph_hash=compatibility_fields["submit_graph_hash"],
            submit_structural_graph_hash=compatibility_fields["submit_structural_graph_hash"],
            turn_identity=turn_identity,
        ).to_dict()
        internal_outcome = TurnOutcome.edit()
        message = "Reorganised layout candidate ready to review."
    else:
        compatibility_fields = _compatibility_fields(state)
        internal_outcome = TurnOutcome.noop(reason="Reorganise preview failed.")
        message = "Reorganise preview failed; no candidate was produced."

    public_outcome = public_outcome_from_turn_outcome(
        internal_outcome,
        response={"candidate": candidate_payload} if candidate_payload is not None else None,
    )
    response = success_envelope(
        context,
        message=message,
        graph=state.ui_payload if has_candidate else None,
        report=state.report,
        artifacts=_relative_artifact_paths(state),
        apply_eligibility=eligibility,
        canvas_apply_allowed=context.canvas_apply_allowed if has_candidate else False,
        queue_allowed=context.queue_allowed if has_candidate else False,
    )
    response.update(
        turn_envelope(
            message=message,
            outcome=public_outcome,
            candidate=candidate_payload,
            eligibility=eligibility,
            debug={
                "route": "reorganise",
                "turn_identity": turn_identity.to_dict(),
                "stage_snapshots": [
                    snapshot.to_dict()
                    for snapshot in _stage_snapshots(context.stage_results.values())
                ],
                "reorganise": {
                    "plan_source": result.plan_source,
                    "ok": result.ok,
                    "has_candidate": has_candidate,
                    "layout_only_structural_noop": evidence_payload[
                        "layout_only_structural_noop"
                    ],
                },
            },
        )
    )
    response.update(compatibility_fields)
    response["route"] = "reorganise"
    response["internal_outcome"] = internal_outcome.to_dict()
    response["change_details"] = {
        "route": "reorganise",
        "layout_only": True,
        "structural_noop_evidence": evidence_payload,
    }
    if not has_candidate:
        response["no_candidate_reason"] = "reorganise_preview_failed"
        response["graph_unchanged"] = True
    return build_legacy_agent_edit_v1(response)


def prepare_post_edit_reorganise_candidate(
    state: Any,
    context: TurnContext,
    *,
    source_ui: Mapping[str, Any],
    decision: Any,
) -> dict[str, Any]:
    """Prepare an optional layout candidate for an already-successful edit turn."""
    write_json_artifact = _artifact_writer()
    options = ReorganisePreviewOptions(
        compile_options=_compile_options_from_payload(state.request_payload)
    )
    result = preview_reorganise_workflow(
        source_ui,
        sidecar_envelope=_sidecar_from_payload(state.request_payload),
        plan_payload=None,
        semantic_plan_provider=None,
        options=options,
    )

    projection_path = state.turn_dir / "post_edit_reorganisation_projection.txt"
    plan_path = state.turn_dir / "post_edit_reorganisation_plan.json"
    report_path = state.turn_dir / "post_edit_reorganisation_report.md"
    metrics_path = state.turn_dir / "post_edit_reorganisation_metrics.json"
    evidence_path = state.turn_dir / "post_edit_structural_noop_evidence.json"

    projection_path.write_text(result.projection.text, encoding="utf-8")
    write_json_artifact(plan_path, _plan_payload(result))
    write_json_artifact(metrics_path, _metrics_payload(result))

    patch_apply = None
    patch_apply_error: dict[str, Any] | None = None
    has_candidate = False
    if result.ok and result.candidate_patch is not None:
        try:
            patch_apply = apply_layout_candidate_patch_to_ui(source_ui, result.candidate_patch)
        except Exception as exc:  # noqa: BLE001 - optional layout candidate must fail closed.
            patch_apply_error = {
                "code": "layout_candidate_patch_apply_failed",
                "severity": "warning",
                "message": "Optional layout candidate could not be applied without structural drift.",
                "detail": {"exception_type": type(exc).__name__},
            }
        else:
            candidate_ui = dict(patch_apply.ui_json)
            has_candidate = _layout_candidate_has_effect(
                original_ui=source_ui,
                candidate_ui=candidate_ui,
                result=result,
                patch_apply=patch_apply,
            )
            if has_candidate:
                state.ui_payload = candidate_ui
                write_json_artifact(state.candidate_ui_path, candidate_ui)

    evidence_payload = _evidence_payload(
        result,
        patch_apply,
        original_ui=source_ui,
        patch_apply_error=patch_apply_error,
        has_candidate=has_candidate,
    )
    write_json_artifact(evidence_path, evidence_payload)
    report_path.write_text(_render_report(result, candidate_written=has_candidate), encoding="utf-8")

    artifact_paths = {
        "post_edit_reorganisation_projection": str(projection_path),
        "post_edit_reorganisation_plan": str(plan_path),
        "post_edit_reorganisation_report": str(report_path),
        "post_edit_reorganisation_metrics": str(metrics_path),
        "post_edit_structural_noop_evidence": str(evidence_path),
    }
    if has_candidate:
        artifact_paths["candidate_ui"] = str(state.candidate_ui_path)
    state.artifacts = {**(state.artifacts or {}), **artifact_paths}

    artifacts = (
        _artifact_ref(projection_path),
        _artifact_ref(plan_path),
        _artifact_ref(metrics_path),
        _artifact_ref(evidence_path),
        _artifact_ref(report_path),
        *((_artifact_ref(state.candidate_ui_path),) if has_candidate else ()),
    )
    context.record_stage(
        StageResult(
            stage="post_edit_reorganise",
            ok=has_candidate,
            blocking=False,
            artifacts=artifacts,
            issues=tuple(_diagnostic_issues(result))
            + ((dict(patch_apply_error),) if patch_apply_error is not None else ()),
            value={
                "candidate_available": has_candidate,
                "functional_candidate_graph_hash": payload_hash(source_ui),
                "reorganised_candidate_graph_hash": (
                    payload_hash(state.ui_payload) if has_candidate else None
                ),
                "layout_only_structural_noop": evidence_payload["layout_only_structural_noop"],
                "full_ui_payload_hash_changed": evidence_payload["full_ui_payload_hash_changed"],
                "layout_evidence_changed": evidence_payload["layout_evidence_changed"],
            },
        )
    )

    decision_payload = (
        decision.to_json() if hasattr(decision, "to_json") else {"result": "prepare_candidate"}
    )
    return {
        **_json_safe(decision_payload),
        "advisory": False,
        "suggested_command": _SKILL_TRIGGER,
        "candidate_prepared": has_candidate,
        "functional_candidate_graph_hash": payload_hash(source_ui),
        "reorganised_candidate_graph_hash": (
            payload_hash(state.ui_payload) if has_candidate else None
        ),
        "message": (
            "Prepared a layout-only reorganise candidate for the edited workflow."
            if has_candidate
            else "The edited workflow remains the candidate; optional layout reorganisation did not produce a separate candidate."
        ),
        "evidence": _json_safe(evidence_payload),
        "artifacts": _json_safe(artifact_paths),
    }


def _compile_options_from_payload(payload: Mapping[str, Any]) -> LayoutCompileOptions:
    spacing = payload.get("spacing") if isinstance(payload.get("spacing"), str) else "balanced"
    existing_group_policy = (
        payload.get("existing_group_policy")
        if isinstance(payload.get("existing_group_policy"), str)
        else "semantic_preserve"
    )
    force_regroup = bool(payload.get("force_regroup"))
    if force_regroup:
        existing_group_policy = "force_regroup"
    return LayoutCompileOptions(
        spacing_preset=spacing,
        existing_group_policy=existing_group_policy,
        force_regroup=force_regroup,
    )


def _explicit_plan_payload(payload: Mapping[str, Any]) -> Any | None:
    for key in ("layout_plan", "reorganise_plan", "reorganisation_plan"):
        if key in payload:
            return payload[key]
    return None


def _sidecar_from_payload(payload: Mapping[str, Any]) -> Mapping[str, Any] | None:
    sidecar = payload.get("layout_sidecar")
    return sidecar if isinstance(sidecar, Mapping) else None


def _plan_payload(result: Any) -> dict[str, Any]:
    return {
        "status": "ok" if result.ok else "failed",
        "plan_source": result.plan_source,
        "plan": result.plan.to_json() if result.plan is not None else None,
        "parse_diagnostics": [
            item.to_json() if hasattr(item, "to_json") else item
            for item in result.parse_diagnostics
        ],
        "validation_report": (
            result.validation_report.to_json()
            if result.validation_report is not None
            else None
        ),
        "provider_diagnostics": [
            diagnostic.to_json() for diagnostic in result.provider_diagnostics
        ],
        "compile_diagnostics": [
            diagnostic.to_json() for diagnostic in result.compile_diagnostics
        ],
        "second_stage_results": [
            second_stage.to_json() for second_stage in result.second_stage_results
        ],
    }


def _metrics_payload(result: Any) -> dict[str, Any]:
    payload: dict[str, Any] = {
        "assessment": result.assessment.to_json(),
        "graph_summary": result.graph_summary.to_json(),
        "projection": {
            "token_estimate": result.projection.token_estimate,
            "scope_count": result.projection.scope_count,
            "canonical_ref_count": result.projection.canonical_ref_count,
            "summarized": result.projection.summarized,
            "truncated": result.projection.truncated,
        },
        "compile": None,
    }
    if result.compile_result is not None and result.compile_result.ok:
        payload["compile"] = {
            "ok": result.compile_result.ok,
            "options": result.compile_result.options.to_json(),
            "report": result.compile_result.report.to_json(),
            "node_layout_count": len(result.compile_result.node_layouts),
            "group_layout_count": len(result.compile_result.group_layouts),
        }
    return payload


def _evidence_payload(
    result: Any,
    patch_apply: Any | None,
    *,
    original_ui: Mapping[str, Any],
    patch_apply_error: Mapping[str, Any] | None = None,
    has_candidate: bool = False,
) -> dict[str, Any]:
    return {
        "apply_data": result.apply_data.to_json(),
        "patch_apply": (
            patch_apply.to_json(include_ui_json=False) if patch_apply is not None else None
        ),
        "patch_apply_error": dict(patch_apply_error) if patch_apply_error is not None else None,
        "candidate_available": bool(has_candidate),
        "full_ui_payload_hash_changed": (
            bool(payload_hash(original_ui) != payload_hash(patch_apply.ui_json))
            if patch_apply is not None
            else False
        ),
        "layout_evidence_changed": _layout_evidence_changed(result, patch_apply),
        "layout_only_structural_noop": result.apply_data.layout_only_structural_noop
        and (patch_apply.layout_only_structural_noop if patch_apply is not None else False),
    }


def _render_report(result: Any, *, candidate_written: bool) -> str:
    assessment = result.assessment.to_json()
    lines = [
        "# Reorganisation Report",
        "",
        f"- Status: {'ok' if candidate_written else 'failed'}",
        "- Source: agent turn",
        f"- Plan source: {result.plan_source}",
        f"- Candidate: {'candidate.ui.json' if candidate_written else 'not written'}",
        "- Metrics: reorganisation_metrics.json",
        "- Structural no-op evidence: structural_noop_evidence.json",
        f"- Layout-only structural no-op: {str(result.apply_data.layout_only_structural_noop).lower()}",
        "",
        "## Assessment",
        "",
        f"- Verdict: {assessment['verdict']}",
        f"- Issues: {len(assessment['issues'])}",
        f"- Diagnostics: {len(assessment['diagnostics'])}",
    ]
    if result.compile_diagnostics:
        lines.extend(["", "## Compile Diagnostics", ""])
        for diagnostic in result.compile_diagnostics[:20]:
            lines.append(f"- {diagnostic.severity}: {diagnostic.code} - {diagnostic.message}")
    return "\n".join(lines).rstrip() + "\n"


def _record_reorganise_stage_results(
    context: TurnContext,
    *,
    result: Any,
    patch_apply: Any | None,
    patch_apply_error: Mapping[str, Any] | None = None,
    has_candidate: bool = False,
    artifacts: tuple[ArtifactRef, ...],
) -> None:
    context.record_stage(
        StageResult(
            stage="ingest",
            ok=True,
            blocking=False,
            artifacts=tuple(artifacts[:2]),
        )
    )
    parse_ok = (
        result.plan is not None
        and not result.provider_diagnostics
        and not result.parse_diagnostics
    )
    plan_ok = result.validation_report is not None and result.validation_report.ok
    second_stage_ok = all(second_stage.ok for second_stage in result.second_stage_results)
    compile_ok = bool(result.compile_result is not None and result.compile_result.ok and second_stage_ok)
    context.record_stage(
        StageResult(
            stage="plan",
            ok=plan_ok,
            blocking=not plan_ok,
            artifacts=tuple(artifacts[2:6]),
            issues=tuple(_diagnostic_issues(result)),
            gate_updates={"plan_validate_ok": plan_ok},
        )
    )
    structural_noop = bool(
        patch_apply is not None and patch_apply.layout_only_structural_noop
    )
    emit_ok = bool(compile_ok and structural_noop and has_candidate and patch_apply_error is None)
    issues = tuple(_diagnostic_issues(result))
    if patch_apply_error is not None:
        issues = (*issues, dict(patch_apply_error))
    context.record_stage(
        StageResult(
            stage="emit",
            ok=emit_ok,
            blocking=not emit_ok,
            artifacts=tuple(artifacts[6:]),
            issues=issues,
            value={
                "candidate_available": has_candidate,
                "compile_ok": compile_ok,
                "layout_only_structural_noop": structural_noop,
                "full_ui_payload_hash_changed": (
                    bool(payload_hash(result.loaded.ui_json) != payload_hash(patch_apply.ui_json))
                    if patch_apply is not None
                    else False
                ),
                "layout_evidence_changed": _layout_evidence_changed(result, patch_apply),
            },
            gate_updates={
                "python_load_ok": parse_ok,
                "lower_ok": plan_ok,
                "ir_validate_ok": compile_ok,
                "ui_emit_ok": emit_ok,
                "ui_fidelity_ok": bool(structural_noop and has_candidate),
                "ui_load_safe_ok": emit_ok,
            },
        )
    )


def _layout_candidate_has_effect(
    *,
    original_ui: Mapping[str, Any],
    candidate_ui: Mapping[str, Any],
    result: Any,
    patch_apply: Any,
) -> bool:
    if not bool(result.apply_data.layout_only_structural_noop):
        return False
    if not bool(patch_apply.layout_only_structural_noop):
        return False
    if payload_hash(original_ui) != payload_hash(candidate_ui):
        return True
    return _layout_evidence_changed(result, patch_apply)


def _layout_evidence_changed(result: Any, patch_apply: Any | None) -> bool:
    if patch_apply is None:
        return False
    applied_entry_keys = tuple(getattr(patch_apply, "applied_entry_keys", ()) or ())
    applied_group_scopes = tuple(getattr(patch_apply, "applied_group_scopes", ()) or ())
    if applied_entry_keys or applied_group_scopes:
        return True
    apply_data = getattr(result, "apply_data", None)
    candidate_patch_sha256 = (
        getattr(apply_data, "candidate_patch_sha256", None)
        if apply_data is not None
        else None
    )
    return bool(candidate_patch_sha256)


def _diagnostic_issues(result: Any) -> list[dict[str, Any]]:
    issues: list[dict[str, Any]] = []
    for item in (
        *result.provider_diagnostics,
        *result.parse_diagnostics,
        *result.compile_diagnostics,
    ):
        if hasattr(item, "to_json"):
            payload = item.to_json()
            if isinstance(payload, dict):
                issues.append(payload)
    if result.validation_report is not None:
        issues.extend(
            item
            for item in result.validation_report.to_json().get("diagnostics", [])
            if isinstance(item, dict)
        )
    return issues


def _compatibility_fields(state: Any) -> dict[str, Any]:
    candidate_graph_hash = payload_hash(state.ui_payload) if state.ui_payload is not None else None
    candidate_structural_graph_hash = (
        structural_graph_hash(state.ui_payload) if state.ui_payload is not None else None
    )
    return {
        "baseline_graph_hash": state.baseline_graph_hash,
        "submit_graph_hash": state.submit_graph_hash,
        "submit_structural_graph_hash": state.submit_structural_graph_hash,
        "submitted_client_graph_hash": state.submitted_client_graph_hash,
        "submitted_client_structural_graph_hash": state.submitted_client_structural_graph_hash,
        "candidate_graph_hash": candidate_graph_hash,
        "candidate_structural_graph_hash": candidate_structural_graph_hash,
        "client_graph_hash": state.submitted_client_graph_hash,
    }


def _relative_artifact_paths(state: Any) -> dict[str, str]:
    artifacts: dict[str, str] = {}
    for name, raw_path in (state.artifacts or {}).items():
        path = Path(raw_path)
        try:
            artifacts[name] = path.relative_to(state.turn_dir).as_posix()
        except ValueError:
            artifacts[name] = path.name
    return artifacts


def _json_safe(value: Any) -> Any:
    return json.loads(json.dumps(value, sort_keys=True, default=str))


def _stage_snapshots(results: Any) -> list[Any]:
    from .contracts import StageSnapshot

    return [StageSnapshot.from_stage_result(result) for result in results]


def _artifact_writer() -> Callable[[Path, Any], ArtifactRef]:
    from .audit import write_json_artifact

    return write_json_artifact


def _artifact_ref(path: Path) -> ArtifactRef:
    from .audit import artifact_ref_for_path

    return artifact_ref_for_path(path)


def write_model_request(path: Path, payload: Mapping[str, Any]) -> None:
    path.write_text(json.dumps(payload, indent=2, sort_keys=True) + "\n", encoding="utf-8")
