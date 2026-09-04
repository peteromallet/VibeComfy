"""Tests for ``vibecomfy.porting.wrappers.discovery``.

Each test exercises one discovery source against a synthetic fixture written
into a temporary directory. ``live`` is exercised via a tiny stub server
substituted into ``urllib.request.urlopen``.
"""
from __future__ import annotations

import io
import json
from pathlib import Path
from unittest import mock

import pytest

from vibecomfy.porting.wrappers import discovery as wd


@pytest.fixture
def sample_object_info() -> dict:
    return {
        "FakeClass": {
            "category": "fake/category",
            "description": "A fake node for testing.",
            "display_name": "Fake Class",
            "inputs": {
                "required": {
                    "model": ["MODEL", {}],
                    "seed": [
                        "INT",
                        {"default": 42, "min": 0, "max": 1000, "step": 1},
                    ],
                    "mode": [
                        ["alpha", "beta", "gamma"],
                        {"default": "alpha"},
                    ],
                },
                "optional": {
                    "extra": ["STRING", {"default": "hello"}],
                },
            },
            "outputs": [
                {"name": "IMAGE", "type": "IMAGE", "is_list": False},
            ],
            "pack": "fake-pack",
        },
    }


def _write_snapshot(root: Path, pack: str, payload: dict, *, rev: str = "v1") -> Path:
    root.mkdir(parents=True, exist_ok=True)
    path = root / f"{pack}@{rev}.json"
    path.write_text(json.dumps(payload, sort_keys=True, indent=2))
    return path


def test_discover_from_snapshot(tmp_path: Path, sample_object_info: dict) -> None:
    snapshot_dir = tmp_path / "snapshots"
    _write_snapshot(snapshot_dir, "fake-pack", sample_object_info)
    specs = wd.discover_pack(
        "fake-pack",
        sources=("snapshot",),
        snapshot_dir=snapshot_dir,
    )
    assert len(specs) == 1
    spec = specs[0]
    assert spec.class_type == "FakeClass"
    assert spec.pack_slug == "fake-pack"
    assert spec.outputs == ("IMAGE",)
    assert spec.output_types == ("IMAGE",)
    assert "snapshot" in spec.source_provenance
    assert spec.inputs["seed"].type == "INT"
    assert spec.inputs["seed"].default == 42
    assert spec.inputs["seed"].has_default is True
    assert spec.inputs["mode"].type == "COMBO"
    assert spec.inputs["mode"].options == ("alpha", "beta", "gamma")
    assert spec.inputs["mode"].default == "alpha"
    assert spec.inputs["model"].type == "MODEL"
    assert spec.inputs["model"].required is True
    assert spec.inputs["extra"].required is False


def test_discover_from_cache(tmp_path: Path, sample_object_info: dict) -> None:
    cache_dir = tmp_path / "cache"
    _write_snapshot(cache_dir, "fake-pack", sample_object_info)
    specs = wd.discover_pack(
        "fake-pack",
        sources=("cache",),
        cache_dir=cache_dir,
    )
    assert len(specs) == 1
    assert "cache" in specs[0].source_provenance


def test_discover_precedence_falls_through(tmp_path: Path, sample_object_info: dict) -> None:
    # cache missing, snapshot present -> should use snapshot.
    snapshot_dir = tmp_path / "snap"
    _write_snapshot(snapshot_dir, "fake-pack", sample_object_info)
    specs = wd.discover_pack(
        "fake-pack",
        sources=("cache", "snapshot"),
        cache_dir=tmp_path / "missing-cache",
        snapshot_dir=snapshot_dir,
    )
    assert specs and "snapshot" in specs[0].source_provenance


def test_discover_live_filters_by_pack(monkeypatch: pytest.MonkeyPatch) -> None:
    payload = {
        "AAA": {"pack": "fake-pack", "inputs": {"required": {}}, "outputs": []},
        "BBB": {"pack": "other-pack", "inputs": {"required": {}}, "outputs": []},
    }

    class _FakeResponse:
        def __init__(self, body: bytes) -> None:
            self._body = body
        def read(self) -> bytes:
            return self._body
        def __enter__(self):
            return self
        def __exit__(self, *exc):
            return False

    def fake_urlopen(url, timeout=15):  # noqa: ARG001
        return _FakeResponse(json.dumps(payload).encode("utf-8"))

    monkeypatch.setattr(wd.urllib.request, "urlopen", fake_urlopen)
    specs = wd.discover_pack(
        "fake-pack",
        sources=("live",),
        server_url="http://localhost:8188",
    )
    assert [s.class_type for s in specs] == ["AAA"]


def test_discover_from_source_ast(tmp_path: Path) -> None:
    pack_dir = tmp_path / "custom_nodes" / "fake-pack"
    pack_dir.mkdir(parents=True)
    (pack_dir / "nodes.py").write_text(
        """
class Foo:
    @classmethod
    def INPUT_TYPES(cls):
        return {
            "required": {
                "model": ("MODEL",),
                "seed": ("INT", {"default": 7, "min": 0, "max": 100}),
                "mode": (["a", "b"], {"default": "a"}),
            },
            "optional": {
                "extra": ("STRING", {"default": "hi"}),
            },
        }
    RETURN_TYPES = ("LATENT",)
    RETURN_NAMES = ("samples",)
    CATEGORY = "test/category"

NODE_CLASS_MAPPINGS = {"Foo": Foo}
"""
    )
    specs = wd.discover_pack(
        "fake-pack",
        sources=("source",),
        custom_nodes_dir=tmp_path / "custom_nodes",
    )
    assert len(specs) == 1
    spec = specs[0]
    assert spec.class_type == "Foo"
    assert spec.outputs == ("samples",)
    assert spec.output_types == ("LATENT",)
    assert spec.category == "test/category"
    assert spec.inputs["mode"].type == "COMBO"
    assert spec.inputs["mode"].options == ("a", "b")
    assert spec.inputs["seed"].default == 7
    assert "source" in spec.source_provenance


def test_discover_pack_returns_empty_when_no_source() -> None:
    specs = wd.discover_pack(
        "nonexistent-pack",
        sources=("cache", "snapshot", "source"),
        cache_dir="/tmp/does-not-exist-cache-xyz",
        snapshot_dir="/tmp/does-not-exist-snap-xyz",
        custom_nodes_dir="/tmp/does-not-exist-custom-xyz",
    )
    assert specs == []


def test_known_pack_slug_resolves_known_class() -> None:
    # KSampler is core, not a custom pack — should return None.
    assert wd.known_pack_slug("KSampler") is None
    # ComfyUI-WanVideoWrapper has WanVideoSampler.
    assert wd.known_pack_slug("WanVideoSampler") == "ComfyUI-WanVideoWrapper"


def test_discover_all_uses_canonical_lock_entries_without_toml_keys(tmp_path: Path) -> None:
    lockfile = tmp_path / "custom_nodes.lock"
    lockfile.write_text(
        """
[nodepacks.FirstPack]
name = "FirstPack"
commit = "abc"
url = "https://example.test/first.git"

[nodepacks.SecondPack]
name = "SecondPack"
commit = "def"
url = "https://example.test/second.git"
""",
        encoding="utf-8",
    )

    discovered = wd.discover_all(
        lockfile=lockfile,
        sources=("source",),
        custom_nodes_dir=tmp_path / "custom_nodes",
        cache_dir=tmp_path / "cache",
        snapshot_dir=tmp_path / "snapshot",
    )

    assert list(discovered) == ["FirstPack", "SecondPack"]
    assert not {"name", "slug", "source", "commit", "url"} & set(discovered)


def test_repository_lock_discovery_projects_exact_13_entries() -> None:
    expected = [
        "ComfyUI-DepthAnythingV2",
        "ComfyUI-GGUF",
        "ComfyUI-KJNodes",
        "ComfyUI-LTXVideo",
        "ComfyUI-Qwen3-TTS",
        "ComfyUI-QwenTTS",
        "ComfyUI-VideoHelperSuite",
        "ComfyUI-WanAnimatePreprocess",
        "ComfyUI-WanVideoWrapper",
        "ComfyUI-segment-anything-2",
        "ExamplePack",
        "comfyui_controlnet_aux",
        "rgthree-comfy",
    ]

    assert [entry.name for entry in wd.read_lockfile(Path("custom_nodes.lock"))] == expected
    assert wd._read_lockfile_pack_slugs(Path("custom_nodes.lock")) == expected
    assert list(wd.discover_all(lockfile="custom_nodes.lock", sources=())) == expected


def test_discover_all_surfaces_malformed_lockfile(tmp_path: Path) -> None:
    lockfile = tmp_path / "custom_nodes.lock"
    lockfile.write_text(
        """
[nodepacks.Broken]
source = "git"
commit = "abc"
url = "https://example.test/broken.git"
unterminated = [
""",
        encoding="utf-8",
    )

    with pytest.raises(ValueError):
        wd.discover_all(lockfile=lockfile)


def test_discover_all_parses_before_discovery_and_rejects_partial_lock(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch,
) -> None:
    lockfile = tmp_path / "custom_nodes.lock"
    lockfile.write_text(
        """
[nodepacks.Valid]
source = "local"
path = "."

[nodepacks.Broken]
source = "git"
commit = ["not-a-string"]
url = "https://example.test/broken.git"
""",
        encoding="utf-8",
    )
    called = False

    def fail_if_called(*args, **kwargs):
        nonlocal called
        called = True
        raise AssertionError("discover_pack must not run for a malformed lock")

    monkeypatch.setattr(wd, "discover_pack", fail_if_called)
    with pytest.raises(ValueError, match="commit must be a string"):
        wd.discover_all(lockfile=lockfile)
    assert called is False


def test_sha256_of_path_is_stable(tmp_path: Path) -> None:
    p = tmp_path / "x.txt"
    p.write_text("hello")
    a = wd.sha256_of_path(p)
    b = wd.sha256_of_path(p)
    assert a == b
    assert len(a) == 64
