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

import os
from typing import Any

from .exec_node import EXEC_CLASS_TYPE, VibeComfyExec
from vibecomfy.contracts.intent_nodes import KIND_TO_CLASS_TYPE

_MAX_DYNAMIC_PORTS = 16

WEB_DIRECTORY = "./web"

try:
    from server import PromptServer

    @PromptServer.instance.routes.get("/vibecomfy/ping")
    async def _vibecomfy_ping(request):  # type: ignore[no-untyped-def]
        from aiohttp import web

        return web.json_response({"status": "ok"})

    from .agent import routes  # noqa: F401

except ImportError:
    pass


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
