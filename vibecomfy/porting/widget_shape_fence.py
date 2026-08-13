"""Deterministic widget-shape verdicts for UI emission.

This module is intentionally pure policy: callers provide all evidence gathered
from the IR, raw LiteGraph payloads, layout preservation, and edit deltas.  The
fence decides whether a node may regenerate widgets, must preserve the raw node
opaque, or must refuse emission.
"""
from __future__ import annotations

from dataclasses import dataclass, field
from enum import Enum
from typing import Any, Mapping

from vibecomfy.porting.emit.ui import WidgetShapeEvidence

_LOW_CONFIDENCE_THRESHOLD = 0.3
_WIDGET_FIELD_PREFIX = "widget_"
_WIDGET_FIELDS = frozenset({"widgets", "widgets_values", "raw_widgets", "_raw_widgets"})


class WidgetShapeDecision(str, Enum):
    SAFE_TO_REGENERATE = "safe_to_regenerate"
    PIN_OPAQUE = "pin_opaque"
    REFUSE = "refuse"


class WidgetShapeReason(str, Enum):
    SCHEMA_BACKED_STATIC = "schema_backed_static"
    OVERFLOW = "overflow"
    SCHEMA_LESS = "schema_less"
    LOW_CONFIDENCE_SCHEMA = "low_confidence_schema"
    DICT_ROW_DYNAMIC_WIDGETS = "dict_row_dynamic_widgets"
    MISSING_RAW_UI_PAYLOAD = "no_prior_ui_payload"
    MISSING_RAW_WIDGET_PAYLOAD = "missing_raw_widget_payload"
    MISSING_LAYOUT_ENTRY = "missing_layout_entry"
    WIDGET_DELTA = "widget_delta"
    LINK_DELTA = "link_delta"


@dataclass(frozen=True, slots=True)
class WidgetShapeVerdict:
    node_id: str
    class_type: str
    decision: WidgetShapeDecision
    reasons: tuple[WidgetShapeReason, ...]
    safe_to_regenerate: bool
    pin_opaque: bool
    refuse: bool
    evidence: WidgetShapeEvidence
    raw_ui_node: Mapping[str, Any] | None = None
    layout_entry: Mapping[str, Any] | None = None
    field_delta: Mapping[str, Any] = field(default_factory=dict)
    link_delta: Mapping[str, Any] = field(default_factory=dict)
    recovery: str | None = None
    use_schema_defaults: bool = False


def decide_widget_shape(
    evidence: WidgetShapeEvidence,
    *,
    raw_widget_payloads: Mapping[str, Any] | None = None,
    raw_payloads: Mapping[str, Mapping[str, Any]] | None = None,
    layout_entries: Mapping[str, Mapping[str, Any]] | None = None,
    field_deltas: Mapping[str, Mapping[str, Any]] | None = None,
    link_deltas: Mapping[str, Mapping[str, Any]] | None = None,
    identity_matched: bool = False,
    allow_schema_default_regenerate: bool = False,
    is_new_node: bool = False,
) -> WidgetShapeVerdict:
    """Classify one node's widget-shape handling.

    ``raw_payloads`` must contain the full raw LiteGraph node dict for a pin.
    ``raw_widget_payloads`` must contain the preserved widget evidence.  Layout,
    field, and link deltas are explicit inputs so the trust boundary is visible:
    dynamic nodes only pin when their raw UI payload is complete and unchanged.
    """
    node_id = str(evidence.node_id)
    raw_widget_payload = _lookup(raw_widget_payloads, node_id)
    raw_ui_node = _lookup(raw_payloads, node_id)
    layout_entry = _lookup(layout_entries, node_id)
    field_delta = dict(_lookup(field_deltas, node_id) or {})
    link_delta = dict(_lookup(link_deltas, node_id) or {})
    has_widget_delta = _has_widget_delta(field_delta)
    has_link_delta = _has_link_delta(link_delta)

    static_reasons = _static_refusal_reasons(evidence)

    # Collateral nodes (no widget delta, no link delta) with a complete
    # raw LiteGraph node dict can carry the payload forward even when
    # they have dynamic / overflow widget-shape problems.  Edited or
    # touched nodes (any delta) fall through to the stricter refusal
    # gates below.
    if (
        raw_ui_node is not None
        and _has_full_raw_ui_payload(raw_ui_node)
        and not has_widget_delta
        and not has_link_delta
    ):
        carry_reasons = static_reasons or (WidgetShapeReason.SCHEMA_BACKED_STATIC,)
        return _verdict(
            evidence,
            WidgetShapeDecision.PIN_OPAQUE,
            carry_reasons,
            raw_ui_node=raw_ui_node,
            layout_entry=layout_entry,
            field_delta=field_delta,
            link_delta=link_delta,
            recovery="carry_forward_raw_ui",
        )

    malformed_new_raw_ui = (
        is_new_node
        and raw_ui_node is not None
        and not _has_full_raw_ui_payload(raw_ui_node)
        # A new node with a partial ``_ui`` stub (inputs/outputs stripped at
        # ingest) is only "malformed" if it actually has a widget-shape problem
        # (``static_reasons``) or no regenerable widget payload. When the widget
        # shape is clean, regeneration rebuilds ``widgets_values`` from the IR,
        # so the partial stub is irrelevant — fall through to regenerate/emit.
        and (
            static_reasons
            or not _has_raw_widget_payload(raw_widget_payload, evidence)
        )
    )
    if malformed_new_raw_ui:
        refuse_reasons = list(static_reasons)
        refuse_reasons.append(WidgetShapeReason.MISSING_RAW_UI_PAYLOAD)
        if not _has_raw_widget_payload(raw_widget_payload, evidence):
            refuse_reasons.append(WidgetShapeReason.MISSING_RAW_WIDGET_PAYLOAD)
        if layout_entry is None:
            refuse_reasons.append(WidgetShapeReason.MISSING_LAYOUT_ENTRY)
        if has_widget_delta:
            refuse_reasons.append(WidgetShapeReason.WIDGET_DELTA)
        if has_link_delta:
            refuse_reasons.append(WidgetShapeReason.LINK_DELTA)
        return _verdict(
            evidence,
            WidgetShapeDecision.REFUSE,
            tuple(refuse_reasons),
            raw_ui_node=raw_ui_node,
            layout_entry=layout_entry,
            field_delta=field_delta,
            link_delta=link_delta,
        )

    benign_schema_default_overflow = (
        allow_schema_default_regenerate
        and not has_widget_delta
        and not has_link_delta
        and _schema_default_safe_static_reasons(static_reasons)
    )
    if benign_schema_default_overflow:
        return _verdict(
            evidence,
            WidgetShapeDecision.SAFE_TO_REGENERATE,
            (WidgetShapeReason.SCHEMA_BACKED_STATIC,),
            raw_ui_node=raw_ui_node,
            layout_entry=layout_entry,
            field_delta=field_delta,
            link_delta=link_delta,
            recovery="schema_default_regenerate",
            use_schema_defaults=True,
        )

    if _observed_static_overflow_recoverable(
        evidence,
        raw_widget_payload=raw_widget_payload,
        raw_ui_node=raw_ui_node,
        has_link_delta=has_link_delta,
        is_new_node=is_new_node,
    ):
        return _verdict(
            evidence,
            WidgetShapeDecision.SAFE_TO_REGENERATE,
            (WidgetShapeReason.OVERFLOW,),
            raw_ui_node=raw_ui_node,
            layout_entry=layout_entry,
            field_delta=field_delta,
            link_delta=link_delta,
            recovery="observed_widget_shape_regenerate",
        )

    if _observed_dynamic_widgets_recoverable(
        evidence,
        raw_widget_payload=raw_widget_payload,
        raw_ui_node=raw_ui_node,
        has_widget_delta=has_widget_delta,
        has_link_delta=has_link_delta,
        is_new_node=is_new_node,
    ):
        return _verdict(
            evidence,
            WidgetShapeDecision.SAFE_TO_REGENERATE,
            (WidgetShapeReason.DICT_ROW_DYNAMIC_WIDGETS,),
            raw_ui_node=raw_ui_node,
            layout_entry=layout_entry,
            field_delta=field_delta,
            link_delta=link_delta,
            recovery="observed_dynamic_widgets_regenerate",
        )

    if evidence.explicit_widget_overflow:
        refuse_reasons = list(static_reasons)
        if not static_reasons and evidence.explicit_widget_overflow:
            refuse_reasons.append(WidgetShapeReason.OVERFLOW)
        if not _has_full_raw_ui_payload(raw_ui_node):
            refuse_reasons.append(WidgetShapeReason.MISSING_RAW_UI_PAYLOAD)
        if not _has_raw_widget_payload(raw_widget_payload, evidence):
            refuse_reasons.append(WidgetShapeReason.MISSING_RAW_WIDGET_PAYLOAD)
        if layout_entry is None:
            refuse_reasons.append(WidgetShapeReason.MISSING_LAYOUT_ENTRY)
        if has_widget_delta:
            refuse_reasons.append(WidgetShapeReason.WIDGET_DELTA)
        if has_link_delta:
            refuse_reasons.append(WidgetShapeReason.LINK_DELTA)
        return _verdict(
            evidence,
            WidgetShapeDecision.REFUSE,
            tuple(refuse_reasons),
            raw_ui_node=raw_ui_node,
            layout_entry=layout_entry,
            field_delta=field_delta,
            link_delta=link_delta,
        )

    if not static_reasons:
        recovery = "schema_default_regenerate" if allow_schema_default_regenerate else None
        return _verdict(
            evidence,
            WidgetShapeDecision.SAFE_TO_REGENERATE,
            (WidgetShapeReason.SCHEMA_BACKED_STATIC,),
            raw_ui_node=raw_ui_node,
            layout_entry=layout_entry,
            field_delta=field_delta,
            link_delta=link_delta,
            recovery=recovery,
            use_schema_defaults=allow_schema_default_regenerate,
        )

    pin_blockers = list(static_reasons)
    if not _has_full_raw_ui_payload(raw_ui_node):
        pin_blockers.append(WidgetShapeReason.MISSING_RAW_UI_PAYLOAD)
    if not _has_raw_widget_payload(raw_widget_payload, evidence):
        pin_blockers.append(WidgetShapeReason.MISSING_RAW_WIDGET_PAYLOAD)
    if layout_entry is None:
        pin_blockers.append(WidgetShapeReason.MISSING_LAYOUT_ENTRY)
    if has_widget_delta:
        pin_blockers.append(WidgetShapeReason.WIDGET_DELTA)
    if has_link_delta:
        pin_blockers.append(WidgetShapeReason.LINK_DELTA)

    if len(pin_blockers) == len(static_reasons):
        return _verdict(
            evidence,
            WidgetShapeDecision.PIN_OPAQUE,
            tuple(pin_blockers),
            raw_ui_node=raw_ui_node,
            layout_entry=layout_entry,
            field_delta=field_delta,
            link_delta=link_delta,
        )

    return _verdict(
        evidence,
        WidgetShapeDecision.REFUSE,
        tuple(pin_blockers),
        raw_ui_node=raw_ui_node,
        layout_entry=layout_entry,
        field_delta=field_delta,
        link_delta=link_delta,
    )


def _lookup(mapping: Mapping[str, Any] | None, node_id: str) -> Any:
    if not mapping:
        return None
    if node_id in mapping:
        return mapping[node_id]
    if node_id.isdigit():
        return mapping.get(str(int(node_id)))
    return None


def _static_refusal_reasons(evidence: WidgetShapeEvidence) -> tuple[WidgetShapeReason, ...]:
    reasons: list[WidgetShapeReason] = []
    has_dynamic_widget_evidence = evidence.overflow or evidence.has_dict_rows
    if evidence.overflow:
        reasons.append(WidgetShapeReason.OVERFLOW)
    if evidence.schema_less and has_dynamic_widget_evidence:
        reasons.append(WidgetShapeReason.SCHEMA_LESS)
    confidence = evidence.confidence
    if (
        confidence is not None
        and confidence <= _LOW_CONFIDENCE_THRESHOLD
        and has_dynamic_widget_evidence
    ):
        reasons.append(WidgetShapeReason.LOW_CONFIDENCE_SCHEMA)
    if evidence.has_dict_rows:
        reasons.append(WidgetShapeReason.DICT_ROW_DYNAMIC_WIDGETS)
    return tuple(reasons)


def _schema_default_safe_static_reasons(
    reasons: tuple[WidgetShapeReason, ...],
) -> bool:
    return not reasons or set(reasons) == {WidgetShapeReason.OVERFLOW}


def _observed_static_overflow_recoverable(
    evidence: WidgetShapeEvidence,
    *,
    raw_widget_payload: Any,
    raw_ui_node: Mapping[str, Any] | None,
    has_link_delta: bool,
    is_new_node: bool,
) -> bool:
    """Allow existing static nodes to preserve observed opaque widget slots.

    This is deliberately narrower than pinning: dynamic dict-row widgets still
    require full raw UI payloads, and new nodes cannot use observed-shape
    recovery because there is no prior serialized widget vector to preserve.
    """
    if is_new_node or has_link_delta:
        return False
    if _has_full_raw_ui_payload(raw_ui_node):
        return False
    if not evidence.overflow or evidence.explicit_widget_overflow:
        return False
    if evidence.has_dict_rows or evidence.schema_less:
        return False
    if evidence.raw_widget_count is None:
        return False
    if int(evidence.raw_widget_count) != int(evidence.candidate_widget_count):
        return False
    if not _has_raw_widget_payload(raw_widget_payload, evidence):
        return False
    return True


def _observed_dynamic_widgets_recoverable(
    evidence: WidgetShapeEvidence,
    *,
    raw_widget_payload: Any,
    raw_ui_node: Mapping[str, Any] | None,
    has_widget_delta: bool,
    has_link_delta: bool,
    is_new_node: bool,
) -> bool:
    if is_new_node or has_widget_delta or has_link_delta:
        return False
    if _has_full_raw_ui_payload(raw_ui_node):
        return False
    if not evidence.has_dict_rows or evidence.overflow or evidence.schema_less:
        return False
    if evidence.raw_widget_count is None:
        return False
    if int(evidence.raw_widget_count) != int(evidence.candidate_widget_count):
        return False
    if (
        evidence.schema_widget_count is not None
        and int(evidence.schema_widget_count) != int(evidence.candidate_widget_count)
    ):
        return False
    if not _has_raw_widget_payload(raw_widget_payload, evidence):
        return False
    return True


def _has_full_raw_ui_payload(raw_ui_node: Mapping[str, Any] | None) -> bool:
    return bool(
        raw_ui_node
        and "id" in raw_ui_node
        and raw_ui_node.get("type") is not None
        and raw_ui_node.get("widgets_values") is not None
    )


def _has_raw_widget_payload(raw_widget_payload: Any, evidence: WidgetShapeEvidence) -> bool:
    if raw_widget_payload is None:
        return False
    length = getattr(raw_widget_payload, "length", None)
    if length is None and isinstance(raw_widget_payload, Mapping):
        length = raw_widget_payload.get("length")
    if length is None:
        return True
    return evidence.raw_widget_count is None or int(length) == int(evidence.raw_widget_count)


def _has_widget_delta(field_delta: Mapping[str, Any]) -> bool:
    return any(
        field in _WIDGET_FIELDS or str(field).startswith(_WIDGET_FIELD_PREFIX)
        for field in field_delta
    )


def _has_link_delta(link_delta: Mapping[str, Any]) -> bool:
    """Interpret the canonical semantic-set comparison supplied by the emitter.

    The fallback preserves compatibility for direct policy callers that still
    provide an opaque link-delta mapping. Resolution issues always fail closed,
    even when the successfully resolved portions of the two sets are equal.
    """
    semantic = link_delta.get("semantic_link_set")
    if not isinstance(semantic, Mapping):
        return bool(link_delta)
    return bool(
        semantic.get("before") != semantic.get("after")
        or semantic.get("before_resolution_issues")
        or semantic.get("after_resolution_issues")
    )


def _verdict(
    evidence: WidgetShapeEvidence,
    decision: WidgetShapeDecision,
    reasons: tuple[WidgetShapeReason, ...],
    *,
    raw_ui_node: Mapping[str, Any] | None,
    layout_entry: Mapping[str, Any] | None,
    field_delta: Mapping[str, Any],
    link_delta: Mapping[str, Any],
    recovery: str | None = None,
    use_schema_defaults: bool = False,
) -> WidgetShapeVerdict:
    return WidgetShapeVerdict(
        node_id=str(evidence.node_id),
        class_type=str(evidence.class_type),
        decision=decision,
        reasons=reasons,
        safe_to_regenerate=decision is WidgetShapeDecision.SAFE_TO_REGENERATE,
        pin_opaque=decision is WidgetShapeDecision.PIN_OPAQUE,
        refuse=decision is WidgetShapeDecision.REFUSE,
        evidence=evidence,
        raw_ui_node=raw_ui_node,
        layout_entry=layout_entry,
        field_delta=field_delta,
        link_delta=link_delta,
        recovery=recovery,
        use_schema_defaults=use_schema_defaults,
    )


__all__ = [
    "WidgetShapeDecision",
    "WidgetShapeReason",
    "WidgetShapeVerdict",
    "decide_widget_shape",
]
