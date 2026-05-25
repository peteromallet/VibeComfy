"""T9: Widget kwargs resolution tests.

Verify that known aliases produce named kwargs (e.g. invert_input_masks=False)
and unknown aliases fall back to widget_N + schema_backed_widget_alias_not_resolved
diagnostic without minting a new diagnostic code (SD3).
"""
from __future__ import annotations

from typing import Any

from vibecomfy.porting.emitter import (
    EmissionDiagnostic,
    READABILITY_WARNING_SCHEMA_BACKED_WIDGET_ALIAS_NOT_RESOLVED,
    emit_scratchpad_python,
)
from vibecomfy.workflow import VibeEdge, VibeNode, VibeWorkflow, WorkflowSource


# ---------------------------------------------------------------------------
# helpers
# ---------------------------------------------------------------------------


def _workflow_with_widgets(
    class_type: str,
    widget_values: dict[str, Any],
    *,
    has_output_edge: bool = True,
) -> VibeWorkflow:
    """Build a workflow with a single node that carries widget values."""
    wf = VibeWorkflow(
        f"test/widget_kwargs_{class_type}",
        WorkflowSource(f"test/widget_kwargs_{class_type}", provenance={"origin": "unit"}),
    )
    node = VibeNode("1", class_type)
    for k, v in widget_values.items():
        node.widgets[k] = v
    wf.nodes["1"] = node
    if has_output_edge:
        wf.nodes["2"] = VibeNode("2", "SaveImage", inputs={"filename_prefix": "out"})
        wf.edges.append(VibeEdge("1", "0", "2", "images"))
    return wf


def _widget_n_keys_in_text(text: str) -> set[str]:
    """Return the set of widget_N= keys that appear in emitted code."""
    import re
    return set(re.findall(r"widget_\d+", text))


# ---------------------------------------------------------------------------
# tests
# ---------------------------------------------------------------------------


def test_widget_kwargs_named_when_alias_known() -> None:
    """Widget values on a class with WIDGET_SCHEMA aliases render as named kwargs.

    CheckpointLoaderSimple has widget_0 → ckpt_name in WIDGET_SCHEMA.
    Without per-node input_aliases metadata, the committed schema resolves
    widget_0 to the named field.
    """
    wf = _workflow_with_widgets(
        "CheckpointLoaderSimple",
        {"widget_0": "v1-5-pruned.safetensors"},
    )

    text = emit_scratchpad_python(wf, source_path="tests/fixtures/widget_kwargs.json")

    # Must use the named field from WIDGET_SCHEMA
    assert "ckpt_name=" in text, f"Expected named kwarg 'ckpt_name=', got:\n{text[-500:]}"
    assert "'v1-5-pruned.safetensors'" in text
    # Must NOT use raw widget_0
    assert "widget_0=" not in text, f"Unexpected widget_0= in:\n{text}"


def test_widget_kwargs_widget_n_fallback_when_alias_unknown() -> None:
    """Unknown class without any alias resolution keeps widget_N fallback
    and emits schema_backed_widget_alias_not_resolved diagnostic (SD3: reused,
    not a new code).
    """
    diags: list[EmissionDiagnostic] = []

    wf = _workflow_with_widgets(
        "SomeUnknownNodeType42",
        {"widget_0": "first", "widget_5": "fifth"},
    )

    text = emit_scratchpad_python(
        wf,
        source_path="tests/fixtures/widget_kwargs_fallback.json",
        diagnostics=diags,
    )

    # Unknown class falls to raw_call; widget values appear with widget_N keys
    assert "raw_call(" in text, (
        "Unknown class should emit raw_call (no typed wrapper)"
    )

    # The widget_N keys should survive in the output
    assert "widget_0=" in text, f"Expected widget_0= fallback in:\n{text[-500:]}"
    assert "widget_5=" in text, f"Expected widget_5= fallback in:\n{text[-500:]}"

    # Must emit the schema_backed_widget_alias_not_resolved diagnostic
    unresolved = [
        d for d in diags
        if d.code == READABILITY_WARNING_SCHEMA_BACKED_WIDGET_ALIAS_NOT_RESOLVED
    ]
    assert len(unresolved) > 0, (
        f"Expected {READABILITY_WARNING_SCHEMA_BACKED_WIDGET_ALIAS_NOT_RESOLVED} "
        f"diagnostic, got codes: {[d.code for d in diags]}"
    )

    # Verify the diagnostic is a warning, not an error
    for d in unresolved:
        assert d.severity == "warning", (
            f"schema_backed_widget_alias_not_resolved should be warning, got {d.severity}"
        )

    # No new diagnostic code minted — only pre-existing codes
    from vibecomfy.porting.emitter import (
        READABILITY_WARNING_CODES,
        READABILITY_WARNING_OPAQUE_COMPONENT_RAW_CALL,
    )
    unknown_codes = [
        d.code for d in diags
        if d.code not in READABILITY_WARNING_CODES
    ]
    assert len(unknown_codes) == 0, (
        f"Unexpected diagnostic code(s) minted outside READABILITY_WARNING_CODES: {unknown_codes!r}"
    )
