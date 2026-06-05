"""Isolated subprocess worker that runs one megaplan ``AIAgent`` turn.

Why a subprocess? ``megaplan.agent.run_agent`` uses bare top-level imports
(``from utils import ...``, ``from model_tools import ...``). When loaded inside
the ComfyUI process those names collide with ComfyUI's own cached ``utils``
module (``sys.modules['utils']``), raising ImportError. Running in a fresh
process where ComfyUI is never imported makes those bare imports resolve to
megaplan's own modules, and also isolates the agent's HTTP/asyncio state from
ComfyUI's aiohttp event loop.

Protocol:
    python megaplan_worker.py <request.json> <result.json>

``request.json`` -> {"agent_kwargs": {...}, "system_message": str|null,
                     "user_message": str, "response_contract": "python"|"delta"|"batch_repl"}
``result.json``  <- {"python": str, "message": str} or {"delta": list, "message": str} on success
                    {"content": str} for batch_repl responses
                    {"error": str, "error_type": str} on failure

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


def main() -> int:
    request_path, result_path = sys.argv[1], sys.argv[2]
    with open(request_path, encoding="utf-8") as fh:
        request = json.load(fh)

    try:
        # Put megaplan's agent dir at the front of sys.path so its bare
        # top-level imports (utils, model_tools, toolsets, ...) resolve to
        # megaplan's modules rather than anything else on the path.
        import megaplan.agent as _agent_pkg

        agent_dir = os.path.dirname(_agent_pkg.__file__)
        if agent_dir not in sys.path:
            sys.path.insert(0, agent_dir)

        from megaplan.agent.run_agent import AIAgent

        agent = AIAgent(**request["agent_kwargs"])
        result = agent.run_conversation(
            user_message=request["user_message"],
            system_message=request.get("system_message"),
        )
        text = result.get("final_response") if isinstance(result, dict) else str(result)
        response_contract = request.get("response_contract") or "python"
        if response_contract == "batch_repl":
            if not isinstance(text, str) or not text.strip():
                raise ValueError("Agent returned an empty batch_repl response.")
            out = {"content": text}
        else:
            payload = _extract_json_object(text or "")
            message = payload.get("message")
            if not isinstance(message, str):
                raise ValueError("Agent JSON must include a string `message` field.")
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

    with open(result_path, "w", encoding="utf-8") as fh:
        json.dump(out, fh)
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
