from __future__ import annotations

import tempfile
from pathlib import Path

from vibecomfy.porting.reorganise.visualize import render_layout_png


def test_render_layout_png_produces_non_empty_png_from_minimal_ui_json() -> None:
    """Smoke test: render_layout_png writes a non-empty PNG file for a minimal UI JSON."""
    ui_json: dict = {
        "nodes": [
            {
                "id": 1,
                "type": "CheckpointLoaderSimple",
                "pos": [100.0, 200.0],
                "size": [300.0, 120.0],
            },
            {
                "id": 2,
                "type": "CLIPTextEncode",
                "pos": [450.0, 200.0],
                "size": [280.0, 140.0],
            },
        ],
        "groups": [
            {
                "title": "Loaders",
                "bounding": [80.0, 160.0, 340.0, 200.0],
            },
            {
                "title": "Conditioning",
                "bounding": [430.0, 160.0, 320.0, 220.0],
            },
        ],
    }

    with tempfile.TemporaryDirectory() as tmpdir:
        png_path = Path(tmpdir) / "layout.png"
        render_layout_png(ui_json, png_path)

        assert png_path.exists(), "PNG file must be created"
        assert png_path.stat().st_size > 0, "PNG file must be non-empty"


def test_render_layout_png_produces_non_empty_png_from_fixture_json() -> None:
    """Smoke test: render_layout_png handles a real fixture-based UI JSON and writes a non-empty PNG."""
    fixture_path = (
        Path(__file__).resolve().parent
        / "fixtures"
        / "reorganise"
        / "simple_text_to_image.json"
    )
    ui_json_raw = fixture_path.read_text(encoding="utf-8")
    import json

    ui_json = json.loads(ui_json_raw)

    with tempfile.TemporaryDirectory() as tmpdir:
        png_path = Path(tmpdir) / "layout_fixture.png"
        render_layout_png(ui_json, png_path)

        assert png_path.exists(), "PNG file must be created from fixture"
        assert png_path.stat().st_size > 0, "PNG file must be non-empty from fixture"
