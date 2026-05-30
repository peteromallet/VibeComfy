"""Static capability taxonomy for ComfyUI node classes.

Design decisions are documented in docs/security/capability_taxonomy.md.
This module has NO imports from analysis, runtime, porting, or registry.
"""
from __future__ import annotations

import re
from typing import Literal

from vibecomfy.security._seed import ALL_SEEDED

Capability = Literal["filesystem_write", "network", "code_exec", "passthrough"]

# Pattern that identifies side-effecting node classes from their name alone.
_SIDE_EFFECTING_RE = re.compile(
    r"^(Save.*|Preview.*|Download.*Load|.*Expression|.*Eval|VHS_VideoCombine|VHS_LoadVideo.*)$"
)


def _classify(class_type: str) -> frozenset[Capability]:
    if _SIDE_EFFECTING_RE.match(class_type):
        return frozenset({"filesystem_write"})
    return frozenset({"passthrough"})


# Frozen taxonomy built by walking ALL_SEEDED and applying the classifier.
CAPABILITY_TAXONOMY: dict[str, frozenset[Capability]] = {
    name: _classify(name) for name in ALL_SEEDED
}


def capabilities_for(class_type: str) -> frozenset[Capability]:
    """Return the capability set for *class_type*.

    Returns the quarantine default (``frozenset({"code_exec"})``) for any
    class not present in the taxonomy — fail-closed per SD1.
    """
    return CAPABILITY_TAXONOMY.get(class_type, unknown_class_policy())


def is_side_effecting(class_type: str) -> bool:
    """Return True if *class_type* has any non-passthrough capability."""
    caps = capabilities_for(class_type)
    return caps != frozenset({"passthrough"})


def unknown_class_policy() -> frozenset[Capability]:
    """Quarantine default for unknown node classes (SD1: treat as code_exec-suspect)."""
    return frozenset({"code_exec"})
