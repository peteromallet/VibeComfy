from concurrent.futures import ThreadPoolExecutor
import json

from vibecomfy.executor.agent_research_stage import (
    _clear_research_checkpoint,
    _load_research_checkpoint,
    _save_research_checkpoint,
    build_evidence_digest,
)
from vibecomfy.executor.evidence_pack import (
    EvidenceArtifact,
    EvidenceLedgerEntry,
    MAX_LEDGER_PROMPT_CHARS,
    MAX_LEDGER_PROMPT_ENTRIES,
    project_ledger_for_prompt,
)


def _entry(label: str) -> EvidenceLedgerEntry:
    return EvidenceLedgerEntry(
        decision="hivemind_get",
        conclusion=label,
        evidence_ids=(f"evidence:{label}",),
        uncertainty="",
        tool_status="ok",
    )


def _artifact(label: str) -> EvidenceArtifact:
    return EvidenceArtifact(
        evidence_id=f"evidence:{label}",
        kind="hivemind_record",
        body={"title": label, "full_body": f"FULL-BODY-{label}"},
        source="test",
    )


def test_research_checkpoint_requires_request_route_and_baseline_identity(tmp_path, monkeypatch):
    monkeypatch.setenv("VIBECOMFY_RESEARCH_CHECKPOINT_DIR", str(tmp_path))
    entries = [_entry("request-a")]
    artifacts = {"evidence:request-a": _artifact("request-a")}

    _save_research_checkpoint(
        "shared-session",
        request_identity="request-a",
        route="research",
        baseline_identity="baseline-a",
        ledger_entries=entries,
        artifacts=artifacts,
    )

    assert _load_research_checkpoint(
        "shared-session",
        request_identity="request-a",
        route="research",
        baseline_identity="baseline-a",
    ) == (entries, artifacts)
    assert _load_research_checkpoint(
        "shared-session",
        request_identity="request-b",
        route="research",
        baseline_identity="baseline-a",
    ) is None
    assert _load_research_checkpoint(
        "shared-session",
        request_identity="request-a",
        route="adapt",
        baseline_identity="baseline-a",
    ) is None
    assert _load_research_checkpoint(
        "shared-session",
        request_identity="request-a",
        route="research",
        baseline_identity="baseline-b",
    ) is None
    # A session id alone is not an authority token.
    assert _load_research_checkpoint("shared-session") is None

    _clear_research_checkpoint(
        "shared-session",
        request_identity="request-a",
        route="research",
        baseline_identity="baseline-a",
    )
    assert not list(tmp_path.glob("research_ckpt_*.json"))


def test_research_checkpoint_concurrent_publication_is_non_lossy(tmp_path, monkeypatch):
    monkeypatch.setenv("VIBECOMFY_RESEARCH_CHECKPOINT_DIR", str(tmp_path))

    def publish(label: str) -> None:
        _save_research_checkpoint(
            "shared-session",
            request_identity=label,
            route="research",
            baseline_identity="baseline",
            ledger_entries=[_entry(label)],
            artifacts={f"evidence:{label}": _artifact(label)},
        )

    with ThreadPoolExecutor(max_workers=2) as pool:
        list(pool.map(publish, ("request-a", "request-b")))

    assert len(list(tmp_path.glob("research_ckpt_*.json"))) == 2
    for label in ("request-a", "request-b"):
        loaded = _load_research_checkpoint(
            "shared-session",
            request_identity=label,
            route="research",
            baseline_identity="baseline",
        )
        assert loaded is not None
        assert loaded[0][0].conclusion == label
        assert loaded[1][f"evidence:{label}"].body["full_body"] == f"FULL-BODY-{label}"


def test_ledger_prompt_projection_bounds_entries_and_size_without_dropping_artifacts():
    raw_ledger = {
        "entries": [
            {
                "decision": f"decision-{index}",
                "conclusion": f"conclusion-{index}-" + ("x" * 4000),
                "evidence_ids": [f"evidence:{index}"],
                "uncertainty": "u" * 2000,
            }
            for index in range(100)
        ]
    }
    projected = project_ledger_for_prompt(raw_ledger)
    serialized = json.dumps(projected, sort_keys=True)

    assert len(projected["entries"]) <= MAX_LEDGER_PROMPT_ENTRIES
    assert len(serialized) <= MAX_LEDGER_PROMPT_CHARS
    assert "decision-0" not in serialized
    assert "decision-99" in serialized

    from vibecomfy.executor.prompts import build_reply_messages

    reply_content = build_reply_messages(
        "summarize the research",
        research_ledger=raw_ledger,
    )[1]["content"]
    assert "decision-0" not in reply_content
    assert "decision-99" in reply_content

    full_artifact = _artifact("kept")
    assert full_artifact.to_dict()["body"]["full_body"] == "FULL-BODY-kept"


def test_research_digest_bounds_oversized_tool_ledger():
    tool_calls = [
        {
            "tool": "hivemind_search",
            "status": "ok",
            "query": f"query-{index}",
            "evidence_ids": [f"evidence:{index}"],
            "conclusion": "c" * 2000,
        }
        for index in range(100)
    ]
    digest = build_evidence_digest(
        question="q",
        tool_calls=tool_calls,
        artifacts={},
    )

    assert len(digest) <= 4_000
    assert "query-99" in digest
    assert "query-0" not in digest
