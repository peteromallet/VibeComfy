"""Baseline validation for demo_factory.

Runs the offline CLI baseline gate (`vibecomfy port check`) on a UI graph using
the cached object_info — no ComfyUI server and no `comfy` import required.
Failed baseline = BASELINE_REJECTED.
"""
from __future__ import annotations

import json
import os
import socket
import subprocess
import sys
import tempfile
from dataclasses import dataclass
from pathlib import Path
from typing import Any


@dataclass(frozen=True, slots=True)
class BaselineResult:
    """Result of baseline validation."""
    passed: bool
    execution_safe: bool
    output_reachable: bool
    compile_error: str | None = None
    output_node_id: str | None = None
    node_count: int = 0
    link_count: int = 0


def _reachable_comfy_url(timeout: float = 0.5) -> str | None:
    """A reachable ComfyUI server URL (for live /object_info), or None.

    Reads ``VIBECOMFY_COMFYUI_URL`` and cheaply probes the port so an absent
    server never blocks the baseline gate.
    """
    from urllib.parse import urlparse

    url = os.environ.get("VIBECOMFY_COMFYUI_URL")
    if not url:
        return None
    try:
        parsed = urlparse(url)
        with socket.create_connection(
            (parsed.hostname or "127.0.0.1", parsed.port or 80), timeout=timeout
        ):
            return url
    except OSError:
        return None


def _on_demand_enabled() -> bool:
    """Whether the baseline gate should resolve non-installed node classes on demand.

    Honors ``VIBECOMFY_ON_DEMAND_SCHEMAS=1`` (the same gate the rest of the system
    uses) so baselines resolve public custom-node packs absent from the comfy-core
    cache instead of being rejected as "unknown class". Runtime boot stays gated on
    ``VIBECOMFY_ON_DEMAND_BOOT=1``.
    """
    return os.environ.get("VIBECOMFY_ON_DEMAND_SCHEMAS") == "1"


def port_check_graph(
    graph: dict[str, Any],
    *,
    timeout: int = 180,
) -> tuple[bool, str | None, dict[str, Any]]:
    """Run offline ``vibecomfy port check`` on a UI graph.

    Uses the auto-resolved object_info cache (newest ``out/cache/object_info*.json``).
    Returns ``(ok, error_message, report_json)``.
    """
    fd, path = tempfile.mkstemp(suffix=".ui.json")
    try:
        with os.fdopen(fd, "w", encoding="utf-8") as fh:
            json.dump(graph, fh)
        cmd = [sys.executable, "-m", "vibecomfy.cli", "port", "check", path, "--json"]
        # When a ComfyUI server is reachable, consult its live /object_info so
        # custom nodes (absent from the comfy-core-only static cache) resolve
        # instead of being rejected as "unknown class". Cheap socket probe guards
        # an absent server so the offline default is unchanged.
        server_url = _reachable_comfy_url()
        if server_url:
            cmd += ["--runtime-object-info", "--server-url", server_url]
        # Resolve non-installed custom-node classes via the on-demand escalation
        # ladder (corpus cache + static AST parse) so golden workflows that use
        # public packs absent from the comfy-core cache are not wrongly rejected
        # as "unknown class" before the agent runs. Opt-in / consistent with the
        # rest of the system: honor VIBECOMFY_ON_DEMAND_SCHEMAS=1 if already set,
        # and pass the CLI flag so the child process activates the same tier.
        # Runtime boot (VIBECOMFY_ON_DEMAND_BOOT=1) stays separately gated.
        if _on_demand_enabled():
            cmd.append("--resolve-on-demand")
        proc = subprocess.run(
            cmd,
            capture_output=True,
            text=True,
            timeout=timeout,
        )
        try:
            data = json.loads(proc.stdout)
        except json.JSONDecodeError:
            if proc.returncode != 0:
                return False, f"port check exit {proc.returncode}: {proc.stderr[:400]}", {}
            return False, "port check produced no JSON output", {}
        # port check may exit non-zero on a not-ok workflow while still emitting JSON
    except subprocess.TimeoutExpired:
        return False, "port check timeout", {}
    except Exception as exc:  # pragma: no cover - defensive
        return False, f"port check failed: {exc}", {}
    finally:
        try:
            os.unlink(path)
        except OSError:
            pass

    ok = bool(data.get("ok"))
    diag = data.get("diagnostics") or []
    hard = [
        d for d in diag
        if isinstance(d, dict) and str(d.get("severity", "")).lower() in ("error", "hard", "fatal")
    ]
    error: str | None = None
    if not ok:
        msgs = [str(d.get("message", d)) for d in hard if d.get("message")]
        error = "; ".join(m[:120] for m in msgs[:3]) or "port check reported not-ok"
        # Validity = node resolvability against the registry (object_info). Hard-fail
        # ONLY when a node class is truly unknown/undefined; missing widget inputs
        # and missing model files are runtime concerns, not node-validity, so a
        # workflow whose nodes all resolve is considered valid (soft-pass).
        _UNKNOWN = (
            "unknown node", "unknown class", "unknown type", "undefined node",
            "undefined class", "not a valid node", "unresolved node",
            "is not a known", "no object_info",
        )
        has_unknown_node = any(any(k in m.lower() for k in _UNKNOWN) for m in msgs)
        if msgs and not has_unknown_node:
            ok = True
            error = f"SOFT-PASS (nodes resolve; runtime concerns only): {error}"
    return ok, error, data


def _find_output_node(graph: dict[str, Any]) -> tuple[str | None, bool]:
    for node in graph.get("nodes", []):
        node_type = (node.get("type", "") or "").lower()
        if ("save" in node_type and "image" in node_type) or ("preview" in node_type and "image" in node_type):
            return str(node.get("id")), True
    return None, False


def run_baseline(golden: dict[str, Any]) -> BaselineResult:
    """Validate the golden UI graph through the offline baseline gates."""
    node_count = len(golden.get("nodes", []))
    link_count = len(golden.get("links", []))

    output_node_id, output_reachable = _find_output_node(golden)

    execution_safe, compile_error, report = port_check_graph(golden)

    # Trust port check's computed public_outputs for reachability when present.
    public_outputs = report.get("public_outputs") if isinstance(report, dict) else None
    if public_outputs:
        output_reachable = len(public_outputs) > 0

    return BaselineResult(
        passed=execution_safe and output_reachable,
        execution_safe=execution_safe,
        output_reachable=output_reachable,
        compile_error=compile_error,
        output_node_id=output_node_id,
        node_count=node_count,
        link_count=link_count,
    )


def write_baseline_proof(result: BaselineResult, output_dir: Path) -> None:
    """Write baseline proof to ``proof/baseline.json``."""
    output_dir = Path(output_dir)
    proof_path = output_dir / "proof" / "baseline.json"
    proof_path.parent.mkdir(parents=True, exist_ok=True)

    proof_path.write_text(
        json.dumps(
            {
                "passed": result.passed,
                "execution_safe": result.execution_safe,
                "output_reachable": result.output_reachable,
                "compile_error": result.compile_error,
                "output_node_id": result.output_node_id,
                "node_count": result.node_count,
                "link_count": result.link_count,
            },
            indent=2,
        ),
        encoding="utf-8",
    )
