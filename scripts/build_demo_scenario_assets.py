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
RESPONSE_FIELDS = ("reply", "apply_eligibility", "session_id", "turn_id")


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

        payload = {
            "source_run_dir": run_dir_name,
            "original_graph": original_graph,
            "candidate_graph": candidate_graph,
            "response": {
                field: response_source[field]
                for field in RESPONSE_FIELDS
                if field in response_source
            },
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
