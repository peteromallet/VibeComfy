from __future__ import annotations

from pathlib import Path
from typing import Any

import httpx
import pytest

from vibecomfy.registry.pack_resolver import (
    AmbiguousPackError,
    PackNotFoundError,
    PackRef,
    lookup_class_candidates,
    resolve_missing_nodes,
    resolve_pack,
)


class FakeRegistryClient:
    def __init__(self, routes: dict[tuple[str, tuple[tuple[str, str], ...]], Any]):
        self.routes = routes
        self.calls: list[tuple[str, tuple[tuple[str, str], ...]]] = []

    def get(self, url: str, **kwargs: Any) -> httpx.Response:
        assert "registry.comfy.org/api/v1/packs" not in url
        params = tuple(sorted((kwargs.get("params") or {}).items()))
        key = (url, params)
        self.calls.append(key)
        payload = self.routes.get(key)
        request = httpx.Request("GET", url)
        if isinstance(payload, httpx.Response):
            return payload
        if payload is None:
            return httpx.Response(404, request=request, json={"error": "not found"})
        return httpx.Response(200, request=request, json=payload)


def test_resolve_pack_uses_exact_comfy_node_endpoint_first(tmp_path: Path) -> None:
    client = FakeRegistryClient(
        {
            ("https://api.comfy.org/comfy-nodes/ImageResizeKJv2/node", ()): {
                "node": {
                    "id": "comfyui-kjnodes",
                    "name": "ComfyUI-KJNodes",
                    "latest_version": "1.2.3",
                    "commit": "abc123",
                    "repository": "https://github.com/kijai/ComfyUI-KJNodes",
                }
            }
        }
    )

    resolution = resolve_pack("ImageResizeKJv2", cache_root=tmp_path, client=client)

    assert resolution.query_type == "class"
    assert resolution.ref == PackRef(
        slug="comfyui-kjnodes",
        source="comfy-registry",
        version="1.2.3",
        commit="abc123",
        url="https://github.com/kijai/ComfyUI-KJNodes",
        name="ComfyUI-KJNodes",
        registry_id="comfyui-kjnodes",
    )
    assert client.calls == [("https://api.comfy.org/comfy-nodes/ImageResizeKJv2/node", ())]


def test_resolve_pack_falls_back_to_class_search(tmp_path: Path) -> None:
    client = FakeRegistryClient(
        {
            (
                "https://api.comfy.org/nodes/search",
                (("comfy_node_search", "MissingClass"),),
            ): {
                "nodes": [
                    {
                        "id": "comfyui-example",
                        "name": "ComfyUI Example",
                        "version": "0.4.0",
                        "commitSha": "def456",
                    }
                ]
            }
        }
    )

    resolution = resolve_pack("MissingClass", cache_root=tmp_path, client=client)

    assert resolution.ref.slug == "comfyui-example"
    assert resolution.ref.version == "0.4.0"
    assert resolution.ref.commit == "def456"
    assert client.calls == [
        ("https://api.comfy.org/comfy-nodes/MissingClass/node", ()),
        ("https://api.comfy.org/nodes/search", (("comfy_node_search", "MissingClass"),)),
    ]


def test_resolve_pack_uses_registry_search_for_slug_lookup(tmp_path: Path) -> None:
    client = FakeRegistryClient(
        {
            ("https://api.comfy.org/nodes/search", (("search", "comfyui-controlnet-aux"),)): {
                "nodes": [
                    {
                        "id": "comfyui-controlnet-aux",
                        "name": "ComfyUI ControlNet Aux",
                        "latestVersion": "1.0.5",
                        "commit_sha": "fedcba",
                    }
                ]
            }
        }
    )

    resolution = resolve_pack("comfyui-controlnet-aux", cache_root=tmp_path, client=client)

    assert resolution.query_type == "slug"
    assert resolution.ref.slug == "comfyui-controlnet-aux"
    assert resolution.ref.version == "1.0.5"
    assert client.calls == [("https://api.comfy.org/nodes/search", (("search", "comfyui-controlnet-aux"),))]


def test_resolve_pack_raises_on_ambiguous_class_search(tmp_path: Path) -> None:
    client = FakeRegistryClient(
        {
            ("https://api.comfy.org/nodes/search", (("comfy_node_search", "AmbiguousNode"),)): {
                "nodes": [
                    {"id": "pack-a", "name": "Pack A"},
                    {"id": "pack-b", "name": "Pack B"},
                ]
            }
        }
    )

    with pytest.raises(AmbiguousPackError) as exc:
        resolve_pack("AmbiguousNode", cache_root=tmp_path, client=client)

    assert [candidate.slug for candidate in exc.value.candidates] == ["pack-a", "pack-b"]


def test_lookup_class_candidates_searches_registry_class_index(tmp_path: Path) -> None:
    client = FakeRegistryClient(
        {
            ("https://api.comfy.org/nodes/search", (("comfy_node_search", "AnyNode"),)): {
                "items": [{"id": "pack-a", "displayName": "Pack A"}]
            }
        }
    )

    candidates = lookup_class_candidates("AnyNode", cache_root=tmp_path, client=client)

    assert candidates == [PackRef(slug="pack-a", source="comfy-registry", name="Pack A", registry_id="pack-a")]
    assert client.calls == [("https://api.comfy.org/nodes/search", (("comfy_node_search", "AnyNode"),))]


def test_resolver_writes_deterministic_cache_and_reuses_it(tmp_path: Path) -> None:
    client = FakeRegistryClient(
        {
            ("https://api.comfy.org/nodes/search", (("search", "comfyui-cache-test"),)): {
                "nodes": [{"id": "comfyui-cache-test", "name": "ComfyUI Cache Test"}]
            }
        }
    )

    first = resolve_pack("comfyui-cache-test", cache_root=tmp_path, client=client)
    second = resolve_pack("comfyui-cache-test", cache_root=tmp_path, client=client)

    assert first.ref == second.ref
    assert second.cache_hit is True
    assert len(client.calls) == 1
    files = sorted(path.relative_to(tmp_path).as_posix() for path in tmp_path.glob("*.json"))
    assert files == [
        "nodes_search.7d893668414e2b03a35615aa9258cdcb34fc7ade9d72d3bb2b489b2eb81c6911.json",
    ]


def test_obsolete_registry_packs_endpoint_is_never_called(tmp_path: Path) -> None:
    client = FakeRegistryClient(
        {
            ("https://api.comfy.org/comfy-nodes/KSampler/node", ()): {
                "node": {"id": "comfy-core", "name": "Comfy Core"}
            },
            ("https://api.comfy.org/nodes/search", (("search", "ComfyUI-KJNodes"),)): {
                "nodes": [{"id": "comfyui-kjnodes", "name": "ComfyUI-KJNodes"}]
            },
        }
    )

    resolve_pack("KSampler", cache_root=tmp_path, client=client)
    resolve_pack("ComfyUI-KJNodes", cache_root=tmp_path, client=client)

    called_urls = [url for url, _params in client.calls]
    assert all("registry.comfy.org/api/v1/packs" not in url for url in called_urls)
    assert called_urls == [
        "https://api.comfy.org/comfy-nodes/KSampler/node",
        "https://api.comfy.org/nodes/search",
    ]


def test_resolve_pack_preserves_authored_commit_pin_on_registry_resolution(tmp_path: Path) -> None:
    client = FakeRegistryClient(
        {
            ("https://api.comfy.org/nodes/search", (("search", "comfyui-kjnodes"),)): {
                "nodes": [
                    {
                        "id": "comfyui-kjnodes",
                        "name": "ComfyUI-KJNodes",
                        "latestVersion": "9.9.9",
                        "commit_sha": "latest999",
                        "repository": "https://github.com/kijai/ComfyUI-KJNodes",
                    }
                ]
            }
        }
    )

    resolution = resolve_pack(
        "comfyui-kjnodes",
        version_pin="deadbeefcafebabe",
        cache_root=tmp_path,
        client=client,
    )

    assert resolution.query_type == "slug"
    assert resolution.ref.version == "deadbeefcafebabe"
    assert resolution.ref.commit == "deadbeefcafebabe"
    assert resolution.ref.url == "https://github.com/kijai/ComfyUI-KJNodes"


def test_resolve_pack_preserves_semver_pin_and_precomputed_local_metadata(tmp_path: Path) -> None:
    client = FakeRegistryClient(
        {
            ("https://api.comfy.org/nodes/search", (("search", "comfyui-kjnodes"),)): {
                "nodes": [
                    {
                        "id": "comfyui-kjnodes",
                        "name": "ComfyUI-KJNodes",
                        "latestVersion": "9.9.9",
                        "commit_sha": "latest999",
                        "repository": "https://github.com/kijai/ComfyUI-KJNodes",
                    }
                ]
            }
        }
    )

    resolution = resolve_pack(
        "comfyui-kjnodes",
        version_pin="1.2.3",
        local_metadata={"commit": "abc1234", "path": "/tmp/ComfyUI-KJNodes"},
        cache_root=tmp_path,
        client=client,
    )

    assert resolution.ref.version == "1.2.3"
    assert resolution.ref.commit == "abc1234"
    assert resolution.ref.path == "/tmp/ComfyUI-KJNodes"


def test_resolve_pack_uses_distinct_aux_git_path_without_registry_fallback(tmp_path: Path) -> None:
    client = FakeRegistryClient({})

    resolution = resolve_pack(
        "AuxOnlyNode",
        aux_id="owner/repo",
        version_pin="deadbeef",
        cache_root=tmp_path,
        client=client,
    )

    assert resolution.query_type == "aux_git"
    assert resolution.ref == PackRef(
        slug="repo",
        source="aux-git",
        version="deadbeef",
        commit="deadbeef",
        url="https://github.com/owner/repo.git",
        name="AuxOnlyNode",
    )
    assert client.calls == []


# ---------------------------------------------------------------------------
# T5 — Unchanged resolve_pack(name) behavior proofs
# ---------------------------------------------------------------------------


def test_resolve_pack_empty_string_raises_value_error(tmp_path: Path) -> None:
    with pytest.raises(ValueError, match="must not be empty"):
        resolve_pack("", cache_root=tmp_path)


def test_resolve_pack_whitespace_only_string_raises_value_error(tmp_path: Path) -> None:
    with pytest.raises(ValueError, match="must not be empty"):
        resolve_pack("   ", cache_root=tmp_path)


def test_resolve_pack_explicit_none_params_preserve_unchanged_behavior(tmp_path: Path) -> None:
    """Calling resolve_pack with version_pin=None, aux_id=None must behave
    identically to calling it without those keyword arguments."""
    client = FakeRegistryClient(
        {
            ("https://api.comfy.org/comfy-nodes/KSampler/node", ()): {
                "node": {
                    "id": "comfy-core",
                    "name": "Comfy Core",
                    "latest_version": "2.0.0",
                    "commit": "ccc111",
                }
            }
        }
    )

    no_kwargs = resolve_pack("KSampler", cache_root=tmp_path, client=client)
    with_kwargs = resolve_pack(
        "KSampler",
        version_pin=None,
        aux_id=None,
        local_metadata=None,
        cache_root=tmp_path,
        client=client,
    )

    assert no_kwargs.ref == with_kwargs.ref
    assert no_kwargs.query_type == with_kwargs.query_type


def test_resolve_pack_unknown_name_raises_pack_not_found(tmp_path: Path) -> None:
    client = FakeRegistryClient({})

    with pytest.raises(PackNotFoundError, match="unknown pack or class"):
        resolve_pack("NonexistentPackOrClass", cache_root=tmp_path, client=client)


def test_resolve_pack_disallow_remote_lookup_raises(tmp_path: Path) -> None:
    client = FakeRegistryClient({})

    with pytest.raises(PackNotFoundError, match="remote lookup disabled"):
        resolve_pack(
            "SomeClass",
            allow_remote_lookup=False,
            cache_root=tmp_path,
            client=client,
        )


def test_resolve_pack_disallow_remote_lookup_allows_aux_git(tmp_path: Path) -> None:
    """allow_remote_lookup=False should NOT block aux_git resolution because
    that path returns before the remote-lookup guard."""
    client = FakeRegistryClient({})

    resolution = resolve_pack(
        "AuxNode",
        aux_id="owner/repo",
        allow_remote_lookup=False,
        cache_root=tmp_path,
        client=client,
    )

    assert resolution.query_type == "aux_git"
    assert client.calls == []


def test_resolve_pack_disallow_remote_lookup_allows_local_path(tmp_path: Path) -> None:
    client = FakeRegistryClient({})

    resolution = resolve_pack(
        "/tmp/ComfyUI-CustomNodes",
        allow_remote_lookup=False,
        cache_root=tmp_path,
        client=client,
    )

    assert resolution.query_type == "local"
    assert client.calls == []


# ---------------------------------------------------------------------------
# T5 — Version-pin preservation on PackRef
# ---------------------------------------------------------------------------


def test_resolve_pack_semver_pin_on_registry_class_resolution(tmp_path: Path) -> None:
    """Semver pin (e.g. '1.2.3') should set version but NOT commit on a
    registry resolution, because semver does not look like a commit SHA."""
    client = FakeRegistryClient(
        {
            ("https://api.comfy.org/comfy-nodes/MyNode/node", ()): {
                "node": {
                    "id": "comfyui-mypack",
                    "name": "MyPack",
                    "latest_version": "4.0.0",
                    "commit": "registry999",
                    "repository": "https://github.com/example/MyPack",
                }
            }
        }
    )

    resolution = resolve_pack(
        "MyNode",
        version_pin="1.2.3",
        cache_root=tmp_path,
        client=client,
    )

    assert resolution.query_type == "class"
    assert resolution.ref.version == "1.2.3"
    # semver pin should NOT overwrite commit
    assert resolution.ref.commit == "registry999"
    assert resolution.ref.url == "https://github.com/example/MyPack"


def test_resolve_pack_version_pin_on_local_path(tmp_path: Path) -> None:
    resolution = resolve_pack(
        "./custom_nodes/MyPack",
        version_pin="abc123def",
        cache_root=tmp_path,
    )

    assert resolution.query_type == "local"
    assert resolution.ref.version == "abc123def"
    assert resolution.ref.commit == "abc123def"
    assert resolution.ref.path is not None
    assert "MyPack" in resolution.ref.path


def test_resolve_pack_version_pin_on_git_url(tmp_path: Path) -> None:
    resolution = resolve_pack(
        "https://github.com/user/repo.git",
        version_pin="deadbeef",
        cache_root=tmp_path,
    )

    assert resolution.query_type == "git"
    assert resolution.ref.slug == "repo"
    assert resolution.ref.version == "deadbeef"
    assert resolution.ref.commit == "deadbeef"
    assert resolution.ref.url == "https://github.com/user/repo.git"


def test_resolve_pack_local_metadata_as_pack_ref_object(tmp_path: Path) -> None:
    client = FakeRegistryClient(
        {
            ("https://api.comfy.org/nodes/search", (("search", "comfyui-kjnodes"),)): {
                "nodes": [
                    {
                        "id": "comfyui-kjnodes",
                        "name": "ComfyUI-KJNodes",
                        "latestVersion": "9.9.9",
                        "commit_sha": "latest999",
                        "repository": "https://github.com/kijai/ComfyUI-KJNodes",
                    }
                ]
            }
        }
    )

    local = PackRef(
        slug="comfyui-kjnodes",
        source="local-git",
        version="abc1234",
        commit="abc1234",
        url="git@github.com:kijai/ComfyUI-KJNodes.git",
        path="/custom_nodes/ComfyUI-KJNodes",
        name="ComfyUI-KJNodes",
    )

    resolution = resolve_pack(
        "comfyui-kjnodes",
        version_pin="1.2.3",
        local_metadata=local,
        cache_root=tmp_path,
        client=client,
    )

    # local_metadata PackRef fields take priority: version comes from
    # the PackRef metadata, not from version_pin
    assert resolution.ref.version == "abc1234"
    assert resolution.ref.commit == "abc1234"
    assert resolution.ref.url == "git@github.com:kijai/ComfyUI-KJNodes.git"
    assert resolution.ref.path == "/custom_nodes/ComfyUI-KJNodes"


def test_resolve_pack_aux_id_without_explicit_version_pin(tmp_path: Path) -> None:
    """aux_id path should work even without a version_pin — the ref just
    won't have version/commit set."""
    client = FakeRegistryClient({})

    resolution = resolve_pack(
        "SomeNode",
        aux_id="owner/repo",
        cache_root=tmp_path,
        client=client,
    )

    assert resolution.query_type == "aux_git"
    assert resolution.ref.source == "aux-git"
    assert resolution.ref.slug == "repo"
    assert resolution.ref.url == "https://github.com/owner/repo.git"
    assert resolution.ref.version is None
    assert resolution.ref.commit is None
    assert client.calls == []


def test_resolve_pack_whitespace_aux_id_treated_as_none(tmp_path: Path) -> None:
    """Whitespace-only aux_id should normalize to None, causing normal
    registry resolution instead of aux_git path."""
    client = FakeRegistryClient(
        {
            ("https://api.comfy.org/nodes/search", (("search", "MyPack"),)): {
                "nodes": [
                    {
                        "id": "comfyui-mypack",
                        "name": "MyPack",
                        "latestVersion": "3.0.0",
                        "commit_sha": "fffeee",
                    }
                ]
            }
        }
    )

    resolution = resolve_pack(
        "MyPack",
        aux_id="   ",
        cache_root=tmp_path,
        client=client,
    )

    assert resolution.query_type == "slug"
    assert resolution.ref.slug == "comfyui-mypack"
    assert resolution.ref.source == "comfy-registry"


# ---------------------------------------------------------------------------
# T5 — PackRef serialization
# ---------------------------------------------------------------------------


def test_pack_ref_to_dict_includes_non_none_fields() -> None:
    ref = PackRef(
        slug="test-pack",
        source="comfy-registry",
        version="1.0.0",
        commit="abc123",
    )

    result = ref.to_dict()
    assert result == {
        "slug": "test-pack",
        "source": "comfy-registry",
        "version": "1.0.0",
        "commit": "abc123",
    }


def test_pack_ref_to_dict_excludes_none_fields() -> None:
    ref = PackRef(slug="minimal", source="local")

    result = ref.to_dict()
    assert result == {"slug": "minimal", "source": "local"}


def test_pack_ref_to_dict_full() -> None:
    ref = PackRef(
        slug="full-pack",
        source="git",
        version="2.0.0",
        commit="def456",
        url="https://github.com/user/repo.git",
        path="/tmp/repo",
        name="Full Pack",
        registry_id="full-pack-id",
    )

    result = ref.to_dict()
    assert result == {
        "slug": "full-pack",
        "source": "git",
        "version": "2.0.0",
        "commit": "def456",
        "url": "https://github.com/user/repo.git",
        "path": "/tmp/repo",
        "name": "Full Pack",
        "registry_id": "full-pack-id",
    }


# ---------------------------------------------------------------------------
# T5 — Lookup edge cases
# ---------------------------------------------------------------------------


def test_lookup_class_candidates_returns_empty_for_unknown_class(tmp_path: Path) -> None:
    client = FakeRegistryClient({})

    candidates = lookup_class_candidates("UnknownClass", cache_root=tmp_path, client=client)

    assert candidates == []
    assert client.calls == [
        ("https://api.comfy.org/nodes/search", (("comfy_node_search", "UnknownClass"),))
    ]


def test_resolve_pack_registry_id_slug_path(tmp_path: Path) -> None:
    """A query that looks like a registry ID should hit /nodes/{id} first."""
    client = FakeRegistryClient(
        {
            ("https://api.comfy.org/nodes/deadbeefcafebabe12345678", ()): {
                "id": "comfyui-custom",
                "name": "Custom Pack",
                "latest_version": "5.0.0",
                "commit_sha": "abc999",
            }
        }
    )

    resolution = resolve_pack(
        "deadbeefcafebabe12345678",
        cache_root=tmp_path,
        client=client,
    )

    assert resolution.query_type == "slug"
    assert resolution.ref.slug == "comfyui-custom"
    assert resolution.ref.version == "5.0.0"
    assert client.calls == [
        ("https://api.comfy.org/nodes/deadbeefcafebabe12345678", ())
    ]


def test_resolve_pack_uses_exact_slug_match_over_fuzzy(tmp_path: Path) -> None:
    """When search returns multiple candidates, _select_exact_slug_or_name
    should pick the exact slug/name match."""
    client = FakeRegistryClient(
        {
            ("https://api.comfy.org/nodes/search", (("search", "comfyui-kjnodes"),)): {
                "nodes": [
                    {"id": "comfyui-kjnodes-extra", "name": "Extra KJNodes"},
                    {"id": "comfyui-kjnodes", "name": "ComfyUI-KJNodes"},
                    {"id": "other-pack", "name": "Other"},
                ]
            }
        }
    )

    resolution = resolve_pack(
        "comfyui-kjnodes",
        cache_root=tmp_path,
        client=client,
    )

    assert resolution.ref.slug == "comfyui-kjnodes"
    assert resolution.query_type == "slug"


def test_resolve_missing_nodes_uses_manager_node_map_for_vhs_class(tmp_path: Path) -> None:
    manager = FakeRegistryClient(
        {
            (
                "https://raw.githubusercontent.com/ltdrdata/ComfyUI-Manager/main/custom-node-map.json",
                (),
            ): {
                "VHS_VideoCombine": "ComfyUI-VideoHelperSuite",
                "OtherNode": "OtherPack",
            },
            (
                "https://raw.githubusercontent.com/ltdrdata/ComfyUI-Manager/main/custom-node-list.json",
                (),
            ): [
                {
                    "title": "ComfyUI-VideoHelperSuite",
                    "reference": "https://github.com/Kosinkadink/ComfyUI-VideoHelperSuite",
                    "description": "Video tools",
                }
            ],
        }
    )
    registry = FakeRegistryClient({})

    result = resolve_missing_nodes(
        "VHS_VideoCombine",
        cache_root=tmp_path,
        manager_client=manager,
        registry_client=registry,
    )

    assert result.query_intent == "class_name"
    assert result.candidates
    candidate = result.candidates[0]
    assert candidate.ref.slug == "ComfyUI-VideoHelperSuite"
    assert candidate.expected_classes == ("VHS_VideoCombine",)
    assert candidate.validation_mode == "class_validatable"
    assert [evidence.source for evidence in candidate.evidence] == ["custom-node-map"]


def test_resolve_missing_nodes_hotshotxl_capability_returns_animatediff_classes(tmp_path: Path) -> None:
    manager = FakeRegistryClient(
        {
            (
                "https://raw.githubusercontent.com/ltdrdata/ComfyUI-Manager/main/custom-node-map.json",
                (),
            ): {
                "ADE_AnimateDiffLoaderWithContext": "ComfyUI-AnimateDiff-Evolved",
                "ADE_UseEvolvedSampling": "ComfyUI-AnimateDiff-Evolved",
                "OtherNode": "OtherPack",
            },
            (
                "https://raw.githubusercontent.com/ltdrdata/ComfyUI-Manager/main/custom-node-list.json",
                (),
            ): [
                {
                    "title": "ComfyUI-AnimateDiff-Evolved",
                    "reference": "https://github.com/Kosinkadink/ComfyUI-AnimateDiff-Evolved",
                    "description": "AnimateDiff workflows including HotshotXL support",
                }
            ],
        }
    )

    result = resolve_missing_nodes(
        "HotshotXL",
        query_intent="capability",
        cache_root=tmp_path,
        manager_client=manager,
        registry_client=FakeRegistryClient({}),
    )

    assert result.query_intent == "capability"
    assert result.candidates
    candidate = result.candidates[0]
    assert candidate.ref.slug == "ComfyUI-AnimateDiff-Evolved"
    assert candidate.expected_classes == ("ADE_AnimateDiffLoaderWithContext", "ADE_UseEvolvedSampling")
    assert candidate.validation_mode == "class_validatable"
    assert candidate.evidence[0].source == "custom-node-map"
    assert candidate.evidence[0].matched_classes == candidate.expected_classes


def test_resolve_missing_nodes_fetches_registry_schema_with_concrete_version(tmp_path: Path) -> None:
    registry = FakeRegistryClient(
        {
            ("https://api.comfy.org/comfy-nodes/VHS_VideoCombine/node", ()): {
                "node": {
                    "id": "comfyui-videohelpersuite",
                    "name": "ComfyUI-VideoHelperSuite",
                    "latestVersion": "latest",
                    "repository": "https://github.com/Kosinkadink/ComfyUI-VideoHelperSuite",
                }
            },
            ("https://api.comfy.org/nodes/comfyui-videohelpersuite/versions", ()): {
                "versions": [{"version": "1.2.3"}, {"version": "latest"}]
            },
            ("https://api.comfy.org/nodes/comfyui-videohelpersuite/versions/1.2.3/schema", ()): {
                "nodes": {"VHS_VideoCombine": {"input": {}}}
            },
        }
    )
    manager = FakeRegistryClient(
        {
            (
                "https://raw.githubusercontent.com/ltdrdata/ComfyUI-Manager/main/custom-node-map.json",
                (),
            ): {},
            (
                "https://raw.githubusercontent.com/ltdrdata/ComfyUI-Manager/main/custom-node-list.json",
                (),
            ): [],
        }
    )

    result = resolve_missing_nodes(
        "VHS_VideoCombine",
        cache_root=tmp_path,
        manager_client=manager,
        registry_client=registry,
    )

    called_urls = [url for url, _params in registry.calls]
    assert "https://api.comfy.org/nodes/comfyui-videohelpersuite/versions/latest/schema" not in called_urls
    assert "https://api.comfy.org/nodes/comfyui-videohelpersuite/versions/1.2.3/schema" in called_urls
    assert result.candidates[0].expected_classes == ("VHS_VideoCombine",)
    assert result.candidates[0].provisional_schema["runnable"] is False


def test_resolve_missing_nodes_preserves_evidence_only_manager_match(tmp_path: Path) -> None:
    manager = FakeRegistryClient(
        {
            (
                "https://raw.githubusercontent.com/ltdrdata/ComfyUI-Manager/main/custom-node-map.json",
                (),
            ): {},
            (
                "https://raw.githubusercontent.com/ltdrdata/ComfyUI-Manager/main/custom-node-list.json",
                (),
            ): [
                {
                    "title": "ComfyUI-AnimateDiff-Evolved",
                    "reference": "https://github.com/Kosinkadink/ComfyUI-AnimateDiff-Evolved",
                    "description": "AnimateDiff workflows including HotshotXL support",
                }
            ],
        }
    )

    result = resolve_missing_nodes(
        "HotshotXL",
        cache_root=tmp_path,
        manager_client=manager,
        registry_client=FakeRegistryClient({}),
    )

    assert result.candidates[0].ref.slug == "ComfyUI-AnimateDiff-Evolved"
    assert result.candidates[0].expected_classes == ()
    assert result.candidates[0].validation_mode == "evidence_only"
    assert "did not provide concrete node classes" in result.candidates[0].warnings[0]


def test_resolve_missing_nodes_github_401_warns_and_falls_back_to_repo_search(tmp_path: Path) -> None:
    github = FakeRegistryClient(
        {
            (
                "https://api.github.com/search/code",
                (("q", "VHS_VideoCombine ComfyUI"),),
            ): httpx.Response(401, request=httpx.Request("GET", "https://api.github.com/search/code"), json={"message": "bad credentials"}),
            (
                "https://api.github.com/search/repositories",
                (("q", "VHS_VideoCombine ComfyUI"),),
            ): {
                "items": [
                    {
                        "name": "ComfyUI-VideoHelperSuite",
                        "full_name": "Kosinkadink/ComfyUI-VideoHelperSuite",
                        "html_url": "https://github.com/Kosinkadink/ComfyUI-VideoHelperSuite",
                        "description": "Contains VHS_VideoCombine nodes",
                    }
                ]
            },
        }
    )
    manager = FakeRegistryClient(
        {
            (
                "https://raw.githubusercontent.com/ltdrdata/ComfyUI-Manager/main/custom-node-map.json",
                (),
            ): {},
            (
                "https://raw.githubusercontent.com/ltdrdata/ComfyUI-Manager/main/custom-node-list.json",
                (),
            ): [],
        }
    )

    result = resolve_missing_nodes(
        "VHS_VideoCombine",
        cache_root=tmp_path,
        manager_client=manager,
        registry_client=FakeRegistryClient({}),
        github_client=github,
    )

    assert any("GitHub code search unavailable (401)" in warning for warning in result.warnings)
    assert result.candidates
    assert result.candidates[0].ref.slug == "ComfyUI-VideoHelperSuite"
    assert result.candidates[0].evidence[0].source == "repository-search"


def test_resolve_missing_nodes_is_read_only_for_external_evidence(tmp_path: Path) -> None:
    manager = FakeRegistryClient(
        {
            (
                "https://raw.githubusercontent.com/ltdrdata/ComfyUI-Manager/main/custom-node-map.json",
                (),
            ): {"VHS_VideoCombine": "ComfyUI-VideoHelperSuite"},
            (
                "https://raw.githubusercontent.com/ltdrdata/ComfyUI-Manager/main/custom-node-list.json",
                (),
            ): [
                {
                    "title": "ComfyUI-VideoHelperSuite",
                    "reference": "https://github.com/Kosinkadink/ComfyUI-VideoHelperSuite",
                    "description": "Video tools",
                }
            ],
        }
    )
    registry = FakeRegistryClient(
        {
            ("https://api.comfy.org/comfy-nodes/VHS_VideoCombine/node", ()): {
                "node": {
                    "id": "comfyui-videohelpersuite",
                    "name": "ComfyUI-VideoHelperSuite",
                    "latestVersion": "1.2.3",
                }
            },
            ("https://api.comfy.org/nodes/comfyui-videohelpersuite/versions/1.2.3/schema", ()): {
                "nodes": {"VHS_VideoCombine": {"input": {}}}
            },
        }
    )

    result = resolve_missing_nodes(
        "VHS_VideoCombine",
        cache_root=tmp_path,
        manager_client=manager,
        registry_client=registry,
    )

    called_urls = [url for url, _params in manager.calls + registry.calls]
    assert result.candidates[0].ref.slug == "ComfyUI-VideoHelperSuite"
    assert all(url.startswith(("https://api.comfy.org/", "https://raw.githubusercontent.com/")) for url in called_urls)
    assert not any(part.name in {"custom_nodes", "ComfyUI-VideoHelperSuite"} for part in tmp_path.rglob("*"))
