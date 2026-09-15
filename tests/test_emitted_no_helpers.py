"""Corpus-wide assertion: zero helper raw_call lines in any ready_templates/**/*.py.

After the resolver+emitter double-gate (T3-T6) and template regeneration (T10-T11),
no ready template may emit raw_call for any resolvable helper class.  This test
fails while templates still contain helpers — regeneration resolves that.
"""

from __future__ import annotations

import re
from pathlib import Path

import pytest

_HELPER_CLASSES = (
    "GetNode",
    "SetNode",
    "Reroute",
    "PrimitiveNode",
    "PrimitiveBoolean",
    "PrimitiveInt",
    "PrimitiveFloat",
    "PrimitiveString",
    "PrimitiveStringMultiline",
)

# Matches raw_call('ClassName', ...) or raw_call(wf, 'ClassName', ...)
_RAW_CALL_HELPER_RE = re.compile(
    r"\braw_call\s*\((?:[^,]+,\s*)?['\"]("
    + "|".join(_HELPER_CLASSES)
    + r")['\"]"
)


def _collect_ready_template_paths() -> list[Path]:
    root = Path(__file__).resolve().parent.parent / "ready_templates"
    if not root.is_dir():
        return []
    return sorted(root.rglob("*.py"))


@pytest.mark.parametrize(
    "template_path",
    _collect_ready_template_paths(),
    ids=lambda p: str(p.relative_to(p.parent.parent.parent)),
)
def test_no_helper_raw_call_in_ready_template(template_path: Path) -> None:
    """Every ready template must have zero raw_call lines for helper classes."""
    text = template_path.read_text()
    matches = _RAW_CALL_HELPER_RE.findall(text)
    if matches:
        found = ", ".join(sorted(set(matches)))
        pytest.fail(
            f"{template_path.relative_to(template_path.parent.parent.parent)} "
            f"contains raw_call to helper class(es): {found}. "
            "Helpers must be stripped by the resolver before emission — "
            "recreate this template from its canonical bundle with templates create."
        )
