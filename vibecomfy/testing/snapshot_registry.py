"""Stem-to-ready-id registry for the curated snapshot corpus.

This is the single source of truth for which ready templates have a
checked-in canonical snapshot under `tests/snapshots/`. Both
`scripts/regenerate_snapshots.py` and the `vibecomfy test verify` CLI
import this mapping.

Stems live flat under `tests/snapshots/`, but ready ids carry the
``image/``/``edit/``/``video/`` kind prefix. Keep this map explicit and
fail-loud on any unmapped stem.
"""

from __future__ import annotations

__all__ = ["STEM_TO_READY_ID"]


STEM_TO_READY_ID: dict[str, str] = {
    "z_image": "image/z_image",
    "flux2_klein_4b_t2i": "image/flux2_klein_4b_t2i",
    "flux2_klein_9b_gguf_t2i": "image/flux2_klein_9b_gguf_t2i",
    "flux2_klein_4b_image_edit_distilled": "edit/flux2_klein_4b_image_edit_distilled",
    "qwen_image_edit": "edit/qwen_image_edit",
    "wan_t2v": "video/wan_t2v",
    "wan_i2v": "video/wan_i2v",
    "ltx2_3_t2v": "video/ltx2_3_t2v",
    "ltx2_3_i2v": "video/ltx2_3_i2v",
}
