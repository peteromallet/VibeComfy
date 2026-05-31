"""M1 final integration gate (T13) for the UI emitter.

Wired to the existing harness (tests/conftest.py + the
``pytest_plugins=("vibecomfy.testing._pytest_plugin",)`` registration). This is the
corpus-wide gate over :mod:`vibecomfy.porting.ui_emitter` and the T2 ingest change.
It covers, in one file:

- (a) offline parity green on a starter set (>=5 spanning image/video/edit) AND across
  the full ``workflow_corpus`` minus the T12 documented allowlist
  (``docs/corpus_parity_allowlist.md``);
- (b) structural-validation green corpus-wide (schema-less assertions skipped + reported);
- (c) uid or display-id present on every node (ir_node_id demoted in M5);
- (d) same-IR -> byte-identical JSON on re-emit;
- (e) the KSampler ``None``-widget round-trip alignment case (Step 7.2);
- schema-less nodes warn-and-emit by default and hard-fail under ``strict=True``.

The offline parity gate never imports ComfyUI (it calls the ``_normalize_ui_to_api``
fallback directly). The real ``convert_ui_to_api`` editor-compatibility smoke is a
separate env-gated ``@pytest.mark.comfy`` release gate and is NOT exercised here.
"""
from __future__ import annotations

import glob
import json
import warnings
from pathlib import Path

import pytest

from vibecomfy.ingest.normalize import convert_to_vibe_format
from vibecomfy.porting.ui_emitter import (
    emit_ui_json,
    offline_emitter_normalizer_self_consistency_check,
    structural_validate,
)
from vibecomfy.workflow import VibeNode, VibeWorkflow, WorkflowSource


# ---------------------------------------------------------------------------
# Fixtures / helpers
# ---------------------------------------------------------------------------

# Starter set: >=5 entries spanning image / video / edit, all in the "gate passes"
# section of docs/corpus_parity_allowlist.md.
_STARTER_SET = [
    "workflow_corpus/official/image/z_image.json",
    "workflow_corpus/official/image/flux2_klein_4b_t2i.json",
    "workflow_corpus/official/video/wan_t2v.json",
    "workflow_corpus/official/video/wan_i2v.json",
    "workflow_corpus/official/edit/qwen_image_edit.json",
    "workflow_corpus/official/edit/flux2_klein_4b_image_edit_base.json",
]

# The T12 documented allowlist (docs/corpus_parity_allowlist.md, "Complete allowlist
# index"). The parity gate is permitted to skip these. For workflow_corpus/**/*.json
# the relevant entries are the two manifests (NOT_A_WORKFLOW) and the one corpus JSON
# with a confirmed parity failure (PARITY_FAIL_TOPOLOGY). The remaining 45 allowlist
# paths are ready_templates/*.py (widget-shape pin/refusal, NAMED_CAG_DIVERGENCE,
# SCHEMA_LESS), which this corpus-glob gate does not enumerate.
_PARITY_ALLOWLIST = {
    "workflow_corpus/manifests/coverage.json",
    "workflow_corpus/manifests/ready_regeneration.json",
    "workflow_corpus/official/image/qwen_image_2512.json",
}


def _corpus_json_paths() -> list[str]:
    return sorted(glob.glob("workflow_corpus/**/*.json", recursive=True))


def _wf_from_json(path: str) -> VibeWorkflow:
    with open(path) as handle:
        raw = json.load(handle)
    return convert_to_vibe_format(raw, source_path=path)


def _local_provider():
    from vibecomfy.schema import get_schema_provider

    return get_schema_provider("local")


def _wf(wf_id: str = "test") -> VibeWorkflow:
    return VibeWorkflow(wf_id, WorkflowSource(wf_id))


def _ksampler(node_id: str = "1") -> VibeNode:
    return VibeNode(
        node_id,
        "KSampler",
        inputs={
            "seed": 5,
            "steps": 20,
            "cfg": 7.0,
            "sampler_name": "euler",
            "scheduler": "normal",
            "denoise": 1.0,
        },
    )


# ---------------------------------------------------------------------------
# (a) Offline parity gate — starter set + full corpus minus allowlist
# ---------------------------------------------------------------------------


@pytest.mark.parametrize("path", _STARTER_SET)
def test_parity_starter_set(path: str) -> None:
    """>=5 starter workflows spanning image/video/edit pass the offline parity gate."""
    wf = _wf_from_json(path)
    ok, diffs = offline_emitter_normalizer_self_consistency_check(wf, schema_provider=_local_provider())
    assert ok, f"{path}: {diffs[:5]}"


def test_parity_starter_set_spans_media() -> None:
    """Guard: the starter set must actually span image, video, and edit media."""
    medias = {p.split("/")[2] for p in _STARTER_SET}
    assert {"image", "video", "edit"} <= medias
    assert len(_STARTER_SET) >= 5


def test_allowlist_documents_widget_shape_taxonomy() -> None:
    """The parity allowlist must describe dynamic overflow as typed pin/refusal."""
    text = Path("docs/corpus_parity_allowlist.md").read_text(encoding="utf-8")

    assert "PIN_OPAQUE_WIDGET_SHAPE" in text
    assert "REFUSED_WIDGET_SHAPE" in text
    assert "Power Lora Loader (rgthree)" in text
    assert "widget_shape_verdict == \"safe_to_regenerate\"" in text
    assert "Ready templates — EMIT_ERROR" not in text
    assert "stale `widget_schema.py` counts | 10 ready templates" not in text


@pytest.mark.parametrize(
    "path", [p for p in _corpus_json_paths() if p not in _PARITY_ALLOWLIST]
)
def test_parity_corpus_minus_allowlist(path: str) -> None:
    """Every workflow_corpus JSON NOT on the T12 allowlist passes the parity gate."""
    wf = _wf_from_json(path)
    with warnings.catch_warnings():
        warnings.simplefilter("ignore")
        ok, diffs = offline_emitter_normalizer_self_consistency_check(wf, schema_provider=_local_provider())
    assert ok, f"{path}: {diffs[:5]}"


def test_parity_gate_never_imports_comfy() -> None:
    """The offline parity gate must never import a ComfyUI module."""
    import builtins

    wf = _wf_from_json("workflow_corpus/official/video/wan_t2v.json")
    provider = _local_provider()
    real_import = builtins.__import__

    def _poisoned(name, *args, **kwargs):
        if name == "comfy" or name.startswith("comfy."):
            raise AssertionError(f"offline parity gate imported ComfyUI module {name!r}")
        return real_import(name, *args, **kwargs)

    builtins.__import__ = _poisoned
    try:
        ok, diffs = offline_emitter_normalizer_self_consistency_check(wf, schema_provider=provider)
    finally:
        builtins.__import__ = real_import
    assert ok, diffs[:5]


# ---------------------------------------------------------------------------
# (b) Structural validation — corpus-wide (schema-less skipped + reported)
# ---------------------------------------------------------------------------


@pytest.mark.parametrize(
    "path",
    [
        p
        for p in _corpus_json_paths()
        if p not in {"workflow_corpus/manifests/coverage.json",
                     "workflow_corpus/manifests/ready_regeneration.json"}
    ],
)
def test_structural_validation_corpus_wide(path: str) -> None:
    """Structural validation is green for every emittable corpus workflow; schema-less
    nodes are skipped and recorded rather than asserted."""
    wf = _wf_from_json(path)
    provider = _local_provider()
    with warnings.catch_warnings():
        warnings.simplefilter("ignore")
        ui = emit_ui_json(wf, schema_provider=provider)
    report = structural_validate(ui, schema_provider=provider)
    assert report["ok"], f"{path}: {report['errors'][:5]}"
    # Schema-less skips must be reported, not silently dropped.
    for skip in report["skipped"]:
        assert "reason" in skip and "class_type" in skip


def test_structural_validation_reports_schema_less_skip() -> None:
    """A schema-less node's slot/widget assertions are skipped AND recorded."""
    wf = _wf()
    wf.nodes["1"] = VibeNode("1", "TotallyUnknownNode", widgets={"widget_0": 1, "widget_1": 2})
    provider = _local_provider()
    with warnings.catch_warnings():
        warnings.simplefilter("ignore")
        ui = emit_ui_json(wf, schema_provider=provider)
    report = structural_validate(ui, schema_provider=provider)
    assert report["ok"] is True
    assert any(s["class_type"] == "TotallyUnknownNode" for s in report["skipped"])


# ---------------------------------------------------------------------------
# (c) uid or display-id present on every node (ir_node_id demoted in M5)
# ---------------------------------------------------------------------------


@pytest.mark.parametrize("path", _STARTER_SET)
def test_uid_or_display_id_present_on_every_node(path: str) -> None:
    """Every emitted node carries vibecomfy_uid (when uid was captured) or vibecomfy_id
    (always), plus the litegraph S&R type key.  ir_node_id must NOT appear."""
    wf = _wf_from_json(path)
    with warnings.catch_warnings():
        warnings.simplefilter("ignore")
        ui = emit_ui_json(wf, schema_provider=_local_provider())
    assert ui["nodes"], f"{path}: no nodes emitted"
    for node in ui["nodes"]:
        props = node["properties"]
        assert "ir_node_id" not in props, (
            f"{path}: node {node['id']} still emits ir_node_id (demoted in M5)"
        )
        has_key = "vibecomfy_uid" in props or "vibecomfy_id" in props
        assert has_key, (
            f"{path}: node {node['id']} missing both vibecomfy_uid and vibecomfy_id"
        )
        assert props["Node name for S&R"] == node["type"]


# ---------------------------------------------------------------------------
# (d) Same-IR -> byte-identical JSON on re-emit
# ---------------------------------------------------------------------------


@pytest.mark.parametrize("path", _STARTER_SET)
def test_same_ir_byte_identical_reemit(path: str) -> None:
    """Re-emitting the same IR yields byte-identical JSON."""
    wf = _wf_from_json(path)
    provider = _local_provider()
    with warnings.catch_warnings():
        warnings.simplefilter("ignore")
        first = json.dumps(emit_ui_json(wf, schema_provider=provider), indent=2, sort_keys=True)
        second = json.dumps(emit_ui_json(wf, schema_provider=provider), indent=2, sort_keys=True)
    assert first == second


# ---------------------------------------------------------------------------
# (e) KSampler None-widget round-trip alignment (Step 7.2)
# ---------------------------------------------------------------------------


def test_ksampler_none_widget_roundtrip_alignment() -> None:
    """The KSampler None-named slot (control_after_generate) must not misalign later
    widget positions; widgets_values stay aligned to the compacted schema ordering and
    parity holds with a retained control value."""
    wf = _wf()
    node = _ksampler()
    node.metadata["control_after_generate"] = "randomize"
    wf.nodes["1"] = node
    wf.nodes["2"] = VibeNode("2", "SaveImage")
    wf.connect("1.0", "2.images")

    ui = emit_ui_json(wf)
    ksamp = next(n for n in ui["nodes"] if n["type"] == "KSampler")
    assert ksamp["widgets_values"] == [5, 20, 7.0, "euler", "normal", 1.0]

    ok, diffs = offline_emitter_normalizer_self_consistency_check(wf)
    assert ok, diffs[:5]


# ---------------------------------------------------------------------------
# Schema-less: warn-and-emit by default; hard-fail under strict
# ---------------------------------------------------------------------------


def test_schema_less_warns_and_emits_by_default() -> None:
    """Default (non-strict): schema-less node emits best-effort and warns."""
    wf = _wf()
    wf.nodes["1"] = VibeNode("1", "DefinitelyUnknownNode")
    with warnings.catch_warnings(record=True) as caught:
        warnings.simplefilter("always")
        ui = emit_ui_json(wf, schema_provider=None)
    assert any("schema-less" in str(w.message) for w in caught)
    assert len(ui["nodes"]) == 1  # still emitted


def test_schema_less_hard_fails_under_strict() -> None:
    """strict=True turns a schema-less node into a hard failure."""
    wf = _wf()
    wf.nodes["1"] = VibeNode("1", "DefinitelyUnknownNode")
    with pytest.raises(ValueError, match="strict=True"):
        emit_ui_json(wf, schema_provider=None, strict=True)
