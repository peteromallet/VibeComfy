from __future__ import annotations

import json
import logging
import os
from importlib import import_module
from pathlib import Path
from typing import Any, Mapping

from ..provider import _latest_clarification_context
from ..session import structural_graph_hash
from .state import AgentEditState
from vibecomfy.executor.contracts import ReadinessReport, RevisionEvidence, TopologyFindings

LOGGER = logging.getLogger(__name__)

_TEXT_TO_IMAGE_SEED_TYPES = (
    "CheckpointLoaderSimple",
    "CLIPTextEncode",
    "EmptyLatentImage",
    "KSampler",
    "VAEDecode",
    "SaveImage",
)

_RUNTIME_OBJECT_INFO_PATH: list[str] = []


def _schema_provider_available(schema_provider: Any) -> bool:
    if schema_provider is None:
        return False
    schemas = getattr(schema_provider, "schemas", None)
    if callable(schemas):
        try:
            return bool(schemas())
        except Exception:
            return False
    get_schema = getattr(schema_provider, "get_schema", None)
    return callable(get_schema)


def _schema_provider_has_class(schema_provider: Any, class_type: str) -> bool:
    get_schema = getattr(schema_provider, "get_schema", None)
    if not callable(get_schema):
        return False
    try:
        return get_schema(class_type) is not None
    except Exception:
        return False


def _graph_class_types_missing_from_schema(
    graph: Mapping[str, Any] | None,
    schema_provider: Any,
) -> tuple[str, ...]:
    if not isinstance(graph, Mapping):
        return ()
    nodes = graph.get("nodes")
    if not isinstance(nodes, list):
        return ()
    missing: list[str] = []
    seen: set[str] = set()
    for node in nodes:
        if not isinstance(node, Mapping):
            continue
        raw = node.get("class_type") or node.get("type")
        class_type = str(raw or "").strip()
        if not class_type or class_type == "Unknown" or class_type in seen:
            continue
        seen.add(class_type)
        if not _schema_provider_has_class(schema_provider, class_type):
            missing.append(class_type)
    return tuple(missing)


def _candidate_dict(candidate: Any) -> dict[str, Any] | None:
    if isinstance(candidate, Mapping):
        return dict(candidate)
    to_dict = getattr(candidate, "to_dict", None)
    if callable(to_dict):
        value = to_dict()
        if isinstance(value, Mapping):
            return dict(value)
    return None


def _resolver_candidate_supports_class(
    candidate: Mapping[str, Any],
    class_type: str,
) -> bool:
    expected = candidate.get("expected_classes")
    if isinstance(expected, (list, tuple)) and class_type in {str(item) for item in expected}:
        return True
    schema_payload = candidate.get("provisional_schema")
    if isinstance(schema_payload, Mapping):
        raw_schema = schema_payload.get("schema")
        if isinstance(raw_schema, Mapping):
            nodes = raw_schema.get("nodes") or raw_schema.get("object_info") or raw_schema
            return isinstance(nodes, Mapping) and class_type in nodes
    return False


def _candidate_stable_key(candidate: Mapping[str, Any]) -> str:
    return (
        str(candidate.get("stable_install_hash") or "")
        or json.dumps(dict(candidate), sort_keys=True, default=str)
    )


def _hydrate_current_graph_unknown_node_schemas(state: AgentEditState) -> tuple[dict[str, Any], ...]:
    missing_classes = _graph_class_types_missing_from_schema(state.graph, state.schema_provider)
    if not missing_classes:
        return ()

    try:
        from vibecomfy.registry.pack_resolver import resolve_missing_nodes
        from vibecomfy.schema import CompositeSchemaProvider, ProvisionalRegistrySchemaProvider
    except Exception as exc:
        LOGGER.debug("registry schema hydration unavailable: %s", exc)
        return ()

    candidates: list[dict[str, Any]] = []
    for class_type in missing_classes:
        try:
            resolution = resolve_missing_nodes(class_type, query_intent="class_name")
        except Exception as exc:
            LOGGER.debug("registry schema hydration failed for %s: %s", class_type, exc)
            continue
        for raw_candidate in getattr(resolution, "candidates", ()) or ():
            candidate = _candidate_dict(raw_candidate)
            if candidate is None:
                continue
            if not _resolver_candidate_supports_class(candidate, class_type):
                continue
            candidates.append(candidate)

    new_candidates = [
        candidate
        for candidate in candidates
        if _candidate_stable_key(candidate) not in state.provisional_registry_candidate_hashes
    ]
    if not new_candidates:
        return ()
    provisional = ProvisionalRegistrySchemaProvider(new_candidates)
    if not provisional.schemas():
        return ()
    state.provisional_registry_candidate_hashes = frozenset(
        {
            *state.provisional_registry_candidate_hashes,
            *(_candidate_stable_key(candidate) for candidate in new_candidates),
        }
    )
    state.schema_provider = CompositeSchemaProvider(provisional, state.schema_provider)
    return tuple(new_candidates)


def _revision_no_candidate_reason(evidence: RevisionEvidence) -> str | None:
    if evidence.safe_candidate_possible:
        return None
    if evidence.topology.missing_graph:
        return "no_graph"
    return "no_changes"


def _executor_classification_text(state: AgentEditState) -> str:
    classification = state.request_payload.get("executor_classification")
    if isinstance(classification, Mapping):
        return " ".join(
            str(classification.get(key) or "")
            for key in ("plan_summary", "intent", "route", "task")
        )
    return ""


def _effective_implementation_task(state: AgentEditState) -> str:
    classification_text = _executor_classification_text(state).strip()
    if not classification_text:
        return state.task
    return f"{state.task}\n\nResolved executor plan/context:\n{classification_text}"


def _runtime_code_additive_request(state: AgentEditState) -> bool:
    classification_text = _executor_classification_text(state)
    task = (
        f"{state.task} {state.request_payload.get('query') or ''} "
        f"{classification_text}"
    ).lower()
    return (
        (
            "code node" in task
            or "runtime code" in task
            or "vibecomfy.exec" in task
            or "imagecode" in task
            or ("pil" in task and "transformation" in task)
        )
        and ("pil" in task or "image" in task or "frame" in task or "process" in task)
    )


def _executor_requested_implementation(state: AgentEditState) -> bool:
    classification = state.request_payload.get("executor_classification")
    if isinstance(classification, Mapping) and "implement" in classification:
        return bool(classification.get("implement"))
    route = state.route.strip() if isinstance(state.route, str) else ""
    return route in {"revise", "adapt", "dev"}


def _state_runtime_execution_requested(state: AgentEditState) -> bool:
    runtime = state.request_payload.get("runtime")
    return isinstance(runtime, Mapping) and bool(runtime.get("execution_requested"))


def _empty_graph_authoring_request(state: AgentEditState) -> bool:
    evidence = state.revision_evidence
    if evidence is None or not evidence.topology.missing_graph:
        return False
    if _state_runtime_execution_requested(state):
        return False
    return _executor_requested_implementation(state)


def _seed_focus_types_for_authoring(state: AgentEditState) -> set[str]:
    task = _effective_implementation_task(state).lower()
    if not _empty_graph_authoring_request(state):
        return set()
    if (
        "sd1.5" in task
        or "sd 1.5" in task
        or "sd15" in task
        or "stable diffusion" in task
        or "text-to-image" in task
        or "text to image" in task
    ):
        return set(_TEXT_TO_IMAGE_SEED_TYPES)
    return set()


def _focus_types_from_research_brief(brief: Mapping[str, Any] | None) -> set[str]:
    if not brief:
        return set()
    candidates: set[str] = set()
    for key in ("search_directions", "model_families"):
        values = brief.get(key)
        if not isinstance(values, (list, tuple)):
            continue
        for value in values:
            if not isinstance(value, str):
                continue
            for token in value.split():
                token = token.strip(".,;:\"'")
                if token and token[0].isupper() and len(token) >= 2 and token.isascii():
                    candidates.add(token)
            parts = value.split()
            if parts and parts[0] and parts[0][0].isupper():
                candidates.add(parts[0].strip(".,;:\"'"))
    return candidates


def _can_attempt_local_additive_revise(state: AgentEditState) -> bool:
    evidence = state.revision_evidence
    if evidence is None:
        return False
    topology = evidence.topology
    readiness = evidence.readiness
    if _empty_graph_authoring_request(state):
        if topology.dangling_links or topology.absent_endpoint_nodes:
            return False
        if readiness.no_gpu_detected or readiness.validation_errors or readiness.readiness_blockers:
            return False
        return True
    if not _runtime_code_additive_request(state):
        return False
    if topology.missing_graph or topology.dangling_links or topology.absent_endpoint_nodes:
        return False
    if readiness.no_gpu_detected or readiness.validation_errors or readiness.readiness_blockers:
        return False
    return bool(
        topology.unknown_class_types
        or topology.missing_required_inputs
        or readiness.missing_models
        or readiness.missing_node_packs
    )


def _stable_blocker_key(value: Any) -> str:
    try:
        return json.dumps(value, sort_keys=True, default=str)
    except TypeError:
        return str(value)


def _subtract_existing_blockers(
    current: tuple[Any, ...],
    existing: tuple[Any, ...],
) -> tuple[Any, ...]:
    existing_keys = {_stable_blocker_key(item) for item in existing}
    return tuple(item for item in current if _stable_blocker_key(item) not in existing_keys)


def _localized_additive_scoped_evidence(
    state: AgentEditState,
    *,
    candidate_topology: TopologyFindings,
    candidate_readiness: ReadinessReport,
) -> tuple[
    TopologyFindings | None,
    ReadinessReport | None,
    TopologyFindings | None,
    ReadinessReport | None,
]:
    if not _can_attempt_local_additive_revise(state) or state.revision_evidence is None:
        return None, None, None, None
    topology = state.revision_evidence.topology
    readiness = state.revision_evidence.readiness
    empty_graph_authoring = _empty_graph_authoring_request(state)
    filtered_original_topology = TopologyFindings(
        missing_graph=False if empty_graph_authoring else topology.missing_graph,
        dangling_links=topology.dangling_links,
        absent_endpoint_nodes=topology.absent_endpoint_nodes,
        socket_type_mismatches=topology.socket_type_mismatches,
        schema_available=topology.schema_available,
        summary=(
            "pre-existing empty-graph authoring baseline ignored for new workflow"
            if empty_graph_authoring
            else "pre-existing unknown/custom-node blockers ignored for localized "
            "runtime code-node addition"
        ),
    )
    filtered_original_readiness = ReadinessReport(
        validation_errors=readiness.validation_errors,
        no_gpu_detected=readiness.no_gpu_detected,
        readiness_blockers=readiness.readiness_blockers,
        object_info_available=readiness.object_info_available,
        summary=(
            "pre-existing missing model/node-pack blockers ignored for localized "
            "runtime code-node addition"
        ),
    )
    filtered_candidate_topology = TopologyFindings(
        missing_graph=candidate_topology.missing_graph,
        dangling_links=candidate_topology.dangling_links,
        absent_endpoint_nodes=candidate_topology.absent_endpoint_nodes,
        socket_type_mismatches=_subtract_existing_blockers(
            candidate_topology.socket_type_mismatches,
            topology.socket_type_mismatches,
        ),
        unknown_class_types=_subtract_existing_blockers(
            candidate_topology.unknown_class_types,
            topology.unknown_class_types,
        ),
        missing_required_inputs=_subtract_existing_blockers(
            candidate_topology.missing_required_inputs,
            topology.missing_required_inputs,
        ),
        schema_available=candidate_topology.schema_available,
        summary=(
            "pre-existing unknown/custom-node blockers subtracted for localized "
            "runtime code-node addition"
        ),
    )
    filtered_candidate_readiness = ReadinessReport(
        missing_models=_subtract_existing_blockers(
            candidate_readiness.missing_models,
            readiness.missing_models,
        ),
        missing_node_packs=_subtract_existing_blockers(
            candidate_readiness.missing_node_packs,
            readiness.missing_node_packs,
        ),
        validation_errors=candidate_readiness.validation_errors,
        no_gpu_detected=candidate_readiness.no_gpu_detected,
        readiness_blockers=candidate_readiness.readiness_blockers,
        object_info_available=candidate_readiness.object_info_available,
        summary=(
            "pre-existing missing model/node-pack blockers subtracted for localized "
            "runtime code-node addition"
        ),
    )
    return (
        filtered_original_topology,
        filtered_original_readiness,
        filtered_candidate_topology,
        filtered_candidate_readiness,
    )


def _session_reference_map_for_evidence(
    conversation_messages: list[dict[str, Any]] | None,
) -> dict[str, Any]:
    if not conversation_messages:
        return {}
    compact: dict[str, Any] = {"recent_message_count": len(conversation_messages)}
    latest = conversation_messages[-1] if conversation_messages else None
    if isinstance(latest, Mapping):
        outcome = latest.get("outcome")
        if isinstance(outcome, Mapping) and isinstance(outcome.get("kind"), str):
            compact["latest_outcome_kind"] = outcome["kind"]
        text = latest.get("text")
        if isinstance(text, str) and text.strip():
            compact["latest_text_preview"] = text.strip()[:160]
    clarification = _latest_clarification_context(conversation_messages)
    if clarification is not None:
        compact["pending_clarification"] = {
            "prior_request": clarification["prior_request"][:240],
            "question": clarification["question"][:240],
        }
    latest_candidate = next(
        (
            msg
            for msg in reversed(conversation_messages)
            if isinstance(msg, Mapping)
            and isinstance(msg.get("text"), str)
            and "Latest candidate reference" in msg["text"]
        ),
        None,
    )
    if isinstance(latest_candidate, Mapping):
        compact["latest_candidate_reference"] = str(latest_candidate.get("text", ""))[:400]
    return compact


def _runtime_execution_requested(task: str | None, payload: Mapping[str, Any]) -> bool:
    text = (task or "").lower()
    if any(word in text for word in ("run", "queue", "execute", "render", "generate")):
        return True
    requested = payload.get("execution_requested") or payload.get("run_requested")
    if requested is True:
        return True
    runtime = payload.get("runtime")
    return isinstance(runtime, Mapping) and runtime.get("execution_requested") is True


def _extract_ready_metadata(payload: Mapping[str, Any], graph: Mapping[str, Any] | None) -> dict[str, Any]:
    metadata: dict[str, Any] = {}
    for key in ("ready_metadata", "ready_template_metadata", "metadata", "requirements"):
        value = payload.get(key)
        if isinstance(value, Mapping):
            metadata[key] = dict(value)
    if isinstance(graph, Mapping):
        extra = graph.get("extra")
        if isinstance(extra, Mapping):
            vibecomfy = extra.get("vibecomfy")
            if isinstance(vibecomfy, Mapping):
                metadata["vibecomfy"] = dict(vibecomfy)
            for key in ("ready_metadata", "requirements", "diagnostics"):
                value = extra.get(key)
                if isinstance(value, Mapping):
                    metadata[key] = dict(value)
                elif isinstance(value, list):
                    metadata[key] = list(value)
    return metadata


def _extract_readiness_diagnostics(
    payload: Mapping[str, Any],
    graph: Mapping[str, Any] | None,
) -> tuple[dict[str, Any], ...]:
    diagnostics: list[dict[str, Any]] = []
    for source in (payload, graph if isinstance(graph, Mapping) else {}):
        raw = source.get("diagnostics") if isinstance(source, Mapping) else None
        if isinstance(raw, list):
            diagnostics.extend(dict(item) for item in raw if isinstance(item, Mapping))
    if isinstance(graph, Mapping):
        extra = graph.get("extra")
        if isinstance(extra, Mapping) and isinstance(extra.get("diagnostics"), list):
            diagnostics.extend(dict(item) for item in extra["diagnostics"] if isinstance(item, Mapping))
    runtime = payload.get("runtime")
    if isinstance(runtime, Mapping) and runtime.get("no_gpu_detected") is True:
        diagnostics.append(
            {
                "code": "no_gpu_detected",
                "severity": "error",
                "message": "No GPU is available for runtime execution.",
            }
        )
    return tuple(diagnostics)


def _request_no_gpu_detected(payload: Mapping[str, Any]) -> bool:
    if payload.get("no_gpu_detected") is True:
        return True
    runtime = payload.get("runtime")
    return isinstance(runtime, Mapping) and runtime.get("no_gpu_detected") is True


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


def _default_runtime_schema_provider() -> Any:
    from vibecomfy.schema import get_authoring_schema_provider, get_schema_provider

    try:
        if not (_RUNTIME_OBJECT_INFO_PATH and Path(_RUNTIME_OBJECT_INFO_PATH[0]).is_file()):
            data = _edit_module()._build_object_info_in_process()
            if data:
                import tempfile

                fd, path = tempfile.mkstemp(prefix="vibecomfy_object_info_", suffix=".json")
                with os.fdopen(fd, "w", encoding="utf-8") as fh:
                    json.dump(data, fh)
                _RUNTIME_OBJECT_INFO_PATH[:] = [path]
        if _RUNTIME_OBJECT_INFO_PATH:
            from vibecomfy.schema.provider import ObjectInfoSchemaProvider

            return ObjectInfoSchemaProvider(_RUNTIME_OBJECT_INFO_PATH[0])
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
def _edit_module() -> Any:
    return import_module("vibecomfy.comfy_nodes.agent.edit")

