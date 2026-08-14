from __future__ import annotations

import importlib
from typing import Any

_EXPORT_MODULES = {
    "AssetAnalysis": "vibecomfy.porting.assets",
    "AssetCandidate": "vibecomfy.porting.report",
    "AssetCheckResult": "vibecomfy.porting.report",
    "BatchResult": "vibecomfy.porting.edit.session",
    "build_reverse_map": "vibecomfy.identity.codec",
    "class_type_counter": "vibecomfy.porting.parity",
    "CompactDiagnostic": "vibecomfy.porting.edit.session",
    "compile_equivalent": "vibecomfy.porting.parity",
    "DoneResult": "vibecomfy.porting.edit.session",
    "EditSession": "vibecomfy.porting.edit.session",
    "EmissionDiagnostic": "vibecomfy.porting.emitter",
    "FieldChange": "vibecomfy.porting.edit.types",
    "encode_slot_names": "vibecomfy.identity.codec",
    "emit_agent_edit_python": "vibecomfy.porting.emitter",
    "emit_available_node_signatures": "vibecomfy.porting.emitter",
    "filter_signature_rows_to_in_graph_nodes": "vibecomfy.porting.emitter",
    "format_signature_rows": "vibecomfy.porting.emitter",
    "InputSignatureField": "vibecomfy.porting.emitter",
    "InputSlotInfo": "vibecomfy.porting.edit.session",
    "NodeDescriptor": "vibecomfy.porting.edit.session",
    "NodePackSuggestion": "vibecomfy.porting.report",
    "NodeSignatureRow": "vibecomfy.porting.emitter",
    "OutputSlotInfo": "vibecomfy.porting.edit.session",
    "OutputSignatureField": "vibecomfy.porting.emitter",
    "PortArtifact": "vibecomfy.porting.report",
    "PortIssue": "vibecomfy.porting.report",
    "ProvenanceConflict": "vibecomfy.porting.provenance",
    "ProvenanceRecord": "vibecomfy.porting.provenance",
    "ProvenanceReport": "vibecomfy.porting.provenance",
    "ProvenanceRequirement": "vibecomfy.porting.provenance",
    "ProvenanceVersionPin": "vibecomfy.porting.provenance",
    "ProvenanceWarning": "vibecomfy.porting.provenance",
    "PortReport": "vibecomfy.porting.report",
    "READABILITY_WARNING_AVOIDABLE_POSITIONAL_OUTPUT": "vibecomfy.porting.emitter",
    "READABILITY_WARNING_CODES": "vibecomfy.porting.emitter",
    "READABILITY_WARNING_HIDDEN_MODEL_FILENAME": "vibecomfy.porting.emitter",
    "READABILITY_WARNING_OUTPUT_NAME_AMBIGUITY": "vibecomfy.porting.emitter",
    "READABILITY_WARNING_SCHEMA_BACKED_WIDGET_ALIAS_NOT_RESOLVED": "vibecomfy.porting.emitter",
    "HIDDEN_MODEL_FILENAME": "vibecomfy.porting.strict_ready",
    "OPAQUE_COMPONENT_NODE_CLASS": "vibecomfy.porting.strict_ready",
    "STRICT_READY_BROKEN_PUBLIC_INPUT": "vibecomfy.porting.strict_ready",
    "STRICT_READY_BUILD_FAILED": "vibecomfy.porting.strict_ready",
    "STRICT_READY_COMPILE_FAILED": "vibecomfy.porting.strict_ready",
    "STRICT_READY_LOAD_FAILED": "vibecomfy.porting.strict_ready",
    "STRICT_READY_MISSING_OUTPUT_CONTRACT": "vibecomfy.porting.strict_ready",
    "STRICT_READY_MISSING_PUBLIC_INPUT": "vibecomfy.porting.strict_ready",
    "STRICT_READY_UNNAMED_OUTPUT_CONTRACT": "vibecomfy.porting.strict_ready",
    "STRICT_READY_UNRESOLVED_WIDGETS": "vibecomfy.porting.strict_ready",
    "STRICT_READY_VIOLATION_CODES": "vibecomfy.porting.strict_ready",
    "StrictReadyContext": "vibecomfy.porting.strict_ready",
    "StrictReadyException": "vibecomfy.porting.strict_ready",
    "apply_strict_ready_exceptions": "vibecomfy.porting.strict_ready",
    "load_strict_ready_exceptions": "vibecomfy.porting.strict_ready",
    "slot_codec": "vibecomfy.identity.codec",
    "StatementResult": "vibecomfy.porting.edit.session",
    "to_python_identifier": "vibecomfy.identity.codec",
    "to_raw_name": "vibecomfy.identity.codec",
    "topology_counter": "vibecomfy.porting.parity",
    "extract_provenance": "vibecomfy.porting.provenance",
    "validate_strict_ready_workflow": "vibecomfy.porting.strict_ready",
    "widget_value_counter": "vibecomfy.porting.parity",
}

__all__ = list(_EXPORT_MODULES)


def __getattr__(name: str) -> Any:
    module_name = _EXPORT_MODULES.get(name)
    if module_name is None:
        raise AttributeError(f"module {__name__!r} has no attribute {name!r}")
    module = importlib.import_module(module_name)
    value = module if name == "slot_codec" else getattr(module, name)
    globals()[name] = value
    return value


def __dir__() -> list[str]:
    return sorted({*globals(), *__all__})
