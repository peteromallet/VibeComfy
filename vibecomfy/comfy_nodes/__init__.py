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
import time
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
_MODULE_START_MONOTONIC = time.monotonic()
_INFO_LAUNCH_FLAG_NAMES = (
    "VIBECOMFY_HEADLESS",
    "VIBECOMFY_CODE_DYNAMIC_IO",
    "VIBECOMFY_ARNOLD_RUNTIME_MODULE",
    "VIBECOMFY_DEMO_PICKER",
    "VIBECOMFY_AGENTIC_REPLAY",
)


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


def _launch_flags_snapshot() -> dict[str, str | None]:
    return {
        name: os.environ.get(name)
        for name in _INFO_LAUNCH_FLAG_NAMES
    }


def _resolve_served_web_path() -> str:
    relative = WEB_DIRECTORY.removeprefix("./")
    return str((_MODULE_DIR / relative).resolve())


def _git_info_snapshot() -> tuple[dict[str, Any], dict[str, Any] | None]:
    from vibecomfy._git_utils import git_stdout_result
    from vibecomfy.commands._diagnostics import diagnostic_to_json
    from vibecomfy.utils import find_repo_root

    repo_root = find_repo_root()

    sha: str | None = None
    session_git_error: Exception | None = None
    try:
        from vibecomfy.runtime.session import current_source_revision
    except Exception as exc:  # pragma: no cover - defensive fallback
        session_git_error = exc
    else:
        try:
            sha = current_source_revision()
        except Exception as exc:  # pragma: no cover - defensive fallback
            session_git_error = exc

    sha_result = None
    if sha is None:
        sha_result = git_stdout_result(repo_root, ["rev-parse", "HEAD"])
        sha = (sha_result.stdout or "").strip() or None

    branch_result = git_stdout_result(repo_root, ["rev-parse", "--abbrev-ref", "HEAD"])
    branch = (branch_result.stdout or "").strip() or None

    dirty_result = git_stdout_result(repo_root, ["status", "--porcelain"])
    dirty_stdout = dirty_result.stdout
    dirty = None if dirty_stdout is None else bool(dirty_stdout.strip())

    diagnostic: dict[str, Any] | None = None
    for result in (sha_result, branch_result, dirty_result):
        if result is not None and result.diagnostic is not None:
            diagnostic = diagnostic_to_json(result.diagnostic)
            break
    if diagnostic is None and session_git_error is not None and sha is None:
        diagnostic = {
            "code": "git_helper_unavailable",
            "message": str(session_git_error),
            "severity": "error",
            "recoverable": True,
        }

    return {
        "sha": sha,
        "branch": branch,
        "dirty": dirty,
    }, diagnostic


def _info_payload() -> dict[str, Any]:
    git, git_diagnostic = _git_info_snapshot()
    payload: dict[str, Any] = {
        "start_time_utc": _utc_isoformat(_MODULE_START_AT_UTC),
        "uptime_seconds": max(0.0, round(time.monotonic() - _MODULE_START_MONOTONIC, 3)),
        "WEB_DIRECTORY": WEB_DIRECTORY,
        "web_source_hash": _web_source_hash(),
        "web_source_path": str(_WEB_SRC_DIR.resolve()),
        "web_dist_path": str(_WEB_DIST_DIR.resolve()),
        "served_web_path": _resolve_served_web_path(),
        "launch_flags": _launch_flags_snapshot(),
        "git_sha": git["sha"],
        "git_branch": git["branch"],
        "git_dirty": git["dirty"],
        "git_diagnostic": git_diagnostic,
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


if os.environ.get("VIBECOMFY_HEADLESS", "0") != "1":
    _ensure_comfyui_root_on_path()

    try:
        from ._server_compat import import_prompt_server

        PromptServer = import_prompt_server()

        # Guard against double registration. ComfyUI can import this module via
        # multiple paths (e.g. the custom_nodes symlink and the package itself),
        # which causes Python to execute it twice. PromptServer.instance is shared,
        # so a single marker there prevents duplicate aiohttp routes.
        if getattr(PromptServer.instance, "_vibecomfy_routes_registered", False):
            _LOGGER.info("VibeComfy routes already registered; skipping.")
        else:
            PromptServer.instance._vibecomfy_routes_registered = True
            _LOGGER.info("PromptServer imported; registering VibeComfy routes.")

            @PromptServer.instance.routes.get("/vibecomfy/ping")
            async def _vibecomfy_ping(request):  # type: ignore[no-untyped-def]
                from aiohttp import web

                return web.json_response({"status": "ok"})

            @PromptServer.instance.routes.get("/vibecomfy/info")
            async def _vibecomfy_info(request):  # type: ignore[no-untyped-def]
                from aiohttp import web

                return web.json_response(_info_payload())

            from .agent import routes  # noqa: F401

            _LOGGER.info("VibeComfy routes registered successfully.")

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

        vibecomfy = properties.get("vibecomfy")
        vibecomfy = vibecomfy if isinstance(vibecomfy, dict) else {}
        # Ensure the sub-dicts intent/runtime exist so downstream code
        # (runtime_code.py execute_runtime_code_dynamic, contract validator)
        # does not need its own defensive get chains.
        vibecomfy.setdefault("intent", {})
        vibecomfy.setdefault("runtime", {})

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
    "VibeComfyStripConditioningKeys": VibeComfyStripConditioningKeys,
    EXEC_CLASS_TYPE: VibeComfyExec,
    KIND_TO_CLASS_TYPE["code"]: VibeComfyCodeIntent,
    KIND_TO_CLASS_TYPE["loop"]: VibeComfyLoopIntent,
}

NODE_DISPLAY_NAME_MAPPINGS = {
    "VibeComfyStripConditioningKeys": "VibeComfy Strip Conditioning Keys",
    EXEC_CLASS_TYPE: "VibeComfy Exec",
    KIND_TO_CLASS_TYPE["code"]: "VibeComfy Code Intent",
    KIND_TO_CLASS_TYPE["loop"]: "VibeComfy Loop Intent",
}
