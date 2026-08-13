"""VibeComfy-local adapter for the live agentic harness.

The adapter stays inside VibeComfy for v1: it calls
``vibecomfy.agent.service.run_headless`` directly.  External callers (e.g.
Astrid) may instead invoke the CLI as a subprocess.
"""

from __future__ import annotations

import json
import os
from pathlib import Path
from typing import Any, Mapping


def _ensure_headless_env() -> None:
    os.environ["VIBECOMFY_HEADLESS"] = "1"


def _load_credential_env_file(path: Path | str | None = None) -> None:
    """Hydrate DEEPSEEK_API_KEY from a sibling .env if not already set.

    The live agentic harness is meant to run with native DeepSeek API by default.
    If DEEPSEEK_API_KEY is not in the environment, try the canonical project
    credential file at ``$BANODOCO_WORKSPACE/brain-of-bndc/.env`` so a local run
    does not silently fall back to OpenRouter.
    """
    if os.environ.get("DEEPSEEK_API_KEY"):
        return
    candidate = path or os.environ.get("BANODOCO_BRAIN_ENV")
    if candidate is None:
        home = Path.home()
        candidate = (
            home
            / "Documents"
            / "banodoco-workspace"
            / "brain-of-bndc"
            / ".env"
        )
    candidate = Path(candidate)
    if not candidate.is_file():
        return
    try:
        for line in candidate.read_text(encoding="utf-8").splitlines():
            line = line.strip()
            if not line or line.startswith("#") or "=" not in line:
                continue
            key, _, value = line.partition("=")
            key = key.strip()
            value = value.strip().strip('"').strip("'")
            if key and value and key not in os.environ:
                os.environ[key] = value
    except OSError:
        pass


# Canonical base URLs for the two supported explicit transports.  ``native`` is
# the harness's historical default (June baseline: native DeepSeek API); it is
# selected deterministically and can never be displaced by an ambient
# credential or an inherited ``VIBECOMFY_OPENROUTER_BASE_URL``.
_TRANSPORT_BASE_URLS = {
    "openrouter": "https://openrouter.ai/api/v1",
    "native": "https://api.deepseek.com/v1",
}
_HARNESS_DEFAULT_TRANSPORT = "native"

# Environment keys that select transport/endpoint/model routing.  Ambient
# copies of these must never leak into a child run: the explicit selector is
# the ONLY authority.  Credential keys (OPENROUTER_API_KEY, DEEPSEEK_API_KEY)
# are deliberately NOT listed — they provide keys, they do not select
# transport.
_TRANSPORT_SELECTING_ENV_KEYS = frozenset(
    {
        "VIBECOMFY_OPENROUTER_BASE_URL",
        "VIBECOMFY_TRANSPORT",
        "VIBECOMFY_OPENROUTER_MODEL",
        "VIBECOMFY_FORCE_MODEL",
        "VIBECOMFY_AGENT_MODEL",
        "VIBECOMFY_HERMES_API_KEY",
        "VIBECOMFY_ARNOLD_MODEL",
        "VIBECOMFY_ARNOLD_BASE_URL",
    }
)


def _ensure_transport_env(transport: str | None = None) -> str:
    """Pin the explicit transport and return the resolved transport name.

    Resolves the selector from (in order): the explicit *transport* argument,
    an explicit ``VIBECOMFY_TRANSPORT`` environment pin, or the deterministic
    harness default (``native``).  The base URL is then rewritten
    UNCONDITIONALLY — an inherited ``VIBECOMFY_OPENROUTER_BASE_URL`` or any
    ambient credential can never silently switch the transport.  Every profile
    phase (classify/research/implement/reply) shares this child environment, so
    the pin reaches all of them.
    """
    resolved = (
        transport
        or os.environ.get("VIBECOMFY_TRANSPORT")
        or _HARNESS_DEFAULT_TRANSPORT
    )
    resolved = str(resolved).strip().lower()
    if resolved not in _TRANSPORT_BASE_URLS:
        raise ValueError(
            f"Unsupported transport {resolved!r}; expected one of "
            f"{sorted(_TRANSPORT_BASE_URLS)}."
        )
    os.environ["VIBECOMFY_TRANSPORT"] = resolved
    os.environ["VIBECOMFY_OPENROUTER_BASE_URL"] = _TRANSPORT_BASE_URLS[resolved]
    return resolved


def _load_workflow(path: str | None) -> dict[str, Any] | None:
    if path is None:
        return None
    p = Path(path)
    if not p.is_file():
        raise ValueError(f"Workflow file not found: {path}")
    with p.open("r", encoding="utf-8") as fh:
        data = json.load(fh)
    if not isinstance(data, dict):
        raise ValueError(f"Workflow file must contain a JSON object: {path}")
    return data


def run_headless_scenario(
    scenario: Mapping[str, Any],
    *,
    output_base: Path | str | None = None,
    tag: str = "agentic-run",
    transport: str | None = None,
) -> dict[str, Any]:
    """Run a single agentic scenario through the headless service.

    Parameters
    ----------
    scenario:
        Must contain at least ``query``.  Optional keys: ``graph``,
        ``workflow_path``, ``profile``, ``session_id``, ``dry_run``,
        ``apply``, ``network``, ``timeout``.
    output_base:
        Base directory for evidence.  Defaults to ``out/agentic``.
    tag:
        Run tag used to build the evidence directory name.
    transport:
        Explicit transport selector: ``"openrouter"`` or ``"native"``.
        ``None`` resolves to the deterministic harness default and never to an
        ambient credential.

    Returns
    -------
    dict
        A summary suitable for ``summary.json``.
    """
    _ensure_headless_env()
    _load_credential_env_file()
    _ensure_transport_env(transport)

    from vibecomfy.agent.contracts import HeadlessAgentRequest
    from vibecomfy.agent.service import run_headless

    query = str(scenario.get("query", "")).strip()
    if not query:
        raise ValueError("Scenario must contain a non-empty 'query'.")

    base = Path(output_base) if output_base is not None else Path("out") / "agentic"
    scenario_id = str(scenario.get("id", "scenario"))
    output_dir = base / tag / scenario_id

    graph = scenario.get("graph")
    if graph is not None and not isinstance(graph, dict):
        raise ValueError("Scenario `graph` must be a JSON object when supplied.")
    if graph is not None and scenario.get("workflow_path") is not None:
        raise ValueError("Scenario accepts either `graph` or `workflow_path`, not both.")
    if graph is None:
        graph = _load_workflow(scenario.get("workflow_path"))

    request = HeadlessAgentRequest(
        query=query,
        graph=graph,
        workflow_id=scenario.get("workflow_id") or (graph.get("workflow_id") if isinstance(graph, dict) else None),
        session_id=scenario.get("session_id"),
        profile=scenario.get("profile"),
        output_dir=output_dir,
        dry_run=bool(scenario.get("dry_run", False)),
        apply=bool(scenario.get("apply", False)),
        network=bool(scenario.get("network", True)),
        timeout=scenario.get("timeout"),
        additive=bool(scenario.get("additive", False)),
    )

    result = run_headless(request, entrypoint="live_agentic_harness")
    return {
        "scenario_id": scenario_id,
        "status": result.status,
        "ok": result.ok,
        "output_dir": str(output_dir),
        "readiness": result.readiness,
        "error": result.error,
        "deepseek_usage": result.response.get("deepseek_usage", {}),
        "deepseek_est_cost_usd": result.response.get("deepseek_est_cost_usd"),
        "deepseek_cost_basis": result.response.get("deepseek_cost_basis"),
        "model_attempts": result.response.get("model_attempts", []),
    }
