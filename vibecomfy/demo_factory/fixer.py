"""Fixer runner for demo_factory.

Wraps the headless agentic harness. The adapter loads the native DeepSeek
provider itself, so we do NOT pre-gate on a specific provider route here — we
let ``run_headless`` surface ``blocked_prerequisite`` and treat that as
``infra_blocked``.
"""
from __future__ import annotations

import json
import os
import re
import uuid
from dataclasses import dataclass
from pathlib import Path
from typing import Any

from tests.live_agentic_harness.adapter import run_headless_scenario


_UUID_RE = re.compile(r"^[0-9a-f]{8}-[0-9a-f]{4}-[0-9a-f]{4}-[0-9a-f]{4}-[0-9a-f]{12}$", re.IGNORECASE)


def _ui_graph_to_ir_envelope(ui_graph: dict[str, Any]) -> dict[str, Any]:
    """Convert a LiteGraph UI graph to a VibeComfy IR envelope.

    The headless agent-edit service consumes an IR envelope graph (rich
    ``nodes`` as a dict, ``edges`` as a list, etc.), NOT a litegraph UI graph
    (nodes=list, links=list). This helper converts UI -> ``VibeWorkflow`` and
    writes the envelope through the single IR writer ``to_envelope()``.

    The envelope is the serialized IR: rich ``nodes`` is the sole structural
    authority and ``compile("api")`` is a derived function, not stored data, so
    no ``compiled_api`` twin is written. ``workflow_id`` is a transport stamp
    applied after ``to_envelope()`` via ``_ensure_workflow_uuid`` — it is not
    an IR field.
    """
    from vibecomfy.ingest.normalize import from_ui
    from vibecomfy.workflow import VibeWorkflow

    # Ensure workflow_id exists (UI graphs often omit it)
    workflow_id = ui_graph.get("id") or ui_graph.get("workflow_id")
    if not workflow_id or not _UUID_RE.match(str(workflow_id)):
        workflow_id = str(uuid.uuid4())

    workflow: VibeWorkflow = from_ui(
        ui_graph,
        source_path=None,
        workflow_id=workflow_id,
        schema_provider=None,  # Use offline schema resolution
    )
    return _ensure_workflow_uuid(workflow.to_envelope())


def _ensure_workflow_uuid(graph: dict[str, Any]) -> dict[str, Any]:
    """Return a copy of ``graph`` with a stable UUID ``workflow_id``.

    The agent-edit apply validator rejects graphs whose ``workflow_id`` is not a
    stable Comfy workflow UUID; port-exported and transcript UI graphs often omit
    it (``workflow_id: None``) while carrying only an ``id``.
    """
    out = dict(graph)
    if not _UUID_RE.match(str(out.get("workflow_id") or "")):
        existing = out.get("id")
        out["workflow_id"] = existing if (isinstance(existing, str) and _UUID_RE.match(existing)) else str(uuid.uuid4())
    return out


@dataclass(frozen=True)
class FixerResult:
    """Result from running the headless fixer."""
    ok: bool
    status: str
    output_dir: str
    candidate: dict[str, Any] | None = None
    error: str | None = None
    readiness: dict[str, Any] | None = None
    deepseek_usage: dict[str, Any] | None = None
    deepseek_est_cost_usd: float | None = None
    infra_blocked: bool = False


_CANDIDATE_FILES = (
    "candidate.ui.json",
    "implementation_result.json",
    "implementation_payload.json",
)
_GRAPH_KEYS = ("candidate", "candidate_ui", "graph", "applied_graph", "ui", "workflow")


def _extract_graph(data: Any) -> dict[str, Any] | None:
    if isinstance(data, dict) and isinstance(data.get("nodes"), list):
        return data
    if isinstance(data, dict):
        for key in _GRAPH_KEYS:
            inner = data.get(key)
            if isinstance(inner, dict) and isinstance(inner.get("nodes"), list):
                return inner
    return None


def _load_candidate(output_dir: Path) -> dict[str, Any] | None:
    """Locate the fixer's repaired candidate UI graph in the run output dir.

    Priority: the repaired graph the agent EMITTED (``response.json ->
    evidence.implementation.graph``), then ``candidate.ui.json``. Note
    ``implementation_payload.json`` holds the INPUT graph, not the repair, so it
    is deliberately not consulted here.
    """
    response_path = output_dir / "response.json"
    if response_path.is_file():
        try:
            data = json.loads(response_path.read_text(encoding="utf-8"))
        except (json.JSONDecodeError, OSError):
            data = None
        if isinstance(data, dict):
            evidence = data.get("evidence")
            impl = evidence.get("implementation") if isinstance(evidence, dict) else None
            graph = _extract_graph(impl) if isinstance(impl, dict) else None
            if graph is not None:
                return graph

    for name in ("candidate.ui.json",):
        path = output_dir / name
        if not path.is_file():
            continue
        try:
            data = json.loads(path.read_text(encoding="utf-8"))
        except (json.JSONDecodeError, OSError):
            continue
        graph = _extract_graph(data)
        if graph is not None:
            return graph
    return None


def run_headless_fixer(
    broken: dict[str, Any],
    inquiry: str,
    *,
    output_base: Path | str,
    tag: str = "demo-factory",
    scenario_id: str = "scenario",
    timeout: int | None = None,
    additive: bool = False,
) -> FixerResult:
    """Run the headless fixer on the broken graph with the inquiry.

    The ``broken`` graph is expected to be a LiteGraph UI format (nodes=list,
    links=list). It is passed directly to the headless agent-edit service,
    which handles UI format internally.

    When ``additive`` is True the request is flagged as an additive restore
    (the caller removed a feature and now asks to re-add it); the revise
    pipeline may then attempt a repair despite the intended topology gap.
    """
    # Ensure workflow_id exists for validation (UI graphs often omit it)
    workflow_id = broken.get("id") or broken.get("workflow_id")
    if not workflow_id or not _UUID_RE.match(str(workflow_id)):
        workflow_id = str(uuid.uuid4())

    try:
        summary = run_headless_scenario(
            scenario={
                "id": scenario_id,
                "query": inquiry,
                "graph": broken,
                "workflow_id": workflow_id,
                "apply": True,
                "network": True,
                "timeout": timeout,
                "additive": bool(additive),
                # Generalizable model/route/effort selector: a named executor
                # profile (see vibecomfy/executor/profile_data/*.toml). Unset ->
                # the runtime default (DeepSeek). e.g. VIBECOMFY_AGENT_PROFILE=openai
                # runs the fixer on Codex/GPT-5.6.
                "profile": os.getenv("VIBECOMFY_AGENT_PROFILE"),
            },
            output_base=output_base,
            tag=tag,
        )
    except Exception as exc:  # pragma: no cover - defensive
        return FixerResult(
            ok=False,
            status="error",
            output_dir=str(output_base),
            error=str(exc),
        )

    status = summary.get("status", "unknown")
    readiness = summary.get("readiness")
    output_dir = Path(summary.get("output_dir", output_base))

    if status == "blocked_prerequisite":
        return FixerResult(
            ok=False,
            status=status,
            output_dir=str(output_dir),
            error=summary.get("error", "provider blocked (blocked_prerequisite)"),
            readiness=readiness,
            infra_blocked=True,
        )

    candidate = _load_candidate(output_dir)

    return FixerResult(
        ok=bool(summary.get("ok", False)),
        status=status,
        output_dir=str(output_dir),
        candidate=candidate,
        error=summary.get("error"),
        readiness=readiness,
        deepseek_usage=summary.get("deepseek_usage"),
        deepseek_est_cost_usd=summary.get("deepseek_est_cost_usd"),
        infra_blocked=False,
    )
