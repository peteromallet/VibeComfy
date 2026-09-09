"""Schema availability-to-admission continuity regressions (no live model)."""

from __future__ import annotations

from copy import deepcopy
import json
from pathlib import Path
from typing import Any

import pytest

from vibecomfy.comfy_nodes.agent.candidate_transaction import build_schema_witness
from vibecomfy.porting.edit.ops import NodeFieldTarget, SetNodeFieldOp
from vibecomfy.porting.edit.session import EditSession
from vibecomfy.schema import InputSpec, NodeSchema
from vibecomfy.schema.provider import SchemaProviderError
from vibecomfy.schema.types import capture_schema_snapshot


_CLASS_TYPE = "CustomAlphaNode"
_REMBG_CLASS_TYPE = "Image Remove Background Rembg (mtb)"


def _schema(*, class_type: str = _CLASS_TYPE) -> NodeSchema:
    return NodeSchema(
        class_type=class_type,
        pack="custom-alpha-pack",
        inputs={"transparent_background": InputSpec("BOOLEAN")},
        outputs=[],
        widget_input_order=("transparent_background",),
        source_provider="object_info",
    )


def _graph() -> dict[str, Any]:
    return {
        "nodes": [
            {
                "id": 6,
                "type": _CLASS_TYPE,
                "properties": {"vibecomfy_uid": "6"},
                "widgets_values": {"transparent_background": False},
            }
        ],
        "links": [],
        "groups": [],
        "last_node_id": 6,
        "last_link_id": 0,
        "version": 0.4,
    }


class _CatalogProvider:
    def __init__(
        self,
        catalog: dict[str, NodeSchema],
        *,
        enumeration_error: Exception | None = None,
    ) -> None:
        self.catalog = catalog
        self.enumeration_error = enumeration_error
        self.snapshot = capture_schema_snapshot(
            request_snapshot={
                "schemas": {},
                "missing_classes": [_CLASS_TYPE],
            },
            node_classes={"6": _CLASS_TYPE},
        )

    def get_schema(self, class_type: str) -> NodeSchema | None:
        return self.catalog.get(class_type)

    def schemas(self) -> dict[str, NodeSchema]:
        if self.enumeration_error is not None:
            raise self.enumeration_error
        return dict(self.catalog)


def _apply(session: EditSession, surface: str, field: str = "transparent_background"):
    if surface == "python":
        return session.apply_batch(f"customalphanode.{field} = True")
    return session.apply_ops(
        (
            SetNodeFieldOp(
                op="set_node_field",
                target=NodeFieldTarget("", "6", field),
                value=True,
            ),
        )
    )


class TestSchemaAvailabilityAdmissionContinuity:
    @pytest.mark.parametrize("surface", ("python", "typed"))
    def test_custom_pack_parameter_edit_admits_replays_and_retains_witness(
        self, surface: str
    ) -> None:
        session = EditSession(
            _graph(), schema_provider=_CatalogProvider({_CLASS_TYPE: _schema()})
        )

        result = _apply(session, surface)

        assert result.ok is True, result.diagnostics
        assert session.revision == 1
        assert session.workflow.nodes["6"].inputs["transparent_background"] is True
        replayed = session.verify_delta_history()
        assert replayed.nodes["6"].inputs["transparent_background"] is True
        snapshot = session.schema_provider.snapshot
        assert snapshot.generation == 1
        assert _CLASS_TYPE in snapshot.schemas
        assert _CLASS_TYPE not in snapshot.missing_classes
        witness = build_schema_witness(
            schema_provider=session.schema_provider,
            submit_graph=None,
            candidate_payload=None,
            delta_envelope=None,
        )
        assert witness["schema_snapshot"]["content_digest"] == snapshot.content_digest
        assert "transparent_background" in witness["schemas"][_CLASS_TYPE]["inputs"]

    @pytest.mark.parametrize("surface", ("python", "typed"))
    def test_unavailable_custom_pack_schema_rejects_atomically(
        self, surface: str
    ) -> None:
        session = EditSession(_graph(), schema_provider=_CatalogProvider({}))
        before = deepcopy(session.workflow)

        result = _apply(session, surface)

        assert result.ok is False
        assert any(diagnostic.code == "missing_touched_schema" for diagnostic in result.diagnostics)
        assert session.revision == 0
        assert session.landed_ops == []
        assert session.history == ()
        assert session.workflow == before

    @pytest.mark.parametrize("surface", ("python", "typed"))
    def test_post_freeze_catalog_tamper_cannot_authorize_a_forged_field(
        self, surface: str
    ) -> None:
        authoritative = _schema()
        session = EditSession(
            _graph(),
            schema_provider=_CatalogProvider({_CLASS_TYPE: authoritative}),
        )
        before = deepcopy(session.workflow)
        authoritative.inputs["forged_field"] = InputSpec("BOOLEAN")

        result = _apply(session, surface, field="forged_field")

        assert result.ok is False
        assert any(
            diagnostic.code
            in {"unknown_field", "unknown_target_field", "schema_admission_mismatch"}
            for diagnostic in result.diagnostics
        )
        assert session.revision == 0
        assert session.landed_ops == []
        assert session.history == ()
        assert session.workflow == before

    @pytest.mark.parametrize("surface", ("python", "typed"))
    def test_catalog_provider_error_is_distinct_and_atomic(self, surface: str) -> None:
        failure = SchemaProviderError(_CLASS_TYPE, RuntimeError("catalog offline"))
        session = EditSession(
            _graph(),
            schema_provider=_CatalogProvider(
                {_CLASS_TYPE: _schema()}, enumeration_error=failure
            ),
        )
        before = deepcopy(session.workflow)

        result = _apply(session, surface)

        assert result.ok is False
        assert any(
            diagnostic.code == "schema_provider_error"
            for diagnostic in result.diagnostics
        )
        assert not any(
            diagnostic.code == "missing_touched_schema"
            for diagnostic in result.diagnostics
        )
        assert session.revision == 0
        assert session.landed_ops == []
        assert session.history == ()
        assert session.workflow == before

    @pytest.mark.parametrize("surface", ("python", "typed"))
    def test_mismatched_catalog_schema_rejects_as_admission_mismatch(
        self, surface: str
    ) -> None:
        session = EditSession(
            _graph(),
            schema_provider=_CatalogProvider(
                {_CLASS_TYPE: _schema(class_type="ForeignAlphaNode")}
            ),
        )
        before = deepcopy(session.workflow)

        result = _apply(session, surface)

        assert result.ok is False
        assert any(
            diagnostic.code == "schema_admission_mismatch"
            for diagnostic in result.diagnostics
        )
        assert session.revision == 0
        assert session.landed_ops == []
        assert session.history == ()
        assert session.workflow == before


def _rembg_object_info() -> dict[str, Any]:
    """Runtime-captured object_info shape; names, never UI positions, are authority."""
    return {
        "LoadImage": {
            "inputs": {
                "required": {
                    "image": ["STRING", {"default": "input.png"}],
                }
            },
            "input_order_all": ["image"],
            "object_info_widget_order": ["image"],
            "outputs": [
                {"name": "IMAGE", "type": "IMAGE", "is_list": False},
                {"name": "MASK", "type": "MASK", "is_list": False},
            ],
            "pack": "comfy-core",
        },
        _REMBG_CLASS_TYPE: {
            "inputs": {
                "required": {
                    "image": ["IMAGE"],
                    "transparent_background": [
                        "BOOLEAN",
                        {"default": False},
                    ],
                    "threshold": [
                        "INT",
                        {"default": 240, "min": 0, "max": 255},
                    ],
                    "edge_smoothing": [
                        "INT",
                        {"default": 10, "min": 0, "max": 255},
                    ],
                    "edge_size": [
                        "INT",
                        {"default": 10, "min": 0, "max": 255},
                    ],
                    "only_mask": ["BOOLEAN", {"default": False}],
                    "background_color": ["STRING", {"default": "#000000"}],
                }
            },
            "input_order_all": [
                "image",
                "transparent_background",
                "threshold",
                "edge_smoothing",
                "edge_size",
                "only_mask",
                "background_color",
            ],
            "object_info_widget_order": [
                None,
                "transparent_background",
                "threshold",
                "edge_smoothing",
                "edge_size",
                "only_mask",
                "background_color",
            ],
            "outputs": [
                {"name": "Image (rgba)", "type": "IMAGE", "is_list": False},
                {"name": "Mask", "type": "MASK", "is_list": False},
                {"name": "Image", "type": "IMAGE", "is_list": False},
            ],
            "pack": "comfy-mtb",
        },
    }


def _rembg_graph(widgets_values: list[Any] | dict[str, Any]) -> dict[str, Any]:
    return {
        "nodes": [
            {
                "id": 1,
                "type": "LoadImage",
                "properties": {"vibecomfy_uid": "1"},
                "widgets_values": ["input.png"],
                "outputs": [
                    {"name": "IMAGE", "type": "IMAGE", "links": [1]},
                    {"name": "MASK", "type": "MASK", "links": None},
                ],
            },
            {
                "id": 6,
                "type": _REMBG_CLASS_TYPE,
                "properties": {"vibecomfy_uid": "6"},
                "widgets_values": widgets_values,
                "inputs": [{"name": "image", "type": "IMAGE", "link": 1}],
                "outputs": [
                    {"name": "Image (rgba)", "type": "IMAGE", "links": None},
                    {"name": "Mask", "type": "MASK", "links": None},
                    {"name": "Image", "type": "IMAGE", "links": None},
                ],
            },
        ],
        "links": [[1, 1, 0, 6, 0, "IMAGE"]],
        "groups": [],
        "last_node_id": 6,
        "last_link_id": 1,
        "version": 0.4,
    }


def _object_info_provider(tmp_path: Path, payload: dict[str, Any]):
    from vibecomfy.schema.provider import ObjectInfoSchemaProvider

    path = tmp_path / "object_info.json"
    path.write_text(json.dumps(payload), encoding="utf-8")
    return ObjectInfoSchemaProvider(path)


def test_product_ingress_preserves_authoritative_rembg_named_field_to_admission(
    tmp_path: Path,
) -> None:
    """The real product door carries runtime object_info through stage/session."""
    from vibecomfy.comfy_nodes.agent import edit as agent_edit_module

    widgets_values = [False, 240, 10, 10, False, "#000000"]
    session_id = "rembg-ingress-list"
    result = agent_edit_module.handle_agent_edit(
        {
            "graph": _rembg_graph(deepcopy(widgets_values)),
            "workflow_id": "rembg-ingress-proof",
            "task": "Enable the Rembg node's transparent background output.",
            "session_id": session_id,
            "max_batches": 1,
        },
        schema_provider=_object_info_provider(tmp_path, _rembg_object_info()),
        deepseek_client=lambda _messages: {
            "message": "Enabled transparent background.",
            "batch": (
                "image_remove_background_rembg__mtb_.transparent_background = True\n"
                "done()"
            ),
        },
        session_root=tmp_path,
    )

    assert result["ok"] is True, result
    assert result["graph_unchanged"] is False, result
    assert result["candidate"] is not None
    assert result["candidate_transaction"] is not None
    operation = result["accepted_batch"][0]["op"]
    assert operation == {
        "op": "set_node_field",
        "target": ["", "6", "transparent_background"],
        "value": True,
    }
    rembg = next(node for node in result["graph"]["nodes"] if node["id"] == 6)
    assert rembg["widgets_values"] == [True, 240, 10, 10, False, "#000000"]

    model_turn = json.loads(
        (
            tmp_path / session_id / "turns" / "0001" / "model_response.json"
        ).read_text(encoding="utf-8")
    )["turns"][0]["batch_result"]
    assert model_turn["batch_ok"] is True
    assert model_turn["landed_op_count"] == 1
    assert model_turn["statements"][0]["op"] == operation

    receipt = json.loads(
        (
            tmp_path
            / session_id
            / "turns"
            / "0001"
            / "authority"
            / "receipt.json"
        ).read_text(encoding="utf-8")
    )
    witness = receipt["schema_witness"]
    schema = witness["schemas"][_REMBG_CLASS_TYPE]
    assert "transparent_background" in schema["inputs"]
    assert "widget_0" not in schema["inputs"]
    assert schema["widget_input_order"] == [
        "transparent_background",
        "threshold",
        "edge_smoothing",
        "edge_size",
        "only_mask",
        "background_color",
    ]
    assert _REMBG_CLASS_TYPE not in witness["missing_class_types"]
    assert receipt["replay"]["replay_ok"] is True
    assert receipt["replay"]["candidate_matches"] is True


def test_product_ingress_unavailable_rembg_schema_rejects_atomically(
    tmp_path: Path,
) -> None:
    from vibecomfy.comfy_nodes.agent import edit as agent_edit_module

    provider_payload = _rembg_object_info()
    del provider_payload[_REMBG_CLASS_TYPE]
    result = agent_edit_module.handle_agent_edit(
        {
            "graph": _rembg_graph([False, 240, 10, 10, False, "#000000"]),
            "workflow_id": "rembg-ingress-proof",
            "task": "Enable the Rembg node's transparent background output.",
            "session_id": "rembg-ingress-unavailable",
            "max_batches": 1,
            "max_consecutive_errors": 1,
        },
        schema_provider=_object_info_provider(tmp_path, provider_payload),
        deepseek_client=lambda _messages: {
            "message": "Enabled transparent background.",
            "batch": (
                "image_remove_background_rembg__mtb_.transparent_background = True\n"
                "done()"
            ),
        },
        session_root=tmp_path,
    )

    attempted = result["batch_turns"][0]["statements"][0]
    assert attempted["op"] == {
        "op": "set_node_field",
        "target": ["", "6", "transparent_background"],
        "value": True,
    }
    assert attempted["ok"] is False
    assert any(
        diagnostic["code"] == "missing_touched_schema"
        for diagnostic in attempted["diagnostics"]
    )
    assert result["accepted_batch"] == []
    assert result["graph_unchanged"] is True
    assert result.get("graph") is None


def test_product_ingress_post_capture_schema_tamper_cannot_authorize_field(
    tmp_path: Path,
) -> None:
    from vibecomfy.comfy_nodes.agent import edit as agent_edit_module
    from vibecomfy.schema import InputSpec

    provider = _object_info_provider(tmp_path, _rembg_object_info())

    def tampering_client(_messages):
        # This happens after ingress and EditSession construction. The mutable
        # provider cannot expand the frozen named-field authority.
        provider.schemas()[_REMBG_CLASS_TYPE].inputs["forged_field"] = InputSpec(
            "BOOLEAN"
        )
        return {
            "message": "Attempted a forged field.",
            "batch": "image_remove_background_rembg__mtb_.forged_field = True\ndone()",
        }

    result = agent_edit_module.handle_agent_edit(
        {
            "graph": _rembg_graph([False, 240, 10, 10, False, "#000000"]),
            "workflow_id": "rembg-ingress-proof",
            "task": "Set the Rembg forged field.",
            "session_id": "rembg-ingress-tampered",
            "max_batches": 1,
            "max_consecutive_errors": 1,
        },
        schema_provider=provider,
        deepseek_client=tampering_client,
        session_root=tmp_path,
    )

    attempted = result["batch_turns"][0]["statements"][0]
    assert attempted["ok"] is False
    assert any(
        diagnostic["code"] in {"unknown_field", "unknown_target_field"}
        for diagnostic in attempted["diagnostics"]
    )
    assert result["accepted_batch"] == []
    assert result["graph_unchanged"] is True
    assert result.get("graph") is None
