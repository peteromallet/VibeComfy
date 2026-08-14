from __future__ import annotations

import json
from pathlib import Path

import pytest

from vibecomfy.agent.artifacts import _execute_research_sources, synthesize_headless_artifacts
from vibecomfy.executor.contracts import (
    ClassifyDecision,
    ExecutorResult,
    ImplementationResult,
    Report,
)


class _LegacyResearchResult:
    """Duck-typed stand-in for the deleted legacy ``ResearchResult`` contract.

    The class was removed by the agent-judgment rework (D02); artifact
    serialization consumes this shape via ``to_dict()`` / ``getattr``.
    """

    def __init__(
        self,
        *,
        summary: str = "",
        sources: tuple = (),
        warnings: tuple = (),
        community_summary: str = "",
        precedent_sources: tuple = (),
        workflow_precedent_status: str = "",
    ) -> None:
        self.summary = summary
        self.sources = sources
        self.warnings = warnings
        self.community_summary = community_summary
        self.precedent_sources = precedent_sources
        self.workflow_precedent_status = workflow_precedent_status

    def to_dict(self) -> dict:
        return {
            "summary": self.summary,
            "sources": list(self.sources),
            "warnings": list(self.warnings),
            "community_summary": self.community_summary,
            "precedent_sources": list(self.precedent_sources),
            "workflow_precedent_status": self.workflow_precedent_status,
        }



def _read_json(path: Path) -> dict:
    return json.loads(path.read_text(encoding="utf-8"))


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
            research=_LegacyResearchResult(
                summary="Found precedent.",
                sources=(
                    {"class_type": "wrong_ltx", "api_key": "source-secret"},
                    {"class_type": "right_hotshot"},
                ),
                precedent_sources=({"class_type": "right_hotshot"},),
                workflow_precedent_status="compatible_workflow_found",
            ),
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
    assert research_json["sources"][0]["api_key"] == "<redacted>"
    assert [s["class_type"] for s in research_json["sources"]] == ["wrong_ltx", "right_hotshot"]

    implementation_payload = _read_json(output_dir / "implementation_payload.json")
    assert implementation_payload["route"] == "adapt"
    assert implementation_payload["executor_route"] == "adapt"
    assert implementation_payload["executor_classification"]["route"] == "adapt"
    assert implementation_payload["graph"] == request["graph"]
    assert implementation_payload["execution_protocol_notes"]["research_goal"] == (
        "Find useful precedent."
    )
    assert implementation_payload["execution_protocol_notes"]["research_summary"] == (
        "Found precedent."
    )
    assert implementation_payload["execution_protocol_notes"]["research_sources"] == [
        {"class_type": "right_hotshot"}
    ]
    assert (
        implementation_payload["execution_protocol_notes"]["workflow_precedent_status"]
        == "compatible_workflow_found"
    )
    assert _read_json(output_dir / "implementation_result.json")["message"] == "Applied edit."


def test_execute_research_sources_derive_from_packet_without_full_fallback() -> None:
    research = {
        "sources": [
            {"class_type": "wrong_ltx", "source": "ready_template"},
            {"class_type": "right_hotshot", "source": "hivemind_workflow"},
        ],
        "precedent_packet": {
            "options": [
                {"source_class_type": "right_hotshot"},
            ],
        },
        "precedent_slices": [
            {"source_class_type": "right_hotshot"},
        ],
    }

    assert _execute_research_sources(research) == [
        {"class_type": "right_hotshot", "source": "hivemind_workflow"}
    ]


def test_adapt_artifacts_do_not_emit_packet_without_compatible_workflow(tmp_path: Path) -> None:
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
            research=_LegacyResearchResult(
                summary="Found supplemental docs only.",
                sources=({"class_type": "wrong_ltx", "source": "object_info"},),
                workflow_precedent_status="no_compatible_workflow_found",
            ),
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
    assert notes["workflow_precedent_status"] == "no_compatible_workflow_found"
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
