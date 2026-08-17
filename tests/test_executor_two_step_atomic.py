"""B04 — atomic edit state machine.

Covers the execute state machine: research/tool continuations may precede
editing; exactly ONE complete Python batch may be accepted; one replacement is
allowed ONLY after rejection; after acceptance further edits are denied; a
second rejection returns no candidate; and parse / resolution / CAS / channel /
bounds / done-gate failures return zero Δ.  Also exercises the
``EditSession.apply_batch`` reuse (never an independent parse/interpret).
"""

from __future__ import annotations

from typing import Any

import pytest

from vibecomfy.executor.two_step import (
    ApplyBatchOutcome,
    TwoStepApplyResult,
    TwoStepEditStateMachine,
    apply_python_batch,
)


def _ok(graph: Any = {"nodes": []}, reason: str = "accepted") -> ApplyBatchOutcome:
    return ApplyBatchOutcome(ok=True, landed_ops=("op",), graph=graph, reason=reason)


def _reject(reason: str, diagnostics: tuple[str, ...] = ()) -> ApplyBatchOutcome:
    return ApplyBatchOutcome(ok=False, reason=reason, diagnostics=diagnostics)


def _machine(responses: list[ApplyBatchOutcome]) -> TwoStepEditStateMachine:
    def apply_fn(code: str) -> ApplyBatchOutcome:
        return responses.pop(0)

    return TwoStepEditStateMachine(apply_fn=apply_fn)


# ── lifecycle ────────────────────────────────────────────────────────────────


def test_first_batch_accepts() -> None:
    machine = _machine([_ok()])
    result = machine.submit("cliptextencode.text = 'hi'")
    assert result.accepted is True
    assert result.delta_ids == ("d1",)
    assert machine.accepted is True
    assert machine.accepted_delta_ids == ("d1",)


def test_after_acceptance_further_edits_denied() -> None:
    machine = _machine([_ok()])
    machine.submit("code1")
    result = machine.submit("code2")
    assert result.accepted is False
    assert result.reason == "edit_already_accepted"


def test_first_rejection_allows_one_replacement() -> None:
    machine = _machine([_reject("unknown_target_field"), _ok()])
    first = machine.submit("bad")
    assert first.accepted is False
    assert first.replacement_allowed is True
    assert first.no_candidate is False
    second = machine.submit("fixed")
    assert second.accepted is True
    assert machine.replacement_used is True


def test_replacement_not_allowed_without_rejection() -> None:
    machine = _machine([_ok()])
    machine.submit("good")
    # A second batch after acceptance is denied outright (never a replacement).
    denied = machine.submit("another")
    assert denied.reason == "edit_already_accepted"


def test_two_rejections_return_no_candidate() -> None:
    machine = _machine([_reject("a"), _reject("b")])
    first = machine.submit("one")
    assert first.accepted is False
    assert first.replacement_allowed is True
    second = machine.submit("two")
    assert second.accepted is False
    assert second.replacement_allowed is False
    assert second.no_candidate is True
    # Any further submission is denied with no candidate.
    third = machine.submit("three")
    assert third.accepted is False
    assert third.no_candidate is True


# ── zero-Δ failure modes (each maps to a rejection, never a partial accept) ──


@pytest.mark.parametrize(
    "reason",
    [
        "stale_baseline",
        "unknown_schema",
        "unknown_target_field",  # socket/literal mismatch
        "batch_failed",  # invalid mixed batch
        "batch_too_large",  # bounds
    ],
)
def test_failure_modes_return_zero_delta(reason: str) -> None:
    machine = _machine([_reject(reason)])
    result = machine.submit("code")
    assert result.accepted is False
    assert result.delta_ids == ()
    assert result.graph is None
    assert result.reason == reason


def test_done_gate_failure_returns_zero_delta() -> None:
    # apply_batch succeeds (ok, landed, apply_eligible) but the done-gate fails.
    machine = _machine([_reject("done_gate_failed")])
    result = machine.submit("code")
    assert result.accepted is False
    assert result.delta_ids == ()
    assert result.reason == "done_gate_failed"


# ── reuse of EditSession.apply_batch as the authority ────────────────────────


class _FlatProvider:
    def get_schema(self, ct: str) -> Any:
        if ct != "CLIPTextEncode":
            return None
        from vibecomfy.schema import InputSpec, NodeSchema, OutputSpec

        return NodeSchema(
            "CLIPTextEncode",
            "core",
            {"text": InputSpec("STRING"), "clip": InputSpec("CLIP")},
            [OutputSpec("CONDITIONING", "CONDITIONING")],
        )


def _flat_ui() -> dict[str, Any]:
    import json
    from pathlib import Path

    path = Path("tests/fixtures/agent_edit/flat.json")
    return json.loads(path.read_text(encoding="utf-8"))


def _edit_session() -> Any:
    from vibecomfy.porting.edit.session import EditSession

    return EditSession(_flat_ui(), schema_provider=_FlatProvider())


def test_apply_python_batch_accepts_a_valid_batch() -> None:
    session = _edit_session()
    outcome = apply_python_batch(session, 'cliptextencode.text = "a faithful edited prompt"')
    assert outcome.ok is True
    assert outcome.landed_ops != ()
    assert outcome.graph is not None


def test_apply_python_batch_rejects_unknown_schema_with_zero_delta() -> None:
    session = _edit_session()
    outcome = apply_python_batch(session, 'unknownnode.field = "x"')
    assert outcome.ok is False
    assert outcome.landed_ops == ()
    assert outcome.graph is None


def test_apply_python_batch_done_gate_failure_rolls_back() -> None:
    session = _edit_session()
    before = len(session.landed_ops)

    class _FailedDone:
        ok = False
        summary = "done_gate_a_mismatch"

    outcome = apply_python_batch(
        session,
        'cliptextencode.text = "a faithful edited prompt"',
        done_fn=lambda: _FailedDone(),
    )
    assert outcome.ok is False
    assert outcome.reason == "done_gate_failed"
    # The just-applied batch was rolled back: zero Δ retained.
    assert len(session.landed_ops) == before


# ── research continuations may precede editing ───────────────────────────────


def test_research_attempt_derivation_for_timeout_empty_result() -> None:
    from vibecomfy.executor.two_step_session import derive_research_attempt

    # A research timeout that recorded no evidence is "empty", never "grounded".
    assert derive_research_attempt([{"tool": "hivemind_search", "evidence_ids": []}]) == "empty"
    assert derive_research_attempt([]) == "never"
