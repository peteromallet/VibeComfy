"""Deterministic Arnold-runtime provider backed by committed editor-session fixtures.

Wire it up by setting the standard discovery env var::

    export VIBECOMFY_ARNOLD_RUNTIME_MODULE="vibecomfy.comfy_nodes.agent.fixture_provider"

This module reads recorded agent-edit turns from
``tests/fixtures/editor_sessions/`` (the repository root is resolved via the
``REPO_ROOT`` environment variable, which is already set by the Playwright
launcher in ``tests/e2e/run.mjs``).  It never touches ``out/editor_sessions/``
and requires no provider API keys — every call is deterministic.

Fixture resolution
------------------
The provider tries to match an incoming *task* string to a known fixture by
consulting ``manifest.json``.  The resolution order is:

1. **``VIBECOMFY_FIXTURE_SCENARIO``** — if set to a session name
   (e.g. ``"smoke_upscale_1"``), that session's first turn is used regardless
   of the incoming task.
2. **Substring match** — the incoming task is substring-matched against the
   ``task_preview`` fields in the manifest.
3. **First-available fallback** — the first fixture in the manifest is used.

When no fixture matches at all (empty manifest or missing directory), a
synthetic ``done()`` batch response is returned so callers receive a
well-formed answer instead of an error.

Contracts
---------
All four entry points accept the same keyword arguments as the existing
``runtime`` adapter so that ``agent_provider`` can call them without
changes.  Every call returns a plain ``dict``; normalization is handled by
``agent_provider``'s existing normalizers.
"""

from __future__ import annotations

import hashlib
import json
import os
from pathlib import Path
from typing import Any, Mapping, Sequence

_FIXTURE_ROOT: Path | None = None
_MANIFEST_CACHE: dict[str, Any] | None = None
_CONTENT_CACHE: dict[str, str] = {}


def _repo_root() -> Path:
    """Resolve the repository root.

    Prefers ``REPO_ROOT`` (set by the Playwright launcher), falling back to
    walking up from this file's location.
    """
    env_root = os.environ.get("REPO_ROOT")
    if env_root:
        return Path(env_root)
    # Fallback: this file lives at vibecomfy/comfy_nodes/fixture_provider.py
    return Path(__file__).resolve().parents[2]


def _fixture_root() -> Path:
    global _FIXTURE_ROOT
    if _FIXTURE_ROOT is None:
        _FIXTURE_ROOT = _repo_root() / "tests" / "fixtures" / "editor_sessions"
    return _FIXTURE_ROOT


def _load_manifest() -> dict[str, Any]:
    global _MANIFEST_CACHE
    if _MANIFEST_CACHE is not None:
        return _MANIFEST_CACHE
    path = _fixture_root() / "manifest.json"
    if path.is_file():
        _MANIFEST_CACHE = json.loads(path.read_text(encoding="utf-8"))
    else:
        _MANIFEST_CACHE = {}
    return _MANIFEST_CACHE


def _compute_key(task: str, messages: Sequence[Mapping[str, Any]]) -> str:
    """Compute a SHA-256 based key from task and messages.

    Matches the deterministic key scheme used when the fixtures were committed.
    """
    payload = task + json.dumps(
        sorted(messages, key=lambda m: json.dumps(m, sort_keys=True)),
        sort_keys=True,
    )
    return hashlib.sha256(payload.encode()).hexdigest()[:16]


def _load_fixture_content(key: str) -> str | None:
    """Load the content string for a fixture key (with caching)."""
    if key in _CONTENT_CACHE:
        return _CONTENT_CACHE[key]
    path = _fixture_root() / key / "fixture.json"
    if not path.is_file():
        return None
    try:
        data = json.loads(path.read_text(encoding="utf-8"))
        content = data.get("content", "")
    except (json.JSONDecodeError, OSError):
        return None
    _CONTENT_CACHE[key] = content
    return content


def _resolve_fixture(task: str, messages: Sequence[Mapping[str, Any]] | None = None) -> str:
    """Resolve a fixture content string for the given task and messages.

    Resolution order:
    1. ``VIBECOMFY_FIXTURE_SCENARIO`` env var (session name).
    2. Hash match against the manifest.
    3. Substring match of task against task_preview entries.
    4. First-available fallback.

    Returns the content string, or a synthetic fallback when nothing matches.
    """
    manifest = _load_manifest()
    if not manifest:
        return _synthetic_response(task)

    # 1 — Forced scenario via env var
    forced_scenario = os.environ.get("VIBECOMFY_FIXTURE_SCENARIO", "").strip()
    if forced_scenario:
        for key, entry in manifest.items():
            if entry.get("session") == forced_scenario:
                content = _load_fixture_content(key)
                if content:
                    return content
        # If the forced scenario doesn't exist, fall through to substring match
        # rather than returning a synthetic response.

    # 2 — Hash match
    if messages:
        key = _compute_key(task, messages)
        if key in manifest:
            content = _load_fixture_content(key)
            if content:
                return content

    # 3 — Substring match on task vs task_preview
    task_lower = task.lower().strip()
    if task_lower:
        for key, entry in manifest.items():
            preview = (entry.get("task_preview") or "").lower().strip()
            if preview and (preview in task_lower or task_lower in preview):
                content = _load_fixture_content(key)
                if content:
                    return content

    # 4 — First-available fallback
    for key in sorted(manifest):
        content = _load_fixture_content(key)
        if content:
            return content

    return _synthetic_response(task)


def _synthetic_response(task: str) -> str:
    """Return a minimal well-formed batch response when no fixture matches."""
    task_preview = task.strip()[:80] if task else "your request"
    return (
        f"I'll process {task_preview}.\n"
        "```batch\n"
        "done()\n"
        "```"
    )


# ── Public entry points ──────────────────────────────────────────────────────


def readiness(*, route: str, model: str | None = None) -> dict[str, Any]:
    """Report that the fixture provider is always ready.

    No credentials or external services are required.
    """
    manifest = _load_manifest()
    fixture_count = len(manifest)
    return {
        "ready": True,
        "backend": "vibecomfy.comfy_nodes.agent.fixture_provider",
        "route": route,
        "model": model or "agent-edit",
        "reason": (
            f"Fixture provider is always ready ({fixture_count} committed turns available)."
        ),
        "fixture_count": fixture_count,
    }


def run_agent_turn(
    *,
    task: str,
    python_source: str,
    route: str,
    model: str | None = None,
    messages: Sequence[Mapping[str, Any]] | None = None,
) -> dict[str, Any]:
    """v1 protocol: return a JSON envelope with ``python`` and ``message`` keys.

    The raw fixture content is batch-repl prose + fence, so we extract the
    prose portion as the message and supply an empty python string (the v1
    path is not the primary protocol for this tier).
    """
    raw = _resolve_fixture(task, messages)
    # Extract the prose portion (everything before the first ```batch fence).
    fence_idx = raw.find("```batch")
    if fence_idx >= 0:
        prose = raw[:fence_idx].strip()
    else:
        prose = raw.strip()
    if not prose:
        prose = "Agent processed the request."
    return {
        "content": json.dumps({"python": "", "message": prose}),
    }


def run_agent_turn_delta(
    *,
    task: str,
    projection: str,
    op_schema: Mapping[str, Any],
    route: str,
    model: str | None = None,
    messages: Sequence[Mapping[str, Any]] | None = None,
) -> dict[str, Any]:
    """Delta protocol: return ``delta`` and ``message`` keys.

    Fixtures are batch-repl, so we return an empty delta list and the prose
    portion of the matched fixture content.
    """
    raw = _resolve_fixture(task, messages)
    fence_idx = raw.find("```batch")
    if fence_idx >= 0:
        prose = raw[:fence_idx].strip()
    else:
        prose = raw.strip()
    if not prose:
        prose = "Agent processed the request."
    return {
        "delta": [],
        "message": prose,
    }


def run_agent_turn_batch(
    *,
    task: str,
    route: str,
    model: str | None = None,
    messages: Sequence[Mapping[str, Any]] | None = None,
) -> dict[str, Any]:
    """Batch-REPL protocol: return the raw model response as ``content``.

    This is the primary code path for the Playwright e2e tier.  The returned
    content is a prose sentence followed by exactly one ```batch fenced block,
    matching the contract expected by :func:`agent_provider.extract_batch_fence`.
    """
    content = _resolve_fixture(task, messages)
    return {"content": content}


def get_agent_status(*, route: str, model: str | None = None) -> dict[str, Any]:
    """Compatibility wrapper around readiness()."""
    payload = readiness(route=route, model=model)
    ready = bool(payload.get("ready"))
    return {
        **payload,
        "ok": ready,
        "detail": str(payload.get("reason") or ""),
        "readiness": "ready" if ready else "unavailable",
    }


__all__ = [
    "get_agent_status",
    "readiness",
    "run_agent_turn",
    "run_agent_turn_batch",
    "run_agent_turn_delta",
]
