"""Phase-8 boundary KPI, frozen at the Phase-0 baseline.

This is deliberately a semantic structural check, not a ban on ``json``.  The
current exceptions name the legacy raw-UI authorities that Batch 15 removes;
Batch 16 replaces this provisional test scanner with the CI checker and drives
the exception set to zero.
"""

from __future__ import annotations

import ast
import re
from pathlib import Path

import pytest


REPO_ROOT = Path(__file__).parents[1]
PRODUCT_ROOT = REPO_ROOT / "vibecomfy"

GRAPH_JSON_DOORS = frozenset(
    {
        "vibecomfy/ingest/normalize.py",
        "vibecomfy/porting/emit/ui.py",
    }
)
PASS_THROUGH_ADAPTERS = frozenset(
    {
        "vibecomfy/commands/port/_export.py",
        "vibecomfy/commands/port/_shared.py",
        "vibecomfy/testing/snapshot.py",
        "vibecomfy/registry/pack_resolver.py",
    }
)

# Provisional baseline only.  These are the raw-UI authority sites discovered
# before the sprint; they are not an allow-list and must be empty in Batch 16.
CURRENT_AUTHORITY_EXCEPTIONS = frozenset(
    {
        "vibecomfy/comfy_nodes/agent/_frag_batch_memory.py",
        "vibecomfy/comfy_nodes/agent/_frag_entrypoint.py",
        "vibecomfy/comfy_nodes/agent/_frag_ingest.py",
        "vibecomfy/comfy_nodes/agent/_frag_transform_stages.py",
        "vibecomfy/comfy_nodes/agent/authority_receipts.py",
        "vibecomfy/comfy_nodes/agent/edit_batch_repl.py",
        "vibecomfy/comfy_nodes/agent/executor_durable.py",
        "vibecomfy/comfy_nodes/agent/python_edit_v1.py",
        "vibecomfy/porting/edit/_describe.py",
        "vibecomfy/porting/edit/_gates.py",
        "vibecomfy/porting/edit/_parse_execute.py",
        "vibecomfy/porting/edit/_render.py",
        "vibecomfy/porting/edit/apply_core.py",
        "vibecomfy/porting/edit/apply_gate.py",
        "vibecomfy/porting/edit/apply_links.py",
        "vibecomfy/porting/edit/apply_mutate.py",
        "vibecomfy/porting/edit/apply_place.py",
        "vibecomfy/porting/edit/apply_resolve.py",
        "vibecomfy/porting/edit/apply_resolve_add.py",
        "vibecomfy/porting/edit/apply_resolve_base.py",
        "vibecomfy/porting/edit/apply_types.py",
        "vibecomfy/porting/edit/ledger.py",
        "vibecomfy/porting/edit/lint.py",
        "vibecomfy/porting/edit/projection.py",
        "vibecomfy/porting/edit/session.py",
        "vibecomfy/porting/reorganise/graph_facts.py",
        "vibecomfy/porting/reorganise/orchestrate.py",
        "vibecomfy/porting/resolution.py",
    }
)

# The exporter is currently more than pass-through: it recognizes raw UI by
# inspecting ``nodes``.  Keep the violation explicit until the Batch-16 gate.
CURRENT_PASS_THROUGH_EXCEPTIONS = frozenset(
    {
        "vibecomfy/commands/port/_export.py",
        "vibecomfy/testing/snapshot.py",
    }
)

# Structural readers/writers seen at the Phase-0 baseline.  This semantic
# ceiling complements the narrower legacy-symbol list above: a later batch may
# remove any entry without updating this test, but no new path may appear.
CURRENT_STRUCTURAL_EXCEPTIONS = frozenset(
    {
        "vibecomfy/_compile/_resolve.py",
        "vibecomfy/comfy_nodes/agent/_frag_batch_loop.py",
        "vibecomfy/comfy_nodes/agent/_frag_batch_memory.py",
        "vibecomfy/comfy_nodes/agent/_frag_humanize.py",
        "vibecomfy/comfy_nodes/agent/_frag_ingest.py",
        "vibecomfy/comfy_nodes/agent/_frag_research.py",
        "vibecomfy/comfy_nodes/agent/_frag_transform_stages.py",
        "vibecomfy/comfy_nodes/agent/_v2_scoped_validation.py",
        "vibecomfy/comfy_nodes/agent/audit.py",
        "vibecomfy/comfy_nodes/agent/candidate_transaction.py",
        "vibecomfy/comfy_nodes/agent/contracts.py",
        "vibecomfy/comfy_nodes/agent/edit_batch_repl.py",
        "vibecomfy/comfy_nodes/agent/graph_normalization.py",
        "vibecomfy/comfy_nodes/agent/layout_operation_v1.py",
        "vibecomfy/comfy_nodes/agent/mutation_materialization_v1.py",
        "vibecomfy/comfy_nodes/agent/projection_registry_v1.py",
        "vibecomfy/comfy_nodes/agent/routes.py",
        "vibecomfy/comfy_nodes/agent/session.py",
        "vibecomfy/commands/_agent_edit_debug.py",
        "vibecomfy/demo_factory/additive_judge.py",
        "vibecomfy/demo_factory/baseline.py",
        "vibecomfy/demo_factory/case.py",
        "vibecomfy/demo_factory/creative.py",
        "vibecomfy/demo_factory/deltas.py",
        "vibecomfy/demo_factory/oracle.py",
        "vibecomfy/demo_factory/predicates.py",
        "vibecomfy/demo_factory/run_campaign.py",
        "vibecomfy/executor/core.py",
        "vibecomfy/executor/edit_suggestion_tools.py",
        "vibecomfy/executor/graph_facts.py",
        "vibecomfy/executor/graph_inspection.py",
        "vibecomfy/executor/layout_hints.py",
        "vibecomfy/executor/provenance.py",
        "vibecomfy/executor/revision_evidence.py",
        "vibecomfy/ingest/summarize.py",
        "vibecomfy/intent/_fixture.py",
        "vibecomfy/model_assets.py",
        "vibecomfy/porting/assets.py",
        "vibecomfy/porting/edit/_describe.py",
        "vibecomfy/porting/edit/_resolve.py",
        "vibecomfy/porting/edit/apply_field_aliases.py",
        "vibecomfy/porting/edit/apply_gate.py",
        "vibecomfy/porting/edit/apply_links.py",
        "vibecomfy/porting/edit/apply_mutate.py",
        "vibecomfy/porting/edit/apply_place.py",
        "vibecomfy/porting/edit/apply_types.py",
        "vibecomfy/porting/edit/ledger.py",
        "vibecomfy/porting/edit/normalize.py",
        "vibecomfy/porting/edit/projection.py",
        "vibecomfy/porting/emit/emit_subgraph.py",
        "vibecomfy/porting/layout/layout_vector.py",
        "vibecomfy/porting/layout_store.py",
        "vibecomfy/porting/provenance.py",
        "vibecomfy/porting/refuse.py",
        "vibecomfy/porting/reorganise/graph_facts.py",
        "vibecomfy/porting/reorganise/orchestrate.py",
        "vibecomfy/porting/reorganise/visualize.py",
        "vibecomfy/porting/subgraph_resolve.py",
        "vibecomfy/porting/widget_shape_fence.py",
        "vibecomfy/porting/widgets/aliases.py",
        "vibecomfy/porting/widgets/compact_resolver.py",
    }
)

_LEGACY_AUTHORITY_SYMBOLS = frozenset(
    {
        "EditLedger",
        "apply_delta",
        "guard_full_ui",
        "normalize_agent_edit_graph",
        "render_edit_projection",
    }
)
_GRAPH_KEYS = frozenset({"nodes", "links", "widgets_values"})
_GRAPH_RECEIVER = re.compile(
    r"(?:^|_)(?:graph|ui|workflow|candidate|raw|envelope|scope)(?:$|_)",
    re.IGNORECASE,
)
_NON_GRAPH_RECEIVER = re.compile(
    r"schema|report|manifest|plan|dependency",
    re.IGNORECASE,
)


def _relative(path: Path) -> str:
    return path.relative_to(REPO_ROOT).as_posix()


def _python_trees() -> tuple[tuple[Path, ast.AST], ...]:
    return tuple(
        (path, ast.parse(path.read_text(encoding="utf-8"), filename=str(path)))
        for path in sorted(PRODUCT_ROOT.rglob("*.py"))
    )


def authority_exception_paths() -> frozenset[str]:
    """Return files that still reference a legacy raw-UI authority."""
    found: set[str] = set()
    for path, tree in _python_trees():
        for node in ast.walk(tree):
            if isinstance(node, ast.Name) and node.id in _LEGACY_AUTHORITY_SYMBOLS:
                found.add(_relative(path))
                break
            if isinstance(node, ast.ClassDef) and node.name in _LEGACY_AUTHORITY_SYMBOLS:
                found.add(_relative(path))
                break
            if isinstance(node, ast.Attribute) and node.attr == "working_ui":
                found.add(_relative(path))
                break
            if isinstance(node, ast.Name) and node.id == "working_ui":
                found.add(_relative(path))
                break
    return frozenset(found - GRAPH_JSON_DOORS)


def _literal_graph_key(node: ast.AST) -> str | None:
    if isinstance(node, ast.Subscript):
        key = node.slice
        if isinstance(key, ast.Constant) and key.value in _GRAPH_KEYS:
            return str(key.value)
    if (
        isinstance(node, ast.Call)
        and isinstance(node.func, ast.Attribute)
        and node.func.attr in {"get", "pop", "setdefault"}
        and node.args
        and isinstance(node.args[0], ast.Constant)
        and node.args[0].value in _GRAPH_KEYS
    ):
        return str(node.args[0].value)
    return None


def _receiver_names(node: ast.AST) -> frozenset[str]:
    return frozenset(
        {
            child.id
            for child in ast.walk(node)
            if isinstance(child, ast.Name)
        }
        | {
            child.attr
            for child in ast.walk(node)
            if isinstance(child, ast.Attribute)
        }
    )


def _is_graph_receiver(node: ast.AST) -> bool:
    names = _receiver_names(node)
    if any(_NON_GRAPH_RECEIVER.search(name) for name in names):
        return False
    return any(_GRAPH_RECEIVER.search(name) for name in names)


def _is_structural_write(tree_node: ast.AST) -> bool:
    if isinstance(tree_node, ast.Assign):
        targets = tree_node.targets
    elif isinstance(tree_node, (ast.AnnAssign, ast.AugAssign)):
        targets = (tree_node.target,)
    else:
        return False
    for target in targets:
        for child in ast.walk(target):
            if not isinstance(child, ast.Subscript):
                continue
            if _literal_graph_key(child) is None:
                continue
            if not any(
                _NON_GRAPH_RECEIVER.search(name)
                for name in _receiver_names(child.value)
            ):
                return True
    return False


def _has_structural_graph_access(tree: ast.AST) -> bool:
    for node in ast.walk(tree):
        if _is_structural_write(node):
            return True
        if _literal_graph_key(node) is None:
            continue
        receiver = node.value if isinstance(node, ast.Subscript) else node.func.value
        if _is_graph_receiver(receiver):
            return True
    return False


def structural_exception_paths() -> frozenset[str]:
    """Return semantic raw graph readers/writers outside doors and adapters."""
    excluded = GRAPH_JSON_DOORS | PASS_THROUGH_ADAPTERS
    return frozenset(
        _relative(path)
        for path, tree in _python_trees()
        if _relative(path) not in excluded and _has_structural_graph_access(tree)
    )


def pass_through_structural_paths() -> frozenset[str]:
    """Return pass-through adapters that inspect a structural graph key."""
    found: set[str] = set()
    adapters = {REPO_ROOT / path for path in PASS_THROUGH_ADAPTERS}
    for path, tree in _python_trees():
        if path not in adapters:
            continue
        structural_link_classifier = any(
            isinstance(node, ast.FunctionDef) and node.name == "_is_link"
            for node in ast.walk(tree)
        )
        if structural_link_classifier or any(
            _literal_graph_key(node) is not None for node in ast.walk(tree)
        ):
            found.add(_relative(path))
    return frozenset(found)


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


def test_boundary_kpi_does_not_grow_beyond_current_named_exceptions() -> None:
    assert authority_exception_paths() <= CURRENT_AUTHORITY_EXCEPTIONS
    assert structural_exception_paths() <= CURRENT_STRUCTURAL_EXCEPTIONS
    assert pass_through_structural_paths() <= CURRENT_PASS_THROUGH_EXCEPTIONS


def test_generic_json_calls_are_not_boundary_violations() -> None:
    tree = ast.parse(
        "import json\n"
        "encoded = json.dumps({'status': 'ok'})\n"
        "decoded = json.loads(encoded)\n"
    )
    assert not _has_structural_graph_access(tree)


@pytest.mark.xfail(
    strict=False,
    reason="batch 16: boundary enforcement drives all provisional exceptions to zero",
)
def test_boundary_kpi_is_zero_outside_the_exact_allow_list() -> None:
    assert authority_exception_paths() == frozenset()
    assert structural_exception_paths() == frozenset()
    assert pass_through_structural_paths() == frozenset()
