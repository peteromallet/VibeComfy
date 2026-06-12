from __future__ import annotations

from typing import Any

from .exec_node import EXEC_CLASS_TYPE, VibeComfyExec
from vibecomfy.contracts.intent_nodes import KIND_TO_CLASS_TYPE

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

    @classmethod
    def INPUT_TYPES(cls) -> dict[str, Any]:
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

    def execute(self, value: Any, **kwargs: Any) -> tuple[Any]:
        from vibecomfy.comfy_nodes.agent.runtime_code import execute_runtime_code

        return (execute_runtime_code(value=value, **kwargs),)


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
