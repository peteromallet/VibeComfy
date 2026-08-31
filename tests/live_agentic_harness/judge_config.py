"""Explicit, preflighted configuration for live-harness LLM judges."""

from __future__ import annotations

from dataclasses import asdict, dataclass
from typing import Any


DEFAULT_JUDGE_ROUTE = "deepseek"
DEFAULT_JUDGE_MODEL = "deepseek-v4-pro"


class JudgeReadinessError(RuntimeError):
    """Raised before paid execution when the configured judge cannot run."""


@dataclass(frozen=True)
class JudgeConfig:
    route: str = DEFAULT_JUDGE_ROUTE
    model: str = DEFAULT_JUDGE_MODEL

    def as_dict(self) -> dict[str, str]:
        return asdict(self)


def resolve_judge_config(
    route: str | None = None,
    model: str | None = None,
) -> JudgeConfig:
    """Resolve optional caller values without consulting ambient credentials."""
    resolved_route = str(route if route is not None else DEFAULT_JUDGE_ROUTE).strip()
    resolved_model = str(model if model is not None else DEFAULT_JUDGE_MODEL).strip()
    if not resolved_route or not resolved_model:
        raise ValueError("judge route and model must be non-empty explicit strings")
    return JudgeConfig(route=resolved_route, model=resolved_model)


def require_judge_readiness(config: JudgeConfig) -> dict[str, Any]:
    """Fail before product dispatch unless *config* has a usable provider."""
    # Use the same public provider seam as judge execution. Its route/model
    # resolution and adapter registration must agree with ``run_model_turn``.
    from vibecomfy.comfy_nodes.agent.provider import readiness

    status = dict(readiness(route=config.route, model=config.model))
    public_keys = {
        "adapter",
        "backend",
        "codex_adapter_registered",
        "codex_auth_present",
        "codex_cli_present",
        "model",
        "normalized_route",
        "provider",
        "provider_available",
        "ready",
        "reason",
        "requested_route",
        "route",
        "transport",
    }
    receipt = {key: status[key] for key in public_keys if key in status}
    receipt["requested_route"] = config.route
    receipt["requested_model"] = config.model
    if status.get("ready") is not True:
        reason = status.get("reason") or "configured judge provider is unavailable"
        raise JudgeReadinessError(
            f"judge preflight failed for {config.route}:{config.model}: {reason}"
        )
    resolved_model = status.get("model")
    if (
        isinstance(resolved_model, str)
        and resolved_model.strip()
        and resolved_model != config.model
    ):
        raise JudgeReadinessError(
            "judge preflight resolved a different model than requested: "
            f"requested={config.model!r} resolved={resolved_model!r}"
        )
    return receipt


__all__ = [
    "DEFAULT_JUDGE_MODEL",
    "DEFAULT_JUDGE_ROUTE",
    "JudgeConfig",
    "JudgeReadinessError",
    "require_judge_readiness",
    "resolve_judge_config",
]
