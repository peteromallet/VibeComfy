"""Workflow node-coverage helper.

Provides :func:`build_workflow_coverage` which checks each class_type in a
workflow against three sources to determine coverage status:

1. **Typed wrapper** — ``vibecomfy.blocks.*`` wrapper modules that emit
   the class via a registered block function.
2. **Schema provider** — the class is known to the local schema index
   or object-info cache.
3. **custom_nodes.lock** — the pack that provides the class is listed in
   the lockfile.
"""

from __future__ import annotations

from collections import Counter
from dataclasses import dataclass, field
from pathlib import Path
from typing import Any

from vibecomfy.blocks import registered_blocks
from vibecomfy.blocks._utils import add_block_node
from vibecomfy.node_packs import LockEntry, read_lockfile
from vibecomfy.workflow import VibeWorkflow


@dataclass
class WorkflowCoverage:
    """Coverage report for a single workflow."""

    per_class: list[dict[str, Any]] = field(default_factory=list)
    total: int = 0
    typed_wrapper: int = 0
    raw_call: int = 0
    missing_lock: int = 0

    def to_json(self) -> dict[str, Any]:
        return {
            "per_class": self.per_class,
            "total": self.total,
            "typed_wrapper": self.typed_wrapper,
            "raw_call": self.raw_call,
            "missing_lock": self.missing_lock,
            "coverage_pct": (
                round(self.typed_wrapper / self.total * 100, 1)
                if self.total > 0
                else 0
            ),
        }


def build_workflow_coverage(
    workflow: VibeWorkflow,
    *,
    schema_provider: Any = None,
    lock_entries: list[LockEntry] | None = None,
    lock_path: Path | None = None,
) -> WorkflowCoverage:
    """Build a coverage report for *workflow*.

    Each class_type is classified as:

    * ``typed_wrapper`` — a block function in ``vibecomfy.blocks.*``
      emits this class via ``add_block_node``.
    * ``raw_call`` — the class has no typed wrapper but IS known to be
      a core ComfyUI class or is in the schema provider.
    * ``missing_lock`` — the class requires a custom-node pack that is
      not listed in ``custom_nodes.lock``.

    Args:
        workflow: The workflow to analyze.
        schema_provider: Optional schema provider for schema lookups.
        lock_entries: Pre-parsed lock entries (avoids re-reading lockfile).
        lock_path: Path to the custom_nodes.lock file.
    """
    if lock_entries is None:
        lock_entries = _safe_read_lock(lock_path)

    # Build the set of class_types that have typed wrappers
    typed_wrapper_classes = _build_typed_wrapper_set()

    coverage = WorkflowCoverage()
    seen: set[str] = set()

    for node in workflow.nodes.values():
        ct = node.class_type
        if ct in seen:
            continue
        seen.add(ct)

        coverage.total += 1

        pack = node.pack or _infer_pack(ct, schema_provider, lock_entries)

        if ct in typed_wrapper_classes:
            coverage.typed_wrapper += 1
            status = "typed_wrapper"
        elif _is_core_comfy_class(ct):
            coverage.raw_call += 1
            status = "raw_call"
        elif schema_provider is not None:
            try:
                schema = schema_provider.get_schema(ct) if hasattr(schema_provider, "get_schema") else None
            except Exception:
                schema = None
            if schema is not None:
                coverage.raw_call += 1
                status = "raw_call"
            else:
                # Check if pack is in lock
                if _pack_in_lock(pack, lock_entries):
                    coverage.raw_call += 1
                    status = "raw_call"
                else:
                    coverage.missing_lock += 1
                    status = "missing_lock"
        else:
            # No schema provider — check lock
            if _pack_in_lock(pack, lock_entries):
                coverage.raw_call += 1
                status = "raw_call"
            else:
                coverage.missing_lock += 1
                status = "missing_lock"

        coverage.per_class.append(
            {
                "class_type": ct,
                "pack": pack or "unknown",
                "coverage": status,
            }
        )

    return coverage


# -- internal helpers ---------------------------------------------------------

_CORE_CLASSES: frozenset[str] = frozenset(
    {
        "CFGGuider",
        "CheckpointLoaderSimple",
        "CLIPLoader",
        "CLIPTextEncode",
        "CLIPVisionEncode",
        "CLIPVisionLoader",
        "CreateVideo",
        "DualCLIPLoader",
        "ImageScaleBy",
        "KSampler",
        "KSamplerSelect",
        "LoadImage",
        "LoraLoaderModelOnly",
        "ManualSigmas",
        "ModelSamplingSD3",
        "PrimitiveBoolean",
        "PrimitiveFloat",
        "PrimitiveInt",
        "PrimitiveNode",
        "PrimitiveString",
        "PrimitiveStringMultiline",
        "RandomNoise",
        "SamplerCustomAdvanced",
        "SaveImage",
        "SaveVideo",
        "UNETLoader",
        "VAEDecode",
        "VAEDecodeTiled",
        "VAELoader",
        "WanImageToVideo",
    }
)


def _is_core_comfy_class(class_type: str) -> bool:
    """Check if *class_type* is a known core ComfyUI class."""
    return class_type in _CORE_CLASSES


def _import_block_submodules() -> None:
    """Compatibility shim for the shared lazy block-module importer."""
    from vibecomfy.blocks._wrapper_discovery import import_block_submodules

    import_block_submodules()


def _build_typed_wrapper_set() -> frozenset[str]:
    """Scan registered block functions for class_types they emit.

    This inspects the ``_BLOCK_REGISTRY`` and traverses the bytecode of
    each block function looking for ``add_block_node`` calls to extract
    the class_type strings.
    """
    _import_block_submodules()
    try:
        blocks = dict(registered_blocks())
    except Exception:
        return frozenset()

    from vibecomfy.blocks._wrapper_discovery import extract_typed_wrapper_class_types

    # Keep extraction outside the narrow registry try: unexpected inspection
    # errors must retain coverage's existing propagation behavior.
    return extract_typed_wrapper_class_types(blocks)


def _infer_pack(
    class_type: str,
    schema_provider: Any,
    lock_entries: list[LockEntry],
) -> str | None:
    """Infer the pack name for a class_type."""
    if _is_core_comfy_class(class_type):
        return "comfy.core"

    # Try schema provider
    if schema_provider is not None:
        try:
            schema = schema_provider.get_schema(class_type) if hasattr(schema_provider, "get_schema") else None
            if schema is not None:
                pack = getattr(schema, "pack", None) or getattr(schema, "pack_name", None)
                if pack:
                    return str(pack)
        except Exception:
            pass

    return None


def _pack_in_lock(pack: str | None, lock_entries: list[LockEntry]) -> bool:
    """Check if *pack* is represented in lock entries."""
    if not pack:
        return False
    if pack == "comfy.core":
        return True
    for entry in lock_entries:
        if entry.name == pack:
            return True
    return False


def _safe_read_lock(lock_path: Path | None = None) -> list[LockEntry]:
    """Read lock entries, returning empty list on any error."""
    try:
        return read_lockfile(lock_path or Path("custom_nodes.lock"))
    except (OSError, ValueError):
        return []


__all__ = [
    "WorkflowCoverage",
    "build_workflow_coverage",
]
