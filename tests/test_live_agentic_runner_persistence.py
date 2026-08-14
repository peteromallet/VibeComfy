from __future__ import annotations

import json
import subprocess
from pathlib import Path

import pytest

from tests.live_agentic_harness.runner import (
    _is_retryable_infra_summary,
    _persist_run_summary,
    _persist_scenario_summary,
    _provider_infra_failure_class,
    run_tag,
)
from tests.live_agentic_harness.scenario_manifest import write_manifest
from vibecomfy.executor.contracts import coerce_model_attempts


def _summary(tmp_path: Path, scenario_id: str, *, ok: bool) -> dict:
    output_dir = tmp_path / "tag" / scenario_id
    return {
        "scenario_id": scenario_id,
        "status": "success" if ok else "error",
        "output_dir": str(output_dir),
        "guard": {"live_agentic_success": ok},
        "deepseek_usage": {},
        "deepseek_est_cost_usd": 0.0,
        "deepseek_cost_basis": "not_available",
        "model_attempts": [],
    }


def _failed_attempt(failure_type: str, *, completion_tokens: int = 0) -> dict:
    return {
        "phase": "classify",
        "attempt": 1,
        "outcome": "failure",
        "failure_type": failure_type,
        "requested_model": "requested",
        "resolved_model": "resolved",
        "adapter": "hermes",
        "provider": "openrouter",
        "transport": "openrouter",
        "endpoint": "https://openrouter.ai/api/v1",
        "finish_reason": "unknown",
        "token_usage": {
            "prompt_tokens": 10,
            "completion_tokens": completion_tokens,
            "total_tokens": 10 + completion_tokens,
        },
    }


def test_persists_per_scenario_and_incremental_run_summary(tmp_path: Path) -> None:
    passing = _summary(tmp_path, "passing", ok=True)
    failing = _summary(tmp_path, "failing", ok=False)

    _persist_scenario_summary(passing, tmp_path, "tag")
    _persist_scenario_summary(failing, tmp_path, "tag")
    partial = _persist_run_summary(
        "tag",
        [passing, failing, None],
        tmp_path,
        total_scenarios=3,
        complete=False,
    )

    assert partial["passed"] == 1
    assert partial["failed"] == 1
    assert partial["pending"] == 1
    assert partial["complete"] is False
    assert (tmp_path / "tag" / "passing" / "agentic_summary.json").exists()
    assert (tmp_path / "tag" / "failing" / "agentic_summary.json").exists()
    assert (tmp_path / "tag" / "run_summary.partial.json").exists()

    persisted = json.loads((tmp_path / "tag" / "run_summary.partial.json").read_text())
    assert persisted["passed"] == 1
    assert persisted["failed"] == 1


def test_final_summary_replaces_partial_summary(tmp_path: Path) -> None:
    passing = _summary(tmp_path, "passing", ok=True)

    _persist_run_summary("tag", [passing], tmp_path, total_scenarios=1, complete=False)
    final = _persist_run_summary("tag", [passing], tmp_path, total_scenarios=1, complete=True)

    assert final["complete"] is True
    assert final["overall_success"] is True
    assert (tmp_path / "tag" / "run_summary.json").exists()
    assert not (tmp_path / "tag" / "run_summary.partial.json").exists()


def test_runner_does_not_retry_outer_timeout(
    tmp_path: Path,
    monkeypatch,
) -> None:  # noqa: ANN001
    scenarios_dir = tmp_path / "scenarios"
    scenarios_dir.mkdir()
    scenario_path = scenarios_dir / "retry-me.json"
    scenario_path.write_text(json.dumps({"id": "retry-me", "query": "do it"}), encoding="utf-8")

    calls = 0

    def fake_run(cmd, **kwargs):  # noqa: ANN001, ANN202
        nonlocal calls
        calls += 1
        if calls == 1:
            raise subprocess.TimeoutExpired(cmd=cmd, timeout=kwargs.get("timeout"))
        out_file = Path(cmd[cmd.index("--single-out") + 1])
        tag = cmd[cmd.index("--tag") + 1]
        output_dir = tmp_path / "out" / tag / "retry-me"
        payload = _summary(tmp_path / "out" / tag, "retry-me", ok=True)
        payload["output_dir"] = str(output_dir)
        out_file.write_text(json.dumps(payload), encoding="utf-8")
        return (0, "", "")

    write_manifest(scenarios_dir)
    monkeypatch.setattr("tests.live_agentic_harness.runner._run_scenario_subprocess", fake_run)

    summary = run_tag(
        "tag",
        scenarios_dir=scenarios_dir,
        output_base=tmp_path / "out",
        max_workers=1,
        per_scenario_timeout=1,
        infra_retries=1,
        progress_every=0,
    )

    scenario = summary["scenarios"][0]
    assert calls == 1
    assert summary["passed"] == 0
    assert summary["raw_first_attempt_passed"] == 0
    assert scenario["attempt_count"] == 1
    assert scenario["attempts"][0]["failure_class"] == "infra_timeout"
    assert scenario["attempts"][0]["score_class"] == "infra_blocked"
    assert scenario["attempts"][0]["retryable_infra"] is False
    assert scenario["attempts"][0]["agent_exercised"] is False
    assert scenario["attempts"][0]["elapsed_s"] is not None
    assert (
        tmp_path / "out" / "tag" / "retry-me" / "agentic_summary.json"
    ).exists()


def test_runner_types_provider_capacity_without_retry(
    tmp_path: Path,
    monkeypatch,
) -> None:  # noqa: ANN001
    scenarios_dir = tmp_path / "scenarios"
    scenarios_dir.mkdir()
    scenario_path = scenarios_dir / "provider-capacity.json"
    scenario_path.write_text(
        json.dumps({"id": "provider-capacity", "query": "do it"}),
        encoding="utf-8",
    )

    calls = 0

    def fake_run(cmd, **kwargs):  # noqa: ANN001, ANN202, ARG001
        nonlocal calls
        calls += 1
        out_file = Path(cmd[cmd.index("--single-out") + 1])
        tag = cmd[cmd.index("--tag") + 1]
        output_dir = tmp_path / "out" / tag / "provider-capacity"
        if calls == 1:
            payload = _summary(tmp_path / "out" / tag, "provider-capacity", ok=False)
            payload.update(
                {
                    "status": "executor_failure",
                    "error": (
                        "OpenRouter rejected the request because the account does "
                        "not have enough credits for the requested token budget."
                    ),
                    "output_dir": str(output_dir),
                    "model_attempts": [_failed_attempt("provider_failure")],
                    "guard": {
                        "live_agentic_success": False,
                        "score_class": "product_fail",
                        "assessment": {
                            "passed": False,
                            "issues": [
                                {
                                    "check": "response_ok",
                                    "severity": "error",
                                    "detail": (
                                        "response.ok is False: OpenRouter rejected "
                                        "the request because the account does not "
                                        "have enough credits for the requested token budget."
                                    ),
                                }
                            ],
                        },
                    },
                }
            )
        else:
            payload = _summary(tmp_path / "out" / tag, "provider-capacity", ok=True)
            payload["output_dir"] = str(output_dir)
        out_file.write_text(json.dumps(payload), encoding="utf-8")
        return (0, "", "")

    write_manifest(scenarios_dir)
    monkeypatch.setattr("tests.live_agentic_harness.runner._run_scenario_subprocess", fake_run)

    summary = run_tag(
        "tag",
        scenarios_dir=scenarios_dir,
        output_base=tmp_path / "out",
        max_workers=1,
        per_scenario_timeout=1,
        infra_retries=1,
        progress_every=0,
    )

    scenario = summary["scenarios"][0]
    assert calls == 1
    assert summary["passed"] == 0
    assert summary["raw_first_attempt_passed"] == 0
    assert scenario["attempt_count"] == 1
    assert scenario["attempts"][0]["failure_class"] == "infra_provider_capacity"
    assert scenario["attempts"][0]["score_class"] == "infra_blocked"
    assert scenario["attempts"][0]["retryable_infra"] is False


def test_runner_retries_only_typed_empty_zero_token_attempt(
    tmp_path: Path,
    monkeypatch,
) -> None:  # noqa: ANN001
    scenarios_dir = tmp_path / "scenarios"
    scenarios_dir.mkdir()
    scenario_path = scenarios_dir / "typed-empty.json"
    scenario_path.write_text(json.dumps({"id": "typed-empty", "query": "do it"}), encoding="utf-8")
    calls = 0

    def fake_run(cmd, **kwargs):  # noqa: ANN001, ANN202, ARG001
        nonlocal calls
        calls += 1
        out_file = Path(cmd[cmd.index("--single-out") + 1])
        tag = cmd[cmd.index("--tag") + 1]
        payload = _summary(tmp_path / "out" / tag, "typed-empty", ok=calls > 1)
        payload["output_dir"] = str(tmp_path / "out" / tag / "typed-empty")
        if calls == 1:
            payload["error"] = "arbitrary wording that must not drive classification"
            payload["model_attempts"] = [_failed_attempt("empty_response", completion_tokens=0)]
        out_file.write_text(json.dumps(payload), encoding="utf-8")
        return (0, "", "")

    write_manifest(scenarios_dir)
    monkeypatch.setattr("tests.live_agentic_harness.runner._run_scenario_subprocess", fake_run)

    summary = run_tag(
        "tag",
        scenarios_dir=scenarios_dir,
        output_base=tmp_path / "out",
        max_workers=1,
        infra_retries=1,
        progress_every=0,
    )

    scenario = summary["scenarios"][0]
    assert calls == 2
    assert scenario["attempts"][0]["failure_class"] == "infra_empty_response"
    assert scenario["attempts"][0]["model_attempts"][0]["failure_type"] == "empty_response"
    assert scenario["attempts"][1]["live_agentic_success"] is True


def test_runner_keeps_malformed_nonempty_as_product_failure(
    tmp_path: Path,
    monkeypatch,
) -> None:  # noqa: ANN001
    scenarios_dir = tmp_path / "scenarios"
    scenarios_dir.mkdir()
    scenario_path = scenarios_dir / "malformed.json"
    scenario_path.write_text(json.dumps({"id": "malformed", "query": "do it"}), encoding="utf-8")
    calls = 0

    def fake_run(cmd, **kwargs):  # noqa: ANN001, ANN202, ARG001
        nonlocal calls
        calls += 1
        out_file = Path(cmd[cmd.index("--single-out") + 1])
        tag = cmd[cmd.index("--tag") + 1]
        payload = _summary(tmp_path / "out" / tag, "malformed", ok=False)
        payload["output_dir"] = str(tmp_path / "out" / tag / "malformed")
        payload["error"] = "OpenRouter rejected / HTTP 429 wording is irrelevant"
        payload["model_attempts"] = [_failed_attempt("malformed_json", completion_tokens=5)]
        out_file.write_text(json.dumps(payload), encoding="utf-8")
        return (1, "", "")

    write_manifest(scenarios_dir)
    monkeypatch.setattr("tests.live_agentic_harness.runner._run_scenario_subprocess", fake_run)

    summary = run_tag(
        "tag",
        scenarios_dir=scenarios_dir,
        output_base=tmp_path / "out",
        max_workers=1,
        infra_retries=1,
        progress_every=0,
    )

    scenario = summary["scenarios"][0]
    assert calls == 1
    assert scenario["score_class"] == "product_fail"
    assert scenario.get("retryable_infra") is not True


def test_runner_counts_persistent_provider_capacity_as_infra_blocked(
    tmp_path: Path,
    monkeypatch,
) -> None:  # noqa: ANN001
    scenarios_dir = tmp_path / "scenarios"
    scenarios_dir.mkdir()
    scenario_path = scenarios_dir / "provider-down.json"
    scenario_path.write_text(json.dumps({"id": "provider-down", "query": "do it"}), encoding="utf-8")

    def fake_run(cmd, **kwargs):  # noqa: ANN001, ANN202, ARG001
        out_file = Path(cmd[cmd.index("--single-out") + 1])
        tag = cmd[cmd.index("--tag") + 1]
        output_dir = tmp_path / "out" / tag / "provider-down"
        payload = _summary(tmp_path / "out" / tag, "provider-down", ok=False)
        payload.update(
            {
                "status": "executor_failure",
                "error": "HTTP Error 429: Too Many Requests",
                "output_dir": str(output_dir),
                "model_attempts": [_failed_attempt("provider_failure")],
                "guard": {
                    "live_agentic_success": False,
                    "score_class": "product_fail",
                    "assessment": {"passed": False, "issues": []},
                },
            }
        )
        out_file.write_text(json.dumps(payload), encoding="utf-8")
        return (1, "", "")

    write_manifest(scenarios_dir)
    monkeypatch.setattr("tests.live_agentic_harness.runner._run_scenario_subprocess", fake_run)

    summary = run_tag(
        "tag",
        scenarios_dir=scenarios_dir,
        output_base=tmp_path / "out",
        max_workers=1,
        per_scenario_timeout=1,
        infra_retries=1,
        progress_every=0,
    )

    scenario = summary["scenarios"][0]
    assert scenario["attempt_count"] == 1
    assert scenario["failure_class"] == "infra_provider_capacity"
    assert scenario["score_class"] == "infra_blocked"
    assert summary["passed"] == 0
    assert summary["infra_failures"] == 1
    assert summary["product_or_assessment_failures"] == 0
    assert summary["score_classes"] == {"infra_blocked": 1}


def test_runner_does_not_classify_soft_search_429_as_infra(
    tmp_path: Path,
    monkeypatch,
) -> None:  # noqa: ANN001
    scenarios_dir = tmp_path / "scenarios"
    scenarios_dir.mkdir()
    scenario_path = scenarios_dir / "soft-search-warning.json"
    scenario_path.write_text(
        json.dumps({"id": "soft-search-warning", "query": "do it"}),
        encoding="utf-8",
    )

    def fake_run(cmd, **kwargs):  # noqa: ANN001, ANN202, ARG001
        out_file = Path(cmd[cmd.index("--single-out") + 1])
        tag = cmd[cmd.index("--tag") + 1]
        output_dir = tmp_path / "out" / tag / "soft-search-warning"
        payload = _summary(tmp_path / "out" / tag, "soft-search-warning", ok=False)
        payload.update(
            {
                "status": "success",
                "error": None,
                "output_dir": str(output_dir),
                "guard": {
                    "live_agentic_success": False,
                    "score_class": "product_fail",
                    "assessment": {
                        "passed": False,
                        "issues": [
                            {
                                "check": "graph_changed",
                                "severity": "error",
                                "detail": "Expected graph change but response.graph_unchanged is True.",
                            },
                            {
                                "check": "soft_warning",
                                "severity": "warning",
                                "detail": "web search: brave search HTTP error: HTTP Error 429: Too Many Requests",
                            },
                        ],
                    },
                },
            }
        )
        out_file.write_text(json.dumps(payload), encoding="utf-8")
        return (1, "", "")

    write_manifest(scenarios_dir)
    monkeypatch.setattr("tests.live_agentic_harness.runner._run_scenario_subprocess", fake_run)

    summary = run_tag(
        "tag",
        scenarios_dir=scenarios_dir,
        output_base=tmp_path / "out",
        max_workers=1,
        per_scenario_timeout=1,
        infra_retries=1,
        progress_every=0,
    )

    scenario = summary["scenarios"][0]
    assert scenario["attempt_count"] == 1
    assert scenario["failure_class"] == "product_or_assessment_failure"
    assert scenario["score_class"] == "product_fail"
    assert scenario.get("retryable_infra") is not True
    assert summary["infra_failures"] == 0
    assert summary["product_or_assessment_failures"] == 1


def test_runner_timeout_preserves_scenario_graph_change_expectation(
    tmp_path: Path,
    monkeypatch,
) -> None:  # noqa: ANN001
    scenarios_dir = tmp_path / "scenarios"
    scenarios_dir.mkdir()
    scenario_path = scenarios_dir / "diagnose.json"
    scenario_path.write_text(
        json.dumps(
            {
                "id": "diagnose",
                "query": "explain the graph",
                "assessment": {"expect_graph_changed": False},
            }
        ),
        encoding="utf-8",
    )

    def fake_run(cmd, **kwargs):  # noqa: ANN001, ANN202
        raise subprocess.TimeoutExpired(cmd=cmd, timeout=kwargs.get("timeout"))

    write_manifest(scenarios_dir)
    monkeypatch.setattr("tests.live_agentic_harness.runner._run_scenario_subprocess", fake_run)

    summary = run_tag(
        "tag",
        scenarios_dir=scenarios_dir,
        output_base=tmp_path / "out",
        max_workers=1,
        per_scenario_timeout=1,
        infra_retries=0,
        progress_every=0,
    )

    scenario = summary["scenarios"][0]
    assert scenario["guard"]["assessment"]["expect_graph_changed"] is False
    assert scenario["failure_class"] == "infra_timeout"
    assert summary["infra_failures"] == 1


def test_retryability_ignores_stale_infra_flags_when_evidence_is_malformed() -> None:
    """Oracle finding 4: persisted failure_class/retryable_infra must never drive retry.

    Canonical ``malformed_json`` evidence with zero tokens is NOT retryable even
    when the summary inherited ``failure_class=infra_empty_response`` and
    ``retryable_infra=True`` from an earlier attempt.
    """
    summary = _summary(Path("/tmp"), "conflicting-flags", ok=False)
    summary["model_attempts"] = [_failed_attempt("malformed_json", completion_tokens=0)]
    summary["failure_class"] = "infra_empty_response"
    summary["retryable_infra"] = True
    summary["score_class"] = "infra_blocked"
    summary["guard"]["failure_class"] = "infra_empty_response"
    summary["guard"]["score_class"] = "infra_blocked"

    assert _provider_infra_failure_class(summary) is None
    assert _is_retryable_infra_summary(summary) is False
    # The inherited markers were cleared, never trusted.
    assert summary.get("failure_class") is None
    assert summary.get("retryable_infra") is False
    assert summary.get("score_class") is None
    assert summary["guard"].get("failure_class") is None
    assert summary["guard"].get("score_class") is None


def test_retryability_is_derived_from_canonical_typed_evidence() -> None:
    """Canonical empty_response + observed zero tokens is retryable regardless of flags."""
    summary = _summary(Path("/tmp"), "canonical-empty", ok=False)
    summary["model_attempts"] = [_failed_attempt("empty_response", completion_tokens=0)]
    summary["failure_class"] = "product_or_assessment_failure"  # stale conflicting flag
    summary["retryable_infra"] = False  # stale conflicting flag

    assert _provider_infra_failure_class(summary) == "infra_empty_response"
    assert _is_retryable_infra_summary(summary) is True
    assert summary["failure_class"] == "infra_empty_response"
    assert summary["retryable_infra"] is True


@pytest.fixture
def leaky_canonical_attempt() -> dict:
    """Canonical failed attempt whose preview embeds oracle finding 5 JSON secrets.

    The canonical shape is exactly what the executor emits (``coerce_model_attempts``
    applies ``ModelAttemptEvidence`` redaction), so a persisted agentic summary must
    never reintroduce the raw secrets.
    """
    attempts = coerce_model_attempts(
        (
            {
                **_failed_attempt("provider_failure"),
                "raw_response_preview": (
                    '{"api_key":"sk-secret",'
                    '"authorization":"Basic dXNlcjpwYXNz",'
                    '"token":"tok-secret"}'
                ),
            },
        )
    )
    return attempts[0]


def test_persisted_agentic_summary_redacts_json_quoted_secrets(
    tmp_path: Path,
    monkeypatch,
    leaky_canonical_attempt: dict,
) -> None:  # noqa: ANN001
    """Oracle finding 5 durable: agentic_summary.json keeps JSON-quoted secrets out."""
    scenarios_dir = tmp_path / "scenarios"
    scenarios_dir.mkdir()
    scenario_path = scenarios_dir / "json-quoted-secrets.json"
    scenario_path.write_text(
        json.dumps({"id": "json-quoted-secrets", "query": "do it"}),
        encoding="utf-8",
    )

    def fake_run(cmd, **kwargs):  # noqa: ANN001, ANN202, ARG001
        out_file = Path(cmd[cmd.index("--single-out") + 1])
        tag = cmd[cmd.index("--tag") + 1]
        payload = _summary(tmp_path / "out" / tag, "json-quoted-secrets", ok=False)
        payload["output_dir"] = str(tmp_path / "out" / tag / "json-quoted-secrets")
        payload["error"] = "provider rejected"
        payload["model_attempts"] = [leaky_canonical_attempt]
        out_file.write_text(json.dumps(payload), encoding="utf-8")
        return (1, "", "")

    write_manifest(scenarios_dir)
    monkeypatch.setattr("tests.live_agentic_harness.runner._run_scenario_subprocess", fake_run)

    run_tag(
        "tag",
        scenarios_dir=scenarios_dir,
        output_base=tmp_path / "out",
        max_workers=1,
        per_scenario_timeout=1,
        infra_retries=0,
        progress_every=0,
    )

    persisted_path = (
        tmp_path / "out" / "tag" / "json-quoted-secrets" / "agentic_summary.json"
    )
    assert persisted_path.exists()
    persisted = persisted_path.read_text(encoding="utf-8")
    assert "sk-secret" not in persisted
    assert "Basic dXNlcjpwYXNz" not in persisted
    assert "tok-secret" not in persisted
    summary = json.loads(persisted)
    # model_attempts is persisted both top-level and inside the attempt record;
    # every occurrence must carry the fully redacted preview.
    for attempt in [summary["model_attempts"][0], summary["attempts"][0]["model_attempts"][0]]:
        preview = attempt["raw_response_preview"]
        assert preview.count("<redacted>") == 3
        assert "sk-secret" not in preview
        assert "Basic dXNlcjpwYXNz" not in preview
        assert "tok-secret" not in preview


# ── B07-lite: explicit transport selector plumbing ──────────────────────────


def test_transport_flag_and_pinned_child_env_survive_subprocess_isolation(
    tmp_path: Path,
    monkeypatch,
) -> None:  # noqa: ANN001
    """Sense-check 1+2: the explicit selector reaches the child command line and
    the child environment is pinned so ambient credentials cannot win."""
    scenarios_dir = tmp_path / "scenarios"
    scenarios_dir.mkdir()
    scenario_path = scenarios_dir / "transport.json"
    scenario_path.write_text(
        json.dumps({"id": "transport", "query": "do it"}),
        encoding="utf-8",
    )
    monkeypatch.setenv("VIBECOMFY_OPENROUTER_BASE_URL", "https://openrouter.ai/api/v1")
    monkeypatch.setenv("VIBECOMFY_FORCE_MODEL", "openrouter:deepseek/deepseek-v4-pro")
    monkeypatch.setenv("OPENROUTER_API_KEY", "sk-or-ambient")
    monkeypatch.setenv("DEEPSEEK_API_KEY", "sk-native-ambient")
    captured: dict = {}

    def fake_run(cmd, **kwargs):  # noqa: ANN001, ANN202, ARG001
        captured["cmd"] = list(cmd)
        captured["env"] = dict(kwargs.get("env") or {})
        out_file = Path(cmd[cmd.index("--single-out") + 1])
        tag = cmd[cmd.index("--tag") + 1]
        payload = _summary(tmp_path / "out" / tag, "transport", ok=True)
        payload["output_dir"] = str(tmp_path / "out" / tag / "transport")
        out_file.write_text(json.dumps(payload), encoding="utf-8")
        return (0, "", "")

    write_manifest(scenarios_dir)
    monkeypatch.setattr("tests.live_agentic_harness.runner._run_scenario_subprocess", fake_run)

    summary = run_tag(
        "tag",
        scenarios_dir=scenarios_dir,
        output_base=tmp_path / "out",
        max_workers=1,
        per_scenario_timeout=1,
        infra_retries=0,
        progress_every=0,
        transport="native",
    )

    # CLI -> child: the selector is on the child command line.
    assert captured["cmd"][captured["cmd"].index("--transport") + 1] == "native"
    # Child environment: ambient transport-selecting keys are pinned away...
    assert "VIBECOMFY_OPENROUTER_BASE_URL" not in captured["env"]
    assert "VIBECOMFY_TRANSPORT" not in captured["env"]
    assert "VIBECOMFY_FORCE_MODEL" not in captured["env"]
    # ...but credential keys are preserved (they supply keys, not transport).
    assert captured["env"]["OPENROUTER_API_KEY"] == "sk-or-ambient"
    assert captured["env"]["DEEPSEEK_API_KEY"] == "sk-native-ambient"
    # The run configuration records the selection.
    assert summary["transport"] == "native"
    assert summary["scenarios"][0]["transport"] == "native"
    persisted = json.loads(
        (tmp_path / "out" / "tag" / "run_summary.json").read_text(encoding="utf-8")
    )
    assert persisted["transport"] == "native"


def test_transport_omitted_resolves_to_openrouter_default_not_ambient_native(
    tmp_path: Path,
    monkeypatch,
) -> None:  # noqa: ANN001
    """Rework 2 (oracle issue 1d): the no-flag default is pinned to the
    canonical OpenRouter product route.  An ambient ``VIBECOMFY_TRANSPORT=native``
    must never leak into the child or displace the default, and the run records
    the resolved default (openrouter), not None."""
    scenarios_dir = tmp_path / "scenarios"
    scenarios_dir.mkdir()
    scenario_path = scenarios_dir / "no-transport.json"
    scenario_path.write_text(
        json.dumps({"id": "no-transport", "query": "do it"}),
        encoding="utf-8",
    )
    monkeypatch.setenv("VIBECOMFY_TRANSPORT", "native")
    monkeypatch.setenv("VIBECOMFY_OPENROUTER_BASE_URL", "https://api.deepseek.com/v1")
    monkeypatch.setenv("OPENROUTER_API_KEY", "***")
    captured: dict = {}

    def fake_run(cmd, **kwargs):  # noqa: ANN001, ANN202, ARG001
        captured["cmd"] = list(cmd)
        captured["env"] = dict(kwargs.get("env") or {})
        out_file = Path(cmd[cmd.index("--single-out") + 1])
        tag = cmd[cmd.index("--tag") + 1]
        payload = _summary(tmp_path / "out" / tag, "no-transport", ok=True)
        payload["output_dir"] = str(tmp_path / "out" / tag / "no-transport")
        out_file.write_text(json.dumps(payload), encoding="utf-8")
        return (0, "", "")

    write_manifest(scenarios_dir)
    monkeypatch.setattr("tests.live_agentic_harness.runner._run_scenario_subprocess", fake_run)

    summary = run_tag(
        "tag",
        scenarios_dir=scenarios_dir,
        output_base=tmp_path / "out",
        max_workers=1,
        per_scenario_timeout=1,
        infra_retries=0,
        progress_every=0,
    )

    # No flag -> the canonical default is forwarded explicitly to the child.
    assert captured["cmd"][captured["cmd"].index("--transport") + 1] == "openrouter"
    # The ambient native pin/base URL is stripped from the child environment.
    assert "VIBECOMFY_TRANSPORT" not in captured["env"]
    assert "VIBECOMFY_OPENROUTER_BASE_URL" not in captured["env"]
    # Credential keys are preserved (they supply keys, not transport).
    assert captured["env"]["OPENROUTER_API_KEY"] == "***"
    # The run configuration records the resolved default.
    assert summary["transport"] == "openrouter"
    assert summary["scenarios"][0]["transport"] == "openrouter"
    persisted = json.loads(
        (tmp_path / "out" / "tag" / "run_summary.json").read_text(encoding="utf-8")
    )
    assert persisted["transport"] == "openrouter"


def test_observed_transport_provenance_passthrough_matches_selection(
    tmp_path: Path,
    monkeypatch,
) -> None:  # noqa: ANN001
    """B01 provenance is consumed verbatim: the runner never rewrites the
    observed transport and never introduces a second metadata format."""
    scenarios_dir = tmp_path / "scenarios"
    scenarios_dir.mkdir()
    scenario_path = scenarios_dir / "observed-transport.json"
    scenario_path.write_text(
        json.dumps({"id": "observed-transport", "query": "do it"}),
        encoding="utf-8",
    )

    native_attempt = _failed_attempt("empty_response", completion_tokens=0)
    native_attempt.update(
        {
            "provider": "deepseek",
            "transport": "native",
            "endpoint": "https://api.deepseek.com/v1",
            "resolved_model": "deepseek-v4-pro",
        }
    )

    def fake_run(cmd, **kwargs):  # noqa: ANN001, ANN202, ARG001
        out_file = Path(cmd[cmd.index("--single-out") + 1])
        tag = cmd[cmd.index("--tag") + 1]
        payload = _summary(tmp_path / "out" / tag, "observed-transport", ok=False)
        payload["output_dir"] = str(tmp_path / "out" / tag / "observed-transport")
        payload["error"] = "empty response"
        payload["model_attempts"] = [native_attempt]
        out_file.write_text(json.dumps(payload), encoding="utf-8")
        return (1, "", "")

    write_manifest(scenarios_dir)
    monkeypatch.setattr("tests.live_agentic_harness.runner._run_scenario_subprocess", fake_run)

    summary = run_tag(
        "tag",
        scenarios_dir=scenarios_dir,
        output_base=tmp_path / "out",
        max_workers=1,
        per_scenario_timeout=1,
        infra_retries=1,
        progress_every=0,
        transport="native",
    )

    scenario = summary["scenarios"][0]
    # Observed B01 attempt provenance: transport/endpoint exactly as the child
    # observed them — no rewriting, no parallel format.
    observed = scenario["attempts"][0]["model_attempts"][0]
    assert observed["transport"] == "native"
    assert observed["endpoint"] == "https://api.deepseek.com/v1"
    assert observed["failure_type"] == "empty_response"
    assert scenario["failure_class"] == "infra_empty_response"
    # Selection and observation agree.
    assert scenario["transport"] == "native"
    assert observed["transport"] == scenario["transport"]


def test_run_single_forwards_transport_selector_to_adapter(
    tmp_path: Path,
    monkeypatch,
) -> None:  # noqa: ANN001
    from tests.live_agentic_harness.runner import run_single

    scenario_path = tmp_path / "single.json"
    scenario_path.write_text(
        json.dumps({"id": "single", "query": "do it"}),
        encoding="utf-8",
    )
    calls: dict = {}

    def fake_headless(scenario, *, output_base, tag, transport=None):  # noqa: ANN001, ANN202, ARG001
        calls["transport"] = transport
        return {
            "scenario_id": "single",
            "status": "success",
            "ok": True,
            "output_dir": str(tmp_path / "out" / tag / "single"),
            "deepseek_usage": {},
            "model_attempts": [],
        }

    def fake_guard(output_dir, *, scenario=None):  # noqa: ANN001, ANN202, ARG001
        return {
            "live_agentic_success": True,
            "score_class": "pass",
            "assessment": {"passed": True, "issues": []},
        }

    monkeypatch.setattr(
        "tests.live_agentic_harness.adapter.run_headless_scenario", fake_headless
    )
    monkeypatch.setattr("tests.live_agentic_harness.guard.guard_output_dir", fake_guard)

    summary = run_single(
        str(scenario_path), "tag", tmp_path / "out", None, transport="openrouter"
    )

    assert calls["transport"] == "openrouter"
    assert summary["transport"] == "openrouter"
