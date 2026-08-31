"""Artifact-shaped replay canaries for the four reported carrier failures."""

from __future__ import annotations

import copy
import json
from pathlib import Path

from vibecomfy.comfy_nodes.agent.authority_receipts import (
    canonical_frozen_name_table,
    verify_replay,
)
from vibecomfy.ingest.normalize import from_ui
from vibecomfy.porting.edit._diff import diff
from vibecomfy.schema.provider import ObjectInfoIndexSchemaProvider


ROOT = Path(__file__).parent / "fixtures" / "replay_domain"
OBJECT_INFO = ObjectInfoIndexSchemaProvider("vibecomfy/porting/cache/object_info")


def _case(stem: str) -> tuple[dict, dict]:
    return (
        json.loads((ROOT / f"{stem}_pre.json").read_text(encoding="utf-8")),
        json.loads((ROOT / f"{stem}_post.json").read_text(encoding="utf-8")),
    )


def _verify(stem: str, fields: list[tuple[str, str, object]]):
    pre, post = _case(stem)
    table = canonical_frozen_name_table(pre, schema_provider=OBJECT_INFO)
    envelope = {
        "schema_version": "2.0.0",
        "ops": [
            {"op": "set_node_field", "target": ["", uid, field], "value": value}
            for uid, field, value in fields
        ],
    }
    return pre, post, table, envelope


def test_canary_14_15_tripo_texture_quality_replays_with_retained_link() -> None:
    pre, post, table, envelope = _verify(
        "tripo_14_15", [("26", "texture_quality", "detailed")]
    )
    receipt = verify_replay(
        pre,
        envelope,
        post,
        schema_provider=OBJECT_INFO,
        name_authority=table,
    )
    assert receipt.replay_ok and receipt.candidate_matches, receipt.error
    assert table["26"] == (
        "texture",
        "pbr",
        "texture_seed",
        "texture_quality",
        "texture_alignment",
    )


def test_canary_32_acestep_two_field_edit_replays_without_link_residuals() -> None:
    pre, post, table, envelope = _verify(
        "acestep_32", [("3", "steps", 30), ("3", "scheduler", "karras")]
    )
    receipt = verify_replay(
        pre,
        envelope,
        post,
        schema_provider=OBJECT_INFO,
        name_authority=table,
    )
    assert receipt.replay_ok and receipt.candidate_matches, receipt.error
    assert table["3"] == (
        "seed",
        "control_after_generate",
        "steps",
        "cfg",
        "sampler_name",
        "scheduler",
        "denoise",
    )


def test_canary_82_83_llama_named_api_ui_vector_replays() -> None:
    pre, post, table, envelope = _verify(
        "llama_82_83", [("3", "max_tokens", 256)]
    )
    receipt = verify_replay(
        pre,
        envelope,
        post,
        schema_provider=OBJECT_INFO,
        name_authority=table,
    )
    assert receipt.replay_ok and receipt.candidate_matches, receipt.error
    assert table["3"][0:6] == (
        "max_tokens",
        "top_k",
        "top_p",
        "min_p",
        "typical_p",
        "temperature",
    )


def test_artifact_tamper_controls_reject_untouched_widget_link_and_delta() -> None:
    pre, post, table, envelope = _verify(
        "tripo_14_15", [("26", "texture_quality", "detailed")]
    )

    untouched = copy.deepcopy(post)
    untouched["nodes"][1]["widgets_values"][2] = 43
    receipt = verify_replay(pre, envelope, untouched, schema_provider=OBJECT_INFO, name_authority=table)
    assert receipt.candidate_matches is False

    endpoint = copy.deepcopy(post)
    endpoint["links"][0][2] = 0  # still a valid output slot on node 7
    endpoint["nodes"][0]["outputs"][0]["links"] = [2]
    endpoint_receipt = verify_replay(pre, envelope, endpoint, schema_provider=OBJECT_INFO, name_authority=table)
    assert endpoint_receipt.candidate_matches is False

    mutated_delta = copy.deepcopy(envelope)
    mutated_delta["ops"][0]["value"] = "original_image"
    delta_receipt = verify_replay(pre, mutated_delta, post, schema_provider=OBJECT_INFO, name_authority=table)
    assert delta_receipt.replay_ok is False or delta_receipt.candidate_matches is False


def test_exact_artifacts_reject_frozen_witness_tamper_and_absence() -> None:
    """The production verifier must consume the artifact's frozen witness.

    A changed roster and a missing row are both authority failures, even when
    the ambient object-info provider could infer a plausible replacement.
    Keep this control on every reported canary so a future carrier adapter
    cannot regress one shape while the others remain covered.
    """
    cases = (
        ("tripo_14_15", "26", "texture_quality", "detailed"),
        ("acestep_32", "3", "steps", 30),
        ("llama_82_83", "3", "max_tokens", 256),
    )
    for stem, uid, field, value in cases:
        pre, post, table, envelope = _verify(stem, [(uid, field, value)])

        unpinned_receipt = verify_replay(
            pre,
            envelope,
            post,
            schema_provider=OBJECT_INFO,
        )
        assert not (
            unpinned_receipt.replay_ok and unpinned_receipt.candidate_matches
        ), stem

        absent = dict(table)
        absent.pop(uid)
        absent_receipt = verify_replay(
            pre,
            envelope,
            post,
            schema_provider=OBJECT_INFO,
            name_authority=absent,
        )
        assert absent_receipt.replay_ok is False
        assert "frozen_name_table" in (absent_receipt.error or "")

        tampered = dict(table)
        roster = list(tampered[uid])
        # Substitute one witness literal with a same-length, unique unrelated
        # name: shape/uniqueness checks alone must not authenticate it.
        roster[-1] = "tampered_unrelated"
        tampered[uid] = tuple(roster)
        tampered_receipt = verify_replay(
            pre,
            envelope,
            post,
            schema_provider=OBJECT_INFO,
            name_authority=tampered,
        )
        assert not (
            tampered_receipt.replay_ok and tampered_receipt.candidate_matches
        )


def test_missing_snapshot_witness_is_not_replaced_by_ambient_object_info() -> None:
    pre, post, _table, _envelope = _verify(
        "tripo_14_15", [("26", "texture_quality", "detailed")]
    )
    pre_wf = from_ui(pre, schema_provider=OBJECT_INFO, use_comfy_converter=False)
    post_wf = from_ui(post, schema_provider=OBJECT_INFO, use_comfy_converter=False)
    pre_wf.metadata.pop("_workflow_snapshot", None)
    ops = diff(pre_wf, post_wf, schema_provider=OBJECT_INFO)
    assert any(getattr(op, "op", None) == "remove_node" for op in ops)


def test_exact_artifacts_missing_snapshot_rows_rebuild_instead_of_fallback() -> None:
    for stem, uid, field, value in (
        ("tripo_14_15", "26", "texture_quality", "detailed"),
        ("acestep_32", "3", "steps", 30),
        ("llama_82_83", "3", "max_tokens", 256),
    ):
        pre, post, _table, _envelope = _verify(stem, [(uid, field, value)])
        pre_wf = from_ui(pre, schema_provider=OBJECT_INFO, use_comfy_converter=False)
        post_wf = from_ui(post, schema_provider=OBJECT_INFO, use_comfy_converter=False)
        pre_wf.metadata.pop("_workflow_snapshot", None)
        ops = diff(pre_wf, post_wf, schema_provider=OBJECT_INFO)
        assert any(getattr(op, "op", None) == "remove_node" for op in ops), stem
