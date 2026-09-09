from __future__ import annotations

from vibecomfy.porting.import_errors import native_boundary_recovery


def test_native_boundary_recovery_is_actionable_without_materializing_candidate() -> None:
    source = "workflow.json"
    result = native_boundary_recovery(
        ValueError(
            "unsupported_boundary_encoding: definition 'definitions[0]' contains "
            "native inputNode/outputNode markers; use an explicit Python-owned boundary mapping"
        ),
        source,
    )

    assert result is not None
    assert result["candidate_status"] == "not_materialized"
    assert "ComfyUI" in result["recovery"]["inspect_source"]
    assert "port check workflow.json" in result["recovery"]["port_after_resolution"]
    assert "port convert workflow.json" in result["recovery"]["materialize_after_resolution"]


def test_import_errors_does_not_relabel_unrelated_failures() -> None:
    assert native_boundary_recovery(ValueError("missing schema"), "workflow.json") is None
