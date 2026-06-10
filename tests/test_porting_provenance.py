from __future__ import annotations

import json
import importlib.util
from pathlib import Path
import sys

_PROVENANCE_PATH = Path(__file__).resolve().parents[1] / "vibecomfy" / "porting" / "provenance.py"
_SPEC = importlib.util.spec_from_file_location("test_porting_provenance_module", _PROVENANCE_PATH)
assert _SPEC and _SPEC.loader
_MODULE = importlib.util.module_from_spec(_SPEC)
sys.modules[_SPEC.name] = _MODULE
_SPEC.loader.exec_module(_MODULE)
extract_provenance = _MODULE.extract_provenance


IDEOGRAM = (Path(__file__).resolve().parents[1] / "docs" / "megaplan_chains" / "node_resolution_epic" / "testing" / "fixtures" / "ideogram4_t2i.json")


def test_extract_provenance_scans_ideogram_top_level_and_subgraphs() -> None:
    report = extract_provenance(json.loads(IDEOGRAM.read_text(encoding="utf-8")))

    assert report.required_pack_slugs == {"comfy-core"}
    assert any(record.scope == "top_level" for record in report.records)
    assert any(record.scope == "subgraph" for record in report.records)
    assert any(record.subgraph_id for record in report.records if record.scope == "subgraph")
    assert not report.aux_only
    assert not report.unprovenanced


def test_extract_provenance_preserves_aux_and_ver_metadata_and_dedupes_cnr_ids() -> None:
    workflow = {
        "nodes": [
            {"id": 1, "type": "KnownCustomNode", "properties": {"cnr_id": "custom-pack", "ver": "1.2.3"}},
            {"id": 2, "type": "SamePackOtherNode", "properties": {"cnr_id": "custom-pack", "ver": "9.9.9"}},
            {"id": 3, "type": "AuxOnlyNode", "properties": {"aux_id": "owner/repo", "ver": "deadbeef"}},
        ],
        "definitions": {
            "subgraphs": [
                {
                    "id": "sg-1",
                    "nodes": [
                        {"id": 4, "type": "NestedNode", "properties": {"cnr_id": "nested-pack", "ver": "0.0.1"}}
                    ],
                }
            ]
        },
    }

    report = extract_provenance(workflow)

    assert report.required_pack_slugs == {"custom-pack", "nested-pack"}
    assert {requirement.identity_key for requirement in report.requirements} == {
        "cnr:custom-pack|aux:-|ver:1.2.3",
        "cnr:custom-pack|aux:-|ver:9.9.9",
        "cnr:nested-pack|aux:-|ver:0.0.1",
        "cnr:-|aux:owner/repo|ver:deadbeef",
    }
    assert any(
        requirement.resolver_kind == "aux_git" and requirement.aux_id == "owner/repo"
        for requirement in report.requirements
    )
    assert [conflict.code for conflict in report.conflicts] == ["conflicting_authored_versions"]
    assert report.conflicts[0].locator_key == "cnr:custom-pack|aux:-"
    assert report.conflicts[0].versions == ("1.2.3", "9.9.9")
    aux_only = report.aux_only[0]
    assert aux_only.node_id == "3"
    assert aux_only.aux_id == "owner/repo"
    assert aux_only.ver == "deadbeef"
    nested = next(record for record in report.records if record.node_id == "4")
    assert nested.scope == "subgraph"
    assert nested.subgraph_id == "sg-1"
    assert nested.ver == "0.0.1"


def test_extract_provenance_builds_requirement_kinds_and_pins_for_commit_semver_core_and_conflicts() -> None:
    workflow = {
        "nodes": [
            {"id": 1, "type": "KSampler", "properties": {"cnr_id": "comfy-core", "ver": "0.24.0"}},
            {"id": 2, "type": "AuxCommitNode", "properties": {"aux_id": "owner/repo", "ver": "deadbeef"}},
            {"id": 3, "type": "SemverNodeA", "properties": {"cnr_id": "custom-pack", "ver": "1.2.3"}},
            {"id": 4, "type": "SemverNodeB", "properties": {"cnr_id": "custom-pack", "ver": "2.0.0"}},
            {"id": 5, "type": "MarkdownNote", "properties": {"cnr_id": "ignored-pack", "ver": "9.9.9"}},
            {"id": 6, "type": "MysteryExec", "properties": {}},
        ]
    }

    report = extract_provenance(workflow)
    requirements = {requirement.identity_key: requirement for requirement in report.requirements}
    version_pins = {pin.identity_key: pin for pin in report.version_pins}

    assert requirements["cnr:comfy-core|aux:-|ver:0.24.0"].resolver_kind == "comfy_core"
    assert requirements["cnr:-|aux:owner/repo|ver:deadbeef"].resolver_kind == "aux_git"
    assert requirements["cnr:custom-pack|aux:-|ver:1.2.3"].version_pin is not None
    assert requirements["cnr:custom-pack|aux:-|ver:2.0.0"].version_pin is not None
    assert version_pins["cnr:-|aux:owner/repo|ver:deadbeef"].version == "deadbeef"
    assert version_pins["cnr:custom-pack|aux:-|ver:1.2.3"].version == "1.2.3"
    assert "cnr:ignored-pack|aux:-|ver:9.9.9" not in requirements
    assert [record.node_id for record in report.unprovenanced] == ["6"]
    assert any(conflict.code == "conflicting_authored_versions" for conflict in report.conflicts)
    assert any(warning.code == "helper_ui_node" for warning in report.warnings)


def test_extract_provenance_reports_execution_like_records_without_provenance() -> None:
    workflow = {
        "nodes": [
            {"id": 10, "type": "KSampler", "properties": {}},
            {"id": 11, "type": "MarkdownNote", "properties": {}},
        ]
    }

    report = extract_provenance(workflow)

    assert [record.node_id for record in report.unprovenanced] == ["10"]
    assert report.unprovenanced[0].class_type == "KSampler"
    assert report.low_confidence is True
    assert [warning.code for warning in report.warnings if warning.low_confidence] == [
        "unprovenanced_execution_node"
    ]


def test_extract_provenance_flags_comfy_core_records_for_non_core_classes() -> None:
    workflow = {
        "nodes": [
            {"id": 20, "type": "ResolutionSelector", "properties": {"cnr_id": "comfy-core", "ver": "0.23.0"}},
            {"id": 21, "type": "VAELoader", "properties": {"cnr_id": "comfy-core", "ver": "0.8.2"}},
        ]
    }

    report = extract_provenance(workflow)

    assert report.required_pack_slugs == {"comfy-core"}
    assert [record.node_id for record in report.core_slug_non_core] == ["20"]
    assert report.core_slug_non_core[0].class_type == "ResolutionSelector"
    assert any(conflict.code == "suspicious_comfy_core" for conflict in report.conflicts)


def test_extract_provenance_ignores_subgraph_proxy_nodes_for_core_mismatch_and_unprovenanced() -> None:
    workflow = {
        "nodes": [
            {"id": 30, "type": "sg-uuid", "properties": {"cnr_id": "comfy-core", "ver": "0.1.0"}},
            {"id": 31, "type": "sg-uuid-2", "properties": {}},
        ],
        "definitions": {"subgraphs": [{"id": "sg-uuid", "nodes": []}, {"id": "sg-uuid-2", "nodes": []}]},
    }

    report = extract_provenance(workflow)

    assert not report.core_slug_non_core
    assert not report.unprovenanced


def test_extract_provenance_dedupes_comfy_core_slug_across_many_records() -> None:
    """Ideogram deduping: multiple nodes with cnr_id='comfy-core' collapse to one required slug."""
    workflow = {
        "nodes": [
            {"id": 1, "type": "VAELoader", "properties": {"cnr_id": "comfy-core", "ver": "0.8.2"}},
            {"id": 2, "type": "KSampler", "properties": {"cnr_id": "comfy-core", "ver": "0.8.2"}},
            {"id": 3, "type": "SaveImage", "properties": {"cnr_id": "comfy-core", "ver": "0.24.0"}},
            {"id": 4, "type": "CLIPLoader", "properties": {"cnr_id": "comfy-core", "ver": "0.8.2"}},
            {"id": 5, "type": "VAEDecode", "properties": {"cnr_id": "comfy-core", "ver": "0.8.2"}},
        ]
    }
    report = extract_provenance(workflow)
    assert report.required_pack_slugs == {"comfy-core"}
    # All five records should exist
    assert len(report.records) == 5
    # None should be flagged as non-core since they are all in CORE_COMFY_CLASSES
    assert not report.core_slug_non_core


def test_extract_provenance_tracks_subgraph_identity_and_index() -> None:
    """Subgraph node scanning: nodes in definitions.subgraphs get correct subgraph_id and subgraph_index."""
    workflow = {
        "nodes": [],
        "definitions": {
            "subgraphs": [
                {
                    "id": "sg-alpha",
                    "nodes": [
                        {"id": 10, "type": "CustomNodeA", "properties": {"cnr_id": "pack-a"}},
                        {"id": 11, "type": "CustomNodeB", "properties": {"cnr_id": "pack-b"}},
                    ],
                },
                {
                    "id": "sg-beta",
                    "nodes": [
                        {"id": 20, "type": "CustomNodeC", "properties": {"cnr_id": "pack-c", "ver": "1.0.0"}},
                    ],
                },
            ]
        },
    }
    report = extract_provenance(workflow)
    assert report.required_pack_slugs == {"pack-a", "pack-b", "pack-c"}

    sg_alpha_nodes = [r for r in report.records if r.subgraph_id == "sg-alpha"]
    assert len(sg_alpha_nodes) == 2
    assert all(r.subgraph_index == 0 for r in sg_alpha_nodes)
    assert all(r.scope == "subgraph" for r in sg_alpha_nodes)

    sg_beta_nodes = [r for r in report.records if r.subgraph_id == "sg-beta"]
    assert len(sg_beta_nodes) == 1
    assert sg_beta_nodes[0].subgraph_index == 1
    assert sg_beta_nodes[0].ver == "1.0.0"


def test_extract_provenance_aux_only_diagnostics_edge_cases() -> None:
    """Aux-only diagnostics: nodes with aux_id but no cnr_id appear in aux_only with metadata preserved."""
    workflow = {
        "nodes": [
            {"id": 1, "type": "MysteryNode", "properties": {"aux_id": "owner/repo", "ver": "abc123"}},
            {"id": 2, "type": "AnotherMystery", "properties": {"aux_id": "other/nest"}},
            {"id": 3, "type": "MixedNode", "properties": {"cnr_id": "known-pack", "aux_id": "ignored/aux"}},
        ]
    }
    report = extract_provenance(workflow)
    assert report.required_pack_slugs == {"known-pack"}
    assert len(report.aux_only) == 2
    aux_ids = {r.aux_id for r in report.aux_only}
    assert aux_ids == {"owner/repo", "other/nest"}
    # Node 3 has both cnr_id and aux_id — should NOT be in aux_only
    assert all(r.node_id != "3" for r in report.aux_only)
    # Ver preserved on aux-only record
    assert report.aux_only[0].ver == "abc123"


def test_extract_provenance_collects_unresolvable_custom_cnr_id() -> None:
    """Unresolvable custom cnr_id: a pack slug not in any registry is still collected in required_pack_slugs."""
    workflow = {
        "nodes": [
            {"id": 1, "type": "ExoticCustomNode", "properties": {"cnr_id": "unlisted-experimental-pack", "ver": "0.0.1"}},
            {"id": 2, "type": "VAELoader", "properties": {"cnr_id": "comfy-core"}},
        ]
    }
    report = extract_provenance(workflow)
    # Both slugs appear — provenance extraction does not validate against a registry
    assert report.required_pack_slugs == {"comfy-core", "unlisted-experimental-pack"}
    # The unresolvable record exists with its metadata intact
    unresolvable = next(r for r in report.records if r.cnr_id == "unlisted-experimental-pack")
    assert unresolvable.class_type == "ExoticCustomNode"
    assert unresolvable.ver == "0.0.1"
    # It is execution-looking (not a helper UI class)
    assert unresolvable.execution_looking is True


def test_extract_provenance_flags_multiple_non_core_comfy_core_records() -> None:
    """Non-core classes suspiciously tagged comfy-core: multiple records in core_slug_non_core list."""
    workflow = {
        "nodes": [
            {"id": 1, "type": "ResolutionSelector", "properties": {"cnr_id": "comfy-core", "ver": "0.23.0"}},
            {"id": 2, "type": "Ideogram4Scheduler", "properties": {"cnr_id": "comfy-core", "ver": "0.23.0"}},
            {"id": 3, "type": "EmptyFlux2LatentImage", "properties": {"cnr_id": "comfy-core", "ver": "0.8.2"}},
            {"id": 4, "type": "VAELoader", "properties": {"cnr_id": "comfy-core", "ver": "0.8.2"}},
        ]
    }
    report = extract_provenance(workflow)
    assert report.required_pack_slugs == {"comfy-core"}
    # Three non-core classes, one core class
    assert len(report.core_slug_non_core) == 3
    flagged_types = {r.class_type for r in report.core_slug_non_core}
    assert flagged_types == {"ResolutionSelector", "Ideogram4Scheduler", "EmptyFlux2LatentImage"}
    # VAELoader is in CORE_COMFY_CLASSES and should not be flagged
    assert all(r.class_type != "VAELoader" for r in report.core_slug_non_core)
    # All flagged records should still have their metadata
    assert all(r.cnr_id == "comfy-core" for r in report.core_slug_non_core)


def test_extract_provenance_unprovenanced_skips_helpers_and_subgraph_proxies() -> None:
    """Unprovenanced diagnostics: helper UI nodes and subgraph proxies are excluded from unprovenanced list."""
    workflow = {
        "nodes": [
            {"id": 1, "type": "UnknownSampler", "properties": {}},
            {"id": 2, "type": "Note", "properties": {}},
            {"id": 3, "type": "MarkdownNote", "properties": {}},
            {"id": 4, "type": "Reroute", "properties": {}},
            {"id": 5, "type": "sg-proxy-1", "properties": {}},
        ],
        "definitions": {
            "subgraphs": [
                {"id": "sg-proxy-1", "nodes": []},
            ]
        },
    }
    report = extract_provenance(workflow)
    assert not report.required_pack_slugs
    # Only the unknown sampler should be flagged as unprovenanced
    assert len(report.unprovenanced) == 1
    assert report.unprovenanced[0].class_type == "UnknownSampler"
    assert report.unprovenanced[0].execution_looking is True
    # Helper/UI nodes and subgraph proxies should not appear as unprovenanced
    helper_types = {r.class_type for r in report.records if not r.execution_looking}
    assert helper_types >= {"Note", "MarkdownNote", "Reroute", "sg-proxy-1"}
    helper_warning_codes = {warning.code for warning in report.warnings if warning.code == "helper_ui_node"}
    assert helper_warning_codes == {"helper_ui_node"}
