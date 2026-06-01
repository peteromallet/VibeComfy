from __future__ import annotations

import shutil
import subprocess

import pytest


def test_browser_harness_smoke() -> None:
    node = shutil.which("node")
    if node is None:
        pytest.skip("node is required for browser harness smoke")

    result = subprocess.run(
        [node, "--test", "tests/browser/roundtrip_smoke.test.mjs"],
        capture_output=True,
        text=True,
        check=False,
    )
    assert result.returncode == 0, result.stdout + "\n" + result.stderr
