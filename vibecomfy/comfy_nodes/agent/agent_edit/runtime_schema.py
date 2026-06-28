"""Runtime schema-provider and graph-adaptation helpers for agent-edit."""

from __future__ import annotations

import json
import os
from pathlib import Path
from typing import Any, Mapping

from ..audit import write_audit
from ..contracts import TurnContext
from ..session import payload_hash, structural_graph_hash, turn_dir_for
from .state import AgentEditState


def _recovery_report_from_ui_payload(
    ui_payload: Mapping[str, Any] | None,
    schema_provider: Any,
) -> list[dict[str, Any]]:
    recovery: list[dict[str, Any]] = []
    if ui_payload is None or schema_provider is None:
        return recovery
    nodes = ui_payload.get("nodes")
    if not isinstance(nodes, list):
        return recovery
    get_schema = getattr(schema_provider, "get_schema", None)
    if not callable(get_schema):
        return recovery
    for node in nodes:
        if not isinstance(node, Mapping):
            continue
        node_id = str(node.get("id", ""))
        class_type = str(node.get("type", ""))
        if not class_type:
            continue
        schema = get_schema(class_type)
        if schema is None:
            recovery.append(
                {
                    "node_id": node_id,
                    "class_type": class_type,
                    "provider": None,
                    "confidence": None,
                    "schema_less": True,
                    "widget_shape_verdict": "not_applicable",
                    "diagnostic": "schema-less: no schema provider evidence for node",
                }
            )
        else:
            recovery.append(
                {
                    "node_id": node_id,
                    "class_type": class_type,
                    "provider": getattr(schema, "source_provider", None),
                    "confidence": getattr(schema, "confidence", None),
                    "schema_less": False,
                    "widget_shape_verdict": "not_applicable",
                }
            )
    return recovery


def _resolver_candidates_from_batch_result(batch_result: Any) -> list[dict[str, Any]]:
    candidates: list[dict[str, Any]] = []
    for statement in getattr(batch_result, "statements", ()) or ():
        detail = getattr(statement, "detail", None)
        if not isinstance(detail, Mapping):
            continue
        raw_candidates = detail.get("resolver_candidates")
        if not isinstance(raw_candidates, list):
            continue
        for raw_candidate in raw_candidates:
            if isinstance(raw_candidate, Mapping):
                candidates.append(dict(raw_candidate))
    return candidates


def _workflow_schema_candidates_from_batch_result(batch_result: Any) -> list[dict[str, Any]]:
    candidates: list[dict[str, Any]] = []
    for statement in getattr(batch_result, "statements", ()) or ():
        detail = getattr(statement, "detail", None)
        if not isinstance(detail, Mapping):
            continue
        raw_candidates = detail.get("workflow_schema_candidates")
        if not isinstance(raw_candidates, list):
            continue
        for raw_candidate in raw_candidates:
            if isinstance(raw_candidate, Mapping):
                candidates.append(dict(raw_candidate))
    return candidates


def _candidate_stable_key(candidate: Mapping[str, Any]) -> str:
    return (
        str(candidate.get("stable_install_hash") or "")
        or json.dumps(dict(candidate), sort_keys=True, default=str)
    )


def _enrich_schema_provider_from_resolver_candidates(
    state: AgentEditState,
    session: Any,
    candidates: list[dict[str, Any]],
) -> None:
    new_candidates = [
        candidate
        for candidate in candidates
        if _candidate_stable_key(candidate) not in state.provisional_registry_candidate_hashes
    ]
    if not new_candidates:
        return
    from vibecomfy.schema import CompositeSchemaProvider, ProvisionalRegistrySchemaProvider

    provisional = ProvisionalRegistrySchemaProvider(new_candidates)
    if not provisional.schemas():
        return
    state.provisional_registry_candidate_hashes = frozenset(
        {
            *state.provisional_registry_candidate_hashes,
            *(_candidate_stable_key(candidate) for candidate in new_candidates),
        }
    )
    enriched = CompositeSchemaProvider(provisional, session.schema_provider)
    session.schema_provider = enriched
    state.schema_provider = enriched


_RUNTIME_OBJECT_INFO_PATH: list[str] = []


def _build_object_info_in_process() -> dict[str, Any] | None:
    try:
        import nodes as comfy_nodes_registry
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
            continue
    return out or None


def _default_runtime_schema_provider(
    *,
    build_object_info_in_process: Any = _build_object_info_in_process,
    runtime_object_info_path: list[str] | None = None,
) -> Any:
    from vibecomfy.schema import get_authoring_schema_provider, get_schema_provider

    cache_path = _RUNTIME_OBJECT_INFO_PATH if runtime_object_info_path is None else runtime_object_info_path
    try:
        if not (cache_path and Path(cache_path[0]).is_file()):
            data = build_object_info_in_process()
            if data:
                import tempfile

                fd, path = tempfile.mkstemp(prefix="vibecomfy_object_info_", suffix=".json")
                with os.fdopen(fd, "w", encoding="utf-8") as fh:
                    json.dump(data, fh)
                cache_path[:] = [path]
        if cache_path:
            from vibecomfy.schema.provider import ObjectInfoSchemaProvider

            return ObjectInfoSchemaProvider(cache_path[0])
    except Exception:
        pass
    fallback = get_authoring_schema_provider()
    try:
        schemas = getattr(fallback, "schemas", None)
        if callable(schemas) and schemas():
            return fallback
    except Exception:
        pass
    return get_schema_provider("local")


def _write_unknown_transition_audits(
    *,
    session_root: Path,
    session_id: str,
    baseline_turn_id: str | None,
    unknown_transitions: tuple[dict[str, Any], ...],
    request_payload: Mapping[str, Any],
    write_audit_fn: Any = write_audit,
) -> None:
    for transition in unknown_transitions:
        turn_id = transition.get("turn_id")
        if not isinstance(turn_id, str) or not turn_id:
            continue
        try:
            write_audit_fn(
                turn_dir_for(session_root, session_id, turn_id) / "unknown_audit",
                context=TurnContext(
                    session_id=session_id,
                    turn_id=turn_id,
                    baseline_turn_id=baseline_turn_id,
                ),
                turn_state="unknown",
                artifacts={"request": dict(request_payload)},
                metadata={"action": "unknown", **transition},
            )
        except Exception:
            continue


def _build_compatibility_response_fields(state: AgentEditState) -> dict[str, Any]:
    candidate_graph_hash = payload_hash(state.ui_payload)
    candidate_structural_graph_hash = structural_graph_hash(state.ui_payload)
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


__all__ = [
    "_RUNTIME_OBJECT_INFO_PATH",
    "_build_compatibility_response_fields",
    "_build_object_info_in_process",
    "_candidate_stable_key",
    "_default_runtime_schema_provider",
    "_enrich_schema_provider_from_resolver_candidates",
    "_recovery_report_from_ui_payload",
    "_resolver_candidates_from_batch_result",
    "_workflow_schema_candidates_from_batch_result",
    "_write_unknown_transition_audits",
]
