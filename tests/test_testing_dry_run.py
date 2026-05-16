"""Tests for vibecomfy.testing.dry_run (T5)."""
from __future__ import annotations

import sys

from vibecomfy.testing import dry_run
from vibecomfy.testing.fixtures import make_workflow_factory
from vibecomfy.workflow import VibeEdge, VibeNode


def _simple_wf():
    wf = make_workflow_factory()(id="dryrun")
    wf.nodes["1"] = VibeNode(id="1", class_type="CheckpointLoaderSimple", inputs={"ckpt_name": "x.safetensors"})
    wf.nodes["2"] = VibeNode(id="2", class_type="SaveImage", inputs={"images": ["1", 0], "filename_prefix": "out"})
    wf.edges.append(VibeEdge(from_node="1", from_output=0, to_node="2", to_input="images"))
    return wf


def test_dry_run_returns_result_with_invocations():
    wf = _simple_wf()
    result = dry_run(wf)
    class_types = {r.class_type for r in result.would_invoke}
    assert "CheckpointLoaderSimple" in class_types
    assert "SaveImage" in class_types


def test_importing_dry_run_does_not_pull_runtime_at_import_time():
    """Import-time contract: just importing the dry_run module must not load runtime.client/server."""
    import subprocess
    code = (
        "from vibecomfy.testing.dry_run import dry_run; "
        "import sys; "
        "forbidden = {'vibecomfy.runtime.client', 'vibecomfy.runtime.server'}; "
        "loaded = forbidden & set(sys.modules); "
        "assert not loaded, sorted(loaded)"
    )
    r = subprocess.run([sys.executable, "-c", code], capture_output=True, text=True, timeout=60)
    assert r.returncode == 0, r.stderr
