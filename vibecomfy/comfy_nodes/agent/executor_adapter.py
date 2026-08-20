"""ComfyUI-agent adapter for the neutral executor host-port contract.

The executor orchestration layer owns no provider exception classes, capture
context variables, edit entrypoint, or session hashing implementation.  This
module is the single inward-facing adapter for those ComfyUI-owned details.
"""

from __future__ import annotations

from vibecomfy.executor.contracts import ExecutorHostPorts

from .contracts import classify_failure, failure_envelope
from .edit import handle_agent_edit
from .provider import (
    AuthError,
    MalformedModelJSON,
    MissingRequiredField,
    ProviderError,
)
from .runtime import (
    begin_deepseek_usage_capture,
    begin_model_attempt_capture,
    end_deepseek_usage_capture,
    end_model_attempt_capture,
    snapshot_deepseek_usage_capture,
    snapshot_model_attempt_capture,
)
from .session import payload_hash


def build_executor_host_ports() -> ExecutorHostPorts:
    """Return the production ComfyUI implementation of executor host ports."""
    return ExecutorHostPorts(
        handle_agent_edit=handle_agent_edit,
        payload_hash=payload_hash,
        classify_failure=classify_failure,
        failure_envelope=failure_envelope,
        begin_deepseek_usage_capture=begin_deepseek_usage_capture,
        snapshot_deepseek_usage_capture=snapshot_deepseek_usage_capture,
        end_deepseek_usage_capture=end_deepseek_usage_capture,
        begin_model_attempt_capture=begin_model_attempt_capture,
        snapshot_model_attempt_capture=snapshot_model_attempt_capture,
        end_model_attempt_capture=end_model_attempt_capture,
        provider_error_types=(
            ProviderError,
            AuthError,
            MalformedModelJSON,
            MissingRequiredField,
            TimeoutError,
        ),
    )


__all__ = ["build_executor_host_ports"]
