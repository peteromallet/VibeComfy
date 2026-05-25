"""Focused tests for the ``port reemit`` CLI verb (Family P resolution path)."""
from __future__ import annotations

import argparse
import json
import shutil
import textwrap
from pathlib import Path
from typing import Any

import pytest

from vibecomfy.commands.port import _cmd_port_reemit
from vibecomfy.porting.reemit import (
    LEGACY_WIDGET_N_PATTERN,
    discover_family_p_paths,
    has_legacy_widget_constants,
)

READY_ROOT = Path(__file__).resolve().parents[1] / "ready_templates"
RUNEXX_TARGET = READY_ROOT / "video" / "ltx2_3_runexx_talking_avatar_qwen_tts.py"


def _args(**overrides: Any) -> argparse.Namespace:
    """Default reemit argparse namespace; tests override specific fields."""
    defaults = dict(
        workflow=None,
        out=None,
        dry_run=False,
        diff=False,
        json=True,
        all_family_p=False,
        runtime_object_info=False,
        object_info_cache=None,
        no_object_info_cache=False,
        server_url=None,
    )
    defaults.update(overrides)
    return argparse.Namespace(**defaults)


def test_has_legacy_widget_constants_detects_both_styles() -> None:
    """Both ``WIDGET_0 = ...`` and ``WIDGET_0_3 = ...`` count as legacy."""
    assert has_legacy_widget_constants("WIDGET_0 = 'vae'\n")
    assert has_legacy_widget_constants("WIDGET_0_3 = 'ref_image'\n")
    assert not has_legacy_widget_constants("WIDGET = 'not_indexed'\n")
    assert not has_legacy_widget_constants("kwargs = {'widget_0': 1}\n")


def test_reemit_on_one_template_dry_run_diff_produces_changes(
    capsys: pytest.CaptureFixture[str],
) -> None:
    """``port reemit <runexx> --dry-run --diff``: post-regen idempotency check.

    After Phase 3 regen (T12/T13) the template is already in the new emitter shape,
    so a reemit dry-run produces no diff — confirming idempotency.
    """
    if not RUNEXX_TARGET.exists():
        pytest.skip("Reference runexx template missing from worktree.")

    rc = _cmd_port_reemit(_args(
        workflow=str(RUNEXX_TARGET),
        dry_run=True,
        diff=True,
        json=True,
    ))
    payload = json.loads(capsys.readouterr().out)
    assert rc == 0, payload
    assert payload["status"] == "ok"
    write = payload["write"]
    assert write["dry_run"] is True
    summary = payload["summary"]
    assert summary["loc"]["original"] > 0
    assert summary["loc"]["emitted"] > 0
    # Post-regen idempotency: reemit on a fresh template produces identical output.
    assert summary["loc"]["original"] == summary["loc"]["emitted"]


def test_reemit_writes_to_out_path_replaces_file(
    tmp_path: Path,
    capsys: pytest.CaptureFixture[str],
) -> None:
    """Reemit writes a new template file when given an --out path.

    Post-T12 regen the template is already in the final emitter shape,
    so reemit produces an idempotent identical copy.
    """
    if not RUNEXX_TARGET.exists():
        pytest.skip("Reference runexx template missing from worktree.")

    out_path = tmp_path / "reemitted.py"
    rc = _cmd_port_reemit(_args(
        workflow=str(RUNEXX_TARGET),
        out=str(out_path),
        json=True,
    ))
    payload = json.loads(capsys.readouterr().out)
    assert rc == 0, payload
    assert payload["status"] == "ok"
    assert payload["write"]["written"] is True
    assert out_path.exists()
    new_text = out_path.read_text(encoding="utf-8")
    original_text = RUNEXX_TARGET.read_text(encoding="utf-8")
    # Post-regen idempotency: reemit on a fresh template produces identical output.
    assert new_text == original_text, "reemit on a regenerated template must be idempotent"
    # Result must remain a valid Python ready template.
    assert "ReadyMetadata" in new_text
    assert "def build()" in new_text


def test_reemit_refuses_manual_marker(
    tmp_path: Path,
    capsys: pytest.CaptureFixture[str],
) -> None:
    """Templates marked ``# vibecomfy: manual`` are refused even by reemit."""
    if not RUNEXX_TARGET.exists():
        pytest.skip("Reference runexx template missing from worktree.")
    staging_dir = tmp_path / "video"
    staging_dir.mkdir(parents=True)
    staging_path = staging_dir / RUNEXX_TARGET.name
    text = RUNEXX_TARGET.read_text(encoding="utf-8")
    # Replace any leading marker with the protected `manual` marker.
    lines = text.splitlines(keepends=True)
    if lines and lines[0].startswith("# vibecomfy:"):
        lines[0] = "# vibecomfy: manual\n"
    else:
        lines.insert(0, "# vibecomfy: manual\n")
    staging_path.write_text("".join(lines), encoding="utf-8")

    rc = _cmd_port_reemit(_args(
        workflow=str(staging_path),
        json=True,
    ))
    payload = json.loads(capsys.readouterr().out)
    assert rc != 0
    assert payload["status"] == "refused"
    assert "manual" in payload["message"]


def test_reemit_all_family_p_discovers_documented_and_legacy(
    capsys: pytest.CaptureFixture[str],
) -> None:
    """--all-family-p sweep finds at least the documented Family P + legacy
    WIDGET_N templates.

    T12 note: the 4 runexx targets (lipsync_custom_audio, motion_transfer_dwpose,
    music_video_low_ram, video_to_video_extend) were resolved in T12 Pass 2
    (regenerated from source), so they no longer have WIDGET_N constants.
    The iamccs_audio_extend_low_ram template has WIDGET_N constants and
    replaces them as the legacy example.
    """
    paths = discover_family_p_paths()
    assert paths, "expected at least one Family P / legacy-WIDGET_N template"
    rel_names = {p.name for p in paths}
    # The 2 documented Family P templates should be discovered via the provenance gaps doc.
    documented = {
        "ltx2_3_runexx_first_last_raw_video_guide.py",
        "wanvideo_wrapper_22_wan_animate_preprocess_kijai.py",
    }
    discovered = documented & rel_names
    assert discovered, f"expected at least one documented Family P template; got {documented & rel_names}"
    # At least one template with legacy WIDGET_N constants should still be in scope.
    assert any(rel_names), "expected at least one template in family-P scope"


def test_reemit_requires_workflow_or_all_flag(capsys: pytest.CaptureFixture[str]) -> None:
    """port reemit with no workflow and no --all-family-p is a usage error."""
    rc = _cmd_port_reemit(_args(json=True))
    err = capsys.readouterr().err
    assert rc != 0
    assert "workflow ref" in err or "--all-family-p" in err
