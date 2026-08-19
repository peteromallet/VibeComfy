from __future__ import annotations

from types import SimpleNamespace

from vibecomfy.comfy_nodes.agent.diagnostics import queue_stage_result
from vibecomfy.comfy_nodes.agent.edit import _recovery_report_from_ui_payload
from vibecomfy.executor.contracts import TopologyFindings
from vibecomfy.executor.revision_evidence import _has_new_topology_blockers


class _Provider:
    def get_schema(self, class_type: str):
        if class_type == "KSampler":
            return SimpleNamespace(
                class_type=class_type,
                source_provider="fixture",
                confidence=1.0,
            )
        return None


def _node(
    node_id: int,
    class_type: str,
    uid: str,
    widgets: list[object],
    *,
    output_name: str = "IMAGE",
) -> dict[str, object]:
    return {
        "id": node_id,
        "type": class_type,
        "properties": {"vibecomfy_uid": uid},
        "inputs": [],
        "outputs": [
            {
                "name": output_name,
                "type": "IMAGE",
                "slot_index": 0,
                "links": None,
            }
        ],
        "widgets_values": widgets,
    }


def _linked_input(name: str, type_name: str, link_id: int | None) -> dict[str, object]:
    return {"name": name, "type": type_name, "link": link_id}


def test_inpaint_seed_edit_with_two_preexisting_unknown_classes_queues() -> None:
    original = {
        "nodes": [
            {
                **_node(
                    18,
                    "INPAINT_InpaintWithModel",
                    "inpaint",
                    [534667941392889, "fixed"],
                ),
                "inputs": [
                    _linked_input("inpaint_model", "INPAINT_MODEL", 1),
                    _linked_input("image", "IMAGE", 2),
                    _linked_input("mask", "MASK", 3),
                    _linked_input("optional_upscale_model", "UPSCALE_MODEL", None),
                ],
            },
            _node(19, "ExistingUnknownAux", "aux", ["fixed"]),
            _node(20, "KSampler", "model-source", []),
            _node(21, "KSampler", "image-source", []),
            _node(22, "KSampler", "mask-source", []),
        ],
        "links": [
            [1, 20, 0, 18, 0, "INPAINT_MODEL"],
            [2, 21, 0, 18, 1, "IMAGE"],
            [3, 22, 0, 18, 2, "MASK"],
        ],
    }
    candidate = {
        "nodes": [
            {
                **_node(118, "INPAINT_InpaintWithModel", "inpaint", [42, "fixed"]),
                "inputs": [
                    _linked_input("image", "IMAGE", 12),
                    _linked_input("inpaint_model", "UNKNOWN", 11),
                    _linked_input("mask", "MASK", 13),
                ],
            },
            _node(119, "ExistingUnknownAux", "aux", ["fixed"]),
            _node(120, "KSampler", "model-source", []),
            _node(121, "KSampler", "image-source", []),
            _node(122, "KSampler", "mask-source", []),
        ],
        "links": [
            [11, 120, 0, 118, 1, "UNKNOWN"],
            [12, 121, 0, 118, 0, "IMAGE"],
            [13, 122, 0, 118, 2, "MASK"],
        ],
    }

    recovery = _recovery_report_from_ui_payload(
        candidate,
        _Provider(),
        original_ui_payload=original,
    )
    queue_result = queue_stage_result(recovery_report=recovery)

    assert queue_result.value["failure_kind"] is None
    assert queue_result.gate_updates["queue_validate_ok"] is True
    assert candidate["nodes"][0]["widgets_values"][0] == 42
    assert all(issue["severity"] == "warning" for issue in queue_result.issues)


def test_acn_strength_edit_drops_only_unlinked_optional_inputs_and_queues() -> None:
    linked_names = ["positive", "negative", "control_net", "image", "vae_optional"]
    optional_names = [
        "mask_optional",
        "timestep_kf",
        "latent_kf_override",
        "weights_override",
        "model_optional",
    ]
    original_inputs = [
        _linked_input(name, name.upper(), index + 1)
        for index, name in enumerate(linked_names)
    ] + [_linked_input(name, name.upper(), None) for name in optional_names]
    candidate_order = ["control_net", "image", "negative", "positive", "vae_optional"]
    candidate_inputs = [
        _linked_input(name, "UNKNOWN" if name == "control_net" else name.upper(), 11 + linked_names.index(name))
        for name in candidate_order
    ]
    original = {
        "nodes": [
            {**_node(60, "ACN_AdvancedControlNetApply", "acn", [0.6, 0, 0.75]), "inputs": original_inputs},
            *[_node(70 + index, "KSampler", f"source-{index}", []) for index in range(5)],
        ],
        "links": [
            [index + 1, 70 + index, 0, 60, index, linked_names[index].upper()]
            for index in range(5)
        ],
    }
    candidate = {
        "nodes": [
            {**_node(160, "ACN_AdvancedControlNetApply", "acn", [0.5, 0, 0.75]), "inputs": candidate_inputs},
            *[_node(170 + index, "KSampler", f"source-{index}", []) for index in range(5)],
        ],
        "links": [
            [11 + index, 170 + index, 0, 160, candidate_order.index(linked_names[index]), linked_names[index].upper()]
            for index in range(5)
        ],
    }

    recovery = _recovery_report_from_ui_payload(
        candidate,
        _Provider(),
        original_ui_payload=original,
    )
    queue_result = queue_stage_result(recovery_report=recovery)
    acn_entry = next(entry for entry in recovery if entry["stable_uid"] == "acn")

    assert acn_entry["schema_less_queue_safe"] is True
    assert acn_entry["schema_less_safety"] == "preexisting_schema_less_widget_values_changed"
    assert queue_result.gate_updates["queue_validate_ok"] is True
    assert candidate["nodes"][0]["widgets_values"][0] == 0.5
    assert all(issue["severity"] == "warning" for issue in queue_result.issues)


def test_dual_ksampler_steps_persist_with_one_preexisting_unknown_class() -> None:
    original = {
        "nodes": [
            _node(57, "KSampler", "sampler-a", [20]),
            _node(58, "KSampler", "sampler-b", [20]),
            _node(59, "ExistingUnknown", "unknown", ["kept"]),
        ],
        "links": [],
    }
    candidate = {
        "nodes": [
            _node(157, "KSampler", "sampler-a", [25]),
            _node(158, "KSampler", "sampler-b", [25]),
            _node(159, "ExistingUnknown", "unknown", ["kept"]),
        ],
        "links": [],
    }

    recovery = _recovery_report_from_ui_payload(
        candidate,
        _Provider(),
        original_ui_payload=original,
    )
    queue_result = queue_stage_result(recovery_report=recovery)

    assert queue_result.gate_updates["queue_validate_ok"] is True
    assert [node["widgets_values"][0] for node in candidate["nodes"][:2]] == [25, 25]


def test_unknown_class_identity_ignores_node_id_but_new_class_still_blocks() -> None:
    original = TopologyFindings(unknown_class_types=("node_id=1: ExistingUnknown",))
    reminted = TopologyFindings(unknown_class_types=("node_id=99: ExistingUnknown",))
    added = TopologyFindings(
        unknown_class_types=(
            "node_id=99: ExistingUnknown",
            "node_id=100: NewlyAddedUnknown",
        )
    )

    assert _has_new_topology_blockers(reminted, original) is False
    assert _has_new_topology_blockers(added, original) is True


def test_preexisting_unknown_slot_name_change_remains_a_hard_block() -> None:
    original = {
        "nodes": [_node(7, "ExistingUnknown", "unknown", [1], output_name="IMAGE")],
        "links": [],
    }
    candidate = {
        "nodes": [_node(70, "ExistingUnknown", "unknown", [1], output_name="RENAMED")],
        "links": [],
    }

    recovery = _recovery_report_from_ui_payload(
        candidate,
        _Provider(),
        original_ui_payload=original,
    )
    queue_result = queue_stage_result(recovery_report=recovery)

    assert queue_result.gate_updates["queue_validate_ok"] is False
    assert any(issue["code"] == "schema_less_queue_blocker" for issue in queue_result.issues)


def test_preexisting_unknown_added_linked_input_name_remains_a_hard_block() -> None:
    original = {
        "nodes": [
            {**_node(7, "ExistingUnknown", "unknown", [1]), "inputs": []},
            _node(8, "KSampler", "source", []),
        ],
        "links": [],
    }
    candidate = {
        "nodes": [
            {
                **_node(70, "ExistingUnknown", "unknown", [1]),
                "inputs": [_linked_input("new_input", "IMAGE", 1)],
            },
            _node(80, "KSampler", "source", []),
        ],
        "links": [[1, 80, 0, 70, 0, "IMAGE"]],
    }

    recovery = _recovery_report_from_ui_payload(
        candidate,
        _Provider(),
        original_ui_payload=original,
    )
    queue_result = queue_stage_result(recovery_report=recovery)

    assert recovery[0]["schema_less_safety"] == "schema_less_inputs_changed"
    assert queue_result.gate_updates["queue_validate_ok"] is False
    assert any(issue["code"] == "schema_less_queue_blocker" for issue in queue_result.issues)
