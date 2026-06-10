"""Characterization-gate subprocess test for --known-failures-audit.

Demonstrates that ``--known-failures-audit`` emits a ``STALE FAILURES``
section when ``known_failures.txt`` contains entries that no longer map to
any collected test ID, and that it does NOT modify ``known_failures.txt``.
"""

from __future__ import annotations

import os
import pathlib
import subprocess
import sys

import pytest

REPO_ROOT = pathlib.Path(__file__).resolve().parents[2]
KF_PATH = REPO_ROOT / "tests" / "known_failures.txt"

# Stale test IDs that are guaranteed not to exist in this repo.
_STALE_IDS = (
    "tests/test_this_does_not_exist.py::test_nonexistent",
    "tests/test_also_nonexistent.py::test_another_fake",
)


def _run_audit(test_target: str = "tests/characterization/test_compile_api_snapshots.py") -> subprocess.CompletedProcess[str]:
    """Run a focused pytest invocation with --known-failures-audit."""
    return subprocess.run(
        [
            sys.executable,
            "-m",
            "pytest",
            "--known-failures-audit",
            test_target,
            "--tb=no",
            "-q",
            "--no-header",
            "-p",
            "no:cacheprovider",
        ],
        capture_output=True,
        text=True,
        cwd=str(REPO_ROOT),
        env={**os.environ, "PYTHONHASHSEED": "0"},
        timeout=120,
    )


@pytest.mark.characterization
def test_known_failures_audit_reports_stale_entries() -> None:
    """Verify --known-failures-audit reports stale entries and does NOT modify the file.

    Temporarily injects stale entries into the real ``known_failures.txt``,
    runs ``--known-failures-audit``, asserts the STALE FAILURES section
    appears in stdout, then restores the original file contents.
    """
    # 1. Save original content
    original = KF_PATH.read_text(encoding="utf-8") if KF_PATH.exists() else ""

    try:
        # 2. Inject stale entries into the real known_failures.txt
        stale_block = "\n# Injected stale entries for --known-failures-audit characterization test\n"
        for sid in _STALE_IDS:
            stale_block += sid + "\n"
        KF_PATH.write_text(original + stale_block, encoding="utf-8")

        # 3. Run audit — the stale entries should be reported
        result = _run_audit()

        # 4. Assert the STALE FAILURES section appeared
        assert "STALE FAILURES" in result.stdout, (
            f"Expected 'STALE FAILURES' section in stdout, got:\n"
            f"STDOUT:\n{result.stdout[:2000]}\n"
            f"STDERR:\n{result.stderr[:1000]}"
        )
        for sid in _STALE_IDS:
            assert sid in result.stdout, (
                f"Expected stale entry '{sid}' in audit output, got:\n{result.stdout[:2000]}"
            )

        # 5. Assert known_failures.txt was NOT modified by the audit run
        after_audit = KF_PATH.read_text(encoding="utf-8")
        assert after_audit == original + stale_block, (
            "--known-failures-audit must NOT modify known_failures.txt"
        )

    finally:
        # 6. Restore original content
        KF_PATH.write_text(original, encoding="utf-8")

    # 7. Verify the file is byte-identical to the original after restore
    restored = KF_PATH.read_text(encoding="utf-8")
    assert restored == original, (
        "known_failures.txt should be byte-identical to original after restore"
    )

