"""Verify that new mode-related symbols are accessible from vibecomfy.contracts."""
from __future__ import annotations


def test_execution_mode_constants_importable() -> None:
    from vibecomfy.contracts import (
        EXECUTION_MODE_SANDBOXED_LOOSE,
        EXECUTION_MODE_SANDBOXED_STRICT,
        EXECUTION_MODE_UNRESTRICTED,
    )
    assert EXECUTION_MODE_SANDBOXED_LOOSE == "sandboxed_loose"
    assert EXECUTION_MODE_SANDBOXED_STRICT == "sandboxed_strict"
    assert EXECUTION_MODE_UNRESTRICTED == "unrestricted"


def test_runtime_code_broad_builtins_importable() -> None:
    from vibecomfy.contracts import RUNTIME_CODE_BROAD_BUILTINS
    assert isinstance(RUNTIME_CODE_BROAD_BUILTINS, frozenset)
    assert "print" in RUNTIME_CODE_BROAD_BUILTINS
    assert "range" in RUNTIME_CODE_BROAD_BUILTINS
    assert len(RUNTIME_CODE_BROAD_BUILTINS) > 16


def test_runtime_code_loose_allowed_imports_importable() -> None:
    from vibecomfy.contracts import RUNTIME_CODE_LOOSE_ALLOWED_IMPORTS
    assert isinstance(RUNTIME_CODE_LOOSE_ALLOWED_IMPORTS, frozenset)
    assert "math" in RUNTIME_CODE_LOOSE_ALLOWED_IMPORTS
    assert "json" in RUNTIME_CODE_LOOSE_ALLOWED_IMPORTS
    assert "re" in RUNTIME_CODE_LOOSE_ALLOWED_IMPORTS


def test_runtime_code_max_source_bytes_new_importable() -> None:
    from vibecomfy.contracts import RUNTIME_CODE_MAX_SOURCE_BYTES_NEW
    assert RUNTIME_CODE_MAX_SOURCE_BYTES_NEW == 65_536


def test_runtime_code_unrestricted_ack_error_importable() -> None:
    from vibecomfy.contracts import RUNTIME_CODE_UNRESTRICTED_ACK_ERROR
    assert RUNTIME_CODE_UNRESTRICTED_ACK_ERROR == "runtime_unrestricted_requires_ack"


def test_runtime_code_timeout_ms_max_raised() -> None:
    from vibecomfy.contracts.intent_nodes import RUNTIME_CODE_TIMEOUT_MS_MAX
    assert RUNTIME_CODE_TIMEOUT_MS_MAX == 10_000


def test_resolve_execution_mode_importable() -> None:
    from vibecomfy.contracts import resolve_execution_mode
    # Falls back to sandboxed_loose when no mode is set.
    assert resolve_execution_mode({}) == "sandboxed_loose"
    assert resolve_execution_mode({"execution_mode": "sandboxed_strict"}) == "sandboxed_strict"
    assert resolve_execution_mode({"execution_mode": "unrestricted"}) == "unrestricted"
    assert resolve_execution_mode({"execution_mode": "expression_v1"}) == "expression_v1"


def test_scan_runtime_code_source_importable() -> None:
    from vibecomfy.contracts import scan_runtime_code_source
    # Basic smoke: scan a harmless source returns a report with no rejects.
    report = scan_runtime_code_source("outputs['x'] = 1 + 2")
    assert report is not None


def test_new_mode_constants_in_all_execution_modes() -> None:
    from vibecomfy.contracts.intent_nodes import _ALL_EXECUTION_MODES, _NEW_EXECUTION_MODES
    assert "sandboxed_loose" in _ALL_EXECUTION_MODES
    assert "sandboxed_strict" in _ALL_EXECUTION_MODES
    assert "unrestricted" in _ALL_EXECUTION_MODES
    assert "expression_v1" in _ALL_EXECUTION_MODES
    assert "sandboxed_loose" in _NEW_EXECUTION_MODES
    assert "expression_v1" not in _NEW_EXECUTION_MODES
