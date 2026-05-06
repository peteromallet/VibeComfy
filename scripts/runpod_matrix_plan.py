from __future__ import annotations

import json
from dataclasses import dataclass
from pathlib import Path


MANIFEST = "workflow_corpus/manifests/coverage.json"


@dataclass(frozen=True, slots=True)
class MatrixRow:
    id: str
    path: str
    media: str
    task: str

    def to_tsv(self) -> str:
        return f"{self.id}\t{self.path}\t{self.media}"


@dataclass(frozen=True, slots=True)
class CorpusMatrixPlan:
    core_rows: tuple[MatrixRow, ...]
    gguf_rows: tuple[MatrixRow, ...]
    ltx_rows: tuple[MatrixRow, ...]
    wan_wrapper_rows: tuple[MatrixRow, ...]
    ready_rows: tuple[MatrixRow, ...]


def build_corpus_matrix_plan(root: Path, *, scope: str = "all", manifest: str = MANIFEST) -> CorpusMatrixPlan:
    rows = _selected_manifest_workflows(root / manifest, scope=scope)
    run_core = scope in {
        "all",
        "wan",
        "wan_core",
        "image_core",
        "audio_core",
        "qwen_tts",
        "qwen_image",
        "qwen_image_2512",
        "z_flux",
        "image_creation_types",
        "z_image",
        "flux2",
        "flux2_4b",
        "flux2_9b",
    }
    run_gguf = scope in {"all", "tail", "gguf", "z_flux", "image_creation_types", "flux2", "flux2_9b"}
    run_wan_wrapper = scope in {
        "all",
        "wan",
        "wan_wrapper",
        "wan_kijai",
        "wan_wrapper_basic",
        "wan_wrapper_5b",
        "wan_creation_types",
        "wan_infinitetalk",
        "sprint35_wan_vace_dry_run",
    }
    run_ltx = scope in {
        "all",
        "tail",
        "ltx",
        "ltx_t2v",
        "ltx_i2v",
        "ltx_official",
        "ltx_official_public",
        "ltx_lightricks",
        "ltx_iclora",
        "ltx_iclora_public",
        "ltx_creation_types",
        "ltx_creation_remainder",
        "ltx_runexx_creation",
    }
    selected_rows = tuple(
        row
        for row in rows
        if (
            run_core
            and not row.id.startswith("ltx2_3")
            and not row.id.startswith("wanvideo_wrapper")
            and "gguf" not in row.id
            and _matches_core_scope(row, scope)
        )
        or (run_wan_wrapper and row.id.startswith("wanvideo_wrapper") and _matches_wan_wrapper_scope(row, scope))
        or (run_gguf and "gguf" in row.id)
        or (run_ltx and row.id.startswith("ltx2_3") and _matches_ltx_scope(row, scope))
    )
    return CorpusMatrixPlan(
        core_rows=tuple(
            row for row in selected_rows if not row.id.startswith("ltx2_3") and not row.id.startswith("wanvideo_wrapper") and "gguf" not in row.id
        ),
        gguf_rows=tuple(row for row in selected_rows if "gguf" in row.id),
        ltx_rows=tuple(row for row in selected_rows if row.id.startswith("ltx2_3")),
        wan_wrapper_rows=tuple(row for row in selected_rows if row.id.startswith("wanvideo_wrapper")),
        ready_rows=tuple(row for row in selected_rows if _ready_path(root, row).exists()),
    )


def format_rows(rows: tuple[MatrixRow, ...]) -> str:
    return "\n".join(row.to_tsv() for row in rows)


def format_ready_rows(rows: tuple[MatrixRow, ...], root: Path) -> str:
    return "\n".join(f"{row.id}\t{_ready_path(root, row).relative_to(root).as_posix()}\t{row.media}" for row in rows)


def _selected_manifest_workflows(manifest_path: Path, *, scope: str) -> tuple[MatrixRow, ...]:
    manifest_workflows = json.loads(manifest_path.read_text(encoding="utf-8"))["workflows"]
    return tuple(
        MatrixRow(
            id=item["id"],
            path=item["path"],
            media=item["media"],
            task=item.get("task", ""),
        )
        for item in manifest_workflows
        if item.get("coverage_tier") == "required" or _include_supplemental_for_scope(item, scope)
    )


def _include_supplemental_for_scope(item: dict, scope: str) -> bool:
    if not item.get("ready_template"):
        return False
    workflow_id = item.get("id", "")
    if scope in {
        "wan_wrapper",
        "wan_kijai",
        "wan_wrapper_basic",
        "wan_wrapper_5b",
        "wan_creation_types",
        "wan_infinitetalk",
        "sprint35_wan_vace_dry_run",
    }:
        return workflow_id.startswith("wanvideo_wrapper")
    if scope in {
        "ltx",
        "ltx_official",
        "ltx_official_public",
        "ltx_lightricks",
        "ltx_iclora",
        "ltx_iclora_public",
        "ltx_creation_types",
        "ltx_creation_remainder",
        "ltx_runexx_creation",
    }:
        return workflow_id.startswith("ltx2_3")
    if scope in {"image_core", "z_flux", "image_creation_types", "flux2", "flux2_4b", "flux2_9b"}:
        return workflow_id.startswith("flux2_klein")
    if scope == "qwen_tts":
        return workflow_id.startswith("qwen3_tts")
    return False


def _matches_ltx_scope(row: MatrixRow, scope: str) -> bool:
    if scope == "ltx_t2v":
        return row.id == "ltx2_3_t2v"
    if scope == "ltx_i2v":
        return row.id == "ltx2_3_i2v"
    if scope in {"ltx_official", "ltx_lightricks"}:
        return row.id.startswith("ltx2_3_lightricks") or row.id in {"ltx2_3_t2v", "ltx2_3_i2v"}
    if scope == "ltx_official_public":
        return row.id in {
            "ltx2_3_t2v",
            "ltx2_3_i2v",
            "ltx2_3_lightricks_two_stage",
            "ltx2_3_lightricks_iclora_motion_track",
            "ltx2_3_lightricks_iclora_union_control",
        }
    if scope == "ltx_iclora":
        return "iclora" in row.id
    if scope == "ltx_iclora_public":
        return row.id in {
            "ltx2_3_lightricks_iclora_motion_track",
            "ltx2_3_lightricks_iclora_union_control",
        }
    if scope == "ltx_creation_types":
        return row.id in {
            "ltx2_3_t2v",
            "ltx2_3_i2v",
            "ltx2_3_lightricks_iclora_motion_track",
            "ltx2_3_lightricks_iclora_union_control",
            "ltx2_3_runexx_first_last_frame",
            "ltx2_3_runexx_video_to_video_extend",
        }
    if scope == "ltx_creation_remainder":
        return row.id in {
            "ltx2_3_i2v",
            "ltx2_3_lightricks_iclora_motion_track",
            "ltx2_3_lightricks_iclora_union_control",
            "ltx2_3_runexx_first_last_frame",
            "ltx2_3_runexx_video_to_video_extend",
        }
    if scope == "ltx_runexx_creation":
        return row.id in {
            "ltx2_3_runexx_first_last_frame",
            "ltx2_3_runexx_video_to_video_extend",
        }
    return True


def _matches_core_scope(row: MatrixRow, scope: str) -> bool:
    if scope == "image_core":
        return row.media == "image"
    if scope == "audio_core":
        return row.media == "audio"
    if scope == "qwen_tts":
        return row.id.startswith("qwen3_tts")
    if scope == "z_image":
        return row.id == "z_image"
    if scope == "qwen_image":
        return row.id.startswith("qwen_image")
    if scope == "qwen_image_2512":
        return row.id == "qwen_image_2512"
    if scope in {"z_flux", "flux2", "image_creation_types"}:
        return row.id == "z_image" or row.id.startswith("flux2_klein")
    if scope == "flux2_4b":
        return row.id.startswith("flux2_klein_4b")
    if scope == "flux2_9b":
        return row.id.startswith("flux2_klein_9b")
    return True


def _matches_wan_wrapper_scope(row: MatrixRow, scope: str) -> bool:
    if scope == "wan_wrapper_basic":
        return row.id in {
            "wanvideo_wrapper_21_14b_t2v",
            "wanvideo_wrapper_21_14b_i2v",
            "wanvideo_wrapper_22_5b_i2v",
            "wanvideo_wrapper_13b_control_lora",
        }
    if scope == "wan_creation_types":
        return row.id in {
            "wanvideo_wrapper_21_14b_t2v",
            "wanvideo_wrapper_21_14b_i2v",
            "wanvideo_wrapper_21_14b_flf2v",
            "wanvideo_wrapper_22_5b_i2v_controlnet",
            "wanvideo_wrapper_13b_control_lora",
            "wanvideo_wrapper_21_14b_v2v_infinitetalk",
        }
    if scope == "wan_infinitetalk":
        return row.id == "wanvideo_wrapper_21_14b_v2v_infinitetalk"
    if scope == "wan_wrapper_5b":
        return row.id == "wanvideo_wrapper_22_5b_i2v"
    if scope == "sprint35_wan_vace_dry_run":
        return row.id == "wanvideo_wrapper_22_14b_vace_cocktail_dry_run"
    return True


def _ready_path(root: Path, row: MatrixRow) -> Path:
    category = "edit" if row.task == "image_edit" else row.media
    return root / "ready_templates" / category / f"{row.id}.py"
