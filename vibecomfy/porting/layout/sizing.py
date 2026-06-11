"""Node-size estimation for the fresh-layout engine.

Pure functions — no IR mutation, no external I/O.  Coords pass through
``_canonicalize_coord`` from ``ui_emitter`` for byte-identical emissions.
"""

from __future__ import annotations

from typing import TYPE_CHECKING

from vibecomfy.porting.emit.ui import _canonicalize_coord

if TYPE_CHECKING:
    from vibecomfy.schema.types import NodeSchema
    from vibecomfy.workflow import VibeNode

# ---------------------------------------------------------------------------
# Named constants
# ---------------------------------------------------------------------------

_DEFAULT_NODE_WIDTH = 320
_HEADER_PX = 30
_WIDGET_PX = 24
_SOCKET_PX = 22
_PREVIEW_BONUS_PX = 220

# Classes whose output types indicate a preview/media widget, which adds
# the tall-widget bonus to the estimated height.
_PREVIEW_CLASS_HINTS = (
    "PreviewImage",
    "PreviewVideo",
    "SaveImage",
    "SaveAnimatedWEBP",
    "VHS_VideoCombine",
    "PreviewAudio",
)

# Absolute minimum node size when no inputs or schema information is available.
_FALLBACK_NODE_SIZE = (_DEFAULT_NODE_WIDTH, _HEADER_PX)

# Output-type strings that trigger the preview tall-widget bonus.
_PREVIEW_OUTPUT_TYPES = frozenset({"IMAGE", "VIDEO", "AUDIO", "MASK"})


# ---------------------------------------------------------------------------
# Public API
# ---------------------------------------------------------------------------


def estimate_node_size(
    node: VibeNode,
    schema: NodeSchema | None,
) -> tuple[int, int]:
    """Return ``(width, height)`` for *node*, canonicalized.

    When *schema* is ``None`` the deterministic fallback is used:
    ``width = 320``, ``height = 30 + 22 * max(len(node.inputs or {}), 0)``.
    When *schema* is provided and the node's class is in
    ``_PREVIEW_CLASS_HINTS`` **and** any schema output type is one of
    ``IMAGE``, ``VIDEO``, ``AUDIO``, or ``MASK``, the height receives the
    ``_PREVIEW_BONUS_PX`` tall-widget bonus.

    All returned values are rounded through ``_canonicalize_coord`` and cast
    to ``int`` for byte-identical emissions.
    """
    width = float(_DEFAULT_NODE_WIDTH)

    # Input-socket rows
    input_count = len(node.inputs) if node.inputs else 0
    height = float(_HEADER_PX + _SOCKET_PX * max(input_count, 0))

    # Tall-widget bonus — only when schema provides output-type data AND the
    # class is a known preview/media class.
    if schema is not None and node.class_type in _PREVIEW_CLASS_HINTS:
        for out_spec in schema.outputs:
            if out_spec.type is not None and out_spec.type.upper() in _PREVIEW_OUTPUT_TYPES:
                height += float(_PREVIEW_BONUS_PX)
                break

    return int(_canonicalize_coord(width)), int(_canonicalize_coord(height))
