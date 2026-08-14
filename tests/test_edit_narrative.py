"""Unit tests for the post-validation narrative narrator.

Covers the _frag_narrator narrative synthesis (exported through the live
edit module) without invoking a real provider.
Tests exercise the fact-grounded prompt construction, deterministic fallback,
and the full _narrate_final_message entrypoint with mocked provider.
G0-T2: the agent ALWAYS writes the message — the LLM narrator runs for every
outcome and its message always ships; the deterministic fallback is used only
when no agent message exists (provider failure / timeout / malformed).
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
    _narrate_final_message,
    _net_field_changes,
    _total_landed_edit_count,
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


def test_total_landed_edit_count_includes_add_only_structural_edits() -> None:
    state = _make_state(
        batch_turns=[{
            "field_changes": [],
            "landed_op_count": 1,
            "delta_ops_envelope": {"ops": [{"op": "add_node"}]},
        }],
    )

    assert _total_landed_edit_count(state) == 1


def test_total_landed_edit_count_combines_fields_and_node_structure() -> None:
    state = _make_state(
        batch_field_changes=(
            FieldChange(uid="sampler", field_path="steps", old=20, new=30),
        ),
        batch_turns=[{
            "field_changes": [{"uid": "sampler", "field_path": "steps"}],
            "delta_ops_envelope": {
                "ops": [
                    {"op": "set_node_field"},
                    {"op": "add_node"},
                ],
            },
        }],
    )

    assert _total_landed_edit_count(state) == 2


def test_total_landed_edit_count_trusts_empty_canonical_envelope() -> None:
    state = _make_state(
        batch_turns=[{
            "field_changes": [],
            "landed_op_count": 1,
            "delta_ops": [{"op": "add_node"}],
            "delta_ops_envelope": {"ops": []},
        }],
    )

    assert _total_landed_edit_count(state) == 0


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


# ── Fact-grounded synthesis prompt (G0-T2) ──────────────────────────────────


class TestNarratorPromptFactGrounded:
    def test_system_prompt_requires_describing_structured_facts(self) -> None:
        from vibecomfy.comfy_nodes.agent.edit import _NARRATOR_SYSTEM_PROMPT
        prompt = _NARRATOR_SYSTEM_PROMPT
        assert "graph_unchanged" in prompt
        assert "outcome.kind" in prompt
        assert "landed_operation_count" in prompt
        assert "validation.passed" in prompt
        assert "Never claim an edit you did not land" in prompt
        assert "describe exactly those facts" in prompt

    def test_user_message_feeds_the_structured_outcome(self) -> None:
        """The narrator request embeds graph_unchanged, outcome.kind, and
        landed_operation_count so the agent writes the message FROM the facts."""
        ctx = _make_narrative_context(
            outcome={
                "kind": "candidate",
                "internal_kind": "edit",
                "public_kind": "candidate",
                "clarification_question": "",
            },
            change={
                "graph_changed": True,
                "graph_unchanged": False,
                "landed_operation_count": 2,
            },
            validation={"passed": True},
        )
        messages = _build_narrator_messages(ctx)
        content = messages[1]["content"]
        assert '"graph_unchanged": false' in content
        assert '"kind": "candidate"' in content
        assert '"landed_operation_count": 2' in content
        assert '"passed": true' in content


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
    def test_writes_context_and_validation_without_request_response(self, tmp_path: Path) -> None:
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
    def test_clean_success_calls_llm_and_ships_agent_message(
        self, tmp_path: Path, monkeypatch: pytest.MonkeyPatch,
    ) -> None:
        """G0-T2: even a clean edit success goes through the LLM narrator and
        the agent's message is the final message — no deterministic fast-path."""
        called_llm = False

        def _fake_run_model_turn(**kwargs: Any) -> dict[str, Any]:
            nonlocal called_llm
            called_llm = True
            return {"json": {"message": "Changed the save prefix to after."}}

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
        context = TurnContext(session_id="clean-success", turn_id="0001")
        for gate_name in context.gate_results:
            context.set_gate(gate_name, True)

        message = _narrate_final_message(
            state,
            context,
            outcome=TurnOutcome.edit(changes=state.batch_field_changes),
            public_outcome="candidate",
        )

        assert called_llm, "the agent (LLM narrator) must write every message"
        assert message == "Changed the save prefix to after."
        # Artifacts should be written on every path
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

    def test_unchanged_graph_edit_calls_llm_and_ships_message(
        self, tmp_path: Path, monkeypatch: pytest.MonkeyPatch,
    ) -> None:
        """Unchanged graph + edit outcome → the LLM narrator writes the message."""
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

    def test_failed_validation_calls_llm_and_ships_message(
        self, tmp_path: Path, monkeypatch: pytest.MonkeyPatch,
    ) -> None:
        """Failed validation → the LLM narrator still writes the message."""
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

    def test_llm_message_always_ships_even_when_prose_contradicts(
        self, tmp_path: Path, monkeypatch: pytest.MonkeyPatch,
    ) -> None:
        """G0-T2: the agent's message ALWAYS ships — no prose gate discards it.

        The LLM produces a message whose prose contradicts the outcome
        ("The graph is unchanged." for an edit that landed). Under the old
        deterministic guard this was discarded for a fallback; now it ships
        verbatim: scoring is structured-only and fact-grounding is enforced
        at the prompt, not by a discard-and-replace gate.
        """
        monkeypatch.setattr(
            "vibecomfy.comfy_nodes.agent.edit.run_model_turn",
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
        context = TurnContext(session_id="always-ship", turn_id="0001")
        for gate_name in context.gate_results:
            context.set_gate(gate_name, True)

        message = _narrate_final_message(
            state,
            context,
            outcome=TurnOutcome.edit(changes=state.batch_field_changes),
            public_outcome="candidate",
        )

        assert message == "The graph is unchanged."
        validation = json.loads(
            (state.turn_dir / "narrative_validation.json").read_text(encoding="utf-8")
        )
        assert validation["selected_source"] == "narrator"

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

    def test_artifact_write_failure_preserves_selected_agent_message(
        self, tmp_path: Path, monkeypatch: pytest.MonkeyPatch,
    ) -> None:
        """G0R: a raise from _write_narrative_artifacts must not replace the
        already-selected narrator message with the deterministic fallback.

        The write call sits inside the outer fallback catch; without the
        best-effort guard, a raising writer would discard the selected agent
        message and ship the deterministic fallback instead.
        """
        def _fake_run_model_turn(**kwargs: Any) -> dict[str, Any]:
            return {"json": {"message": "Changed the sampler seed to 42."}}

        monkeypatch.setattr(
            "vibecomfy.comfy_nodes.agent.edit.run_model_turn",
            _fake_run_model_turn,
        )

        def _failing_artifact_write(*args: Any, **kwargs: Any) -> None:
            raise RuntimeError("artifact write exploded")

        monkeypatch.setattr(
            "vibecomfy.comfy_nodes.agent.edit._write_narrative_artifacts",
            _failing_artifact_write,
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
        context = TurnContext(session_id="artifact-write-fail", turn_id="0001")
        for gate_name in context.gate_results:
            context.set_gate(gate_name, True)

        message = _narrate_final_message(
            state,
            context,
            outcome=TurnOutcome.edit(changes=state.batch_field_changes),
            public_outcome="candidate",
        )

        # The selected agent message ships unchanged — never the fallback.
        assert message == "Changed the sampler seed to 42."


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


# ── T14: Defensive narrator preserves durable state on catastrophic failure ──


class TestNarratorCatastrophicFallback:
    """Verify _narrate_final_message never raises — narration failure is presentation-only."""

    def test_unrecoverable_error_returns_deterministic_fallback(
        self, tmp_path: Path, monkeypatch: pytest.MonkeyPatch,
    ) -> None:
        """When an unexpected exception occurs inside the narrator,
        a deterministic fallback message is returned instead of crashing."""
        # Make _assemble_narrative_context raise an unexpected error.
        def _failing_assemble(*args: Any, **kwargs: Any) -> None:
            raise RuntimeError("simulated catastrophic narrator failure")

        monkeypatch.setattr(
            "vibecomfy.comfy_nodes.agent.edit._assemble_narrative_context",
            _failing_assemble,
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
        context = TurnContext(session_id="catastrophic", turn_id="0001")
        for gate_name in context.gate_results:
            context.set_gate(gate_name, True)

        # Must not raise — narration failure is presentation-only.
        message = _narrate_final_message(
            state,
            context,
            outcome=TurnOutcome.edit(changes=state.batch_field_changes),
            public_outcome="candidate",
        )

        assert isinstance(message, str)
        assert len(message) > 0
        # The message should be a deterministic fallback, not empty or an error.
        assert "after" in message.lower()
