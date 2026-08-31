"""Shared mechanics for discovering literal typed-wrapper class types.

This module deliberately owns neither registry acquisition policy nor caching.
Callers use :func:`import_block_submodules` to perform lazy decorator imports,
snapshot their registry with their existing error envelope, and then pass that
snapshot to :func:`extract_typed_wrapper_class_types`.
"""

from __future__ import annotations

import importlib
import inspect
import re
from collections.abc import Mapping
from typing import Any


_BLOCK_MODULES: tuple[str, ...] = (
    "vibecomfy.blocks.loaders",
    "vibecomfy.blocks.sampling",
    "vibecomfy.blocks.encoding",
    "vibecomfy.blocks.decode",
    "vibecomfy.blocks.latent",
    "vibecomfy.blocks.save",
    "vibecomfy.blocks.video",
    "vibecomfy.blocks.subgraph",
)
_TYPED_WRAPPER_CALL_RE = re.compile(
    r'add_block_node\s*\([^)]*?["\']([A-Za-z_][A-Za-z0-9_]*)["\']'
)


def import_block_submodules() -> None:
    """Import every block module, continuing after per-module failures."""
    for module_name in _BLOCK_MODULES:
        try:
            importlib.import_module(module_name)
        except Exception:
            pass


def extract_typed_wrapper_class_types(
    blocks: Mapping[str, Any],
) -> frozenset[str]:
    """Extract literal class types from an already-snapshotted block registry.

    Source-inspection failures known from ordinary Python callables
    (``OSError`` and ``TypeError``) are skipped per function. Other exceptions
    intentionally propagate so callers can preserve their own failure
    envelopes.
    """
    wrapper_classes: set[str] = set()
    for block_fn in blocks.values():
        try:
            source = inspect.getsource(block_fn)
            for match in _TYPED_WRAPPER_CALL_RE.finditer(source):
                class_type = match.group(1)
                if class_type != "vibecomfy":
                    wrapper_classes.add(class_type)
        except (OSError, TypeError):
            pass
    return frozenset(wrapper_classes)
