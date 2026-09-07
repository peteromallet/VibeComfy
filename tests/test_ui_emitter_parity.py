"""UI emitter parity against canonical Python, with honest native-boundary negatives.

Python ready templates are the semantic authority. Source JSON is a mapped
companion: ingestible UI graphs keep a positive from_ui proof, while native
``-10``/``-20`` / ``inputNode``/``outputNode`` graphs fail closed with
``unsupported_boundary_encoding`` instead of being simplified into a fake
positive.
"""
from __future__ import annotations

import glob
import json
import warnings
from collections.abc import Mapping
from pathlib import Path

import pytest

from vibecomfy.cli_loader import load_bundle
from vibecomfy.ingest.normalize import from_ui
from vibecomfy.porting.emit.ui import (
    emit_ui_json,
    offline_emitter_normalizer_self_consistency_check,
    structural_validate,
)
from vibecomfy.workflow import VibeNode, VibeWorkflow, WorkflowSource


_STARTER_SET = [
    "image/z_image",
    "image/flux2_klein_4b_t2i",
    "video/wan_t2v",
    "video/wan_i2v",
    "edit/qwen_image_edit",
    "edit/flux2_klein_4b_image_edit_base",
]

_READY_PARITY_SET = [
    "edit/flux2_klein_4b_image_edit_base",
    "edit/flux2_klein_4b_image_edit_distilled",
    "edit/flux2_klein_9b_image_edit_base",
    "edit/flux2_klein_9b_image_edit_distilled",
    "edit/qwen_image_edit",
    "image/basic_image_upscale",
    "image/flux2_klein_4b_t2i",
    "image/flux2_klein_9b_gguf_t2i",
    "image/flux2_klein_9b_t2i",
    "image/qwen_image_2512",
    "image/z_image",
    "image/z_image_img2img",
    "video/wan_i2v",
    "video/wan_t2v",
]

_INGESTIBLE_OFFICIAL_SOURCE_UI = [
    "ready_templates/sources/official/video/wan_t2v.json",
    "ready_templates/sources/official/video/wan_i2v.json",
]

_PARITY_ALLOWLIST = {
    "ready_templates/sources/manifests/coverage.json",
    "ready_templates/sources/manifests/ready_regeneration.json",
    "ready_templates/sources/official/image/qwen_image_2512.json",
}

_NATIVE_MARKERS = {-10, -20, "-10", "-20"}


def _corpus_json_paths() -> list[str]:
    return sorted(glob.glob("ready_templates/sources/**/*.json", recursive=True))


def _contains_native_boundary(value: object) -> bool:
    if isinstance(value, Mapping):
        if "inputNode" in value or "outputNode" in value:
            return True
        return any(_contains_native_boundary(item) for item in value.values())
    if isinstance(value, (list, tuple)):
        return any(_contains_native_boundary(item) for item in value)
    return value in _NATIVE_MARKERS


def _native_source_ui_paths() -> list[str]:
    paths: list[str] = []
    for path in _corpus_json_paths():
        if path in _PARITY_ALLOWLIST:
            continue
        raw = json.loads(Path(path).read_text(encoding="utf-8"))
        if not isinstance(raw, Mapping):
            continue
        if not isinstance(raw.get("nodes"), list):
            continue
        if _contains_native_boundary(raw):
            paths.append(path)
    return paths


def _local_provider():
    from vibecomfy.schema import get_schema_provider

    return get_schema_provider("local")


def _wf_from_ready(template_id: str) -> VibeWorkflow:
    return load_bundle(template_id).workflow


def _wf_from_json(path: str) -> VibeWorkflow:
    with open(path) as handle:
        raw = json.load(handle)
    return from_ui(raw, source_path=path)


def _source_path_from_ready(template_id: str) -> str | None:
    from vibecomfy.commands.validate import _source_workflow_from_template
    from vibecomfy.registry.ready import ready_template_discovery, resolve_ready_template

    record = resolve_ready_template(template_id, ready_template_discovery())
    return _source_workflow_from_template(Path(record.path).read_text(encoding="utf-8"))


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


@pytest.mark.parametrize("template_id", _STARTER_SET)
def test_parity_starter_set(template_id: str) -> None:
    """Starter ready templates spanning image/video/edit pass offline UI parity."""
    wf = _wf_from_ready(template_id)
    ok, diffs = offline_emitter_normalizer_self_consistency_check(wf, schema_provider=_local_provider())
    assert ok, f"{template_id}: {diffs[:5]}"


def test_parity_starter_set_spans_media() -> None:
    """Guard: the starter set must actually span image, video, and edit media."""
    medias = {template_id.split("/", 1)[0] for template_id in _STARTER_SET}
    assert {"image", "video", "edit"} <= medias
    assert len(_STARTER_SET) >= 5


def test_allowlist_documents_widget_shape_taxonomy() -> None:
    """The parity allowlist must describe dynamic overflow as typed pin/refusal."""
    text = Path("docs/templates/corpus_parity_allowlist.md").read_text(encoding="utf-8")

    assert "PIN_OPAQUE_WIDGET_SHAPE" in text
    assert "REFUSED_WIDGET_SHAPE" in text
    assert "Power Lora Loader (rgthree)" in text
    assert "widget_shape_verdict == \"safe_to_regenerate\"" in text
    assert "Ready templates — EMIT_ERROR" not in text
    assert "stale `widget_schema.py` counts | 10 ready templates" not in text


@pytest.mark.parametrize("template_id", _READY_PARITY_SET)
def test_parity_ready_python_corpus(template_id: str) -> None:
    """Canonical ready Python is the emit/compile parity corpus."""
    wf = _wf_from_ready(template_id)
    with warnings.catch_warnings():
        warnings.simplefilter("ignore")
        ok, diffs = offline_emitter_normalizer_self_consistency_check(wf, schema_provider=_local_provider())
    assert ok, f"{template_id}: {diffs[:5]}"


@pytest.mark.parametrize("template_id", _STARTER_SET)
def test_ready_python_mapped_source_is_native_negative_or_ingestible_positive(template_id: str) -> None:
    """Mapped source JSON is not simplified: native sentinels fail closed."""
    wf = _wf_from_ready(template_id)
    ok, diffs = offline_emitter_normalizer_self_consistency_check(wf, schema_provider=_local_provider())
    assert ok, f"{template_id}: {diffs[:5]}"
    source_path = _source_path_from_ready(template_id)
    assert source_path, f"{template_id}: ready template is missing mapped source JSON provenance"
    raw = json.loads(Path(source_path).read_text(encoding="utf-8"))
    if _contains_native_boundary(raw):
        with pytest.raises(ValueError, match="unsupported_boundary_encoding"):
            from_ui(raw, source_path=source_path)
        return
    source_wf = from_ui(raw, source_path=source_path)
    with warnings.catch_warnings():
        warnings.simplefilter("ignore")
        ok, diffs = offline_emitter_normalizer_self_consistency_check(
            source_wf, schema_provider=_local_provider()
        )
    assert ok, f"{source_path}: {diffs[:5]}"


@pytest.mark.parametrize("path", _INGESTIBLE_OFFICIAL_SOURCE_UI)
def test_parity_ingestible_official_source_ui(path: str) -> None:
    """Official source UI without native sentinels still has a positive from_ui proof."""
    wf = _wf_from_json(path)
    with warnings.catch_warnings():
        warnings.simplefilter("ignore")
        ok, diffs = offline_emitter_normalizer_self_consistency_check(wf, schema_provider=_local_provider())
    assert ok, f"{path}: {diffs[:5]}"


@pytest.mark.parametrize(
    "path",
    [path for path in _native_source_ui_paths() if "/official/" in path],
)
def test_official_native_source_ui_is_unsupported_boundary(path: str) -> None:
    """Official mapped sources with native -10/-20 fail closed at the T17 boundary."""
    raw = json.loads(Path(path).read_text(encoding="utf-8"))
    with pytest.raises(ValueError, match="unsupported_boundary_encoding"):
        from_ui(raw, source_path=path)


@pytest.mark.parametrize(
    "path",
    [path for path in _native_source_ui_paths() if "/official/" not in path],
)
def test_native_source_ui_fails_closed(path: str) -> None:
    """Native-marked source graphs never become a from_ui positive."""
    raw = json.loads(Path(path).read_text(encoding="utf-8"))
    with pytest.raises(ValueError) as excinfo:
        from_ui(raw, source_path=path)
    message = str(excinfo.value)
    assert any(
        token in message
        for token in (
            "unsupported_boundary_encoding",
            "unknown endpoint",
            "ambiguous virtual-wire",
        )
    ), message


def test_parity_gate_never_imports_comfy() -> None:
    """The offline parity gate must never import a ComfyUI module."""
    import builtins

    wf = _wf_from_ready("video/wan_t2v")
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


@pytest.mark.parametrize("template_id", _READY_PARITY_SET)
def test_structural_validation_ready_python(template_id: str) -> None:
    """Structural validation is green for canonical ready Python graphs."""
    wf = _wf_from_ready(template_id)
    provider = _local_provider()
    with warnings.catch_warnings():
        warnings.simplefilter("ignore")
        ui = emit_ui_json(wf, schema_provider=provider)
    report = structural_validate(ui, schema_provider=provider)
    assert report["ok"], f"{template_id}: {report['errors'][:5]}"
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


@pytest.mark.parametrize("template_id", _STARTER_SET)
def test_uid_or_display_id_present_on_every_node(template_id: str) -> None:
    """Every emitted node carries vibecomfy_uid or vibecomfy_id, plus S&R type."""
    wf = _wf_from_ready(template_id)
    with warnings.catch_warnings():
        warnings.simplefilter("ignore")
        ui = emit_ui_json(wf, schema_provider=_local_provider())
    assert ui["nodes"], f"{template_id}: no nodes emitted"
    for node in ui["nodes"]:
        props = node["properties"]
        assert "ir_node_id" not in props, (
            f"{template_id}: node {node['id']} still emits ir_node_id (demoted in M5)"
        )
        has_key = "vibecomfy_uid" in props or "vibecomfy_id" in props
        assert has_key, (
            f"{template_id}: node {node['id']} missing both vibecomfy_uid and vibecomfy_id"
        )
        assert props["Node name for S&R"] == node["type"]


@pytest.mark.parametrize("template_id", _STARTER_SET)
def test_same_ir_byte_identical_reemit(template_id: str) -> None:
    """Re-emitting the same IR yields byte-identical JSON."""
    wf = _wf_from_ready(template_id)
    provider = _local_provider()
    with warnings.catch_warnings():
        warnings.simplefilter("ignore")
        first = json.dumps(emit_ui_json(wf, schema_provider=provider), indent=2, sort_keys=True)
        second = json.dumps(emit_ui_json(wf, schema_provider=provider), indent=2, sort_keys=True)
    assert first == second


def test_ksampler_none_widget_roundtrip_alignment() -> None:
    """Retained control_after_generate stays in native order and does not slide later widgets."""
    wf = _wf()
    node = _ksampler()
    node.metadata["control_after_generate"] = "randomize"
    wf.nodes["1"] = node
    wf.nodes["2"] = VibeNode("2", "SaveImage")
    wf.connect("1.0", "2.images")

    ui = emit_ui_json(wf)
    ksamp = next(n for n in ui["nodes"] if n["type"] == "KSampler")
    assert ksamp["widgets_values"] == [5, "randomize", 20, 7.0, "euler", "normal", 1.0]

    ok, diffs = offline_emitter_normalizer_self_consistency_check(wf)
    assert ok, diffs[:5]


def test_schema_less_warns_and_emits_by_default() -> None:
    """Default (non-strict): schema-less node emits best-effort and warns."""
    wf = _wf()
    wf.nodes["1"] = VibeNode("1", "DefinitelyUnknownNode")
    with warnings.catch_warnings(record=True) as caught:
        warnings.simplefilter("always")
        ui = emit_ui_json(wf, schema_provider=None)
    assert any("schema-less" in str(w.message) for w in caught)
    assert len(ui["nodes"]) == 1


def test_schema_less_hard_fails_under_strict() -> None:
    """strict=True turns a schema-less node into a hard failure."""
    wf = _wf()
    wf.nodes["1"] = VibeNode("1", "DefinitelyUnknownNode")
    with pytest.raises(ValueError, match="strict=True"):
        emit_ui_json(wf, schema_provider=None, strict=True)
