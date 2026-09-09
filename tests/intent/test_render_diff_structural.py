"""Tests for render_diff.py — structural proxy diff and seed fixing.

CI invocation: pytest -m intent_ci tests/intent/test_render_diff_structural.py
"""
import copy

import pytest

from vibecomfy import load_workflow_any
from vibecomfy.intent.render_diff import SEED_FIELDS, StructuralDiffResult, fix_seeds_in_ir, structural_proxy_diff

pytestmark = pytest.mark.intent_ci


# ---------------------------------------------------------------------------
# structural_proxy_diff tests (2 image-family fixtures)
# ---------------------------------------------------------------------------

def _load_image_pair():
    """Return independent complete z_image graphs whose public sampler seed changes."""
    pre = load_workflow_any("image/z_image")
    post = fix_seeds_in_ir(pre, seed=99999)
    return pre, post


def test_structural_proxy_diff_detects_difference():
    pre, post = _load_image_pair()
    report = structural_proxy_diff(pre, post)
    assert isinstance(report, StructuralDiffResult)
    assert pre.compile("api")["8"]["inputs"]["seed"] == 770044821593082
    assert post.compile("api")["8"]["inputs"]["seed"] == 99999
    assert report.api_sha_pre != report.api_sha_post, "pre and post hashes should differ after seed change"
    assert report.equal is False


def test_structural_proxy_diff_identical_workflows():
    pre = load_workflow_any("image/z_image")
    post = copy.deepcopy(pre)
    report = structural_proxy_diff(pre, post)
    assert report.equal is True
    assert report.api_sha_pre == report.api_sha_post


# ---------------------------------------------------------------------------
# fix_seeds_in_ir mutation tests (image, edit, video families)
# ---------------------------------------------------------------------------

def _count_sampler_nodes(wf):
    return sum(1 for n in wf.nodes.values() if n.class_type in SEED_FIELDS)


def test_fix_seeds_mutated_image_fixture():
    """fix_seeds_in_ir must mutate ≥1 sampler node in the image-family pre-workflow."""
    wf = load_workflow_any("image/z_image")
    assert _count_sampler_nodes(wf) >= 1, "z_image should have at least one sampler node"
    fixed = fix_seeds_in_ir(wf, seed=12345)
    mutated = sum(
        1
        for orig, new in zip(wf.nodes.values(), fixed.nodes.values())
        if orig.class_type in SEED_FIELDS
        and orig.inputs.get(SEED_FIELDS[orig.class_type][0]) != new.inputs.get(SEED_FIELDS[new.class_type][0])
    )
    assert mutated >= 1, "fix_seeds_in_ir must mutate at least one sampler seed (image)"


def test_fix_seeds_mutated_edit_fixture():
    """fix_seeds_in_ir must mutate ≥1 sampler node in an edit-family pre-workflow."""
    wf = load_workflow_any("edit/qwen_image_edit")
    assert _count_sampler_nodes(wf) >= 1, "qwen_image_edit should have at least one sampler node"
    fixed = fix_seeds_in_ir(wf, seed=42)
    mutated = sum(
        1
        for orig, new in zip(wf.nodes.values(), fixed.nodes.values())
        if orig.class_type in SEED_FIELDS
        and orig.inputs.get(SEED_FIELDS[orig.class_type][0]) != new.inputs.get(SEED_FIELDS[new.class_type][0])
    )
    assert mutated >= 1, "fix_seeds_in_ir must mutate at least one sampler seed (edit)"


def test_fix_seeds_mutated_video_ltx_fixture():
    """fix_seeds_in_ir must mutate ≥1 sampler node in the LTX video fixture.

    This test drives out the silent no-op on LTX: the ready template exposes
    RandomNoise nodes (with noise_seed) which are the actual seed-bearing nodes
    in SamplerCustomAdvanced / LTX-2.3 graphs.  If SEED_FIELDS omits RandomNoise,
    this fixture would silently leave seeds unchanged.
    """
    wf = load_workflow_any("video/ltx2_3_t2v")
    assert _count_sampler_nodes(wf) >= 1, "ltx2_3_t2v should have at least one node in SEED_FIELDS"
    fixed = fix_seeds_in_ir(wf, seed=77777)
    mutated = sum(
        1
        for (nid, orig), (_, new) in zip(wf.nodes.items(), fixed.nodes.items())
        if orig.class_type in SEED_FIELDS
        and orig.inputs.get(SEED_FIELDS[orig.class_type][0]) != new.inputs.get(SEED_FIELDS[new.class_type][0])
    )
    assert mutated >= 1, "fix_seeds_in_ir must mutate at least one seed node (video/ltx)"


def test_fix_seeds_no_sampler_raises():
    """fix_seeds_in_ir should raise ValueError when no sampler node exists."""
    wf = load_workflow_any("image/z_image")
    # Remove all sampler nodes from a deep copy
    cloned = copy.deepcopy(wf)
    sampler_ids = [nid for nid, n in cloned.nodes.items() if n.class_type in SEED_FIELDS]
    for nid in sampler_ids:
        del cloned.nodes[nid]
    with pytest.raises(ValueError, match="no sampler node found"):
        fix_seeds_in_ir(cloned, seed=1)
