"""VibeComfy-local adapter for the live agentic harness.

The adapter stays inside VibeComfy for v1: it calls
``vibecomfy.agent.service.run_headless`` directly.  External callers (e.g.
Astrid) may instead invoke the CLI as a subprocess.
"""

from __future__ import annotations

import json
import os
import threading
from pathlib import Path
from typing import Any, Mapping

from .output_paths import authorized_output_dir

_ENV_PIN_LOCK = threading.Lock()


def _ensure_headless_env() -> None:
    # T5.4: comparison legs run concurrently in one process (thread lane);
    # all legs write the SAME value, so pin it once under a lock and never
    # downgrade a correct value.
    with _ENV_PIN_LOCK:
        if os.environ.get("VIBECOMFY_HEADLESS") != "1":
            os.environ["VIBECOMFY_HEADLESS"] = "1"


def _load_credential_env_file(path: Path | str | None = None) -> None:
    """Hydrate credential keys (e.g. DEEPSEEK_API_KEY) from a sibling .env.

    The live agentic harness runs the canonical OpenRouter product route by
    default.  This file exists so a local run still finds its API keys when
    they are not in the environment. This harness-local loader mutates only the
    harness process and skips transport selectors. The product runtime uses a
    separate, non-mutating resolver for ``~/.hermes/.env``.
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
    with _ENV_PIN_LOCK:
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
    pipeline_mode: str | None = None,
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
    pipeline_mode:
        Explicit canonical executor mode: ``"staged"`` or ``"threaded"``.
        ``None`` preserves the normal staged default for legacy callers.

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

    scenario_id = str(scenario.get("id", "scenario"))
    output_dir = authorized_output_dir(output_base, tag, scenario_id)

    graph = scenario.get("graph")
    if graph is not None and not isinstance(graph, dict):
        raise ValueError("Scenario `graph` must be a JSON object when supplied.")
    if graph is not None and scenario.get("workflow_path") is not None:
        raise ValueError("Scenario accepts either `graph` or `workflow_path`, not both.")
    if graph is None:
        graph = _load_workflow(scenario.get("workflow_path"))

    assessment = scenario.get("assessment")
    expect_graph_changed = None
    if isinstance(assessment, Mapping) and "expect_graph_changed" in assessment:
        value = assessment["expect_graph_changed"]
        if not isinstance(value, bool):
            raise ValueError(
                "Scenario `assessment.expect_graph_changed` must be a boolean."
            )
        expect_graph_changed = value

    assessment_map = assessment if isinstance(assessment, Mapping) else {}

    def _string_tuple(value: object) -> tuple[str, ...]:
        if not isinstance(value, (list, tuple)):
            return ()
        return tuple(str(item).strip() for item in value if str(item).strip())

    refusal_kinds = _string_tuple(assessment_map.get("allow_safe_refusal_outcome_kinds"))
    absent_classes = _string_tuple(assessment_map.get("expected_no_candidate_absent_classes"))
    absent_features = tuple(
        dict(item)
        for item in (assessment_map.get("expected_no_candidate_absent_features") or ())
        if isinstance(item, Mapping)
    )
    reason = assessment_map.get("expected_no_candidate_reason")
    typed_refusal = bool(
        refusal_kinds
        or absent_classes
        or absent_features
        or (isinstance(reason, str) and reason.strip())
    )
    interaction_mode = scenario.get("interaction_mode")
    if (
        interaction_mode is None
        and scenario.get("apply") is False
        and expect_graph_changed is False
        and not typed_refusal
    ):
        interaction_mode = "answer_only"

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
        interaction_mode=interaction_mode,
        expect_graph_changed=expect_graph_changed,
        max_batches=scenario.get("max_batches"),
        pipeline_mode=pipeline_mode,
        allow_safe_refusal_outcome_kinds=refusal_kinds,
        expected_no_candidate_absent_classes=absent_classes,
        expected_no_candidate_absent_features=absent_features,
    )

    result = run_headless(
        request,
        entrypoint="live_agentic_harness",
        scenario_id=str(scenario.get("id") or "") or None,
    )
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
        # The comparison lane requires an explicit attestation even though
        # staged remains byte-compatible when its mode is omitted internally.
        "pipeline_mode": pipeline_mode,
    }
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
