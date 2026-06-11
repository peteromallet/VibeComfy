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
                     "response_contract": "python"|"delta"|"batch_repl"}
``result.json``  <- {"python": str, "message": str} or {"delta": list, "message": str} on success
                    {"content": str} for batch_repl responses
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
import os
import re
import sys


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


def _build_request(*, agent_id: str, user_message: str, system_message: str | None):
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
) -> str:
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
    )

    if agent_id == "hermes":
        from arnold.agent import ArnoldDispatcher
        from arnold.agent.adapters.deepseek import DeepSeekAdapter
        from arnold.agent.run_agent import AIAgent

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
            return AIAgent(**merged)

        dispatcher = ArnoldDispatcher()
        dispatcher.register(agent_id, DeepSeekAdapter(agent_factory=_factory))
        result = dispatcher.dispatch(request)
        return result.raw_output or ""

    # codex / claude / anything else: route through the shared default
    # dispatcher. Raises LookupError if the adapter is not registered.
    from arnold.agent import dispatch as _default_dispatch

    result = _default_dispatch(request)
    return result.raw_output or ""


def main() -> int:
    request_path, result_path = sys.argv[1], sys.argv[2]
    with open(request_path, encoding="utf-8") as fh:
        request = json.load(fh)

    try:
        agent_id = request.get("agent_id") or "hermes"
        text = _dispatch_turn(
            agent_id=agent_id,
            agent_kwargs=request["agent_kwargs"],
            user_message=request["user_message"],
            system_message=request.get("system_message"),
        )
        response_contract = request.get("response_contract") or "python"
        if response_contract == "batch_repl":
            if not isinstance(text, str) or not text.strip():
                raise ValueError("Agent returned an empty batch_repl response.")
            out = {"content": text}
        else:
            payload = _extract_json_object(text or "")
            message = payload.get("message")
            if not isinstance(message, str):
                message = "Applied the requested edit."
        if response_contract == "delta":
            delta = payload.get("delta")
            if not isinstance(delta, list):
                raise ValueError("Agent JSON must include a list `delta` field.")
            out = {"delta": delta, "message": message}
        elif response_contract == "python":
            python = payload.get("python")
            if not isinstance(python, str):
                raise ValueError("Agent JSON must include a string `python` field.")
            out = {"python": python, "message": message}
        elif response_contract != "batch_repl":
            raise ValueError(f"Unsupported response_contract {response_contract!r}.")
    except Exception as exc:  # noqa: BLE001 - report all failures to parent
        out = {"error": str(exc), "error_type": type(exc).__name__}
        # A LookupError means no adapter is registered for the requested agent id
        # (e.g. codex/claude not wired into the default dispatcher yet); an
        # ImportError means the backend's heavy deps are missing. Both are setup
        # faults — flag them so the parent surfaces a non-retryable
        # runtime-unavailable signal rather than a transient provider error.
        if isinstance(exc, (LookupError, ImportError)):
            out["runtime_unavailable"] = True

    with open(result_path, "w", encoding="utf-8") as fh:
        json.dump(out, fh)
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
