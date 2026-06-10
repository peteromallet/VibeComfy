"""Regenerate all 18 affected ready templates via the canonical port_convert_workflow
path, catching ConversionWriteError/ConversionParityError per template.

Usage: python -m tools.regenerate_affected_templates [--dry-run] [--template <ready_id>]
"""

from __future__ import annotations

import json
import sys
from pathlib import Path
from typing import Any

# TODO(repo-root): migrate to vibecomfy.utils.find_repo_root() once this tool's
# script-mode import path is package-import-safe.
REPO_ROOT = Path(__file__).resolve().parents[1]
READY_ROOT = REPO_ROOT / "ready_templates"

# Map ready_id -> source workflow JSON
# Derived from provenance/source_workflow in each ready template
AFFECTED_TEMPLATES: dict[str, str] = {
    "video/ltx2_3_runexx_talking_avatar_qwen_tts": "workflow_corpus/custom_nodes/ltxvideo/runexx/LTX-2.3_Talking_Avatar_Qwen_TTS.json",
    "video/ltx2_3_lightricks_iclora_motion_track": "workflow_corpus/custom_nodes/ltxvideo/lightricks_2_3/LTX-2.3_ICLoRA_Motion_Track_Distilled.json",
    "video/wanvideo_wrapper_21_14b_fun_control": "workflow_corpus/custom_nodes/wanvideo_wrapper/kijai/wan21_14b_fun_control.json",
    "video/wanvideo_wrapper_wan_animate": "workflow_corpus/custom_nodes/wanvideo_wrapper/kijai/wan_animate.json",
    "video/wanvideo_wrapper_21_14b_wanmove_i2v": "workflow_corpus/custom_nodes/wanvideo_wrapper/kijai/wan21_14b_wanmove_i2v.json",
    "video/wanvideo_wrapper_21_14b_fun_control_camera": "workflow_corpus/custom_nodes/wanvideo_wrapper/kijai/wan21_14b_fun_control_camera.json",
    "video/wanvideo_wrapper_21_14b_flf2v": "workflow_corpus/custom_nodes/wanvideo_wrapper/kijai/wan21_14b_flf2v.json",
    "video/ltx2_3_lightricks_iclora_hdr": "workflow_corpus/custom_nodes/ltxvideo/lightricks_2_3/LTX-2.3_ICLoRA_HDR_Distilled.json",
    "video/ltx2_3_lightricks_two_stage": "workflow_corpus/custom_nodes/ltxvideo/lightricks_2_3/LTX-2.3_T2V_I2V_Two_Stage_Distilled.json",
    "edit/qwen_image_edit": "workflow_corpus/official/edit/qwen_image_edit.json",
    "image/flux2_klein_9b_t2i": "workflow_corpus/official/image/flux2_klein_9b_t2i.json",
    "image/qwen_image_2512": "workflow_corpus/official/image/qwen_image_2512.json",
    "image/flux2_klein_4b_t2i": "workflow_corpus/official/image/flux2_klein_4b_t2i.json",
    "image/flux2_klein_9b_gguf_t2i": "workflow_corpus/custom_nodes/flux2/flux2_klein_9b_gguf_t2i.json",
    # Templates with no resolvable source workflow JSON -- listed for completeness
    # but will fail gracefully with a missing-source diagnostic.
    "video/wan22_animate_native_first_stage": "ready_templates/video/wan22_animate_native_first_stage.py",
    "video/ltx2_3_first_last_frame_travel_iclora_control": "ready_templates/video/ltx2_3_first_last_frame_travel_iclora_control.py",
    "video/ltx2_3_lightricks_first_last_parity": "ready_templates/video/ltx2_3_lightricks_first_last_parity.py",
    "video/ltx2_3_lightricks_first_last_two_stage_lowvram": "ready_templates/video/ltx2_3_lightricks_first_last_two_stage_lowvram.py",
}


def regenerate_one(ready_id: str, source: str, *, dry_run: bool = False) -> tuple[bool, str]:
    """Regenerate a single ready template via port_convert_workflow.

    Returns (success, note).
    """
    from vibecomfy.porting.workbench import load_port_source
    from vibecomfy.porting.convert import (
        port_convert_workflow,
        port_convert_and_write,
        ConversionWriteError,
        ManualTemplateRefusal,
    )
    from vibecomfy.errors import ConversionParityError
    from vibecomfy._workflow_helpers import HelperDiagnostic
    from vibecomfy.schema import ConversionSchemaProvider

    source_path = REPO_ROOT / source
    out_path = READY_ROOT / f"{ready_id}.py"

    if not source_path.exists():
        return (False, f"source_not_found: {source_path}")

    try:
        loaded = load_port_source(str(source_path))
    except Exception as exc:
        return (False, f"load_port_source_failed: {type(exc).__name__}: {exc}")

    # Build conversion schema provider from cached object_info
    try:
        schema_provider = ConversionSchemaProvider()
    except Exception:
        schema_provider = None

    # Build provenance from the report
    try:
        from vibecomfy.porting.workbench import analyze_source
        report = analyze_source(
            str(source_path),
            schema_provider=schema_provider,
            head_check_models=False,
            mode="auto",
        )
        provenance = report.provenance
        source_hash = report.source_hash
        workflow_shape = report.workflow_shape
        raw_workflow = loaded.raw_workflow
    except Exception:
        provenance = {}
        source_hash = None
        workflow_shape = None
        raw_workflow = None

    try:
        result = port_convert_workflow(
            loaded.workflow,
            ready_id=ready_id,
            source_path=str(source_path),
            provenance=provenance,
            source_hash=source_hash,
            workflow_shape=workflow_shape,
            schema_provider=schema_provider,
            raw_workflow=raw_workflow,
        )
    except (ConversionWriteError, ConversionParityError, ManualTemplateRefusal) as exc:
        return (False, f"conversion_error: {type(exc).__name__}: {exc}")
    except Exception as exc:
        return (False, f"port_convert_workflow_failed: {type(exc).__name__}: {exc}")

    if result.validation is not None and not result.validation.ok:
        diags = getattr(result.validation, "emission_diagnostics", [])
        diag_codes = [getattr(d, "code", "?") for d in diags]
        diag_sevs = [getattr(d, "severity", "?") for d in diags if getattr(d, "severity", None) == "error"]
        if diag_sevs:
            return (False, f"validation_failed: errors={diag_sevs[:5]}, codes={diag_codes[:5]}")
        # Warnings only — log but continue
        print(f"\n    [warnings: {diag_codes[:3]}]", end="")

    try:
        port_convert_and_write(
            result,
            out_path,
            dry_run=dry_run,
            diff=False,
        )
    except (ConversionWriteError, ManualTemplateRefusal) as exc:
        return (False, f"write_failed: {type(exc).__name__}: {exc}")

    return (True, "ok")


def main() -> int:
    import argparse
    parser = argparse.ArgumentParser()
    parser.add_argument("--dry-run", action="store_true")
    parser.add_argument("--template", type=str, default=None)
    args = parser.parse_args()

    if args.template:
        if args.template not in AFFECTED_TEMPLATES:
            print(f"Unknown template: {args.template}", file=sys.stderr)
            return 1
        templates = {args.template: AFFECTED_TEMPLATES[args.template]}
    else:
        templates = AFFECTED_TEMPLATES

    successes: list[str] = []
    failures: list[tuple[str, str]] = []

    for ready_id, source in templates.items():
        print(f"Regenerating: {ready_id} <- {source} ...", end=" ", flush=True)
        ok, note = regenerate_one(ready_id, source, dry_run=args.dry_run)
        if ok:
            print("OK")
            successes.append(ready_id)
        else:
            print(f"FAIL: {note}")
            failures.append((ready_id, note))

    print(f"\n--- Results ---")
    print(f"Successes: {len(successes)}")
    for s in successes:
        print(f"  OK: {s}")
    print(f"Failures: {len(failures)}")
    for rid, note in failures:
        print(f"  FAIL: {rid} — {note}")

    if failures:
        print("\nNon-empty failure list — hard stop. Fix resolver gaps before re-running.")
        return 1
    return 0


if __name__ == "__main__":
    sys.exit(main())
