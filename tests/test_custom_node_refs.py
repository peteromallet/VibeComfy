from __future__ import annotations

import pytest

from vibecomfy.custom_node_refs import (
    CustomNodeRefConflict,
    check_pack_pin_compatibility,
    normalize_custom_node_requirements,
)
from vibecomfy.node_packs import LockEntry
from vibecomfy.workflow import VibeWorkflow, WorkflowRequirements, WorkflowSource


def test_structured_custom_nodes_normalize_to_string_nodes_and_refs() -> None:
    requirements, warnings = normalize_custom_node_requirements(
        {
            "custom_nodes": [
                {"slug": "comfyui-kjnodes", "source": "git", "url": "https://example.test/kj.git", "commit": "abc"},
                "ComfyUI-VideoHelperSuite",
            ],
            "custom_node_refs": [
                {"slug": "comfyui-controlnet-aux", "source": "comfy-registry", "version": "1.0.5"},
            ],
        }
    )

    assert requirements["custom_nodes"] == ["ComfyUI-VideoHelperSuite", "comfyui-kjnodes"]
    assert requirements["custom_node_refs"] == [
        {"slug": "comfyui-controlnet-aux", "source": "comfy-registry", "version": "1.0.5"},
        {"slug": "comfyui-kjnodes", "source": "git", "url": "https://example.test/kj.git", "commit": "abc"},
    ]
    assert warnings


def test_legacy_metadata_mutation_cannot_reopen_custom_node_ref_authority() -> None:
    workflow = VibeWorkflow(
        "m",
        WorkflowSource("m"),
        metadata={"requirements": {"custom_node_refs": [{"slug": "p", "source": "git", "commit": "old"}]}},
    )
    workflow.metadata["requirements"]["custom_node_refs"][0]["commit"] = "new"
    workflow.finalize_metadata()
    assert [ref["commit"] for ref in workflow.requirements.custom_node_refs] == ["old"]


def test_pack_pin_compatibility_reports_commit_conflict() -> None:
    workflow = VibeWorkflow(
        id="test",
        source=WorkflowSource(id="test"),
        requirements=WorkflowRequirements(custom_nodes=["comfyui-kjnodes"]),
        metadata={
            "requirements": {
                "custom_nodes": ["comfyui-kjnodes"],
                "custom_node_refs": [
                    {"slug": "comfyui-kjnodes", "source": "git", "commit": "expected"},
                ],
            }
        },
    )

    issues = check_pack_pin_compatibility(
        workflow,
        [
            LockEntry(
                name="ComfyUI-KJNodes",
                slug="comfyui-kjnodes",
                source="git",
                commit="actual",
                url="https://example.test/kj.git",
            )
        ],
    )

    assert [(issue.code, issue.severity) for issue in issues] == [("custom_node_ref_pin_conflict", "error")]
    assert "expected" in issues[0].message
    assert "actual" in issues[0].message


def test_pack_pin_compatibility_warns_for_legacy_unpinned_custom_nodes() -> None:
    workflow = VibeWorkflow(
        id="test",
        source=WorkflowSource(id="test"),
        requirements=WorkflowRequirements(custom_nodes=["ComfyUI-KJNodes"]),
        metadata={"requirements": {"custom_nodes": ["ComfyUI-KJNodes"]}},
    )

    issues = check_pack_pin_compatibility(workflow, [])

    assert [(issue.code, issue.severity) for issue in issues] == [("legacy_custom_nodes_unpinned", "warning")]


def test_pack_pin_compatibility_warns_for_unpinned_structured_ref_missing_from_lock() -> None:
    workflow = VibeWorkflow(
        id="test",
        source=WorkflowSource(id="test"),
        requirements=WorkflowRequirements(custom_nodes=["ComfyUI-GGUF"]),
        metadata={
            "requirements": {
                "custom_nodes": ["ComfyUI-GGUF"],
                "custom_node_refs": [
                    {"slug": "ComfyUI-GGUF", "source": "git", "url": "https://example.test/gguf.git"},
                ],
            }
        },
    )

    issues = check_pack_pin_compatibility(workflow, [])

    assert [(issue.code, issue.severity) for issue in issues] == [("custom_node_ref_missing_from_lock", "warning")]


def test_pack_pin_compatibility_errors_for_pinned_structured_ref_missing_from_lock() -> None:
    workflow = VibeWorkflow(
        id="test",
        source=WorkflowSource(id="test"),
        requirements=WorkflowRequirements(custom_nodes=["ComfyUI-GGUF"]),
        metadata={
            "requirements": {
                "custom_nodes": ["ComfyUI-GGUF"],
                "custom_node_refs": [
                    {"slug": "ComfyUI-GGUF", "source": "git", "commit": "abc123"},
                ],
            }
        },
    )

    issues = check_pack_pin_compatibility(workflow, [])

    assert [(issue.code, issue.severity) for issue in issues] == [("custom_node_ref_missing_from_lock", "error")]


def test_conflicting_exact_refs_report_values_and_source_locations() -> None:
    with pytest.raises(CustomNodeRefConflict) as error:
        normalize_custom_node_requirements(
            {
                "custom_node_refs": [
                    {"slug": "pack", "source": "git", "commit": "aaa"},
                    {"slug": "pack", "source": "git", "commit": "bbb"},
                ]
            }
        )
    message = str(error.value)
    assert "aaa" in message and "bbb" in message
    assert "requirements.custom_node_refs[0]" in message
    assert "requirements.custom_node_refs[1]" in message


def test_typed_ref_is_semantic_identity_and_envelope_roundtrips_evidence() -> None:
    from vibecomfy.workflow import VibeNode

    workflow = VibeWorkflow(
        id="typed-ref",
        source=WorkflowSource(id="typed-ref"),
        requirements=WorkflowRequirements(
            custom_node_refs=[
                {
                    "slug": "pack",
                    "source": "git",
                    "commit": "aaa",
                    "version_range": ">=1,<2",
                    "schema_hash": "schema-a",
                    "source_evidence": {"path": "nodes.py", "sha256": "source-a"},
                }
            ]
        ),
    )
    node = VibeNode(id="1", class_type="KSampler")
    node.uid = "1"
    workflow.nodes[node.id] = node
    before = workflow.semantic_digest()
    envelope = workflow.to_envelope()
    restored = VibeWorkflow.from_envelope(envelope)
    assert restored.requirements.custom_node_refs == workflow.requirements.custom_node_refs
    assert restored.semantic_digest() == before
    restored.requirements.custom_node_refs[0]["commit"] = "bbb"
    assert restored.semantic_digest() != before


def test_legacy_metadata_refs_are_admitted_to_typed_requirements() -> None:
    workflow = VibeWorkflow(
        id="legacy-ref",
        source=WorkflowSource(id="legacy-ref"),
        metadata={
            "requirements": {
                "custom_node_refs": [
                    {"slug": "legacy-pack", "source": "git", "commit": "old"}
                ]
            }
        },
    )
    assert workflow.requirements.custom_node_refs == [
        {"slug": "legacy-pack", "source": "git", "commit": "old"}
    ]


def test_canonical_python_export_contains_typed_ref_constraints_and_evidence() -> None:
    from vibecomfy.porting.emit.entrypoints import emit_canonical_python
    from vibecomfy.workflow import VibeNode

    workflow = VibeWorkflow(
        id="canonical-ref",
        source=WorkflowSource(id="canonical-ref"),
        requirements=WorkflowRequirements(
            custom_node_refs=[
                {
                    "slug": "pack",
                    "source": "git",
                    "commit": "abc",
                    "version_range": ">=1,<2",
                    "schema_hash": "schema",
                    "source_evidence": {"sha256": "source"},
                }
            ]
        ),
    )
    node = VibeNode(id="1", class_type="KSampler")
    node.uid = "1"
    workflow.nodes[node.id] = node
    source = emit_canonical_python(
        workflow,
        ready_metadata={"capability": "unknown"},
        ready_requirements={},
    )
    assert "custom_node_refs" in source
    assert "version_range" in source and "schema_hash" in source
    assert "source_evidence" in source
