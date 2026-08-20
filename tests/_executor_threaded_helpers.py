"""Shared deterministic substrate for threaded-executor contract tests."""

from __future__ import annotations

import importlib
import json
from dataclasses import replace
from functools import partial
from pathlib import Path
from typing import Any

import pytest


FEATURE_GUARD_REASON = (
    "canonical threaded driver, durable thread hooks, and shared IR edit kernel "
    "must be available together"
)

# This is the suite's single feature-availability guard.  Keep it at the shared
# import boundary so every assertion becomes mandatory as soon as the planned
# threaded substrate is fully present.
try:
    threaded = importlib.import_module("vibecomfy.executor.threaded")
    executor_core = importlib.import_module("vibecomfy.executor.core")
    executor_contracts = importlib.import_module("vibecomfy.executor.contracts")
    edit_kernel = importlib.import_module("vibecomfy.porting.edit")
    thread_store = importlib.import_module("vibecomfy.comfy_nodes.agent.session")

    for module, names in (
        (
            threaded,
            (
                "THREADED_MAX_AGENT_BATCHES",
                "ThreadedPurposeBudget",
                "run_threaded_executor",
            ),
        ),
        (
            executor_contracts,
            (
                "ExecutorHostPorts",
                "ExecutorRequest",
                "ExecutorResult",
                "coerce_orchestration_mode",
                "resolve_orchestration_mode",
            ),
        ),
        (
            edit_kernel,
            (
                "ClaimReferenceError",
                "EditSession",
                "apply_edit_tool_call",
                "close_terminal_checkpoint",
                "lower_edit_tool_call",
            ),
        ),
        (
            thread_store,
            (
                "_ThreadSessionError",
                "_thread_abort",
                "_thread_append",
                "_thread_begin",
                "_thread_close",
                "_thread_complete",
                "_thread_load",
            ),
        ),
    ):
        for name in names:
            getattr(module, name)
except (AttributeError, ImportError, ModuleNotFoundError):
    THREADED_FEATURE_AVAILABLE = False
    threaded = None
    executor_core = None
    executor_contracts = None
    edit_kernel = None
    thread_store = None
else:
    THREADED_FEATURE_AVAILABLE = True

THREADED_FEATURE_REQUIRED = pytest.mark.skipif(
    not THREADED_FEATURE_AVAILABLE, reason=FEATURE_GUARD_REASON
)

if THREADED_FEATURE_AVAILABLE:
    ExecutorHostPorts = executor_contracts.ExecutorHostPorts
    ExecutorRequest = executor_contracts.ExecutorRequest
    ExecutorResult = executor_contracts.ExecutorResult
    ThreadSessionError = thread_store._ThreadSessionError
else:
    ExecutorHostPorts = object
    ExecutorRequest = object
    ExecutorResult = object
    ThreadSessionError = RuntimeError

_FIXTURE = Path(__file__).parent / "fixtures" / "executor" / "threaded_ir.json"


class LawSchemaProvider:
    """Offline schemas for the focused threaded IR fixture."""

    def __init__(self) -> None:
        from vibecomfy.schema import InputSpec, NodeSchema, OutputSpec

        self._schemas = {
            "LawNodeA": NodeSchema(
                "LawNodeA", "threaded-test", {}, [OutputSpec("IMAGE", "IMAGE")]
            ),
            "LawNodeB": NodeSchema(
                "LawNodeB", "threaded-test", {}, [OutputSpec("IMAGE", "IMAGE")]
            ),
            "LawNodeC": NodeSchema(
                "LawNodeC",
                "threaded-test",
                {"image": InputSpec("IMAGE"), "prompt": InputSpec("STRING")},
                [],
            ),
        }

    def get_schema(self, class_type: str) -> Any:
        return self._schemas.get(class_type)


def fixture_graph() -> dict[str, Any]:
    return json.loads(_FIXTURE.read_text(encoding="utf-8"))


def edit_session() -> Any:
    return edit_kernel.EditSession(
        fixture_graph(), schema_provider=LawSchemaProvider()
    )


class _Failure:
    kind = type("Kind", (), {"value": "ValidationError"})()
    user_facing_message = "failed"


def host_ports(session_root: Path | None = None) -> Any:
    """Return neutral executor ports, optionally bound to a temporary store."""

    ports = ExecutorHostPorts(
        handle_agent_edit=lambda *args, **kwargs: {},
        payload_hash=thread_store.payload_hash,
        classify_failure=lambda *args, **kwargs: _Failure(),
        failure_envelope=lambda *args, **kwargs: _Failure(),
        begin_deepseek_usage_capture=lambda: object(),
        snapshot_deepseek_usage_capture=lambda: ({}, False),
        end_deepseek_usage_capture=lambda token: None,
        begin_model_attempt_capture=lambda: object(),
        snapshot_model_attempt_capture=lambda: (),
        end_model_attempt_capture=lambda token: None,
    )
    if session_root is None:
        return ports
    return replace(
        ports,
        thread_load=partial(thread_store._thread_load, session_root),
        thread_begin=partial(thread_store._thread_begin, session_root=session_root),
        thread_append=partial(thread_store._thread_append, session_root=session_root),
        thread_complete=partial(thread_store._thread_complete, session_root=session_root),
        thread_abort=partial(thread_store._thread_abort, session_root=session_root),
        thread_close=partial(thread_store._thread_close, session_root=session_root),
    )
