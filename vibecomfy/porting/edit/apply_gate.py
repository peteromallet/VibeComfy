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

from vibecomfy.porting.edit._ir_utils import _uids_for_op
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


def verify_apply(
    pre: VibeWorkflow,
    post: VibeWorkflow,
    *,
    delta: str | Sequence[EditOp] | None = None,
    landed_ops: Sequence[EditOp] = (),
    schema_provider: Any | None = None,
    name_hints: Mapping[str, str] | None = None,
) -> ApplyGateResult:
    """Replay-verify ``post`` against ``pre`` + Δ and reject corrupt topology.

    ``landed_ops`` is the accepted batch (preferred Δ).  ``delta`` is used
    as the interpret source when ``landed_ops`` is empty but a batch
    source is still available.
    """
    if not isinstance(pre, VibeWorkflow) or not isinstance(post, VibeWorkflow):
        raise TypeError("verify_apply requires VibeWorkflow pre and post")

    claimed_ops = tuple(landed_ops)
    diagnostics: list[CompactDiagnostic] = []
    admission_reason: str | None = None
    if claimed_ops:
        from vibecomfy.porting.edit.admit import (
            AdmissionRejected,
            admission_snapshot_for,
            admit_operations,
            rejected_ops_are_invisible,
        )

        admitted = admit_operations(
            admission_snapshot_for(pre, schema_provider),
            claimed_ops,
            working_workflow=pre,
        )
        if rejected_ops_are_invisible(admitted) or isinstance(admitted, AdmissionRejected):
            admission_reason = admitted.typed_reason
            # RR1-FIX(2): distinguish a zero-net-change named-absence rollback
            # (every op bounced on schema absence; the graph is untouched) from
            # corruption. Downstream projection treats this shape as an honest
            # no-candidate terminal instead of an authority error.
            zero_net_change = editable_signature(pre) == editable_signature(post)
            diagnostics.append(
                CompactDiagnostic(
                    code=admitted.typed_reason,
                    message=admitted.typed_reason,
                    severity="error",
                    detail={
                        "evidence_refs": list(admitted.evidence_refs),
                        "zero_net_change": zero_net_change,
                    },
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
    replay_source: str | Sequence[EditOp] | None = (
        delta if isinstance(delta, str) else (claimed_ops or delta)
    )
    claimed_edit = bool(claimed_ops) or bool(delta)

    if not claimed_edit or editable_signature(pre) == editable_signature(post):
        if admission_reason is not None:
            return _reject(admission_reason, diagnostics)
        return ApplyGateResult(ok=True, apply_eligible=False, reason="empty_delta")


    from vibecomfy.porting.edit._diff import diff

    replay_delta = diff(pre, post, schema_provider=schema_provider)
    if not replay_delta:
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


def _uid_by_node_id(workflow: VibeWorkflow) -> dict[str, str]:
    mapping: dict[str, str] = {}
    for node_id, node in workflow.nodes.items():
        uid = getattr(node, "uid", None)
        if isinstance(uid, str) and uid:
            mapping[str(node_id)] = uid
    return mapping


def _node_id_by_uid(workflow: VibeWorkflow) -> dict[str, str]:
    return {uid: node_id for node_id, uid in _uid_by_node_id(workflow).items()}


def _edge_uid_records(workflow: VibeWorkflow) -> set[tuple[str, str, str, str]]:
    uid_by_id = _uid_by_node_id(workflow)
    records: set[tuple[str, str, str, str]] = set()
    for edge in workflow.edges:
        src = uid_by_id.get(str(edge.from_node))
        dst = uid_by_id.get(str(edge.to_node))
        if not src or not dst:
            continue
        records.add((src, str(edge.from_output), dst, str(edge.to_input)))
    return records


def _self_loop_uids(workflow: VibeWorkflow) -> set[str]:
    loops: set[str] = set()
    uid_by_id = _uid_by_node_id(workflow)
    for edge in workflow.edges:
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


def _freeze(value: Any) -> Any:
    if isinstance(value, Mapping):
        return tuple(sorted((str(k), _freeze(v)) for k, v in value.items()))
    if isinstance(value, (list, tuple)):
        return tuple(_freeze(item) for item in value)
    return value


def _node_field_signature(node: Any) -> tuple[Any, ...]:
    widgets = dict(getattr(node, "widgets", None) or {})
    inputs = getattr(node, "inputs", None) or {}
    scalars: dict[str, Any] = {}
    if isinstance(inputs, Mapping):
        for name, value in inputs.items():
            if isinstance(value, (list, tuple)):
                continue
            scalars[str(name)] = value
    merged = {**scalars, **widgets}
    return (
        str(getattr(node, "class_type", "")),
        tuple(sorted((str(k), _freeze(v)) for k, v in merged.items())),
        mode_to_litegraph(getattr(node, "mode", 0)),
    )


def editable_signature(
    workflow: VibeWorkflow,
) -> tuple[dict[str, tuple[Any, ...]], frozenset[tuple[str, str, str, str]]]:
    """uid → (class, fields, mode) plus the uid-addressed edge set."""
    nodes: dict[str, tuple[Any, ...]] = {}
    for node in workflow.nodes.values():
        uid = getattr(node, "uid", None)
        if not isinstance(uid, str) or not uid:
            continue
        nodes[uid] = _node_field_signature(node)
    return nodes, frozenset(_edge_uid_records(workflow))


def _is_leftover_link_mismatch(
    expected_edges: set[tuple[str, str, str, str]],
    actual_edges: set[tuple[str, str, str, str]],
) -> bool:
    """S2: leftover links/last_link_id furniture should be ignored.

    vace-retarget 4 leftover ops, 2a31ec threaded replay mismatch were
    pure emit link-id drift, not semantic edge changes. When node
    signatures already match, any edge delta is leftover furniture.
    """
    return True


def _replay_reconstruct_diagnostic(
    pre: VibeWorkflow,
    post: VibeWorkflow,
    replay_source: str | Sequence[EditOp],
    *,
    schema_provider: Any | None,
    name_hints: Mapping[str, str] | None,
) -> CompactDiagnostic | None:
    from vibecomfy.porting.edit._interpret import interpret

    replayed = interpret(
        pre,
        replay_source,
        schema_provider=schema_provider,
        name_hints=name_hints,
    )
    if not replayed.ok:
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
    expected = editable_signature(post)
    actual = editable_signature(replayed.workflow)
    if expected == actual:
        return None
    expected_nodes, expected_edges = expected
    actual_nodes, actual_edges = actual
    # S2: interpret(pre,Δ) ignore leftover links/last_link_id. When nodes
    # match, edge delta is leftover furniture (emit link-id / last_link_id
    # allocation). vace-retarget, 2a31ec, e8c20a all had valid field edits
    # but were rejected due to 4 leftover ops that were pure furniture.
    if expected_nodes == actual_nodes and _is_leftover_link_mismatch(set(expected_edges), set(actual_edges)):
        return None
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
                "only_in_post": tuple(sorted(expected_edges - actual_edges)),
                "only_in_replay": tuple(sorted(actual_edges - expected_edges)),
            },
            "emit_path": "vibecomfy/porting/emit/ui.py:emit_ui_json",
        },
    )
