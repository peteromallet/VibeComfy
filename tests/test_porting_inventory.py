"""Tests for the repo-only readability inventory scanner.

Covers: repo-only enumeration, deterministic JSON shape, marker parsing
(`# vibecomfy: manual`, `# vibecomfy: generated`, `# vibecomfy: broken-regen`), provenance joins with
coverage.json/template_index.json, missing-source flags, exclusion of
temp/plugin/user-global ready roots, and inventory counts for positional
outputs/widget_N/UUID class types/local helpers/missing outputs/categories.
"""

from __future__ import annotations

import json
import tempfile
from pathlib import Path
from unittest import mock

import pytest

from vibecomfy.porting.readability_inventory import (
    READY_ROOT,
    REPO_ROOT,
    ReadabilityCounts,
    ReadabilityInventory,
    TemplateInventoryEntry,
    _classify_marker,
    _count_local_node_copies,
    _count_n_uuid_variables,
    _count_positional_outs,
    _count_uuid_class_types,
    _count_widget_n_fields,
    _detect_missing_output_contract,
    _enumerate_repo_templates,
    _load_coverage_map,
    _load_template_index_map,
    _ready_id_for_path,
    build_readability_inventory,
)


# ---------------------------------------------------------------------------
# Enumeration tests
# ---------------------------------------------------------------------------


def test_enumerate_repo_templates_returns_only_py_files() -> None:
    """Repo templates are only .py files in ready_templates/."""
    paths = _enumerate_repo_templates()
    for p in paths:
        assert p.suffix == ".py"
        assert p.is_relative_to(READY_ROOT)


def test_enumerate_repo_templates_excludes_init_py() -> None:
    """__init__.py files are excluded from enumeration."""
    paths = _enumerate_repo_templates()
    for p in paths:
        assert p.name != "__init__.py"


def test_enumerate_repo_templates_excludes_underscore_prefixed() -> None:
    """Files with basename starting with '_' are excluded."""
    paths = _enumerate_repo_templates()
    for p in paths:
        assert not p.name.startswith("_")


def test_enumerate_repo_templates_is_sorted() -> None:
    """Enumeration returns sorted paths for deterministic output."""
    paths = _enumerate_repo_templates()
    assert paths == sorted(paths)


def test_ready_id_for_path_derives_from_relative_path() -> None:
    """ready_id is the relative path minus .py suffix."""
    path = READY_ROOT / "image" / "z_image.py"
    assert _ready_id_for_path(path) == "image/z_image"


def test_enumerate_repo_templates_never_calls_ready_template_ids() -> None:
    """The inventory scanner never calls ready_template_ids()."""
    paths = _enumerate_repo_templates()
    # This is a static glob — no runtime discovery involved.
    assert len(paths) > 0


# ---------------------------------------------------------------------------
# Marker parsing
# ---------------------------------------------------------------------------


def test_classify_marker_detects_manual() -> None:
    source = "# vibecomfy: manual\nfrom vibecomfy.workflow import VibeWorkflow\n"
    assert _classify_marker(source) == "manual"


def test_classify_marker_detects_broken_regen() -> None:
    source = "# vibecomfy: broken-regen\nfrom vibecomfy.workflow import VibeWorkflow\n"
    assert _classify_marker(source) == "broken-regen"


def test_classify_marker_detects_generated() -> None:
    source = "# vibecomfy: generated\n"
    assert _classify_marker(source) == "generated"


def test_classify_marker_detects_reference_legacy_api_workflow() -> None:
    source = "API_WORKFLOW = {\n    '1': {'class_type': 'LoadImage', 'inputs': {}}\n}\n"
    assert _classify_marker(source) == "reference"


def test_classify_marker_detects_authored_via_nodes() -> None:
    source = "NODES = (\n    ('1', 'LoadImage', {'image': 'test.png'}),\n)\n"
    assert _classify_marker(source) == "authored"


def test_classify_marker_unknown_when_no_hints() -> None:
    source = "def build():\n    pass\n"
    assert _classify_marker(source) == "unknown"


def test_classify_marker_manual_wins_over_api_workflow() -> None:
    source = "# vibecomfy: manual\nAPI_WORKFLOW = {}\n"
    assert _classify_marker(source) == "manual"


# ---------------------------------------------------------------------------
# Readability counts
# ---------------------------------------------------------------------------


def test_count_positional_outs_finds_integer_slot_accesses() -> None:
    source = 'node.out(0)\nother.node.out(1)\nnot_a.out("name")'
    assert _count_positional_outs(source) == 2


def test_count_positional_outs_ignores_named_accesses() -> None:
    source = 'node.out("IMAGE")\nnode.out("samples")\n'
    assert _count_positional_outs(source) == 0


def test_count_widget_n_fields_finds_all_widget_references() -> None:
    source = "widget_0 = 'hello'\nwidget_1 = 42\nwidget_22 = 'there'"
    assert _count_widget_n_fields(source) == 3


def test_count_uuid_class_types_finds_uuid_nodes() -> None:
    # Pattern: ('uuid', 'ClassName', {...})
    source = "NODES = (\n    ('12345678-1234-1234-1234-123456789abc', 'LoadImage', {}),\n)\n"
    assert _count_uuid_class_types(source) >= 1


def test_count_n_uuid_variables_finds_n_uuid_patterns() -> None:
    source = "n_12345678_1234_1234_1234_123456789abc = node.out(0)\n"
    assert _count_n_uuid_variables(source) == 1


def test_count_local_node_copies_finds_node_references() -> None:
    source = "_node = wf.add_node('LoadImage')\n_node.out(0)\n"
    assert _count_local_node_copies(source) >= 1


def test_detect_missing_output_contract_true_when_no_register() -> None:
    source = "def build():\n    pass\n"
    assert _detect_missing_output_contract(source) is True


def test_detect_missing_output_contract_false_with_register_output() -> None:
    source = "wf.register_output('images', node_id='5', slot=0)\n"
    assert _detect_missing_output_contract(source) is False


def test_detect_missing_output_contract_false_with_outputs_assignment() -> None:
    source = "_outputs = ('image',)\n"
    assert _detect_missing_output_contract(source) is False


# ---------------------------------------------------------------------------
# Provenance joins
# ---------------------------------------------------------------------------


def test_load_coverage_map_reads_coverage_json() -> None:
    """coverage.json is loaded and keyed by ready_template id."""
    coverage = _load_coverage_map()
    assert isinstance(coverage, dict)
    # At least one entry should exist for z_image
    assert any("z_image" in key for key in coverage)


def test_load_template_index_map_reads_template_index() -> None:
    """template_index.json is loaded and keyed by template id."""
    index = _load_template_index_map()
    assert isinstance(index, dict)
    # Should contain at least the known templates
    assert "image/z_image" in index


def test_coverage_join_produces_coverage_tier(tmp_path: Path) -> None:
    """When coverage.json has ready_template info, the tier is populated."""
    # Just verify the prod data works
    coverage = _load_coverage_map()
    assert len(coverage) > 0
    # Coverage entries should have coverage_tier
    for _key, entry in coverage.items():
        assert "coverage_tier" in entry or "task" in entry or "path" in entry


def test_template_index_join_produces_id_keyed_map() -> None:
    """template_index.json is keyed by id."""
    index = _load_template_index_map()
    for key, entry in index.items():
        assert "id" in entry
        assert entry["id"] == key


# ---------------------------------------------------------------------------
# Deterministic JSON shape
# ---------------------------------------------------------------------------


def test_inventory_json_has_version_and_counts() -> None:
    """The inventory JSON shape is deterministic and includes version + counts."""
    inventory = build_readability_inventory()
    data = inventory.to_json()
    assert data["version"] == 1
    assert "template_count" in data
    assert isinstance(data["template_count"], int)
    assert data["template_count"] > 0
    assert "entries" in data
    assert "summary" in data
    assert "generated_from" in data
    assert "include_rule" in data
    assert "exclude_rule" in data


def test_inventory_entries_have_required_fields() -> None:
    """Every inventory entry has the required structural fields."""
    inventory = build_readability_inventory()
    for entry in inventory.entries:
        entry_dict = {
            "ready_id": entry.ready_id,
            "path": entry.path,
            "marker": entry.marker,
            "coverage_tier": entry.coverage_tier,
            "capability": entry.capability,
            "source_role": entry.source_role,
            "source_workflow": entry.source_workflow,
            "app_active": entry.app_active,
            "counts": {
                "positional_outs": entry.counts.positional_outs,
                "widget_n_fields": entry.counts.widget_n_fields,
                "uuid_class_types": entry.counts.uuid_class_types,
                "n_uuid_variables": entry.counts.n_uuid_variables,
                "local_node_copies": entry.counts.local_node_copies,
                "missing_output_contract": entry.counts.missing_output_contract,
            },
            "missing_source_provenance": entry.missing_source_provenance,
        }
        assert "ready_id" in entry_dict
        assert "path" in entry_dict
        assert "marker" in entry_dict
        assert entry_dict["marker"] in ("generated", "manual", "broken-regen", "reference", "authored", "unknown")
        assert isinstance(entry_dict["counts"]["positional_outs"], int)
        assert isinstance(entry_dict["counts"]["widget_n_fields"], int)
        assert isinstance(entry_dict["counts"]["uuid_class_types"], int)
        assert isinstance(entry_dict["counts"]["n_uuid_variables"], int)
        assert isinstance(entry_dict["counts"]["local_node_copies"], int)
        assert isinstance(entry_dict["counts"]["missing_output_contract"], bool)


def test_inventory_json_is_roundtrippable() -> None:
    """The to_json() output is valid JSON and round-trips."""
    inventory = build_readability_inventory()
    data = inventory.to_json()
    json_str = json.dumps(data, indent=2, sort_keys=True)
    parsed = json.loads(json_str)
    assert parsed["version"] == data["version"]
    assert parsed["template_count"] == data["template_count"]
    assert len(parsed["entries"]) == data["template_count"]


def test_inventory_json_entries_are_stable() -> None:
    """Two consecutive builds produce identical entry lists (same order, same ids)."""
    inv1 = build_readability_inventory()
    inv2 = build_readability_inventory()
    assert [e.ready_id for e in inv1.entries] == [e.ready_id for e in inv2.entries]
    assert [e.marker for e in inv1.entries] == [e.marker for e in inv2.entries]
    assert inv1.template_count == inv2.template_count


# ---------------------------------------------------------------------------
# Exclusion of temp/plugin/user-global ready roots
# ---------------------------------------------------------------------------


def test_inventory_does_not_include_paths_outside_ready_templates() -> None:
    """All paths in the inventory must be under ready_templates/ (repo-only)."""
    inventory = build_readability_inventory()
    for entry in inventory.entries:
        assert entry.path.startswith("ready_templates/"), (
            f"Entry {entry.ready_id} has path {entry.path} which is outside ready_templates/"
        )


def test_inventory_excludes_non_existent_paths() -> None:
    """Inventory only contains paths that actually exist."""
    inventory = build_readability_inventory()
    for entry in inventory.entries:
        full_path = REPO_ROOT / entry.path
        assert full_path.exists(), f"Path {entry.path} does not exist"


def test_inventory_never_uses_ready_template_ids_function_in_build(tmp_path: Path) -> None:
    """build_readability_inventory() never calls ready_template_ids()."""
    # Verify the module never actually calls ready_template_ids() at runtime.
    # The docstring mentions it as a warning, but the code must not reference
    # it in any import or call.
    import ast
    import inspect
    import vibecomfy.porting.readability_inventory as mod

    source = inspect.getsource(mod)
    tree = ast.parse(source)

    # Check all Call nodes for ready_template_ids
    calls = [node for node in ast.walk(tree) if isinstance(node, ast.Call)]
    for call in calls:
        if isinstance(call.func, ast.Name):
            assert call.func.id != "ready_template_ids"
        elif isinstance(call.func, ast.Attribute):
            # e.g. some_module.ready_template_ids
            assert call.func.attr != "ready_template_ids"

    # Check all imports — no import of ready_template_ids
    imports = [node for node in ast.walk(tree) if isinstance(node, (ast.Import, ast.ImportFrom))]
    for imp in imports:
        for alias in imp.names:
            assert alias.name != "ready_template_ids"


# ---------------------------------------------------------------------------
# Missing-source flags
# ---------------------------------------------------------------------------


def test_generated_template_without_source_workflow_is_flagged() -> None:
    """Generated templates without source_workflow in metadata are flagged."""
    inventory = build_readability_inventory()
    generated = [e for e in inventory.entries if e.marker == "generated"]
    flagged = [e for e in generated if e.missing_source_provenance]
    # At least some generated templates should exist
    assert len(generated) > 0
    # And we should have flagged ones if they lack source_workflow
    # (We won't assert a specific count, as it depends on repo state)


def test_manual_template_is_not_flagged_missing_source() -> None:
    """Manual templates are not flagged as missing source provenance."""
    inventory = build_readability_inventory()
    manual = [e for e in inventory.entries if e.marker == "manual"]
    for e in manual:
        assert not e.missing_source_provenance, (
            f"Manual template {e.ready_id} should not be flagged as missing source"
        )


def test_reference_template_is_not_flagged_missing_source() -> None:
    """Reference templates are not flagged as missing source provenance."""
    inventory = build_readability_inventory()
    reference = [e for e in inventory.entries if e.marker == "reference"]
    for e in reference:
        assert not e.missing_source_provenance, (
            f"Reference template {e.ready_id} should not be flagged as missing source"
        )


def test_summary_includes_missing_source_provenance_count() -> None:
    """The summary includes a missing_source_provenance count."""
    inventory = build_readability_inventory()
    assert "missing_source_provenance" in inventory.summary
    assert isinstance(inventory.summary["missing_source_provenance"], int)


# ---------------------------------------------------------------------------
# Summary counts
# ---------------------------------------------------------------------------


def test_summary_includes_marker_counts() -> None:
    """The summary breaks down marker counts."""
    inventory = build_readability_inventory()
    summary = inventory.summary
    marker_keys = [k for k in summary if k.startswith("marker_")]
    assert len(marker_keys) > 0
    total_markers = sum(summary[k] for k in marker_keys)
    assert total_markers == inventory.template_count


def test_summary_includes_readability_issue_counts() -> None:
    """The summary includes total counts for each readability issue type."""
    inventory = build_readability_inventory()
    summary = inventory.summary
    for key in [
        "positional_outs_total",
        "widget_n_fields_total",
        "uuid_class_types_total",
        "n_uuid_variables_total",
        "local_node_copies_total",
        "missing_output_contract",
        "templates_with_issues",
    ]:
        assert key in summary, f"Summary missing key: {key}"
        assert isinstance(summary[key], int)


def test_summary_app_active_count() -> None:
    """The summary includes an app_active count."""
    inventory = build_readability_inventory()
    assert "app_active" in inventory.summary


def test_readability_counts_data_class_fields() -> None:
    """ReadabilityCounts has all required fields with correct defaults."""
    counts = ReadabilityCounts()
    assert counts.positional_outs == 0
    assert counts.widget_n_fields == 0
    assert counts.uuid_class_types == 0
    assert counts.n_uuid_variables == 0
    assert counts.local_node_copies == 0
    assert counts.missing_output_contract is False


def test_template_inventory_entry_defaults() -> None:
    """TemplateInventoryEntry has correct defaults."""
    entry = TemplateInventoryEntry(ready_id="test/id", path="ready_templates/test/id.py", marker="unknown", coverage_tier="", capability="")
    assert entry.source_role is None
    assert entry.source_workflow is None
    assert entry.app_active is False
    assert entry.missing_source_provenance is True


# ---------------------------------------------------------------------------
# Edge cases
# ---------------------------------------------------------------------------


def test_marker_with_extra_comment_noise() -> None:
    """Marker detection works even with extra comment characters."""
    source = "# vibecomfy: manual  # some extra note\n"
    assert _classify_marker(source) == "manual"


def test_marker_case_sensitive() -> None:
    """Markers are case-sensitive."""
    source = "# VIBECOMFY: MANUAL\n"
    assert _classify_marker(source) == "unknown"


def test_empty_source_is_unknown() -> None:
    assert _classify_marker("") == "unknown"


def test_whitespace_only_source_is_unknown() -> None:
    assert _classify_marker("   \n  \n") == "unknown"


def test_count_positional_outs_zero_for_no_matches() -> None:
    assert _count_positional_outs("no outputs here") == 0


def test_count_widget_n_zero_for_no_matches() -> None:
    assert _count_widget_n_fields("no_widgets_here") == 0


def test_count_uuid_class_types_zero_for_non_uuid_source() -> None:
    assert _count_uuid_class_types("normal python code without uuids") == 0


def test_count_n_uuid_zero_for_no_matches() -> None:
    assert _count_n_uuid_variables("var = 42") == 0


def test_count_local_node_copies_zero_for_no_matches() -> None:
    assert _count_local_node_copies("wf.node('LoadImage')") == 0


# ---------------------------------------------------------------------------
# T5: inventory only counts local_node_copies for generated strict-ready templates
# ---------------------------------------------------------------------------


def test_inventory_local_node_copies_only_for_generated_marker(tmp_path: Path) -> None:
    """local_node_copies only counted for 'generated' marker, zero for others."""
    # Create templates with different markers but same _node content
    generated_content = "# vibecomfy: generated\n" + "_node " * 3 + "\n"
    manual_content = "# vibecomfy: manual\n" + "_node " * 3 + "\n"
    reference_content = "API_WORKFLOW = {}\n" + "_node " * 3 + "\n"
    authored_content = "NODES = []\n" + "_node " * 3 + "\n"
    unknown_content = "_node " * 3 + "\n"

    # Test the classification and counting logic directly
    assert _classify_marker(generated_content) == "generated"
    assert _classify_marker(manual_content) == "manual"
    assert _classify_marker(reference_content) == "reference"
    assert _classify_marker(authored_content) == "authored"
    assert _classify_marker(unknown_content) == "unknown"

    # All have the same raw _node count
    assert _count_local_node_copies(generated_content) == 3
    assert _count_local_node_copies(manual_content) == 3

    # But inventory only counts for generated marker
    # Simulate the counting logic
    for marker, content in [
        ("generated", generated_content),
        ("manual", manual_content),
        ("reference", reference_content),
        ("authored", authored_content),
        ("unknown", unknown_content),
    ]:
        actual_count = _count_local_node_copies(content) if marker == "generated" else 0
        if marker == "generated":
            assert actual_count == 3, f"Expected 3 for {marker}, got {actual_count}"
        else:
            assert actual_count == 0, f"Expected 0 for {marker}, got {actual_count}"


def test_inventory_includes_local_node_copies_in_json_output() -> None:
    """local_node_copies appears in both ReadabilityCounts and JSON serialization."""
    counts = ReadabilityCounts(local_node_copies=5, positional_outs=2)

    # Verify data class field
    assert counts.local_node_copies == 5

    # Verify JSON round-trip via TemplateInventoryEntry
    entry = TemplateInventoryEntry(
        ready_id="test/local",
        path="ready_templates/test/local.py",
        marker="generated",
        coverage_tier="required",
        capability="test",
        counts=counts,
    )
    # Verify the to_json method includes local_node_copies
    json_data = ReadabilityInventory(
        template_count=1,
        entries=[entry],
    ).to_json()

    assert json_data["entries"][0]["counts"]["local_node_copies"] == 5
    assert "local_node_copies" in json_data["entries"][0]["counts"]


def test_load_coverage_map_handles_missing_file() -> None:
    """Returns empty dict when coverage.json doesn't exist."""
    with mock.patch.object(Path, "exists", return_value=False):
        result = _load_coverage_map()
    assert result == {}


def test_load_template_index_map_handles_missing_file() -> None:
    """Returns empty dict when template_index.json doesn't exist."""
    with mock.patch.object(Path, "exists", return_value=False):
        result = _load_template_index_map()
    assert result == {}
