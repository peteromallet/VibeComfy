from __future__ import annotations

"""Concurrency contract tests for workflow_context module.

Covers 6 contracts:
1. Nested new_workflow raises RuntimeError
2. asyncio.gather isolates active workflows per task
3. Threads each build a workflow without cross-contamination
4. Post-exit: compile works, context-bound node() fails with remediation message
5. _current_workflow_or_raise() outside context includes remediation message
6. ContextVar survives await inside async build body

Includes at least one scenario exercising templates.node('ClassType', ...)
(the real caller path) per callers-1 flag.
"""

import asyncio
import threading
from typing import Any

import pytest

from vibecomfy.templates import new_workflow, node as templates_node
from vibecomfy.workflow import VibeWorkflow
from vibecomfy.workflow_context import _current_workflow_or_raise, active_workflow

# Minimal metadata for new_workflow()
_METADATA: dict[str, Any] = {"ready_template": "test/context"}


# ---------------------------------------------------------------------------
# Contract 1: nested new_workflow(...) raises RuntimeError
# ---------------------------------------------------------------------------


def test_nested_new_workflow_raises_runtime_error() -> None:
    """Nested with new_workflow(...) raises the existing RuntimeError 
    from workflow_context.bind_workflow."""
    with new_workflow(_METADATA) as wf1:
        assert wf1 is not None
        with pytest.raises(RuntimeError, match="Nested workflow contexts"):
            with new_workflow(_METADATA):
                pass  # pragma: no cover


# ---------------------------------------------------------------------------
# Contract 2: asyncio.gather isolates active workflows per task
# ---------------------------------------------------------------------------


@pytest.mark.asyncio
async def test_asyncio_gather_isolates_workflows() -> None:
    """Each asyncio task sees only its own workflow."""
    results: list[tuple[int, str | None]] = []

    async def build_in_context(task_id: int) -> tuple[int, str | None]:
        metadata = {"ready_template": f"test/context-{task_id}"}
        with new_workflow(metadata) as wf:
            # Use the templates.node() real caller path
            node_builder = templates_node("LoadImage", image="test.png")
            wf_id = wf.id
            # Verify _current_workflow_or_raise returns this workflow
            current = _current_workflow_or_raise()
            assert current.id == wf_id
            return (task_id, wf_id)

    tasks = [build_in_context(i) for i in range(3)]
    gathered = await asyncio.gather(*tasks)

    ids = [wf_id for _, wf_id in gathered]
    # All three should be different (each task had its own workflow)
    assert len(set(ids)) == 3, f"Expected 3 distinct workflows, got {ids}"
    # No cross-contamination
    for i, (task_id, wf_id) in enumerate(gathered):
        assert wf_id is not None
        assert f"context-{task_id}" in wf_id


# ---------------------------------------------------------------------------
# Contract 3: two threads each build a workflow without cross-contamination
# ---------------------------------------------------------------------------


def test_thread_isolation() -> None:
    """Two threads each build a workflow without node cross-contamination."""
    thread_results: list[dict[str, Any]] = []

    def build_in_thread(thread_id: int) -> None:
        metadata = {"ready_template": f"test/thread-{thread_id}"}
        with new_workflow(metadata) as wf:
            # Use templates.node() real caller path
            node_builder = templates_node("LoadImage", image=f"thread-{thread_id}.png")
            wf_id = wf.id
            current = _current_workflow_or_raise()
            assert current.id == wf_id
            thread_results.append({
                "thread_id": thread_id,
                "wf_id": wf_id,
                "node_count": len(wf.nodes),
            })

    t1 = threading.Thread(target=build_in_thread, args=(1,))
    t2 = threading.Thread(target=build_in_thread, args=(2,))
    t1.start()
    t2.start()
    t1.join()
    t2.join()

    assert len(thread_results) == 2
    # Each thread should have built a workflow with exactly 1 node (LoadImage)
    for result in thread_results:
        assert result["node_count"] == 1
        assert f"thread-{result['thread_id']}" in result["wf_id"]

    # Verify the two workflows are different objects
    wf_ids = [r["wf_id"] for r in thread_results]
    assert wf_ids[0] != wf_ids[1]


# ---------------------------------------------------------------------------
# Contract 4: post-exit compile works, context-bound node() fails
# ---------------------------------------------------------------------------


def test_post_exit_compile_works_node_fails() -> None:
    """After context exit, wf.compile('api') works but context-bound
    node() fails with remediation message."""
    wf: VibeWorkflow | None = None

    with new_workflow(_METADATA) as wf_inner:
        wf_inner.add_node("LoadImage", image="post.png")
        wf = wf_inner

    assert wf is not None

    # compile('api') should still work — the workflow object is independent
    api = wf.compile("api")
    assert api is not None
    assert len(api) == 1

    # Active workflow should be None outside context
    assert active_workflow() is None

    # _current_workflow_or_raise() should fail with remediation message
    with pytest.raises(RuntimeError, match="No active workflow"):
        _current_workflow_or_raise()

    # templates.node() should fail because it calls _current_workflow_or_raise()
    with pytest.raises(RuntimeError, match="No active workflow"):
        templates_node("LoadImage", image="should-fail.png")


# ---------------------------------------------------------------------------
# Contract 5: _current_workflow_or_raise() outside context includes
#              the 'with new_workflow(...)' remediation message
# ---------------------------------------------------------------------------


def test_current_workflow_or_raise_outside_context_remediation_message() -> None:
    """The error message from _current_workflow_or_raise() outside a context
    includes the v2.7 with-less `wf = new_workflow(...)` remediation hint."""
    # Ensure we are outside any context
    assert active_workflow() is None

    with pytest.raises(RuntimeError) as exc_info:
        _current_workflow_or_raise()

    message = str(exc_info.value)
    assert "wf = new_workflow(" in message, (
        f"Remediation message missing. Got: {message}"
    )
    assert "No active workflow" in message


# ---------------------------------------------------------------------------
# Contract 6: ContextVar survives await inside a build body
# ---------------------------------------------------------------------------


@pytest.mark.asyncio
async def test_contextvar_survives_await() -> None:
    """The ContextVar survives an await inside an async def using the context."""

    async def async_operation() -> str:
        # Simulate an async operation
        await asyncio.sleep(0)
        return "done"

    async def build_with_await() -> VibeWorkflow:
        with new_workflow({"ready_template": "test/async-context"}) as wf:
            # Context is bound before await
            assert active_workflow() is not None
            assert active_workflow().id == wf.id

            # Await — context should survive
            result = await async_operation()
            assert result == "done"

            # After await, context should still be bound
            assert active_workflow() is not None
            assert active_workflow().id == wf.id

            # Use templates.node() — the real caller path
            node_builder = templates_node("LoadImage", image="async-test.png")
            assert wf.id in active_workflow().id  # type: ignore[union-attr]

            return wf

    wf_result = await build_with_await()
    assert wf_result is not None
    assert len(wf_result.nodes) == 1

    # After context exit, verify context is unbound
    assert active_workflow() is None
