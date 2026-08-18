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


def test_inpaint_seed_edit_with_two_preexisting_unknown_classes_queues() -> None:
    original = {
        "nodes": [
            _node(18, "INPAINT_InpaintWithModel", "inpaint", [534667941392889]),
            _node(19, "ExistingUnknownAux", "aux", ["fixed"]),
        ],
        "links": [],
    }
    candidate = {
        "nodes": [
            _node(118, "INPAINT_InpaintWithModel", "inpaint", [42]),
            _node(119, "ExistingUnknownAux", "aux", ["fixed"]),
        ],
        "links": [],
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
