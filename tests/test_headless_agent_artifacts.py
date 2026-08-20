from __future__ import annotations

import json
from pathlib import Path

import pytest

from vibecomfy.agent.artifacts import synthesize_headless_artifacts
from vibecomfy.executor.agent_research_stage import AgentResearchTrace
from vibecomfy.executor.contracts import (
    ClassifyDecision,
    ExecutorResult,
    ImplementationResult,
    Report,
)
from vibecomfy.executor.core import AgentResearchResult
from vibecomfy.executor.evidence_pack import (
    EvidenceArtifact,
    EvidenceLedger,
    EvidenceLedgerEntry,
    EvidencePack,
)


def _read_json(path: Path) -> dict:
    return json.loads(path.read_text(encoding="utf-8"))


def _agent_research_result(
    *,
    decision: str = "hivemind_search",
    conclusion: str = "2 hit(s)",
) -> AgentResearchResult:
    """Real C1 research result: edit routes serialize ONLY the compact ledger."""
    trace = AgentResearchTrace(
        route="adapt",
        question="Find useful precedent.",
        iterations=(),
        final_verdict="enough",
        summary="Found precedent.",
        citations=("hivemind:workflows:111",),
        uncertainty="",
        status="ok",
        elapsed_seconds=0.0,
    )
    pack = EvidencePack(
        artifacts={
            "hivemind:workflows:111": EvidenceArtifact(
                evidence_id="hivemind:workflows:111",
                kind="hivemind_search_hit",
                body={"title": "Found precedent."},
                source="hivemind",
            ),
        },
        ledger=EvidenceLedger(
            entries=(
                EvidenceLedgerEntry(
                    decision=decision,
                    conclusion=conclusion,
                    evidence_ids=("hivemind:workflows:111",),
                    uncertainty="",
                ),
            )
        ),
    )
    return AgentResearchResult(route="adapt", trace=trace, evidence_pack=pack)


def test_headless_artifacts_persist_exact_reply_request(tmp_path: Path) -> None:
    output_dir = tmp_path / "reply-request"
    messages = [
        {"role": "system", "content": "Inspect only."},
        {"role": "user", "content": "Graph census: 3 nodes, 3 edges."},
    ]
    result = ExecutorResult.success(
        report=Report(
            plan=ClassifyDecision(route="inspect", task="inspect_graph"),
            reply_request={
                "query": "explain this graph",
                "messages": messages,
                "route": "openrouter",
                "model": "example/model",
                "response_contract": "text",
            },
        ),
        reply="Grounded answer.",
    )

    manifest = synthesize_headless_artifacts(
        request={"query": "explain this graph", "graph": {"nodes": []}},
        result=result,
        response={"ok": True, "route": "inspect", "reply": "Grounded answer."},
        output_dir=output_dir,
        status="success",
        readiness={"ready": True},
        entrypoint="test",
    )

    assert "reply_request.json" in manifest["manifest"]
    persisted = _read_json(output_dir / "reply_request.json")
    assert persisted["messages"] == messages
    assert persisted["response_contract"] == "text"


def test_threaded_research_evidence_survives_public_artifact_projection(
    tmp_path: Path,
) -> None:
    implementation = ImplementationResult(
        message="Grounded research answer.",
        durable_response={
            "graph_unchanged": True,
            "research_findings": {
                "sources": [{"title": "Fetched distilled workflow"}],
                "summary": "Fetched a lower-step workflow precedent.",
                "community_summary": "Fetched a lower-step workflow precedent.",
                "warnings": [],
                # Narrative/findings metadata is not execution proof. These
                # counterfeit counters must lose to the typed tool ledger.
                "research_attempt": "never",
                "tool_calls_executed": 99,
                "evidence_artifacts": 99,
            },
            "batch_turns": [{
                "turn_number": 0,
                "statements": [{
                    "detail": {
                        "tool_call": "hivemind_get",
                        "tool_status": "ok",
                        "ledger_entry": {
                            "decision": "hivemind_get",
                            "conclusion": "Fetched distilled workflow.",
                            # Production batch hivemind_get keeps the fetched
                            # record's canonical id; grounding comes from the
                            # typed tool_call, not an id naming convention.
                            "evidence_ids": ["hivemind:workflows:7"],
                        },
                    },
                }],
            }],
        },
    )
    result = ExecutorResult.success(
        report=Report(
            plan=ClassifyDecision(
                research=True,
                implement=False,
                route="research",
                task="research_nodes",
            ),
            implementation=implementation,
            deepseek_usage={"n_calls": 1},
            orchestration_mode="threaded",
        ),
        reply="Grounded research answer.",
    )
    response = result.to_dict()
    output_dir = tmp_path / "threaded-research"

    synthesize_headless_artifacts(
        request={"query": "find a distilled workflow"},
        result=result,
        response=response,
        output_dir=output_dir,
        status="success",
        readiness={"ready": True},
        entrypoint="test",
    )

    persisted = _read_json(output_dir / "response.json")
    research = persisted["evidence"]["research"]
    assert research["research_attempt"] == "grounded"
    assert research["tool_calls_executed"] == 1
    assert research["evidence_artifacts"] == 1
    assert research["citations"] == ["hivemind:workflows:7"]

    # The same persisted artifact is what the live assessor adjudicates.
    # This proves threaded research is not merely executed and then discarded.
    from tests.live_agentic_harness.assessor import assess_live_output_dir

    assessment = assess_live_output_dir(
        output_dir,
        scenario={
            "assessment": {
                "expect_graph_changed": False,
                "require_executed_research": True,
            },
            "classification": {"kind": "health_control"},
        },
    )
    assert assessment["passed"] is True, assessment["issues"]


def test_headless_artifacts_redact_metadata_and_write_phase_payloads(tmp_path: Path) -> None:
    output_dir = tmp_path / "out"
    request = {
        "query": "adapt this graph",
        "graph": {"nodes": [{"id": 1, "class_type": "LoadImage"}]},
        "session_id": "session-1",
        "extra": {
            "api_key": "sk-secret",
            "nested": {"access_token": "token-secret"},
        },
    }
    result = ExecutorResult.success(
        report=Report(
            plan=ClassifyDecision(
                research=True,
                implement=True,
                route="adapt",
                task="research_precedent",
                research_goal="Find useful precedent.",
            ),
            research=_agent_research_result(),
            implementation=ImplementationResult(
                graph={"nodes": [{"id": 2}]},
                message="Applied edit.",
                durable_response={"session_id": "session-1", "turn_id": "0001"},
            ),
        ),
        graph={"nodes": [{"id": 2}]},
        reply="Done.",
    )

    manifest = synthesize_headless_artifacts(
        request=request,
        result=result,
        response={
            "ok": True,
            "route": "adapt",
            "reply": "Done.",
            "debug": {"provider_token": "response-secret"},
        },
        output_dir=output_dir,
        status="success",
        readiness={"ready": True, "api_key": "readiness-secret"},
        entrypoint="test",
    )

    assert manifest["manifest"] == [
        "request.json",
        "response.json",
        "flow_metadata.json",
        "classification.json",
        "research.json",
        "implementation_payload.json",
        "implementation_result.json",
        "original.ui.json",
        "final.ui.json",
    ]
    original_ui = _read_json(output_dir / "original.ui.json")
    final_ui = _read_json(output_dir / "final.ui.json")
    assert original_ui == request["graph"]
    assert final_ui == {"nodes": [{"id": 2}]}
    assert _read_json(output_dir / "request.json")["extra"]["api_key"] == "<redacted>"
    assert (
        _read_json(output_dir / "request.json")["extra"]["nested"]["access_token"]
        == "<redacted>"
    )
    assert _read_json(output_dir / "flow_metadata.json")["readiness"]["api_key"] == "<redacted>"
    assert _read_json(output_dir / "response.json")["debug"]["provider_token"] == "<redacted>"
    research_json = _read_json(output_dir / "research.json")
    assert research_json["mode"] == "agent_owned"
    assert research_json["ledger"]["entries"]

    implementation_payload = _read_json(output_dir / "implementation_payload.json")
    assert implementation_payload["route"] == "adapt"
    assert implementation_payload["executor_route"] == "adapt"
    assert implementation_payload["executor_classification"]["route"] == "adapt"
    assert implementation_payload["graph"] == request["graph"]
    notes = implementation_payload["execution_protocol_notes"]
    # D03: notes carry ONLY the compact F01 ledger (research_sources is a
    # passthrough for payloads that carry it; the C1 result serializes ledger
    # only, so notes == {"ledger": ...}).
    assert set(notes) == {"ledger"}
    assert notes["ledger"]["entries"]
    for legacy_key in (
        "research_goal",
        "research_summary",
        "workflow_precedent_status",
        "research_warnings",
        "precedent_packet",
        "_discardability",
    ):
        assert legacy_key not in notes, legacy_key
    assert "research_context_packet" not in implementation_payload
    assert _read_json(output_dir / "implementation_result.json")["message"] == "Applied edit."


def test_adapt_artifacts_carry_only_compact_ledger_without_sources(tmp_path: Path) -> None:
    output_dir = tmp_path / "out"
    request = {
        "query": "adapt this graph",
        "graph": {"nodes": [{"id": 1, "class_type": "LoadImage"}]},
    }
    result = ExecutorResult.success(
        report=Report(
            plan=ClassifyDecision(
                research=True,
                implement=True,
                route="adapt",
                research_goal="Find precedent.",
            ),
            research=_agent_research_result(decision="hivemind_get", conclusion="record fetched"),
            implementation=ImplementationResult(message="No compatible precedent."),
        ),
        graph=request["graph"],
        reply="Done.",
    )

    synthesize_headless_artifacts(
        request=request,
        result=result,
        response={"ok": True, "route": "adapt"},
        output_dir=output_dir,
        status="success",
    )

    implementation_payload = _read_json(output_dir / "implementation_payload.json")
    assert "research_context_packet" not in implementation_payload
    notes = implementation_payload["execution_protocol_notes"]
    assert set(notes) == {"ledger"}
    assert notes["ledger"]["entries"]
    assert "research_sources" not in notes


def test_headless_artifacts_copy_only_real_durable_turn_files(tmp_path: Path) -> None:
    turn_dir = tmp_path / "sessions" / "session-1" / "turns" / "0001"
    turn_dir.mkdir(parents=True)
    (turn_dir / "request.json").write_text('{"query": "real"}\n', encoding="utf-8")
    (turn_dir / "response.json").write_text('{"ok": true, "route": "inspect"}\n', encoding="utf-8")
    (turn_dir / "chat.json").write_text('{"messages": []}\n', encoding="utf-8")

    output_dir = tmp_path / "out"
    manifest = synthesize_headless_artifacts(
        request={"query": "synthetic"},
        result=ExecutorResult.success(
            report=Report(plan=ClassifyDecision(route="inspect", task="inspect_graph")),
            reply="inspected",
        ),
        response={
            "ok": True,
            "route": "inspect",
            "detail_json_path": str(turn_dir / "response.json"),
        },
        output_dir=output_dir,
        status="success",
    )

    assert sorted(manifest["copied_turn_artifacts"]) == [
        "chat.json",
        "request.json",
        "response.json",
    ]
    assert manifest["optional_model_artifacts"] == {
        "messages.jsonl": False,
        "model_attempts.json": False,
        "model_request.json": False,
        "model_response.json": False,
        "reply_request.json": False,
    }
    assert not (output_dir / "messages.jsonl").exists()
    assert not (output_dir / "model_request.json").exists()
    assert not (output_dir / "model_response.json").exists()
    assert _read_json(output_dir / "request.json") == {"query": "real"}


def test_headless_artifacts_copy_model_files_when_turn_produced_them(tmp_path: Path) -> None:
    turn_dir = tmp_path / "sessions" / "session-1" / "turns" / "0002"
    turn_dir.mkdir(parents=True)
    (turn_dir / "response.json").write_text('{"ok": true}\n', encoding="utf-8")
    (turn_dir / "messages.jsonl").write_text('{"role": "user"}\n', encoding="utf-8")
    (turn_dir / "model_request.json").write_text('{"messages": []}\n', encoding="utf-8")
    (turn_dir / "model_response.json").write_text('{"turns": []}\n', encoding="utf-8")

    output_dir = tmp_path / "out"
    manifest = synthesize_headless_artifacts(
        request={"query": "edit"},
        result=ExecutorResult.success(
            report=Report(
                plan=ClassifyDecision(route="revise", task="edit_graph"),
                implementation=ImplementationResult(message="edited"),
            ),
            reply="edited",
        ),
        response={"ok": True, "detail_json_path": str(turn_dir / "response.json")},
        output_dir=output_dir,
        status="success",
    )

    assert manifest["optional_model_artifacts"] == {
        "messages.jsonl": True,
        "model_attempts.json": False,
        "model_request.json": True,
        "model_response.json": True,
        "reply_request.json": False,
    }
    assert (output_dir / "messages.jsonl").read_text(encoding="utf-8") == '{"role": "user"}\n'
    assert (output_dir / "model_request.json").is_file()
    assert (output_dir / "model_response.json").is_file()


def test_malformed_json_artifact_body_is_omitted(tmp_path: Path) -> None:
    turn_dir = tmp_path / "sessions" / "session-1" / "turns" / "malformed-json"
    turn_dir.mkdir(parents=True)
    (turn_dir / "response.json").write_text('{"ok": false}\n', encoding="utf-8")
    secret = "sk-malformed-json-secret"
    (turn_dir / "model_request.json").write_text(
        '{"api_key":"' + secret + '"', encoding="utf-8"
    )
    output_dir = tmp_path / "out"

    synthesize_headless_artifacts(
        request={"query": "test"},
        result=ExecutorResult.failure(kind="ProviderError", stage="classify", message="bad"),
        response={"ok": False, "detail_json_path": str(turn_dir / "response.json")},
        output_dir=output_dir,
        status="error",
    )

    assert _read_json(output_dir / "model_request.json") == {
        "redacted_unparseable_artifact": True
    }
    assert secret not in "\n".join(
        path.read_text(encoding="utf-8") for path in output_dir.iterdir() if path.is_file()
    )


def test_malformed_jsonl_artifact_body_is_omitted(tmp_path: Path) -> None:
    turn_dir = tmp_path / "sessions" / "session-1" / "turns" / "malformed-jsonl"
    turn_dir.mkdir(parents=True)
    (turn_dir / "response.json").write_text('{"ok": false}\n', encoding="utf-8")
    credential = "dXNlcjpwYXNz"
    (turn_dir / "messages.jsonl").write_text(
        '{"role":"user","content":"safe"}\n'
        '{"authorization":"Basic ' + credential + '"\n',
        encoding="utf-8",
    )
    output_dir = tmp_path / "out"

    synthesize_headless_artifacts(
        request={"query": "test"},
        result=ExecutorResult.failure(kind="ProviderError", stage="classify", message="bad"),
        response={"ok": False, "detail_json_path": str(turn_dir / "response.json")},
        output_dir=output_dir,
        status="error",
    )

    assert _read_json(output_dir / "messages.jsonl") == {
        "redacted_unparseable_artifact": True
    }
    persisted = "\n".join(
        path.read_text(encoding="utf-8") for path in output_dir.iterdir() if path.is_file()
    )
    assert credential not in persisted
    assert "Basic" not in persisted


def test_model_attempt_artifact_is_canonical_and_redacts_secrets(tmp_path: Path) -> None:
    output_dir = tmp_path / "out"
    result = ExecutorResult.success(
        report=Report(
            model_attempts=(
                {
                    "phase": "classify",
                    "attempt": 1,
                    "outcome": "failure",
                    "failure_type": "malformed_json",
                    "requested_model": "requested-model",
                    "resolved_model": "resolved-model",
                    "adapter": "hermes",
                    "provider": "openrouter",
                    "transport": "openrouter",
                    "endpoint": (
                        "https://user:password@OpenRouter.ai/api/v1/?api_key=sk-secret"
                        "&signature=sig-secret"
                    ),
                    "finish_reason": "stop",
                    "token_usage": {
                        "prompt_tokens": 11,
                        "completion_tokens": 4,
                        "total_tokens": 15,
                    },
                    "raw_response_preview": (
                        "Authorization: Bearer top-secret "
                        "https://example.test/v1?token=url-secret"
                    ),
                },
                {
                    "phase": "reply",
                    "attempt": 1,
                    "outcome": "success",
                    "requested_model": "requested-model",
                    "resolved_model": "resolved-model",
                    "adapter": "codex",
                    "provider": "unknown",
                    "transport": "unknown",
                    "endpoint": "unknown",
                    "finish_reason": "unknown",
                    "token_usage": {},
                    "raw_response_preview": "must never persist on success",
                },
            )
        ),
        reply="ok",
    )

    manifest = synthesize_headless_artifacts(
        request={"query": "test"},
        result=result,
        response={"ok": True},
        output_dir=output_dir,
        status="success",
    )

    assert "model_attempts.json" in manifest["manifest"]
    assert manifest["optional_model_artifacts"]["model_attempts.json"] is True
    attempts = _read_json(output_dir / "model_attempts.json")["attempts"]
    assert attempts[0]["endpoint"] == "https://openrouter.ai/api/v1"
    assert "top-secret" not in attempts[0]["raw_response_preview"]
    assert "url-secret" not in attempts[0]["raw_response_preview"]
    assert "raw_response_preview" not in attempts[1]
    assert attempts[1]["provider"] == "unknown"
    persisted = "\n".join(
        path.read_text(encoding="utf-8")
        for path in output_dir.iterdir()
        if path.is_file()
    )
    assert "sk-secret" not in persisted
    assert "sig-secret" not in persisted
    assert "top-secret" not in persisted
    assert "url-secret" not in persisted


@pytest.fixture
def json_quoted_secret_raw_preview() -> str:
    """raw_response_preview embedding oracle finding 5 JSON-quoted secrets."""
    return (
        '{"api_key":"sk-secret",'
        '"authorization":"Basic dXNlcjpwYXNz",'
        '"token":"tok-secret"}'
    )


def test_model_attempt_artifact_redacts_json_quoted_secrets(
    tmp_path: Path, json_quoted_secret_raw_preview: str
) -> None:
    """Oracle finding 5 durable: model_attempts.json must not persist JSON-quoted secrets."""
    output_dir = tmp_path / "out"
    result = ExecutorResult.success(
        report=Report(
            model_attempts=(
                {
                    "phase": "classify",
                    "attempt": 1,
                    "outcome": "failure",
                    "failure_type": "malformed_json",
                    "requested_model": "requested-model",
                    "resolved_model": "resolved-model",
                    "adapter": "hermes",
                    "provider": "openrouter",
                    "transport": "openrouter",
                    "endpoint": "https://openrouter.ai/api/v1",
                    "finish_reason": "unknown",
                    "token_usage": {
                        "prompt_tokens": 1,
                        "completion_tokens": 0,
                        "total_tokens": 1,
                    },
                    "raw_response_preview": json_quoted_secret_raw_preview,
                },
            )
        ),
        reply="ok",
    )

    manifest = synthesize_headless_artifacts(
        request={"query": "test"},
        result=result,
        response={"ok": True},
        output_dir=output_dir,
        status="success",
    )

    assert "model_attempts.json" in manifest["manifest"]
    attempts = _read_json(output_dir / "model_attempts.json")["attempts"]
    preview = attempts[0]["raw_response_preview"]
    assert "sk-secret" not in preview
    assert "Basic dXNlcjpwYXNz" not in preview
    assert "tok-secret" not in preview
    assert preview.count("<redacted>") == 3
    persisted = "\n".join(
        path.read_text(encoding="utf-8")
        for path in output_dir.iterdir()
        if path.is_file()
    )
    assert "sk-secret" not in persisted
    assert "Basic dXNlcjpwYXNz" not in persisted
    assert "tok-secret" not in persisted


def test_turn_artifact_secrets_in_ordinary_fields_are_redacted(tmp_path: Path) -> None:
    """Oracle finding 5: parsed JSON artifacts with secrets in ordinary leaves.

    A durable turn artifact persisting ``Authorization`` headers or
    credential-bearing URLs under ordinary keys (``content``, ``url``,
    ``message``, ``error``) must come out fully redacted.
    """
    turn_dir = tmp_path / "sessions" / "session-1" / "turns" / "leaky"
    turn_dir.mkdir(parents=True)
    (turn_dir / "response.json").write_text('{"ok": false}\n', encoding="utf-8")
    (turn_dir / "request.json").write_text(
        json.dumps(
            {
                "content": "Authorization: Basic dXNlcjpwYXNz",
                "url": "https://example.test/v1?token=url-secret&sig=abc123",
                "message": "retry with Authorization: Bearer eyJhbGciOiJIUzI1NiJ9",
                "error": "call https://api.example.test/v2?api_key=sk-live-123",
                "safe": "plain text without secrets",
            }
        ),
        encoding="utf-8",
    )

    output_dir = tmp_path / "out"
    synthesize_headless_artifacts(
        request={"query": "test"},
        result=ExecutorResult.failure(kind="ProviderError", stage="classify", message="bad"),
        response={"ok": False, "detail_json_path": str(turn_dir / "response.json")},
        output_dir=output_dir,
        status="error",
    )

    copied = _read_json(output_dir / "request.json")
    assert copied["content"] == "Authorization: <redacted>"
    assert copied["url"] == "https://example.test/v1?token=<redacted>&sig=<redacted>"
    assert copied["message"] == "retry with Authorization: <redacted>"
    assert copied["error"] == "call https://api.example.test/v2?api_key=<redacted>"
    assert copied["safe"] == "plain text without secrets"
    persisted = "\n".join(
        path.read_text(encoding="utf-8") for path in output_dir.iterdir() if path.is_file()
    )
    assert "dXNlcjpwYXNz" not in persisted
    assert "url-secret" not in persisted
    assert "abc123" not in persisted
    assert "eyJhbGciOiJIUzI1NiJ9" not in persisted
    assert "sk-live-123" not in persisted


def test_synthesized_response_secrets_in_ordinary_fields_are_redacted(tmp_path: Path) -> None:
    """Oracle finding 5: synthesized response with secrets in ordinary leaves.

    The response/request payloads synthesized by ``synthesize_headless_artifacts``
    must redact authorization headers and credential-bearing URLs even when they
    arrive under ordinary ``content``/``url``/``error`` fields.
    """
    output_dir = tmp_path / "out"
    synthesize_headless_artifacts(
        request={"query": "test", "url": "https://api.example.test/v1?apikey=req-secret"},
        result=ExecutorResult.failure(kind="ProviderError", stage="classify", message="bad"),
        response={
            "ok": False,
            "reply": "auth failed",
            "content": (
                "see https://api.example.test/v1?token=url-secret "
                "then Authorization: Bearer live-token"
            ),
            "error": "Authorization: ApiKey live-abcdef",
        },
        output_dir=output_dir,
        status="error",
    )

    response_json = _read_json(output_dir / "response.json")
    assert response_json["reply"] == "auth failed"
    assert response_json["content"] == (
        "see https://api.example.test/v1?token=<redacted> then Authorization: <redacted>"
    )
    assert response_json["error"] == "Authorization: <redacted>"
    request_json = _read_json(output_dir / "request.json")
    assert request_json["url"] == "https://api.example.test/v1?apikey=<redacted>"
    persisted = "\n".join(
        path.read_text(encoding="utf-8") for path in output_dir.iterdir() if path.is_file()
    )
    assert "req-secret" not in persisted
    assert "url-secret" not in persisted
    assert "live-token" not in persisted
    assert "live-abcdef" not in persisted


_NON_EDIT_UI_ROUTES = (
    "respond",
    "research",
    "inspect",
    "clarify",
    "requires_custom_nodes",
)


@pytest.mark.parametrize("route", _NON_EDIT_UI_ROUTES)
def test_universal_ui_evidence_for_non_edit_routes_without_turn_dir(
    tmp_path: Path,
    route: str,
) -> None:
    """Every adjudicated non-edit route persists original/final with final==original."""
    graph = {"nodes": [{"id": 1, "type": "LoadImage"}], "links": []}
    output_dir = tmp_path / route
    synthesize_headless_artifacts(
        request={"query": f"{route} this graph", "graph": graph},
        result=ExecutorResult.success(
            report=Report(plan=ClassifyDecision(route=route, task=route)),
            reply="ok",
            graph=graph,
        ),
        response={"ok": True, "route": route, "graph_unchanged": True},
        output_dir=output_dir,
        status="success",
    )
    original = _read_json(output_dir / "original.ui.json")
    final = _read_json(output_dir / "final.ui.json")
    assert original == graph
    assert final == original


@pytest.mark.parametrize("route", _NON_EDIT_UI_ROUTES)
def test_universal_ui_evidence_for_non_edit_routes_with_turn_dir(
    tmp_path: Path,
    route: str,
) -> None:
    """Turn-dir synthesis still projects final from original for unchanged routes."""
    graph = {"nodes": [{"id": 1, "type": "KSampler"}], "links": []}
    turn_dir = tmp_path / "sessions" / "s1" / "turns" / "0001"
    turn_dir.mkdir(parents=True)
    (turn_dir / "request.json").write_text(json.dumps({"query": route, "graph": graph}))
    (turn_dir / "response.json").write_text(
        json.dumps({"ok": True, "route": route, "graph_unchanged": True})
    )
    output_dir = tmp_path / f"out-{route}"
    synthesize_headless_artifacts(
        request={"query": route, "graph": graph},
        result=ExecutorResult.success(
            report=Report(plan=ClassifyDecision(route=route, task=route)),
            reply="ok",
        ),
        response={
            "ok": True,
            "route": route,
            "graph_unchanged": True,
            "detail_json_path": str(turn_dir / "response.json"),
        },
        output_dir=output_dir,
        status="success",
    )
    original = _read_json(output_dir / "original.ui.json")
    final = _read_json(output_dir / "final.ui.json")
    assert original == graph
    assert final == original


def test_edit_route_final_ui_uses_candidate_when_graph_changed(tmp_path: Path) -> None:
    original_graph = {"nodes": [{"id": 1, "type": "LoadImage"}], "links": []}
    candidate_graph = {"nodes": [{"id": 1, "type": "LoadImage"}, {"id": 2, "type": "SaveImage"}], "links": []}
    turn_dir = tmp_path / "sessions" / "s1" / "turns" / "0002"
    turn_dir.mkdir(parents=True)
    (turn_dir / "original.ui.json").write_text(json.dumps(original_graph))
    (turn_dir / "candidate.ui.json").write_text(json.dumps(candidate_graph))
    (turn_dir / "response.json").write_text(json.dumps({"ok": True, "route": "revise"}))
    output_dir = tmp_path / "edit-out"
    synthesize_headless_artifacts(
        request={"query": "add save", "graph": original_graph},
        result=ExecutorResult.success(
            report=Report(
                plan=ClassifyDecision(route="revise", implement=True),
                implementation=ImplementationResult(message="edited"),
            ),
            graph=candidate_graph,
        ),
        response={
            "ok": True,
            "route": "revise",
            "graph_unchanged": False,
            "detail_json_path": str(turn_dir / "response.json"),
        },
        output_dir=output_dir,
        status="success",
    )
    assert _read_json(output_dir / "original.ui.json") == original_graph
    assert _read_json(output_dir / "final.ui.json") == candidate_graph
