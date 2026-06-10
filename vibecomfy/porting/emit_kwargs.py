"""emit_kwargs.py — variable-name, topology, and node-kwargs helpers.

This module is the foundation seam carved from :mod:`vibecomfy.porting.emitter`
as part of the M2 structural-decomposition epic (Step 4).  It is a leaf-level
module: it does not import from any other ``emit_*.py`` module.

All names exported here remain importable from ``vibecomfy.porting.emitter``
via explicit re-exports so that existing callers are unaffected.
"""

from __future__ import annotations

import keyword
import re
from typing import TYPE_CHECKING, Any, Mapping

from vibecomfy.errors import ArityDisagreementError
from vibecomfy.porting.object_info import (
    class_has_list_output,
    class_output_count,
)
from vibecomfy.porting.widget_aliases import resolve_widget_key_with_provenance
from vibecomfy.porting.widget_schema import WIDGET_SCHEMA

if TYPE_CHECKING:
    pass


__all__ = [
    # link-type checks
    "_is_link",
    "_is_any_link",
    "_ui_output_names",
    # variable-name helpers
    "_UUID_RE",
    "_safe_var",
    "_connection_role_name",
    "_empty_text_role",
    "_id_sort_key",
    "_topological_node_order",
    "_compute_variable_names",
    "_locked_variable_uid_map",
    "_apply_locked_variable_names",
    "_is_valid_locked_variable_alias",
    # output-variable-name helpers
    "_compute_output_variable_names",
    "_SHADOWING_OUTPUT_NAMES",
    "_SHADOWING_OUTPUT_ALIASES",
    "_shadowing_output_prefix",
    "_safe_output_var_name",
    "_schema_output_names_for_unpack",
    "_declared_ui_output_names",
    "_has_out_of_range_edge",
    "_class_collision_suffix",
    "_live_output_slots_for_function",
    "_edges_in_with_subgraph_external_refs",
    "_assignment_target",
    "_first_output_var",
    # value formatting
    "_format_value",
    "_is_schema_default",
    "_format_metadata_dict",
    # output-name resolution
    "_node_output_names",
    "_declared_output_names_for_call_metadata",
    "_safe_output_name",
    "_output_fallback_diagnostic",
    "_is_schema_confirmed_single_output",
    "_is_single_output_ref",
    # edge-reference expressions
    "_node_binding_expr",
    "_edge_ref_expr",
    "_wrapper_kwarg_name",
    # Power Lora Loader widget helpers
    "_translate_power_lora_loader_widget",
    "_power_lora_widget_index",
    "_is_power_lora_config",
    # emission diagnostics collector
    "_collect_emission_diagnostics",
    # core node-kwargs builder
    "_node_kwargs",
]

# ---------------------------------------------------------------------------
# Model file suffixes (used by _format_value for path normalization)
# ---------------------------------------------------------------------------

_MODEL_FILE_SUFFIXES: tuple[str, ...] = (
    ".safetensors", ".ckpt", ".pt", ".bin", ".pth", ".gguf", ".onnx",
)

# ---------------------------------------------------------------------------
# Shadowing output-variable name constants
# ---------------------------------------------------------------------------

_SHADOWING_OUTPUT_NAMES: frozenset[str] = frozenset(
    {
        "int",
        "float",
        "bool",
        "boolean",
        "str",
        "list",
        "bytes",
        "dict",
        "set",
        "type",
        "id",
        "input",
    }
)

_SHADOWING_OUTPUT_ALIASES: dict[str, str] = {
    "boolean": "bool",
}


# ---------------------------------------------------------------------------
# UUID pattern (used by _safe_var and _is_single_output_ref)
# ---------------------------------------------------------------------------

_UUID_RE = re.compile(
    r"^[0-9a-f]{8}-[0-9a-f]{4}-[0-9a-f]{4}-[0-9a-f]{4}-[0-9a-f]{12}$",
    re.IGNORECASE,
)


# ---------------------------------------------------------------------------
# Link-type checks
# ---------------------------------------------------------------------------

def _is_link(value: Any) -> bool:
    if not (isinstance(value, list) and len(value) == 2):
        return False
    nid, slot = value
    if not isinstance(slot, int):
        return False
    return all(part.isdigit() for part in str(nid).split(":"))


def _is_any_link(value: Any) -> bool:
    return isinstance(value, list) and len(value) == 2 and isinstance(value[1], int)


def _ui_output_names(ui: Any) -> list[str]:
    if not isinstance(ui, Mapping):
        return []
    names: list[str] = []
    for item in ui.get("outputs") or ():
        if isinstance(item, Mapping):
            names.append(str(item.get("name") or ""))
    return names


# ---------------------------------------------------------------------------
# Variable-name helpers
# ---------------------------------------------------------------------------

def _safe_var(class_type: str) -> str:
    # v2.6.4 Fix 6: UUID class types (ComfyUI subgraphs) get a short, readable
    # variable name based on the first 8 chars of the UUID rather than the
    # full 36-char hyphen-replaced string. So
    # `7b34ab90-36f9-45ba-a665-71d418f0df18` becomes `subgraph_7b34ab90`
    # instead of `n_7b34ab90_36f9_45ba_a665_71d418f0df18`.
    if _UUID_RE.match(class_type):
        short = class_type.split("-", 1)[0].lower()
        return f"subgraph_{short}"
    name = re.sub(r"[^a-zA-Z0-9_]", "_", class_type.lower())
    if not name or name[0].isdigit():
        name = f"n_{name}"
    if keyword.iskeyword(name):
        name = f"{name}_"
    return name


def _connection_role_name(workflow_nodes: dict[str, Any], edges_out: dict[str, list[tuple[str, str]]]) -> dict[str, str]:
    roles: dict[str, str] = {}
    for src_node_id, node in workflow_nodes.items():
        if node.class_type != "CLIPTextEncode":
            continue
        for to_node, to_input in edges_out.get(src_node_id, []):
            target = workflow_nodes.get(to_node)
            if target is None:
                continue
            if target.class_type == "KSampler" and to_input in ("positive", "negative"):
                roles[src_node_id] = to_input
                break
            if target.class_type in ("CFGGuider", "MultimodalGuider") and to_input in ("positive", "negative"):
                roles[src_node_id] = to_input
                break
    return roles


def _empty_text_role(workflow_nodes: dict[str, Any]) -> dict[str, str]:
    roles: dict[str, str] = {}
    for nid, node in workflow_nodes.items():
        if node.class_type != "CLIPTextEncode":
            continue
        text_value = node.inputs.get("text", node.widgets.get("text", node.widgets.get("widget_0")))
        if isinstance(text_value, str) and text_value.strip() == "":
            roles.setdefault(nid, "negative")
    return roles


def _id_sort_key(nid: str) -> tuple[Any, ...]:
    parts = str(nid).split(":")
    if all(part.isdigit() for part in parts):
        return tuple(int(part) for part in parts)
    return (1 << 31, str(nid))


def _topological_node_order(nodes: dict[str, Any], edges_in: dict[str, list[Any]]) -> list[str]:
    deps: dict[str, set[str]] = {nid: set() for nid in nodes}
    for nid, node in nodes.items():
        for edge in edges_in.get(nid, []):
            if edge.from_node in nodes:
                deps[nid].add(edge.from_node)
        for value in list(node.inputs.values()) + list(node.widgets.values()):
            if _is_link(value):
                src = str(value[0])
                if src in nodes:
                    deps[nid].add(src)

    pending = set(nodes.keys())
    out: list[str] = []
    while pending:
        ready = sorted((nid for nid in pending if not (deps[nid] - set(out))), key=_id_sort_key)
        if not ready:
            out.extend(sorted(pending, key=_id_sort_key))
            break
        for nid in ready:
            out.append(nid)
            pending.discard(nid)
    return out


def _compute_variable_names(workflow_nodes: dict[str, Any], edges: list[Any]) -> dict[str, str]:
    edges_out: dict[str, list[tuple[str, str]]] = {}
    for edge in edges:
        edges_out.setdefault(edge.from_node, []).append((edge.to_node, edge.to_input))

    role_conn = _connection_role_name(workflow_nodes, edges_out)
    role_empty = _empty_text_role(workflow_nodes)
    sorted_ids = sorted(workflow_nodes.keys(), key=_id_sort_key)

    used: dict[str, int] = {}
    var_names: dict[str, str] = {}
    for nid in sorted_ids:
        node = workflow_nodes[nid]
        base = role_conn.get(nid) or role_empty.get(nid) or _safe_var(node.class_type)
        used[base] = used.get(base, 0) + 1
        var_names[nid] = base if used[base] == 1 else f"{base}_{used[base]}"
    return var_names


def _locked_variable_uid_map(
    workflow_nodes: Mapping[str, Any],
    *,
    scope_path: str = "",
    diagnostics: "list[Any] | None" = None,
) -> dict[str, str]:
    from vibecomfy.porting.uid import make_uid
    # Import EmissionDiagnostic and warning constants lazily to avoid circular
    # import (emitter.py imports from emit_kwargs.py at module level).
    from vibecomfy.porting.emitter import (  # noqa: PLC0415
        EmissionDiagnostic,
        READABILITY_WARNING_LOCKED_VARIABLE_UID_COLLISION,
    )

    uid_to_nid: dict[str, str] = {}
    for nid, node in workflow_nodes.items():
        candidates: list[str] = []
        node_uid = str(getattr(node, "uid", "") or "")
        if node_uid:
            candidates.append(node_uid)
        raw_ui = getattr(node, "metadata", {}).get("_ui") if hasattr(node, "metadata") else None
        properties = raw_ui.get("properties") if isinstance(raw_ui, Mapping) else None
        ui_uid = properties.get("vibecomfy_uid") if isinstance(properties, Mapping) else None
        if ui_uid is not None:
            ui_uid_str = str(ui_uid)
            candidates.append(ui_uid_str)
            if scope_path:
                candidates.append(make_uid(scope_path, ui_uid_str))
        if scope_path and node_uid and "#" not in node_uid:
            candidates.append(make_uid(scope_path, node_uid))

        for uid in dict.fromkeys(candidates):
            previous = uid_to_nid.get(uid)
            if previous is not None and previous != str(nid):
                if diagnostics is not None:
                    diagnostics.append(
                        EmissionDiagnostic(
                            code=READABILITY_WARNING_LOCKED_VARIABLE_UID_COLLISION,
                            message=(
                                f"Locked variable uid {uid!r} maps to multiple node ids "
                                f"({previous!r}, {str(nid)!r}); ignoring the later binding."
                            ),
                            severity="error",
                            node_id=str(nid),
                            class_type=str(getattr(node, "class_type", "")),
                            detail={"uid": uid, "existing_node_id": previous, "colliding_node_id": str(nid)},
                        )
                    )
                continue
            uid_to_nid[uid] = str(nid)
    return uid_to_nid


def _is_valid_locked_variable_alias(alias: str) -> bool:
    return alias.isidentifier() and not keyword.iskeyword(alias)


def _apply_locked_variable_names(
    workflow_nodes: Mapping[str, Any],
    var_names: dict[str, str],
    *,
    variable_name_locks: Mapping[str, str] | None,
    strict: bool,
    diagnostics: "list[Any] | None",
    scope_path: str = "",
) -> None:
    if not variable_name_locks:
        return

    # Lazy import to avoid circular dependency
    from vibecomfy.porting.emitter import (  # noqa: PLC0415
        EmissionDiagnostic,
        READABILITY_WARNING_LOCKED_VARIABLE_ALIAS_MISSING,
        READABILITY_WARNING_LOCKED_VARIABLE_ALIAS_INVALID,
        READABILITY_WARNING_LOCKED_VARIABLE_ALIAS_COLLISION,
    )

    uid_to_nid = _locked_variable_uid_map(workflow_nodes, scope_path=scope_path, diagnostics=diagnostics)
    locked_by_nid: dict[str, tuple[str, str]] = {}
    for uid, alias in sorted((str(key), str(value)) for key, value in variable_name_locks.items()):
        nid = uid_to_nid.get(uid)
        if nid is None:
            if strict and diagnostics is not None:
                diagnostics.append(
                    EmissionDiagnostic(
                        code=READABILITY_WARNING_LOCKED_VARIABLE_ALIAS_MISSING,
                        message=f"Locked variable uid {uid!r} was not present in emitted scope {scope_path!r}.",
                        severity="error",
                        detail={"uid": uid, "alias": alias, "scope_path": scope_path},
                    )
                )
            continue
        if not _is_valid_locked_variable_alias(alias):
            if diagnostics is not None:
                diagnostics.append(
                    EmissionDiagnostic(
                        code=READABILITY_WARNING_LOCKED_VARIABLE_ALIAS_INVALID,
                        message=f"Locked variable alias {alias!r} for uid {uid!r} is not a valid Python variable name.",
                        severity="error",
                        node_id=nid,
                        class_type=str(getattr(workflow_nodes.get(nid), "class_type", "")),
                        detail={"uid": uid, "alias": alias, "scope_path": scope_path},
                    )
                )
            continue
        locked_by_nid[nid] = (uid, alias)

    aliases_to_nids: dict[str, list[str]] = {}
    for nid, (_uid, alias) in locked_by_nid.items():
        aliases_to_nids.setdefault(alias, []).append(nid)
    colliding_locked_aliases = {alias for alias, nids in aliases_to_nids.items() if len(nids) > 1}

    generated_unlocked = {alias: nid for nid, alias in var_names.items() if nid not in locked_by_nid}
    for nid, (uid, alias) in locked_by_nid.items():
        collision_node = generated_unlocked.get(alias)
        if alias in colliding_locked_aliases or collision_node is not None:
            if diagnostics is not None:
                diagnostics.append(
                    EmissionDiagnostic(
                        code=READABILITY_WARNING_LOCKED_VARIABLE_ALIAS_COLLISION,
                        message=f"Locked variable alias {alias!r} for uid {uid!r} collides with another emitted variable.",
                        severity="error",
                        node_id=nid,
                        class_type=str(getattr(workflow_nodes.get(nid), "class_type", "")),
                        detail={
                            "uid": uid,
                            "alias": alias,
                            "scope_path": scope_path,
                            "colliding_node_id": collision_node,
                            "locked_collision": alias in colliding_locked_aliases,
                        },
                    )
                )
            continue
        var_names[nid] = alias


# ---------------------------------------------------------------------------
# Output variable names
# ---------------------------------------------------------------------------

def _class_collision_suffix(class_type: str) -> str:
    parts = re.findall(r"[A-Z]+(?=[A-Z][a-z]|$)|[A-Z]?[a-z]+|\d+", class_type)
    return _safe_var(parts[0] if parts else class_type)


def _shadowing_output_prefix(class_type: str) -> str:
    if class_type == "SimpleCalculatorKJ":
        return "calc"
    if class_type in {"SimpleMath", "SimpleMath+"}:
        return "math"
    return _class_collision_suffix(class_type)


def _safe_output_var_name(output_name: str, prefix: str) -> str:
    normalized = str(output_name).lower()
    base = _safe_var(normalized)
    if base in _SHADOWING_OUTPUT_NAMES:
        return f"{prefix}_{_SHADOWING_OUTPUT_ALIASES.get(base, base)}"
    return base


def _declared_ui_output_names(node: Any) -> list[str]:
    raw_ui = getattr(node, "metadata", {}).get("_ui") if hasattr(node, "metadata") else None
    outputs = raw_ui.get("outputs") if isinstance(raw_ui, Mapping) else None
    if not isinstance(outputs, list):
        return []
    slots: dict[int, str] = {}
    max_slot = -1
    for index, output in enumerate(outputs):
        if not isinstance(output, Mapping):
            continue
        slot = output.get("slot_index", index)
        try:
            slot_index = int(slot)
        except (TypeError, ValueError):
            slot_index = index
        if slot_index < 0:
            continue
        max_slot = max(max_slot, slot_index)
        name = output.get("name")
        slots[slot_index] = name if isinstance(name, str) else ""
    if max_slot < 0:
        return []
    return [slots.get(slot, "") for slot in range(max_slot + 1)]


def _node_output_names(node: Any) -> list[str]:
    """Return output names for `_outputs` emission, preserving partial evidence.

    Unlike the old all-truthy gate, this always returns the full list from
    metadata so that `_outputs` is emitted even when some names are blank.
    The per-slot safety decision for `.out('name')` is made separately by
    `_safe_output_name` during incoming edge formatting.
    """
    output_names = getattr(node, "metadata", {}).get("output_names")
    if not isinstance(output_names, (list, tuple)):
        return []
    result: list[str] = []
    for name in output_names:
        if isinstance(name, str) and name:
            result.append(name)
        else:
            result.append("")
    return result


def _schema_output_names_for_unpack(node: Any) -> list[str]:
    # Lazy import to avoid circular dependency
    from vibecomfy.porting.emitter import (  # noqa: PLC0415
        _node_local_output_names,
        _node_local_arity_check,
    )

    ui_names = _declared_ui_output_names(node)
    metadata_names = _node_output_names(node)
    cache_names: list[str] = []
    try:
        cache_names = [str(name) for name in _node_local_output_names(node) if str(name)]
    except Exception:
        cache_names = []
    if ui_names and metadata_names and len(ui_names) != len(metadata_names):
        raise ArityDisagreementError(
            (
                f"output arity disagreement for {node.class_type}: metadata declares "
                f"{len(metadata_names)} outputs but UI declares {len(ui_names)}. "
                "Refresh the object_info schema snapshot."
            ),
            class_type=str(node.class_type),
            snapshot_pack=None,
            snapshot_version=None,
            snapshot_output_count=len(metadata_names),
            ui_output_count=len(ui_names),
        )
    ui_output_count = len(ui_names) if ui_names else None
    _node_local_arity_check(node, ui_output_count)
    if ui_names:
        return ui_names
    if metadata_names:
        return metadata_names
    return cache_names


def _declared_output_names_for_call_metadata(node: Any) -> list[str]:
    # Lazy import to avoid circular dependency
    from vibecomfy.porting.emitter import _node_local_arity_check  # noqa: PLC0415

    ui_names = _declared_ui_output_names(node)
    metadata_names = _node_output_names(node)
    if ui_names and metadata_names and len(ui_names) != len(metadata_names):
        raise ArityDisagreementError(
            (
                f"output arity disagreement for {node.class_type}: metadata declares "
                f"{len(metadata_names)} outputs but UI declares {len(ui_names)}. "
                "Refresh the object_info schema snapshot."
            ),
            class_type=str(node.class_type),
            snapshot_pack=None,
            snapshot_version=None,
            snapshot_output_count=len(metadata_names),
            ui_output_count=len(ui_names),
        )
    ui_output_count = len(ui_names) if ui_names else None
    _node_local_arity_check(node, ui_output_count)
    if ui_names:
        return ui_names
    return metadata_names


def _has_out_of_range_edge(node_id: str, output_count: int, edges: list[Any]) -> bool:
    for edge in edges:
        if str(getattr(edge, "from_node", "")) != node_id:
            continue
        try:
            slot = int(getattr(edge, "from_output"))
        except (TypeError, ValueError):
            return True
        if slot < 0 or slot >= output_count:
            return True
    return False


def _compute_output_variable_names(
    workflow_nodes: dict[str, Any],
    var_names: dict[str, str],
    edges: list[Any],
) -> dict[str, dict[int, str]]:
    # Lazy import to avoid circular dependency
    from vibecomfy.porting.emitter import _wrapper_module_for_class  # noqa: PLC0415

    unpackable: dict[str, list[str]] = {}
    for nid, node in sorted(workflow_nodes.items(), key=lambda item: _id_sort_key(item[0])):
        if _wrapper_module_for_class(str(node.class_type)) is None:
            continue
        names = _schema_output_names_for_unpack(node)
        if len(names) <= 1:
            continue
        if _has_out_of_range_edge(str(nid), len(names), edges):
            continue
        unpackable[str(nid)] = names

    used = {
        var
        for nid, var in var_names.items()
        if str(nid) not in unpackable
    }
    output_vars: dict[str, dict[int, str]] = {}
    for nid, names in unpackable.items():
        node = workflow_nodes[nid]
        suffix = _class_collision_suffix(str(node.class_type))
        shadow_prefix = _shadowing_output_prefix(str(node.class_type))
        slot_vars: dict[int, str] = {}
        for index, name in enumerate(names):
            base = _safe_output_var_name(str(name), shadow_prefix)
            candidate = base
            if candidate in used:
                ordinal = 2
                while f"{base}_{ordinal}" in used:
                    ordinal += 1
                candidate = f"{base}_{ordinal}"
            used.add(candidate)
            slot_vars[index] = candidate
        output_vars[nid] = slot_vars
    return output_vars


def _live_output_slots_for_function(
    workflow_nodes: dict[str, Any],
    edges_in: dict[str, list[Any]],
    output_var_names: dict[str, dict[int, str]],
    *,
    return_refs: tuple[tuple[str, int], ...] = (),
    tail_lines: list[str] | None = None,
) -> dict[str, set[int]]:
    live: dict[str, set[int]] = {str(nid): set() for nid in output_var_names}

    def mark(from_node: str, from_slot: int) -> None:
        if from_node in live:
            live[from_node].add(from_slot)

    for edges in edges_in.values():
        for edge in edges:
            try:
                mark(str(edge.from_node), int(edge.from_output))
            except (TypeError, ValueError):
                continue
    for node in workflow_nodes.values():
        for value in list(getattr(node, "inputs", {}).values()) + list(getattr(node, "widgets", {}).values()):
            if _is_link(value):
                mark(str(value[0]), int(value[1]))
    for node_id, slot in return_refs:
        mark(str(node_id), int(slot))

    # The ready-template finalize tail may bind output_node to the first
    # unpacked output variable of a terminal output node.
    tail_text = "\n".join(tail_lines or ())
    if "output_node=" in tail_text:
        for node_id, slot_vars in output_var_names.items():
            first_var = _first_output_var(slot_vars)
            if first_var is not None and re.search(rf"\boutput_node\s*=\s*{re.escape(first_var)}\b", tail_text):
                live[node_id].add(min(slot_vars))
    return live


def _edges_in_with_subgraph_external_refs(
    prepared: dict[str, Any],
    workflow_nodes: dict[str, Any],
    edges_in: dict[str, list[Any]],
) -> dict[str, list[Any]]:
    subgraphs: dict[str, Any] = prepared.get("subgraph_definitions") or {}
    if not subgraphs:
        return edges_in

    from vibecomfy.workflow import VibeEdge

    out = {str(node_id): list(edges) for node_id, edges in edges_in.items()}
    for node_id, node in workflow_nodes.items():
        subgraph = subgraphs.get(str(getattr(node, "class_type", "")))
        if subgraph is None:
            continue
        for port in subgraph.inputs:
            if port.external_ref is None:
                continue
            source_id, source_slot = port.external_ref
            if str(source_id) not in workflow_nodes:
                continue
            out.setdefault(str(node_id), []).append(
                VibeEdge(str(source_id), str(source_slot), str(node_id), port.name)
            )
    return out


def _assignment_target(
    var: str,
    output_vars: dict[int, str] | None,
    *,
    live_slots: set[int] | None = None,
) -> str | None:
    if not output_vars:
        return var
    ordered = sorted(output_vars)
    if live_slots is None:
        return ", ".join(output_vars[index] for index in ordered)
    if not any(index in live_slots for index in ordered):
        return None
    return ", ".join(output_vars[index] if index in live_slots else "_" for index in ordered)


def _first_output_var(output_vars: dict[int, str] | None) -> str | None:
    if not output_vars:
        return None
    first_slot = min(output_vars)
    return output_vars[first_slot]


# ---------------------------------------------------------------------------
# Value formatting
# ---------------------------------------------------------------------------

def _format_value(value: Any, *, elide_strings_over: int | None = None) -> str:
    # Normalize Windows-style backslash separators to forward slashes in model
    # file paths (e.g. 'LTXVideo\\v2\\file.safetensors' → 'LTXVideo/v2/file.safetensors').
    # ComfyUI model loaders accept either separator.
    if isinstance(value, str) and "\\" in value:
        if value.endswith(_MODEL_FILE_SUFFIXES) or any(
            f"\\{ext[1:]}" in value for ext in _MODEL_FILE_SUFFIXES
        ):
            value = value.replace("\\", "/")
    if elide_strings_over is not None and isinstance(value, str) and len(value) > elide_strings_over:
        head = repr(value[:240])
        tail = repr(value[-80:])
        n_elided = len(value) - 320
        return f"({head} + \"[...{n_elided} chars elided...]\" + {tail})"
    return repr(value)


def _is_schema_default(
    class_type: str,
    key: str,
    value: Any,
    node_metadata: Mapping[str, Any] | dict[str, Any],
    *,
    node: Any = None,
) -> bool:
    # Lazy import to avoid circular dependency
    from vibecomfy.porting.emitter import (  # noqa: PLC0415
        _CURATED_SCHEMA_DEFAULTS,
        _node_local_class_defaults,
    )
    from vibecomfy.porting.object_info import class_defaults

    keep = node_metadata.get("keep_defaults") or node_metadata.get("keep_kwargs") or ()
    if key in set(str(item) for item in keep):
        return False
    defaults = dict(_CURATED_SCHEMA_DEFAULTS.get(class_type, {}))
    try:
        if node is not None:
            defaults.update(_node_local_class_defaults(node))
        else:
            defaults.update(class_defaults(class_type))
    except Exception:
        pass
    return key in defaults and value == defaults[key]


def _format_metadata_dict(name: str, value: dict[str, Any]) -> str:
    import pprint
    formatted = pprint.pformat(value, width=110, sort_dicts=False)
    return f"{name} = {formatted}"


# ---------------------------------------------------------------------------
# Output-name resolution
# ---------------------------------------------------------------------------

def _safe_output_name(
    workflow_nodes: dict[str, Any] | None,
    from_node: str,
    from_slot: int,
) -> str | None:
    """Return the safe output name for a slot, or `None` if numeric fallback is needed.

    A name is *safe* for `.out('name')` when all of these hold:

    * *slot in range:* `from_slot` is a valid index into the source node's
      `output_names` metadata list.
    * *name non-empty:* the name at that index is a non-blank string.
    * *name unique:* the name appears exactly once in the source node's
      `output_names` list (no duplicates).
    * *name not conflicted:* the source node's metadata does not list the name
      in a `conflicted_outputs` key.
    """
    if workflow_nodes is None:
        return None
    src_node = workflow_nodes.get(from_node)
    if src_node is None:
        return None
    output_names = getattr(src_node, "metadata", {}).get("output_names")
    if not isinstance(output_names, (list, tuple)):
        return None
    if from_slot < 0 or from_slot >= len(output_names):
        return None
    name = output_names[from_slot]
    if not isinstance(name, str) or not name:
        return None
    # Duplicate check: the name must appear exactly once.
    if list(output_names).count(name) > 1:
        return None
    # Conflicted check: the name must not be in the conflicted_outputs list.
    conflicted = getattr(src_node, "metadata", {}).get("conflicted_outputs")
    if isinstance(conflicted, (list, tuple, set, frozenset)) and name in conflicted:
        return None
    return name


def _output_fallback_diagnostic(
    diagnostics: "list[Any]",
    workflow_nodes: dict[str, Any],
    from_node: str,
    from_slot: int,
    *,
    target_node: Any,
    target_input: str,
) -> None:
    """Record a diagnostic explaining why `.out(n)` was used instead of `.out('name')`.

    Only fires when the source node *has* output_names metadata - otherwise
    numeric fallback is expected and not an avoidable concern.
    """
    # Lazy import to avoid circular dependency
    from vibecomfy.porting.emitter import (  # noqa: PLC0415
        EmissionDiagnostic,
        READABILITY_WARNING_AVOIDABLE_POSITIONAL_OUTPUT,
    )

    src_node = workflow_nodes.get(from_node)
    if src_node is None:
        return

    output_names = getattr(src_node, "metadata", {}).get("output_names")
    # If the source node has no output_names metadata at all, numeric fallback
    # is the only option - no diagnostic warranted.
    if not isinstance(output_names, (list, tuple)):
        return

    src_ctype = getattr(src_node, "class_type", None)
    tgt_nid = getattr(target_node, "id", None)
    tgt_ctype = getattr(target_node, "class_type", None)

    reason_parts: list[str] = []
    if from_slot < 0 or from_slot >= len(output_names):
        reason_parts.append(
            f"slot {from_slot} out of range (source has {len(output_names)} output(s))"
        )
    else:
        name = output_names[from_slot]
        if not isinstance(name, str) or not name:
            reason_parts.append(f"output_names[{from_slot}] is blank")
        elif list(output_names).count(name) > 1:
            reason_parts.append(
                f"output_names[{from_slot}]={name!r} is duplicated in source output_names"
            )
        else:
            conflicted = getattr(src_node, "metadata", {}).get("conflicted_outputs")
            if isinstance(conflicted, (list, tuple, set, frozenset)) and name in conflicted:
                reason_parts.append(
                    f"output_names[{from_slot}]={name!r} is marked conflicted"
                )
            else:
                # Should not reach here - _safe_output_name would have succeeded.
                # Log it anyway as a safety net.
                reason_parts.append(
                    f"output_names[{from_slot}]={name!r} is not safe for named emission"
                )

    reason = "; ".join(reason_parts)
    diagnostics.append(
        EmissionDiagnostic(
            code=READABILITY_WARNING_AVOIDABLE_POSITIONAL_OUTPUT,
            message=(
                f"Edge from {from_node} ({src_ctype}).out({from_slot}) to "
                f"{tgt_nid} ({tgt_ctype}).{target_input} uses numeric .out({from_slot}) "
                f"because: {reason}"
            ),
            severity="warning",
            node_id=str(tgt_nid) if tgt_nid is not None else None,
            class_type=tgt_ctype,
            detail={
                "from_node": from_node,
                "from_slot": from_slot,
                "target_input": target_input,
                "reason": reason,
                "output_names": list(output_names),
            },
        )
    )


def _is_schema_confirmed_single_output(class_type: str, output_names: list[str] | tuple[str, ...]) -> bool:
    try:
        return class_output_count(class_type) == 1 and not class_has_list_output(class_type)
    except Exception:
        return len(output_names) == 1


def _is_single_output_ref(
    workflow_nodes: dict[str, Any] | None,
    from_node: str,
    from_slot: int,
) -> bool:
    if from_slot != 0 or workflow_nodes is None:
        return False
    src_node = workflow_nodes.get(from_node)
    if src_node is None:
        return False
    output_names = _node_output_names(src_node)
    if _UUID_RE.match(str(src_node.class_type)) and len(output_names) == 1:
        return True
    return _is_schema_confirmed_single_output(str(src_node.class_type), output_names)


# ---------------------------------------------------------------------------
# Edge-reference expressions
# ---------------------------------------------------------------------------

def _node_binding_expr(node_id: str, var_names: dict[str, str]) -> str:
    # Lazy import to avoid circular dependency
    from vibecomfy.porting.emitter import _wrapper_module_for_class  # noqa: PLC0415

    var = var_names.get(str(node_id))
    if var is not None and _wrapper_module_for_class(var.split("_", 1)[0]) is not None:
        return f"{var}.node.id"
    if var is not None:
        return f"{var}.node.id"
    return repr(str(node_id))


def _edge_ref_expr(
    workflow_nodes: dict[str, Any] | None,
    var_names: dict[str, str],
    output_var_names: dict[str, dict[int, str]],
    from_node_str: str,
    from_slot: int,
    *,
    bare_single_output_refs: bool,
    diagnostics: "list[Any] | None",
    target_node: Any,
    target_input: str,
) -> str:
    if from_node_str in var_names:
        unpacked_ref = output_var_names.get(from_node_str, {}).get(from_slot)
        if unpacked_ref is not None:
            return unpacked_ref
        if bare_single_output_refs and _is_single_output_ref(workflow_nodes, from_node_str, from_slot):
            return var_names[from_node_str]
        safe_name = _safe_output_name(workflow_nodes, from_node_str, from_slot)
        if safe_name is not None:
            return f"{var_names[from_node_str]}.out({safe_name!r})"
        if diagnostics is not None and workflow_nodes is not None:
            _output_fallback_diagnostic(
                diagnostics, workflow_nodes, from_node_str, from_slot,
                target_node=target_node, target_input=target_input,
            )
        return f"{var_names[from_node_str]}.out({from_slot})"
    return f"[{from_node_str!r}, {from_slot}]"


def _wrapper_kwarg_name(name: str) -> str:
    # Lazy import to avoid circular dependency
    from vibecomfy.porting.emitter import RESERVED_WRAPPER_INPUT_NAMES  # noqa: PLC0415

    return f"{name}_" if name in RESERVED_WRAPPER_INPUT_NAMES or keyword.iskeyword(name) else name


# ---------------------------------------------------------------------------
# Power Lora Loader widget helpers
# ---------------------------------------------------------------------------

def _translate_power_lora_loader_widget(key: str, value: Any) -> str | None:
    """Map rgthree Power Lora dynamic widget slots to stable kwargs.

    rgthree stores decorative header/separator widgets beside an open-ended
    list of LoRA option dictionaries. The committed object_info snapshot only
    exposes model/clip sockets, so normal widget aliasing cannot name these
    UI-saved values.
    """
    if key.startswith("unused_widget_"):
        return None
    if not key.startswith("widget_"):
        return key
    index = _power_lora_widget_index(key)
    if index is None:
        return key
    if not _is_power_lora_config(value):
        return None
    return f"lora_{max(1, index - 3)}"


def _power_lora_widget_index(key: str) -> int | None:
    if key.startswith("widget_"):
        suffix = key.removeprefix("widget_")
    elif key.startswith("unused_widget_"):
        suffix = key.removeprefix("unused_widget_")
    else:
        return None
    try:
        return int(suffix)
    except ValueError:
        return None


def _is_power_lora_config(value: Any) -> bool:
    return isinstance(value, dict) and {"on", "lora", "strength"}.issubset(value)


# ---------------------------------------------------------------------------
# Emission diagnostics collector
# ---------------------------------------------------------------------------

def _collect_emission_diagnostics(
    node: Any,
    output_names: list[str],
    incoming: dict[str, tuple[str, int]],
    var_names: dict[str, str],
) -> "list[Any]":
    """Collect readability diagnostics for a single node during emission.

    This is called from `_node_kwargs` when a diagnostics collector is
    provided.  Currently flags:

    * **avoidable_positional_output** - the node has output names available
      (from schema metadata) but the emitter is using numeric `.out(n)`
      because one or more names are unsafe (blank, duplicate, conflicted).

    * **output_name_ambiguity** - output name is duplicated within the
      same node, forcing a numeric fallback.

    * **schema_backed_widget_alias_not_resolved** - one or more
      `widget_N` keys remain positional because no alias mapping could
      be resolved from schema / widget table evidence.
    """
    # Lazy import to avoid circular dependency
    from vibecomfy.porting.emitter import (  # noqa: PLC0415
        EmissionDiagnostic,
        READABILITY_WARNING_AVOIDABLE_POSITIONAL_OUTPUT,
        READABILITY_WARNING_OUTPUT_NAME_AMBIGUITY,
        READABILITY_WARNING_SCHEMA_BACKED_WIDGET_ALIAS_NOT_RESOLVED,
    )

    diags: list[Any] = []
    nid = getattr(node, "id", None)
    ctype = getattr(node, "class_type", None)
    metadata = getattr(node, "metadata", {}) or {}
    node_input_aliases = metadata.get("input_aliases")

    # 1. avoidable_positional_output / output_name_ambiguity
    if output_names:
        safe_names: set[str] = set()
        has_unsafe = False
        has_duplicate = False
        seen: set[str] = set()
        for name in output_names:
            if not name:
                has_unsafe = True
            elif name in seen:
                has_unsafe = True
                has_duplicate = True
            else:
                seen.add(name)
                safe_names.add(name)
        if has_unsafe:
            if has_duplicate:
                diags.append(
                    EmissionDiagnostic(
                        code=READABILITY_WARNING_OUTPUT_NAME_AMBIGUITY,
                        message=f"Node {nid} ({ctype}) has duplicate output names; falling back to numeric .out(n).",
                        severity="warning",
                        node_id=str(nid) if nid is not None else None,
                        class_type=ctype,
                        detail={"output_names": output_names},
                    )
                )
            else:
                diags.append(
                    EmissionDiagnostic(
                        code=READABILITY_WARNING_AVOIDABLE_POSITIONAL_OUTPUT,
                        message=f"Node {nid} ({ctype}) has partial/blank output names; some outputs use numeric .out(n).",
                        severity="warning",
                        node_id=str(nid) if nid is not None else None,
                        class_type=ctype,
                        detail={"output_names": output_names},
                    )
                )
    else:
        # No output names at all - check if schema has input_aliases available
        if not node_input_aliases:
            # Check if there are widget_N keys that could be aliased
            widget_keys = [
                k for k in getattr(node, "widgets", {}).keys()
                if k.startswith("widget_")
            ] + [
                k for k in getattr(node, "inputs", {}).keys()
                if k.startswith("widget_")
            ]
            if widget_keys:
                schema_source = metadata.get("schema_source")
                schema_available = schema_source is not None
                if schema_available:
                    diags.append(
                        EmissionDiagnostic(
                            code=READABILITY_WARNING_SCHEMA_BACKED_WIDGET_ALIAS_NOT_RESOLVED,
                            message=f"Node {nid} ({ctype}) has {len(set(widget_keys))} unresolved widget_N keys despite schema being available.",
                            severity="warning",
                            node_id=str(nid) if nid is not None else None,
                            class_type=ctype,
                            detail={
                                "widget_keys": list(set(widget_keys)),
                                "schema_source": schema_source,
                            },
                        )
                    )

    # 3. schema_backed_widget_alias_not_resolved - when widget_N keys remain
    #    positional even though input_aliases could potentially cover them, or
    #    when the fallback to static WIDGET_SCHEMA was used.
    if node_input_aliases:
        # We have input_aliases - check if any widget_N index falls outside
        # the aliases list, forcing a fallback.
        widget_indices: list[int] = []
        for k in list(getattr(node, "widgets", {}).keys()) + list(getattr(node, "inputs", {}).keys()):
            if k.startswith("widget_"):
                try:
                    widget_indices.append(int(k.split("_", 1)[1]))
                except ValueError:
                    pass
        if widget_indices:
            max_idx = max(widget_indices)
            if max_idx >= len(node_input_aliases):
                unresolved = [
                    f"widget_{i}" for i in widget_indices
                    if i >= len(node_input_aliases)
                ]
                diags.append(
                    EmissionDiagnostic(
                        code=READABILITY_WARNING_SCHEMA_BACKED_WIDGET_ALIAS_NOT_RESOLVED,
                        message=(
                            f"Node {nid} ({ctype}) has {len(unresolved)} widget_N key(s) "
                            f"({', '.join(unresolved)}) outside input_aliases range "
                            f"(len={len(node_input_aliases)}); keeping positional."
                        ),
                        severity="warning",
                        node_id=str(nid) if nid is not None else None,
                        class_type=ctype,
                        detail={
                            "unresolved_widgets": unresolved,
                            "input_aliases_length": len(node_input_aliases),
                        },
                    )
                )

    return diags


# ---------------------------------------------------------------------------
# Core node-kwargs builder
# ---------------------------------------------------------------------------

def _node_kwargs(
    node: Any,
    edges_in: dict[str, list[Any]],
    var_names: dict[str, str],
    *,
    workflow_nodes: dict[str, Any] | None = None,
    output_var_names: dict[str, dict[int, str]] | None = None,
    diagnostics: "list[Any] | None" = None,
    constant_map: dict[tuple[str, str], str] | None = None,
    use_ui_widget_aliases: bool = False,
    strip_schema_defaults: bool = False,
    omit_single_output_metadata: bool = False,
    bare_single_output_refs: bool = False,
    emit_reserved_keyword_args: bool = False,
    preserve_fields: set[str] | None = None,
    external_refs: dict[tuple[str, str], str] | None = None,
) -> list[tuple[str, str]]:
    # Lazy imports to avoid circular dependency
    from vibecomfy.porting.emitter import (  # noqa: PLC0415
        RESERVED_WRAPPER_INPUT_NAMES,
        _ui_widget_aliases,
        READABILITY_WARNING_SCHEMA_UNKNOWN_KWARG_HIDDEN_BY_EXTRAS,
        EmissionDiagnostic,
    )

    cls = node.class_type
    schema = [name for name in WIDGET_SCHEMA.get(cls, []) if name is not None]
    schema_set = set(schema)

    # Per-node widget alias metadata populated by the schema provider during
    # convert_to_vibe_format.  Prefer this over the static WIDGET_SCHEMA so
    # that schema-source evidence wins - the static table is only a fallback.
    node_metadata: dict[str, Any] = getattr(node, "metadata", None) or {}
    input_aliases: list[str | None] | None = node_metadata.get("input_aliases") or (
        _ui_widget_aliases(node) if use_ui_widget_aliases else None
    )

    if constant_map is None:
        constant_map = {}
    if preserve_fields is None:
        preserve_fields = set()
    if external_refs is None:
        external_refs = {}

    incoming: dict[str, tuple[str, int]] = {}
    incoming_exprs: dict[str, str] = {}
    for edge in edges_in.get(node.id, []):
        incoming[edge.to_input] = (edge.from_node, int(edge.from_output))

    def _translate_widget(key: str, value: Any = None) -> str | None:
        if key.startswith("unused_widget_"):
            return None
        if cls == "Power Lora Loader (rgthree)":
            return _translate_power_lora_loader_widget(key, value)
        if not key.startswith("widget_"):
            return key
        return resolve_widget_key_with_provenance(cls, key, input_aliases=input_aliases).name

    raw_inputs: dict[str, Any] = {}
    for key, value in node.inputs.items():
        if _is_any_link(value) and str(value[0]) == "-10":
            translated_link = _translate_widget(key, value)
            if translated_link is not None:
                expr = external_refs.get((str(getattr(node, "id", "")), translated_link))
                if expr is not None:
                    incoming_exprs[translated_link] = expr
        elif _is_link(value):
            translated_link = _translate_widget(key, value)
            if translated_link is not None:
                incoming.setdefault(translated_link, (str(value[0]), int(value[1])))
        else:
            raw_inputs[key] = value
    for key, value in node.widgets.items():
        if _is_any_link(value) and str(value[0]) == "-10":
            translated_link = _translate_widget(key, value)
            if translated_link is not None:
                expr = external_refs.get((str(getattr(node, "id", "")), translated_link))
                if expr is not None:
                    incoming_exprs[translated_link] = expr
        elif _is_link(value):
            translated_link = _translate_widget(key, value)
            if translated_link is not None:
                incoming.setdefault(translated_link, (str(value[0]), int(value[1])))
        elif key not in raw_inputs:
            raw_inputs[key] = value

    static_inputs: dict[str, Any] = {}
    for key, value in raw_inputs.items():
        translated = _translate_widget(key, value)
        if translated is None:
            continue
        value = _resolve_graph_field_get_string(value, workflow_nodes)
        if translated != key and translated not in raw_inputs and translated not in static_inputs:
            if translated not in incoming and translated not in incoming_exprs:
                static_inputs[translated] = value
            # else: translated name already connected via an edge — drop the shadow widget value
        else:
            static_inputs[key] = value

    if schema:
        ordered_static_keys = [key for key in schema if key in static_inputs]
        ordered_static_keys += sorted(key for key in static_inputs if key not in schema_set)
    else:
        ordered_static_keys = sorted(static_inputs.keys())

    def _is_python_ident(name: str) -> bool:
        return name.isidentifier() and not keyword.iskeyword(name)

    def _format_static_value(key: str, value: Any) -> str:
        """Format a static value, substituting constant name if hoisted."""
        nid = getattr(node, "id", None)
        if nid is not None:
            const_name = constant_map.get((str(nid), key))
            if const_name is not None:
                return const_name
        return _format_value(value)

    out: list[tuple[str, str]] = []
    extras: list[tuple[str, str]] = []
    output_names = _declared_output_names_for_call_metadata(node)
    if output_names and not (omit_single_output_metadata and _is_schema_confirmed_single_output(cls, output_names)):
        out.append(("_outputs", _format_value(tuple(output_names))))
    for key in ordered_static_keys:
        if key in incoming or key in incoming_exprs:
            continue
        if key not in preserve_fields and strip_schema_defaults and _is_schema_default(cls, key, static_inputs[key], node_metadata, node=node):
            continue
        if not _is_python_ident(key) and not (emit_reserved_keyword_args and key in RESERVED_WRAPPER_INPUT_NAMES):
            extras.append((key, _format_static_value(key, static_inputs[key])))
            continue
        if diagnostics is not None and schema and key not in schema_set and emit_reserved_keyword_args:
            diagnostics.append(
                EmissionDiagnostic(
                    code=READABILITY_WARNING_SCHEMA_UNKNOWN_KWARG_HIDDEN_BY_EXTRAS,
                    message=(
                        f"Node {getattr(node, 'id', None)} ({cls}) emits schema-unknown kwarg {key!r}; "
                        "typed wrappers accept it through **_extras, so verify the field is intentional."
                    ),
                    severity="warning",
                    node_id=str(getattr(node, "id", "")),
                    class_type=cls,
                    detail={"input": key, "schema_inputs": sorted(schema_set)},
                )
            )
        out.append((key, _format_static_value(key, static_inputs[key])))

    all_incoming_keys = set(incoming) | set(incoming_exprs)
    if schema:
        ordered_incoming = [key for key in schema if key in all_incoming_keys]
        ordered_incoming += sorted(key for key in all_incoming_keys if key not in schema_set)
    else:
        ordered_incoming = sorted(all_incoming_keys)

    for to_input in ordered_incoming:
        if to_input in incoming_exprs:
            expr = incoming_exprs[to_input]
        else:
            from_node, from_slot = incoming[to_input]
            from_node_str = str(from_node)
            expr = _edge_ref_expr(
                workflow_nodes,
                var_names,
                output_var_names or {},
                from_node_str,
                from_slot,
                bare_single_output_refs=bare_single_output_refs,
                diagnostics=diagnostics,
                target_node=node,
                target_input=to_input,
            )
        if not _is_python_ident(to_input) and not (emit_reserved_keyword_args and to_input in RESERVED_WRAPPER_INPUT_NAMES):
            extras.append((to_input, expr))
            continue
        if diagnostics is not None and schema and to_input not in schema_set and emit_reserved_keyword_args:
            diagnostics.append(
                EmissionDiagnostic(
                    code=READABILITY_WARNING_SCHEMA_UNKNOWN_KWARG_HIDDEN_BY_EXTRAS,
                    message=(
                        f"Node {getattr(node, 'id', None)} ({cls}) emits schema-unknown linked kwarg {to_input!r}; "
                        "typed wrappers accept it through **_extras, so verify the field is intentional."
                    ),
                    severity="warning",
                    node_id=str(getattr(node, "id", "")),
                    class_type=cls,
                    detail={"input": to_input, "schema_inputs": sorted(schema_set), "linked": True},
                )
            )
        out.append((to_input, expr))

    # -- readability diagnostics: positional output detection ------------
    if diagnostics is not None:
        emit_diags = _collect_emission_diagnostics(node, output_names, incoming, var_names)
        diagnostics.extend(emit_diags)

    if extras:
        extras_repr = "{" + ", ".join(f"{key!r}: {value}" for key, value in extras) + "}"
        out.append(("_extras", extras_repr))
    return out


# ---------------------------------------------------------------------------
# Helper used by _node_kwargs: _resolve_graph_field_get_string
# (lazy import from emitter to avoid circular dependency at step 4)
# ---------------------------------------------------------------------------

def _resolve_graph_field_get_string(value: Any, workflow_nodes: Any) -> Any:
    """Thin shim that delegates to emitter._resolve_graph_field_get_string."""
    from vibecomfy.porting.emitter import _resolve_graph_field_get_string as _impl  # noqa: PLC0415
    return _impl(value, workflow_nodes)
