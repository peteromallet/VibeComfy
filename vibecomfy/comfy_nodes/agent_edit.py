from __future__ import annotations

import dataclasses
import json
import os
import re
import uuid
from pathlib import Path
from typing import Any, Callable


DeepSeekClient = Callable[[list[dict[str, str]]], dict[str, str]]

_DEFAULT_MODEL = "deepseek-chat"
_SESSION_ROOT = Path("out/editor_sessions")


def _safe_session_id(value: str | None = None) -> str:
    if not value:
        return uuid.uuid4().hex
    safe = re.sub(r"[^A-Za-z0-9_.-]", "_", value)
    return safe[:80] or uuid.uuid4().hex


def _extract_json_object(text: str) -> dict[str, Any]:
    """Parse a model response that should be JSON, tolerating fenced blocks."""
    stripped = text.strip()
    if stripped.startswith("```"):
        match = re.search(r"```(?:json)?\s*(.*?)```", stripped, re.DOTALL)
        if match:
            stripped = match.group(1).strip()
    try:
        parsed = json.loads(stripped)
    except json.JSONDecodeError as exc:
        raise ValueError(
            "DeepSeek response was not valid JSON with keys `python` and `message`."
        ) from exc
    if not isinstance(parsed, dict):
        raise ValueError("DeepSeek response must be a JSON object.")
    return parsed


def _deepseek_api_key() -> str | None:
    key = os.getenv("DEEPSEEK_API_KEY")
    if key:
        return key
    env_path = Path(os.getenv("HERMES_HOME", Path.home() / ".hermes")) / ".env"
    try:
        lines = env_path.read_text(encoding="utf-8").splitlines()
    except OSError:
        return None
    for line in lines:
        stripped = line.strip()
        if not stripped or stripped.startswith("#") or "=" not in stripped:
            continue
        name, value = stripped.split("=", 1)
        if name.strip() == "DEEPSEEK_API_KEY":
            return value.strip().strip("\"'")
    return None


def _default_deepseek_client(messages: list[dict[str, str]]) -> dict[str, str]:
    """Call DeepSeek's OpenAI-compatible chat completions API."""
    api_key = _deepseek_api_key()
    if not api_key:
        raise RuntimeError(
            "DEEPSEEK_API_KEY is required for VibeComfy agent edits "
            "(env var or ~/.hermes/.env)."
        )

    import httpx

    response = httpx.post(
        os.getenv("DEEPSEEK_BASE_URL", "https://api.deepseek.com/chat/completions"),
        headers={
            "Authorization": f"Bearer {api_key}",
            "Content-Type": "application/json",
        },
        json={
            "model": os.getenv("VIBECOMFY_DEEPSEEK_MODEL", _DEFAULT_MODEL),
            "messages": messages,
            "temperature": 0.2,
            "response_format": {"type": "json_object"},
        },
        timeout=float(os.getenv("VIBECOMFY_DEEPSEEK_TIMEOUT", "120")),
    )
    response.raise_for_status()
    payload = response.json()
    content = payload["choices"][0]["message"]["content"]
    parsed = _extract_json_object(content)
    python = parsed.get("python")
    message = parsed.get("message")
    if not isinstance(python, str) or not isinstance(message, str):
        raise ValueError("DeepSeek JSON must include string keys `python` and `message`.")
    return {"python": python, "message": message}


def _build_messages(*, task: str, python_source: str) -> list[dict[str, str]]:
    system = (
        "You edit VibeComfy Python scratchpads for a ComfyUI canvas.\n"
        "Return only JSON with keys `python` and `message`.\n"
        "`python` must be the complete replacement file. Preserve imports, build(), "
        "metadata, node ids, and layout-related identity unless the user request "
        "requires a graph edit. Prefer simple VibeWorkflow/template API changes "
        "such as set_prompt, set_seed, set_steps, node/add_node/connect/replace_edge. "
        "Do not download models, run ComfyUI, use network, or include markdown fences.\n"
        "`message` should be a concise explanation for the user."
    )
    user = (
        f"User request:\n{task}\n\n"
        "Current scratchpad Python:\n"
        "```python\n"
        f"{python_source}\n"
        "```"
    )
    return [{"role": "system", "content": system}, {"role": "user", "content": user}]


def handle_agent_edit(
    payload: dict[str, Any],
    *,
    schema_provider: Any = None,
    deepseek_client: DeepSeekClient | None = None,
    session_root: Path | None = None,
) -> dict[str, Any]:
    """Convert current UI JSON to Python, ask DeepSeek to edit it, emit UI JSON."""
    from vibecomfy.ingest.normalize import convert_to_vibe_format
    from vibecomfy.porting.convert import port_convert_and_write, port_convert_workflow
    from vibecomfy.porting.layout import evaluate_felt_delta
    from vibecomfy.porting.layout_store import store_from_ui_json, write_store
    from vibecomfy.porting.ui_emitter import emit_ui_json
    from vibecomfy.schema import get_schema_provider
    from vibecomfy.security.agent_generated_loader import (
        load_agent_generated_scratchpad,
    )

    task = payload.get("task")
    graph = payload.get("graph")
    if not isinstance(task, str) or not task.strip():
        raise ValueError("`task` is required.")
    if not isinstance(graph, dict):
        raise ValueError("`graph` must be a ComfyUI UI JSON object.")

    if schema_provider is None:
        schema_provider = get_schema_provider("local")
    client = deepseek_client or _default_deepseek_client
    root = session_root or _SESSION_ROOT
    session_id = _safe_session_id(payload.get("session_id"))
    session_dir = root / session_id
    session_dir.mkdir(parents=True, exist_ok=True)

    original_ui_path = session_dir / "original.ui.json"
    current_py_path = session_dir / "current.py"
    candidate_ui_path = session_dir / "candidate.ui.json"
    messages_path = session_dir / "messages.jsonl"

    original_ui_path.write_text(json.dumps(graph, indent=2, sort_keys=True), encoding="utf-8")
    wf = convert_to_vibe_format(graph, schema_provider=schema_provider)
    conversion = port_convert_workflow(
        wf,
        source_path=str(original_ui_path),
        schema_provider=schema_provider,
        raw_workflow=graph,
    )
    port_convert_and_write(conversion, current_py_path)
    python_before = current_py_path.read_text(encoding="utf-8")

    messages = _build_messages(task=task, python_source=python_before)
    model_result = client(messages)
    python_after = model_result["python"]
    user_message = model_result["message"]
    current_py_path.write_text(python_after, encoding="utf-8")

    edited_wf = load_agent_generated_scratchpad(current_py_path)
    recovery_report: list[dict[str, Any]] = []
    change_report_out: list[Any] = []
    prior_store = store_from_ui_json(graph)
    ui_payload = emit_ui_json(
        edited_wf,
        schema_provider=schema_provider,
        prior_store=prior_store,
        recovery_report=recovery_report,
        change_report_out=change_report_out,
        guard_original_ui=graph,
    )
    candidate_ui_path.write_text(
        json.dumps(ui_payload, indent=2, sort_keys=True),
        encoding="utf-8",
    )
    write_store(current_py_path, store_from_ui_json(ui_payload))

    reroute_uids = frozenset(
        (node.uid or node_id)
        for node_id, node in edited_wf.nodes.items()
        if node.class_type == "Reroute"
    )
    felt_report = (
        evaluate_felt_delta(
            prior_store,
            ui_payload,
            change_report_out[0],
            reroute_uids=reroute_uids,
        )
        if change_report_out
        else None
    )
    report = {
        "change": dataclasses.asdict(change_report_out[0]) if change_report_out else {},
        "recovery": recovery_report,
        "felt": dataclasses.asdict(felt_report) if felt_report is not None else {},
    }
    messages_path.open("a", encoding="utf-8").write(
        json.dumps({"task": task, "message": user_message}, sort_keys=True) + "\n"
    )
    return {
        "graph": ui_payload,
        "message": user_message,
        "report": report,
        "session_id": session_id,
        "artifacts": {
            "original_ui": str(original_ui_path),
            "python": str(current_py_path),
            "candidate_ui": str(candidate_ui_path),
            "messages": str(messages_path),
        },
        "version": 1,
    }
