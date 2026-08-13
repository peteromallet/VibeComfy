from __future__ import annotations

import json
from pathlib import Path

from vibecomfy.agent.artifacts import _execute_research_sources, synthesize_headless_artifacts
from vibecomfy.executor.contracts import (
    ClassifyDecision,
    ExecutorResult,
    ImplementationResult,
    Report,
    ResearchResult,
)


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
            research=ResearchResult(
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
    ]
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
            research=ResearchResult(
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
        "model_request.json": True,
        "model_response.json": True,
    }
    assert (output_dir / "messages.jsonl").read_text(encoding="utf-8") == '{"role": "user"}\n'
    assert (output_dir / "model_request.json").is_file()
    assert (output_dir / "model_response.json").is_file()


def test_failed_model_call_artifact_has_complete_provenance(tmp_path: Path) -> None:
    """Every failed model call persists the complete provenance field set:
    phase, parse reason, zero/nonzero completion-token flag and count, finish
    reason, bounded raw preview, requested and resolved model, adapter/provider,
    and endpoint/base URL.  Previews are bounded and credentials are absent."""
    from vibecomfy.executor.core import _enrich_failure_envelope, _model_response_artifact
    from vibecomfy.comfy_nodes.agent.contracts import classify_failure

    class _FakeModelError(Exception):
        pass

    exc = _FakeModelError("boom")
    exc.parse_reason = "malformed_json"  # type: ignore[attr-defined]
    exc.raw_response_preview = "x" * 5000  # type: ignore[attr-defined]  # must be bounded
    exc.finish_reason = "stop"  # type: ignore[attr-defined]
    exc.completion_tokens = 42  # type: ignore[attr-defined]
    exc.completion_tokens_zero = False  # type: ignore[attr-defined]
    exc.prompt_tokens = 100  # type: ignore[attr-defined]
    exc.total_tokens = 142  # type: ignore[attr-defined]
    exc.model = "deepseek-v4-flash"  # type: ignore[attr-defined]
    exc.requested_model = "deepseek-v4-flash"  # type: ignore[attr-defined]
    exc.resolved_model = "deepseek-v4-flash"  # type: ignore[attr-defined]
    exc.adapter = "hermes"  # type: ignore[attr-defined]
    exc.provider = "openrouter"  # type: ignore[attr-defined]
    exc.phase = "classify"  # type: ignore[attr-defined]
    exc.endpoint = "https://api.deepseek.com/v1"  # type: ignore[attr-defined]
    exc.api_key = "sk-secret-credential"  # type: ignore[attr-defined]  # never persisted

    failure = classify_failure("agent_response", exc)
    failure = _enrich_failure_envelope(failure, exc, phase="classify", model="deepseek-v4-flash")
    artifact = _model_response_artifact(failure)

    assert artifact is not None
    error = artifact["turns"][0]["error"]
    required = {
        "phase",
        "parse_reason",
        "completion_tokens_zero",
        "completion_tokens",
        "finish_reason",
        "raw_response_preview",
        "requested_model",
        "resolved_model",
        "adapter",
        "provider",
        "endpoint",
    }
    missing = required - set(error)
    assert not missing, f"provenance fields missing: {sorted(missing)}"
    assert error["phase"] == "classify"
    assert error["parse_reason"] == "malformed_json"
    assert error["completion_tokens_zero"] is False
    assert error["completion_tokens"] == 42
    assert error["finish_reason"] == "stop"
    assert error["requested_model"] == "deepseek-v4-flash"
    assert error["resolved_model"] == "deepseek-v4-flash"
    assert error["adapter"] == "hermes"
    assert error["provider"] == "openrouter"
    assert error["endpoint"] == "https://api.deepseek.com/v1"
    # Bounded preview.
    assert len(error["raw_response_preview"]) <= 1200
    # Secrets never persisted.
    assert "sk-secret-credential" not in json.dumps(artifact)
    assert "api_key" not in error

    # The headless artifact boundary persists the same complete field set.
    output_dir = tmp_path / "out"
    failed_result = ExecutorResult.failure(
        kind="MalformedModelJSON",
        stage="classify",
        message="The model response could not be parsed. The graph is unchanged.",
        report=Report(
            classification_status="failed",
            model_response=artifact,
        ),
    )
    manifest = synthesize_headless_artifacts(
        request={"query": "parse me"},
        result=failed_result,
        response=failed_result.to_dict(),
        output_dir=output_dir,
        status="executor_failure",
    )
    assert "model_response.json" in manifest["manifest"]
    persisted = json.loads((output_dir / "model_response.json").read_text(encoding="utf-8"))
    persisted_error = persisted["turns"][0]["error"]
    missing_persisted = required - set(persisted_error)
    assert not missing_persisted, f"persisted provenance fields missing: {sorted(missing_persisted)}"
    assert "sk-secret-credential" not in json.dumps(persisted)
    classification = json.loads((output_dir / "classification.json").read_text(encoding="utf-8"))
    assert classification["classification_status"] == "failed"
    assert "plan" not in classification
