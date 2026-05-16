"""Canonical snapshot helpers shared by the regen script and the
`vibecomfy test` CLI.

The functions in this module are the single source of truth for how a
compiled API dict is serialised into the three-sidecar form
(`<stem>.api.json`, `<stem>.class_types.json`, `<stem>.widget_values.json`).
`scripts/regenerate_snapshots.py` imports them so byte parity with the
committed snapshots is preserved.

Also exposes:

- `STEM_TO_READY_ID` — re-export of the curated stem registry.
- `parse_directives(text)` — parser for `# vibecomfy-snapshot: ...` opt-outs
  that apply ONLY to user-recipe snapshots.
- `normalize_seed_field(api, *, replacement)` — utility for tests/recipes to
  normalise volatile seed widget values before snapshotting.
- `load_recipe_build(path)` — `importlib.util.spec_from_file_location`
  loader that returns a recipe's `build` callable (or `WORKFLOW` module
  attribute) with a hashed stable module name.

This module MUST stay runtime-free at import time: tests run in clean envs
that do not have ComfyUI installed.
"""

from __future__ import annotations

import hashlib
import importlib.util
import json
import re
import sys
from collections import Counter
from dataclasses import dataclass
from pathlib import Path
from typing import Any, Callable

from vibecomfy.testing.snapshot_registry import STEM_TO_READY_ID

__all__ = [
    "STEM_TO_READY_ID",
    "RecipeDirective",
    "_canonical_api_text",
    "_canonical_class_types_text",
    "_canonical_widget_values_text",
    "_is_link",
    "canonicalize_api",
    "canonicalize_class_types",
    "canonicalize_widget_values",
    "apply_directives",
    "load_recipe_build",
    "normalize_seed_field",
    "parse_directives",
]


# ---------------------------------------------------------------------------
# Canonicalisers (moved from scripts/regenerate_snapshots.py — names pinned)
# ---------------------------------------------------------------------------


def _is_link(value: object) -> bool:
    """Return True when an API-dict input looks like a node link.

    Links are ``[node_id_str, slot_int]`` pairs; everything else is a widget
    value that participates in the widget-values histogram.
    """
    return (
        isinstance(value, list)
        and len(value) == 2
        and isinstance(value[0], str)
        and isinstance(value[1], int)
    )


def _canonical_api_text(api: dict) -> str:
    # Preserve insertion order from compile("api"); committed snapshots are not
    # alphabetised (keys "1".."10" appear in numeric insert order, not lexical).
    return json.dumps(api, indent=2, ensure_ascii=False)


def _canonical_class_types_text(api: dict) -> str:
    rows = sorted(str(node.get("class_type", "Unknown")) for node in api.values() if isinstance(node, dict))
    return json.dumps(rows, indent=2)


def _canonical_widget_values_text(api: dict) -> str:
    histogram: Counter[tuple[str, str, str]] = Counter()
    for node in api.values():
        if not isinstance(node, dict):
            continue
        class_type = str(node.get("class_type", "Unknown"))
        inputs = node.get("inputs") or {}
        for field, value in inputs.items():
            if _is_link(value):
                continue
            histogram[(class_type, str(field), repr(value))] += 1
    rows = [[class_type, field, value_repr, count] for (class_type, field, value_repr), count in sorted(histogram.items())]
    return json.dumps(rows, indent=2, ensure_ascii=False)


# Public-facing wrappers (identical behaviour, stable names).
def canonicalize_api(api_dict: dict) -> str:
    """Canonical JSON text for the `.api.json` sidecar."""
    return _canonical_api_text(api_dict)


def canonicalize_class_types(api_dict: dict) -> str:
    """Canonical JSON text for the `.class_types.json` sidecar."""
    return _canonical_class_types_text(api_dict)


def canonicalize_widget_values(api_dict: dict) -> str:
    """Canonical JSON text for the `.widget_values.json` sidecar."""
    return _canonical_widget_values_text(api_dict)


# ---------------------------------------------------------------------------
# Seed normaliser
# ---------------------------------------------------------------------------

_DEFAULT_SEED_FIELDS = ("seed", "noise_seed")


def normalize_seed_field(
    api: dict,
    *,
    replacement: int = 0,
    fields: tuple[str, ...] = _DEFAULT_SEED_FIELDS,
) -> dict:
    """Return a shallow copy of `api` with any `seed`/`noise_seed` widget
    rewritten to `replacement`. Used by user recipes/tests to silence
    deliberately non-deterministic seed values before snapshotting.

    Link values (`[node_id, slot]` pairs) are left untouched — a seed sourced
    from another node is structural, not a freeze candidate.
    """
    normalized: dict[str, Any] = {}
    for node_id, node in api.items():
        if not isinstance(node, dict):
            normalized[node_id] = node
            continue
        inputs = dict(node.get("inputs") or {})
        for field in fields:
            if field in inputs and not _is_link(inputs[field]):
                inputs[field] = replacement
        new_node = dict(node)
        new_node["inputs"] = inputs
        normalized[node_id] = new_node
    return normalized


# ---------------------------------------------------------------------------
# User-recipe directive parser
# ---------------------------------------------------------------------------


@dataclass(frozen=True, slots=True)
class RecipeDirective:
    """One parsed `# vibecomfy-snapshot: ...` directive."""

    kind: str  # "ignore-field" or "ignore-node"
    target: str  # `<Class>.<field>` for ignore-field, `<Class>` for ignore-node
    raw: str


_DIRECTIVE_RE = re.compile(
    r"#\s*vibecomfy-snapshot\s*:\s*(ignore-field|ignore-node)\s+([^\s#]+)"
)


def parse_directives(text: str) -> list[RecipeDirective]:
    """Extract `# vibecomfy-snapshot: ...` directives from a Python file body.

    Only `ignore-field <Class>.<field>` and `ignore-node <Class>` are
    recognised today. Anything else (and the central `tests/snapshots/`
    registry) is left alone — directives must NEVER be applied to the
    curated snapshot corpus.
    """
    out: list[RecipeDirective] = []
    for match in _DIRECTIVE_RE.finditer(text):
        kind = match.group(1)
        target = match.group(2)
        if kind == "ignore-field" and "." not in target:
            # Malformed — silently skip so a typo doesn't masquerade as a
            # valid directive.
            continue
        out.append(RecipeDirective(kind=kind, target=target, raw=match.group(0)))
    return out


def apply_directives(api: dict, directives: list[RecipeDirective]) -> dict:
    """Apply `ignore-field`/`ignore-node` directives to a *copy* of `api`.

    `ignore-node <Class>` drops every node whose `class_type` matches.
    `ignore-field <Class>.<field>` drops the named input from every node of
    that class.
    """
    if not directives:
        return api
    ignore_nodes = {d.target for d in directives if d.kind == "ignore-node"}
    ignore_fields: dict[str, set[str]] = {}
    for d in directives:
        if d.kind != "ignore-field":
            continue
        class_type, _, field = d.target.partition(".")
        ignore_fields.setdefault(class_type, set()).add(field)
    out: dict[str, Any] = {}
    for node_id, node in api.items():
        if not isinstance(node, dict):
            out[node_id] = node
            continue
        class_type = str(node.get("class_type", "Unknown"))
        if class_type in ignore_nodes:
            continue
        new_node = dict(node)
        if class_type in ignore_fields:
            inputs = {
                key: value
                for key, value in (node.get("inputs") or {}).items()
                if key not in ignore_fields[class_type]
            }
            new_node["inputs"] = inputs
        out[node_id] = new_node
    return out


# ---------------------------------------------------------------------------
# Recipe loader
# ---------------------------------------------------------------------------


def load_recipe_build(path: str | Path) -> Callable[[], Any] | Any:
    """Load a user recipe file and return the workflow builder.

    Contract:

    1. Precondition: `vibecomfy` must be importable in the active env.
       Many ready-templates do `from vibecomfy.registry.ready_template
       import _node`; if the env is broken we raise `RuntimeError` with a
       clear message rather than letting an opaque ImportError leak.
    2. Prepend `Path(path).parent` to `sys.path` so sibling helpers resolve.
    3. Use a stable module name derived from a hash of the absolute path so
       multiple recipes with the same filename do not collide in
       `sys.modules`.
    4. Restore `sys.path` in a `finally` block.
    5. Prefer the module's `build()` callable; fall back to a module-level
       `WORKFLOW` attribute.

    The return value is either the `build` callable (caller must invoke it)
    or the materialised `WORKFLOW`.
    """
    try:
        importlib.util.find_spec("vibecomfy")
    except (ModuleNotFoundError, ValueError) as exc:
        raise RuntimeError(
            "load_recipe_build: `vibecomfy` is not importable in the active env. "
            "Install the package (`pip install -e .` or equivalent) before "
            "loading a recipe — many ready_templates import "
            "`from vibecomfy.registry.ready_template import _node` at module "
            "level."
        ) from exc

    target = Path(path).resolve()
    if not target.is_file():
        raise FileNotFoundError(f"load_recipe_build: recipe path does not exist: {target}")

    parent = str(target.parent)
    digest = hashlib.sha1(str(target).encode("utf-8")).hexdigest()[:12]
    module_name = f"vibecomfy_recipe_{target.stem}_{digest}"

    added_parent = False
    if parent not in sys.path:
        sys.path.insert(0, parent)
        added_parent = True
    try:
        spec = importlib.util.spec_from_file_location(module_name, str(target))
        if spec is None or spec.loader is None:  # pragma: no cover - defensive
            raise RuntimeError(f"load_recipe_build: could not build import spec for {target}")
        module = importlib.util.module_from_spec(spec)
        sys.modules[module_name] = module
        try:
            spec.loader.exec_module(module)
        except Exception:
            sys.modules.pop(module_name, None)
            raise
    finally:
        if added_parent:
            try:
                sys.path.remove(parent)
            except ValueError:  # pragma: no cover - already removed
                pass

    build = getattr(module, "build", None)
    if callable(build):
        return build
    workflow = getattr(module, "WORKFLOW", None)
    if workflow is not None:
        return workflow
    raise RuntimeError(
        f"load_recipe_build: {target} must define `build()` or a module-level "
        "`WORKFLOW` attribute."
    )
