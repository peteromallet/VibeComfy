"""P6-CORPUS-G1-ORPHAN focused tests.

Sub-fix A (resolution (b) — expose the 13th field): the ``90a1d5`` instance
of ``TripoTextToModelNode`` was saved against a 12-field widget roster while
the authoritative schema carries 13 fields (``geometry_quality`` appended at
positional index 12). The instance widget vector is repaired so
``geometry_quality`` is authorable-in-instance, per the frozen snapshot
widget-name table.

Sub-fix B: an input alias / model-stack advertisement must never target an
ORPHAN node — one structurally disconnected from every executed output chain
(no directed path into a consuming terminal). Detection is purely structural
(backward reachability); node mode/bypass state is ignored.
"""

from __future__ import annotations

import json
from pathlib import Path

import pytest

from vibecomfy.executor.graph_facts import GraphFieldTarget, inspect_effective_field
from vibecomfy.executor.graph_inspection import (
    compute_derivations,
    derive_inputs,
    derive_model_stack,
    derive_orphans,
    derive_outputs,
    inspect_graph,
    render_inspect_markdown,
)
from vibecomfy.porting.widgets.schema import effective_widget_names_for_class

REPO = Path(__file__).resolve().parents[1]
CORPUS_90A1D5 = REPO / "external_workflows/corpus/90a1d5ff9044902e.json"
CORPUS_2A31EC = REPO / "external_workflows/corpus/2a31ec45fd22a623.json"


def _load_envelope(path: Path) -> dict:
    return json.loads(path.read_text(encoding="utf-8"))


# ── Sub-fix A: geometry_quality authorable-in-instance ───────────────────────


class TestGeometryQualityAuthorable:
    def test_snapshot_table_has_thirteenth_field_at_index_12(self) -> None:
        names = effective_widget_names_for_class(
            "TripoTextToModelNode", allow_object_info_fallback=True
        )
        assert len(names) == 13
        assert names[12] == "geometry_quality"

    def test_field_settable_on_repaired_instance(self) -> None:
        """The repaired 90a1d5 instance carries a slot at the table's index 12."""
        if not CORPUS_90A1D5.is_file():
            pytest.skip("external_workflows corpus is not vendored in this checkout")
        envelope = _load_envelope(CORPUS_90A1D5)
        fact = inspect_effective_field(
            envelope, GraphFieldTarget(node_id="3", field_name="geometry_quality")
        )
        assert fact.widget_index == 12
        assert fact.raw_value_known is True
        assert fact.raw_value == "standard"

    def test_value_is_a_valid_schema_choice(self) -> None:
        entry = json.loads(
            (REPO / "vibecomfy/porting/cache/object_info/index.json").read_text(
                encoding="utf-8"
            )
        )
        schema_path = REPO / "vibecomfy/porting/cache/object_info" / entry[
            "TripoTextToModelNode"
        ]
        schema = json.loads(schema_path.read_text(encoding="utf-8"))
        node_schema = schema["TripoTextToModelNode"]
        inputs = node_schema.get("input") or node_schema.get("inputs")
        spec = inputs["optional"]["geometry_quality"]
        assert fact_style_options(spec)

    def test_widget_representations_agree_at_index_12(self) -> None:
        if not CORPUS_90A1D5.is_file():
            pytest.skip("external_workflows corpus is not vendored in this checkout")
        envelope = _load_envelope(CORPUS_90A1D5)
        node = envelope["nodes"]["3"]
        ui_values = node["metadata"]["_ui"]["widgets_values"]
        raw = node["raw_widgets"]
        assert len(ui_values) == 13
        assert raw["length"] == 13
        assert len(raw["values"]) == 13
        assert ui_values[12] == raw["values"][12] == node["widgets"]["widget_12"]

    def test_repaired_vector_shape_resolves_through_snapshot_table(self) -> None:
        """Always-run proof of the resolution mechanics the repair enables.

        A TripoTextToModelNode-shaped instance whose widget vector covers the
        snapshot table's 13 names resolves ``geometry_quality`` at index 12,
        while the pre-repair 12-slot vector leaves it unresolvable.
        """
        values = [None] * 12 + ["standard"]
        repaired = {
            "nodes": {
                "3": {
                    "class_type": "TripoTextToModelNode",
                    "widgets_values": values,
                }
            }
        }
        pre_repair = {
            "nodes": {
                "3": {
                    "class_type": "TripoTextToModelNode",
                    "widgets_values": values[:12],
                }
            }
        }
        stale_fact = inspect_effective_field(
            pre_repair, GraphFieldTarget(node_id="3", field_name="geometry_quality")
        )
        assert stale_fact.raw_value_known is False
        fact = inspect_effective_field(
            repaired, GraphFieldTarget(node_id="3", field_name="geometry_quality")
        )
        assert fact.widget_index == 12
        assert fact.raw_value_known is True
        assert fact.raw_value == "standard"

    def test_real_corpus_instance_if_present(self) -> None:
        if not CORPUS_90A1D5.is_file():
            pytest.skip("external_workflows corpus is not vendored in this checkout")
        envelope = _load_envelope(CORPUS_90A1D5)
        fact = inspect_effective_field(
            envelope, GraphFieldTarget(node_id="3", field_name="geometry_quality")
        )
        assert fact.widget_index == 12
        assert fact.raw_value_known is True

    def test_pre_existing_slots_unchanged_by_repair(self) -> None:
        """The repair appends; the original 12 slots keep their values."""
        if not CORPUS_90A1D5.is_file():
            pytest.skip("external_workflows corpus is not vendored in this checkout")
        envelope = _load_envelope(CORPUS_90A1D5)
        values = envelope["nodes"]["3"]["metadata"]["_ui"]["widgets_values"]
        assert values[:12] == [
            "Generate a 3D model of a steampunk-inspired spider drone with brass "
            "legs, steam vents, and a camera eye, set in a crouched, ready-to-leap "
            "posture.\n",
            "",
            "v2.5-20250123",
            "None",
            True,
            True,
            42,
            42,
            42,
            "detailed",
            -1,
            False,
        ]


def fact_style_options(spec: list) -> bool:
    """The COMBO spec's second element carries the allowed choices."""
    options = spec[1]["options"] if isinstance(spec, list) and len(spec) > 1 else []
    return "standard" in options and "detailed" in options


# ── Sub-fix B: orphan alias not advertised ───────────────────────────────────


def _leg11_shaped_graph() -> dict:
    """Edge-less UNETLoader 8 beside a live LoadAudio → Generate → Save chain."""
    return {
        "nodes": [
            {"id": 2, "type": "LoadAudio", "class_type": "LoadAudio"},
            {
                "id": 3,
                "type": "AceStepSFTGenerate",
                "class_type": "AceStepSFTGenerate",
                "inputs": [{"name": "reference_audio", "type": "AUDIO", "link": 1}],
            },
            {
                "id": 4,
                "type": "SaveAudio",
                "class_type": "SaveAudio",
                "inputs": [{"name": "audio", "type": "AUDIO", "link": 2}],
            },
            {"id": 8, "type": "UNETLoader", "class_type": "UNETLoader"},
        ],
        "links": [
            [1, 2, 0, 3, 0, "AUDIO"],
            [2, 3, 0, 4, 0, "AUDIO"],
        ],
    }


class TestOrphanAliasNotAdvertised:
    def test_orphan_detection_is_structural_reachability(self) -> None:
        evidence = inspect_graph(_leg11_shaped_graph())
        assert derive_orphans(evidence) == (8,)

    def test_orphan_excluded_from_inputs_and_model_stack(self) -> None:
        evidence = inspect_graph(_leg11_shaped_graph())
        assert 8 not in derive_inputs(evidence)
        assert 8 not in derive_model_stack(evidence)
        derivations = compute_derivations(evidence)
        assert 8 not in derivations.inputs
        assert 8 not in derivations.model_stack

    def test_orphan_excluded_from_outputs_and_rendered_evidence(self) -> None:
        evidence = inspect_graph(_leg11_shaped_graph())
        assert 8 not in derive_outputs(evidence)
        markdown = render_inspect_markdown(evidence)
        advertised = markdown.split("## Model Stack")[1].split("## Key Nodes")[0]
        inputs_outputs = markdown.split("## Inputs / Outputs")[1].split(
            "## Dormant Branches"
        )[0]
        assert "[8] UNETLoader" not in advertised
        assert "[8] UNETLoader" not in inputs_outputs

    def test_connected_checkpoint_loader_still_advertised(self) -> None:
        graph = _leg11_shaped_graph()
        graph["nodes"].append(
            {
                "id": 9,
                "type": "CheckpointLoaderSimple",
                "class_type": "CheckpointLoaderSimple",
            }
        )
        graph["nodes"][1]["inputs"].append(
            {"name": "unet", "type": "MODEL", "link": 3}
        )
        graph["links"].append([3, 9, 0, 3, 1, "MODEL"])
        evidence = inspect_graph(graph)
        assert derive_orphans(evidence) == (8,)
        assert 9 in derive_inputs(evidence)
        assert set(derive_model_stack(evidence)) == {9, 3, 4}

    def test_rule_ignores_bypass_mode_state(self) -> None:
        """Structural only: a mode=4 (bypassed) node that feeds the chain stays."""
        graph = _leg11_shaped_graph()
        graph["nodes"].append(
            {
                "id": 5,
                "type": "AceStepSFTLoraLoader",
                "class_type": "AceStepSFTLoraLoader",
                "mode": 4,
            }
        )
        graph["nodes"][1]["inputs"].append(
            {"name": "lora", "type": "ACESTEP_LORA", "link": 4}
        )
        graph["links"].append([4, 5, 0, 3, 1, "ACESTEP_LORA"])
        evidence = inspect_graph(graph)
        assert derive_orphans(evidence) == (8,)
        assert 5 in derive_inputs(evidence)

    def test_isolated_node_is_orphan_regardless_of_class(self) -> None:
        graph = {
            "nodes": [
                {"id": 1, "type": "LoadImage", "class_type": "LoadImage"},
                {
                    "id": 2,
                    "type": "SaveImage",
                    "class_type": "SaveImage",
                    "inputs": [{"name": "images", "type": "IMAGE", "link": 1}],
                },
                {"id": 99, "type": "CheckpointLoaderSimple", "class_type": "CheckpointLoaderSimple"},
            ],
            "links": [[1, 1, 0, 2, 0, "IMAGE"]],
        }
        evidence = inspect_graph(graph)
        assert derive_orphans(evidence) == (99,)
        assert 99 not in derive_inputs(evidence)
        assert derive_model_stack(evidence) == ()

    def test_no_output_chain_keeps_every_node(self) -> None:
        """No consuming terminal anywhere → nothing is provably orphaned."""
        graph = {
            "nodes": [
                {"id": 1, "type": "KSampler", "class_type": "KSampler"},
                {"id": 2, "type": "CheckpointLoaderSimple", "class_type": "CheckpointLoaderSimple"},
            ],
        }
        evidence = inspect_graph(graph)
        assert derive_orphans(evidence) == ()
        assert set(derive_inputs(evidence)) == {1, 2}
        assert set(derive_model_stack(evidence)) == {2}

    def test_leg11_corpus_unetloader_is_orphan_if_present(self) -> None:
        """The actual leg-11 workflow: inputs.model targeted edge-less node 8."""
        if not CORPUS_2A31EC.is_file():
            pytest.skip("external_workflows corpus is not vendored in this checkout")
        envelope = _load_envelope(CORPUS_2A31EC)
        declared_model_node = str(envelope["inputs"]["model"]["node_id"])
        evidence = inspect_graph(envelope)
        orphan_ids = {str(nid) for nid in derive_orphans(evidence)}
        input_ids = {str(nid) for nid in derive_inputs(evidence)}
        stack_ids = {str(nid) for nid in derive_model_stack(evidence)}
        assert declared_model_node in orphan_ids
        assert declared_model_node not in input_ids
        assert declared_model_node not in stack_ids
