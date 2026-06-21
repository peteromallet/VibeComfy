"""Deterministic topology evidence helpers for LiteGraph JSON.

Produces :class:`TopologyFindings` and :class:`ReadinessReport` evidence
artifacts without LLM/provider calls.  Every public function is pure: it
only reads from the graph dict, optional object_info schema provider, and
session context — never mutates them.

These helpers are the evidence foundation used by both the executor
(``core.py``) and direct agent-edit flows.  A false negative can permit
unsafe mutation outside the edited file, so every check is structural
and testable without network or model dependencies.
"""

from __future__ import annotations

import logging
from typing import Any

from vibecomfy.porting.object_info import class_is_known

from .contracts import ReadinessReport, ScopedDiff, TopologyFindings
from .graph_inspection import EdgeEvidence, inspect_graph, normalise_links

LOGGER = logging.getLogger(__name__)

# ── public helpers ───────────────────────────────────────────────────────────


def collect_topology_evidence(
    graph: dict[str, Any] | None,
    *,
    schema_available: bool = True,
    schema_provider: Any = None,
) -> TopologyFindings:
    """Collect deterministic topology findings for a LiteGraph graph dict.

    Parameters
    ----------
    graph:
        The ComfyUI ``prompt`` dict with ``nodes`` and optional ``links``
        keys, or ``None``.  When ``None``, returns
        ``TopologyFindings(missing_graph=True)``.
    schema_available:
        When ``False``, schema-dependent checks (unknown class types,
        missing required inputs) degrade gracefully rather than guessing.
        The ``schema_available`` field in the returned
        :class:`TopologyFindings` is set to this value.

    Returns
    -------
    TopologyFindings
        Always returns a populated instance — never raises.
    """
    if graph is None or not isinstance(graph, dict):
        return TopologyFindings(
            missing_graph=True,
            schema_available=schema_available,
            summary="No graph attached.",
        )

    nodes_raw = graph.get("nodes")
    if not isinstance(nodes_raw, list) or not nodes_raw:
        return TopologyFindings(
            missing_graph=True,
            schema_available=schema_available,
            summary="Graph has no nodes.",
        )

    # Build node id set and class_type lookup.
    node_ids: set[int | str] = set()
    node_class_types: dict[int | str, str] = {}
    node_inputs: dict[int | str, list[dict]] = {}
    for i, node in enumerate(nodes_raw):
        if not isinstance(node, dict):
            continue
        nid: int | str = node.get("id", i)
        node_ids.add(nid)
        ct = node.get("class_type") or node.get("type") or "Unknown"
        node_class_types[nid] = str(ct)
        raw_inputs = node.get("inputs")
        if isinstance(raw_inputs, list):
            node_inputs[nid] = raw_inputs

    # ── dangling / missing links ────────────────────────────────────────
    links_raw = graph.get("links")
    edges: tuple[EdgeEvidence, ...] = ()
    if isinstance(links_raw, list):
        try:
            edges = normalise_links(links_raw)
        except (TypeError, ValueError):
            edges = ()

    dangling_links: list[str] = []
    absent_endpoint_nodes: list[str] = []
    seen_endpoints: set[int | str] = set()

    # Collect all endpoint node ids referenced by edges.
    edge_endpoint_ids: set[int | str] = set()
    if isinstance(links_raw, list):
        for idx, link in enumerate(links_raw):
            if isinstance(link, list):
                missing_link_id = len(link) == 0 or link[0] is None
            elif isinstance(link, dict):
                missing_link_id = link.get("id") is None and link.get("link_id") is None
            else:
                missing_link_id = True
            if missing_link_id:
                dangling_links.append(f"link_index={idx}: missing link id")

    for edge in edges:
        edge_endpoint_ids.add(edge.origin_node)
        edge_endpoint_ids.add(edge.target_node)

    for edge in edges:
        src_in_graph = edge.origin_node in node_ids
        tgt_in_graph = edge.target_node in node_ids

        if not src_in_graph or not tgt_in_graph:
            missing_src = "source" if not src_in_graph else ""
            missing_tgt = "target" if not tgt_in_graph else ""
            missing_parts = [p for p in (missing_src, missing_tgt) if p]
            dangling_links.append(
                f"link_id={edge.link_id}: "
                f"origin={edge.origin_node} -> target={edge.target_node} "
                f"(missing {', '.join(missing_parts)} endpoint(s))"
            )

        if not src_in_graph:
            absent = str(edge.origin_node)
            if absent not in absent_endpoint_nodes:
                absent_endpoint_nodes.append(absent)
        if not tgt_in_graph:
            absent = str(edge.target_node)
            if absent not in absent_endpoint_nodes:
                absent_endpoint_nodes.append(absent)

        seen_endpoints.add(edge.origin_node)
        seen_endpoints.add(edge.target_node)

    # ── unknown class types (schema-backed) ─────────────────────────────
    unknown_class_types: list[str] = []
    if schema_available:
        for nid, ct in sorted(node_class_types.items(), key=lambda kv: str(kv[0])):
            if ct == "Unknown":
                unknown_class_types.append(f"node_id={nid}: <no class_type>")
            elif not _class_is_known(ct, schema_provider=schema_provider):
                unknown_class_types.append(f"node_id={nid}: {ct}")

    # ── missing required inputs (schema-backed) ─────────────────────────
    missing_required_inputs: list[dict[str, Any]] = []
    if schema_available:
        for nid, inputs in node_inputs.items():
            ct = node_class_types.get(nid, "Unknown")
            if ct == "Unknown":
                continue
            # Check each input for required fields that are neither
            # linked nor have a literal widget value present.
            for inp_idx, inp in enumerate(inputs):
                if not isinstance(inp, dict):
                    continue
                inp_name = inp.get("name", f"slot_{inp_idx}")
                # Check if this input receives a link.
                link_val = inp.get("link")
                has_link = link_val is not None
                # Check if widget_values supplies a literal.
                widget_val = inp.get("widget")
                has_widget = widget_val is not None
                # Check object_info for whether this input is required.
                is_required = (
                    _input_is_required(ct, inp_name, schema_provider=schema_provider)
                    if schema_provider is not None
                    else _input_is_required(ct, inp_name)
                )
                if is_required and not has_link and not has_widget:
                    missing_required_inputs.append({
                        "node_id": nid,
                        "class_type": ct,
                        "input_name": inp_name,
                        "has_link": False,
                        "has_widget_value": False,
                        "reason": (
                            f"Required input '{inp_name}' on node "
                            f"[{nid}] {ct} has no link or literal widget value."
                        ),
                    })

    # ── build summary ──────────────────────────────────────────────────
    summary_parts: list[str] = []
    if dangling_links:
        summary_parts.append(f"{len(dangling_links)} dangling link(s)")
    if absent_endpoint_nodes:
        summary_parts.append(
            f"{len(absent_endpoint_nodes)} absent endpoint node(s)"
        )
    if unknown_class_types:
        summary_parts.append(
            f"{len(unknown_class_types)} unknown class type(s)"
        )
    if missing_required_inputs:
        summary_parts.append(
            f"{len(missing_required_inputs)} missing required input(s)"
        )
    if not summary_parts:
        summary_parts.append("no topology issues detected")
    if not schema_available:
        summary_parts.append("(schema unavailable — class/input checks skipped)")

    return TopologyFindings(
        missing_graph=False,
        dangling_links=tuple(dangling_links),
        absent_endpoint_nodes=tuple(absent_endpoint_nodes),
        unknown_class_types=tuple(unknown_class_types),
        missing_required_inputs=tuple(missing_required_inputs),
        schema_available=schema_available,
        summary="; ".join(summary_parts),
    )


def collect_readiness_evidence(
    graph: dict[str, Any] | None,
    *,
    object_info_available: bool = True,
    schema_provider: Any = None,
    missing_models: tuple[str, ...] = (),
    missing_node_packs: tuple[str, ...] = (),
    validation_errors: tuple[str, ...] = (),
    no_gpu_detected: bool = False,
    readiness_blockers: tuple[str, ...] = (),
    ready_metadata: dict[str, Any] | None = None,
    diagnostics: tuple[dict[str, Any], ...] = (),
) -> ReadinessReport:
    """Collect deterministic readiness evidence for a graph.

    Parameters
    ----------
    graph:
        The ComfyUI ``prompt`` dict, or ``None``.  Used to cross-reference
        class types against known readiness data.
    object_info_available:
        When ``False``, readiness checks degrade gracefully.
    missing_models:
        Pre-computed list of missing model file names/paths.
    missing_node_packs:
        Pre-computed list of missing node pack identifiers.
    validation_errors:
        Pre-computed validation error messages.
    no_gpu_detected:
        ``True`` when no usable GPU was detected at runtime.
    readiness_blockers:
        Additional explicit readiness blocker messages.

    Returns
    -------
    ReadinessReport
        Always returns a populated instance.
    """
    metadata_missing_models, metadata_missing_packs = _readiness_from_metadata(ready_metadata)
    diagnostic_models, diagnostic_packs, diagnostic_errors, diagnostic_no_gpu = (
        _readiness_from_diagnostics(diagnostics)
    )
    missing_models = _dedupe_strings(
        (*missing_models, *metadata_missing_models, *diagnostic_models)
    )
    missing_node_packs = _dedupe_strings(
        (*missing_node_packs, *metadata_missing_packs, *diagnostic_packs)
    )
    validation_errors = _dedupe_strings((*validation_errors, *diagnostic_errors))
    no_gpu_detected = no_gpu_detected or diagnostic_no_gpu

    # If caller or fallback evidence supplied blockers, use them directly.
    if missing_models or missing_node_packs or validation_errors or no_gpu_detected or readiness_blockers:
        summary_parts: list[str] = []
        if missing_models:
            summary_parts.append(f"{len(missing_models)} missing model(s)")
        if missing_node_packs:
            summary_parts.append(f"{len(missing_node_packs)} missing node pack(s)")
        if validation_errors:
            summary_parts.append(f"{len(validation_errors)} validation error(s)")
        if no_gpu_detected:
            summary_parts.append("no GPU detected")
        if readiness_blockers:
            summary_parts.append(f"{len(readiness_blockers)} explicit blocker(s)")
        return ReadinessReport(
            missing_models=missing_models,
            missing_node_packs=missing_node_packs,
            validation_errors=validation_errors,
            no_gpu_detected=no_gpu_detected,
            readiness_blockers=readiness_blockers,
            object_info_available=object_info_available,
            summary="; ".join(summary_parts) if summary_parts else "",
        )

    if graph is None or not isinstance(graph, dict):
        return ReadinessReport(
            object_info_available=object_info_available,
            summary="No graph to assess readiness for." if object_info_available else "",
        )

    nodes_raw = graph.get("nodes")
    if not isinstance(nodes_raw, list):
        return ReadinessReport(
            object_info_available=object_info_available,
            summary="Graph has no nodes to assess.",
        )

    # Collect class types present in the graph.
    class_types: set[str] = set()
    node_schemas: dict[str, Any] = {}
    for n in nodes_raw:
        if isinstance(n, dict):
            ct = n.get("class_type") or n.get("type")
            if isinstance(ct, str) and ct.strip():
                class_type = ct.strip()
                class_types.add(class_type)
                node_schemas[class_type] = _schema_for_class(
                    class_type,
                    schema_provider=schema_provider,
                    object_info_available=object_info_available,
                )

    # Cross-reference against object_info: flag unknown class types as
    # potential missing-node-pack indicators.
    unknown_classes: list[str] = []
    if object_info_available:
        for ct in sorted(class_types):
            if node_schemas.get(ct) is None and not _class_is_known(ct, schema_provider=schema_provider):
                unknown_classes.append(ct)

    choice_missing_models = _missing_models_from_schema_choices(
        nodes_raw,
        node_schemas=node_schemas,
    )
    missing_models = _dedupe_strings((*missing_models, *choice_missing_models))
    missing_node_packs = _dedupe_strings((*missing_node_packs, *unknown_classes))

    summary_parts: list[str] = []
    if missing_models:
        summary_parts.append(f"{len(missing_models)} missing model(s)")
    if missing_node_packs:
        summary_parts.append(
            f"{len(missing_node_packs)} class type(s) not recognized by "
            f"object_info — possible missing node pack(s): "
            + ", ".join(missing_node_packs)
        )
    if validation_errors:
        summary_parts.append(f"{len(validation_errors)} validation error(s)")

    return ReadinessReport(
        missing_models=missing_models,
        missing_node_packs=missing_node_packs,
        validation_errors=validation_errors,
        object_info_available=object_info_available,
        summary="; ".join(summary_parts),
    )


# ── internal helpers ─────────────────────────────────────────────────────────


def _class_is_known(class_type: str, *, schema_provider: Any = None) -> bool:
    get_schema = getattr(schema_provider, "get_schema", None)
    if callable(get_schema):
        try:
            return get_schema(class_type) is not None
        except Exception:
            return False
    return class_is_known(class_type)


def _schema_for_class(
    class_type: str,
    *,
    schema_provider: Any = None,
    object_info_available: bool = True,
) -> Any:
    if not object_info_available:
        return None
    get_schema = getattr(schema_provider, "get_schema", None)
    if callable(get_schema):
        try:
            return get_schema(class_type)
        except Exception:
            return None
    return None


def _dedupe_strings(values: tuple[Any, ...]) -> tuple[str, ...]:
    seen: set[str] = set()
    result: list[str] = []
    for value in values:
        if value is None:
            continue
        text = str(value).strip()
        if not text or text in seen:
            continue
        seen.add(text)
        result.append(text)
    return tuple(result)


def _readiness_from_metadata(
    metadata: dict[str, Any] | None,
) -> tuple[tuple[str, ...], tuple[str, ...]]:
    if not isinstance(metadata, dict):
        return (), ()
    candidates: list[dict[str, Any]] = [metadata]
    for key in ("requirements", "ready_metadata", "metadata", "vibecomfy"):
        value = metadata.get(key)
        if isinstance(value, dict):
            candidates.append(value)

    missing_models: list[Any] = []
    missing_packs: list[Any] = []
    for item in candidates:
        missing_models.extend(_list_strings(item.get("missing_models")))
        missing_packs.extend(_list_strings(item.get("missing_node_packs")))
        missing_packs.extend(_list_strings(item.get("missing_custom_nodes")))
        missing_models.extend(_explicitly_missing_names(item.get("models")))
        missing_models.extend(_explicitly_missing_names(item.get("model_assets")))
        missing_packs.extend(_explicitly_missing_names(item.get("custom_nodes")))
        missing_packs.extend(_explicitly_missing_names(item.get("custom_node_packs")))
    return _dedupe_strings(tuple(missing_models)), _dedupe_strings(tuple(missing_packs))


def _readiness_from_diagnostics(
    diagnostics: tuple[dict[str, Any], ...],
) -> tuple[tuple[str, ...], tuple[str, ...], tuple[str, ...], bool]:
    missing_models: list[Any] = []
    missing_packs: list[Any] = []
    validation_errors: list[str] = []
    no_gpu = False
    for diagnostic in diagnostics:
        if not isinstance(diagnostic, dict):
            continue
        code = str(diagnostic.get("code") or "").lower()
        message = str(diagnostic.get("message") or "").strip()
        detail = diagnostic.get("detail") if isinstance(diagnostic.get("detail"), dict) else {}
        if "gpu" in code and ("missing" in code or "no_" in code or "unavailable" in code):
            no_gpu = True
        if "model" in code and ("missing" in code or "unavailable" in code):
            missing_models.extend(_list_strings(detail.get("models")))
            missing_models.append(detail.get("model") or detail.get("name") or message)
        elif ("node_pack" in code or "custom_node" in code) and (
            "missing" in code or "unavailable" in code
        ):
            missing_packs.extend(_list_strings(detail.get("packs")))
            missing_packs.append(detail.get("pack") or detail.get("name") or message)
        elif code:
            severity = str(diagnostic.get("severity") or "").lower()
            if severity == "error" and message:
                validation_errors.append(message)
    return (
        _dedupe_strings(tuple(missing_models)),
        _dedupe_strings(tuple(missing_packs)),
        _dedupe_strings(tuple(validation_errors)),
        no_gpu,
    )


def _list_strings(value: Any) -> list[str]:
    if isinstance(value, str):
        return [value]
    if isinstance(value, list):
        result: list[str] = []
        for item in value:
            if isinstance(item, str):
                result.append(item)
            elif isinstance(item, dict):
                name = item.get("name") or item.get("id") or item.get("path") or item.get("pack")
                if isinstance(name, str):
                    result.append(name)
        return result
    if isinstance(value, dict):
        return [str(key) for key in value]
    return []


def _explicitly_missing_names(value: Any) -> list[str]:
    if isinstance(value, dict):
        iterable = value.values()
    elif isinstance(value, list):
        iterable = value
    else:
        return []
    result: list[str] = []
    for item in iterable:
        if isinstance(item, str):
            continue
        if not isinstance(item, dict):
            continue
        missing = (
            item.get("missing") is True
            or item.get("available") is False
            or item.get("present") is False
            or item.get("ready") is False
        )
        if not missing:
            continue
        name = item.get("name") or item.get("id") or item.get("path") or item.get("pack")
        if isinstance(name, str) and name.strip():
            result.append(name)
    return result


def _missing_models_from_schema_choices(
    nodes_raw: list[Any],
    *,
    node_schemas: dict[str, Any],
) -> tuple[str, ...]:
    missing: list[str] = []
    for node in nodes_raw:
        if not isinstance(node, dict):
            continue
        class_type = str(node.get("class_type") or node.get("type") or "")
        schema = node_schemas.get(class_type)
        inputs = getattr(schema, "inputs", None)
        if not isinstance(inputs, dict):
            continue
        widget_values = node.get("widgets_values")
        widget_index = 0
        for input_name, spec in inputs.items():
            choices = getattr(spec, "choices", None)
            if not choices or not _modelish_input_name(input_name):
                if not _link_only_spec(spec):
                    widget_index += 1
                continue
            value = _node_input_widget_value(node, input_name)
            if value is None and isinstance(widget_values, list) and widget_index < len(widget_values):
                value = widget_values[widget_index]
            if value is not None and str(value) not in {str(choice) for choice in choices}:
                missing.append(str(value))
            if not _link_only_spec(spec):
                widget_index += 1
    return _dedupe_strings(tuple(missing))


def _node_input_widget_value(node: dict[str, Any], input_name: str) -> Any:
    inputs = node.get("inputs")
    if not isinstance(inputs, list):
        return None
    for item in inputs:
        if isinstance(item, dict) and item.get("name") == input_name:
            return item.get("widget")
    return None


def _modelish_input_name(input_name: str) -> bool:
    lowered = input_name.lower()
    return any(
        marker in lowered
        for marker in ("model", "ckpt", "checkpoint", "vae", "clip", "lora", "unet")
    )


def _link_only_spec(spec: Any) -> bool:
    typ = str(getattr(spec, "type", "") or "").upper()
    return typ in {"MODEL", "CLIP", "VAE", "IMAGE", "LATENT", "CONDITIONING", "MASK"}


def _input_is_required(
    class_type: str,
    input_name: str,
    *,
    schema_provider: Any = None,
) -> bool:
    """Check object_info whether *input_name* on *class_type* is required.

    Falls back safely to ``False`` when object_info is unavailable,
    the class is unknown, or the input is not found.
    """
    get_schema = getattr(schema_provider, "get_schema", None)
    if callable(get_schema):
        try:
            schema = get_schema(class_type)
        except Exception:
            schema = None
        inputs = getattr(schema, "inputs", None)
        if isinstance(inputs, dict):
            spec = inputs.get(input_name)
            return bool(getattr(spec, "required", False)) if spec is not None else False

    try:
        from vibecomfy.porting.object_info import get_class
    except ImportError:
        return False

    entry = get_class(class_type)
    if entry is None:
        return False

    inputs = entry.get("inputs")
    if not isinstance(inputs, dict):
        return False

    # Check both "required" and "optional" sections.
    required_inputs = inputs.get("required")
    if isinstance(required_inputs, dict) and input_name in required_inputs:
        return True

    # If it's in optional, it's not required.
    # If it's in neither, we conservatively assume not required.
    return False


def schema_backed_unknown_class_types(
    graph: dict[str, Any] | None,
) -> tuple[str, ...]:
    """Return class types present in *graph* that object_info does not know.

    Convenience wrapper that delegates to :func:`collect_topology_evidence`
    and extracts the ``unknown_class_types`` field.

    Returns an empty tuple when the graph is ``None`` or empty.
    """
    evidence = collect_topology_evidence(graph, schema_available=True)
    return evidence.unknown_class_types


# ── scoped diff computation (M3) ──────────────────────────────────────────────


def compute_scoped_diff(
    original_graph: dict[str, Any] | None,
    candidate_graph: dict[str, Any] | None,
    *,
    topology: TopologyFindings | None = None,
    readiness: ReadinessReport | None = None,
    candidate_topology: TopologyFindings | None = None,
    candidate_readiness: ReadinessReport | None = None,
    target_node_ids: tuple[str, ...] = (),
) -> ScopedDiff:
    """Compute a stable scoped diff between *original_graph* and *candidate_graph*.

    Produces a :class:`ScopedDiff` with changed/added/removed/untouched node
    ids, link summaries, stable dot paths, before/after hashes, and
    candidate-eligibility blockers.

    Parameters
    ----------
    original_graph:
        The current graph dict (before the candidate edit).
    candidate_graph:
        The proposed post-edit graph dict.
    topology:
        Optional pre-computed :class:`TopologyFindings` for the original
        graph.  Topology blockers disqualify candidate eligibility.
    readiness:
        Optional pre-computed :class:`ReadinessReport` for the runtime
        environment.  Readiness blockers disqualify candidate eligibility.

    Returns
    -------
    ScopedDiff
        Always returns a populated instance — never raises.
    """
    eligibility_blockers: list[str] = []

    # ── 1. Missing evidence checks ──────────────────────────────────────
    missing_evidence = False
    if original_graph is None or not isinstance(original_graph, dict):
        missing_evidence = True
        eligibility_blockers.append("no_original_graph")
    if candidate_graph is None or not isinstance(candidate_graph, dict):
        missing_evidence = True
        eligibility_blockers.append("no_candidate_graph")
    if topology is None or readiness is None:
        missing_evidence = True
    if missing_evidence:
        eligibility_blockers.insert(0, "missing_evidence")

    # ── 2. Hash computation ─────────────────────────────────────────────
    before_hash = _hash_graph(original_graph)
    after_hash = _hash_graph(candidate_graph)

    # ── 3. Node-level diff ──────────────────────────────────────────────
    orig_nodes_raw = (
        original_graph.get("nodes") if isinstance(original_graph, dict) else None
    )
    cand_nodes_raw = (
        candidate_graph.get("nodes") if isinstance(candidate_graph, dict) else None
    )

    orig_nodes: list[dict] = (
        [n for n in orig_nodes_raw if isinstance(n, dict)]
        if isinstance(orig_nodes_raw, list)
        else []
    )
    cand_nodes: list[dict] = (
        [n for n in cand_nodes_raw if isinstance(n, dict)]
        if isinstance(cand_nodes_raw, list)
        else []
    )

    # Build node-id→node maps, using string keys for stable comparison.
    orig_node_map: dict[str, dict] = {}
    for n in orig_nodes:
        nid = str(n.get("id", ""))
        if nid:
            orig_node_map[nid] = n

    cand_node_map: dict[str, dict] = {}
    for n in cand_nodes:
        nid = str(n.get("id", ""))
        if nid:
            cand_node_map[nid] = n

    orig_ids = set(orig_node_map)
    cand_ids = set(cand_node_map)

    added_ids = sorted(cand_ids - orig_ids, key=_node_id_sort_key)
    removed_ids = sorted(orig_ids - cand_ids, key=_node_id_sort_key)
    common_ids = orig_ids & cand_ids

    # Changed nodes: nodes present in both but with different content.
    changed_ids: list[str] = []
    for nid in sorted(common_ids, key=_node_id_sort_key):
        if _node_content_hash(orig_node_map[nid]) != _node_content_hash(cand_node_map[nid]):
            changed_ids.append(nid)

    untouched_ids = sorted(
        common_ids - set(changed_ids), key=_node_id_sort_key
    )

    # ── 4. Link-level diff ──────────────────────────────────────────────
    orig_links_raw = (
        original_graph.get("links") if isinstance(original_graph, dict) else None
    )
    cand_links_raw = (
        candidate_graph.get("links") if isinstance(candidate_graph, dict) else None
    )

    orig_links: list[dict] = (
        [l for l in orig_links_raw if isinstance(l, (dict, list))]
        if isinstance(orig_links_raw, list)
        else []
    )
    cand_links: list[dict] = (
        [l for l in cand_links_raw if isinstance(l, (dict, list))]
        if isinstance(cand_links_raw, list)
        else []
    )

    orig_link_ids = {_link_identity(l) for l in orig_links}
    cand_link_ids = {_link_identity(l) for l in cand_links}

    added_link_ids = cand_link_ids - orig_link_ids
    removed_link_ids = orig_link_ids - cand_link_ids

    # Changed links: same identity but different content.
    changed_link_ids: set[str] = set()
    orig_link_map = {_link_identity(l): l for l in orig_links}
    cand_link_map = {_link_identity(l): l for l in cand_links}
    for lid in orig_link_ids & cand_link_ids:
        if _link_content_hash(orig_link_map[lid]) != _link_content_hash(cand_link_map[lid]):
            changed_link_ids.add(lid)

    # ── 5. Stable dot paths ─────────────────────────────────────────────
    diff_paths: list[str] = []
    # Node-level paths
    for nid in added_ids:
        diff_paths.append(f"nodes.added.{nid}")
    for nid in removed_ids:
        diff_paths.append(f"nodes.removed.{nid}")
    for nid in changed_ids:
        # Compute which fields changed within the node.
        orig_node = orig_node_map[nid]
        cand_node = cand_node_map[nid]
        diff_paths.extend(
            f"nodes.{nid}.{path}"
            for path in _diff_value_paths(orig_node, cand_node)
        )
    # Link-level paths
    for lid in sorted(added_link_ids, key=_link_id_sort_key):
        diff_paths.append(f"links.added.{lid}")
    for lid in sorted(removed_link_ids, key=_link_id_sort_key):
        diff_paths.append(f"links.removed.{lid}")
    for lid in sorted(changed_link_ids, key=_link_id_sort_key):
        diff_paths.append(f"links.changed.{lid}")

    # ── 6. Candidate eligibility blockers ───────────────────────────────
    has_topology_blockers = (
        topology is not None and topology.has_blockers
    )
    has_readiness_blockers = (
        readiness is not None and readiness.has_blockers
    )
    has_candidate_topology_blockers = (
        candidate_topology is not None and candidate_topology.has_blockers
    )
    has_candidate_readiness_blockers = (
        candidate_readiness is not None and candidate_readiness.has_blockers
    )
    has_schema_unavailable = (
        topology is not None and topology.schema_available is False
    )

    if has_topology_blockers:
        eligibility_blockers.append("unresolved_topology_blockers")
    if has_readiness_blockers:
        eligibility_blockers.append("unresolved_readiness_blockers")
    if has_candidate_topology_blockers:
        eligibility_blockers.append("candidate_topology_blockers")
    if has_candidate_readiness_blockers:
        eligibility_blockers.append("candidate_readiness_blockers")
    if has_schema_unavailable:
        eligibility_blockers.append("schema_unavailable")

    # Check for no diff at all.
    has_any_diff = bool(
        changed_ids or added_ids or removed_ids
        or changed_link_ids or added_link_ids or removed_link_ids
    )
    if not has_any_diff:
        eligibility_blockers.append("no_diff")

    # Check for broad unrelated diff (>50% nodes changed/added/removed).
    total_orig = len(orig_ids)
    if total_orig > 0:
        affected = len(changed_ids) + len(removed_ids) + len(added_ids)
        if affected / total_orig > 0.5:
            eligibility_blockers.append("broad_unrelated_diff")

    normalized_targets = tuple(
        str(node_id).strip()
        for node_id in target_node_ids
        if str(node_id).strip()
    )
    target_matched = True
    if normalized_targets:
        touched_nodes = set(changed_ids) | set(added_ids) | set(removed_ids)
        for link_id in [*added_link_ids, *removed_link_ids, *changed_link_ids]:
            raw_link = cand_link_map.get(link_id) or orig_link_map.get(link_id)
            if raw_link is None:
                continue
            link_payload = _link_serializable(raw_link)
            for key in ("origin_node", "target_node"):
                value = link_payload.get(key)
                if value is not None:
                    touched_nodes.add(str(value))
        target_matched = bool(touched_nodes & set(normalized_targets))
        if not target_matched:
            eligibility_blockers.append("target_mismatch")

    candidate_eligible = (
        len(eligibility_blockers) == 0
        and original_graph is not None
        and candidate_graph is not None
    )

    # ── 7. Build summary ────────────────────────────────────────────────
    summary_parts: list[str] = []
    if changed_ids:
        summary_parts.append(f"{len(changed_ids)} changed node(s)")
    if added_ids:
        summary_parts.append(f"{len(added_ids)} added node(s)")
    if removed_ids:
        summary_parts.append(f"{len(removed_ids)} removed node(s)")
    if untouched_ids:
        summary_parts.append(f"{len(untouched_ids)} untouched node(s)")
    if changed_link_ids:
        summary_parts.append(f"{len(changed_link_ids)} changed link(s)")
    if added_link_ids:
        summary_parts.append(f"{len(added_link_ids)} added link(s)")
    if removed_link_ids:
        summary_parts.append(f"{len(removed_link_ids)} removed link(s)")
    if not summary_parts:
        summary_parts.append("no changes detected")
    if eligibility_blockers:
        summary_parts.append(
            f"ineligible: {'; '.join(eligibility_blockers)}"
        )

    return ScopedDiff(
        changed_nodes=tuple(changed_ids),
        added_nodes=tuple(added_ids),
        removed_nodes=tuple(removed_ids),
        untouched_nodes=tuple(untouched_ids),
        changed_links=tuple(sorted(changed_link_ids, key=_link_id_sort_key)),
        added_links=tuple(
            _link_serializable(cand_link_map[lid])
            for lid in sorted(added_link_ids, key=_link_id_sort_key)
        ),
        removed_links=tuple(
            _link_serializable(orig_link_map[lid])
            for lid in sorted(removed_link_ids, key=_link_id_sort_key)
        ),
        diff_paths=tuple(diff_paths),
        target_node_ids=normalized_targets,
        target_matched=target_matched,
        before_hash=before_hash,
        after_hash=after_hash,
        candidate_eligible=candidate_eligible,
        eligibility_blockers=tuple(eligibility_blockers),
        summary="; ".join(summary_parts),
    )


# ── internal diff helpers ─────────────────────────────────────────────────────


def _hash_graph(graph: dict[str, Any] | None) -> str:
    """Compute a stable SHA-256 hash of *graph* (deterministic JSON serialization)."""
    import hashlib
    import json

    if graph is None:
        return ""
    try:
        serialized = json.dumps(graph, sort_keys=True, default=str)
    except (TypeError, ValueError):
        serialized = str(graph)
    return hashlib.sha256(serialized.encode("utf-8")).hexdigest()


def _node_content_hash(node: dict) -> str:
    """Stable hash of a single node dict for change detection."""
    import hashlib
    import json

    node = _node_for_scoped_diff(node)
    try:
        serialized = json.dumps(node, sort_keys=True, default=str)
    except (TypeError, ValueError):
        serialized = str(node)
    return hashlib.sha256(serialized.encode("utf-8")).hexdigest()


def _node_for_scoped_diff(node: dict) -> dict:
    """Return node content with edit-engine identity stamps removed.

    The batch editor may stamp ``properties.vibecomfy_uid`` onto otherwise
    untouched nodes so later guards can address them. That identity metadata is
    not a user-visible graph revision and must not broaden a scoped diff.
    """
    import copy

    cleaned = copy.deepcopy(node)
    properties = cleaned.get("properties")
    if isinstance(properties, dict):
        properties.pop("vibecomfy_uid", None)
        if not properties:
            cleaned.pop("properties", None)
    return cleaned


def _link_content_hash(link: dict | list) -> str:
    """Stable hash of a single link for change detection."""
    import hashlib
    import json

    if isinstance(link, list):
        try:
            serialized = json.dumps(link, sort_keys=True, default=str)
        except (TypeError, ValueError):
            serialized = str(link)
    else:
        try:
            serialized = json.dumps(link, sort_keys=True, default=str)
        except (TypeError, ValueError):
            serialized = str(link)
    return hashlib.sha256(serialized.encode("utf-8")).hexdigest()


def _diff_value_paths(before: Any, after: Any, prefix: str = "") -> tuple[str, ...]:
    """Return stable dot/index paths for changed leaves between two JSON-ish values."""
    if before == after:
        return ()
    if isinstance(before, dict) and isinstance(after, dict):
        paths: list[str] = []
        for key in sorted(set(before) | set(after), key=str):
            child = f"{prefix}.{key}" if prefix else str(key)
            if child == "properties.vibecomfy_uid":
                continue
            paths.extend(_diff_value_paths(before.get(key), after.get(key), child))
        return tuple(paths)
    if isinstance(before, list) and isinstance(after, list):
        paths = []
        max_len = max(len(before), len(after))
        for idx in range(max_len):
            bv = before[idx] if idx < len(before) else None
            av = after[idx] if idx < len(after) else None
            child = f"{prefix}.{idx}" if prefix else str(idx)
            paths.extend(_diff_value_paths(bv, av, child))
        return tuple(paths)
    return (prefix or "value",)


def _link_identity(link: dict | list) -> str:
    """Return a stable identity string for *link* for set membership.

    Uses link_id when available (both list and dict shapes), falling back
    to a hash of the endpoint tuple.
    """
    if isinstance(link, list) and len(link) >= 1:
        return f"link:{link[0]}"
    if isinstance(link, dict):
        lid = link.get("id") or link.get("link_id")
        if lid is not None:
            return f"link:{lid}"
        # Fallback: identity from endpoints.
        origin = link.get("origin_id", "?")
        target = link.get("target_id", "?")
        return f"link:{origin}->{target}"
    # Fallback: hash the whole thing.
    return f"link:hash:{_link_content_hash(link)[:8]}"


def _link_serializable(link: dict | list) -> dict[str, Any]:
    """Convert a link to a serializable dict form for ScopedDiff."""
    if isinstance(link, list):
        return {
            "link_id": link[0] if len(link) > 0 else None,
            "origin_node": link[1] if len(link) > 1 else None,
            "origin_slot": link[2] if len(link) > 2 else None,
            "target_node": link[3] if len(link) > 3 else None,
            "target_slot": link[4] if len(link) > 4 else None,
            "type": link[5] if len(link) > 5 else None,
        }
    # dict shape
    return {
        "link_id": link.get("id") or link.get("link_id"),
        "origin_node": link.get("origin_id"),
        "origin_slot": link.get("origin_slot"),
        "target_node": link.get("target_id"),
        "target_slot": link.get("target_slot"),
        "type": link.get("type"),
    }


def _node_id_sort_key(node_id: str) -> tuple[int, str]:
    """Sort key that tries to sort numerically, falling back to string."""
    try:
        return (0, str(int(node_id)).zfill(8))
    except (ValueError, TypeError):
        return (1, node_id)


def _link_id_sort_key(link_id: str) -> tuple[int, str]:
    """Sort key for link identity strings that tries numeric parsing."""
    # link_id format: "link:123" or "link:hash:abc123" or "link:1->2"
    parts = link_id.split(":", 1)
    if len(parts) == 2:
        num_part = parts[1].split("->")[0].split(":")[0]
        try:
            return (0, str(int(num_part)).zfill(8))
        except (ValueError, TypeError):
            pass
    return (1, link_id)


__all__ = [
    "collect_readiness_evidence",
    "collect_topology_evidence",
    "compute_scoped_diff",
    "schema_backed_unknown_class_types",
]
