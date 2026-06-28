"""Identifier and output-variable helpers for generated Python emission."""

from __future__ import annotations

import keyword
import re
from collections.abc import Callable, Mapping
from typing import Any

from vibecomfy.porting.emit.diagnostics import (
    EmissionDiagnostic,
    READABILITY_WARNING_AVOIDABLE_POSITIONAL_OUTPUT,
    READABILITY_WARNING_LOCKED_VARIABLE_ALIAS_COLLISION,
    READABILITY_WARNING_LOCKED_VARIABLE_ALIAS_INVALID,
    READABILITY_WARNING_LOCKED_VARIABLE_ALIAS_MISSING,
    READABILITY_WARNING_LOCKED_VARIABLE_UID_COLLISION,
)
from vibecomfy.porting.emit.wrappers import _wrapper_module_for_class
from vibecomfy.porting.object_info import (
    class_has_list_output,
    class_is_known,
    class_output_count,
    require_class_output_count,
)
from vibecomfy.porting.object_info import output_names as class_output_names

_UUID_RE = re.compile(
    r"^[0-9a-f]{8}-[0-9a-f]{4}-[0-9a-f]{4}-[0-9a-f]{4}-[0-9a-f]{12}$",
    re.IGNORECASE,
)


def _safe_var(class_type: str) -> str:
    # UUID class types (ComfyUI subgraphs) get a short, readable variable name.
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


def _topological_node_order(
    nodes: dict[str, Any],
    edges_in: dict[str, list[Any]],
    *,
    is_link: Callable[[Any], bool] | None = None,
) -> list[str]:
    if is_link is None:
        is_link = _is_link
    deps: dict[str, set[str]] = {nid: set() for nid in nodes}
    for nid, node in nodes.items():
        for edge in edges_in.get(nid, []):
            if edge.from_node in nodes:
                deps[nid].add(edge.from_node)
        for value in list(node.inputs.values()) + list(node.widgets.values()):
            if is_link(value):
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
    diagnostics: list[EmissionDiagnostic] | None = None,
) -> dict[str, str]:
    from vibecomfy.identity.uid import make_uid

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


def _apply_locked_variable_names(
    workflow_nodes: Mapping[str, Any],
    var_names: dict[str, str],
    *,
    variable_name_locks: Mapping[str, str] | None,
    strict: bool,
    diagnostics: list[EmissionDiagnostic] | None,
    scope_path: str = "",
) -> None:
    if not variable_name_locks:
        return

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


def _is_valid_locked_variable_alias(alias: str) -> bool:
    return alias.isidentifier() and not keyword.iskeyword(alias)


def _compute_output_variable_names(
    workflow_nodes: dict[str, Any],
    var_names: dict[str, str],
    edges: list[Any],
) -> dict[str, dict[int, str]]:
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


def _schema_output_names_for_unpack(node: Any) -> list[str]:
    metadata_names = _node_output_names(node)
    if metadata_names:
        return metadata_names
    class_type = str(node.class_type)
    if not class_is_known(class_type):
        require_class_output_count(class_type)
    return [str(name) for name in class_output_names(class_type) if str(name)]


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


def _class_collision_suffix(class_type: str) -> str:
    parts = re.findall(r"[A-Z]+(?=[A-Z][a-z]|$)|[A-Z]?[a-z]+|\d+", class_type)
    return _safe_var(parts[0] if parts else class_type)


def _live_output_slots_for_function(
    workflow_nodes: dict[str, Any],
    edges_in: dict[str, list[Any]],
    output_var_names: dict[str, dict[int, str]],
    *,
    is_link: Callable[[Any], bool] | None = None,
    return_refs: tuple[tuple[str, int], ...] = (),
    tail_lines: list[str] | None = None,
) -> dict[str, set[int]]:
    if is_link is None:
        is_link = _is_link
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
            if is_link(value):
                mark(str(value[0]), int(value[1]))
    for node_id, slot in return_refs:
        mark(str(node_id), int(slot))

    tail_text = "\n".join(tail_lines or ())
    if "output_node=" in tail_text:
        for node_id, slot_vars in output_var_names.items():
            first_var = _first_output_var(slot_vars)
            if first_var is not None and re.search(rf"\boutput_node\s*=\s*{re.escape(first_var)}\b", tail_text):
                live[node_id].add(min(slot_vars))
    return live


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


def _edge_ref_expr(
    workflow_nodes: dict[str, Any] | None,
    var_names: dict[str, str],
    output_var_names: dict[str, dict[int, str]],
    from_node_str: str,
    from_slot: int,
    *,
    bare_single_output_refs: bool,
    diagnostics: list[EmissionDiagnostic] | None,
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


def _is_link(value: Any) -> bool:
    if not (isinstance(value, list) and len(value) == 2):
        return False
    nid, slot = value
    if not isinstance(slot, int):
        return False
    return all(part.isdigit() for part in str(nid).split(":"))


def _node_output_names(node: Any) -> list[str]:
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


def _safe_output_name(
    workflow_nodes: dict[str, Any] | None,
    from_node: str,
    from_slot: int,
) -> str | None:
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
    if list(output_names).count(name) > 1:
        return None
    conflicted = getattr(src_node, "metadata", {}).get("conflicted_outputs")
    if isinstance(conflicted, (list, tuple, set, frozenset)) and name in conflicted:
        return None
    return name


def _output_fallback_diagnostic(
    diagnostics: list[EmissionDiagnostic],
    workflow_nodes: dict[str, Any],
    from_node: str,
    from_slot: int,
    *,
    target_node: Any,
    target_input: str,
) -> None:
    src_node = workflow_nodes.get(from_node)
    if src_node is None:
        return

    output_names = getattr(src_node, "metadata", {}).get("output_names")
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


__all__ = [
    "_SHADOWING_OUTPUT_ALIASES",
    "_SHADOWING_OUTPUT_NAMES",
    "_UUID_RE",
    "_apply_locked_variable_names",
    "_assignment_target",
    "_class_collision_suffix",
    "_compute_output_variable_names",
    "_compute_variable_names",
    "_connection_role_name",
    "_edge_ref_expr",
    "_empty_text_role",
    "_first_output_var",
    "_has_out_of_range_edge",
    "_id_sort_key",
    "_is_schema_confirmed_single_output",
    "_is_link",
    "_is_single_output_ref",
    "_is_valid_locked_variable_alias",
    "_live_output_slots_for_function",
    "_locked_variable_uid_map",
    "_node_output_names",
    "_output_fallback_diagnostic",
    "_safe_output_name",
    "_safe_output_var_name",
    "_safe_var",
    "_schema_output_names_for_unpack",
    "_shadowing_output_prefix",
    "_topological_node_order",
]
