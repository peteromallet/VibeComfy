"""VibeComfy capability-fence security package.

Public surface:
  Capability            — string literal type for the four capability tags
  CAPABILITY_TAXONOMY   — frozen mapping of known class_type → frozenset[Capability]
  capabilities_for      — lookup helper (returns quarantine default for unknowns)
  is_side_effecting     — convenience predicate
  unknown_class_policy  — returns the quarantine frozenset (frozenset{"code_exec"})

No imports from analysis, runtime, porting, or registry are permitted here.
"""
from vibecomfy.security.capabilities import (
    CAPABILITY_TAXONOMY,
    Capability,
    capabilities_for,
    is_side_effecting,
    unknown_class_policy,
)

__all__ = [
    "Capability",
    "CAPABILITY_TAXONOMY",
    "capabilities_for",
    "is_side_effecting",
    "unknown_class_policy",
]
