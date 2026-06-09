"""Characterization-gate conftest: enforces PYTHONHASHSEED=0.

Every test under ``tests/characterization/`` that is collected with the
``characterization`` marker MUST have ``PYTHONHASHSEED=0`` in the parent
process environment.  This conftest installs an autouse fixture that fails
loudly at collection time if the invariant is violated.
"""

from __future__ import annotations

import os

import pytest


@pytest.fixture(autouse=True)
def _require_pythonhashseed_zero() -> None:
    """Fail immediately if ``PYTHONHASHSEED`` is not ``"0"``.

    The characterization gate depends on deterministic hash ordering
    (dict iteration, set ordering, etc.).  ``PYTHONHASHSEED=0`` is the
    CPython-supported mechanism for this.  Setting it in the parent process
    is sufficient — no subprocess re-exec is needed.
    """
    seed = os.environ.get("PYTHONHASHSEED")
    if seed != "0":
        pytest.fail(
            "PYTHONHASHSEED must be '0' to run characterization tests.\n"
            f"Current value: {seed!r}\n"
            "Re-run with: PYTHONHASHSEED=0 pytest -m characterization"
        )
