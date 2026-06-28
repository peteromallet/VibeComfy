from __future__ import annotations

import subprocess
import sys


EXPECTED_EMITTER_ALL = [
    "EmissionDiagnostic",
    "EmissionSeverity",
    "READABILITY_WARNING_AVOIDABLE_POSITIONAL_OUTPUT",
    "READABILITY_WARNING_OUTPUT_NAME_AMBIGUITY",
    "READABILITY_WARNING_SCHEMA_BACKED_WIDGET_ALIAS_NOT_RESOLVED",
    "READABILITY_WARNING_HIDDEN_MODEL_FILENAME",
    "READABILITY_WARNING_LOCAL_HELPER_COPY_IN_STRICT_TEMPLATE",
    "READABILITY_WARNING_LONG_ONE_LINE_NODE_CALL",
    "READABILITY_WARNING_GENERATED_TEMPLATE_NOT_FORMATTED",
    "READABILITY_WARNING_GENERATED_VARIABLE_NAME_TOO_LONG",
    "READABILITY_WARNING_LOCKED_VARIABLE_ALIAS_INVALID",
    "READABILITY_WARNING_LOCKED_VARIABLE_ALIAS_COLLISION",
    "READABILITY_WARNING_LOCKED_VARIABLE_ALIAS_MISSING",
    "READABILITY_WARNING_LOCKED_VARIABLE_UID_COLLISION",
    "READABILITY_WARNING_CODES",
    "NodeSignatureRow",
    "InputSignatureField",
    "OutputSignatureField",
    "emit_available_node_signatures",
    "format_signature_rows",
    "format_as_python",
    "emit_ready_template_python",
    "emit_agent_edit_python",
    "emit_scratchpad_python",
]


def _run_python(source: str) -> None:
    subprocess.run(
        [sys.executable, "-c", source],
        check=True,
        text=True,
    )


def test_emitter_facade_preserves_exact_public_all() -> None:
    import vibecomfy.porting.emitter as emitter

    assert list(emitter.__all__) == EXPECTED_EMITTER_ALL
    for name in EXPECTED_EMITTER_ALL:
        assert hasattr(emitter, name), name


def test_emitter_facade_preserves_representative_private_imports() -> None:
    import vibecomfy.porting.emitter as emitter
    from vibecomfy.porting.emit import diagnostics
    from vibecomfy.porting.emit import emit_ready
    from vibecomfy.porting.emit import format_values
    from vibecomfy.porting.emit import naming_codegen
    from vibecomfy.porting.emit import node_kwargs_core
    from vibecomfy.porting.emit import subgraph_defs
    from vibecomfy.porting.emit import subgraph_functions

    assert emitter._format_value is format_values._format_value
    assert emitter._safe_var is naming_codegen._safe_var
    assert emitter._emit_subgraph_functions is subgraph_functions._emit_subgraph_functions
    assert emitter._build_subgraph_def is subgraph_defs._build_subgraph_def
    assert emitter._ui_widget_values_by_name is node_kwargs_core._ui_widget_values_by_name
    assert emitter._strip_unused_template_imports is emit_ready._strip_unused_template_imports
    assert emitter.READABILITY_WARNING_CODES is diagnostics.READABILITY_WARNING_CODES


def test_vibecomfy_all_traversal_does_not_import_emitter_or_miss_exports() -> None:
    _run_python(
        """
import sys
import vibecomfy

assert "vibecomfy.porting.emitter" not in sys.modules
for name in vibecomfy.__all__:
    getattr(vibecomfy, name)
assert "vibecomfy.porting.emitter" not in sys.modules
"""
    )


def test_porting_emit_lazy_reexports_from_emitter_facade() -> None:
    _run_python(
        """
import sys
import vibecomfy.porting.emit as emit

assert "vibecomfy.porting.emitter" not in sys.modules
assert emit.__all__[:24] == [
    "EmissionDiagnostic",
    "EmissionSeverity",
    "READABILITY_WARNING_AVOIDABLE_POSITIONAL_OUTPUT",
    "READABILITY_WARNING_OUTPUT_NAME_AMBIGUITY",
    "READABILITY_WARNING_SCHEMA_BACKED_WIDGET_ALIAS_NOT_RESOLVED",
    "READABILITY_WARNING_HIDDEN_MODEL_FILENAME",
    "READABILITY_WARNING_LOCAL_HELPER_COPY_IN_STRICT_TEMPLATE",
    "READABILITY_WARNING_LONG_ONE_LINE_NODE_CALL",
    "READABILITY_WARNING_GENERATED_TEMPLATE_NOT_FORMATTED",
    "READABILITY_WARNING_GENERATED_VARIABLE_NAME_TOO_LONG",
    "READABILITY_WARNING_LOCKED_VARIABLE_ALIAS_INVALID",
    "READABILITY_WARNING_LOCKED_VARIABLE_ALIAS_COLLISION",
    "READABILITY_WARNING_LOCKED_VARIABLE_ALIAS_MISSING",
    "READABILITY_WARNING_LOCKED_VARIABLE_UID_COLLISION",
    "READABILITY_WARNING_CODES",
    "NodeSignatureRow",
    "InputSignatureField",
    "OutputSignatureField",
    "emit_available_node_signatures",
    "format_signature_rows",
    "format_as_python",
    "emit_ready_template_python",
    "emit_agent_edit_python",
    "emit_scratchpad_python",
]

from vibecomfy.porting.emit import EmissionDiagnostic, emit_ready_template_python, emitter

assert "vibecomfy.porting.emitter" in sys.modules
assert EmissionDiagnostic is emitter.EmissionDiagnostic
assert emit_ready_template_python is emitter.emit_ready_template_python
assert emit.EmissionDiagnostic is emitter.EmissionDiagnostic
assert emit.emitter is emitter
"""
    )
