"""RRSYN2-5: untouched widget rows survive so accepted deltas replay
byte-for-byte.

The observed corruption: source row ``[null, null, 1.0, "multiply"]``
emitted as ``[null, null, 1.8]`` after a named write to ``strength`` —
silently dropping the untouched ``strength_type`` literal.  Emission must
overwrite ONLY the resolved position; a ``None`` carrier never masks a
captured raw value; trailing captured values are never trimmed; and the
authority receipt rejects a named field that cannot resolve to exactly one
raw position BEFORE landing.
"""

from __future__ import annotations

from types import SimpleNamespace
from typing import Any

from vibecomfy.porting.emit.ui import _build_widget_values


def _node(
    *,
    inputs: dict[str, Any] | None = None,
    widgets: dict[str, Any] | None = None,
    raw_row: list[Any],
) -> SimpleNamespace:
    return SimpleNamespace(
        widgets=dict(widgets or {}),
        inputs=dict(inputs or {}),
        metadata={"_ui": {"widgets_values": list(raw_row)}},
    )


# ── emission: preserve untouched rows ────────────────────────────────────────


def test_named_write_overwrites_only_its_position() -> None:
    """The ip-adapter leg: strength 1.0 -> 1.8 keeps strength_type."""
    node = _node(
        inputs={"strength": 1.8},
        raw_row=[None, None, 1.0, "multiply"],
    )
    names = [None, None, "strength", "strength_type"]
    values = _build_widget_values(node, names)
    assert values == [None, None, 1.8, "multiply"]


def test_none_carrier_never_masks_captured_literal() -> None:
    node = _node(
        inputs={"strength_type": None},
        raw_row=[None, None, 1.0, "multiply"],
    )
    names = [None, None, "strength", "strength_type"]
    values = _build_widget_values(node, names)
    assert values == [None, None, 1.0, "multiply"]


def test_trailing_captured_value_is_never_trimmed() -> None:
    node = _node(inputs={}, raw_row=[1.0, "multiply"])
    names: list[str | None] = ["strength", None]
    values = _build_widget_values(node, names)
    assert values == [1.0, "multiply"]


def test_genuinely_absent_trailing_none_still_trims() -> None:
    """No raw row at all — legacy trim behavior is preserved."""
    node = _node(widgets={}, inputs={}, raw_row=[])
    values = _build_widget_values(node, ["strength", None])
    assert values == []


def test_explicit_none_write_without_raw_row_is_honored_mid_row() -> None:
    """With no captured row, a None carrier is emitted as-is; the literal
    after it stops the legacy trailing trim."""
    node = SimpleNamespace(
        widgets={},
        inputs={"strength": None, "strength_type": "multiply"},
        metadata={"_ui": {}},
    )
    values = _build_widget_values(node, ["strength", "strength_type"])
    assert values == [None, "multiply"]


# ── authority receipt: typed field-resolution rejection ─────────────────────


_SUBMIT_GRAPH: dict[str, Any] = {
    "nodes": [
        {
            "id": 9,
            "type": "StyleModelStrength",
            "widgets_values": [1.0, "multiply"],
            "properties": {"vibecomfy_uid": "style-node"},
            "outputs": [],
        },
    ],
    "links": [],
}
_NAME_AUTHORITY = {"9": ["strength", "strength_type"]}


def _envelope(field: str, value: Any) -> dict[str, Any]:
    return {
        "delta_contract": "delta_v1",
        "schema_version": "2.0.0",
        "ops": [
            {
                "op": "set_node_field",
                "target": ["", "style-node", field],
                "value": value,
            }
        ],
        "op_count": 1,
    }


def test_unresolvable_named_field_fails_receipt_before_landing() -> None:
    from vibecomfy.comfy_nodes.agent.authority_receipts import recompute_apply

    ok, candidate, error, op_count = recompute_apply(
        _SUBMIT_GRAPH,
        _envelope("not_a_real_widget", 2),
        name_authority=_NAME_AUTHORITY,
    )
    assert ok is False
    assert candidate is None
    assert error is not None
    assert error.startswith("field_resolution_unresolved:")
    assert "not_a_real_widget" in error
    assert op_count == 1


def test_resolvable_named_field_still_lands_and_replays() -> None:
    from vibecomfy.comfy_nodes.agent.authority_receipts import recompute_apply

    ok, candidate, error, _op_count = recompute_apply(
        _SUBMIT_GRAPH,
        _envelope("strength", 1.8),
        name_authority=_NAME_AUTHORITY,
    )
    assert ok is True, error
    assert candidate is not None
    by_id = {str(n["id"]): n for n in candidate["nodes"]}
    widgets = by_id["9"].get("widgets_values")
    assert widgets[0] == 1.8
    # The untouched literal survives byte-for-byte in the replayed candidate.
    assert widgets[1] == "multiply"
