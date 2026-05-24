from __future__ import annotations

import ast
from dataclasses import dataclass
from pathlib import Path
from typing import Any


_UNSUPPORTED = object()


@dataclass(frozen=True)
class NodeSourceEntry:
    node_id: str
    variable: str | None
    class_type: str
    source_path: str | None
    source_line: int | None

    def to_json(self) -> dict[str, Any]:
        return {
            "node_id": self.node_id,
            "variable": self.variable,
            "class_type": self.class_type,
            "source_path": self.source_path,
            "source_line": self.source_line,
        }


def build_source_map(path: str | Path | None) -> dict[str, NodeSourceEntry]:
    if path is None:
        return {}
    source_path = Path(path)
    try:
        source = source_path.read_text(encoding="utf-8")
        tree = ast.parse(source, filename=str(source_path))
    except (OSError, SyntaxError):
        return {}
    return source_map_from_tree(tree, source_path=str(source_path))


def source_map_from_tree(tree: ast.AST, *, source_path: str | None = None) -> dict[str, NodeSourceEntry]:
    entries: dict[str, NodeSourceEntry] = {}
    _attach_parents(tree)
    next_auto_id = 1
    calls = [
        node
        for node in ast.walk(tree)
        if isinstance(node, ast.Call) and _call_name(node.func) in {"_node", "node", "ready_node"}
    ]
    for call in sorted(calls, key=lambda item: (getattr(item, "lineno", 0), getattr(item, "col_offset", 0))):
        parsed = _runtime_node_call(call, next_auto_id)
        if parsed is None:
            continue
        if parsed["uses_auto_id"]:
            next_auto_id += 1
        variable = _assigned_name(call)
        entry = NodeSourceEntry(
            node_id=parsed["node_id"],
            variable=variable,
            class_type=parsed["class_type"],
            source_path=source_path,
            source_line=getattr(call, "lineno", None),
        )
        entries[entry.node_id] = entry
    return entries


def _runtime_node_call(node: ast.Call, next_auto_id: int) -> dict[str, Any] | None:
    call_name = _call_name(node.func)
    uses_auto_id = False
    if call_name == "_node":
        class_type = _literal_arg(node, 1)
        node_id = _literal_arg(node, 2)
    elif call_name == "ready_node":
        class_type = _literal_arg(node, 1)
        node_id = _keyword_literal(node, "source_id")
        if not isinstance(node_id, str):
            node_id = str(next_auto_id)
            uses_auto_id = True
    elif call_name == "node":
        class_type = _literal_arg(node, 0)
        node_id = str(next_auto_id)
        uses_auto_id = True
    else:
        return None
    if not isinstance(class_type, str) or not isinstance(node_id, str):
        return None
    return {"class_type": class_type, "node_id": node_id, "uses_auto_id": uses_auto_id}


def _assigned_name(call: ast.Call) -> str | None:
    parent = getattr(call, "_parent", None)
    while isinstance(parent, ast.Call):
        parent = getattr(parent, "_parent", None)
    if isinstance(parent, ast.Assign) and parent.targets:
        return _target_name(parent.targets[0])
    if isinstance(parent, ast.AnnAssign):
        return _target_name(parent.target)
    return None


def _attach_parents(node: ast.AST) -> None:
    root = node
    while getattr(root, "_parent", None) is not None:
        root = getattr(root, "_parent")
    for parent in ast.walk(root):
        for child in ast.iter_child_nodes(parent):
            setattr(child, "_parent", parent)


def _target_name(target: ast.AST) -> str | None:
    if isinstance(target, ast.Name):
        return target.id
    if isinstance(target, ast.Attribute):
        return target.attr
    if isinstance(target, ast.Tuple) and target.elts:
        return _target_name(target.elts[0])
    return None


def _literal_arg(node: ast.Call, index: int) -> Any:
    if index >= len(node.args):
        return _UNSUPPORTED
    return _literal_value(node.args[index])


def _keyword_literal(node: ast.Call, name: str) -> Any:
    for keyword in node.keywords:
        if keyword.arg == name:
            return _literal_value(keyword.value)
    return None


def _literal_value(node: ast.AST) -> Any:
    if isinstance(node, ast.Constant):
        return node.value
    try:
        return ast.literal_eval(node)
    except (ValueError, TypeError):
        return _UNSUPPORTED


def _call_name(func: ast.AST) -> str:
    if isinstance(func, ast.Name):
        return func.id
    if isinstance(func, ast.Attribute):
        return func.attr
    return ""
