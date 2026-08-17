from __future__ import annotations

import difflib
from typing import Any, Mapping

from vibecomfy.porting.edit.ops import (
    AddNodeOp,
    EditOp,
    LinkSourceRef,
    LinkTargetRef,
    NodeFieldTarget,
    NodeTarget,
    RemoveLinkOp,
    RemoveNodeOp,
    SetModeOp,
    SetNodeFieldOp,
    SubgraphInterfaceOp,
    UpsertLinkOp,
)
from vibecomfy.porting.edit.projection import MODE_LABELS
from vibecomfy.porting.edit._session_types import (
    CompactDiagnostic,
    StatementResult,
    _diag,
)
from vibecomfy.porting.edit.types import FieldChange
from vibecomfy.workflow import VibeWorkflow, mode_to_litegraph

_UNRESOLVED_OLD_VALUE = object()

# ───────────────────────────────────────────────────────────────────────────
# Batch 9 (Law 3): canonical Δ as a batch value.
#
# ``diff(pre, post)`` is the pure generalizer: it computes the minimal set of
# Python-surface statements (the same six-op grammar ``interpret`` accepts) that
# transform ``pre`` into ``post`` over the editable quotient (π_edit).  The
# session's accepted batch IS the Δ; ``diff`` exists for judge/replay use and
# must be an inverse of ``interpret`` over the quotient:
#
#   pi_edit(interpret(pre, diff(pre, post))) == pi_edit(post)
#   diff(pre, interpret(pre, batch))  ~  the accepted statements (minimal,
#                                         deterministic)
#
# No parallel prose/JSON delta representation: the VALUE is the batch (the
# typed ops the grammar yields).  The summary functions below remain as the
# humanization layer only.
# ───────────────────────────────────────────────────────────────────────────


def _quotient_bindings(workflow: VibeWorkflow) -> dict[str, str]:
    """uid → emitted binding for the editable-quotient nodes.

    Mirrors ``pi_edit``'s node filter exactly (UI-only furniture is stripped,
    unresolvable helpers are excluded, virtual wires are kept) so ``diff`` and
    ``pi_edit`` agree on which nodes are editable.  Bindings are the pure
    ``(class_type, uid-order)`` function, so they are identical for pre, post,
    and any interpret reconstruction that preserves uids.
    """
    from vibecomfy._compile._helpers import (
        RESOLVABLE_HELPER_CLASS_TYPES,
        UI_ONLY_CLASS_TYPES,
    )
    from vibecomfy.porting.emit.emit_kwargs import _compute_variable_names
    from vibecomfy.porting.emit.emit_prepare import (
        _VIRTUAL_WIRE_EMITTER_CLASS_TYPES,
    )
    from vibecomfy.workflow import VibeEdge

    nodes = {
        str(node_id): node
        for node_id, node in workflow.nodes.items()
        if str(node.class_type) not in UI_ONLY_CLASS_TYPES
        and not (
            str(node.class_type) in RESOLVABLE_HELPER_CLASS_TYPES
            and str(node.class_type) not in _VIRTUAL_WIRE_EMITTER_CLASS_TYPES
        )
    }
    edges = [
        VibeEdge(edge.from_node, edge.from_output, edge.to_node, edge.to_input)
        for edge in workflow.edges
        if str(edge.from_node) in nodes and str(edge.to_node) in nodes
    ]
    names = _compute_variable_names(nodes, edges)
    return {
        str(node.uid): str(names[str(node_id)])
        for node_id, node in nodes.items()
        if getattr(node, "uid", None) is not None
        and str(node.uid)
        and str(node_id) in names
    }


def _quotient_node_by_uid(workflow: VibeWorkflow, uid: str) -> Any | None:
    for node in workflow.nodes.values():
        if str(getattr(node, "uid", "") or "") == str(uid):
            return node
    return None


def _node_id_by_uid(workflow: VibeWorkflow, uid: str) -> str | None:
    for node_id, node in workflow.nodes.items():
        if str(getattr(node, "uid", "") or "") == str(uid):
            return str(node_id)
    return None


def _edge_output_port(workflow: VibeWorkflow, edge: Any) -> str:
    """Normalize an edge's ``from_output`` to the π_edit-visible named port.

    Numeric slots are resolved through the deterministic typed-port aliases
    (``_agent_edit_output_ports``) so the emitted ``upsert_link`` source and
    ``pi_edit(post)`` agree even when the post IR stores a numeric slot.
    Named ports (raw output names or typed ``MASK_0`` aliases) pass through
    unchanged.
    """
    from vibecomfy.porting.emit.emit_prepare import _agent_edit_output_aliases

    raw = edge.from_output
    if isinstance(raw, str) and raw.isdigit():
        raw = int(raw)
    if isinstance(raw, int):
        source = workflow.nodes.get(str(edge.from_node))
        if source is not None:
            aliases = _agent_edit_output_aliases(source)
            if raw in aliases:
                return aliases[raw]
        return str(raw)
    return str(raw)


def _connection_key(workflow: VibeWorkflow, edge: Any) -> tuple[str, str, str, str]:
    return (
        str(getattr(workflow.nodes.get(str(edge.from_node)), "uid", "") or ""),
        _edge_output_port(workflow, edge),
        str(getattr(workflow.nodes.get(str(edge.to_node)), "uid", "") or ""),
        str(edge.to_input),
    )


def _quotient_connections(
    workflow: VibeWorkflow, uids: set[str]
) -> set[tuple[str, str, str, str]]:
    result: set[tuple[str, str, str, str]] = set()
    for edge in workflow.edges:
        src = workflow.nodes.get(str(edge.from_node))
        dst = workflow.nodes.get(str(edge.to_node))
        src_uid = str(getattr(src, "uid", "") or "")
        dst_uid = str(getattr(dst, "uid", "") or "")
        if src_uid not in uids or dst_uid not in uids:
            continue
        result.add(
            (
                src_uid,
                _edge_output_port(workflow, edge),
                dst_uid,
                str(edge.to_input),
            )
        )
    return result


def _incoming_connections(
    workflow: VibeWorkflow, target_uid: str, uids: set[str]
) -> set[tuple[str, str, str, str]]:
    return {
        key
        for key in _quotient_connections(workflow, uids)
        if key[2] == target_uid
    }


def _common_node_rebuild_required(
    pre_node: Any, post_node: Any
) -> bool:
    """True when a common node's π_edit delta needs remove+add.

    ``set_node_field`` writes by name to the channel the pre-node already has
    (widgets preferred, else inputs), so any change the op cannot express — a
    class-type change, a removed field name, a widget field added/removed/moved
    between channels, or a dual-channel name whose input value also changed —
    must be expressed as ``remove_node`` + ``add_node`` (the minimal batch
    that can reproduce post's node exactly).  A brand-new INPUT field needs no
    rebuild: ``set_node_field`` lands unknown names in the input channel.
    """
    if str(pre_node.class_type) != str(post_node.class_type):
        return True
    pre_widgets = dict(getattr(pre_node, "widgets", {}) or {})
    post_widgets = dict(getattr(post_node, "widgets", {}) or {})
    pre_inputs = dict(getattr(pre_node, "inputs", {}) or {})
    post_inputs = dict(getattr(post_node, "inputs", {}) or {})
    if set(pre_widgets) != set(post_widgets):
        return True
    if set(pre_inputs) - set(post_inputs):
        return True
    # A name in BOTH channels of the pre-node can only be written by
    # set_node_field into the widget channel; if its input value changed too,
    # the op cannot reproduce post.
    overlap = set(pre_widgets) & set(pre_inputs)
    for name in overlap:
        if pre_inputs.get(name) != post_inputs.get(name):
            return True
    return False


def _node_field_ops(uid: str, pre_node: Any, post_node: Any) -> list[EditOp]:
    """set_node_field ops for a common node over stable channels."""
    pre_widgets = dict(getattr(pre_node, "widgets", {}) or {})
    post_widgets = dict(getattr(post_node, "widgets", {}) or {})
    pre_inputs = dict(getattr(pre_node, "inputs", {}) or {})
    post_inputs = dict(getattr(post_node, "inputs", {}) or {})
    ops: list[EditOp] = []
    for name in sorted(pre_widgets):
        if pre_widgets.get(name) != post_widgets.get(name):
            ops.append(
                SetNodeFieldOp(
                    op="set_node_field",
                    target=NodeFieldTarget("", uid, name),
                    value=post_widgets.get(name),
                )
            )
    for name in sorted(pre_inputs):
        if name in pre_widgets:
            # Dual-channel name: the input value is unchanged (checked by the
            # rebuild guard); the widget op above already covers the name.
            continue
        if pre_inputs.get(name) != post_inputs.get(name):
            ops.append(
                SetNodeFieldOp(
                    op="set_node_field",
                    target=NodeFieldTarget("", uid, name),
                    value=post_inputs.get(name),
                )
            )
    for name in sorted(set(post_inputs) - set(pre_inputs) - set(pre_widgets)):
        # Brand-new input field: set_node_field lands unknown names in the
        # input channel, exactly where post keeps it.
        ops.append(
            SetNodeFieldOp(
                op="set_node_field",
                target=NodeFieldTarget("", uid, name),
                value=post_inputs.get(name),
            )
        )
    return ops


def _add_node_op_for(uid: str, post: VibeWorkflow, uids: set[str]) -> AddNodeOp:
    post_node = _quotient_node_by_uid(post, uid)
    assert post_node is not None
    wired_names = {
        key[3]
        for key in _incoming_connections(post, uid, uids)
    }
    fields: dict[str, Any] = {}
    # Inputs first, then widgets: a name in BOTH channels keeps its WIDGET
    # value (the literal channel), which ``widget_field_names`` restores.
    for name, value in (dict(getattr(post_node, "inputs", {}) or {})).items():
        if str(name) in wired_names:
            continue
        fields[str(name)] = value
    for name, value in (dict(getattr(post_node, "widgets", {}) or {})).items():
        fields[str(name)] = value
    inputs: dict[str, LinkSourceRef] = {}
    for src_uid, port, _dst_uid, input_name in sorted(
        _incoming_connections(post, uid, uids)
    ):
        inputs[input_name] = LinkSourceRef("", src_uid, port)
    return AddNodeOp(
        op="add_node",
        scope_path="",
        class_type=str(post_node.class_type),
        fields=fields,
        inputs=inputs,
        uid=uid,
        node_id=_node_id_by_uid(post, uid),
        # Batch 9 fix: carry the instance widgets channel explicitly so
        # ``_split_add_fields`` restores unknown-schema widget fields on the
        # interpret side (schema classification alone would drop them).
        widget_field_names=tuple(
            sorted(str(name) for name in (getattr(post_node, "widgets", {}) or {}))
        ),
    )


def _subgraph_interfaces(workflow: VibeWorkflow) -> dict[str, tuple[str, tuple, tuple]]:
    """id → (name, inputs, outputs) for retained ``definitions`` subgraphs.

    Mirrors π_edit's ``_graph_interfaces`` projection exactly (same raw
    definitions source and same ``_subgraph_definitions_from_raw`` parser) so
    ``diff`` and the quotient agree on which signatures are grammar-visible.
    """
    from vibecomfy.porting.emit.emit_subgraph import _subgraph_definitions_from_raw

    metadata = getattr(workflow, "metadata", None) or {}
    definitions = metadata.get("definitions")
    if not isinstance(definitions, Mapping):
        return {}
    subgraphs = _subgraph_definitions_from_raw(
        {"definitions": dict(definitions)}, source_path=None
    )
    return {
        str(subgraph.id): (
            str(subgraph.raw_name),
            tuple((port.name, port.type) for port in subgraph.inputs),
            tuple((port.name, port.type) for port in subgraph.outputs),
        )
        for subgraph in subgraphs.values()
    }


def _subgraph_interface_ops(
    pre: VibeWorkflow, post: VibeWorkflow
) -> list[SubgraphInterfaceOp]:
    """Add/remove/change statements for grammar-visible subgraph signatures."""
    pre_subgraphs = _subgraph_interfaces(pre)
    post_subgraphs = _subgraph_interfaces(post)
    ops: list[SubgraphInterfaceOp] = []
    for sub_id in sorted(post_subgraphs):
        if sub_id not in pre_subgraphs:
            name, inputs, outputs = post_subgraphs[sub_id]
            ops.append(
                SubgraphInterfaceOp(
                    op="subgraph_interface",
                    action="add",
                    name=name,
                    inputs=inputs,
                    outputs=outputs,
                    id=sub_id,
                )
            )
        elif pre_subgraphs[sub_id] != post_subgraphs[sub_id]:
            name, inputs, outputs = post_subgraphs[sub_id]
            ops.append(
                SubgraphInterfaceOp(
                    op="subgraph_interface",
                    action="change",
                    name=name,
                    inputs=inputs,
                    outputs=outputs,
                    id=sub_id,
                )
            )
    for sub_id in sorted(pre_subgraphs):
        if sub_id not in post_subgraphs:
            name, _inputs, _outputs = pre_subgraphs[sub_id]
            ops.append(
                SubgraphInterfaceOp(
                    op="subgraph_interface",
                    action="remove",
                    name=name,
                    id=sub_id,
                )
            )
    return ops


def _order_add_uids(add_uids: set[str], post: VibeWorkflow, uids: set[str]) -> list[str]:
    """Deterministic topological order: sources added before dependents."""
    remaining = set(add_uids)
    ordered: list[str] = []
    while remaining:
        ready = sorted(
            uid
            for uid in remaining
            if all(
                src_uid not in remaining
                for src_uid, _port, _dst, _input_name in _incoming_connections(
                    post, uid, uids
                )
            )
        )
        if not ready:
            ready = [sorted(remaining)[0]]
        ordered.extend(ready)
        remaining.difference_update(ready)
    return ordered


def diff(
    pre: VibeWorkflow,
    post: VibeWorkflow,
    *,
    schema_provider: Any = None,
) -> tuple[EditOp, ...]:
    """Canonical Δ: the minimal deterministic batch that turns ``pre`` into
    ``post`` over the editable quotient (Law 3).

    The result is a tuple of the SAME six ops ``interpret`` accepts
    (``set_node_field``, ``set_mode``, ``add_node``, ``upsert_link``,
    ``remove_node``, ``remove_link``) — a valid batch source — so
    ``interpret(pre, diff(pre, post))`` reconstructs ``post``'s π_edit.
    Pure and deterministic: the inputs are never mutated and the same
    ``(pre, post)`` always yields the same Δ.  ``diff(pre, pre)`` is the
    empty batch.

    ``schema_provider`` is accepted for API symmetry with ``interpret``; the
    quotient derivation is schema-independent (bindings are a pure function
    of class_type + uid order), so it is not required.
    """
    _ = schema_provider
    if not isinstance(pre, VibeWorkflow) or not isinstance(post, VibeWorkflow):
        raise TypeError("diff requires VibeWorkflow pre and post")

    pre_bindings = _quotient_bindings(pre)
    post_bindings = _quotient_bindings(post)
    pre_uids = set(pre_bindings)
    post_uids = set(post_bindings)
    common_uids = sorted(pre_uids & post_uids)
    removed_uids = sorted(pre_uids - post_uids)
    added_uids = sorted(post_uids - pre_uids)
    if not (common_uids or removed_uids or added_uids):
        return ()

    rebuild_uids: set[str] = set()
    ops: list[EditOp] = []

    # 0. Subgraph-interface statements: π_edit includes grammar-visible
    #    subgraph signatures (``metadata["definitions"]``), so a definitions
    #    delta is part of the canonical Δ (Law 3).  Emitted first; they are
    #    independent of the node/link ops below.
    ops.extend(_subgraph_interface_ops(pre, post))

    # 1. Node removals (incl. rebuild removals for common nodes whose π_edit
    #    cannot be expressed with set_node_field/set_mode alone).
    for uid in common_uids:
        pre_node = _quotient_node_by_uid(pre, uid)
        post_node = _quotient_node_by_uid(post, uid)
        if pre_node is None or post_node is None:
            continue
        if _common_node_rebuild_required(pre_node, post_node):
            rebuild_uids.add(uid)
    for uid in sorted(rebuild_uids) + removed_uids:
        ops.append(RemoveNodeOp(op="remove_node", target=NodeTarget("", uid)))

    # 2. Link removals: pre-only connections whose target node survives.
    #    A rewire (same target input, new source in post) needs no remove_link:
    #    upsert_link is replace-semantics over the target input.
    pre_conns = _quotient_connections(pre, pre_uids)
    post_conns = _quotient_connections(post, post_uids)
    post_target_inputs = {
        (dst_uid, input_name) for _src, _port, dst_uid, input_name in post_conns
    }
    for src_uid, port, dst_uid, input_name in sorted(pre_conns - post_conns):
        if dst_uid not in post_uids or dst_uid in rebuild_uids:
            continue  # covered by remove_node
        if src_uid in removed_uids or src_uid in rebuild_uids:
            continue  # remove_node drops the source's edges
        if (dst_uid, input_name) in post_target_inputs:
            continue  # rewire: covered by upsert_link
        ops.append(
            RemoveLinkOp(
                op="remove_link",
                target=LinkTargetRef("", dst_uid, input_name),
            )
        )

    # 3. Mode + literal-field changes on surviving common nodes.
    for uid in common_uids:
        if uid in rebuild_uids:
            continue
        pre_node = _quotient_node_by_uid(pre, uid)
        post_node = _quotient_node_by_uid(post, uid)
        if pre_node is None or post_node is None:
            continue
        if mode_to_litegraph(pre_node.mode) != mode_to_litegraph(post_node.mode):
            ops.append(
                SetModeOp(
                    op="set_mode",
                    target=NodeTarget("", uid),
                    mode=mode_to_litegraph(post_node.mode),
                )
            )
        ops.extend(_node_field_ops(uid, pre_node, post_node))

    # 4. Node additions (topologically ordered: a new node's wired inputs may
    #    reference other new nodes).  AddNodeOp has no mode channel, so a
    #    non-default mode needs an explicit set_mode right after the add.
    for uid in _order_add_uids(rebuild_uids | set(added_uids), post, post_uids):
        ops.append(_add_node_op_for(uid, post, post_uids))
        post_node = _quotient_node_by_uid(post, uid)
        if post_node is not None and mode_to_litegraph(post_node.mode) != 0:
            ops.append(
                SetModeOp(
                    op="set_mode",
                    target=NodeTarget("", uid),
                    mode=mode_to_litegraph(post_node.mode),
                )
            )

    # 5. New connections whose target survives: upsert (replaces any pre edge
    #    on the same input, so a rewire needs no separate remove_link).
    #    A rebuilt node's remove_node also drops its OUTGOING edges, so every
    #    post edge from a rebuilt node to a surviving target is re-established
    #    here too (incoming edges travel via add_node.inputs).
    emitted_upserts: set[tuple[str, str, str, str]] = set()
    for src_uid, port, dst_uid, input_name in sorted(post_conns - pre_conns):
        if dst_uid in added_uids or dst_uid in rebuild_uids:
            continue  # covered by add_node.inputs
        emitted_upserts.add((src_uid, port, dst_uid, input_name))
    for src_uid, port, dst_uid, input_name in sorted(post_conns):
        if src_uid not in rebuild_uids or dst_uid in added_uids or dst_uid in rebuild_uids:
            continue
        emitted_upserts.add((src_uid, port, dst_uid, input_name))
    for src_uid, port, dst_uid, input_name in sorted(emitted_upserts):
        ops.append(
            UpsertLinkOp(
                op="upsert_link",
                source=LinkSourceRef("", src_uid, port),
                target=LinkTargetRef("", dst_uid, input_name),
            )
        )

    return tuple(ops)



class _DiffMixin:
    """Diff and summarize methods extracted from EditSession."""

    def _summarize_op(self, op: EditOp) -> str:
        """Generate a single-sentence summary for one edit operation."""
        if isinstance(op, SetNodeFieldOp):
            return self._summarize_set_node_field(op)
        if isinstance(op, AddNodeOp):
            return self._summarize_add_node(op)
        if isinstance(op, RemoveNodeOp):
            return self._summarize_remove_node(op)
        if isinstance(op, UpsertLinkOp):
            return self._summarize_upsert_link(op)
        if isinstance(op, RemoveLinkOp):
            return self._summarize_remove_link(op)
        if isinstance(op, SetModeOp):
            return self._summarize_set_mode(op)
        return ""

    def _summarize_set_node_field(self, op: SetNodeFieldOp) -> str:
        name = self._node_display_name(op.target.scope_path, op.target.uid)
        field = op.target.field_path
        old_value = self._original_node_field_value(op.target.scope_path, op.target.uid, field)
        new_value = op.value
        if old_value is not None:
            return f"Changed {name}.{field} from {old_value!r} to {new_value!r}."
        return f"Set {name}.{field} = {new_value!r}."

    def _summarize_add_node(self, op: AddNodeOp) -> str:
        name = self.name_by_uid.get(
            self._uid_for_scope(op.scope_path, op.class_type), op.class_type
        )
        detail_parts: list[str] = []
        if op.inputs:
            input_parts: list[str] = []
            for field_name, source_ref in op.inputs.items():
                src_name = self._node_display_name(source_ref.scope_path, source_ref.uid)
                socket_type = self._output_socket_type(source_ref.scope_path, source_ref.uid, source_ref.output_slot)
                slot_str = source_ref.output_slot
                if isinstance(slot_str, int):
                    slot_str = str(slot_str)
                type_hint = f" ({socket_type})" if socket_type else ""
                input_parts.append(f"{src_name}.{slot_str}{type_hint}")
                # Check for adjacent same-type inputs
                adj = self._adjacent_same_type_inputs(
                    op.scope_path if op.scope_path else "", field_name
                )
                if adj:
                    input_parts[-1] += f" (adjacent same-type: {adj})"
            detail_parts.append("with inputs: " + ", ".join(input_parts))
        if op.fields:
            field_parts = [f"{k}={v!r}" for k, v in op.fields.items()]
            detail_parts.append("with fields: " + ", ".join(field_parts))
        detail = "; ".join(detail_parts)
        if detail:
            return f"Added {op.class_type} node '{name}' {detail}."
        return f"Added {op.class_type} node '{name}'."

    def _summarize_remove_node(self, op: RemoveNodeOp) -> str:
        name = self.name_by_uid.get(op.target.uid, op.target.uid)
        class_type = self._original_node_class_type(op.target.scope_path, op.target.uid)
        ct_str = f"{class_type} " if class_type else ""
        return f"Removed {ct_str}node '{name}'."

    def _summarize_upsert_link(self, op: UpsertLinkOp) -> str:
        src_name = self._node_display_name(op.source.scope_path, op.source.uid)
        dst_name = self._node_display_name(op.target.scope_path, op.target.uid)
        src_slot = op.source.output_slot
        if isinstance(src_slot, int):
            src_slot = str(src_slot)
        dst_field = op.target.input_field
        socket_type = self._output_socket_type(op.source.scope_path, op.source.uid, op.source.output_slot)
        type_hint = f" ({socket_type})" if socket_type else ""

        # Check original ledger for a pre-existing link to determine new vs rewire
        prev_link = self._find_link_to_target_in_ledger(
            self.original_ledger, op.target.scope_path, op.target.uid, op.target.input_field
        )
        if prev_link is not None:
            # Rewire case: original ledger had a link
            pass
        else:
            # No original link — this is a new connection
            prev_link = None
        if prev_link is not None:
            prev_src_uid, prev_src_slot = prev_link
            prev_name = self._node_display_name(op.target.scope_path, prev_src_uid)
            prev_slot_str = str(prev_src_slot) if isinstance(prev_src_slot, int) else prev_src_slot
            return (
                f"Rewired {dst_name}.{dst_field}{type_hint} "
                f"from {prev_name}.{prev_slot_str} → {src_name}.{src_slot}."
            )
        return (
            f"Connected {src_name}.{src_slot}{type_hint} → "
            f"{dst_name}.{dst_field}."
        )

    def _summarize_remove_link(self, op: RemoveLinkOp) -> str:
        if op.target is None:
            return f"Removed link id={op.link_id}."
        name = self._node_display_name(op.target.scope_path, op.target.uid)
        field = op.target.input_field
        prev_link = self._find_link_to_target(op.target.scope_path, op.target.uid, op.target.input_field)
        if prev_link is not None:
            prev_src_uid, prev_src_slot = prev_link
            prev_name = self._node_display_name(op.target.scope_path, prev_src_uid)
            return f"Disconnected {name}.{field} from {prev_name}.{prev_src_slot}."
        return f"Disconnected {name}.{field}."

    def _summarize_set_mode(self, op: SetModeOp) -> str:
        name = self._node_display_name(op.target.scope_path, op.target.uid)
        old_mode = self._original_node_mode(op.target.scope_path, op.target.uid)
        old_label = MODE_LABELS.get(old_mode, f"mode={old_mode}")
        new_label = MODE_LABELS.get(op.mode, f"mode={op.mode}")
        return f"Changed {name} mode from {old_label} to {new_label}."

    def _build_field_changes(
        self,
        landed_ops: tuple[EditOp, ...],
        statement_results: tuple[StatementResult, ...],
    ) -> tuple[tuple[FieldChange, ...], tuple[StatementResult, ...]]:
        if not landed_ops:
            return (), statement_results

        field_changes: list[FieldChange] = []
        unresolved_by_statement: dict[int, list[CompactDiagnostic]] = {}
        landed_statement_indexes = [i for i, statement in enumerate(statement_results) if statement.landed]

        for op_index, op in enumerate(landed_ops):
            if op_index >= len(landed_statement_indexes):
                break
            statement_index = landed_statement_indexes[op_index]
            change, unresolved = self._field_change_from_landed_op(op)
            if change is not None:
                field_changes.append(change)
            if unresolved is not None:
                unresolved_by_statement.setdefault(statement_index, []).append(unresolved)

        if not unresolved_by_statement:
            return tuple(field_changes), statement_results

        updated_results: list[StatementResult] = list(statement_results)
        for statement_index, extras in unresolved_by_statement.items():
            statement = updated_results[statement_index]
            updated_results[statement_index] = StatementResult(
                statement_index=statement.statement_index,
                source=statement.source,
                ok=statement.ok,
                diagnostics=statement.diagnostics + tuple(extras),
                landed=statement.landed,
                op_kind=statement.op_kind,
                detail=dict(statement.detail),
                touched_uids=statement.touched_uids,
                dependency_cause=statement.dependency_cause,
                teaching_hint=statement.teaching_hint,
                status=statement.status,
                reason=statement.reason,
            )
        return tuple(field_changes), tuple(updated_results)

    def _field_change_from_landed_op(
        self, op: EditOp
    ) -> tuple[FieldChange | None, CompactDiagnostic | None]:
        if isinstance(op, SetNodeFieldOp):
            old = self._original_node_field_value(
                op.target.scope_path, op.target.uid, op.target.field_path
            )
            new = op.value
            field_path = op.target.field_path
            uid = op.target.uid
        elif isinstance(op, SetModeOp):
            old = self._original_node_mode(op.target.scope_path, op.target.uid)
            new = op.mode
            field_path = "mode"
            uid = op.target.uid
        elif isinstance(op, UpsertLinkOp):
            old = self._original_link_value(
                op.target.scope_path, op.target.uid, op.target.input_field
            )
            new = self._link_ref_value(op.source)
            field_path = op.target.input_field
            uid = op.target.uid
        elif isinstance(op, RemoveLinkOp) and op.target is not None:
            old = self._original_link_value(
                op.target.scope_path, op.target.uid, op.target.input_field
            )
            new = None
            field_path = op.target.input_field
            uid = op.target.uid
        else:
            return None, None

        unresolved = None
        if old is _UNRESOLVED_OLD_VALUE:
            unresolved = _diag(
                "field_change_old_unresolved",
                (
                    f"Could not resolve the original value for {uid}.{field_path}; "
                    "emitting the landed change with old=None."
                ),
                severity="info",
                detail={"uid": uid, "field_path": field_path},
            )
            old = None
        return FieldChange(uid=uid, field_path=field_path, old=old, new=new), unresolved


def _render_op_diff(op: Any, *, old_value: Any = None) -> str:
    """Produce a single-line diff summary for one edit operation.

    Driven by the same pattern as ``_summarize_op`` but kept compact so it is
    suitable for line-by-line agent feedback.

    When *old_value* is supplied for a ``SetNodeFieldOp`` whose *field_path*
    is ``"source"`` and both values are strings, a multi-line unified diff is
    produced so that changed ``vibecomfy.exec`` source bodies are readable.
    """
    if isinstance(op, SetNodeFieldOp):
        field = op.target.field_path
        uid = op.target.uid
        new_val = op.value
        if (
            field == "source"
            and old_value is not None
            and isinstance(old_value, str)
            and isinstance(new_val, str)
        ):
            old_lines = old_value.splitlines(keepends=True)
            new_lines = new_val.splitlines(keepends=True)
            diff_lines = list(
                difflib.unified_diff(
                    old_lines,
                    new_lines,
                    fromfile=f"{uid}/source (old)",
                    tofile=f"{uid}/source (new)",
                    lineterm="",
                )
            )
            if diff_lines:
                header = f"set_node_field  uid={uid!r} field={field!r}  ({len(old_lines)}→{len(new_lines)} lines)"
                return header + "\n" + "\n".join(diff_lines)
        old = _repr_short(new_val)
        return f"set_node_field  uid={uid!r} field={field!r} → {old}"
    if isinstance(op, AddNodeOp):
        ct = op.class_type
        n_inputs = len(op.inputs) if op.inputs else 0
        n_fields = len(op.fields) if op.fields else 0
        return f"add_node  class_type={ct!r}  inputs={n_inputs}  fields={n_fields}"
    if isinstance(op, RemoveNodeOp):
        return f"remove_node  uid={op.target.uid!r}"
    if isinstance(op, UpsertLinkOp):
        src = f"{op.source.uid}.{op.source.output_slot}"
        tgt = f"{op.target.uid}.{op.target.input_field}"
        return f"upsert_link  {src} → {tgt}"
    if isinstance(op, RemoveLinkOp):
        if op.target is not None:
            return f"remove_link  target={op.target.uid!r}.{op.target.input_field}"
        return f"remove_link  link_id={op.link_id}"
    if isinstance(op, SetModeOp):
        return f"set_mode  uid={op.target.uid!r} → mode={op.mode}"
    if isinstance(op, SubgraphInterfaceOp):
        detail = f"action={op.action} name={op.name!r}"
        if op.inputs:
            detail += f" inputs={len(op.inputs)}"
        if op.outputs:
            detail += f" outputs={len(op.outputs)}"
        return f"subgraph_interface  {detail}"
    return repr(type(op).__name__)


def _repr_short(value: Any) -> str:
    """Truncate repr for compact display."""
    s = repr(value)
    if len(s) > 60:
        return s[:57] + "..."
    return s
