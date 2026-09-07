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

import pytest

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


def _failed_result(
    detail_json_path: str,
    *,
    accepted_batch: list[dict[str, Any]] | None = None,
    candidate: dict[str, Any] | None = None,
    authority_receipt: dict[str, Any] | None = None,
) -> ExecutorResult:
    durable_response: dict[str, Any] = {
        "session_id": "sess-art",
        "turn_id": "turn-9",
        "accepted_batch": list(accepted_batch or []),
        "change_details": {"landed_operation_count": 0},
    }
    if candidate is not None:
        durable_response["candidate"] = {"graph": candidate, "state": "candidate"}
        durable_response["graph"] = candidate
    if authority_receipt is not None:
        durable_response["authority_receipt"] = authority_receipt
    failure: dict[str, Any] = {
        "failure_kind": "ValidationError",
        "stage": "implement",
        "message": "Emit refused: unknown port AUDIO_0.",
        "session_id": "sess-art",
        "turn_id": "turn-9",
        "detail_json_path": detail_json_path,
    }
    if candidate is not None:
        failure["candidate"] = {"graph": candidate, "state": "candidate"}
        failure["candidate_graph"] = candidate
    if authority_receipt is not None:
        failure["authority_receipt"] = authority_receipt
    return ExecutorResult.failure(
        kind="ValidationError",
        stage="implement",
        message="Emit refused: unknown port AUDIO_0.",
        report=Report(
            implementation=ImplementationResult(
                message="Emit refused: unknown port AUDIO_0.",
                failure=failure,
                durable_response=durable_response,
            )
        ),
    )


def _write_turn_dir(
    turn_dir: Path,
    *,
    candidate: dict[str, Any] | None = None,
) -> None:
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
        json.dumps(
            candidate
            or {"nodes": [{"id": 7, "type": "LTXVAudioVAEDecode"}]}
        ),
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


def _real_accepted_seed_fixture() -> tuple[
    dict[str, Any], dict[str, Any], list[dict[str, Any]], dict[str, Any]
]:
    from tests.test_comfy_nodes_agent_edit import _live_seed_edit_fixture
    from vibecomfy.comfy_nodes.agent.authority_receipts import build_authority_receipt

    fixture = _live_seed_edit_fixture()
    accepted = [{"statement_index": 0, "op": fixture["matching_op_dict"]}]
    delta = {"schema_version": "2.0.0", "ops": [fixture["matching_op_dict"]]}
    receipt = build_authority_receipt(
        session_id="sess-art",
        turn_id="turn-9",
        submit_graph=fixture["original"],
        cumulative_delta_envelope=delta,
        candidate=fixture["candidate"],
        response={"accepted_batch": accepted},
        schema_version="2.0.0",
        schema_provider=fixture["schema_provider"],
    )
    assert receipt.is_applyable is True
    return fixture["original"], fixture["candidate"], accepted, receipt.to_dict()


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
        response={
            "ok": False,
            "candidate_graph": {
                "nodes": [{"id": 7, "type": "LTXVAudioVAEDecode"}]
            },
            "change_details": {
                "landed_operation_count": 2,
                "batch_turns": [{"landed_op_count": 2}],
            },
        },
        output_dir=output_dir,
        status="failed",
    )

    assert "final.ui.json" in set(manifest["manifest"])
    final_ui = json.loads(
        (output_dir / "final.ui.json").read_text(encoding="utf-8")
    )
    final_nodes = final_ui.get("nodes") or []
    assert not any(node.get("id") == 7 for node in final_nodes)


@pytest.mark.parametrize(
    "malformed_batch",
    [
        {"statement_index": 0, "op": {"op": "add_node"}},
        [{"statement_index": 0}],
        ["add_node"],
        [{"statement_index": 0, "op": {}}],
        [{"statement_index": 0, "op": {"op": "invented"}}],
    ],
)
def test_malformed_accepted_batch_cannot_publish_failed_candidate(
    tmp_path: Path,
    malformed_batch: Any,
) -> None:
    turn_dir = tmp_path / "sessions" / "sess-art" / "turns" / "turn-9"
    _write_turn_dir(turn_dir)
    output_dir = tmp_path / "out"

    synthesize_headless_artifacts(
        request={"query": "wire the audio output", "graph": {"nodes": []}},
        result=_failed_result(str(turn_dir / "response.json")),
        response={"ok": False, "accepted_batch": malformed_batch},
        output_dir=output_dir,
        status="failed",
    )

    assert json.loads(
        (output_dir / "final.ui.json").read_text(encoding="utf-8")
    ) == {"nodes": []}


def test_failed_later_gate_preserves_candidate_with_durable_accepted_batch(
    tmp_path: Path,
) -> None:
    """A matched accepted edit survives a later gate failure as the product."""
    original, candidate, accepted, receipt = _real_accepted_seed_fixture()
    turn_dir = tmp_path / "sessions" / "sess-art" / "turns" / "turn-9"
    _write_turn_dir(turn_dir, candidate=candidate)
    output_dir = tmp_path / "out"

    synthesize_headless_artifacts(
        request={"query": "set the seed", "graph": original},
        result=_failed_result(
            str(turn_dir / "response.json"),
            accepted_batch=accepted,
            candidate=candidate,
            authority_receipt=receipt,
        ),
        response={"ok": False, "message": "A later emit check failed."},
        output_dir=output_dir,
        status="failed",
    )

    assert json.loads(
        (output_dir / "final.ui.json").read_text(encoding="utf-8")
    ) == candidate


@pytest.mark.parametrize("invalid_op", [{}, {"op": "invented"}])
def test_invalid_accepted_op_cannot_reuse_valid_candidate_receipt(
    tmp_path: Path,
    invalid_op: dict[str, Any],
) -> None:
    original, candidate, _accepted, receipt = _real_accepted_seed_fixture()
    turn_dir = tmp_path / "sessions" / "sess-art" / "turns" / "turn-9"
    _write_turn_dir(turn_dir, candidate=candidate)
    output_dir = tmp_path / "out"

    synthesize_headless_artifacts(
        request={"query": "set the seed", "graph": original},
        result=_failed_result(
            str(turn_dir / "response.json"),
            accepted_batch=[{"statement_index": 0, "op": invalid_op}],
            candidate=candidate,
            authority_receipt=receipt,
        ),
        response={"ok": False},
        output_dir=output_dir,
        status="failed",
    )

    assert json.loads(
        (output_dir / "final.ui.json").read_text(encoding="utf-8")
    ) == original


def test_failed_candidate_must_match_accepted_terminal_receipt(tmp_path: Path) -> None:
    original, candidate, accepted, receipt = _real_accepted_seed_fixture()
    mismatched = json.loads(json.dumps(candidate))
    mismatched["nodes"][0]["id"] = 999_999
    turn_dir = tmp_path / "sessions" / "sess-art" / "turns" / "turn-9"
    _write_turn_dir(turn_dir, candidate=mismatched)
    output_dir = tmp_path / "out"

    synthesize_headless_artifacts(
        request={"query": "set the seed", "graph": original},
        result=_failed_result(
            str(turn_dir / "response.json"),
            accepted_batch=accepted,
            candidate=mismatched,
            authority_receipt=receipt,
        ),
        response={"ok": False},
        output_dir=output_dir,
        status="failed",
    )

    assert json.loads(
        (output_dir / "final.ui.json").read_text(encoding="utf-8")
    ) == original


@pytest.mark.parametrize(
    ("field", "value"),
    [
        (("replay", "replay_ok"), "true"),
        (("replay", "verification_kind"), "invented_replay"),
        (("replay", "persisted_candidate_hash"), "e" * 64),
    ],
)
def test_malformed_or_unbound_receipt_cannot_publish_failed_candidate(
    tmp_path: Path,
    field: tuple[str, str],
    value: Any,
) -> None:
    original, candidate, accepted, receipt = _real_accepted_seed_fixture()
    malformed = json.loads(json.dumps(receipt))
    malformed[field[0]][field[1]] = value
    turn_dir = tmp_path / "sessions" / "sess-art" / "turns" / "turn-9"
    _write_turn_dir(turn_dir, candidate=candidate)
    output_dir = tmp_path / "out"

    synthesize_headless_artifacts(
        request={"query": "set the seed", "graph": original},
        result=_failed_result(
            str(turn_dir / "response.json"),
            accepted_batch=accepted,
            candidate=candidate,
            authority_receipt=malformed,
        ),
        response={"ok": False},
        output_dir=output_dir,
        status="failed",
    )

    assert json.loads(
        (output_dir / "final.ui.json").read_text(encoding="utf-8")
    ) == original


def test_replay_structural_hashes_must_bind_the_terminal_candidate(
    tmp_path: Path,
) -> None:
    original, candidate, accepted, receipt = _real_accepted_seed_fixture()
    malformed = json.loads(json.dumps(receipt))
    malformed["replay"]["persisted_candidate_hash"] = "e" * 64
    malformed["replay"]["recomputed_candidate_hash"] = "e" * 64
    turn_dir = tmp_path / "sessions" / "sess-art" / "turns" / "turn-9"
    _write_turn_dir(turn_dir, candidate=candidate)
    output_dir = tmp_path / "out"

    synthesize_headless_artifacts(
        request={"query": "set the seed", "graph": original},
        result=_failed_result(
            str(turn_dir / "response.json"),
            accepted_batch=accepted,
            candidate=candidate,
            authority_receipt=malformed,
        ),
        response={"ok": False},
        output_dir=output_dir,
        status="failed",
    )

    assert json.loads(
        (output_dir / "final.ui.json").read_text(encoding="utf-8")
    ) == original


@pytest.mark.parametrize("identity", [None, 9])
def test_failed_candidate_requires_exact_typed_terminal_identity(
    tmp_path: Path,
    identity: Any,
) -> None:
    original, candidate, accepted, receipt = _real_accepted_seed_fixture()
    turn_dir = tmp_path / "sessions" / "sess-art" / "turns" / "turn-9"
    _write_turn_dir(turn_dir, candidate=candidate)
    output_dir = tmp_path / "out"
    response: dict[str, Any] = {
        "ok": False,
        "accepted_batch": accepted,
        "candidate": {"graph": candidate},
        "authority_receipt": receipt,
        "turn_id": "turn-9",
    }
    if identity is not None:
        response["session_id"] = identity

    synthesize_headless_artifacts(
        request={"query": "set the seed", "graph": original},
        result=_failed_result(str(turn_dir / "response.json")),
        response=response,
        output_dir=output_dir,
        status="failed",
    )

    assert json.loads(
        (output_dir / "final.ui.json").read_text(encoding="utf-8")
    ) == original


def test_explicit_empty_response_batch_overrides_stale_result_batch(
    tmp_path: Path,
) -> None:
    original, candidate, accepted, receipt = _real_accepted_seed_fixture()
    turn_dir = tmp_path / "sessions" / "sess-art" / "turns" / "turn-9"
    _write_turn_dir(turn_dir, candidate=candidate)
    output_dir = tmp_path / "out"

    synthesize_headless_artifacts(
        request={"query": "set the seed", "graph": original},
        result=_failed_result(
            str(turn_dir / "response.json"),
            accepted_batch=accepted,
            candidate=candidate,
            authority_receipt=receipt,
        ),
        response={"ok": False, "accepted_batch": []},
        output_dir=output_dir,
        status="failed",
    )

    assert json.loads(
        (output_dir / "final.ui.json").read_text(encoding="utf-8")
    ) == original
