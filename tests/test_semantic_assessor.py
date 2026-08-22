"""T5.2 canonical semantic assessor — typed-carrier and honesty proofs."""

from __future__ import annotations

import json
from pathlib import Path

import pytest

from tests.live_agentic_harness.intent_judge import judge_edit_intent
from tests.live_agentic_harness.semantic_assessor import (
    CanonicalSemanticView,
    LineageMismatch,
    TypedCarrierRequired,
    canonical_semantic_view,
    judge_graph_pair,
    require_matching_lineage,
)

_LIN = {
    "scenario_id": "s1",
    "session_id": "sess",
    "turn_id": "0001",
    "baseline_id": "0000",
}


def _ui_graph(seed: int = 7) -> dict:
    return {
        "last_node_id": 1,
        "last_link_id": 0,
        "nodes": [
            {
                "id": 1,
                "type": "KSampler",
                "properties": {"vibecomfy_uid": "1"},
                "widgets_values": [seed, "fixed", 20, 8, "euler", "normal", 1],
            }
        ],
        "links": [],
    }


def _api_graph(seed: int = 7) -> dict:
    return {
        "1": {
            "class_type": "KSampler",
            "inputs": {"seed": seed, "steps": 20},
        }
    }


# ── typed-only construction ──────────────────────────────────────────────────


def test_arbitrary_dict_is_rejected_not_guessed() -> None:
    with pytest.raises(TypedCarrierRequired):
        canonical_semantic_view({"nodes": "not-a-graph"}, lineage=_LIN)
    with pytest.raises(TypedCarrierRequired):
        canonical_semantic_view({"random": {"nested": True}}, lineage=_LIN)
    with pytest.raises(TypedCarrierRequired):
        canonical_semantic_view(42)


def test_ui_api_envelope_carriers_decode_through_own_named_door() -> None:
    ui_view = canonical_semantic_view(_ui_graph(), lineage=_LIN)
    assert ui_view.source_representation == "ui"
    api_view = canonical_semantic_view(_api_graph(), lineage=_LIN)
    assert api_view.source_representation == "api"
    envelope = json.loads(
        (Path(__file__).parent / "fixtures/3c978e6c11a8a768.json").read_text(
            encoding="utf-8"
        )
    )
    env_view = canonical_semantic_view(envelope, lineage=_LIN)
    assert env_view.source_representation == "envelope"


def test_mixed_ui_api_pair_is_decoded_per_side_not_forced_through_one_decoder() -> None:
    """r5 failure #1 counterexample: UI original + API final must each decode
    through its own door — the API side is never reinterpreted as UI."""
    pre = canonical_semantic_view(_ui_graph(seed=7), lineage=_LIN)
    post = canonical_semantic_view(_api_graph(seed=7), lineage=_LIN)
    assert pre.source_representation == "ui"
    assert post.source_representation == "api"


# ── lineage matching ─────────────────────────────────────────────────────────


def test_mismatched_lineage_pair_is_rejected() -> None:
    pre = canonical_semantic_view(_ui_graph(), lineage=_LIN)
    post = canonical_semantic_view(
        _ui_graph(),
        lineage={**_LIN, "session_id": "other-session"},
    )
    with pytest.raises(LineageMismatch, match="session_id"):
        require_matching_lineage(pre, post)
    with pytest.raises(LineageMismatch, match="session_id"):
        judge_graph_pair(pre, post, (), schema_provider=None)


def test_unknown_lineage_keys_do_not_false_positive() -> None:
    pre = canonical_semantic_view(_ui_graph(), lineage={"scenario_id": "s1"})
    post = canonical_semantic_view(_ui_graph(), lineage={})
    require_matching_lineage(pre, post)  # empty = unknown, not contradictory


# ── verdict honesty: no synthesis ever ───────────────────────────────────────


def _pair(seed_pre: int, seed_post: int) -> tuple:
    pre = canonical_semantic_view(_ui_graph(seed_pre), lineage=_LIN)
    post = canonical_semantic_view(_ui_graph(seed_post), lineage=_LIN)
    return pre, post


@pytest.mark.parametrize("gate_failed", [False, True])
def test_unchanged_with_no_delta_never_synthesizes_an_edit(gate_failed: bool) -> None:
    pre, post = _pair(7, 7)
    verdict = judge_graph_pair(pre, post, (), queue_gate_failed=gate_failed)
    assert verdict.outcome == "no_edit"
    assert verdict.reason == "no_accepted_delta_and_unchanged_product"
    assert verdict.detail["pre_digest"] == verdict.detail["post_digest"]


def test_changed_product_without_authority_is_undetermined() -> None:
    pre, post = _pair(7, 30)
    verdict = judge_graph_pair(pre, post, ())
    assert verdict.outcome == "undetermined"
    assert verdict.reason == "changed_product_without_accepted_delta"


def test_withheld_batch_is_undetermined_even_when_ops_exist() -> None:
    pre, post = _pair(7, 30)
    ops = ({"op": "set_node_field", "target": ["", "1", "seed"], "value": 30},)
    verdict = judge_graph_pair(pre, post, ops, queue_gate_failed=True)
    assert verdict.outcome == "undetermined"


def test_accepted_delta_matching_product_is_applied_edit() -> None:
    pre, post = _pair(7, 30)
    ops = ({"op": "set_node_field", "target": ["", "1", "seed"], "value": 30},)
    verdict = judge_graph_pair(pre, post, ops)
    assert verdict.outcome == "applied_edit"


def test_accepted_delta_contradicting_product_is_fail_closed() -> None:
    pre, post = _pair(7, 30)
    # Δ claims a change to node "99" that never happened.
    ops = ({"op": "set_node_field", "target": ["", "99", "widgets_values.0"], "value": 1},)
    verdict = judge_graph_pair(pre, post, ops)
    assert verdict.outcome == "undetermined"
    assert "does_not_reconstruct" in verdict.reason or "reconstruct" in verdict.reason


# ── judge integration over artifacts ─────────────────────────────────────────


def _write_run(tmp_path: Path, *, pre: dict, post: dict, response: dict, lineage: bool) -> None:
    (tmp_path / "original.ui.json").write_text(json.dumps(pre), encoding="utf-8")
    (tmp_path / "final.ui.json").write_text(json.dumps(post), encoding="utf-8")
    (tmp_path / "response.json").write_text(json.dumps(response), encoding="utf-8")
    if lineage:
        from vibecomfy.comfy_nodes.agent.artifact_lineage import (
            LINK_KINDS,
            FALLBACK_REASONS,
            build_artifact_lineage,
            fallback_row,
        )

        manifest = build_artifact_lineage(
            lineage=_LIN,
            rows=[fallback_row(k, sorted(FALLBACK_REASONS[k])[0]) for k in LINK_KINDS],
        )
        (tmp_path / "artifact_lineage.json").write_text(
            json.dumps(manifest), encoding="utf-8"
        )


def test_canonical_mode_unchanged_no_delta_fails_without_model_call(tmp_path: Path) -> None:
    _write_run(
        tmp_path,
        pre=_ui_graph(7),
        post=_ui_graph(7),
        response={"ok": True, "graph_unchanged": True},
        lineage=True,
    )
    verdict = judge_edit_intent(tmp_path, {"query": "set seed to 30"})
    assert verdict["pass_"] is False
    assert "no edit exists" in (verdict.get("rationale") or "")
    assert verdict.get("metadata", {}).get("verdict") == "no_edit"


def test_canonical_mode_changed_without_delta_is_undetermined(tmp_path: Path) -> None:
    _write_run(
        tmp_path,
        pre=_ui_graph(7),
        post=_ui_graph(30),
        response={"ok": True, "graph_unchanged": False},
        lineage=True,
    )
    verdict = judge_edit_intent(tmp_path, {"query": "set seed to 30"})
    assert verdict["pass_"] is None
    assert "changed_product_without_accepted_delta" in (verdict.get("error") or "")


def test_canonical_mode_withheld_batch_is_undetermined(tmp_path: Path) -> None:
    _write_run(
        tmp_path,
        pre=_ui_graph(7),
        post=_ui_graph(30),
        response={
            "ok": True,
            "gates": {"queue_validate_ok": False},
            "accepted_batch": [
                {
                    "ok": True,
                    "landed": True,
                    "op": {
                        "op": "set_node_field",
                        "target": ["", "1", "seed"],
                        "value": 30,
                    },
                }
            ],
        },
        lineage=True,
    )
    verdict = judge_edit_intent(tmp_path, {"query": "set seed to 30"})
    assert verdict["pass_"] is None
    assert "withheld_accepted_batch" in (verdict.get("error") or "")


def test_legacy_artifacts_without_lineage_keep_rc12b_behavior(
    tmp_path: Path, monkeypatch
) -> None:
    """Lineage-less fixtures keep the historical product-diff seed (frozen
    compatibility surface; ledger T5.5-LS-01)."""
    calls: list[int] = []

    def fake_run_model_turn(task, *, messages, **kwargs):  # noqa: ANN001, ANN202
        calls.append(len(calls))
        payload = json.loads(messages[1]["content"])
        assert payload.get("delta", {}).get("seed") == "canonical_diff"
        return {
            "content": json.dumps(
                {
                    "pass_": True,
                    "criteria": {
                        "correct_node_targeted": True,
                        "correct_parameter_changed": True,
                        "value_semantically_matches_intent": True,
                        "no_orphaned_wiring": True,
                    },
                    "rationale": "legacy product graded",
                }
            )
        }

    monkeypatch.setattr(
        "tests.live_agentic_harness.intent_judge.run_model_turn",
        fake_run_model_turn,
    )
    _write_run(
        tmp_path,
        pre=_ui_graph(7),
        post=_ui_graph(30),
        response={"ok": True, "gates": {"queue_validate_ok": False}},
        lineage=False,
    )
    verdict = judge_edit_intent(tmp_path, {"query": "set steps to 30"})
    assert verdict["pass_"] is True
    assert len(calls) == 1
