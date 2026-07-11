from __future__ import annotations

import copy
import json
from pathlib import Path

import pytest

from tools.run_corrective_gate import (
    GateError,
    REPO_ROOT,
    _count_node,
    _count_pytest,
    _playwright_counts,
    load_inventory,
    validate_inventory,
)


INVENTORY_PATH = REPO_ROOT / "tests" / "corrective_gate_inventory.json"


def test_locked_inventory_is_complete_and_runner_separated() -> None:
    inventory = load_inventory(INVENTORY_PATH)
    validate_inventory(inventory, REPO_ROOT)


def test_inventory_rejects_wrong_runner_extension() -> None:
    inventory = copy.deepcopy(load_inventory(INVENTORY_PATH))
    inventory["python"]["paths"][0] = "tests/e2e/run.mjs"
    with pytest.raises(GateError, match="wrong-runner"):
        validate_inventory(inventory, REPO_ROOT)


def test_inventory_rejects_quarantine_drift() -> None:
    inventory = copy.deepcopy(load_inventory(INVENTORY_PATH))
    inventory["quarantine_sha256"].pop(next(iter(inventory["quarantine_sha256"])))
    with pytest.raises(GateError, match="file set drifted"):
        validate_inventory(inventory, REPO_ROOT)


def test_runner_count_parsers_fail_closed_on_zero_collection(tmp_path: Path) -> None:
    assert _count_pytest("21 passed, 2 skipped in 1.00s") == 23
    assert _count_pytest("no tests ran") == 0
    assert _count_node("TAP version 13\n# tests 17\n# pass 17\n") == 17
    assert _count_node("TAP version 13\n") == 0

    result = tmp_path / "results.json"
    result.write_text(json.dumps({"stats": {"expected": 1, "unexpected": 0, "flaky": 0, "skipped": 0}}))
    assert _playwright_counts(result) == (1, {"expected": 1, "unexpected": 0, "flaky": 0, "skipped": 0})
    result.write_text("{}")
    with pytest.raises(GateError, match="no stats"):
        _playwright_counts(result)
