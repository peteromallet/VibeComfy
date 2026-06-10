"""Drift guard for agent_edit_response_contract_generated.js.

Ensures the generated JS module is always byte-for-byte identical to what
`scripts/generate_agent_contract_js.py` produces from the Python source of
truth.  Run via subprocess+difflib so there is zero chance of in-process
import caching hiding a stale artifact.
"""

from __future__ import annotations

import difflib
import os
import subprocess
import sys
import tempfile


REPO_ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))

GENERATOR_SCRIPT = os.path.join(REPO_ROOT, "scripts", "generate_agent_contract_js.py")
COMMITTED_FILE = os.path.join(
    REPO_ROOT,
    "vibecomfy",
    "comfy_nodes",
    "web",
    "agent_edit_response_contract_generated.js",
)


def _run_generator() -> str:
    """Run the generator script writing to a temp file, return the generated JS source."""
    with tempfile.NamedTemporaryFile(
        mode="w", suffix=".js", encoding="utf-8", delete=False
    ) as tmp:
        tmp_path = tmp.name

    try:
        env = os.environ.copy()
        env["PYTHONPATH"] = REPO_ROOT + os.pathsep + env.get("PYTHONPATH", "")

        proc = subprocess.run(
            [sys.executable, GENERATOR_SCRIPT, "--output", tmp_path],
            capture_output=True,
            text=True,
            timeout=30,
            env=env,
            cwd=REPO_ROOT,
        )

        if proc.returncode != 0:
            raise AssertionError(
                f"Generator script failed (exit {proc.returncode}):\n"
                f"STDOUT:\n{proc.stdout}\n"
                f"STDERR:\n{proc.stderr}"
            )

        with open(tmp_path, "r", encoding="utf-8") as fh:
            return fh.read()
    finally:
        try:
            os.unlink(tmp_path)
        except OSError:
            pass


def test_generated_js_matches_codegen():
    """The committed generated JS must match what the codegen script produces."""
    # 1. Assert the committed file exists
    assert os.path.isfile(COMMITTED_FILE), (
        f"Generated JS file not found at {COMMITTED_FILE}. "
        "Run scripts/generate_agent_contract_js.py to create it."
    )

    # 2. Read the committed file
    with open(COMMITTED_FILE, "r", encoding="utf-8") as fh:
        committed = fh.read()

    # 3. Run the generator against a temp file
    generated = _run_generator()

    # 4. Byte-for-byte comparison
    if committed != generated:
        diff = "".join(
            difflib.unified_diff(
                committed.splitlines(keepends=True),
                generated.splitlines(keepends=True),
                fromfile="committed: " + COMMITTED_FILE,
                tofile="generated (from scripts/generate_agent_contract_js.py)",
            )
        )
        raise AssertionError(
            f"Generated JS drift detected!\n\n"
            f"The committed file at {COMMITTED_FILE} does not match what the\n"
            f"codegen script produces.  Run this to regenerate:\n\n"
            f"    python scripts/generate_agent_contract_js.py\n\n"
            f"Diff:\n{diff}"
        )
