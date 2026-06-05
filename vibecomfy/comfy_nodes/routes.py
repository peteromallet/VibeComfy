from __future__ import annotations

import dataclasses
import json
from pathlib import Path
from typing import Any

from .agent_contracts import (
    FailureKind,
    TurnContext,
    apply_eligibility_payload,
    classify_failure,
    derive_apply_eligibility,
    failure_envelope,
)
from .agent_edit import _SESSION_ROOT, _safe_session_id, handle_agent_edit
from .agent_provider import readiness, handle_credential_submission
from .agent_session import accept_turn, payload_hash, rebaseline_session, reject_turn, session_dir_for, turn_dir_for
from .agent_audit import artifact_ref_for_path, write_audit


def _handle_roundtrip(
    payload: dict[str, Any], *, schema_provider: Any = None
) -> dict[str, Any]:
    """Torch-free core: convert UI graph + emit, return enriched graph + change report.

    All engine imports are lazy so this function is importable without ComfyUI or torch.
    Call from tests directly; the aiohttp wrapper below delegates to this.
    """
    from vibecomfy.ingest.normalize import convert_to_vibe_format  # noqa: PLC0415
    from vibecomfy.porting.layout import evaluate_felt_delta  # noqa: PLC0415
    from vibecomfy.porting.ui_emitter import emit_ui_json  # noqa: PLC0415
    from vibecomfy.schema import get_schema_provider  # noqa: PLC0415

    try:
        if schema_provider is None:
            schema_provider = get_schema_provider("local")
        recovery_report: list = []
        change_report_out: list = []
        wf = convert_to_vibe_format(payload["graph"])
        emitted_ui = emit_ui_json(
            wf,
            schema_provider=schema_provider,
            recovery_report=recovery_report,
            change_report_out=change_report_out,
            guard_original_ui=payload["graph"],
        )
        change_dict = dataclasses.asdict(change_report_out[0]) if change_report_out else {}
        reroute_uids = frozenset(
            (node.uid or node_id)
            for node_id, node in wf.nodes.items()
            if node.class_type == "Reroute"
        )
        felt_report = (
            evaluate_felt_delta(
                None,
                emitted_ui,
                change_report_out[0],
                reroute_uids=reroute_uids,
            )
            if change_report_out
            else None
        )
        return {
            "graph": emitted_ui,
            "report": {
                "change": change_dict,
                "recovery": recovery_report,
                "felt": dataclasses.asdict(felt_report) if felt_report is not None else {},
            },
            "version": 1,
        }
    except Exception as exc:
        return {"error": str(exc), "kind": type(exc).__name__}


def _idempotency_key(payload: dict[str, Any]) -> str | None:
    value = payload.get("idempotency_key")
    return value if isinstance(value, str) and value else None


def _root(path: Any = None) -> Path:
    return Path(path) if path is not None else _SESSION_ROOT


def _handle_agent_edit_action(
    payload: Any,
    *,
    action: str,
    session_root: Any = None,
) -> dict[str, Any]:
    if not isinstance(payload, dict):
        return failure_envelope(
            FailureKind.MISSING_REQUIRED_FIELD,
            action,
            agent_failure_context={"explanation": "Request body must be a JSON object."},
        ).to_dict()
    session_id_raw = payload.get("session_id")
    turn_id = payload.get("turn_id")
    if not isinstance(session_id_raw, str) or not session_id_raw.strip():
        return failure_envelope(
            FailureKind.MISSING_REQUIRED_FIELD,
            action,
            agent_failure_context={"explanation": "`session_id` is required."},
        ).to_dict()
    if not isinstance(turn_id, str) or not turn_id.strip():
        return failure_envelope(
            FailureKind.MISSING_REQUIRED_FIELD,
            action,
            agent_failure_context={"explanation": "`turn_id` is required."},
        ).to_dict()
    session_id = _safe_session_id(session_id_raw)
    root = _root(session_root)
    mutator = accept_turn if action == "accept" else reject_turn

    def _write_action_response(response: dict[str, Any]) -> Path:
        path = turn_dir_for(root, session_id, turn_id) / f"{action}_response.json"
        path.parent.mkdir(parents=True, exist_ok=True)
        path.write_text(json.dumps(response, indent=2, sort_keys=True) + "\n", encoding="utf-8")
        return path

    result = mutator(
        session_root=root,
        session_id=session_id,
        turn_id=turn_id,
        client_graph_hash=payload.get("client_graph_hash")
        if isinstance(payload.get("client_graph_hash"), str)
        else None,
        request_payload=payload,
        idempotency_key=_idempotency_key(payload),
        response_writer=_write_action_response,
    )
    if not isinstance(result, dict):
        return result.to_dict()
    terminal_state = result.get("accepted_state") if isinstance(result.get("accepted_state"), str) else None
    eligibility = derive_apply_eligibility(
        TurnContext(
            session_id=session_id,
            turn_id=turn_id,
            baseline_turn_id=result.get("baseline_turn_id")
            if isinstance(result.get("baseline_turn_id"), str)
            else None,
        ),
        candidate_state=terminal_state,
    )
    result.update(
        apply_eligibility_payload(
            eligibility,
            canvas_apply_allowed=False,
            queue_allowed=False,
        )
    )
    try:
        audit_dir = turn_dir_for(root, session_id, turn_id) / f"{action}_audit"
        audit_path = audit_dir / "audit.json"
        if audit_path.exists():
            audit_ref = artifact_ref_for_path(audit_path)
        else:
            audit_ref = write_audit(
                audit_dir,
                context=TurnContext(
                    session_id=session_id,
                    turn_id=turn_id,
                    baseline_turn_id=result.get("baseline_turn_id")
                    if isinstance(result.get("baseline_turn_id"), str)
                    else None,
                    idempotency_key=_idempotency_key(payload),
                ),
                turn_state=result.get("accepted_state")
                if isinstance(result.get("accepted_state"), str)
                else None,
                response=result,
                artifacts={"request": payload},
                metadata={"action": action},
            )
        result = {**result, "audit_ref": audit_ref.to_dict()}
    except Exception as exc:
        failure = classify_failure("audit", exc)
        return failure.to_dict()
    return result


def _handle_agent_edit_accept(payload: Any, *, session_root: Any = None) -> dict[str, Any]:
    return _handle_agent_edit_action(payload, action="accept", session_root=session_root)


def _handle_agent_edit_reject(payload: Any, *, session_root: Any = None) -> dict[str, Any]:
    return _handle_agent_edit_action(payload, action="reject", session_root=session_root)


def _handle_agent_edit_rebaseline(payload: Any, *, session_root: Any = None) -> dict[str, Any]:
    if not isinstance(payload, dict):
        return failure_envelope(
            FailureKind.MISSING_REQUIRED_FIELD,
            "rebaseline",
            agent_failure_context={"explanation": "Request body must be a JSON object."},
        ).to_dict()
    session_id_raw = payload.get("session_id")
    if not isinstance(session_id_raw, str) or not session_id_raw.strip():
        return failure_envelope(
            FailureKind.MISSING_REQUIRED_FIELD,
            "rebaseline",
            agent_failure_context={"explanation": "`session_id` is required."},
        ).to_dict()
    session_id = _safe_session_id(session_id_raw)
    root = _root(session_root)

    result = rebaseline_session(
        session_root=root,
        session_id=session_id,
        request_payload=payload,
        idempotency_key=_idempotency_key(payload),
    )
    if not isinstance(result, dict):
        return result.to_dict()
    eligibility = derive_apply_eligibility(
        TurnContext(
            session_id=session_id,
            baseline_turn_id=result.get("baseline_turn_id")
            if isinstance(result.get("baseline_turn_id"), str)
            else None,
        ),
        has_candidate=False,
    )
    result.update(
        apply_eligibility_payload(
            eligibility,
            canvas_apply_allowed=False,
            queue_allowed=False,
        )
    )

    try:
        rebaseline_id = result.get("rebaseline_id")
        audit_dir = (
            session_dir_for(root, session_id)
            / "_rebaseline"
            / str(rebaseline_id)
            / "audit"
        )
        audit_path = audit_dir / "audit.json"
        if audit_path.exists():
            audit_ref = artifact_ref_for_path(audit_path)
        else:
            audit_ref = write_audit(
                audit_dir,
                context=TurnContext(
                    session_id=session_id,
                    baseline_turn_id=result.get("baseline_turn_id")
                    if isinstance(result.get("baseline_turn_id"), str)
                    else None,
                    idempotency_key=_idempotency_key(payload),
                ),
                response=result,
                artifacts={"request": payload},
                metadata={
                    "action": "rebaseline",
                    "rebaseline_id": rebaseline_id,
                },
            )
        result = {**result, "audit_ref": audit_ref.to_dict()}
    except Exception as exc:
        failure = classify_failure("audit", exc)
        return failure.to_dict()
    return result


def _handle_agent_edit_audit(
    params: dict[str, Any],
    *,
    session_root: Any = None,
) -> dict[str, Any]:
    session_id_raw = params.get("session_id")
    turn_id = params.get("turn_id")
    action = params.get("action")
    if not isinstance(session_id_raw, str) or not isinstance(turn_id, str):
        return failure_envelope(
            FailureKind.MISSING_REQUIRED_FIELD,
            "audit",
            agent_failure_context={"explanation": "`session_id` and `turn_id` are required."},
        ).to_dict()
    session_id = _safe_session_id(session_id_raw)
    audit_dir = "audit"
    if action in {"accept", "reject", "unknown"}:
        audit_dir = f"{action}_audit"
    path = turn_dir_for(_root(session_root), session_id, turn_id) / audit_dir / "audit.json"
    session_dir = session_dir_for(_root(session_root), session_id).resolve()
    try:
        resolved = path.resolve()
        if session_dir not in resolved.parents:
            raise ValueError("Audit path escaped the session directory.")
        body = resolved.read_bytes()
    except Exception as exc:
        return classify_failure("audit", exc).to_dict()
    return {
        "ok": True,
        "body": body,
        "headers": {
            "Content-Type": "application/json",
            "Content-Disposition": f'attachment; filename="{session_id}-{turn_id}-{audit_dir}.json"',
            "X-Content-Type-Options": "nosniff",
        },
        "path": str(resolved),
        "sha256": payload_hash(json.loads(body.decode("utf-8"))),
    }


def _handle_agent_status(params: dict[str, Any] | None = None) -> dict[str, Any]:
    params = params or {}
    route = params.get("route") if isinstance(params.get("route"), str) else None
    model = params.get("model") if isinstance(params.get("model"), str) else None
    ready_payload = readiness(route=route, model=model)
    ok = bool(ready_payload.get("ready"))
    status: dict[str, Any] = {
        **ready_payload,
        "ok": ok,
        "readiness": "ready" if ok else "unavailable",
    }
    if not ok and not status.get("provider_available") and "error" not in status:
        status["error"] = str(status.get("reason") or "Provider is unavailable.")
    return status


def _handle_agent_credentials(
    payload: Any,
    *,
    env_path: Any = None,
) -> dict[str, Any]:
    if not isinstance(payload, dict):
        return failure_envelope(
            FailureKind.MISSING_REQUIRED_FIELD,
            "credentials",
            agent_failure_context={"explanation": "Request body must be a JSON object."},
        ).to_dict()
    try:
        return handle_credential_submission(
            payload,
            env_path=Path(env_path) if env_path is not None else None,
        )
    except Exception as exc:
        return classify_failure("ingest", exc).to_dict()


def _handle_agent_edit(
    payload: Any,
    *,
    schema_provider: Any = None,
    deepseek_client: Any = None,
    session_root: Any = None,
    client_id: str | None = None,
) -> dict[str, Any]:
    if not isinstance(payload, dict):
        return failure_envelope(
            FailureKind.MISSING_REQUIRED_FIELD,
            "ingest",
            agent_failure_context={"explanation": "Request body must be a JSON object."},
        ).to_dict()
    try:
        return handle_agent_edit(
            payload,
            schema_provider=schema_provider,
            deepseek_client=deepseek_client,
            session_root=session_root,
            client_id=client_id,
        )
    except Exception as exc:
        stage = "ingest" if isinstance(exc, ValueError) else "route"
        return classify_failure(stage, exc).to_dict()


try:
    from aiohttp import web as _web  # noqa: PLC0415
    from server import PromptServer as _PromptServer  # noqa: PLC0415

    @_PromptServer.instance.routes.post("/vibecomfy/roundtrip")
    async def roundtrip_route(request):  # type: ignore[no-untyped-def]
        try:
            payload = await request.json()
        except Exception as exc:
            return _web.json_response(
                {"error": str(exc), "kind": type(exc).__name__}, status=400
            )
        result = _handle_roundtrip(payload)
        if "error" in result:
            return _web.json_response(result, status=400)
        return _web.json_response(result)

    @_PromptServer.instance.routes.post("/vibecomfy/agent-edit")
    async def agent_edit_route(request):  # type: ignore[no-untyped-def]
        try:
            payload = await request.json()
        except Exception as exc:
            return _web.json_response(
                failure_envelope(
                    FailureKind.MISSING_REQUIRED_FIELD,
                    "ingest",
                    agent_failure_context={
                        "explanation": f"Request body must be valid JSON: {exc}"
                    },
                ).to_dict(),
                status=400,
            )
        client_id = payload.get("client_id") if isinstance(payload.get("client_id"), str) and payload.get("client_id").strip() else None
        result = _handle_agent_edit(payload, client_id=client_id)
        if result.get("ok") is False:
            status = 500 if result.get("stage") == "route" else 400
            return _web.json_response(result, status=status)
        return _web.json_response(result)

    @_PromptServer.instance.routes.post("/vibecomfy/agent-edit/accept")
    async def agent_edit_accept_route(request):  # type: ignore[no-untyped-def]
        try:
            payload = await request.json()
        except Exception as exc:
            return _web.json_response(
                failure_envelope(
                    FailureKind.MISSING_REQUIRED_FIELD,
                    "accept",
                    agent_failure_context={
                        "explanation": f"Request body must be valid JSON: {exc}"
                    },
                ).to_dict(),
                status=400,
            )
        result = _handle_agent_edit_accept(payload)
        return _web.json_response(result, status=400 if result.get("ok") is False else 200)

    @_PromptServer.instance.routes.post("/vibecomfy/agent-edit/reject")
    async def agent_edit_reject_route(request):  # type: ignore[no-untyped-def]
        try:
            payload = await request.json()
        except Exception as exc:
            return _web.json_response(
                failure_envelope(
                    FailureKind.MISSING_REQUIRED_FIELD,
                    "reject",
                    agent_failure_context={
                        "explanation": f"Request body must be valid JSON: {exc}"
                    },
                ).to_dict(),
                status=400,
            )
        result = _handle_agent_edit_reject(payload)
        return _web.json_response(result, status=400 if result.get("ok") is False else 200)

    @_PromptServer.instance.routes.post("/vibecomfy/agent-edit/rebaseline")
    async def agent_edit_rebaseline_route(request):  # type: ignore[no-untyped-def]
        try:
            payload = await request.json()
        except Exception as exc:
            return _web.json_response(
                failure_envelope(
                    FailureKind.MISSING_REQUIRED_FIELD,
                    "rebaseline",
                    agent_failure_context={
                        "explanation": f"Request body must be valid JSON: {exc}"
                    },
                ).to_dict(),
                status=400,
            )
        result = _handle_agent_edit_rebaseline(payload)
        return _web.json_response(result, status=400 if result.get("ok") is False else 200)

    @_PromptServer.instance.routes.get("/vibecomfy/agent-edit/audit")
    async def agent_edit_audit_route(request):  # type: ignore[no-untyped-def]
        result = _handle_agent_edit_audit(dict(request.query))
        if result.get("ok") is not True:
            return _web.json_response(result, status=400)
        return _web.Response(
            body=result["body"],
            headers=result["headers"],
        )

    @_PromptServer.instance.routes.get("/vibecomfy/agent/status")
    async def agent_status_route(request):  # type: ignore[no-untyped-def]
        return _web.json_response(_handle_agent_status(dict(request.query)))

    @_PromptServer.instance.routes.post("/vibecomfy/agent/credentials")
    async def agent_credentials_route(request):  # type: ignore[no-untyped-def]
        try:
            payload = await request.json()
        except Exception as exc:
            return _web.json_response(
                failure_envelope(
                    FailureKind.MISSING_REQUIRED_FIELD,
                    "credentials",
                    agent_failure_context={
                        "explanation": f"Request body must be valid JSON: {exc}"
                    },
                ).to_dict(),
                status=400,
            )
        result = _handle_agent_credentials(payload)
        return _web.json_response(result, status=400 if result.get("ok") is False else 200)

except ImportError:
    pass
