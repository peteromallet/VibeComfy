from __future__ import annotations

from pathlib import Path

import pytest

from vibecomfy.node_packs_lockfile import LockEntry


@pytest.fixture(autouse=True)
def _clear_node_pack_cache():
    import vibecomfy.node_packs as node_packs

    node_packs.clear_known_node_packs_cache()
    yield
    node_packs.clear_known_node_packs_cache()


def test_resolve_node_packs_uses_rich_lock_class_sets(monkeypatch) -> None:
    import vibecomfy.node_packs as node_packs

    def fake_read_lockfile(path: Path = Path("custom_nodes.lock")) -> list[LockEntry]:
        return [
            LockEntry(
                name="ComfyUI-RichPack",
                slug="comfyui-rich-pack",
                source="comfy-registry",
                version="1.0.0",
                commit="abc123",
                url="https://example.test/rich.git",
                class_set=("RichNodeB", "RichNodeA"),
                pip_packages=("example-extra",),
                schema_hash="feedface",
            )
        ]

    monkeypatch.setattr(node_packs, "read_lockfile", fake_read_lockfile)

    packs = node_packs.resolve_node_packs({"RichNodeA"})

    assert [(pack.name, pack.repo, sorted(pack.classes), pack.pip_packages, pack.class_schema_sha256) for pack in packs] == [
        (
            "ComfyUI-RichPack",
            "https://example.test/rich.git",
            ["RichNodeA", "RichNodeB"],
            ("example-extra",),
            "feedface",
        )
    ]
    assert node_packs.unresolved_class_types({"RichNodeA", "MissingNode"}) == ["MissingNode"]


def test_rich_lock_overrides_static_seed_pack_by_name(monkeypatch) -> None:
    import vibecomfy.node_packs as node_packs

    def fake_read_lockfile(path: Path = Path("custom_nodes.lock")) -> list[LockEntry]:
        return [
            LockEntry(
                name="ComfyUI-KJNodes",
                git_commit_sha="abc123",
                url="https://example.test/kj.git",
                class_set=("OnlyLockedKJNode",),
            )
        ]

    monkeypatch.setattr(node_packs, "read_lockfile", fake_read_lockfile)

    assert [pack.name for pack in node_packs.resolve_node_packs({"OnlyLockedKJNode"})] == ["ComfyUI-KJNodes"]
    assert node_packs.resolve_node_packs({"ImageResizeKJv2"}) == []


def test_static_seed_packs_remain_bootstrap_fallback(monkeypatch) -> None:
    import vibecomfy.node_packs as node_packs

    monkeypatch.setattr(node_packs, "read_lockfile", lambda path=Path("custom_nodes.lock"): [])

    packs = node_packs.resolve_node_packs({"ImageResizeKJv2"})

    assert [pack.name for pack in packs] == ["ComfyUI-KJNodes"]
    assert node_packs.unresolved_class_types({"ImageResizeKJv2"}) == []
