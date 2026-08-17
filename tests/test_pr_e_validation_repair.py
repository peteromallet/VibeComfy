"""Focused tests for PR-E (validation repair): asset-warning parity, structured
issue retention, bounded done() repair turn, Mapping-aware compaction, and the
concrete-class clarification guard."""

from __future__ import annotations

import json
from pathlib import Path
from types import SimpleNamespace

import pytest

from vibecomfy.comfy_nodes.agent.edit import (
    _class_names_from_text,
    _compact_diag_to_dict,
    handle_agent_edit,
)
from vibecomfy.ingest.normalize import from_ui
from vibecomfy.porting.edit._interpret import interpret
from vibecomfy.porting.edit._session_types import CompactDiagnostic, DoneResult
from vibecomfy.porting.edit.ops import NodeFieldTarget, SetNodeFieldOp
from vibecomfy.porting.edit.session import EditSession
from vibecomfy.porting.emit.ui import emit_ui_json
from vibecomfy.schema.provider import InputSpec, NodeSchema, OutputSpec
from vibecomfy.schema.validate import validate_api_against_schema
from vibecomfy.workflow import ValidationIssue


class _Provider:
    def __init__(self, schemas: dict[str, NodeSchema]) -> None:
        self._schemas = schemas

    def get_schema(self, class_type: str) -> NodeSchema | None:
        return self._schemas.get(class_type)

    def schemas(self) -> dict[str, NodeSchema]:
        return dict(self._schemas)

    all_schemas = schemas


def _schema(class_type: str, **inputs) -> NodeSchema:
    return NodeSchema(
        class_type=class_type,
        pack=None,
        inputs={name: InputSpec(**spec) for name, spec in inputs.items()},
        outputs=[],
        source_provider="test",
        confidence=1.0,
    )


_UNET_SCHEMA = _schema(
    "UNETLoader",
    unet_name={"type": "STRING", "choices": ["sd15.safetensors", "acestep-v15.safetensors"]},
    weight_dtype={"type": "STRING", "choices": ["default", "fp16", "fp32"]},
)
_KSAMPLER_SCHEMA = _schema(
    "KSampler",
    steps={"type": "INT", "min": 1, "max": 100, "default": 20},
    sampler_name={"type": "STRING", "choices": ["euler", "heun"]},
)


def _ui_graph() -> dict:
    return {
        "nodes": [
            {
                "id": 1,
                "type": "UNETLoader",
                "mode": 0,
                "properties": {"vibecomfy_uid": "8"},
                "widgets_values": ["sd15.safetensors", "default"],
                "inputs": [{"name": "unet_name", "type": "MODEL", "link": None}],
                "outputs": [{"name": "MODEL", "type": "MODEL", "links": [], "slot_index": 0}],
            }
        ],
        "links": [],
    }


def test_asset_swap_is_a_warning_not_a_hard_error_at_apply() -> None:
    """Unavailable checkpoint/model assets must not block the literal edit."""
    provider = _Provider({"UNETLoader": _UNET_SCHEMA})
    op = SetNodeFieldOp(
        op="set_node_field",
        target=NodeFieldTarget("", "8", "unet_name"),
        value="acestep-sft-v2.safetensors",
    )
    ui = _ui_graph()
    workflow = from_ui(ui, schema_provider=provider, use_comfy_converter=False)
    applied = interpret(workflow, (op,), schema_provider=provider)
    assert applied.ok is True
    candidate = emit_ui_json(
        applied.workflow,
        schema_provider=provider,
        include_virtual_wires=True,
        prior_ui_payload=ui,
    )
    assert candidate is not None
    codes = [issue.code for issue in applied.diagnostics]
    assert "asset_not_installed" in codes
    assert "value_not_in_enum" not in codes


def test_semantic_enum_violation_is_still_a_hard_error_at_apply() -> None:
    provider = _Provider({"UNETLoader": _UNET_SCHEMA})
    op = SetNodeFieldOp(
        op="set_node_field",
        target=NodeFieldTarget("", "8", "weight_dtype"),
        value="bogus_dtype",
    )
    workflow = from_ui(_ui_graph(), schema_provider=provider, use_comfy_converter=False)
    applied = interpret(workflow, (op,), schema_provider=provider)
    assert applied.ok is False
    assert any(issue.code == "value_not_in_enum" for issue in applied.diagnostics)


def test_final_validation_asset_enum_warns_semantic_enum_errors() -> None:
    provider = _Provider({"UNETLoader": _UNET_SCHEMA, "KSampler": _KSAMPLER_SCHEMA})
    api = {
        "1": {
            "class_type": "UNETLoader",
            "inputs": {"unet_name": "acestep-sft-v2.safetensors", "weight_dtype": "default"},
        },
        "2": {
            "class_type": "KSampler",
            "inputs": {"steps": 20, "sampler_name": "bogus_sampler"},
        },
    }
    issues = validate_api_against_schema(api, provider)
    by_code: dict[str, list[ValidationIssue]] = {}
    for issue in issues:
        by_code.setdefault(issue.code, []).append(issue)

    asset_issues = by_code.get("value_not_in_enum", [])
    unet = [i for i in asset_issues if (i.detail or {}).get("class_type") == "UNETLoader"]
    ksampler = [i for i in asset_issues if (i.detail or {}).get("class_type") == "KSampler"]
    assert unet and unet[0].severity == "warning"
    assert (unet[0].detail or {}).get("choice_scope") == "environment_asset"
    assert ksampler and ksampler[0].severity == "error"
    assert (ksampler[0].detail or {}).get("choice_scope") == "semantic"
    # Warnings are never hard errors.
    assert not any(issue.severity == "error" and (issue.detail or {}).get("class_type") == "UNETLoader" for issue in issues)


def test_compact_diag_to_dict_is_mapping_aware() -> None:
    mapping = {
        "code": "value_not_in_enum",
        "message": "not a declared choice",
        "severity": "error",
        "detail": {"choices": ["a", "b"]},
    }
    compact = _compact_diag_to_dict(mapping)
    assert compact["code"] == "value_not_in_enum"
    assert compact["message"] == "not a declared choice"
    assert compact["detail"] == {"choices": ["a", "b"]}


def test_class_names_from_text_matches_camelcase_concrete_classes() -> None:
    names = _class_names_from_text(
        "AudioLDM2 is not authorable; WanVideoModelLoader and StableZero123 are, but Rodin3D_Fusion is not."
    )
    assert "AudioLDM2" in names
    assert "WanVideoModelLoader" in names
    assert "StableZero123" in names
    assert "Rodin3D_Fusion" in names


def _batch_provider() -> _Provider:
    return _Provider(
        {
            "LoadImage": NodeSchema(
                class_type="LoadImage",
                pack=None,
                inputs={"image": InputSpec(type="STRING")},
                outputs=[OutputSpec("IMAGE", "IMAGE")],
                source_provider="test",
                confidence=1.0,
            ),
            "SaveImage": NodeSchema(
                class_type="SaveImage",
                pack=None,
                inputs={
                    "images": InputSpec(type="IMAGE", required=True),
                    "filename_prefix": InputSpec(type="STRING"),
                },
                outputs=[],
                source_provider="test",
                confidence=1.0,
            ),
        }
    )


def _saveimage_graph() -> dict:
    return {
        "nodes": [
            {
                "id": 1,
                "type": "LoadImage",
                "mode": 0,
                "properties": {"vibecomfy_uid": "load"},
                "inputs": [],
                "outputs": [{"name": "IMAGE", "type": "IMAGE", "links": [1], "slot_index": 0}],
                "widgets_values": ["input.png"],
            },
            {
                "id": 2,
                "type": "SaveImage",
                "mode": 0,
                "properties": {"vibecomfy_uid": "save"},
                "inputs": [
                    {"name": "images", "type": "IMAGE", "link": 1},
                    {"name": "filename_prefix", "type": "STRING", "link": None},
                ],
                "outputs": [],
                "widgets_values": ["before"],
            },
        ],
        "links": [[1, 1, 0, 2, 0, "IMAGE"]],
    }


def test_done_validation_failure_allows_one_bounded_repair_turn(
    tmp_path: Path,
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    monkeypatch.setenv("VIBECOMFY_AGENT_EDIT_BATCH_REPL", "1")
    monkeypatch.setattr(
        "vibecomfy.comfy_nodes.agent.edit.run_model_turn",
        lambda **_kwargs: {"json": {}},
    )

    calls = {"n": 0}
    original_done = EditSession.done

    def _failing_done_once(self):
        calls["n"] += 1
        if calls["n"] == 1:
            return DoneResult(
                ok=False,
                summary="Gate A failed: value not in enum.",
                diagnostics=(
                    CompactDiagnostic(
                        code="value_not_in_enum",
                        message="saveimage.filename_prefix rejected: value 'after' is not in the declared enum.",
                        severity="error",
                        detail={
                            "node_id": "2",
                            "class_type": "SaveImage",
                            "input": "filename_prefix",
                            "value": "after",
                            "choices": ["before", "default"],
                        },
                    ),
                ),
            )
        return original_done(self)

    monkeypatch.setattr(EditSession, "done", _failing_done_once)

    def _fake_client(_messages):
        if calls["n"] == 0:
            return {"batch": 'saveimage.filename_prefix = "after"\ndone()', "message": "Renaming."}
        return {"batch": "done()", "message": "Confirmed."}

    result = handle_agent_edit(
        {
            "graph": _saveimage_graph(),
            "workflow_id": "pr-e-repair",
            "task": "rename the save prefix to 'after'",
            "session_id": "pr-e-repair",
            "max_batches": 4,
            "max_consecutive_errors": 3,
        },
        schema_provider=_batch_provider(),
        deepseek_client=_fake_client,
        session_root=tmp_path,
    )

    assert result["ok"] is True
    assert calls["n"] == 2
    model_response = json.loads(
        (tmp_path / "pr-e-repair" / "turns" / "0001" / "model_response.json").read_text(encoding="utf-8")
    )
    turns = model_response["turns"]
    turn0 = turns[0]["batch_result"]
    assert "done() was NOT accepted" in turn0["report"]
    assert "value_not_in_enum" in turn0["report"]
    assert "target: node=SaveImage input=filename_prefix id=2" in turn0["report"]
    assert "declared choices: before, default" in turn0["report"]
    repair = turn0["done_validation_repair"]
    assert repair["attempt"] == 1
    assert repair["diagnostics"][0]["code"] == "value_not_in_enum"
    assert repair["diagnostics"][0]["detail"]["choices"] == ["before", "default"]


def test_h_scenario_speedup_value_is_genuinely_faster() -> None:
    scenario = json.loads(
        Path(
            "tests/live_agentic_harness/scenarios/"
            "image-image-to-image-with-stable-zero123-and-backgro-def5b5.json"
        ).read_text(encoding="utf-8")
    )
    query = scenario["query"]
    assert "steps to 4" in query and "speed up" in query
    assert "steps to 30" not in query
    workflow = json.loads(
        Path("external_workflows/corpus/def5b5d3b3b372dd.json").read_text(encoding="utf-8")
    )
    nodes = workflow.get("nodes") or workflow.get("prompt") or {}
    steps_values: list[int] = []

    def _walk(value):
        if isinstance(value, dict):
            for key, item in value.items():
                if key == "steps" and isinstance(item, (int, float)):
                    steps_values.append(int(item))
                _walk(item)
        elif isinstance(value, list):
            for item in value:
                _walk(item)

    _walk(nodes)
    assert 8 in steps_values
