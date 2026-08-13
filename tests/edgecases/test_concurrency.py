from __future__ import annotations

"""Edge case: concurrency safety.

Verifies that multiple conversions running concurrently (threads and
async) do not interfere with each other.
"""

import asyncio
import concurrent.futures
import threading

import pytest

from vibecomfy.porting.convert import port_convert_workflow
from vibecomfy.workflow import VibeEdge, VibeNode, VibeWorkflow, WorkflowSource


def _make_workflow(seed: int) -> VibeWorkflow:
    """Create a workflow with a unique identifier based on seed."""
    wf = VibeWorkflow(
        f"concurrent-{seed}",
        WorkflowSource(f"source/concurrent_{seed}", source_type="api"),
    )
    wf.nodes["1"] = VibeNode("1", "LoadImage", inputs={"image": f"img_{seed}.png"})
    wf.nodes["2"] = VibeNode(
        "2", "SaveImage", inputs={"filename_prefix": f"out/conc_{seed}"}
    )
    wf.edges.append(VibeEdge("1", "0", "2", "images"))
    return wf


def test_concurrent_thread_conversions() -> None:
    """Multiple threads converting workflows should not interfere."""
    count = 8
    results: list[tuple[int, str]] = []

    def convert(seed: int) -> None:
        wf = _make_workflow(seed)
        result = port_convert_workflow(wf)
        assert result.validation is not None
        assert result.validation.ok
        results.append((seed, result.text))

    with concurrent.futures.ThreadPoolExecutor(max_workers=4) as executor:
        futures = [executor.submit(convert, i) for i in range(count)]
        concurrent.futures.wait(futures)
        # Check for exceptions
        for future in futures:
            future.result()  # raises if the thread raised

    assert len(results) == count
    # Each result's text should contain the unique seed identifier
    for seed, text in results:
        assert f"img_{seed}.png" in text or f"conc_{seed}" in text


@pytest.mark.asyncio
async def test_concurrent_async_conversions() -> None:
    """Multiple async tasks converting workflows should not interfere."""
    count = 4

    async def convert(seed: int) -> str:
        wf = _make_workflow(seed)
        # Run in thread pool to avoid blocking the event loop
        loop = asyncio.get_running_loop()
        result = await loop.run_in_executor(None, port_convert_workflow, wf)
        assert result.validation is not None
        assert result.validation.ok
        return result.text

    tasks = [convert(i) for i in range(count)]
    texts = await asyncio.gather(*tasks)

    assert len(texts) == count
    for i, text in enumerate(texts):
        assert f"img_{i}.png" in text or f"conc_{i}" in text


def test_sequential_after_concurrent_no_state_leak() -> None:
    """After concurrent conversions, sequential conversion still works correctly."""
    # First run some concurrent conversions
    with concurrent.futures.ThreadPoolExecutor(max_workers=3) as executor:
        futures = [executor.submit(port_convert_workflow, _make_workflow(i)) for i in range(4)]
        concurrent.futures.wait(futures)

    # Then run a sequential one
    wf = _make_workflow(999)
    result = port_convert_workflow(wf)
    assert result.validation is not None
    assert result.validation.ok
    assert "img_999.png" in result.text or "conc_999" in result.text
