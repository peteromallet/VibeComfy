from __future__ import annotations

import json
from types import SimpleNamespace

import tools.check_strict_ready_templates as gate


def test_strict_ready_gate_report_is_repo_only_and_deterministic() -> None:
    first = gate.build_strict_ready_report()
    second = gate.build_strict_ready_report()

    assert json.dumps(first, sort_keys=True) == json.dumps(second, sort_keys=True)
    assert first["version"] == 1
    assert first["template_count"] >= first["target_count"] > 0
    assert all(target["source_scope"] == "repo" for target in first["targets"])
    assert all(target["indexed"] is True for target in first["targets"])
    assert all(target["source_scope"] != "dynamic" for target in first["targets"])
    assert first["diagnostics"] == sorted(
        first["diagnostics"],
        key=lambda item: (item["ready_id"], item["category"], item["code"], item["target"]),
    )


def test_static_drift_diagnostics_report_public_contract_mismatch(monkeypatch) -> None:
    class _Contract:
        def to_dict(self) -> dict[str, object]:
            return {
                "public_inputs": [{"name": "prompt", "node_id": "2", "field": "text"}],
                "public_outputs": [],
            }

    monkeypatch.setattr(gate, "_workflow_from_repo_template", lambda *_args, **_kwargs: object())
    monkeypatch.setattr(gate, "build_contract", lambda _workflow: _Contract())
    diagnostics = gate._static_drift_diagnostics(
        {
            "id": "image/example",
            "path": "ready_templates/image/example.py",
            "public_inputs": [{"name": "prompt", "node_id": "1", "field": "text"}],
            "public_outputs": [],
        },
        ready_id="image/example",
        enforced=True,
    )

    assert [item["code"] for item in diagnostics] == [
        "static_contract_inputs_only_built",
        "static_contract_inputs_only_static",
    ]
    assert all(item["severity"] == "error" and item["enforced"] is True for item in diagnostics)


def test_generated_style_diagnostics_are_warnings_until_protected() -> None:
    entry = SimpleNamespace(
        marker="generated",
        counts=SimpleNamespace(
            positional_outs=1,
            widget_n_fields=0,
            uuid_class_types=0,
            n_uuid_variables=0,
            local_node_copies=0,
            missing_output_contract=True,
        ),
    )

    diagnostics = gate._style_diagnostics(
        entry,
        ready_id="image/generated",
        path="ready_templates/image/generated.py",
        enforced=False,
    )

    assert [item["code"] for item in diagnostics] == [
        "generated_template_positional_out",
        "generated_template_missing_output_contract",
    ]
    assert all(item["severity"] == "warning" and item["enforced"] is False for item in diagnostics)


def test_manual_legacy_v26_shape_diagnostics_are_not_blocking_when_unprotected(tmp_path: Path) -> None:
    template = tmp_path / "manual.py"
    template.write_text(
        """
# vibecomfy: manual
from vibecomfy.registry.ready_template import bind_input

def _at(wf, node_id, field):
    return wf.nodes[node_id].inputs[field]

def build():
    bind_input(None, 'prompt', '1', 'text')
""".lstrip(),
        encoding="utf-8",
    )

    diagnostics = gate._v26_shape_diagnostics(
        ready_id="image/manual",
        path=template,
        relative_path="ready_templates/image/manual.py",
        enforced=False,
    )

    assert any(item["code"] == "v26_legacy_ready_template_call" for item in diagnostics)
    assert all(item["severity"] == "warning" and item["enforced"] is False for item in diagnostics)


def test_legacy_vocabulary_diagnostic_flips_per_target_ok_false(monkeypatch) -> None:
    """Synthetic legacy import/call diagnostic causes per-target ok=false."""
    monkeypatch.setattr(
        gate,
        "_legacy_vocabulary_diagnostics",
        lambda **_kwargs: [
            gate._diagnostic(
                code="legacy_vocabulary_import",
                message="Generated template imports legacy module 'vibecomfy.registry.ready_template'.",
                ready_id="image/example",
                target="ready_templates/image/example.py",
                severity="error",
                category="legacy_vocabulary",
                enforced=True,
                detail={"import": "vibecomfy.registry.ready_template", "line": 5},
            ),
        ],
    )

    target = gate._check_template(
        {
            "id": "image/example",
            "path": "ready_templates/image/example.py",
            "coverage_tier": "required",
            "app_active": True,
        },
        None,
    )

    assert target["ok"] is False
    assert len(target["legacy_vocabulary_diagnostics"]) == 1
    diag = target["legacy_vocabulary_diagnostics"][0]
    assert diag["code"] == "legacy_vocabulary_import"
    assert diag["severity"] == "error"
    assert diag["enforced"] is True
    assert diag["category"] == "legacy_vocabulary"


def test_legacy_vocabulary_call_flips_per_target_ok_false(monkeypatch) -> None:
    """Synthetic legacy call diagnostic causes per-target ok=false and exits nonzero."""
    monkeypatch.setattr(
        gate,
        "_legacy_vocabulary_diagnostics",
        lambda **_kwargs: [
            gate._diagnostic(
                code="legacy_vocabulary_call",
                message="Generated template calls legacy function 'bind_input'.",
                ready_id="video/legacy",
                target="ready_templates/video/legacy.py:42",
                severity="error",
                category="legacy_vocabulary",
                enforced=True,
                detail={"call": "bind_input", "line": 42},
            ),
        ],
    )

    target = gate._check_template(
        {
            "id": "video/legacy",
            "path": "ready_templates/video/legacy.py",
            "coverage_tier": "required",
            "app_active": True,
        },
        None,
    )

    assert target["ok"] is False
    assert len(target["legacy_vocabulary_diagnostics"]) == 1
    diag = target["legacy_vocabulary_diagnostics"][0]
    assert diag["code"] == "legacy_vocabulary_call"
    assert diag["severity"] == "error"
    assert diag["enforced"] is True
    assert diag["category"] == "legacy_vocabulary"


def test_legacy_vocabulary_main_exits_nonzero(monkeypatch, capsys) -> None:
    """Synthetic legacy diagnostic causes main() to exit nonzero and report ok=false."""
    monkeypatch.setattr(
        gate,
        "build_strict_ready_report",
        lambda: {
            "ok": False,
            "target_count": 1,
            "summary": {"diagnostics": 1, "enforced_errors": 1},
            "diagnostics": [
                {
                    "ready_id": "image/example",
                    "category": "legacy_vocabulary",
                    "code": "legacy_vocabulary_call",
                    "target": "ready_templates/image/example.py:42",
                    "severity": "error",
                    "enforced": True,
                    "message": "Generated template calls legacy function 'bind_input'.",
                }
            ],
        },
    )

    assert gate.main(["--json"]) == 1
    payload = json.loads(capsys.readouterr().out)
    assert payload["ok"] is False
    assert payload["summary"]["enforced_errors"] == 1


def test_strict_ready_gate_main_exits_nonzero_for_enforced_errors(monkeypatch, capsys) -> None:
    monkeypatch.setattr(
        gate,
        "build_strict_ready_report",
        lambda: {
            "ok": False,
            "target_count": 1,
            "summary": {"diagnostics": 1},
            "diagnostics": [
                {
                    "ready_id": "image/example",
                    "category": "strict_ready",
                    "code": "strict_ready_missing_public_input",
                    "target": "public_inputs",
                    "severity": "error",
                    "enforced": True,
                    "message": "missing input",
                }
            ],
        },
    )

    assert gate.main(["--json"]) == 1
    payload = json.loads(capsys.readouterr().out)
    assert payload["ok"] is False


def test_v26_shape_rejects_derivable_source_workflow_and_provenance(tmp_path: Path) -> None:
    template = tmp_path / "example.py"
    template.write_text(
        """
from vibecomfy.templates import ReadyMetadata, new_workflow

PUBLIC_INPUTS = {}
MODELS = {}
READY_METADATA = ReadyMetadata.build(
    capability='text_to_image',
    inputs=PUBLIC_INPUTS,
    models=MODELS,
    source_workflow='workflow_corpus/official/image/example.json',
    provenance={'source_workflow': 'workflow_corpus/official/image/example.json'},
)

def build():
    with new_workflow(READY_METADATA, source_path=__file__) as wf:
        return wf.finalize(PUBLIC_INPUTS)
""".lstrip(),
        encoding="utf-8",
    )

    diagnostics = gate._v26_shape_diagnostics(
        ready_id="image/example",
        path=template,
        relative_path="ready_templates/image/example.py",
        enforced=True,
    )

    codes = {item["code"] for item in diagnostics}
    assert codes == {"v26_derivable_metadata_field"}
    messages = {item["message"] for item in diagnostics}
    assert "ReadyMetadata.build emits derivable field 'source_workflow'." in messages
    assert "ReadyMetadata.build emits derivable field 'provenance'." in messages
    assert all(item["severity"] == "error" and item["enforced"] is True for item in diagnostics)



