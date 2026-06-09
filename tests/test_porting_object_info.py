"""Deterministic tests for object-info serializer, consumer, and widget-order reconciliation.

No ComfyUI / RunPod / network required.
"""

from __future__ import annotations

import json
import warnings
from pathlib import Path
from unittest import mock

import pytest

from vibecomfy.node_packs_lockfile import compute_schema_hash
from vibecomfy.porting.object_info.consume import CACHE_DIR as _PROD_CACHE_DIR, effective_widget_names_for_class
from vibecomfy.porting.object_info.serialize import CacheIdentity, build_cache, pack_key_from_module, refresh_from_source
from vibecomfy.porting.widget_schema import WIDGET_SCHEMA


# ---------------------------------------------------------------------------
# Minimal object_info fixtures
# ---------------------------------------------------------------------------

_SAMPLE_OBJECT_INFO: dict = {
    "LTX2_NAG": {
        "python_module": "ComfyUI-KJNodes.nodes.ltxv_nodes",
        "name": "LTX2_NAG",
        "display_name": "NAG",
        "description": "Neural Adaptive Guidance for LTX2",
        "category": "LTXVideo/patches",
        "function": "patch",
        "input": {
            "required": {
                "model": ["MODEL"],
                "nag_scale": ["FLOAT", {"default": 11.0, "min": 0.5, "max": 50.0, "step": 0.25}],
                "nag_alpha": ["FLOAT", {"default": 0.25, "min": 0.05, "max": 4.0, "step": 0.01}],
                "nag_tau": ["FLOAT", {"default": 2.5, "min": 0.5, "max": 20.0, "step": 0.01}],
                "apply_to_all": ["BOOLEAN", {"default": True}],
            },
        },
        "input_order": {
            "required": ["model", "nag_scale", "nag_alpha", "nag_tau", "apply_to_all"],
            "optional": [],
        },
        "output": ["MODEL"],
        "output_name": ["MODEL"],
        "output_is_list": [False],
    },
    "PrimitiveString": {
        "python_module": "comfy_extras.nodes_primitives",
        "name": "PrimitiveString",
        "category": "",
        "function": "string",
        "display_name": "PrimitiveString",
        "description": "",
        "input": {
            "required": {"value": ["STRING", {"multiline": "", "default": ""}]},
        },
        "input_order": {"required": ["value"], "optional": []},
        "output": ["STRING"],
        "output_name": ["STRING"],
        "output_is_list": [False],
    },
    "SomeUnknownClass": {
        "python_module": "ComfyUI-KJNodes.nodes.unknown",
        "name": "SomeUnknownClass",
        "display_name": "Unknown",
        "description": "",
        "category": "misc",
        "function": "do_thing",
        "input": {
            "required": {
                "model": ["MODEL"],
                "widget_0": ["INT", {"default": 5}],
                "widget_1": ["FLOAT", {"default": 0.5}],
            },
            "optional": {"widget_2": ["STRING", {"default": "hello"}]},
        },
        "input_order": {
            "required": ["model", "widget_0", "widget_1"],
            "optional": ["widget_2"],
        },
        "output": ["MODEL"],
        "output_name": ["patched_model"],
        "output_is_list": [False],
    },
}


def _object_info_entry(
    *,
    python_module: str,
    name: str,
    output_names: list[str],
) -> dict:
    return {
        "python_module": python_module,
        "name": name,
        "display_name": name,
        "description": "",
        "category": "test",
        "function": "run",
        "input": {"required": {}, "optional": {}},
        "input_order": {"required": [], "optional": []},
        "output": output_names,
        "output_name": output_names,
        "output_is_list": [False] * len(output_names),
    }


def _build_temp_cache(tmp_path: Path) -> Path:
    """Build object_info cache in *tmp_path* and return the cache root."""
    source = tmp_path / "object_info.json"
    source.write_text(json.dumps(_SAMPLE_OBJECT_INFO), encoding="utf-8")
    cache_root = tmp_path / "object_info"
    build_cache(str(source), version="test", cache_dir=str(cache_root))
    return cache_root


# ---------------------------------------------------------------------------
# pack_key_from_module
# ---------------------------------------------------------------------------


@pytest.mark.parametrize(
    "python_module, expected",
    [
        ("ComfyUI-KJNodes.nodes.ltxv_nodes", "ComfyUI-KJNodes"),
        ("ComfyUI-LTXVideo", "ComfyUI-LTXVideo"),
        ("custom_nodes.some_pack.nodes", "custom_nodes.some_pack"),
        ("nodes", "nodes"),
        (".", "comfy_core"),
        ("", "comfy_core"),
    ],
)
def test_pack_key_from_module(python_module: str, expected: str) -> None:
    assert pack_key_from_module(python_module) == expected


# ---------------------------------------------------------------------------
# build_cache (serialize)
# ---------------------------------------------------------------------------


def test_build_cache_creates_per_pack_files_and_index(tmp_path: Path) -> None:
    source = tmp_path / "object_info.json"
    source.write_text(json.dumps(_SAMPLE_OBJECT_INFO), encoding="utf-8")
    cache_root = tmp_path / "cache_obj"

    class_count, pack_count = build_cache(str(source), version="test", cache_dir=str(cache_root))

    assert class_count == 3
    assert pack_count == 2  # ComfyUI-KJNodes + comfy_extras

    # Check index.json exists
    index_file = cache_root / "index.json"
    assert index_file.is_file()
    index = json.loads(index_file.read_text())
    assert index["LTX2_NAG"] == "ComfyUI-KJNodes@test.json"
    assert index["SomeUnknownClass"] == "ComfyUI-KJNodes@test.json"
    assert index["PrimitiveString"] == "comfy_extras@test.json"

    # Check per-pack files exist and are valid JSON
    pack_file = cache_root / "ComfyUI-KJNodes@test.json"
    assert pack_file.is_file()
    pack_data = json.loads(pack_file.read_text())
    assert "LTX2_NAG" in pack_data
    assert "SomeUnknownClass" in pack_data
    assert pack_data["LTX2_NAG"]["object_info_widget_order"] == [
        None,  # model is MODEL (excluded)
        "nag_scale",
        "nag_alpha",
        "nag_tau",
        "apply_to_all",
    ]

    pack_file2 = cache_root / "comfy_extras@test.json"
    assert pack_file2.is_file()
    pack_data2 = json.loads(pack_file2.read_text())
    assert "PrimitiveString" in pack_data2


def test_build_cache_is_deterministic(tmp_path: Path) -> None:
    """Running build_cache twice with the same input must produce identical output."""
    source = tmp_path / "object_info.json"
    source.write_text(json.dumps(_SAMPLE_OBJECT_INFO), encoding="utf-8")

    cache1 = tmp_path / "cache1"
    cache2 = tmp_path / "cache2"

    build_cache(str(source), version="test", cache_dir=str(cache1))
    build_cache(str(source), version="test", cache_dir=str(cache2))

    idx1 = json.loads((cache1 / "index.json").read_text())
    idx2 = json.loads((cache2 / "index.json").read_text())
    assert idx1 == idx2

    for name in idx1.values():
        assert json.loads((cache1 / name).read_text()) == json.loads((cache2 / name).read_text())


def test_build_cache_writes_identity_and_canonical_schema_hash_metadata(tmp_path: Path) -> None:
    source = tmp_path / "object_info.json"
    source.write_text(json.dumps({"LTX2_NAG": _SAMPLE_OBJECT_INFO["LTX2_NAG"]}), encoding="utf-8")
    cache_root = tmp_path / "cache_obj"

    build_cache(
        str(source),
        version="unused-version",
        cache_dir=str(cache_root),
        identity=CacheIdentity(
            pack_slug="ComfyUI-KJNodes",
            pack_version="2.0.0",
            git_commit="abc123",
            evidence_identity="runpod-snapshot-2026-06-09",
            source_kind="executed_object_info",
        ),
    )

    pack_data = json.loads((cache_root / "ComfyUI-KJNodes@unused-version.json").read_text(encoding="utf-8"))
    entry = pack_data["LTX2_NAG"]
    expected_hash = compute_schema_hash({"LTX2_NAG": _SAMPLE_OBJECT_INFO["LTX2_NAG"]})

    assert entry["pack"] == "ComfyUI-KJNodes"
    assert entry["pack_slug"] == "ComfyUI-KJNodes"
    assert entry["pack_version"] == "2.0.0"
    assert entry["git_commit"] == "abc123"
    assert entry["evidence_identity"] == "runpod-snapshot-2026-06-09"
    assert entry["source_kind"] == "executed_object_info"
    assert entry["schema_hash"] == expected_hash
    assert entry["class_schema_sha256"] == expected_hash


def test_build_cache_hash_uses_canonical_projection_not_source_bytes(tmp_path: Path) -> None:
    first = {
        "StableNode": _object_info_entry(
            python_module="nodes",
            name="StableNode",
            output_names=["IMAGE"],
        )
    }
    second = {
        "StableNode": {
            **first["StableNode"],
            "description": "changed prose outside the canonical schema projection",
            "display_name": "Changed Display Name",
        }
    }
    source1 = tmp_path / "first.json"
    source2 = tmp_path / "second.json"
    source1.write_text(json.dumps(first, sort_keys=False), encoding="utf-8")
    source2.write_text(json.dumps(second, sort_keys=True, indent=2), encoding="utf-8")
    cache1 = tmp_path / "cache1"
    cache2 = tmp_path / "cache2"

    build_cache(str(source1), version="v1", cache_dir=str(cache1))
    build_cache(str(source2), version="v2", cache_dir=str(cache2))

    entry1 = json.loads((cache1 / "nodes@v1.json").read_text(encoding="utf-8"))["StableNode"]
    entry2 = json.loads((cache2 / "nodes@v2.json").read_text(encoding="utf-8"))["StableNode"]
    expected_hash = compute_schema_hash(first)

    assert entry1["schema_hash"] == expected_hash
    assert entry2["schema_hash"] == expected_hash
    assert entry1["class_schema_sha256"] == entry2["class_schema_sha256"] == expected_hash


def test_build_cache_partial_refresh_preserves_cross_pack_and_same_pack_classes(tmp_path: Path) -> None:
    initial_source = tmp_path / "initial_object_info.json"
    initial_source.write_text(
        json.dumps(
            {
                "ComfyMathExpression": _object_info_entry(
                    python_module="nodes",
                    name="ComfyMathExpression",
                    output_names=["FLOAT", "INT"],
                ),
                "OtherCoreNode": _object_info_entry(
                    python_module="nodes",
                    name="OtherCoreNode",
                    output_names=["IMAGE"],
                ),
                "WanVideoModelLoader": _object_info_entry(
                    python_module="ComfyUI-WanVideoWrapper.nodes",
                    name="WanVideoModelLoader",
                    output_names=["MODEL"],
                ),
            }
        ),
        encoding="utf-8",
    )
    cache_root = tmp_path / "cache_obj"
    build_cache(str(initial_source), version="old", cache_dir=str(cache_root))

    partial_source = tmp_path / "partial_object_info.json"
    partial_source.write_text(
        json.dumps(
            {
                "ComfyMathExpression": _object_info_entry(
                    python_module="nodes",
                    name="ComfyMathExpression",
                    output_names=["FLOAT", "INT", "BOOL"],
                )
            }
        ),
        encoding="utf-8",
    )

    class_count, pack_count = build_cache(str(partial_source), version="new", cache_dir=str(cache_root))

    assert class_count == 1
    assert pack_count == 1
    index = json.loads((cache_root / "index.json").read_text(encoding="utf-8"))
    assert index["ComfyMathExpression"] == "nodes@new.json"
    assert index["OtherCoreNode"] == "nodes@new.json"
    assert index["WanVideoModelLoader"] == "ComfyUI-WanVideoWrapper@old.json"

    core_pack = json.loads((cache_root / "nodes@new.json").read_text(encoding="utf-8"))
    assert [output["name"] for output in core_pack["ComfyMathExpression"]["outputs"]] == [
        "FLOAT",
        "INT",
        "BOOL",
    ]
    assert "OtherCoreNode" in core_pack
    wan_pack = json.loads((cache_root / "ComfyUI-WanVideoWrapper@old.json").read_text(encoding="utf-8"))
    assert "WanVideoModelLoader" in wan_pack


def test_build_cache_full_pack_refresh_replaces_same_pack_mapping_but_preserves_other_packs(
    tmp_path: Path,
) -> None:
    initial_source = tmp_path / "initial_object_info.json"
    initial_source.write_text(
        json.dumps(
            {
                "ComfyMathExpression": _object_info_entry(
                    python_module="nodes",
                    name="ComfyMathExpression",
                    output_names=["FLOAT", "INT"],
                ),
                "RemovedCoreNode": _object_info_entry(
                    python_module="nodes",
                    name="RemovedCoreNode",
                    output_names=["IMAGE"],
                ),
                "WanVideoModelLoader": _object_info_entry(
                    python_module="ComfyUI-WanVideoWrapper.nodes",
                    name="WanVideoModelLoader",
                    output_names=["MODEL"],
                ),
            }
        ),
        encoding="utf-8",
    )
    cache_root = tmp_path / "cache_obj"
    build_cache(str(initial_source), version="old", cache_dir=str(cache_root))

    full_source = tmp_path / "full_object_info.json"
    full_source.write_text(
        json.dumps(
            {
                "ComfyMathExpression": _object_info_entry(
                    python_module="nodes",
                    name="ComfyMathExpression",
                    output_names=["FLOAT", "INT", "BOOL"],
                )
            }
        ),
        encoding="utf-8",
    )

    build_cache(
        str(full_source),
        version="new",
        cache_dir=str(cache_root),
        full_pack_refresh={"nodes"},
    )

    index = json.loads((cache_root / "index.json").read_text(encoding="utf-8"))
    assert index["ComfyMathExpression"] == "nodes@new.json"
    assert "RemovedCoreNode" not in index
    assert index["WanVideoModelLoader"] == "ComfyUI-WanVideoWrapper@old.json"

    core_pack = json.loads((cache_root / "nodes@new.json").read_text(encoding="utf-8"))
    assert sorted(core_pack) == ["ComfyMathExpression"]
    assert [output["name"] for output in core_pack["ComfyMathExpression"]["outputs"]] == [
        "FLOAT",
        "INT",
        "BOOL",
    ]


def test_refresh_from_source(tmp_path: Path) -> None:
    source = tmp_path / "object_info.json"
    source.write_text(json.dumps(_SAMPLE_OBJECT_INFO), encoding="utf-8")
    cache_root = tmp_path / "refresh_cache"

    result = refresh_from_source(str(source), cache_dir=str(cache_root))
    assert result["status"] == "ok"
    assert result["classes_indexed"] == 3
    assert result["packs_written"] == 2
    assert result["version"] == "runpod-snapshot"


# ---------------------------------------------------------------------------
# consume module (monkeypatched to use temp cache)
# ---------------------------------------------------------------------------


def test_get_class_returns_correct_data(tmp_path: Path, monkeypatch: pytest.MonkeyPatch) -> None:
    cache_root = _build_temp_cache(tmp_path)
    _patch_consume_paths(monkeypatch, cache_root)

    from vibecomfy.porting.object_info.consume import get_class as gc

    entry = gc("LTX2_NAG")
    assert entry is not None
    assert entry["pack"] == "ComfyUI-KJNodes"
    assert entry["pack_version"] == "test"
    assert entry["function"] == "patch"
    assert entry["object_info_widget_order"] == [None, "nag_scale", "nag_alpha", "nag_tau", "apply_to_all"]

    assert gc("NonExistentClass") is None


def test_object_info_widget_order_filters_link_sockets(tmp_path: Path, monkeypatch: pytest.MonkeyPatch) -> None:
    cache_root = _build_temp_cache(tmp_path)
    _patch_consume_paths(monkeypatch, cache_root)

    from vibecomfy.porting.object_info.consume import object_info_widget_order as oiwo

    order = oiwo("LTX2_NAG")
    assert order == [None, "nag_scale", "nag_alpha", "nag_tau", "apply_to_all"]

    order2 = oiwo("PrimitiveString")
    assert order2 == ["value"]

    assert oiwo("NonExistentClass") == []


def test_output_names_and_types(tmp_path: Path, monkeypatch: pytest.MonkeyPatch) -> None:
    cache_root = _build_temp_cache(tmp_path)
    _patch_consume_paths(monkeypatch, cache_root)

    from vibecomfy.porting.object_info.consume import output_names as on_, output_types as ot_

    assert on_("LTX2_NAG") == ["MODEL"]
    assert ot_("LTX2_NAG") == ["MODEL"]
    assert on_("PrimitiveString") == ["STRING"]
    assert on_("NonExistentClass") == []
    assert on_("SomeUnknownClass") == ["patched_model"]
    assert ot_("SomeUnknownClass") == ["MODEL"]


def test_list_classes_and_stats(tmp_path: Path, monkeypatch: pytest.MonkeyPatch) -> None:
    cache_root = _build_temp_cache(tmp_path)
    _patch_consume_paths(monkeypatch, cache_root)

    from vibecomfy.porting.object_info.consume import cache_stats, list_classes as lc

    classes = lc()
    assert isinstance(classes, list)
    assert len(classes) == 3
    assert classes == sorted(classes)
    assert "LTX2_NAG" in classes
    assert "PrimitiveString" in classes
    assert "SomeUnknownClass" in classes

    stats = cache_stats()
    assert stats["total_classes"] == 3
    assert stats["packs_cached"] == 0  # lazy — packs loaded on demand


def test_typed_arity_helpers_preserve_unknown_class_defaults(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch,
) -> None:
    cache_root = _build_temp_cache(tmp_path)
    _patch_consume_paths(monkeypatch, cache_root)

    from vibecomfy.porting.object_info.consume import (
        check_output_arity_consensus,
        class_is_known,
        require_class_output_count,
    )

    assert class_is_known("TotallyFakeClass") is False
    assert check_output_arity_consensus("TotallyFakeClass", ui_output_count=3) == 0
    assert require_class_output_count("TotallyFakeClass", ui_output_count=3) == 0


def test_typed_arity_helpers_raise_when_cache_has_fewer_outputs_than_ui(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch,
) -> None:
    cache_root = _build_temp_cache(tmp_path)
    _patch_consume_paths(monkeypatch, cache_root)

    from vibecomfy.errors import ArityDisagreementError
    from vibecomfy.porting.object_info.consume import require_class_output_count

    with pytest.raises(ArityDisagreementError) as exc:
        require_class_output_count("LTX2_NAG", ui_output_count=2)

    err = exc.value
    assert err.class_type == "LTX2_NAG"
    assert err.snapshot_pack == "ComfyUI-KJNodes"
    assert err.snapshot_version == "test"
    assert err.snapshot_output_count == 1
    assert err.ui_output_count == 2
    assert "LTX2_NAG" in str(err)
    assert "Refresh" in err.message


def test_typed_arity_helpers_warn_when_cache_has_more_outputs_than_ui(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch,
) -> None:
    cache_root = _build_temp_cache(tmp_path)
    _patch_consume_paths(monkeypatch, cache_root)

    from vibecomfy.porting.object_info.consume import check_output_arity_consensus

    with warnings.catch_warnings(record=True) as caught:
        warnings.simplefilter("always")
        count = check_output_arity_consensus("SomeUnknownClass", ui_output_count=0)

    assert count == 1
    assert len(caught) == 1
    assert "SomeUnknownClass" in str(caught[0].message)


def test_typed_arity_helpers_noop_when_cache_matches_ui(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch,
) -> None:
    cache_root = _build_temp_cache(tmp_path)
    _patch_consume_paths(monkeypatch, cache_root)

    from vibecomfy.porting.object_info.consume import check_output_arity_consensus

    with warnings.catch_warnings(record=True) as caught:
        warnings.simplefilter("always")
        count = check_output_arity_consensus("LTX2_NAG", ui_output_count=1)

    assert count == 1
    assert caught == []


def test_identity_lookup_preserves_legacy_class_lookup_and_resolves_evidence_entry(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch,
) -> None:
    first_source = tmp_path / "first.json"
    first_source.write_text(
        json.dumps(
            {
                "ComfyMathExpression": _object_info_entry(
                    python_module="nodes",
                    name="ComfyMathExpression",
                    output_names=["FLOAT", "INT"],
                )
            }
        ),
        encoding="utf-8",
    )
    second_source = tmp_path / "second.json"
    second_source.write_text(
        json.dumps(
            {
                "ComfyMathExpression": _object_info_entry(
                    python_module="nodes",
                    name="ComfyMathExpression",
                    output_names=["FLOAT", "INT", "BOOL"],
                )
            }
        ),
        encoding="utf-8",
    )
    cache_root = tmp_path / "cache_obj"
    build_cache(
        str(first_source),
        version="commit-v1",
        cache_dir=str(cache_root),
        identity=CacheIdentity(pack_slug="nodes", git_commit="abc123", source_kind="executed_object_info"),
        full_pack_refresh={"nodes"},
    )
    build_cache(
        str(second_source),
        version="evidence-v1",
        cache_dir=str(cache_root),
        identity=CacheIdentity(
            pack_slug="nodes",
            evidence_identity="object_info_comfyui_0.24.0.1.json",
            source_kind="static_evidence",
        ),
        full_pack_refresh=False,
    )
    _patch_consume_paths(monkeypatch, cache_root)

    from vibecomfy.porting.object_info import (
        get_class,
        get_class_by_identity,
        has_class_identity,
    )
    from vibecomfy.porting.object_info.consume import output_names as cached_output_names

    legacy_entry = get_class("ComfyMathExpression")
    assert legacy_entry is not None
    assert legacy_entry["evidence_identity"] == "object_info_comfyui_0.24.0.1.json"
    assert legacy_entry["git_commit"] is None
    assert cached_output_names("ComfyMathExpression") == ["FLOAT", "INT", "BOOL"]

    commit_entry = get_class_by_identity("ComfyMathExpression", pack_slug="nodes", git_commit="abc123")
    assert commit_entry is not None
    assert [output["name"] for output in commit_entry["outputs"]] == ["FLOAT", "INT"]
    assert commit_entry["git_commit"] == "abc123"

    evidence_entry = get_class_by_identity(
        "ComfyMathExpression",
        pack_slug="nodes",
        evidence_identity="object_info_comfyui_0.24.0.1.json",
    )
    assert evidence_entry is not None
    assert [output["name"] for output in evidence_entry["outputs"]] == ["FLOAT", "INT", "BOOL"]
    assert evidence_entry["evidence_identity"] == "object_info_comfyui_0.24.0.1.json"
    assert has_class_identity(
        "ComfyMathExpression",
        pack_slug="nodes",
        evidence_identity="object_info_comfyui_0.24.0.1.json",
    ) is True
    assert has_class_identity(
        "ComfyMathExpression",
        pack_slug="nodes",
        evidence_identity="missing-evidence.json",
    ) is False


def test_identity_lookup_raises_typed_ambiguity_for_duplicate_identity_matches(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch,
) -> None:
    source = tmp_path / "object_info.json"
    source.write_text(
        json.dumps(
            {
                "ComfyMathExpression": _object_info_entry(
                    python_module="nodes",
                    name="ComfyMathExpression",
                    output_names=["FLOAT", "INT", "BOOL"],
                )
            }
        ),
        encoding="utf-8",
    )
    cache_root = tmp_path / "cache_obj"
    build_cache(
        str(source),
        version="dup-a",
        cache_dir=str(cache_root),
        identity=CacheIdentity(
            pack_slug="nodes",
            evidence_identity="object_info_comfyui_0.24.0.1.json",
            source_kind="static_evidence",
        ),
        full_pack_refresh={"nodes"},
    )
    build_cache(
        str(source),
        version="dup-b",
        cache_dir=str(cache_root),
        identity=CacheIdentity(
            pack_slug="nodes",
            evidence_identity="object_info_comfyui_0.24.0.1.json",
            source_kind="static_evidence",
        ),
        full_pack_refresh={"nodes"},
    )
    _patch_consume_paths(monkeypatch, cache_root)

    from vibecomfy.errors import ObjectInfoIdentityAmbiguityError
    from vibecomfy.porting.object_info import get_class_by_identity

    with pytest.raises(ObjectInfoIdentityAmbiguityError) as exc:
        get_class_by_identity(
            "ComfyMathExpression",
            pack_slug="nodes",
            evidence_identity="object_info_comfyui_0.24.0.1.json",
        )

    err = exc.value
    assert err.class_type == "ComfyMathExpression"
    assert err.pack_slug == "nodes"
    assert err.git_commit is None
    assert err.evidence_identity == "object_info_comfyui_0.24.0.1.json"
    assert len(err.matches) == 2
    assert {match["filename"] for match in err.matches} == {"nodes@dup-a.json", "nodes@dup-b.json"}
    assert "multiple object_info cache entries matched" in str(err)


# ---------------------------------------------------------------------------
# effective_widget_names_for_class (widget_schema tiered lookup)
# ---------------------------------------------------------------------------


def test_effective_widget_names_uses_curated_schema_over_object_info(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch,
) -> None:
    cache_root = _build_temp_cache(tmp_path)
    _patch_consume_paths(monkeypatch, cache_root)

    curated = WIDGET_SCHEMA.get("LTX2_NAG")
    assert curated is not None, "LTX2_NAG must be in WIDGET_SCHEMA"

    names = effective_widget_names_for_class("LTX2_NAG", allow_object_info_fallback=True)
    assert names == curated

    from vibecomfy.porting.object_info.consume import object_info_widget_order as oiwo

    raw = oiwo("LTX2_NAG")
    assert raw != names, "curated order must differ from object_info raw order"


def test_effective_widget_names_fallback_to_object_info(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch,
) -> None:
    cache_root = _build_temp_cache(tmp_path)
    _patch_consume_paths(monkeypatch, cache_root)

    assert "SomeUnknownClass" not in WIDGET_SCHEMA

    names_no = effective_widget_names_for_class("SomeUnknownClass", allow_object_info_fallback=False)
    assert names_no == []

    names_yes = effective_widget_names_for_class("SomeUnknownClass", allow_object_info_fallback=True)
    assert names_yes == [None, "widget_0", "widget_1", "widget_2"]


def test_effective_widget_names_unknown_class(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch,
) -> None:
    cache_root = _build_temp_cache(tmp_path)
    _patch_consume_paths(monkeypatch, cache_root)

    assert effective_widget_names_for_class("TotallyFakeClass", allow_object_info_fallback=False) == []
    assert effective_widget_names_for_class("TotallyFakeClass", allow_object_info_fallback=True) == []


def test_widget_resolver_does_not_auto_apply_shifted_object_info(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch,
) -> None:
    cache_root = _build_temp_cache(tmp_path)
    _patch_consume_paths(monkeypatch, cache_root)

    from vibecomfy.porting.widget_aliases import resolve_widget_name_with_provenance

    result = resolve_widget_name_with_provenance("SomeUnknownClass", 1)

    assert result.resolved is False
    assert result.name == "widget_1"
    assert result.source == "unresolved"


def test_widget_resolver_uses_schema_provider_before_object_info() -> None:
    from vibecomfy.schema import InputSpec, NodeSchema
    from vibecomfy.porting.widget_aliases import resolve_widget_name_with_provenance

    class Provider:
        def get_schema(self, class_type: str) -> NodeSchema | None:
            if class_type != "ProviderNode":
                return None
            return NodeSchema(
                class_type="ProviderNode",
                pack=None,
                inputs={
                    "image": InputSpec("IMAGE"),
                    "prompt": InputSpec("STRING"),
                    "strength": InputSpec("FLOAT"),
                },
                outputs=[],
                source_provider="test_provider",
            )

    result = resolve_widget_name_with_provenance("ProviderNode", 1, schema_provider=Provider())

    assert result.resolved is True
    assert result.name == "strength"
    assert result.source == "test_provider"


# ---------------------------------------------------------------------------
# helpers
# ---------------------------------------------------------------------------


def _patch_consume_paths(monkeypatch: pytest.MonkeyPatch, cache_root: Path) -> None:
    """Point the consumer module at a temp cache directory and reset internal state."""
    import vibecomfy.porting.object_info.consume as _consume

    monkeypatch.setattr(_consume, "CACHE_DIR", cache_root)
    monkeypatch.setattr(_consume, "INDEX_PATH", cache_root / "index.json")
    monkeypatch.setattr(_consume, "_index", None)
    monkeypatch.setattr(_consume, "_pack_cache", {})
