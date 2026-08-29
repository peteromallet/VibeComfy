from __future__ import annotations

from pathlib import Path
from types import SimpleNamespace

import pytest

from vibecomfy.porting import simulate


def _template_source(extra_build_lines: str) -> str:
    return f'''# vibecomfy: generated
from vibecomfy.workflow import VibeNode, VibeWorkflow, WorkflowSource


def build():
    wf = VibeWorkflow(id="simulate-case", source=WorkflowSource(id="simulate-case"))
{extra_build_lines}
    return wf
'''


def _simulate_source(
    tmp_path: Path,
    monkeypatch: pytest.MonkeyPatch,
    extra_build_lines: str,
) -> simulate.SimulationResult:
    template_id = "image/simulate_case"
    template_path = tmp_path / "simulate_case.py"
    template_path.write_text(_template_source(extra_build_lines), encoding="utf-8")
    snapshot = SimpleNamespace(
        templates_list=[
            {
                "id": template_id,
                "path": str(template_path),
                "marker": "generated",
            }
        ]
    )
    monkeypatch.setattr(simulate, "build_corpus_snapshot", lambda _root: snapshot)
    monkeypatch.setattr(simulate, "get_schema_provider", lambda _mode: None)

    result = simulate.simulate_rule(
        "drop_set_id_map=true",
        template_ids=[template_id],
    )
    assert result.templates_total == len(result.per_template)
    assert result.templates_total == result.parity_preserved + result.parity_broken
    return result


def test_simulate_reports_invalid_transformed_source(
    tmp_path: Path,
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    result = _simulate_source(
        tmp_path,
        monkeypatch,
        '    if True:\n        wf._set_id_map({"node": "1"})',
    )

    assert result.templates_affected == 1
    assert result.parity_preserved == 0
    assert result.parity_broken == 1
    assert result.per_template[0]["parity_ok"] is False
    assert "IndentationError" in result.per_template[0]["error"]


def test_simulate_reports_semantic_divergence_in_transformed_source(
    tmp_path: Path,
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    result = _simulate_source(
        tmp_path,
        monkeypatch,
        '    wf.nodes["1"] = VibeNode(id="1", class_type="SaveImage", '
        'inputs={"filename_prefix": "_set_id_map("})',
    )

    assert result.templates_affected == 1
    assert result.parity_preserved == 0
    assert result.parity_broken == 1
    assert result.per_template[0]["parity_ok"] is False
    assert result.per_template[0]["semantic_parity_ok"] is False
    assert "canonical_form mismatch" in result.per_template[0]["parity_diffs"]


def test_simulate_preserves_unchanged_lookalike(
    tmp_path: Path,
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    result = _simulate_source(
        tmp_path,
        monkeypatch,
        "    # _set_id_map without a call is untouched",
    )

    assert result.templates_affected == 0
    assert result.parity_preserved == 1
    assert result.parity_broken == 0
    assert result.per_template[0]["changed"] is False


def test_simulate_accepts_changed_semantics_preserving_lookalike(
    tmp_path: Path,
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    result = _simulate_source(
        tmp_path,
        monkeypatch,
        "    # removing this _set_id_map( comment changes only source text",
    )

    assert result.templates_affected == 1
    assert result.parity_preserved == 1
    assert result.parity_broken == 0
    assert result.per_template[0]["changed"] is True
    assert result.per_template[0]["semantic_parity_ok"] is True


def test_simulate_reports_missing_requested_template_consistently(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    monkeypatch.setattr(
        simulate,
        "build_corpus_snapshot",
        lambda _root: SimpleNamespace(templates_list=[]),
    )
    monkeypatch.setattr(simulate, "get_schema_provider", lambda _mode: None)

    result = simulate.simulate_rule(
        "drop_set_id_map=true",
        template_ids=["image/missing"],
    )

    assert result.templates_total == 1
    assert result.templates_affected == 0
    assert result.parity_preserved == 0
    assert result.parity_broken == 1
    assert len(result.per_template) == 1
    assert result.per_template[0]["parity_ok"] is False
    assert result.per_template[0]["error"] == (
        "template not found in corpus: image/missing"
    )
