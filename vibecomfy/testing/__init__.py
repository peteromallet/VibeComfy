"""Public testing surface for VibeComfy users.

This subpackage gives users a `pytest`-style toolkit for asserting on
`VibeWorkflow` graphs and compiled API dicts, plus a dry-run runtime
and snapshot helpers.

Implementation modules (`assertions`, `dry_run`, `fixtures`, `snapshot`)
are filled in by later tasks; this scaffold forward-declares the public
names so users can rely on a stable import surface from day one.

Import-cost contract: this module (and everything it imports at module
level) MUST NOT pull in `vibecomfy.schema.provider`, `vibecomfy.runtime.*`,
or `vibecomfy.comfy_command`. Use the local Protocols in
`vibecomfy.testing._schema` (`SchemaProviderLike`, `NodeSchemaLike`)
when type annotations are needed.
"""

from __future__ import annotations

from vibecomfy.testing._schema import NodeSchemaLike, SchemaProviderLike
from vibecomfy.testing.assertions import (
    assert_compiles_cleanly,
    assert_edge,
    assert_input_bound,
    assert_input_value,
    assert_no_dangling_handles,
    assert_node_present,
    assert_output_kind,
)
from vibecomfy.testing.dry_run import DryRunResult, WouldInvoke, dry_run
from vibecomfy.testing.snapshot import canonicalize_api

__all__ = [
    # Schema Protocols (local, runtime-free)
    "NodeSchemaLike",
    "SchemaProviderLike",
    # Assertions (filled in by T2)
    "assert_node_present",
    "assert_edge",
    "assert_input_value",
    "assert_output_kind",
    "assert_input_bound",
    "assert_compiles_cleanly",
    "assert_no_dangling_handles",
    # Dry-run runtime (filled in by T3)
    "dry_run",
    "DryRunResult",
    "WouldInvoke",
    # Fixtures (filled in by T4)
    "vibecomfy_workflow_factory",
    "vibecomfy_handle_factory",
    "dry_runtime",
    "make_workflow_factory",
    "make_handle_factory",
    # Snapshot helpers (filled in by T6)
    "canonicalize_api",
]


def _not_yet_implemented(_name: str):
    def _stub(*_args, **_kwargs):  # pragma: no cover - placeholder
        raise NotImplementedError(
            f"vibecomfy.testing.{_name} is forward-declared by T1; "
            "implementation lands in a later batch."
        )

    _stub.__name__ = _name
    _stub.__qualname__ = _name
    return _stub


# Forward-declared placeholders. Later batches replace each of these with
# `from .<module> import <name>` re-exports.
# (T2: assertions now imported above.)

vibecomfy_workflow_factory = _not_yet_implemented("vibecomfy_workflow_factory")
vibecomfy_handle_factory = _not_yet_implemented("vibecomfy_handle_factory")
dry_runtime = _not_yet_implemented("dry_runtime")
make_workflow_factory = _not_yet_implemented("make_workflow_factory")
make_handle_factory = _not_yet_implemented("make_handle_factory")
