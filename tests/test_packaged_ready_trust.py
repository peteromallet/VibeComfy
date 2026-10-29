"""Verify the wheel's ready-template trust boundary without a checkout."""

from __future__ import annotations

import os
from pathlib import Path
import subprocess
import sys

import pytest


@pytest.mark.timeout(180)
def test_wheel_ready_templates_and_external_paths_from_neutral_cwd(tmp_path: Path) -> None:
    repo = Path(__file__).resolve().parents[1]
    wheel_dir = tmp_path / "wheels"
    wheel_dir.mkdir()
    build = subprocess.run(
        [sys.executable, "-m", "build", "--wheel", "--no-isolation", "--outdir", str(wheel_dir)],
        cwd=repo, capture_output=True, text=True,
    )
    assert build.returncode == 0, build.stdout + build.stderr
    wheels = list(wheel_dir.glob("vibecomfy-*.whl"))
    assert len(wheels) == 1
    installed = tmp_path / "installed"
    install = subprocess.run(
        [sys.executable, "-m", "pip", "install", "--no-deps", "--disable-pip-version-check",
         "--target", str(installed), str(wheels[0])],
        cwd=tmp_path, capture_output=True, text=True,
    )
    assert install.returncode == 0, install.stdout + install.stderr

    neutral = tmp_path / "neutral"
    neutral.mkdir()
    script = r'''
from pathlib import Path
import sys
sys.path.insert(0, sys.argv[1])
import vibecomfy
from vibecomfy.errors import CheckoutRequiredError
from vibecomfy.registry.ready import repo_ready_template_root, workflow_from_ready
from vibecomfy.scratchpad_loader import load_scratchpad
from vibecomfy.security.gate import CapabilityFenceError, GateContext, set_gate_context
from vibecomfy.security.loader_provenance import _provenance_for_path
from vibecomfy.utils import find_repo_root

package = Path(vibecomfy.__file__).resolve().parent
assert package == (Path(sys.argv[1]) / "vibecomfy").resolve()
try:
    find_repo_root()
except CheckoutRequiredError:
    pass
else:
    raise AssertionError("unexpected checkout")
root = repo_ready_template_root().resolve()
assert root == package / "ready_templates"
set_gate_context(GateContext(non_interactive=True, assume_yes=False, audit=[]))
workflow = workflow_from_ready("image/z_image")
assert workflow.nodes and workflow.metadata["ready_template"] == "image/z_image"

# Neither a checkout-shaped cwd nor another file in the package is trusted.
scratchpad = Path.cwd() / "out" / "scratchpads" / "external.py"
scratchpad.parent.mkdir(parents=True)
scratchpad.write_text("from pathlib import Path\nPath('executed').write_text('yes')\n")
for path in (scratchpad, package / "security" / "loader_provenance.py"):
    assert _provenance_for_path(path) == "untrusted_source"
try:
    load_scratchpad(scratchpad)
except CapabilityFenceError as exc:
    assert exc.detail["provenance"] == "untrusted_source"
else:
    raise AssertionError("scratchpad was trusted")

# A symlink inside the wheel corpus must not make an external template trusted.
link = root / "escape_probe.py"
link.symlink_to(scratchpad)
try:
    assert _provenance_for_path(link) == "untrusted_source"
    try:
        workflow_from_ready("escape_probe")
    except CapabilityFenceError as exc:
        assert exc.detail["provenance"] == "untrusted_source"
    else:
        raise AssertionError("external ready template was trusted")
finally:
    link.unlink()
assert not Path("executed").exists()
'''
    env = {key: value for key, value in os.environ.items() if key != "PYTHONPATH"}
    env["HOME"] = str(neutral)
    result = subprocess.run(
        [sys.executable, "-I", "-c", script, str(installed)], cwd=neutral,
        env=env, capture_output=True, text=True, timeout=120,
    )
    assert result.returncode == 0, result.stdout + result.stderr
