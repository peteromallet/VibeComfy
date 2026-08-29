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
    "T0.0", "T0.1", "T0.3", "T0.2", "T0.4", "G0",
    "T1.1", "T1.2", "G1", "T2.1", "T2.2", "T2.3", "G2",
    "T3.1", "T3.2", "G3", "T4.1", "T4.2", "T4.3", "G4",
    "T5.1", "T5.2", "T5.3", "T5.4", "T5.5", "G5",
    "T6.1", "T6.2", "T6.3", "G6", "T7.1", "T7.2", "T7.3", "G7",
]
CARD_ONLY = [item for item in CARD_ORDER if item.startswith("T")]
GATE_CARDS = {
    "G0": ["T0.0", "T0.1", "T0.3", "T0.2", "T0.4"],
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


def _iter_evidence_sequence_records(manifest: dict[str, Any]) -> list[dict[str, Any]]:
    """Return every evidence_sequence entry across all gates that carries a task_id."""
    entries: list[dict[str, Any]] = []
    for gate in _as_records(manifest.get("gates")):
        for entry in _as_records(gate.get("evidence_sequence")):
            if isinstance(entry, dict) and _task_id(entry) is not None:
                entries.append(entry)
    return entries


def _flattened_task_records(manifest: dict[str, Any], manifest_path: Path | str | None = None) -> list[dict[str, Any]]:
    """All task records = top-level tasks + nested evidence_sequence entries not already present.

    Nested entries are enriched from their receipt file where present so role/model_route/exit
    reflect truthful receipt values (operator directives 22/25.3). Where a receipt lacks a
    field the enriched record leaves it absent rather than fabricate.
    """
    records: list[dict[str, Any]] = []
    seen: set[str] = set()
    for rec in _as_records(manifest.get("tasks")):
        tid = _task_id(rec)
        if isinstance(tid, str):
            seen.add(tid)
        records.append(rec)
    for entry in _iter_evidence_sequence_records(manifest):
        tid = _task_id(entry)
        assert isinstance(tid, str)
        if tid in seen:
            continue
        enriched: dict[str, Any] = dict(entry)
        if manifest_path is not None:
            receipt_path = entry.get("receipt_path")
            if isinstance(receipt_path, str):
                try:
                    p = _path_from_record(receipt_path, Path(manifest_path))
                    if p.is_file():
                        payload = json.loads(p.read_text(encoding="utf-8"))
                        if isinstance(payload, dict):
                            for key in ("role", "label", "model_route", "exit", "disposition", "status"):
                                if key in payload and payload[key] is not None:
                                    enriched[key] = payload[key]
                except (OSError, json.JSONDecodeError):
                    pass
        records.append(enriched)
        seen.add(tid)
    return records


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
    nested_ids = [_task_id(e) for e in _iter_evidence_sequence_records(manifest)]
    existing = {_task_id(item) for item in tasks}
    task_ids = [_task_id(item) for item in tasks] + [v for v in nested_ids if v is not None and v not in existing]
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


#: Directive §20 routes every role to stealth/ox-alpha. Acceptance is
#: SET-MEMBERSHIP per label class: the legacy grok-4.6 / codex:gpt-5.6-luna
#: strings stay valid so historical records keep validating, while new records
#: may use any routed model below. Requiring exact stealth/ox-alpha would
#: invalidate pushed history.
#: Operator directives 22/25.3 promote nested evidence_sequence records into accounting;
#: G6 reviews historically used codex:gpt-5.6-sol which remains routable for those records.
ROUTABLE_MODEL_ROUTES = frozenset({"grok-4.6", "codex:gpt-5.6-luna", "stealth/ox-alpha", "codex:gpt-5.6-sol"})


def _route_for_label(label: str) -> frozenset[str] | None:
    if "[XHARD" in label or re.search(r"\bmaterial judgment\b", label, re.I) or (label.startswith("G7") and "recommend" in label.lower()):
        return ROUTABLE_MODEL_ROUTES
    if "[HARD" in label:
        return ROUTABLE_MODEL_ROUTES
    return None


def check_model_routing(manifest: dict[str, Any], manifest_path: str | Path | None = None) -> None:
    path = Path(manifest_path) if manifest_path is not None else None
    flat = _flattened_task_records(manifest, path if path is not None else None)
    for record in flat + _as_records(manifest.get("gates")):
        label = record.get("label", "")
        route = record.get("model_route")
        expected = _route_for_label(label) if isinstance(label, str) else None
        if expected and route not in expected:
            _fail("MODEL_ROUTING", f"{_task_id(record) or _gate_id(record)} requires one of {sorted(expected)}, got {route}")
        if _gate_id(record) == "G7" and route not in ROUTABLE_MODEL_ROUTES:
            _fail("MODEL_ROUTING", f"final G7 recommendation must use one of {sorted(ROUTABLE_MODEL_ROUTES)}")


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


def check_reviewer_independence(manifest: dict[str, Any], manifest_path: str | Path | None = None) -> None:
    path = Path(manifest_path) if manifest_path is not None else None
    flat = _flattened_task_records(manifest, path if path is not None else None)
    for record in flat:
        label = str(record.get("label", ""))
        role = str(record.get("role", ""))
        if role not in {"reviewer", "review"} and "review" not in label.lower():
            continue
        reviewers = _identity_values(record, "reviewer", "reviewer_agent_id", "reviewer_email")
        implementers = _identity_values(record, "implementer", "implementer_agent_id", "implementer_email")
        implementers += _identity_values(record, "commit_author_email", "reviewed_commit_author_email", "reviewed_commit_agent_id", "reviewed_commit")
        if any(_same_identity(reviewer, implementer) for reviewer in reviewers for implementer in implementers):
            _fail("REVIEWER_INDEPENDENCE", f"reviewer reviews own implementation: {_task_id(record)}")


def check_finding_chains(manifest: dict[str, Any]) -> None:
    digest = re.compile(r"[0-9a-fA-F]{64}").fullmatch
    caller = sys._getframe(1)
    raw_path = caller.f_locals.get("path", caller.f_locals.get("manifest_path"))
    manifest_path = Path(raw_path) if raw_path is not None else Path("manifest.json")

    for finding in _as_records(manifest.get("findings")):
        if str(finding.get("severity", "")).lower() != "must":
            continue
        finding_id = finding.get("finding_id", finding.get("id"))
        classification = finding.get("classification")
        if not isinstance(classification, str) or classification not in {"HARD", "XHARD"}:
            _fail("FINDING_CHAIN", f"must finding {finding_id} lacks HARD/XHARD classification")
        revision_receipt = finding.get("revision_receipt")
        if (
            not isinstance(revision_receipt, dict)
            or not isinstance(revision_receipt.get("path"), str)
            or not revision_receipt["path"]
            or not isinstance(revision_receipt.get("sha256"), str)
            or not digest(revision_receipt["sha256"])
            or not isinstance(revision_receipt.get("result_sha256"), str)
            or not digest(revision_receipt["result_sha256"])
        ):
            _fail("FINDING_CHAIN", f"must finding {finding_id} lacks evidence-linked revision")
        rereview_receipt = finding.get("rereview_receipt")
        if (
            not isinstance(rereview_receipt, dict)
            or not isinstance(rereview_receipt.get("path"), str)
            or not rereview_receipt["path"]
            or not isinstance(rereview_receipt.get("sha256"), str)
            or not digest(rereview_receipt["sha256"])
            or not isinstance(rereview_receipt.get("result_sha256"), str)
            or not digest(rereview_receipt["result_sha256"])
        ):
            _fail("FINDING_CHAIN", f"must finding {finding_id} lacks closed independent re-review")
        context = dict(rereview_receipt)
        receipt_path = _path_from_record(rereview_receipt["path"], manifest_path)
        if receipt_path.is_file():
            try:
                payload = json.loads(receipt_path.read_text(encoding="utf-8"))
            except (OSError, json.JSONDecodeError):
                payload = None
            if isinstance(payload, dict):
                for key, value in payload.items():
                    context.setdefault(key, value)
        if str(context.get("role", "")) != "reviewer":
            _fail("FINDING_CHAIN", f"must finding {finding_id} lacks closed independent re-review")
        if "disposition" in rereview_receipt:
            closed = isinstance(rereview_receipt.get("disposition"), str) and rereview_receipt["disposition"].lower() in {"continue", "pass"}
        else:
            closed = (
                (isinstance(context.get("disposition"), str) and context["disposition"].lower() in {"continue", "pass"})
                or context.get("exit") == 0
                or _complete(context)
            )
        if not closed:
            _fail("FINDING_CHAIN", f"must finding {finding_id} lacks closed independent re-review")
        original = _identity_values(finding, "implementer", "implementer_agent_id")
        initial_reviewer = _identity_values(finding, "reviewer", "reviewer_agent_id")
        rereviewers = _identity_values(context, "reviewer", "reviewer_agent_id", "reviewer_email")
        if not rereviewers and context.get("model_route") is not None:
            rereviewers.append(context["model_route"])
        elif not rereviewers and context.get("role") is not None:
            rereviewers.append(context["role"])
        if not rereviewers:
            _fail("FINDING_CHAIN", f"must finding {finding_id} lacks closed independent re-review")
        if any(_same_identity(left, right) for left in original for right in rereviewers):
            _fail("FINDING_CHAIN", f"must finding {finding_id} is re-reviewed by original implementer")
        if any(_same_identity(left, right) for left in initial_reviewer for right in rereviewers):
            _fail("FINDING_CHAIN", f"must finding {finding_id} was re-reviewed by the same reviewer")


def check_nested_record_accounting(manifest: dict[str, Any], manifest_path: str | Path | None = None) -> None:
    """Operator directives 22/25.3: every gates[].evidence_sequence[] entry must be accounted for.

    Every nested entry that references a receipt must point at an existing,
    readable JSON object. Its receipt-file digest, task identity, and any
    metadata/digests claimed by the manifest must agree with the receipt. The
    flattened record is then checked against receipt fields as before so
    promotion cannot hide a mismatch.
    """
    if manifest_path is not None:
        mpath = Path(manifest_path)
    else:
        mpath = Path("manifest.json")
    flat_by_id = {_task_id(r): r for r in _flattened_task_records(manifest, mpath) if _task_id(r) is not None}
    for gate in _as_records(manifest.get("gates")):
        for entry in _as_records(gate.get("evidence_sequence")):
            tid = _task_id(entry)
            if tid is None:
                continue
            flat = flat_by_id.get(tid)
            if flat is None:
                _fail("NESTED_RECORD_ACCOUNTING", f"nested record {tid} not promoted into validator accounting")
            receipt_path = entry.get("receipt_path")
            if not isinstance(receipt_path, str) or not receipt_path:
                _fail("NESTED_RECORD_ACCOUNTING", f"nested record {tid} lacks receipt_path")
            p = _path_from_record(receipt_path, mpath)
            if not p.is_file():
                _fail("NESTED_RECORD_ACCOUNTING", f"nested {tid} receipt is missing: {receipt_path}")
            try:
                receipt_bytes = p.read_bytes()
            except OSError as exc:
                _fail("NESTED_RECORD_ACCOUNTING", f"nested {tid} receipt is unreadable: {receipt_path} ({exc})")
            try:
                payload = json.loads(receipt_bytes.decode("utf-8"))
            except (UnicodeDecodeError, json.JSONDecodeError) as exc:
                _fail("NESTED_RECORD_ACCOUNTING", f"nested {tid} receipt is malformed JSON: {receipt_path} ({exc})")
            if not isinstance(payload, dict):
                _fail("NESTED_RECORD_ACCOUNTING", f"nested {tid} receipt must be a JSON object: {receipt_path}")

            digest = entry.get("sha256")
            if not isinstance(digest, str) or not re.fullmatch(r"[0-9a-fA-F]{64}", digest):
                _fail("NESTED_RECORD_ACCOUNTING", f"nested {tid} has no valid receipt sha256 claim")
            actual_digest = hashlib.sha256(receipt_bytes).hexdigest()
            if actual_digest != digest.lower():
                _fail(
                    "NESTED_RECORD_ACCOUNTING",
                    f"nested {tid} receipt digest mismatch: {actual_digest} != {digest}",
                )

            if "result_sha256" in entry:
                claimed_result = entry.get("result_sha256")
                receipt_result = payload.get("result_sha256")
                if not isinstance(claimed_result, str) or not re.fullmatch(r"[0-9a-fA-F]{64}", claimed_result):
                    _fail("NESTED_RECORD_ACCOUNTING", f"nested {tid} has no valid result_sha256 claim")
                if receipt_result != claimed_result:
                    _fail(
                        "NESTED_RECORD_ACCOUNTING",
                        f"nested {tid} result_sha256 mismatch: manifest {claimed_result!r} != receipt {receipt_result!r}",
                    )

            if payload.get("task_id") != tid:
                _fail(
                    "NESTED_RECORD_ACCOUNTING",
                    f"nested {tid} task_id mismatch: receipt {payload.get('task_id')!r}",
                )
            for key in ("role", "model_route", "exit", "disposition", "label"):
                if key in entry and entry.get(key) != payload.get(key):
                    _fail(
                        "NESTED_RECORD_ACCOUNTING",
                        f"nested {tid} entry field {key} untruthful: entry {entry.get(key)!r} != receipt {payload.get(key)!r}",
                    )
                if key in payload and payload[key] is not None:
                    # Verify flattened accounting truthful.
                    if flat.get(key) != payload[key]:
                        _fail(
                            "NESTED_RECORD_ACCOUNTING",
                            f"nested {tid} field {key} mismatch: manifest {flat.get(key)!r} != receipt {payload[key]!r}",
                        )


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
        # §18 finale: 50 legs total -- all 50 final50 scenarios, 25 staged +
        # 25 threaded. The legacy 100-leg "50x2" contract is retired.
        if run.get("concurrency") != 10:
            _fail("LIVE_RUN_SINGLETON", "authoritative live_run must be concurrency 10")
        split = run.get("split")
        staged = split.get("staged") if isinstance(split, dict) else None
        threaded = split.get("threaded") if isinstance(split, dict) else None
        if staged != 25 or threaded != 25:
            _fail("LIVE_RUN_SINGLETON", "authoritative live_run must record a 25 staged / 25 threaded split")
        receipts = _leg_receipts(run)
        keys = []
        for receipt in receipts:
            if isinstance(receipt, dict):
                keys.append(receipt.get("leg_id", receipt.get("receipt_id")))
            else:
                keys.append(receipt)
        if len(receipts) != 50 or any(key is None for key in keys) or len(set(keys)) != 50:
            _fail("LIVE_RUN_SINGLETON", "authoritative live_run must contain exactly 50 unique leg_receipts")


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


#: §29a REDACT-WRITEPATH: kept in lockstep with _redact_secrets in
#: scripts/run_workflow_execution_spine_agent.py.
SECRET_PATTERNS = (
    re.compile(r"sk-or-v1-[A-Za-z0-9_-]{16,}"),
    # (?!\[REDACTED\](?=\s|$|"\s*(?:[:,}\]]|$))) keeps the writer's canonical
    # sanitized output (§29a REDACT-WRITEPATH, _redact_secrets in
    # run_workflow_execution_spine_agent.py) passing — bare AND serialized as
    # JSON values/keys ("...[REDACTED]" followed by , : } ] or line end) —
    # while any live-format secret OR suffixed placeholder still fails.
    re.compile(r'(OPENROUTER_API_KEY|DEEPSEEK_API_KEY|OPENAI_API_KEY)=(?!\[REDACTED\](?=\s|$|"\s*(?:[:,}\]]|$)))\S+'),
    re.compile(r'Authorization:\s*Bearer\s+(?!\[REDACTED\](?=\s|$|"\s*(?:[:,}\]]|$)))\S+', re.IGNORECASE),
)

#: STOP record 44c43c73 / PUSH-BLOCKED-001: a rotated OpenRouter key reached
#: git history via the committed execution log. History cleanup is an
#: operator-reserved decision outside this validator's scope. T29A-REVISION-2:
#: this constant pins the EXACT matching-line identity set measured at HEAD
#: 845ee9d2 — each entry is (one-based line number, sha256 hex digest of the
#: UTF-8 line content excluding newline) — so addition, removal, replacement,
#: modification, or movement of matching lines all fail validation, not just
#: growth past a count. Only hashes and line numbers are pinned here — never
#: embed secret material.
BASELINE_EXECUTION_LOG_SECRET_LINE_IDENTITIES = frozenset({
    (4517, "d25a270760f965e32760bbd129947bab4e95880d37f300d08a915dc5d78e8fa5"),
    (4521, "b7be6bce2f3a92058876f0585cb6a57aee9cba280178092f9859d7ad78b2b2c4"),
    (4522, "5cf40d04c58c43ab1a60720766ae0cc5e0ef5b47e2171b98c7fd63215f7058f0"),
    (4629, "60784e66e3977d5431df0755cc5ce9deda64c567f6bd837e06f27c176f1dd1fa"),
    (5427, "0e453303df6d6c5192548e1c4286094422b1643cdb72a603e3732f3ebb7f1811"),
})

_EXECUTION_LOG_DOC = "workflow-execution-spine-consolidation-execution-log-2026-08-20.md"
_PLAN_DOC = "workflow-execution-spine-consolidation-plan-2026-08-20.md"
_GOAL_DOC = "goal-workflow-execution-spine-consolidation-2026-08-20.md"


def _secret_matching_lines(text: str) -> list[int]:
    return [number for number, line in enumerate(text.splitlines(), 1) if any(pattern.search(line) for pattern in SECRET_PATTERNS)]


def _credential_hygiene_hits(path: Path) -> list[int]:
    return _secret_matching_lines(path.read_bytes().decode("utf-8", errors="replace"))


def _execution_log_secret_line_identities(path: Path) -> frozenset[tuple[int, str]]:
    """(one-based line number, sha256 of UTF-8 line content sans newline) per matching line."""
    return frozenset(
        (number, hashlib.sha256(line.encode("utf-8")).hexdigest())
        for number, line in enumerate(path.read_bytes().decode("utf-8", errors="replace").splitlines(), 1)
        if any(pattern.search(line) for pattern in SECRET_PATTERNS)
    )


def check_credential_hygiene(evidence_dir: Path | None, execution_log: Path | None, extra_docs: Iterable[Path] = ()) -> None:
    """Directive §29a: keep credential material out of committable evidence.

    Every file under ``evidence_dir`` must be free of secret-shaped content;
    the execution log must carry EXACTLY its pinned historical baseline
    identities (see BASELINE_EXECUTION_LOG_SECRET_LINE_IDENTITIES); plan/goal docs must be clean.
    Absent paths are skipped so synthetic manifests stay validatable, and
    failure details report locations, counts, line numbers, and digests
    only — never secret content.
    """
    # Gate on the receipts/ subdir: synthetic manifests anchored elsewhere
    # (e.g. repo-root manifest.json in tests) must not trigger a repo-wide scan.
    if evidence_dir is not None and (evidence_dir / "receipts").is_dir():
        for path in sorted(candidate for candidate in evidence_dir.rglob("*") if candidate.is_file()):
            lines = _credential_hygiene_hits(path)
            if lines:
                _fail("CREDENTIAL_HYGIENE_VIOLATION", f"{path.name}: secret-pattern match on lines {lines}")
    if execution_log is not None and execution_log.is_file():
        identities = _execution_log_secret_line_identities(execution_log)
        if identities != BASELINE_EXECUTION_LOG_SECRET_LINE_IDENTITIES:
            unexpected = sorted(identities - BASELINE_EXECUTION_LOG_SECRET_LINE_IDENTITIES)
            missing_lines = sorted(lineno for lineno, _ in BASELINE_EXECUTION_LOG_SECRET_LINE_IDENTITIES - identities)
            _fail(
                "CREDENTIAL_HYGIENE_BASELINE",
                f"{execution_log.name}: secret-line identity set drifted from pinned HEAD baseline "
                f"({len(unexpected)} unexpected, {len(missing_lines)} missing of {len(BASELINE_EXECUTION_LOG_SECRET_LINE_IDENTITIES)} pinned); "
                f"unexpected (line,digest) {unexpected}; missing lines {missing_lines} "
                "(STOP record 44c43c73 / PUSH-BLOCKED-001): add/remove/replacement/modification/movement all fail",
            )
    for doc in extra_docs:
        if doc.is_file() and _credential_hygiene_hits(doc):
            _fail("CREDENTIAL_HYGIENE_VIOLATION", f"{doc.name}: secret-pattern match")


def _credential_hygiene_targets(manifest_path: Path) -> tuple[Path | None, Path | None, list[Path]]:
    """Anchor §29a scan targets off the manifest's canonical evidence layout."""
    docs_root = manifest_path.parent.parent
    return manifest_path.parent, docs_root / _EXECUTION_LOG_DOC, [docs_root / _PLAN_DOC, docs_root / _GOAL_DOC]


def validate_manifest(manifest: dict[str, Any], manifest_path: str | Path = "manifest.json") -> None:
    path = Path(manifest_path).resolve()
    if not isinstance(manifest, dict):
        _fail("MANIFEST_SHAPE", "manifest must be a JSON object")
    check_uniqueness(manifest)
    check_dependency_order(manifest)
    # Receipt paths are the source of truth for promoted nested records. Check
    # them before derived routing/reviewer projections so any receipt defect
    # is reported as NESTED_RECORD_ACCOUNTING rather than masked by a later
    # projection check.
    check_nested_record_accounting(manifest, path)
    check_model_routing(manifest, path)
    check_reviewer_independence(manifest, path)
    check_finding_chains(manifest)
    check_artifact_digests(manifest, path)
    check_test_singletons(manifest)
    check_final_five(manifest)
    check_live_run(manifest)
    check_verdicts(manifest)
    check_credential_hygiene(*_credential_hygiene_targets(path))


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
