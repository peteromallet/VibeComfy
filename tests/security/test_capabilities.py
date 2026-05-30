"""Tests for vibecomfy.security capabilities module (T2)."""
from __future__ import annotations

import re
import subprocess
import sys


def test_output_classes_map_to_filesystem_write() -> None:
    """Every _OUTPUT_CLASSES key maps to filesystem_write."""
    from vibecomfy.security._seed import OUTPUT_CLASS_NAMES
    from vibecomfy.security.capabilities import capabilities_for

    for name in OUTPUT_CLASS_NAMES:
        caps = capabilities_for(name)
        assert "filesystem_write" in caps, f"{name!r} should have filesystem_write"


def test_output_node_names_map_to_filesystem_write() -> None:
    """Every OUTPUT_NODE_NAMES entry maps to filesystem_write."""
    from vibecomfy.security._seed import OUTPUT_NODE_NAMES
    from vibecomfy.security.capabilities import capabilities_for

    for name in OUTPUT_NODE_NAMES:
        caps = capabilities_for(name)
        assert "filesystem_write" in caps, f"{name!r} should have filesystem_write"


def test_passthrough_nodes() -> None:
    """Core non-side-effecting nodes map to passthrough."""
    from vibecomfy.security.capabilities import capabilities_for

    for name in ("CLIPTextEncode", "KSampler", "VAEDecode"):
        caps = capabilities_for(name)
        assert caps == frozenset({"passthrough"}), (
            f"{name!r} should map to passthrough, got {caps!r}"
        )


def test_unknown_class_returns_quarantine_default() -> None:
    """An unknown class returns the code_exec quarantine default."""
    from vibecomfy.security.capabilities import capabilities_for, unknown_class_policy

    result = capabilities_for("SomeCompletelyUnknownNode_XYZ")
    assert result == unknown_class_policy()
    assert result == frozenset({"code_exec"})


def test_taxonomy_values_are_frozensets() -> None:
    """All CAPABILITY_TAXONOMY values are frozenset instances."""
    from vibecomfy.security.capabilities import CAPABILITY_TAXONOMY

    for name, caps in CAPABILITY_TAXONOMY.items():
        assert isinstance(caps, frozenset), (
            f"CAPABILITY_TAXONOMY[{name!r}] is {type(caps)}, expected frozenset"
        )


def test_unknown_class_policy_returns_frozenset() -> None:
    from vibecomfy.security.capabilities import unknown_class_policy

    result = unknown_class_policy()
    assert isinstance(result, frozenset)
    assert result == frozenset({"code_exec"})


def test_no_forbidden_imports_in_security_package() -> None:
    """security/__init__.py and capabilities.py must not import from forbidden layers."""
    import importlib.util
    import pathlib

    forbidden = {"analysis", "runtime", "porting", "registry"}
    security_root = pathlib.Path(__file__).parent.parent.parent / "vibecomfy" / "security"
    targets = [security_root / "__init__.py", security_root / "capabilities.py"]

    import_re = re.compile(r"^\s*(?:import|from)\s+([\w.]+)")

    for path in targets:
        source = path.read_text()
        for line in source.splitlines():
            m = import_re.match(line)
            if not m:
                continue
            module = m.group(1)
            parts = module.split(".")
            for part in parts:
                assert part not in forbidden, (
                    f"{path.name} imports from forbidden layer {part!r}: {line!r}"
                )
