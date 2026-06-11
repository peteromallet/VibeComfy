"""Megaplan/Arnold runtime adapter for the VibeComfy agent-edit loop.

VibeComfy's ``agent_provider._load_arnold_runtime`` discovers a runtime module
that exposes ``run_agent_turn(...)`` and (optionally) ``get_agent_status(...)``.
The shipped arnold harness (``pip install`` of
https://github.com/peteromallet/arnold, importable as the ``arnold`` package;
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
* ``deepseek``  -> DeepSeek direct (``https://api.deepseek.com``), key resolved
  from ``DEEPSEEK_API_KEY`` or ``~/.hermes/.env`` (where the browser
  credential route writes it). This is the canonical browser-key route.
* ``arnold`` (also ``auto`` / ``anthropic`` / ``openai-codex`` after VibeComfy
  normalises them) -> AIAgent's own provider resolution (Claude via OpenRouter
  or local OAuth). Honest about availability: status reports ``ok`` only when a
  usable credential resolves.

Everything heavy (provider routing, retries, OAuth resolution) is handled by the
real ``AIAgent`` backend; this file is intentionally thin.
"""

from __future__ import annotations

import json
import os
import subprocess
import sys
import tempfile
from pathlib import Path
from typing import Any, Mapping, Sequence

# How long to wait for a single agent turn (subprocess) before giving up.
_TURN_TIMEOUT_SECONDS = float(os.getenv("VIBECOMFY_AGENT_TURN_TIMEOUT", "180"))
_WORKER_PATH = str(Path(__file__).with_name("worker.py"))

# DeepSeek direct endpoint defaults (OpenAI-compatible chat-completions).
# Use deepseek-v4-pro: the advanced, reasoning-capable variant. The legacy
# `deepseek-chat` alias now maps to deepseek-v4-flash in NON-thinking mode — a
# non-reasoning model that cannot plan multi-step structural graph edits and
# spirals on read-only search() calls without ever committing an edit.
_DEEPSEEK_MODEL = os.getenv("VIBECOMFY_DEEPSEEK_MODEL", "deepseek-v4-pro")
_DEEPSEEK_BASE_URL = os.getenv("VIBECOMFY_DEEPSEEK_BASE_URL", "https://api.deepseek.com/v1")
# v4-pro is a THINKING model: reasoning_tokens are billed against max_tokens.
# With no cap (the AIAgent default), a hard edit turn's reasoning exhausts the
# budget before any `content` is emitted — the response comes back empty, with
# no ```batch fence, and the turn fails as MalformedModelJSON. Set the model's
# true output ceiling so reasoning + the (small) batch block both fit. The
# DeepSeek API reports the valid range for deepseek-v4-pro as [1, 393216]; this
# is only a ceiling — billing is on tokens actually generated, not the cap.
_DEEPSEEK_MAX_TOKENS = int(os.getenv("VIBECOMFY_DEEPSEEK_MAX_TOKENS", "393216"))

# Arnold/Hermes (Claude etc.) default model when a non-DeepSeek route is used.
_ARNOLD_MODEL = os.getenv("VIBECOMFY_ARNOLD_MODEL", "anthropic/claude-opus-4.6")
_ARNOLD_BASE_URL = os.getenv("VIBECOMFY_ARNOLD_BASE_URL") or None

_HERMES_ENV_PATH = Path("~/.hermes/.env").expanduser()


def _load_env_file_into_environ(path: Path = _HERMES_ENV_PATH) -> None:
    """Best-effort: hydrate os.environ from ~/.hermes/.env without overwriting.

    The browser credential route writes ``DEEPSEEK_API_KEY=...`` here, so a
    ComfyUI process started without the key in its environment still picks it up.
    """
    try:
        text = path.read_text(encoding="utf-8")
    except (FileNotFoundError, OSError):
        return
    for line in text.splitlines():
        line = line.strip()
        if not line or line.startswith("#") or "=" not in line:
            continue
        key, _, value = line.partition("=")
        key = key.strip()
        value = value.strip().strip('"').strip("'")
        if key and key not in os.environ:
            os.environ[key] = value


# Hydrate on import so credential presence + provider calls see the stored key.
_load_env_file_into_environ()


def _resolve_deepseek_key() -> str | None:
    # Re-read the env file each call so a freshly browser-submitted key is seen
    # without restarting the server.
    if not os.getenv("DEEPSEEK_API_KEY"):
        _load_env_file_into_environ()
    return os.getenv("DEEPSEEK_API_KEY")


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


def _normalize_route(route: str | None) -> str:
    normalized = (route or "arnold").strip().lower()
    if normalized in {"auto", "anthropic", "openai-codex"}:
        return "arnold"
    return normalized or "arnold"


# Panel route -> arnold dispatch agent id. The worker registers/dispatches under
# this id. Only ``hermes`` (DeepSeekAdapter) is wired in the default dispatcher
# today; ``codex`` / ``claude`` will raise LookupError until adapters are
# registered (Step B's readiness gate keeps the panel from reaching them).
_ROUTE_TO_AGENT_ID = {
    "deepseek": "hermes",
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
    return _ROUTE_TO_AGENT_ID.get(requested, "hermes")


def _default_model_for_route(route: str, model: str | None) -> str:
    if model:
        return model
    return _DEEPSEEK_MODEL if route == "deepseek" else _ARNOLD_MODEL


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


def _build_agent_kwargs(agent_id: str) -> dict[str, Any]:
    """AIAgent constructor kwargs for a single, tool-free completion.

    Keyed off the resolved *dispatch agent id* (not the panel route) so that the
    DeepSeek configuration follows wherever ``hermes`` is selected — including
    ``auto`` once it resolves to ``hermes``. For ``codex`` / ``claude`` the worker
    dispatches through the default dispatcher and ignores ``agent_kwargs``, so we
    pass only the tool-free single-shot flags and never the legacy ``_ARNOLD_MODEL``
    OpenRouter hardcode (no live route uses it anymore).
    """
    common: dict[str, Any] = dict(
        max_iterations=1,
        enabled_toolsets=[],          # no tools: one-shot completion
        save_trajectories=False,      # no trajectory files on disk
        skip_context_files=True,      # don't load SOUL.md / AGENTS.md
        skip_memory=True,             # don't load/write the memory store
        quiet_mode=True,
    )
    if agent_id == "hermes":
        return dict(
            model=_DEEPSEEK_MODEL,
            api_key=_resolve_deepseek_key(),
            base_url=_DEEPSEEK_BASE_URL,
            provider="deepseek",
            max_tokens=_DEEPSEEK_MAX_TOKENS,
            **common,
        )
    # codex / claude -> default dispatcher resolves everything; kwargs unused.
    return dict(**common)


def _run_worker(
    agent_kwargs: dict[str, Any],
    system_msg: str | None,
    user_msg: str,
    *,
    response_contract: str = "python",
    agent_id: str = "hermes",
) -> dict[str, Any]:
    """Run one AIAgent turn in an isolated subprocess; return its result dict.

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
                    "agent_kwargs": agent_kwargs,
                    "system_message": system_msg,
                    "user_message": user_msg,
                    "response_contract": response_contract,
                },
                fh,
            )
        env = dict(os.environ)
        # Ensure the child can see the DeepSeek key even if only ~/.hermes/.env had it.
        key = _resolve_deepseek_key()
        if key:
            env["DEEPSEEK_API_KEY"] = key
        # Don't leak ComfyUI's cwd/path into the child (it is what causes the
        # `utils` collision); run from a neutral directory.
        proc = subprocess.run(
            [sys.executable, _WORKER_PATH, req_path, res_path],
            cwd=tmp,
            env=env,
            capture_output=True,
            text=True,
            timeout=_TURN_TIMEOUT_SECONDS,
        )
        try:
            with open(res_path, encoding="utf-8") as fh:
                return json.load(fh)
        except (FileNotFoundError, json.JSONDecodeError) as exc:
            tail = (proc.stderr or proc.stdout or "")[-800:]
            raise RuntimeError(
                f"Agent worker produced no result (exit {proc.returncode}). {exc}. "
                f"Worker output tail:\n{tail}"
            ) from exc


def run_agent_turn(
    *,
    task: str,
    python_source: str,
    route: str,
    model: str | None = None,
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

    if agent_id == "hermes" and not _resolve_deepseek_key():
        raise PermissionError(
            "DeepSeek route selected but no DEEPSEEK_API_KEY is available "
            "(checked environment and ~/.hermes/.env). Submit a key via the "
            "VibeComfy panel or export DEEPSEEK_API_KEY."
        )

    agent_kwargs = _build_agent_kwargs(agent_id)
    result = _run_worker(
        agent_kwargs,
        system_msg,
        user_msg,
        response_contract="python",
        agent_id=agent_id,
    )
    if "error" in result:
        # Surface auth-style failures as PermissionError so VibeComfy classifies
        # them as auth errors; everything else stays a provider error.
        err = result.get("error", "agent worker failed")
        if result.get("error_type") in {"AuthError", "AuthenticationError", "PermissionError"}:
            raise PermissionError(err)
        if _is_runtime_unavailable(result):
            raise ImportError(err)
        raise RuntimeError(err)
    return {"python": result["python"], "message": result["message"]}


def run_agent_turn_delta(
    *,
    task: str,
    projection: str,
    op_schema: Mapping[str, Any],
    route: str,
    model: str | None = None,
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

    if agent_id == "hermes" and not _resolve_deepseek_key():
        raise PermissionError(
            "DeepSeek route selected but no DEEPSEEK_API_KEY is available "
            "(checked environment and ~/.hermes/.env). Submit a key via the "
            "VibeComfy panel or export DEEPSEEK_API_KEY."
        )

    agent_kwargs = _build_agent_kwargs(agent_id)
    result = _run_worker(
        agent_kwargs,
        system_msg,
        user_msg,
        response_contract="delta",
        agent_id=agent_id,
    )
    if "error" in result:
        err = result.get("error", "agent worker failed")
        if result.get("error_type") in {"AuthError", "AuthenticationError", "PermissionError"}:
            raise PermissionError(err)
        if _is_runtime_unavailable(result):
            raise ImportError(err)
        raise RuntimeError(err)
    return {"delta": result["delta"], "message": result["message"]}


def run_agent_turn_batch(
    *,
    task: str,
    route: str,
    model: str | None = None,
    messages: Sequence[Mapping[str, Any]] | None = None,
) -> dict[str, Any]:
    """Run one batch-REPL agent-edit turn and return raw model content."""
    agent_id = _agent_id_for_route(route)
    system_msg, user_msg = _split_messages(messages)
    if user_msg is None:
        user_msg = f"User request:\n{task}"

    if agent_id == "hermes" and not _resolve_deepseek_key():
        raise PermissionError(
            "DeepSeek route selected but no DEEPSEEK_API_KEY is available "
            "(checked environment and ~/.hermes/.env). Submit a key via the "
            "VibeComfy panel or export DEEPSEEK_API_KEY."
        )

    agent_kwargs = _build_agent_kwargs(agent_id)
    result = _run_worker(
        agent_kwargs,
        system_msg,
        user_msg,
        response_contract="batch_repl",
        agent_id=agent_id,
    )
    if "error" in result:
        err = result.get("error", "agent worker failed")
        if result.get("error_type") in {"AuthError", "AuthenticationError", "PermissionError"}:
            raise PermissionError(err)
        if _is_runtime_unavailable(result):
            raise ImportError(err)
        if result.get("error_type") in {"JSONDecodeError", "ValueError"}:
            return {"content": ""}
        raise RuntimeError(err)
    return {"content": result["content"]}


def _requested_route(route: str | None) -> str:
    """Canonical panel route name (claude->anthropic, codex->openai-codex)."""
    requested = (route or "").strip().lower()
    if requested == "claude":
        return "anthropic"
    if requested == "codex":
        return "openai-codex"
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

    Only ``deepseek`` reaches a real, registered adapter today
    (``hermes`` -> DeepSeekAdapter). ``openai-codex`` and ``anthropic`` have no
    adapter registered in the default dispatcher yet, so they report
    ``ready: False`` with a clear reason — the panel must tell the truth rather
    than green-light them off an unrelated OpenRouter/Anthropic key.
    """
    backend = "arnold.pipelines.megaplan.agent.run_agent.AIAgent"
    requested = _requested_route(route)

    if requested == "deepseek" or (
        requested in {"", "auto"} and _resolve_deepseek_key()
    ):
        key = _resolve_deepseek_key()
        return {
            "ready": bool(key),
            "backend": backend,
            "route": "deepseek",
            "model": _default_model_for_route("deepseek", model),
            "base_url": _DEEPSEEK_BASE_URL,
            "deepseek_key_present": bool(key),
            "reason": (
                "DeepSeek key resolved; ready to run agent-edit turns."
                if key
                else "No DEEPSEEK_API_KEY in environment or ~/.hermes/.env."
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

    # Bare/legacy ``arnold`` (or anything else) with no DeepSeek key: fall through
    # to the best available registered+ready backend (prefer deepseek). For
    # ``auto`` with no DeepSeek key, that is whatever else is wired; today only
    # hermes is guaranteed, so report not-ready honestly.
    if requested in {"", "auto", "arnold"}:
        if _adapter_registered("hermes") and _resolve_deepseek_key():
            key = _resolve_deepseek_key()
            return {
                "ready": True,
                "backend": backend,
                "route": "deepseek",
                "model": _default_model_for_route("deepseek", model),
                "base_url": _DEEPSEEK_BASE_URL,
                "deepseek_key_present": bool(key),
                "reason": "DeepSeek key resolved; ready to run agent-edit turns.",
            }
    return {
        "ready": False,
        "backend": backend,
        "route": requested or "arnold",
        "model": _default_model_for_route(_normalize_route(route), model),
        "reason": (
            "No agent adapter is wired for this route yet; only the deepseek "
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


__all__ = ["run_agent_turn", "run_agent_turn_delta", "run_agent_turn_batch", "readiness", "get_agent_status"]
