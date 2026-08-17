"""Phase-8 boundary KPI: the CI checker is the single source of truth.

Post-deletion (batch 15) the raw-UI mutation engine is gone.  This module
asserts the named doors, that a planted structural read is a CI
violation, that generic ``json`` calls are not violations, that the
product tree has zero CI violations, and that leftover structural
readers are zero — there is no product-reader allow-list.
"""

from __future__ import annotations

from scripts.check_ir_boundary import (
    GRAPH_JSON_DOORS,
    PASS_THROUGH_ADAPTERS,
    ci_violations,
    classify_violation,
    forbidden_symbol_paths,
    pass_through_structural_paths,
    scan_file,
    scan_source,
    structural_read_paths,
)


def test_boundary_contract_has_exact_named_doors_and_pass_through_adapters() -> None:
    assert GRAPH_JSON_DOORS == {
        "vibecomfy/ingest/normalize.py",
        "vibecomfy/ingest/door_access.py",
        "vibecomfy/porting/emit/ui.py",
    }
    assert PASS_THROUGH_ADAPTERS == {
        "vibecomfy/commands/port/_export.py",
        "vibecomfy/commands/port/_shared.py",
        "vibecomfy/testing/snapshot.py",
        "vibecomfy/registry/pack_resolver.py",
    }
    assert "working_ui" not in GRAPH_JSON_DOORS
    assert "working_ui" not in PASS_THROUGH_ADAPTERS


def test_planted_structural_read_is_flagged() -> None:
    hits = scan_source(
        "x = {}\nnodes = x.get('nodes')\n",
        filename="vibecomfy/planted_outside_allowlist.py",
    )
    planted = next(
        item for item in hits if item.kind == "structural_read" and item.detail == "nodes"
    )
    assert classify_violation(planted) == "structural_read"

    wv_hits = scan_source(
        "payload = {}\nvalues = payload['widgets_values']\n",
        filename="vibecomfy/planted_widgets_values.py",
    )
    planted_wv = next(
        item
        for item in wv_hits
        if item.kind == "structural_read" and item.detail == "widgets_values"
    )
    assert classify_violation(planted_wv) == "structural_read"


def test_doors_are_not_ci_violations() -> None:
    from pathlib import Path

    root = Path(__file__).resolve().parents[1]
    for rel in GRAPH_JSON_DOORS:
        leaked = [item for item in scan_file(root / rel) if classify_violation(item) is not None]
        assert leaked == [], rel


def test_generic_json_calls_are_not_boundary_violations() -> None:
    hits = scan_source(
        "import json\n"
        "encoded = json.dumps({'status': 'ok'})\n"
        "decoded = json.loads(encoded)\n",
        filename="json_only.py",
    )
    assert hits == ()


def test_checker_self_test_passes() -> None:
    from scripts.check_ir_boundary import main

    assert main(["--self-test"]) == 0


def test_boundary_kpi_is_zero_ci_violations() -> None:
    assert forbidden_symbol_paths() == frozenset()
    assert pass_through_structural_paths() == frozenset()
    assert ci_violations() == ()


def test_structural_readers_are_zero() -> None:
    assert structural_read_paths() == frozenset()
