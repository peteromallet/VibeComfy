"""ComfyUI adapter for the executor's neutral host-port contract.

The orchestration package owns no provider exceptions, runtime capture
context, edit entrypoint, or durable hashing implementation. This module is
the single inward-facing adapter for those ComfyUI-owned details.
"""

from __future__ import annotations

from functools import partial

from vibecomfy.executor.contracts import ExecutorHostPorts

from .contracts import classify_failure, failure_envelope
from .edit import _SESSION_ROOT, handle_agent_edit
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
from .session import (
    _thread_abort,
    _thread_append,
    _thread_begin,
    _thread_close,
    _thread_complete,
    _thread_load,
    payload_hash,
)


def build_executor_host_ports() -> ExecutorHostPorts:
    """Build the production implementation of the executor host seam."""
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
        thread_load=partial(_thread_load, _SESSION_ROOT),
        thread_begin=partial(_thread_begin, session_root=_SESSION_ROOT),
        thread_append=partial(_thread_append, session_root=_SESSION_ROOT),
        thread_complete=partial(_thread_complete, session_root=_SESSION_ROOT),
        thread_abort=partial(_thread_abort, session_root=_SESSION_ROOT),
        thread_close=partial(_thread_close, session_root=_SESSION_ROOT),
    )


__all__ = ["build_executor_host_ports"]
