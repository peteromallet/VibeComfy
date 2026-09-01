"""
Turn orchestration: run/classify stages and dev/batch product paths (T-039 extraction of the edit_orchestration fragment).

Extracted from the edit.py exec-assembled fragments (T-039, ORACLE-6).
The fragment SOURCE string stays in edit.py until T-041 removes the machinery;
this module is the live implementation. Function bodies resolve their free
names from the assembled edit-module namespace at call time (marked with a
T-039 late import comment) so monkeypatches on edit.* stay visible exactly as
under the old exec assembly; guarded imports stay function-local.
"""
from __future__ import annotations

from pathlib import Path
import dataclasses
import json
import os
import threading
import traceback
from typing import Any, Mapping


def _run_stage(
    name: str,
    state: AgentEditState,
    context: TurnContext,
    fn: Callable[..., StageResult],
    *args: Any,
    **kwargs: Any,
) -> StageResult:
    from vibecomfy.comfy_nodes.agent.edit import (FailureKind, StageResult, _StageBlocked, _classify_stage_failure, _is_provider_exception, _record, failure_envelope)  # T-039 late import: host namespace lookup; resolved at call time
    try:
        result = fn(state, context, *args, **kwargs)
    except Exception as exc:
        failure_stage = (
            "agent_response"
            if name in {"agent", "agent_delta"}
            or (name in {"agent_batch", "agent_batch_repl"} and _is_provider_exception(exc))
            else name
        )
        failure = _classify_stage_failure(failure_stage, exc, context)
        batch_stage_traceback: str | None = None
        if name in {"agent_batch", "agent_batch_repl"}:
            # Retain structured validation issues even when the loop raised:
            # the accumulated per-turn diagnostics are the only actionable
            # evidence the agent can repair from, so they must survive into
            # the failure envelope instead of being replaced by the bare
            # exception text (which is often empty, e.g. a bare assert).
            from vibecomfy.comfy_nodes.agent.edit import _batch_turn_diagnostics  # T-039 late import: host namespace lookup; resolved at call time
            turn_diagnostics = _batch_turn_diagnostics(
                list(getattr(state, "batch_turns", ()) or ())
            )
            failure_context = dict(failure.agent_failure_context or {})
            existing_issues = failure_context.get("issues")
            issues = (
                list(existing_issues)
                if isinstance(existing_issues, (list, tuple)) and existing_issues
                else list(turn_diagnostics)
            )
            if not _is_provider_exception(exc):
                # Unexpected crash inside the batch loop (e.g. 'NoneType'
                # object is not iterable): expose one bounded structured issue
                # identifying the internal stage and terminal frame so the
                # executor surfaces a real diagnostic instead of `{}`.
                issues.append(_batch_stage_exception_issue(name, exc))
                batch_stage_traceback = traceback.format_exc()
            if issues:
                failure_context["issues"] = issues
                failure = dataclasses.replace(
                    failure,
                    agent_failure_context=failure_context,
                )
        result_issues: list[Any] = [failure.agent_failure_context]
        if batch_stage_traceback is not None:
            # Full traceback stays in the private turn/audit record only; the
            # public failure envelope carries just the bounded issue above.
            result_issues.append(
                {"code": "agent_batch_stage_traceback", "traceback": batch_stage_traceback}
            )
        result = StageResult(
            stage=name,
            ok=False,
            blocking=True,
            issues=tuple(result_issues),
        )
        _record(context, result)
        raise _StageBlocked(result, failure) from exc
    _record(context, result)
    if result.blocking:
        failure_kind = None
        if isinstance(result.value, dict):
            failure_kind = result.value.get("failure_kind")
        public_stage = name
        issue_codes = {
            str(issue.get("code"))
            for issue in result.issues
            if isinstance(issue, dict) and issue.get("code") is not None
        }
        diagnostic_codes: set[str] = set()
        if name == "agent_batch_repl":
            for turn in state.batch_turns:
                if not isinstance(turn, Mapping):
                    continue
                diagnostics = list(turn.get("diagnostics") or [])
                for statement in turn.get("statements") or []:
                    if isinstance(statement, Mapping):
                        diagnostics.extend(statement.get("diagnostics") or [])
                diagnostic_codes.update(
                    str(diagnostic.get("code"))
                    for diagnostic in diagnostics
                    if isinstance(diagnostic, Mapping) and diagnostic.get("code") is not None
                )
        parse_or_query_codes = {
            "batch_syntax_error",
            "nested_call_not_allowed",
            "unsupported_query_call",
        }
        if (
            name == "agent_batch_repl"
            and "batch_budget_exhausted" in issue_codes
            and not diagnostic_codes.intersection(parse_or_query_codes)
        ):
            public_stage = "agent_batch"
        failure = failure_envelope(
            failure_kind or FailureKind.VALIDATION_ERROR,
            public_stage,
            context,
            agent_failure_context={
                "explanation": f"Stage {public_stage} blocked the agent edit.",
                "issues": [dict(issue) for issue in result.issues if isinstance(issue, dict)],
                **(
                    {
                        "validation_errors": result.value["validation_errors"],
                    }
                    if isinstance(result.value, dict)
                    and result.value.get("validation_errors") is not None
                    else {}
                ),
                **(
                    {
                        "diagnostics": result.value["diagnostics"],
                    }
                    if isinstance(result.value, dict)
                    and result.value.get("diagnostics") is not None
                    else {}
                ),
            },
        )
        if failure.kind is FailureKind.STALE_STATE_MISMATCH and public_stage in {"ingest", "ingest_v2"}:
            failure = dataclasses.replace(
                failure,
                user_facing_message=(
                    "The canvas changed since the current backend baseline. "
                    "Rebaseline and resubmit from the current canvas."
                ),
            )
        raise _StageBlocked(result, failure)
    return result


def _is_provider_exception(exc: Exception) -> bool:
    provider_exception_names = {
        "AuthError",
        "MalformedModelJSON",
        "MissingRequiredField",
        "ProviderError",
    }
    return any(type_.__name__ in provider_exception_names for type_ in type(exc).__mro__)


def _terminal_traceback_frame(exc: BaseException) -> dict[str, Any]:
    """Return the deepest traceback frame as a repository-relative location."""

    deepest = None
    frame_tb = exc.__traceback__
    while frame_tb is not None:
        deepest = frame_tb
        frame_tb = frame_tb.tb_next
    if deepest is None:
        return {}
    code = deepest.tb_frame.f_code
    filename = code.co_filename
    try:
        repo_root = Path(__file__).resolve().parents[3]
        filename = Path(filename).resolve().relative_to(repo_root).as_posix()
    except (ValueError, OSError):
        pass
    return {"file": filename, "function": code.co_name, "line": int(deepest.tb_lineno)}


def _batch_stage_exception_issue(stage: str, exc: BaseException) -> dict[str, Any]:
    """Bounded public issue identifying an unexpected crash inside a batch stage."""

    issue: dict[str, Any] = {
        "code": "agent_batch_stage_exception",
        "exception_type": type(exc).__name__,
        "stage": stage,
        "message": str(exc),
    }
    issue.update(_terminal_traceback_frame(exc))
    return issue


def _classify_stage_failure(
    stage: str,
    exc_or_issue: Any,
    context: TurnContext | Mapping[str, Any] | None = None,
) -> FailureEnvelope:
    from vibecomfy.comfy_nodes.agent.edit import (FailureKind, classify_failure, failure_envelope)  # T-039 late import: host namespace lookup; resolved at call time
    failure = classify_failure(stage, exc_or_issue, context)
    if stage in {"ingest", "ingest_v2"} and failure.kind is FailureKind.UNSUPPORTED_NON_DAG:
        lower_message = str(exc_or_issue).lower()
        if "non-dag" not in lower_message and "control flow" not in lower_message:
            return failure_envelope(
                FailureKind.VALIDATION_ERROR,
                stage,
                context,
                agent_failure_context=failure.agent_failure_context,
            )
    return failure


def _batch_repl_candidate_needs_queue_validate(state: AgentEditState) -> bool:
    from vibecomfy.comfy_nodes.agent.edit import (_BATCH_EXIT_DONE, _BATCH_EXIT_EDIT_CLARIFY, _batch_candidate_graph_changed, _total_landed_edit_count)  # T-039 late import: host namespace lookup; resolved at call time
    if state.batch_exit_mode not in {_BATCH_EXIT_DONE, _BATCH_EXIT_EDIT_CLARIFY}:
        return False
    if not isinstance(state.ui_payload, Mapping):
        return False
    if not _batch_candidate_graph_changed(state):
        return False
    return _total_landed_edit_count(state) > 0


def _stage_batch_repl_queue_validate(
    state: AgentEditState,
    _context: TurnContext,
) -> StageResult:
    from vibecomfy.comfy_nodes.agent.edit import (_queue_recovery_report_for_candidate, queue_stage_result)  # T-039 late import: host namespace lookup; resolved at call time
    recovery_report = _queue_recovery_report_for_candidate(
        ui_payload=state.ui_payload,
        schema_provider=state.schema_provider,
        original_ui_payload=state.graph,
        existing_recovery_report=(state.report or {}).get("recovery"),
    )
    if state.report is None:
        state.report = {}
    state.report["recovery"] = recovery_report
    return queue_stage_result(
        recovery_report=recovery_report,
        change_report=(state.report or {}).get("change"),
    )


def _run_batch_repl_queue_validate_if_needed(
    state: AgentEditState,
    context: TurnContext,
) -> None:
    from vibecomfy.comfy_nodes.agent.edit import (_batch_repl_candidate_needs_queue_validate, _run_stage, _stage_batch_repl_queue_validate, derive_gates)  # T-039 late import: host namespace lookup; resolved at call time
    if not _batch_repl_candidate_needs_queue_validate(state):
        return
    queue_result = _run_stage(
        "queue_validate",
        state,
        context,
        _stage_batch_repl_queue_validate,
    )
    derive_gates(
        context,
        queue_blockers=queue_result.issues,
        require_probe_receipt=False,  # offline authoring validation; no live runtime probe here
    )
    if state.report is None:
        state.report = {}
    state.report["queue_blockers"] = [dict(issue) for issue in queue_result.issues]


def _run_batch_repl_product_path(
    state: AgentEditState,
    context: TurnContext,
    *,
    deepseek_client: DeepSeekClient | None = None,
    route: str | None = None,
    model: str | None = None,
    effort: str | None = None,
    client_id: str | None = None,
    conversation_messages: list[dict[str, Any]] | None = None,
) -> AgentEditState:
    from vibecomfy.comfy_nodes.agent.edit import (_adaptation_slice_domain_mismatch_diagnostic, _run_batch_repl_queue_validate_if_needed, _run_stage, _stage_agent_batch_repl, _stage_ingest_v2, _stage_readonly_diagnostic_report, _stage_revision_evidence, _stage_revision_readonly_report)  # T-039 late import: host namespace lookup; resolved at call time
    _run_stage("ingest", state, context, _stage_ingest_v2)
    _run_stage(
        "revision_evidence",
        state,
        context,
        _stage_revision_evidence,
        route=state.route,
        conversation_messages=conversation_messages,
    )
    readonly_diagnostic = _adaptation_slice_domain_mismatch_diagnostic(
        state,
        route=state.route or route,
    )
    if readonly_diagnostic is not None:
        _run_stage(
            "agent_batch",
            state,
            context,
            _stage_readonly_diagnostic_report,
            route=state.route,
            conversation_messages=conversation_messages,
            message=readonly_diagnostic.get("message"),
            report_payload=readonly_diagnostic.get("report_payload"),
            no_candidate_reason=readonly_diagnostic.get("no_candidate_reason"),
        )
        return state
    evidence = state.revision_evidence
    if evidence is not None and (
        evidence.topology.dangling_links
        or evidence.topology.absent_endpoint_nodes
        or evidence.readiness.has_blockers
    ):
        _run_stage(
            "agent_batch",
            state,
            context,
            _stage_revision_readonly_report,
            route=state.route,
            conversation_messages=conversation_messages,
        )
        return state
    _run_stage(
        "agent_batch",
        state,
        context,
        _stage_agent_batch_repl,
        deepseek_client=deepseek_client,
        route=route,
        model=model,
        effort=effort,
        client_id=client_id,
        conversation_messages=conversation_messages,
    )
    _run_batch_repl_queue_validate_if_needed(state, context)
    return state


_RUNTIME_OBJECT_INFO_PATH: list[str] = []
_RUNTIME_OBJECT_INFO_LOCK = threading.Lock()

def _build_object_info_in_process() -> dict[str, Any] | None:
    """Build ComfyUI /object_info IN-PROCESS from the live node registry.

    Mirrors ComfyUI server.py's ``node_info`` builder. We must NOT fetch /object_info
    over HTTP here: the agent-edit turn runs inside ComfyUI's event loop, so a blocking
    self-request deadlocks (the server can't answer while the loop is blocked) and times
    out, silently degrading to an empty schema provider. Reading the in-memory mappings
    avoids the loop entirely.
    """
    try:
        import nodes as comfy_nodes_registry  # ComfyUI global registry
    except Exception:
        return None
    mappings = getattr(comfy_nodes_registry, "NODE_CLASS_MAPPINGS", None)
    if not isinstance(mappings, dict) or not mappings:
        return None
    display = getattr(comfy_nodes_registry, "NODE_DISPLAY_NAME_MAPPINGS", {}) or {}
    out: dict[str, Any] = {}
    for name, cls in mappings.items():
        try:
            getv1 = getattr(cls, "GET_NODE_INFO_V1", None)
            if callable(getv1) and getattr(cls, "GET_NODE_INFO_V1", None) is not None:
                try:
                    out[name] = getv1()
                    continue
                except Exception:
                    pass
            info: dict[str, Any] = {}
            info["input"] = cls.INPUT_TYPES()
            rt = list(getattr(cls, "RETURN_TYPES", []) or [])
            info["output"] = rt
            info["output_name"] = list(getattr(cls, "RETURN_NAMES", rt) or rt)
            info["output_is_list"] = list(getattr(cls, "OUTPUT_IS_LIST", [False] * len(rt)) or [])
            info["name"] = name
            info["display_name"] = display.get(name, name)
            info["output_node"] = bool(getattr(cls, "OUTPUT_NODE", False))
            out[name] = info
        except Exception:
            # Some INPUT_TYPES() raise (missing models, etc.); skip those classes.
            continue
    return out or None


def _default_runtime_schema_provider(on_demand_schemas: bool | None = None) -> Any:
    from vibecomfy.comfy_nodes.agent.edit import (_build_object_info_in_process)  # T-039 late import: host namespace lookup; resolved at call time
    """Schema provider for live edit turns: the LIVE in-process ComfyUI registry.

    The offline ``local`` provider reads an out/cache snapshot that is empty in a bare
    ComfyUI checkout, so it knows ZERO classes — which makes ``add_node`` reject every
    class as ``unknown_add_node_class_type`` (even a perfectly-installed ``PreviewImage``).
    ``RuntimeSchemaProvider`` (HTTP) can't be used here: it's either blocked inside the
    event loop, or a self-request deadlocks. So we build object_info IN-PROCESS from
    ``nodes.NODE_CLASS_MAPPINGS`` once, cache it to a temp file, and return the synchronous
    file-backed ``ObjectInfoSchemaProvider``. Falls back to ``local`` only if the registry
    is unavailable (i.e. not running inside ComfyUI).
    """
    from vibecomfy.schema import get_authoring_schema_provider

    try:
        # T5.4: concurrent executor turns (comparison legs, batch REPLs) must
        # not race the one-shot temp-file build; mkstemp names are unique so a
        # lost race only wastes work — the lock removes even that.
        with _RUNTIME_OBJECT_INFO_LOCK:
            if not (_RUNTIME_OBJECT_INFO_PATH and Path(_RUNTIME_OBJECT_INFO_PATH[0]).is_file()):
                data = _build_object_info_in_process()
                if data:
                    import tempfile

                    fd, path = tempfile.mkstemp(prefix="vibecomfy_object_info_", suffix=".json")
                    with os.fdopen(fd, "w", encoding="utf-8") as fh:
                        json.dump(data, fh)
                    _RUNTIME_OBJECT_INFO_PATH[:] = [path]
        if _RUNTIME_OBJECT_INFO_PATH:
            from vibecomfy.schema.provider import (
                CompositeSchemaProvider,
                ObjectInfoSchemaProvider,
            )

            # Installed runtime schemas stay authoritative; the authoring tail
            # fills legitimate gaps for workflow nodes from absent packs.
            return CompositeSchemaProvider(
                ObjectInfoSchemaProvider(_RUNTIME_OBJECT_INFO_PATH[0]),
                get_authoring_schema_provider(
                    on_demand_schemas=on_demand_schemas,
                ),
            )
    except Exception:
        pass
    # Headless fallback (no comfy imported in-process): resolve every INSTALLED
    # node by querying a separately-running ComfyUI's live /object_info, then the
    # shipped corpus, then the offline authoring chain. RuntimeSchemaProvider with
    # an explicit server_url only does a GET (no spawn); a cheap socket probe guards
    # an absent server so the edit turn never hangs. The in-process path above
    # already covers the live-product case, where an HTTP self-request would deadlock.
    import socket
    from urllib.parse import urlparse
    from vibecomfy.schema.provider import (
        CompositeSchemaProvider,
        RuntimeSchemaProvider,
    )

    server_url = os.environ.get("VIBECOMFY_COMFYUI_URL")
    reachable = False
    if server_url:
        try:
            parsed = urlparse(server_url)
            with socket.create_connection(
                (parsed.hostname or "127.0.0.1", parsed.port or 80), timeout=0.5
            ):
                reachable = True
        except OSError:
            reachable = False
    providers: list[Any] = []
    if reachable:
        providers.append(RuntimeSchemaProvider(server_url=server_url))
    # AuthoringSchemaProvider already consults the shipped corpus (ObjectInfoIndex),
    # source parser, and local index, plus the on-demand resolver (default ON; the
    # request's on_demand_schemas flag or VIBECOMFY_ON_DEMAND_SCHEMAS="0" can opt out)
    # — so it stands in for the entire offline + on-demand tail.
    providers.append(get_authoring_schema_provider(on_demand_schemas=on_demand_schemas))
    return CompositeSchemaProvider(*providers)


__all__ = (
    "_RUNTIME_OBJECT_INFO_PATH",
    "_batch_repl_candidate_needs_queue_validate",
    "_build_object_info_in_process",
    "_classify_stage_failure",
    "_default_runtime_schema_provider",
    "_is_provider_exception",
    "_run_batch_repl_product_path",
    "_run_batch_repl_queue_validate_if_needed",

    "_run_stage",
    "_stage_batch_repl_queue_validate",
)
