"""Action 5 — fence canonicalization + typed-refusal affordance.

d66a66 fence-miss: a lone ```python fence + done() is a valid batch.
Reply-lane typed refusals stay emit-able kinds, not untyped prose.
Staged inspect prompt: cite what is actually in the graph.
"""
from __future__ import annotations

import json

import pytest

from vibecomfy.comfy_nodes.agent import provider as agent_provider
from vibecomfy.executor.prompts import (
    build_reply_messages,
    parse_reply_payload,
    parse_reply_response,
)


def test_lone_python_fence_with_done_canonicalizes_to_batch() -> None:
    """d66a66: a lone ```python fence ending in done() is a valid batch."""
    text = (
        "Updating the export path.\n"
        "```python\n"
        "save.filename_prefix = \"mesh_out\"\n"
        "done()\n"
        "```\n"
    )
    provenance: dict = {}
    batch_code, prose = agent_provider.extract_batch_fence(
        text, parse_provenance=provenance
    )
    assert batch_code == 'save.filename_prefix = "mesh_out"\ndone()'
    assert "Updating the export path." in prose
    assert "save.filename_prefix" not in prose
    assert provenance == {
        "parse_reason": "canonicalized_python_fence",
        "fence_count": 1,
    }


def test_lone_python_fence_without_done_stays_missing_batch_fence() -> None:
    """Python fences that do not parse as a batch still fail closed."""
    text = "```python\nprint(\'hello\')\n```"
    with pytest.raises(agent_provider.MalformedModelJSON) as raised:
        agent_provider.extract_batch_fence(text)
    assert raised.value.parse_reason == "missing_batch_fence"


def test_python_fence_does_not_override_real_batch_fence() -> None:
    """A ```batch fence still wins when a Python fence is also present."""
    text = (
        "```python\nprint(\'hello\')\ndone()\n```\n"
        "```batch\nset_node_field(\'n1\', \'text\', \'new value\')\n```\n"
    )
    batch_code, prose = agent_provider.extract_batch_fence(text)
    assert batch_code == "set_node_field('n1', 'text', 'new value')"
    assert "print" in prose
    assert "done()" in prose


def test_two_python_fences_fail_closed() -> None:
    """Canonicalization is lone-fence only; two Python fences stay missing."""
    text = (
        "```python\nx = 1\ndone()\n```\n"
        "```python\ny = 2\ndone()\n```\n"
    )
    with pytest.raises(agent_provider.MalformedModelJSON) as raised:
        agent_provider.extract_batch_fence(text)
    assert raised.value.parse_reason == "missing_batch_fence"


def test_normalize_batch_response_records_python_fence_provenance() -> None:
    result = agent_provider._normalize_batch_response(
        "```python\ndone()\n```",
        route="test",
        model=None,
    )
    assert result.batch == "done()"
    assert result.audit_metadata["batch_parse"] == {
        "parse_reason": "canonicalized_python_fence",
        "fence_count": 1,
    }


def test_typed_refusal_payload_preserves_kind_and_classes() -> None:
    raw = json.dumps({
        "kind": "requires_custom_nodes",
        "missing_classes": ["HotshotXLLoader", "AnimateDiffLoader"],
        "reply": "HotshotXL is not in the current authoring surface.",
    })
    payload = parse_reply_payload(raw)
    assert payload.is_typed_refusal is True
    assert payload.kind == "requires_custom_nodes"
    assert payload.missing_classes == ("HotshotXLLoader", "AnimateDiffLoader")
    assert payload.text == "HotshotXL is not in the current authoring surface."
    assert parse_reply_response(raw) == payload.text


def test_typed_refusal_missing_runtime_classes_alias() -> None:
    raw = json.dumps({
        "kind": "requires_custom_nodes",
        "missing_runtime_classes": ["MTCNN"],
        "reply": "MTCNN is absent from the runtime class list.",
    })
    payload = parse_reply_payload(raw)
    assert payload.kind == "requires_custom_nodes"
    assert payload.missing_classes == ("MTCNN",)


def test_typed_refusal_without_prose_synthesizes_emit_able_text() -> None:
    """A kind + missing_classes envelope is emit-able even without reply prose."""
    raw = json.dumps({
        "kind": "requires_custom_nodes",
        "missing_classes": ["RetinaFace"],
    })
    payload = parse_reply_payload(raw)
    assert payload.is_typed_refusal is True
    assert payload.kind == "requires_custom_nodes"
    assert payload.missing_classes == ("RetinaFace",)
    assert "RetinaFace" in payload.text


def test_typed_clarify_refusal_uses_question() -> None:
    raw = json.dumps({
        "kind": "clarify",
        "question": "Which sampler should keep the existing steps?",
    })
    payload = parse_reply_payload(raw)
    assert payload.kind == "clarify"
    assert payload.text == "Which sampler should keep the existing steps?"


def test_untyped_noop_kind_is_not_a_typed_refusal() -> None:
    """Scoring noop as requires_custom_nodes is rejected; noop stays prose."""
    raw = json.dumps({
        "kind": "noop",
        "reply": "Nothing to change.",
    })
    payload = parse_reply_payload(raw)
    assert payload.is_typed_refusal is False
    assert payload.kind is None
    assert payload.text == "Nothing to change."


def test_typed_refusal_kind_without_evidence_still_fail_closed() -> None:
    raw = json.dumps({"kind": "requires_custom_nodes"})
    with pytest.raises(ValueError, match="reply"):
        parse_reply_payload(raw)


def test_reply_prompt_documents_typed_refusal_affordance() -> None:
    system = build_reply_messages("install hotshot")[0]["content"]
    assert "typed refusal" in system
    assert '"kind": "requires_custom_nodes"' in system
    assert "missing_classes" in system
    assert "untyped noop" in system


def test_staged_inspect_prompt_cites_what_is_actually_in_the_graph() -> None:
    msgs = build_reply_messages(
        "what encoder options does this graph use?",
        graph_inspection="1: VHS_VideoCombine widgets=[format=auto]",
        effective_route="inspect",
    )
    user = msgs[1]["content"]
    system = msgs[0]["content"]
    assert "cite what is actually in the graph" in user
    assert "cite what is actually in the graph" in system
    assert "do not invent parameters, codec families, bit depths" in user
    assert "VHS_VideoCombine widgets=[format=auto]" in user
