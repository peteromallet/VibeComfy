"""RRSYN2-2: headless artifact synthesis must preserve the durable failed turn.

A failed implement phase that closed a durable turn must still produce
``implementation_payload.json`` / ``implementation_result.json`` and copy the
exact turn's artifacts (candidate.ui.json audit-only, batch_failure_evidence,
abort, messages, audit response) so the leg is adjudicable.
"""

from __future__ import annotations

import json
from pathlib import Path
from typing import Any

from vibecomfy.agent.artifacts import synthesize_headless_artifacts
from vibecomfy.executor.contracts import (
    ExecutorResult,
    ImplementationResult,
    Report,
)

_COPIED_TURN_ARTIFACTS = (
    "response.json",
    "messages.jsonl",
    "candidate.ui.json",
    "batch_failure_evidence.json",
    "abort.json",
    "audit.json",
)


def _failed_result(detail_json_path: str) -> ExecutorResult:
    return ExecutorResult.failure(
        kind="ValidationError",
        stage="implement",
        message="Emit refused: unknown port AUDIO_0.",
        report=Report(
            implementation=ImplementationResult(
                message="Emit refused: unknown port AUDIO_0.",
                failure={
                    "failure_kind": "ValidationError",
                    "stage": "implement",
                    "message": "Emit refused: unknown port AUDIO_0.",
                    "session_id": "sess-art",
                    "turn_id": "turn-9",
                    "detail_json_path": detail_json_path,
                },
                durable_response={
                    "session_id": "sess-art",
                    "turn_id": "turn-9",
                    "accepted_batch": [],
                    "change_details": {"landed_operation_count": 0},
                },
            )
        ),
    )


def _write_turn_dir(turn_dir: Path) -> None:
    turn_dir.mkdir(parents=True, exist_ok=True)
    (turn_dir / "response.json").write_text(
        json.dumps({"ok": False, "message": "Emit refused."}), encoding="utf-8"
    )
    (turn_dir / "messages.jsonl").write_text(
        json.dumps({"role": "user", "text": "wire the audio output"})
        + "\n"
        + json.dumps({"role": "assistant", "text": "Emit refused."})
        + "\n",
        encoding="utf-8",
    )
    (turn_dir / "candidate.ui.json").write_text(
        json.dumps({"nodes": [{"id": 7, "type": "LTXVAudioVAEDecode"}]}),
        encoding="utf-8",
    )
    (turn_dir / "batch_failure_evidence.json").write_text(
        json.dumps({"reason": "emit_refused", "port": "AUDIO_0"}),
        encoding="utf-8",
    )
    (turn_dir / "abort.json").write_text(
        json.dumps({"aborted": True}), encoding="utf-8"
    )
    (turn_dir / "audit.json").write_text(
        json.dumps({"audit": True}), encoding="utf-8"
    )


def test_failed_implementation_writes_payload_and_copies_exact_turn(
    tmp_path: Path,
) -> None:
    turn_dir = tmp_path / "sessions" / "sess-art" / "turns" / "turn-9"
    _write_turn_dir(turn_dir)
    output_dir = tmp_path / "out"

    manifest = synthesize_headless_artifacts(
        request={"query": "wire the audio output", "graph": {"nodes": []}},
        result=_failed_result(str(turn_dir / "response.json")),
        # A bare failure envelope: no top-level session identity — the
        # retained implementation failure is what locates the turn.
        response={"ok": False, "message": "Emit refused."},
        output_dir=output_dir,
        status="failed",
    )

    names = set(manifest["manifest"])
    assert "implementation_payload.json" in names
    assert "implementation_result.json" in names
    for copied in _COPIED_TURN_ARTIFACTS:
        assert copied in names, copied
        assert (output_dir / copied).is_file(), copied
    evidence = json.loads(
        (output_dir / "batch_failure_evidence.json").read_text(encoding="utf-8")
    )
    assert evidence["port"] == "AUDIO_0"
    retained = json.loads(
        (output_dir / "implementation_result.json").read_text(encoding="utf-8")
    )
    assert retained["failure"]["session_id"] == "sess-art"


def test_refused_candidate_never_becomes_final_ui(tmp_path: Path) -> None:
    """The audit-only candidate must never be published as final.ui.json."""
    turn_dir = tmp_path / "sessions" / "sess-art" / "turns" / "turn-9"
    _write_turn_dir(turn_dir)
    output_dir = tmp_path / "out"

    manifest: dict[str, Any] = synthesize_headless_artifacts(
        request={"query": "wire the audio output", "graph": {"nodes": []}},
        result=_failed_result(str(turn_dir / "response.json")),
        response={"ok": False},
        output_dir=output_dir,
        status="failed",
    )

    assert "final.ui.json" in set(manifest["manifest"])
    final_ui = json.loads(
        (output_dir / "final.ui.json").read_text(encoding="utf-8")
    )
    final_nodes = final_ui.get("nodes") or []
    assert not any(node.get("id") == 7 for node in final_nodes)
