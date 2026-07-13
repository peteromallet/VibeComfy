"""Isolated subprocess worker that runs one agent turn via Arnold dispatch.

The agent harness was renamed from ``megaplan`` to ``arnold``. Per-turn work
now flows through the vendor-agnostic dispatch seam
``arnold.agent.ArnoldDispatcher`` instead of constructing ``AIAgent`` directly.
The default ``arnold.agent.dispatch`` pre-registers only ``"hermes" ->
DeepSeekAdapter`` (a real adapter that lazily imports ``AIAgent`` and runs
``run_conversation``); ``"codex"`` / ``"claude"`` are not registered yet and a
dispatch to them raises ``LookupError`` (the parent's readiness gate keeps the
panel from reaching them).

Why a subprocess? ``DeepSeekAdapter`` lazily imports the ``AIAgent`` backend,
whose modules use bare top-level imports (``from utils import ...``,
``from model_tools import ...``). When loaded inside the ComfyUI process those
names collide with ComfyUI's own cached ``utils`` module
(``sys.modules['utils']``), raising ImportError. Running in a fresh process
where ComfyUI is never imported makes those bare imports resolve to the agent's
own modules, and also isolates the agent's HTTP/asyncio state from ComfyUI's
aiohttp event loop.

Protocol:
    python worker.py <request.json> <result.json>

``request.json`` -> {"agent_id": str, "agent_kwargs": {...},
                     "system_message": str|null, "user_message": str,
                     "response_contract": "python"|"delta"|"batch_repl"|"json"|"text"}
``result.json``  <- {"python": str, "message": str} or {"delta": list, "message": str} on success
                    {"content": str} for batch_repl / json / text responses
                    {"json": dict} additionally for json contract
                    {"error": str, "error_type": str} on failure

``agent_kwargs`` are the AIAgent constructor kwargs the parent resolved for the
route (model, api_key, base_url, provider, max_tokens, the tool-free single-shot
flags, ...). ``DeepSeekAdapter`` builds only a minimal kwargs set itself, so we
inject a factory that merges the parent's kwargs verbatim — this reproduces the
exact AIAgent construction the worker used before the dispatch seam was added.

stdout/stderr may contain agent chatter; the parent only reads ``result.json``.
"""

from __future__ import annotations

import json
import logging
import os
from pathlib import Path
import re
import sys
import time
from typing import Any


def _bootstrap_repo_root() -> None:
    """Make this file runnable by absolute path from a neutral cwd."""
    repo_root = Path(__file__).resolve().parents[3]
    repo_root_str = str(repo_root)
    if repo_root_str not in sys.path:
        sys.path.insert(0, repo_root_str)


_bootstrap_repo_root()

from vibecomfy.agent.deepseek_usage import (
    add_deepseek_usage,
    coerce_deepseek_usage,
    empty_deepseek_usage,
)
from vibecomfy.executor.profiler import profiler_log, profiler_span, short_text, utc_now_iso

LOGGER = logging.getLogger(__name__)


def _extract_json_object(text: str) -> dict:
    stripped = (text or "").strip()
    if stripped.startswith("```"):
        match = re.search(r"```(?:json)?\s*(.*?)```", stripped, re.DOTALL)
        if match:
            stripped = match.group(1).strip()
    try:
        parsed = json.loads(stripped)
    except json.JSONDecodeError:
        # The model often emits the JSON object followed by EXTRA data (a second
        # object, or trailing prose / reasoning), which makes a strict json.loads
        # raise "Extra data" and fail the whole turn. A greedy {.*} regex is worse —
        # on "{obj}{extra}" it captures BOTH and still fails. Decode the FIRST
        # complete object from the first '{' with raw_decode and ignore the rest.
        start = stripped.find("{")
        if start == -1:
            raise
        parsed, _ = json.JSONDecoder().raw_decode(stripped[start:])
    if not isinstance(parsed, dict):
        raise ValueError("Agent response JSON was not an object.")
    return parsed


def _anchor_agent_package_on_syspath() -> None:
    """Put the agent package dir on sys.path so its bare top-level imports
    (``utils``, ``model_tools``, ``toolsets``, ...) resolve to its own modules.

    Best-effort: if the legacy ``arnold.pipelines.megaplan.agent`` package is not
    importable (e.g. a slimmed install), the adapter still drives its own lazy
    import; we just skip the path anchor.
    """
    try:
        import arnold.pipelines.megaplan.agent as _agent_pkg
    except ImportError:
        return
    agent_dir = os.path.dirname(_agent_pkg.__file__)
    if agent_dir and agent_dir not in sys.path:
        sys.path.insert(0, agent_dir)


def _build_request(
    *,
    agent_id: str,
    user_message: str,
    system_message: str | None,
    model: str | None = None,
    effort: str | None = None,
):
    """Construct the tool-free single-shot AgentRequest for a panel turn.

    Tool-free single-shot: empty ``toolsets`` in metadata -> the DeepSeekAdapter
    does not enable any toolset, and the parent kwargs already carry
    ``enabled_toolsets=[]`` / ``max_iterations=1``. No ``output_schema`` /
    ``response_format``: the panel parses its own python/delta/batch fences from
    the raw text, so the adapter returns ``raw_output`` unchanged.
    """
    from arnold.agent import AgentRequest

    return AgentRequest(
        agent=agent_id,
        mode="default",
        model=model,
        resolved_model=model,
        effort=effort,
        prompt=user_message,
        system_prompt=system_message,
        read_only=True,
        metadata={"toolsets": []},
    )


def _dispatch_turn(
    *,
    agent_id: str,
    agent_kwargs: dict,
    user_message: str,
    system_message: str | None,
    model: str | None = None,
    effort: str | None = None,
) -> tuple[str, dict[str, Any]]:
    """Run one agent turn through the Arnold dispatch seam; return raw text.

    * ``hermes`` (DeepSeek): the parent resolved the full DeepSeek kwargs
      (model, api_key, base_url, provider, max_tokens, the tool-free single-shot
      flags). The module-level default ``DeepSeekAdapter()`` reads only from
      ``HERMES_API_KEY``/``OPENAI_API_KEY`` + metadata, so it would NOT carry the
      parent's DeepSeek configuration through. We therefore register a dedicated
      :class:`DeepSeekAdapter` on a local dispatcher whose ``AIAgent`` factory
      merges those kwargs verbatim — reproducing the exact construction the
      worker used before the dispatch seam existed.
    * ``codex`` / ``claude`` (and any other id): dispatch through the *default*
      dispatcher (``arnold.agent.dispatch``). The adapters for those ids are
      registered by their owning components; if none is registered yet,
      ``dispatch`` raises :class:`LookupError`, which the parent maps to the
      runtime-unavailable signal. We never silently route them through DeepSeek.
    """
    _anchor_agent_package_on_syspath()
    request = _build_request(
        agent_id=agent_id,
        user_message=user_message,
        system_message=system_message,
        model=model,
        effort=effort,
    )

    if agent_id == "hermes":
        from arnold.agent import ArnoldDispatcher
        from arnold.agent.adapters.deepseek import DeepSeekAdapter
        from arnold.agent.run_agent import AIAgent
        import arnold.agent.run_agent as run_agent_module

        usage_tracker: dict[str, Any] = {
            "usage": empty_deepseek_usage(),
            "cache_breakout_calls": 0,
        }
        last_result: dict[str, Any] = {}

        def _usage_int(raw: Any, *names: str) -> int | None:
            candidates: list[Any] = [raw]
            if hasattr(raw, "model_extra"):
                candidates.append(getattr(raw, "model_extra"))
            for candidate in candidates:
                if candidate is None:
                    continue
                for name in names:
                    if isinstance(candidate, dict):
                        value = candidate.get(name)
                    else:
                        value = getattr(candidate, name, None)
                    if value is None:
                        continue
                    try:
                        return max(0, int(value))
                    except (TypeError, ValueError):
                        continue
            return None

        def _prompt_tokens_details(raw: Any) -> Any:
            details = getattr(raw, "prompt_tokens_details", None)
            if details is not None:
                return details
            if isinstance(raw, dict):
                return raw.get("prompt_tokens_details")
            model_extra = getattr(raw, "model_extra", None)
            if isinstance(model_extra, dict):
                return model_extra.get("prompt_tokens_details")
            return None

        def _record_usage(raw_usage: Any, canonical_usage: Any) -> None:
            prompt_tokens = _usage_int(raw_usage, "prompt_tokens")
            completion_tokens = _usage_int(raw_usage, "completion_tokens")
            total_tokens = _usage_int(raw_usage, "total_tokens")
            if prompt_tokens is None:
                prompt_tokens = max(0, int(getattr(canonical_usage, "prompt_tokens", 0) or 0))
            if completion_tokens is None:
                completion_tokens = max(0, int(getattr(canonical_usage, "output_tokens", 0) or 0))
            if total_tokens is None:
                total_tokens = prompt_tokens + completion_tokens

            cache_hit_tokens = _usage_int(raw_usage, "prompt_cache_hit_tokens")
            cache_miss_tokens = _usage_int(raw_usage, "prompt_cache_miss_tokens")
            cache_breakout_available = (
                cache_hit_tokens is not None or cache_miss_tokens is not None
            )
            if not cache_breakout_available:
                details = _prompt_tokens_details(raw_usage)
                cached_tokens = _usage_int(details, "cached_tokens")
                if cached_tokens is not None:
                    cache_hit_tokens = cached_tokens
                    cache_miss_tokens = max(0, prompt_tokens - cached_tokens)
                    cache_breakout_available = True
            if cache_breakout_available:
                usage_tracker["cache_breakout_calls"] += 1

            usage_tracker["usage"] = add_deepseek_usage(
                usage_tracker["usage"],
                {
                    "prompt_tokens": prompt_tokens,
                    "completion_tokens": completion_tokens,
                    "total_tokens": total_tokens,
                    "prompt_cache_hit_tokens": cache_hit_tokens or 0,
                    "prompt_cache_miss_tokens": cache_miss_tokens or 0,
                    "n_calls": 1,
                },
            )

        original_normalize_usage = run_agent_module.normalize_usage

        def _tracking_normalize_usage(
            response_usage: Any,
            *,
            provider: str | None = None,
            api_mode: str | None = None,
        ):
            canonical_usage = original_normalize_usage(
                response_usage,
                provider=provider,
                api_mode=api_mode,
            )
            try:
                _record_usage(response_usage, canonical_usage)
            except Exception:
                pass
            return canonical_usage

        class _TrackingAIAgent(AIAgent):
            def run_conversation(self, *args, **kwargs):
                result = super().run_conversation(*args, **kwargs)
                if isinstance(result, dict):
                    last_result.clear()
                    last_result.update(result)
                return result

        def _factory(**adapter_kwargs):
            # Start from the adapter's resolved kwargs (toolsets/session_db_path
            # it derives from the request), then let the PARENT-resolved values
            # win — the parent deliberately resolved the panel's proven DeepSeek
            # config (model=deepseek-v4-pro, provider, base_url, api_key,
            # max_tokens). The adapter's generic default model
            # ("deepseek/deepseek-chat") is NOT a valid DeepSeek API name, so it
            # must never override the parent's model.
            merged = dict(adapter_kwargs)
            for key, value in agent_kwargs.items():
                if value is not None:
                    merged[key] = value
            return _TrackingAIAgent(**merged)

        dispatcher = ArnoldDispatcher()
        dispatcher.register(agent_id, DeepSeekAdapter(agent_factory=_factory))
        run_agent_module.normalize_usage = _tracking_normalize_usage
        try:
            result = dispatcher.dispatch(request)
        finally:
            run_agent_module.normalize_usage = original_normalize_usage

        tracked_usage = coerce_deepseek_usage(usage_tracker["usage"])
        if tracked_usage["n_calls"] <= 0 and last_result:
            tracked_usage = coerce_deepseek_usage(
                {
                    "prompt_tokens": last_result.get("prompt_tokens"),
                    "completion_tokens": last_result.get("completion_tokens"),
                    "total_tokens": last_result.get("total_tokens"),
                    "prompt_cache_hit_tokens": last_result.get("cache_read_tokens"),
                    "prompt_cache_miss_tokens": last_result.get("input_tokens"),
                    "n_calls": last_result.get("api_calls"),
                }
            )
            usage_tracker["cache_breakout_calls"] = tracked_usage["n_calls"]
        return result.raw_output or "", {
            "deepseek_usage": tracked_usage,
            "deepseek_cache_breakout_complete": (
                tracked_usage["n_calls"] > 0
                and usage_tracker["cache_breakout_calls"] >= tracked_usage["n_calls"]
            ),
        }

    # codex / claude / anything else: route through the shared default
    # dispatcher. Raises LookupError if the adapter is not registered.
    from arnold.agent import dispatch as _default_dispatch

    result = _default_dispatch(request)
    return result.raw_output or "", {}


def main() -> int:
    if not logging.getLogger().handlers:
        logging.basicConfig(level=logging.INFO)
    request_path, result_path = sys.argv[1], sys.argv[2]
    with open(request_path, encoding="utf-8") as fh:
        request = json.load(fh)

    profiling_context = (
        request.get("profiling_context")
        if isinstance(request.get("profiling_context"), dict)
        else {}
    )
    profiler_log(
        LOGGER,
        "worker.request",
        profiling_context=profiling_context,
        agent_id=request.get("agent_id") or "hermes",
        response_contract=request.get("response_contract") or "python",
        user_message_preview=short_text(request.get("user_message")),
    )

    worker_started_at = utc_now_iso()
    worker_started_monotonic = time.monotonic()
    try:
        agent_id = request.get("agent_id") or "hermes"
        response_contract = request.get("response_contract") or "python"
        with profiler_span(
            LOGGER,
            "worker.run_turn",
            profiling_context=profiling_context,
            agent_id=agent_id,
            response_contract=response_contract,
        ) as span:
            text, worker_metadata = _dispatch_turn(
                agent_id=agent_id,
                agent_kwargs=request["agent_kwargs"],
                user_message=request["user_message"],
                system_message=request.get("system_message"),
                model=request.get("model"),
                effort=request.get("effort"),
            )
            span.update(raw_text_length=len(text or ""))
            if response_contract == "batch_repl":
                if not isinstance(text, str) or not text.strip():
                    raise ValueError("Agent returned an empty batch_repl response.")
                out = {"content": text}
            elif response_contract == "text":
                if not isinstance(text, str) or not text.strip():
                    raise ValueError("Agent returned an empty text response.")
                out = {"content": text}
            elif response_contract == "json":
                if not isinstance(text, str) or not text.strip():
                    raise ValueError("Agent returned an empty json response.")
                payload = _extract_json_object(text)
                out = {"content": text, "json": payload}
            elif response_contract in ("python", "delta"):
                payload = _extract_json_object(text or "")
                message = payload.get("message")
                if not isinstance(message, str):
                    raise ValueError("Agent JSON must include a string `message` field.")
                if response_contract == "delta":
                    delta = payload.get("delta")
                    if not isinstance(delta, list):
                        raise ValueError("Agent JSON must include a list `delta` field.")
                    out = {"delta": delta, "message": message}
                else:  # python
                    python = payload.get("python")
                    if not isinstance(python, str):
                        raise ValueError("Agent JSON must include a string `python` field.")
                    out = {"python": python, "message": message}
            else:
                raise ValueError(f"Unsupported response_contract {response_contract!r}.")
            if isinstance(worker_metadata, dict):
                out.update(worker_metadata)
    except Exception as exc:  # noqa: BLE001 - report all failures to parent
        out = {"error": str(exc), "error_type": type(exc).__name__}
        # A LookupError means no adapter is registered for the requested agent id
        # (e.g. codex/claude not wired into the default dispatcher yet); an
        # ImportError means the backend's heavy deps are missing. Both are setup
        # faults — flag them so the parent surfaces a non-retryable
        # runtime-unavailable signal rather than a transient provider error.
        if isinstance(exc, (LookupError, ImportError)):
            out["runtime_unavailable"] = True

    out["_profiling"] = {
        **profiling_context,
        "agent_id": request.get("agent_id") or "hermes",
        "response_contract": request.get("response_contract") or "python",
        "started_at": worker_started_at,
        "ended_at": utc_now_iso(),
        "elapsed_ms": max(0, int((time.monotonic() - worker_started_monotonic) * 1000)),
    }

    with open(result_path, "w", encoding="utf-8") as fh:
        json.dump(out, fh)
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
