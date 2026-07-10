from __future__ import annotations

from typing import Any

from vibecomfy.porting.layout_store import store_from_ui_json
from vibecomfy.porting.emit.ui import WidgetShapeEvidence, extract_raw_ui_node_map
from vibecomfy.porting.widget_shape_fence import (
    WidgetShapeDecision,
    WidgetShapeReason,
    WidgetShapeVerdict,
    decide_widget_shape,
)
from vibecomfy.workflow import RawWidgetPayload


def _evidence(**overrides: Any) -> WidgetShapeEvidence:
    values = {
        "node_id": "7",
        "class_type": "DynamicRows",
        "schema_less": False,
        "confidence": 1.0,
        "raw_widget_count": 2,
        "candidate_widget_count": 2,
        "schema_widget_count": 2,
        "compacted_widget_names": ("a", "b"),
        "raw_widget_shape": "list",
        "has_dict_rows": False,
        "overflow": False,
        "provider": "test_provider",
        "explicit_widget_overflow": False,
        "raw_widget_length_recovered": False,
    }
    values.update(overrides)
    return WidgetShapeEvidence(**values)


def _raw_widgets(length: int = 2) -> RawWidgetPayload:
    return RawWidgetPayload(
        values=["x", "y"][:length],
        shape="list",
        source="ui.widgets_values",
        has_dict_rows=False,
        length=length,
    )


def _raw_node() -> dict[str, Any]:
    return {
        "id": 7,
        "type": "DynamicRows",
        "pos": [10, 20],
        "size": [300, 120],
        "widgets_values": [{"row": 1}, {"row": 2}],
    }


def _layout() -> dict[str, Any]:
    return {"pos": [10, 20], "size": [300, 120]}


def test_schema_backed_confident_non_overflow_node_is_safe_to_regenerate() -> None:
    verdict = decide_widget_shape(_evidence())

    assert isinstance(verdict, WidgetShapeVerdict)
    assert verdict.decision is WidgetShapeDecision.SAFE_TO_REGENERATE
    assert verdict.safe_to_regenerate is True
    assert verdict.pin_opaque is False
    assert verdict.refuse is False
    assert verdict.reasons == (WidgetShapeReason.SCHEMA_BACKED_STATIC,)


def test_overflow_with_unchanged_full_raw_payload_pins_opaque() -> None:
    evidence = _evidence(
        overflow=True,
        raw_widget_count=3,
        candidate_widget_count=3,
        schema_widget_count=2,
    )

    verdict = decide_widget_shape(
        evidence,
        raw_widget_payloads={"7": _raw_widgets(length=3)},
        raw_payloads={"7": _raw_node()},
        layout_entries={"7": _layout()},
    )

    assert verdict.decision is WidgetShapeDecision.PIN_OPAQUE
    assert verdict.pin_opaque is True
    assert verdict.refuse is False
    assert WidgetShapeReason.OVERFLOW in verdict.reasons


def test_overflow_without_raw_payload_refuses() -> None:
    evidence = _evidence(
        overflow=True,
        raw_widget_count=None,
        candidate_widget_count=3,
        schema_widget_count=2,
    )

    verdict = decide_widget_shape(
        evidence,
        raw_widget_payloads={},
        raw_payloads={},
        layout_entries={},
    )

    assert verdict.decision is WidgetShapeDecision.REFUSE
    assert WidgetShapeReason.OVERFLOW in verdict.reasons
    assert WidgetShapeReason.MISSING_RAW_UI_PAYLOAD in verdict.reasons
    assert WidgetShapeReason.MISSING_RAW_WIDGET_PAYLOAD in verdict.reasons
    assert WidgetShapeReason.MISSING_LAYOUT_ENTRY in verdict.reasons


def test_static_overflow_matching_observed_widgets_recovers_by_regeneration() -> None:
    evidence = _evidence(
        overflow=True,
        raw_widget_count=3,
        candidate_widget_count=3,
        schema_widget_count=2,
    )

    verdict = decide_widget_shape(
        evidence,
        raw_widget_payloads={"7": _raw_widgets(length=3)},
        field_deltas={"7": {"widgets_values": ("old", "new")}},
    )

    assert verdict.decision is WidgetShapeDecision.SAFE_TO_REGENERATE
    assert verdict.recovery == "observed_widget_shape_regenerate"
    assert WidgetShapeReason.OVERFLOW in verdict.reasons


def test_static_overflow_observed_shape_recovery_refuses_link_changes() -> None:
    evidence = _evidence(
        overflow=True,
        raw_widget_count=3,
        candidate_widget_count=3,
        schema_widget_count=2,
    )

    verdict = decide_widget_shape(
        evidence,
        raw_widget_payloads={"7": _raw_widgets(length=3)},
        link_deltas={"7": {"incoming_edge_sig": ("old", "new")}},
    )

    assert verdict.decision is WidgetShapeDecision.REFUSE
    assert WidgetShapeReason.LINK_DELTA in verdict.reasons


def test_static_overflow_observed_shape_recovery_does_not_apply_to_new_nodes() -> None:
    evidence = _evidence(
        overflow=True,
        raw_widget_count=3,
        candidate_widget_count=3,
        schema_widget_count=2,
    )

    verdict = decide_widget_shape(
        evidence,
        raw_widget_payloads={"7": _raw_widgets(length=3)},
        is_new_node=True,
    )

    assert verdict.decision is WidgetShapeDecision.REFUSE
    assert WidgetShapeReason.OVERFLOW in verdict.reasons


def test_dynamic_node_with_unchanged_full_raw_payload_pins_opaque() -> None:
    evidence = _evidence(has_dict_rows=True)

    verdict = decide_widget_shape(
        evidence,
        raw_widget_payloads={"7": _raw_widgets()},
        raw_payloads={"7": _raw_node()},
        layout_entries={"7": _layout()},
        field_deltas={},
        link_deltas={},
    )

    assert verdict.decision is WidgetShapeDecision.PIN_OPAQUE
    assert verdict.pin_opaque is True
    assert verdict.refuse is False
    assert verdict.raw_ui_node == _raw_node()
    assert verdict.layout_entry == _layout()
    assert verdict.reasons == (WidgetShapeReason.DICT_ROW_DYNAMIC_WIDGETS,)


def test_dynamic_node_without_raw_payload_refuses() -> None:
    evidence = _evidence(schema_less=True, has_dict_rows=True, provider=None, confidence=None)

    verdict = decide_widget_shape(
        evidence,
        raw_widget_payloads={},
        raw_payloads={},
        layout_entries={"7": _layout()},
    )

    assert verdict.decision is WidgetShapeDecision.REFUSE
    assert WidgetShapeReason.SCHEMA_LESS in verdict.reasons
    assert WidgetShapeReason.MISSING_RAW_UI_PAYLOAD in verdict.reasons
    assert WidgetShapeReason.MISSING_RAW_WIDGET_PAYLOAD in verdict.reasons


def test_dynamic_node_matching_observed_widgets_recovers_by_regeneration() -> None:
    verdict = decide_widget_shape(
        _evidence(has_dict_rows=True),
        raw_widget_payloads={"7": _raw_widgets()},
    )

    assert verdict.decision is WidgetShapeDecision.SAFE_TO_REGENERATE
    assert verdict.recovery == "observed_dynamic_widgets_regenerate"
    assert WidgetShapeReason.DICT_ROW_DYNAMIC_WIDGETS in verdict.reasons


def test_identity_matched_node_carries_forward_raw_ui_without_other_payloads() -> None:
    evidence = _evidence(
        overflow=True,
        raw_widget_count=3,
        candidate_widget_count=2,
        schema_widget_count=2,
    )

    verdict = decide_widget_shape(
        evidence,
        raw_payloads={"7": _raw_node()},
        identity_matched=True,
    )

    assert verdict.decision is WidgetShapeDecision.PIN_OPAQUE
    assert verdict.recovery == "carry_forward_raw_ui"
    assert verdict.raw_ui_node == _raw_node()


def test_schema_known_generated_node_uses_schema_default_regeneration() -> None:
    verdict = decide_widget_shape(
        _evidence(raw_widget_count=None),
        raw_payloads={},
        raw_widget_payloads={},
        allow_schema_default_regenerate=True,
    )

    assert verdict.decision is WidgetShapeDecision.SAFE_TO_REGENERATE
    assert verdict.recovery == "schema_default_regenerate"
    assert verdict.use_schema_defaults is True


def test_schema_known_generated_explicit_overflow_uses_schema_default_regeneration() -> None:
    verdict = decide_widget_shape(
        _evidence(
            raw_widget_count=None,
            candidate_widget_count=4,
            schema_widget_count=2,
            overflow=True,
            explicit_widget_overflow=True,
        ),
        raw_payloads={},
        raw_widget_payloads={},
        allow_schema_default_regenerate=True,
    )

    assert verdict.decision is WidgetShapeDecision.SAFE_TO_REGENERATE
    assert verdict.recovery == "schema_default_regenerate"
    assert verdict.use_schema_defaults is True


def test_new_node_with_null_raw_type_or_widgets_still_refuses() -> None:
    verdict = decide_widget_shape(
        _evidence(),
        raw_payloads={"7": {"id": 7, "type": None, "widgets_values": None}},
        allow_schema_default_regenerate=True,
        is_new_node=True,
    )

    assert verdict.decision is WidgetShapeDecision.REFUSE
    assert WidgetShapeReason.MISSING_RAW_UI_PAYLOAD in verdict.reasons


def test_dynamic_node_with_widget_delta_refuses_instead_of_pinning() -> None:
    evidence = _evidence(has_dict_rows=True)

    verdict = decide_widget_shape(
        evidence,
        raw_widget_payloads={"7": _raw_widgets()},
        raw_payloads={"7": _raw_node()},
        layout_entries={"7": _layout()},
        field_deltas={"7": {"widget_1": ("old", "new")}},
    )

    assert verdict.decision is WidgetShapeDecision.REFUSE
    assert WidgetShapeReason.DICT_ROW_DYNAMIC_WIDGETS in verdict.reasons
    assert WidgetShapeReason.WIDGET_DELTA in verdict.reasons


def test_dynamic_node_with_link_delta_refuses_instead_of_pinning() -> None:
    evidence = _evidence(has_dict_rows=True)

    verdict = decide_widget_shape(
        evidence,
        raw_widget_payloads={"7": _raw_widgets()},
        raw_payloads={"7": _raw_node()},
        layout_entries={"7": _layout()},
        link_deltas={"7": {"inputs": {"image": ("old", "new")}}},
    )

    assert verdict.decision is WidgetShapeDecision.REFUSE
    assert WidgetShapeReason.DICT_ROW_DYNAMIC_WIDGETS in verdict.reasons
    assert WidgetShapeReason.LINK_DELTA in verdict.reasons


def test_raw_ui_node_map_extracts_full_payload_by_id_and_uid() -> None:
    raw_node = _raw_node()
    raw_node["properties"] = {"vibecomfy_uid": "uid-dynamic"}
    ui_payload = {"nodes": [raw_node]}

    raw_map = extract_raw_ui_node_map(ui_payload)

    assert raw_map["7"] == raw_node
    assert raw_map["uid-dynamic"] == raw_node
    assert "widgets_values" in raw_map["uid-dynamic"]


def test_collateral_overflow_without_delta_pins_opaque() -> None:
    """Collateral node with overflow, full raw UI, and no deltas pins opaque.

    Even when identity_matched is False, a node that has a complete
    raw LiteGraph dict and no widget/link deltas should carry the
    payload forward rather than refusing or regenerating.
    """
    evidence = _evidence(
        overflow=True,
        raw_widget_count=3,
        candidate_widget_count=3,
        schema_widget_count=2,
    )

    verdict = decide_widget_shape(
        evidence,
        raw_payloads={"7": _raw_node()},
        layout_entries={"7": _layout()},
        field_deltas={},
        link_deltas={},
        identity_matched=False,
    )

    assert verdict.decision is WidgetShapeDecision.PIN_OPAQUE
    assert verdict.pin_opaque is True
    assert verdict.refuse is False
    assert verdict.recovery == "carry_forward_raw_ui"
    assert WidgetShapeReason.OVERFLOW in verdict.reasons


def test_collateral_dynamic_node_without_delta_pins_opaque() -> None:
    """Collateral dynamic (dict-row) node without deltas pins opaque.

    A node with dict-row widgets that is untouched by any edit
    should pin opaque when the raw UI payload is complete.
    """
    evidence = _evidence(has_dict_rows=True)

    verdict = decide_widget_shape(
        evidence,
        raw_payloads={"7": _raw_node()},
        layout_entries={"7": _layout()},
        field_deltas={},
        link_deltas={},
        identity_matched=False,
    )

    assert verdict.decision is WidgetShapeDecision.PIN_OPAQUE
    assert verdict.pin_opaque is True
    assert verdict.refuse is False
    assert verdict.recovery == "carry_forward_raw_ui"
    assert WidgetShapeReason.DICT_ROW_DYNAMIC_WIDGETS in verdict.reasons


def test_collateral_schema_less_node_without_delta_pins_opaque() -> None:
    """Collateral schema-less node without deltas pins opaque.

    Even a schema-less node with full raw UI and no deltas
    should carry forward rather than refusing.
    """
    evidence = _evidence(schema_less=True, provider=None, confidence=None)

    verdict = decide_widget_shape(
        evidence,
        raw_payloads={"7": _raw_node()},
        layout_entries={"7": _layout()},
        field_deltas={},
        link_deltas={},
        identity_matched=False,
    )

    assert verdict.decision is WidgetShapeDecision.PIN_OPAQUE
    assert verdict.pin_opaque is True
    assert verdict.refuse is False
    assert verdict.recovery == "carry_forward_raw_ui"


def test_collateral_node_with_widget_delta_still_refuses() -> None:
    """Touched collateral node with a widget delta must still refuse.

    The relaxation only applies to truly collateral (untouched) nodes.
    Once a widget delta exists, the strict refusal path is preserved.
    """
    evidence = _evidence(
        overflow=True,
        raw_widget_count=3,
        candidate_widget_count=3,
        schema_widget_count=2,
    )

    verdict = decide_widget_shape(
        evidence,
        raw_payloads={"7": _raw_node()},
        layout_entries={"7": _layout()},
        field_deltas={"7": {"widget_0": ("old", "new")}},
        identity_matched=False,
    )

    assert verdict.decision is WidgetShapeDecision.REFUSE
    assert WidgetShapeReason.WIDGET_DELTA in verdict.reasons


def test_collateral_node_with_link_delta_still_refuses() -> None:
    """Touched collateral node with a link delta must still refuse."""
    evidence = _evidence(
        overflow=True,
        raw_widget_count=3,
        candidate_widget_count=3,
        schema_widget_count=2,
    )

    verdict = decide_widget_shape(
        evidence,
        raw_payloads={"7": _raw_node()},
        layout_entries={"7": _layout()},
        link_deltas={"7": {"incoming_edge_sig": ("old", "new")}},
        identity_matched=False,
    )

    assert verdict.decision is WidgetShapeDecision.REFUSE
    assert WidgetShapeReason.LINK_DELTA in verdict.reasons


def test_collateral_node_without_raw_ui_payload_still_refuses() -> None:
    """Collateral node without a complete raw UI payload must still refuse."""
    evidence = _evidence(
        overflow=True,
        raw_widget_count=3,
        candidate_widget_count=3,
        schema_widget_count=2,
    )

    verdict = decide_widget_shape(
        evidence,
        raw_payloads={},
        layout_entries={},
        field_deltas={},
        link_deltas={},
        identity_matched=False,
    )

    assert verdict.decision is WidgetShapeDecision.REFUSE


def test_prior_store_only_layout_match_does_not_make_dynamic_node_pin_capable() -> None:
    raw_node = _raw_node()
    raw_node["properties"] = {"vibecomfy_uid": "7"}
    prior_store = store_from_ui_json({"nodes": [raw_node]})
    evidence = _evidence(has_dict_rows=True)

    verdict = decide_widget_shape(
        evidence,
        raw_widget_payloads={"7": _raw_widgets()},
        raw_payloads=extract_raw_ui_node_map(None),
        layout_entries=prior_store["entries"],
        field_deltas={},
        link_deltas={},
    )

    assert verdict.decision is WidgetShapeDecision.SAFE_TO_REGENERATE
    assert verdict.recovery == "observed_dynamic_widgets_regenerate"
    assert WidgetShapeReason.DICT_ROW_DYNAMIC_WIDGETS in verdict.reasons
