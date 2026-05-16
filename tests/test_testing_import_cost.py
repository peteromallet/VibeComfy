"""Import-cost regression guard for vibecomfy.testing (T5)."""
from __future__ import annotations

import subprocess
import sys


def test_importing_vibecomfy_testing_does_not_pull_runtime_or_comfy_command():
    """Subprocess so we measure a clean module table."""
    code = (
        "import vibecomfy.testing, sys; "
        "forbidden = {'vibecomfy.runtime.client', 'vibecomfy.runtime.server', 'vibecomfy.comfy_command'}; "
        "loaded = forbidden & set(sys.modules); "
        "assert not loaded, sorted(loaded)"
    )
    result = subprocess.run([sys.executable, "-c", code], capture_output=True, text=True, timeout=60)
    assert result.returncode == 0, result.stderr
