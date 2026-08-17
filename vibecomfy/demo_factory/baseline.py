"""Structural baseline validation for demo_factory.

The port checker remains the raw UI->API converter.  Structural policy is
applied afterwards so missing local packs and model inventories do not decide
whether a user's graph is coherent.
"""
from __future__ import annotations

import json
import os
import socket
import subprocess
import sys
import tempfile
from dataclasses import dataclass, field
from functools import lru_cache
from pathlib import Path
from typing import Any

from vibecomfy.metadata import OUTPUT_NODE_NAMES
from vibecomfy.templates import _OUTPUT_KIND_HEURISTIC, _is_terminal_output_class


from vibecomfy.ingest.door_access import door_get_links, door_get_nodes, door_get_widgets_values
@dataclass(frozen=True, slots=True)
class BaselineResult:
    """Result of baseline validation."""

    passed: bool
    execution_safe: bool
    output_reachable: bool
    compile_error: str | None = None
    output_node_id: str | None = None
    node_count: int = 0
    link_count: int = 0
    structural_safe: bool = False
    runtime_ready_on_current_server: bool = False
    hard_blockers: tuple[dict[str, Any], ...] = ()
    warnings: tuple[dict[str, Any], ...] = ()
    schema_unavailable_classes: tuple[str, ...] = ()
    resolved_classes: tuple[str, ...] = ()
    checks_skipped_for_missing_schema: tuple[dict[str, Any], ...] = ()
    output_boundary: dict[str, Any] | None = None
    port_report: dict[str, Any] = field(default_factory=dict)


def _reachable_comfy_url(timeout: float = 0.5) -> str | None:
    """A reachable ComfyUI server URL (for live /object_info), or None."""
    from urllib.parse import urlparse

    url = os.environ.get("VIBECOMFY_COMFYUI_URL")
    if not url:
        return None
    try:
        parsed = urlparse(url)
        with socket.create_connection(
            (parsed.hostname or "127.0.0.1", parsed.port or 80), timeout=timeout
        ):
            return url
    except OSError:
        return None


def _on_demand_enabled() -> bool:
    """Whether the legacy raw port check may resolve schemas on demand.

    Mirrors ``AuthoringSchemaProvider``: default ON; ``VIBECOMFY_ON_DEMAND_SCHEMAS=0``
    opts out. Kept consistent with the provider so the parent's notion of "on-demand
    is on" matches what the port-check child subprocess actually does.
    """
    return os.environ.get("VIBECOMFY_ON_DEMAND_SCHEMAS", "1") != "0"


def _run_port_check_report(
    graph: dict[str, Any],
    *,
    timeout: int,
    allow_environment_resolution: bool,
) -> tuple[str | None, dict[str, Any]]:
    """Run the port-check subprocess and return its complete JSON payload."""
    fd, path = tempfile.mkstemp(suffix=".ui.json")
    try:
        with os.fdopen(fd, "w", encoding="utf-8") as fh:
            json.dump(graph, fh)
        cmd = [sys.executable, "-m", "vibecomfy.cli", "port", "check", path, "--json"]
        if allow_environment_resolution:
            server_url = _reachable_comfy_url()
            if server_url:
                cmd += ["--runtime-object-info", "--server-url", server_url]
            if _on_demand_enabled():
                cmd.append("--resolve-on-demand")
            child_env = None
        else:
            # Structural pass/fail must not depend on a dev server, pack clone,
            # runtime boot, or ambient resolver flags. On-demand resolution is
            # default-ON at the provider now, so merely stripping the env var is
            # not enough — force it OFF for a deterministic structural verdict.
            child_env = os.environ.copy()
            child_env.pop("VIBECOMFY_COMFYUI_URL", None)
            child_env["VIBECOMFY_ON_DEMAND_SCHEMAS"] = "0"
            child_env["VIBECOMFY_ON_DEMAND_BOOT"] = "0"
        proc = subprocess.run(
            cmd,
            capture_output=True,
            text=True,
            timeout=timeout,
            env=child_env,
        )
        try:
            data = json.loads(proc.stdout)
        except json.JSONDecodeError:
            if proc.returncode != 0:
                return f"port check exit {proc.returncode}: {proc.stderr[:400]}", {}
            return "port check produced no JSON output", {}
    except subprocess.TimeoutExpired:
        return "port check timeout", {}
    except Exception as exc:  # pragma: no cover - defensive
        return f"port check failed: {exc}", {}
    finally:
        try:
            os.unlink(path)
        except OSError:
            pass
    return None, data


def port_check_graph(
    graph: dict[str, Any],
    *,
    timeout: int = 180,
) -> tuple[bool, str | None, dict[str, Any]]:
    """Run the legacy raw converter policy.

    This wrapper intentionally retains its existing behavior for callers that
    explicitly want current-server conversion readiness.
    """
    subprocess_error, data = _run_port_check_report(
        graph,
        timeout=timeout,
        allow_environment_resolution=True,
    )
    if subprocess_error is not None:
        return False, subprocess_error, data

    ok = bool(data.get("ok"))
    diag = data.get("diagnostics") or []
    hard = [
        d
        for d in diag
        if isinstance(d, dict)
        and str(d.get("severity", "")).lower() in ("error", "hard", "fatal")
    ]
    error: str | None = None
    if not ok:
        msgs = [str(d.get("message", d)) for d in hard if d.get("message")]
        error = "; ".join(m[:120] for m in msgs[:3]) or "port check reported not-ok"
        _UNKNOWN = (
            "unknown node",
            "unknown class",
            "unknown type",
            "undefined node",
            "undefined class",
            "not a valid node",
            "unresolved node",
            "is not a known",
            "no object_info",
        )
        has_unknown_node = any(
            any(token in message.lower() for token in _UNKNOWN) for message in msgs
        )
        if msgs and not has_unknown_node:
            ok = True
            error = f"SOFT-PASS (nodes resolve; runtime concerns only): {error}"
    return ok, error, data


def _diagnostic_record(
    code: str,
    *,
    detail: dict[str, Any] | None = None,
    message: str | None = None,
    severity: str = "error",
    **extra: Any,
) -> dict[str, Any]:
    return {
        "code": code,
        "message": message or code.replace("_", " "),
        "severity": severity,
        "detail": dict(detail or {}),
        **extra,
    }


def _parse_raw_link(link: Any) -> dict[str, Any] | None:
    if isinstance(link, list) and len(link) >= 5:
        return {
            "id": link[0],
            "source_node_id": link[1],
            "source_slot": link[2],
            "target_node_id": link[3],
            "target_slot": link[4],
        }
    if isinstance(link, dict):
        aliases = {
            "id": link.get("id"),
            "source_node_id": link.get("origin_id", link.get("source_node_id")),
            "source_slot": link.get("origin_slot", link.get("source_slot")),
            "target_node_id": link.get("target_id", link.get("target_node_id")),
            "target_slot": link.get("target_slot"),
        }
        if all(aliases[key] is not None for key in aliases):
            return aliases
    return None


def _integer_slot(value: Any) -> bool:
    if isinstance(value, bool):
        return False
    try:
        return int(value) >= 0 and str(value).strip() == str(int(value))
    except (TypeError, ValueError):
        return False


def _raw_topology(
    graph: dict[str, Any],
) -> tuple[dict[str, dict[str, Any]], list[dict[str, Any]], list[dict[str, Any]]]:
    """Validate topology directly from UI records, before normalization."""
    blockers: list[dict[str, Any]] = []
    raw_nodes = door_get_nodes(graph)
    if not isinstance(raw_nodes, list) or not raw_nodes:
        blockers.append(
            _diagnostic_record(
                "empty_or_unmaterialized_graph",
                message="Graph has no materialized UI nodes.",
            )
        )
        return {}, [], blockers

    nodes: dict[str, dict[str, Any]] = {}
    for index, node in enumerate(raw_nodes):
        if not isinstance(node, dict) or node.get("id") is None:
            blockers.append(
                _diagnostic_record(
                    "malformed_node_record",
                    detail={"node_index": index},
                    message=f"Node record {index} has no usable id.",
                )
            )
            continue
        node_id = str(node["id"])
        if node_id in nodes:
            blockers.append(
                _diagnostic_record(
                    "duplicate_node_id",
                    detail={"node_id": node_id},
                    message=f"Node id {node_id} appears more than once.",
                )
            )
        else:
            nodes[node_id] = node
        if not str(node.get("type") or "").strip():
            blockers.append(
                _diagnostic_record(
                    "missing_node_type",
                    detail={"node_id": node_id},
                    message=f"Node {node_id} has no class type.",
                )
            )

    raw_links = door_get_links(graph, [])
    if not isinstance(raw_links, list):
        blockers.append(
            _diagnostic_record(
                "malformed_link_collection",
                message="Graph links must be a list.",
            )
        )
        return nodes, [], blockers

    links: list[dict[str, Any]] = []
    link_ids: set[str] = set()
    for index, raw_link in enumerate(raw_links):
        link = _parse_raw_link(raw_link)
        if link is None:
            blockers.append(
                _diagnostic_record(
                    "malformed_raw_link",
                    detail={"link_index": index, "link": raw_link},
                    message=f"Raw link {index} is malformed.",
                )
            )
            continue
        link_id = str(link["id"])
        source_id = str(link["source_node_id"])
        target_id = str(link["target_node_id"])
        link["id"] = link_id
        link["source_node_id"] = source_id
        link["target_node_id"] = target_id
        if link_id in link_ids:
            blockers.append(
                _diagnostic_record(
                    "duplicate_link_id",
                    detail={"link_id": link_id},
                    message=f"Raw link id {link_id} appears more than once.",
                )
            )
        link_ids.add(link_id)
        if source_id not in nodes or target_id not in nodes:
            blockers.append(
                _diagnostic_record(
                    "raw_link_missing_endpoint",
                    detail={
                        "link_id": link_id,
                        "source_node_id": source_id,
                        "target_node_id": target_id,
                        "missing_source": source_id not in nodes,
                        "missing_target": target_id not in nodes,
                    },
                    message=f"Raw link {link_id} references a missing endpoint.",
                )
            )
        if not _integer_slot(link["source_slot"]) or not _integer_slot(
            link["target_slot"]
        ):
            blockers.append(
                _diagnostic_record(
                    "raw_link_invalid_slot",
                    detail={
                        "link_id": link_id,
                        "source_slot": link["source_slot"],
                        "target_slot": link["target_slot"],
                    },
                    message=f"Raw link {link_id} has a non-numeric slot.",
                )
            )
        links.append(link)

    links_by_id = {link["id"]: link for link in links}
    for node_id, node in nodes.items():
        for input_item in node.get("inputs", []) or []:
            if not isinstance(input_item, dict) or input_item.get("link") is None:
                continue
            link_id = str(input_item["link"])
            link = links_by_id.get(link_id)
            if link is None or link["target_node_id"] != node_id:
                blockers.append(
                    _diagnostic_record(
                        "raw_input_link_inconsistent",
                        detail={
                            "node_id": node_id,
                            "input": input_item.get("name"),
                            "link_id": link_id,
                        },
                        message=(
                            f"Node {node_id} input {input_item.get('name')!r} "
                            f"references inconsistent raw link {link_id}."
                        ),
                    )
                )
    return nodes, links, blockers


@lru_cache(maxsize=1)
def _cached_object_info_output_classes() -> frozenset[str]:
    """Read only bundled object-info evidence whose rows declare output_node."""
    root = Path(__file__).resolve().parents[1] / "porting" / "cache" / "object_info"
    output_classes: set[str] = set()
    for path in sorted(root.glob("*.json")):
        try:
            payload = json.loads(path.read_text(encoding="utf-8"))
        except (OSError, json.JSONDecodeError):
            continue
        if not isinstance(payload, dict):
            continue
        for class_type, row in payload.items():
            if isinstance(row, dict) and row.get("output_node") is True:
                output_classes.add(str(class_type))
    return frozenset(output_classes)


def _node_enabled(node: dict[str, Any]) -> bool:
    try:
        mode = int(node.get("mode", 0))
    except (TypeError, ValueError):
        mode = 0
    return mode not in {2, 4}


def _upstream_path_exists(
    boundary_id: str,
    incoming: dict[str, list[str]],
) -> bool:
    """Require a real inbound traversal from a source to the boundary."""
    if not incoming.get(boundary_id):
        return False

    def visit(node_id: str, visiting: frozenset[str]) -> bool:
        if node_id in visiting:
            return False
        parents = incoming.get(node_id, [])
        if not parents:
            return node_id != boundary_id
        return any(visit(parent, visiting | {node_id}) for parent in parents)

    return visit(boundary_id, frozenset())


def _output_reachability(
    graph: dict[str, Any],
    *,
    report: dict[str, Any] | None = None,
) -> tuple[str | None, bool, dict[str, Any] | None]:
    nodes, links, blockers = _raw_topology(graph)
    if blockers:
        valid_links = [
            link
            for link in links
            if link["source_node_id"] in nodes and link["target_node_id"] in nodes
        ]
    else:
        valid_links = links
    incoming: dict[str, list[str]] = {}
    outgoing: dict[str, list[str]] = {}
    for link in valid_links:
        source_id = link["source_node_id"]
        target_id = link["target_node_id"]
        incoming.setdefault(target_id, []).append(source_id)
        outgoing.setdefault(source_id, []).append(target_id)

    explicit_ids = {
        str(item.get("node_id"))
        for item in (report or {}).get("public_outputs", [])
        if isinstance(item, dict) and item.get("node_id") is not None
    }
    object_info_outputs = _cached_object_info_output_classes()
    candidates: list[tuple[int, str, str, str]] = []
    for node_id, node in nodes.items():
        if not _node_enabled(node) or not incoming.get(node_id):
            continue
        class_type = str(node.get("type") or "")
        properties = node.get("properties")
        explicit_property = (
            isinstance(properties, dict) and properties.get("output_node") is True
        )
        if node_id in explicit_ids:
            candidates.append((0, node_id, "explicit_public_output", "high"))
        elif explicit_property or class_type in object_info_outputs:
            candidates.append((1, node_id, "object_info_output_node", "high"))
        elif class_type in OUTPUT_NODE_NAMES or class_type in _OUTPUT_KIND_HEURISTIC:
            candidates.append((2, node_id, "shared_output_catalog", "high"))
        elif _is_terminal_output_class(class_type) and not outgoing.get(node_id):
            candidates.append((3, node_id, "shared_terminal_output_heuristic", "medium"))
        elif not outgoing.get(node_id) and not (node.get("outputs") or []):
            candidates.append((4, node_id, "connected_terminal_boundary", "low"))

    for _, node_id, rule, confidence in sorted(
        candidates, key=lambda item: (item[0], _node_sort_key(item[1]))
    ):
        if _upstream_path_exists(node_id, incoming):
            return node_id, True, {
                "node_id": node_id,
                "class_type": str(nodes[node_id].get("type") or ""),
                "rule": rule,
                "confidence": confidence,
            }
    return None, False, None


def _node_sort_key(value: str) -> tuple[int, int | str]:
    return (0, int(value)) if value.isdigit() else (1, value)


def _find_output_node(
    graph: dict[str, Any],
    report: dict[str, Any] | None = None,
) -> tuple[str | None, bool]:
    """Return a structurally reachable output boundary, if one exists."""
    node_id, reachable, _ = _output_reachability(graph, report=report)
    return node_id, reachable


def _graph_class_types(graph: dict[str, Any] | None) -> set[str]:
    if not isinstance(graph, dict):
        return set()
    return {
        str(node.get("type"))
        for node in door_get_nodes(graph, [])
        if isinstance(node, dict) and str(node.get("type") or "").strip()
    }


def _unresolved_class(diag: dict[str, Any]) -> str | None:
    detail = diag.get("detail") if isinstance(diag.get("detail"), dict) else {}
    value = (
        diag.get("class_type")
        or detail.get("class_type")
        or detail.get("runtime_class_type")
    )
    return str(value) if value is not None and str(value).strip() else None


def _raw_node_for_diag(
    nodes: dict[str, dict[str, Any]], diag: dict[str, Any]
) -> dict[str, Any] | None:
    detail = diag.get("detail") if isinstance(diag.get("detail"), dict) else {}
    node_id = diag.get("node_id") or detail.get("node_id")
    return nodes.get(str(node_id)) if node_id is not None else None


def _credible_missing_required(
    diag: dict[str, Any],
    nodes: dict[str, dict[str, Any]],
) -> bool:
    """Hard only when credible schema evidence matches an exposed raw socket."""
    detail = diag.get("detail") if isinstance(diag.get("detail"), dict) else {}
    if detail.get("has_default") is True:
        return False
    try:
        confidence = float(detail.get("schema_confidence", 0.0))
    except (TypeError, ValueError):
        confidence = 0.0
    if confidence < 0.9:
        return False
    input_name = detail.get("input")
    raw_node = _raw_node_for_diag(nodes, diag)
    if raw_node is None or not isinstance(input_name, str):
        return False
    for raw_input in raw_node.get("inputs", []) or []:
        if not isinstance(raw_input, dict) or raw_input.get("name") != input_name:
            continue
        return raw_input.get("link") is None and not isinstance(
            raw_input.get("widget"), dict
        )
    return False


def _widget_contains_link_shape(value: Any, source_id: str, source_slot: Any) -> bool:
    if (
        isinstance(value, list)
        and len(value) == 2
        and str(value[0]) == source_id
        and str(value[1]) == str(source_slot)
    ):
        return True
    if isinstance(value, (list, tuple)):
        return any(
            _widget_contains_link_shape(item, source_id, source_slot) for item in value
        )
    if isinstance(value, dict):
        return any(
            _widget_contains_link_shape(item, source_id, source_slot)
            for item in value.values()
        )
    return False


def _manufactured_widget_edge(
    diag: dict[str, Any],
    *,
    graph: dict[str, Any],
    nodes: dict[str, dict[str, Any]],
    links: list[dict[str, Any]],
) -> bool:
    detail = diag.get("detail") if isinstance(diag.get("detail"), dict) else {}
    if detail.get("compile_code") != "compiled_edge_missing_endpoint":
        return False
    source_id = detail.get("source_node_id")
    source_slot = detail.get("source_output", detail.get("source_slot", 1))
    target_id = detail.get("target_node_id")
    if source_id is None or target_id is None:
        return False
    source_id = str(source_id)
    target_id = str(target_id)
    if source_id in nodes:
        return False
    if any(
        link["source_node_id"] == source_id
        or link["target_node_id"] == source_id
        for link in links
    ):
        return False
    target = nodes.get(target_id)
    if target is None:
        return False
    return _widget_contains_link_shape(
        door_get_widgets_values(target), source_id, source_slot
    )


_UNRESOLVED_CODES = frozenset({"unresolved_runtime_class", "unknown_class_type"})
_RUNTIME_ONLY_CODES = frozenset(
    {
        "known_runtime_required_input_missing",
        "dynamic_combo_selector_missing",
        "optional_acceleration_requires_unavailable_package",
        "headless_preview_override_not_supported",
        "ltx_audio_vae_wrong_loader",
        "metadata_environment_mismatch",
        "missing_model_asset",
    }
)
_SCHEMA_DRIFT_CODES = frozenset(
    {
        "unknown_input",
        "compiled_widget_input_missing",
        "widget_alias_unresolved",
        "missing_dynamic_input",
        "type_mismatch",
        "value_type_mismatch",
        "value_out_of_range",
    }
)
_HARD_GRAPH_CODES = frozenset(
    {
        "invalid_link_shape",
        "invalid_output_index",
        "invalid_dynamic_input_count",
        "dynamic_input_exceeds_count",
        "helper_edge_unresolved",
        "compiled_edge_missing_endpoint",
    }
)


def _as_warning(
    diag: dict[str, Any],
    *,
    reason: str,
    **detail_updates: Any,
) -> dict[str, Any]:
    warning = dict(diag)
    warning["severity"] = "warning"
    detail = dict(warning.get("detail") or {})
    detail.update({"structural_disposition": "warning", "structural_reason": reason})
    detail.update(detail_updates)
    warning["detail"] = detail
    return warning


def _as_blocker(diag: dict[str, Any], *, reason: str) -> dict[str, Any]:
    blocker = dict(diag)
    blocker["severity"] = "error"
    detail = dict(blocker.get("detail") or {})
    detail.update({"structural_disposition": "hard", "structural_reason": reason})
    blocker["detail"] = detail
    return blocker


def _raw_widget_contains_declared_choice(
    diag: dict[str, Any],
    nodes: dict[str, dict[str, Any]],
) -> bool:
    """Prove positional enum/schema ambiguity from the original widget vector."""
    detail = diag.get("detail") if isinstance(diag.get("detail"), dict) else {}
    choices = detail.get("choices")
    raw_node = _raw_node_for_diag(nodes, diag)
    if raw_node is None or not isinstance(choices, list) or not choices:
        return False

    def scalars(value: Any):
        if isinstance(value, (list, tuple)):
            for item in value:
                yield from scalars(item)
        elif isinstance(value, dict):
            for item in value.values():
                yield from scalars(item)
        else:
            yield value

    widget_values = list(scalars(door_get_widgets_values(raw_node)))
    return any(
        type(widget_value) is type(choice) and widget_value == choice
        for widget_value in widget_values
        for choice in choices
    )


def structural_check_graph(
    graph: dict[str, Any],
    *,
    timeout: int = 180,
    pre_existing_types: set[str] | None = None,
) -> dict[str, Any]:
    """Classify the full port report under offline structural policy.

    Diagnostic decisions use ``code`` and structured ``detail`` only.  Missing
    schemas for pre-existing nodes are warnings; introduced unresolved classes
    are explicitly flagged but remain warnings without authoritative evidence
    that the class cannot exist.
    """
    subprocess_error, report = _run_port_check_report(
        graph,
        timeout=timeout,
        allow_environment_resolution=False,
    )
    nodes, links, topology_blockers = _raw_topology(graph)
    hard_blockers = list(topology_blockers)
    warnings: list[dict[str, Any]] = []
    graph_types = _graph_class_types(graph)
    baseline_mode = pre_existing_types is None
    known_pre_existing = set(graph_types if baseline_mode else pre_existing_types or set())
    unavailable: set[str] = set()
    introduced_unavailable: set[str] = set()

    if subprocess_error is not None:
        hard_blockers.append(
            _diagnostic_record(
                "port_check_subprocess_failed",
                message=subprocess_error,
                detail={"error": subprocess_error},
            )
        )

    diagnostics = [
        dict(diag)
        for diag in (report.get("diagnostics", []) if isinstance(report, dict) else [])
        if isinstance(diag, dict)
    ]
    manufactured_diagnostics = [
        diag
        for diag in diagnostics
        if _manufactured_widget_edge(diag, graph=graph, nodes=nodes, links=links)
    ]
    manufactured_cluster = bool(manufactured_diagnostics) and not topology_blockers

    for diag in diagnostics:
        severity = str(diag.get("severity") or "warning").lower()
        code = str(diag.get("code") or "")
        detail = diag.get("detail") if isinstance(diag.get("detail"), dict) else {}
        if code in _UNRESOLVED_CODES:
            class_type = _unresolved_class(diag)
            if class_type:
                unavailable.add(class_type)
                origin = (
                    "pre_existing"
                    if class_type in known_pre_existing
                    else "fixer_introduced"
                )
                if origin == "fixer_introduced":
                    introduced_unavailable.add(class_type)
                warnings.append(
                    _as_warning(
                        diag,
                        reason="schema_unavailable",
                        node_origin=origin,
                        fixer_introduced=origin == "fixer_introduced",
                    )
                )
            else:
                warnings.append(_as_warning(diag, reason="schema_unavailable"))
            continue
        if severity not in {"error", "hard", "fatal"}:
            warnings.append(dict(diag))
            continue
        if code == "value_not_in_enum":
            if detail.get("choice_scope") == "environment_asset":
                warnings.append(_as_warning(diag, reason="environment_asset_inventory"))
            elif _raw_widget_contains_declared_choice(diag, nodes):
                warnings.append(
                    _as_warning(diag, reason="schema_mapping_ambiguous")
                )
            else:
                hard_blockers.append(_as_blocker(diag, reason="semantic_enum"))
            continue
        if code == "missing_required_input":
            if _credible_missing_required(diag, nodes):
                hard_blockers.append(
                    _as_blocker(diag, reason="credible_non_defaultable_required_input")
                )
            else:
                warnings.append(
                    _as_warning(diag, reason="schema_version_or_ui_obligation_inconclusive")
                )
            continue
        if code in _RUNTIME_ONLY_CODES:
            warnings.append(_as_warning(diag, reason="runtime_readiness_only"))
            continue
        if code in _SCHEMA_DRIFT_CODES:
            warnings.append(_as_warning(diag, reason="schema_or_version_drift"))
            continue
        if code == "api_compile_failed":
            if _manufactured_widget_edge(
                diag, graph=graph, nodes=nodes, links=links
            ) or (manufactured_cluster and not detail.get("compile_code")):
                warnings.append(_as_warning(diag, reason="manufactured_widget_edge"))
            else:
                hard_blockers.append(_as_blocker(diag, reason="api_compile_invariant"))
            continue
        if code in {"missing_edge_source", "missing_edge_target"}:
            if manufactured_cluster:
                warnings.append(_as_warning(diag, reason="manufactured_widget_edge"))
            else:
                hard_blockers.append(_as_blocker(diag, reason="compiled_edge_endpoint"))
            continue
        if code in _HARD_GRAPH_CODES:
            hard_blockers.append(_as_blocker(diag, reason="graph_invariant"))
            continue
        # Port errors not backed by a structural category stay visible without
        # coupling baseline admission to this machine's runtime contract.
        warnings.append(_as_warning(diag, reason="non_structural_port_diagnostic"))

    output_node_id, output_reachable, output_boundary = _output_reachability(
        graph, report=report
    )
    if not output_reachable:
        hard_blockers.append(
            _diagnostic_record(
                "no_reachable_output",
                message="Graph has no enabled output boundary with a real upstream path.",
                detail={"structural_disposition": "hard"},
            )
        )

    resolved = sorted(graph_types - unavailable)
    checks_skipped = [
        {
            "class_type": class_type,
            "node_origin": (
                "pre_existing"
                if class_type in known_pre_existing
                else "fixer_introduced"
            ),
            "checks": [
                "required_inputs",
                "input_enum",
                "edge_socket_type",
                "output_index",
            ],
            "reason": "schema_unavailable",
        }
        for class_type in sorted(unavailable)
    ]
    structural_safe = not hard_blockers
    return {
        "passed": structural_safe and output_reachable,
        "structural_safe": structural_safe,
        "output_reachable": output_reachable,
        "runtime_ready_on_current_server": bool(report.get("ok"))
        if isinstance(report, dict)
        else False,
        "hard_blockers": hard_blockers,
        "warnings": warnings,
        "schema_unavailable_classes": sorted(unavailable),
        "fixer_introduced_schema_unavailable_classes": sorted(
            introduced_unavailable
        ),
        "resolved_classes": resolved,
        "checks_skipped_for_missing_schema": checks_skipped,
        "output_node_id": output_node_id,
        "output_boundary": output_boundary,
        "port_report": report,
    }


def _blocker_summary(blockers: list[dict[str, Any]]) -> str | None:
    if not blockers:
        return None
    parts: list[str] = []
    for blocker in blockers[:3]:
        code = str(blocker.get("code") or "structural_blocker")
        detail = blocker.get("detail")
        parts.append(f"{code}: {json.dumps(detail, sort_keys=True, default=str)}")
    return "; ".join(parts)


def run_baseline(golden: dict[str, Any]) -> BaselineResult:
    """Validate a golden as a coherent graph with a reachable result boundary."""
    structural = structural_check_graph(golden)
    hard_blockers = list(structural["hard_blockers"])
    return BaselineResult(
        passed=bool(
            structural["structural_safe"] and structural["output_reachable"]
        ),
        execution_safe=bool(structural["runtime_ready_on_current_server"]),
        output_reachable=bool(structural["output_reachable"]),
        compile_error=_blocker_summary(hard_blockers),
        output_node_id=structural["output_node_id"],
        node_count=len(door_get_nodes(golden, [])),
        link_count=len(door_get_links(golden, [])),
        structural_safe=bool(structural["structural_safe"]),
        runtime_ready_on_current_server=bool(
            structural["runtime_ready_on_current_server"]
        ),
        hard_blockers=tuple(hard_blockers),
        warnings=tuple(structural["warnings"]),
        schema_unavailable_classes=tuple(
            structural["schema_unavailable_classes"]
        ),
        resolved_classes=tuple(structural["resolved_classes"]),
        checks_skipped_for_missing_schema=tuple(
            structural["checks_skipped_for_missing_schema"]
        ),
        output_boundary=structural["output_boundary"],
        port_report=dict(structural["port_report"]),
    )


def write_baseline_proof(result: BaselineResult, output_dir: Path) -> None:
    """Write the full structured baseline proof to ``proof/baseline.json``."""
    output_dir = Path(output_dir)
    proof_path = output_dir / "proof" / "baseline.json"
    proof_path.parent.mkdir(parents=True, exist_ok=True)
    proof_path.write_text(
        json.dumps(
            {
                "passed": result.passed,
                "execution_safe": result.execution_safe,
                "structural_safe": result.structural_safe,
                "runtime_ready_on_current_server": result.runtime_ready_on_current_server,
                "output_reachable": result.output_reachable,
                "compile_error": result.compile_error,
                "output_node_id": result.output_node_id,
                "output_boundary": result.output_boundary,
                "node_count": result.node_count,
                "link_count": result.link_count,
                "hard_blockers": list(result.hard_blockers),
                "warnings": list(result.warnings),
                "schema_unavailable_classes": list(
                    result.schema_unavailable_classes
                ),
                "resolved_classes": list(result.resolved_classes),
                "checks_skipped_for_missing_schema": list(
                    result.checks_skipped_for_missing_schema
                ),
                "port_report": result.port_report,
            },
            indent=2,
            sort_keys=True,
        )
        + "\n",
        encoding="utf-8",
    )
