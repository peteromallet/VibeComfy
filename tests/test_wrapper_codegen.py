"""Behavioral tests for the canonical public wrapper renderer."""
from __future__ import annotations

import hashlib
import importlib
import inspect
from datetime import datetime, timezone
from pathlib import Path

import pytest

from vibecomfy.porting.wrappers import codegen as wc
from vibecomfy.porting.wrappers.discovery import ClassSpec, InputFieldSpec


def _make_simple_spec(class_type: str = "SimpleSampler") -> ClassSpec:
    return ClassSpec(
        pack_slug="demo-pack",
        class_type=class_type,
        inputs={
            "model": InputFieldSpec("model", "MODEL", required=True),
            "seed": InputFieldSpec("seed", "INT", required=True, default=42, has_default=True),
            "mode": InputFieldSpec("mode", "COMBO", required=True, default="alpha", has_default=True, options=("alpha", "beta")),
            "extra": InputFieldSpec("extra", "STRING", required=False, default="hi", has_default=True),
        },
        outputs=("latent",),
        output_types=("LATENT",),
        category="test/category",
        display_name="Simple Sampler",
        source_provenance="object_info cache demo-pack@v1.json sha256:deadbeef",
    )


def test_render_is_deterministic_even_with_different_timestamps(tmp_path: Path) -> None:
    spec = _make_simple_spec()
    a = wc.render_pack("demo-pack", [spec], out_dir=tmp_path, timestamp=datetime(2024, 1, 1, tzinfo=timezone.utc))
    b = wc.render_pack("demo-pack", [spec], out_dir=tmp_path, timestamp=datetime(2034, 1, 1, tzinfo=timezone.utc))
    assert a.source_text == b.source_text
    assert a.source_sha256 == b.source_sha256
    assert "generated_at: 1970-01-01T00:00:00+00:00" in a.source_text
    assert hashlib.sha256(a.source_text.encode()).hexdigest()


def test_render_header_contains_marker_and_sha(tmp_path: Path) -> None:
    result = wc.render_pack("demo-pack", [_make_simple_spec()], out_dir=tmp_path)
    parsed = wc.parse_generated_header(result.source_text)
    assert parsed is not None
    assert parsed["pack"] == "demo-pack"
    assert parsed["source_sha256"] == result.source_sha256
    assert parsed["generator_version"] == wc.GENERATOR_VERSION
    assert parsed["classes"] == "1"
    assert "source: object_info cache demo-pack" in result.source_text


def test_parse_generated_header_returns_none_for_handwritten() -> None:
    assert wc.parse_generated_header('"""hand-written module"""\n\nx = 1\n') is None


def test_render_imports_and_discovery_metadata(tmp_path: Path, monkeypatch: pytest.MonkeyPatch) -> None:
    out_dir = tmp_path / "nodes"
    out_dir.mkdir()
    (out_dir / "__init__.py").write_text("")
    result = wc.render_pack("demo-pack", [_make_simple_spec()], out_dir=out_dir)
    result.module_path.write_text(result.source_text)
    monkeypatch.syspath_prepend(str(tmp_path))
    mod = importlib.import_module("nodes." + result.module_path.stem)
    assert mod.__all__ == ["SimpleSampler"]
    assert mod.__vibecomfy_class_types__ == {"SimpleSampler": "SimpleSampler"}
    assert callable(mod.SimpleSampler)
    assert not hasattr(mod.SimpleSampler, "add")


def test_render_round_trip_to_public_node(tmp_path: Path, monkeypatch: pytest.MonkeyPatch) -> None:
    out_dir = tmp_path / "nodes"
    out_dir.mkdir()
    (out_dir / "__init__.py").write_text("")
    result = wc.render_pack("demo-pack", [_make_simple_spec()], out_dir=out_dir)
    result.module_path.write_text(result.source_text)
    monkeypatch.syspath_prepend(str(tmp_path))
    mod = importlib.import_module("nodes." + result.module_path.stem)
    from vibecomfy.workflow import VibeWorkflow, WorkflowSource

    wf = VibeWorkflow("rt", WorkflowSource(id="rt", path="rt.py", source_type="inline"))
    builder = mod.SimpleSampler(wf, model=None, seed=7, mode="beta", _id="node-1", _mode="raw", _uid="u1", custom="x")
    assert builder.node.id == "node-1"
    assert wf.nodes["node-1"].class_type == "SimpleSampler"
    assert wf.nodes["node-1"].inputs["seed"] == 7
    assert wf.nodes["node-1"].mode != 0
    assert wf.nodes["node-1"].uid == "u1"
    assert wf.nodes["node-1"].inputs["custom"] == "x"
    assert inspect.signature(mod.SimpleSampler).parameters["mode"].annotation == "Literal['alpha', 'beta'] | _Omitted"


def test_identifier_unsafe_names_and_unknown_types_compile(tmp_path: Path) -> None:
    spec = ClassSpec(
        pack_slug="weird-pack",
        class_type="WeirdNode",
        inputs={
            "double_blocks.0.": InputFieldSpec("double_blocks.0.", "DYNAMIC_SOCKET", required=False),
            "normal": InputFieldSpec("normal", "INT", required=False),
            "class": InputFieldSpec("class", "STRING", required=False),
        },
        outputs=("OUT",),
        output_types=("FLOAT",),
        source_provenance="test",
    )
    result = wc.render_pack("weird-pack", [spec], out_dir=tmp_path)
    compile(result.source_text, str(result.module_path), "exec")
    assert "double_blocks_0" in result.source_text
    assert "_kwargs['double_blocks.0.']" in result.source_text
    assert "Any | _Omitted" in result.source_text
    assert "class_" in result.source_text


def test_class_name_collisions_are_retained_with_suffix() -> None:
    result = wc.render_pack("dup", [_make_simple_spec("Foo (bar)"), _make_simple_spec("Foo_bar")], out_dir=Path("/tmp"))
    assert result.skipped_classes == ()
    assert result.class_count == 2
    assert "def Foo_bar(" in result.source_text
    assert "def Foo_bar_2(" in result.source_text
    assert "'Foo_bar_2': 'Foo_bar'" in result.source_text


def test_schema_change_changes_source_sha() -> None:
    a = _make_simple_spec()
    b = _make_simple_spec()
    b = ClassSpec(**{**b.__dict__, "output_types": ("IMAGE",)}) if hasattr(b, "__dict__") else ClassSpec(
        pack_slug=b.pack_slug, class_type=b.class_type, inputs=b.inputs, outputs=b.outputs,
        output_types=("IMAGE",), category=b.category, display_name=b.display_name,
        source_provenance=b.source_provenance,
    )
    assert wc.render_pack("demo-pack", [a], out_dir=Path("/tmp")).source_sha256 != wc.render_pack("demo-pack", [b], out_dir=Path("/tmp")).source_sha256


def test_widget_schema_render_lists_non_link_fields() -> None:
    text = wc.render_widget_schema([_make_simple_spec()])
    assert "'SimpleSampler'" in text
    assert "'seed'" in text
    assert "'model'" not in text


def test_known_output_has_no_private_or_class_abi() -> None:
    text = wc.render_pack("demo-pack", [_make_simple_spec()], out_dir=Path("/tmp")).source_text
    for forbidden in (".add(", "class SimpleSampler", "_NodeBuilder", "wf._node"):
        assert forbidden not in text
