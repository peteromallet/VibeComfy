from __future__ import annotations

import json
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


def test_simulate_runs_copied_artifacts_with_sibling_imports_and_isolated_side_effects(
    tmp_path: Path,
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    package = tmp_path / "fixture_package"
    package.mkdir()
    (package / "__init__.py").write_text("", encoding="utf-8")
    state = package / "state.txt"
    state.write_text("0", encoding="utf-8")
    (package / "sibling.py").write_text(
        """from pathlib import Path

state_path = Path(__file__).with_name("state.txt")
value = int(state_path.read_text()) + 1
state_path.write_text(str(value))
""",
        encoding="utf-8",
    )
    template_path = package / "template.py"
    template_path.write_text(
        """# vibecomfy: generated
from .sibling import value
from vibecomfy.workflow import VibeNode, VibeWorkflow, WorkflowSource


def build():
    wf = VibeWorkflow(id="isolated", source=WorkflowSource(id="isolated"))
    wf.nodes["1"] = VibeNode(
        id="1", class_type="SaveImage", inputs={"filename_prefix": str(value)}
    )
    # _set_id_map( is removed only from the copied artifact
    return wf
""",
        encoding="utf-8",
    )
    template_id = "image/isolated"
    snapshot = SimpleNamespace(
        templates_list=[
            {"id": template_id, "path": str(template_path), "marker": "generated"}
        ]
    )
    monkeypatch.setattr(simulate, "build_corpus_snapshot", lambda _root: snapshot)
    result = simulate.simulate_rule(
        "drop_set_id_map=true",
        template_ids=[template_id],
        schema_provider=None,
    )

    assert result.parity_broken == 0
    assert result.per_template[0]["parity_ok"] is True
    assert result.per_template[0]["changed"] is True
    assert state.read_text(encoding="utf-8") == "0"
    repeat = simulate.simulate_rule(
        "drop_set_id_map=true",
        template_ids=[template_id],
        schema_provider=None,
    )
    assert json.dumps(repeat.to_json(), sort_keys=True) == json.dumps(
        result.to_json(), sort_keys=True
    )


def test_simulate_rejects_malformed_boolean_without_running_corpus(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    def fail_if_discovered(_root: Path) -> object:
        raise AssertionError("corpus discovery must not run for malformed booleans")

    monkeypatch.setattr(simulate, "build_corpus_snapshot", fail_if_discovered)
    result = simulate.simulate_rule("drop_set_id_map=maybe")

    assert result.parity_broken == 0
    assert result.error is not None
    assert "Invalid boolean value" in result.error
