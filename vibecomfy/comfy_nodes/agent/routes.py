from __future__ import annotations

import asyncio
import copy
import dataclasses
import gzip
import hashlib
import json
import logging
import os
import subprocess
import sys
import urllib.request
from pathlib import Path
from typing import Any, Mapping

from vibecomfy.ingest.normalize import door_get_nodes

from . import _agentic_replay_service

_LOGGER = logging.getLogger(__name__)

from vibecomfy.security.gate import CapabilityFenceError

from .audit import artifact_ref_for_path, write_audit
from .edit import DEFAULT_CHAT_DISPLAY_MESSAGES, _SESSION_ROOT, _write_turn_chat_artifact as _edit_write_turn_chat_artifact
from .contracts import (
    AgentError,
    ApplyEligibility,
    FailureKind,
    ProviderStatus,
    TurnContext,
    build_legacy_agent_edit_v1,
    classify_failure,
    ensure_agent_edit_response_contract,
    failure_envelope,
    product_failure_envelope_fields,
    public_chat_rehydrate_payload,
    public_session_json_payload,
)
from .executor_response import (
    _CLARIFY_FORBIDDEN_KEYS,
    _NON_APPLYABLE_FORBIDDEN_KEYS,
    _executor_compatibility_fields,
    _sanitize_clarify_payload,
    _serialize_executor_result,
    _strip_non_applyable_forbidden_fields,
)
from .executor_durable import maybe_write_executor_only_durable_turn
from .provider import readiness, handle_credential_submission
from .hivemind_feedback import submit_hivemind_feedback
from .session import (
    accept_turn as _session_accept_turn,
    allocate_turn as _session_allocate_turn,
    normalize_path_component,
    normalize_session_id,
    rebaseline_session as _session_rebaseline_session,
    record_idempotent_response as _session_record_idempotent_response,
    reject_turn as _session_reject_turn,
    session_dir_for,
)



def handle_agent_edit(*args: Any, **kwargs: Any) -> dict[str, Any]:
    from .edit import handle_agent_edit as _handle_agent_edit_impl  # noqa: PLC0415

    return _handle_agent_edit_impl(*args, **kwargs)


def read_session_chat(*args: Any, **kwargs: Any) -> dict[str, Any]:
    from .edit import read_session_chat as _read_session_chat_impl  # noqa: PLC0415

    return _read_session_chat_impl(*args, **kwargs)


def accept_turn(*args: Any, **kwargs: Any) -> dict[str, Any]:
    return _session_accept_turn(*args, **kwargs)


def reject_turn(*args: Any, **kwargs: Any) -> dict[str, Any]:
    return _session_reject_turn(*args, **kwargs)


def rebaseline_session(*args: Any, **kwargs: Any) -> dict[str, Any]:
    return _session_rebaseline_session(*args, **kwargs)


def _handle_roundtrip(
    payload: dict[str, Any], *, schema_provider: Any = None
) -> dict[str, Any]:
    """Torch-free core: convert UI graph + emit, return enriched graph + change report.

    All engine imports are lazy so this function is importable without ComfyUI or torch.
    Call from tests directly; the aiohttp wrapper below delegates to this.
    """
    from vibecomfy.ingest.normalize import from_ui  # noqa: PLC0415
    from vibecomfy.porting.layout import evaluate_felt_delta  # noqa: PLC0415
    from vibecomfy.porting.emit.ui import emit_ui_json  # noqa: PLC0415
    from vibecomfy.schema import get_schema_provider  # noqa: PLC0415

    try:
        if schema_provider is None:
            schema_provider = get_schema_provider("local")
        recovery_report: list = []
        change_report_out: list = []
        wf = from_ui(payload["graph"])
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


# ── Demo scenario helpers (VIBECOMFY_DEMO_PICKER gated) ───────────────────


def _demo_repo_root() -> Path:
    """Return the repository root: vibecomfy/comfy_nodes/agent/routes.py → 3 parents."""
    return Path(__file__).resolve().parents[3]


def _demo_run_root() -> Path:
    """Legacy test seam for pre-bundle demo fixtures."""
    return _demo_repo_root() / "out" / "agentic" / "agentic-100-20260630-021138"


def _load_demo_asset_bundle() -> dict[str, Any]:
    """Load immutable scenario payloads shipped with the VibeComfy package."""
    path = Path(__file__).resolve().parent / "demo_scenario_assets.json.gz"
    with gzip.open(path, "rt", encoding="utf-8") as handle:
        payload = json.load(handle)
    if not isinstance(payload, dict) or not isinstance(payload.get("scenarios"), dict):
        raise ValueError("Bundled demo scenario asset is invalid")
    return payload


def _load_demo_manifest() -> dict[str, Any]:
    path = _demo_repo_root() / "vibecomfy" / "comfy_nodes" / "agent" / "demo_scenarios.json"
    with path.open("r", encoding="utf-8") as f:
        return json.load(f)


def _is_safe_demo_id(scenario_id: str) -> bool:
    if not isinstance(scenario_id, str) or not scenario_id:
        return False
    if any(sep in scenario_id for sep in ("/", "\\", os.sep)):
        return False
    if scenario_id in (".", "..") or ".." in scenario_id:
        return False
    if scenario_id.startswith("."):
        return False
    return True


def _load_demo_json_file(run_dir: Path, filename: str | None) -> Any:
    if not filename:
        return None
    path = Path(filename)
    if path.is_absolute():
        return None
    path = run_dir / path
    try:
        path.resolve().relative_to(run_dir.resolve())
    except ValueError:
        return None
    if not path.is_file():
        return None
    try:
        return json.loads(path.read_text(encoding="utf-8"))
    except Exception:
        return None


def _is_litegraph_ui_graph(graph: Any) -> bool:
    return isinstance(graph, dict) and isinstance(door_get_nodes(graph), list)


def _is_comfy_api_graph(graph: Any) -> bool:
    if not isinstance(graph, dict) or _is_litegraph_ui_graph(graph):
        return False
    return any(isinstance(value, dict) and "class_type" in value for value in graph.values())


def _convert_demo_api_graph_to_ui(api_graph: Mapping[str, Any]) -> dict[str, Any] | None:
    """Best-effort API→UI fallback for old demo artifacts.

    Compiled ComfyUI API JSON does not carry the author's canvas layout. When
    older scenario runs only have API JSON, this keeps the demo loadable while
    explicitly marking the layout as generated rather than source-authored.
    """
    try:
        from vibecomfy.ingest.normalize import from_api  # noqa: PLC0415
        from vibecomfy.porting.emit.ui import emit_ui_json  # noqa: PLC0415
        from vibecomfy.schema import get_schema_provider  # noqa: PLC0415

        workflow = from_api(dict(api_graph))
        ui_graph = emit_ui_json(workflow, schema_provider=get_schema_provider("local"))
    except Exception:
        return None
    if not isinstance(ui_graph, dict):
        return None
    extra = ui_graph.setdefault("extra", {})
    if isinstance(extra, dict):
        vibe = extra.setdefault("vibecomfy", {})
        if isinstance(vibe, dict):
            vibe["demo_layout_source"] = "generated_from_api"
            vibe["demo_layout_warning"] = (
                "This scenario was archived as ComfyUI API JSON, which has no original canvas positions."
            )
    return ui_graph


def _resolve_request_graph_as_ui(run_dir: Path) -> dict[str, Any] | None:
    request_json = _load_demo_json_file(run_dir, "request.json")
    if not isinstance(request_json, dict):
        return None
    graph = request_json.get("graph")
    if _is_litegraph_ui_graph(graph):
        return copy.deepcopy(graph)
    if _is_comfy_api_graph(graph):
        return _convert_demo_api_graph_to_ui(graph)
    return None


def _resolve_original_graph(
    response_json: Any,
    run_dir: Path,
    run_location: Mapping[str, Any],
) -> dict[str, Any] | None:
    """Load the original UI graph, preferring response.json artifacts mapping."""
    candidates: list[str] = []
    if isinstance(response_json, dict):
        artifacts = response_json.get("artifacts")
        if isinstance(artifacts, dict):
            original_ui = artifacts.get("original_ui")
            if isinstance(original_ui, str):
                candidates.append(original_ui)
    candidates.append(run_location.get("original_ui", "original.ui.json"))
    for filename in candidates:
        data = _load_demo_json_file(run_dir, filename)
        if isinstance(data, dict):
            return data
    request_graph = _resolve_request_graph_as_ui(run_dir)
    if isinstance(request_graph, dict):
        return request_graph
    return None


def _resolve_candidate_graph(
    response_json: Any,
    run_dir: Path,
    run_location: Mapping[str, Any],
) -> dict[str, Any] | None:
    """Resolve candidate graph, preferring curated layout-bearing UI artifacts."""
    if isinstance(response_json, dict):
        artifacts = response_json.get("artifacts")
        if isinstance(artifacts, dict):
            candidate_ui = artifacts.get("candidate_ui")
            if isinstance(candidate_ui, str):
                data = _load_demo_json_file(run_dir, candidate_ui)
                if isinstance(data, dict):
                    return data
    candidate_ui = run_location.get("candidate_ui", "candidate.ui.json")
    data = _load_demo_json_file(run_dir, candidate_ui)
    if isinstance(data, dict):
        return data
    if isinstance(response_json, dict):
        if isinstance(response_json.get("candidate_graph"), dict):
            return response_json["candidate_graph"]
        candidate = response_json.get("candidate")
        if isinstance(candidate, dict) and isinstance(candidate.get("graph"), dict):
            return candidate["graph"]
    return None


def _inherit_demo_layout(
    candidate_graph: dict[str, Any],
    original_graph: Mapping[str, Any],
) -> dict[str, Any]:
    """Preserve baseline canvas placement for unchanged LiteGraph node IDs."""
    if not _is_litegraph_ui_graph(candidate_graph) or not _is_litegraph_ui_graph(original_graph):
        return candidate_graph
    original_nodes = {
        node.get("id"): node
        for node in door_get_nodes(original_graph, [])
        if isinstance(node, Mapping) and node.get("id") is not None
    }
    if not original_nodes:
        return candidate_graph
    out = copy.deepcopy(candidate_graph)
    for node in door_get_nodes(out, []):
        if not isinstance(node, dict):
            continue
        original = original_nodes.get(node.get("id"))
        if not isinstance(original, Mapping):
            continue
        for key in ("pos", "size"):
            if key in original:
                node[key] = copy.deepcopy(original[key])
    return out


def _resolve_demo_scenario(scenario_id: str) -> tuple[dict[str, Any], int]:
    """Load one demo scenario: metadata + original graph + candidate graph."""
    if not _is_safe_demo_id(scenario_id):
        return {"ok": False, "error": "Invalid scenario ID"}, 400

    manifest = _load_demo_manifest()
    scenarios = manifest.get("scenarios", [])
    record = next((s for s in scenarios if s.get("id") == scenario_id), None)
    if record is None:
        return {"ok": False, "error": "Scenario not found"}, 404

    asset_name = record.get("asset")
    if isinstance(asset_name, str) and asset_name:
        try:
            bundle = _load_demo_asset_bundle()
        except FileNotFoundError:
            return {"ok": False, "error": "Scenario asset not found"}, 404
        except Exception as exc:
            return {"ok": False, "error": f"Failed to load scenario asset: {exc}"}, 500
        payload = bundle["scenarios"].get(scenario_id)
        if not isinstance(payload, dict):
            return {"ok": False, "error": "Scenario asset not found"}, 404
        original_graph = payload.get("original_graph")
        candidate_graph = payload.get("candidate_graph")
        if not _is_litegraph_ui_graph(original_graph):
            return {"ok": False, "error": "Bundled original graph is invalid"}, 500
        if not _is_litegraph_ui_graph(candidate_graph):
            return {"ok": False, "error": "Bundled candidate graph is invalid"}, 500
        candidate_graph = _inherit_demo_layout(candidate_graph, original_graph)
        response = payload.get("response")
        if not isinstance(response, dict):
            response = {}
        return {
            "ok": True,
            "scenario": record,
            "source_run_tree": manifest.get("source_run_tree"),
            "original_graph": original_graph,
            "candidate_graph": candidate_graph,
            "agent_reply": response.get("reply") or response.get("message") or "",
            "eligibility": response.get("apply_eligibility") or response.get("eligibility") or {},
            "outcome": response.get("outcome") or {"kind": "candidate"},
            "change_details": response.get("change_details") or {},
            "report": response.get("report") or {},
            "candidate_graph_hash": response.get("candidate_graph_hash"),
            "candidate_structural_graph_hash": response.get("candidate_structural_graph_hash"),
            "session_id": response.get("session_id") or f"demo-{scenario_id}",
            "turn_id": response.get("turn_id") or f"demo-{scenario_id}-turn",
        }, 200

    # Kept only as a test seam for synthetic manifests. Curated production
    # records always name an immutable package asset above.
    run_location = record.get("run_location", {})
    run_dir_name = run_location.get("run_dir")
    if not isinstance(run_dir_name, str) or not run_dir_name:
        return {"ok": False, "error": "Scenario run_location missing"}, 404

    run_root = _demo_run_root()
    run_dir = (run_root / run_dir_name).resolve()
    try:
        run_dir.relative_to(run_root.resolve())
    except ValueError:
        return {"ok": False, "error": "Scenario path escapes run root"}, 404

    response_path = run_dir / run_location.get("response_json", "response.json")
    try:
        response_json = json.loads(response_path.read_text(encoding="utf-8"))
    except FileNotFoundError:
        response_json = None
    except Exception as exc:
        return {"ok": False, "error": f"Failed to load response JSON: {exc}"}, 500

    original_graph = _resolve_original_graph(response_json, run_dir, run_location)
    if original_graph is None:
        return {"ok": False, "error": "Original graph not found"}, 404

    candidate_graph = _resolve_candidate_graph(response_json, run_dir, run_location)
    if candidate_graph is None:
        return {"ok": False, "error": "Candidate graph not found"}, 404
    candidate_graph = _inherit_demo_layout(candidate_graph, original_graph)

    if isinstance(response_json, dict):
        agent_reply = response_json.get("reply") or response_json.get("message") or ""
        eligibility = response_json.get("apply_eligibility") or response_json.get("eligibility") or {}
        outcome = response_json.get("outcome") or {"kind": "candidate"}
        change_details = response_json.get("change_details") or response_json.get("change") or {}
        report = response_json.get("report") or {}
        candidate_graph_hash = response_json.get("candidate_graph_hash")
        candidate_structural_graph_hash = response_json.get("candidate_structural_graph_hash")
        session_id = response_json.get("session_id") or f"demo-{scenario_id}"
        turn_id = response_json.get("turn_id") or f"demo-{scenario_id}-turn"
    else:
        agent_reply = ""
        eligibility = {}
        outcome = {"kind": "candidate"}
        change_details = {}
        report = {}
        candidate_graph_hash = None
        candidate_structural_graph_hash = None
        session_id = f"demo-{scenario_id}"
        turn_id = f"demo-{scenario_id}-turn"

    return {
        "ok": True,
        "scenario": record,
        "source_run_tree": manifest.get("source_run_tree"),
        "original_graph": original_graph,
        "candidate_graph": candidate_graph,
        "agent_reply": agent_reply,
        "eligibility": eligibility,
        "outcome": outcome,
        "change_details": change_details,
        "report": report,
        "candidate_graph_hash": candidate_graph_hash,
        "candidate_structural_graph_hash": candidate_structural_graph_hash,
        "session_id": session_id,
        "turn_id": turn_id,
    }, 200


def _load_demo_scenarios_list() -> tuple[dict[str, Any], int]:
    """Return the curated list without loading large graph files."""
    manifest = _load_demo_manifest()
    return {
        "ok": True,
        "scenarios": list(manifest.get("scenarios", [])),
        "source_run_tree": manifest.get("source_run_tree"),
    }, 200


# ── Agentic replay helpers ───────────────────────────────────────────────────


def _agentic_replay_root() -> Path:
    """Return the root containing persisted agentic run evidence."""
    return _demo_repo_root() / "out" / "agentic"


def _is_agentic_replay_enabled() -> bool:
    return _agentic_replay_service.is_enabled()


def _is_safe_replay_id(value: str) -> bool:
    return _agentic_replay_service.is_safe_replay_id(value)


def _list_agentic_replay_runs() -> tuple[dict[str, Any], int]:
    return _agentic_replay_service.list_runs(
        _agentic_replay_root(),
        enabled=_is_agentic_replay_enabled(),
    )


def _list_agentic_replay_tests(run_id: str) -> tuple[dict[str, Any], int]:
    return _agentic_replay_service.list_tests(
        _agentic_replay_root(),
        run_id,
        enabled=_is_agentic_replay_enabled(),
    )


def _resolve_agentic_replay_scenario(run_id: str, test_id: str) -> tuple[dict[str, Any], int]:
    return _agentic_replay_service.resolve_scenario(
        _agentic_replay_root(),
        run_id,
        test_id,
        enabled=_is_agentic_replay_enabled(),
    )


def _handle_agent_status(params: dict[str, Any] | None = None) -> dict[str, Any]:
    params = params or {}
    route = params.get("route") if isinstance(params.get("route"), str) else None
    model = params.get("model") if isinstance(params.get("model"), str) else None
    _LOGGER.info("/vibecomfy/agent/status request route=%r model=%r", route, model)
    try:
        ready_payload = readiness(route=route, model=model)
    except Exception as exc:
        _LOGGER.exception("/vibecomfy/agent/status readiness() raised an exception")
        raise
    ok = bool(ready_payload.get("ready"))
    raw_provider_error = _provider_status_raw_error(ready_payload)
    user_message = _provider_status_message(
        ready=ok,
        provider_available=bool(ready_payload.get("provider_available")),
        raw_error=raw_provider_error,
        reason=ready_payload.get("reason"),
    )
    provider_status = ProviderStatus(
        provider=str(ready_payload.get("provider") or "arnold"),
        provider_available=bool(ready_payload.get("provider_available")),
        ready=ok,
        model=ready_payload.get("model") if isinstance(ready_payload.get("model"), str) else None,
        route=ready_payload.get("route") if isinstance(ready_payload.get("route"), str) else None,
        message=user_message,
        error=(
            {
                "message": user_message,
                "type": "provider_unavailable",
            }
            if not ok and not ready_payload.get("provider_available")
            else None
        ),
    )
    status: dict[str, Any] = {
        **ready_payload,
        **provider_status.to_dict(),
        "ok": ok,
        "readiness": "ready" if ok else "unavailable",
    }
    if not ok:
        status["reason"] = user_message
        status["message"] = user_message
    if raw_provider_error is not None:
        debug = dict(status.get("debug")) if isinstance(status.get("debug"), Mapping) else {}
        provider_debug = dict(debug.get("provider_status")) if isinstance(debug.get("provider_status"), Mapping) else {}
        provider_debug["raw_error"] = raw_provider_error
        debug["provider_status"] = provider_debug
        status["debug"] = debug
    _LOGGER.info(
        "/vibecomfy/agent/status response ready=%s route=%s requested_route=%s route_options=%s",
        status.get("ready"),
        status.get("route"),
        status.get("requested_route"),
        list(status.get("route_options", {}).keys()),
    )
    return status


def _json_hash(payload: Mapping[str, Any]) -> str:
    raw = json.dumps(payload, sort_keys=True, separators=(",", ":"))
    return hashlib.sha256(raw.encode("utf-8")).hexdigest()


def _install_intent_identity(pack: Mapping[str, Any], expected_classes: list[str], validation_mode: str) -> dict[str, Any]:
    return {
        "slug": pack.get("slug"),
        "source": pack.get("source"),
        "version": pack.get("version"),
        "commit": pack.get("commit"),
        "url": pack.get("url"),
        "registry_id": pack.get("registry_id"),
        "expected_classes": expected_classes,
        "validation_mode": validation_mode,
    }


def _install_intent_hash(pack: Mapping[str, Any], expected_classes: list[str], validation_mode: str) -> str:
    return _json_hash(_install_intent_identity(pack, expected_classes, validation_mode))


def _install_route_error(message: str, *, code: str = "validation_error", warnings: list[str] | None = None) -> dict[str, Any]:
    return {
        "ok": False,
        "status": "rejected",
        "error": code,
        "message": message,
        "warnings": list(warnings or ()),
    }


def _request_bool(payload: Mapping[str, Any], *keys: str) -> bool:
    return any(payload.get(key) is True for key in keys)


def _as_nonempty_string(value: Any) -> str | None:
    if isinstance(value, str) and value.strip():
        return value.strip()
    return None


def _coerce_expected_classes(value: Any) -> list[str]:
    if not isinstance(value, list):
        return []
    result: list[str] = []
    seen: set[str] = set()
    for item in value:
        text = _as_nonempty_string(item)
        if text is None or text in seen:
            continue
        seen.add(text)
        result.append(text)
    return result


def _pack_ref_from_install_payload(pack: Mapping[str, Any], repo_url: str):
    from vibecomfy.registry.pack_resolver import PackRef  # noqa: PLC0415

    slug = _as_nonempty_string(pack.get("slug")) or _as_nonempty_string(pack.get("name"))
    if slug is None:
        raise ValueError("package slug or name is required.")
    return PackRef(
        slug=slug,
        source=_as_nonempty_string(pack.get("source")) or "install_request",
        version=_as_nonempty_string(pack.get("version")),
        commit=_as_nonempty_string(pack.get("commit")),
        url=repo_url,
        path=_as_nonempty_string(pack.get("path")),
        name=_as_nonempty_string(pack.get("name")),
        registry_id=_as_nonempty_string(pack.get("registry_id")),
    )


def _fetch_object_info_for_install_validation() -> Mapping[str, Any]:
    """Refresh local ComfyUI object_info after a node-pack install."""
    base_url = os.environ.get("VIBECOMFY_COMFYUI_URL", "http://127.0.0.1:8188").rstrip("/")
    request = urllib.request.Request(f"{base_url}/object_info", headers={"Accept": "application/json"})
    with urllib.request.urlopen(request, timeout=10) as response:  # noqa: S310 - local ComfyUI endpoint.
        payload = json.loads(response.read().decode("utf-8"))
    if not isinstance(payload, Mapping):
        raise ValueError("/object_info returned a non-object payload.")
    return payload


def _validate_installed_pack_classes(expected_classes: list[str], validation_mode: str) -> dict[str, Any]:
    if validation_mode != "class_validatable" or not expected_classes:
        return {
            "validation_status": "validation_skipped",
            "validated": False,
            "missing_classes": expected_classes,
            "present_classes": [],
            "message": "Post-install validation skipped because the proposal is not class-validatable.",
        }
    try:
        object_info = _fetch_object_info_for_install_validation()
    except Exception as exc:
        return {
            "validation_status": "validation_skipped",
            "validated": False,
            "missing_classes": expected_classes,
            "present_classes": [],
            "message": f"Post-install /object_info refresh failed: {type(exc).__name__}: {exc}",
        }
    present = [class_name for class_name in expected_classes if class_name in object_info]
    missing = [class_name for class_name in expected_classes if class_name not in object_info]
    if missing:
        return {
            "validation_status": "restart_required",
            "validated": False,
            "missing_classes": missing,
            "present_classes": present,
            "message": "Installed pack did not appear in /object_info yet; restart ComfyUI, then retry the edit.",
        }
    return {
        "validation_status": "installed",
        "validated": True,
        "missing_classes": [],
        "present_classes": present,
        "message": "Installed pack classes are present in /object_info.",
    }


def _find_reresolved_install_candidate(
    *,
    pack: Mapping[str, Any],
    expected_classes: list[str],
    submitted_hash: str,
) -> Mapping[str, Any] | None:
    from vibecomfy.registry.pack_resolver import resolve_missing_nodes  # noqa: PLC0415

    query = expected_classes[0] if expected_classes else (
        _as_nonempty_string(pack.get("slug")) or _as_nonempty_string(pack.get("name"))
    )
    if query is None:
        return None
    resolution = resolve_missing_nodes(query, query_intent="class_name" if expected_classes else None)
    for candidate in resolution.candidates:
        candidate_payload = candidate.to_dict()
        if candidate_payload.get("stable_install_hash") == submitted_hash:
            return candidate_payload
    return None


def _handle_node_pack_install(payload: Any) -> dict[str, Any]:
    if not isinstance(payload, Mapping):
        return _install_route_error("Request body must be a JSON object.")
    candidate = payload.get("candidate") if isinstance(payload.get("candidate"), Mapping) else payload
    pack = candidate.get("pack") if isinstance(candidate.get("pack"), Mapping) else None
    if pack is None:
        return _install_route_error("package pack metadata is required.")
    package_name = _as_nonempty_string(pack.get("slug")) or _as_nonempty_string(pack.get("name"))
    repo_url = (
        _as_nonempty_string(payload.get("repo_url"))
        or _as_nonempty_string(candidate.get("repo_url"))
        or _as_nonempty_string(pack.get("url"))
    )
    if package_name is None:
        return _install_route_error("package slug or name is required.")
    if repo_url is None:
        return _install_route_error("repo URL is required.")

    expected_classes = _coerce_expected_classes(candidate.get("expected_classes"))
    validation_mode = _as_nonempty_string(candidate.get("validation_mode")) or "evidence_only"
    if validation_mode != "class_validatable":
        return _install_route_error(
            "Install proposals from the normal action must be class_validatable; evidence_only proposals cannot be installed from this path.",
            code="evidence_only_rejected",
        )
    if not expected_classes:
        return _install_route_error(
            "Install proposals from the normal action require non-empty expected_classes.",
            code="evidence_only_rejected",
        )
    submitted_hash = _as_nonempty_string(payload.get("stable_install_hash")) or _as_nonempty_string(
        candidate.get("stable_install_hash")
    )
    if submitted_hash is None:
        return _install_route_error("stable_install_hash is required.")
    if not _request_bool(payload, "user_confirmed", "confirmed", "confirmed_install_intent"):
        return _install_route_error("explicit user-confirmed install intent is required.", code="confirmation_required")

    warnings: list[str] = []
    local_hash = _install_intent_hash(pack, expected_classes, validation_mode)
    if submitted_hash != local_hash:
        try:
            reresolved = _find_reresolved_install_candidate(
                pack=pack,
                expected_classes=expected_classes,
                submitted_hash=submitted_hash,
            )
        except Exception as exc:
            reresolved = None
            warnings.append(f"Install proposal re-resolution failed: {type(exc).__name__}: {exc}")
        if reresolved is not None:
            reresolved_pack = reresolved.get("pack") if isinstance(reresolved.get("pack"), Mapping) else {}
            reresolved_classes = _coerce_expected_classes(reresolved.get("expected_classes"))
            reresolved_mode = _as_nonempty_string(reresolved.get("validation_mode")) or "evidence_only"
            if _install_intent_identity(reresolved_pack, reresolved_classes, reresolved_mode) != _install_intent_identity(
                pack, expected_classes, validation_mode
            ):
                return _install_route_error(
                    "install proposal hash resolves to a different package identity; re-run node resolution before installing.",
                    code="stable_identity_mismatch",
                    warnings=warnings,
                )
        warnings.append("stable_install_hash did not match the submitted identity; using the current stable package identity.")

    try:
        pack_ref = _pack_ref_from_install_payload(pack, repo_url)
    except ValueError as exc:
        return _install_route_error(str(exc))

    from vibecomfy.node_packs import install_pack  # noqa: PLC0415

    try:
        result = install_pack(
            name=package_name,
            repo=repo_url,
            pack_ref=pack_ref,
            checkout_ref=_as_nonempty_string(pack.get("version")) or _as_nonempty_string(pack.get("commit")),
            expected_commit=_as_nonempty_string(pack.get("commit")),
        )
    except CapabilityFenceError as exc:
        response = _install_route_error(
            "Install blocked by capability gate.",
            code="capability_gate_rejected",
            warnings=warnings,
        )
        response["gate_detail"] = exc.detail
        return response
    install_ok = result.status in {"installed", "refreshed"}
    validation = (
        _validate_installed_pack_classes(expected_classes, validation_mode)
        if install_ok
        else {
            "validation_status": "validation_skipped",
            "validated": False,
            "missing_classes": expected_classes,
            "present_classes": [],
            "message": "Post-install validation skipped because installation did not complete.",
        }
    )
    return {
        "ok": install_ok,
        "status": result.status,
        "install_status": result.status,
        **validation,
        "name": result.name,
        "git_commit_sha": result.git_commit_sha,
        "error": result.error,
        "expected_classes": expected_classes,
        "validation_mode": validation_mode,
        "stable_install_hash": local_hash,
        "warnings": warnings,
    }


def _provider_status_raw_error(payload: Mapping[str, Any]) -> str | None:
    for key in ("error", "reason", "detail", "message"):
        value = payload.get(key)
        if isinstance(value, str) and value.strip():
            return value.strip()
    return None


def _provider_status_message(
    *,
    ready: bool,
    provider_available: bool,
    raw_error: str | None,
    reason: Any,
) -> str:
    if ready:
        return "Provider ready."
    if not provider_available:
        return "The model provider is unavailable. Check local provider configuration."
    if isinstance(reason, str) and reason.strip():
        return reason.strip()
    if raw_error:
        return "The model provider is not ready."
    return "The model provider is not ready."


def _failure_response(stage: str, failure: Any) -> dict[str, Any]:
    """Build the single agent-edit failure envelope shared by every route family.

    Both the executor submit family and the legacy test-only handlers route
    every failure through this one builder, so the two families emit the same
    wire envelope: the v1 ``FailureEnvelope.to_dict()`` payload merged with the
    product envelope fields, contract-stamped for the stage, and
    stale-recovery-normalised exactly as the executor path always was.
    """
    serialized = _to_serializable(failure)
    if isinstance(failure, AgentError):
        serialized.update(product_failure_envelope_fields(failure))
    try:
        stamped = ensure_agent_edit_response_contract(serialized, stage=stage)
    except Exception as exc:
        _LOGGER.error(
            "Agent-edit response contract validation failed for stage %s: %s",
            stage,
            type(exc).__name__,
        )
        contract_failure = failure_envelope(
            FailureKind.VALIDATION_ERROR,
            stage,
            agent_failure_context={
                "explanation": "The agent response failed public contract validation.",
                "contract_error": type(exc).__name__,
            },
        )
        stamped = contract_failure.to_dict()
        stamped.update(product_failure_envelope_fields(contract_failure))
    return _ensure_stale_recovery(stamped)


def _handle_agent_edit(
    payload: Any,
    *,
    schema_provider: Any = None,
    deepseek_client: Any = None,
    session_root: Any = None,
    client_id: str | None = None,
) -> dict[str, Any]:
    try:
        result = handle_agent_edit(
            payload,
            schema_provider=schema_provider,
            deepseek_client=deepseek_client,
            session_root=Path(session_root) if session_root is not None else None,
            client_id=client_id,
        )
    except Exception as exc:
        return _failure_response("route", classify_failure("route", exc))
    if isinstance(result, dict):
        return _sanitize_clarify_payload(result)
    failure = failure_envelope(
        FailureKind.VALIDATION_ERROR,
        "route",
        agent_failure_context={"explanation": "handle_agent_edit returned a non-dict result."},
    )
    return _failure_response("route", failure)


def _executor_request_payload(payload: dict[str, Any]) -> dict[str, Any]:
    request_payload = dict(payload)
    if "query" not in request_payload and isinstance(request_payload.get("task"), str):
        request_payload["query"] = request_payload["task"]
    route = str(request_payload.get("route") or "").strip().lower()
    route_profile = {
        "openai-codex": "openai",
        "codex": "openai",
        "openrouter": "openrouter",
        "anthropic": "anthropic",
        "claude": "anthropic",
        "opensource": "opensource",
    }.get(route)
    if route_profile is not None:
        # A recognized provider route owns its executor profile.  Do not let a
        # stale or custom client claim OpenRouter while selecting another
        # provider's stages underneath it.
        request_payload["profile"] = route_profile
    elif "profile" not in request_payload:
        request_payload["profile"] = "default"
    return request_payload


def _handle_agent_executor_submit(
    payload: Any,
    *,
    client_id: str | None = None,
) -> tuple[dict[str, Any], int]:
    from vibecomfy.executor.contracts import ExecutorRequest  # noqa: PLC0415
    from vibecomfy.executor.core import run_executor  # noqa: PLC0415

    if not isinstance(payload, dict):
        return (
            _failure_response(
                "agent_executor",
                failure_envelope(
                    FailureKind.MISSING_REQUIRED_FIELD,
                    "agent_executor",
                    agent_failure_context={"explanation": "Request body must be a JSON object."},
                ),
            ),
            400,
        )

    # ── T2: Normalise session_id before it reaches ExecutorRequest ────────
    # ExecutorRequest.from_payload() accepts a raw session_id string, but the
    # route layer must sanitise it first so that no path-component attack can
    # be embedded in a durable turn allocation or response-writer path downstream.
    safe_payload = dict(payload)
    raw_session_id = safe_payload.get("session_id")
    if isinstance(raw_session_id, str):
        safe_payload["session_id"] = normalize_session_id(raw_session_id)
    elif "session_id" in safe_payload:
        # Non-string sentinel values (null, numbers, etc.) → strip entirely.
        del safe_payload["session_id"]

    try:
        request = ExecutorRequest.from_payload(_executor_request_payload(safe_payload))
    except Exception as exc:
        return _failure_response("agent_executor", classify_failure("agent_executor", exc)), 400
    result = run_executor(request, client_id=client_id)
    response = _serialize_executor_result(result)
    # T7/T9: Durable turn writer for executor-only non-applyable turns
    # (clarify/inspect/respond/research).  When the executor skips implementation,
    # no durable response is produced by handle_agent_edit.  Allocate a lightweight
    # turn and write request/response/chat artifacts so the frontend can rehydrate
    # from canonical durable storage (SD1, SD2).
    response = _maybe_write_executor_only_durable_turn(
        response=response,
        result=result,
        payload=safe_payload,
        request=request,
    )
    status = 200 if response.get("ok") is not False else 500
    return response, status


def _maybe_write_executor_only_durable_turn(
    *,
    response: dict[str, Any],
    result: Any,
    payload: dict[str, Any],
    request: Any,
) -> dict[str, Any]:
    return maybe_write_executor_only_durable_turn(
        response=response,
        result=result,
        payload=payload,
        request=request,
        session_root=_SESSION_ROOT,
        allocate_turn_func=_session_allocate_turn,
        record_idempotent_response_func=_session_record_idempotent_response,
    )


def _session_root_path(session_root: Any) -> Path:
    return Path(session_root) if session_root is not None else _SESSION_ROOT


def _coerce_chat_max_messages(raw_value: Any) -> int:
    if isinstance(raw_value, str):
        value = raw_value.strip()
        if not value:
            return DEFAULT_CHAT_DISPLAY_MESSAGES
        try:
            parsed = int(value)
        except ValueError:
            return DEFAULT_CHAT_DISPLAY_MESSAGES
    elif isinstance(raw_value, int):
        parsed = raw_value
    else:
        return DEFAULT_CHAT_DISPLAY_MESSAGES
    if parsed <= 0:
        return DEFAULT_CHAT_DISPLAY_MESSAGES
    return min(parsed, DEFAULT_CHAT_DISPLAY_MESSAGES)


def _handle_agent_edit_chat(
    payload: Any,
    *,
    session_root: Any = None,
) -> dict[str, Any]:
    if not isinstance(payload, dict):
        return _failure_response(
            "chat",
            failure_envelope(
                FailureKind.MISSING_REQUIRED_FIELD,
                "chat",
                agent_failure_context={"explanation": "Request body must be a JSON object."},
            ),
        )
    raw_session_id = payload.get("session_id")
    max_messages = _coerce_chat_max_messages(payload.get("max_messages"))
    # ── T2: Normalise session_id before it reaches read_session_chat.
    session_id = normalize_session_id(raw_session_id) if isinstance(raw_session_id, str) else None
    try:
        result = read_session_chat(
            Path(session_root) if session_root is not None else _SESSION_ROOT,
            session_id,
            max_messages=max_messages,
        )
    except Exception as exc:
        return _failure_response("chat", classify_failure("chat", exc))
    if not isinstance(result, dict):
        return _failure_response(
            "chat",
            failure_envelope(
                FailureKind.VALIDATION_ERROR,
                "chat",
                agent_failure_context={"explanation": "read_session_chat returned a non-dict result."},
            ),
        )
    latest_candidate = result.get("latest_candidate")
    outcome = (
        latest_candidate.get("outcome")
        if isinstance(latest_candidate, Mapping) and isinstance(latest_candidate.get("outcome"), Mapping)
        else {"kind": "noop"}
    )
    raw_response = dict(result)
    raw_response["ok"] = True
    response = public_chat_rehydrate_payload(raw_response)
    response["outcome"] = dict(outcome) if isinstance(outcome, Mapping) else {"kind": "noop"}
    return response


def _json_response_writer(path: Path):  # type: ignore[no-untyped-def]
    def _write(response: dict[str, Any]) -> Path:
        path.parent.mkdir(parents=True, exist_ok=True)
        path.write_text(
            json.dumps(response, indent=2, sort_keys=True) + "\n",
            encoding="utf-8",
        )
        return path

    return _write


def _stamp_action_success(
    response: Mapping[str, Any],
    *,
    eligibility_reason: str,
    eligibility_message: str,
) -> dict[str, Any]:
    stamped = dict(response)
    stamped["outcome"] = {"kind": "noop"}
    stamped = build_legacy_agent_edit_v1(
        {
            **stamped,
            "eligibility": ApplyEligibility(
                applyable=False,
                reason=eligibility_reason,
                message=eligibility_message,
            ).to_dict(),
            "canvas_apply_allowed": False,
            "queue_allowed": False,
        }
    )
    return ensure_agent_edit_response_contract(stamped, stage=str(stamped.get("action") or "route"))


def _ensure_stale_recovery(response: Mapping[str, Any]) -> dict[str, Any]:
    if response.get("kind") != FailureKind.STALE_STATE_MISMATCH.value:
        return dict(response)
    if isinstance(response.get("rebaseline_recovery"), Mapping):
        return dict(response)
    agent_failure_context = response.get("agent_failure_context")
    issues = []
    if isinstance(agent_failure_context, Mapping) and isinstance(agent_failure_context.get("issues"), list):
        issues = [
            dict(issue)
            for issue in agent_failure_context["issues"]
            if isinstance(issue, Mapping)
        ]
    reason = (
        agent_failure_context.get("reason")
        if isinstance(agent_failure_context, Mapping) and isinstance(agent_failure_context.get("reason"), str)
        else "stale_state_recovery"
    )
    recovery = {
        "action": "rebaseline",
        "endpoint": "/vibecomfy/agent-edit/rebaseline",
        "reason": reason,
        "last_known_baseline_graph_hash": response.get("expected_baseline_graph_hash"),
        "submit_structural_graph_hash": response.get("submit_structural_graph_hash"),
    }
    if issues:
        issues[0].setdefault("rebaseline_recovery", dict(recovery))
    else:
        issues = [
            {
                "message": (
                    agent_failure_context.get("explanation")
                    if isinstance(agent_failure_context, Mapping)
                    else response.get("message")
                ),
                "rebaseline_recovery": dict(recovery),
            }
        ]
    failure_context = dict(agent_failure_context) if isinstance(agent_failure_context, Mapping) else {}
    failure_context["issues"] = issues
    stamped = dict(response)
    stamped["agent_failure_context"] = failure_context
    stamped["rebaseline_recovery"] = dict(recovery)
    outcome = stamped.get("outcome")
    if isinstance(outcome, Mapping):
        outcome_payload = dict(outcome)
        outcome_payload["rebaseline_recovery"] = dict(recovery)
        stamped["outcome"] = outcome_payload
    return stamped


def _normalize_action_response(
    result: Any,
    *,
    stage: str,
    success_reason: str | None = None,
    success_message: str | None = None,
) -> dict[str, Any]:
    serialized = _to_serializable(result)
    if serialized.get("ok") is True:
        if success_reason is not None and success_message is not None:
            return _stamp_action_success(
                serialized,
                eligibility_reason=success_reason,
                eligibility_message=success_message,
            )
        return serialized
    return _failure_response(stage, serialized)


def _audit_path_for_action(session_root: Path, session_id: str, turn_id: str, action: str) -> Path:
    return session_dir_for(session_root, session_id) / "turns" / turn_id / f"{action}_audit" / "audit.json"


def _attach_action_audit(
    response: dict[str, Any],
    *,
    request_payload: Mapping[str, Any],
    session_root: Path,
    action: str,
) -> dict[str, Any]:
    session_id = response.get("session_id")
    turn_id = response.get("turn_id")
    if not isinstance(session_id, str) or not isinstance(turn_id, str):
        return response
    audit_path = _audit_path_for_action(session_root, session_id, turn_id, action)
    if not audit_path.is_file():
        write_audit(
            audit_path.parent,
            context=TurnContext(
                session_id=session_id,
                turn_id=turn_id,
                baseline_turn_id=response.get("baseline_turn_id")
                if isinstance(response.get("baseline_turn_id"), str)
                else None,
            ),
            turn_state=response.get("accepted_state") if isinstance(response.get("accepted_state"), str) else None,
            response=response,
            artifacts={"request": dict(request_payload)},
            metadata={"action": action},
        )
    result = dict(response)
    result["audit_ref"] = artifact_ref_for_path(audit_path).to_dict()
    return result


def _handle_agent_edit_accept(
    payload: Any,
    *,
    session_root: Any = None,
) -> dict[str, Any]:
    if not isinstance(payload, dict):
        return _failure_response(
            "accept",
            failure_envelope(
                FailureKind.MISSING_REQUIRED_FIELD,
                "accept",
                agent_failure_context={"explanation": "Request body must be a JSON object."},
            ),
        )
    turn_id = payload.get("turn_id")
    if not isinstance(turn_id, str) or not turn_id.strip():
        return _failure_response(
            "accept",
            failure_envelope(
                FailureKind.MISSING_REQUIRED_FIELD,
                "accept",
                agent_failure_context={"explanation": "turn_id is required."},
            ),
        )
    root = _session_root_path(session_root)
    raw_session_id = payload.get("session_id")
    # ── T2: Normalise session_id through the authoritative normaliser before
    # it reaches durable accept_turn() or the response-writer path builder.
    session_id = normalize_session_id(raw_session_id) if isinstance(raw_session_id, str) else ""
    safe_turn_id = normalize_path_component(turn_id) if isinstance(turn_id, str) and turn_id.strip() else turn_id
    try:
        result = accept_turn(
            session_root=root,
            session_id=session_id,
            turn_id=turn_id,
            client_graph_hash=payload.get("client_graph_hash")
            if isinstance(payload.get("client_graph_hash"), str)
            else None,
            request_payload=payload,
            idempotency_key=payload.get("idempotency_key")
            if isinstance(payload.get("idempotency_key"), str)
            else None,
            response_writer=_json_response_writer(root / session_id / "turns" / safe_turn_id / "accept_response.json")
            if session_id
            else None,
        )
    except Exception as exc:
        return _failure_response("accept", classify_failure("accept", exc))
    serialized = _normalize_action_response(
        result,
        stage="accept",
        success_reason="superseded",
        success_message="This candidate has been superseded.",
    )
    if serialized.get("ok") is True:
        try:
            return _attach_action_audit(
                serialized,
                request_payload=payload,
                session_root=root,
                action="accept",
            )
        except Exception as exc:
            return _failure_response("audit", classify_failure("audit", exc))
    return serialized


def _handle_agent_edit_reject(
    payload: Any,
    *,
    session_root: Any = None,
) -> dict[str, Any]:
    if not isinstance(payload, dict):
        return _failure_response(
            "reject",
            failure_envelope(
                FailureKind.MISSING_REQUIRED_FIELD,
                "reject",
                agent_failure_context={"explanation": "Request body must be a JSON object."},
            ),
        )
    turn_id = payload.get("turn_id")
    if not isinstance(turn_id, str) or not turn_id.strip():
        return _failure_response(
            "reject",
            failure_envelope(
                FailureKind.MISSING_REQUIRED_FIELD,
                "reject",
                agent_failure_context={"explanation": "turn_id is required."},
            ),
        )
    root = _session_root_path(session_root)
    raw_session_id = payload.get("session_id")
    # ── T2: Normalise session_id through the authoritative normaliser before
    # it reaches durable reject_turn() or the response-writer path builder.
    session_id = normalize_session_id(raw_session_id) if isinstance(raw_session_id, str) else ""
    safe_turn_id = normalize_path_component(turn_id) if isinstance(turn_id, str) and turn_id.strip() else turn_id
    reject_idempotency_key = (
        payload.get("idempotency_key")
        if isinstance(payload.get("idempotency_key"), str)
        else None
    )
    reject_response_name = "reject_response.json"
    if reject_idempotency_key:
        key_digest = hashlib.sha256(reject_idempotency_key.encode("utf-8")).hexdigest()[:16]
        reject_response_name = f"reject_response.{key_digest}.json"
    try:
        result = reject_turn(
            session_root=root,
            session_id=session_id,
            turn_id=turn_id,
            client_graph_hash=payload.get("client_graph_hash")
            if isinstance(payload.get("client_graph_hash"), str)
            else None,
            request_payload=payload,
            idempotency_key=reject_idempotency_key,
            response_writer=_json_response_writer(
                root / session_id / "turns" / safe_turn_id / reject_response_name
            )
            if session_id
            else None,
        )
    except Exception as exc:
        return _failure_response("reject", classify_failure("reject", exc))
    serialized = _normalize_action_response(
        result,
        stage="reject",
        success_reason="superseded",
        success_message="This candidate has been superseded.",
    )
    if serialized.get("ok") is True:
        try:
            return _attach_action_audit(
                serialized,
                request_payload=payload,
                session_root=root,
                action="reject",
            )
        except Exception as exc:
            return _failure_response("audit", classify_failure("audit", exc))
    return serialized


def _handle_agent_edit_rebaseline(
    payload: Any,
    *,
    session_root: Any = None,
) -> dict[str, Any]:
    if not isinstance(payload, dict):
        return _failure_response(
            "rebaseline",
            failure_envelope(
                FailureKind.MISSING_REQUIRED_FIELD,
                "rebaseline",
                agent_failure_context={"explanation": "Request body must be a JSON object."},
            ),
        )
    raw_session_id = payload.get("session_id")
    # ── T2: Normalise session_id before it reaches durable rebaseline_session.
    session_id = normalize_session_id(raw_session_id) if isinstance(raw_session_id, str) else ""
    try:
        result = rebaseline_session(
            session_root=_session_root_path(session_root),
            session_id=session_id,
            request_payload=payload,
            idempotency_key=payload.get("idempotency_key")
            if isinstance(payload.get("idempotency_key"), str)
            else None,
        )
    except Exception as exc:
        return _failure_response("rebaseline", classify_failure("rebaseline", exc))
    return _normalize_action_response(
        result,
        stage="rebaseline",
        success_reason="no_candidate",
        success_message="No candidate is available to apply.",
    )


def _handle_agent_edit_audit(
    payload: Any,
    *,
    session_root: Any = None,
) -> dict[str, Any]:
    if not isinstance(payload, dict):
        return _failure_response(
            "audit",
            failure_envelope(
                FailureKind.MISSING_REQUIRED_FIELD,
                "audit",
                agent_failure_context={"explanation": "Request body must be a JSON object."},
            ),
        )
    raw_session_id = payload.get("session_id")
    if not isinstance(raw_session_id, str) or not raw_session_id.strip():
        return _failure_response(
            "audit",
            failure_envelope(
                FailureKind.MISSING_REQUIRED_FIELD,
                "audit",
                agent_failure_context={"explanation": "session_id is required."},
            ),
        )
    raw_turn_id = payload.get("turn_id")
    if not isinstance(raw_turn_id, str) or not raw_turn_id.strip():
        return _failure_response(
            "audit",
            failure_envelope(
                FailureKind.MISSING_REQUIRED_FIELD,
                "audit",
                agent_failure_context={"explanation": "turn_id is required."},
            ),
        )
    action = payload.get("action")
    if action not in {"accept", "reject", "rebaseline"}:
        return _failure_response(
            "audit",
            failure_envelope(
                FailureKind.MISSING_REQUIRED_FIELD,
                "audit",
                agent_failure_context={"explanation": "action must be one of accept, reject, or rebaseline."},
            ),
        )
    # ── T2: Normalise session_id and turn_id before path construction.
    session_id = normalize_session_id(raw_session_id)
    turn_id = normalize_path_component(raw_turn_id)
    audit_path = _audit_path_for_action(_session_root_path(session_root), session_id, turn_id, action)
    try:
        body = audit_path.read_bytes()
    except OSError as exc:
        return _failure_response("audit", classify_failure("audit", exc))
    return {
        "ok": True,
        "headers": {
            "Content-Type": "application/json",
            "Content-Disposition": f'attachment; filename="{session_id}-{turn_id}-{action}_audit.json"',
            "X-Content-Type-Options": "nosniff",
        },
        "body": body,
    }





def _handle_agent_credentials(
    payload: Any,
    *,
    env_path: Any = None,
) -> dict[str, Any]:
    if not isinstance(payload, dict):
        return _failure_response(
            "credentials",
            failure_envelope(
                FailureKind.MISSING_REQUIRED_FIELD,
                "credentials",
                agent_failure_context={"explanation": "Request body must be a JSON object."},
            ),
        )
    try:
        return handle_credential_submission(
            payload,
            env_path=Path(env_path) if env_path is not None else None,
        )
    except Exception as exc:
        return _failure_response("ingest", classify_failure("ingest", exc))


def _agent_settings_path(path: Any = None) -> Path:
    if path is not None:
        return Path(path)
    configured = os.environ.get("VIBECOMFY_AGENT_SETTINGS_PATH")
    if configured:
        return Path(configured).expanduser()
    return Path.home() / ".vibecomfy" / "agent_settings.json"


def _load_agent_settings(*, settings_path: Any = None) -> dict[str, Any]:
    path = _agent_settings_path(settings_path)
    try:
        data = json.loads(path.read_text(encoding="utf-8"))
    except FileNotFoundError:
        data = {}
    except Exception:
        _LOGGER.exception("Failed to read VibeComfy agent settings from %s", path)
        data = {}
    if not isinstance(data, dict):
        data = {}
    return {
        "research_contribution_enabled": bool(data.get("research_contribution_enabled")),
        "research_contribution_last_trigger": data.get("research_contribution_last_trigger"),
    }


def _save_agent_settings(settings: Mapping[str, Any], *, settings_path: Any = None) -> dict[str, Any]:
    current = _load_agent_settings(settings_path=settings_path)
    if "research_contribution_enabled" in settings:
        current["research_contribution_enabled"] = bool(settings.get("research_contribution_enabled"))
    if "research_contribution_last_trigger" in settings:
        current["research_contribution_last_trigger"] = settings.get("research_contribution_last_trigger")
    path = _agent_settings_path(settings_path)
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(json.dumps(current, indent=2, sort_keys=True) + "\n", encoding="utf-8")
    return current


def _handle_agent_settings_get(*, settings_path: Any = None) -> dict[str, Any]:
    settings = _load_agent_settings(settings_path=settings_path)
    return {"ok": True, **settings}


def _handle_agent_settings_post(payload: Any, *, settings_path: Any = None) -> dict[str, Any]:
    if not isinstance(payload, dict):
        return _failure_response(
            "agent_settings",
            failure_envelope(
                FailureKind.MISSING_REQUIRED_FIELD,
                "agent_settings",
                agent_failure_context={"explanation": "Request body must be a JSON object."},
            ),
        )
    settings = _save_agent_settings(payload, settings_path=settings_path)
    return {"ok": True, **settings}


def _run_research_contribution_pipeline(*, runner: Any = None) -> dict[str, Any]:
    repo_root = Path(__file__).resolve().parents[3]
    command = [
        sys.executable,
        str(repo_root / "scripts" / "pipeline_orchestrate.py"),
        "--upload",
    ]
    popen = runner or subprocess.Popen
    process = popen(
        command,
        cwd=str(repo_root),
        stdout=subprocess.DEVNULL,
        stderr=subprocess.DEVNULL,
        start_new_session=True,
    )
    return {
        "pid": getattr(process, "pid", None),
        "command": command,
        "cwd": str(repo_root),
    }


def _handle_research_contribution_run(
    payload: Any = None,
    *,
    settings_path: Any = None,
    runner: Any = None,
) -> dict[str, Any]:
    settings = _load_agent_settings(settings_path=settings_path)
    if not settings["research_contribution_enabled"]:
        return {
            "ok": True,
            "triggered": False,
            "reason": "research_contribution_disabled",
            **settings,
        }
    try:
        started = _run_research_contribution_pipeline(runner=runner)
    except Exception as exc:
        _LOGGER.exception("Failed to start VibeComfy research contribution pipeline")
        return _failure_response("agent_settings", classify_failure("agent_settings", exc))
    trigger = {"started_at": _utc_now_iso(), **started}
    settings = _save_agent_settings({"research_contribution_last_trigger": trigger}, settings_path=settings_path)
    return {
        "ok": True,
        "triggered": True,
        **settings,
    }


def _utc_now_iso() -> str:
    from datetime import datetime, timezone

    return datetime.now(timezone.utc).replace(microsecond=0).isoformat()




def _handle_vibecomfy_submit_rating(payload: Any) -> tuple[dict[str, Any], int]:
    safe_payload = dict(payload) if isinstance(payload, dict) else payload
    if isinstance(safe_payload, dict):
        raw_session_id = safe_payload.get("session_id")
        raw_turn_id = safe_payload.get("turn_id")
        if isinstance(raw_session_id, str):
            safe_payload["session_id"] = normalize_session_id(raw_session_id)
        if isinstance(raw_turn_id, str):
            safe_payload["turn_id"] = normalize_path_component(raw_turn_id)
        if isinstance(safe_payload.get("session_id"), str) and isinstance(safe_payload.get("turn_id"), str):
            safe_payload["response_id"] = f"{safe_payload['session_id']}/{safe_payload['turn_id']}"
    result, status = submit_hivemind_feedback(safe_payload)
    if result.get("ok") is True and 200 <= status < 300:
        return result, 201
    return result, status


def _to_serializable(result: Any) -> Any:
    """Convert a FailureEnvelope/dataclass result to a plain dict for JSON."""
    if result is None:
        return {}
    if isinstance(result, dict):
        return result
    if hasattr(result, "to_dict") and callable(result.to_dict):
        return result.to_dict()
    return {"error": "Non-serializable result", "repr": repr(result)}


def register_agent_edit_routes(app) -> None:
    """Register the /vibecomfy/agent-edit/* routes on a ComfyUI PromptServer *app*.

    Includes the legacy POST /agent/edit alias for backward compatibility.
    This function is a no-op when ``VIBECOMFY_HEADLESS=1`` is set in the
    environment, so importing this module outside a ComfyUI server does not
    trigger ``aiohttp`` or ``server`` side effects.

    Parameters
    ----------
    app:
        A ComfyUI ``PromptServer`` instance whose ``.routes`` attribute exposes
        an ``aiohttp.RouteTableDef``.
    """
    from pathlib import Path as _Path  # noqa: PLC0415
    from aiohttp import web as _web  # noqa: PLC0415
    from .edit import (  # noqa: PLC0415
        _SESSION_ROOT as _EDIT_SESSION_ROOT,
        handle_agent_edit,
        read_session_bundle,
        read_session_chat,
        read_session_json,
    )
    from .session import (  # noqa: PLC0415
        accept_turn,
        finalize_turn_transaction as _session_finalize_turn_transaction,
        normalize_session_id as _safe_session_id,
        prepare_turn_transaction as _session_prepare_turn_transaction,
        rebaseline_session,
        reconcile_turn_transactions as _session_reconcile_turn_transactions,
        rollback_turn_transaction as _session_rollback_turn_transaction,
    )
    from ._frag_session_bundle import (  # noqa: PLC0415
        recover_session_for_workflow,
    )
    from .contracts import (
        FailureKind as _FK,
        classify_failure as _classify_failure,
        ensure_agent_edit_response_contract as _ensure_contract,
        failure_envelope as _failure_envelope,
    )

    _SESSION_ROOT = _Path(_EDIT_SESSION_ROOT)

    def _client_id_from_payload(payload: Any) -> str | None:
        cid = payload.get("client_id") if isinstance(payload, dict) else None
        if isinstance(cid, str) and cid.strip():
            return cid
        return None

    def _session_id_from_query(request) -> str:  # type: ignore[no-untyped-def]
        return _safe_session_id(request.query.get("session_id"))

    def _json_error(message: str, stage: str = "agent_edit", status: int = 400):  # type: ignore[no-untyped-def]
        return _web.json_response(
            _ensure_contract(
                _failure_envelope(
                    _FK.MISSING_REQUIRED_FIELD,
                    stage,
                    agent_failure_context={"explanation": message},
                ).to_dict(),
                stage=stage,
            ),
            status=status,
        )

    @app.routes.post("/vibecomfy/agent-edit")
    async def _agent_edit_route(request):  # type: ignore[no-untyped-def]
        try:
            payload = await request.json()
        except Exception as exc:
            return _json_error(f"Request body must be valid JSON: {exc}", stage="agent_edit")
        if not isinstance(payload, dict):
            return _json_error("Request body must be a JSON object.", stage="agent_edit")
        try:
            result, status = await asyncio.to_thread(
                _handle_agent_executor_submit,
                payload,
                client_id=_client_id_from_payload(payload),
            )
        except Exception as exc:
            failure = _classify_failure("agent_edit", exc)
            return _web.json_response(
                _ensure_contract(failure.to_dict(), stage="agent_edit"),
                status=500,
            )
        if not isinstance(result, dict):
            return _json_error("run_executor returned a non-dict result.", stage="agent_edit", status=500)
        if result.get("status") == "error":
            return _web.json_response(result, status=400)
        return _web.json_response(result, status=status)

    @app.routes.post("/vibecomfy/agent-executor")
    async def _agent_executor_route(request):  # type: ignore[no-untyped-def]
        try:
            payload = await request.json()
        except Exception as exc:
            return _json_error(f"Request body must be valid JSON: {exc}", stage="agent_executor")
        if not isinstance(payload, dict):
            return _json_error("Request body must be a JSON object.", stage="agent_executor")
        try:
            result, status = await asyncio.to_thread(
                _handle_agent_executor_submit,
                payload,
                client_id=_client_id_from_payload(payload),
            )
        except Exception as exc:
            failure = _classify_failure("agent_executor", exc)
            return _web.json_response(
                _ensure_contract(failure.to_dict(), stage="agent_executor"),
                status=500,
            )
        return _web.json_response(result, status=status)

    @app.routes.post("/agent/edit")
    async def _legacy_agent_edit_route(request):  # type: ignore[no-untyped-def]
        try:
            payload = await request.json()
        except Exception as exc:
            return _json_error(f"Request body must be valid JSON: {exc}", stage="agent_edit")
        if not isinstance(payload, dict):
            return _json_error("Request body must be a JSON object.", stage="agent_edit")
        try:
            result, status = await asyncio.to_thread(
                _handle_agent_executor_submit,
                payload,
                client_id=_client_id_from_payload(payload),
            )
        except Exception as exc:
            failure = _classify_failure("agent_edit", exc)
            return _web.json_response(
                _ensure_contract(failure.to_dict(), stage="agent_edit"),
                status=500,
            )
        if not isinstance(result, dict):
            return _json_error("run_executor returned a non-dict result.", stage="agent_edit", status=500)
        if result.get("status") == "error":
            return _web.json_response(result, status=400)
        return _web.json_response(result, status=status, headers={"X-VibeComfy-Legacy-Route": "true"})

    # ── Named temporary bridge: /vibecomfy/agent-edit/accept → /finalize ──
    # Deletion condition: remove when every live browser client posts directly
    # to /vibecomfy/agent-edit/finalize for V2 applyable turns for one full
    # release cycle (tracked via per-session accept_bridge_v2_count in session.py).
    @app.routes.post("/vibecomfy/agent-edit/accept")
    async def _agent_edit_accept_route(request):  # type: ignore[no-untyped-def]
        try:
            payload = await request.json()
        except Exception as exc:
            return _json_error(f"Request body must be valid JSON: {exc}", stage="accept")
        if not isinstance(payload, dict):
            return _json_error("Request body must be a JSON object.", stage="accept")
        session_id = _safe_session_id(payload.get("session_id"))
        turn_id = payload.get("turn_id")
        if not isinstance(turn_id, str) or not turn_id.strip():
            return _json_error("turn_id is required.", stage="accept")
        try:
            result = await asyncio.to_thread(
                accept_turn,
                session_root=_SESSION_ROOT,
                session_id=session_id,
                turn_id=turn_id,
                client_graph_hash=payload.get("client_graph_hash"),
                request_payload=payload,
                idempotency_key=payload.get("idempotency_key")
                if isinstance(payload.get("idempotency_key"), str)
                else None,
            )
        except Exception as exc:
            failure = _classify_failure("accept", exc)
            return _web.json_response(
                _ensure_contract(failure.to_dict(), stage="accept"),
                status=500,
            )
        response = _to_serializable(result)
        # Surface bridge-use evidence on every response so operators can
        # observe whether the accept→finalize bridge is still in active use.
        if isinstance(response, dict) and isinstance(result, dict):
            bridge_meta = result.get("bridge")
            if isinstance(bridge_meta, dict):
                response.setdefault("bridge", bridge_meta)
        return _web.json_response(response)

    @app.routes.post("/vibecomfy/agent-edit/prepare")
    async def _agent_edit_prepare_route(request):  # type: ignore[no-untyped-def]
        try:
            payload = await request.json()
        except Exception as exc:
            return _json_error(f"Request body must be valid JSON: {exc}", stage="prepare")
        if not isinstance(payload, dict):
            return _json_error("Request body must be a JSON object.", stage="prepare")
        session_id = _safe_session_id(payload.get("session_id"))
        turn_id = payload.get("turn_id")
        if not isinstance(turn_id, str) or not turn_id.strip():
            return _json_error("turn_id is required.", stage="prepare")
        try:
            result = await asyncio.to_thread(
                _session_prepare_turn_transaction,
                session_root=_SESSION_ROOT,
                session_id=session_id,
                turn_id=turn_id,
                request_payload=payload,
                idempotency_key=payload.get("idempotency_key")
                if isinstance(payload.get("idempotency_key"), str)
                else None,
            )
        except Exception as exc:
            failure = _classify_failure("prepare", exc)
            return _web.json_response(
                _ensure_contract(failure.to_dict(), stage="prepare"),
                status=500,
            )
        return _web.json_response(_to_serializable(result))

    @app.routes.post("/vibecomfy/agent-edit/finalize")
    async def _agent_edit_finalize_route(request):  # type: ignore[no-untyped-def]
        try:
            payload = await request.json()
        except Exception as exc:
            return _json_error(f"Request body must be valid JSON: {exc}", stage="finalize")
        if not isinstance(payload, dict):
            return _json_error("Request body must be a JSON object.", stage="finalize")
        session_id = _safe_session_id(payload.get("session_id"))
        turn_id = payload.get("turn_id")
        if not isinstance(turn_id, str) or not turn_id.strip():
            return _json_error("turn_id is required.", stage="finalize")
        try:
            result = await asyncio.to_thread(
                _session_finalize_turn_transaction,
                session_root=_SESSION_ROOT,
                session_id=session_id,
                turn_id=turn_id,
                request_payload=payload,
                idempotency_key=payload.get("idempotency_key")
                if isinstance(payload.get("idempotency_key"), str)
                else None,
            )
        except Exception as exc:
            failure = _classify_failure("finalize", exc)
            return _web.json_response(
                _ensure_contract(failure.to_dict(), stage="finalize"),
                status=500,
            )
        return _web.json_response(_to_serializable(result))

    @app.routes.post("/vibecomfy/agent-edit/rollback")
    async def _agent_edit_rollback_route(request):  # type: ignore[no-untyped-def]
        try:
            payload = await request.json()
        except Exception as exc:
            return _json_error(f"Request body must be valid JSON: {exc}", stage="rollback")
        if not isinstance(payload, dict):
            return _json_error("Request body must be a JSON object.", stage="rollback")
        session_id = _safe_session_id(payload.get("session_id"))
        turn_id = payload.get("turn_id")
        if not isinstance(turn_id, str) or not turn_id.strip():
            return _json_error("turn_id is required.", stage="rollback")
        try:
            result = await asyncio.to_thread(
                _session_rollback_turn_transaction,
                session_root=_SESSION_ROOT,
                session_id=session_id,
                turn_id=turn_id,
                request_payload=payload,
                idempotency_key=payload.get("idempotency_key")
                if isinstance(payload.get("idempotency_key"), str)
                else None,
            )
        except Exception as exc:
            failure = _classify_failure("rollback", exc)
            return _web.json_response(
                _ensure_contract(failure.to_dict(), stage="rollback"),
                status=500,
            )
        return _web.json_response(_to_serializable(result))

    @app.routes.post("/vibecomfy/agent-edit/reconcile")
    async def _agent_edit_reconcile_route(request):  # type: ignore[no-untyped-def]
        try:
            payload = await request.json()
        except Exception as exc:
            return _json_error(f"Request body must be valid JSON: {exc}", stage="reconcile")
        if not isinstance(payload, dict):
            return _json_error("Request body must be a JSON object.", stage="reconcile")
        session_id = _safe_session_id(payload.get("session_id"))
        turn_id = payload.get("turn_id")
        try:
            result = await asyncio.to_thread(
                _session_reconcile_turn_transactions,
                session_root=_SESSION_ROOT,
                session_id=session_id,
                turn_id=turn_id if isinstance(turn_id, str) and turn_id.strip() else None,
            )
        except Exception as exc:
            failure = _classify_failure("reconcile", exc)
            return _web.json_response(
                _ensure_contract(failure.to_dict(), stage="reconcile"),
                status=500,
            )
        return _web.json_response(_to_serializable(result))

    @app.routes.post("/vibecomfy/agent-edit/reject")
    async def _agent_edit_reject_route(request):  # type: ignore[no-untyped-def]
        try:
            payload = await request.json()
        except Exception as exc:
            return _json_error(f"Request body must be valid JSON: {exc}", stage="reject")
        if not isinstance(payload, dict):
            return _json_error("Request body must be a JSON object.", stage="reject")
        try:
            result = await asyncio.to_thread(
                _handle_agent_edit_reject,
                payload,
                session_root=_SESSION_ROOT,
            )
        except Exception as exc:
            failure = _classify_failure("reject", exc)
            return _web.json_response(
                _ensure_contract(failure.to_dict(), stage="reject"),
                status=500,
            )
        return _web.json_response(_to_serializable(result))

    @app.routes.post("/vibecomfy/agent-edit/rebaseline")
    async def _agent_edit_rebaseline_route(request):  # type: ignore[no-untyped-def]
        try:
            payload = await request.json()
        except Exception as exc:
            return _json_error(f"Request body must be valid JSON: {exc}", stage="rebaseline")
        if not isinstance(payload, dict):
            return _json_error("Request body must be a JSON object.", stage="rebaseline")
        session_id = _safe_session_id(payload.get("session_id"))
        try:
            result = await asyncio.to_thread(
                rebaseline_session,
                session_root=_SESSION_ROOT,
                session_id=session_id,
                request_payload=payload,
                idempotency_key=payload.get("idempotency_key")
                if isinstance(payload.get("idempotency_key"), str)
                else None,
            )
        except Exception as exc:
            failure = _classify_failure("rebaseline", exc)
            return _web.json_response(
                _ensure_contract(failure.to_dict(), stage="rebaseline"),
                status=500,
            )
        return _web.json_response(_to_serializable(result))

    @app.routes.get("/vibecomfy/agent-edit/chat")
    async def _agent_edit_chat_route(request):  # type: ignore[no-untyped-def]
        session_id = _session_id_from_query(request)
        max_messages = _coerce_chat_max_messages(request.query.get("max_messages"))
        try:
            result = await asyncio.to_thread(
                read_session_chat,
                _SESSION_ROOT,
                session_id,
                max_messages=max_messages,
            )
        except Exception as exc:
            failure = _classify_failure("chat", exc)
            return _web.json_response(
                _ensure_contract(failure.to_dict(), stage="chat"),
                status=500,
            )
        return _web.json_response(_to_serializable(public_chat_rehydrate_payload(result)))

    @app.routes.get("/vibecomfy/agent-edit/recover")
    async def _agent_edit_recover_route(request):  # type: ignore[no-untyped-def]
        workflow_id = request.query.get("workflow_id")
        if not isinstance(workflow_id, str) or not workflow_id.strip():
            return _json_error(
                "Missing required query parameter `workflow_id`.",
                stage="recover",
            )
        try:
            result = await asyncio.to_thread(
                recover_session_for_workflow,
                _SESSION_ROOT,
                workflow_id.strip(),
            )
        except Exception as exc:
            failure = _classify_failure("recover", exc)
            return _web.json_response(
                _ensure_contract(failure.to_dict(), stage="recover"),
                status=500,
            )
        return _web.json_response(_to_serializable(result))

    @app.routes.get("/vibecomfy/agent-edit/session-bundle")
    async def _agent_edit_session_bundle_route(request):  # type: ignore[no-untyped-def]
        session_id = _session_id_from_query(request)
        try:
            result = await asyncio.to_thread(
                read_session_bundle,
                _SESSION_ROOT,
                session_id,
            )
        except Exception as exc:
            failure = _classify_failure("session_bundle", exc)
            return _web.json_response(
                _ensure_contract(failure.to_dict(), stage="session_bundle"),
                status=500,
            )
        return _web.json_response(_to_serializable(result))

    @app.routes.get("/vibecomfy/agent-edit/session-json")
    async def _agent_edit_session_json_route(request):  # type: ignore[no-untyped-def]
        session_id = _session_id_from_query(request)
        try:
            result = await asyncio.to_thread(
                read_session_json,
                _SESSION_ROOT,
                session_id,
            )
        except Exception as exc:
            failure = _classify_failure("session_json", exc)
            return _web.json_response(
                _ensure_contract(failure.to_dict(), stage="session_json"),
                status=500,
            )
        return _web.json_response(_to_serializable(public_session_json_payload(result)))

    @app.routes.post("/vibecomfy/node-packs/install")
    async def _node_pack_install_route(request):  # type: ignore[no-untyped-def]
        try:
            payload = await request.json()
        except Exception as exc:
            return _web.json_response(
                _install_route_error(f"Request body must be valid JSON: {exc}"),
                status=400,
            )
        result = await asyncio.to_thread(_handle_node_pack_install, payload)
        status = 200 if result.get("ok") is True else 400
        return _web.json_response(_to_serializable(result), status=status)

    @app.routes.get("/vibecomfy/demo/scenarios")
    async def _demo_scenarios_route(request):  # type: ignore[no-untyped-def]
        if os.environ.get("VIBECOMFY_DEMO_PICKER") != "1":
            return _web.json_response({"ok": False, "error": "Not found"}, status=404)
        try:
            result, status = await asyncio.to_thread(_load_demo_scenarios_list)
        except Exception as exc:
            _LOGGER.exception("/vibecomfy/demo/scenarios failed")
            return _web.json_response(
                {"ok": False, "error": f"Failed to load demo manifest: {exc}"},
                status=500,
            )
        return _web.json_response(_to_serializable(result), status=status)

    @app.routes.get("/vibecomfy/demo/scenario")
    async def _demo_scenario_route(request):  # type: ignore[no-untyped-def]
        if os.environ.get("VIBECOMFY_DEMO_PICKER") != "1":
            return _web.json_response({"ok": False, "error": "Not found"}, status=404)
        scenario_id = request.query.get("id")
        if not isinstance(scenario_id, str) or not scenario_id.strip():
            return _web.json_response({"ok": False, "error": "id is required"}, status=400)
        try:
            result, status = await asyncio.to_thread(_resolve_demo_scenario, scenario_id)
        except Exception as exc:
            _LOGGER.exception("/vibecomfy/demo/scenario failed")
            return _web.json_response(
                {"ok": False, "error": f"Failed to load scenario: {exc}"},
                status=500,
            )
        return _web.json_response(_to_serializable(result), status=status)

    @app.routes.get("/vibecomfy/agentic-replay/runs")
    async def _agentic_replay_runs_route(request):  # type: ignore[no-untyped-def]
        try:
            result, status = await asyncio.to_thread(_list_agentic_replay_runs)
        except Exception as exc:
            _LOGGER.exception("/vibecomfy/agentic-replay/runs failed")
            return _web.json_response(
                {"ok": False, "error": f"Failed to list replay runs: {exc}"},
                status=500,
            )
        return _web.json_response(_to_serializable(result), status=status)

    @app.routes.get("/vibecomfy/agentic-replay/runs/{run_id}/tests")
    async def _agentic_replay_tests_route(request):  # type: ignore[no-untyped-def]
        run_id = request.match_info.get("run_id")
        if not isinstance(run_id, str) or not run_id.strip():
            return _web.json_response({"ok": False, "error": "run_id is required"}, status=400)
        try:
            result, status = await asyncio.to_thread(_list_agentic_replay_tests, run_id)
        except Exception as exc:
            _LOGGER.exception("/vibecomfy/agentic-replay/runs/%s/tests failed", run_id)
            return _web.json_response(
                {"ok": False, "error": f"Failed to list replay tests: {exc}"},
                status=500,
            )
        return _web.json_response(_to_serializable(result), status=status)

    @app.routes.get("/vibecomfy/agentic-replay/runs/{run_id}/tests/{test_id}")
    async def _agentic_replay_scenario_route(request):  # type: ignore[no-untyped-def]
        run_id = request.match_info.get("run_id")
        test_id = request.match_info.get("test_id")
        if not isinstance(run_id, str) or not run_id.strip():
            return _web.json_response({"ok": False, "error": "run_id is required"}, status=400)
        if not isinstance(test_id, str) or not test_id.strip():
            return _web.json_response({"ok": False, "error": "test_id is required"}, status=400)
        try:
            result, status = await asyncio.to_thread(_resolve_agentic_replay_scenario, run_id, test_id)
        except Exception as exc:
            _LOGGER.exception("/vibecomfy/agentic-replay/runs/%s/tests/%s failed", run_id, test_id)
            return _web.json_response(
                {"ok": False, "error": f"Failed to load replay scenario: {exc}"},
                status=500,
            )
        return _web.json_response(_to_serializable(result), status=status)

# ── Route registration (guarded: no-op when VIBECOMFY_HEADLESS=1) ──────────

if os.environ.get("VIBECOMFY_HEADLESS") != "1":
    try:
        from aiohttp import web as _web  # noqa: PLC0415
        from .._server_compat import import_prompt_server

        _PromptServer = import_prompt_server()

        @_PromptServer.instance.routes.post("/vibecomfy/roundtrip")
        async def roundtrip_route(request):  # type: ignore[no-untyped-def]
            _LOGGER.info("/vibecomfy/roundtrip request")
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


        @_PromptServer.instance.routes.post("/vibecomfy/agent-edit/rating")
        async def agent_edit_rating_route(request):  # type: ignore[no-untyped-def]
            _LOGGER.info("/vibecomfy/agent-edit/rating request")
            try:
                payload = await request.json()
            except Exception as exc:
                return _web.json_response(
                    {
                        "ok": False,
                        "error": "validation",
                        "detail": f"Request body must be valid JSON: {exc}",
                    },
                    status=400,
                )
            result, status = await asyncio.to_thread(_handle_vibecomfy_submit_rating, payload)
            return _web.json_response(result, status=status)

        @_PromptServer.instance.routes.get("/vibecomfy/agent/status")
        async def agent_status_route(request):  # type: ignore[no-untyped-def]
            try:
                payload = _handle_agent_status(dict(request.query))
                return _web.json_response(payload)
            except Exception as exc:
                _LOGGER.exception("/vibecomfy/agent/status route handler failed")
                return _web.json_response(
                    {
                        "ok": False,
                        "ready": False,
                        "error": f"Status handler error: {exc}",
                        "route_options": {},
                    },
                    status=500,
                )

        @_PromptServer.instance.routes.post("/vibecomfy/agent/credentials")
        async def agent_credentials_route(request):  # type: ignore[no-untyped-def]
            _LOGGER.info("/vibecomfy/agent/credentials request")
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

        @_PromptServer.instance.routes.get("/vibecomfy/agent/settings")
        async def agent_settings_get_route(request):  # type: ignore[no-untyped-def]
            _LOGGER.info("/vibecomfy/agent/settings GET request")
            result = _handle_agent_settings_get()
            return _web.json_response(result, status=400 if result.get("ok") is False else 200)

        @_PromptServer.instance.routes.post("/vibecomfy/agent/settings")
        async def agent_settings_post_route(request):  # type: ignore[no-untyped-def]
            _LOGGER.info("/vibecomfy/agent/settings POST request")
            try:
                payload = await request.json()
            except Exception as exc:
                return _web.json_response(
                    failure_envelope(
                        FailureKind.MISSING_REQUIRED_FIELD,
                        "agent_settings",
                        agent_failure_context={
                            "explanation": f"Request body must be valid JSON: {exc}"
                        },
                    ).to_dict(),
                    status=400,
                )
            result = _handle_agent_settings_post(payload)
            return _web.json_response(result, status=400 if result.get("ok") is False else 200)

        @_PromptServer.instance.routes.post("/vibecomfy/agent/research-contribution/run")
        async def agent_research_contribution_run_route(request):  # type: ignore[no-untyped-def]
            _LOGGER.info("/vibecomfy/agent/research-contribution/run request")
            try:
                payload = await request.json()
            except Exception:
                payload = {}
            result = _handle_research_contribution_run(payload)
            return _web.json_response(result, status=400 if result.get("ok") is False else 200)

        # Also register the agent edit route on the global PromptServer instance
        register_agent_edit_routes(_PromptServer.instance)
        _LOGGER.info("vibecomfy agent routes module loaded and all routes registered.")

    except ImportError as _routes_import_exc:
        _LOGGER.warning("vibecomfy agent routes module could not register server routes: %s", _routes_import_exc)
