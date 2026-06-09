#!/usr/bin/env python3
"""Audit every class_type used by ready_templates/**/*.py.

Cross-reference against custom_nodes.lock pack class_sets + core ComfyUI
classes. Classify each class as typed-wrapper, fallback-helper, or
schema-missing-blocker. Write inventory to vibecomfy/porting/cache/class_inventory.json.
"""

from __future__ import annotations

import ast
import json
import sys
import tomllib
from collections import defaultdict
from pathlib import Path

# TODO(repo-root): migrate to vibecomfy.utils.find_repo_root() once this tool's
# script-mode import path is package-import-safe.
REPO = Path(__file__).resolve().parent.parent

LOCK_FILE = REPO / "custom_nodes.lock"
READY_DIR = REPO / "ready_templates"
CACHE_DIR = REPO / "vibecomfy" / "porting" / "cache"
INVENTORY_PATH = CACHE_DIR / "class_inventory.json"

# Helper classes that should never get typed wrappers
FALLBACK_HELPERS = frozenset({
    "SetNode", "GetNode", "Note", "MarkdownNote", "Reroute",
    "PrimitiveNode", "PrimitiveBoolean", "PrimitiveInt", "PrimitiveFloat",
    "PrimitiveString",
})

# UI-only / helper nodes from rgthree and elsewhere that are safe to skip
UI_ONLY_PATTERNS = {
    "Any Switch (rgthree)", "Fast Groups Bypasser (rgthree)",
    "Fast Groups Muter (rgthree)", "Label (rgthree)",
    "Seed (rgthree)",
}

from vibecomfy.contracts.validation import OPAQUE_COMPONENT_CLASS_RE  # noqa: E402


def parse_custom_nodes_lock(path: Path) -> dict[str, dict]:
    """Parse the TOML custom_nodes.lock into nodepack records."""
    with open(path, "rb") as f:
        data = tomllib.load(f)
    nodepacks = data.get("nodepacks", {})
    if not isinstance(nodepacks, dict):
        return {}
    return {str(name): dict(value) for name, value in nodepacks.items() if isinstance(value, dict)}


def extract_class_types_from_file(filepath: Path) -> list[dict]:
    """Extract all class_type strings from node(wf, ...) calls in a ready template."""
    results = []
    try:
        tree = ast.parse(filepath.read_text())
    except SyntaxError:
        return results

    class NodeVisitor(ast.NodeVisitor):
        def visit_Call(self, node):
            # Look for patterns:
            # - node(wf, 'ClassName', ...)
            # - _at(wf, ..., 'ClassName', ...)
            # - wf.node('ClassName', ...)
            if isinstance(node.func, ast.Name) and node.func.id in ("node", "_at"):
                args = node.args
                # node(wf, class_type, _id, ...)
                if len(args) >= 2:
                    arg1 = args[1] if node.func.id == "node" else (args[2] if len(args) > 2 else None)
                    if isinstance(arg1, ast.Constant) and isinstance(arg1.value, str):
                        class_type = arg1.value
                        # Check for source id
                        source_id = None
                        if node.func.id == "node" and len(args) >= 3:
                            sid = args[2]
                            if isinstance(sid, ast.Constant):
                                source_id = str(sid.value)
                        # Also check _id kwarg
                        for kw in node.keywords:
                            if kw.arg == "_id" and source_id is None:
                                if isinstance(kw.value, ast.Constant):
                                    source_id = str(kw.value.value)
                        results.append({
                            "class_type": class_type,
                            "source_id": source_id,
                            "file": str(filepath),
                        })
            elif isinstance(node.func, ast.Attribute) and node.func.attr == "node":
                args = node.args
                if args and isinstance(args[0], ast.Constant) and isinstance(args[0].value, str):
                    results.append({
                        "class_type": args[0].value,
                        "source_id": None,
                        "file": str(filepath),
                    })
            self.generic_visit(node)

    NodeVisitor().visit(tree)
    return results


def main():
    # Parse lock
    packs = parse_custom_nodes_lock(LOCK_FILE)

    # Build pack class sets.
    pack_class_sets = {}
    for pack_key, pack_data in packs.items():
        class_set = pack_data.get("class_set", [])
        if isinstance(class_set, list):
            pack_class_sets[pack_key] = set(class_set)

    # Extract all class_types from ready templates
    all_refs = []
    for py_file in sorted(READY_DIR.rglob("*.py")):
        refs = extract_class_types_from_file(py_file)
        all_refs.extend(refs)

    # Aggregate by class_type
    class_to_files = defaultdict(set)
    class_to_source_ids = defaultdict(set)
    for ref in all_refs:
        ct = ref["class_type"]
        class_to_files[ct].add(ref["file"])
        if ref["source_id"]:
            class_to_source_ids[ct].add(ref["source_id"])

    # Classify each class_type
    inventory = {
        "typed_wrappers": {},
        "fallback_helpers": {},
        "schema_missing": {},
        "stats": {
            "total_classes": len(class_to_files),
            "total_files": len(set(ref["file"] for ref in all_refs)),
            "total_refs": len(all_refs),
        }
    }

    for class_type in sorted(class_to_files):
        files = sorted(class_to_files[class_type])
        source_ids = sorted(class_to_source_ids[class_type])

        # Find which pack this class is in
        found_pack = None
        for pack_key, class_set in pack_class_sets.items():
            if class_type in class_set:
                found_pack = pack_key
                break

        entry = {
            "class_type": class_type,
            "file_count": len(files),
            "files": files,
            "source_ids": source_ids,
            "pack": found_pack,
            "is_core": found_pack is None,
            "non_numeric_source_ids": [sid for sid in source_ids if not sid.isdigit()],
        }

        if class_type in FALLBACK_HELPERS:
            inventory["fallback_helpers"][class_type] = entry
        elif class_type in UI_ONLY_PATTERNS:
            inventory["fallback_helpers"][class_type] = entry
        elif OPAQUE_COMPONENT_CLASS_RE.match(class_type):
            inventory["fallback_helpers"][class_type] = {
                **entry,
                "reason": "opaque_component_subgraph",
            }
        else:
            inventory["typed_wrappers"][class_type] = entry

    # Write inventory
    CACHE_DIR.mkdir(parents=True, exist_ok=True)
    with open(INVENTORY_PATH, "w", encoding="utf-8") as f:
        json.dump(inventory, f, indent=2, ensure_ascii=False)

    print(f"Audit complete: {inventory['stats']['total_classes']} unique class_types")
    print(f"  typed_wrappers: {len(inventory['typed_wrappers'])}")
    print(f"  fallback_helpers: {len(inventory['fallback_helpers'])}")
    print(f"  schema_missing: {len(inventory['schema_missing'])}")
    print(f"  total references: {inventory['stats']['total_refs']}")
    print(f"Written to: {INVENTORY_PATH}")

    # Flag: check for non-numeric source ids
    non_numeric = [sid for sids in class_to_source_ids.values() for sid in sids if not sid.isdigit()]
    if non_numeric:
        print(f"\nNon-numeric source ids found: {non_numeric}")
    else:
        print("\nNo non-numeric source ids found.")

    return 0


if __name__ == "__main__":
    sys.exit(main())
