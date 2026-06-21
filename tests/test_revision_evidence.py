"""Unit tests for topology evidence helpers in revision_evidence.py.

Covers every required broken-graph and schema-fallback case using tiny graph
fixtures and fake schema data only — no provider/LLM calls, no network.
"""

from __future__ import annotations

import copy
from unittest import mock

import pytest

from vibecomfy.executor.contracts import TopologyFindings, ReadinessReport
from vibecomfy.executor import revision_evidence


class _Spec:
    def __init__(self, typ: str, *, choices: list[str] | None = None) -> None:
        self.type = typ
        self.choices = choices


class _Schema:
    def __init__(self, inputs: dict[str, _Spec]) -> None:
        self.inputs = inputs


class _SchemaProvider:
    def __init__(self, schemas: dict[str, _Schema]) -> None:
        self._schemas = schemas

    def get_schema(self, class_type: str) -> _Schema | None:
        return self._schemas.get(class_type)

# ── tiny graph fixtures ──────────────────────────────────────────────────────


def _empty_graph() -> dict:
    return {"nodes": [], "links": []}


def _one_node_graph(node_id: int = 1, class_type: str = "KSampler") -> dict:
    return {"nodes": [{"id": node_id, "type": class_type}], "links": []}


def _two_node_graph() -> dict:
    return {
        "nodes": [
            {"id": 1, "type": "CheckpointLoaderSimple"},
            {"id": 2, "type": "KSampler"},
        ],
        "links": [
            [1, 1, 0, 2, 0, "MODEL"],
        ],
    }


def _dangling_link_graph() -> dict:
    """Link references a target node id (99) that does not exist."""
    return {
        "nodes": [
            {"id": 1, "type": "CheckpointLoaderSimple"},
            {"id": 2, "type": "KSampler"},
        ],
        "links": [
            [1, 1, 0, 99, 0, "MODEL"],  # target 99 is absent
        ],
    }


def _missing_link_id_graph() -> dict:
    return {
        "nodes": [
            {"id": 1, "type": "CheckpointLoaderSimple"},
            {"id": 2, "type": "KSampler"},
        ],
        "links": [
            [None, 1, 0, 2, 0, "MODEL"],
            {"origin_id": 1, "origin_slot": 0, "target_id": 2, "target_slot": 1, "type": "MODEL"},
        ],
    }


def _missing_both_endpoints_graph() -> dict:
    """Link references both origin 88 and target 99 — neither exists."""
    return {
        "nodes": [{"id": 1, "type": "KSampler"}],
        "links": [
            [1, 88, 0, 99, 0, "MODEL"],
        ],
    }


def _dict_link_graph() -> dict:
    """Dict-shaped links (named fields instead of positional list)."""
    return {
        "nodes": [
            {"id": 10, "type": "VAELoader"},
            {"id": 20, "type": "VAEDecode"},
        ],
        "links": [
            {"id": 1, "origin_id": 10, "origin_slot": 0,
             "target_id": 20, "target_slot": 0, "type": "VAE"},
        ],
    }


def _dict_link_dangling_graph() -> dict:
    """Dict-shaped link with missing target."""
    return {
        "nodes": [
            {"id": 10, "type": "VAELoader"},
        ],
        "links": [
            {"id": 1, "origin_id": 10, "origin_slot": 0,
             "target_id": 999, "target_slot": 0, "type": "VAE"},
        ],
    }


def _graph_with_unknown_class() -> dict:
    return {
        "nodes": [
            {"id": 1, "type": "KSampler"},
            {"id": 2, "type": "TotallyFakeNodeXYZ"},
        ],
        "links": [],
    }


def _graph_with_missing_required_inputs() -> dict:
    """A KSampler node with required inputs that have no link or widget value."""
    return {
        "nodes": [
            {
                "id": 1,
                "type": "KSampler",
                "inputs": [
                    {"name": "model", "link": None},      # required, no link, no widget
                    {"name": "positive", "link": None},    # required, no link, no widget
                    {"name": "negative", "link": None},    # required, no link, no widget
                    {"name": "latent_image", "link": None}, # required, no link, no widget
                    {"name": "seed", "widget": 42},         # required, has widget
                    {"name": "steps", "widget": 20},        # required, has widget
                    {"name": "cfg", "widget": 7.0},         # required, has widget
                    {"name": "sampler_name", "widget": "euler"},  # required, has widget
                    {"name": "scheduler", "widget": "normal"},    # required, has widget
                    {"name": "denoise", "widget": 1.0},     # required, has widget
                ],
            },
        ],
        "links": [],
    }


def _graph_with_linked_inputs() -> dict:
    """A KSampler node with required inputs linked."""
    return {
        "nodes": [
            {
                "id": 1,
                "type": "CheckpointLoaderSimple",
                "inputs": [
                    {"name": "ckpt_name", "widget": "sd_xl_base.safetensors"},
                ],
            },
            {
                "id": 2,
                "type": "KSampler",
                "inputs": [
                    {"name": "model", "link": 1},
                    {"name": "positive", "link": 3},
                    {"name": "negative", "link": 4},
                    {"name": "latent_image", "link": 5},
                    {"name": "seed", "widget": 42},
                    {"name": "steps", "widget": 20},
                    {"name": "cfg", "widget": 7.0},
                    {"name": "sampler_name", "widget": "euler"},
                    {"name": "scheduler", "widget": "normal"},
                    {"name": "denoise", "widget": 1.0},
                ],
            },
        ],
        "links": [
            [1, 1, 0, 2, 0, "MODEL"],
            [2, 3, 0, 2, 1, "CONDITIONING"],
            [3, 4, 0, 2, 2, "CONDITIONING"],
            [4, 5, 0, 2, 3, "LATENT"],
        ],
    }


# ── collect_topology_evidence tests ───────────────────────────────────────────


class TestCollectTopologyEvidence:
    """Tests for collect_topology_evidence covering all broken-graph cases."""

    def test_none_graph_returns_missing_graph(self) -> None:
        result = revision_evidence.collect_topology_evidence(None)
        assert result.missing_graph is True
        assert result.summary == "No graph attached."
        assert result.has_blockers is True
        assert result.dangling_links == ()
        assert result.absent_endpoint_nodes == ()

    def test_empty_dict_returns_missing_graph(self) -> None:
        result = revision_evidence.collect_topology_evidence({})
        assert result.missing_graph is True
        assert "no nodes" in result.summary.lower()

    def test_empty_nodes_returns_missing_graph(self) -> None:
        result = revision_evidence.collect_topology_evidence(_empty_graph())
        assert result.missing_graph is True
        assert "no nodes" in result.summary.lower()

    def test_non_dict_graph_returns_missing(self) -> None:
        result = revision_evidence.collect_topology_evidence("not-a-dict")  # type: ignore[arg-type]
        assert result.missing_graph is True

    def test_clean_graph_no_topology_issues(self) -> None:
        result = revision_evidence.collect_topology_evidence(_two_node_graph())
        assert result.missing_graph is False
        assert result.dangling_links == ()
        assert result.absent_endpoint_nodes == ()
        assert "no topology issues detected" in result.summary
        assert result.has_blockers is False

    def test_dangling_link_detected(self) -> None:
        result = revision_evidence.collect_topology_evidence(_dangling_link_graph())
        assert result.missing_graph is False
        assert len(result.dangling_links) == 1
        assert "link_id=1" in result.dangling_links[0]
        assert "target=99" in result.dangling_links[0]
        assert "missing target endpoint" in result.dangling_links[0]
        assert "99" in result.absent_endpoint_nodes
        assert result.has_blockers is True

    def test_missing_link_ids_detected(self) -> None:
        result = revision_evidence.collect_topology_evidence(_missing_link_id_graph())
        assert len(result.dangling_links) == 2
        assert "link_index=0: missing link id" in result.dangling_links
        assert "link_index=1: missing link id" in result.dangling_links
        assert result.has_blockers is True

    def test_missing_both_endpoints(self) -> None:
        result = revision_evidence.collect_topology_evidence(
            _missing_both_endpoints_graph()
        )
        assert len(result.dangling_links) == 1
        assert "missing source" in result.dangling_links[0]
        assert "target" in result.dangling_links[0]
        assert "88" in result.absent_endpoint_nodes
        assert "99" in result.absent_endpoint_nodes
        assert len(result.absent_endpoint_nodes) == 2

    def test_dict_link_clean(self) -> None:
        """Dict-shaped links that are well-formed produce no issues."""
        result = revision_evidence.collect_topology_evidence(_dict_link_graph())
        assert result.dangling_links == ()
        assert result.absent_endpoint_nodes == ()
        assert result.has_blockers is False

    def test_dict_link_dangling(self) -> None:
        result = revision_evidence.collect_topology_evidence(
            _dict_link_dangling_graph()
        )
        assert len(result.dangling_links) == 1
        assert "target=999" in result.dangling_links[0]
        assert "missing target endpoint" in result.dangling_links[0]
        assert "999" in result.absent_endpoint_nodes

    def test_unknown_class_types_schema_available(self) -> None:
        """With schema_available=True, unknown class types are flagged."""
        # Mock class_is_known to return False for the fake node.
        with mock.patch(
            "vibecomfy.executor.revision_evidence.class_is_known",
            side_effect=lambda ct: ct != "TotallyFakeNodeXYZ",
        ):
            result = revision_evidence.collect_topology_evidence(
                _graph_with_unknown_class(), schema_available=True,
            )
        assert len(result.unknown_class_types) == 1
        assert "TotallyFakeNodeXYZ" in result.unknown_class_types[0]
        assert result.has_blockers is True

    def test_unknown_class_types_schema_unavailable(self) -> None:
        """With schema_available=False, unknown class types are NOT checked."""
        result = revision_evidence.collect_topology_evidence(
            _graph_with_unknown_class(), schema_available=False,
        )
        result_dict = result.to_dict()
        assert result_dict["unknown_class_types"] == []
        assert result.schema_available is False
        assert "(schema unavailable" in result.summary.lower()

    def test_missing_required_inputs_schema_available(self) -> None:
        """With schema_available=True, nodes missing required inputs are flagged."""
        # KSampler has known required inputs: model, positive, negative, latent_image
        # These have no link and no widget_value in the fixture.
        # Mock _input_is_required to return True for the four known required inputs.
        with mock.patch(
            "vibecomfy.executor.revision_evidence._input_is_required",
            side_effect=lambda ct, inp: (
                ct == "KSampler"
                and inp in ("model", "positive", "negative", "latent_image")
            ),
        ):
            result = revision_evidence.collect_topology_evidence(
                _graph_with_missing_required_inputs(), schema_available=True,
            )
        assert len(result.missing_required_inputs) == 4
        missing_names = {item["input_name"] for item in result.missing_required_inputs}
        assert missing_names == {"model", "positive", "negative", "latent_image"}
        assert result.has_blockers is True

    def test_missing_required_inputs_schema_unavailable(self) -> None:
        """With schema_available=False, required input checks are skipped."""
        result = revision_evidence.collect_topology_evidence(
            _graph_with_missing_required_inputs(), schema_available=False,
        )
        assert len(result.missing_required_inputs) == 0
        assert result.schema_available is False

    def test_linked_inputs_not_missing(self) -> None:
        """Nodes with linked required inputs are not flagged as missing."""
        with mock.patch(
            "vibecomfy.executor.revision_evidence._input_is_required",
            side_effect=lambda ct, inp: (
                ct == "KSampler"
                and inp in ("model", "positive", "negative", "latent_image")
            ),
        ):
            result = revision_evidence.collect_topology_evidence(
                _graph_with_linked_inputs(), schema_available=True,
            )
        # All four required inputs have links → no missing required inputs.
        assert len(result.missing_required_inputs) == 0

    def test_no_class_type_node_flagged(self) -> None:
        """Node with no class_type and no type field gets 'Unknown' and flagged."""
        graph = {
            "nodes": [{"id": 1}],
            "links": [],
        }
        with mock.patch(
            "vibecomfy.executor.revision_evidence.class_is_known",
            return_value=False,
        ):
            result = revision_evidence.collect_topology_evidence(
                graph, schema_available=True,
            )
        assert len(result.unknown_class_types) == 1
        assert "no class_type" in result.unknown_class_types[0].lower()

    def test_to_dict_roundtrip(self) -> None:
        """to_dict() on TopologyFindings produces valid serializable output."""
        result = revision_evidence.collect_topology_evidence(
            _dangling_link_graph(), schema_available=False,
        )
        d = result.to_dict()
        assert isinstance(d, dict)
        assert d["missing_graph"] is False
        assert isinstance(d["dangling_links"], list)
        assert isinstance(d["absent_endpoint_nodes"], list)
        assert d["schema_available"] is False
        assert d["has_blockers"] is True
        assert "summary" in d


# ── collect_readiness_evidence tests ──────────────────────────────────────────


class TestCollectReadinessEvidence:
    """Tests for collect_readiness_evidence."""

    def test_none_graph_returns_clean_report(self) -> None:
        result = revision_evidence.collect_readiness_evidence(None)
        assert isinstance(result, ReadinessReport)
        assert result.missing_models == ()
        assert result.missing_node_packs == ()
        assert result.has_blockers is False
        assert "No graph to assess" in result.summary

    def test_precomputed_blockers_passthrough(self) -> None:
        result = revision_evidence.collect_readiness_evidence(
            _empty_graph(),
            missing_models=("sd_xl.safetensors",),
            missing_node_packs=("ComfyUI-MissingPack",),
            validation_errors=("missing required node",),
            no_gpu_detected=True,
            readiness_blockers=("explicit blocker",),
        )
        assert "sd_xl.safetensors" in result.missing_models
        assert "ComfyUI-MissingPack" in result.missing_node_packs
        assert len(result.validation_errors) == 1
        assert result.no_gpu_detected is True
        assert "explicit blocker" in result.readiness_blockers
        assert result.has_blockers is True

    def test_graph_with_known_classes_no_issues(self) -> None:
        with mock.patch(
            "vibecomfy.executor.revision_evidence.class_is_known",
            return_value=True,
        ):
            result = revision_evidence.collect_readiness_evidence(
                _two_node_graph(), object_info_available=True,
            )
        assert result.missing_node_packs == ()
        assert result.has_blockers is False

    def test_graph_with_unknown_classes(self) -> None:
        with mock.patch(
            "vibecomfy.executor.revision_evidence.class_is_known",
            side_effect=lambda ct: ct != "TotallyFakeNodeXYZ",
        ):
            result = revision_evidence.collect_readiness_evidence(
                _graph_with_unknown_class(), object_info_available=True,
            )
        assert len(result.missing_node_packs) == 1
        assert "TotallyFakeNodeXYZ" in result.missing_node_packs[0]
        assert result.has_blockers is True

    def test_object_info_model_choice_detects_missing_model(self) -> None:
        provider = _SchemaProvider(
            {
                "CheckpointLoaderSimple": _Schema(
                    {"ckpt_name": _Spec("CHOICE", choices=["present.safetensors"])}
                )
            }
        )
        graph = {
            "nodes": [
                {
                    "id": 1,
                    "type": "CheckpointLoaderSimple",
                    "widgets_values": ["missing.safetensors"],
                }
            ],
            "links": [],
        }

        result = revision_evidence.collect_readiness_evidence(
            graph,
            object_info_available=True,
            schema_provider=provider,
        )

        assert result.missing_models == ("missing.safetensors",)
        assert result.has_blockers is True

    def test_ready_metadata_and_diagnostics_fallbacks_report_missing_assets(self) -> None:
        result = revision_evidence.collect_readiness_evidence(
            _two_node_graph(),
            object_info_available=False,
            ready_metadata={
                "requirements": {
                    "models": [{"name": "wan.safetensors", "available": False}],
                    "custom_nodes": [{"name": "ComfyUI-WanVideoWrapper", "missing": True}],
                }
            },
            diagnostics=(
                {
                    "code": "missing_model",
                    "severity": "error",
                    "message": "flux.safetensors",
                },
                {
                    "code": "no_gpu_detected",
                    "severity": "error",
                    "message": "No GPU detected.",
                },
            ),
        )

        assert result.object_info_available is False
        assert set(result.missing_models) == {"wan.safetensors", "flux.safetensors"}
        assert result.missing_node_packs == ("ComfyUI-WanVideoWrapper",)
        assert result.no_gpu_detected is True
        assert result.has_blockers is True

    def test_object_info_unavailable_degrade(self) -> None:
        """When object_info is unavailable, readiness degrades gracefully."""
        result = revision_evidence.collect_readiness_evidence(
            _graph_with_unknown_class(), object_info_available=False,
        )
        assert result.missing_node_packs == ()
        assert result.has_blockers is False

    def test_to_dict(self) -> None:
        result = revision_evidence.collect_readiness_evidence(
            _empty_graph(),
            missing_models=("m1",),
            no_gpu_detected=True,
        )
        d = result.to_dict()
        assert d["missing_models"] == ["m1"]
        assert d["no_gpu_detected"] is True
        assert d["has_blockers"] is True


# ── schema_backed_unknown_class_types tests ───────────────────────────────────


class TestSchemaBackedUnknownClassTypes:
    """Tests for schema_backed_unknown_class_types convenience wrapper."""

    def test_none_graph_returns_empty(self) -> None:
        result = revision_evidence.schema_backed_unknown_class_types(None)
        assert result == ()

    def test_empty_graph_returns_empty(self) -> None:
        result = revision_evidence.schema_backed_unknown_class_types(_empty_graph())
        assert result == ()

    def test_all_known_returns_empty(self) -> None:
        with mock.patch(
            "vibecomfy.executor.revision_evidence.class_is_known",
            return_value=True,
        ):
            result = revision_evidence.schema_backed_unknown_class_types(
                _two_node_graph()
            )
        assert result == ()

    def test_unknown_class_returned(self) -> None:
        with mock.patch(
            "vibecomfy.executor.revision_evidence.class_is_known",
            side_effect=lambda ct: ct != "TotallyFakeNodeXYZ",
        ):
            result = revision_evidence.schema_backed_unknown_class_types(
                _graph_with_unknown_class()
            )
        assert len(result) == 1
        assert "TotallyFakeNodeXYZ" in result[0]


# ── compute_scoped_diff tests ────────────────────────────────────────────────


class TestComputeScopedDiff:
    def test_changed_added_removed_untouched_paths_and_hashes(self) -> None:
        original = {
            "nodes": [
                {"id": 1, "type": "CheckpointLoaderSimple", "widgets_values": ["a.safetensors"]},
                {"id": 2, "type": "KSampler", "widgets_values": [1, 20]},
                {"id": 3, "type": "SaveImage"},
            ],
            "links": [[1, 1, 0, 2, 0, "MODEL"]],
        }
        candidate = copy.deepcopy(original)
        candidate["nodes"][1]["widgets_values"][1] = 30
        candidate["nodes"].pop(2)
        candidate["nodes"].append({"id": 4, "type": "PreviewImage"})
        candidate["links"] = [[2, 1, 0, 4, 0, "IMAGE"]]

        diff = revision_evidence.compute_scoped_diff(
            original,
            candidate,
            topology=TopologyFindings(),
            readiness=ReadinessReport(),
        )

        assert diff.changed_nodes == ("2",)
        assert diff.added_nodes == ("4",)
        assert diff.removed_nodes == ("3",)
        assert diff.untouched_nodes == ("1",)
        assert diff.added_links[0]["link_id"] == 2
        assert diff.removed_links[0]["link_id"] == 1
        assert "nodes.2.widgets_values.1" in diff.diff_paths
        assert "nodes.added.4" in diff.diff_paths
        assert "nodes.removed.3" in diff.diff_paths
        assert "links.added.link:2" in diff.diff_paths
        assert "links.removed.link:1" in diff.diff_paths
        assert len(diff.before_hash) == 64
        assert len(diff.after_hash) == 64
        assert diff.before_hash != diff.after_hash
        assert diff.has_diff is True
        assert diff.candidate_eligible is False
        assert "broad_unrelated_diff" in diff.eligibility_blockers

    def test_small_scoped_change_is_eligible_with_evidence(self) -> None:
        original = _two_node_graph()
        candidate = copy.deepcopy(original)
        candidate["nodes"][1]["widgets_values"] = [123]

        diff = revision_evidence.compute_scoped_diff(
            original,
            candidate,
            topology=TopologyFindings(),
            readiness=ReadinessReport(),
        )

        assert diff.changed_nodes == ("2",)
        assert diff.added_nodes == ()
        assert diff.removed_nodes == ()
        assert diff.untouched_nodes == ("1",)
        assert diff.diff_paths == ("nodes.2.widgets_values",)
        assert diff.candidate_eligible is True
        assert diff.eligibility_blockers == ()

    def test_added_node_inside_scoped_diff_is_eligible_with_evidence(self) -> None:
        original = {
            "nodes": [
                {"id": 1, "type": "CheckpointLoaderSimple"},
                {"id": 2, "type": "KSampler"},
                {"id": 3, "type": "SaveImage"},
            ],
            "links": [],
        }
        candidate = copy.deepcopy(original)
        candidate["nodes"].append({"id": 4, "type": "PreviewImage"})

        diff = revision_evidence.compute_scoped_diff(
            original,
            candidate,
            topology=TopologyFindings(),
            readiness=ReadinessReport(),
        )

        assert diff.added_nodes == ("4",)
        assert diff.removed_nodes == ()
        assert diff.changed_nodes == ()
        assert "nodes.added.4" in diff.diff_paths
        assert diff.candidate_eligible is True
        assert diff.eligibility_blockers == ()

    def test_removed_node_inside_scoped_diff_is_eligible_with_evidence(self) -> None:
        original = {
            "nodes": [
                {"id": 1, "type": "CheckpointLoaderSimple"},
                {"id": 2, "type": "KSampler"},
                {"id": 3, "type": "SaveImage"},
            ],
            "links": [],
        }
        candidate = copy.deepcopy(original)
        candidate["nodes"] = candidate["nodes"][:2]

        diff = revision_evidence.compute_scoped_diff(
            original,
            candidate,
            topology=TopologyFindings(),
            readiness=ReadinessReport(),
        )

        assert diff.removed_nodes == ("3",)
        assert diff.added_nodes == ()
        assert diff.changed_nodes == ()
        assert "nodes.removed.3" in diff.diff_paths
        assert diff.candidate_eligible is True
        assert diff.eligibility_blockers == ()

    def test_added_and_removed_links_are_summarized_and_eligible(self) -> None:
        original = {
            "nodes": [
                {"id": 1, "type": "CheckpointLoaderSimple"},
                {"id": 2, "type": "KSampler"},
                {"id": 3, "type": "SaveImage"},
            ],
            "links": [[1, 1, 0, 2, 0, "MODEL"]],
        }
        candidate = copy.deepcopy(original)
        candidate["links"] = [[2, 2, 0, 3, 0, "IMAGE"]]

        diff = revision_evidence.compute_scoped_diff(
            original,
            candidate,
            topology=TopologyFindings(),
            readiness=ReadinessReport(),
        )

        assert diff.added_links == (
            {
                "link_id": 2,
                "origin_node": 2,
                "origin_slot": 0,
                "target_node": 3,
                "target_slot": 0,
                "type": "IMAGE",
            },
        )
        assert diff.removed_links == (
            {
                "link_id": 1,
                "origin_node": 1,
                "origin_slot": 0,
                "target_node": 2,
                "target_slot": 0,
                "type": "MODEL",
            },
        )
        assert "links.added.link:2" in diff.diff_paths
        assert "links.removed.link:1" in diff.diff_paths
        assert diff.candidate_eligible is True
        assert diff.eligibility_blockers == ()

    def test_no_diff_blocks_candidate(self) -> None:
        graph = _two_node_graph()
        diff = revision_evidence.compute_scoped_diff(
            graph,
            copy.deepcopy(graph),
            topology=TopologyFindings(),
            readiness=ReadinessReport(),
        )
        assert diff.has_diff is False
        assert diff.candidate_eligible is False
        assert "no_diff" in diff.eligibility_blockers

    def test_missing_evidence_blocks_candidate(self) -> None:
        diff = revision_evidence.compute_scoped_diff(
            _two_node_graph(),
            _one_node_graph(3, "PreviewImage"),
        )
        assert diff.candidate_eligible is False
        assert "missing_evidence" in diff.eligibility_blockers

    def test_topology_and_readiness_blockers_disqualify_candidate(self) -> None:
        original = _two_node_graph()
        candidate = copy.deepcopy(original)
        candidate["nodes"][1]["widgets_values"] = [1]

        diff = revision_evidence.compute_scoped_diff(
            original,
            candidate,
            topology=TopologyFindings(dangling_links=("link_id=1",)),
            readiness=ReadinessReport(validation_errors=("bad graph",)),
        )

        assert diff.candidate_eligible is False
        assert "unresolved_topology_blockers" in diff.eligibility_blockers
        assert "unresolved_readiness_blockers" in diff.eligibility_blockers

    def test_schema_unavailable_disqualifies_candidate(self) -> None:
        original = _two_node_graph()
        candidate = copy.deepcopy(original)
        candidate["nodes"][1]["widgets_values"] = [1]

        diff = revision_evidence.compute_scoped_diff(
            original,
            candidate,
            topology=TopologyFindings(schema_available=False),
            readiness=ReadinessReport(),
        )

        assert diff.candidate_eligible is False
        assert "schema_unavailable" in diff.eligibility_blockers

    def test_candidate_introducing_readiness_blocker_is_ineligible(self) -> None:
        original = _two_node_graph()
        candidate = copy.deepcopy(original)
        candidate["nodes"].append({"id": 3, "type": "MissingPackNode"})

        diff = revision_evidence.compute_scoped_diff(
            original,
            candidate,
            topology=TopologyFindings(),
            readiness=ReadinessReport(),
            candidate_readiness=ReadinessReport(missing_node_packs=("MissingPackNode",)),
        )

        assert diff.candidate_eligible is False
        assert "candidate_readiness_blockers" in diff.eligibility_blockers

    def test_target_mismatch_blocks_candidate(self) -> None:
        original = _two_node_graph()
        candidate = copy.deepcopy(original)
        candidate["nodes"][0]["widgets_values"] = ["changed"]

        diff = revision_evidence.compute_scoped_diff(
            original,
            candidate,
            topology=TopologyFindings(),
            readiness=ReadinessReport(),
            target_node_ids=("2",),
        )

        assert diff.target_node_ids == ("2",)
        assert diff.target_matched is False
        assert diff.candidate_eligible is False
        assert "target_mismatch" in diff.eligibility_blockers


# ── edge case: node with non-dict entries ─────────────────────────────────────


class TestEdgeCases:
    """Edge cases for topology evidence helpers."""

    def test_non_dict_nodes_skipped(self) -> None:
        graph = {
            "nodes": [{"id": 1, "type": "KSampler"}, "not-a-dict", 42],
            "links": [],
        }
        result = revision_evidence.collect_topology_evidence(graph)
        assert result.missing_graph is False
        assert result.has_blockers is False

    def test_node_with_string_id(self) -> None:
        graph = {
            "nodes": [
                {"id": "loader-1", "type": "CheckpointLoaderSimple"},
                {"id": "sampler-2", "type": "KSampler"},
            ],
            "links": [
                [1, "loader-1", 0, "sampler-2", 0, "MODEL"],
            ],
        }
        result = revision_evidence.collect_topology_evidence(graph)
        assert result.dangling_links == ()
        assert result.has_blockers is False

    def test_node_without_id_uses_index(self) -> None:
        graph = {
            "nodes": [
                {"type": "KSampler"},  # no id → uses index 0
            ],
            "links": [],
        }
        result = revision_evidence.collect_topology_evidence(graph)
        assert result.missing_graph is False
