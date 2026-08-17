"""Delta derivation from broken->golden graph pairs.

Produces canonical edit ops (SetNodeFieldOp, AddNodeOp, RemoveNodeOp,
UpsertLinkOp, RemoveLinkOp) by comparing UI graphs node-by-node and
field-by-field.
"""
from __future__ import annotations

from vibecomfy.ingest.door_access import door_get_links, door_get_nodes, door_get_widgets_values, door_links, door_nodes
import json
import copy
from dataclasses import dataclass, field
from pathlib import Path
from typing import Any

from vibecomfy.porting.edit.ops import (
    AddNodeOp,
    EditOp,
    LinkSourceRef,
    LinkTargetRef,
    NodeFieldTarget,
    NodeTarget,
    RemoveLinkOp,
    RemoveNodeOp,
    SetNodeFieldOp,
    UpsertLinkOp,
)


@dataclass(frozen=True)
class FaultInjection:
    """A fault injection with its repair delta and predicates.

    Attributes
    ----------
    broken:
        The fault-injected (broken) UI graph.
    golden:
        The correct (golden) UI graph.
    repair_delta:
        Canonical edit ops that transform broken->golden.
    fault_delta:
        Inverse edit ops (golden->broken) for proving fault injection.
    fault_predicate:
        Predicate that matches the broken graph at fault locus.
    repaired_predicate:
        Predicate that matches the golden graph at fault locus.
    description:
        Human-readable fault description.
    """
    broken: dict[str, Any]
    golden: dict[str, Any]
    repair_delta: tuple[EditOp, ...]
    fault_delta: tuple[EditOp, ...]
    fault_predicate: dict[str, Any]
    repaired_predicate: dict[str, Any]
    description: str
    user_effect: str = ""


def _build_node_index(graph: dict[str, Any]) -> dict[str, dict[str, Any]]:
    """Build a node index by id from a UI graph.

    Node ids are normalized to ``str`` so they match the str-ified keys used by
    ``_build_link_index`` (ComfyUI node ids are often ints in UI JSON).
    """
    nodes = door_get_nodes(graph, [])
    return {str(node.get("id", "")): node for node in nodes if isinstance(node, dict)}


def _build_link_index(graph: dict[str, Any]) -> dict[tuple[str, str, str, str, str], dict[str, Any]]:
    """Build a link index by (from_node, from_slot, to_node, to_slot, type) from UI graph.

    UI links are arrays: [link_id, from_slot, from_node, to_slot, to_node, type]
    """
    links = door_get_links(graph, [])
    index = {}
    for link in links:
        if not isinstance(link, list) or len(link) < 6:
            continue
        # ComfyUI UI link format: [link_id, from_node, from_slot, to_node, to_slot, type]
        link_id, from_node, from_slot, to_node, to_slot, link_type = link[:6]
        key = (str(from_node), str(from_slot), str(to_node), str(to_slot), str(link_type))
        index[key] = {"id": link_id, "from_node": from_node, "from_slot": from_slot,
                      "to_node": to_node, "to_slot": to_slot, "type": link_type}
    return index


def _normalize_widget_value(value: Any) -> Any:
    """Normalize widget values for comparison."""
    if isinstance(value, (int, float, str, bool, type(None))):
        return value
    if isinstance(value, list):
        return [_normalize_widget_value(v) for v in value]
    if isinstance(value, dict):
        # For dict values, compare sorted items
        return {k: _normalize_widget_value(v) for k, v in sorted(value.items())}
    return str(value)


def _compare_widgets(
    broken_widgets: dict[str, Any],
    golden_widgets: dict[str, Any],
    node_id: str,
    scope_path: str = "/",
) -> list[SetNodeFieldOp]:
    """Compare widgets between broken and golden nodes, produce SetNodeFieldOp for diffs."""
    ops = []

    # Get all widget keys from both
    all_keys = set(broken_widgets.keys()) | set(golden_widgets.keys())

    for key in sorted(all_keys):
        broken_val = broken_widgets.get(key)
        golden_val = golden_widgets.get(key)

        # Skip internal keys
        if key in {"color", "posed", "name", "id"}:
            continue

        # Normalize and compare
        broken_norm = _normalize_widget_value(broken_val)
        golden_norm = _normalize_widget_value(golden_val)

        if broken_norm != golden_norm:
            # Field differs - create SetNodeFieldOp
            target = NodeFieldTarget(
                scope_path=scope_path,
                uid=str(node_id),
                field_path=str(key),
            )
            ops.append(SetNodeFieldOp(op="set_node_field", target=target, value=golden_val))

    return ops


def _compare_links(
    broken_links: dict[tuple[str, str, str, str, str], dict[str, Any]],
    golden_links: dict[tuple[str, str, str, str, str], dict[str, Any]],
    scope_path: str = "/",
) -> tuple[list[UpsertLinkOp], list[RemoveLinkOp]]:
    """Compare links between broken and golden, produce UpsertLinkOp/RemoveLinkOp."""
    upsert_ops: list[UpsertLinkOp] = []
    remove_ops: list[RemoveLinkOp] = []

    # Links only in golden (need to add)
    for key, link_data in golden_links.items():
        if key not in broken_links:
            from_node, from_slot, to_node, to_slot, _ = key
            source = LinkSourceRef(
                scope_path=scope_path,
                uid=str(from_node),
                output_slot=str(from_slot),
            )
            target = LinkTargetRef(
                scope_path=scope_path,
                uid=str(to_node),
                input_field=str(to_slot),
            )
            upsert_ops.append(UpsertLinkOp(op="upsert_link", source=source, target=target))

    # Links only in broken (need to remove)
    for key, link_data in broken_links.items():
        if key not in golden_links:
            to_node = key[2]
            to_slot = key[3]
            target = LinkTargetRef(
                scope_path=scope_path,
                uid=str(to_node),
                input_field=str(to_slot),
            )
            remove_ops.append(RemoveLinkOp(op="remove_link", target=target))

    return upsert_ops, remove_ops


def _find_link_source(
    graph: dict[str, Any],
    to_node: Any,
    to_slot: Any,
) -> tuple[str | None, str | None]:
    """Return (from_node, from_slot) of the link feeding ``to_node:to_slot``."""
    to_node_s, to_slot_s = str(to_node), str(to_slot)
    for link in door_get_links(graph, []):
        if not isinstance(link, list) or len(link) < 6:
            continue
        # ComfyUI UI link: [link_id, from_node, from_slot, to_node, to_slot, type]
        if str(link[3]) == to_node_s and str(link[4]) == to_slot_s:
            return str(link[1]), str(link[2])
    return None, None


def _additive_link_locus(
    locus_type: str,
    *,
    from_node: Any,
    from_slot: Any,
    to_node: Any,
    to_slot: Any,
    added_node_types: dict[str, str],
) -> dict[str, Any]:
    """Build a link locus item that is tolerant of re-added node ids.

    For additive (remove_feature -> re-add) repairs the fixer synthesizes a
    fresh node, so a link endpoint that the golden pinned to the added node's
    id must instead be matched by node TYPE.  When an endpoint id is in
    ``added_node_types``, emit ``from_node_type``/``to_node_type`` (carrying
    the surviving-anchor id on the other endpoint) so the evaluator can accept
    any sound re-add at a new id.  Surviving endpoints keep their absolute id
    so normal repair predicates are unaffected.
    """
    item: dict[str, Any] = {
        "type": locus_type,
        "from_slot": from_slot,
        "to_slot": to_slot,
    }
    from_id = str(from_node)
    to_id = str(to_node)
    if from_id in added_node_types:
        item["from_node_type"] = added_node_types[from_id]
        item["from_node"] = from_id
    else:
        item["from_node"] = from_id
    if to_id in added_node_types:
        item["to_node_type"] = added_node_types[to_id]
        item["to_node"] = to_id
    else:
        item["to_node"] = to_id
    return item


def _additive_witness_locus(
    added_id: str,
    node_type: str,
    golden: dict[str, Any],
) -> dict[str, Any]:
    """Build the shared additive contract locus item for one added node.

    The same schema is used for both ``additive_witness`` (repaired) and
    ``additive_absence`` (fault): the repaired side asserts a witness exists,
    the fault side asserts no witness exists.  ``edges`` carry the SURVIVING
    peer endpoint pinned by id (stable across the fault); ``widgets_values`` is
    the golden node's positional widget list.

    Known limitation: witness edges assume the peer endpoint survived the fault
    with a stable id.  If two added nodes link to each other (both fresh ids),
    the peer won't resolve in the candidate and the witness won't match.
    Acceptable for the additive demos in scope (single-feature restore).
    """
    golden_nodes = _build_node_index(golden)
    golden_node = golden_nodes.get(str(added_id), {})
    widgets_values = door_get_widgets_values(golden_node)
    if not isinstance(widgets_values, list):
        widgets_values = []

    edges: list[dict[str, Any]] = []
    added_id_s = str(added_id)
    for link in door_get_links(golden, []):
        if not isinstance(link, list) or len(link) < 6:
            continue
        # ComfyUI UI link: [link_id, from_node, from_slot, to_node, to_slot, type]
        _, from_node, from_slot, to_node, to_slot, _ = link[:6]
        if str(from_node) == added_id_s:
            edges.append({
                "direction": "out",
                "peer": str(to_node),
                "self_slot": str(from_slot),
                "peer_slot": str(to_slot),
            })
        elif str(to_node) == added_id_s:
            edges.append({
                "direction": "in",
                "peer": str(from_node),
                "self_slot": str(to_slot),
                "peer_slot": str(from_slot),
            })

    return {
        "type": "additive_witness",  # overwritten by callers as needed
        "node_type": node_type,
        "edges": edges,
        "widgets_values": widgets_values,
    }


def _build_predicates_from_delta(
    repair_delta: tuple[EditOp, ...],
    broken: dict[str, Any],
    golden: dict[str, Any],
) -> tuple[dict[str, Any], dict[str, Any]]:
    """Build fault and repaired predicates from repair delta.

    The predicate captures the locus of the fault - the minimal set of
    (node, field) or link signatures that differ.

    Additive restores (add_node ops) use a WITNESS-BOUND contract: the agent
    must re-add ONE node of the right type whose incident edges AND widget
    values all match the golden, bound to a SINGLE fresh candidate node.  This
    replaces the old scattered additive predicates (node_type_present tautology
    + type-tolerant link matching + missing added-node widgets) which both
    missed real errors (wrong sigma schedule) and rejected correct repairs.
    """
    fault_locus: list[dict[str, Any]] = []
    repaired_locus: list[dict[str, Any]] = []

    # Additive (add_node) deltas: collect added-node ids -> type.  These drive
    # the witness contract below AND suppress redundant link-locus emission
    # for links touching an added node (the witness already covers the added
    # node's edges).
    added_node_types: dict[str, str] = {}
    for op in repair_delta:
        if getattr(op, "op", None) == "add_node" and getattr(op, "class_type", None):
            uid = getattr(op, "node_id", None) or getattr(getattr(op, "target", None), "uid", None)
            if isinstance(uid, str) and uid:
                added_node_types[uid] = op.class_type

    # Build one witness contract per added node.  Both locus items share the
    # same edges + widgets_values + node_type; the locus TYPE differs:
    # additive_witness (repaired) asserts a witness EXISTS; additive_absence
    # (fault) asserts NO witness exists.
    for added_id, node_type in added_node_types.items():
        contract = _additive_witness_locus(added_id, node_type, golden)
        witness_locus = dict(contract)
        witness_locus["type"] = "additive_witness"
        absence_locus = dict(contract)
        absence_locus["type"] = "additive_absence"
        repaired_locus.append(witness_locus)
        fault_locus.append(absence_locus)

    for op in repair_delta:
        if op.op == "set_node_field":
            # Field-level fault
            target = op.target  # NodeFieldTarget
            node_id = target.uid
            field_path = target.field_path

            # Get node for context
            broken_nodes = _build_node_index(broken)
            golden_nodes = _build_node_index(golden)

            broken_node = broken_nodes.get(node_id, {})
            golden_node = golden_nodes.get(node_id, {})

            fault_locus.append({
                "type": "node_field",
                "node_id": node_id,
                "node_type": broken_node.get("type", ""),
                "field": field_path,
                "value": broken_node.get("widgets", {}).get(field_path),
            })

            repaired_locus.append({
                "type": "node_field",
                "node_id": node_id,
                "node_type": golden_node.get("type", ""),
                "field": field_path,
                "value": golden_node.get("widgets", {}).get(field_path),
            })

        elif op.op == "upsert_link":
            # Missing link in broken.  If EITHER endpoint is an added node, the
            # witness contract already covers that edge — skip the redundant
            # (and id-pinning) link locus.  Surviving-survivor links still get
            # their normal id-anchored locus.
            source = op.source
            target = op.target
            if str(source.uid) in added_node_types or str(target.uid) in added_node_types:
                continue

            fault_locus.append({
                "type": "link_absent",
                "from_node": source.uid,
                "from_slot": source.output_slot,
                "to_node": target.uid,
                "to_slot": target.input_field,
            })

            repaired_locus.append(_additive_link_locus(
                "link_present",
                from_node=source.uid,
                from_slot=source.output_slot,
                to_node=target.uid,
                to_slot=target.input_field,
                added_node_types=added_node_types,
            ))

        elif op.op == "remove_link":
            # Extra link in broken (e.g. a bypass). Record the SPECIFIC source so
            # the predicate is "this source->target absent", not "any link to
            # target absent" (which would false-fail a sound rewire repair).
            target = op.target
            from_node, from_slot = _find_link_source(broken, target.uid, target.input_field)

            # Skip when an endpoint is an added node (witness covers it).
            if (
                (from_node is not None and str(from_node) in added_node_types)
                or str(target.uid) in added_node_types
            ):
                continue

            fault_locus.append({
                "type": "link_present",
                "from_node": from_node,
                "from_slot": from_slot,
                "to_node": target.uid,
                "to_slot": target.input_field,
            })

            repaired_locus.append(_additive_link_locus(
                "link_absent",
                from_node=from_node,
                from_slot=from_slot,
                to_node=target.uid,
                to_slot=target.input_field,
                added_node_types=added_node_types,
            ))

        elif op.op == "add_node":
            # Handled by the witness contract above (additive_witness /
            # additive_absence).  No per-op locus here.
            continue

        elif op.op == "remove_node":
            # Extra node in broken
            target = op.target
            broken_nodes = _build_node_index(broken)
            broken_node = broken_nodes.get(target.uid, {})

            fault_locus.append({
                "type": "node_present",
                "node_id": target.uid,
                "node_type": broken_node.get("type", ""),
            })

            repaired_locus.append({
                "type": "node_absent",
                "node_id": target.uid,
                "node_type": broken_node.get("type", ""),
            })

    # Widget-value diffs: ComfyUI UI nodes carry ``widgets_values`` as a
    # positional list (not a ``widgets`` dict), so the set_node_field path above
    # misses them. Capture every differing slot as a ``widget_value`` predicate
    # so the oracle can verify parameter/widget repairs the fixer actually made.
    _bn = _build_node_index(broken)
    _gn = _build_node_index(golden)
    for _nid, _bnode in _bn.items():
        _gnode = _gn.get(_nid)
        if not isinstance(_gnode, dict):
            continue
        _bw = door_get_widgets_values(_bnode)
        _gw = door_get_widgets_values(_gnode)
        if not isinstance(_bw, list) or not isinstance(_gw, list):
            continue
        for _i in range(min(len(_bw), len(_gw))):
            if _bw[_i] != _gw[_i]:
                fault_locus.append({
                    "type": "widget_value",
                    "node_id": _nid,
                    "widget_index": _i,
                    "value": _bw[_i],
                })
                repaired_locus.append({
                    "type": "widget_value",
                    "node_id": _nid,
                    "widget_index": _i,
                    "value": _gw[_i],
                })

    return {
        "locus": fault_locus,
        "description": "Graph matches broken state at fault locus",
    }, {
        "locus": repaired_locus,
        "description": "Graph matches golden state at repaired locus",
    }


def derive_repair_delta(
    broken: dict[str, Any],
    golden: dict[str, Any],
    scope_path: str = "/",
) -> FaultInjection:
    """Derive canonical repair delta from broken->golden graph diff.

    Parameters
    ----------
    broken:
        The fault-injected (broken) UI graph.
    golden:
        The correct (golden) UI graph.
    scope_path:
        Path prefix for node targets (default "/").

    Returns
    -------
    FaultInjection
        Structured fault injection with repair delta, inverse delta, and predicates.
    """
    # Build indexes
    broken_nodes = _build_node_index(broken)
    golden_nodes = _build_node_index(golden)
    broken_links = _build_link_index(broken)
    golden_links = _build_link_index(golden)

    # Collect all ops
    ops: list[EditOp] = []

    # Compare nodes
    all_node_ids = set(broken_nodes.keys()) | set(golden_nodes.keys())

    for node_id in sorted(all_node_ids):
        if node_id not in golden_nodes:
            # Node only in broken -> remove
            ops.append(RemoveNodeOp(
                op="remove_node",
                target=NodeTarget(scope_path=scope_path, uid=node_id),
            ))
        elif node_id not in broken_nodes:
            # Node only in golden -> add
            node = golden_nodes[node_id]
            ops.append(AddNodeOp(
                op="add_node",
                scope_path=scope_path,
                class_type=node.get("type", ""),
                fields=node.get("widgets", {}),
                inputs=node.get("inputs", {}),
                uid=node_id,
                node_id=node_id,
            ))
        else:
            # Node in both - compare widgets
            broken_node = broken_nodes[node_id]
            golden_node = golden_nodes[node_id]
            ops.extend(_compare_widgets(
                broken_node.get("widgets", {}),
                golden_node.get("widgets", {}),
                node_id,
                scope_path,
            ))

    # Compare links
    upsert_ops, remove_ops = _compare_links(broken_links, golden_links, scope_path)
    ops.extend(upsert_ops)
    ops.extend(remove_ops)

    repair_delta = tuple(ops)

    # Build predicates
    fault_predicate, repaired_predicate = _build_predicates_from_delta(
        repair_delta, broken, golden
    )

    # Build description
    locus_descriptions = []
    for item in fault_predicate.get("locus", []):
        if item["type"] == "node_field":
            locus_descriptions.append(f"node {item['node_id']} field {item['field']}")
        elif item["type"] == "link_absent":
            locus_descriptions.append(f"missing link {item['from_node']}.{item['from_slot']}->{item['to_node']}.{item['to_slot']}")
        elif item["type"] == "link_present":
            locus_descriptions.append(f"extra link to {item['to_node']}.{item['to_slot']}")
        elif item["type"] == "node_absent":
            locus_descriptions.append(f"missing node {item['node_id']}")
        elif item["type"] == "node_present":
            locus_descriptions.append(f"extra node {item['node_id']}")

    description = f"Fault at: {', '.join(locus_descriptions)}" if locus_descriptions else "No fault detected"

    return FaultInjection(
        broken=broken,
        golden=golden,
        repair_delta=repair_delta,
        fault_delta=(),  # Inverse delta computed on demand for proving
        fault_predicate=fault_predicate,
        repaired_predicate=repaired_predicate,
        description=description,
    )


def inject_final_output_bypass_fault(
    golden: dict[str, Any],
) -> FaultInjection:
    """Inject a 'final-output branch bypass' fault for smoke testing.

    This fault rewires the final Save* node's input from the processing node
    (e.g., ImageScaleBy, VAEDecode) to the source node (LoadImage, LoadAudio),
    bypassing the actual processing. Works for SaveImage, SaveAudioMP3, and
    video save nodes.

    Parameters
    ----------
    golden:
        The golden (correct) UI graph.

    Returns
    -------
    FaultInjection
        Structured fault injection with broken graph and repair delta.
    """
    # Deep copy to create broken version
    broken = copy.deepcopy(golden)
    b_nodes = {n.get("id"): n for n in door_get_nodes(broken, [])}
    b_links = door_get_links(broken, [])

    def _find_node(pred):
        for n in door_nodes(broken):
            if pred((n.get("type") or "")):
                return n
        return None

    # Find any Save* node (SaveImage, SaveAudioMP3, etc.)
    save_node = _find_node(lambda t: "save" in t.lower())
    if save_node is None:
        raise ValueError("No Save* node found in golden graph")
    save_id = save_node.get("id")
    save_type = save_node.get("type", "")

    # Determine the modality from save node type
    if "audio" in save_type.lower() or "sound" in save_type.lower():
        modality = "audio"
        load_type = "load"
        type_filter = lambda t: "load" in t.lower() and ("audio" in t.lower() or "sound" in t.lower())
        output_type = "AUDIO"
    elif "video" in save_type.lower():
        modality = "video"
        load_type = "load"
        type_filter = lambda t: "load" in t.lower() and "video" in t.lower()
        output_type = "VIDEO"
    else:
        modality = "image"
        load_type = "load"
        type_filter = lambda t: "load" in t.lower() and "image" in t.lower()
        output_type = "IMAGE"

    # Save*'s primary input + the link currently feeding it
    save_input = next(
        (i for i in save_node.get("inputs", []) if i.get("type") == output_type),
        None,
    )
    if save_input is None:
        # Fallback to first input
        save_input = next((i for i in save_node.get("inputs", [])), None)
    if save_input is None:
        raise ValueError(f"{save_type} has no input to bypass")
    old_link_id = save_input.get("link")
    old_link = next((l for l in b_links if isinstance(l, list) and l and l[0] == old_link_id), None)
    if old_link is None:
        raise ValueError(f"No link {old_link_id!r} feeding {save_type}")
    # ComfyUI UI link: [link_id, from_node, from_slot, to_node, to_slot, type]
    _lid, proc_id, _proc_slot, _to_node, to_slot, ltype = old_link

    load_node = _find_node(type_filter)
    if load_node is None:
        # Try generic load node fallback
        load_node = _find_node(lambda t: "load" in t.lower())
    if load_node is None:
        raise ValueError(f"No Load* node found for modality {modality}")
    load_id = load_node.get("id")
    load_out = next(
        (o for o in load_node.get("outputs", [])
         if o.get("type") == output_type or ("image" in (o.get("name") or "").lower() if output_type == "IMAGE" else False)),
        None,
    )
    if load_out is None:
        load_out = load_node.get("outputs", [{}])[0]
    load_slot = load_out.get("slot_index", 0) if isinstance(load_out, dict) else 0

    new_id = max((l[0] for l in b_links if isinstance(l, list) and l), default=0) + 1

    # Rewire the links array: drop processing->Save*, add Load*->Save*.
    broken["links"] = [l for l in b_links if not (isinstance(l, list) and l and l[0] == old_link_id)]
    door_links(broken).append([new_id, load_id, load_slot, save_id, to_slot, ltype])

    # Keep node input/output link references consistent (no dangling links, no
    # absent endpoints) so the broken graph stays valid for the fixer + port check.
    save_input["link"] = new_id
    proc_node = b_nodes.get(proc_id)
    if isinstance(proc_node, dict):
        for o in proc_node.get("outputs", []):
            if isinstance(door_get_links(o), list):
                o["links"] = [x for x in door_links(o) if x != old_link_id]
    if isinstance(load_out, dict):
        load_links = door_get_links(load_out) if isinstance(door_get_links(load_out), list) else []
        if new_id not in load_links:
            load_links.append(new_id)
        load_out["links"] = load_links

    # Derive the repair delta from the now-consistent broken graph
    injection = derive_repair_delta(broken, golden)

    return FaultInjection(
        broken=injection.broken,
        golden=injection.golden,
        repair_delta=injection.repair_delta,
        fault_delta=injection.fault_delta,
        fault_predicate={
            "locus": [{
                "type": "link_present",
                "from_node": str(load_id),
                "from_slot": str(load_slot),
                "to_node": str(save_id),
                "to_slot": str(to_slot),
            }],
            "description": f"{save_type} wired directly to Load* (bypassing the processing node)",
        },
        repaired_predicate=injection.repaired_predicate,
        description=f"Final-output bypass: {save_type} takes input from Load* instead of {proc_id}",
        user_effect=(
            "the saved output still matches the raw input instead of the processed result — "
            "it's as if the main processing step is being skipped before the export"
        ),
    )


def inject_conditioning_swap_fault(
    golden: dict[str, Any],
) -> FaultInjection:
    """Inject a 'conditioning swap' fault for text-to-image workflows.

    This fault swaps the positive and negative conditioning inputs to a
    KSampler or SamplerCustomAdvanced node, inverting the generation semantics.

    Parameters
    ----------
    golden:
        The golden (correct) UI graph.

    Returns
    -------
    FaultInjection
        Structured fault injection with broken graph and repair delta.
    """
    broken = copy.deepcopy(golden)
    b_nodes = {n.get("id"): n for n in door_get_nodes(broken, [])}
    b_links = door_get_links(broken, [])

    def _find_node(pred):
        for n in door_nodes(broken):
            if pred((n.get("type") or "")):
                return n
        return None

    # Find KSampler or SamplerCustomAdvanced
    sampler_node = _find_node(lambda t: "ksampler" in t.lower() or "sampler" in t.lower())
    if sampler_node is None:
        raise ValueError("No KSampler/Sampler node found in golden graph")
    sampler_id = sampler_node.get("id")

    # Find positive and negative conditioning inputs
    pos_input = next(
        (i for i in sampler_node.get("inputs", []) if "positive" in (i.get("name") or "").lower()),
        None,
    )
    neg_input = next(
        (i for i in sampler_node.get("inputs", []) if "negative" in (i.get("name") or "").lower()),
        None,
    )

    if pos_input is None or neg_input is None:
        raise ValueError("Sampler missing positive/negative inputs")

    pos_link_id = pos_input.get("link")
    neg_link_id = neg_input.get("link")

    if pos_link_id is None or neg_link_id is None:
        raise ValueError("Conditioning inputs not linked")

    # Find the source nodes for positive/negative
    pos_from_node, pos_from_slot = _find_link_source(broken, sampler_id, pos_input.get("name", ""))
    neg_from_node, neg_from_slot = _find_link_source(broken, sampler_id, neg_input.get("name", ""))

    # Swap: positive takes negative's link, negative takes positive's link
    pos_input["link"] = neg_link_id
    neg_input["link"] = pos_link_id

    # Update source nodes' output link references
    pos_source = b_nodes.get(str(pos_from_node))
    neg_source = b_nodes.get(str(neg_from_node))

    if isinstance(pos_source, dict):
        for o in pos_source.get("outputs", []):
            if isinstance(door_get_links(o), list):
                # Replace old link_id with neg_link_id at target input
                for idx, link_ref in enumerate(door_links(o)):
                    if link_ref == pos_link_id:
                        door_links(o)[idx] = neg_link_id

    if isinstance(neg_source, dict):
        for o in neg_source.get("outputs", []):
            if isinstance(door_get_links(o), list):
                for idx, link_ref in enumerate(door_links(o)):
                    if link_ref == neg_link_id:
                        door_links(o)[idx] = pos_link_id

    # Update links array
    for link in door_links(broken):
        if isinstance(link, list) and len(link) >= 6:
            if link[0] == pos_link_id:
                link[3] = sampler_id
                # Keep to_slot as positive's slot
            elif link[0] == neg_link_id:
                link[3] = sampler_id
                # Keep to_slot as negative's slot

    injection = derive_repair_delta(broken, golden)

    return FaultInjection(
        broken=injection.broken,
        golden=injection.golden,
        repair_delta=injection.repair_delta,
        fault_delta=injection.fault_delta,
        fault_predicate={
            "locus": [{
                "type": "link_present",
                "from_node": str(neg_from_node),
                "from_slot": str(neg_from_slot),
                "to_node": str(sampler_id),
                "to_slot": str(next((i.get("name", "") for i in sampler_node.get("inputs", []) if "positive" in str(i.get("name", "")).lower()), "positive")),
            }],
            "description": "Positive conditioning connected to negative's source",
        },
        repaired_predicate=injection.repaired_predicate,
        description=f"Conditioning swap: positive/negative inputs to sampler {sampler_id} are swapped",
        user_effect=(
            "the generation produces the exact opposite of what's intended — "
            "it's as if the style guidance and content guidance are flipped, "
            "resulting in images that look nothing like the prompt description"
        ),
    )


def inject_vae_output_bypass_fault(
    golden: dict[str, Any],
) -> FaultInjection:
    """Inject a 'VAE decode bypass' fault for workflows with VAE decode.

    This fault rewires the Save* node (SaveImage, SaveAudioMP3, etc.) to take
    input from the node before VAEDecode/VAEEncode (e.g., KSampler's latent
    output), causing it to save latents/encoded data instead of decoded pixels/audio.

    Parameters
    ----------
    golden:
        The golden (correct) UI graph.

    Returns
    -------
    FaultInjection
        Structured fault injection with broken graph and repair delta.
    """
    broken = copy.deepcopy(golden)
    b_nodes = {n.get("id"): n for n in door_get_nodes(broken, [])}
    b_links = door_get_links(broken, [])

    def _find_node(pred):
        for n in door_nodes(broken):
            if pred((n.get("type") or "")):
                return n
        return None

    # Find VAE decode node and any Save* node
    vae_node = _find_node(lambda t: "vae" in t.lower() and ("decode" in t.lower() or "encode" in t.lower()))
    save_node = _find_node(lambda t: "save" in t.lower())

    if vae_node is None or save_node is None:
        raise ValueError("Missing VAEDecode/VAEEncode or Save* node")

    vae_id = vae_node.get("id")
    vae_type = vae_node.get("type", "")
    save_id = save_node.get("id")
    save_type = save_node.get("type", "")

    # Determine the VAE input name based on node type
    if "decode" in vae_type.lower():
        vae_input_name = "samples"
    else:  # encode
        vae_input_name = "pixels"

    # Find what feeds VAE's input
    vae_input = next(
        (i for i in vae_node.get("inputs", []) if vae_input_name in (i.get("name") or "").lower()),
        None,
    )
    if vae_input is None:
        # Try first input as fallback
        vae_input = next((i for i in vae_node.get("inputs", [])), None)
    if vae_input is None:
        raise ValueError(f"{vae_type} has no input")

    upstream_link_id = vae_input.get("link")
    if upstream_link_id is None:
        raise ValueError(f"{vae_type} input not linked")

    # Find the actual link to get upstream node and slot
    upstream_link = next((l for l in b_links if isinstance(l, list) and l and l[0] == upstream_link_id), None)
    if upstream_link is None:
        raise ValueError(f"Cannot find link {upstream_link_id} feeding {vae_type}")
    # ComfyUI UI link: [link_id, from_node, from_slot, to_node, to_slot, type]
    upstream_from_node = upstream_link[1]
    upstream_from_slot = upstream_link[2]

    # Find Save*'s input and its current link
    save_input = next(
        (i for i in save_node.get("inputs", []) if i.get("link")),
        None,
    )
    if save_input is None:
        raise ValueError(f"{save_type} has no linked input")

    old_save_link_id = save_input.get("link")
    if old_save_link_id is None:
        raise ValueError(f"{save_type} input not linked")

    # Find the old link to get the correct to_slot and link_type
    old_save_link = next((l for l in b_links if isinstance(l, list) and l and l[0] == old_save_link_id), None)
    if old_save_link is None:
        raise ValueError(f"Cannot find link {old_save_link_id}")

    # ComfyUI UI link: [link_id, from_node, from_slot, to_node, to_slot, type]
    _lid, _old_from, _old_from_slot, _old_to, to_slot, link_type = old_save_link

    new_id = max((l[0] for l in b_links if isinstance(l, list) and l), default=100) + 1

    # Remove old VAE->Save* link, add upstream->Save* link
    broken["links"] = [l for l in b_links if not (isinstance(l, list) and l and l[0] == old_save_link_id)]
    door_links(broken).append([new_id, upstream_from_node, upstream_from_slot, save_id, to_slot, link_type])

    # Update Save* input reference
    save_input["link"] = new_id

    # Update VAE output to remove the old link
    if isinstance(vae_node, dict):
        for o in vae_node.get("outputs", []):
            if isinstance(door_get_links(o), list):
                o["links"] = [x for x in door_links(o) if x != old_save_link_id]

    # Update upstream node's output to include new link
    upstream_node = b_nodes.get(str(upstream_from_node))
    if isinstance(upstream_node, dict):
        for o in upstream_node.get("outputs", []):
            if isinstance(door_get_links(o), list):
                if new_id not in door_links(o):
                    door_links(o).append(new_id)

    injection = derive_repair_delta(broken, golden)

    return FaultInjection(
        broken=injection.broken,
        golden=injection.golden,
        repair_delta=injection.repair_delta,
        fault_delta=injection.fault_delta,
        fault_predicate={
            "locus": [{
                "type": "link_present",
                "from_node": str(upstream_from_node),
                "from_slot": str(upstream_from_slot),
                "to_node": str(save_id),
                "to_slot": str(to_slot),
            }],
            "description": f"{save_type} wired to pre-VAE node (skipping decode)",
        },
        repaired_predicate=injection.repaired_predicate,
        description=f"VAE bypass: {save_type} takes input from {upstream_from_node} instead of {vae_type}",
        user_effect=(
            "the saved output looks like noise or corrupted data — "
            "it's as if the content was never properly decoded from its internal representation"
        ),
    )


def inject_latent_source_swap_fault(
    golden: dict[str, Any],
) -> FaultInjection:
    """Inject a 'latent source swap' fault for img2img/i2v workflows.

    This fault rewires the sampler's latent_image input to take from the wrong
    source (e.g., EmptyLatentImage instead of VAEEncode output), breaking
    the image-to-image/video pipeline.

    Parameters
    ----------
    golden:
        The golden (correct) UI graph.

    Returns
    -------
    FaultInjection
        Structured fault injection with broken graph and repair delta.
    """
    broken = copy.deepcopy(golden)
    b_nodes = {n.get("id"): n for n in door_get_nodes(broken, [])}
    b_links = door_get_links(broken, [])

    def _find_node(pred):
        for n in door_nodes(broken):
            if pred((n.get("type") or "")):
                return n
        return None

    # Find KSampler
    sampler_node = _find_node(lambda t: "ksampler" in t.lower() or "sampler" in t.lower())
    if sampler_node is None:
        raise ValueError("No KSampler node found in golden graph")
    sampler_id = sampler_node.get("id")

    # Find the latent_image input
    latent_input = next(
        (i for i in sampler_node.get("inputs", []) if "latent" in (i.get("name") or "").lower()),
        None,
    )
    if latent_input is None:
        raise ValueError("Sampler has no latent_image input")

    old_link_id = latent_input.get("link")
    if old_link_id is None:
        raise ValueError("Sampler latent input not linked")

    old_from_node, old_from_slot = _find_link_source(broken, sampler_id, latent_input.get("name", ""))

    # Find an alternative latent source (EmptyLatentImage or similar)
    alt_node = _find_node(lambda t: "empty" in t.lower() and "latent" in t.lower())
    if alt_node is None:
        # Try VAEEncode as alternative
        alt_node = _find_node(lambda t: "vae" in t.lower() and "encode" in t.lower())

    if alt_node is None or alt_node.get("id") == old_from_node:
        raise ValueError("No alternative latent source found")

    alt_id = alt_node.get("id")
    alt_out = next(
        (o for o in alt_node.get("outputs", [])
         if (o.get("type") == "LATENT" or "latent" in (o.get("name") or "").lower())),
        None,
    )
    alt_slot = alt_out.get("slot_index", 0) if isinstance(alt_out, dict) else 0

    new_id = max((l[0] for l in b_links if isinstance(l, list) and l), default=100) + 1

    # Remove old link, add alternative->sampler link
    broken["links"] = [l for l in b_links if not (isinstance(l, list) and l and l[0] == old_link_id)]
    door_links(broken).append([new_id, alt_id, alt_slot, sampler_id, latent_input.get("name", "latent_image"), "LATENT"])

    # Update sampler input
    latent_input["link"] = new_id

    # Update old source output to remove the link
    old_source = b_nodes.get(str(old_from_node))
    if isinstance(old_source, dict):
        for o in old_source.get("outputs", []):
            if isinstance(door_get_links(o), list):
                o["links"] = [x for x in door_links(o) if x != old_link_id]

    # Update alternative source output to include new link
    if isinstance(alt_out, dict):
        alt_links = door_get_links(alt_out) if isinstance(door_get_links(alt_out), list) else []
        if new_id not in alt_links:
            alt_links.append(new_id)
        alt_out["links"] = alt_links

    injection = derive_repair_delta(broken, golden)

    return FaultInjection(
        broken=injection.broken,
        golden=injection.golden,
        repair_delta=injection.repair_delta,
        fault_delta=injection.fault_delta,
        fault_predicate={
            "locus": [{
                "type": "link_present",
                "from_node": str(alt_id),
                "from_slot": str(alt_slot),
                "to_node": str(sampler_id),
                "to_slot": str(latent_input.get("name", "latent_image")),
            }],
            "description": "Sampler wired to wrong latent source",
        },
        repaired_predicate=injection.repaired_predicate,
        description=f"Latent source swap: sampler takes input from {alt_id} instead of {old_from_node}",
        user_effect=(
            "the generation ignores the input image entirely — "
            "it's as if the reference image is disconnected, producing a completely different result"
        ),
    )


def inject_wrong_output_slot_fault(
    golden: dict[str, Any],
) -> FaultInjection:
    """Inject a 'wrong output slot' fault for multi-output nodes.

    This fault connects a downstream node to the wrong output slot of a
    multi-output node (e.g., MASK instead of IMAGE from LoadImage).

    Parameters
    ----------
    golden:
        The golden (correct) UI graph.

    Returns
    -------
    FaultInjection
        Structured fault injection with broken graph and repair delta.
    """
    broken = copy.deepcopy(golden)
    b_nodes = {n.get("id"): n for n in door_get_nodes(broken, [])}
    b_links = door_get_links(broken, [])

    def _find_node(pred):
        for n in door_nodes(broken):
            if pred((n.get("type") or "")):
                return n
        return None

    # Find LoadImage (has IMAGE and MASK outputs)
    load_node = _find_node(lambda t: "load" in t.lower() and "image" in t.lower())
    if load_node is None:
        raise ValueError("No LoadImage node found in golden graph")

    load_id = load_node.get("id")
    outputs = load_node.get("outputs", [])

    # Find IMAGE and MASK output slots
    image_out = next((o for o in outputs if o.get("type") == "IMAGE"), None)
    mask_out = next((o for o in outputs if o.get("type") == "MASK"), None)

    if image_out is None or mask_out is None:
        raise ValueError("LoadImage missing IMAGE or MASK output")

    image_slot = image_out.get("slot_index", 0)
    mask_slot = mask_out.get("slot_index", 1)

    # Find a node consuming IMAGE from LoadImage
    target_link = None
    target_node = None
    target_input = None

    for link in b_links:
        if isinstance(link, list) and len(link) >= 6:
            if link[1] == load_id and link[2] == image_slot:
                target_link = link
                to_node_id = link[3]
                # Use the raw to_node_id as key (b_nodes keys are ints)
                target_node = b_nodes.get(to_node_id)
                # Find the input name
                if target_node:
                    target_input = next(
                        (i for i in target_node.get("inputs", []) if i.get("link") == link[0]),
                        None,
                    )
                break

    if target_link is None or target_node is None:
        raise ValueError("No node consuming LoadImage IMAGE output found")

    target_id = target_node.get("id")
    old_link_id = target_link[0]
    to_slot = target_link[4]
    link_type = target_link[5]

    new_id = max((l[0] for l in b_links if isinstance(l, list) and l), default=100) + 1

    # Remove IMAGE->target link, add MASK->target link
    broken["links"] = [l for l in b_links if not (isinstance(l, list) and l and l[0] == old_link_id)]
    door_links(broken).append([new_id, load_id, mask_slot, target_id, to_slot, "MASK"])

    # Update target input
    if target_input:
        target_input["link"] = new_id

    # Update IMAGE output to remove the link
    if isinstance(image_out, dict):
        if isinstance(door_get_links(image_out), list):
            image_out["links"] = [x for x in door_links(image_out) if x != old_link_id]

    # Update MASK output to include new link
    if isinstance(mask_out, dict):
        mask_links = door_get_links(mask_out) if isinstance(door_get_links(mask_out), list) else []
        if new_id not in mask_links:
            mask_links.append(new_id)
        mask_out["links"] = mask_links

    injection = derive_repair_delta(broken, golden)

    return FaultInjection(
        broken=injection.broken,
        golden=injection.golden,
        repair_delta=injection.repair_delta,
        fault_delta=injection.fault_delta,
        fault_predicate={
            "locus": [{
                "type": "link_present",
                "from_node": str(load_id),
                "from_slot": str(mask_slot),
                "to_node": str(target_id),
                "to_slot": str(to_slot),
            }],
            "description": "Downstream node wired to MASK slot instead of IMAGE",
        },
        repaired_predicate=injection.repaired_predicate,
        description=f"Wrong output slot: {target_id} takes MASK from LoadImage instead of IMAGE",
        user_effect=(
            "the downstream processing receives a mask instead of an image — "
            "it's as if the wrong data type is flowing through the pipeline, "
            "causing type mismatches or unexpected behavior"
        ),
    )


def inject_prompt_not_wired_fault(
    golden: dict[str, Any],
) -> FaultInjection:
    """Inject a 'prompt not wired' fault for workflows with CLIPTextEncode.

    This fault disconnects the CLIPTextEncode positive conditioning output
    from the sampler, breaking the prompt guidance.

    Parameters
    ----------
    golden:
        The golden (correct) UI graph.

    Returns
    -------
    FaultInjection
        Structured fault injection with broken graph and repair delta.
    """
    broken = copy.deepcopy(golden)
    b_nodes = {n.get("id"): n for n in door_get_nodes(broken, [])}
    b_links = door_get_links(broken, [])

    def _find_node(pred):
        for n in door_nodes(broken):
            if pred((n.get("type") or "")):
                return n
        return None

    # Find CLIPTextEncode (positive prompt) and sampler
    clip_node = _find_node(lambda t: "clip" in t.lower() and "text" in t.lower() and "encode" in t.lower())
    sampler_node = _find_node(lambda t: "ksampler" in t.lower() or "sampler" in t.lower())

    if clip_node is None or sampler_node is None:
        raise ValueError("No CLIPTextEncode or sampler node found in golden graph")

    clip_id = clip_node.get("id")
    sampler_id = sampler_node.get("id")

    # Find the positive input on the sampler
    pos_input = next(
        (i for i in sampler_node.get("inputs", []) if "positive" in (i.get("name") or "").lower()),
        None,
    )

    if pos_input is None:
        raise ValueError("Sampler has no positive conditioning input")

    pos_link_id = pos_input.get("link")
    if pos_link_id is None:
        raise ValueError("Positive conditioning not linked")

    # Find the actual link to get from_node/from_slot
    pos_link = next((l for l in b_links if isinstance(l, list) and l and l[0] == pos_link_id), None)
    if pos_link is None:
        raise ValueError(f"Cannot find link {pos_link_id}")

    # ComfyUI UI link: [link_id, from_node, from_slot, to_node, to_slot, type]
    from_node = pos_link[1]
    from_slot = pos_link[2]
    to_slot = pos_link[4]

    # Remove the link
    broken["links"] = [l for l in b_links if not (isinstance(l, list) and l and l[0] == pos_link_id)]

    # Update sampler input to remove link reference
    pos_input["link"] = None

    # Update CLIPTextEncode output to remove the link
    if isinstance(clip_node, dict):
        for o in clip_node.get("outputs", []):
            if isinstance(door_get_links(o), list):
                o["links"] = [x for x in door_links(o) if x != pos_link_id]

    injection = derive_repair_delta(broken, golden)

    return FaultInjection(
        broken=injection.broken,
        golden=injection.golden,
        repair_delta=injection.repair_delta,
        fault_delta=injection.fault_delta,
        fault_predicate={
            "locus": [{
                "type": "link_absent",
                "from_node": str(from_node),
                "from_slot": str(from_slot),
                "to_node": str(sampler_id),
                "to_slot": str(to_slot),
            }],
            "description": "Positive conditioning disconnected from sampler",
        },
        repaired_predicate=injection.repaired_predicate,
        description=f"Prompt not wired: CLIPTextEncode {clip_id} disconnected from sampler {sampler_id}",
        user_effect=(
            "the generation doesn't follow my prompt at all — "
            "it's as if the positive conditioning is missing, producing unrelated or default results"
        ),
    )


def inject_disabled_control_preprocessor_fault(
    golden: dict[str, Any],
) -> FaultInjection:
    """Inject a 'disabled ControlNet preprocessor' fault.

    This fault sets a ControlNet preprocessor or reference node's mode to bypass (4),
    disabling the control signal.

    Parameters
    ----------
    golden:
        The golden (correct) UI graph.

    Returns
    -------
    FaultInjection
        Structured fault injection with broken graph and repair delta.
    """
    broken = copy.deepcopy(golden)
    b_nodes = {n.get("id"): n for n in door_get_nodes(broken, [])}

    def _find_node(pred):
        for n in door_nodes(broken):
            if pred((n.get("type") or "")):
                return n
        return None

    # Find ControlNet preprocessor or reference node
    # Common types: *, Preprocessor, Reference, ApplyControlNet
    control_node = _find_node(lambda t: any(
        k in t.lower() for k in ["preprocessor", "reference", "apply", "control"]
    ) and "net" in t.lower() or any(
        k in t.lower() for k in ["lineart", "canny", "depth", "pose", "openpose"]
    ))

    if control_node is None:
        raise ValueError("No ControlNet preprocessor/reference node found in golden graph")

    node_id = control_node.get("id")
    node_type = control_node.get("type", "")

    # Get current mode and widgets_values
    widgets_values = door_get_widgets_values(control_node, [])
    if not isinstance(widgets_values, list):
        widgets_values = []

    # Find mode field - typically index 2 or 3 in ControlNet preprocessors
    # Common modes: 0=enabled, 1=only faster, 2=only pinhole, 3=only midpoint, 4=bypass, 5=mute
    # We'll set to bypass (4)
    mode_index = None
    for i, v in enumerate(widgets_values):
        if isinstance(v, int) and v in range(6):  # Mode is typically 0-5
            mode_index = i
            break

    if mode_index is None:
        # Default to index 2 or 3 for ControlNet nodes
        mode_index = 2 if len(widgets_values) > 2 else 3

    # Store original value for predicate
    original_mode = widgets_values[mode_index] if mode_index < len(widgets_values) else 0

    # Set mode to bypass (4) or mute (5)
    new_widgets_values = list(widgets_values)
    while len(new_widgets_values) <= mode_index:
        new_widgets_values.append(0)
    new_widgets_values[mode_index] = 4  # bypass mode

    # Update node
    control_node["widgets_values"] = new_widgets_values

    injection = derive_repair_delta(broken, golden)

    return FaultInjection(
        broken=injection.broken,
        golden=injection.golden,
        repair_delta=injection.repair_delta,
        fault_delta=injection.fault_delta,
        fault_predicate={
            "locus": [{
                "type": "widget_value",
                "node_id": str(node_id),
                "node_type": node_type,
                "widget_index": mode_index,
                "value": 4,  # bypass mode
            }],
            "description": f"{node_type} mode set to bypass",
        },
        repaired_predicate=injection.repaired_predicate,
        description=f"Disabled ControlNet preprocessor: {node_type} mode set to bypass",
        user_effect=(
            "the control signal doesn't affect the output — "
            "it's as if the ControlNet guidance is completely ignored"
        ),
    )


def inject_denoise_too_high_fault(
    golden: dict[str, Any],
) -> FaultInjection:
    """Inject a 'denoise too high' fault for img2img workflows.

    This fault sets the denoise parameter to ~1.0, making img2img
    behave like txt2img (losing the input image influence).

    Parameters
    ----------
    golden:
        The golden (correct) UI graph.

    Returns
    -------
    FaultInjection
        Structured fault injection with broken graph and repair delta.
    """
    broken = copy.deepcopy(golden)
    b_nodes = {n.get("id"): n for n in door_get_nodes(broken, [])}

    def _find_node(pred):
        for n in door_nodes(broken):
            if pred((n.get("type") or "")):
                return n
        return None

    # Find KSampler with denoise parameter (or img2img sampler)
    sampler_node = _find_node(lambda t: "ksampler" in t.lower() or "sampler" in t.lower())
    if sampler_node is None:
        raise ValueError("No sampler node found in golden graph")

    node_id = sampler_node.get("id")
    node_type = sampler_node.get("type", "")

    # Get widgets_values
    widgets_values = door_get_widgets_values(sampler_node, [])
    if not isinstance(widgets_values, list):
        raise ValueError(f"{node_type} has no widgets_values")

    # For KSampler: [seed, seed_mode, steps, cfg, scheduler, denoise]
    # denoise is at index 5 if present
    denoise_index = None
    for i in range(len(widgets_values)):
        if isinstance(widgets_values[i], float) and 0.0 <= widgets_values[i] <= 1.0:
            # Could be denoise or cfg - cfg is often int-like, denoise is float
            if i == 5 or (len(widgets_values) >= 6 and i == 5):
                denoise_index = i
                break
            elif denoise_index is None:
                denoise_index = i

    if denoise_index is None:
        # Default to index 5 for KSampler
        denoise_index = 5

    # Store original value
    original_denoise = widgets_values[denoise_index] if denoise_index < len(widgets_values) else 0.5

    # Set denoise to 1.0
    new_widgets_values = list(widgets_values)
    while len(new_widgets_values) <= denoise_index:
        new_widgets_values.append(0.0)
    new_widgets_values[denoise_index] = 1.0

    sampler_node["widgets_values"] = new_widgets_values

    injection = derive_repair_delta(broken, golden)

    return FaultInjection(
        broken=injection.broken,
        golden=injection.golden,
        repair_delta=injection.repair_delta,
        fault_delta=injection.fault_delta,
        fault_predicate={
            "locus": [{
                "type": "widget_value",
                "node_id": str(node_id),
                "node_type": node_type,
                "widget_index": denoise_index,
                "value": 1.0,
            }],
            "description": f"{node_type} denoise set to 1.0",
        },
        repaired_predicate=injection.repaired_predicate,
        description=f"Denoise too high: {node_type} denoise={original_denoise}→1.0",
        user_effect=(
            "the output doesn't resemble my input image at all — "
            "it's as if the img2img strength is maxed out, generating a completely new image"
        ),
    )


def inject_cfg_too_high_fault(
    golden: dict[str, Any],
) -> FaultInjection:
    """Inject a 'CFG too high' fault.

    This fault sets the CFG scale to ~20, causing oversaturation
    and artifacts.

    Parameters
    ----------
    golden:
        The golden (correct) UI graph.

    Returns
    -------
    FaultInjection
        Structured fault injection with broken graph and repair delta.
    """
    broken = copy.deepcopy(golden)
    b_nodes = {n.get("id"): n for n in door_get_nodes(broken, [])}

    def _find_node(pred):
        for n in door_nodes(broken):
            if pred((n.get("type") or "")):
                return n
        return None

    # Find sampler or cfg node
    sampler_node = _find_node(lambda t: "ksampler" in t.lower() or "sampler" in t.lower() or "cfg" in t.lower())
    if sampler_node is None:
        raise ValueError("No sampler/CFG node found in golden graph")

    node_id = sampler_node.get("id")
    node_type = sampler_node.get("type", "")

    # Get widgets_values
    widgets_values = door_get_widgets_values(sampler_node, [])
    if not isinstance(widgets_values, list):
        raise ValueError(f"{node_type} has no widgets_values")

    # For KSampler: [seed, seed_mode, steps, cfg, scheduler, denoise]
    # cfg is at index 3
    cfg_index = 3 if len(widgets_values) > 3 else None

    if cfg_index is None:
        # Try to find a float that could be cfg (typically 4-15 range)
        for i, v in enumerate(widgets_values):
            if isinstance(v, (int, float)) and 4.0 <= v <= 15.0:
                cfg_index = i
                break

    if cfg_index is None:
        raise ValueError(f"{node_type} has no identifiable cfg parameter")

    # Store original value
    original_cfg = widgets_values[cfg_index]

    # Set cfg to 20
    new_widgets_values = list(widgets_values)
    new_widgets_values[cfg_index] = 20

    sampler_node["widgets_values"] = new_widgets_values

    injection = derive_repair_delta(broken, golden)

    return FaultInjection(
        broken=injection.broken,
        golden=injection.golden,
        repair_delta=injection.repair_delta,
        fault_delta=injection.fault_delta,
        fault_predicate={
            "locus": [{
                "type": "widget_value",
                "node_id": str(node_id),
                "node_type": node_type,
                "widget_index": cfg_index,
                "value": 20,
            }],
            "description": f"{node_type} CFG set to 20",
        },
        repaired_predicate=injection.repaired_predicate,
        description=f"CFG too high: {node_type} cfg={original_cfg}→20",
        user_effect=(
            "the output looks oversaturated and has artifacts — "
            "it's as if the CFG scale is way too high, making the generation look harsh and unnatural"
        ),
    )


def inject_steps_too_low_fault(
    golden: dict[str, Any],
) -> FaultInjection:
    """Inject a 'steps too low' fault.

    This fault sets the sampling steps to ~2, causing underfitting
    and poor quality.

    Parameters
    ----------
    golden:
        The golden (correct) UI graph.

    Returns
    -------
    FaultInjection
        Structured fault injection with broken graph and repair delta.
    """
    broken = copy.deepcopy(golden)
    b_nodes = {n.get("id"): n for n in door_get_nodes(broken, [])}

    def _find_node(pred):
        for n in door_nodes(broken):
            if pred((n.get("type") or "")):
                return n
        return None

    # Find sampler node
    sampler_node = _find_node(lambda t: "ksampler" in t.lower() or "sampler" in t.lower())
    if sampler_node is None:
        raise ValueError("No sampler node found in golden graph")

    node_id = sampler_node.get("id")
    node_type = sampler_node.get("type", "")

    # Get widgets_values
    widgets_values = door_get_widgets_values(sampler_node, [])
    if not isinstance(widgets_values, list):
        raise ValueError(f"{node_type} has no widgets_values")

    # For KSampler: [seed, seed_mode, steps, cfg, scheduler, denoise]
    # steps is at index 2
    steps_index = 2 if len(widgets_values) > 2 else None

    if steps_index is None:
        raise ValueError(f"{node_type} has no identifiable steps parameter")

    # Store original value
    original_steps = widgets_values[steps_index]

    # Set steps to 2
    new_widgets_values = list(widgets_values)
    new_widgets_values[steps_index] = 2

    sampler_node["widgets_values"] = new_widgets_values

    injection = derive_repair_delta(broken, golden)

    return FaultInjection(
        broken=injection.broken,
        golden=injection.golden,
        repair_delta=injection.repair_delta,
        fault_delta=injection.fault_delta,
        fault_predicate={
            "locus": [{
                "type": "widget_value",
                "node_id": str(node_id),
                "node_type": node_type,
                "widget_index": steps_index,
                "value": 2,
            }],
            "description": f"{node_type} steps set to 2",
        },
        repaired_predicate=injection.repaired_predicate,
        description=f"Steps too low: {node_type} steps={original_steps}→2",
        user_effect=(
            "the output looks unfinished and low quality — "
            "it's as if the generation didn't run enough steps, resulting in a blurry or underdeveloped image"
        ),
    )


def inject_resolution_wrong_fault(
    golden: dict[str, Any],
) -> FaultInjection:
    """Inject a 'wrong resolution' fault.

    This fault sets EmptyLatentImage dimensions to a mismatched resolution
    (e.g., 512x512 when expecting 1024x1024).

    Parameters
    ----------
    golden:
        The golden (correct) UI graph.

    Returns
    -------
    FaultInjection
        Structured fault injection with broken graph and repair delta.
    """
    broken = copy.deepcopy(golden)
    b_nodes = {n.get("id"): n for n in door_get_nodes(broken, [])}

    def _find_node(pred):
        for n in door_nodes(broken):
            if pred((n.get("type") or "")):
                return n
        return None

    # Find EmptyLatentImage or similar
    empty_node = _find_node(lambda t: ("empty" in t.lower() and "latent" in t.lower()) or
                                        ("emptysd" in t.lower() or "emptyflux" in t.lower()))
    if empty_node is None:
        raise ValueError("No EmptyLatentImage node found in golden graph")

    node_id = empty_node.get("id")
    node_type = empty_node.get("type", "")

    # Get widgets_values
    widgets_values = door_get_widgets_values(empty_node, [])
    if not isinstance(widgets_values, list) or len(widgets_values) < 2:
        raise ValueError(f"{node_type} has insufficient widgets_values")

    # For EmptyLatentImage: [width, height, batch_size]
    original_width = widgets_values[0]
    original_height = widgets_values[1]

    # Set wrong resolution - halve both dimensions
    new_width = max(256, original_width // 2)
    new_height = max(256, original_height // 2)

    new_widgets_values = list(widgets_values)
    new_widgets_values[0] = new_width
    new_widgets_values[1] = new_height

    empty_node["widgets_values"] = new_widgets_values

    injection = derive_repair_delta(broken, golden)

    return FaultInjection(
        broken=injection.broken,
        golden=injection.golden,
        repair_delta=injection.repair_delta,
        fault_delta=injection.fault_delta,
        fault_predicate={
            "locus": [{
                "type": "widget_value",
                "node_id": str(node_id),
                "node_type": node_type,
                "widget_index": 0,  # width
                "value": new_width,
            }, {
                "type": "widget_value",
                "node_id": str(node_id),
                "node_type": node_type,
                "widget_index": 1,  # height
                "value": new_height,
            }],
            "description": f"{node_type} resolution set to {new_width}x{new_height}",
        },
        repaired_predicate=injection.repaired_predicate,
        description=f"Resolution wrong: {node_type} {original_width}x{original_height}→{new_width}x{new_height}",
        user_effect=(
            "the output resolution is wrong — "
            "it's as if the latent dimensions were halved, producing a much smaller image than expected"
        ),
    )


def inject_fps_framecount_desync_fault(
    golden: dict[str, Any],
) -> FaultInjection:
    """Inject an 'FPS/framecount desync' fault for video workflows.

    This fault creates a mismatch between FPS and frame count, causing
    timing issues in video output.

    Parameters
    ----------
    golden:
        The golden (correct) UI graph.

    Returns
    -------
    FaultInjection
        Structured fault injection with broken graph and repair delta.
    """
    broken = copy.deepcopy(golden)
    b_nodes = {n.get("id"): n for n in door_get_nodes(broken, [])}

    def _find_node(pred):
        for n in door_nodes(broken):
            if pred((n.get("type") or "")):
                return n
        return None

    # Find video-related node with fps/frame_count
    # Common types: *, VideoCombineInfo, VideoCombine, ...
    video_node = _find_node(lambda t: "video" in t.lower() or "fps" in t.lower() or "frame" in t.lower())
    if video_node is None:
        # Try to find node with fps in widgets_values
        for n in door_get_nodes(broken, []):
            wv = door_get_widgets_values(n, [])
            if isinstance(wv, list) and any(isinstance(v, (int, float)) and v > 1 and v < 120 for v in wv):
                video_node = n
                break

    if video_node is None:
        raise ValueError("No video node with FPS/frame_count found in golden graph")

    node_id = video_node.get("id")
    node_type = video_node.get("type", "")

    # Get widgets_values
    widgets_values = door_get_widgets_values(video_node, [])
    if not isinstance(widgets_values, list):
        raise ValueError(f"{node_type} has no widgets_values")

    # Find fps and frame_count indices
    # Common layout: [fps, frame_count, ...] or [..., fps, frame_count]
    fps_index = None
    frame_count_index = None

    for i, v in enumerate(widgets_values):
        if isinstance(v, (int, float)) and 1 <= v <= 120:
            if fps_index is None:
                fps_index = i
            elif frame_count_index is None:
                frame_count_index = i
                break

    if fps_index is None:
        raise ValueError(f"{node_type} has no identifiable fps parameter")

    # If only fps found, that's still valid for the fault
    original_fps = widgets_values[fps_index]

    # Set fps to a mismatched value (e.g., double)
    new_fps = min(120, original_fps * 2)
    new_widgets_values = list(widgets_values)
    new_widgets_values[fps_index] = new_fps

    video_node["widgets_values"] = new_widgets_values

    injection = derive_repair_delta(broken, golden)

    locus_items = [{
        "type": "widget_value",
        "node_id": str(node_id),
        "node_type": node_type,
        "widget_index": fps_index,
        "value": new_fps,
    }]

    return FaultInjection(
        broken=injection.broken,
        golden=injection.golden,
        repair_delta=injection.repair_delta,
        fault_delta=injection.fault_delta,
        fault_predicate={
            "locus": locus_items,
            "description": f"{node_type} fps set to {new_fps}",
        },
        repaired_predicate=injection.repaired_predicate,
        description=f"FPS/framecount desync: {node_type} fps={original_fps}→{new_fps}",
        user_effect=(
            "the video timing is off — "
            "it's as if the frame rate doesn't match the expected duration, causing sync issues"
        ),
    )
