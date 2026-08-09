"""Regression: authority replay must match the executor's sequential application.

The batch-REPL executor builds the candidate it returns to the user by applying
ops **one at a time, in program order** (``_parse_execute`` calls
``apply_delta(working_ui, (op,))`` per statement). ``apply_delta(submit,
all_ops)`` resolves every ``add_node`` against the *pre-mutation* graph (before
removes land), so on a multi-add edit its layout placement can diverge from the
executor's strict order. That divergence is only in non-semantic ``pos``
coordinates, but the authority byte-hash tripped on it and rejected a valid
candidate (the "switch to sdxl" symptom: candidate passed every gate incl.
``ui_fidelity_ok`` yet ``candidate_matches`` was false; the identical retry
passed). ``recompute_apply`` now applies ops sequentially, mirroring the
executor, so the authority verifies the graph the user actually receives.
"""
from __future__ import annotations

import json
from pathlib import Path

from vibecomfy.comfy_nodes.agent.authority_receipts import (
    recompute_apply,
    verify_replay,
)
from vibecomfy.comfy_nodes.agent.session import payload_hash
from vibecomfy.porting.edit.apply_core import apply_delta
from vibecomfy.porting.edit.ops import normalize_delta_ops
from vibecomfy.schema import InputSpec, NodeSchema, OutputSpec

FIXTURE = (
    Path(__file__).parent
    / "characterization"
    / "fixtures"
    / "agent_edit"
    / "case_01_widget_set"
    / "input_ui.json"
)


class _ClipSchemaProvider:
    """Minimal provider that knows CLIPTextEncode — enough to add nodes offline."""

    def __init__(self) -> None:
        self._schema = NodeSchema(
            class_type="CLIPTextEncode",
            pack="core",
            inputs={
                "text": InputSpec(type="STRING", required=True),
                "clip": InputSpec(type="CLIP", required=True),
            },
            outputs=[OutputSpec(type="CONDITIONING", name="CONDITIONING")],
        )

    def get_schema(self, class_type: str) -> NodeSchema | None:
        return self._schema if class_type == "CLIPTextEncode" else None


def _submit_graph() -> dict:
    return json.loads(FIXTURE.read_text(encoding="utf-8"))


def _envelope(ops: list) -> dict:
    return {"schema_version": "2.0.0", "ops": ops}


def _sequential_candidate(submit: dict, ops: tuple, schema_provider) -> dict:
    """Apply ops one at a time, in order — exactly how the executor builds it."""
    working = submit
    for op in ops:
        step = apply_delta(working, (op,), schema_provider=schema_provider)
        assert step.ok and step.candidate is not None, step.diagnostics
        working = step.candidate
    return working


def test_replay_matches_executor_candidate_on_multi_add_with_remove() -> None:
    """The authority must accept the candidate the executor actually produces.

    Delta: remove the two prompt encoders that sit to the right of the
    checkpoint, then add two CLIPTextEncode nodes anchored to the right of the
    checkpoint. Sequential application removes them first, so the adds land in
    the freed region; all-at-once places the adds before the removes land, so
    collision avoidance nudges them elsewhere. The executor is sequential, so
    the authority must be too.
    """
    schema_provider = _ClipSchemaProvider()
    submit = _submit_graph()
    envelope = _envelope(
        [
            {"op": "remove_node", "target": ["", "2"]},
            {"op": "remove_node", "target": ["", "3"]},
            {
                "op": "add_node",
                "uid": "n10",
                "node_id": "10",
                "scope_path": "",
                "class_type": "CLIPTextEncode",
                "anchor": {"relation": "right_of", "near": ["", "1"]},
                "fields": {"text": "positive prompt"},
                "inputs": {"clip": ["", "1", "CLIP"]},
            },
            {
                "op": "add_node",
                "uid": "n11",
                "node_id": "11",
                "scope_path": "",
                "class_type": "CLIPTextEncode",
                "anchor": {"relation": "right_of", "near": ["", "1"]},
                "fields": {"text": "negative prompt"},
                "inputs": {"clip": ["", "1", "CLIP"]},
            },
        ]
    )
    ops = normalize_delta_ops(envelope)

    candidate_seq = _sequential_candidate(submit, ops, schema_provider)
    candidate_all = apply_delta(
        submit, ops, schema_provider=schema_provider
    ).candidate

    # The bug condition: the two application strategies genuinely diverge. If
    # this ever stops diverging, placement changed and this guard should be
    # revisited — but the invariant test below still holds regardless.
    assert payload_hash(candidate_seq) != payload_hash(candidate_all), (
        "expected sequential vs all-at-once to diverge on this multi-add delta; "
        "the regression fixture no longer exercises the bug condition"
    )

    receipt = verify_replay(submit, envelope, candidate_seq, schema_provider=schema_provider)
    assert receipt.replay_ok is True
    assert receipt.candidate_matches is True, (
        f"authority rejected the executor's own sequential candidate: {receipt.error}"
    )


def test_recompute_apply_is_sequential_invariant() -> None:
    """For any delta, recompute_apply must equal one-at-a-time application."""
    schema_provider = _ClipSchemaProvider()
    submit = _submit_graph()
    envelope = _envelope(
        [
            {"op": "set_node_field", "target": ["", "5", "seed"], "value": 99},
            {"op": "remove_node", "target": ["", "4"]},
            {
                "op": "add_node",
                "uid": "n10",
                "node_id": "10",
                "scope_path": "",
                "class_type": "CLIPTextEncode",
                "anchor": {"relation": "right_of", "near": ["", "1"]},
                "fields": {"text": "positive prompt"},
                "inputs": {"clip": ["", "1", "CLIP"]},
            },
        ]
    )
    ops = normalize_delta_ops(envelope)

    ok, recomputed, error, _ = recompute_apply(submit, envelope, schema_provider=schema_provider)
    assert ok is True, error
    assert error is None

    expected = _sequential_candidate(submit, ops, schema_provider)
    assert payload_hash(recomputed) == payload_hash(expected), (
        "recompute_apply drifted from sequential application"
    )
