"""Phase-8 boundary KPI: the CI checker is the single source of truth.

Post-deletion (batch 15) the raw-UI mutation engine is gone.  This module
asserts the final allow-list, that a planted structural read is flagged, that
generic ``json`` calls are not violations, and that the product tree has zero
CI violations (forbidden symbols, graph-receiver writes outside the doors,
pass-through inspection).
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

# Leftover inspection of emitted/transport JSON.  Not mutation authority and
# not an allow-list — the set must not grow.  Additions mean a new reader
# landed outside the doors.
CURRENT_STRUCTURAL_READS = frozenset(
    {
        "vibecomfy/_compile/_resolve.py",
        "vibecomfy/comfy_nodes/agent/_frag_batch_loop.py",
        "vibecomfy/comfy_nodes/agent/_frag_humanize.py",
        "vibecomfy/comfy_nodes/agent/_frag_ingest.py",
        "vibecomfy/comfy_nodes/agent/_frag_research.py",
        "vibecomfy/comfy_nodes/agent/_frag_transform_stages.py",
        "vibecomfy/comfy_nodes/agent/_v2_scoped_validation.py",
        "vibecomfy/comfy_nodes/agent/audit.py",
        "vibecomfy/comfy_nodes/agent/candidate_transaction.py",
        "vibecomfy/comfy_nodes/agent/contracts.py",
        "vibecomfy/comfy_nodes/agent/edit_batch_repl.py",
        "vibecomfy/comfy_nodes/agent/layout_operation_v1.py",
        "vibecomfy/comfy_nodes/agent/mutation_materialization_v1.py",
        "vibecomfy/comfy_nodes/agent/projection_registry_v1.py",
        "vibecomfy/comfy_nodes/agent/routes.py",
        "vibecomfy/comfy_nodes/agent/session.py",
        "vibecomfy/commands/_agent_edit_debug.py",
        "vibecomfy/executor/edit_suggestion_tools.py",
        "vibecomfy/executor/graph_facts.py",
        "vibecomfy/executor/graph_inspection.py",
        "vibecomfy/executor/layout_hints.py",
        "vibecomfy/executor/provenance.py",
        "vibecomfy/executor/revision_evidence.py",
        "vibecomfy/ingest/summarize.py",
        "vibecomfy/model_assets.py",
        "vibecomfy/porting/assets.py",
        "vibecomfy/porting/edit/_describe.py",
        "vibecomfy/porting/edit/apply_field_aliases.py",
        "vibecomfy/porting/edit/session.py",
        "vibecomfy/porting/emit/emit_subgraph.py",
        "vibecomfy/porting/layout/layout_vector.py",
        "vibecomfy/porting/layout_store.py",
        "vibecomfy/porting/provenance.py",
        "vibecomfy/porting/refuse.py",
        "vibecomfy/porting/reorganise/graph_facts.py",
        "vibecomfy/porting/reorganise/visualize.py",
        "vibecomfy/porting/widget_shape_fence.py",
        "vibecomfy/porting/widgets/aliases.py",
        "vibecomfy/porting/widgets/compact_resolver.py",
    }
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


def test_planted_structural_read_outside_the_allow_list_is_flagged() -> None:
    hits = scan_source(
        "graph = {}\nnodes = graph.get('nodes')\n",
        filename="vibecomfy/planted_outside_allowlist.py",
    )
    assert any(item.kind == "structural_read" and item.detail == "nodes" for item in hits)


def test_allow_list_doors_are_not_ci_violations() -> None:
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


def test_boundary_kpi_is_zero_outside_the_exact_allow_list() -> None:
    assert forbidden_symbol_paths() == frozenset()
    assert pass_through_structural_paths() == frozenset()
    assert ci_violations() == ()


def test_structural_readers_do_not_grow_beyond_the_post_deletion_inventory() -> None:
    assert structural_read_paths() <= CURRENT_STRUCTURAL_READS
