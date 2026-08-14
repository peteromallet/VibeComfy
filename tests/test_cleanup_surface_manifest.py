"""Frozen cleanup-surface manifest enforcement (T-036, ORACLE-6).

Loads the frozen surface manifest (tests/fixtures/agent_edit/cleanup_surface_manifest.json,
captured by ORACLE-1 T-004/T-005) and asserts the LIVE
``vibecomfy.comfy_nodes.agent.edit`` module still exposes the pinned surface.

Semantics per S2: ``__all__`` is membership-only — order is NOT contractual, so
every comparison is set equality, never list order.

The suite MUST pass TODAY against the current pre-split edit module — that is the
activation: it proves the frozen surface is intact right now and will catch
regressions during T-037..T-041. Names the manifest marks ``required_post_split``
are asserted as a declared contract (membership in the manifest list), not as live
attrs — ``load_agent_generated_scratchpad`` is absent pre-split and flips to a live
presence after T-039 makes it real.

T-042 (ORACLE-7, S5) adds session-manifest enforcement to this same file: the
manifest's ``session`` section pins session.__all__ (23), public_direct (31)
and private_imported_by_name (23), asserted against the live session module the
same way the edit tests assert against edit. The suite MUST pass TODAY against
the pre-extraction session module — that is the activation: T-043..T-048 will be
checked against the frozen session surface.
"""

from __future__ import annotations

import json
from pathlib import Path

import pytest

from vibecomfy.comfy_nodes.agent import edit as agent_edit
from vibecomfy.comfy_nodes.agent import session as agent_session


ROOT = Path(__file__).resolve().parents[1]
MANIFEST_PATH = ROOT / "tests/fixtures/agent_edit/cleanup_surface_manifest.json"

# Frozen counts pinned by the ORACLE-1 capture; the name sets themselves are
# read from the manifest (never hardcoded here), only the counts are pinned.
PINNED_EDIT_EXPORT_COUNT = 459  # 463 - 1 peer removal - 3 precedent/adaptation prompt machinery removed in R1-B (fix 5)
PINNED_SESSION_ALL_COUNT = 23
PINNED_SESSION_PUBLIC_DIRECT_COUNT = 31
PINNED_SESSION_PRIVATE_IMPORTED_COUNT = 23


def _load_manifest() -> dict:
    data = json.loads(MANIFEST_PATH.read_text(encoding="utf-8"))
    if not isinstance(data, dict):
        raise ValueError(f"manifest must be a JSON object: {MANIFEST_PATH}")
    return data


_MANIFEST = _load_manifest()


def _edit_section() -> dict:
    return _MANIFEST["edit"]


def _session_section() -> dict:
    # T-042: session-surface enforcement (S5). The manifest's session section
    # pins session.__all__ (23, membership-only), public_direct (31) and
    # private_imported_by_name (23); the tests below assert those against the
    # live session module the same way the edit tests assert against edit.
    return _MANIFEST["session"]


# ── edit.__all__ (S2 membership-only) ────────────────────────────────────────


def test_edit_all_matches_frozen_manifest_membership_only() -> None:
    """`set(edit.__all__)` equals the frozen manifest set; order is irrelevant."""
    manifest_names = _edit_section()["__all__"]
    assert set(agent_edit.__all__) == set(manifest_names)


def test_edit_all_length_matches_frozen_count() -> None:
    """Sanity: the manifest's edit __all__ length matches the pinned 472 count."""
    assert len(_edit_section()["__all__"]) == PINNED_EDIT_EXPORT_COUNT


# ── S3 must-survive attrs: patched + imported-by-name ────────────────────────


@pytest.mark.parametrize("name", _edit_section()["patched_via_edit_module"])
def test_patched_name_survives_as_live_attr(name: str) -> None:
    """Every monkeypatched name stays a top-level edit-module attr and exported."""
    assert hasattr(agent_edit, name), f"{name} missing from live edit module"
    assert name in agent_edit.__all__, f"{name} missing from edit.__all__"


@pytest.mark.parametrize("name", _edit_section()["imported_by_name"])
def test_imported_name_survives_as_live_attr(name: str) -> None:
    """Every imported-by-name surface stays a top-level edit-module attr."""
    assert hasattr(agent_edit, name), f"{name} missing from live edit module"


# ── required_post_split (T-039 contract, not yet live) ───────────────────────


def test_required_post_split_contract_declared_in_manifest() -> None:
    """Names marked required_post_split are a declared contract, not live attrs.

    load_agent_generated_scratchpad is currently only a local import inside
    _frag_transform_stages.py — hasattr(edit, ...) is False today. Asserting
    membership in the manifest's required_post_split list is the T-039 contract;
    after T-039 makes it a top-level edit-module attr, this test can add a live
    hasattr assertion for each name in the list (the flip is expected).
    """
    required = _edit_section()["required_post_split"]
    assert required, "required_post_split must declare the post-split contract"
    assert "load_agent_generated_scratchpad" in required
    # Post-T-039 flip point: for name in required: assert hasattr(agent_edit, name)


# ── session surface (S5, T-042): __all__ 23 / public 31 / private 23 ─────────


def test_session_all_matches_frozen_manifest_membership_only() -> None:
    """`set(session.__all__)` equals the frozen manifest set; order is irrelevant."""
    manifest_names = _session_section()["__all__"]
    assert set(agent_session.__all__) == set(manifest_names)


@pytest.mark.parametrize(
    ("key", "pinned"),
    [
        ("__all__", PINNED_SESSION_ALL_COUNT),
        ("public_direct", PINNED_SESSION_PUBLIC_DIRECT_COUNT),
        ("private_imported_by_name", PINNED_SESSION_PRIVATE_IMPORTED_COUNT),
    ],
)
def test_session_section_lengths_match_frozen_counts(key: str, pinned: int) -> None:
    """Sanity: each session manifest list length matches its pinned 23/31/23 count."""
    assert len(_session_section()[key]) == pinned


@pytest.mark.parametrize("name", _session_section()["public_direct"])
def test_session_public_direct_name_survives_as_live_attr(name: str) -> None:
    """Every public_direct name stays a top-level session-module attr."""
    assert hasattr(agent_session, name), f"{name} missing from live session module"


@pytest.mark.parametrize("name", _session_section()["private_imported_by_name"])
def test_session_private_imported_name_survives_as_live_attr(name: str) -> None:
    """Every _-prefixed imported-by-name helper stays a top-level session-module attr.

    These must remain importable by name for the T-048 monkeypatch/importer
    compatibility, not just present via `session.<name>`.
    """
    assert hasattr(agent_session, name), f"{name} missing from live session module"
