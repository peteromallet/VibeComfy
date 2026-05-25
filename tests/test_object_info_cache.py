"""T11: Object-info cache write/parse tests (offline, no ComfyUI required).

Tests:
  1. _cmd_nodes_refresh_object_info mocked HTTP flow: mock the HTTP response,
     assert the written file shape matches the existing 24-snapshot schema.
  2. Offline port convert still works with the cache present and no server.
  3. ``nodes refresh-object-info --help`` exits 0.
"""

from __future__ import annotations

import argparse
import json
import subprocess
import sys
from pathlib import Path
from unittest import mock

import pytest

from vibecomfy.porting.object_info.consume import CACHE_DIR as _PROD_CACHE_DIR
from vibecomfy.porting.object_info.serialize import _make_cache_entry, build_cache


# ---------------------------------------------------------------------------
# Minimal fake object_info response matching the real ComfyUI /object_info shape
# ---------------------------------------------------------------------------

_FAKE_OBJECT_INFO_RESPONSE: dict = {
    "KSampler": {
        "python_module": "nodes",
        "name": "KSampler",
        "display_name": "KSampler",
        "description": "Standard sampler",
        "category": "sampling",
        "function": "sample",
        "input": {
            "required": {
                "model": ["MODEL"],
                "seed": ["INT", {"default": 0, "min": 0, "max": 2**32}],
                "steps": ["INT", {"default": 20, "min": 1, "max": 10000}],
                "cfg": ["FLOAT", {"default": 7.0, "min": 0.0, "max": 100.0}],
                "sampler_name": [["euler", "dpm_2"], {}],
                "scheduler": [["normal", "karras"], {}],
                "positive": ["CONDITIONING"],
                "negative": ["CONDITIONING"],
                "latent_image": ["LATENT"],
                "denoise": ["FLOAT", {"default": 1.0, "min": 0.0, "max": 1.0}],
            },
        },
        "input_order": {
            "required": [
                "model", "seed", "steps", "cfg", "sampler_name", "scheduler",
                "positive", "negative", "latent_image", "denoise",
            ],
            "optional": [],
        },
        "output": ["LATENT"],
        "output_name": ["LATENT"],
        "output_is_list": [False],
    },
    "SaveImage": {
        "python_module": "nodes",
        "name": "SaveImage",
        "display_name": "Save Image",
        "description": "Save image to disk",
        "category": "image",
        "function": "save_images",
        "input": {
            "required": {
                "images": ["IMAGE"],
                "filename_prefix": ["STRING", {"default": "ComfyUI"}],
            },
        },
        "input_order": {"required": ["images", "filename_prefix"], "optional": []},
        "output": ["IMAGE"],
        "output_name": ["images"],
        "output_is_list": [False],
        "output_node": True,
    },
}

_EXPECTED_CACHE_KEYS = frozenset({
    "category", "description", "display_name",
    "input_order", "input_order_all", "inputs",
    "object_info_widget_order", "outputs", "function",
})


# ---------------------------------------------------------------------------
# Helper: load one real existing cache file and return its entry structure
# ---------------------------------------------------------------------------

def _get_real_snapshot_entry() -> dict:
    """Return one entry from an existing committed snapshot file."""
    index_path = _PROD_CACHE_DIR / "index.json"
    if not index_path.is_file():
        pytest.skip("Committed object_info cache not found")
    index = json.loads(index_path.read_text(encoding="utf-8"))
    first_file = next(iter(index.values()))
    pack_path = _PROD_CACHE_DIR / first_file
    pack_data = json.loads(pack_path.read_text(encoding="utf-8"))
    return next(iter(pack_data.values()))


# ---------------------------------------------------------------------------
# T11-1: mocked HTTP response, cache written, shape matches 24-snapshot schema
# ---------------------------------------------------------------------------

def test_refresh_object_info_mocked_http_writes_correct_shape(tmp_path: Path) -> None:
    """Mock the HTTP response; assert written files match the 24-snapshot shape."""
    from vibecomfy.commands.nodes import _cmd_nodes_refresh_object_info

    # Verify that a real committed snapshot follows _EXPECTED_CACHE_KEYS
    real_entry = _get_real_snapshot_entry()
    assert _EXPECTED_CACHE_KEYS.issubset(real_entry.keys()), (
        f"Committed snapshot is missing keys: {_EXPECTED_CACHE_KEYS - real_entry.keys()}"
    )

    # Build fake HTTP response and mock httpx.get
    fake_response = mock.Mock()
    fake_response.json.return_value = _FAKE_OBJECT_INFO_RESPONSE
    fake_response.raise_for_status = mock.Mock()

    cache_dir = tmp_path / "cache"
    cache_dir.mkdir()

    args = argparse.Namespace(
        server_url="http://localhost:8188",
        version="test-snapshot",
        cache_dir=str(cache_dir),
        json=False,
    )

    with mock.patch("httpx.get", return_value=fake_response) as mock_get:
        ret = _cmd_nodes_refresh_object_info(args)

    assert ret == 0, "Command should return 0 on success"
    mock_get.assert_called_once()
    call_url = mock_get.call_args[0][0]
    assert call_url == "http://localhost:8188/object_info"

    # Verify index.json was written
    index_path = cache_dir / "index.json"
    assert index_path.is_file(), "index.json was not written"
    index = json.loads(index_path.read_text(encoding="utf-8"))
    assert "KSampler" in index
    assert "SaveImage" in index

    # Verify per-pack files have the expected key schema (matching real snapshots)
    seen_files: set[str] = set()
    for class_type, filename in index.items():
        if filename in seen_files:
            continue
        seen_files.add(filename)
        pack_path = cache_dir / filename
        assert pack_path.is_file(), f"Pack file {filename} was not written"
        pack_data = json.loads(pack_path.read_text(encoding="utf-8"))
        assert class_type in pack_data
        entry = pack_data[class_type]
        missing = _EXPECTED_CACHE_KEYS - entry.keys()
        assert not missing, (
            f"Cache entry for {class_type} is missing keys: {missing}. "
            f"Entry keys: {sorted(entry.keys())}"
        )

    # Spot-check KSampler widget order: should only include widget-like inputs
    ksampler_pack = cache_dir / index["KSampler"]
    ksampler_data = json.loads(ksampler_pack.read_text(encoding="utf-8"))
    ksampler_entry = ksampler_data["KSampler"]
    widget_order = ksampler_entry["object_info_widget_order"]
    # MODEL/CONDITIONING/LATENT are link-only and should be absent
    for link_type_name in ("model", "positive", "negative", "latent_image"):
        assert link_type_name not in widget_order, (
            f"Link-only input {link_type_name!r} should not appear in widget_order"
        )
    # seed, steps, cfg, sampler_name, scheduler, denoise are widget-like
    for widget_name in ("seed", "steps", "cfg", "sampler_name", "scheduler", "denoise"):
        assert widget_name in widget_order, (
            f"Widget input {widget_name!r} should appear in widget_order"
        )


# ---------------------------------------------------------------------------
# T11-2: offline port convert still works with the existing cache present
# ---------------------------------------------------------------------------

def test_offline_port_convert_works_with_cache(tmp_path: Path) -> None:
    """Offline port convert produces a result even with the cache present.

    The committed cache (vibecomfy/porting/cache/object_info/) must not
    require a live server for standard port_convert to succeed.
    """
    from vibecomfy.porting.convert import port_convert_workflow
    from vibecomfy.porting.workbench import load_port_source
    from vibecomfy.schema import get_authoring_schema_provider

    source = "workflow_corpus/official/image/z_image.json"
    if not Path(source).is_file():
        pytest.skip("z_image workflow not present")

    # This must work purely offline — no server mock needed.
    schema_provider = get_authoring_schema_provider()
    loaded = load_port_source(source, schema_provider=schema_provider)
    result = port_convert_workflow(
        loaded.workflow,
        ready_id="image/z_image",
        source_path=loaded.source_path,
        schema_provider=schema_provider,
        raw_workflow=loaded.raw_workflow,
    )
    assert result.text, "port_convert_workflow should produce non-empty text"
    assert "def build()" in result.text, "Emitted code should contain a build() function"


# ---------------------------------------------------------------------------
# T11-3: ``nodes refresh-object-info --help`` exits 0
# ---------------------------------------------------------------------------

def test_refresh_object_info_help_exits_zero() -> None:
    """``nodes refresh-object-info --help`` must run without error."""
    result = subprocess.run(
        [sys.executable, "-m", "vibecomfy.cli", "nodes", "refresh-object-info", "--help"],
        capture_output=True,
        text=True,
    )
    assert result.returncode == 0, (
        f"--help exited {result.returncode}:\n{result.stderr}"
    )
    assert "refresh-object-info" in result.stdout or "server-url" in result.stdout
