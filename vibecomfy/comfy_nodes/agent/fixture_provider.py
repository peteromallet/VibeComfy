"""Deterministic Arnold-runtime provider backed by committed editor-session fixtures.

Wire it up by setting the standard discovery env var::

    export VIBECOMFY_ARNOLD_RUNTIME_MODULE="vibecomfy.comfy_nodes.agent.fixture_provider"

This module reads recorded agent-edit turns from the fixture corpus selected by
``VIBECOMFY_FIXTURE_DIR``.  When that variable is absent, it uses
``REPO_ROOT/tests/fixtures/editor_sessions/`` and finally the source-checkout
location derived from this file.  It never touches ``out/editor_sessions/`` and
requires no provider API keys — every call is deterministic.

Fixture resolution
------------------
The provider tries to match an incoming *task* string to a known fixture by
consulting ``manifest.json``.  The resolution order is:

1. **``VIBECOMFY_FIXTURE_SCENARIO``** — if set to a session name
   (e.g. ``"smoke_upscale_1"``), that session's lowest numeric turn is used
   regardless of the incoming task.  Missing or drifted forced selectors fail
   closed with a typed error.
2. **Hash match** — the first 16 hexadecimal characters of SHA-256 over the
   task text are matched against each fixture's committed ``_meta.task_hash``.
3. **Substring match** — the incoming task is substring-matched against the
   ``task_preview`` fields in the manifest.
4. **First-available fallback** — the first fixture in the manifest is used.

When the selected corpus is missing or empty, every entry point refuses with a
typed unavailable result.  The provider never reports readiness or fabricates
a successful edit without a real fixture corpus.

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
import re
from dataclasses import dataclass
from pathlib import Path
from typing import Any, Mapping, Sequence

_FIXTURE_ROOT: Path | None = None
_MANIFEST_CACHE: dict[str, Any] | None = None
_MANIFEST_ERROR: dict[str, Any] | None = None
_MANIFEST_CACHE_ROOT: Path | None = None
_CONTENT_CACHE: dict[str, Any] = {}
_METADATA_CACHE: dict[str, dict[str, Any] | None] = {}
_DOCUMENT_CACHE: dict[str, Any] = {}
_DOCUMENT_CACHE_ROOT: Path | None = None


@dataclass(frozen=True)
class FixtureResolution:
    """The selected fixture, or a typed refusal when selection is unsafe."""

    content: str | None
    fixture_key: str | None
    fixture_session: str | None
    match_kind: str
    fallback_used: bool
    error: dict[str, Any] | None = None

    def metadata(self) -> dict[str, Any]:
        return {
            "key": self.fixture_key,
            "session": self.fixture_session,
            "match_kind": self.match_kind,
            "fallback_used": self.fallback_used,
        }


class _FixtureDeltaResponse(dict[str, Any]):
    """Strict delta wire payload with an out-of-band audit sidecar."""

    def __init__(self, *, message: str, audit_metadata: Mapping[str, Any]) -> None:
        super().__init__(delta=[], message=message)
        self.audit_metadata = dict(audit_metadata)


def _repo_root() -> Path:
    """Resolve the repository root.

    Prefers ``REPO_ROOT`` (set by the Playwright launcher), falling back to
    walking up from this file's location.
    """
    env_root = os.environ.get("REPO_ROOT")
    if env_root:
        return Path(env_root)
    # This file lives at vibecomfy/comfy_nodes/agent/fixture_provider.py.
    return Path(__file__).resolve().parents[3]


def _fixture_root() -> Path:
    """Select the one fixture corpus used by validation and execution.

    The environment is intentionally consulted on every call: test harnesses
    and launcher processes can change it between imports.  An explicit fixture
    directory must outrank both the private ``_FIXTURE_ROOT`` test override and
    ``REPO_ROOT``; the private override then outranks ``REPO_ROOT`` for callers
    that construct temporary corpora.
    """
    configured = os.environ.get("VIBECOMFY_FIXTURE_DIR", "").strip()
    if configured:
        return Path(configured)
    if _FIXTURE_ROOT is not None:
        return _FIXTURE_ROOT
    repo_root = os.environ.get("REPO_ROOT", "").strip()
    if repo_root:
        return Path(repo_root) / "tests" / "fixtures" / "editor_sessions"
    return _repo_root() / "tests" / "fixtures" / "editor_sessions"


def _fixture_key_issue(key: Any) -> str | None:
    """Return a refusal reason when *key* is not a safe fixture directory ID."""
    if not isinstance(key, str) or not key:
        return "fixture key must be a non-empty string"
    if key in {".", ".."} or "\x00" in key:
        return "fixture key must be a single relative directory ID"
    if Path(key).is_absolute() or "/" in key or "\\" in key:
        return "fixture key must not contain absolute-path or separator characters"
    return None


def _read_fixture_json(key: str, filename: str) -> Any:
    """Read one fixture file through directory FDs, refusing symlink escapes."""
    if _fixture_key_issue(key) is not None:
        return None
    nofollow = getattr(os, "O_NOFOLLOW", 0)
    if not nofollow:
        return None
    flags = os.O_RDONLY | getattr(os, "O_CLOEXEC", 0) | nofollow
    directory_flags = flags | getattr(os, "O_DIRECTORY", 0)
    root_fd: int | None = None
    fixture_fd: int | None = None
    file_fd: int | None = None
    try:
        root_fd = os.open(_fixture_root(), directory_flags)
        fixture_fd = os.open(key, directory_flags, dir_fd=root_fd)
        file_fd = os.open(filename, flags, dir_fd=fixture_fd)
        with os.fdopen(file_fd, "r", encoding="utf-8") as stream:
            file_fd = None
            return json.load(stream)
    except (OSError, json.JSONDecodeError, UnicodeDecodeError):
        return None
    finally:
        if file_fd is not None:
            os.close(file_fd)
        if fixture_fd is not None:
            os.close(fixture_fd)
        if root_fd is not None:
            os.close(root_fd)


def _read_manifest_json() -> Any:
    """Read the manifest through a no-follow root/file descriptor pair."""
    nofollow = getattr(os, "O_NOFOLLOW", 0)
    if not nofollow:
        raise OSError("O_NOFOLLOW is unavailable")
    flags = os.O_RDONLY | getattr(os, "O_CLOEXEC", 0) | nofollow
    root_fd: int | None = None
    file_fd: int | None = None
    try:
        root_fd = os.open(_fixture_root(), flags | getattr(os, "O_DIRECTORY", 0))
        file_fd = os.open("manifest.json", flags, dir_fd=root_fd)
        with os.fdopen(file_fd, "r", encoding="utf-8") as stream:
            file_fd = None
            return json.load(stream)
    finally:
        if file_fd is not None:
            os.close(file_fd)
        if root_fd is not None:
            os.close(root_fd)


def _sync_fixture_root() -> Path:
    """Invalidate all fixture-domain caches when corpus authority changes."""
    global _DOCUMENT_CACHE_ROOT, _MANIFEST_CACHE, _MANIFEST_CACHE_ROOT, _MANIFEST_ERROR
    root = _fixture_root()
    if _DOCUMENT_CACHE_ROOT != root or _MANIFEST_CACHE_ROOT != root:
        _DOCUMENT_CACHE.clear()
        _CONTENT_CACHE.clear()
        _METADATA_CACHE.clear()
        _MANIFEST_CACHE = None
        _MANIFEST_ERROR = None
        _DOCUMENT_CACHE_ROOT = root
        _MANIFEST_CACHE_ROOT = root
    return root


def _load_fixture_document(key: str) -> Any:
    _sync_fixture_root()
    if key not in _DOCUMENT_CACHE:
        _DOCUMENT_CACHE[key] = _read_fixture_json(key, "fixture.json")
    return _DOCUMENT_CACHE[key]


def _load_manifest() -> dict[str, Any]:
    global _MANIFEST_CACHE, _MANIFEST_ERROR, _MANIFEST_CACHE_ROOT
    root = _sync_fixture_root()
    if _MANIFEST_CACHE is not None and _MANIFEST_CACHE_ROOT == root:
        return _MANIFEST_CACHE
    _MANIFEST_ERROR = None
    _MANIFEST_CACHE_ROOT = root
    path = root / "manifest.json"
    try:
        loaded = _read_manifest_json()
    except (FileNotFoundError, NotADirectoryError):
        _MANIFEST_ERROR = {
            "kind": "fixture_unavailable",
            "code": "fixture_root_missing",
            "message": (
                f"Fixture corpus {root} is missing or has no manifest at {path}; "
                "configure VIBECOMFY_FIXTURE_DIR or REPO_ROOT."
            ),
        }
        _MANIFEST_CACHE = {}
        return _MANIFEST_CACHE
    except (json.JSONDecodeError, OSError, UnicodeDecodeError) as exc:
        _MANIFEST_ERROR = {
            "kind": "fixture_corruption",
            "code": "manifest_unreadable",
            "message": f"Fixture manifest {path} cannot be read as JSON: {exc}.",
        }
        _MANIFEST_CACHE = {}
        return _MANIFEST_CACHE
    if not isinstance(loaded, dict):
        _MANIFEST_ERROR = {
            "kind": "fixture_corruption",
            "code": "manifest_not_object",
            "message": f"Fixture manifest {path} must contain a JSON object.",
        }
        _MANIFEST_CACHE = {}
        return _MANIFEST_CACHE
    if not loaded:
        _MANIFEST_ERROR = {
            "kind": "fixture_unavailable",
            "code": "empty_manifest",
            "message": f"Fixture corpus {root} has an empty manifest at {path}.",
        }
    for key, entry in loaded.items():
        key_issue = _fixture_key_issue(key)
        if key_issue is not None:
            _MANIFEST_ERROR = {
                "kind": "fixture_corruption",
                "code": "manifest_key_unsafe",
                "message": f"Fixture manifest entry {key!r} is unsafe: {key_issue}.",
            }
            break
        if not isinstance(entry, dict):
            _MANIFEST_ERROR = {
                "kind": "fixture_corruption",
                "code": "manifest_entry_not_object",
                "message": f"Fixture manifest entry {key!r} must be a JSON object.",
            }
            break
        if not isinstance(entry.get("session"), str) or not entry["session"]:
            _MANIFEST_ERROR = {
                "kind": "fixture_corruption",
                "code": "manifest_session_invalid",
                "message": f"Fixture manifest entry {key!r} has an invalid session.",
            }
            break
        turn = entry.get("turn")
        if not isinstance(turn, str) or not turn.isdigit():
            _MANIFEST_ERROR = {
                "kind": "fixture_corruption",
                "code": "malformed_turn",
                "message": f"Fixture manifest entry {key!r} has malformed turn {turn!r}.",
            }
            break
        if not isinstance(entry.get("task_preview"), str):
            _MANIFEST_ERROR = {
                "kind": "fixture_corruption",
                "code": "manifest_task_preview_invalid",
                "message": f"Fixture manifest entry {key!r} has an invalid task_preview.",
            }
            break
        task_hash = entry.get("task_hash")
        if task_hash is not None and (
            not isinstance(task_hash, str)
            or len(task_hash) != 16
            or any(char not in "0123456789abcdef" for char in task_hash)
        ):
            _MANIFEST_ERROR = {
                "kind": "fixture_corruption",
                "code": "manifest_task_hash_invalid",
                "message": f"Fixture manifest entry {key!r} has an invalid task_hash.",
            }
            break
    _MANIFEST_CACHE = loaded
    return _MANIFEST_CACHE


def _compute_key(task: str, messages: Sequence[Mapping[str, Any]] | None = None) -> str:
    """Compute the committed fixture task hash.

    The editor-session corpus records ``_meta.task_hash`` as the first 16
    hexadecimal characters of SHA-256 over the task text alone.  ``messages``
    remains accepted for adapter compatibility but is intentionally excluded
    from this authoritative contract. Synthetic replay fixtures without a
    request task use their committed fixture key as their identity hash.
    """
    del messages
    return hashlib.sha256(task.encode("utf-8")).hexdigest()[:16]


def _load_fixture_metadata(key: str) -> dict[str, Any] | None:
    """Load the committed ``fixture.json`` metadata used for hash matching."""
    _sync_fixture_root()
    if key in _METADATA_CACHE:
        return _METADATA_CACHE[key]
    data = _load_fixture_document(key)
    if not isinstance(data, Mapping):
        _METADATA_CACHE[key] = None
        return None
    metadata = data.get("_meta")
    result = dict(metadata) if isinstance(metadata, Mapping) else None
    _METADATA_CACHE[key] = result
    return result


def _load_fixture_content(key: str) -> Any:
    """Load raw fixture content for validation (with caching)."""
    _sync_fixture_root()
    if key in _CONTENT_CACHE:
        return _CONTENT_CACHE[key]
    data = _load_fixture_document(key)
    content = data.get("content", "") if isinstance(data, Mapping) else None
    _CONTENT_CACHE[key] = content
    return content


def _content_issue(content: Any, *, key: str, mode: str) -> tuple[str, str] | None:
    if content is None or content == "":
        return (
            "fixture_content_missing",
            f"Fixture key {key!r} has no readable content for {mode} mode.",
        )
    if not isinstance(content, str):
        return (
            "fixture_content_invalid",
            f"Fixture key {key!r} content must be a string for {mode} mode, "
            f"not {type(content).__name__}.",
        )
    markers = list(re.finditer(r"```", content))
    opener = re.search(r"```batch[ \t]*\r?\n", content)
    closing = (
        re.match(r"```[ \t]*(?:\r?\n|$)", content[markers[1].start():])
        if len(markers) > 1
        else None
    )
    body = (
        content[opener.end() : markers[1].start()]
        if opener is not None and len(markers) > 1
        else ""
    )
    if (
        len(markers) != 2
        or opener is None
        or opener.start() != markers[0].start()
        or closing is None
        or not body.strip()
    ):
        return (
            "fixture_fence_invalid",
            f"Fixture key {key!r} content must contain exactly one complete "
            f"```batch fence for {mode} mode (found {len(markers)} fence markers).",
        )
    return None


def _fixture_identity_issue(
    key: str,
    entry: Mapping[str, Any],
) -> tuple[str, str] | None:
    metadata = _load_fixture_metadata(key)
    if metadata is None:
        return (
            "fixture_metadata_missing",
            f"Fixture key {key!r} has no readable _meta identity metadata.",
        )
    expected = {
        "key": key,
        "session": entry.get("session"),
        "turn": entry.get("turn"),
    }
    for field, value in expected.items():
        if metadata.get(field) != value:
            return (
                "fixture_identity_mismatch",
                f"Fixture key {key!r} _meta.{field}={metadata.get(field)!r} "
                f"does not match manifest value {value!r}.",
            )
    manifest_hash = entry.get("task_hash")
    if manifest_hash is not None and metadata.get("task_hash") != manifest_hash:
        return (
            "manifest_task_hash_mismatch",
            f"Fixture key {key!r} _meta.task_hash={metadata.get('task_hash')!r} "
            f"does not match manifest task_hash={manifest_hash!r}.",
        )
    request = _read_fixture_json(key, "request.json")
    if request is None:
        return (
            "fixture_request_missing",
            f"Fixture key {key!r} request.json cannot be read as a JSON object.",
        )
    task = request.get("task") if isinstance(request, dict) else None
    actual_hash = _compute_key(task) if isinstance(task, str) else None
    if actual_hash is None and metadata.get("synthetic") and metadata.get("task_hash") == key:
        return None
    if actual_hash is None or metadata.get("task_hash") != actual_hash:
        return (
            "fixture_task_hash_mismatch",
            f"Fixture key {key!r} _meta.task_hash does not match the authoritative "
            "SHA-256 hash of request.json task text.",
        )
    return None


def _fixture_error(
    *,
    code: str,
    message: str,
    forced_scenario: str | None,
    available_scenarios: Sequence[str],
    kind: str = "fixture_not_found",
) -> dict[str, Any]:
    return {
        "kind": kind,
        "code": code,
        "message": message,
        "forced_scenario": forced_scenario,
        "available_scenarios": list(available_scenarios),
    }


def _corruption_resolution(
    key: str,
    entry: Mapping[str, Any],
    code: str,
    message: str,
    *,
    forced_scenario: str | None = None,
) -> FixtureResolution:
    return FixtureResolution(
        content=None,
        fixture_key=key,
        fixture_session=(
            forced_scenario
            or (str(entry.get("session")) if entry.get("session") else None)
        ),
        match_kind="corrupt",
        fallback_used=False,
        error={
            "kind": "fixture_corruption",
            "code": code,
            "message": message,
            "forced_scenario": forced_scenario,
            "available_scenarios": [],
        },
    )


def _ambiguous_resolution(
    matches: Sequence[tuple[str, Mapping[str, Any]]],
    task_hash: str,
) -> FixtureResolution:
    keys = [key for key, _entry in matches]
    return FixtureResolution(
        content=None,
        fixture_key=None,
        fixture_session=None,
        match_kind="ambiguous",
        fallback_used=False,
        error={
            "kind": "fixture_ambiguous",
            "code": "ambiguous_task_hash",
            "message": (
                f"Task hash {task_hash!r} matches multiple valid fixtures "
                f"({', '.join(keys)}); provide authoritative session context "
                "or force a fixture scenario."
            ),
            "task_hash": task_hash,
            "fixture_keys": keys,
            "fallback_used": False,
        },
    )


def _context_session(messages: Sequence[Mapping[str, Any]] | None) -> str | None:
    """Extract one explicit session identity, never infer it from prose."""
    sessions: set[str] = set()
    for message in messages or ():
        if not isinstance(message, Mapping):
            continue
        for field in ("session_id", "session"):
            value = message.get(field)
            if isinstance(value, str) and value.strip():
                sessions.add(value.strip())
    return next(iter(sessions)) if len(sessions) == 1 else None


def _forced_fixture_resolution(
    manifest: Mapping[str, Any],
    forced_scenario: str,
    *,
    mode: str,
) -> FixtureResolution:
    available_scenarios = sorted(
        {
            str(entry.get("session"))
            for entry in manifest.values()
            if isinstance(entry, Mapping) and entry.get("session")
        }
    )

    def refusal(
        code: str,
        message: str,
        *,
        key: str | None = None,
        kind: str = "fixture_not_found",
    ) -> FixtureResolution:
        return FixtureResolution(
            content=None,
            fixture_key=key,
            fixture_session=forced_scenario,
            match_kind="forced_missing",
            fallback_used=False,
            error=_fixture_error(
                code=code,
                message=message,
                forced_scenario=forced_scenario,
                available_scenarios=available_scenarios,
                kind=kind,
            ),
        )

    if not manifest:
        return refusal(
            "empty_manifest",
            f"Forced fixture scenario {forced_scenario!r} cannot be resolved: "
            f"the manifest at {_fixture_root() / 'manifest.json'} is empty.",
        )

    candidates = [
        (key, entry)
        for key, entry in manifest.items()
        if isinstance(entry, Mapping) and entry.get("session") == forced_scenario
    ]
    if not candidates:
        return refusal(
            "forced_scenario_not_found",
            f"Forced fixture scenario {forced_scenario!r} is not present in "
            f"the manifest at {_fixture_root() / 'manifest.json'}. Choose one "
            f"of: {', '.join(available_scenarios) or '(none)'}.",
        )

    turns: dict[int, tuple[str, Mapping[str, Any]]] = {}
    for key, entry in candidates:
        raw_turn = entry.get("turn")
        if not isinstance(raw_turn, str) or not raw_turn.isdigit():
            return refusal(
                "malformed_turn",
                f"Forced fixture scenario {forced_scenario!r} has malformed turn "
                f"{raw_turn!r} for fixture key {key!r}; repair the manifest.",
                key=key,
            )
        turn = int(raw_turn)
        if turn in turns:
            duplicate_key = turns[turn][0]
            return refusal(
                "duplicate_turn",
                f"Forced fixture scenario {forced_scenario!r} has duplicate numeric "
                f"turn {turn} in fixture keys {duplicate_key!r} and {key!r}; "
                "repair the manifest.",
                key=key,
            )
        turns[turn] = (key, entry)

    for turn in sorted(turns):
        key, entry = turns[turn]
        identity_issue = _fixture_identity_issue(key, entry)
        if identity_issue is not None:
            code, message = identity_issue
            return refusal(code, message, key=key, kind="fixture_corruption")
        content = _load_fixture_content(key)
        content_issue = _content_issue(content, key=key, mode=mode)
        if content_issue is not None:
            code, message = content_issue
            return refusal(
                code,
                message,
                key=key,
                kind="fixture_corruption",
            )

    turn = min(turns)
    key, _entry = turns[turn]
    return FixtureResolution(
        content=_load_fixture_content(key),
        fixture_key=key,
        fixture_session=forced_scenario,
        match_kind="explicit",
        fallback_used=False,
    )


def _resolve_fixture_result(
    task: str,
    messages: Sequence[Mapping[str, Any]] | None = None,
    *,
    mode: str = "batch",
) -> FixtureResolution:
    """Resolve a fixture content string for the given task and messages.

    Resolution order:
    1. ``VIBECOMFY_FIXTURE_SCENARIO`` env var (session name; lowest numeric
       valid turn).
    2. Task-only hash match against committed fixture metadata.
    3. Substring match of task against task_preview entries.
    4. First-available fallback.

    Forced selectors are authoritative: a missing or drifted selector returns a
    typed error instead of silently choosing a different turn.  An unavailable
    corpus is also a typed refusal for unforced calls; it never becomes a
    synthetic success.
    """
    manifest = _load_manifest()
    forced_scenario = os.environ.get("VIBECOMFY_FIXTURE_SCENARIO", "").strip()
    if _MANIFEST_ERROR is not None:
        unavailable = _MANIFEST_ERROR.get("kind") == "fixture_unavailable"
        return FixtureResolution(
            content=None,
            fixture_key=None,
            fixture_session=forced_scenario or None,
            match_kind=("forced_missing" if forced_scenario else "unavailable")
            if unavailable
            else "manifest_invalid",
            fallback_used=False,
            error={
                **_MANIFEST_ERROR,
                "forced_scenario": forced_scenario or None,
            },
        )
    if forced_scenario:
        return _forced_fixture_resolution(manifest, forced_scenario, mode=mode)
    for key, entry in manifest.items():
        if not isinstance(entry, Mapping):
            continue
        identity_issue = _fixture_identity_issue(key, entry)
        if identity_issue is not None:
            code, message = identity_issue
            return _corruption_resolution(
                key,
                entry,
                code,
                message,
                forced_scenario=forced_scenario or None,
            )
        content_issue = _content_issue(
            _load_fixture_content(key),
            key=key,
            mode=mode,
        )
        if content_issue is not None:
            code, message = content_issue
            return _corruption_resolution(
                key,
                entry,
                code,
                message,
                forced_scenario=forced_scenario or None,
            )
    # 1 — Hash match.  The task-only hash is authoritative, even when the
    # adapter did not provide conversation messages.
    task_hash = _compute_key(task, messages)
    hash_matches = []
    for key, entry in manifest.items():
        fixture_meta = _load_fixture_metadata(key)
        recorded_hash = (
            entry.get("task_hash") if isinstance(entry, Mapping) else None
        ) or (fixture_meta or {}).get("task_hash")
        if recorded_hash == task_hash:
            hash_matches.append((key, entry))
    if len(hash_matches) > 1:
        context_session = _context_session(messages)
        if context_session is not None:
            contextual_matches = [
                (key, entry)
                for key, entry in hash_matches
                if isinstance(entry, Mapping) and entry.get("session") == context_session
            ]
            if len(contextual_matches) == 1:
                hash_matches = contextual_matches
            else:
                return _ambiguous_resolution(hash_matches, task_hash)
        else:
            return _ambiguous_resolution(hash_matches, task_hash)
    for key, entry in hash_matches:
        if not isinstance(entry, Mapping):
            continue
        identity_issue = _fixture_identity_issue(key, entry)
        if identity_issue is not None:
            code, message = identity_issue
            return _corruption_resolution(key, entry, code, message)
        content = _load_fixture_content(key)
        content_issue = _content_issue(content, key=key, mode=mode)
        if content_issue is not None:
            code, message = content_issue
            return _corruption_resolution(key, entry, code, message)
        return FixtureResolution(
            content=content,
            fixture_key=key,
            fixture_session=(str(entry.get("session")) if entry.get("session") else None),
            match_kind="hash",
            fallback_used=False,
        )

    # 2 — Substring match on task vs task_preview
    task_lower = task.lower().strip()
    if task_lower:
        for key, entry in manifest.items():
            if not isinstance(entry, Mapping):
                continue
            preview = (entry.get("task_preview") or "").lower().strip()
            if preview and (preview in task_lower or task_lower in preview):
                identity_issue = _fixture_identity_issue(key, entry)
                if identity_issue is not None:
                    code, message = identity_issue
                    return _corruption_resolution(key, entry, code, message)
                content = _load_fixture_content(key)
                content_issue = _content_issue(content, key=key, mode=mode)
                if content_issue is not None:
                    code, message = content_issue
                    return _corruption_resolution(key, entry, code, message)
                return FixtureResolution(
                    content=content,
                    fixture_key=key,
                    fixture_session=(str(entry.get("session")) if entry.get("session") else None),
                    match_kind="substring",
                    fallback_used=False,
                )

    # 3 — First-available fallback (intentional only when unforced)
    for key in sorted(manifest):
        entry = manifest[key]
        if not isinstance(entry, Mapping):
            continue
        identity_issue = _fixture_identity_issue(key, entry)
        if identity_issue is not None:
            code, message = identity_issue
            return _corruption_resolution(key, entry, code, message)
        content = _load_fixture_content(key)
        content_issue = _content_issue(content, key=key, mode=mode)
        if content_issue is not None:
            code, message = content_issue
            return _corruption_resolution(key, entry, code, message)
        return FixtureResolution(
            content=content,
            fixture_key=key,
            fixture_session=(str(entry.get("session")) if entry.get("session") else None),
            match_kind="fallback",
            fallback_used=True,
        )

    # A valid manifest should always provide a real fixture.  Keep this as a
    # typed refusal in case a future loader filters every row unexpectedly.
    return FixtureResolution(
        content=None,
        fixture_key=None,
        fixture_session=None,
        match_kind="unavailable",
        fallback_used=False,
        error=_fixture_error(
            code="no_usable_fixtures",
            message=f"Fixture corpus {_fixture_root()} has no usable fixtures.",
            forced_scenario=None,
            available_scenarios=[],
            kind="fixture_unavailable",
        ),
    )


def _resolve_fixture(task: str, messages: Sequence[Mapping[str, Any]] | None = None) -> str:
    """Compatibility wrapper returning only content for legacy callers."""
    result = _resolve_fixture_result(task, messages)
    return result.content or ""


def _response_metadata(result: FixtureResolution) -> dict[str, Any]:
    """Expose fixture provenance without changing the protocol payload shape."""
    metadata = result.metadata()
    response = {
        "fixture": metadata,
        "fixture_metadata": metadata,
        "fixture_key": result.fixture_key,
        "match_kind": result.match_kind,
        "fallback_used": result.fallback_used,
    }
    if result.error is not None:
        response["error"] = result.error
    return response


def _delta_response(result: FixtureResolution, message: str) -> _FixtureDeltaResponse:
    return _FixtureDeltaResponse(
        message=message,
        audit_metadata={"fixture": result.metadata()},
    )


def _synthetic_response(task: str) -> str:
    """Legacy helper retained for import compatibility; never used for calls."""
    task_preview = task.strip()[:80] if task else "your request"
    return (
        f"I'll process {task_preview}.\n"
        "```batch\n"
        "done()\n"
        "```"
    )


# ── Public entry points ──────────────────────────────────────────────────────


def readiness(*, route: str, model: str | None = None) -> dict[str, Any]:
    """Report whether the fixture manifest and committed fixtures are usable."""
    manifest = _load_manifest()
    fixture_count = len(manifest)
    base = {
        "backend": "vibecomfy.comfy_nodes.agent.fixture_provider",
        "route": route,
        "model": model or "agent-edit",
        "fixture_count": fixture_count,
    }
    if _MANIFEST_ERROR is not None:
        return {
            **base,
            "ready": False,
            "ok": False,
            "readiness": "unavailable",
            "reason": _MANIFEST_ERROR["message"],
            "error": dict(_MANIFEST_ERROR),
        }
    for key, entry in manifest.items():
        if not isinstance(entry, Mapping):
            continue
        identity_issue = _fixture_identity_issue(key, entry)
        if identity_issue is not None:
            code, message = identity_issue
            error = {
                "kind": "fixture_corruption",
                "code": code,
                "message": message,
                "fixture_key": key,
            }
            return {
                **base,
                "ready": False,
                "ok": False,
                "readiness": "unavailable",
                "reason": message,
                "error": error,
            }
        content_issue = _content_issue(
            _load_fixture_content(key),
            key=key,
            mode="readiness",
        )
        if content_issue is not None:
            code, message = content_issue
            error = {
                "kind": "fixture_corruption",
                "code": code,
                "message": message,
                "fixture_key": key,
            }
            return {
                **base,
                "ready": False,
                "ok": False,
                "readiness": "unavailable",
                "reason": message,
                "error": error,
            }
    return {
        **base,
        "ready": True,
        "reason": (
            f"Fixture provider is always ready ({fixture_count} committed turns available)."
        ),
        "ok": True,
        "readiness": "ready",
    }


def run_agent_turn(
    *,
    task: str,
    python_source: str,
    route: str,
    model: str | None = None,
    effort: str | None = None,
    messages: Sequence[Mapping[str, Any]] | None = None,
) -> dict[str, Any]:
    """v1 protocol: return a JSON envelope with ``python`` and ``message`` keys.

    The raw fixture content is batch-repl prose + fence, so we extract the
    prose portion as the message and supply an empty python string (the v1
    path is not the primary protocol for this tier).
    """
    resolution = _resolve_fixture_result(task, messages, mode="v1")
    if resolution.error is not None:
        return _response_metadata(resolution)
    raw = resolution.content or ""
    # Extract the prose portion (everything before the first ```batch fence).
    fence_idx = raw.find("```batch")
    if fence_idx >= 0:
        prose = raw[:fence_idx].strip()
    else:
        prose = raw.strip()
    if not prose:
        prose = "Agent processed the request."
    return {
        **_response_metadata(resolution),
        "content": json.dumps({"python": "", "message": prose}),
    }


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
    """Delta protocol: return ``delta`` and ``message`` keys.

    Fixtures are batch-repl, so we return an empty delta list and the prose
    portion of the matched fixture content.
    """
    resolution = _resolve_fixture_result(task, messages, mode="delta")
    if resolution.error is not None:
        return _response_metadata(resolution)
    raw = resolution.content or ""
    fence_idx = raw.find("```batch")
    if fence_idx >= 0:
        prose = raw[:fence_idx].strip()
    else:
        prose = raw.strip()
    if not prose:
        prose = "Agent processed the request."
    return _delta_response(resolution, prose)


def run_agent_turn_batch(
    *,
    task: str,
    route: str,
    model: str | None = None,
    effort: str | None = None,
    messages: Sequence[Mapping[str, Any]] | None = None,
) -> dict[str, Any]:
    """Batch-REPL protocol: return the raw model response as ``content``.

    This is the primary code path for the Playwright e2e tier.  The returned
    content is a prose sentence followed by exactly one ```batch fenced block,
    matching the contract expected by :func:`agent_provider.extract_batch_fence`.
    """
    resolution = _resolve_fixture_result(task, messages, mode="batch")
    return {
        **_response_metadata(resolution),
        "content": resolution.content or "",
    }


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
    "FixtureResolution",
    "get_agent_status",
    "readiness",
    "run_agent_turn",
    "run_agent_turn_batch",
    "run_agent_turn_delta",
]
