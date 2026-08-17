"""CI gate: raw workflow-JSON structural logic lives only at the named doors.

Law 5: VibeWorkflow is the sole graph authority after ingest.  LiteGraph /
envelope ``nodes``, ``links``, widget arrays, and link tuples may be
inspected or mutated only in the two doors.  Four named pass-through
adapters may serialize whole payloads; they may not inspect or mutate
structure (including ``detect_workflow_shape``).  Generic ``json.loads`` /
``json.dumps`` is not a violation.  ``working_ui`` is not a door, adapter,
or graph authority.

Additions to either allow-list or the leftover-read inventory require
editing this file.  There is no open-ended "transport/artifact adapters"
category.

Exit 1 when the product tree has a CI violation:

* a forbidden legacy authority symbol
* a structural write of a graph key outside the doors
* a structural graph-key read outside the doors and leftover inventory
* any structural graph-key access, or ``detect_workflow_shape``, inside a
  pass-through adapter
"""

from __future__ import annotations

import argparse
import ast
import re
import sys
from dataclasses import dataclass
from pathlib import Path

REPO_ROOT = Path(__file__).resolve().parents[1]
PRODUCT_ROOT = REPO_ROOT / "vibecomfy"

GRAPH_JSON_DOORS: frozenset[str] = frozenset(
    {
        "vibecomfy/ingest/normalize.py",
        "vibecomfy/porting/emit/ui.py",
    }
)
PASS_THROUGH_ADAPTERS: frozenset[str] = frozenset(
    {
        "vibecomfy/commands/port/_export.py",
        "vibecomfy/commands/port/_shared.py",
        "vibecomfy/testing/snapshot.py",
        "vibecomfy/registry/pack_resolver.py",
    }
)

FORBIDDEN_SYMBOLS: frozenset[str] = frozenset(
    {
        "EditLedger",
        "apply_delta",
        "guard_full_ui",
        "normalize_agent_edit_graph",
        "render_edit_projection",
    }
)

# Leftover inspection of emitted/transport JSON.  Not mutation authority and
# not a door.  Additions mean a new reader landed outside the doors.
STRUCTURAL_READ_INVENTORY: frozenset[str] = frozenset(
    {
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
        "vibecomfy/comfy_nodes/agent/layout_operation_v1.py",
        "vibecomfy/comfy_nodes/agent/mutation_materialization_v1.py",
        "vibecomfy/comfy_nodes/agent/projection_registry_v1.py",
        "vibecomfy/comfy_nodes/agent/routes.py",
        "vibecomfy/comfy_nodes/agent/session.py",
        "vibecomfy/commands/_agent_edit_debug.py",
        "vibecomfy/commands/analyze.py",
        "vibecomfy/commands/inspect.py",
        "vibecomfy/commands/nodes.py",
        "vibecomfy/commands/sources.py",
        "vibecomfy/executor/edit_suggestion_tools.py",
        "vibecomfy/executor/graph_facts.py",
        "vibecomfy/executor/graph_inspection.py",
        "vibecomfy/executor/layout_hints.py",
        "vibecomfy/executor/provenance.py",
        "vibecomfy/executor/revision_evidence.py",
        "vibecomfy/identity/scope.py",
        "vibecomfy/ingest/summarize.py",
        "vibecomfy/intent/_fixture.py",
        "vibecomfy/intent/_refusal_spine_probe.py",
        "vibecomfy/model_assets.py",
        "vibecomfy/porting/assets.py",
        "vibecomfy/porting/edit/_describe.py",
        "vibecomfy/porting/edit/apply_field_aliases.py",
        "vibecomfy/porting/edit/editable_surface.py",
        "vibecomfy/porting/edit/lint.py",
        "vibecomfy/porting/edit/session.py",
        "vibecomfy/porting/emit/emit_prepare.py",
        "vibecomfy/porting/emit/emit_ready.py",
        "vibecomfy/porting/emit/emit_subgraph.py",
        "vibecomfy/porting/emit/signatures.py",
        "vibecomfy/porting/endpoint_invariant.py",
        "vibecomfy/porting/layout/groups.py",
        "vibecomfy/porting/layout/layout_vector.py",
        "vibecomfy/porting/layout_store.py",
        "vibecomfy/porting/provenance.py",
        "vibecomfy/porting/refuse.py",
        "vibecomfy/porting/reorganise/graph_facts.py",
        "vibecomfy/porting/reorganise/orchestrate.py",
        "vibecomfy/porting/reorganise/parse.py",
        "vibecomfy/porting/reorganise/visualize.py",
        "vibecomfy/porting/widget_shape_fence.py",
        "vibecomfy/porting/widgets/aliases.py",
        "vibecomfy/porting/widgets/compact_resolver.py",
        "vibecomfy/runtime/watchdog.py",
    }
)

_GRAPH_KEYS: frozenset[str] = frozenset({"nodes", "links", "widgets_values"})
_NON_GRAPH_RECEIVER = re.compile(
    r"schema|report|manifest|plan|dependency|group",
    re.IGNORECASE,
)
_SHAPE_INSPECTORS: frozenset[str] = frozenset({"detect_workflow_shape"})

# Campaign fixture generators are not product graph authority.  Forbidden
# symbols inside them still fail the gate.  Additions require editing this file.
_SYMBOL_ONLY_PREFIXES: tuple[str, ...] = ("vibecomfy/demo_factory/",)


@dataclass(frozen=True, slots=True)
class Violation:
    path: str
    lineno: int
    kind: str
    detail: str

    def format(self) -> str:
        return f"{self.path}:{self.lineno}: {self.kind}: {self.detail}"


def _relative(path: Path) -> str:
    return path.resolve().relative_to(REPO_ROOT).as_posix()


def _python_files() -> tuple[Path, ...]:
    return tuple(sorted(PRODUCT_ROOT.rglob("*.py")))


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
        {child.id for child in ast.walk(node) if isinstance(child, ast.Name)}
        | {child.attr for child in ast.walk(node) if isinstance(child, ast.Attribute)}
    )


def _is_graph_receiver(node: ast.AST) -> bool:
    """Unknown receivers count as graph so ``x.get("nodes")`` is flagged."""
    names = _receiver_names(node)
    if any(_NON_GRAPH_RECEIVER.search(name) for name in names):
        return False
    return True


def _write_targets(node: ast.AST) -> tuple[ast.AST, ...]:
    if isinstance(node, ast.Assign):
        return tuple(node.targets)
    if isinstance(node, (ast.AnnAssign, ast.AugAssign)):
        return (node.target,)
    return ()


def _call_name(node: ast.Call) -> str | None:
    func = node.func
    if isinstance(func, ast.Name):
        return func.id
    if isinstance(func, ast.Attribute):
        return func.attr
    return None


def scan_source(source: str, *, filename: str) -> tuple[Violation, ...]:
    """Scan one module.  Doors and pass-through exemptions are not applied."""
    tree = ast.parse(source, filename=filename)
    found: list[Violation] = []
    seen: set[tuple[int, str, str]] = set()

    def _add(lineno: int, kind: str, detail: str) -> None:
        key = (lineno, kind, detail)
        if key in seen:
            return
        seen.add(key)
        found.append(Violation(filename, lineno, kind, detail))

    for node in ast.walk(tree):
        if isinstance(node, ast.Name) and node.id in FORBIDDEN_SYMBOLS:
            _add(node.lineno, "forbidden_symbol", node.id)
        elif isinstance(node, ast.Attribute) and node.attr in FORBIDDEN_SYMBOLS:
            _add(node.lineno, "forbidden_symbol", node.attr)
        elif isinstance(node, ast.ClassDef) and node.name in FORBIDDEN_SYMBOLS:
            _add(node.lineno, "forbidden_symbol", node.name)

        if isinstance(node, ast.Call):
            call_name = _call_name(node)
            if call_name in _SHAPE_INSPECTORS:
                _add(getattr(node, "lineno", 0), "shape_inspection", call_name)

        for target in _write_targets(node):
            for child in ast.walk(target):
                key = _literal_graph_key(child)
                if key is None or not isinstance(child, ast.Subscript):
                    continue
                if _is_graph_receiver(child.value):
                    _add(child.lineno, "structural_write", key)

        key = _literal_graph_key(node)
        if key is None:
            continue
        receiver = node.value if isinstance(node, ast.Subscript) else node.func.value
        if _is_graph_receiver(receiver):
            _add(getattr(node, "lineno", 0), "structural_read", key)

    return tuple(found)


def scan_file(path: Path) -> tuple[Violation, ...]:
    return scan_source(path.read_text(encoding="utf-8"), filename=_relative(path))


def _is_symbol_only(rel: str) -> bool:
    return any(rel.startswith(prefix) for prefix in _SYMBOL_ONLY_PREFIXES)


def classify_violation(item: Violation) -> str | None:
    """Return the CI bucket, or None if the hit is allow-listed / inventory-only."""
    rel = item.path
    if rel in GRAPH_JSON_DOORS:
        return None
    if item.kind == "forbidden_symbol":
        return "forbidden_symbol"
    if rel in PASS_THROUGH_ADAPTERS:
        return "pass_through_structural"
    if _is_symbol_only(rel):
        return None
    if item.kind == "structural_write":
        return "structural_write"
    if item.kind == "shape_inspection":
        return None
    if item.kind == "structural_read":
        if rel in STRUCTURAL_READ_INVENTORY:
            return None
        return "structural_read"
    return None


def scan_product_tree() -> tuple[Violation, ...]:
    found: list[Violation] = []
    for path in _python_files():
        found.extend(scan_file(path))
    return tuple(found)


def ci_violations(hits: tuple[Violation, ...] | None = None) -> tuple[Violation, ...]:
    items = scan_product_tree() if hits is None else hits
    return tuple(item for item in items if classify_violation(item) is not None)


def structural_read_paths(hits: tuple[Violation, ...] | None = None) -> frozenset[str]:
    """Product files (outside doors/adapters) that still inspect a graph key."""
    items = scan_product_tree() if hits is None else hits
    excluded = GRAPH_JSON_DOORS | PASS_THROUGH_ADAPTERS
    return frozenset(
        item.path
        for item in items
        if item.kind == "structural_read"
        and item.path not in excluded
        and not _is_symbol_only(item.path)
    )


def pass_through_structural_paths(hits: tuple[Violation, ...] | None = None) -> frozenset[str]:
    items = scan_product_tree() if hits is None else hits
    return frozenset(
        item.path
        for item in items
        if item.path in PASS_THROUGH_ADAPTERS
        and item.kind in {"structural_read", "structural_write", "shape_inspection"}
    )


def forbidden_symbol_paths(hits: tuple[Violation, ...] | None = None) -> frozenset[str]:
    items = scan_product_tree() if hits is None else hits
    return frozenset(
        item.path
        for item in items
        if item.kind == "forbidden_symbol" and item.path not in GRAPH_JSON_DOORS
    )


def _self_test() -> int:
    planted = scan_source(
        "x = {}\nnodes = x.get('nodes')\n",
        filename="vibecomfy/planted_outside_allowlist.py",
    )
    planted_read = next(
        (item for item in planted if item.kind == "structural_read" and item.detail == "nodes"),
        None,
    )
    if planted_read is None:
        print("self-test: planted x.get('nodes') was not flagged", file=sys.stderr)
        return 1
    if classify_violation(planted_read) != "structural_read":
        print("self-test: planted structural read was not a CI violation", file=sys.stderr)
        return 1

    planted_wv = scan_source(
        "payload = {}\nvalues = payload['widgets_values']\n",
        filename="vibecomfy/planted_widgets_values.py",
    )
    planted_wv_read = next(
        (
            item
            for item in planted_wv
            if item.kind == "structural_read" and item.detail == "widgets_values"
        ),
        None,
    )
    if planted_wv_read is None:
        print("self-test: planted ['widgets_values'] read was not flagged", file=sys.stderr)
        return 1
    if classify_violation(planted_wv_read) != "structural_read":
        print("self-test: planted widgets_values read was not a CI violation", file=sys.stderr)
        return 1

    planted_write = scan_source(
        "graph = {}\ngraph['links'] = []\n",
        filename="planted_write.py",
    )
    if not any(item.kind == "structural_write" and item.detail == "links" for item in planted_write):
        print("self-test: planted structural write was not flagged", file=sys.stderr)
        return 1
    planted_symbol = scan_source(
        "from x import apply_delta\napply_delta(graph)\n",
        filename="planted_symbol.py",
    )
    if not any(item.kind == "forbidden_symbol" and item.detail == "apply_delta" for item in planted_symbol):
        print("self-test: planted forbidden symbol was not flagged", file=sys.stderr)
        return 1
    json_only = scan_source(
        "import json\nencoded = json.dumps({'status': 'ok'})\ndecoded = json.loads(encoded)\n",
        filename="json_only.py",
    )
    if json_only:
        print("self-test: generic json.loads/dumps was flagged", file=sys.stderr)
        return 1
    for rel in GRAPH_JSON_DOORS:
        path = REPO_ROOT / rel
        if not path.is_file():
            print(f"self-test: missing door {rel}", file=sys.stderr)
            return 1
        door_hits = scan_file(path)
        leaked = [item for item in door_hits if classify_violation(item) is not None]
        if leaked:
            print(f"self-test: door {rel} produced a CI violation", file=sys.stderr)
            return 1
    print("self-test: ok")
    return 0


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(description=__doc__.splitlines()[0])
    parser.add_argument(
        "--self-test",
        action="store_true",
        help="flag planted structural reads; confirm doors and json.loads pass",
    )
    args = parser.parse_args(argv)
    if args.self_test:
        return _self_test()

    hits = scan_product_tree()
    fatal = ci_violations(hits)
    if fatal:
        print("IR boundary violations:", file=sys.stderr)
        for item in fatal:
            print(f"  {item.format()}", file=sys.stderr)
        return 1
    print("IR boundary: clean")
    return 0


if __name__ == "__main__":
    sys.exit(main())
