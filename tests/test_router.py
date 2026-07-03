from __future__ import annotations

import pytest

from vibecomfy import router
from vibecomfy.patches.types import Patch


# ---------------------------------------------------------------------------
# list_routes
# ---------------------------------------------------------------------------


def test_list_routes_returns_all_registered_routes() -> None:
    routes = router.list_routes()

    assert isinstance(routes, list)
    assert len(routes) >= 6  # the six routes registered in _rules.py

    for entry in routes:
        assert "verb_kind" in entry
        assert "verb_name" in entry
        assert "template_id" in entry
        assert isinstance(entry["verb_kind"], str)
        assert isinstance(entry["verb_name"], str)
        assert isinstance(entry["template_id"], str)

    # Sanity-check a few known registrations
    template_ids = {entry["template_id"] for entry in routes}
    for tid in (
        "image/z_image",
        "image/flux2_klein_4b_t2i",
        "video/wan_t2v",
        "video/ltx2_3_t2v",
        "video/wan_i2v",
        "video/ltx2_3_i2v",
    ):
        assert tid in template_ids


# ---------------------------------------------------------------------------
# describe_route
# ---------------------------------------------------------------------------


def test_describe_route_returns_matching_metadata() -> None:
    results = router.describe_route("video", "t2v")
    assert isinstance(results, list)
    assert len(results) >= 2  # wan_t2v + ltx2_3_t2v

    template_ids = {r["template_id"] for r in results}
    assert "video/wan_t2v" in template_ids
    assert "video/ltx2_3_t2v" in template_ids

    for r in results:
        assert r["verb_kind"] == "video"
        assert r["verb_name"] == "t2v"


def test_describe_route_empty_for_unknown_verb() -> None:
    assert router.describe_route("nonexistent", "whatever") == []


def test_describe_route_empty_for_known_kind_unknown_name() -> None:
    assert router.describe_route("image", "i2i") == []


# ---------------------------------------------------------------------------
# pick – unchanged positive behaviour (existing parametrized tests)
# ---------------------------------------------------------------------------


@pytest.mark.parametrize(
    ("verb_kind", "verb_name", "inputs", "template_id", "patch_names"),
    [
        ("image", "t2i", {}, "image/z_image", []),
        ("image", "t2i", {"model": "flux2_klein_4b"}, "image/flux2_klein_4b_t2i", []),
        ("video", "t2v", {}, "video/wan_t2v", []),
        ("video", "t2v", {"model": "ltx"}, "video/ltx2_3_t2v", ["ltx_lowvram", "resolution:384x256x9"]),
        ("video", "i2v", {}, "video/wan_i2v", []),
        ("video", "i2v", {"model": "ltx"}, "video/ltx2_3_i2v", ["ltx_lowvram", "resolution:384x256x9"]),
    ],
)
def test_router_positive_rules(
    verb_kind: str,
    verb_name: str,
    inputs: dict[str, object],
    template_id: str,
    patch_names: list[str],
) -> None:
    result = router.pick(verb_kind, verb_name, **inputs)

    assert result.template_id == template_id
    assert [patch.name for patch in result.explicit_patches] == patch_names
    assert isinstance(result.applicable_patches, list)
    assert all(isinstance(patch, Patch) for patch in result.applicable_patches)
    if inputs.get("model") == "ltx":
        assert result.applicable_patches == []


# ---------------------------------------------------------------------------
# pick – KeyError diagnostics
# ---------------------------------------------------------------------------


@pytest.mark.parametrize(
    ("verb_kind", "verb_name", "inputs"),
    [
        ("whatever", "unknown", {}),
        ("image", "t2i", {"model": "flux2_klein_9b_gguf"}),
        ("image", "edit", {"model": "qwen"}),
        ("image", "edit", {"model": "flux2_klein_4b"}),
    ],
)
def test_router_rejects_unknown_and_deferred_routes(
    verb_kind: str,
    verb_name: str,
    inputs: dict[str, object],
) -> None:
    with pytest.raises(KeyError):
        router.pick(verb_kind, verb_name, **inputs)


def test_keyerror_includes_available_routes_for_unknown_kind() -> None:
    with pytest.raises(KeyError) as excinfo:
        router.pick("whatever", "unknown")
    msg = str(excinfo.value)
    assert "no route for whatever.unknown" in msg
    # Should list available verb kinds
    assert "available verb kinds" in msg
    assert "image" in msg
    assert "video" in msg


def test_keyerror_includes_available_verbs_for_known_kind() -> None:
    with pytest.raises(KeyError) as excinfo:
        router.pick("image", "edit")
    msg = str(excinfo.value)
    assert "no route for image.edit" in msg
    assert "available 'image' verbs" in msg
    assert "t2i" in msg


def test_keyerror_includes_nearest_match() -> None:
    with pytest.raises(KeyError) as excinfo:
        router.pick("image", "t2v")  # "t2v" is close to "t2i"
    msg = str(excinfo.value)
    assert "no route for image.t2v" in msg
    # Should list available 'image' verbs
    assert "available 'image' verbs" in msg
    # difflib should find "image.t2i" as a nearest match
    assert "nearest" in msg.lower() or "image.t2i" in msg


def test_keyerror_raised_for_no_matching_predicate() -> None:
    """Even when verb_kind/verb_name match a registered route, a predicate
    miss still raises KeyError (not a different exception type)."""
    with pytest.raises(KeyError) as excinfo:
        router.pick("image", "t2i", model="no_such_model")
    msg = str(excinfo.value)
    assert "no route for image.t2i" in msg
    assert "available 'image' verbs" in msg
