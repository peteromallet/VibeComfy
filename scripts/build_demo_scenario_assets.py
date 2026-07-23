#!/usr/bin/env python3
"""Build the immutable demo-picker scenario bundle from its manifest provenance."""

from __future__ import annotations

import argparse
import gzip
import hashlib
import io
import json
from pathlib import Path
from typing import Any, Mapping


ROOT = Path(__file__).resolve().parents[1]
DEFAULT_MANIFEST = ROOT / "vibecomfy" / "comfy_nodes" / "agent" / "demo_scenarios.json"
DEFAULT_OUTPUT = ROOT / "vibecomfy" / "comfy_nodes" / "agent" / "demo_scenario_assets.json.gz"
RESPONSE_FIELDS = (
    "reply",
    "apply_eligibility",
    "session_id",
    "turn_id",
    "outcome",
    "candidate_graph_hash",
    "candidate_structural_graph_hash",
)


def _project_change_details(value: Any) -> dict[str, Any]:
    """Keep the renderer-facing change contract without bundling debug internals."""
    if not isinstance(value, Mapping):
        return {}

    projected = {
        key: value[key]
        for key in (
            "done_summary",
            "final_summary",
            "gate_a",
            "gate_b",
            "landed_operation_count",
        )
        if key in value
    }
    operations = value.get("operations")
    if isinstance(operations, list):
        projected["operations"] = [
            {
                key: operation[key]
                for key in ("uid", "field_path", "old", "new", "summary")
                if key in operation
            }
            for operation in operations
            if isinstance(operation, Mapping)
        ]

    batch_turns = value.get("batch_turns")
    if isinstance(batch_turns, list):
        projected["batch_turns"] = []
        for turn in batch_turns:
            if not isinstance(turn, Mapping):
                continue
            projected_turn = {
                key: turn[key]
                for key in (
                    "turn_number",
                    "message",
                    "route",
                    "model",
                    "batch_ok",
                    "landed_op_count",
                    "statement_count",
                )
                if key in turn
            }
            field_changes = turn.get("field_changes")
            if isinstance(field_changes, list):
                projected_turn["field_changes"] = [
                    {
                        key: change[key]
                        for key in ("uid", "field_path", "old", "new")
                        if key in change
                    }
                    for change in field_changes
                    if isinstance(change, Mapping)
                ]
            statements = turn.get("statements")
            if isinstance(statements, list):
                projected_turn["statements"] = [
                    {
                        key: statement[key]
                        for key in ("op_kind", "landed", "touched_uids")
                        if key in statement
                    }
                    for statement in statements
                    if isinstance(statement, Mapping)
                ]
            projected["batch_turns"].append(projected_turn)
    return projected


def _project_report(value: Any) -> dict[str, Any]:
    """Keep only report fields consumed by normal preview/render surfaces."""
    if not isinstance(value, Mapping):
        return {}
    return {
        key: value[key]
        for key in (
            "kind",
            "route",
            "reorganise",
            "change",
            "revision_evidence",
            "queue_blockers",
            "diagnostics",
            "gates",
        )
        if key in value
    }


def _load_json(path: Path) -> Any:
    with path.open("r", encoding="utf-8") as handle:
        return json.load(handle)


def _canonical_bytes(value: Any) -> bytes:
    return json.dumps(
        value,
        ensure_ascii=False,
        separators=(",", ":"),
        sort_keys=True,
    ).encode("utf-8")


def _payload_fingerprint(payload: Mapping[str, Any]) -> str:
    preview_payload = {
        "original_graph": payload["original_graph"],
        "candidate_graph": payload["candidate_graph"],
    }
    return hashlib.sha256(_canonical_bytes(preview_payload)).hexdigest()


def build_bundle(*, root: Path, manifest_path: Path) -> dict[str, Any]:
    """Build and validate a compact bundle using each manifest record's source run."""
    manifest = _load_json(manifest_path)
    source_run_tree = manifest.get("source_run_tree")
    if not isinstance(source_run_tree, str) or not source_run_tree:
        raise ValueError("Demo manifest source_run_tree must be a non-empty string")
    run_root = (root / source_run_tree).resolve()

    scenarios: dict[str, Any] = {}
    fingerprints: dict[str, str] = {}
    for record in manifest.get("scenarios", []):
        scenario_id = record.get("id")
        run_location = record.get("run_location")
        if not isinstance(scenario_id, str) or not isinstance(run_location, Mapping):
            raise ValueError("Every demo scenario must have an id and run_location")
        run_dir_name = run_location.get("run_dir")
        if not isinstance(run_dir_name, str) or not run_dir_name:
            raise ValueError(f"{scenario_id}: run_location.run_dir is missing")
        run_dir = (run_root / run_dir_name).resolve()
        try:
            run_dir.relative_to(run_root)
        except ValueError as exc:
            raise ValueError(f"{scenario_id}: source run escapes source_run_tree") from exc

        original_name = run_location.get("original_ui", "original.ui.json")
        candidate_name = run_location.get("candidate_ui", "candidate.ui.json")
        response_name = run_location.get("response_json", "response.json")
        original_graph = _load_json(run_dir / str(original_name))
        candidate_graph = _load_json(run_dir / str(candidate_name))
        response_source = _load_json(run_dir / str(response_name))
        if not isinstance(original_graph, dict) or not isinstance(original_graph.get("nodes"), list):
            raise ValueError(f"{scenario_id}: original graph is not LiteGraph UI JSON")
        if not isinstance(candidate_graph, dict) or not isinstance(candidate_graph.get("nodes"), list):
            raise ValueError(f"{scenario_id}: candidate graph is not LiteGraph UI JSON")
        if not isinstance(response_source, Mapping):
            raise ValueError(f"{scenario_id}: response is not a JSON object")

        response = {
            field: response_source[field]
            for field in RESPONSE_FIELDS
            if field in response_source
        }
        response["change_details"] = _project_change_details(
            response_source.get("change_details")
        )
        response["report"] = _project_report(response_source.get("report"))
        payload = {
            "source_run_dir": run_dir_name,
            "original_graph": original_graph,
            "candidate_graph": candidate_graph,
            "response": response,
        }
        fingerprint = _payload_fingerprint(payload)
        duplicate = fingerprints.get(fingerprint)
        if duplicate is not None:
            raise ValueError(
                f"{scenario_id}: bundled payload duplicates {duplicate}; "
                "check demo scenario provenance"
            )
        fingerprints[fingerprint] = scenario_id
        scenarios[scenario_id] = payload

    return {"version": 1, "scenarios": scenarios}


def write_bundle(bundle: Mapping[str, Any], output_path: Path) -> None:
    """Write byte-for-byte reproducible gzip output (stable JSON and mtime)."""
    output_path.parent.mkdir(parents=True, exist_ok=True)
    raw = _canonical_bytes(bundle)
    buffer = io.BytesIO()
    with gzip.GzipFile(filename="", mode="wb", fileobj=buffer, mtime=0) as handle:
        handle.write(raw)
    output_path.write_bytes(buffer.getvalue())


def main() -> int:
    parser = argparse.ArgumentParser()
    parser.add_argument("--manifest", type=Path, default=DEFAULT_MANIFEST)
    parser.add_argument("--output", type=Path, default=DEFAULT_OUTPUT)
    args = parser.parse_args()
    bundle = build_bundle(root=ROOT, manifest_path=args.manifest.resolve())
    write_bundle(bundle, args.output.resolve())
    print(
        json.dumps(
            {
                "output": str(args.output.resolve()),
                "scenarios": len(bundle["scenarios"]),
                "sha256": hashlib.sha256(args.output.resolve().read_bytes()).hexdigest(),
            },
            sort_keys=True,
        )
    )
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
