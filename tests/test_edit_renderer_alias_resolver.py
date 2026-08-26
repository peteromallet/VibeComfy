"""RRSYN2-4: renderer-emitted output aliases are valid at admission AND replay.

One canonical resolver (``canonical_renderer_output``) decides whether a
``TYPE_N`` alias (``AUDIO_0``), integer slot, ``unknown_N`` fallback, or
literal name resolves against the frozen node's output evidence.  Admission
(``admit_operation`` → ``_known_output``/``_validate_link``) and authority
replay (``recompute_apply`` → the identical admit seam) must never disagree.
"""

from __future__ import annotations

import json
from types import SimpleNamespace
from typing import Any, Mapping

from vibecomfy.porting.edit._interpret import (
    canonical_renderer_output,
    renderer_output_slots,
)
from vibecomfy.porting.edit._op_validate import _known_output


def _node(
    metadata: dict[str, Any] | None = None,
    *,
    class_type: str = "AudioDecoder",
    uid: str = "7",
) -> SimpleNamespace:
    return SimpleNamespace(
        class_type=class_type,
        uid=uid,
        metadata=dict(metadata or {}),
    )


# ── canonical resolver units ─────────────────────────────────────────────────


def test_typed_alias_resolves_to_frozen_name() -> None:
    node = _node({"output_names": ["AUDIO"], "output_types": ["AUDIO"]})
    assert canonical_renderer_output(node, "AUDIO_0") == "AUDIO"
    assert canonical_renderer_output(node, 0) == "AUDIO"
    assert _known_output(node, "AUDIO_0", None) is True


def test_typed_alias_agrees_with_ui_output_evidence() -> None:
    node = _node({"_ui": {"outputs": [{"name": "AUDIO", "type": "AUDIO"}]}})
    assert canonical_renderer_output(node, "AUDIO_0") == "AUDIO"
    assert _known_output(node, "AUDIO_0", None) is True


def test_mismatched_type_token_rejects_even_with_valid_index() -> None:
    node = _node({"output_names": ["AUDIO"], "output_types": ["AUDIO"]})
    assert canonical_renderer_output(node, "IMAGE_0") is None
    assert _known_output(node, "IMAGE_0", None) is False


def test_out_of_range_alias_rejects() -> None:
    node = _node({"output_names": ["AUDIO"], "output_types": ["AUDIO"]})
    assert canonical_renderer_output(node, "AUDIO_3") is None
    assert _known_output(node, "AUDIO_3", None) is False


def test_index_backed_unknown_fallback_round_trips() -> None:
    node = _node(
        {
            "_ui": {"outputs": [{"name": "", "type": "AUDIO"}]},
            "output_names": [None],
        }
    )
    assert canonical_renderer_output(node, "unknown_0") is not None
    assert _known_output(node, "unknown_0", None) is True
    assert _known_output(node, "unknown_5", None) is False


def test_literal_names_still_match_any_frozen_evidence() -> None:
    ui_only = _node({"_ui": {"outputs": [{"name": "AUDIO"}, {"name": "VIDEO"}]}})
    assert _known_output(ui_only, "AUDIO", None) is True
    assert _known_output(ui_only, 0, None) is True
    bare_string_ui = _node({"output_names": None, "_ui": {"outputs": ["VIDEO"]}})
    assert _known_output(bare_string_ui, "VIDEO", None) is True
    assert _known_output(bare_string_ui, 9, None) is False
    names_only = _node({"output_names": ["LATENT", "VIDEO"]})
    assert _known_output(names_only, "LATENT", None) is True
    assert _known_output(names_only, "MISSING", None) is False
    empty = _node({})
    assert _known_output(empty, "ANY", None) is False
    assert _known_output(empty, 0, None) is False


# ── admission + replay parity through the shared seam ────────────────────────


_SUBMIT_GRAPH: dict[str, Any] = {
    "nodes": [
        {
            "id": 1,
            "type": "AudioDecoder",
            "inputs": {},
            "outputs": [
                {"name": "AUDIO", "type": "AUDIO", "links": []},
            ],
        },
        {
            "id": 2,
            "type": "SaveAudio",
            # Declared socket input; the literal-write channel stays closed.
            "inputs": {"audio": None},
            "outputs": [],
        },
    ],
    "links": [],
}


class _FrozenProvider:
    """Frozen admission authority over the two synthetic classes above."""

    def __init__(self) -> None:
        from vibecomfy.schema import InputSpec, NodeSchema, OutputSpec
        from vibecomfy.schema.types import (
            FrozenSchemaSnapshotProvider,
            capture_schema_snapshot,
            schema_payload_from_node_schema,
        )

        schemas = {
            "AudioDecoder": NodeSchema(
                class_type="AudioDecoder",
                pack="test",
                inputs={},
                outputs=[OutputSpec(type="AUDIO", name="AUDIO")],
            ),
            "SaveAudio": NodeSchema(
                class_type="SaveAudio",
                pack="test",
                inputs={"audio": InputSpec(type="AUDIO", required=True)},
                outputs=[],
            ),
        }
        payloads = {
            class_type: schema_payload_from_node_schema(class_type, schema)
            for class_type, schema in schemas.items()
        }
        snap = capture_schema_snapshot(
            class_types=sorted(payloads),
            request_snapshot={
                "contract_version": "schema_snapshot_v1",
                "schemas": payloads,
                "missing_classes": [],
            },
            node_classes={"1": "AudioDecoder", "2": "SaveAudio"},
        )
        self._inner = FrozenSchemaSnapshotProvider(snap)

    def get_schema(self, class_type: str):
        return self._inner.get_schema(class_type)

    def __getattr__(self, name: str):
        return getattr(self._inner, name)


def _provider() -> "_FrozenProvider":
    return _FrozenProvider()


def _envelope(op: dict[str, Any]) -> dict[str, Any]:
    return {"ops": [op], "op_count": 1}


def test_upsert_link_with_rendered_audio_alias_admits_and_replays() -> None:
    """The c80bbf shape: the frozen render exposed AUDIO_0 and existing edges
    use it; admission AND authority replay must both accept the alias."""
    from vibecomfy.comfy_nodes.agent.authority_receipts import recompute_apply

    op = {
        "op": "upsert_link",
        "from": ["", "1", "AUDIO_0"],
        "to": ["", "2", "audio"],
    }
    ok, candidate, error, op_count = recompute_apply(
        _SUBMIT_GRAPH,
        _envelope(op),
        schema_provider=_provider(),
    )
    assert ok is True, error
    assert candidate is not None
    assert op_count == 1
    # The link actually landed in the replayed candidate: SaveAudio's
    # ``audio`` input is wired to AudioDecoder output slot 0.
    by_id = {str(node.get("id")): node for node in candidate.get("nodes", [])}
    save_node = by_id.get("2") or {}
    entries = [
        item
        for item in (save_node.get("inputs") or [])
        if isinstance(item, Mapping) and item.get("name") == "audio"
    ]
    assert entries, json.dumps(save_node)[:200]
    assert entries[0].get("link") is not None


def _envelope(op: dict[str, Any]) -> dict[str, Any]:
    return {
        "delta_contract": "delta_v1",
        "schema_version": "2.0.0",
        "ops": [op],
        "op_count": 1,
    }


def test_unknown_alias_rejected_identically_at_admission_and_replay() -> None:
    from vibecomfy.comfy_nodes.agent.authority_receipts import recompute_apply
    from vibecomfy.ingest.normalize import from_ui
    from vibecomfy.porting.edit.admit import (
        AdmissionRejected,
        admission_snapshot_for,
        admit_operations,
    )

    bad_op = {
        "op": "upsert_link",
        "from": ["", "1", "IMAGE_0"],
        "to": ["", "2", "audio"],
    }
    workflow = from_ui(
        dict(_SUBMIT_GRAPH),
        schema_provider=None,
        use_comfy_converter=False,
    )
    result = admit_operations(
        admission_snapshot_for(workflow, _provider()),
        [bad_op],
        working_workflow=workflow,
    )
    assert isinstance(result, AdmissionRejected)
    assert result.typed_reason == "unknown_port"
    joined = " ".join(result.evidence_refs)
    assert "IMAGE_0" in joined
    assert "valid output slots" in joined
    assert any(ref.startswith("offered:") for ref in result.evidence_refs)

    ok, _candidate, error, _count = recompute_apply(
        _SUBMIT_GRAPH,
        _envelope(bad_op),
        schema_provider=_provider(),
    )
    assert ok is False
    assert error == "unknown_port"


def test_rejection_evidence_names_node_offered_slot_and_valid_slots() -> None:
    from vibecomfy.ingest.normalize import from_ui
    from vibecomfy.porting.edit.admit import (
        admission_snapshot_for,
        admit_operation,
    )

    workflow = from_ui(
        dict(_SUBMIT_GRAPH),
        schema_provider=None,
        use_comfy_converter=False,
    )
    result = admit_operation(
        admission_snapshot_for(workflow, _provider()),
        {
            "op": "upsert_link",
            "from": ["", "1", "AUDIO_9"],
            "to": ["", "2", "audio"],
        },
        working_workflow=workflow,
    )
    assert getattr(result, "typed_reason", "") == "unknown_port"
    joined = " ".join(getattr(result, "evidence_refs", ()))
    assert "AUDIO_9" in joined
    assert "0:AUDIO" in joined           # the valid slot listing
    assert "frozen_render_ui" in joined  # evidence source attribution



# ── batch-review RR2: interior blank output rows keep frozen slot indices ────


def test_interior_blank_ui_row_keeps_slot_indices() -> None:
    """``[IMAGE, {}, AUDIO]``: the blank interior row OWNS index 1.  The
    canonical alias domain must advertise ``2:AUDIO`` — never ``1:AUDIO`` —
    so AUDIO_2 resolves and AUDIO_1 rejects (fail-closed)."""
    node = _node(
        {"_ui": {"outputs": [{"type": "IMAGE"}, {}, {"type": "AUDIO"}]}}
    )
    assert canonical_renderer_output(node, "AUDIO_2") == "AUDIO_2"
    assert canonical_renderer_output(node, "AUDIO_1") is None
    assert canonical_renderer_output(node, "IMAGE_0") == "IMAGE_0"
    assert canonical_renderer_output(node, "IMAGE_1") is None
    slots, _sources = renderer_output_slots(node)
    assert slots == ("0:IMAGE", "2:AUDIO")
    assert _known_output(node, "AUDIO_2", None) is True
    assert _known_output(node, "AUDIO_1", None) is False


_BLANK_ROW_GRAPH: dict[str, Any] = {
    "nodes": [
        {
            "id": 1,
            "type": "AudioDecoder",
            "inputs": {},
            "outputs": [
                {"name": "FRAME", "type": "IMAGE", "links": []},
                {},
                {"name": "CLIP", "type": "AUDIO", "links": []},
            ],
        },
        {
            "id": 2,
            "type": "SaveAudio",
            # Declared socket input; the literal-write channel stays closed.
            "inputs": {"audio": None},
            "outputs": [],
        },
    ],
    "links": [],
}


def test_blank_interior_row_alias_admits_and_replays_true_index() -> None:
    """Admission AND authority replay agree through the shared seam when the
    frozen render carries an interior blank output row: AUDIO_2 lands on
    slot 2; AUDIO_1 is rejected identically on both paths."""
    from vibecomfy.comfy_nodes.agent.authority_receipts import recompute_apply
    from vibecomfy.ingest.normalize import from_ui
    from vibecomfy.porting.edit.admit import (
        AdmissionRejected,
        admission_snapshot_for,
        admit_operations,
    )

    good_op = {
        "op": "upsert_link",
        "from": ["", "1", "AUDIO_2"],
        "to": ["", "2", "audio"],
    }
    workflow = from_ui(
        dict(_BLANK_ROW_GRAPH),
        schema_provider=None,
        use_comfy_converter=False,
    )
    admitted = admit_operations(
        admission_snapshot_for(workflow, _provider()),
        [good_op],
        working_workflow=workflow,
    )
    assert not isinstance(admitted, AdmissionRejected)

    ok, candidate, error, op_count = recompute_apply(
        _BLANK_ROW_GRAPH,
        _envelope(good_op),
        schema_provider=_provider(),
    )
    assert ok is True, error
    assert candidate is not None
    assert op_count == 1
    by_id = {str(node.get("id")): node for node in candidate.get("nodes", [])}
    save_node = by_id.get("2") or {}
    entries = [
        item
        for item in (save_node.get("inputs") or [])
        if isinstance(item, Mapping) and item.get("name") == "audio"
    ]
    assert entries, json.dumps(save_node)[:200]
    assert entries[0].get("link") is not None

    bad_op = {
        "op": "upsert_link",
        "from": ["", "1", "AUDIO_1"],
        "to": ["", "2", "audio"],
    }
    rejected = admit_operations(
        admission_snapshot_for(workflow, _provider()),
        [bad_op],
        working_workflow=workflow,
    )
    assert isinstance(rejected, AdmissionRejected)
    joined = " ".join(rejected.evidence_refs)
    assert "0:FRAME" in joined
    assert "2:CLIP" in joined
    ok2, _candidate2, error2, _count2 = recompute_apply(
        _BLANK_ROW_GRAPH,
        _envelope(bad_op),
        schema_provider=_provider(),
    )
    assert ok2 is False
    assert error2 == "unknown_port"