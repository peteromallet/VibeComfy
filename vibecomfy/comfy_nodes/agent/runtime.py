"""Megaplan/Arnold runtime adapter for the VibeComfy agent-edit loop.

VibeComfy's ``agent_provider._load_arnold_runtime`` discovers a runtime module
that exposes ``run_agent_turn(...)`` and (optionally) ``get_agent_status(...)``.
The shipped arnold harness (``pip install`` of
https://github.com/peteromallet/Arnold, importable as the ``arnold`` package;
formerly ``megaplan``) does not expose those exact entry points -- its agent
backend is the ``arnold.pipelines.megaplan.agent.run_agent.AIAgent`` class (the
legacy ``megaplan.agent.run_agent.AIAgent`` location is still accepted as a
fallback). This module is the small adapter the runbook calls for: it drives
``AIAgent`` for a single, tool-free completion and returns VibeComfy's
agent-edit contracts.

Wire it up by pointing the discovery env var at this module::

    export VIBECOMFY_ARNOLD_RUNTIME_MODULE="vibecomfy.comfy_nodes.agent.runtime"

Routes
------
* ``openrouter``  -> OpenRouter (``https://openrouter.ai/api/v1``), key resolved
  from ``OPENROUTER_API_KEY`` or ``~/.hermes/.env`` (where the browser
  credential route writes it). This is the canonical browser-key route.
* ``arnold`` (also ``auto`` / ``anthropic`` / ``openai-codex`` after VibeComfy
  normalises them) -> AIAgent's own provider resolution (Claude via OpenRouter
  or local OAuth). Honest about availability: status reports ``ok`` only when a
  usable credential resolves.

Everything heavy (provider routing, retries, OAuth resolution) is handled by the
real ``AIAgent`` backend; this file is intentionally thin.
"""

from __future__ import annotations

import contextvars
import json
import os
import signal
import subprocess
import sys
import tempfile
import time
import logging
from pathlib import Path
from typing import Any, Mapping, Sequence

from vibecomfy.agent.deepseek_usage import (
    add_deepseek_usage,
    coerce_deepseek_usage,
    empty_deepseek_usage,
)
from vibecomfy.executor.contracts import (
    ModelAttemptEvidence,
    coerce_model_attempts,
    normalize_model_endpoint,
)
from vibecomfy.executor.profiler import (
    new_profile_id,
    profiler_log,
    profiler_span,
    short_text,
)

# How long to wait for a single agent turn (subprocess) before giving up.
_TURN_TIMEOUT_SECONDS = float(os.getenv("VIBECOMFY_AGENT_TURN_TIMEOUT", "180"))
# Grace granted after SIGTERM before a timed-out worker's process GROUP is
# SIGKILLed. Short by design: a hung grandchild (the cluster-A pipe hang) must
# not extend the turn timeout meaningfully.
_TURN_KILL_GRACE_SECONDS = float(os.getenv("VIBECOMFY_AGENT_TURN_KILL_GRACE", "3"))
_WORKER_PATH = str(Path(__file__).with_name("worker.py"))

# Per-turn agentic iteration budget for the Arnold AIAgent loop. The worker is
# a single tool-free completion, but deepseek-v4-flash exhausted a
# one-iteration, 2048-token turn (cluster B) and emitted prose instead of the
# required JSON. Default 2 gives the loop room to finish a synthesis; bounded
# so a runaway agentic loop cannot burn the scenario budget.
_AGENT_MAX_ITERATIONS = max(1, min(8, int(os.getenv("VIBECOMFY_AGENT_MAX_ITERATIONS", "2"))))

# Cluster-B correction retry: when a worker turn is killed by the model's
# iteration/token budget (finish_reason="length"), emits the exact
# iteration-limit sentinel, or returns zero usable contract output, retry once
# with a short correction prompt appended to the user message. The correction
# nudge is deliberately small — the raised budgets above are the primary fix.
_ITERATION_EXHAUSTION_CORRECTION_PROMPT = (
    "\n\nYour previous response was cut off by the model's iteration/token "
    "limit and could not be used. Produce the complete required response now, "
    "matching the exact output contract (a single JSON object, or exactly one "
    "```batch fenced block for batch_repl) with no preamble, no truncation, "
    "and no placeholder text."
)
_ITERATION_EXHAUSTION_MAX_CORRECTIONS = max(
    1, int(os.getenv("VIBECOMFY_AGENT_ITERATION_RETRY_CORRECTIONS", "1"))
)

# A fresh worker/transport retry is deliberately narrow: only a canonical
# empty-response failure with observed zero completion tokens may consume the
# extra attempts. Timeouts, capacity/provider errors, and malformed content do
# not retry here.
_WORKER_TRANSIENT_MAX_ATTEMPTS = max(1, int(os.getenv("VIBECOMFY_AGENT_TURN_RETRIES", "3")))
_WORKER_TRANSIENT_BACKOFF_SECONDS = float(os.getenv("VIBECOMFY_AGENT_TURN_RETRY_BACKOFF", "2.0"))
LOGGER = logging.getLogger(__name__)
_DEEPSEEK_USAGE_CAPTURE: contextvars.ContextVar[dict[str, Any] | None] = contextvars.ContextVar(
    "vibecomfy_deepseek_usage_capture",
    default=None,
)
_MODEL_ATTEMPT_CAPTURE: contextvars.ContextVar[list[dict[str, Any]] | None] = contextvars.ContextVar(
    "vibecomfy_model_attempt_capture",
    default=None,
)

_CANONICAL_OPENROUTER_BASE_URL = "https://openrouter.ai/api/v1"
_NATIVE_DEEPSEEK_BASE_URL = "https://api.deepseek.com/v1"
_OPENROUTER_MODEL = os.getenv("VIBECOMFY_OPENROUTER_MODEL", "openrouter:deepseek/deepseek-v4-pro")
_OPENROUTER_BASE_URL = os.getenv("VIBECOMFY_OPENROUTER_BASE_URL", "https://openrouter.ai/api/v1")
# Cluster B: a 2048-token ceiling truncated deepseek-v4-flash classify/reply
# turns (finish_reason="length" → prose instead of the required JSON). 4096
# gives the single-shot completion room for the full synthesis.
_OPENROUTER_MAX_TOKENS = int(os.getenv("VIBECOMFY_OPENROUTER_MAX_TOKENS", "4096"))

# Environment keys that select transport/endpoint/model routing.  These may be
# pinned explicitly by an operator or the live-agentic harness, but they must
# never be hydrated from the ambient ~/.hermes/.env credential file: a stored
# key is a credential, not a transport selector.  OPENROUTER_API_KEY /
# DEEPSEEK_API_KEY are deliberately NOT listed.
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

# Arnold/Hermes (Claude etc.) default model when a non-browser-key route is used.
_ARNOLD_MODEL = os.getenv("VIBECOMFY_ARNOLD_MODEL", "anthropic/claude-opus-4.6")
_ARNOLD_BASE_URL = os.getenv("VIBECOMFY_ARNOLD_BASE_URL") or None

_HERMES_ENV_PATH = Path("~/.hermes/.env").expanduser()


def begin_deepseek_usage_capture() -> contextvars.Token:
    return _DEEPSEEK_USAGE_CAPTURE.set(
        {
            "usage": empty_deepseek_usage(),
            "cache_breakout_complete": True,
        }
    )


def snapshot_deepseek_usage_capture() -> tuple[dict[str, int], bool]:
    state = _DEEPSEEK_USAGE_CAPTURE.get()
    if not isinstance(state, dict):
        return empty_deepseek_usage(), False
    usage = coerce_deepseek_usage(state.get("usage"))
    if usage["n_calls"] <= 0:
        return usage, False
    return usage, bool(state.get("cache_breakout_complete"))


def end_deepseek_usage_capture(token: contextvars.Token) -> None:
    _DEEPSEEK_USAGE_CAPTURE.reset(token)


def begin_model_attempt_capture() -> contextvars.Token:
    return _MODEL_ATTEMPT_CAPTURE.set([])


def snapshot_model_attempt_capture() -> tuple[dict[str, Any], ...]:
    return coerce_model_attempts(_MODEL_ATTEMPT_CAPTURE.get())


def end_model_attempt_capture(token: contextvars.Token) -> None:
    _MODEL_ATTEMPT_CAPTURE.reset(token)


def record_model_attempts(value: Any) -> None:
    """Append canonical attempts to the active executor capture, without duplicates."""
    state = _MODEL_ATTEMPT_CAPTURE.get()
    if state is None:
        return
    for attempt in coerce_model_attempts(value):
        if state and state[-1] == attempt:
            continue
        state.append(attempt)


def replace_last_model_attempts(value: Any) -> None:
    """Replace the matching captured suffix with normalized attempt evidence."""
    state = _MODEL_ATTEMPT_CAPTURE.get()
    normalized = coerce_model_attempts(value)
    if state is None or not normalized:
        return
    if len(state) >= len(normalized):
        state[-len(normalized):] = normalized
    else:
        state.extend(normalized)


def replace_last_model_attempt(value: Mapping[str, Any]) -> None:
    """Replace the most recent captured transport-success after domain parse failure."""
    replace_last_model_attempts([value])


def _record_captured_deepseek_usage(result: Any) -> None:
    state = _DEEPSEEK_USAGE_CAPTURE.get()
    if not isinstance(state, dict) or not isinstance(result, dict):
        return
    usage = coerce_deepseek_usage(result.get("deepseek_usage"))
    if usage["n_calls"] <= 0:
        return
    state["usage"] = add_deepseek_usage(state.get("usage"), usage)
    if not result.get("deepseek_cache_breakout_complete", False):
        state["cache_breakout_complete"] = False


def _read_env_file_entries(path: Path = _HERMES_ENV_PATH) -> list[tuple[str, str]]:
    """Read dotenv-style key/value pairs in file order."""
    entries: list[tuple[str, str]] = []
    try:
        text = path.read_text(encoding="utf-8")
    except (FileNotFoundError, OSError):
        return entries
    for line in text.splitlines():
        line = line.strip()
        if not line or line.startswith("#") or "=" not in line:
            continue
        key, _, value = line.partition("=")
        key = key.strip()
        value = value.strip().strip('"').strip("'")
        if key:
            entries.append((key, value))
    return entries


def _read_env_file(path: Path = _HERMES_ENV_PATH) -> dict[str, str]:
    """Read dotenv-style key/value pairs, with later duplicate entries winning."""
    values: dict[str, str] = {}
    for key, value in _read_env_file_entries(path):
        values[key] = value
    return values


def _load_env_file_into_environ(path: Path = _HERMES_ENV_PATH) -> None:
    """Best-effort: hydrate os.environ from ~/.hermes/.env without overwriting.

    The browser credential route writes ``OPENROUTER_API_KEY=*** here, so a
    ComfyUI process started without the key in its environment still picks it up.

    Credentials hydrate; transport-selecting keys never do.  A value stored in
    the credential file is a key, not a transport decision — the explicit
    ``VIBECOMFY_TRANSPORT`` / base-URL pin (or the canonical default) is the
    only authority, so an ambient file cannot silently switch transports.
    """
    for key, value in _read_env_file(path).items():
        if key and key not in os.environ and key not in _TRANSPORT_SELECTING_ENV_KEYS:
            os.environ[key] = value


# Hydrate on import so credential presence + provider calls see the stored key.
_load_env_file_into_environ()


def _resolve_openrouter_key() -> str | None:
    # Re-read the env file each call so a freshly browser-submitted key is seen
    # without restarting the server. Duplicate OPENROUTER_API_KEY lines can
    # exist; prefer the OpenRouter-shaped key over stale generic sk-* entries.
    file_values = _read_env_file()
    for key, value in file_values.items():
        if (
            key
            and value
            and key not in os.environ
            and key not in _TRANSPORT_SELECTING_ENV_KEYS
        ):
            os.environ[key] = value
    file_keys = [
        value.strip()
        for key, value in _read_env_file_entries()
        if key == "OPENROUTER_API_KEY" and value.strip()
    ]
    for file_key in file_keys:
        if file_key.startswith("sk-or-"):
            os.environ["OPENROUTER_API_KEY"] = file_key
            return file_key
    if file_keys:
        os.environ["OPENROUTER_API_KEY"] = file_keys[-1]
    _load_env_file_into_environ()
    candidates: list[tuple[str, str]] = []
    for key, value in file_values.items():
        if key == "OPENROUTER_API_KEY" or key.startswith("OPENROUTER_API_KEY_"):
            value = value.strip()
            if value:
                candidates.append((key, value))
    for key, value in os.environ.items():
        if key == "OPENROUTER_API_KEY" or key.startswith("OPENROUTER_API_KEY_"):
            value = value.strip()
            if value:
                candidates.append((key, value))
    candidates.sort(key=lambda item: (item[0] != "OPENROUTER_API_KEY", item[0]))
    for _, value in candidates:
        if value.startswith("sk-or-"):
            return value
    return candidates[0][1] if candidates else None


def _is_runtime_unavailable(result: Mapping[str, Any]) -> bool:
    """True when a worker error means the agent runtime is unavailable.

    Covers a missing backend dependency (``ImportError`` /
    ``ModuleNotFoundError``) and an unregistered dispatch adapter
    (``LookupError`` — e.g. codex/claude not wired into the default dispatcher
    yet). The worker also sets ``runtime_unavailable: True`` for these. All map
    to a non-retryable AGENT_RUNTIME_UNAVAILABLE signal upstream, never to a
    transient provider error.
    """
    if result.get("runtime_unavailable"):
        return True
    return result.get("error_type") in {"ModuleNotFoundError", "ImportError", "LookupError"}


def _raise_worker_error(result: Mapping[str, Any]) -> None:
    err = str(result.get("error") or "agent worker failed")
    output_tail = "\n".join(
        str(result.get(key) or "").strip()
        for key in ("worker_stdout_tail", "worker_stderr_tail")
        if result.get(key)
    ).strip()
    if output_tail:
        err = f"{err}\n\nWorker output tail:\n{output_tail}"
    error_type = str(result.get("error_type") or "").strip()
    message = f"{error_type}: {err}" if error_type and error_type not in err else err
    lowered = message.lower()

    def _with_worker_result(exc: BaseException) -> BaseException:
        """Attach the full worker result dict additively for evidence plumbing.

        The exception type and message are unchanged; upstream classify/reply
        failure envelopes can read ``worker_result`` to persist parse_reason,
        raw preview, usage, model, phase, and endpoint without re-resolving
        provider internals.
        """
        try:
            exc.worker_result = dict(result)  # type: ignore[attr-defined]
        except Exception:  # noqa: BLE001 - evidence attachment is best-effort
            pass
        return exc

    if (
        error_type in {"AuthError", "AuthenticationError", "PermissionError"}
        or "authenticationerror" in lowered
        or "error code: 401" in lowered
        or "missing authentication header" in lowered
        or "invalid api key" in lowered
        or "unauthorized" in lowered
    ):
        raise _with_worker_result(PermissionError(message))
    if _is_runtime_unavailable(result):
        raise _with_worker_result(ImportError(message))
    raise _with_worker_result(RuntimeError(message))


def _normalize_route(route: str | None) -> str:
    normalized = (route or "arnold").strip().lower()
    if normalized in {"auto", "anthropic", "openai-codex"}:
        return "arnold"
    if normalized == "hermes":
        return "openrouter"
    if normalized in {"arnold", "openrouter", "deepseek"}:
        return "openrouter" if normalized == "deepseek" else normalized
    return "unknown"


# Panel route -> arnold dispatch agent id. The worker registers/dispatches under
# this id. Only ``hermes`` is wired in the default dispatcher today; ``codex`` /
# ``claude`` will raise LookupError until adapters are registered (Step B's
# readiness gate keeps the panel from reaching them).
_ROUTE_TO_AGENT_ID = {
    "deepseek": "hermes",
    "openrouter": "hermes",
    "openai-codex": "codex",
    "anthropic": "claude",
}


def _agent_id_for_route(route: str | None) -> str:
    """Map a panel route name to the arnold dispatch agent id.

    Unlike :func:`_normalize_route`, this keeps anthropic/openai-codex distinct
    so the worker can dispatch to the correct (eventual) adapter. ``auto`` and
    bare ``arnold`` fall back to ``hermes`` (the only registered backend).
    """
    requested = (route or "").strip().lower()
    if requested == "claude":
        requested = "anthropic"
    elif requested == "codex":
        requested = "openai-codex"
    if requested in {"", "auto", "arnold", "hermes"}:
        return "hermes"
    return _ROUTE_TO_AGENT_ID.get(requested, "unknown")


def _default_model_for_route(route: str, model: str | None) -> str:
    normalized_route = _normalize_route(route)
    if normalized_route == "unknown":
        return "unknown"
    if _is_real_model_override(model):
        return _strip_provider_prefix(model, "openrouter")
    if normalized_route == "openrouter":
        return _strip_provider_prefix(_OPENROUTER_MODEL, "openrouter")
    return _ARNOLD_MODEL


def _is_real_model_override(model: str | None) -> bool:
    """True when *model* is an actual provider model, not the panel contract id."""
    normalized = (model or "").strip()
    return bool(normalized and normalized != "agent-edit")


def _runtime_model_for_route(route: str | None, model: str | None) -> str | None:
    """Return the model slug to hand to the provider adapter.

    The browser/status contract historically used ``agent-edit`` as a product
    label.  That is not a valid OpenRouter/Anthropic/Codex model id, so keep it
    out of the provider seam and let the route resolve its real default.
    """
    normalized_route = _normalize_route(route)
    if normalized_route == "unknown":
        return None
    # Explicit per-process force-override: when set, ignore the profile/judge
    # model slug and route everything through this model (e.g. swapping the
    # hermes backend to a non-DeepSeek OpenAI-compatible endpoint). No-op unset.
    forced_model = os.getenv("VIBECOMFY_FORCE_MODEL")
    if forced_model:
        return forced_model
    if _is_real_model_override(model):
        return model
    if normalized_route == "openrouter":
        return _OPENROUTER_MODEL
    if normalized_route in {"arnold", "anthropic", "openai-codex"}:
        return _ARNOLD_MODEL
    return None


def _strip_provider_prefix(model: str, provider: str) -> str:
    prefix = f"{provider}:"
    return model.split(":", 1)[1] if model.lower().startswith(prefix) else model


def _normalize_native_deepseek_model(model: str) -> str:
    """Strip provider prefixes DeepSeek's native API rejects.

    Native ``api.deepseek.com`` only accepts bare model names
    (``deepseek-v4-pro`` / ``deepseek-v4-flash``).  OpenRouter-style slugs like
    ``openrouter:deepseek/deepseek-v4-flash`` or ``deepseek/deepseek-v4-flash``
    (which the executor profile ships) are rejected with HTTP 400
    "The supported API model names are deepseek-v4-pro or deepseek-v4-flash, but
    you passed deepseek/deepseek-v4-flash."  Strip both the ``openrouter:``
    route prefix and any ``deepseek/`` provider segment when pointed at the
    native endpoint.
    """
    stripped = _strip_provider_prefix(model, "openrouter")
    # Drop a leading "deepseek/" provider segment (OpenRouter-format slug).
    if "/" in stripped:
        provider_seg, _, model_seg = stripped.partition("/")
        if provider_seg.lower() == "deepseek" and model_seg:
            stripped = model_seg
    return stripped


def _explicit_transport() -> str | None:
    """Return the explicit ``VIBECOMFY_TRANSPORT`` pin, or ``None``.

    Only an explicit pin (set by the live-agentic harness selector or by an
    operator) is honored.  Ambience — inherited base URLs, stored credentials,
    credential presence — never selects transport.
    """
    value = os.getenv("VIBECOMFY_TRANSPORT", "").strip().lower()
    if value in {"openrouter", "native"}:
        return value
    return None


def _base_url_for_route(route: str | None) -> str:
    """Resolve the hermes endpoint from the explicit transport pin first.

    An explicit ``VIBECOMFY_TRANSPORT`` pin is AUTHORITATIVE: when set, every
    profile phase resolves to the pinned transport's endpoint.  The route-level
    OpenRouter default applies only when no pin is set, so a route contract can
    never displace an explicit selection (and ambient credentials/base URLs can
    never silently switch an operator's pinned transport).
    """
    transport = _explicit_transport()
    if transport == "native":
        return _NATIVE_DEEPSEEK_BASE_URL
    if transport == "openrouter":
        return _CANONICAL_OPENROUTER_BASE_URL
    if (route or "").strip().lower() == "openrouter":
        return _CANONICAL_OPENROUTER_BASE_URL
    return _OPENROUTER_BASE_URL


def _is_native_deepseek_endpoint(base_url: str | None = None) -> bool:
    if _explicit_transport() == "native":
        return True
    return "deepseek.com" in (base_url or _OPENROUTER_BASE_URL or "").lower()


def _hermes_credential_for(route: str | None, model: str | None) -> str | None:
    # A pinned native transport is authoritative over the route-level OpenRouter
    # default: prefer DEEPSEEK_API_KEY directly so a stale OpenRouter ``sk-or-*``
    # pool key can't win — _resolve_openrouter_key() force-prefers any sk-or-*
    # entry it finds in ~/.hermes/.env.
    if _explicit_transport() == "native" and os.getenv("DEEPSEEK_API_KEY"):
        return os.getenv("DEEPSEEK_API_KEY")
    if (route or "").strip().lower() == "openrouter":
        return _resolve_openrouter_key()
    # Explicit per-process override (e.g. pointing the hermes backend at a
    # non-OpenRouter OpenAI-compatible endpoint such as Fireworks). Bypasses
    # _resolve_openrouter_key(), which force-clobbers OPENROUTER_API_KEY from
    # ~/.hermes/.env and would ignore a freshly-exported key. No-op when unset.
    explicit_key = os.getenv("VIBECOMFY_HERMES_API_KEY")
    if explicit_key:
        return explicit_key
    # When pointed at DeepSeek's native API, prefer DEEPSEEK_API_KEY directly so a
    # stale OpenRouter ``sk-or-*`` pool key in ~/.hermes/.env can't win —
    # _resolve_openrouter_key() force-prefers any sk-or-* entry it finds there.
    if _is_native_deepseek_endpoint() and os.getenv("DEEPSEEK_API_KEY"):
        return os.getenv("DEEPSEEK_API_KEY")
    return _resolve_openrouter_key()


def _has_arnold_credential() -> bool:
    return bool(
        os.getenv("ANTHROPIC_API_KEY")
        or os.getenv("ANTHROPIC_TOKEN")
        or os.getenv("OPENROUTER_API_KEY")
        or os.getenv("CLAUDE_CODE_OAUTH_TOKEN")
        or Path("~/.claude/.credentials.json").expanduser().exists()
        or Path("~/.hermes/.anthropic_oauth.json").expanduser().exists()
    )


def _split_messages(messages: Sequence[Mapping[str, Any]] | None) -> tuple[str | None, str | None]:
    """Return (system_message, user_message) from VibeComfy's built messages."""
    system_msg: str | None = None
    user_msg: str | None = None
    for entry in messages or []:
        role = entry.get("role")
        content = entry.get("content")
        if not isinstance(content, str):
            continue
        if role == "system" and system_msg is None:
            system_msg = content
        elif role == "user":
            user_msg = content
    return system_msg, user_msg


def _build_agent_kwargs(agent_id: str, route: str | None = None, model: str | None = None) -> dict[str, Any]:
    """AIAgent constructor kwargs for a single, tool-free completion.

    Keyed off the resolved *dispatch agent id* (not the panel route). ``hermes``
    is always configured for OpenRouter, including the legacy ``deepseek`` route
    alias. For ``codex`` / ``claude`` the worker dispatches through the default
    dispatcher and ignores ``agent_kwargs``, so we pass only the tool-free
    single-shot flags.
    """
    common: dict[str, Any] = dict(
        max_iterations=_AGENT_MAX_ITERATIONS,
        enabled_toolsets=[],          # no tools: one-shot completion
        save_trajectories=False,      # no trajectory files on disk
        skip_context_files=True,      # don't load SOUL.md / AGENTS.md
        skip_memory=True,             # don't load/write the memory store
        quiet_mode=True,
    )
    if agent_id == "hermes":
        base_url = _base_url_for_route(route)
        resolved_model = _runtime_model_for_route(route, model) or _OPENROUTER_MODEL
        if _is_native_deepseek_endpoint(base_url):
            # Native api.deepseek.com rejects OpenRouter-style ``deepseek/`` slugs
            # with HTTP 400; normalize to the bare model name it accepts.
            resolved_model = _normalize_native_deepseek_model(resolved_model)
        else:
            resolved_model = _strip_provider_prefix(resolved_model, "openrouter")
        return dict(
            model=resolved_model,
            api_key=_hermes_credential_for(route, model),
            base_url=base_url,
            provider="openrouter",
            max_tokens=_OPENROUTER_MAX_TOKENS,
            **common,
        )
    # codex / claude -> default dispatcher resolves everything; kwargs unused.
    return dict(**common)


def _is_typed_empty_worker_result(result: Mapping[str, Any]) -> bool:
    """True only for typed empty responses with observed zero completion tokens."""
    attempts = coerce_model_attempts(result.get("model_attempts"))
    if not attempts:
        return False
    latest = attempts[-1]
    usage = latest.get("token_usage")
    return (
        latest.get("outcome") == "failure"
        and latest.get("failure_type") == "empty_response"
        and isinstance(usage, Mapping)
        and usage.get("completion_tokens") == 0
    )


def _runtime_provider_transport(
    *, agent_id: str, agent_kwargs: Mapping[str, Any]
) -> tuple[str, str, str]:
    endpoint = normalize_model_endpoint(agent_kwargs.get("base_url"))
    if agent_id != "hermes":
        return "unknown", "unknown", endpoint
    if "openrouter.ai" in endpoint:
        return "openrouter", "openrouter", endpoint
    if "deepseek.com" in endpoint:
        return "deepseek", "native", endpoint
    if endpoint != "unknown":
        return "unknown", "openai_compatible", endpoint
    return "unknown", "unknown", endpoint


def _timeout_model_attempt(
    *,
    agent_kwargs: Mapping[str, Any],
    agent_id: str,
    requested_model: str | None,
    resolved_model: str | None,
    profiling_context: Mapping[str, Any] | None,
    attempt: int,
) -> dict[str, Any]:
    provider, transport, endpoint = _runtime_provider_transport(
        agent_id=agent_id, agent_kwargs=agent_kwargs
    )
    return ModelAttemptEvidence(
        phase=(profiling_context or {}).get("backend_phase") or "agent_turn",
        attempt=attempt,
        outcome="failure",
        failure_type="timeout",
        requested_model=requested_model,
        resolved_model=resolved_model or agent_kwargs.get("model"),
        adapter=agent_id,
        provider=provider,
        transport=transport,
        endpoint=endpoint,
    ).to_dict()


def _is_iteration_exhaustion_result(result: Mapping[str, Any]) -> bool:
    """True when a worker result shows iteration/token exhaustion.

    Recoverable with a short correction retry when any of these hold:
    * ``finish_reason == "length"`` (the provider cut the completion off),
    * the raw output contains the exact iteration-limit sentinel
      (``I reached the iteration limit``) that deepseek-v4-flash emits,
    * the worker received non-empty raw output but produced ZERO usable
      contract fields (parse failure on prose instead of the required JSON,
      a missing batch fence, ...).

    Deliberately does NOT match canonical typed-empty responses (parse_reason
    ``"empty"`` with empty raw): those stay exclusively on the existing
    typed-empty transport-retry path.
    """
    finish_reason = str(result.get("finish_reason") or "").strip().casefold()
    if finish_reason == "length":
        return True
    raw = str(result.get("raw_response_preview") or result.get("content") or "").strip()
    if "I reached the iteration limit" in raw:
        return True
    usable = (
        str(result.get("content") or "").strip()
        or str(result.get("json") or "").strip()
        or str(result.get("python") or "").strip()
        or str(result.get("delta") or "").strip()
    )
    if usable:
        return False
    parse_reason = str(result.get("parse_reason") or "").strip()
    return bool(raw) and parse_reason in {
        "empty",
        "malformed_json",
        "non_json_content",
        "missing_content",
        "missing_required_fields",
    }


def _terminate_worker_group(pid: int) -> None:
    """Terminate the worker's process GROUP and let the caller reap it.

    The worker is spawned with ``start_new_session=True``, so it is a session
    leader whose process-group id equals its pid; signalling the group reaches
    every grandchild that inherited the worker's stdio fds (the cluster-A pipe
    hang: ``subprocess.run(timeout=...)`` blocked in ``communicate()`` forever
    because a grandchild held the captured pipe open). SIGTERM first with a
    short grace so a well-behaved worker can flush; then SIGKILL, which is
    uncatchable, so the caller's subsequent ``wait()`` cannot hang.

    ``PermissionError`` (EPERM) from ``killpg`` is treated like ESRCH: macOS
    returns EPERM for a process group whose members are all zombies (nothing
    left to signal), which is exactly the "already gone" state we probe for.
    """
    try:
        os.killpg(pid, signal.SIGTERM)
    except (ProcessLookupError, PermissionError):
        return  # already gone, or only zombies remain
    deadline = time.monotonic() + _TURN_KILL_GRACE_SECONDS
    while time.monotonic() < deadline:
        try:
            os.killpg(pid, 0)
        except (ProcessLookupError, PermissionError):
            return  # group exited during the grace window
        time.sleep(0.05)
    try:
        os.killpg(pid, signal.SIGKILL)
    except (ProcessLookupError, PermissionError):
        pass


def _run_worker_subprocess(
    command: list[str],
    *,
    cwd: str,
    env: Mapping[str, str],
    timeout: float,
    stdout_path: str,
    stderr_path: str,
) -> tuple[int, str, str]:
    """Run *command* in its own process group; return (returncode, stdout, stderr).

    stdout/stderr go to regular temp FILES, never pipes: a grandchild that
    inherits the worker's stdio fds cannot keep a pipe open past our timeout,
    so the turn timeout actually fires (cluster A). On timeout the whole process
    GROUP is terminated (SIGTERM → short grace → SIGKILL) and the direct child
    is reaped before ``subprocess.TimeoutExpired`` is re-raised for the caller.
    """
    with open(stdout_path, "w", encoding="utf-8") as out_fh, open(
        stderr_path, "w", encoding="utf-8"
    ) as err_fh:
        proc = subprocess.Popen(
            command,
            cwd=cwd,
            env=env,
            stdout=out_fh,
            stderr=err_fh,
            start_new_session=True,
        )
        try:
            proc.wait(timeout=timeout)
        except subprocess.TimeoutExpired:
            _terminate_worker_group(proc.pid)
            proc.wait()  # SIGKILLed; cannot hang
            raise
    with open(stdout_path, encoding="utf-8", errors="replace") as fh:
        stdout_text = fh.read()
    with open(stderr_path, encoding="utf-8", errors="replace") as fh:
        stderr_text = fh.read()
    return proc.returncode, stdout_text, stderr_text


def _run_worker(
    agent_kwargs: dict[str, Any],
    system_msg: str | None,
    user_msg: str,
    *,
    response_contract: str = "python",
    agent_id: str = "hermes",
    model: str | None = None,
    requested_model: str | None = None,
    effort: str | None = None,
    profiling_context: Mapping[str, Any] | None = None,
) -> dict[str, Any]:
    """Run one AIAgent turn in an isolated subprocess; return its result dict.

    A fresh subprocess/transport is permitted only after a canonical
    ``empty_response`` attempt with observed ``completion_tokens == 0``. Timeouts,
    provider/capacity errors, and malformed non-empty content surface immediately.
    """
    accumulated_attempts: list[dict[str, Any]] = []
    iteration_corrections = 0
    for attempt in range(_WORKER_TRANSIENT_MAX_ATTEMPTS):
        attempt_profile = dict(profiling_context or {})
        if attempt:
            attempt_profile["transient_retry_count"] = attempt
        try:
            result = _run_worker_once(
                agent_kwargs,
                system_msg,
                user_msg,
                response_contract=response_contract,
                agent_id=agent_id,
                model=model,
                requested_model=requested_model,
                effort=effort,
                profiling_context=attempt_profile,
            )
        except TimeoutError as exc:
            timeout_attempt = _timeout_model_attempt(
                agent_kwargs=agent_kwargs,
                agent_id=agent_id,
                requested_model=requested_model,
                resolved_model=model,
                profiling_context=profiling_context,
                attempt=len(accumulated_attempts) + 1,
            )
            accumulated_attempts.append(timeout_attempt)
            record_model_attempts([timeout_attempt])
            exc.model_attempts = list(accumulated_attempts)  # type: ignore[attr-defined]
            raise
        attempts = list(coerce_model_attempts(result.get("model_attempts")))
        for item in attempts:
            item["attempt"] = len(accumulated_attempts) + 1
            normalized = ModelAttemptEvidence.from_mapping(item).to_dict()
            accumulated_attempts.append(normalized)
            record_model_attempts([normalized])
        if accumulated_attempts:
            result["model_attempts"] = list(accumulated_attempts)
        if (
            _is_iteration_exhaustion_result(result)
            and not _is_typed_empty_worker_result(result)
            and iteration_corrections < _ITERATION_EXHAUSTION_MAX_CORRECTIONS
            and attempt + 1 < _WORKER_TRANSIENT_MAX_ATTEMPTS
        ):
            iteration_corrections += 1
            LOGGER.warning(
                "agent worker output shows iteration/token exhaustion "
                "(attempt %d/%d, finish_reason=%r); retrying once with a "
                "correction prompt",
                attempt + 1,
                _WORKER_TRANSIENT_MAX_ATTEMPTS,
                result.get("finish_reason"),
            )
            user_msg = f"{user_msg}\n\n{_ITERATION_EXHAUSTION_CORRECTION_PROMPT}"
            continue
        if (
            "error" in result
            and _is_typed_empty_worker_result(result)
            and attempt + 1 < _WORKER_TRANSIENT_MAX_ATTEMPTS
        ):
            LOGGER.warning(
                "agent worker returned typed empty response (attempt %d/%d); retrying",
                attempt + 1,
                _WORKER_TRANSIENT_MAX_ATTEMPTS,
            )
            time.sleep(_WORKER_TRANSIENT_BACKOFF_SECONDS * attempt)
            continue
        return result
    raise RuntimeError("agent worker retry loop exited without a result")


def _run_worker_once(
    agent_kwargs: dict[str, Any],
    system_msg: str | None,
    user_msg: str,
    *,
    response_contract: str = "python",
    agent_id: str = "hermes",
    model: str | None = None,
    requested_model: str | None = None,
    effort: str | None = None,
    profiling_context: Mapping[str, Any] | None = None,
) -> dict[str, Any]:
    """Run one AIAgent turn in an isolated subprocess; return its result dict.

    Single attempt — no retry. See :func:`_run_worker` for the retry wrapper.

    Isolation avoids the top-level module-name collision between megaplan's
    agent (bare ``import utils`` / ``model_tools``) and ComfyUI's own ``utils``
    package, and keeps the agent's asyncio/HTTP state out of ComfyUI's loop.
    """
    with tempfile.TemporaryDirectory(prefix="vibecomfy-agent-") as tmp:
        req_path = os.path.join(tmp, "request.json")
        res_path = os.path.join(tmp, "result.json")
        with open(req_path, "w", encoding="utf-8") as fh:
            json.dump(
                {
                    "agent_id": agent_id,
                    "model": model,
                    "requested_model": requested_model,
                    "effort": effort,
                    "agent_kwargs": agent_kwargs,
                    "system_message": system_msg,
                    "user_message": user_msg,
                    "response_contract": response_contract,
                    "profiling_context": dict(profiling_context or {}),
                },
                fh,
            )
        env = dict(os.environ)
        # Ensure the child sees the same credential the parent resolved for the
        # Hermes adapter.  For native DeepSeek endpoints this must be the
        # DeepSeek key, not a stale browser/OpenRouter key from ~/.hermes/.env.
        hermes_key = agent_kwargs.get("api_key") or _resolve_openrouter_key()
        if isinstance(hermes_key, str) and hermes_key:
            env["OPENROUTER_API_KEY"] = hermes_key
            env["OPENAI_API_KEY"] = hermes_key
            env["HERMES_API_KEY"] = hermes_key
        # Don't leak ComfyUI's cwd/path into the child (it is what causes the
        # `utils` collision); run from a neutral directory.
        stdout_path = os.path.join(tmp, "worker.stdout.log")
        stderr_path = os.path.join(tmp, "worker.stderr.log")
        try:
            with profiler_span(
                LOGGER,
                "runtime.worker_subprocess",
                agent_id=agent_id,
                response_contract=response_contract,
                worker_path=_WORKER_PATH,
                profiling_context=dict(profiling_context or {}),
            ) as span:
                returncode, stdout_text, stderr_text = _run_worker_subprocess(
                    [sys.executable, _WORKER_PATH, req_path, res_path],
                    cwd=tmp,
                    env=env,
                    timeout=_TURN_TIMEOUT_SECONDS,
                    stdout_path=stdout_path,
                    stderr_path=stderr_path,
                )
                span.update(
                    returncode=returncode,
                    stdout_length=len(stdout_text),
                    stderr_length=len(stderr_text),
                )
        except subprocess.TimeoutExpired as exc:
            raise TimeoutError(
                f"Agent worker timed out after {_TURN_TIMEOUT_SECONDS:g} seconds."
            ) from exc
        try:
            with open(res_path, encoding="utf-8") as fh:
                result = json.load(fh)
                worker_profile = result.get("_profiling") if isinstance(result, dict) else None
                profiler_log(
                    LOGGER,
                    "runtime.worker_result",
                    agent_id=agent_id,
                    response_contract=response_contract,
                    profiling_context=dict(profiling_context or {}),
                    worker_profile=worker_profile if isinstance(worker_profile, dict) else None,
                    result_keys=sorted(result.keys()) if isinstance(result, dict) else None,
                )
                if isinstance(result, dict) and "error" in result:
                    if stdout_text.strip():
                        result.setdefault("worker_stdout_tail", stdout_text[-4000:])
                    if stderr_text.strip():
                        result.setdefault("worker_stderr_tail", stderr_text[-4000:])
                _record_captured_deepseek_usage(result)
                return result
        except (FileNotFoundError, json.JSONDecodeError) as exc:
            tail = (stderr_text or stdout_text or "")[-800:]
            raise RuntimeError(
                f"Agent worker produced no result (exit {returncode}). {exc}. "
                f"Worker output tail:\n{tail}"
            ) from exc


def run_agent_turn(
    *,
    task: str,
    python_source: str,
    route: str,
    model: str | None = None,
    effort: str | None = None,
    messages: Sequence[Mapping[str, Any]] | None = None,
) -> dict[str, Any]:
    """Run one agent-edit turn through the megaplan AIAgent backend.

    Returns ``{"python": <str>, "message": <str>}`` as VibeComfy expects.
    """
    agent_id = _agent_id_for_route(route)
    system_msg, user_msg = _split_messages(messages)
    if user_msg is None:
        # Fall back to reconstructing the user message from the raw inputs.
        user_msg = (
            f"User request:\n{task}\n\n"
            "Current scratchpad Python:\n```python\n" + (python_source or "") + "\n```"
        )

    if agent_id == "hermes" and not _hermes_credential_for(route, model):
        raise PermissionError(
            "OpenRouter route selected but no OPENROUTER_API_KEY is available "
            "(checked environment and ~/.hermes/.env). Submit a key via the "
            "VibeComfy panel or export OPENROUTER_API_KEY."
        )

    agent_kwargs = _build_agent_kwargs(agent_id, route=route, model=model)
    result = _run_worker(
        agent_kwargs,
        system_msg,
        user_msg,
        response_contract="python",
        agent_id=agent_id,
        model=_runtime_model_for_route(route, model),
        requested_model=model,
        effort=effort,
        profiling_context={"backend_phase": "implement"},
    )
    if "error" in result:
        _raise_worker_error(result)
    return dict(result)


def run_agent_turn_delta(
    *,
    task: str,
    projection: str,
    op_schema: Mapping[str, Any],
    route: str,
    model: str | None = None,
    effort: str | None = None,
    messages: Sequence[Mapping[str, Any]] | None = None,
) -> dict[str, Any]:
    """Run one v2 agent-edit turn and return ``{"delta": [...], "message": str}``."""
    agent_id = _agent_id_for_route(route)
    system_msg, user_msg = _split_messages(messages)
    if user_msg is None:
        user_msg = (
            f"User request:\n{task}\n\n"
            "Address-preserving UI projection:\n"
            f"{projection}"
        )

    if agent_id == "hermes" and not _hermes_credential_for(route, model):
        raise PermissionError(
            "OpenRouter route selected but no OPENROUTER_API_KEY is available "
            "(checked environment and ~/.hermes/.env). Submit a key via the "
            "VibeComfy panel or export OPENROUTER_API_KEY."
        )

    agent_kwargs = _build_agent_kwargs(agent_id, route=route, model=model)
    result = _run_worker(
        agent_kwargs,
        system_msg,
        user_msg,
        response_contract="delta",
        agent_id=agent_id,
        model=_runtime_model_for_route(route, model),
        requested_model=model,
        effort=effort,
        profiling_context={"backend_phase": "implement"},
    )
    if "error" in result:
        _raise_worker_error(result)
    return dict(result)


def run_agent_turn_batch(
    *,
    task: str,
    route: str,
    model: str | None = None,
    effort: str | None = None,
    messages: Sequence[Mapping[str, Any]] | None = None,
) -> dict[str, Any]:
    """Run one batch-REPL agent-edit turn and return raw model content."""
    agent_id = _agent_id_for_route(route)
    system_msg, user_msg = _split_messages(messages)
    if user_msg is None:
        user_msg = f"User request:\n{task}"

    if agent_id == "hermes" and not _hermes_credential_for(route, model):
        raise PermissionError(
            "OpenRouter route selected but no OPENROUTER_API_KEY is available "
            "(checked environment and ~/.hermes/.env). Submit a key via the "
            "VibeComfy panel or export OPENROUTER_API_KEY."
        )

    agent_kwargs = _build_agent_kwargs(agent_id, route=route, model=model)
    result = _run_worker(
        agent_kwargs,
        system_msg,
        user_msg,
        response_contract="batch_repl",
        agent_id=agent_id,
        model=_runtime_model_for_route(route, model),
        requested_model=model,
        effort=effort,
        profiling_context={"backend_phase": "batch"},
    )
    if "error" in result:
        _raise_worker_error(result)
    return dict(result)


def _requested_route(route: str | None) -> str:
    """Canonical panel route name (claude->anthropic, codex->openai-codex).

    The ``hermes`` dispatch agent id is exposed as a product route in headless
    executor specs; for readiness/status purposes it is the same as the
    OpenRouter browser-key route.
    """
    requested = (route or "").strip().lower()
    if requested == "claude":
        return "anthropic"
    if requested == "codex":
        return "openai-codex"
    if requested in {"deepseek", "hermes"}:
        return "openrouter"
    return requested


def _codex_cli_present() -> bool:
    """True if a `codex` CLI binary resolves on PATH."""
    import shutil

    return bool(shutil.which("codex"))


def _claude_cli_present() -> bool:
    """True if a `claude` CLI binary resolves on PATH."""
    import shutil

    return bool(shutil.which("claude"))


def _bun_present() -> bool:
    """True if a `bun` binary resolves on PATH (shannon launcher dependency)."""
    import shutil

    return bool(shutil.which("bun"))


def _registered_agent_ids() -> set[str]:
    """Best-effort introspection of the arnold default dispatcher's registry.

    The dispatcher exposes no public registry query, so we read its private
    ``_adapters`` mapping defensively. If arnold (or the attribute) is not
    importable, return an empty set rather than crashing — readiness must never
    raise.
    """
    try:
        import arnold.agent as _agent_mod
    except ImportError:
        return set()
    dispatcher = getattr(_agent_mod, "_default", None)
    adapters = getattr(dispatcher, "_adapters", None)
    if isinstance(adapters, dict):
        return set(adapters.keys())
    return set()


def _adapter_registered(agent_id: str) -> bool:
    """True when *agent_id* has an adapter registered in the default dispatcher."""
    return agent_id in _registered_agent_ids()


def _auth_json_has_token(path: Path) -> bool:
    """True if an auth.json at *path* carries a non-empty credential.

    Recognizes the standalone Codex CLI shape (ChatGPT OAuth: ``tokens`` dict
    with ``access_token``/``id_token``, or a top-level ``OPENAI_API_KEY``) as
    well as the hermes shape (``token``/``access_token``/``api_key``).
    """
    try:
        raw = path.expanduser().read_text(encoding="utf-8")
    except (FileNotFoundError, OSError):
        return False
    try:
        data = json.loads(raw)
    except json.JSONDecodeError:
        return False
    if not isinstance(data, dict):
        return False
    for key in ("token", "access_token", "api_key", "OPENAI_API_KEY", "id_token"):
        value = data.get(key)
        if isinstance(value, str) and value.strip():
            return True
    tokens = data.get("tokens")
    if isinstance(tokens, dict):
        for key in ("access_token", "id_token", "account_id"):
            value = tokens.get(key)
            if isinstance(value, str) and value.strip():
                return True
    return False


def _codex_auth_present() -> bool:
    """True if the codex CLI is authenticated.

    The standalone ``codex`` CLI (ChatGPT login) stores creds in
    ``~/.codex/auth.json``; the hermes-wrapped variant used ``~/.hermes/auth.json``.
    Either satisfies the codex route.
    """
    return _auth_json_has_token(Path("~/.codex/auth.json")) or _auth_json_has_token(
        Path("~/.hermes/auth.json")
    )


def readiness(*, route: str, model: str | None = None) -> dict[str, Any]:
    """Report truthful, per-route backend readiness.

    Only the browser-key ``openrouter`` route reaches a real, registered adapter
    today (``hermes`` configured for OpenRouter).
    ``openai-codex`` and ``anthropic`` have no
    adapter registered in the default dispatcher yet, so they report
    ``ready: False`` with a clear reason — the panel must tell the truth rather
    than green-light them off an unrelated OpenRouter/Anthropic key.
    """
    backend = "arnold.pipelines.megaplan.agent.run_agent.AIAgent"
    requested = _requested_route(route)

    if requested == "openrouter" or (
        requested in {"", "auto"} and _resolve_openrouter_key()
    ):
        key = _resolve_openrouter_key()
        return {
            "ready": bool(key),
            "backend": backend,
            "route": "openrouter",
            "model": _default_model_for_route("openrouter", model),
            "base_url": _CANONICAL_OPENROUTER_BASE_URL,
            "openrouter_key_present": bool(key),
            "reason": (
                "OpenRouter key resolved; ready to run agent-edit turns."
                if key
                else "No OPENROUTER_API_KEY in environment or ~/.hermes/.env."
            ),
        }

    if requested == "openai-codex":
        # The codex route is ready only when (a) a ``codex`` adapter is registered
        # in the default dispatcher AND (b) codex is actually usable here: the
        # ``codex`` CLI on PATH plus a ~/.hermes/auth.json token. Never green-light
        # off an unrelated key.
        registered = _adapter_registered("codex")
        have_token = _codex_auth_present()
        have_cli = _codex_cli_present()
        if not registered:
            # Not wired yet: report honest probe details (this shape is what the
            # panel shows while the parallel codex adapter is still in flight).
            return {
                "ready": False,
                "backend": backend,
                "route": "openai-codex",
                "model": _default_model_for_route("openai-codex", model),
                "codex_adapter_registered": False,
                "codex_auth_present": have_token,
                "codex_cli_present": have_cli,
                "reason": (
                    "codex adapter not wired yet (no Codex adapter registered in the "
                    "arnold dispatcher; "
                    f"codex auth {'present' if have_token else 'absent'}, "
                    f"codex CLI {'on PATH' if have_cli else 'not on PATH'})."
                ),
            }
        usable = have_cli and have_token
        return {
            "ready": usable,
            "backend": backend,
            "route": "openai-codex",
            "model": _default_model_for_route("openai-codex", model),
            "codex_adapter_registered": True,
            "codex_auth_present": have_token,
            "codex_cli_present": have_cli,
            "reason": (
                "codex adapter registered and codex is usable (CLI on PATH + "
                "codex login present). Note: a live turn still depends on Codex "
                "account quota."
                if usable
                else (
                    "codex adapter registered but codex is not usable: "
                    f"codex CLI {'on PATH' if have_cli else 'not on PATH'}, "
                    f"codex auth {'present' if have_token else 'absent'}."
                )
            ),
        }

    if requested == "anthropic":
        # The claude route is ready only when (a) a ``claude``/``shannon`` adapter
        # is registered AND (b) Claude is usable here: ``claude`` and ``bun`` on
        # PATH (the shannon launcher's runtime deps). Never green-light off an
        # Anthropic/OpenRouter key alone.
        registered = _adapter_registered("claude") or _adapter_registered("shannon")
        if not registered:
            return {
                "ready": False,
                "backend": backend,
                "route": "anthropic",
                "model": _default_model_for_route("anthropic", model),
                "shannon_adapter_registered": False,
                "reason": (
                    "claude/shannon adapter not wired yet (no Claude/Shannon adapter "
                    "registered in the arnold dispatcher)."
                ),
            }
        have_claude = _claude_cli_present()
        have_bun = _bun_present()
        usable = have_claude and have_bun
        return {
            "ready": usable,
            "backend": backend,
            "route": "anthropic",
            "model": _default_model_for_route("anthropic", model),
            "shannon_adapter_registered": True,
            "claude_cli_present": have_claude,
            "bun_present": have_bun,
            "reason": (
                "claude/shannon adapter registered and Claude is usable (claude + "
                "bun on PATH)."
                if usable
                else (
                    "claude/shannon adapter registered but Claude is not usable: "
                    f"claude CLI {'on PATH' if have_claude else 'not on PATH'}, "
                    f"bun {'on PATH' if have_bun else 'not on PATH'}."
                )
            ),
        }

    # Bare/legacy ``arnold`` (or anything else) with no OpenRouter key: fall through
    # to the best available registered+ready backend (prefer OpenRouter). For
    # ``auto`` with no OpenRouter key, that is whatever else is wired; today only
    # hermes is guaranteed, so report not-ready honestly.
    if requested in {"", "auto", "arnold"}:
        if _adapter_registered("hermes") and _resolve_openrouter_key():
            key = _resolve_openrouter_key()
            return {
                "ready": True,
                "backend": backend,
                "route": "openrouter",
                "model": _default_model_for_route("openrouter", model),
                "base_url": _OPENROUTER_BASE_URL,
                "openrouter_key_present": bool(key),
                "reason": "OpenRouter key resolved; ready to run agent-edit turns.",
            }
    return {
        "ready": False,
        "backend": backend,
        "route": (
            "unknown"
            if requested and _normalize_route(requested) == "unknown"
            else requested or "arnold"
        ),
        "model": _default_model_for_route(_normalize_route(route), model),
        "reason": (
            "No agent adapter is wired for this route yet; only the openrouter "
            "route reaches a registered backend."
        ),
    }


def get_agent_status(*, route: str, model: str | None = None) -> dict[str, Any]:
    """Compatibility wrapper around readiness().

    Prefer readiness(); this legacy shape remains for callers that still expect
    status-like fields.
    """
    payload = readiness(route=route, model=model)
    ready = bool(payload.get("ready"))
    return {
        **payload,
        "ok": ready,
        "detail": str(payload.get("reason") or ""),
        "readiness": "ready" if ready else "unavailable",
    }




def run_model_turn(
    *,
    task: str,
    messages: Sequence[Mapping[str, Any]] | None = None,
    route: str,
    model: str | None = None,
    effort: str | None = None,
    response_contract: str = "json",
    profiling_context: Mapping[str, Any] | None = None,
) -> dict[str, Any]:
    """Run a generic model turn through the Arnold dispatch seam.

    Unlike ``run_agent_turn`` (which hardcodes ``response_contract="python"``
    and the python/message contract) or ``run_agent_turn_batch`` (which
    hardcodes ``response_contract="batch_repl"``), this entry point accepts
    an arbitrary *response_contract* so the executor can request ``"json"``
    or ``"text"`` responses.

    Returns the worker result dict directly.  For ``"json"`` contracts the
    dict contains ``{"content": <raw_text>, "json": <parsed_dict>}``; for
    ``"text"`` it contains ``{"content": <raw_text>}``.
    """
    agent_id = _agent_id_for_route(route)
    system_msg, user_msg = _split_messages(messages)
    if user_msg is None:
        user_msg = f"User request:\n{task}"
    effective_profile = {
        "model_turn_id": (
            str(profiling_context.get("model_turn_id"))
            if isinstance(profiling_context, Mapping) and profiling_context.get("model_turn_id")
            else new_profile_id("model")
        ),
        "route": route,
        "model": model,
        "response_contract": response_contract,
        **(dict(profiling_context or {})),
    }

    with profiler_span(
        LOGGER,
        "runtime.run_model_turn",
        model_turn_id=effective_profile.get("model_turn_id"),
        agent_id=agent_id,
        route=route,
        model=model,
        response_contract=response_contract,
        task_preview=short_text(task),
    ) as span:
        if agent_id == "hermes" and not _hermes_credential_for(route, model):
            raise PermissionError(
                "OpenRouter route selected but no OPENROUTER_API_KEY is available "
                "(checked environment and ~/.hermes/.env). Submit a key via the "
                "VibeComfy panel or export OPENROUTER_API_KEY."
            )

        agent_kwargs = _build_agent_kwargs(agent_id, route=route, model=model)
        result = _run_worker(
            agent_kwargs,
            system_msg,
            user_msg,
            response_contract=response_contract,
            agent_id=agent_id,
            model=_runtime_model_for_route(route, model),
            requested_model=model,
            effort=effort,
            profiling_context=effective_profile,
        )
        if "error" in result:
            _raise_worker_error(result)

        span.update(
            result_keys=sorted(result.keys()),
            worker_profile=result.get("_profiling") if isinstance(result.get("_profiling"), dict) else None,
        )
        return result

__all__ = [
    "begin_deepseek_usage_capture", "snapshot_deepseek_usage_capture",
    "end_deepseek_usage_capture", "begin_model_attempt_capture",
    "snapshot_model_attempt_capture", "end_model_attempt_capture",
    "record_model_attempts", "replace_last_model_attempt", "replace_last_model_attempts",
    "run_agent_turn", "run_agent_turn_delta", "run_agent_turn_batch",
    "run_model_turn", "readiness", "get_agent_status",
]
