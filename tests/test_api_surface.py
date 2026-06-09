from __future__ import annotations

import importlib


PUBLIC_EXPORT_SNAPSHOTS = {
    "vibecomfy": [
        "Artifact", "Image", "Video", "Audio", "Latent", "Mask", "Handle",
        "VibeWorkflow", "VibeNode", "VibeEdge", "VibeInput", "VibeOutput",
        "WorkflowRequirements", "WorkflowSource", "ValidationIssue", "ValidationReport",
        "workflow_from_file", "workflow_from_id", "workflow_from_template", "workflow_from_ready",
        "ready_template_ids", "load_workflow_any", "load_workflow_json", "load_template",
        "ensure_plugins_loaded", "image", "video", "blocks", "patches",
        "router", "run", "run_sync", "run_embedded", "run_embedded_sync",
    ],
    "vibecomfy.workflow": [
        "OPAQUE_COMPONENT_CLASS_RE", "ValidationIssue", "ValidationReport", "VibeEdge",
        "VibeInput", "VibeNode", "VibeOutput", "VibeWorkflow", "WorkflowRequirements",
        "WorkflowSource",
    ],
    "vibecomfy.handles": ["Handle"],
    "vibecomfy.errors": [
        "ContextVarBindingError", "ConversionParityError", "DriftError", "ModelAssetError",
        "QueueError", "RuntimeNodeError", "SchemaValidationError", "SubgraphFreshnessError",
        "VibeComfyError",
    ],
    "vibecomfy.schema": [
        "AuthoringSchemaProvider", "InputSpec", "NodeCallValidationIssue",
        "NodeCallValidationReport", "CompositeSchemaProvider", "ConversionSchemaProvider",
        "LocalSchemaProvider", "NodeSchema", "ObjectInfoSchemaProvider", "OutputSpec",
        "RuntimeSchemaProvider", "SchemaIndexError", "SchemaProvider", "SchemaSourceInfo",
        "SourceSchemaProvider", "get_authoring_schema_provider", "get_schema_provider",
        "schema_for", "schema_registry_empty", "schemas_for", "socket_types_compatible",
        "validate_node_call",
    ],
    "vibecomfy.artifacts": ["Artifact", "ArtifactKind", "Image", "Video", "Audio", "Latent", "Mask"],
    "vibecomfy.templates": [
        "InputSpec", "ModelAsset", "ReadyMetadata", "_at", "_current_workflow_or_raise",
        "_derive_output_kind", "finalize", "finalize_ready", "new_workflow", "node",
        "template_input", "template_output",
    ],
}


def test_public_module_all_snapshots_are_intentional() -> None:
    for module_name, expected in PUBLIC_EXPORT_SNAPSHOTS.items():
        module = importlib.import_module(module_name)
        assert list(module.__all__) == expected


def test_method_level_apis_are_not_module_export_snapshots() -> None:
    from vibecomfy.workflow import VibeWorkflow

    assert "export_to_json" not in PUBLIC_EXPORT_SNAPSHOTS["vibecomfy.workflow"]
    assert hasattr(VibeWorkflow, "export_to_json")
