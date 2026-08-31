"""Mixed API/UI replay-domain characterization for schema-opaque nodes.

The API pre-carrier names ``max_tokens`` while the UI post-carrier stores the
same node positionally.  A frozen pre-state roster must make this one field
edit, rather than a node replacement. Every acceptance assertion has a
fail-closed tamper control.
"""

from __future__ import annotations

import copy
import json
from pathlib import Path

from vibecomfy.ingest.normalize import from_api, from_envelope, from_ui
from vibecomfy.ingest.snapshot import frozen_widget_names_by_uid
from vibecomfy.porting.edit._diff import diff
from vibecomfy.porting.edit._interpret import interpret
from vibecomfy.porting.edit.ops import parse_edit_delta


_FIXTURES = Path(__file__).parent / "fixtures" / "replay_domain"


def _mixed_fixture() -> tuple[object, dict, dict]:
    api = json.loads((_FIXTURES / "llama_api_pre.json").read_text(encoding="utf-8"))
    pre = from_envelope(from_api(api).to_envelope())
    post_ui = json.loads(
        (_FIXTURES / "llama_ui_post.json").read_text(encoding="utf-8")
    )
    post = from_ui(post_ui, use_comfy_converter=False)
    return pre, post_ui, post


def test_mixed_api_ui_one_field_edit_stays_one_delta() -> None:
    pre, _post_ui, post = _mixed_fixture()
    ops = diff(pre, post)
    assert len(ops) == 1
    assert ops[0].target.uid == "3"
    assert ops[0].target.field_path == "max_tokens"
    assert ops[0].value == 512
    replayed = interpret(pre, ops)
    assert replayed.ok is True, replayed.diagnostics
    assert diff(replayed.workflow, post) == ()


def test_mixed_carrier_tampering_stays_fail_closed() -> None:
    pre, post_ui, _post = _mixed_fixture()
    op = {"op": "set_node_field", "target": ["", "3", "max_tokens"], "value": 512}
    ops = parse_edit_delta([op])
    replayed = interpret(pre, ops)
    assert replayed.ok is True

    # An untouched widget mutation cannot hide behind the shared field roster.
    tampered_widget = copy.deepcopy(post_ui)
    tampered_widget["nodes"][0]["widgets_values"][1] = 0.9
    tampered = from_ui(tampered_widget, use_comfy_converter=False)
    assert diff(replayed.workflow, tampered)

    # Link endpoints are part of the frozen identity domain too. Changing an
    # endpoint cannot be laundered as an unchanged link-id or widget edit.
    linked = {
        "nodes": [
            {
                "id": 1,
                "type": "ContextSource",
                "inputs": [],
                "outputs": [{"name": "context", "links": [4], "slot_index": 0}],
                "widgets_values": [],
                "properties": {"vibecomfy_uid": "1"},
            },
            {
                "id": 3,
                "type": "llama_cpp_parameters",
                "inputs": [{"name": "context", "link": 4}],
                "outputs": [],
                "widgets_values": [1024, 0.8],
                "properties": {"vibecomfy_uid": "3"},
            },
        ],
        "links": [[4, 1, 0, 3, 0, "CONTEXT"]],
    }
    linked_tamper = copy.deepcopy(linked)
    linked_tamper["links"][0][1] = 99
    linked_tamper_wf = from_ui(linked_tamper, use_comfy_converter=False)
    linked_wf = from_ui(linked, use_comfy_converter=False)
    assert diff(linked_wf, linked_tamper_wf)

    # A changed delta value is a different operation, even though its target
    # identity is the same.
    altered = parse_edit_delta(
        [{"op": "set_node_field", "target": ["", "3", "max_tokens"], "value": 513}]
    )
    assert diff(replayed.workflow, interpret(pre, altered).workflow)

    # Removing the frozen pre-state witness must not silently fall back to a
    # fresh ambient roster; the carrier mismatch remains visible as residuals.
    unwitnessed = copy.deepcopy(pre)
    unwitnessed.metadata.pop("_workflow_snapshot", None)
    assert diff(unwitnessed, tampered)


def test_carrier_witness_rejects_value_order_and_duplicate_ambiguity() -> None:
    api = json.loads((_FIXTURES / "llama_api_pre.json").read_text(encoding="utf-8"))

    value_tamper = copy.deepcopy(api)
    value_tamper["3"]["_widget_order_witness"]["values"][0] = 999
    value_wf = from_envelope(from_api(value_tamper).to_envelope())
    assert frozen_widget_names_by_uid(value_wf)["3"] == ()

    order_tamper = copy.deepcopy(api)
    order_tamper["3"]["_widget_order_witness"]["names"] = [
        "temperature",
        "max_tokens",
    ]
    order_wf = from_envelope(from_api(order_tamper).to_envelope())
    assert frozen_widget_names_by_uid(order_wf)["3"] == ()

    duplicate = copy.deepcopy(api)
    duplicate["3"]["_widget_order_witness"]["names"] = [
        "max_tokens",
        "max_tokens",
    ]
    duplicate_wf = from_envelope(from_api(duplicate).to_envelope())
    assert frozen_widget_names_by_uid(duplicate_wf)["3"] == ()
