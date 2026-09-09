"""Focused r9 schema producer/provisioning regressions (offline only)."""

from __future__ import annotations

import json
from pathlib import Path
from types import SimpleNamespace

import pytest

from vibecomfy.errors import OnDemandCloneError
from vibecomfy.ingest.normalize import from_ui
from vibecomfy.porting.edit._op_validate import ApplyOpsError, _validate_one
from vibecomfy.porting.edit.ops import NodeFieldTarget, SetNodeFieldOp
from vibecomfy.schema import InputSpec, NodeSchema
from vibecomfy.schema import on_demand
from vibecomfy.schema.on_demand import OnDemandInstallSchemaProvider
from vibecomfy.schema.provider import _parse_input_spec
from vibecomfy.schema.types import capture_schema_snapshot, schema_snapshot_to_payload


def test_object_info_unknown_bounds_are_omitted_without_coercion() -> None:
    unknown = _parse_input_spec(
        ["INT", {"min": "0", "max": "BIGMAX"}], required=False
    )
    typed = _parse_input_spec(
        ["INT", {"min": 0, "max": 2147483647}], required=False
    )

    assert unknown.min is None
    assert unknown.max is None
    assert typed.min == 0
    assert typed.max == 2147483647

    # The sanitized producer output remains admissible under the strict
    # snapshot contract (the raw BIGMAX sentinel would fail this gate).
    from vibecomfy.porting.edit.admit import _validate_schema_payload_structure

    schema = NodeSchema(
        class_type="LoadImagesFromDirectory",
        pack="advanced-controlnet",
        inputs={"image_load_cap": unknown},
        outputs=[],
    )
    snapshot = capture_schema_snapshot(
        class_types=[schema.class_type],
        request_snapshot={
            "contract_version": "schema_snapshot_v1",
            "schemas": {
                schema.class_type: {
                    "class_type": schema.class_type,
                    "pack": schema.pack,
                    "inputs": {
                        "image_load_cap": {
                            "type": unknown.type,
                            "required": unknown.required,
                            "default": unknown.default,
                            "choices": unknown.choices,
                            "min": unknown.min,
                            "max": unknown.max,
                            "unresolved_choices": unknown.unresolved_choices,
                            "asset_kind": unknown.asset_kind,
                        }
                    },
                    "input_order": ["image_load_cap"],
                    "outputs": [],
                    "widget_input_order": [],
                    "provenance": {
                        "source_provider": "object_info",
                        "source_path": None,
                        "source_cache_path": None,
                        "source_server_url": None,
                        "source_package": None,
                        "source_version": None,
                        "source_hash": None,
                        "confidence": 1.0,
                        "conflicts": [],
                        "ignored_evidence": [],
                    },
                }
            },
            "missing_classes": [],
        },
    )
    _validate_schema_payload_structure(schema_snapshot_to_payload(snapshot), label="schema")


def _clone_ref() -> SimpleNamespace:
    return SimpleNamespace(
        slug="sample-pack",
        url="https://example.invalid/sample-pack",
        commit="commit-123",
        version=None,
    )


def _fake_git_with_racing_publication(
    sandbox: Path,
    *,
    matching: bool,
    monkeypatch: pytest.MonkeyPatch,
) -> Path:
    target = sandbox / "sample-pack"
    ref = _clone_ref()
    published = False

    def fake_run(command: list[str], timeout: int) -> SimpleNamespace:
        nonlocal published
        if command[:2] == ["git", "clone"]:
            Path(command[-1]).mkdir(parents=True)
            return SimpleNamespace(stdout="", stderr="")
        if "remote" in command and "get-url" in command:
            return SimpleNamespace(stdout=ref.url + "\n", stderr="")
        if command[-2:] == ["rev-parse", "HEAD"]:
            if not published and str(target) not in command:
                published = True
                (target / ".git").mkdir(parents=True)
                marker = {
                    "complete": True,
                    "slug": "sample-pack",
                    "url": ref.url,
                    "pin": ref.commit if matching else "other-pin",
                    "head": ref.commit,
                }
                (target / on_demand._CLONE_COMPLETE_MARKER).write_text(
                    json.dumps(marker), encoding="utf-8"
                )
            return SimpleNamespace(stdout=ref.commit + "\n", stderr="")
        if command[-1].endswith("^{commit}"):
            return SimpleNamespace(stdout=ref.commit + "\n", stderr="")
        return SimpleNamespace(stdout="", stderr="")

    monkeypatch.setattr(on_demand, "_run_git", fake_run)
    return target


def test_clone_reuses_matching_target_that_appears_during_publish(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    sandbox = tmp_path / "sandbox"
    provider = OnDemandInstallSchemaProvider(sandbox_root=sandbox)
    target = _fake_git_with_racing_publication(sandbox, matching=True, monkeypatch=monkeypatch)

    assert provider._ensure_clone(_clone_ref()) == target
    assert target.is_dir()


def test_clone_rejects_conflicting_target_that_appears_during_publish(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    sandbox = tmp_path / "sandbox"
    provider = OnDemandInstallSchemaProvider(sandbox_root=sandbox)
    target = _fake_git_with_racing_publication(sandbox, matching=False, monkeypatch=monkeypatch)

    with pytest.raises(OnDemandCloneError, match="conflicting"):
        provider._ensure_clone(_clone_ref())
    assert target.is_dir()


class _SchemaProvider:
    def __init__(self, schema: NodeSchema) -> None:
        self.schema = schema

    def get_schema(self, class_type: str) -> NodeSchema | None:
        return self.schema if class_type == self.schema.class_type else None


def test_canvas_named_field_without_exact_schema_witness_is_rejected() -> None:
    provider = _SchemaProvider(
        NodeSchema(
            class_type="MoonvalleyImg2VideoNode",
            pack="moonvalley",
            inputs={"prompt": InputSpec(type="STRING")},
            outputs=[],
        )
    )
    workflow = from_ui(
        {
            "nodes": [
                {
                    "id": 34,
                    "type": "MoonvalleyImg2VideoNode",
                    "widgets_values": {"steps": 100},
                    "inputs": [],
                    "outputs": [],
                    "properties": {"vibecomfy_uid": "34"},
                }
            ],
            "links": [],
            "groups": [],
        },
        schema_provider=provider,
        use_comfy_converter=False,
    )
    operation = SetNodeFieldOp(
        op="set_node_field",
        target=NodeFieldTarget("", "34", "steps"),
        value=80,
    )

    with pytest.raises(ApplyOpsError, match="exact authoring-schema witness") as caught:
        _validate_one(workflow, operation, provider)
    assert caught.value.code == "unknown_target_field"
