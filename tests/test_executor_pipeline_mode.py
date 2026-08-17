"""B01 — two-step pipeline mode plumbing and dispatch toggle.

Covers ``PipelineMode`` coercion, resolution precedence (request > env >
default), typed request/configuration errors, ``ExecutorRequest`` and
``HeadlessAgentRequest`` round-trips, and the ``run_executor`` dispatch
seam (two-step branches to the execute stub; full mode is untouched).
"""

from __future__ import annotations

import pytest

from vibecomfy.agent.contracts import HeadlessAgentRequest
from vibecomfy.executor import two_step as two_step_module
from vibecomfy.executor.contracts import (
    DEFAULT_PIPELINE_MODE,
    PIPELINE_MODE_ENV_VAR,
    ClassifyDecision,
    ExecutorRequest,
    ExecutorResult,
    PipelineModeConfigurationError,
    PipelineModeRequestError,
    coerce_pipeline_mode,
    resolve_pipeline_mode,
)
from vibecomfy.executor.core import run_executor


# ── coerce_pipeline_mode ─────────────────────────────────────────────────────


class TestCoercePipelineMode:
    def test_none_passes_through(self) -> None:
        assert coerce_pipeline_mode(None) is None

    def test_valid_modes_round_trip(self) -> None:
        assert coerce_pipeline_mode("full") == "full"
        assert coerce_pipeline_mode("two_step") == "two_step"

    @pytest.mark.parametrize(
        "bad",
        ["bogus", "FULL", "Two_Step", " two_step", "full ", "", 42, 0, True, ["full"]],
    )
    def test_invalid_values_raise_request_error(self, bad: object) -> None:
        with pytest.raises(PipelineModeRequestError):
            coerce_pipeline_mode(bad)


# ── resolve_pipeline_mode ────────────────────────────────────────────────────


class TestResolvePipelineMode:
    def test_default_is_full(self) -> None:
        request = ExecutorRequest(query="x")
        assert resolve_pipeline_mode(request, environ={}) == DEFAULT_PIPELINE_MODE
        assert resolve_pipeline_mode(request, environ={}) == "full"

    def test_environment_beats_default(self) -> None:
        request = ExecutorRequest(query="x")
        resolved = resolve_pipeline_mode(
            request, environ={PIPELINE_MODE_ENV_VAR: "two_step"}
        )
        assert resolved == "two_step"

    def test_request_beats_environment(self) -> None:
        request = ExecutorRequest(query="x", pipeline_mode="full")
        resolved = resolve_pipeline_mode(
            request, environ={PIPELINE_MODE_ENV_VAR: "two_step"}
        )
        assert resolved == "full"

    def test_request_two_step_beats_environment_full(self) -> None:
        request = ExecutorRequest(query="x", pipeline_mode="two_step")
        resolved = resolve_pipeline_mode(
            request, environ={PIPELINE_MODE_ENV_VAR: "full"}
        )
        assert resolved == "two_step"

    def test_invalid_environment_value_is_configuration_error(self) -> None:
        request = ExecutorRequest(query="x")
        with pytest.raises(PipelineModeConfigurationError):
            resolve_pipeline_mode(request, environ={PIPELINE_MODE_ENV_VAR: "bogus"})

    def test_empty_environment_value_falls_back_to_default(self) -> None:
        request = ExecutorRequest(query="x")
        resolved = resolve_pipeline_mode(
            request, environ={PIPELINE_MODE_ENV_VAR: ""}
        )
        assert resolved == "full"

    def test_os_environ_used_when_environ_is_none(self, monkeypatch: pytest.MonkeyPatch) -> None:
        request = ExecutorRequest(query="x")
        monkeypatch.setenv(PIPELINE_MODE_ENV_VAR, "two_step")
        assert resolve_pipeline_mode(request) == "two_step"

    def test_os_environ_invalid_raises_configuration_error(
        self, monkeypatch: pytest.MonkeyPatch
    ) -> None:
        request = ExecutorRequest(query="x")
        monkeypatch.setenv(PIPELINE_MODE_ENV_VAR, "nope")
        with pytest.raises(PipelineModeConfigurationError):
            resolve_pipeline_mode(request)


# ── ExecutorRequest.pipeline_mode ────────────────────────────────────────────


class TestExecutorRequestPipelineMode:
    def test_round_trip_from_payload_to_dict(self) -> None:
        req = ExecutorRequest.from_payload({"query": "x", "pipeline_mode": "two_step"})
        assert req.pipeline_mode == "two_step"
        assert req.to_dict()["pipeline_mode"] == "two_step"

    def test_unspecified_is_omitted_from_to_dict(self) -> None:
        req = ExecutorRequest.from_payload({"query": "x"})
        assert req.pipeline_mode is None
        assert "pipeline_mode" not in req.to_dict()

    def test_direct_construction_accepts_valid_modes(self) -> None:
        assert ExecutorRequest(query="x", pipeline_mode="full").pipeline_mode == "full"
        assert (
            ExecutorRequest(query="x", pipeline_mode="two_step").pipeline_mode
            == "two_step"
        )

    def test_direct_construction_rejects_invalid_mode(self) -> None:
        with pytest.raises(PipelineModeRequestError):
            ExecutorRequest(query="x", pipeline_mode="bogus")

    def test_from_payload_rejects_invalid_mode(self) -> None:
        with pytest.raises(PipelineModeRequestError):
            ExecutorRequest.from_payload({"query": "x", "pipeline_mode": "bogus"})

    def test_explicit_null_is_omitted_from_to_dict(self) -> None:
        req = ExecutorRequest.from_payload({"query": "x", "pipeline_mode": None})
        assert req.pipeline_mode is None
        assert "pipeline_mode" not in req.to_dict()


# ── HeadlessAgentRequest.pipeline_mode ───────────────────────────────────────


class TestHeadlessAgentRequestPipelineMode:
    def test_carried_through_to_executor_request(self) -> None:
        headless = HeadlessAgentRequest.from_payload(
            {"query": "x", "pipeline_mode": "two_step"}
        )
        assert headless.pipeline_mode == "two_step"
        assert headless.to_executor_request().pipeline_mode == "two_step"

    def test_to_dict_round_trip(self) -> None:
        headless = HeadlessAgentRequest.from_payload(
            {"query": "x", "pipeline_mode": "two_step"}
        )
        assert headless.to_dict()["pipeline_mode"] == "two_step"
        plain = HeadlessAgentRequest.from_payload({"query": "x"})
        assert plain.pipeline_mode is None
        assert "pipeline_mode" not in plain.to_dict()

    def test_direct_construction_rejects_invalid_mode(self) -> None:
        with pytest.raises(PipelineModeRequestError):
            HeadlessAgentRequest(query="x", pipeline_mode="bogus")

    def test_from_payload_rejects_invalid_mode(self) -> None:
        with pytest.raises(PipelineModeRequestError):
            HeadlessAgentRequest.from_payload({"query": "x", "pipeline_mode": "bogus"})


# ── run_executor dispatch seam ───────────────────────────────────────────────


class TestRunExecutorDispatch:
    def test_two_step_request_field_dispatches_to_two_step(
        self, monkeypatch: pytest.MonkeyPatch
    ) -> None:
        decision = ClassifyDecision.edit(route="adapt", plan_summary="summary")
        monkeypatch.setattr(
            "vibecomfy.executor.core._run_classify",
            lambda *args, **kwargs: decision,
        )
        canned = ExecutorResult.success(reply="injected two-step outcome")

        captured: dict[str, object] = {}

        def fake_outcome(**kwargs: object) -> ExecutorResult:
            captured.update(kwargs)
            return canned

        monkeypatch.setattr(two_step_module, "_two_step_outcome", fake_outcome)
        # Full-mode phases must never run in two-step mode.
        monkeypatch.setattr(
            "vibecomfy.executor.core._run_agent_owned_research",
            lambda *args, **kwargs: pytest.fail("research must not run in two-step"),
        )
        monkeypatch.setattr(
            "vibecomfy.executor.core._run_implement",
            lambda *args, **kwargs: pytest.fail("implement must not run in two-step"),
        )
        monkeypatch.setattr(
            "vibecomfy.executor.core._run_reply",
            lambda *args, **kwargs: pytest.fail("reply must not run in two-step"),
        )

        result = run_executor(
            ExecutorRequest(query="adapt the graph", pipeline_mode="two_step")
        )

        assert result is canned
        assert captured["pipeline_mode"] == "two_step"
        assert captured["plan"] is decision
        assert captured["request"].pipeline_mode == "two_step"

    def test_two_step_environment_dispatches_to_two_step(
        self, monkeypatch: pytest.MonkeyPatch
    ) -> None:
        decision = ClassifyDecision.respond_only(route="respond")
        monkeypatch.setattr(
            "vibecomfy.executor.core._run_classify",
            lambda *args, **kwargs: decision,
        )
        canned = ExecutorResult.success(reply="env-injected two-step outcome")
        captured: list[dict[str, object]] = []

        def fake_outcome(**kwargs: object) -> ExecutorResult:
            captured.append(kwargs)
            return canned

        monkeypatch.setattr(two_step_module, "_two_step_outcome", fake_outcome)
        monkeypatch.setenv(PIPELINE_MODE_ENV_VAR, "two_step")

        result = run_executor(ExecutorRequest(query="hello"))

        assert result is canned
        assert captured[0]["pipeline_mode"] == "two_step"

    def test_full_mode_never_dispatches_to_two_step(
        self, monkeypatch: pytest.MonkeyPatch
    ) -> None:
        decision = ClassifyDecision.respond_only(route="respond")
        monkeypatch.setattr(
            "vibecomfy.executor.core._run_classify",
            lambda *args, **kwargs: decision,
        )
        monkeypatch.setattr(
            "vibecomfy.executor.core._run_reply",
            lambda *args, **kwargs: "full-mode reply",
        )
        monkeypatch.setattr(
            two_step_module,
            "_two_step_outcome",
            lambda **kwargs: pytest.fail("two-step must not run in full mode"),
        )

        result = run_executor(ExecutorRequest(query="hello"))

        assert result.ok is True
        assert result.reply == "full-mode reply"

    def test_invalid_environment_value_fails_fast_as_configuration_failure(
        self, monkeypatch: pytest.MonkeyPatch
    ) -> None:
        decision = ClassifyDecision.respond_only(route="respond")
        monkeypatch.setattr(
            "vibecomfy.executor.core._run_classify",
            lambda *args, **kwargs: decision,
        )
        monkeypatch.setattr(
            two_step_module,
            "_two_step_outcome",
            lambda **kwargs: pytest.fail("two-step must not run on bad env"),
        )
        monkeypatch.setenv(PIPELINE_MODE_ENV_VAR, "bogus")

        result = run_executor(ExecutorRequest(query="hello"))

        assert result.ok is False
        assert result.failure_stage == "configuration"
        assert "bogus" in (result.failure_message or "")

    def test_invalid_request_mode_rejected_at_construction(self) -> None:
        with pytest.raises(PipelineModeRequestError):
            ExecutorRequest(query="hello", pipeline_mode="sideways")
