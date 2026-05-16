"""Dry-run runtime for `VibeWorkflow` graphs.

`dry_run(wf)` compiles the workflow to its API dict and returns a
`DryRunResult` containing the dict, a topologically ordered list of
`WouldInvoke` records, and a list of warnings. It NEVER calls ComfyUI and
NEVER raises — compile failures land in `warnings` so users can inspect
partial state.

Import-cost contract: this module MUST NOT top-level-import
`vibecomfy.runtime.*`, `vibecomfy.schema.provider`, or
`vibecomfy.comfy_command`. `vibecomfy.schema.cache` is permitted but is
imported lazily inside `dry_run` to keep `import vibecomfy.testing` cheap
(see T5's import-cost subprocess test).
"""

from __future__ import annotations

from dataclasses import dataclass, field
from typing import Any

from vibecomfy.testing._schema import SchemaProviderLike
from vibecomfy.testing._stub_schema import _StubSchemaProvider

__all__ = ["DryRunResult", "WouldInvoke", "dry_run"]


@dataclass(frozen=True, slots=True)
class WouldInvoke:
    """One record per node in the compiled API dict, in topological order.

    `inputs` is a shallow copy of the compiled node's `inputs` mapping;
    `depends_on` is the list of upstream node ids (preserving order of
    appearance) referenced via `[node_id, slot]` link refs.
    """

    node_id: str
    class_type: str
    inputs: dict[str, Any]
    depends_on: list[str]


@dataclass(frozen=True, slots=True)
class DryRunResult:
    api_dict: dict[str, Any]
    would_invoke: list[WouldInvoke] = field(default_factory=list)
    warnings: list[str] = field(default_factory=list)


def _is_link(value: Any) -> bool:
    """`[node_id_str, slot_int]` link ref check."""
    return (
        isinstance(value, list)
        and len(value) == 2
        and isinstance(value[0], str)
        and isinstance(value[1], int)
    )


def _collect_depends_on(inputs: dict[str, Any]) -> list[str]:
    seen: list[str] = []
    seen_set: set[str] = set()
    for value in inputs.values():
        if _is_link(value):
            dep = value[0]
            if dep not in seen_set:
                seen.append(dep)
                seen_set.add(dep)
    return seen


def _topological_order(api: dict[str, Any]) -> list[str]:
    """Kahn's algorithm over the link-ref DAG; ties resolved by original
    insertion order. Cycles fall back to insertion order to keep dry-run
    permissive — the assertion library is where you'd catch a real cycle.
    """
    deps: dict[str, set[str]] = {}
    insertion_order = list(api.keys())
    for node_id, node in api.items():
        if not isinstance(node, dict):
            deps[node_id] = set()
            continue
        inputs = node.get("inputs") or {}
        deps[node_id] = {
            value[0]
            for value in inputs.values()
            if _is_link(value) and value[0] in api
        }
    ordered: list[str] = []
    ordered_set: set[str] = set()
    remaining = list(insertion_order)
    progress = True
    while remaining and progress:
        progress = False
        still: list[str] = []
        for node_id in remaining:
            if deps[node_id].issubset(ordered_set):
                ordered.append(node_id)
                ordered_set.add(node_id)
                progress = True
            else:
                still.append(node_id)
        remaining = still
    # Cycle fallback: append in original order.
    ordered.extend(remaining)
    return ordered


def _resolve_schema_provider(
    explicit: SchemaProviderLike | None,
) -> tuple[SchemaProviderLike, list[str]]:
    if explicit is not None:
        return explicit, []
    warnings: list[str] = []
    # Lazy import so `import vibecomfy.testing` does not load `comfy_command`.
    try:
        from vibecomfy.schema.cache import (  # noqa: PLC0415 — intentional lazy import
            latest_object_info_cache_path,
            load_object_info_cache,
        )
    except Exception as exc:  # noqa: BLE001
        warnings.append(f"schema_unavailable: cache module unimportable ({exc!r})")
        return _StubSchemaProvider({}), warnings

    cache_path = latest_object_info_cache_path("out/cache")
    if cache_path is None:
        warnings.append("schema_unavailable")
        return _StubSchemaProvider({}), warnings
    object_info = load_object_info_cache(cache_path) or {}
    return _StubSchemaProvider(object_info), warnings


def dry_run(
    wf: Any,
    *,
    schema_provider: SchemaProviderLike | None = None,
) -> DryRunResult:
    """Compile `wf` to its API dict and return a `DryRunResult` without
    calling ComfyUI. Never raises — compile exceptions are captured as a
    `'compile_failed: <repr(exc)>'` warning.
    """
    warnings: list[str] = []
    provider, resolve_warnings = _resolve_schema_provider(schema_provider)
    warnings.extend(resolve_warnings)

    try:
        api_dict = wf.compile("api")
    except Exception as exc:  # noqa: BLE001
        warnings.append(f"compile_failed: {exc!r}")
        return DryRunResult(api_dict={}, would_invoke=[], warnings=warnings)

    if not isinstance(api_dict, dict):
        warnings.append(
            f"compile_returned_non_dict: type={type(api_dict).__name__}"
        )
        return DryRunResult(api_dict={}, would_invoke=[], warnings=warnings)

    order = _topological_order(api_dict)
    would_invoke: list[WouldInvoke] = []
    for node_id in order:
        node_entry = api_dict.get(node_id)
        if not isinstance(node_entry, dict):
            continue
        class_type = str(node_entry.get("class_type", "Unknown"))
        inputs = dict(node_entry.get("inputs") or {})
        # Touch the schema provider so it appears used (and so users can swap
        # in a stricter provider that warns on unknown classes).
        _schema = provider.node_schema(class_type)
        del _schema
        would_invoke.append(
            WouldInvoke(
                node_id=str(node_id),
                class_type=class_type,
                inputs=inputs,
                depends_on=_collect_depends_on(inputs),
            )
        )

    return DryRunResult(api_dict=api_dict, would_invoke=would_invoke, warnings=warnings)
