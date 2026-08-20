from __future__ import annotations

import json
import os
from pathlib import Path
from typing import Any, Mapping


def is_enabled() -> bool:
    return os.environ.get("VIBECOMFY_AGENTIC_REPLAY") == "1"


def is_safe_replay_id(value: str) -> bool:
    if not isinstance(value, str) or not value:
        return False
    if any(sep in value for sep in ("/", "\\", os.sep)):
        return False
    if value in (".", "..") or ".." in value:
        return False
    if value.startswith("."):
        return False
    return "~" not in value


def _run_dir(root: Path, run_id: str) -> Path | None:
    if not is_safe_replay_id(run_id):
        return None
    resolved_root = root.resolve()
    run_dir = (resolved_root / run_id).resolve()
    try:
        run_dir.relative_to(resolved_root)
    except ValueError:
        return None
    return run_dir


def _test_dir(root: Path, run_id: str, test_id: str) -> Path | None:
    if not is_safe_replay_id(test_id):
        return None
    run_dir = _run_dir(root, run_id)
    if run_dir is None:
        return None
    test_dir = (run_dir / test_id).resolve()
    try:
        test_dir.relative_to(run_dir)
    except ValueError:
        return None
    return test_dir


def _read_json(path: Path) -> Any:
    try:
        return json.loads(path.read_text(encoding="utf-8"))
    except FileNotFoundError:
        return None
    except json.JSONDecodeError:
        return None


def _graph(
    test_dir: Path,
    response_json: Mapping[str, Any],
    kind: str,
) -> dict[str, Any] | None:
    keys = {
        "original": ("original_graph", "original_ui"),
        "candidate": ("candidate_graph", "candidate_ui"),
    }[kind]
    for key in keys:
        value = response_json.get(key)
        if isinstance(value, dict):
            return value
    artifacts = response_json.get("artifacts")
    if isinstance(artifacts, Mapping):
        for key in keys:
            value = artifacts.get(key)
            if isinstance(value, str):
                graph = _read_json(test_dir / value)
                if isinstance(graph, dict):
                    return graph
    fallback = "original.ui.json" if kind == "original" else "candidate.ui.json"
    graph = _read_json(test_dir / fallback)
    return graph if isinstance(graph, dict) else None


def _stage_payload(
    response_json: Mapping[str, Any],
    *,
    original_graph: dict[str, Any] | None,
    candidate_graph: dict[str, Any] | None,
) -> list[dict[str, Any]]:
    stages = response_json.get("stages")
    if isinstance(stages, list) and all(isinstance(stage, dict) for stage in stages):
        return [dict(stage) for stage in stages]
    projected: list[dict[str, Any]] = [
        {"id": "sent", "label": "Sent"},
        {"id": "thinking", "label": "Thinking"},
    ]
    if original_graph is not None and candidate_graph is not None:
        projected.extend(
            [
                {
                    "id": "ready_to_apply",
                    "label": "Ready to apply",
                    "original_graph": original_graph,
                    "candidate_graph": candidate_graph,
                },
                {
                    "id": "applied",
                    "label": "Applied",
                    "original_graph": original_graph,
                    "candidate_graph": candidate_graph,
                },
            ]
        )
    else:
        projected.append(
            {
                "id": "missing_artifacts",
                "label": "Missing artifacts",
                "status": "missing",
            }
        )
    return projected


def list_runs(root: Path, *, enabled: bool) -> tuple[dict[str, Any], int]:
    if not enabled:
        return {"ok": False, "error": "Not found"}, 404
    if not root.is_dir():
        return {"ok": True, "runs": []}, 200
    runs = []
    for path in sorted(root.iterdir(), key=lambda item: item.name):
        if not path.is_dir() or not is_safe_replay_id(path.name):
            continue
        runs.append({"run_id": path.name, "label": path.name})
    return {"ok": True, "runs": runs}, 200


def list_tests(
    root: Path,
    run_id: str,
    *,
    enabled: bool,
) -> tuple[dict[str, Any], int]:
    if not enabled:
        return {"ok": False, "error": "Not found"}, 404
    run_dir = _run_dir(root, run_id)
    if run_dir is None:
        return {"ok": False, "error": "Invalid run ID"}, 400
    if not run_dir.is_dir():
        return {"ok": False, "error": "Run not found"}, 404
    tests = []
    for path in sorted(run_dir.iterdir(), key=lambda item: item.name):
        if not path.is_dir() or not is_safe_replay_id(path.name):
            continue
        response_json = _read_json(path / "response.json")
        label = path.name
        query = None
        if isinstance(response_json, Mapping):
            label = str(
                response_json.get("title") or response_json.get("name") or path.name
            )
            query_value = response_json.get("query")
            query = query_value if isinstance(query_value, str) else None
        tests.append({"test_id": path.name, "label": label, "query": query})
    return {"ok": True, "run_id": run_id, "tests": tests}, 200


def resolve_scenario(
    root: Path,
    run_id: str,
    test_id: str,
    *,
    enabled: bool,
) -> tuple[dict[str, Any], int]:
    if not enabled:
        return {"ok": False, "error": "Not found"}, 404
    test_dir = _test_dir(root, run_id, test_id)
    if test_dir is None:
        return {"ok": False, "error": "Invalid replay ID"}, 400
    if not test_dir.is_dir():
        return {"ok": False, "error": "Replay test not found"}, 404
    response_json = _read_json(test_dir / "response.json")
    if not isinstance(response_json, Mapping):
        return {"ok": False, "error": "response.json not found"}, 404
    original_graph = _graph(test_dir, response_json, "original")
    candidate_graph = _graph(test_dir, response_json, "candidate")
    query = response_json.get("query")
    reply = (
        response_json.get("reply")
        or response_json.get("message")
        or response_json.get("agent_reply")
        or ""
    )
    checks = response_json.get("checks")
    status = (
        "ready"
        if original_graph is not None and candidate_graph is not None
        else "missing"
    )
    missing: list[str] = []
    if original_graph is None:
        missing.append("original_graph")
    if candidate_graph is None:
        missing.append("candidate_graph")
    session_id = response_json.get("session_id") or f"replay-{run_id}-{test_id}"
    turn_id = response_json.get("turn_id") or f"replay-{test_id}-turn"
    payload = {
        "ok": True,
        "run_id": run_id,
        "test_id": test_id,
        "status": status,
        "checks": checks if isinstance(checks, list) else [],
        "query": query if isinstance(query, str) else "",
        "agent_reply": reply if isinstance(reply, str) else "",
        "original_graph": original_graph,
        "candidate_graph": candidate_graph,
        "stages": _stage_payload(
            response_json,
            original_graph=original_graph,
            candidate_graph=candidate_graph,
        ),
        "session_id": session_id
        if isinstance(session_id, str)
        else f"replay-{run_id}-{test_id}",
        "turn_id": turn_id if isinstance(turn_id, str) else f"replay-{test_id}-turn",
        "source_dir": str(test_dir.relative_to(root)),
    }
    if missing:
        payload["ok"] = False
        payload["error"] = "Replay artifacts missing: " + ", ".join(missing)
        payload["missing_artifacts"] = missing
    return payload, 200
