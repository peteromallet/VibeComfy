from __future__ import annotations

import json
import subprocess
import sys

from vibecomfy.comfy_nodes.agent.executor_response import serialize_executor_result


def _canonical_json(payload: dict) -> bytes:
    return json.dumps(payload, sort_keys=True, separators=(",", ":")).encode("utf-8")


def test_executor_response_module_import_does_not_load_routes_or_executor_core() -> None:
    code = """
import sys
import vibecomfy.comfy_nodes.agent.executor_response
assert "vibecomfy.comfy_nodes.agent.routes" not in sys.modules
assert "vibecomfy.executor.core" not in sys.modules
"""

    env = dict(__import__("os").environ)
    # Headless mode keeps the comfy_nodes package from registering ComfyUI
    # server routes at import time; the assertion targets what
    # executor_response itself pulls in.
    env["VIBECOMFY_HEADLESS"] = "1"
    completed = subprocess.run(
        [sys.executable, "-c", code],
        check=False,
        capture_output=True,
        text=True,
        env=env,
    )

    assert completed.returncode == 0, completed.stderr


def test_serialize_executor_result_shapes_clarify_response_without_apply_fields() -> None:
    payload = {
        "ok": True,
        "route": "clarify",
        "reply": "Which model should I use?",
        "candidate": {"graph": {"nodes": []}},
        "candidate_graph": {"nodes": []},
        "graph": {"nodes": []},
        "apply_eligible": True,
        "apply_eligibility": {"applyable": True, "reason": "applyable"},
        "eligibility": {"applyable": True, "reason": "applyable"},
        "apply_allowed": True,
        "canvas_apply_allowed": True,
        "queue_allowed": True,
    }

    serialized = serialize_executor_result(payload)

    assert serialized == {
        "ok": True,
        "route": "clarify",
        "reply": "Which model should I use?",
        "message": "Which model should I use?",
        "graph_unchanged": False,
        "outcome": {
            "kind": "clarify",
            "question": "Which model should I use?",
            "clarification": {"message": "Which model should I use?"},
        },
        "clarification_required": True,
        "clarification_message": "Which model should I use?",
    }


def test_serialize_executor_result_strips_non_applyable_response_fields() -> None:
    payload = {
        "ok": True,
        "route": "requires_custom_nodes",
        "reply": "Install custom nodes before applying edits.",
        "outcome": {"kind": "requires_custom_nodes", "candidates": [{"expected_classes": ["VHS_VideoCombine"]}]},
        "candidate": {"graph": {"nodes": [{"id": 1}], "links": []}},
        "candidate_graph": {"nodes": [{"id": 1}], "links": []},
        "graph": {"nodes": [{"id": 1}], "links": []},
        "apply_eligible": True,
        "apply_eligibility": {"applyable": True, "reason": "applyable"},
        "eligibility": {"applyable": True, "reason": "applyable"},
        "apply_allowed": True,
        "canvas_apply_allowed": True,
        "queue_allowed": True,
    }

    serialized = serialize_executor_result(payload)

    assert serialized["outcome"] == payload["outcome"]
    for forbidden_key in (
        "candidate",
        "candidate_graph",
        "graph",
        "apply_eligible",
        "apply_eligibility",
        "eligibility",
        "apply_allowed",
        "canvas_apply_allowed",
        "queue_allowed",
    ):
        assert forbidden_key not in serialized


def test_routes_executor_serializer_matches_extracted_helper(monkeypatch) -> None:
    monkeypatch.setenv("VIBECOMFY_HEADLESS", "1")
    from vibecomfy.comfy_nodes.agent import routes

    payload = {
        "ok": True,
        "route": "clarify",
        "reply": "What style should I use?",
        "candidate": {"graph": {"nodes": []}},
        "apply_eligible": True,
    }

    assert _canonical_json(routes._serialize_executor_result(payload)) == _canonical_json(
        serialize_executor_result(payload)
    )


# ── Characterization: authority leak via non-durable executor results ──────

AUTHORITY_SYNTHESIS_KEYS = frozenset(
    {
        "apply_eligibility",
        "eligibility",
        "apply_allowed",
        "canvas_apply_allowed",
        "queue_allowed",
    }
)


def test_non_durable_executor_result_never_synthesizes_authority_fields() -> None:
    """Prove that executor compatibility does NOT mint authority fields.

    A non-durable executor result (no ``outcome``, ``apply_eligibility``,
    ``eligibility``, or durable ``graph``) arrives with ``apply_eligible=True``
    and a ``candidate`` graph.  The serializer may add presentation aliases
    (``message``, ``outcome.kind``) but MUST NOT invent authority claims
    like ``apply_allowed`` or ``canvas_apply_allowed`` — those are the edit
    engine's responsibility.
    """
    non_durable_payload: dict = {
        "ok": True,
        "route": "edit",
        "reply": "Here is the edit for you.",
        "candidate": {
            "graph": {"nodes": [{"id": 1}], "links": []},
        },
        "apply_eligible": True,
    }

    serialized = serialize_executor_result(non_durable_payload)

    leaked = AUTHORITY_SYNTHESIS_KEYS & serialized.keys()
    assert not leaked, (
        f"Non-durable executor result leaked authority fields: {sorted(leaked)}. "
        f"Full serialized keys: {sorted(serialized.keys())}"
    )


def test_non_durable_edit_result_preserves_presentation_aliases_only() -> None:
    """Non-durable edit results keep message/graph_unchanged but no authority."""
    non_durable_payload: dict = {
        "ok": True,
        "route": "edit",
        "reply": "Edited the seed value.",
        "candidate": {
            "graph": {"nodes": [{"id": 9}], "links": []},
        },
        "apply_eligible": True,
    }

    serialized = serialize_executor_result(non_durable_payload)

    # Presentation aliases are legitimate compatibility bridges.
    assert isinstance(serialized.get("message"), str)
    assert "message" in serialized
    assert "graph_unchanged" in serialized

    # Authority fields must not appear.
    assert "apply_eligibility" not in serialized
    assert "eligibility" not in serialized
    assert "apply_allowed" not in serialized
    assert "canvas_apply_allowed" not in serialized
    assert "queue_allowed" not in serialized


def test_non_durable_clarify_result_never_synthesizes_authority_fields() -> None:
    """Clarify routes also suppress authority synthesis from non-durable data."""
    non_durable_payload: dict = {
        "ok": True,
        "route": "clarify",
        "reply": "Which model should I use?",
        "candidate": {"graph": {"nodes": []}},
        "apply_eligible": True,
    }

    serialized = serialize_executor_result(non_durable_payload)

    leaked = AUTHORITY_SYNTHESIS_KEYS & serialized.keys()
    assert not leaked, (
        f"Non-durable clarify result leaked authority fields: {sorted(leaked)}"
    )


def test_non_durable_respond_result_never_synthesizes_authority_fields() -> None:
    """Respond routes also suppress authority synthesis from non-durable data."""
    non_durable_payload: dict = {
        "ok": True,
        "route": "respond",
        "reply": "Nothing to change right now.",
    }

    serialized = serialize_executor_result(non_durable_payload)

    leaked = AUTHORITY_SYNTHESIS_KEYS & serialized.keys()
    assert not leaked, (
        f"Non-durable respond result leaked authority fields: {sorted(leaked)}"
    )


# ── Batch 10: response carries Δ references; claims ⊆ accepted Δ ────────────


def test_serialize_executor_result_preserves_delta_references() -> None:
    """The response carries the canonical Δ references: the envelope and the
    derived ops view survive serialization unchanged."""
    envelope = {
        "schema_version": "2.0.0",
        "ops": [
            {
                "op": "set_node_field",
                "target": ["", "sampler", "steps"],
                "value": 30,
            }
        ],
    }
    payload: dict = {
        "ok": True,
        "route": "edit",
        "reply": "Changed sampler.steps from 20 to 30.",
        "delta_ops_envelope": envelope,
        "delta_ops": list(envelope["ops"]),
        "accepted_batch": [
            {
                "statement_index": 1,
                "source": 'set_field(uid="sampler", field="steps", value=30)',
                "op_kind": "edit",
                "touched_uids": ["sampler"],
            }
        ],
    }

    serialized = serialize_executor_result(payload)

    assert serialized["delta_ops_envelope"] == envelope
    assert serialized["delta_ops"] == envelope["ops"]
    assert serialized["accepted_batch"][0]["statement_index"] == 1


def test_reply_change_claims_must_reference_accepted_delta() -> None:
    """The reply-must-match-diff law: a claim about a non-landed statement is
    invalid; claims within the accepted Δ pass.  The canonical Δ source is
    ``accepted_batch`` only (batch 10) — legacy delta_ops_envelope views are
    never consulted."""
    from vibecomfy.executor.contracts import validate_reply_change_claims

    op = {
        "op": "set_node_field",
        "target": ["", "sampler", "steps"],
        "value": 30,
    }
    valid_response: dict = {
        "accepted_batch": [
            {
                "statement_index": 1,
                "source": 'set_field(uid="sampler", field="steps", value=30)',
                "op_kind": "edit",
                "touched_uids": ["sampler"],
                "op": op,
            }
        ],
        "change_details": {
            "operations": [
                {
                    "uid": "sampler",
                    "field_path": "steps",
                    "summary": "Changed sampler.steps from 20 to 30.",
                }
            ]
        },
    }
    assert validate_reply_change_claims(valid_response) == []

    invalid_response: dict = {
        "accepted_batch": [
            {
                "statement_index": 1,
                "source": 'set_field(uid="sampler", field="steps", value=30)',
                "op_kind": "edit",
                "touched_uids": ["sampler"],
                "op": op,
            }
        ],
        "change_details": {
            "operations": [
                {
                    "uid": "sampler",
                    "field_path": "seed",
                    "summary": "Changed sampler.seed from 42 to 99.",
                }
            ]
        },
    }
    violations = validate_reply_change_claims(invalid_response)
    assert len(violations) == 1
    assert "not in the accepted Δ" in violations[0]
