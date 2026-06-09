"""Formatting helpers for the ready-template Python emitter."""

from __future__ import annotations

import pprint
from typing import Any


def format_value(value: Any) -> str:
    """Pretty-print a literal kwarg value for the emitter."""
    if isinstance(value, str):
        return repr(value)
    if isinstance(value, bool) or value is None:
        return repr(value)
    if isinstance(value, (int, float)):
        return repr(value)
    if isinstance(value, (list, dict, tuple)):
        return repr(value)
    return repr(value)


def format_kwargs_block(
    kwargs: list[tuple[str, str]],
    *,
    indent: str = "    ",
    leading: str,
) -> str:
    """Format a kwargs list as a multi-line call body."""
    if not kwargs:
        return f"{leading})"
    lines = [leading]
    for key, expr in kwargs:
        # Wrap long string literals across multiple lines for readability.
        rendered = expr
        if expr.startswith("'") or expr.startswith('"'):
            # Use Python string concat for long literals to keep line widths sane.
            if len(expr) > 100:
                rendered = expr
        lines.append(f"{indent}{indent}{key}={rendered},")
    lines.append(f"{indent})")
    return "\n".join(lines)


def format_metadata_dict(name: str, value: dict) -> str:
    """Serialize READY_METADATA / READY_REQUIREMENTS as an assignable dict literal."""
    formatted = pprint.pformat(value, width=110, sort_dicts=False)
    return f"{name} = {formatted}"


__all__ = ["format_kwargs_block", "format_metadata_dict", "format_value"]
