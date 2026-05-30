"""M4 fresh layout engine (Phase 1 primitives → Phase 2 composition).

The public entry-point is :func:`layout`, which accepts the workflow IR and
returns a :class:`LayoutResult` carrying positions and groups.  This module
re-exports :class:`LayoutResult` so callers can import it from here.
"""

from __future__ import annotations

from vibecomfy.porting.layout.engine import layout
from vibecomfy.porting.layout.types import LayoutResult

__all__ = ["LayoutResult", "layout"]
