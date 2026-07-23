#!/usr/bin/env python3
"""Populate layout-bearing UI artifacts for live-agentic scenario outputs."""

from __future__ import annotations

import argparse
import json
import sys
from pathlib import Path
from typing import Any, Mapping

ROOT = Path(__file__).resolve().parents[1]
if str(ROOT) not in sys.path:
    sys.path.insert(0, str(ROOT))

from tests.live_agentic_harness.source_layouts import (
    load_json,
    load_source_ui_graph,
    overlay_candidate_on_source,
    repo_root,
)


DEMO_ALIAS_SCENARIOS: Mapping[str, str] = {
    "tts_emotion_injection": "audio-tts-narration-using-indextts-2",
    "qwen_face_distortion_wrong_slot": "image-image-editing-with-qwen-image",
    "vace_identity_padded_reference": "multi-wan-vace-video-retargeting-driven",
    "triporefine_stage_add": "3d-3d-model-generation-and-rigging-workflow-90a1d5",
    "av_fps_desync": "multi-image-to-video-generation-with-2",
    "sdxl_plastic_fabric": "image-sdxl-txt2img-cat-in-spacesuit",
}


def _candidate_graph(response: Mapping[str, Any]) -> dict[str, Any] | None:
    candidate = response.get("candidate_graph")
    if isinstance(candidate, dict):
        return candidate
    nested = response.get("candidate")
    if isinstance(nested, Mapping) and isinstance(nested.get("graph"), dict):
        return nested["graph"]
    graph = response.get("graph")
    if isinstance(graph, dict):
        return graph
    return None


def _scenario_files(root: Path) -> list[Path]:
    scenarios = root / "tests" / "live_agentic_harness" / "scenarios"
    return sorted(scenarios.glob("*.json"))


def _scenario_index(root: Path) -> dict[str, dict[str, Any]]:
    scenarios: dict[str, dict[str, Any]] = {}
    for scenario_path in _scenario_files(root):
        scenario = load_json(scenario_path)
        scenario_id = scenario.get("id")
        if isinstance(scenario_id, str):
            scenarios[scenario_id] = scenario
    return scenarios


def _write_json(path: Path, data: Any) -> None:
    path.write_text(json.dumps(data, indent=2, sort_keys=True, default=str) + "\n", encoding="utf-8")


def _source_path_label(source_path: Path | None, root: Path) -> str | None:
    if source_path is None:
        return None
    try:
        return str(source_path.relative_to(root))
    except ValueError:
        return str(source_path)


def _reconcile_one(
    *,
    root: Path,
    run_dir: Path,
    scenario_id: str,
    workflow_path: str,
    write: bool,
    row_extra: Mapping[str, Any] | None = None,
) -> dict[str, Any]:
    resolved_source = load_source_ui_graph(workflow_path, root=root)
    response_path = run_dir / "response.json"
    source_path = resolved_source[0] if resolved_source is not None else None
    row: dict[str, Any] = {
        "scenario_id": scenario_id,
        "workflow_path": workflow_path,
        "source_ui_path": _source_path_label(source_path, root),
        "run_dir": _source_path_label(run_dir, root) or str(run_dir),
        "run_dir_exists": run_dir.is_dir(),
        "status": "skipped",
    }
    if row_extra:
        row.update(row_extra)
    if source_path is None:
        row["status"] = "missing_source_ui"
        return row
    if not response_path.is_file():
        row["status"] = "no_run_output"
        return row

    source_ui = resolved_source[1]
    response = load_json(response_path)
    candidate = _candidate_graph(response)
    if candidate is None:
        row["status"] = "missing_candidate_graph"
        return row

    candidate_ui = overlay_candidate_on_source(source_ui, candidate)
    row["status"] = "would_write" if not write else "written"
    row["original_nodes"] = len(source_ui.get("nodes", []))
    row["candidate_nodes"] = len(candidate_ui.get("nodes", []))
    if write:
        _write_json(run_dir / "original.ui.json", source_ui)
        _write_json(run_dir / "candidate.ui.json", candidate_ui)
    return row


def reconcile(
    *,
    root: Path,
    run_root: Path,
    write: bool,
) -> dict[str, Any]:
    rows: list[dict[str, Any]] = []
    scenarios = _scenario_index(root)
    for scenario in scenarios.values():
        scenario_id = scenario.get("id")
        workflow_path = scenario.get("workflow_path")
        if not isinstance(scenario_id, str) or not isinstance(workflow_path, str):
            continue

        run_dir = run_root / scenario_id
        rows.append(_reconcile_one(
            root=root,
            run_dir=run_dir,
            scenario_id=scenario_id,
            workflow_path=workflow_path,
            write=write,
        ))

    for alias_id, canonical_id in DEMO_ALIAS_SCENARIOS.items():
        canonical = scenarios.get(canonical_id)
        workflow_path = canonical.get("workflow_path") if isinstance(canonical, Mapping) else None
        if not isinstance(workflow_path, str):
            rows.append({
                "scenario_id": alias_id,
                "canonical_scenario_id": canonical_id,
                "status": "missing_canonical_scenario",
            })
            continue
        rows.append(_reconcile_one(
            root=root,
            run_dir=run_root / alias_id,
            scenario_id=alias_id,
            workflow_path=workflow_path,
            write=write,
            row_extra={
                "canonical_scenario_id": canonical_id,
                "kind": "demo_alias",
            },
        ))

    return {
        "run_root": str(run_root),
        "write": write,
        "total": len(rows),
        "written": sum(1 for row in rows if row["status"] == "written"),
        "would_write": sum(1 for row in rows if row["status"] == "would_write"),
        "demo_alias_written": sum(
            1 for row in rows if row.get("kind") == "demo_alias" and row["status"] == "written"
        ),
        "demo_alias_would_write": sum(
            1 for row in rows if row.get("kind") == "demo_alias" and row["status"] == "would_write"
        ),
        "missing_source_ui": sum(1 for row in rows if row["status"] == "missing_source_ui"),
        "no_run_output": sum(1 for row in rows if row["status"] == "no_run_output"),
        "missing_candidate_graph": sum(1 for row in rows if row["status"] == "missing_candidate_graph"),
        "rows": rows,
    }


def main() -> int:
    parser = argparse.ArgumentParser()
    parser.add_argument(
        "--run-root",
        default="out/agentic/agentic-100-20260630-021138",
        help="Agentic run root containing per-scenario output directories.",
    )
    parser.add_argument("--write", action="store_true", help="Write original.ui.json and candidate.ui.json.")
    args = parser.parse_args()

    root = repo_root()
    run_root = Path(args.run_root)
    if not run_root.is_absolute():
        run_root = root / run_root
    result = reconcile(root=root, run_root=run_root, write=args.write)
    print(json.dumps(result, indent=2, sort_keys=True))
    return 1 if result["missing_source_ui"] else 0


if __name__ == "__main__":
    raise SystemExit(main())
