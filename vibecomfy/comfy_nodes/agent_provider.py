from __future__ import annotations

import importlib
import json
import os
import re
from dataclasses import dataclass
from pathlib import Path
from typing import Any, Callable, Mapping

from .agent_audit import redact_closed_set


DEFAULT_ROUTE = "arnold"
DEFAULT_MODEL = "agent-edit"
DEFAULT_HERMES_ENV_PATH = Path("~/.hermes/.env")


class ProviderError(RuntimeError):
    pass


class AuthError(ProviderError):
    def __init__(self, message: str = "provider authentication failed") -> None:
        super().__init__(message)
        self.response = type("Response", (), {"status_code": 401})()


class MalformedModelJSON(ProviderError, ValueError):
    pass


class MissingRequiredField(ProviderError, ValueError):
    pass


@dataclass(frozen=True)
class AgentTurnResult:
    python: str
    message: str
    route: str
    model: str | None = None
    audit_metadata: Mapping[str, Any] | None = None

    def to_dict(self) -> dict[str, Any]:
        return {
            "python": self.python,
            "message": self.message,
            "route": self.route,
            "model": self.model,
            "audit_metadata": dict(self.audit_metadata or {}),
        }


def _extract_json_object(text: str) -> dict[str, Any]:
    stripped = text.strip()
    if stripped.startswith("```"):
        match = re.search(r"```(?:json)?\s*(.*?)```", stripped, re.DOTALL)
        if match:
            stripped = match.group(1).strip()
    try:
        parsed = json.loads(stripped)
    except json.JSONDecodeError as exc:
        raise MalformedModelJSON(
            "Agent response was not valid JSON with keys `python` and `message`."
        ) from exc
    if not isinstance(parsed, dict):
        raise MalformedModelJSON("Agent response must be a JSON object.")
    return parsed


def build_messages(*, task: str, python_source: str) -> list[dict[str, str]]:
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


def _credential_presence() -> dict[str, bool]:
    return {
        "arnold_api_key": bool(os.getenv("ARNOLD_API_KEY")),
        "hermes_api_key": bool(os.getenv("HERMES_API_KEY")),
        "deepseek_api_key": bool(os.getenv("DEEPSEEK_API_KEY")),
    }


def _non_secret_mapping(value: Mapping[str, Any]) -> dict[str, Any]:
    redacted = redact_closed_set(dict(value)).value
    return redacted if isinstance(redacted, dict) else {}


def _load_arnold_runtime() -> Any:
    module_name = os.getenv("VIBECOMFY_ARNOLD_RUNTIME_MODULE")
    candidates = [module_name] if module_name else [
        "arnold.hermes",
        "hermes_agent",
        "arnold",
    ]
    errors: list[str] = []
    for candidate in candidates:
        if not candidate:
            continue
        try:
            return importlib.import_module(candidate)
        except ImportError as exc:
            errors.append(f"{candidate}: {exc}")
    raise ProviderError(
        "Arnold/Hermes runtime is unavailable. Install/configure Arnold or set "
        "VIBECOMFY_ARNOLD_RUNTIME_MODULE. Import attempts: " + "; ".join(errors)
    )


def _normalize_agent_response(
    response: Any,
    *,
    route: str,
    model: str | None,
    audit_metadata: Mapping[str, Any] | None = None,
) -> AgentTurnResult:
    if isinstance(response, AgentTurnResult):
        return response
    if isinstance(response, str):
        payload = _extract_json_object(response)
    elif isinstance(response, Mapping):
        payload = dict(response)
        content = payload.get("content")
        if isinstance(content, str) and "python" not in payload:
            payload = _extract_json_object(content)
    else:
        raise MalformedModelJSON("Agent response must be a JSON string or object.")

    python = payload.get("python")
    message = payload.get("message")
    if not isinstance(python, str):
        raise MissingRequiredField("Agent JSON must include string key `python`.")
    if not isinstance(message, str):
        raise MissingRequiredField("Agent JSON must include string key `message`.")
    return AgentTurnResult(
        python=python,
        message=message,
        route=route,
        model=model,
        audit_metadata=audit_metadata or {},
    )


def _call_runtime(runtime: Any, *, task: str, python_source: str, route: str, model: str | None) -> Any:
    messages = build_messages(task=task, python_source=python_source)
    if hasattr(runtime, "run_agent_turn"):
        return runtime.run_agent_turn(
            task=task,
            python_source=python_source,
            route=route,
            model=model,
            messages=messages,
        )
    if hasattr(runtime, "run"):
        return runtime.run(
            task=task,
            python_source=python_source,
            route=route,
            model=model,
            messages=messages,
        )
    raise ProviderError("Arnold/Hermes runtime does not expose run_agent_turn or run.")


def run_agent_turn(
    task: str,
    python_source: str,
    *,
    route: str | None = None,
    model: str | None = None,
) -> AgentTurnResult:
    selected_route = route or DEFAULT_ROUTE
    selected_model = model or os.getenv("VIBECOMFY_AGENT_MODEL", DEFAULT_MODEL)
    runtime = _load_arnold_runtime()
    try:
        response = _call_runtime(
            runtime,
            task=task,
            python_source=python_source,
            route=selected_route,
            model=selected_model,
        )
    except PermissionError as exc:
        raise AuthError(str(exc)) from exc
    except TimeoutError:
        raise
    except (ProviderError, MalformedModelJSON, MissingRequiredField):
        raise
    except Exception as exc:
        raise ProviderError(str(exc)) from exc
    return _normalize_agent_response(
        response,
        route=selected_route,
        model=selected_model,
        audit_metadata={
            "provider": "arnold",
            "legacy_deepseek_fallback_enabled": False,
            "credential_presence": _credential_presence(),
        },
    )


def get_agent_status(*, route: str | None = None, model: str | None = None) -> dict[str, Any]:
    selected_route = route or DEFAULT_ROUTE
    selected_model = model or os.getenv("VIBECOMFY_AGENT_MODEL", DEFAULT_MODEL)
    try:
        runtime = _load_arnold_runtime()
    except ProviderError as exc:
        return {
            "ok": False,
            "route": selected_route,
            "model": selected_model,
            "provider": "arnold",
            "provider_available": False,
            "error": str(exc),
            "credential_presence": _credential_presence(),
            "legacy_deepseek_fallback_enabled": False,
        }
    status_fn: Callable[..., Any] | None = getattr(runtime, "get_agent_status", None)
    status = status_fn(route=selected_route, model=selected_model) if status_fn else {}
    if not isinstance(status, Mapping):
        status = {}
    runtime_status = _non_secret_mapping(status)
    return {
        **runtime_status,
        "ok": bool(runtime_status.get("ok", True)),
        "route": selected_route,
        "model": selected_model,
        "provider": "arnold",
        "provider_available": True,
        "credential_presence": _credential_presence(),
        "legacy_deepseek_fallback_enabled": False,
    }


def _hermes_env_path(path: Path | None = None) -> Path:
    return (path or DEFAULT_HERMES_ENV_PATH).expanduser()


def save_deepseek_api_key(api_key: str, *, env_path: Path | None = None) -> dict[str, Any]:
    if not isinstance(api_key, str) or not api_key.strip():
        raise ValueError("DeepSeek API key must be a non-empty string.")
    target = _hermes_env_path(env_path)
    target.parent.mkdir(parents=True, exist_ok=True)
    lines: list[str] = []
    try:
        lines = target.read_text(encoding="utf-8").splitlines()
    except FileNotFoundError:
        lines = []
    replaced = False
    rendered: list[str] = []
    for line in lines:
        if line.startswith("DEEPSEEK_API_KEY="):
            rendered.append(f"DEEPSEEK_API_KEY={api_key.strip()}")
            replaced = True
        else:
            rendered.append(line)
    if not replaced:
        rendered.append(f"DEEPSEEK_API_KEY={api_key.strip()}")
    tmp = target.with_name(f".{target.name}.{os.getpid()}.tmp")
    tmp.write_text("\n".join(rendered).rstrip("\n") + "\n", encoding="utf-8")
    try:
        os.chmod(tmp, 0o600)
    except OSError:
        pass
    tmp.replace(target)
    return {
        "ok": True,
        "stored": True,
        "provider": "deepseek",
        "key_name": "DEEPSEEK_API_KEY",
        "path": str(target),
    }


def handle_credential_submission(
    payload: Mapping[str, Any],
    *,
    env_path: Path | None = None,
) -> dict[str, Any]:
    provider = str(payload.get("provider") or payload.get("route") or "").lower()
    deepseek_key = payload.get("deepseek_api_key")
    api_key = payload.get("api_key")
    if isinstance(deepseek_key, str):
        return save_deepseek_api_key(deepseek_key, env_path=env_path)
    if provider == "deepseek" and isinstance(api_key, str):
        return save_deepseek_api_key(api_key, env_path=env_path)
    if provider in {"claude", "codex"} or "claude_api_key" in payload or "codex_api_key" in payload:
        return {
            "ok": True,
            "stored": False,
            "provider": provider or "unsupported",
            "ignored": True,
            "reason": "Claude/Codex credentials are not stored by VibeComfy S1.",
        }
    return {
        "ok": False,
        "stored": False,
        "provider": provider or "unknown",
        "ignored": True,
        "reason": "No supported S1 credential was submitted.",
    }


__all__ = [
    "AgentTurnResult",
    "AuthError",
    "MalformedModelJSON",
    "MissingRequiredField",
    "ProviderError",
    "_load_arnold_runtime",
    "build_messages",
    "get_agent_status",
    "handle_credential_submission",
    "run_agent_turn",
    "save_deepseek_api_key",
]
