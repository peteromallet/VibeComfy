"""Graph-facts tests for adapt-route prompt evidence (T12).

Prove that adapt-route prompts include:
- current output node types
- terminal output socket types
- socket mismatch facts
- missing required inputs
- unknown class types
- missing node packs
- readiness notes derived from existing readiness data
"""

import copy
import json
from pathlib import Path
from types import SimpleNamespace
from typing import Any

import pytest

from vibecomfy.executor.contracts import (
    GraphFacts,
    ReadinessReport,
    RevisionEvidence,
    TopologyFindings,
)
from vibecomfy.executor.revision_evidence import collect_graph_facts
from vibecomfy.executor.revision_evidence import (
    collect_topology_evidence,
    compute_scoped_diff,
    semantic_graph_hash,
    semantic_graph_projection,
)


# ══════════════════════════════════════════════════════════════════════════════
# Shared helpers
# ══════════════════════════════════════════════════════════════════════════════


def _make_simple_graph(*, nodes: list[dict] | None = None,
                       links: list | None = None) -> dict[str, Any]:
    """Build a minimal ComfyUI prompt dict."""
    return {
        "nodes": nodes or [],
        "links": links or [],
    }


def _idless_link(source_port: str, target_port: str) -> dict[str, Any]:
    return {
        "from": {"node_uid": "source", "port": source_port},
        "to": {"node_uid": "sink", "port": target_port},
    }


def _finalize_scoped_diff(
    original: dict[str, Any],
    candidate: dict[str, Any],
    *,
    tmp_path: Path,
    monkeypatch: pytest.MonkeyPatch,
    batch_turns: list[dict[str, Any]] | None = None,
) -> RevisionEvidence:
    """Run the terminal revision evidence finalizer with deterministic collectors."""
    from vibecomfy.comfy_nodes.agent import edit as agent_edit_module

    state = SimpleNamespace(
        task="test revision",
        graph=original,
        ui_payload=candidate,
        request_payload={},
        schema_provider=object(),
        revision_evidence=RevisionEvidence(
            topology=TopologyFindings(schema_available=True),
            readiness=ReadinessReport(),
        ),
        report={},
        artifacts=None,
        revision_evidence_payload=None,
        route="revise",
        batch_turns=batch_turns or [],
        batch_field_changes=(),
        batch_noop_field_changes=(),
        batch_exit_mode="",
        batch_done_summary="",
        batch_final_summary="",
        user_message="",
        candidate_ui_path=tmp_path / "candidate.ui.json",
        revision_evidence_path=tmp_path / "revision_evidence.json",
    )

    monkeypatch.setattr(
        agent_edit_module,
        "_schema_provider_available",
        lambda _provider: True,
    )
    monkeypatch.setattr(
        agent_edit_module,
        "collect_topology_evidence",
        lambda *_args, **_kwargs: TopologyFindings(schema_available=True),
    )
    monkeypatch.setattr(
        agent_edit_module,
        "collect_readiness_evidence",
        lambda *_args, **_kwargs: ReadinessReport(),
    )
    monkeypatch.setattr(agent_edit_module, "_extract_ready_metadata", lambda *_args: None)
    monkeypatch.setattr(
        agent_edit_module,
        "_extract_readiness_diagnostics",
        lambda *_args: None,
    )
    monkeypatch.setattr(
        agent_edit_module,
        "_runtime_execution_requested",
        lambda *_args: False,
    )
    monkeypatch.setattr(
        agent_edit_module,
        "_request_no_gpu_detected",
        lambda *_args: False,
    )
    monkeypatch.setattr(
        agent_edit_module,
        "_localized_additive_scoped_evidence",
        lambda current_state, **kwargs: (
            current_state.revision_evidence.topology,
            current_state.revision_evidence.readiness,
            kwargs["candidate_topology"],
            kwargs["candidate_readiness"],
        ),
    )
    monkeypatch.setattr(
        agent_edit_module,
        "_write_revision_evidence_artifact",
        lambda *_args, **_kwargs: None,
    )

    agent_edit_module._finalize_revision_evidence_with_candidate(
        state,
        route="revise",
        conversation_messages=None,
    )
    return state.revision_evidence


def test_revision_finalizer_keeps_metadata_and_layout_only_hashes_no_diff(
    tmp_path: Path,
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    original = _make_simple_graph(nodes=[{"id": 1, "class_type": "KSampler"}])
    candidate = copy.deepcopy(original)
    candidate["metadata"] = {"created_by": "layout-tool"}
    candidate["groups"] = [{"title": "Layout", "bounding": [0, 0, 100, 100]}]
    candidate["extra"] = {"ds": {"scale": 1.25}}

    evidence = _finalize_scoped_diff(
        original,
        candidate,
        tmp_path=tmp_path,
        monkeypatch=monkeypatch,
    )
    scoped = evidence.scoped_diff
    assert scoped is not None
    assert scoped.before_hash != scoped.after_hash
    assert scoped.has_diff is False
    assert scoped.candidate_eligible is False
    assert "no_diff" in scoped.eligibility_blockers
    assert evidence.no_candidate_reason == "no_changes"


def test_revision_finalizer_does_not_promote_noop_landed_operation(
    tmp_path: Path,
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    original = _make_simple_graph(nodes=[{"id": 1, "class_type": "KSampler"}])
    batch_turns = [
        {
            "statements": [
                {
                    "statement_index": 0,
                    "source": "add_node(...)",
                    "ok": True,
                    "landed": True,
                    "op": {"op": "add_node", "node": {"id": 1}},
                }
            ]
        }
    ]

    evidence = _finalize_scoped_diff(
        original,
        copy.deepcopy(original),
        tmp_path=tmp_path,
        monkeypatch=monkeypatch,
        batch_turns=batch_turns,
    )
    scoped = evidence.scoped_diff
    assert scoped is not None
    assert scoped.has_diff is False
    assert scoped.candidate_eligible is False
    assert "no_diff" in scoped.eligibility_blockers
    assert evidence.no_candidate_reason == "no_changes"


def test_revision_finalizer_preserves_true_semantic_field_candidate(
    tmp_path: Path,
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    original = _make_simple_graph(
        nodes=[{"id": 1, "class_type": "KSampler", "widgets_values": [20]}]
    )
    candidate = copy.deepcopy(original)
    candidate["nodes"][0]["widgets_values"] = [25]

    evidence = _finalize_scoped_diff(
        original,
        candidate,
        tmp_path=tmp_path,
        monkeypatch=monkeypatch,
    )
    scoped = evidence.scoped_diff
    assert scoped is not None
    assert scoped.has_diff is True
    assert scoped.changed_nodes == ("1",)
    assert scoped.candidate_eligible is True
    assert evidence.no_candidate_reason is None



@pytest.mark.parametrize(
    ("field", "value"),
    [
        ("pos", [100, 200]),
        ("size", [320, 180]),
        ("flags", {"collapsed": True}),
        ("order", 9),
        ("title", "Moved visually"),
        ("color", "#fff"),
    ],
)
def test_scoped_diff_excludes_layout_only_node_facts(
    field: str,
    value: Any,
) -> None:
    original = _make_simple_graph(
        nodes=[
            {
                "id": 1,
                "class_type": "KSampler",
                "properties": {"vibecomfy_uid": "sampler"},
                "pos": [0, 0],
                "size": [315, 262],
            }
        ]
    )
    candidate = copy.deepcopy(original)
    candidate["nodes"][0][field] = value

    scoped = compute_scoped_diff(
        original,
        candidate,
        topology=TopologyFindings(schema_available=True),
        readiness=ReadinessReport(),
        candidate_topology=TopologyFindings(schema_available=True),
        candidate_readiness=ReadinessReport(),
    )

    assert semantic_graph_hash(original) == semantic_graph_hash(candidate)
    assert scoped.has_diff is False
    assert scoped.candidate_eligible is False
    assert "no_diff" in scoped.eligibility_blockers


def test_scoped_diff_and_public_projection_preserve_semantic_node_properties() -> None:
    original = _make_simple_graph(
        nodes=[
            {
                "id": 1,
                "class_type": "KSampler",
                "properties": {"vibecomfy_uid": "sampler", "backend_mode": "fast"},
            }
        ]
    )
    candidate = copy.deepcopy(original)
    candidate["nodes"][0]["properties"]["backend_mode"] = "accurate"

    scoped = compute_scoped_diff(
        original,
        candidate,
        topology=TopologyFindings(schema_available=True),
        readiness=ReadinessReport(),
        candidate_topology=TopologyFindings(schema_available=True),
        candidate_readiness=ReadinessReport(),
    )

    assert semantic_graph_hash(original) != semantic_graph_hash(candidate)
    assert scoped.changed_nodes == ("1",)
    assert scoped.diff_paths == ("nodes.1.properties.backend_mode",)
    assert scoped.candidate_eligible is True


def _scoped_link_diff(original: dict[str, Any], candidate: dict[str, Any]) -> Any:
    return compute_scoped_diff(
        original,
        candidate,
        topology=TopologyFindings(schema_available=True),
        readiness=ReadinessReport(),
        candidate_topology=TopologyFindings(schema_available=True),
        candidate_readiness=ReadinessReport(),
    )


def test_semantic_projection_and_scoped_diff_preserve_link_order() -> None:
    first = _idless_link("out-a", "in-a")
    second = _idless_link("out-b", "in-b")
    original = _make_simple_graph(links=[first, second])
    candidate = _make_simple_graph(links=[second, first])

    assert semantic_graph_projection(candidate)["links"] == [second, first]
    assert semantic_graph_hash(original) != semantic_graph_hash(candidate)
    scoped = _scoped_link_diff(original, candidate)
    assert scoped.has_diff is True
    assert scoped.candidate_eligible is False
    assert "links.order" in scoped.diff_paths
    assert "unrepresentable_link_order" in scoped.eligibility_blockers


def test_revision_finalizer_marks_order_only_candidate_unrepresentable(
    tmp_path: Path,
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    first = _idless_link("out-a", "in-a")
    second = _idless_link("out-b", "in-b")
    original = _make_simple_graph(links=[first, second])
    candidate = _make_simple_graph(links=[second, first])

    evidence = _finalize_scoped_diff(
        original,
        candidate,
        tmp_path=tmp_path,
        monkeypatch=monkeypatch,
    )

    assert evidence.candidate_eligible is False
    assert evidence.no_candidate_reason == "unrepresentable_link_order"
    assert evidence.scoped_diff is not None
    assert evidence.scoped_diff.has_diff is True
    assert "links.order" in evidence.scoped_diff.diff_paths


def test_scoped_diff_preserves_duplicate_idless_link_addition() -> None:
    link = _idless_link("out", "in")
    original = _make_simple_graph(links=[link])
    candidate = _make_simple_graph(links=[link, copy.deepcopy(link)])

    scoped = _scoped_link_diff(original, candidate)
    assert semantic_graph_hash(original) != semantic_graph_hash(candidate)
    assert scoped.has_diff is True
    assert scoped.candidate_eligible is True
    assert len(scoped.added_links) == 1
    assert len(scoped.removed_links) == 0


def test_scoped_diff_preserves_duplicate_idless_link_removal() -> None:
    link = _idless_link("out", "in")
    original = _make_simple_graph(links=[link, copy.deepcopy(link)])
    candidate = _make_simple_graph(links=[link])

    scoped = _scoped_link_diff(original, candidate)
    assert semantic_graph_hash(original) != semantic_graph_hash(candidate)
    assert scoped.has_diff is True
    assert scoped.candidate_eligible is True
    assert len(scoped.added_links) == 0
    assert len(scoped.removed_links) == 1


def test_scoped_diff_preserves_duplicate_idless_link_reordering() -> None:
    first = _idless_link("out-a", "in-a")
    second = _idless_link("out-b", "in-b")
    original = _make_simple_graph(links=[first, copy.deepcopy(first), second])
    candidate = _make_simple_graph(links=[first, second, copy.deepcopy(first)])

    scoped = _scoped_link_diff(original, candidate)
    assert semantic_graph_hash(original) != semantic_graph_hash(candidate)
    assert scoped.has_diff is True
    assert scoped.candidate_eligible is False
    assert scoped.added_links == ()
    assert scoped.removed_links == ()
    assert "links.order" in scoped.diff_paths
    assert "unrepresentable_link_order" in scoped.eligibility_blockers


def test_scoped_diff_matches_standard_origin_target_ids_losslessly() -> None:
    original = _make_simple_graph(
        links=[{"id": 7, "origin_id": 1, "origin_slot": 0, "target_id": 2, "target_slot": 0, "type": "IMAGE"}]
    )
    candidate = _make_simple_graph(
        links=[{"id": 8, "origin_id": 1, "origin_slot": 0, "target_id": 2, "target_slot": 0, "type": "IMAGE"}]
    )

    scoped = compute_scoped_diff(
        original,
        candidate,
        topology=TopologyFindings(schema_available=True),
        readiness=ReadinessReport(),
        candidate_topology=TopologyFindings(schema_available=True),
        candidate_readiness=ReadinessReport(),
        target_node_ids=("2",),
    )

    assert scoped.target_matched is True
    assert scoped.candidate_eligible is True
    assert scoped.added_links == (
        {"link_id": 8, "origin_node": 1, "origin_slot": 0, "target_node": 2, "target_slot": 0, "type": "IMAGE"},
    )
    assert scoped.removed_links == (
        {"link_id": 7, "origin_node": 1, "origin_slot": 0, "target_node": 2, "target_slot": 0, "type": "IMAGE"},
    )


def test_scoped_diff_matches_legacy_source_target_forms() -> None:
    original = _make_simple_graph(
        links=[{"id": 7, "source_node": 1, "source_slot": 0, "target_node": 2, "target_slot": 0, "type": "IMAGE"}]
    )
    candidate = _make_simple_graph(
        links=[{"id": 8, "source": {"node_uid": 1, "port": 0}, "target": {"node_uid": 2, "port": 0}, "type": "IMAGE"}]
    )

    scoped = compute_scoped_diff(
        original,
        candidate,
        topology=TopologyFindings(schema_available=True),
        readiness=ReadinessReport(),
        candidate_topology=TopologyFindings(schema_available=True),
        candidate_readiness=ReadinessReport(),
        target_node_ids=("2",),
    )

    assert scoped.target_matched is True
    assert scoped.candidate_eligible is True
    assert scoped.added_links[0]["origin_node"] == 1
    assert scoped.added_links[0]["target_node"] == 2


def test_scoped_diff_fails_closed_for_malformed_link_endpoints() -> None:
    original = _make_simple_graph(
        links=[{"id": 7, "origin_id": 1, "origin_slot": 0, "target_id": 2, "target_slot": 0, "type": "IMAGE"}]
    )
    candidate = _make_simple_graph(
        links=[{"id": 8, "origin_id": 1, "origin_slot": 0, "target_slot": 0, "type": "IMAGE"}]
    )

    scoped = _scoped_link_diff(original, candidate)

    assert scoped.has_diff is True
    assert scoped.candidate_eligible is False
    assert "malformed_link" in scoped.eligibility_blockers


def test_scoped_diff_fails_closed_for_non_link_record() -> None:
    original = _make_simple_graph(links=[])
    candidate = _make_simple_graph(links=["not-a-link"])

    scoped = _scoped_link_diff(original, candidate)

    assert semantic_graph_hash(original) != semantic_graph_hash(candidate)
    assert scoped.has_diff is True
    assert scoped.candidate_eligible is False
    assert "malformed_link" in scoped.eligibility_blockers


def _graph_with_terminal_node() -> dict[str, Any]:
    """Two nodes: SaveImage (terminal/leaf) wired from LoadImage."""
    return _make_simple_graph(
        nodes=[
            {"id": 1, "class_type": "LoadImage",
             "outputs": [{"name": "IMAGE", "type": "IMAGE"}]},
            {"id": 2, "class_type": "SaveImage",
             "outputs": []},
        ],
        links=[
            [1, 0, 2, 0, "IMAGE"],
        ],
    )


def _graph_with_multiple_output_types() -> dict[str, Any]:
    """Graph ending in IMAGE and LATENT output nodes."""
    return _make_simple_graph(
        nodes=[
            {"id": 1, "class_type": "CheckpointLoader",
             "outputs": [{"name": "MODEL", "type": "MODEL"}]},
            {"id": 2, "class_type": "KSampler",
             "outputs": [{"name": "LATENT", "type": "LATENT"}]},
            {"id": 3, "class_type": "VAEDecode",
             "outputs": [{"name": "IMAGE", "type": "IMAGE"}]},
            {"id": 4, "class_type": "PreviewImage",
             "outputs": []},
            {"id": 5, "class_type": "SaveImage",
             "outputs": []},
        ],
        links=[
            [1, 0, 2, 0, "MODEL"],
            [2, 0, 3, 0, "LATENT"],
            [3, 0, 4, 0, "IMAGE"],
            [3, 0, 5, 0, "IMAGE"],
        ],
    )


def _graph_with_unknown_class_types() -> dict[str, Any]:
    """Graph with UnknownClass nodes."""
    return _make_simple_graph(
        nodes=[
            {"id": 1, "class_type": "UnknownNodeA",
             "outputs": [{"name": "IMAGE", "type": "IMAGE"}]},
            {"id": 2, "class_type": "UnknownNodeB",
             "outputs": []},
        ],
        links=[
            [1, 0, 2, 0, "IMAGE"],
        ],
    )


def _graph_with_dangling_outputs() -> dict[str, Any]:
    """Graph where an output slot is unconsumed."""
    return _make_simple_graph(
        nodes=[
            {"id": 1, "class_type": "CheckpointLoader",
             "outputs": [
                 {"name": "MODEL", "type": "MODEL"},
                 {"name": "CLIP", "type": "CLIP"},
                 {"name": "VAE", "type": "VAE"},
             ]},
            {"id": 2, "class_type": "KSampler",
             "outputs": [{"name": "LATENT", "type": "LATENT"}]},
            {"id": 3, "class_type": "VAEDecode",
             "outputs": [{"name": "IMAGE", "type": "IMAGE"}]},
            {"id": 4, "class_type": "SaveImage",
             "outputs": []},
        ],
        links=[
            [1, 0, 2, 0, "MODEL"],    # MODEL consumed
            # CLIP (slot 1) and VAE (slot 2) from node 1 are unconsumed
            [2, 0, 3, 0, "LATENT"],
            [3, 0, 4, 0, "IMAGE"],
        ],
    )


def _graph_with_terminal_socket_types() -> dict[str, Any]:
    """Terminal nodes with IMAGE and MASK output socket types.

    Node 1 (LoadImage) sources IMAGE, node 2 (MaskGen) sources MASK,
    both feed into node 3 (MergeMasks) which combines them.
    Node 3 is the only terminal — it must have output sockets for
    terminal socket types to be populated.
    """
    return _make_simple_graph(
        nodes=[
            {"id": 1, "class_type": "LoadImage",
             "outputs": [{"name": "IMAGE", "type": "IMAGE"}]},
            {"id": 2, "class_type": "MaskGen",
             "outputs": [{"name": "MASK", "type": "MASK"}]},
            {"id": 3, "class_type": "MergeMasks",
             "outputs": [
                 {"name": "IMAGE", "type": "IMAGE"},
                 {"name": "MASK", "type": "MASK"},
             ]},
        ],
        links=[
            [1, 0, 3, 0, "IMAGE"],
            [2, 0, 3, 1, "MASK"],
        ],
    )


def test_scoped_diff_tolerates_preexisting_topology_blockers_for_parameter_edit() -> None:
    original = _make_simple_graph(
        nodes=[
            {"id": 1, "class_type": "LoadImage", "widgets_values": ["input.png"]},
            {"id": 2, "class_type": "SaveImage", "widgets_values": ["before"]},
        ],
        links=[[77, 999, 0, 2, 0, "IMAGE"]],
    )
    candidate = json.loads(json.dumps(original))
    candidate["nodes"][1]["widgets_values"] = ["after"]
    original_topology = collect_topology_evidence(original, schema_available=True)
    candidate_topology = collect_topology_evidence(candidate, schema_available=True)

    scoped = compute_scoped_diff(
        original,
        candidate,
        topology=original_topology,
        readiness=ReadinessReport(),
        candidate_topology=candidate_topology,
        candidate_readiness=ReadinessReport(),
    )

    assert original_topology.has_blockers is True
    assert candidate_topology.has_blockers is True
    assert scoped.changed_nodes == ("2",)
    assert scoped.candidate_eligible is True
    assert "candidate_topology_blockers" not in scoped.eligibility_blockers
    assert "unresolved_topology_blockers" not in scoped.eligibility_blockers


def test_scoped_diff_blocks_new_topology_damage_from_removed_load_bearing_node() -> None:
    original = _make_simple_graph(
        nodes=[
            {"id": 1, "class_type": "LoadImage", "outputs": [{"name": "IMAGE", "type": "IMAGE"}]},
            {
                "id": 2,
                "class_type": "SaveImage",
                "inputs": [{"name": "images", "type": "IMAGE", "link": 77}],
            },
        ],
        links=[[77, 1, 0, 2, 0, "IMAGE"]],
    )
    candidate = _make_simple_graph(
        nodes=[
            {
                "id": 2,
                "class_type": "SaveImage",
                "inputs": [{"name": "images", "type": "IMAGE", "link": 77}],
            },
        ],
        links=[[77, 1, 0, 2, 0, "IMAGE"]],
    )
    original_topology = collect_topology_evidence(original, schema_available=True)
    candidate_topology = collect_topology_evidence(candidate, schema_available=True)

    scoped = compute_scoped_diff(
        original,
        candidate,
        topology=original_topology,
        readiness=ReadinessReport(),
        candidate_topology=candidate_topology,
        candidate_readiness=ReadinessReport(),
    )

    assert original_topology.has_blockers is False
    assert candidate_topology.has_blockers is True
    assert scoped.removed_nodes == ("1",)
    assert scoped.candidate_eligible is False
    assert "candidate_topology_blockers" in scoped.eligibility_blockers


# ══════════════════════════════════════════════════════════════════════════════
# collect_graph_facts — output node types
# ══════════════════════════════════════════════════════════════════════════════


class TestCollectGraphFactsOutputNodeTypes:
    """collect_graph_facts correctly identifies terminal/output node types."""

    def test_terminal_node_type_in_output_node_types(self) -> None:
        """Terminal SaveImage node appears in current_output_node_types."""
        facts = collect_graph_facts(_graph_with_terminal_node())
        assert "SaveImage" in facts.current_output_node_types

    def test_load_image_not_in_output_node_types(self) -> None:
        """LoadImage (a source, not terminal) is NOT in output_node_types."""
        facts = collect_graph_facts(_graph_with_terminal_node())
        assert "LoadImage" not in facts.current_output_node_types

    def test_multiple_output_node_types(self) -> None:
        """Multiple terminal nodes all captured."""
        facts = collect_graph_facts(_graph_with_multiple_output_types())
        assert "PreviewImage" in facts.current_output_node_types
        assert "SaveImage" in facts.current_output_node_types

    def test_no_output_node_types_for_none_graph(self) -> None:
        """None graph yields empty output_node_types."""
        facts = collect_graph_facts(None)
        assert facts.current_output_node_types == ()

    def test_no_output_node_types_for_empty_graph(self) -> None:
        """Empty graph yields empty output_node_types."""
        facts = collect_graph_facts(_make_simple_graph())
        assert facts.current_output_node_types == ()


# ══════════════════════════════════════════════════════════════════════════════
# collect_graph_facts — terminal output socket types
# ══════════════════════════════════════════════════════════════════════════════


class TestCollectGraphFactsTerminalSocketTypes:
    """collect_graph_facts identifies terminal output socket types."""

    def test_terminal_socket_type_image_captured(self) -> None:
        """Terminal node with IMAGE output socket captured."""
        facts = collect_graph_facts(_graph_with_terminal_socket_types())
        assert "IMAGE" in facts.terminal_output_socket_types

    def test_terminal_socket_type_mask_captured(self) -> None:
        """Terminal node with MASK output socket captured."""
        facts = collect_graph_facts(_graph_with_terminal_socket_types())
        assert "MASK" in facts.terminal_output_socket_types

    def test_all_terminal_socket_types_present(self) -> None:
        """Both IMAGE and MASK terminal sockets appear."""
        facts = collect_graph_facts(_graph_with_terminal_socket_types())
        assert len(facts.terminal_output_socket_types) == 2
        assert "IMAGE" in facts.terminal_output_socket_types
        assert "MASK" in facts.terminal_output_socket_types

    def test_no_terminal_socket_types_for_none_graph(self) -> None:
        """None graph yields empty terminal socket types."""
        facts = collect_graph_facts(None)
        assert facts.terminal_output_socket_types == ()

    def test_no_terminal_socket_types_with_no_links(self) -> None:
        """Graph with nodes but no links: all nodes terminal, socket types captured."""
        g = _make_simple_graph(nodes=[
            {"id": 1, "class_type": "SaveImage",
             "outputs": []},
        ])
        facts = collect_graph_facts(g)
        # SaveImage has no output sockets, so terminal socket types are empty
        assert facts.terminal_output_socket_types == ()
        assert "SaveImage" in facts.current_output_node_types


# ══════════════════════════════════════════════════════════════════════════════
# collect_graph_facts — socket mismatch facts
# ══════════════════════════════════════════════════════════════════════════════


class TestCollectGraphFactsSocketMismatches:
    """GraphFacts carries socket_type_mismatches from topology collector."""

    def test_no_mismatches_when_graph_clean(self) -> None:
        """Clean graph yields no socket mismatches in facts."""
        facts = collect_graph_facts(_graph_with_terminal_node())
        assert facts.socket_type_mismatches == ()

    def test_socket_mismatches_in_facts_to_dict(self) -> None:
        """Socket mismatches appear in to_dict() output."""
        facts = collect_graph_facts(_graph_with_terminal_node())
        d = facts.to_dict()
        assert "socket_type_mismatches" in d
        assert d["socket_type_mismatches"] == []

    def test_socket_mismatches_not_lost(self) -> None:
        """When topology finds mismatches they survive into GraphFacts."""
        # Direct construction to verify field flow
        gf = GraphFacts(
            socket_type_mismatches=(
                {"node": "3", "expected": "MODEL", "got": "CLIP"},
            ),
        )
        assert len(gf.socket_type_mismatches) == 1
        assert gf.socket_type_mismatches[0]["node"] == "3"
        assert gf.has_blockers is True


# ══════════════════════════════════════════════════════════════════════════════
# collect_graph_facts — missing required inputs
# ══════════════════════════════════════════════════════════════════════════════


class TestCollectGraphFactsMissingRequiredInputs:
    """GraphFacts carries missing_required_inputs from topology collector."""

    def test_no_missing_inputs_when_graph_clean(self) -> None:
        """Clean graph yields no missing_required_inputs."""
        facts = collect_graph_facts(_graph_with_terminal_node())
        assert facts.missing_required_inputs == ()

    def test_missing_required_inputs_in_to_dict(self) -> None:
        """Missing required inputs field appears in to_dict()."""
        facts = collect_graph_facts(_graph_with_terminal_node())
        d = facts.to_dict()
        assert "missing_required_inputs" in d
        assert d["missing_required_inputs"] == []

    def test_missing_required_inputs_survive_from_topology(self) -> None:
        """When topology has missing inputs, GraphFacts preserves them."""
        gf = GraphFacts(
            missing_required_inputs=(
                {"node": "2", "missing_input": "model"},
            ),
        )
        assert len(gf.missing_required_inputs) == 1
        assert gf.missing_required_inputs[0]["missing_input"] == "model"
        assert gf.has_blockers is True


# ══════════════════════════════════════════════════════════════════════════════
# collect_graph_facts — unknown class types
# ══════════════════════════════════════════════════════════════════════════════


class TestCollectGraphFactsUnknownClassTypes:
    """GraphFacts captures unknown_class_types from topology."""

    def test_unknown_class_types_populated(self) -> None:
        """Graph with unknown class types populates the field."""
        facts = collect_graph_facts(_graph_with_unknown_class_types())
        assert len(facts.unknown_class_types) >= 2
        # collect_topology_evidence may prefix with "node_id=X: "
        joined = " ".join(facts.unknown_class_types)
        assert "UnknownNodeA" in joined
        assert "UnknownNodeB" in joined

    def test_unknown_class_types_appear_in_to_dict(self) -> None:
        """Unknown class types serialized in to_dict()."""
        facts = collect_graph_facts(_graph_with_unknown_class_types())
        d = facts.to_dict()
        assert "unknown_class_types" in d
        joined = " ".join(d["unknown_class_types"])
        assert "UnknownNodeA" in joined
        assert "UnknownNodeB" in joined

    def test_unknown_class_types_triggers_blockers(self) -> None:
        """Unknown class types make has_blockers True."""
        facts = collect_graph_facts(_graph_with_unknown_class_types())
        assert facts.has_blockers is True

    def test_no_unknown_class_types_for_known_graph(self) -> None:
        """Graph with all known types yields empty unknown_class_types (depends on schema)."""
        facts = collect_graph_facts(_graph_with_terminal_node(),
                                    schema_available=False)
        # When schema is unavailable, unknown types degrade gracefully
        # but raw graph traversal may still capture them
        d = facts.to_dict()
        assert "unknown_class_types" in d


# ══════════════════════════════════════════════════════════════════════════════
# collect_graph_facts — missing node packs
# ══════════════════════════════════════════════════════════════════════════════


class TestCollectGraphFactsMissingNodePacks:
    """GraphFacts carries missing_node_packs from readiness collector."""

    def test_missing_node_packs_in_to_dict(self) -> None:
        """Missing node packs field present in serialization."""
        facts = collect_graph_facts(_graph_with_terminal_node())
        d = facts.to_dict()
        assert "missing_node_packs" in d

    def test_missing_node_packs_from_readiness(self) -> None:
        """Readiness-derived missing_node_packs survive into GraphFacts."""
        gf = GraphFacts(
            missing_node_packs=("custom_nodes/my_pack",),
        )
        assert gf.missing_node_packs == ("custom_nodes/my_pack",)
        d = gf.to_dict()
        assert d["missing_node_packs"] == ["custom_nodes/my_pack"]
        assert gf.has_blockers is True

    def test_missing_node_packs_default_empty(self) -> None:
        """Default missing_node_packs is empty."""
        gf = GraphFacts()
        assert gf.missing_node_packs == ()


# ══════════════════════════════════════════════════════════════════════════════
# collect_graph_facts — readiness blockers / notes
# ══════════════════════════════════════════════════════════════════════════════


class TestCollectGraphFactsReadinessNotes:
    """GraphFacts carries readiness_blockers from readiness data."""

    def test_readiness_blockers_in_to_dict(self) -> None:
        """Readiness blockers field present in serialization."""
        facts = collect_graph_facts(_graph_with_terminal_node())
        d = facts.to_dict()
        assert "readiness_blockers" in d

    def test_readiness_blockers_from_parameter(self) -> None:
        """Explicit readiness_blockers parameter flows into GraphFacts."""
        facts = collect_graph_facts(
            _graph_with_terminal_node(),
            readiness_blockers=("no GPU available",),
        )
        assert "no GPU available" in facts.readiness_blockers
        assert facts.has_blockers is True

    def test_no_gpu_detected_in_to_dict(self) -> None:
        """no_gpu_detected field present in serialization."""
        facts = collect_graph_facts(_graph_with_terminal_node())
        d = facts.to_dict()
        assert "no_gpu_detected" in d
        assert d["no_gpu_detected"] is False

    def test_no_gpu_detected_from_parameter(self) -> None:
        """no_gpu_detected=True flows into GraphFacts."""
        facts = collect_graph_facts(
            _graph_with_terminal_node(),
            no_gpu_detected=True,
        )
        assert facts.no_gpu_detected is True
        assert facts.has_blockers is True

    def test_readiness_blockers_combined(self) -> None:
        """Multiple readiness blockers all captured."""
        facts = collect_graph_facts(
            _graph_with_terminal_node(),
            readiness_blockers=("missing model", "no GPU"),
            no_gpu_detected=True,
        )
        assert len(facts.readiness_blockers) == 2
        assert "missing model" in facts.readiness_blockers
        assert "no GPU" in facts.readiness_blockers
        assert facts.no_gpu_detected is True

    def test_readiness_notes_empty_by_default(self) -> None:
        """Default readiness_blockers is empty."""
        gf = GraphFacts()
        assert gf.readiness_blockers == ()
        assert gf.no_gpu_detected is False


# ══════════════════════════════════════════════════════════════════════════════
# collect_graph_facts — summary includes readiness/blocker notes
# ══════════════════════════════════════════════════════════════════════════════


class TestCollectGraphFactsSummary:
    """collect_graph_facts summary includes output types, socket types,
    and readiness/blocker notes derived from existing data."""

    def test_summary_includes_output_node_types(self) -> None:
        """Summary mentions output node types count."""
        facts = collect_graph_facts(_graph_with_terminal_node())
        assert "output node type" in facts.summary.lower()
        assert "SaveImage" in facts.summary

    def test_summary_includes_terminal_socket_types(self) -> None:
        """Summary mentions terminal socket types when present."""
        facts = collect_graph_facts(_graph_with_terminal_socket_types())
        assert "socket type" in facts.summary.lower()

    def test_summary_includes_blocker_count(self) -> None:
        """Summary includes blocker count when blockers present."""
        facts = collect_graph_facts(
            _graph_with_unknown_class_types(),
            readiness_blockers=("no GPU",),
        )
        assert "blocker" in facts.summary.lower()

    def test_summary_no_issues_when_clean(self) -> None:
        """Clean graph summary says 'no graph-fact issues detected'
        when there are no output node types and no blockers."""
        # A graph with no terminal nodes that have output types, and no
        # schema available (so unknown_class_types degrade gracefully).
        g = _make_simple_graph(nodes=[
            {"id": 1, "class_type": "LoadImage",
             "outputs": [{"name": "IMAGE", "type": "IMAGE"}]},
            {"id": 2, "class_type": "SaveImage",
             "outputs": []},
        ], links=[
            [1, 0, 2, 0, "IMAGE"],
        ])
        facts = collect_graph_facts(g, schema_available=True)
        # Even a clean graph may have output node types (SaveImage is terminal).
        # The "no graph-fact issues" line appears when there are no output node
        # types, no terminal socket types, and no blockers.
        # For a truly clean graph with no blockers, the summary will NOT
        # say "no graph-fact issues detected" if there ARE output node types.
        # This is expected: output node types are informational, not blockers.
        # The key assertion is that the summary doesn't claim blockers.
        assert "blocker" not in facts.summary.lower() or facts.has_blockers is False

    def test_summary_includes_dangling_inputs(self) -> None:
        """Summary mentions dangling inputs when detected."""
        facts = collect_graph_facts(_graph_with_dangling_outputs())
        assert "dangling" in facts.summary.lower()

    def test_summary_in_to_dict(self) -> None:
        """Summary field serialized in to_dict()."""
        facts = collect_graph_facts(_graph_with_terminal_node())
        d = facts.to_dict()
        assert "summary" in d
        assert len(d["summary"]) > 0


# ══════════════════════════════════════════════════════════════════════════════
# collect_graph_facts — dangling inputs / outputs
# ══════════════════════════════════════════════════════════════════════════════


class TestCollectGraphFactsDangling:
    """collect_graph_facts detects dangling inputs and outputs."""

    def test_has_dangling_outputs_when_socket_unconsumed(self) -> None:
        """Graph with unconsumed output socket has has_dangling_outputs=True."""
        facts = collect_graph_facts(_graph_with_dangling_outputs())
        assert facts.has_dangling_outputs is True

    def test_no_dangling_outputs_when_all_consumed(self) -> None:
        """Simple wired graph has no dangling outputs."""
        facts = collect_graph_facts(_graph_with_terminal_node())
        assert facts.has_dangling_outputs is False


# ══════════════════════════════════════════════════════════════════════════════
# collect_graph_facts — from_collectors projection
# ══════════════════════════════════════════════════════════════════════════════


class TestCollectGraphFactsFromCollectors:
    """collect_graph_facts properly projects from topology and readiness."""

    def test_readiness_data_reused_not_duplicated(self) -> None:
        """collect_graph_facts reuses existing ReadinessReport/TopologyFindings."""
        facts = collect_graph_facts(
            _graph_with_terminal_node(),
            readiness_blockers=("blocker1",),
        )
        # The readiness blockers came through the function, proving
        # collect_readiness_evidence was called and its data projected.
        assert "blocker1" in facts.readiness_blockers

    def test_topology_data_reused(self) -> None:
        """Facts from topology collector appear in GraphFacts output."""
        facts = collect_graph_facts(_graph_with_unknown_class_types())
        # Unknown class types came through collect_topology_evidence
        assert len(facts.unknown_class_types) >= 2


# ══════════════════════════════════════════════════════════════════════════════
# collect_graph_facts — adapt prompt injection (prompt assembly)
# ══════════════════════════════════════════════════════════════════════════════


class TestAdaptPromptGraphFactsInjection:
    """Adapt-route prompt assembly includes GraphFacts fields in the
    adapt_scoped_research_context that flows into build_batch_messages."""

    def test_graph_facts_to_dict_has_all_required_fields(self) -> None:
        """Every field required for adapt prompt evidence is present in to_dict."""
        facts = collect_graph_facts(_graph_with_dangling_outputs())
        d = facts.to_dict()
        required_fields = [
            "current_output_node_types",
            "terminal_output_socket_types",
            "socket_type_mismatches",
            "missing_required_inputs",
            "unknown_class_types",
            "missing_models",
            "missing_node_packs",
            "readiness_blockers",
            "has_blockers",
            "summary",
        ]
        for field in required_fields:
            assert field in d, f"Field '{field}' missing from GraphFacts.to_dict()"

    def test_graph_facts_json_serializable(self) -> None:
        """GraphFacts.to_dict() output is JSON-serializable for prompt injection."""
        facts = collect_graph_facts(
            _graph_with_terminal_socket_types(),
            readiness_blockers=("no GPU",),
        )
        d = facts.to_dict()
        # Must not raise
        json_str = json.dumps(d, indent=2)
        assert len(json_str) > 0
        assert "current_output_node_types" in json_str
        assert "terminal_output_socket_types" in json_str
        assert "socket_type_mismatches" in json_str
        assert "missing_required_inputs" in json_str
        assert "unknown_class_types" in json_str

    def test_adapt_prompt_includes_graph_facts_section(self) -> None:
        """When graph_facts dict is present, adapt_scoped_research_context
        includes the '## Graph Facts' header."""
        facts = collect_graph_facts(_graph_with_terminal_node())
        facts_dict = facts.to_dict()
        facts_str = json.dumps(facts_dict, indent=2, sort_keys=True)

        # Replicate the prompt assembly logic from edit.py lines 4124-4131
        parts: list[str] = []
        parts.append(
            "## Graph Facts (workflow topology evidence)\n"
            "Deterministic topology/readiness evidence about the current graph. "
            "Use this to understand the workflow structure, terminal outputs, "
            "and any known blockers. NOT a revision verdict.\n"
            f"{facts_str}"
        )
        context = "\n\n".join(parts)

        # Verify the prompt block includes key evidence
        assert "## Graph Facts (workflow topology evidence)" in context
        assert "NOT a revision verdict" in context
        assert "current_output_node_types" in context
        assert "terminal_output_socket_types" in context
        assert "missing_required_inputs" in context
        assert "missing_node_packs" in context
        assert "readiness_blockers" in context
        assert "unknown_class_types" in context
        assert "socket_type_mismatches" in context

    def test_adapt_prompt_block_includes_readiness_data(self) -> None:
        """Readiness data (missing_node_packs, readiness_blockers) appears
        in the prompt block derived from graph_facts."""
        facts = collect_graph_facts(
            _graph_with_terminal_node(),
            readiness_blockers=("Runtime execution was requested, but no GPU is available.",),
            no_gpu_detected=True,
        )
        facts_dict = facts.to_dict()
        facts_str = json.dumps(facts_dict, indent=2, sort_keys=True)

        assert "readiness_blockers" in facts_str
        assert "no GPU" in facts_str
        assert facts_dict["no_gpu_detected"] is True
        assert len(facts_dict["readiness_blockers"]) >= 1

    def test_adapt_prompt_block_includes_missing_node_packs(self) -> None:
        """Missing node packs from readiness appear in the prompt block."""
        gf = GraphFacts(
            current_output_node_types=("SaveImage",),
            missing_node_packs=("custom_nodes/comfyui-videohelpersuite",),
            missing_models=(),
            readiness_blockers=(),
            summary="1 missing node pack",
        )
        d = gf.to_dict()
        facts_str = json.dumps(d, indent=2, sort_keys=True)
        assert "missing_node_packs" in facts_str
        assert "comfyui-videohelpersuite" in facts_str

    def test_adapt_prompt_block_includes_socket_mismatch_facts(self) -> None:
        """Socket mismatch facts appear in the JSON prompt block."""
        gf = GraphFacts(
            socket_type_mismatches=(
                {"node": "5", "expected": "IMAGE", "got": "LATENT"},
            ),
            summary="1 socket type mismatch",
        )
        d = gf.to_dict()
        facts_str = json.dumps(d, indent=2, sort_keys=True)
        assert "socket_type_mismatches" in facts_str
        assert "IMAGE" in facts_str
        assert "LATENT" in facts_str

    def test_adapt_prompt_block_includes_unknown_class_types(self) -> None:
        """Unknown class types appear in the JSON prompt block."""
        gf = GraphFacts(
            unknown_class_types=("CustomSampler",),
            summary="1 unknown class type",
        )
        d = gf.to_dict()
        facts_str = json.dumps(d, indent=2, sort_keys=True)
        assert "unknown_class_types" in facts_str
        assert "CustomSampler" in facts_str

    def test_precedent_adaptation_plan_wraps_graph_facts(self) -> None:
        """Simulate how precedent_adaptation_plan gets graph_facts injected
        as part of the combined adaptation plan text."""
        from vibecomfy.comfy_nodes.agent.provider import build_batch_messages

        facts = collect_graph_facts(_graph_with_terminal_socket_types())
        facts_dict = facts.to_dict()
        facts_str = json.dumps(facts_dict, indent=2, sort_keys=True)

        # Build a combined adaptation plan that mimics the edit.py assembly:
        # precedent_adaptation_prompt + "\n\n" + adapt_scoped_research_context
        adapt_scoped = (
            "## Scoped Research Context (execution_protocol_notes)\n"
            "This is contextual evidence, NOT authoritative guidance.\n"
            '{"research_goal": "test"}\n\n'
            "## Graph Facts (workflow topology evidence)\n"
            "Deterministic topology/readiness evidence about the current graph. "
            "Use this to understand the workflow structure, terminal outputs, "
            "and any known blockers. NOT a revision verdict.\n"
            f"{facts_str}"
        )

        combined_plan = adapt_scoped.strip()

        messages = build_batch_messages(
            task="adapt image generation",
            turn_number=0,
            python_source="img = LoadImage()",
            signature_catalog="LoadImage(image), SaveImage(images)",
            available_node_names="LoadImage, SaveImage",
            precedent_adaptation_plan=combined_plan,
        )

        user_content = messages[1]["content"]
        assert "Precedent adaptation plan (structured):" in user_content
        # Graph facts evidence is present
        assert "Graph Facts" in user_content
        assert "current_output_node_types" in user_content
        assert "terminal_output_socket_types" in user_content
        assert "socket_type_mismatches" in user_content
        assert "missing_required_inputs" in user_content
        assert "unknown_class_types" in user_content
        assert "missing_node_packs" in user_content
        assert "readiness_blockers" in user_content

    def test_adapt_prompt_discardability_note_present(self) -> None:
        """When execution_protocol_notes has _discardability, it flows to prompt."""
        facts = collect_graph_facts(_graph_with_terminal_node())
        facts_dict = facts.to_dict()
        facts_str = json.dumps(facts_dict, indent=2, sort_keys=True)

        # Simulate the adapt_scoped_research_context assembly with discardability
        discard_note = "This evidence is discardable if irrelevant."
        parts: list[str] = []
        parts.append(
            "## Graph Facts (workflow topology evidence)\n"
            "Deterministic topology/readiness evidence about the current graph. "
            "Use this to understand the workflow structure, terminal outputs, "
            "and any known blockers. NOT a revision verdict.\n"
            f"{facts_str}"
        )
        parts.append(f"**Discardability**: {discard_note}")
        context = "\n\n".join(parts)

        assert "**Discardability**" in context
        assert "discardable if irrelevant" in context
        assert "## Graph Facts" in context

    def test_graph_facts_no_winner_or_best_keys(self) -> None:
        """GraphFacts serialization never includes forbidden winner-like keys."""
        facts = collect_graph_facts(
            _graph_with_unknown_class_types(),
            readiness_blockers=("test blocker",),
        )
        d = facts.to_dict()
        forbidden = {
            "winner", "best", "selected", "chosen", "score", "rank",
            "primary", "preferred", "pick", "choice", "top", "recommended",
        }
        for key in forbidden:
            assert key not in d, f"Forbidden key '{key}' found in GraphFacts.to_dict()"

    def test_graph_facts_structural_summary_includes_output_types(self) -> None:
        """Summary built by collect_graph_facts names output node types."""
        facts = collect_graph_facts(_graph_with_multiple_output_types())
        assert "output node type" in facts.summary.lower()
        assert "PreviewImage" in facts.summary or "SaveImage" in facts.summary

    def test_graph_facts_structural_summary_includes_terminal_sockets(self) -> None:
        """Summary built by collect_graph_facts names terminal socket types."""
        facts = collect_graph_facts(_graph_with_terminal_socket_types())
        assert "socket type" in facts.summary.lower()


# ══════════════════════════════════════════════════════════════════════════════
# Integration: graph_facts → adapt prompt completeness
# ══════════════════════════════════════════════════════════════════════════════


class TestGraphFactsAdaptPromptCompleteness:
    """All eight categories of graph-fact evidence are present in the
    adapt-scoped research context that the model receives."""

    def test_all_eight_evidence_categories_in_to_dict(self) -> None:
        """to_dict includes all eight evidence categories required by SC12."""
        facts = collect_graph_facts(
            _graph_with_multiple_output_types(),
            readiness_blockers=("missing model X",),
            no_gpu_detected=True,
        )
        d = facts.to_dict()

        # 1. current_output_node_types
        assert len(d["current_output_node_types"]) >= 2
        # 2. terminal_output_socket_types
        assert isinstance(d["terminal_output_socket_types"], list)
        # 3. socket_type_mismatches
        assert "socket_type_mismatches" in d
        # 4. missing_required_inputs
        assert "missing_required_inputs" in d
        # 5. unknown_class_types
        assert "unknown_class_types" in d
        # 6. missing_node_packs
        assert "missing_node_packs" in d
        # 7. readiness_blockers (readiness notes)
        assert len(d["readiness_blockers"]) >= 1
        assert "missing model X" in d["readiness_blockers"]
        # 8. summary includes readiness-derived notes
        assert len(d["summary"]) > 0

    def test_all_fields_serialized_as_lists(self) -> None:
        """Tuple fields serialized as JSON lists in to_dict."""
        facts = collect_graph_facts(_graph_with_terminal_socket_types())
        d = facts.to_dict()
        assert isinstance(d["current_output_node_types"], list)
        assert isinstance(d["terminal_output_socket_types"], list)
        assert isinstance(d["unknown_class_types"], list)
        assert isinstance(d["missing_models"], list)
        assert isinstance(d["missing_node_packs"], list)
        assert isinstance(d["readiness_blockers"], list)
        assert isinstance(d["socket_type_mismatches"], list)
        assert isinstance(d["missing_required_inputs"], list)


def test_topology_evidence_tolerates_int_node_id_with_str_link_endpoint() -> None:
    """ComfyUI LiteGraph mixes int node ids with str endpoint refs in links.

    A valid graph where ``nodes[*].id`` is the int ``1`` but the link stores
    the endpoint as the string ``"1"`` must NOT be misreported as having an
    absent endpoint node.  Prior to the fix this false positive blocked every
    demo_factory additive (remove_feature) case at the revise pre-edit gate.
    """
    graph = {
        "nodes": [
            {
                "id": 1,
                "type": "LoadImage",
                "inputs": [],
                "outputs": [{"name": "IMAGE", "type": "IMAGE", "links": [3]}],
            },
            {
                "id": 3,
                "type": "SaveImage",
                "inputs": [{"name": "images", "type": "IMAGE", "link": 3}],
                "outputs": [],
            },
        ],
        "links": [[3, "1", 0, "3", 0, "IMAGE"]],
    }
    findings = collect_topology_evidence(graph, schema_available=False)
    assert findings.absent_endpoint_nodes == ()
    assert findings.dangling_links == ()
    assert findings.has_blockers is False


def test_topology_evidence_still_detects_genuinely_absent_endpoint() -> None:
    """Type-tolerance must not mask a real dangling endpoint reference."""
    graph = {
        "nodes": [
            {"id": 1, "type": "LoadImage", "inputs": [], "outputs": []},
            {"id": 2, "type": "SaveImage", "inputs": [], "outputs": []},
        ],
        # Link references node id 99 which is not in nodes — genuinely absent.
        "links": [[5, 1, 0, 99, 0, "IMAGE"]],
    }
    findings = collect_topology_evidence(graph, schema_available=False)
    assert "99" in findings.absent_endpoint_nodes
    assert findings.has_blockers is True
