#!/usr/bin/env python3
"""Validate workflow execution-spine evidence using only the standard library."""
from __future__ import annotations

import argparse
import hashlib
import json
import re
import subprocess
import sys
from pathlib import Path
from typing import Any, Iterable

FINAL_FIVE = {
    "audio-tts-narration-using-indextts-2": "c099f40b9208579ce320a0e5bcd9c579b78265f3639f828059efee41c26fb28d",
    "image-image-editing-with-qwen-image": "dc1062c6fd00ef18395d403ce725964c1d68e354ba9ac6ed56278b835fae20f3",
    "live-graph-explanation-smoke": "d93e79a71bd0bf6c496744ba81a1f9af9ee7672467a83d6100ffe638c3cd538c",
    "multi-video-based-character-replacement-using": "625ed91eacf070e1d531a806b69b8221bf7a02f1e5c2a42b98502b0ae48ac63d",
    "speed-distillation-research": "52b36af605acb7728c5809ac0961e901c5bc2fecc1f91f167911428a5d2efa7a",
}
CARD_ORDER = [
    "T0.0", "T0.1", "T0.3", "T0.2", "G0",
    "T1.1", "T1.2", "G1", "T2.1", "T2.2", "T2.3", "G2",
    "T3.1", "T3.2", "G3", "T4.1", "T4.2", "T4.3", "G4",
    "T5.1", "T5.2", "T5.3", "T5.4", "T5.5", "G5",
    "T6.1", "T6.2", "T6.3", "G6", "T7.1", "T7.2", "T7.3", "G7",
]
CARD_ONLY = [item for item in CARD_ORDER if item.startswith("T")]
GATE_CARDS = {
    "G0": ["T0.0", "T0.1", "T0.3", "T0.2"],
    "G1": ["T1.1", "T1.2"], "G2": ["T2.1", "T2.2", "T2.3"],
    "G3": ["T3.1", "T3.2"], "G4": ["T4.1", "T4.2", "T4.3"],
    "G5": ["T5.1", "T5.2", "T5.3", "T5.4", "T5.5"],
    "G6": ["T6.1", "T6.2", "T6.3"], "G7": ["T7.1", "T7.2", "T7.3"],
}


class EvidenceValidationError(ValueError):
    """Raised with a stable typed prefix for one failed validation class."""

    def __init__(self, error_type: str, detail: str):
        super().__init__(f"{error_type}: {detail}")
        self.error_type = error_type
        self.detail = detail


def _fail(error_type: str, detail: str) -> None:
    raise EvidenceValidationError(error_type, detail)


def _sha256(path: Path) -> str:
    return hashlib.sha256(path.read_bytes()).hexdigest()


def _path_from_record(raw: str, manifest_path: Path) -> Path:
    path = Path(raw)
    return path if path.is_absolute() else (manifest_path.parent / path)


def _as_records(value: Any) -> list[dict[str, Any]]:
    if not isinstance(value, list):
        return []
    return [item for item in value if isinstance(item, dict)]


def _task_id(record: dict[str, Any]) -> str | None:
    value = record.get("task_id", record.get("task"))
    return value if isinstance(value, str) else None


def _gate_id(record: dict[str, Any]) -> str | None:
    value = record.get("gate_id", record.get("gate"))
    return value if isinstance(value, str) and value.startswith("G") else None


def _complete(record: dict[str, Any]) -> bool:
    return record.get("status") in {"pass", "passed", "complete", "completed", "green"} or record.get("disposition") in {"pass", "passed", "complete", "completed", "green"}


def check_uniqueness(manifest: dict[str, Any]) -> None:
    raw_tasks = manifest.get("tasks")
    raw_gates = manifest.get("gates")
    if not isinstance(raw_tasks, list) or not isinstance(raw_gates, list):
        _fail("TASK_GATE_UNIQUENESS", "tasks and gates must be arrays")
    if any(not isinstance(item, dict) for item in raw_tasks):
        _fail("TASK_GATE_UNIQUENESS", "every task record must be an object")
    if any(not isinstance(item, dict) for item in raw_gates):
        _fail("TASK_GATE_UNIQUENESS", "every gate record must be an object")
    tasks = [item for item in raw_tasks if isinstance(item, dict)]
    task_ids = [_task_id(item) for item in tasks]
    if any(value is None for value in task_ids):
        _fail("TASK_GATE_UNIQUENESS", "task record lacks task_id")
    duplicates = sorted({value for value in task_ids if task_ids.count(value) > 1})
    if duplicates:
        _fail("TASK_GATE_UNIQUENESS", f"duplicate task_id: {duplicates}")
    gates = [item for item in raw_gates if isinstance(item, dict)]
    gate_ids = [_gate_id(item) for item in gates]
    if any(value is None for value in gate_ids):
        _fail("TASK_GATE_UNIQUENESS", "gate record lacks gate_id")
    duplicates = sorted({value for value in gate_ids if gate_ids.count(value) > 1})
    if duplicates:
        _fail("TASK_GATE_UNIQUENESS", f"duplicate gate disposition: {duplicates}")


def check_dependency_order(manifest: dict[str, Any]) -> None:
    tasks = _as_records(manifest.get("tasks"))
    ids = [_task_id(item) for item in tasks]
    expected_positions = {value: index for index, value in enumerate(CARD_ONLY)}
    previous = -1
    for value in ids:
        if value not in expected_positions:
            _fail("DEPENDENCY_ORDER", f"unknown task or gate in tasks: {value}")
        position = expected_positions[value]
        if position <= previous:
            _fail("DEPENDENCY_ORDER", f"task sequence is not a dependency-preserving subsequence: {ids}")
        previous = position
    gates = _as_records(manifest.get("gates"))
    present = set(ids)
    for gate in gates:
        gate_id = _gate_id(gate)
        if gate_id not in GATE_CARDS:
            _fail("DEPENDENCY_ORDER", f"unknown gate: {gate_id}")
        missing = [card for card in GATE_CARDS[gate_id] if card not in present]
        if _complete(gate) and missing:
            _fail("DEPENDENCY_ORDER", f"{gate_id} completes before constituent cards: {missing}")
        if not _complete(gate):
            later_cards = [card for card in ids if CARD_ORDER.index(card) > CARD_ORDER.index(gate_id)]
            if later_cards:
                _fail("DEPENDENCY_ORDER", f"card appears after open gate {gate_id}: {later_cards[0]}")
    ordered = [(item.get("sequence"), _task_id(item) or _gate_id(item)) for item in tasks + gates if isinstance(item.get("sequence"), int)]
    if ordered and ordered != sorted(ordered, key=lambda pair: pair[0]):
        _fail("DEPENDENCY_ORDER", "explicit record sequence is not increasing")


def _route_for_label(label: str) -> str | None:
    if "[XHARD" in label or re.search(r"\bmaterial judgment\b", label, re.I) or (label.startswith("G7") and "recommend" in label.lower()):
        return "grok-4.6"
    if "[HARD" in label:
        return "codex:gpt-5.6-luna"
    return None


def check_model_routing(manifest: dict[str, Any]) -> None:
    for record in _as_records(manifest.get("tasks")) + _as_records(manifest.get("gates")):
        label = record.get("label", "")
        route = record.get("model_route")
        expected = _route_for_label(label) if isinstance(label, str) else None
        if expected and route != expected:
            _fail("MODEL_ROUTING", f"{_task_id(record) or _gate_id(record)} requires {expected}, got {route}")
        if _gate_id(record) == "G7" and route != "grok-4.6":
            _fail("MODEL_ROUTING", "final G7 recommendation must use grok-4.6")


def _same_identity(left: Any, right: Any) -> bool:
    if left is None or right is None:
        return False
    return str(left) == str(right)


def _identity_values(record: dict[str, Any], *keys: str) -> list[Any]:
    values: list[Any] = []
    for key in keys:
        value = record.get(key)
        if isinstance(value, dict):
            values.extend(value.get(name) for name in ("agent_id", "email", "author_email") if value.get(name) is not None)
        elif value is not None:
            values.append(value)
    return values


def check_reviewer_independence(manifest: dict[str, Any]) -> None:
    for record in _as_records(manifest.get("tasks")):
        label = str(record.get("label", ""))
        role = str(record.get("role", ""))
        if role != "reviewer" and "review" not in label.lower():
            continue
        reviewers = _identity_values(record, "reviewer", "reviewer_agent_id", "reviewer_email")
        implementers = _identity_values(record, "implementer", "implementer_agent_id", "implementer_email")
        implementers += _identity_values(record, "commit_author_email", "reviewed_commit_author_email", "reviewed_commit_agent_id", "reviewed_commit")
        if any(_same_identity(reviewer, implementer) for reviewer in reviewers for implementer in implementers):
            _fail("REVIEWER_INDEPENDENCE", f"reviewer reviews own implementation: {_task_id(record)}")


def check_finding_chains(manifest: dict[str, Any]) -> None:
    tasks = _as_records(manifest.get("tasks"))
    for finding in _as_records(manifest.get("findings")):
        if str(finding.get("severity", "")).lower() != "must":
            continue
        finding_id = finding.get("finding_id", finding.get("id"))
        classification = finding.get("classification")
        revision_id = finding.get("revision_task_id", finding.get("revision"))
        rereview_id = finding.get("re_review_task_id", finding.get("rereview"))
        if not isinstance(classification, str) or classification not in {"HARD", "XHARD"}:
            _fail("FINDING_CHAIN", f"must finding {finding_id} lacks HARD/XHARD classification")
        revision = _find_task(tasks, str(revision_id)) if revision_id else None
        rereview = _find_task(tasks, str(rereview_id)) if rereview_id else None
        if revision is None or not revision.get("evidence_link"):
            _fail("FINDING_CHAIN", f"must finding {finding_id} lacks evidence-linked revision")
        if rereview is None or str(rereview.get("role", "")) != "reviewer" or not _complete(rereview):
            _fail("FINDING_CHAIN", f"must finding {finding_id} lacks closed independent re-review")
        original = finding.get("implementer", finding.get("implementer_agent_id"))
        reviewer = rereview.get("reviewer", rereview.get("reviewer_agent_id"))
        if _same_identity(original, reviewer):
            _fail("FINDING_CHAIN", f"must finding {finding_id} is re-reviewed by original implementer")
        initial_reviewer = finding.get("reviewer", finding.get("reviewer_agent_id"))
        if _same_identity(initial_reviewer, reviewer):
            _fail("FINDING_CHAIN", f"must finding {finding_id} was re-reviewed by the same reviewer")


def _iter_digest_refs(value: Any, prefix: str = "manifest") -> Iterable[tuple[str, str, str]]:
    if isinstance(value, dict):
        path = value.get("path")
        digest = value.get("sha256", value.get("digest"))
        if isinstance(path, str) and isinstance(digest, str) and re.fullmatch(r"[0-9a-fA-F]{64}", digest):
            yield prefix, path, digest.lower()
        for key, child in value.items():
            yield from _iter_digest_refs(child, f"{prefix}.{key}")
    elif isinstance(value, list):
        for index, child in enumerate(value):
            yield from _iter_digest_refs(child, f"{prefix}[{index}]")


def check_artifact_digests(manifest: dict[str, Any], manifest_path: Path) -> None:
    for location, raw_path, expected in _iter_digest_refs(manifest):
        path = _path_from_record(raw_path, manifest_path)
        if not path.is_file():
            _fail("ARTIFACT_DIGEST", f"{location} references missing artifact: {raw_path}")
        actual = _sha256(path)
        if actual != expected:
            _fail("ARTIFACT_DIGEST", f"{location} digest mismatch for {raw_path}: {actual} != {expected}")


def check_test_singletons(manifest: dict[str, Any]) -> None:
    shards = _as_records(manifest.get("shards"))
    ids = [item.get("shard_id", item.get("id")) for item in shards]
    if any(not isinstance(value, str) or not value for value in ids):
        _fail("TEST_SINGLETON", "every focused shard record requires a shard_id")
    duplicate_ids = sorted({value for value in ids if ids.count(value) > 1})
    if duplicate_ids:
        _fail("TEST_SINGLETON", f"focused shard appears more than once: {duplicate_ids}")
    broad = [item for item in shards if item.get("shard_id", item.get("id")) == "broad_suite_once_v1" or item.get("singleton_key") == "broad_suite_once_v1"]
    broad += [item for item in _as_records(manifest.get("broad_suite")) if item.get("singleton_key") == "broad_suite_once_v1"]
    if len(broad) > 1:
        _fail("TEST_SINGLETON", "broad_suite_once_v1 appears more than once")
    g6 = next((gate for gate in _as_records(manifest.get("gates")) if _gate_id(gate) == "G6"), None)
    if g6 and _complete(g6) and len(broad) != 1:
        _fail("TEST_SINGLETON", "G6 is complete but broad_suite_once_v1 is not recorded exactly once")


def _final_five_mapping(value: Any) -> dict[str, str]:
    if isinstance(value, dict):
        if "scenarios" in value and isinstance(value["scenarios"], list):
            return _final_five_mapping(value["scenarios"])
        return {str(key): str(val) for key, val in value.items() if isinstance(val, str)}
    if isinstance(value, list):
        result: dict[str, str] = {}
        for item in value:
            if isinstance(item, dict):
                scenario_id = item.get("scenario_id", item.get("id"))
                digest = item.get("locked_input_sha256", item.get("sha256"))
                if isinstance(scenario_id, str) and isinstance(digest, str):
                    result[scenario_id] = digest
        return result
    return {}


def check_final_five(manifest: dict[str, Any]) -> None:
    actual = _final_five_mapping(manifest.get("final_five"))
    if actual != FINAL_FIVE:
        _fail("FINAL_FIVE_INTEGRITY", f"locked scenario identity/digests differ: {actual}")


def _leg_receipts(live_run: dict[str, Any]) -> list[Any]:
    value = live_run.get("leg_receipts", live_run.get("legs", []))
    return value if isinstance(value, list) else []


def check_live_run(manifest: dict[str, Any]) -> None:
    runs = _as_records(manifest.get("live_runs"))
    authoritative = [run for run in runs if run.get("authoritative", True) and run.get("status", "authoritative") not in {"superseded", "non_authoritative"}]
    if len(authoritative) > 1:
        _fail("LIVE_RUN_SINGLETON", "more than one authoritative G7.2 live_run")
    for run in authoritative:
        if run.get("task_id") not in {None, "T7.2"} and run.get("card") not in {None, "T7.2"}:
            _fail("LIVE_RUN_SINGLETON", "authoritative live_run is not G7.2")
        if run.get("concurrency") != 10 or run.get("mode") != "5x2":
            _fail("LIVE_RUN_SINGLETON", "authoritative live_run must be concurrency 10 and mode 5x2")
        receipts = _leg_receipts(run)
        keys = []
        for receipt in receipts:
            if isinstance(receipt, dict):
                keys.append(receipt.get("leg_id", receipt.get("receipt_id")))
            else:
                keys.append(receipt)
        if len(receipts) != 10 or any(key is None for key in keys) or len(set(keys)) != 10:
            _fail("LIVE_RUN_SINGLETON", "authoritative live_run must contain exactly ten unique leg_receipts")


def _walk_assessments(value: Any) -> Iterable[dict[str, Any]]:
    if isinstance(value, dict):
        if "verdict" in value or "assessment" in value:
            yield value
        for child in value.values():
            yield from _walk_assessments(child)
    elif isinstance(value, list):
        for child in value:
            yield from _walk_assessments(child)


def check_verdicts(manifest: dict[str, Any]) -> None:
    for assessment in _walk_assessments(manifest.get("live_runs", [])):
        verdict = assessment.get("verdict")
        normalized = verdict.lower() if isinstance(verdict, str) else verdict
        if normalized == "process_completed":
            _fail("PROCESS_COMPLETION_VERDICT", "final leg uses process_completed instead of product assessment")
        if normalized in {"fail", "undetermined"} and not assessment.get("reason") and not assessment.get("typed_reason"):
            _fail("PROCESS_COMPLETION_VERDICT", f"{normalized} leg lacks a typed reason")
        if normalized not in {None, "product_pass", "fail", "undetermined"}:
            _fail("PROCESS_COMPLETION_VERDICT", f"unsupported final leg verdict: {verdict}")


def validate_manifest(manifest: dict[str, Any], manifest_path: str | Path = "manifest.json") -> None:
    path = Path(manifest_path).resolve()
    if not isinstance(manifest, dict):
        _fail("MANIFEST_SHAPE", "manifest must be a JSON object")
    check_uniqueness(manifest)
    check_dependency_order(manifest)
    check_model_routing(manifest)
    check_reviewer_independence(manifest)
    check_finding_chains(manifest)
    check_artifact_digests(manifest, path)
    check_test_singletons(manifest)
    check_final_five(manifest)
    check_live_run(manifest)
    check_verdicts(manifest)


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("manifest", type=Path)
    args = parser.parse_args(argv)
    try:
        manifest = json.loads(args.manifest.read_text(encoding="utf-8"))
        validate_manifest(manifest, args.manifest)
    except EvidenceValidationError as exc:
        print(str(exc), file=sys.stderr)
        return 1
    except (OSError, json.JSONDecodeError) as exc:
        print(f"MANIFEST_SHAPE: cannot load manifest: {exc}", file=sys.stderr)
        return 1
    print(f"OK: {args.manifest}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
