from __future__ import annotations

import pytest

from vibecomfy.comfy_nodes.agent import provider as agent_provider
from vibecomfy.porting.edit.ops import (
    AgentDeltaTurnResult,
    DELTA_DIAGNOSTIC_LEGACY_SHAPE,
    DELTA_DIAGNOSTIC_UNSUPPORTED_SCOPED_APPLY,
    EditOpParseError,
    canonical_op_to_dict,
    ensure_root_scoped_delta_envelope,
    normalize_delta_agent_response,
    normalize_delta_envelope,
    normalize_delta_test_client_response,
    parse_edit_delta,
)


def test_v1_agent_provider_normalizer_remains_python_message_only() -> None:
    result = agent_provider._normalize_agent_response(  # type: ignore[attr-defined]
        {"python": "print('ok')", "message": "done"},
        route="arnold",
        model="agent-edit",
    )

    assert result.python == "print('ok')"
    assert result.message == "done"
    assert result.route == "arnold"


def test_normalize_delta_agent_response_parses_typed_v2_delta() -> None:
    result = normalize_delta_agent_response(
        {
            "delta": [
                {
                    "op": "set_node_field",
                    "target": ["", "seed-node", "inputs.seed"],
                    "value": 7,
                },
                {
                    "op": "set_mode",
                    "target": ["sg:abc", "bypass-node"],
                    "mode": 4,
                },
            ],
            "message": "updated the seed and bypassed the node",
        },
        route="deepseek",
        model="agent-edit-v2",
    )

    assert isinstance(result, AgentDeltaTurnResult)
    assert len(result.delta) == 2
    assert result.message == "updated the seed and bypassed the node"
    assert result.route == "deepseek"
    assert result.model == "agent-edit-v2"


def test_normalize_delta_test_client_response_requires_typed_delta() -> None:
    result = normalize_delta_test_client_response(
        {
            "delta": [
                {
                    "op": "remove_link",
                    "id": 12,
                }
            ],
            "message": "removed the stale link",
        }
    )

    assert result.route == "test_client"
    assert len(result.delta) == 1


def test_agent_delta_turn_result_to_dict_emits_canonical_envelope_and_bridge() -> None:
    result = AgentDeltaTurnResult(
        delta=parse_edit_delta(
            [
                {
                    "op": "add_node",
                    "scope_path": "",
                    "uid": "preview-uid",
                    "node_id": "77",
                    "class_type": "PreviewImage",
                    "fields": {},
                    "inputs": {"images": ["", "seed-node", "IMAGE"]},
                }
            ]
        ),
        message="added preview node",
        route="deepseek",
        model="agent-edit-v2",
        audit_metadata={"response_contract": "delta"},
    )

    payload = result.to_dict()

    assert payload["delta"] == payload["delta_ops_envelope"]["ops"]
    assert payload["delta_ops_envelope"] == {
        "schema_version": "2.0.0",
        "ops": [
            {
                "op": "add_node",
                "scope_path": "",
                "uid": "preview-uid",
                "node_id": "77",
                "class_type": "PreviewImage",
                "fields": {},
                "inputs": {"images": ["", "seed-node", "IMAGE"]},
            }
        ],
    }


def test_normalize_delta_envelope_roundtrips_canonical_v2_ops() -> None:
    payload = {
        "schema_version": "2.0.0",
        "ops": [
            {
                "op": "set_node_field",
                "target": ["", "seed-node", "inputs.seed"],
                "value": 7,
            },
            {
                "op": "set_mode",
                "target": ["", "mute-node"],
                "mode": 4,
            },
            {
                "op": "add_node",
                "scope_path": "",
                "uid": "new-uid",
                "node_id": "9001",
                "class_type": "PreviewImage",
                "fields": {"filename_prefix": "after"},
                "inputs": {"images": ["", "seed-node", "IMAGE"]},
            },
            {
                "op": "upsert_link",
                "from": ["", "seed-node", "IMAGE"],
                "to": ["", "preview-node", "images"],
            },
            {
                "op": "remove_node",
                "target": ["", "old-node"],
            },
            {
                "op": "remove_link",
                "to": ["", "preview-node", "images"],
            },
        ],
    }

    envelope = normalize_delta_envelope(payload)

    assert envelope.schema_version == "2.0.0"
    assert [canonical_op_to_dict(op) for op in envelope.ops] == payload["ops"]
    assert envelope.to_dict() == payload


def test_normalize_delta_envelope_rejects_legacy_wrapped_mapping() -> None:
    with pytest.raises(EditOpParseError, match="Legacy"):
        normalize_delta_envelope(
            {
                "ops": [],
                "diagnostics": [],
            }
        )

    exc = pytest.raises(
        EditOpParseError,
        normalize_delta_envelope,
        {"delta_ops": {"ops": []}},
    )
    assert exc.value.code == DELTA_DIAGNOSTIC_LEGACY_SHAPE


def test_ensure_root_scoped_delta_envelope_rejects_non_root_scope() -> None:
    with pytest.raises(EditOpParseError, match="Non-root scoped apply"):
        ensure_root_scoped_delta_envelope(
            {
                "schema_version": "2.0.0",
                "ops": [
                    {
                        "op": "set_mode",
                        "target": ["sg:nested", "node-1"],
                        "mode": 2,
                    }
                ],
            }
        )

    exc = pytest.raises(
        EditOpParseError,
        ensure_root_scoped_delta_envelope,
        {
            "schema_version": "2.0.0",
            "ops": [{"op": "remove_node", "target": ["sg:nested", "node-1"]}],
        },
    )
    assert exc.value.code == DELTA_DIAGNOSTIC_UNSUPPORTED_SCOPED_APPLY


@pytest.mark.parametrize(
    "payload",
    [
        [{"op": "rename_everything", "target": ["", "u1"], "value": "x"}],
        [{"op": "noop"}],
    ],
)
def test_parse_edit_delta_rejects_unknown_ops(payload: list[dict[str, object]]) -> None:
    with pytest.raises(EditOpParseError, match="Unsupported edit op"):
        parse_edit_delta(payload)


@pytest.mark.parametrize(
    ("payload", "match"),
    [
        (
            [{"op": "set_node_field", "target": ["", "only-two"], "value": 1}],
            r"target must be a list of length 3",
        ),
        (
            [{"op": "remove_node", "target": "u1"}],
            r"target must be a list of length 2",
        ),
        (
            [{"op": "upsert_link", "from": ["", "u1"], "to": ["", "u2", "images"]}],
            r"from must be a list of length 3",
        ),
        (
            [{"op": "upsert_link", "from": ["", "u1", 0], "to": ["", "u2"]}],
            r"to must be a list of length 3",
        ),
    ],
)
def test_parse_edit_delta_rejects_malformed_targets(
    payload: list[dict[str, object]],
    match: str,
) -> None:
    with pytest.raises(EditOpParseError, match=match):
        parse_edit_delta(payload)


def test_parse_edit_delta_rejects_raw_node_payloads() -> None:
    with pytest.raises(EditOpParseError, match="unsupported raw payload field"):
        parse_edit_delta(
            [
                {
                    "op": "add_node",
                    "scope_path": "",
                    "class_type": "SaveImage",
                    "fields": {"filename_prefix": "after"},
                    "node": {"id": 99, "type": "SaveImage"},
                }
            ]
        )


@pytest.mark.parametrize(
    "payload",
    [
        [{"op": "upsert_link", "from": ["", "u1", 0], "to": ["", "u2", "images"], "link": [1, 2, 3]}],
        [{"op": "remove_link", "id": 1, "raw_link": {"id": 1}}],
    ],
)
def test_parse_edit_delta_rejects_raw_link_payloads(payload: list[dict[str, object]]) -> None:
    with pytest.raises(EditOpParseError, match="unsupported raw payload field"):
        parse_edit_delta(payload)


@pytest.mark.parametrize("mode", [-1, 1, 3, 5, True, "4"])
def test_parse_edit_delta_rejects_invalid_modes(mode: object) -> None:
    with pytest.raises(EditOpParseError, match=r"mode must be one of: 0, 2, 4"):
        parse_edit_delta([{"op": "set_mode", "target": ["", "u1"], "mode": mode}])


@pytest.mark.parametrize(
    ("payload", "match"),
    [
        (
            [{"op": "reorder", "target": ["", "u1"], "axis": "fields", "order": ["seed"]}],
            r"axis must be one of: slots, widgets",
        ),
        (
            [{"op": "reorder", "target": ["", "u1"], "axis": "widgets", "order": [0, 1]}],
            r"order\[0\] must be a string",
        ),
        (
            [{"op": "reorder", "target": ["", "u1"], "axis": "slots", "order": []}],
            r"order must not be empty",
        ),
        (
            [{"op": "reorder", "target": ["", "u1"], "axis": "widgets", "order": ["seed", "seed"]}],
            r"order must not contain duplicate entries",
        ),
    ],
)
def test_parse_edit_delta_rejects_unsupported_reorder_forms(
    payload: list[dict[str, object]],
    match: str,
) -> None:
    with pytest.raises(EditOpParseError, match=match):
        parse_edit_delta(payload)


@pytest.mark.parametrize(
    ("payload", "exc_type", "match"),
    [
        (
            {"message": "missing delta"},
            agent_provider.MissingRequiredField,
            r"key `delta`",
        ),
        (
            {"delta": [], "message": "x", "python": "print('legacy')"},
            EditOpParseError,
            r"only accepts `delta` and `message`",
        ),
        (
            {"delta": "not-a-list", "message": "x"},
            EditOpParseError,
            r"delta must be a list of op objects",
        ),
    ],
)
def test_normalize_delta_agent_response_is_strict_about_v2_contract(
    payload: dict[str, object],
    exc_type: type[Exception],
    match: str,
) -> None:
    with pytest.raises(exc_type, match=match):
        normalize_delta_agent_response(payload, route="arnold", model="agent-edit-v2")
