"""
vibecomfy ComfyUI custom-node entry point.

Dynamic IO (Option C) — env flag VIBECOMFY_CODE_DYNAMIC_IO=1
-------------------------------------------------------------
When the flag is set, VibeComfyCodeIntent exposes a pre-declared 16-slot wildcard
input pool (in_0..in_15) plus hidden unique_id/prompt instead of the old
named-kwarg config surface.  MAX_DYNAMIC_PORTS=16 is the hard cap enforced by
the contract layer (validate_typed_io_spec).

Why 16-port pool instead of per-instance addInput/removeInput:
ComfyUI discovers node ports exclusively by calling INPUT_TYPES as a @classmethod
with no instance state available.  Per-instance port counts are therefore
infeasible from the Python side; the pre-declared wildcard pool is the correct
architecture (SD1).  The frontend hides unused trailing slots and relabels active
ones at runtime without changing the serialised in_i key names.

To opt back into the pre-sprint behaviour (single 'value' input + config kwargs),
unset VIBECOMFY_CODE_DYNAMIC_IO or set it to any value other than "1".
"""
from __future__ import annotations

import logging
import os
import sys
import hashlib
import inspect
import threading
import uuid
from datetime import datetime, timezone
from pathlib import Path
from typing import Any

_LOGGER = logging.getLogger(__name__)

_REPO_ROOT = Path(__file__).resolve().parents[2]
if str(_REPO_ROOT) not in sys.path:
    sys.path.insert(0, str(_REPO_ROOT))

from .exec_node import EXEC_CLASS_TYPE, VibeComfyExec
from vibecomfy.contracts.intent_nodes import KIND_TO_CLASS_TYPE

_MAX_DYNAMIC_PORTS = 16

# Resolve WEB_DIRECTORY to the cache-busted web_dist/<hash>/ copy matching the
# current web/ source content when available. Never fall back to an arbitrary
# older dist: serving stale ESM modules is worse than using ./web directly in
# development.
_MODULE_DIR = Path(__file__).resolve().parent
_WEB_SRC_DIR = _MODULE_DIR / "web"
_WEB_DIST_DIR = _MODULE_DIR / "web_dist"
_WEB_DIRECTORY = "./web"  # fallback
_MODULE_START_AT_UTC = datetime.now(timezone.utc)
_PROCESS_START_ID = uuid.uuid4().hex
_INFO_CONTRACT_VERSION = 1

_ROUTES_UNINITIALIZED = "uninitialized"
_ROUTES_LOADING = "loading"
_ROUTES_REGISTERED = "registered"
_ROUTES_PENDING_AUDIT = "pending_audit"
_ROUTES_READY = "ready"
_ROUTES_FAILED = "failed"


class _RouteRegistrationOwner:
    """Shared route-init state stored on the PromptServer instance."""

    def __init__(self) -> None:
        self.condition = threading.Condition(threading.RLock())
        self.state = _ROUTES_UNINITIALIZED
        self.error: BaseException | None = None
        self.owner_thread: int | None = None


_route_state = _ROUTES_UNINITIALIZED
_route_error: BaseException | None = None
_route_owner_thread: int | None = None
_route_condition = threading.Condition(threading.RLock())
_route_local_owner = _RouteRegistrationOwner()


def _mirror_route_owner(owner: _RouteRegistrationOwner) -> None:
    """Keep legacy module diagnostics as a view, never as the authority."""
    global _route_error, _route_owner_thread, _route_state
    _route_state = owner.state
    _route_error = owner.error
    _route_owner_thread = owner.owner_thread


def _route_registration_owner(instance: Any) -> _RouteRegistrationOwner:
    """Return one owner shared by all loaders using this PromptServer."""
    for host in (instance, getattr(instance, "app", None)):
        if host is None:
            continue
        try:
            attributes = vars(host)
        except TypeError:
            continue
        owner = attributes.get("_vibecomfy_route_registration_owner")
        if isinstance(owner, _RouteRegistrationOwner):
            return owner
        # dict.setdefault is the one atomic publication point needed when two
        # alternate module loaders first see the same PromptServer instance.
        candidate = _RouteRegistrationOwner()
        return attributes.setdefault("_vibecomfy_route_registration_owner", candidate)
    return _route_local_owner


def _web_source_hash() -> str | None:
    """Return the 12-char content hash used by build_web_cache_bust.sh."""
    if not _WEB_SRC_DIR.is_dir():
        return None
    digest = hashlib.sha256()
    try:
        entries = sorted(_p for _p in _WEB_SRC_DIR.iterdir() if _p.is_file())
        for entry in entries:
            if entry.name.endswith((".bak", "~", ".orig", ".tmp")):
                continue
            digest.update(entry.name.encode("utf-8"))
            digest.update(b"\0")
            digest.update(entry.read_bytes())
            digest.update(b"\0")
    except OSError:
        return None
    return digest.hexdigest()[:12]


if _WEB_DIST_DIR.is_dir():
    _source_hash = _web_source_hash()
    _matching_dist = _WEB_DIST_DIR / _source_hash if _source_hash else None
    if _matching_dist is not None and _matching_dist.is_dir():
        try:
            if any(_p.is_file() for _p in _matching_dist.iterdir()):
                _WEB_DIRECTORY = f"./web_dist/{_matching_dist.name}"
        except OSError:
            pass
WEB_DIRECTORY = _WEB_DIRECTORY
_LOGGER.info("VibeComfy custom node loading. WEB_DIRECTORY=%s", WEB_DIRECTORY)


def _utc_isoformat(value: datetime) -> str:
    return value.astimezone(timezone.utc).isoformat().replace("+00:00", "Z")


def _runtime_modes_snapshot() -> dict[str, bool | str]:
    """Return semantic modes without reflecting raw environment values."""
    return {
        "headless": os.environ.get("VIBECOMFY_HEADLESS") == "1",
        "dynamic_io": os.environ.get("VIBECOMFY_CODE_DYNAMIC_IO") == "1",
        "runtime_module": (
            "configured"
            if os.environ.get("VIBECOMFY_ARNOLD_RUNTIME_MODULE")
            else "default"
        ),
        "demo_picker": os.environ.get("VIBECOMFY_DEMO_PICKER") == "1",
        "agentic_replay": os.environ.get("VIBECOMFY_AGENTIC_REPLAY") == "1",
    }


def _served_asset_snapshot(source_hash: str | None) -> dict[str, str | None]:
    """Describe the served bytes without exposing or trusting a filesystem path."""
    if WEB_DIRECTORY == "./web":
        return {
            "served_asset_kind": "source",
            "served_asset_id": f"source:{source_hash}" if source_hash else None,
            "served_asset_state": "identified" if source_hash else "unavailable",
        }
    if source_hash and WEB_DIRECTORY == f"./web_dist/{source_hash}":
        return {
            "served_asset_kind": "cache_busted_dist",
            "served_asset_id": f"dist:{source_hash}",
            "served_asset_state": "identified",
        }
    return {
        "served_asset_kind": "unknown",
        "served_asset_id": None,
        "served_asset_state": "unavailable",
    }


def _git_info_snapshot() -> dict[str, Any]:
    from vibecomfy._git_utils import git_stdout_result
    from vibecomfy.utils import find_repo_root

    try:
        repo_root = find_repo_root()
        sha_result = git_stdout_result(repo_root, ["rev-parse", "HEAD"])
        dirty_result = git_stdout_result(repo_root, ["status", "--porcelain"])
    except Exception:  # pragma: no cover - defensive containment
        return {
            "sha": None,
            "dirty": None,
            "state": "unavailable",
        }

    sha_candidate = (sha_result.stdout or "").strip().lower()
    sha = (
        sha_candidate
        if len(sha_candidate) in (40, 64)
        and all(character in "0123456789abcdef" for character in sha_candidate)
        else None
    )
    dirty = (
        bool(dirty_result.stdout.strip())
        if dirty_result.stdout is not None
        else None
    )
    if sha is None:
        state = "unavailable"
    elif dirty is None:
        state = "dirty_state_unavailable"
    else:
        state = "dirty" if dirty else "clean"
    return {
        "sha": sha,
        "dirty": dirty,
        "state": state,
    }


def _info_payload() -> dict[str, Any]:
    git = _git_info_snapshot()
    source_hash = _web_source_hash()
    served_asset = _served_asset_snapshot(source_hash)
    remediation: list[str] = []
    if git["state"] == "unavailable":
        remediation.append("restore_git_metadata")
    elif git["state"] == "dirty_state_unavailable":
        remediation.append("check_git_worktree_state")
    if source_hash is None:
        remediation.append("rebuild_web_assets")
    if served_asset["served_asset_state"] == "unavailable" and source_hash is not None:
        remediation.append("restart_with_matching_web_assets")

    payload: dict[str, Any] = {
        "info_contract_version": _INFO_CONTRACT_VERSION,
        "process_start_id": _PROCESS_START_ID,
        "start_time_utc": _utc_isoformat(_MODULE_START_AT_UTC),
        "git_sha": git["sha"],
        "git_dirty": git["dirty"],
        "git_state": git["state"],
        "web_source_hash": source_hash,
        "web_source_state": "identified" if source_hash else "unavailable",
        **served_asset,
        "runtime_modes": _runtime_modes_snapshot(),
        "remediation": remediation,
    }
    return payload

def _ensure_comfyui_root_on_path() -> None:
    """Make sure the running ComfyUI root is on sys.path.

    Some launchers run custom nodes without putting the ComfyUI root directory on
    PYTHONPATH.  The routes below need to import ``server.PromptServer``, so we
    look for the directory that contains both ``server.py`` and ``nodes.py`` and
    add it if necessary.
    """
    candidates: list[Path] = [Path.cwd()]
    candidates.extend(Path(__file__).resolve().parents)
    for candidate in candidates:
        if (candidate / "server.py").is_file() and (candidate / "nodes.py").is_file():
            path_str = str(candidate)
            if path_str not in sys.path:
                _LOGGER.info("Adding ComfyUI root to sys.path: %s", path_str)
                sys.path.insert(0, path_str)
            else:
                _LOGGER.info("ComfyUI root already on sys.path: %s", path_str)
            return
    _LOGGER.warning("Could not locate ComfyUI root (no server.py + nodes.py found).")


def _resolve_prompt_server_instance() -> Any:
    _ensure_comfyui_root_on_path()
    from ._server_compat import import_prompt_server

    global PromptServer
    PromptServer = import_prompt_server()
    return PromptServer.instance


def _mark_route_failed(
    instance: Any,
    owner: _RouteRegistrationOwner,
    error: BaseException,
) -> None:
    with owner.condition:
        owner.error = error
        owner.owner_thread = None
        owner.state = _ROUTES_FAILED
        _mirror_route_owner(owner)
        owner.condition.notify_all()
    instance._vibecomfy_routes_registration_failed = True
    instance._vibecomfy_routes_registration_error = error


def _mark_route_ready(instance: Any, owner: _RouteRegistrationOwner) -> None:
    with owner.condition:
        owner.error = None
        owner.owner_thread = None
        owner.state = _ROUTES_READY
        _mirror_route_owner(owner)
        owner.condition.notify_all()
    instance._vibecomfy_routes_registered = True


def _bind_startup_audit(instance: Any, owner: _RouteRegistrationOwner) -> None:
    """Make the existing startup audit the final route-init phase."""
    app = getattr(instance, "app", None)
    startup = getattr(app, "on_startup", None)
    if startup is None or not startup:
        raise RuntimeError("VibeComfy route registration did not install startup audit")
    original_audit = startup[-1]

    async def _tracked_audit(startup_app: Any) -> Any:
        try:
            result = original_audit(startup_app)
            if inspect.isawaitable(result):
                result = await result
        except BaseException as error:
            _mark_route_failed(instance, owner, error)
            raise
        _mark_route_ready(instance, owner)
        return result

    startup[-1] = _tracked_audit


def _register_routes_once(
    instance: Any,
    owner: _RouteRegistrationOwner,
) -> None:

    prior_error = getattr(instance, "_vibecomfy_routes_registration_error", None)
    if getattr(instance, "_vibecomfy_routes_registration_failed", False):
        if isinstance(prior_error, BaseException):
            raise prior_error
        raise RuntimeError("VibeComfy route registration previously failed")

    # Guard against double registration. ComfyUI can import this module via
    # multiple paths (e.g. the custom_nodes symlink and the package itself),
    # which causes Python to execute it twice. PromptServer.instance is shared,
    # so a single marker there prevents duplicate aiohttp routes.
    if getattr(instance, "_vibecomfy_routes_registered", False):
        _LOGGER.info("VibeComfy routes already registered; skipping.")
        with owner.condition:
            if owner.state == _ROUTES_UNINITIALIZED:
                owner.state = _ROUTES_READY
                _mirror_route_owner(owner)
        return

    _LOGGER.info("PromptServer imported; registering VibeComfy routes.")
    try:
        from .http_security import (
            CSRF_BOOTSTRAP_PATH,
            csrf_bootstrap_response,
            install_http_namespace_middleware,
            register_http_route,
        )

        global _vibecomfy_ping, _vibecomfy_info, _vibecomfy_csrf_bootstrap

        @register_http_route(instance.routes, "GET", "/vibecomfy/ping")
        async def _vibecomfy_ping(request):  # type: ignore[no-untyped-def]
            from aiohttp import web

            return web.json_response({"status": "ok"})

        @register_http_route(instance.routes, "GET", "/vibecomfy/info")
        async def _vibecomfy_info(request):  # type: ignore[no-untyped-def]
            from aiohttp import web

            return web.json_response(_info_payload())

        @register_http_route(instance.routes, "GET", CSRF_BOOTSTRAP_PATH)
        async def _vibecomfy_csrf_bootstrap(request):  # type: ignore[no-untyped-def]
            return csrf_bootstrap_response()

        from .agent import routes  # noqa: F401

        install_http_namespace_middleware(instance)
        with owner.condition:
            owner.state = _ROUTES_REGISTERED
            _mirror_route_owner(owner)
        _bind_startup_audit(instance, owner)
        with owner.condition:
            owner.state = _ROUTES_PENDING_AUDIT
            _mirror_route_owner(owner)
        _LOGGER.info("VibeComfy routes registered successfully.")
    except BaseException as error:
        _mark_route_failed(instance, owner, error)
        raise


def _ensure_routes_registered() -> None:
    global _route_error, _route_owner_thread, _route_state
    current_thread = threading.get_ident()
    try:
        instance = _resolve_prompt_server_instance()
    except BaseException as error:
        with _route_condition:
            _route_error = error
            _route_owner_thread = None
            _route_state = _ROUTES_FAILED
            _route_condition.notify_all()
        raise
    owner = _route_registration_owner(instance)
    with owner.condition:
        while True:
            _mirror_route_owner(owner)
            if owner.state in {
                _ROUTES_REGISTERED,
                _ROUTES_PENDING_AUDIT,
                _ROUTES_READY,
            }:
                return
            if owner.state == _ROUTES_FAILED:
                error = owner.error
                if error is None:
                    raise RuntimeError("route registration failed without a diagnostic")
                raise error
            if owner.state == _ROUTES_LOADING:
                if owner.owner_thread == current_thread:
                    raise RuntimeError("route registration is not reentrant")
                owner.condition.wait()
                continue
            owner.state = _ROUTES_LOADING
            owner.owner_thread = current_thread
            _mirror_route_owner(owner)
            break

    try:
        _register_routes_once(instance, owner)
    except BaseException as error:
        if owner.state != _ROUTES_FAILED:
            _mark_route_failed(instance, owner, error)
        raise

    with owner.condition:
        if owner.state == _ROUTES_LOADING:
            error = RuntimeError(
                "VibeComfy route registration completed without a startup audit"
            )
            _mark_route_failed(instance, owner, error)
            raise error
        else:
            owner.owner_thread = None
            _mirror_route_owner(owner)
            owner.condition.notify_all()


if os.environ.get("VIBECOMFY_HEADLESS", "0") != "1":
    try:
        _ensure_routes_registered()
    except ImportError as _route_import_exc:
        _LOGGER.warning(
            "Could not register VibeComfy agent routes (%s); "
            "the ComfyUI server may not be available. "
            "POST /vibecomfy/agent-edit and /vibecomfy/agent/status will not be served.",
            _route_import_exc,
        )


def _strip_conditioning_keys(conditioning: list[Any], keys: set[str]) -> list[Any]:
    stripped: list[Any] = []
    for item in conditioning:
        if (
            isinstance(item, (list, tuple))
            and len(item) == 2
            and isinstance(item[1], dict)
        ):
            metadata = dict(item[1])
            for key in keys:
                metadata.pop(key, None)
            stripped.append([item[0], metadata])
        else:
            stripped.append(item)
    return stripped


class VibeComfyStripConditioningKeys:
    """Remove selected conditioning metadata keys while preserving embeddings."""

    @classmethod
    def INPUT_TYPES(cls) -> dict[str, Any]:
        return {
            "required": {
                "positive": ("CONDITIONING",),
                "negative": ("CONDITIONING",),
                "keys": (
                    "STRING",
                    {
                        "default": "guide_attention_entries",
                        "multiline": False,
                    },
                ),
            }
        }

    RETURN_TYPES = ("CONDITIONING", "CONDITIONING")
    RETURN_NAMES = ("positive", "negative")
    FUNCTION = "strip"
    CATEGORY = "conditioning/vibecomfy"
    SEARCH_ALIASES: list[str] = ["VibeComfy"]

    def strip(self, positive: list[Any], negative: list[Any], keys: str):
        key_set = {key.strip() for key in str(keys or "").split(",") if key.strip()}
        if not key_set:
            return positive, negative
        return (
            _strip_conditioning_keys(positive, key_set),
            _strip_conditioning_keys(negative, key_set),
        )


class _VibeComfyIntentNodeBase:
    CATEGORY = "vibecomfy/intent"
    RETURN_TYPES = ("*",)
    RETURN_NAMES = ("value",)
    FUNCTION = "passthrough"

    VIBECOMFY_EDITOR_ONLY = True
    VIBECOMFY_RUNTIME_BACKED = False
    VIBECOMFY_LOWERED = False
    VIBECOMFY_INTENT_NODE = True

    SEARCH_ALIASES: list[str] = ["VibeComfy"]

    @classmethod
    def INPUT_TYPES(cls) -> dict[str, Any]:
        return {
            "required": {
                "value": ("*",),
            }
        }

    def passthrough(self, value: Any, **_ignored: Any) -> tuple[Any]:
        return (value,)


class VibeComfyCodeIntent(_VibeComfyIntentNodeBase):
    VIBECOMFY_INTENT_KIND = "code"
    FUNCTION = "execute"
    VIBECOMFY_RUNTIME_BACKED = True

    # Class-level port surface is fixed at import time based on the flag.
    # execute() re-reads os.environ live so test harnesses can toggle the flag
    # after import without re-registering the node class.
    if os.environ.get("VIBECOMFY_CODE_DYNAMIC_IO", "0") == "1":
        RETURN_TYPES = ("*",) * _MAX_DYNAMIC_PORTS
        RETURN_NAMES = tuple(f"out_{i}" for i in range(_MAX_DYNAMIC_PORTS))

    @classmethod
    def INPUT_TYPES(cls) -> dict[str, Any]:
        if os.environ.get("VIBECOMFY_CODE_DYNAMIC_IO", "0") == "1":
            optional: dict[str, Any] = {
                **{f"in_{i}": ("*",) for i in range(_MAX_DYNAMIC_PORTS)},
                "source": ("STRING", {"default": "", "multiline": True}),
                "spec": ("STRING", {"default": "", "multiline": True}),
                "execution_mode": (
                    ["sandboxed_loose", "sandboxed_strict", "unrestricted"],
                    {"default": "sandboxed_loose"},
                ),
            }
            return {
                "optional": optional,
                "hidden": {
                    "unique_id": "UNIQUE_ID",
                    "prompt": "PROMPT",
                },
            }
        return {
            "required": {
                "value": ("*",),
            },
            "optional": {
                "runtime_backed": ("BOOLEAN", {"default": False}),
                "runtime_contract_version": ("STRING", {"default": "runtime_code_v1"}),
                "execution_mode": ("STRING", {"default": "expression_v1"}),
                "timeout_ms": ("INT", {"default": 1000, "min": 1, "max": 10000}),
                "max_source_bytes": ("INT", {"default": 16384, "min": 1, "max": 16384}),
                "allowed_builtins": ("JSON",),
                "redaction_policy": ("JSON",),
                "policy_version": ("STRING", {"default": "runtime_code_policy_v1"}),
                "passthrough_on_non_json": ("BOOLEAN", {"default": False}),
                "vibecomfy_uid": ("STRING", {"default": ""}),
                "kind": ("STRING", {"default": "code"}),
                "io": ("JSON",),
                "source": ("STRING", {"default": "", "multiline": True}),
                "spec": ("STRING", {"default": "", "multiline": True}),
            },
        }

    def execute(self, **kwargs: Any) -> tuple[Any, ...]:
        # Re-read os.environ directly so test harnesses toggling the flag after
        # import get the correct execution branch without re-importing the module.
        if os.environ.get("VIBECOMFY_CODE_DYNAMIC_IO", "0") != "1":
            from vibecomfy.comfy_nodes.agent.runtime_code import execute_runtime_code

            value = kwargs.pop("value", None)
            return (execute_runtime_code(value=value, **kwargs),)

        # --- Dynamic IO path (flag ON) ---
        unique_id = kwargs.get("unique_id")
        prompt = kwargs.get("prompt")

        # Defensive .get() chain: missing or unexpected types at any level are
        # treated as an empty dict rather than crashing execute().
        node_data: dict[str, Any] = {}
        if isinstance(prompt, dict) and unique_id is not None:
            raw = prompt.get(str(unique_id))
            if isinstance(raw, dict):
                node_data = raw

        meta = node_data.get("_meta")
        meta = meta if isinstance(meta, dict) else {}
        properties = meta.get("properties")
        if not isinstance(properties, dict) or not properties:
            raw_props = node_data.get("properties")
            properties = raw_props if isinstance(raw_props, dict) else {}

        raw_vibecomfy = properties.get("vibecomfy")
        # Prompt metadata belongs to ComfyUI's queued prompt. Copy the layers
        # we enrich below so a node execution never mutates that shared prompt.
        vibecomfy = dict(raw_vibecomfy) if isinstance(raw_vibecomfy, dict) else {}
        # Ensure the sub-dicts intent/runtime exist so downstream code
        # (runtime_code.py execute_runtime_code_dynamic, contract validator)
        # does not need its own defensive get chains.
        existing_intent = vibecomfy.get("intent")
        vibecomfy["intent"] = dict(existing_intent) if isinstance(existing_intent, dict) else {}
        existing_runtime = vibecomfy.get("runtime")
        vibecomfy["runtime"] = dict(existing_runtime) if isinstance(existing_runtime, dict) else {}

        # --- Widget-to-property roundtrip: source / spec / execution_mode ---
        _NEW_MODE_SET = frozenset({"sandboxed_loose", "sandboxed_strict", "unrestricted"})

        widget_source: str = str(kwargs.get("source", ""))
        widget_spec: str = str(kwargs.get("spec", ""))
        widget_mode: str = str(kwargs.get("execution_mode", "sandboxed_loose"))

        # Validate widget mode against the bare set; ignore unrecognised.
        if widget_mode not in _NEW_MODE_SET:
            widget_mode = vibecomfy.get("execution_mode", "sandboxed_loose")
            if widget_mode not in _NEW_MODE_SET:
                widget_mode = "sandboxed_loose"

        # Write non-empty widget source/spec into intent; fall back to
        # property source when the widget is empty (preserves agent-authored
        # code that predates the widget).
        intent: dict[str, Any] = vibecomfy["intent"]
        if widget_source.strip():
            intent["source"] = widget_source
        elif "source" not in intent:
            intent["source"] = ""
        if widget_spec.strip():
            intent["spec"] = widget_spec
        elif "spec" not in intent:
            intent["spec"] = ""

        # Dynamic CodeIntent widgets are the live runtime contract. The
        # executor validates vibecomfy.runtime, not the historical top-level
        # execution_mode, so copy every contract field before dispatch.
        runtime: dict[str, Any] = vibecomfy["runtime"]
        runtime_widget_fields = (
            "runtime_backed", "runtime_contract_version", "timeout_ms",
            "max_source_bytes", "allowed_builtins", "allowed_imports",
            "redaction_policy", "policy_version", "passthrough_on_non_json",
            "unrestricted_ack",
        )
        has_widget_runtime = any(field in kwargs for field in runtime_widget_fields)
        for field in runtime_widget_fields:
            if field in kwargs:
                runtime[field] = kwargs[field]
        # Preserve the defensive missing-prompt shape for callers which only
        # inspect metadata; an actual runtime contract always has either saved
        # runtime data or one of the runtime widget fields above.
        if runtime or has_widget_runtime:
            runtime["execution_mode"] = widget_mode
        vibecomfy["execution_mode"] = widget_mode

        io = vibecomfy.get("io")
        io = io if isinstance(io, dict) else {}
        inputs_spec = io.get("inputs")
        inputs_spec = inputs_spec if isinstance(inputs_spec, list) else []

        # Remap in_i kwargs to user-declared names from io.inputs[i].
        # Slots beyond the declared inputs_spec are silently dropped.
        named_inputs: dict[str, Any] = {}
        for i in range(_MAX_DYNAMIC_PORTS):
            slot_key = f"in_{i}"
            if slot_key not in kwargs:
                continue
            if i < len(inputs_spec):
                entry = inputs_spec[i]
                if isinstance(entry, (list, tuple)) and entry and isinstance(entry[0], str):
                    named_inputs[entry[0]] = kwargs[slot_key]
                else:
                    named_inputs[slot_key] = kwargs[slot_key]

        from vibecomfy.comfy_nodes.agent.runtime_code import execute_runtime_code_dynamic

        result_dict = execute_runtime_code_dynamic(
            named_inputs=named_inputs,
            vibecomfy_props=vibecomfy,
        )

        # Map declared output names to the 16-slot tuple; unused trailing slots are None.
        outputs_spec = io.get("outputs")
        outputs_spec = outputs_spec if isinstance(outputs_spec, list) else []
        output_names: list[str] = []
        for entry in outputs_spec:
            if isinstance(entry, (list, tuple)) and entry and isinstance(entry[0], str):
                output_names.append(entry[0])

        result_list: list[Any] = [None] * _MAX_DYNAMIC_PORTS
        for i, name in enumerate(output_names[:_MAX_DYNAMIC_PORTS]):
            result_list[i] = result_dict.get(name)

        return tuple(result_list)


class VibeComfyLoopIntent(_VibeComfyIntentNodeBase):
    VIBECOMFY_INTENT_KIND = "loop"


NODE_CLASS_MAPPINGS = {
    # Lowercase canonical key (what the agent edit engine emits) plus the
    # CamelCase legacy alias; both resolve to the same class.
    "vibecomfy.strip_conditioning_keys": VibeComfyStripConditioningKeys,
    "VibeComfyStripConditioningKeys": VibeComfyStripConditioningKeys,
    EXEC_CLASS_TYPE: VibeComfyExec,
    KIND_TO_CLASS_TYPE["code"]: VibeComfyCodeIntent,
    KIND_TO_CLASS_TYPE["loop"]: VibeComfyLoopIntent,
}

NODE_DISPLAY_NAME_MAPPINGS = {
    "vibecomfy.strip_conditioning_keys": "VibeComfy Strip Conditioning Keys",
    "VibeComfyStripConditioningKeys": "VibeComfy Strip Conditioning Keys",
    EXEC_CLASS_TYPE: "VibeComfy Exec",
    KIND_TO_CLASS_TYPE["code"]: "VibeComfy Code Intent",
    KIND_TO_CLASS_TYPE["loop"]: "VibeComfy Loop Intent",
}
