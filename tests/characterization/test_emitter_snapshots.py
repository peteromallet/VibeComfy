"""Characterization-gate emitter snapshots.

Parametrised over every stem in ``STEM_TO_READY_ID``, this module drives
both ``emit_scratchpad_python`` and ``emit_ready_template_python``, neutralises
absolute paths via ``_canon.neutralize_paths``, and diffs the result against
committed golden files under ``tests/characterization/goldens/emitter/``.

Bootstrap: set ``VIBECOMFY_CHARACTERIZATION_WRITE=1`` to regenerate all
goldens.  Stems listed in ``_emitter_xfail.txt`` are expected to drift and
will be reported as XFAIL rather than FAIL.
"""

from __future__ import annotations

import os
import re
from pathlib import Path

import pytest

from vibecomfy import load_workflow_any
from vibecomfy.porting.convert import _ready_metadata, _ready_requirements
from vibecomfy.porting.emitter import emit_ready_template_python, emit_scratchpad_python
from vibecomfy.testing.snapshot_registry import STEM_TO_READY_ID

from . import _canon

# ---------------------------------------------------------------------------
# Paths
# ---------------------------------------------------------------------------

GOLDEN_DIR = Path(__file__).resolve().parent / "goldens" / "emitter"
XFAIL_FILE = Path(__file__).resolve().parent / "_emitter_xfail.txt"

# ---------------------------------------------------------------------------
# Constants
# ---------------------------------------------------------------------------

MAX_SIZE_BYTES = 200 * 1024  # 200 KB cap
_WRITE_MODE = os.environ.get("VIBECOMFY_CHARACTERIZATION_WRITE") == "1"

# Regex that matches absolute filesystem paths (``/dir/...``) but EXCLUDES
# URL-like constructs (``https://``, ``http://``, ``git://``, ``ssh://``,
# ``file://``).
_ABSOLUTE_PATH_RE = re.compile(r"(?<![:\w/])/[A-Za-z0-9_][^/\s\"',)\]}>]+/")


# ---------------------------------------------------------------------------
# Helpers
# ---------------------------------------------------------------------------


def _load_xfail_set() -> frozenset[str]:
    """Return the set of stems expected to fail from _emitter_xfail.txt."""
    if not XFAIL_FILE.exists():
        return frozenset()
    stems: set[str] = set()
    for line in XFAIL_FILE.read_text(encoding="utf-8").splitlines():
        stripped = line.strip()
        if not stripped or stripped.startswith("#"):
            continue
        # Line format: "<stem>  # optional comment"
        stem = stripped.split("#")[0].strip()
        if stem:
            stems.add(stem)
    return frozenset(stems)


def _assert_no_absolute_paths(text: str, stem: str, kind: str) -> None:
    """Fail if *text* contains any residual absolute path."""
    matches = _ABSOLUTE_PATH_RE.findall(text)
    if matches:
        unique = sorted(set(m.strip() for m in matches))
        pytest.fail(
            f"[{stem}/{kind}] Residual absolute paths after neutralization: "
            + ", ".join(unique[:10])
            + (" ..." if len(unique) > 10 else "")
        )


def _write_golden(stem: str, kind: str, text: str) -> None:
    """Atomically write a golden file."""
    target = GOLDEN_DIR / f"{stem}.{kind}.py.golden"
    target.parent.mkdir(parents=True, exist_ok=True)
    tmp = target.with_suffix(target.suffix + ".tmp")
    tmp.write_text(text, encoding="utf-8")
    tmp.replace(target)


def _read_golden(stem: str, kind: str) -> str | None:
    """Read a golden file; return None if it doesn't exist."""
    target = GOLDEN_DIR / f"{stem}.{kind}.py.golden"
    if not target.exists():
        return None
    return target.read_text(encoding="utf-8")


# ---------------------------------------------------------------------------
# Parametrised test
# ---------------------------------------------------------------------------

_KINDS = ("scratchpad", "ready")


@pytest.mark.characterization
@pytest.mark.parametrize("stem", sorted(STEM_TO_READY_ID.keys()))
@pytest.mark.parametrize("kind", _KINDS)
def test_emitter_snapshot(stem: str, kind: str) -> None:
    """Assert emitter output is byte-stable against committed goldens."""
    ready_id = STEM_TO_READY_ID[stem]
    workflow = load_workflow_any(ready_id)
    source_path = workflow.metadata.get("source_workflow") or workflow.metadata.get(
        "ready_template_path"
    )

    # Derive ready-metadata / ready-requirements for the ready-template emitter.
    ready_metadata = dict(workflow.metadata)
    ready_requirements: dict[str, object] = {
        "models": list(workflow.requirements.models),
        "custom_nodes": list(workflow.requirements.custom_nodes),
    }
    # Ensure the template_id is present in metadata (used by emitter).
    ready_metadata.setdefault("ready_template", ready_id)
    ready_metadata.setdefault("source_workflow", str(source_path or ""))

    if kind == "scratchpad":
        source = emit_scratchpad_python(
            workflow,
            workflow_id=getattr(workflow, "id", stem),
            source_path=str(source_path) if source_path else None,
        )
    else:  # kind == "ready"
        source = emit_ready_template_python(
            workflow,
            ready_metadata=ready_metadata,
            ready_requirements=ready_requirements,
            template_id=ready_id,
        )

    # --- Neutralize paths ---
    neutralized = _canon.neutralize_paths(source)

    # --- Size cap ---
    size = len(neutralized.encode("utf-8"))
    xfail_stems = _load_xfail_set()

    # --- Write mode ---
    if _WRITE_MODE:
        _write_golden(stem, kind, neutralized)
        return  # Don't assert in write mode.

    # --- Golden comparison ---
    golden = _read_golden(stem, kind)

    if golden is None:
        if stem in xfail_stems:
            pytest.xfail(f"[{stem}/{kind}] No golden yet; listed in _emitter_xfail.txt.")
        pytest.fail(
            f"[{stem}/{kind}] No golden file found. "
            f"Run with VIBECOMFY_CHARACTERIZATION_WRITE=1 to bootstrap."
        )

    # --- Assert no residual absolute paths ---
    _assert_no_absolute_paths(neutralized, stem, kind)

    # --- Assert size cap ---
    if size > MAX_SIZE_BYTES:
        pytest.fail(
            f"[{stem}/{kind}] Emitter output exceeds 200 KB cap: "
            f"{size} bytes (max {MAX_SIZE_BYTES})."
        )

    # --- Assert golden match ---
    if neutralized != golden:
        if stem in xfail_stems:
            pytest.xfail(
                f"[{stem}/{kind}] Golden mismatch (expected per _emitter_xfail.txt)."
            )
        # Show a compact diff
        import difflib

        diff_lines = list(
            difflib.unified_diff(
                golden.splitlines(keepends=True),
                neutralized.splitlines(keepends=True),
                fromfile=f"golden/{stem}.{kind}.py.golden",
                tofile=f"regenerated/{stem}.{kind}",
            )
        )
        diff_text = "".join(diff_lines[:50])
        pytest.fail(
            f"[{stem}/{kind}] Emitter output drifted from golden:\n{diff_text}"
            f"\nRegenerate with VIBECOMFY_CHARACTERIZATION_WRITE=1."
        )
