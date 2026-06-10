"""Tests for vibecomfy.security.capabilities."""

from __future__ import annotations

import re
from pathlib import Path

import pytest

from vibecomfy.security import (
    CAPABILITY_TAXONOMY,
    capabilities_for,
    is_side_effecting,
    unknown_class_policy,
)
from vibecomfy.security._seed import (
    ALL_SEEDED,
    KNOWN_PASSTHROUGH,
    OUTPUT_NODE_NAMES,
    _OUTPUT_CLASSES_KEYS,
)


FORBIDDEN_IMPORT_PATTERNS: list[str] = [
    r"from\s+vibecomfy\.analysis\b",
    r"from\s+vibecomfy\.runtime\b",
    r"from\s+vibecomfy\.porting\b",
    r"from\s+vibecomfy\.registry\b",
    r"import\s+vibecomfy\.analysis\b",
    r"import\s+vibecomfy\.runtime\b",
    r"import\s+vibecomfy\.porting\b",
    r"import\s+vibecomfy\.registry\b",
]

SECURITY_DIR = Path(__file__).resolve().parent.parent.parent / "vibecomfy" / "security"
FILES_TO_CHECK: list[Path] = [
    SECURITY_DIR / "__init__.py",
    SECURITY_DIR / "capabilities.py",
]


@pytest.mark.parametrize("file_path", FILES_TO_CHECK)
def test_no_forbidden_imports_in_source(file_path: Path) -> None:
    """No security package source import from analysis/runtime/porting/registry."""
    assert file_path.is_file(), f"Missing file: {file_path}"
    source = file_path.read_text()
    for pattern in FORBIDDEN_IMPORT_PATTERNS:
        assert not re.search(pattern, source), (
            f"Forbidden import pattern {pattern!r} found in {file_path.name}"
        )


def test_output_classes_map_to_filesystem_write() -> None:
    for class_type in _OUTPUT_CLASSES_KEYS:
        caps = capabilities_for(class_type)
        assert "filesystem_write" in caps, (
            f"{class_type!r} should have filesystem_write, got {caps}"
        )


def test_output_node_names_map_to_filesystem_write() -> None:
    for class_type in OUTPUT_NODE_NAMES:
        caps = capabilities_for(class_type)
        assert "filesystem_write" in caps, (
            f"{class_type!r} should have filesystem_write, got {caps}"
        )


def test_cliptextencode_is_passthrough() -> None:
    assert capabilities_for("CLIPTextEncode") == frozenset({"passthrough"})


def test_ksampler_is_passthrough() -> None:
    assert capabilities_for("KSampler") == frozenset({"passthrough"})


def test_vaedecode_is_passthrough() -> None:
    assert capabilities_for("VAEDecode") == frozenset({"passthrough"})


def test_unknown_class_returns_quarantine_default() -> None:
    caps = capabilities_for("TotallyMadeUpClassNameThatDoesNotExist")
    assert caps == unknown_class_policy()
    assert caps == frozenset({"code_exec"})


def test_taxonomy_values_are_frozenset() -> None:
    for class_type, caps in CAPABILITY_TAXONOMY.items():
        assert isinstance(caps, frozenset), (
            f"CAPABILITY_TAXONOMY[{class_type!r}] must be frozenset, "
            f"got {type(caps).__name__}"
        )


def test_unknown_class_policy_returns_frozenset() -> None:
    result = unknown_class_policy()
    assert isinstance(result, frozenset)
    assert result == frozenset({"code_exec"})


def test_is_side_effecting_passthrough() -> None:
    assert not is_side_effecting("CLIPTextEncode")
    assert not is_side_effecting("KSampler")
    assert not is_side_effecting("VAEDecode")


def test_is_side_effecting_filesystem_write() -> None:
    assert is_side_effecting("SaveImage")
    assert is_side_effecting("VHS_VideoCombine")


def test_is_side_effecting_unknown() -> None:
    assert is_side_effecting("TotallyMadeUpClassNameThatDoesNotExist")


def test_seeded_coverage_at_least_95_percent() -> None:
    covered: set[str] = set(CAPABILITY_TAXONOMY.keys()) | KNOWN_PASSTHROUGH
    all_seeded_set: set[str] = set(ALL_SEEDED)

    uncovered: set[str] = all_seeded_set - covered
    total = len(all_seeded_set)
    covered_count = total - len(uncovered)
    coverage_pct = (covered_count / total * 100) if total > 0 else 100.0

    assert coverage_pct >= 95.0, (
        f"Coverage is {coverage_pct:.1f}% ({covered_count}/{total}); "
        f"must be >=95%. Uncovered: {sorted(uncovered)}"
    )
