"""Canonicalization helpers for the characterization gate.

Every helper in this module is designed to strip volatility from outputs that
are otherwise deterministic so that two consecutive runs with
``PYTHONHASHSEED=0`` produce byte-identical results.
"""

from __future__ import annotations

import hashlib
import re
from pathlib import Path
from typing import Any

# ---------------------------------------------------------------------------
# Path neutralization
# ---------------------------------------------------------------------------

# The repo root is resolved once at import time (the conftest guarantees
# PYTHONHASHSEED=0 before any characterization test is collected).
_REPO_ROOT = Path(__file__).resolve().parents[2]

# Match an absolute path that starts with the repo root.
_REPO_PATH_RE = re.compile(re.escape(str(_REPO_ROOT)) + r"(?:/[^\s\"',)\]}>]*)?(?=/|\"|'|,|\)|\]|\}|>|\s|$)")


def neutralize_paths(text: str) -> str:
    """Replace absolute paths rooted at the repo checkout with ``<REPO_ROOT>``."""
    return _REPO_PATH_RE.sub("<REPO_ROOT>", text)


# ---------------------------------------------------------------------------
# Seed neutralization
# ---------------------------------------------------------------------------

_SEED_RE = re.compile(r'"seed"\s*:\s*\d+')
_NOISE_SEED_RE = re.compile(r'"noise_seed"\s*:\s*\d+')

_SEED_REPLACEMENT = '"seed": 0'
_NOISE_SEED_REPLACEMENT = '"noise_seed": 0'


def neutralize_seeds(text: str) -> str:
    """Replace literal ``"seed": <int>`` and ``"noise_seed": <int>`` with ``0``.

    This is a text-level normalizer for JSON / Python repr output — it does
    not parse JSON, so it works on any text blob that contains those patterns.
    """
    text = _SEED_RE.sub(_SEED_REPLACEMENT, text)
    text = _NOISE_SEED_RE.sub(_NOISE_SEED_REPLACEMENT, text)
    return text


# ---------------------------------------------------------------------------
# Volatile UI stripping
# ---------------------------------------------------------------------------

# Fields that Litegraph may reorder / reassign across runs even when the
# workflow is semantically identical.
_VOLATILE_UI_FIELDS: frozenset[str] = frozenset(
    {
        "pos",
        "size",
        "order",
        "flags",
        "last_node_id",
        "last_link_id",
    }
)


def strip_volatile_ui(ui: dict[str, Any]) -> dict[str, Any]:
    """Return a shallow copy of *ui* with volatile Litegraph fields removed.

    Only top-level dict keys are pruned; nested dicts and lists are left
    untouched.  This is sufficient for the characterization agent-edit
    roundtrip assertions, which compare structural hashes of the UI dict.
    """
    return {k: v for k, v in ui.items() if k not in _VOLATILE_UI_FIELDS}


# ---------------------------------------------------------------------------
# Structural hash
# ---------------------------------------------------------------------------


def structural_hash(data: object) -> str:
    """Return a stable SHA-256 hex digest of *data*.

    *data* is serialized via ``repr()`` with ``ensure_ascii=False``  before
    hashing.  This is intentionally NOT JSON-based — ``repr()`` is stable
    under ``PYTHONHASHSEED=0`` and captures Python-specific types (tuples,
    sets, etc.) that JSON would lose.
    """
    raw = repr(data).encode("utf-8")
    return hashlib.sha256(raw).hexdigest()
