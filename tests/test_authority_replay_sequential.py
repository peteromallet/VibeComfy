"""Regression: authority replay must match sequential interpret+emit.

``recompute_apply`` applies ops one at a time through interpret+emit, mirroring
the batch-REPL executor. These tests lock that contract without the deleted
all-at-once apply_delta path.
"""
from __future__ import annotations

import json
from pathlib import Path

from vibecomfy.comfy_nodes.agent.authority_receipts import (
    recompute_apply,
    verify_replay,
)
from vibecomfy.comfy_nodes.agent.session import payload_hash
from vibecomfy.ingest.normalize import from_ui
from vibecomfy.porting.edit._interpret import interpret
from vibecomfy.porting.edit.ops import normalize_delta_ops
from vibecomfy.porting.emit.ui import emit_ui_json
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


def _sequential_candidate(submit: dict, envelope: dict, schema_provider) -> dict:
    """Apply ops one at a time via interpret+emit — the live sequential path."""
    ops = normalize_delta_ops(envelope)
    workflow = from_ui(dict(submit), schema_provider=schema_provider, use_comfy_converter=False)
    for op in ops:
        step = interpret(workflow, (op,), schema_provider=schema_provider)
        assert step.ok, step.diagnostics
        workflow = step.workflow
    return emit_ui_json(
        workflow,
        schema_provider=schema_provider,
        include_virtual_wires=True,
        prior_ui_payload=submit,
    )


def test_replay_matches_executor_candidate_on_multi_add_with_remove() -> None:
    """The authority must accept the candidate sequential interpret produces."""
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

    candidate = _sequential_candidate(submit, envelope, schema_provider)
    receipt = verify_replay(submit, envelope, candidate, schema_provider=schema_provider)
    assert receipt.replay_ok is True
    assert receipt.candidate_matches is True, (
        f"authority rejected the sequential interpret candidate: {receipt.error}"
    )


def test_recompute_apply_is_sequential_invariant() -> None:
    """For any delta, recompute_apply must equal one-at-a-time interpret+emit."""
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

    ok, recomputed, error, _ = recompute_apply(submit, envelope, schema_provider=schema_provider)
    assert ok is True, error
    assert error is None

    expected = _sequential_candidate(submit, envelope, schema_provider)
    assert payload_hash(recomputed) == payload_hash(expected), (
        "recompute_apply drifted from sequential interpret+emit"
    )
