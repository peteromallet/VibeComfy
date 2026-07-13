"""Unit tests for the post-validation narrative narrator.

Covers the new edit_narrator module without invoking a real provider.
Tests exercise the fast-path predicate, guard checks, deterministic fallback,
and the full _narrate_final_message entrypoint with mocked provider.
"""

from __future__ import annotations

import json
from pathlib import Path
from typing import Any
from unittest.mock import patch

import pytest

from vibecomfy.comfy_nodes.agent.edit import (
    AgentEditState,
    NarrativeContext,
    _assemble_narrative_context,
    _build_narrator_messages,
    _call_narrator_llm,
    _deterministic_narrative_fallback,
    _guard_narrative_message,
    _narrate_final_message,
    _narrator_fast_path_applies,
    _net_field_changes,
    _write_narrative_artifacts,
)
from vibecomfy.comfy_nodes.agent.contracts import (
    ApplyEligibility,
    FailureEnvelope,
    FailureKind,
    TurnContext,
    TurnOutcome,
)
from vibecomfy.comfy_nodes.agent.provider import (
    MalformedModelJSON,
    MissingRequiredField,
    ProviderError,
)
from vibecomfy.porting.edit.types import FieldChange


def test_net_field_changes_collapses_revisions_and_drops_reverted_edits() -> None:
    changes = (
        FieldChange(uid="prompt", field_path="text", old="calm", new="energetic"),
        FieldChange(uid="engine", field_path="emotion_control", old="options", new="qwen"),
        FieldChange(uid="prompt", field_path="text", old="calm", new="dramatic"),
        FieldChange(uid="engine", field_path="emotion_control", old="options", new="options"),
    )

    assert _net_field_changes(changes) == (
        FieldChange(uid="prompt", field_path="text", old="calm", new="dramatic"),
    )


# ── helpers ────────────────────────────────────────────────────────────────


def _narrative_context_payload_overrides(**overrides: Any) -> dict[str, Any]:
    """Build a minimal narrative context payload for guard testing."""
    defaults: dict[str, Any] = {
        "task": "test task",
        "route": "",
        "outcome": {
            "internal_kind": "edit",
            "public_kind": "candidate",
            "batch_exit_mode": "",
            "clarification_question": "",
        },
        "change": {
            "graph_changed": True,
            "landed_operation_count": 1,
            "operations": [],
        },
        "validation": {"passed": True},
        "apply_eligibility": {
            "applyable": True,
            "reason": "applyable",
            "message": "",
            "warnings": [],
        },
        "change_details": {},
        "diagnostics": {"delta": [], "lowering": []},
        "research": {},
        "revision": {},
    }
    defaults.update(overrides)
    return defaults


def _make_narrative_context(**overrides: Any) -> NarrativeContext:
    return NarrativeContext.from_dict(_narrative_context_payload_overrides(**overrides))


def _make_state(**overrides: Any) -> AgentEditState:
    """Create a minimal AgentEditState for narrative testing."""
    defaults: dict[str, Any] = {
        "task": "test task",
        "graph": {},
        "request_payload": {},
        "schema_provider": None,
        "baseline_graph_hash": None,
        "submit_graph_hash": None,
        "submit_structural_graph_hash": None,
        "submitted_client_graph_hash": None,
        "submitted_client_structural_graph_hash": None,
        "session_dir": Path("/tmp/test_narrative_session"),
        "turn_dir": Path("/tmp/test_narrative_session/turn_001"),
        "request_path": Path("/tmp/test_narrative_session/request.json"),
        "original_ui_path": Path("/tmp/test_narrative_session/original.json"),
        "before_py_path": Path("/tmp/test_narrative_session/before.py"),
        "after_py_path": Path("/tmp/test_narrative_session/after.py"),
        "projection_path": Path("/tmp/test_narrative_session/projection.json"),
        "model_request_path": Path("/tmp/test_narrative_session/model_request.json"),
        "model_response_path": Path("/tmp/test_narrative_session/model_response.json"),
        "candidate_ui_path": Path("/tmp/test_narrative_session/candidate.json"),
        "messages_path": Path("/tmp/test_narrative_session/messages.json"),
        "user_message": "",
        "raw_executor_message": "",
        "batch_field_changes": (),
        "batch_done_summary": "",
        "batch_final_summary": "",
        "batch_exit_mode": "",
        "narrative_context_path": Path("narrative_context.json"),
        "narrative_request_path": Path("narrative_request.json"),
        "narrative_response_path": Path("narrative_response.json"),
        "narrative_validation_path": Path("narrative_validation.json"),
        "artifacts": {},
    }
    defaults.update(overrides)
    return AgentEditState(**defaults)


# ── NarrativeContext dataclass ──────────────────────────────────────────────


class TestNarrativeContext:
    def test_basic_properties(self) -> None:
        ctx = _make_narrative_context(
            task="add a node",
            route="openrouter",
            outcome={"internal_kind": "edit", "public_kind": "candidate", "clarification_question": ""},
            change={"graph_changed": True, "landed_operation_count": 3},
            validation={"passed": True},
        )
        assert ctx.task == "add a node"
        assert ctx.route == "openrouter"
        assert ctx.internal_kind == "edit"
        assert ctx.public_kind == "candidate"
        assert ctx.graph_changed is True
        assert ctx.landed_operation_count == 3
        assert ctx.validation_passed is True
        assert ctx.failure_kind == ""
        assert ctx.clarification_question == ""

    def test_defaults_when_missing_payload_keys(self) -> None:
        ctx = NarrativeContext.from_dict({})
        assert ctx.task == ""
        assert ctx.route == ""
        assert ctx.internal_kind == ""
        assert ctx.public_kind == ""
        assert ctx.graph_changed is False
        assert ctx.landed_operation_count == 0
        assert ctx.validation_passed is False
        assert ctx.failure_kind == ""
        assert ctx.failure_message == ""
        assert ctx.apply_eligibility_applyable is False
        assert ctx.clarification_question == ""

    def test_failure_properties(self) -> None:
        ctx = _make_narrative_context(
            failure={
                "kind": "timeout",
                "stage": "research",
                "retryable": True,
                "graph_unchanged": True,
                "next_action": "retry",
                "message": "The provider timed out.",
            },
        )
        assert ctx.failure_kind == "timeout"
        assert ctx.failure_message == "The provider timed out."

    def test_apply_eligibility_property(self) -> None:
        ctx = _make_narrative_context(
            apply_eligibility={"applyable": True, "reason": "applyable", "message": "ok", "warnings": []},
        )
        assert ctx.apply_eligibility_applyable is True

        ctx2 = _make_narrative_context(
            apply_eligibility={"applyable": False, "reason": "no_candidate", "message": "nope", "warnings": []},
        )
        assert ctx2.apply_eligibility_applyable is False

    def test_to_dict_and_from_dict_roundtrip(self) -> None:
        payload = _narrative_context_payload_overrides()
        ctx = NarrativeContext.from_dict(payload)
        assert ctx.to_dict() == payload

    def test_clarification_question(self) -> None:
        ctx = _make_narrative_context(
            outcome={
                "internal_kind": "clarify",
                "public_kind": "clarify",
                "clarification_question": "Which node should I edit?",
            },
        )
        assert ctx.clarification_question == "Which node should I edit?"


# ── Fast-path predicate (SD1) ───────────────────────────────────────────────


class TestNarratorFastPath:
    def test_clean_edit_success_applies(self) -> None:
        ctx = _make_narrative_context(
            outcome={"internal_kind": "edit", "public_kind": "candidate", "clarification_question": ""},
            change={"graph_changed": True, "landed_operation_count": 2},
            validation={"passed": True},
        )
        assert _narrator_fast_path_applies(ctx) is True

    def test_not_edit_outcome_does_not_apply(self) -> None:
        for kind in ("clarify", "noop", "budget", "edit+clarify"):
            ctx = _make_narrative_context(
                outcome={"internal_kind": kind, "public_kind": kind, "clarification_question": ""},
            )
            assert _narrator_fast_path_applies(ctx) is False, f"kind={kind} should not fast-path"

    def test_graph_not_changed_does_not_apply(self) -> None:
        ctx = _make_narrative_context(
            change={"graph_changed": False, "landed_operation_count": 0},
        )
        assert _narrator_fast_path_applies(ctx) is False

    def test_zero_landed_ops_does_not_apply(self) -> None:
        ctx = _make_narrative_context(
            change={"graph_changed": True, "landed_operation_count": 0},
        )
        assert _narrator_fast_path_applies(ctx) is False

    def test_failed_validation_does_not_apply(self) -> None:
        ctx = _make_narrative_context(
            validation={"passed": False},
        )
        assert _narrator_fast_path_applies(ctx) is False

    def test_failure_kind_present_does_not_apply(self) -> None:
        ctx = _make_narrative_context(
            failure={"kind": "timeout", "message": "timed out"},
        )
        assert _narrator_fast_path_applies(ctx) is False

    def test_graph_changed_but_zero_landed_ops_does_not_apply(self) -> None:
        ctx = _make_narrative_context(
            change={"graph_changed": True, "landed_operation_count": 0},
        )
        assert _narrator_fast_path_applies(ctx) is False


# ── Guard checks ────────────────────────────────────────────────────────────


class TestGuardNarrativeMessage:
    def test_accepts_clean_edit_message(self) -> None:
        ctx = _make_narrative_context(
            outcome={"internal_kind": "edit", "public_kind": "candidate", "clarification_question": ""},
            change={"graph_changed": True, "landed_operation_count": 1},
            validation={"passed": True},
        )
        result = _guard_narrative_message("Changed the filename prefix on the SaveImage node.", ctx)
        assert result["ok"] is True
        assert result["issues"] == []

    def test_rejects_empty_message(self) -> None:
        ctx = _make_narrative_context()
        result = _guard_narrative_message("", ctx)
        assert result["ok"] is False
        assert "empty_message" in result["issues"]

    def test_rejects_gate_jargon(self) -> None:
        ctx = _make_narrative_context()
        result = _guard_narrative_message("Gate A passed and plan_validate_ok was true.", ctx)
        assert result["ok"] is False
        assert "exposed_gate_jargon" in result["issues"]

    def test_rejects_no_edit_claim_when_edit_outcome(self) -> None:
        ctx = _make_narrative_context(
            outcome={"internal_kind": "edit", "public_kind": "candidate", "clarification_question": ""},
            change={"graph_changed": True, "landed_operation_count": 2},
            validation={"passed": True},
        )
        result = _guard_narrative_message("The graph is unchanged.", ctx)
        assert result["ok"] is False
        assert "contradicts_edit_outcome" in result["issues"]
        # It should also flag that no edits were claimed when edits actually landed
        assert "claims_no_edit_when_edits_landed" in result["issues"]

    def test_rejects_edit_claim_when_no_edit_outcome(self) -> None:
        ctx = _make_narrative_context(
            outcome={"internal_kind": "noop", "public_kind": "noop", "clarification_question": ""},
            change={"graph_changed": False, "landed_operation_count": 0},
            validation={"passed": True},
        )
        result = _guard_narrative_message("Changed several nodes in the graph.", ctx)
        assert result["ok"] is False
        assert "contradicts_no_edit_outcome" in result["issues"]

    def test_rejects_edit_outcome_without_landed_operations(self) -> None:
        ctx = _make_narrative_context(
            outcome={"internal_kind": "edit", "public_kind": "candidate", "clarification_question": ""},
            change={"graph_changed": False, "landed_operation_count": 0},
            validation={"passed": True},
        )
        result = _guard_narrative_message("Everything is good.", ctx)
        assert result["ok"] is False
        assert "edit_outcome_without_landed_operations" in result["issues"]

    def test_rejects_incorrect_landed_operation_count(self) -> None:
        ctx = _make_narrative_context(
            outcome={"internal_kind": "edit", "public_kind": "candidate", "clarification_question": ""},
            change={"graph_changed": True, "landed_operation_count": 1},
            validation={"passed": True},
        )
        result = _guard_narrative_message("Applied 5 changes to the workflow.", ctx)
        assert result["ok"] is False
        assert "incorrect_landed_operation_count" in result["issues"]

    def test_rejects_validation_pass_claim_when_validation_failed(self) -> None:
        ctx = _make_narrative_context(
            validation={"passed": False},
        )
        result = _guard_narrative_message("Validation passed and the candidate is ready to apply.", ctx)
        assert result["ok"] is False
        assert "contradicts_validation_failure" in result["issues"]

    def test_rejects_validation_fail_claim_when_validation_passed(self) -> None:
        ctx = _make_narrative_context(
            validation={"passed": True},
        )
        result = _guard_narrative_message("Validation failed due to schema errors.", ctx)
        assert result["ok"] is False
        assert "contradicts_validation_success" in result["issues"]

    def test_rejects_clarify_without_question(self) -> None:
        ctx = _make_narrative_context(
            outcome={
                "internal_kind": "clarify",
                "public_kind": "clarify",
                "clarification_question": "Which node should I change?",
            },
            change={"graph_changed": False, "landed_operation_count": 0},
            validation={"passed": False},
        )
        result = _guard_narrative_message("I need one more detail before continuing.", ctx)
        assert result["ok"] is False
        assert "clarify_without_question" in result["issues"]
        assert "clarify_question_missing" in result["issues"]

    def test_accepts_clarify_with_question(self) -> None:
        ctx = _make_narrative_context(
            outcome={
                "internal_kind": "clarify",
                "public_kind": "clarify",
                "clarification_question": "Which node should I edit?",
            },
            change={"graph_changed": False, "landed_operation_count": 0},
            validation={"passed": False},
        )
        result = _guard_narrative_message(
            "Which node should I edit before continuing?", ctx,
        )
        assert result["ok"] is True
        assert result["issues"] == []

    def test_accepts_edit_clarify_with_question(self) -> None:
        ctx = _make_narrative_context(
            outcome={
                "internal_kind": "edit+clarify",
                "public_kind": "clarify",
                "clarification_question": "Should I also update the color?",
            },
            change={"graph_changed": True, "landed_operation_count": 3},
            validation={"passed": True},
        )
        result = _guard_narrative_message(
            "Applied 3 changes. Should I also update the color?", ctx,
        )
        assert result["ok"] is True


# ── Deterministic fallback ──────────────────────────────────────────────────


class TestDeterministicNarrativeFallback:
    def test_edit_outcome_produces_humanized_message(self, tmp_path: Path) -> None:
        state = _make_state(
            graph={"nodes": [{"id": 1, "type": "SaveImage"}]},
            ui_payload={"nodes": [{"id": 1, "type": "SaveImage"}]},
            batch_field_changes=(
                FieldChange(uid="1", field_path="filename_prefix", old="before", new="after"),
            ),
            batch_exit_mode="done",
            session_dir=tmp_path / "session",
            turn_dir=tmp_path / "turns" / "0001",
        )
        state.turn_dir.mkdir(parents=True, exist_ok=True)
        message = _deterministic_narrative_fallback(
            state,
            outcome=TurnOutcome.edit(changes=state.batch_field_changes),
        )
        assert len(message) > 0
        assert "after" in message

    def test_noop_outcome_produces_message(self, tmp_path: Path) -> None:
        state = _make_state(
            session_dir=tmp_path / "session",
            turn_dir=tmp_path / "turns" / "0001",
        )
        state.turn_dir.mkdir(parents=True, exist_ok=True)
        message = _deterministic_narrative_fallback(
            state,
            outcome=TurnOutcome.noop(),
        )
        assert len(message) > 0
        assert message[-1] in ".!?"

    def test_clarify_outcome_produces_question(self, tmp_path: Path) -> None:
        state = _make_state(
            session_dir=tmp_path / "session",
            turn_dir=tmp_path / "turns" / "0001",
        )
        state.turn_dir.mkdir(parents=True, exist_ok=True)
        message = _deterministic_narrative_fallback(
            state,
            outcome=TurnOutcome.clarify(question="Which file should I use?"),
        )
        assert "?" in message

    def test_failure_outcome_uses_failure_message(self, tmp_path: Path) -> None:
        state = _make_state(
            session_dir=tmp_path / "session",
            turn_dir=tmp_path / "turns" / "0001",
        )
        state.turn_dir.mkdir(parents=True, exist_ok=True)
        failure = FailureEnvelope(
            kind=FailureKind.TIMEOUT_ERROR,
            stage="research",
            retryable=True,
            next_action="retry",
            graph_unchanged=True,
            user_facing_message="The research timed out.",
        )
        message = _deterministic_narrative_fallback(
            state,
            failure=failure,
        )
        assert len(message) > 0


# ── Prompt construction ─────────────────────────────────────────────────────


class TestBuildNarratorMessages:
    def test_builds_system_and_user_messages(self) -> None:
        ctx = _make_narrative_context()
        messages = _build_narrator_messages(ctx)
        assert len(messages) == 2
        assert messages[0]["role"] == "system"
        assert messages[1]["role"] == "user"
        assert "narrative context" in messages[1]["content"].lower()
        assert "message" in messages[1]["content"].lower()

    def test_includes_raw_executor_message(self) -> None:
        ctx = _make_narrative_context()
        messages = _build_narrator_messages(ctx, raw_executor_message="executor text")
        assert "executor text" in messages[1]["content"]

    def test_includes_fallback_message(self) -> None:
        ctx = _make_narrative_context()
        messages = _build_narrator_messages(ctx, fallback_message="fallback ref")
        assert "fallback ref" in messages[1]["content"]


# ── Artifact writer ─────────────────────────────────────────────────────────


class TestWriteNarrativeArtifacts:
    def test_writes_context_and_validation_on_fast_path(self, tmp_path: Path) -> None:
        state = _make_state(
            session_dir=tmp_path / "session",
            turn_dir=tmp_path / "turns" / "0001",
            narrative_context_path=Path("narrative_context.json"),
            narrative_request_path=Path("narrative_request.json"),
            narrative_response_path=Path("narrative_response.json"),
            narrative_validation_path=Path("narrative_validation.json"),
        )
        state.turn_dir.mkdir(parents=True, exist_ok=True)
        ctx = _make_narrative_context()
        validation = {"ok": True, "message": "", "issues": []}
        _write_narrative_artifacts(state, ctx, validation)

        # context and validation always written
        assert (state.turn_dir / "narrative_context.json").is_file()
        assert (state.turn_dir / "narrative_validation.json").is_file()
        # request and response only when provided
        assert not (state.turn_dir / "narrative_request.json").is_file()
        assert not (state.turn_dir / "narrative_response.json").is_file()

    def test_writes_all_four_when_request_and_response_provided(self, tmp_path: Path) -> None:
        state = _make_state(
            session_dir=tmp_path / "session",
            turn_dir=tmp_path / "turns" / "0001",
            narrative_context_path=Path("narrative_context.json"),
            narrative_request_path=Path("narrative_request.json"),
            narrative_response_path=Path("narrative_response.json"),
            narrative_validation_path=Path("narrative_validation.json"),
        )
        state.turn_dir.mkdir(parents=True, exist_ok=True)
        ctx = _make_narrative_context()
        validation = {"ok": True, "message": "", "issues": []}
        request_messages = [{"role": "system", "content": "test"}]
        llm_response = {"json": {"message": "test"}}
        _write_narrative_artifacts(
            state, ctx, validation,
            request_messages=request_messages,
            llm_response=llm_response,
        )

        assert (state.turn_dir / "narrative_context.json").is_file()
        assert (state.turn_dir / "narrative_validation.json").is_file()
        assert (state.turn_dir / "narrator_request.json").is_file()
        assert (state.turn_dir / "narrator_response.json").is_file()

    def test_survives_unwritable_directory(self, tmp_path: Path) -> None:
        state = _make_state(
            session_dir=tmp_path / "session",
            turn_dir=tmp_path / "does_not_exist" / "readonly",
        )
        ctx = _make_narrative_context()
        validation = {"ok": True, "message": "", "issues": []}
        # Should not raise
        _write_narrative_artifacts(state, ctx, validation)


# ── Full _narrate_final_message entrypoint ──────────────────────────────────


class TestNarrateFinalMessage:
    def test_clean_success_uses_fast_path_and_skips_llm(
        self, tmp_path: Path, monkeypatch: pytest.MonkeyPatch,
    ) -> None:
        """SD1: clean edit success → fast-path, no LLM call."""
        called_llm = False

        def _fake_run_model_turn(**kwargs: Any) -> dict[str, Any]:
            nonlocal called_llm
            called_llm = True
            return {"json": {"message": "should not be used"}}

        monkeypatch.setattr(
            "vibecomfy.comfy_nodes.agent.edit.run_model_turn",
            _fake_run_model_turn,
        )

        state = _make_state(
            graph={"nodes": [{"id": 1, "type": "SaveImage"}]},
            ui_payload={"nodes": [{"id": 1, "type": "SaveImage"}]},
            batch_field_changes=(
                FieldChange(uid="1", field_path="filename_prefix", old="before", new="after"),
            ),
            batch_exit_mode="done",
            session_dir=tmp_path / "session",
            turn_dir=tmp_path / "turns" / "0001",
            narrative_context_path=Path("narrative_context.json"),
            narrative_request_path=Path("narrative_request.json"),
            narrative_response_path=Path("narrative_response.json"),
            narrative_validation_path=Path("narrative_validation.json"),
            artifacts={},
        )
        state.turn_dir.mkdir(parents=True, exist_ok=True)
        context = TurnContext(session_id="fast-path", turn_id="0001")
        for gate_name in context.gate_results:
            context.set_gate(gate_name, True)

        message = _narrate_final_message(
            state,
            context,
            outcome=TurnOutcome.edit(changes=state.batch_field_changes),
            public_outcome="candidate",
        )

        assert not called_llm, "LLM should not be called for clean edit success"
        assert len(message) > 0
        assert "after" in message
        # Artifacts should be written on fast-path
        assert (state.turn_dir / "narrative_context.json").is_file()
        assert (state.turn_dir / "narrative_validation.json").is_file()

    def test_provider_failure_falls_back_to_deterministic(
        self, tmp_path: Path, monkeypatch: pytest.MonkeyPatch,
    ) -> None:
        """Provider error → fallback to deterministic message."""
        monkeypatch.setattr(
            "vibecomfy.comfy_nodes.agent.edit.run_model_turn",
            lambda **_kwargs: (_ for _ in ()).throw(ProviderError("narrator offline")),
        )

        state = _make_state(
            graph={"nodes": [{"id": 1, "type": "SaveImage"}]},
            ui_payload={"nodes": [{"id": 1, "type": "SaveImage"}]},
            batch_field_changes=(
                FieldChange(uid="1", field_path="filename_prefix", old="before", new="after"),
            ),
            batch_exit_mode="done",
            session_dir=tmp_path / "session",
            turn_dir=tmp_path / "turns" / "0001",
            narrative_context_path=Path("narrative_context.json"),
            narrative_request_path=Path("narrative_request.json"),
            narrative_response_path=Path("narrative_response.json"),
            narrative_validation_path=Path("narrative_validation.json"),
            artifacts={},
        )
        state.turn_dir.mkdir(parents=True, exist_ok=True)
        context = TurnContext(session_id="provider-fail", turn_id="0001")
        for gate_name in context.gate_results:
            context.set_gate(gate_name, True)

        message = _narrate_final_message(
            state,
            context,
            outcome=TurnOutcome.edit(changes=state.batch_field_changes),
            public_outcome="candidate",
        )

        assert len(message) > 0
        assert "after" in message

    def test_malformed_response_falls_back_to_deterministic(
        self, tmp_path: Path, monkeypatch: pytest.MonkeyPatch,
    ) -> None:
        """Malformed LLM response → fallback to deterministic."""
        monkeypatch.setattr(
            "vibecomfy.comfy_nodes.agent.edit.run_model_turn",
            lambda **_kwargs: {"json": {}},  # empty json, missing "message"
        )

        state = _make_state(
            graph={"nodes": [{"id": 1, "type": "SaveImage"}]},
            ui_payload={"nodes": [{"id": 1, "type": "SaveImage"}]},
            batch_field_changes=(
                FieldChange(uid="1", field_path="filename_prefix", old="before", new="after"),
            ),
            batch_exit_mode="done",
            session_dir=tmp_path / "session",
            turn_dir=tmp_path / "turns" / "0001",
            narrative_context_path=Path("narrative_context.json"),
            narrative_request_path=Path("narrative_request.json"),
            narrative_response_path=Path("narrative_response.json"),
            narrative_validation_path=Path("narrative_validation.json"),
            artifacts={},
        )
        state.turn_dir.mkdir(parents=True, exist_ok=True)
        context = TurnContext(session_id="malformed", turn_id="0001")
        for gate_name in context.gate_results:
            context.set_gate(gate_name, True)

        message = _narrate_final_message(
            state,
            context,
            outcome=TurnOutcome.edit(changes=state.batch_field_changes),
            public_outcome="candidate",
        )

        assert len(message) > 0
        assert "after" in message

    def test_timeout_falls_back_to_deterministic(
        self, tmp_path: Path, monkeypatch: pytest.MonkeyPatch,
    ) -> None:
        """TimeoutError → fallback."""
        monkeypatch.setattr(
            "vibecomfy.comfy_nodes.agent.edit.run_model_turn",
            lambda **_kwargs: (_ for _ in ()).throw(TimeoutError("narrator timed out")),
        )

        state = _make_state(
            graph={"nodes": [{"id": 1, "type": "SaveImage"}]},
            ui_payload={"nodes": [{"id": 1, "type": "SaveImage"}]},
            batch_field_changes=(
                FieldChange(uid="1", field_path="filename_prefix", old="before", new="after"),
            ),
            batch_exit_mode="done",
            session_dir=tmp_path / "session",
            turn_dir=tmp_path / "turns" / "0001",
            narrative_context_path=Path("narrative_context.json"),
            narrative_request_path=Path("narrative_request.json"),
            narrative_response_path=Path("narrative_response.json"),
            narrative_validation_path=Path("narrative_validation.json"),
            artifacts={},
        )
        state.turn_dir.mkdir(parents=True, exist_ok=True)
        context = TurnContext(session_id="timeout", turn_id="0001")
        for gate_name in context.gate_results:
            context.set_gate(gate_name, True)

        message = _narrate_final_message(
            state,
            context,
            outcome=TurnOutcome.edit(changes=state.batch_field_changes),
            public_outcome="candidate",
        )

        assert len(message) > 0
        # Should have fallen back, not crashed
        assert "after" in message

    def test_unchanged_graph_edit_goes_to_llm_not_fast_path(
        self, tmp_path: Path, monkeypatch: pytest.MonkeyPatch,
    ) -> None:
        """Unchanged graph + edit outcome → not clean success → LLM path."""
        llm_called = False

        def _fake_run_model_turn(**kwargs: Any) -> dict[str, Any]:
            nonlocal llm_called
            llm_called = True
            return {"json": {"message": "The graph was already correct; no changes were needed."}}

        monkeypatch.setattr(
            "vibecomfy.comfy_nodes.agent.edit.run_model_turn",
            _fake_run_model_turn,
        )

        state = _make_state(
            graph={"nodes": [{"id": 1, "type": "SaveImage"}]},
            ui_payload={"nodes": [{"id": 1, "type": "SaveImage"}]},
            batch_exit_mode="done",
            session_dir=tmp_path / "session",
            turn_dir=tmp_path / "turns" / "0001",
            narrative_context_path=Path("narrative_context.json"),
            narrative_request_path=Path("narrative_request.json"),
            narrative_response_path=Path("narrative_response.json"),
            narrative_validation_path=Path("narrative_validation.json"),
            artifacts={},
        )
        state.turn_dir.mkdir(parents=True, exist_ok=True)
        context = TurnContext(session_id="unchanged", turn_id="0001")
        for gate_name in context.gate_results:
            context.set_gate(gate_name, True)

        message = _narrate_final_message(
            state,
            context,
            outcome=TurnOutcome.edit(changes=()),  # no changes
            public_outcome="candidate",
        )

        assert llm_called, "LLM should be called when graph is unchanged"
        assert len(message) > 0

    def test_failed_validation_goes_to_llm_not_fast_path(
        self, tmp_path: Path, monkeypatch: pytest.MonkeyPatch,
    ) -> None:
        """Failed validation → not clean success → LLM path."""
        llm_called = False

        def _fake_run_model_turn(**kwargs: Any) -> dict[str, Any]:
            nonlocal llm_called
            llm_called = True
            return {"json": {"message": "Validation failed; the candidate cannot be applied."}}

        monkeypatch.setattr(
            "vibecomfy.comfy_nodes.agent.edit.run_model_turn",
            _fake_run_model_turn,
        )

        state = _make_state(
            graph={"nodes": [{"id": 1, "type": "SaveImage"}]},
            ui_payload={"nodes": [{"id": 1, "type": "SaveImage"}]},
            batch_field_changes=(
                FieldChange(uid="1", field_path="filename_prefix", old="before", new="after"),
            ),
            batch_exit_mode="done",
            session_dir=tmp_path / "session",
            turn_dir=tmp_path / "turns" / "0001",
            narrative_context_path=Path("narrative_context.json"),
            narrative_request_path=Path("narrative_request.json"),
            narrative_response_path=Path("narrative_response.json"),
            narrative_validation_path=Path("narrative_validation.json"),
            artifacts={},
        )
        state.turn_dir.mkdir(parents=True, exist_ok=True)
        context = TurnContext(session_id="failed-val", turn_id="0001")
        # Set validation to fail
        for gate_name in context.gate_results:
            context.set_gate(gate_name, False)

        message = _narrate_final_message(
            state,
            context,
            outcome=TurnOutcome.edit(changes=state.batch_field_changes),
            public_outcome="candidate",
        )

        assert llm_called, "LLM should be called when validation fails"
        assert len(message) > 0

    def test_clarify_outcome_calls_llm_and_returns_question(
        self, tmp_path: Path, monkeypatch: pytest.MonkeyPatch,
    ) -> None:
        """Clarify outcome → LLM path with question-based guard."""
        monkeypatch.setattr(
            "vibecomfy.comfy_nodes.agent.edit.run_model_turn",
            lambda **_kwargs: {"json": {"message": "Which node should I edit next?"}},
        )

        state = _make_state(
            graph={"nodes": [{"id": 1, "type": "SaveImage"}]},
            ui_payload={"nodes": [{"id": 1, "type": "SaveImage"}]},
            session_dir=tmp_path / "session",
            turn_dir=tmp_path / "turns" / "0001",
            narrative_context_path=Path("narrative_context.json"),
            narrative_request_path=Path("narrative_request.json"),
            narrative_response_path=Path("narrative_response.json"),
            narrative_validation_path=Path("narrative_validation.json"),
            artifacts={},
        )
        state.turn_dir.mkdir(parents=True, exist_ok=True)
        context = TurnContext(session_id="clarify-llm", turn_id="0001")
        for gate_name in context.gate_results:
            context.set_gate(gate_name, True)

        message = _narrate_final_message(
            state,
            context,
            outcome=TurnOutcome.clarify(question="Which node should I edit next?"),
            public_outcome="clarify",
        )

        assert "?" in message

    def test_llm_message_failing_guard_falls_back(
        self, tmp_path: Path, monkeypatch: pytest.MonkeyPatch,
    ) -> None:
        """LLM produces a message that fails guard → fallback."""
        monkeypatch.setattr(
            "vibecomfy.comfy_nodes.agent.edit.run_model_turn",
            # LLM returns a message that contradicts the edit outcome
            lambda **_kwargs: {"json": {"message": "The graph is unchanged."}},
        )

        state = _make_state(
            graph={"nodes": [{"id": 1, "type": "SaveImage"}]},
            ui_payload={"nodes": [{"id": 1, "type": "SaveImage"}]},
            batch_field_changes=(
                FieldChange(uid="1", field_path="filename_prefix", old="before", new="after"),
            ),
            batch_exit_mode="done",
            session_dir=tmp_path / "session",
            turn_dir=tmp_path / "turns" / "0001",
            narrative_context_path=Path("narrative_context.json"),
            narrative_request_path=Path("narrative_request.json"),
            narrative_response_path=Path("narrative_response.json"),
            narrative_validation_path=Path("narrative_validation.json"),
            artifacts={},
        )
        state.turn_dir.mkdir(parents=True, exist_ok=True)
        context = TurnContext(session_id="guard-reject", turn_id="0001")
        for gate_name in context.gate_results:
            context.set_gate(gate_name, True)

        message = _narrate_final_message(
            state,
            context,
            outcome=TurnOutcome.edit(changes=state.batch_field_changes),
            public_outcome="candidate",
        )

        # Should have fallen back to deterministic, which includes the actual change
        assert "after" in message
        assert message != "The graph is unchanged."

    def test_raw_executor_message_not_published(
        self, tmp_path: Path, monkeypatch: pytest.MonkeyPatch,
    ) -> None:
        """Raw executor message is not used as the public message."""
        monkeypatch.setattr(
            "vibecomfy.comfy_nodes.agent.edit.run_model_turn",
            lambda **_kwargs: (_ for _ in ()).throw(ProviderError("offline")),
        )

        state = _make_state(
            graph={"nodes": [{"id": 1, "type": "SaveImage"}]},
            ui_payload={"nodes": [{"id": 1, "type": "SaveImage"}]},
            batch_field_changes=(
                FieldChange(uid="1", field_path="filename_prefix", old="before", new="after"),
            ),
            batch_exit_mode="done",
            raw_executor_message="Executor raw success line that must stay non-public.",
            session_dir=tmp_path / "session",
            turn_dir=tmp_path / "turns" / "0001",
            narrative_context_path=Path("narrative_context.json"),
            narrative_request_path=Path("narrative_request.json"),
            narrative_response_path=Path("narrative_response.json"),
            narrative_validation_path=Path("narrative_validation.json"),
            artifacts={},
        )
        state.turn_dir.mkdir(parents=True, exist_ok=True)
        context = TurnContext(session_id="executor-hidden", turn_id="0001")
        for gate_name in context.gate_results:
            context.set_gate(gate_name, True)

        message = _narrate_final_message(
            state,
            context,
            outcome=TurnOutcome.edit(changes=state.batch_field_changes),
            public_outcome="candidate",
        )

        assert message != state.raw_executor_message
        assert len(message) > 0

    def test_noop_outcome_goes_to_llm(
        self, tmp_path: Path, monkeypatch: pytest.MonkeyPatch,
    ) -> None:
        """Noop outcome → LLM path (not clean edit)."""
        llm_called = False

        def _fake_run_model_turn(**kwargs: Any) -> dict[str, Any]:
            nonlocal llm_called
            llm_called = True
            return {"json": {"message": "No changes were needed for this turn."}}

        monkeypatch.setattr(
            "vibecomfy.comfy_nodes.agent.edit.run_model_turn",
            _fake_run_model_turn,
        )

        state = _make_state(
            graph={"nodes": [{"id": 1, "type": "SaveImage"}]},
            ui_payload={"nodes": [{"id": 1, "type": "SaveImage"}]},
            session_dir=tmp_path / "session",
            turn_dir=tmp_path / "turns" / "0001",
            narrative_context_path=Path("narrative_context.json"),
            narrative_request_path=Path("narrative_request.json"),
            narrative_response_path=Path("narrative_response.json"),
            narrative_validation_path=Path("narrative_validation.json"),
            artifacts={},
        )
        state.turn_dir.mkdir(parents=True, exist_ok=True)
        context = TurnContext(session_id="noop-llm", turn_id="0001")
        for gate_name in context.gate_results:
            context.set_gate(gate_name, True)

        message = _narrate_final_message(
            state,
            context,
            outcome=TurnOutcome.noop(),
            public_outcome="noop",
        )

        assert llm_called
        assert len(message) > 0

    def test_artifacts_recorded_on_every_path(
        self, tmp_path: Path, monkeypatch: pytest.MonkeyPatch,
    ) -> None:
        """Every path records at minimum narrative_context.json + narrative_validation.json."""
        monkeypatch.setattr(
            "vibecomfy.comfy_nodes.agent.edit.run_model_turn",
            lambda **_kwargs: (_ for _ in ()).throw(ProviderError("offline")),
        )

        state = _make_state(
            graph={"nodes": [{"id": 1, "type": "SaveImage"}]},
            ui_payload={"nodes": [{"id": 1, "type": "SaveImage"}]},
            batch_field_changes=(
                FieldChange(uid="1", field_path="filename_prefix", old="before", new="after"),
            ),
            batch_exit_mode="done",
            session_dir=tmp_path / "session",
            turn_dir=tmp_path / "turns" / "0001",
            narrative_context_path=Path("narrative_context.json"),
            narrative_request_path=Path("narrative_request.json"),
            narrative_response_path=Path("narrative_response.json"),
            narrative_validation_path=Path("narrative_validation.json"),
            artifacts={},
        )
        state.turn_dir.mkdir(parents=True, exist_ok=True)
        context = TurnContext(session_id="artifacts-check", turn_id="0001")
        for gate_name in context.gate_results:
            context.set_gate(gate_name, True)

        _narrate_final_message(
            state,
            context,
            outcome=TurnOutcome.edit(changes=state.batch_field_changes),
            public_outcome="candidate",
        )

        assert (state.turn_dir / "narrative_context.json").is_file()
        assert (state.turn_dir / "narrative_validation.json").is_file()


# ── _assemble_narrative_context integration ────────────────────────────────


class TestAssembleNarrativeContext:
    def test_builds_context_from_state_and_context(self, tmp_path: Path) -> None:
        state = _make_state(
            graph={"nodes": [{"id": 1, "type": "SaveImage"}]},
            ui_payload={"nodes": [{"id": 1, "type": "SaveImage"}]},
            batch_field_changes=(
                FieldChange(uid="1", field_path="filename_prefix", old="before", new="after"),
            ),
            batch_exit_mode="done",
            task="change filename",
            route="openrouter",
            session_dir=tmp_path / "session",
            turn_dir=tmp_path / "turns" / "0001",
        )
        state.turn_dir.mkdir(parents=True, exist_ok=True)
        context = TurnContext(session_id="assemble", turn_id="0001")
        for gate_name in context.gate_results:
            context.set_gate(gate_name, True)

        ctx = _assemble_narrative_context(
            state,
            context,
            outcome=TurnOutcome.edit(changes=state.batch_field_changes),
            public_outcome="candidate",
        )

        assert isinstance(ctx, NarrativeContext)
        assert ctx.internal_kind == "edit"
        assert ctx.public_kind == "candidate"
        assert ctx.task == "change filename"
        assert ctx.route == "openrouter"


# ── Regression: misleading executor narrative (67785df94db647ca) ─────────


_REGRESSION_FIXTURE_PATH = (
    Path(__file__).resolve().parent
    / "fixtures"
    / "editor_sessions"
    / "67785df94db647ca"
    / "model_response.json"
)
_MISLEADING_PHRASES = (
    "We'll load",
    "We'll update",
    "create proper dual",
    "create dual‑prompt",
)


@pytest.fixture(scope="module")
def _regression_fixture_data() -> dict[str, Any]:
    raw = _REGRESSION_FIXTURE_PATH.read_text(encoding="utf-8")
    return json.loads(raw)


@pytest.fixture(scope="module")
def _regression_misleading_turn(_regression_fixture_data: dict[str, Any]) -> dict[str, Any]:
    """Return the failure turn with batch_ok=false and landed_op_count=0."""
    turns: list[dict[str, Any]] = _regression_fixture_data.get("turns", [])
    for turn in turns:
        br = turn.get("batch_result", {})
        if br.get("batch_ok") is False and br.get("landed_op_count") == 0:
            return turn
    raise AssertionError("No failure turn with batch_ok=false and landed_op_count=0 found in fixture")


class TestNarrativeRegression67785df94db647ca:
    """Regression test that the narrator does not publish misleading future-edit
    executor messages when the turn actually failed.

    The fixture ``tests/fixtures/editor_sessions/67785df94db647ca/model_response.json``
    contains a turn where ``batch_ok=false`` and ``landed_op_count=0`` but the
    raw executor message says *\"We'll load an SDXL checkpoint...\"* — describing
    what the executor *intended* to do, not the actual failure.  The narrator
    must never surface that misleading future-edit prose as the public message.
    """

    def test_fixture_encodes_required_facts(
        self, _regression_fixture_data: dict[str, Any],
    ) -> None:
        """Confirm the fixture itself encodes the regression scenario."""
        turns: list[dict[str, Any]] = _regression_fixture_data.get("turns", [])
        assert len(turns) >= 2, "Fixture must have at least two turns"

        found = False
        for turn in turns:
            br = turn.get("batch_result", {})
            if br.get("batch_ok") is False:
                found = True
                # batch_ok=false
                assert br.get("batch_ok") is False
                # landed_op_count=0
                assert br.get("landed_op_count") == 0
                # message contains future-edit "We'll" language
                msg = str(br.get("message", ""))
                assert any(phrase.lower() in msg.lower() for phrase in _MISLEADING_PHRASES), (
                    f"Misleading future-edit message not found in: {msg[:120]}"
                )
                break
        assert found, "Fixture must contain a turn with batch_ok=false"

    def test_regression_narrator_does_not_publish_misleading_message(
        self,
        _regression_misleading_turn: dict[str, Any],
        tmp_path: Path,
    ) -> None:
        """The narrated message must report the actual failure, not future intended edits."""
        br = _regression_misleading_turn["batch_result"]
        misleading_msg = str(br.get("message", ""))

        state = _make_state(
            graph={"nodes": [{"id": 1, "type": "SaveImage"}]},
            ui_payload={"nodes": [{"id": 1, "type": "SaveImage"}]},
            raw_executor_message=misleading_msg,
            batch_exit_mode="done",
            user_message="switch to SDXL",
            session_dir=tmp_path / "session",
            turn_dir=tmp_path / "turns" / "0001",
        )
        state.turn_dir.mkdir(parents=True, exist_ok=True)

        failure = FailureEnvelope(
            kind=FailureKind.LOWERING_FAILURE,
            stage="lowering",
            retryable=True,
            next_action="retry",
            graph_unchanged=True,
            user_facing_message="The batch could not be applied because several statements "
            "used unsupported expression syntax.",
        )

        context = TurnContext(session_id="67785df94db647ca", turn_id="0001")
        for gate_name in context.gate_results:
            context.set_gate(gate_name, True)

        message = _narrate_final_message(
            state,
            context,
            failure=failure,
            public_outcome="failure",
        )

        # ── Assertions ──────────────────────────────────────────────────
        # 1. The misleading future-edit prose must never appear.
        for phrase in _MISLEADING_PHRASES:
            assert phrase.lower() not in message.lower(), (
                f"Misleading phrase {phrase!r} leaked into narrated message: {message}"
            )

        # 2. The raw executor message itself must not be published verbatim.
        assert message != misleading_msg, (
            "Raw misleading executor message was published as-is"
        )

        # 3. The message must mention the failure / what actually went wrong.
        assert len(message) > 0
        assert "unsupported" in message.lower() or "could not" in message.lower() or \
            "failed" in message.lower() or "error" in message.lower(), (
            f"Narrated message does not describe the failure: {message}"
        )
