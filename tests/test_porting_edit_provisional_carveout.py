"""Carve-out unit test: LayerMask fail-closed vs Preview3D provisional allowed."""

from vibecomfy.porting.edit.admit import (
    AdmissionRejected,
    _CARVED_OUT_FAIL_CLOSED_CLASSES,
    _is_provisional_touched_for_admit,
    admit_operation,
)


def _session():
    from tests.test_porting_edit_kernel import _session as kernel_session

    return kernel_session()


def _schema_pair(session, *, extra_missing: str | None = None):
    from tests.test_porting_edit_kernel import _schema_pair as kernel_pair

    return kernel_pair(session, extra_missing=extra_missing)


def test_provisional_carveout_layer_mask_fail_closed_while_preview3d_allowed() -> None:
    # Documents _CARVED_OUT_FAIL_CLOSED_CLASSES constant.
    assert "LayerMask: SegmentAnythingUltra V3" in _CARVED_OUT_FAIL_CLOSED_CLASSES

    session = _session()
    pair, _uid = _schema_pair(session)
    # Use catalog from pair (schema) for helper checks
    catalog = pair.schema
    assert catalog is not None

    # LayerMask add must stay fail-closed via carve-out (helper returns False)
    layer_op = {"op": "add_node", "class_type": "LayerMask: SegmentAnythingUltra V3", "uid": "carve-1"}
    assert _is_provisional_touched_for_admit(layer_op, session.workflow, catalog) is False
    rejected = admit_operation(pair, layer_op, working_workflow=session.workflow)
    assert isinstance(rejected, AdmissionRejected)
    assert rejected.typed_reason == "missing_touched_schema"

    # Preview3D provisional add should be allowed by helper (not carved out, class is missing)
    preview_op = {"op": "add_node", "class_type": "Preview3D", "uid": "carve-2"}
    # Preview3D is not in known catalog, so helper should return True (allow provisional)
    assert _is_provisional_touched_for_admit(preview_op, session.workflow, catalog) is True
