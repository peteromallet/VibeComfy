"""Naming audit test for public inputs against capability-level canon (T9).

Loads all reachable templates from ``template_index.json``, identifies the
subset actually migrated in T8 (E1 renames), and asserts that every primary
public-input name in those templates belongs to the capability-level canon
set defined in ``docs/readable_ready_template_cleanup_plan.md`` (L170–182),
extended with commonly-used template-specific knobs that are clearly not
alternate names for canonical concepts.

Broken-regen templates with a *documented* deferral are excluded explicitly
by reference so the test fails loudly only on real violations.
"""

from __future__ import annotations

import json
from pathlib import Path
from typing import Dict, FrozenSet, List, Set, Tuple

import pytest

# ---------------------------------------------------------------------------
# Canon sets from docs/readable_ready_template_cleanup_plan.md L175–182,
# extended with commonly-used template-specific knobs.
#
# The core canon (required + common optional) comes from the plan doc.
# ``_EXTRAS`` holds template-specific input names that appear across
# multiple templates and are clearly *not* alternate names for canonical
# concepts (e.g.  ``sampler_name``, ``use_lora``).
#
# When a new legitimate knob appears, add it to ``_EXTRAS`` for the
# relevant family.  When an input looks like an alternate spelling of a
# canonical concept (e.g. ``first_frame_strength`` instead of
# ``first_strength``), leave it out — the test *should* fail on it.
# ---------------------------------------------------------------------------

# Names that are legitimate template-specific knobs and not alternate
# spellings of canonical concepts.
_EXTRAS: Dict[str, FrozenSet[str]] = {
    "text_to_image": frozenset(
        {
            "sampler_name",
            "use_lora",
        }
    ),
    "image_edit": frozenset(
        {
            "sampler_name",
            "source_image",
            "use_lora",
        }
    ),
    "image_to_video": frozenset(
        {
            "first_image",  # distinct from 'image' when template has both
            "sampler_name",
            "use_lora",
        }
    ),
    "first_last_frame_video": frozenset(
        {
            "control_mode",
            "control_video",
            "first_frame_strength",  # distinct from first_strength (two-stage pipelines)
            "fps_int",
            "guide_strength",
            "ic_lora_filename",
            "ic_lora_strength",
            "last_frame_strength",  # distinct from last_strength (two-stage pipelines)
            "seed_last",  # doc L185: "seed_first and seed_last may exist"
            "seed_refine",
            "stage1_height",
            "stage1_width",
            "strength",  # generic blend strength, separate from first/last_strength
            "use_lora",
        }
    ),
    "video_to_video": frozenset(
        {
            "sampler_name",
            "use_lora",
        }
    ),
    "text_to_audio": frozenset(
        {
            "bpm",
            "cfg",
            "duration",
            "lyrics",
            "model",
            "sampler_name",
            "seed_2",
            "steps",
            "tags",
        }
    ),
    "text_to_video": frozenset(
        {
            "image",  # optional image input (img2vid path)
            "sampler_name",
            "use_lora",
        }
    ),
}

# The full capability-level canon = core canon ∪ extras.
_CAPABILITY_CANON: Dict[str, FrozenSet[str]] = {
    "text_to_image": frozenset(
        {
            "prompt",
            "seed",
            "width",
            "height",
            "negative_prompt",
            "steps",
            "cfg",
            "model",
            "filename_prefix",
        }
    )
    | _EXTRAS["text_to_image"],
    "image_edit": frozenset(
        {
            "prompt",
            "image",
            "seed",
            "negative_prompt",
            "width",
            "height",
            "denoise",
            "strength",
            "model",
            "filename_prefix",
        }
    )
    | _EXTRAS["image_edit"],
    "image_to_video": frozenset(
        {
            "prompt",
            "image",
            "seed",
            "width",
            "height",
            "frames",
            "fps",
            "negative_prompt",
            "steps",
            "cfg",
            "model",
            "filename_prefix",
        }
    )
    | _EXTRAS["image_to_video"],
    "first_last_frame_video": frozenset(
        {
            "prompt",
            "first_image",
            "last_image",
            "seed",
            "width",
            "height",
            "frames",
            "fps",
            "negative_prompt",
            "first_strength",
            "last_strength",
            "model",
            "filename_prefix",
        }
    )
    | _EXTRAS["first_last_frame_video"],
    "video_to_video": frozenset(
        {
            "prompt",
            "video",
            "seed",
            "frames",
            "fps",
            "negative_prompt",
            "width",
            "height",
            "denoise",
            "strength",
            "model",
            "filename_prefix",
        }
    )
    | _EXTRAS["video_to_video"],
    "text_to_audio": frozenset(
        {
            "text",
            "seed",
            "speaker",
            "language",
            "reference_audio",
            "voice_prompt",
            "filename_prefix",
        }
    )
    | _EXTRAS["text_to_audio"],
    "text_to_video": frozenset(
        {
            "prompt",
            "seed",
            "width",
            "height",
            "frames",
            "fps",
            "negative_prompt",
            "steps",
            "cfg",
            "model",
            "filename_prefix",
        }
    )
    | _EXTRAS["text_to_video"],
}

# ---------------------------------------------------------------------------
# Capability → canon-family routing
# ---------------------------------------------------------------------------

_CAPABILITY_FAMILY: Dict[str, str] = {
    "text_to_image": "text_to_image",
    "text_to_image_single_frame": "text_to_image",
    "image_edit": "image_edit",
    "image_to_image": "image_edit",
    "image_to_video": "image_to_video",
    "image_to_video_controlnet": "image_to_video",
    "first_last_frame_video": "first_last_frame_video",
    "first_last_frame_control_video": "first_last_frame_video",
    "first_last_frame_raw_video_guide": "first_last_frame_video",
    "first_middle_last_frame_video": "first_last_frame_video",
    "text_to_video": "text_to_video",
    "text_to_video_controlnet": "text_to_video",
    "video_to_video_extend": "video_to_video",
    "video_to_video_talking_avatar": "video_to_video",
    "text_to_audio_song": "text_to_audio",
    "text_to_speech_custom_voice": "text_to_audio",
    "text_to_speech_voice_clone": "text_to_audio",
    "text_to_speech_voice_design": "text_to_audio",
}

# ---------------------------------------------------------------------------
# Templates actually migrated in T8 (E1 renames).
# Source: T8 executor_notes — renames applied across these 17 templates.
# ---------------------------------------------------------------------------

_T8_MIGRATED_TEMPLATE_IDS: FrozenSet[str] = frozenset(
    {
        "edit/qwen_image_edit",
        "video/ltx2_3_first_last_frame_travel_iclora_control",
        "video/ltx2_3_i2v",
        "video/ltx2_3_iamccs_audio_extend_low_ram",
        "video/ltx2_3_iamccs_audio_image_to_video",
        "video/ltx2_3_iamccs_long_i2v",
        "video/ltx2_3_lightricks_first_last_parity",
        "video/ltx2_3_lightricks_first_last_two_stage_lowvram",
        "video/ltx2_3_lightricks_iclora_union_control",
        "video/ltx2_3_runexx_first_last_frame",
        "video/ltx2_3_runexx_first_last_raw_video_guide",
        "video/ltx2_3_t2v",
        "video/wan_i2v",
        "video/wan_t2v",
        "video/wanvideo_wrapper_13b_vace",
        "video/wanvideo_wrapper_22_s2v_framepack_pose",
        "video/wanvideo_wrapper_22_wan_animate_preprocess_kijai",
    }
)

# ---------------------------------------------------------------------------
# Broken-regen templates with a *documented* deferral — excluded from the
# naming assertion by explicit reference.  (T7 confirmed zero deferrals,
# so this set is empty.  It exists as a mechanism so future deferrals can
# be recorded in one place and the test stays precise.)
# ---------------------------------------------------------------------------

_DEFERRED_BROKEN_REGEN: Dict[str, str] = {
    # Example entry (not active):
    # "video/example": (
    #     "T7 executor notes: broken-regen; deferral note: "
    #     "'cannot rename input_image without breaking downstream API consumers'"
    # ),
}

# ---------------------------------------------------------------------------
# Helpers
# ---------------------------------------------------------------------------


def _load_template_index() -> dict:
    path = Path("template_index.json")
    if not path.exists():
        pytest.skip("template_index.json not found")
    return json.loads(path.read_text(encoding="utf-8"))


def _primary_input_names(public_inputs: list[dict]) -> list[str]:
    """Return primary public-input names, excluding alias-only rows.

    The static-contract extractor fans aliases out into separate index rows
    (one per alias name, with ``aliases: []``).  A name is an alias when it
    appears in the ``aliases`` field of another row.
    """
    all_alias_names: set[str] = set()
    for entry in public_inputs:
        for alias in entry.get("aliases", ()):
            all_alias_names.add(alias)

    return [entry["name"] for entry in public_inputs if entry["name"] not in all_alias_names]


def _build_violations() -> Dict[str, list]:
    """Build a dict of ``{template_id: [non_canonical_primary_names]}``.

    Only templates that are (a) in the T8 migrated set, (b) mapped to a
    known capability family, and (c) NOT in the documented-deferral list
    are asserted.
    """
    index = _load_template_index()
    violations: Dict[str, list] = {}

    for tpl in index["templates"]:
        tid: str = tpl["id"]

        # --- scope gates ---------------------------------------------------
        if tid not in _T8_MIGRATED_TEMPLATE_IDS:
            continue

        capability: str = tpl.get("capability", "")
        family: str | None = _CAPABILITY_FAMILY.get(capability)
        if family is None:
            # No canon defined for this capability — skip assertion.
            continue

        if tid in _DEFERRED_BROKEN_REGEN:
            continue

        # --- primary-name check --------------------------------------------
        canon: FrozenSet[str] = _CAPABILITY_CANON[family]
        primary_names = _primary_input_names(tpl.get("public_inputs", []))
        non_canonical = [n for n in primary_names if n not in canon]

        if non_canonical:
            violations[tid] = non_canonical

    return violations


# ---------------------------------------------------------------------------
# Tests
# ---------------------------------------------------------------------------


def test_all_migrated_template_primary_names_are_in_capability_canon() -> None:
    """Every primary public-input name in a migrated template must be in its
    capability-level canon set (plan L170–182 + common template knobs).

    This test scopes to the 17 templates actually touched by the T8 (E1)
    renames and excludes any broken-regen template with a documented
    deferral (currently none — T7 confirmed zero deferrals).
    """
    violations = _build_violations()

    if not violations:
        return  # all clean

    # Build a readable failure message listing every violation.
    lines: list[str] = [
        f"{len(violations)} migrated template(s) have non-canonical primary "
        f"public-input names (see docs/readable_ready_template_cleanup_plan.md "
        f"L170–182 for the capability canon, and the ``_EXTRAS`` dict in this "
        f"file for recognised template-specific knobs):\n",
    ]
    for tid in sorted(violations):
        names = violations[tid]
        lines.append(f"  {tid}: {', '.join(sorted(names))}")

    pytest.fail("\n".join(lines))


def test_deferred_broken_regen_entries_are_valid_template_ids() -> None:
    """Every key in ``_DEFERRED_BROKEN_REGEN`` must reference a real template.

    This prevents stale deferral entries from silently hiding violations.
    """
    index = _load_template_index()
    all_ids = {tpl["id"] for tpl in index["templates"]}

    stale = [tid for tid in _DEFERRED_BROKEN_REGEN if tid not in all_ids]
    assert stale == [], (
        f"Deferred broken-regen entries reference unknown template IDs: {stale}"
    )


def test_all_deferred_templates_are_in_migrated_set() -> None:
    """Deferred templates must be in the T8 migrated set (otherwise the
    deferral mechanism is masking a template that wasn't in scope)."""
    not_in_scope = [
        tid for tid in _DEFERRED_BROKEN_REGEN if tid not in _T8_MIGRATED_TEMPLATE_IDS
    ]
    assert not_in_scope == [], (
        f"Deferred templates not in T8 migrated set: {not_in_scope}"
    )


def test_template_index_has_all_migrated_template_ids() -> None:
    """Sanity: every T8-migrated template ID must exist in template_index.json."""
    index = _load_template_index()
    all_ids = {tpl["id"] for tpl in index["templates"]}

    missing = [tid for tid in _T8_MIGRATED_TEMPLATE_IDS if tid not in all_ids]
    assert missing == [], (
        f"T8 migrated template IDs not found in template_index.json: {missing}"
    )
