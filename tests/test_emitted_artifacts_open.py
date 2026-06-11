"""Structural-parse tests for open-from-file paths.

These two structural-parse assertions (JSON and PNG) stand in for drag-drop AND
File>Open — no DOM is exercised.  A Playwright harness is explicitly out of scope
per the M7 milestone assumptions.

Each test:
  1. Loads a ready template, emits it to UI JSON, builds a prior store.
  2. Deserializes the emitted JSON (or extracts it from a synthesized PNG).
  3. Passes the result directly to ``convert_to_vibe_format`` — asserts no exception.
  4. Re-emits with the prior store and asserts ``change_report.content_edits.preserved``
     is non-empty, confirming node-identity survives the round-trip.
"""
from __future__ import annotations

import io
import json

import pytest

try:
    import PIL.Image
    import PIL.PngImagePlugin
except ImportError:
    pytest.skip("Pillow not installed; skip artifact-open tests", allow_module_level=True)

from vibecomfy import load_workflow_any
from vibecomfy.ingest.normalize import convert_to_vibe_format
from vibecomfy.porting.layout_store import store_from_ui_json
from vibecomfy.porting.emit.ui import emit_ui_json
from vibecomfy.schema import get_schema_provider

_TEMPLATES = [
    "image/z_image",
    "video/ltx2_3_i2v",
]

_PROVIDER = None


def _provider():
    global _PROVIDER
    if _PROVIDER is None:
        _PROVIDER = get_schema_provider("local")
    return _PROVIDER


def _first_emit(template_id: str) -> tuple[dict, dict]:
    """Load template, emit to UI JSON, build prior store. Returns (emitted_ui, prior_store)."""
    wf = load_workflow_any(template_id)
    emitted = emit_ui_json(wf, schema_provider=_provider())
    prior = store_from_ui_json(emitted)
    return emitted, prior


def _assert_preserved_nonempty(graph: dict, prior_store: dict) -> None:
    """Convert graph → VibeWorkflow, re-emit with prior_store, assert preserved non-empty."""
    wf2 = convert_to_vibe_format(graph)
    cr_out: list = []
    emit_ui_json(
        wf2,
        schema_provider=_provider(),
        prior_store=prior_store,
        change_report_out=cr_out,
    )
    assert cr_out, "emit_ui_json did not populate change_report_out"
    assert cr_out[0].content_edits.preserved, (
        f"Expected at least one preserved node after round-trip; "
        f"new_auto_placed={cr_out[0].content_edits.new_auto_placed}"
    )


@pytest.mark.parametrize("template_id", _TEMPLATES)
def test_json_open(template_id: str) -> None:
    """JSON round-trip: serialize emitted graph to bytes, json.loads, convert, re-emit.

    Stands in for File>Open with a .json workflow file (no DOM exercised).
    """
    emitted, prior = _first_emit(template_id)

    json_bytes = json.dumps(emitted).encode()
    loaded_graph = json.loads(json_bytes)

    # Must not raise
    wf2 = convert_to_vibe_format(loaded_graph)
    assert wf2 is not None

    _assert_preserved_nonempty(loaded_graph, prior)


@pytest.mark.parametrize("template_id", _TEMPLATES)
def test_png_open(template_id: str) -> None:
    """PNG round-trip: embed workflow in tEXt chunk via PIL, extract, convert, re-emit.

    Stands in for drag-drop or File>Open with a .png containing an embedded workflow.
    ComfyUI's SaveImage uses PngInfo.add_text('prompt', json.dumps(workflow)) — this
    test synthesizes that artifact programmatically since no emit-to-png path exists.
    Extraction uses PIL directly (per gate prerequisite_ordering-4).
    """
    emitted, prior = _first_emit(template_id)

    # Synthesize PNG with workflow in 'prompt' tEXt chunk (same as ComfyUI SaveImage)
    png_info = PIL.PngImagePlugin.PngInfo()
    png_info.add_text("prompt", json.dumps(emitted))
    img = PIL.Image.new("RGB", (64, 64), color=(0, 0, 0))
    bio = io.BytesIO()
    img.save(bio, format="PNG", pnginfo=png_info)
    bio.seek(0)

    # Extract via PIL — do not use any vendored comfyui helper
    with PIL.Image.open(bio) as opened:
        raw_chunk = opened.text["prompt"]
    loaded_from_png = json.loads(raw_chunk)

    # Must not raise
    wf3 = convert_to_vibe_format(loaded_from_png)
    assert wf3 is not None

    _assert_preserved_nonempty(loaded_from_png, prior)
