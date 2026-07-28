"""Focused unit tests for the demo_factory creative feature matcher.

Guards the unification in plan task #20: ``_node_matches_feature`` used to build
its own hardcoded monolithic ``object_info`` JSON cache; it now sources the
per-class ``category`` through the shared object_info chokepoint
(:func:`vibecomfy.porting.object_info.get_class`, which reads the same per-pack
cache the ``AuthoringSchemaProvider`` index layer reads). Behavior must be
preserved: a known comfy-core family matches by category, custom-node classes
match by keyword, and bogus types never match.
"""
from __future__ import annotations

from vibecomfy.demo_factory.creative import _node_matches_feature, find_feature_node_ids


def test_node_matches_feature_resolves_known_category_via_shared_cache() -> None:
    # ``image/upscaling`` is a comfy-core category surfaced by the shared
    # object_info cache (get_class), not a keyword in the node TYPE name.
    assert _node_matches_feature("ImageScaleBy", "upscale") is True
    assert _node_matches_feature("ImageScaleToTotalPixels", "upscale") is True
    # ``sampling`` family resolves through the shared cache category too.
    assert _node_matches_feature("KSampler", "refinement_pass") is True


def test_node_matches_feature_falls_back_to_keyword_for_uncached_custom_node() -> None:
    # FaceDetailer is a custom-node class absent from the object_info cache; the
    # keyword fallback must still match it so feature detection is not lost.
    assert _node_matches_feature("FaceDetailer", "face_detailer") is True


def test_node_matches_feature_returns_falsy_for_bogus_node() -> None:
    assert _node_matches_feature("DefinitelyNotARealComfyClass_xyz", "upscale") is False
    assert _node_matches_feature("", "upscale") is False


def test_find_feature_node_ids_skips_unknown_graph_nodes() -> None:
    # UI-node graph shape: ``nodes`` is a list of ``{id, type}`` dicts.
    graph = {
        "nodes": [
            {"id": 1, "type": "ImageScaleBy"},
            {"id": 2, "type": "DefinitelyNotARealComfyClass_xyz"},
            {"id": 3, "type": "LoadImage"},
        ]
    }
    assert find_feature_node_ids(graph, "upscale") == ["1"]


def test_hardcoded_monolithic_cache_helper_was_removed() -> None:
    # The duplicate path is gone: the creative module must no longer carry its
    # own object_info loader / cache symbol.
    import vibecomfy.demo_factory.creative as creative

    assert not hasattr(creative, "_object_info")
    assert not hasattr(creative, "_OBJECT_INFO_CACHE")
