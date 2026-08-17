"""VibeComfy-local adapter for the live agentic harness.

The adapter stays inside VibeComfy for v1: it calls
``vibecomfy.agent.service.run_headless`` directly.  External callers (e.g.
Astrid) may instead invoke the CLI as a subprocess.
"""

from __future__ import annotations

import hashlib
import json
import os
from pathlib import Path
from typing import Any, Mapping


def _ensure_headless_env() -> None:
    os.environ["VIBECOMFY_HEADLESS"] = "1"


def _load_credential_env_file(path: Path | str | None = None) -> None:
    """Hydrate credential keys (e.g. DEEPSEEK_API_KEY) from a sibling .env.

    The live agentic harness runs the canonical OpenRouter product route by
    default.  This file exists so a local run still finds its API keys when
    they are not in the environment.  Credentials hydrate; transport-selecting
    keys never do — mirroring ``runtime._load_env_file_into_environ`` — so an
    ambient .env can never set ``VIBECOMFY_TRANSPORT`` (or any endpoint/model
    pin) and silently switch the transport when no explicit flag is given.
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
            if (
                key
                and value
                and key not in os.environ
                and key not in _TRANSPORT_SELECTING_ENV_KEYS
            ):
                os.environ[key] = value
    except OSError:
        pass


# Canonical base URLs for the two supported explicit transports.  ``openrouter``
# is the product/canonical route and the harness's default; ``native`` is the
# explicit benchmark lane (June baseline: native DeepSeek API).  The default is
# selected deterministically and can never be displaced by an ambient
# credential or an inherited ``VIBECOMFY_OPENROUTER_BASE_URL``.
_TRANSPORT_BASE_URLS = {
    "openrouter": "https://openrouter.ai/api/v1",
    "native": "https://api.deepseek.com/v1",
}
_HARNESS_DEFAULT_TRANSPORT = "openrouter"

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
    harness default (``openrouter`` — the canonical product route).  The base
    URL is then rewritten
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


def _two_step_session_id(scenario_id: str) -> str:
    """Deterministic, stable per-window session id for a two-step scenario.

    The two-step execute phase requires a ``session_id`` (the server never
    mints ids), and one window's classify → execute chain must reuse a SINGLE
    session id so the session can continue across the window's model calls.
    Deriving the id from the scenario id alone makes it stable across runner
    attempts (infra retries reuse the same session) and across separate runs
    of the same scenario, while the ``two-step-`` prefix keeps it disjoint
    from caller-supplied session ids.  The output is a single safe path
    component (``[a-z0-9-]`` only).
    """
    digest = hashlib.sha256(f"two-step:{scenario_id}".encode("utf-8")).hexdigest()
    return f"two-step-{digest[:24]}"


def _resolve_pipeline_mode(
    pipeline_mode: str | None,
    scenario: Mapping[str, Any],
) -> str | None:
    """Resolve the effective pipeline mode: explicit arg → descriptor → None.

    The explicit ``pipeline_mode`` argument (from the runner's
    ``--pipeline-mode`` flag) is the ONLY authority; otherwise the scenario
    descriptor's ``pipeline_mode`` key (or its ``_tags.pipeline_mode``) is
    used; otherwise ``None`` (the product default — ``full`` — applies).
    Invalid values raise :class:`PipelineModeRequestError`.
    """
    from vibecomfy.executor.contracts import coerce_pipeline_mode  # noqa: PLC0415

    value = pipeline_mode
    if value is None:
        value = scenario.get("pipeline_mode")
    if value is None:
        tags = scenario.get("_tags")
        if isinstance(tags, Mapping):
            value = tags.get("pipeline_mode")
    return coerce_pipeline_mode(value)


def run_headless_scenario(
    scenario: Mapping[str, Any],
    *,
    output_base: Path | str | None = None,
    tag: str = "agentic-run",
    transport: str | None = None,
    pipeline_mode: str | None = None,
) -> dict[str, Any]:
    """Run a single agentic scenario through the headless service.

    Parameters
    ----------
    scenario:
        Must contain at least ``query``.  Optional keys: ``graph``,
        ``workflow_path``, ``profile``, ``session_id``, ``dry_run``,
        ``apply``, ``network``, ``timeout``, ``pipeline_mode``.
    output_base:
        Base directory for evidence.  Defaults to ``out/agentic``.
    tag:
        Run tag used to build the evidence directory name.
    transport:
        Explicit transport selector: ``"openrouter"`` or ``"native"``.
        ``None`` resolves to the deterministic harness default and never to an
        ambient credential.
    pipeline_mode:
        Explicit pipeline-mode selector: ``"full"`` or ``"two_step"``.
        ``None`` falls back to the scenario descriptor's ``pipeline_mode``
        (or ``_tags.pipeline_mode``), then to the product default.  A
        two-step scenario without an explicit ``session_id`` gets a stable
        per-window session id derived from its scenario id.

    Returns
    -------
    dict
        A summary suitable for ``summary.json``.  The effective
        ``pipeline_mode`` is always recorded; the ``session_id`` is recorded
        when a two-step run used one (minted or supplied).
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

    mode = _resolve_pipeline_mode(pipeline_mode, scenario)
    session_id = scenario.get("session_id")
    if mode == "two_step" and not session_id:
        session_id = _two_step_session_id(scenario_id)

    request = HeadlessAgentRequest(
        query=query,
        graph=graph,
        workflow_id=scenario.get("workflow_id") or (graph.get("workflow_id") if isinstance(graph, dict) else None),
        session_id=session_id,
        profile=scenario.get("profile"),
        output_dir=output_dir,
        dry_run=bool(scenario.get("dry_run", False)),
        apply=bool(scenario.get("apply", False)),
        network=bool(scenario.get("network", True)),
        timeout=scenario.get("timeout"),
        additive=bool(scenario.get("additive", False)),
        interaction_mode=scenario.get("interaction_mode"),
        max_batches=scenario.get("max_batches"),
        pipeline_mode=mode,
    )

    result = run_headless(request, entrypoint="live_agentic_harness")
    summary: dict[str, Any] = {
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
        "pipeline_mode": mode,
    }
    if session_id is not None:
        summary["session_id"] = session_id
    # Persist the typed parse reason from the executor's model_response artifact
    # so the runner's infra reclassification is evidence-based (parse_reason ==
    # "empty" AND completion_tokens == 0), never phrase-matching alone.
    parse_reason = _extract_parse_reason(result.response)
    if parse_reason is not None:
        summary["parse_reason"] = parse_reason
    return summary


def _extract_parse_reason(response: Mapping[str, Any]) -> str | None:
    """Read ``parse_reason`` from the executor failure's model_response artifact.

    Shape: ``response.report.executor.model_response.turns[0].error.parse_reason``.
    Returns None when the attempt did not fail on a model response or the
    artifact is missing — absence is NOT evidence of an empty response.
    """
    report = response.get("report")
    if not isinstance(report, Mapping):
        return None
    executor = report.get("executor")
    if not isinstance(executor, Mapping):
        return None
    model_response = executor.get("model_response")
    if not isinstance(model_response, Mapping):
        return None
    turns = model_response.get("turns")
    if not isinstance(turns, (list, tuple)) or not turns:
        return None
    first = turns[0]
    if not isinstance(first, Mapping):
        return None
    error = first.get("error")
    if not isinstance(error, Mapping):
        return None
    value = error.get("parse_reason")
    if not isinstance(value, str) or not value.strip():
        return None
    return value.strip()
