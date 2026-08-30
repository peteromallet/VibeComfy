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


def test_semantic_projection_reads_are_not_raw_graph_reads() -> None:
    hits = scan_source(
        "from vibecomfy.executor.revision_evidence import semantic_graph_projection\n"
        "before = semantic_graph_projection(original)\n"
        "after = semantic_graph_projection(candidate)\n"
        "same_nodes = before['nodes'] == after['nodes']\n"
        "same_links = before.get('links') == after.get('links')\n",
        filename="vibecomfy/semantic_projection_consumer.py",
    )
    assert hits == ()


def test_projection_provenance_does_not_allow_reassigned_or_arbitrary_dicts() -> None:
    reassigned = scan_source(
        "before = semantic_graph_projection(original)\n"
        "before = arbitrary_payload\n"
        "nodes = before['nodes']\n",
        filename="vibecomfy/reassigned_projection.py",
    )
    assert any(item.kind == "structural_read" and item.detail == "nodes" for item in reassigned)

    arbitrary = scan_source(
        "before = {}\n"
        "nodes = before['nodes']\n",
        filename="vibecomfy/arbitrary_projection_name.py",
    )
    assert any(item.kind == "structural_read" and item.detail == "nodes" for item in arbitrary)


def test_projection_provenance_rejects_qualified_calls_and_all_rebinding_forms() -> None:
    qualified = scan_source(
        "before = helper.semantic_graph_projection(original)\n"
        "read = before['nodes']\n",
        filename="vibecomfy/qualified_projection.py",
    )
    assert any(item.kind == "structural_read" and item.detail == "nodes" for item in qualified)

    wrong_import = scan_source(
        "from untrusted import semantic_graph_projection\n"
        "before = semantic_graph_projection(original)\n"
        "read = before['nodes']\n",
        filename="vibecomfy/untrusted_projection.py",
    )
    assert any(item.kind == "structural_read" and item.detail == "nodes" for item in wrong_import)

    cases = {
        "aug": "before = semantic_graph_projection(original)\nbefore += payload\nread = before['nodes']\n",
        "for": "before = semantic_graph_projection(original)\nfor before in values:\n    read = before['nodes']\n",
        "with": "before = semantic_graph_projection(original)\nwith context() as before:\n    read = before['nodes']\n",
        "except": "before = semantic_graph_projection(original)\ntry:\n    work()\nexcept Exception as before:\n    read = before['nodes']\n",
        "import": "before = semantic_graph_projection(original)\nimport something as before\nread = before['nodes']\n",
        "parameter": "before = semantic_graph_projection(original)\ndef f(before):\n    return before['nodes']\n",
        "lambda": "before = semantic_graph_projection(original)\nread = (lambda before: before['nodes'])(payload)\n",
        "delete": "before = semantic_graph_projection(original)\ndel before\nread = before['nodes']\n",
        "comprehension": "before = semantic_graph_projection(original)\nvalues = [before['nodes'] for before in payload]\n",
    }
    for name, source in cases.items():
        hits = scan_source(source, filename=f"vibecomfy/rebound_{name}.py")
        assert any(item.kind == "structural_read" and item.detail == "nodes" for item in hits), name


def test_exact_projection_import_alias_remains_a_true_projection() -> None:
    hits = scan_source(
        "from vibecomfy.executor.revision_evidence import semantic_graph_projection as project\n"
        "before = project(original)\n"
        "read = before['nodes']\n",
        filename="vibecomfy/projection_import_alias.py",
    )
    assert hits == ()


def test_canonical_projection_definition_remains_a_true_projection() -> None:
    hits = scan_source(
        "def semantic_graph_projection(graph):\n"
        "    return {'nodes': graph}\n"
        "before = semantic_graph_projection(original)\n"
        "read = before['nodes']\n",
        filename="vibecomfy/executor/revision_evidence.py",
    )
    assert hits == ()


def test_match_mapping_rest_rebinds_projection_receiver() -> None:
    rebound = scan_source(
        "from vibecomfy.executor.revision_evidence import semantic_graph_projection\n"
        "before = semantic_graph_projection(original)\n"
        "match payload:\n"
        "    case {'nodes': _, **before}:\n"
        "        pass\n"
        "read = before['nodes']\n",
        filename="vibecomfy/match_mapping_rebound.py",
    )
    assert any(item.kind == "structural_read" and item.detail == "nodes" for item in rebound)

    retained = scan_source(
        "from vibecomfy.executor.revision_evidence import semantic_graph_projection\n"
        "before = semantic_graph_projection(original)\n"
        "match payload:\n"
        "    case {'nodes': _, **rest}:\n"
        "        pass\n"
        "read = before['nodes']\n",
        filename="vibecomfy/match_mapping_retained.py",
    )
    assert retained == ()


def test_duplicate_canonical_projection_definitions_fail_closed() -> None:
    hits = scan_source(
        "def semantic_graph_projection(graph):\n"
        "    return {'nodes': graph}\n"
        "def semantic_graph_projection(graph):\n"
        "    return {'nodes': graph}\n"
        "before = semantic_graph_projection(original)\n"
        "read = before['nodes']\n",
        filename="vibecomfy/executor/revision_evidence.py",
    )
    assert any(item.kind == "structural_read" and item.detail == "nodes" for item in hits)


def test_class_locals_are_not_treated_as_method_closure_bindings() -> None:
    hits = scan_source(
        "class Container:\n"
        "    from vibecomfy.executor.revision_evidence import semantic_graph_projection\n"
        "    def method(self):\n"
        "        before = semantic_graph_projection(original)\n"
        "        return before['nodes']\n",
        filename="vibecomfy/class_scope_projection.py",
    )
    assert any(item.kind == "structural_read" and item.detail == "nodes" for item in hits)


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
