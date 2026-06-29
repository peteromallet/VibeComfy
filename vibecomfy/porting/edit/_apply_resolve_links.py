from __future__ import annotations

from typing import Any

from ._apply_common import _endpoint_port_issues, _issue, _ctx
from ._apply_types import ResolvedLinkEndpoint, ResolvedOp, ResolvedRemoveLinkRef
from .ledger import EditLedger
from .ops import LinkTargetRef, NodeTarget, RemoveLinkOp, UpsertLinkOp
from vibecomfy.porting.report import PortIssue
from vibecomfy.porting.resolution import EditLedgerBackend, _find_named_slot
from vibecomfy.schema import socket_types_compatible


def _resolve_upsert_link(
    ledger: EditLedger,
    op: UpsertLinkOp,
    *,
    schema_provider: Any,
) -> tuple[ResolvedOp | None, list[PortIssue]]:
    if op.source.scope_path != op.target.scope_path:
        return None, [
            _issue(
                "cross_scope_link_unsupported",
                "Link endpoints must resolve within the same scope.",
                detail={
                    "from_scope_path": op.source.scope_path,
                    "to_scope_path": op.target.scope_path,
                },
            )
        ]
    source, source_issues = _resolve_source_endpoint(ledger, op.source, schema_provider=schema_provider)
    if source_issues:
        return None, source_issues
    target, target_issues = _resolve_target_endpoint(ledger, op.target, schema_provider=schema_provider)
    if target_issues:
        return None, target_issues
    assert source is not None and target is not None
    if not isinstance(source.node_id, int) or not isinstance(target.node_id, int):
        return None, [
            _issue(
                "non_numeric_link_endpoint",
                "Link endpoints must have numeric LiteGraph node ids.",
                detail={
                    "from_scope_path": op.source.scope_path,
                    "from_uid": op.source.uid,
                    "from_node_id": source.node_id,
                    "to_scope_path": op.target.scope_path,
                    "to_uid": op.target.uid,
                    "to_node_id": target.node_id,
                },
            )
        ]
    if source.socket_type and target.socket_type and not socket_types_compatible(source.socket_type, target.socket_type):
        return None, [
            _issue(
                "incompatible_socket_types",
                f"Cannot connect {source.class_type}.{source.slot_name} ({source.socket_type}) to "
                f"{target.class_type}.{target.slot_name} ({target.socket_type}).",
                detail={
                    "from_scope_path": op.source.scope_path,
                    "from_uid": op.source.uid,
                    "from_slot": source.slot_name,
                    "from_type": source.socket_type,
                    "to_scope_path": op.target.scope_path,
                    "to_uid": op.target.uid,
                    "to_input": target.slot_name,
                    "to_type": target.socket_type,
                },
            )
        ]
    return (source, target), []


def _resolve_remove_link(
    ledger: EditLedger,
    op: RemoveLinkOp,
) -> tuple[ResolvedOp | None, list[PortIssue]]:
    from ._apply_resolve import _resolve_node

    if op.link_id is not None:
        matches = [
            ResolvedRemoveLinkRef(scope_path=scope_path, link_id=link_id, link=link)
            for (scope_path, link_id), link in ledger.link_index.items()
            if link_id == op.link_id
        ]
        if not matches:
            return None, [
                _issue(
                    "unknown_link_id",
                    f"Unknown link id {op.link_id}.",
                    detail={"link_id": op.link_id},
                )
            ]
        if len(matches) > 1:
            return None, [
                _issue(
                    "ambiguous_link_id",
                    f"Link id {op.link_id} exists in multiple scopes.",
                    detail={"link_id": op.link_id, "scope_paths": [item.scope_path for item in matches]},
                )
            ]
        return matches[0], []

    assert op.target is not None
    node_ref, issues = _resolve_node(ledger, NodeTarget(op.target.scope_path, op.target.uid))
    if issues:
        return None, issues
    assert node_ref is not None
    return _resolve_remove_link_target(ledger, node_ref.node, node_ref.class_type, op.target)


def _resolve_remove_link_target(
    ledger: EditLedger,
    node: Any,
    class_type: str,
    target: LinkTargetRef,
) -> tuple[ResolvedRemoveLinkRef | None, list[PortIssue]]:
    raw_input = _find_named_slot(node.get("inputs"), target.input_field)
    if raw_input is None:
        return None, [
            _issue(
                "unknown_link_target_input",
                f"{class_type} does not expose input {target.input_field!r}.",
                detail={
                    "scope_path": target.scope_path,
                    "uid": target.uid,
                    "input": target.input_field,
                },
            )
        ]
    link_id = raw_input.get("link")
    if not isinstance(link_id, int):
        return None, [
            _issue(
                "missing_link_to_remove",
                f"{class_type}.{target.input_field} has no incoming link to remove.",
                detail={
                    "scope_path": target.scope_path,
                    "uid": target.uid,
                    "input": target.input_field,
                },
            )
        ]
    link = ledger.resolve_link(target.scope_path, link_id)
    if link is None:
        return None, [
            _issue(
                "dangling_link_reference",
                f"Input {target.input_field!r} references missing link id {link_id}.",
                detail={"scope_path": target.scope_path, "link_id": link_id},
            )
        ]
    return ResolvedRemoveLinkRef(scope_path=target.scope_path, link_id=link_id, link=link), []


def _resolve_source_endpoint(
    ledger: EditLedger,
    ref: Any,
    *,
    schema_provider: Any,
) -> tuple[ResolvedLinkEndpoint | None, list[PortIssue]]:
    from ._apply_widgets import _schema_output_type

    backend = EditLedgerBackend(ledger)
    result = _ctx.resolve_source_endpoint(backend, ref, schema_provider=schema_provider)
    if result.value is None:
        return None, _endpoint_port_issues(result)
    ep = result.value
    socket_type = ep.socket_type
    if socket_type is None:
        socket_type = _schema_output_type(schema_provider, ep.class_type, ep.slot_index, ep.slot_name)
    return (
        ResolvedLinkEndpoint(
            ref=ref,
            node=ep.node,
            class_type=ep.class_type,
            node_id=ep.node_id,
            slot_index=ep.slot_index,
            slot_name=ep.slot_name,
            socket_type=socket_type,
        ),
        [],
    )


def _resolve_target_endpoint(
    ledger: EditLedger,
    ref: Any,
    *,
    schema_provider: Any,
) -> tuple[ResolvedLinkEndpoint | None, list[PortIssue]]:
    backend = EditLedgerBackend(ledger)
    result = _ctx.resolve_target_endpoint(backend, ref, schema_provider=schema_provider)
    if result.value is None:
        return None, _endpoint_port_issues(result)
    ep = result.value
    return (
        ResolvedLinkEndpoint(
            ref=ref,
            node=ep.node,
            class_type=ep.class_type,
            node_id=ep.node_id,
            slot_index=ep.slot_index,
            slot_name=ep.slot_name,
            socket_type=ep.socket_type,
        ),
        [],
    )
