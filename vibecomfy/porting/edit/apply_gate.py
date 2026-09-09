"""Apply-gate: replay-verify + structural sanity before claiming success.

After ``interpret(pre, Δ)`` the apply path must prove the product before
any ``apply_eligible=true`` / "validated successfully" claim (RC6 / B4 S4).

Checks, in order:

1. Newly created self-loops ``u→u`` that were not in ``pre``.
2. Orphaned outputs of nodes touched by Δ (a pre outgoing slot of a
   touched node has no post consumer, and the original destination's
   matching input is now unconnected).
3. Replay-verify: ``interpret(pre, Δ)`` reconstructs ``post`` over the
   editable signature (uids, class, widgets/mode, edges).
4. Empty replay: a claimed edit whose ``diff(pre, post)`` is empty is
   not apply-eligible.

``guard_emit`` already refuses uid-matched nodes changed outside
``snapshot_delta``; this module does not reimplement that check.
"""

from __future__ import annotations

from dataclasses import dataclass
from typing import Any, Mapping, Sequence

from vibecomfy.porting.edit._ir_utils import (
    RecursiveEditError,
    _freeze,
    _uids_for_op,
    recursive_state_snapshot,
)
from vibecomfy.porting.edit._session_types import CompactDiagnostic, _diag
from vibecomfy.porting.edit.ops import EditOp, RemoveLinkOp, RemoveNodeOp
from vibecomfy.workflow import VibeWorkflow, mode_to_litegraph


@dataclass(frozen=True, slots=True)
class ApplyGateResult:
    """Outcome of :func:`verify_apply`.

    ``ok`` is false when the candidate is corrupt or unverifiable.
    ``apply_eligible`` is true only when a non-empty, replay-verified Δ
    survived every structural check.
    """

    ok: bool
    apply_eligible: bool
    diagnostics: tuple[CompactDiagnostic, ...] = ()
    reason: str | None = None


class _EditableIdentityError(ValueError):
    """The editable quotient cannot identify every node and edge exactly."""

    def __init__(self, reason: str, **detail: Any) -> None:
        self.reason = reason
        self.detail = detail
        super().__init__(reason)


def _identity_text(value: Any, *, field: str, detail: Mapping[str, Any]) -> str:
    if not isinstance(value, str) or not value.strip():
        raise _EditableIdentityError(
            f"missing_{field}",
            **detail,
        )
    return value


def _edge_identity(edge: Any, *, edge_index: int) -> tuple[str, str, str, str]:
    try:
        source_node = edge.from_node
        source_slot = edge.from_output
        destination_node = edge.to_node
        destination_slot = edge.to_input
    except AttributeError as exc:
        raise _EditableIdentityError(
            "malformed_edge",
            edge_index=edge_index,
            missing_field=str(exc).split("'")[-2] if "'" in str(exc) else "",
        ) from exc
    return (
        _identity_text(
            str(source_node) if isinstance(source_node, (int, str)) else source_node,
            field="edge_source_node_id",
            detail={"edge_index": edge_index},
        ),
        _identity_text(
            source_slot,
            field="edge_source_slot",
            detail={"edge_index": edge_index},
        ),
        _identity_text(
            str(destination_node)
            if isinstance(destination_node, (int, str))
            else destination_node,
            field="edge_destination_node_id",
            detail={"edge_index": edge_index},
        ),
        _identity_text(
            destination_slot,
            field="edge_destination_slot",
            detail={"edge_index": edge_index},
        ),
    )


def _node_items(workflow: VibeWorkflow) -> tuple[tuple[Any, Any], ...]:
    nodes = getattr(workflow, "nodes", None)
    if not isinstance(nodes, Mapping):
        raise _EditableIdentityError("malformed_nodes", actual_type=type(nodes).__name__)
    return tuple(nodes.items())


def _edge_items(workflow: VibeWorkflow) -> tuple[Any, ...]:
    edges = getattr(workflow, "edges", None)
    if not isinstance(edges, (list, tuple)):
        raise _EditableIdentityError("malformed_edges", actual_type=type(edges).__name__)
    return tuple(edges)


def _uid_by_node_id(workflow: VibeWorkflow) -> dict[str, str]:
    mapping: dict[str, str] = {}
    node_id_by_uid: dict[str, str] = {}
    for raw_node_id, node in _node_items(workflow):
        if not isinstance(raw_node_id, (int, str)) or (
            isinstance(raw_node_id, str) and not raw_node_id.strip()
        ):
            raise _EditableIdentityError(
                "missing_node_id",
                node_id=raw_node_id,
            )
        node_id = str(raw_node_id)
        declared_node_id = getattr(node, "id", None)
        if not isinstance(declared_node_id, (int, str)) or str(declared_node_id) != node_id:
            raise _EditableIdentityError(
                "node_id_mismatch",
                node_id=node_id,
                declared_node_id=declared_node_id,
            )
        if node_id in mapping:
            raise _EditableIdentityError(
                "ambiguous_node_id",
                node_id=node_id,
            )
        uid = getattr(node, "uid", None)
        if not isinstance(uid, str) or not uid.strip():
            raise _EditableIdentityError(
                "missing_node_uid",
                node_id=node_id,
            )
        prior_node_id = node_id_by_uid.get(uid)
        if prior_node_id is not None:
            raise _EditableIdentityError(
                "duplicate_node_uid",
                uid=uid,
                node_ids=(prior_node_id, node_id),
            )
        mapping[node_id] = uid
        node_id_by_uid[uid] = node_id
    return mapping


def _node_id_by_uid(workflow: VibeWorkflow) -> dict[str, str]:
    return {uid: node_id for node_id, uid in _uid_by_node_id(workflow).items()}


def _edge_uid_records(
    workflow: VibeWorkflow,
) -> tuple[tuple[str, str, str, str], ...]:
    uid_by_id = _uid_by_node_id(workflow)
    records: list[tuple[str, str, str, str]] = []
    for edge_index, edge in enumerate(_edge_items(workflow)):
        source_id, source_slot, destination_id, destination_slot = _edge_identity(
            edge,
            edge_index=edge_index,
        )
        source_uid = uid_by_id.get(source_id)
        destination_uid = uid_by_id.get(destination_id)
        if source_uid is None or destination_uid is None:
            raise _EditableIdentityError(
                "unresolvable_edge_endpoint",
                edge_index=edge_index,
                source_node_id=source_id,
                destination_node_id=destination_id,
                unresolved=tuple(
                    endpoint
                    for endpoint, uid in (
                        ("source", source_uid),
                        ("destination", destination_uid),
                    )
                    if uid is None
                ),
            )
        records.append((source_uid, source_slot, destination_uid, destination_slot))
    return tuple(sorted(records))


def _self_loop_uids(workflow: VibeWorkflow) -> set[str]:
    loops: set[str] = set()
    uid_by_id = _uid_by_node_id(workflow)
    for edge in _edge_items(workflow):
        src_id = str(edge.from_node)
        dst_id = str(edge.to_node)
        if src_id != dst_id:
            continue
        uid = uid_by_id.get(src_id)
        if uid:
            loops.add(uid)
    return loops


def _new_self_loop_diagnostic(
    pre: VibeWorkflow,
    post: VibeWorkflow,
) -> CompactDiagnostic | None:
    new_loops = _self_loop_uids(post) - _self_loop_uids(pre)
    if not new_loops:
        return None
    return _diag(
        "apply_gate_new_self_loop",
        "Apply gate refused success: the edit created a self-loop "
        f"({', '.join(sorted(new_loops))}) that was not in the pre-IR.",
        severity="error",
        detail={"uids": tuple(sorted(new_loops))},
    )


def _touched_uids(ops: Sequence[EditOp]) -> set[str]:
    uids: set[str] = set()
    for op in ops:
        for _scope, uid in _uids_for_op(op):
            if uid:
                uids.add(str(uid))
    return uids


def _explicit_remove_target_uids(ops: Sequence[EditOp]) -> set[str]:
    removed: set[str] = set()
    for op in ops:
        if isinstance(op, RemoveNodeOp):
            uid = getattr(op.target, "uid", None)
            if uid:
                removed.add(str(uid))
        elif isinstance(op, RemoveLinkOp):
            uid = getattr(op.target, "uid", None)
            if uid:
                removed.add(str(uid))
    return removed


def _outgoing_slots_by_uid(
    workflow: VibeWorkflow,
) -> dict[str, set[str]]:
    slots: dict[str, set[str]] = {}
    for src_uid, src_slot, _dst_uid, _dst_slot in _edge_uid_records(workflow):
        slots.setdefault(src_uid, set()).add(src_slot)
    return slots


def _pre_destinations_for_output(
    workflow: VibeWorkflow,
    src_uid: str,
    src_slot: str,
) -> tuple[tuple[str, str], ...]:
    dests: list[tuple[str, str]] = []
    for rec_src, rec_slot, dst_uid, dst_slot in _edge_uid_records(workflow):
        if rec_src == src_uid and rec_slot == src_slot:
            dests.append((dst_uid, dst_slot))
    return tuple(dests)


def _input_connected(workflow: VibeWorkflow, dst_uid: str, dst_slot: str) -> bool:
    return any(
        rec_dst == dst_uid and rec_in == dst_slot
        for _src, _slot, rec_dst, rec_in in _edge_uid_records(workflow)
    )


def _orphaned_output_diagnostic(
    pre: VibeWorkflow,
    post: VibeWorkflow,
    ops: Sequence[EditOp],
) -> CompactDiagnostic | None:
    if not ops:
        return None
    touched = _touched_uids(ops)
    if not touched:
        return None
    skip_uids = _explicit_remove_target_uids(ops)
    pre_ids = _node_id_by_uid(pre)
    post_ids = _node_id_by_uid(post)
    pre_out = _outgoing_slots_by_uid(pre)
    post_out = _outgoing_slots_by_uid(post)
    orphans: list[dict[str, Any]] = []
    for uid in sorted(touched):
        if uid in skip_uids:
            continue
        if uid not in pre_ids or uid not in post_ids:
            continue
        lost_slots = pre_out.get(uid, set()) - post_out.get(uid, set())
        for slot in sorted(lost_slots):
            for dst_uid, dst_slot in _pre_destinations_for_output(pre, uid, slot):
                if dst_uid not in post_ids:
                    continue
                if _input_connected(post, dst_uid, dst_slot):
                    continue
                orphans.append(
                    {
                        "uid": uid,
                        "output_slot": slot,
                        "destination_uid": dst_uid,
                        "destination_input": dst_slot,
                    }
                )
    if not orphans:
        return None
    return _diag(
        "apply_gate_orphaned_output",
        "Apply gate refused success: a touched node's output no longer "
        "reaches its original destination and that destination input is "
        "now unconnected.",
        severity="error",
        detail={"orphans": tuple(orphans)},
    )


def _node_field_signature(node: Any) -> tuple[Any, ...]:
    widgets = dict(getattr(node, "widgets", None) or {})
    inputs = getattr(node, "inputs", None) or {}
    fields: list[tuple[str, str, Any]] = []
    if isinstance(inputs, Mapping):
        # Canonical API link pairs are represented by the edge quotient and
        # must not be confused with authored two-item list literals.  Every
        # other grammar-visible input value, including list/tuple/mapping
        # aggregates, remains part of replay equality.
        from vibecomfy._compile._graph import is_canonical_api_link

        fields.extend(
            (
                "input",
                str(name),
                _freeze(value),
            )
            for name, value in inputs.items()
            if not is_canonical_api_link(value)
        )
    fields.extend(
        ("widget", str(name), _freeze(value))
        for name, value in widgets.items()
    )
    return (
        str(getattr(node, "class_type", "")),
        tuple(sorted(fields)),
        mode_to_litegraph(getattr(node, "mode", 0)),
    )


def _subgraph_interface_signature(workflow: VibeWorkflow) -> tuple[Any, ...]:
    """Return grammar-visible subgraph signatures in the editable quotient."""
    from vibecomfy.porting.edit._diff import _subgraph_interfaces

    interfaces = _subgraph_interfaces(workflow)
    return tuple(
        (str(subgraph_id), name, inputs, outputs)
        for subgraph_id, (name, inputs, outputs) in sorted(interfaces.items())
    )


def _recursive_editable_signature(workflow: VibeWorkflow) -> tuple[Any, ...]:
    """Return the typed, non-root portion of the editable quotient.

    This is intentionally a projection of the existing ephemeral index and
    field descriptor.  It does not copy, normalize, emit, or mutate recursive
    definitions; it only makes admitted field/mode edits visible to the
    existing replay gate.  Presentation, provenance, occurrence shells, and
    volatile link IDs are excluded.
    """
    try:
        snapshot = recursive_state_snapshot(workflow)
    except RecursiveEditError as exc:
        raise _EditableIdentityError(
            f"recursive_{exc.code}",
            **exc.detail,
        ) from exc
    return snapshot


def editable_signature(
    workflow: VibeWorkflow,
) -> tuple[
    dict[str, tuple[Any, ...]],
    tuple[tuple[str, str, str, str], ...],
    tuple[Any, ...],
    tuple[Any, ...],
]:
    """Return the complete canonical editable quotient signature.

    Runtime link IDs, layout, and other emit furniture are deliberately absent.
    Grammar-visible subgraph interfaces are included alongside nodes and edges.
    Every node and every edge endpoint must be identifiable; otherwise callers
    must fail closed rather than compare a partial quotient.
    """
    uid_by_id = _uid_by_node_id(workflow)
    nodes = {
        uid_by_id[str(node_id)]: _node_field_signature(node)
        for node_id, node in _node_items(workflow)
    }
    return (
        nodes,
        _edge_uid_records(workflow),
        _subgraph_interface_signature(workflow),
        _recursive_editable_signature(workflow),
    )


def _recursive_error_diagnostic(error: RecursiveEditError) -> CompactDiagnostic:
    """Convert typed recursive identity/diff failures into gate diagnostics."""
    structural = error.code == "unsupported_structural_scope"
    return _diag(
        "apply_gate_recursive_structural" if structural else "apply_gate_unverifiable_identity",
        "Apply gate refused success: recursive typed state could not be "
        "replayed safely; capture -> port through canonical Python -> "
        "reopen/reload before retrying.",
        severity="error",
        detail={
            "recursive_reason": error.code,
            **error.detail,
        },
    )


def verify_apply(
    pre: VibeWorkflow,
    post: VibeWorkflow,
    *,
    delta: str | Sequence[EditOp] | None = None,
    landed_ops: Sequence[EditOp] = (),
    schema_provider: Any | None = None,
    name_hints: Mapping[str, str] | None = None,
    value_default_context: Any = None,
) -> ApplyGateResult:
    """Replay-verify ``post`` against ``pre`` + Δ and reject corrupt topology.

    ``landed_ops`` is the accepted batch (preferred Δ).  ``delta`` is used
    as the interpret source when ``landed_ops`` is empty but a batch
    source is still available.
    """
    if not isinstance(pre, VibeWorkflow) or not isinstance(post, VibeWorkflow):
        raise TypeError("verify_apply requires VibeWorkflow pre and post")

    try:
        pre_signature = editable_signature(pre)
    except _EditableIdentityError as exc:
        return _reject(
            "unverifiable_identity",
            (_editable_identity_diagnostic("pre", exc),),
        )
    try:
        post_signature = editable_signature(post)
    except _EditableIdentityError as exc:
        return _reject(
            "unverifiable_identity",
            (_editable_identity_diagnostic("post", exc),),
        )
    claimed_ops = tuple(landed_ops)
    diagnostics: list[CompactDiagnostic] = []
    admission_reason: str | None = None
    if claimed_ops:
        from vibecomfy.porting.edit.admit import (
            AdmissionRejected,
            admission_snapshot_for,
            admit_operations,
        )

        admitted = admit_operations(
            admission_snapshot_for(pre, schema_provider),
            claimed_ops,
            working_workflow=pre,
        )
        if isinstance(admitted, AdmissionRejected):
            admission_reason = admitted.typed_reason
            diagnostics.append(
                CompactDiagnostic(
                    code=admitted.typed_reason,
                    message=admitted.typed_reason,
                    severity="error",
                    detail={"evidence_refs": list(admitted.evidence_refs)},
                )
            )


    self_loop_diag = _new_self_loop_diagnostic(pre, post)
    if self_loop_diag is not None:
        diagnostics.append(self_loop_diag)
        return _reject("new_self_loop", diagnostics)

    orphan_diag = _orphaned_output_diagnostic(pre, post, claimed_ops)
    if orphan_diag is not None:
        diagnostics.append(orphan_diag)
        return _reject("orphaned_output", diagnostics)

    # A Python batch's source is the authoritative replay value. Its AddNodeOp
    # intentionally carries no schema-derived widget-channel classification
    # for unknown-schema nodes, so replaying only the typed op can re-channel
    # literals even though replaying the accepted source is faithful to the
    # post-IR. Typed-tool callers do not supply a source string and continue
    # to replay their canonical ops.
    #
    # Value-default binding is the exception: selected literals are sealed
    # onto the accepted AddNodeOp with an immutable marker. Replay that
    # retained proof rather than re-resolving from constructor context.
    from vibecomfy.porting.edit.value_defaults import VALUE_DEFAULT_FIELDS_MARKER

    has_retained_value_defaults = any(
        isinstance(getattr(operation, "fields", None), Mapping)
        and VALUE_DEFAULT_FIELDS_MARKER in operation.fields
        for operation in claimed_ops
    )
    replay_source: str | Sequence[EditOp] | None = (
        claimed_ops
        if has_retained_value_defaults
        else (delta if isinstance(delta, str) else (claimed_ops or delta))
    )
    claimed_edit = bool(claimed_ops) or bool(delta)

    if not claimed_edit:
        if admission_reason is not None:
            return _reject(admission_reason, diagnostics)
        return ApplyGateResult(ok=True, apply_eligible=False, reason="empty_delta")

    if pre_signature == post_signature:
        # A server replay can report ``no_op`` even though the caller supplied
        # an accepted operation.  Still run the exact accepted source through
        # the reconstruction diagnostic: this proves that the operation was
        # truly identity-preserving and catches any unclaimed scalar/topology
        # mutation injected into the staged post workflow.  The identity case
        # remains ineligible for application after that proof.
        _replay_reconstruct_diagnostic(
            pre,
            post,
            claimed_ops,
            schema_provider=schema_provider,
            name_hints=name_hints,
            value_default_context=value_default_context,
        )
        # The post state is already byte/canonical-identical to pre, so a
        # mismatch here describes the expected effect of the claimed op (a
        # typed server ``no_op``), not an unclaimed mutation in post.  Keep
        # the historical empty-delta disposition after exercising replay;
        # non-identity posts take the strict mismatch path below.
        if admission_reason is not None:
            return _reject(admission_reason, diagnostics)
        return ApplyGateResult(ok=True, apply_eligible=False, reason="empty_delta")


    from vibecomfy.porting.edit._diff import diff

    try:
        replay_delta = diff(pre, post, schema_provider=schema_provider)
    except RecursiveEditError as exc:
        diagnostics.append(_recursive_error_diagnostic(exc))
        return _reject(
            "unsupported_structural_scope"
            if exc.code == "unsupported_structural_scope"
            else "unverifiable_identity",
            diagnostics,
        )
    # ``diff`` deliberately projects some ambiguous list-shaped input values
    # out of its legacy link detector.  A non-empty claimed source/operation
    # is still an authoritative replay value; exact signature comparison
    # below proves whether it reconstructed the staged candidate.  Only fail
    # for an empty diff when there is no source to replay at all.
    if not replay_delta and replay_source is None:
        diagnostics.append(
            _diag(
                "apply_gate_empty_replay",
                "Apply gate refused success: interpret claimed an edit but "
                "diff(pre, post) is empty, so the product cannot be replayed.",
                severity="error",
                detail={"landed_op_count": len(claimed_ops)},
            )
        )
        return _reject("empty_replay", diagnostics)

    if replay_source is None:
        replay_source = replay_delta

    reconstruct_diag = _replay_reconstruct_diagnostic(
        pre,
        post,
        replay_source,
        schema_provider=schema_provider,
        name_hints=name_hints,
        value_default_context=value_default_context,
    )
    if reconstruct_diag is not None:
        diagnostics.append(reconstruct_diag)
        return _reject("replay_mismatch", diagnostics)

    if admission_reason is not None:
        return _reject(admission_reason, diagnostics)
    return ApplyGateResult(ok=True, apply_eligible=True)


def apply_eligible_for(result: ApplyGateResult) -> bool:
    """True only when the gate accepted a replay-verified, non-empty Δ."""
    return bool(result.ok and result.apply_eligible)


def apply_eligible_from_projection(projection: Any) -> bool:
    """Apply eligibility is a projection of gateway-verified accepted delta + replay.

    Consumes the one T2.2 ``TerminalProjection``. Audit/prose never authorize Apply.
    """
    if projection is None:
        return False
    eligibility = getattr(projection, "eligibility", None)
    if isinstance(eligibility, Mapping):
        return bool(eligibility.get("applyable")) and getattr(projection, "terminal_state", None) == "applied"
    return False


def _reject(reason: str, diagnostics: Sequence[CompactDiagnostic]) -> ApplyGateResult:
    return ApplyGateResult(
        ok=False,
        apply_eligible=False,
        diagnostics=tuple(diagnostics),
        reason=reason,
    )
def _editable_identity_diagnostic(
    graph: str,
    error: _EditableIdentityError,
) -> CompactDiagnostic:
    return _diag(
        "apply_gate_unverifiable_identity",
        "Apply gate refused success: the editable graph identity is missing, "
        "non-unique, or has an unresolvable edge endpoint; capture -> port "
        "through canonical Python -> reopen/reload.",
        severity="error",
        detail={
            "graph": graph,
            "identity_reason": error.reason,
            **error.detail,
        },
    )


def _replay_reconstruct_diagnostic(
    pre: VibeWorkflow,
    post: VibeWorkflow,
    replay_source: str | Sequence[EditOp],
    *,
    schema_provider: Any | None,
    name_hints: Mapping[str, str] | None,
    value_default_context: Any = None,
) -> CompactDiagnostic | None:
    from vibecomfy.porting.edit._interpret import interpret

    expected = editable_signature(post)
    replayed = interpret(
        pre,
        replay_source,
        schema_provider=schema_provider,
        name_hints=name_hints,
        value_default_context=value_default_context,
    )
    if not replayed.ok:
        replay_codes = tuple(
            str(getattr(item, "code", ""))
            for item in replayed.diagnostics
        )
        # A malformed retained topology (notably duplicate canonical edges)
        # can prevent the replay interpreter from producing a workflow at all.
        # The staged candidate is still comparable to the retained pre-state,
        # so report the stable replay-mismatch evidence rather than collapsing
        # this structural disagreement into generic replay failure.
        if any(
            code
            in {
                "full_ui_identity_malformed",
                "full_ui_link_added_unattributed",
                "full_ui_link_changed_unattributed",
                "full_ui_link_removed_unattributed",
            }
            for code in replay_codes
        ):
            try:
                actual = editable_signature(pre)
            except _EditableIdentityError as exc:
                return _editable_identity_diagnostic("replay", exc)
            return _replay_mismatch_diagnostic(
                expected,
                actual,
                replay_codes=replay_codes,
            )
        return _diag(
            "apply_gate_replay_failed",
            "Apply gate refused success: interpret(pre, Δ) failed while "
            "replaying the accepted batch.",
            severity="error",
            detail={
                "codes": tuple(
                    getattr(item, "code", "") for item in replayed.diagnostics
                ),
                "emit_path": "vibecomfy/porting/edit/_interpret.py:interpret",
            },
        )
    try:
        actual = editable_signature(replayed.workflow)
    except _EditableIdentityError as exc:
        return _editable_identity_diagnostic("replay", exc)
    if expected == actual:
        return None

    return _replay_mismatch_diagnostic(expected, actual)


def _replay_mismatch_diagnostic(
    expected: tuple[Any, ...],
    actual: tuple[Any, ...],
    *,
    replay_codes: Sequence[str] = (),
) -> CompactDiagnostic:
    """Describe exact staged-versus-replay quotient disagreement."""

    from collections import Counter

    expected_nodes, expected_edges, expected_interfaces, expected_recursive = expected
    actual_nodes, actual_edges, actual_interfaces, actual_recursive = actual
    expected_edge_counts = Counter(expected_edges)
    actual_edge_counts = Counter(actual_edges)
    return _diag(
        "apply_gate_replay_mismatch",
        "Apply gate refused success: interpret(pre, Δ) did not reconstruct post.",
        severity="error",
        detail={
            "node_uid_delta": {
                "only_in_post": tuple(sorted(set(expected_nodes) - set(actual_nodes))),
                "only_in_replay": tuple(sorted(set(actual_nodes) - set(expected_nodes))),
            },
            "edge_delta": {
                "only_in_post": tuple(
                    sorted((expected_edge_counts - actual_edge_counts).elements())
                ),
                "only_in_replay": tuple(
                    sorted((actual_edge_counts - expected_edge_counts).elements())
                ),
            },
            "subgraph_interface_delta": {
                "only_in_post": tuple(
                    item for item in expected_interfaces if item not in actual_interfaces
                ),
                "only_in_replay": tuple(
                    item for item in actual_interfaces if item not in expected_interfaces
                ),
            },
            "recursive_delta": {
                "only_in_post": tuple(
                    item for item in expected_recursive if item not in actual_recursive
                ),
                "only_in_replay": tuple(
                    item for item in actual_recursive if item not in expected_recursive
                ),
            },
            "replay_codes": tuple(replay_codes),
            "emit_path": "vibecomfy/porting/emit/ui.py:emit_ui_json",
        },
    )
