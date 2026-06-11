from __future__ import annotations

import json
import os
from dataclasses import dataclass, field, replace
from typing import TYPE_CHECKING, Any

from vibecomfy.memory_profile import MemoryProfile, apply_memory_profile_overrides
from vibecomfy.workflow import VibeWorkflow

if TYPE_CHECKING:
    from comfy.cli_args_types import Configuration
else:
    Configuration = Any


@dataclass(slots=True)
class SessionConfig:
    memory_profile: MemoryProfile | None = None
    vram_policy: str = "auto"
    reserve_vram_gb: float | None = None
    cache_policy: str = "smart"
    disable_smart_memory: bool = False
    warm_policy: str = "auto"
    auto_flush_vram_threshold_gb: float = 2.0
    port: int | None = None
    extra: dict[str, Any] = field(default_factory=dict)

    @classmethod
    def from_dict(cls, values: dict[str, Any]) -> "SessionConfig":
        kwargs, extra = _partition_comfy_config(values)
        return cls(**kwargs, extra=extra)

    @classmethod
    def from_workflow_metadata(cls, workflow: VibeWorkflow) -> "SessionConfig":
        values = workflow.metadata.get("comfy_configuration", {})
        if not isinstance(values, dict):
            values = {}
        return cls.from_dict(values)


def apply_memory_profile_override(
    config: SessionConfig,
    memory_profile: int | MemoryProfile,
) -> SessionConfig:
    profile = MemoryProfile.parse(memory_profile)
    resolved = apply_memory_profile_overrides(config, profile, precedence="profile")
    return replace(resolved, memory_profile=profile)


def _partition_comfy_config(values: dict[str, Any]) -> tuple[dict[str, Any], dict[str, Any]]:
    """Split mixed config into SessionConfig kwargs and raw extra Comfy keys.

    HiddenSwitch keys are translated first, then typed SessionConfig field
    names overwrite translated values when both forms are present.
    """
    typed_fields = {
        "memory_profile",
        "port",
        "vram_policy",
        "cache_policy",
        "warm_policy",
        "reserve_vram_gb",
        "disable_smart_memory",
        "auto_flush_vram_threshold_gb",
    }
    kwargs: dict[str, Any] = {}
    extra: dict[str, Any] = {}

    if "memory_profile" in values and values["memory_profile"] is not None:
        profile = MemoryProfile.parse(values["memory_profile"])
        kwargs["memory_profile"] = profile
        kwargs.update(profile.to_session_overrides())

    for key, value in values.items():
        if key in typed_fields:
            continue
        if key == "reserve_vram":
            kwargs["reserve_vram_gb"] = value
        elif key in {"highvram", "lowvram", "normalvram"}:
            if value:
                kwargs["vram_policy"] = key.removesuffix("vram")
        elif key == "cache_none":
            if value:
                kwargs["cache_policy"] = "none"
        elif key == "cache_classic":
            if value:
                kwargs["cache_policy"] = "classic"
        elif key == "cache_lru":
            if value:
                kwargs["cache_policy"] = f"lru:{value}"
        else:
            extra[key] = value

    for key, value in values.items():
        if key in typed_fields and key != "memory_profile":
            kwargs[key] = value

    return kwargs, extra


def _embedded_configuration_for_session(config: SessionConfig) -> Configuration | None:
    values: dict[str, Any] = {}
    if config.port is not None:
        values["port"] = config.port
    if config.vram_policy in {"high", "low", "normal"}:
        values[f"{config.vram_policy}vram"] = True
    if config.reserve_vram_gb is not None:
        values["reserve_vram"] = config.reserve_vram_gb
    if config.cache_policy == "classic":
        values["cache_classic"] = True
    elif config.cache_policy == "none":
        values["cache_none"] = True
    elif config.cache_policy.startswith("lru:"):
        values["cache_lru"] = int(config.cache_policy.split(":", 1)[1])
    if config.disable_smart_memory:
        values["disable_smart_memory"] = True

    values.update(config.extra)
    env_config = os.environ.get("VIBECOMFY_COMFY_CONFIGURATION")
    if env_config:
        parsed = json.loads(env_config)
        if not isinstance(parsed, dict):
            raise ValueError("VIBECOMFY_COMFY_CONFIGURATION must be a JSON object")
        values.update(parsed)
    if not values:
        return None

    from comfy.client.embedded_comfy_client import default_configuration

    configuration = default_configuration()
    configuration.update(values)
    return configuration


def _embedded_configuration(workflow: VibeWorkflow) -> Configuration | None:
    return _embedded_configuration_for_session(SessionConfig.from_workflow_metadata(workflow))


def _comfy_server_argv(config: SessionConfig) -> tuple[str, ...]:
    from .server_process import _comfyui_executable

    argv = [_comfyui_executable(), "serve"]
    if config.vram_policy in {"high", "low", "normal"}:
        argv.append(f"--{config.vram_policy}vram")
    if config.reserve_vram_gb is not None:
        argv.extend(["--reserve-vram", str(config.reserve_vram_gb)])
    if config.disable_smart_memory:
        argv.append("--disable-smart-memory")
    if config.cache_policy == "classic":
        argv.append("--cache-classic")
    elif config.cache_policy == "none":
        argv.append("--cache-none")
    elif config.cache_policy.startswith("lru:"):
        argv.extend(["--cache-lru", config.cache_policy.split(":", 1)[1]])
    argv.extend(["--port", str(config.port or 8188)])
    return tuple(argv)
