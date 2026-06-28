from __future__ import annotations

import keyword
import logging
import re
from pathlib import Path
from typing import Any, Mapping

from vibecomfy.node_packs import LockEntry, read_lockfile
from vibecomfy.porting.emit.format_values import _format_value
from vibecomfy.utils import repo_relative_path

logger = logging.getLogger(__name__)
_PROVENANCE_PATH_KEYS: frozenset[str] = frozenset({"source_path", "source_workflow_path", "source_workflow"})

def _model_assets_for_emit(
    metadata: Mapping[str, Any],
    requirements: Mapping[str, Any],
) -> list[Mapping[str, Any]]:
    def usable(asset: Mapping[str, Any]) -> bool:
        return bool(asset.get("url"))

    raw_assets = metadata.get("model_assets")
    if isinstance(raw_assets, list):
        return [dict(asset) for asset in raw_assets if isinstance(asset, Mapping) and usable(asset)]
    raw_requirement_models = requirements.get("models") if isinstance(requirements, Mapping) else None
    if isinstance(raw_requirement_models, list):
        return [dict(asset) for asset in raw_requirement_models if isinstance(asset, Mapping) and usable(asset)]
    return []


def _model_key(asset: Mapping[str, Any], used: set[str]) -> str:
    role = _model_role_key(asset)
    if role:
        candidate = role
        index = 2
        while candidate in used:
            candidate = f"{role}_{index}"
            index += 1
        used.add(candidate)
        return candidate
    raw_name = str(asset.get("name") or asset.get("filename") or "model")
    base = re.sub(r"[^0-9a-zA-Z_]+", "_", raw_name.rsplit(".", 1)[0]).strip("_").lower() or "model"
    if base[0].isdigit():
        base = f"model_{base}"
    if keyword.iskeyword(base):
        base = f"{base}_model"
    candidate = base
    index = 2
    while candidate in used:
        candidate = f"{base}_{index}"
        index += 1
    used.add(candidate)
    return candidate


def _model_role_key(asset: Mapping[str, Any]) -> str | None:
    subdir = str(asset.get("subdir") or asset.get("directory") or "").replace("\\", "/").strip("/")
    field = str(asset.get("field") or asset.get("input") or "").lower()
    role_by_subdir = {
        "checkpoints": "checkpoint",
        "clip_vision": "clip_vision",
        "controlnet": "controlnet",
        "diffusion_models": "diffusion_model",
        "latent_upscale_models": "upscale_model",
        "loras": "lora",
        "text_encoders": "text_encoder",
        "unet": "unet",
        "vae": "vae",
    }
    if field in {"ckpt_name", "checkpoint"}:
        return "checkpoint"
    if field in {"unet_name", "model_name"} and subdir in {"diffusion_models", "unet"}:
        return role_by_subdir.get(subdir, "model")
    if field in {"vae_name"}:
        return "vae"
    if field in {"clip_name", "clip_name1", "clip_name2", "text_encoder"}:
        return "text_encoder"
    return role_by_subdir.get(subdir)


def _format_models_block(model_assets: list[Mapping[str, Any]]) -> list[str]:
    if not model_assets:
        return []
    lines = ["MODELS = {"]
    used: set[str] = set()
    for asset in model_assets:
        key = _model_key(asset, used)
        filename = asset.get("filename", asset.get("name"))
        subdir = asset.get("subdir") or asset.get("directory") or "checkpoints"
        args: list[str] = []
        if filename is not None and not _filename_is_url_derived(str(filename), asset.get("url")):
            args.append(f"filename={_format_value(filename)}")
        for field_name in ("url", "target_path", "sha256", "hf_revision", "size_bytes", "gated"):
            value = asset.get(field_name)
            if value is not None:
                args.append(f"{field_name}={_format_value(value)}")
        if subdir is not None:
            args.append(f"subdir={_format_value(subdir)}")
        lines.append(f"    {key!r}: ModelAsset({', '.join(args)}),")
    lines.append("}")
    return lines


def _filename_is_url_derived(filename: str, url: Any) -> bool:
    if not isinstance(url, str) or not url:
        return False
    path = url.split("?", 1)[0].split("#", 1)[0].rstrip("/")
    if not path:
        return False
    return Path(path).name == filename


def _apply_ready_template_metadata_defaults(metadata: dict[str, Any], template_id: str) -> None:
    if template_id == "video/ltx2_3_runexx_first_last_frame":
        metadata.setdefault("comfy_configuration", {"memory_profile": 3, "fp8_e4m3fn_text_enc": True})


def _metadata_extras_for_emit(metadata: Mapping[str, Any]) -> dict[str, Any]:
    derived_keys = {
        "ready_template",
        "workflow_template",
        "capability",
        "output_prefix",
        "unbound_inputs",
        "model_assets",
        "edit_guide",
        "requirements",
        "id_map",
        "ready_template_path",
        "python_policy_applied",
        "source_role",
        "source_workflow",
        "vibecomfy_version",
        "comfy_core",
        "coverage_tier",
        "custom_node_packs",
        "_has_public_inputs_for_emit",
    }
    extras = {
        str(key): value
        for key, value in metadata.items()
        if key not in derived_keys and value is not None
    }
    provenance = metadata.get("provenance")
    if isinstance(provenance, Mapping) and not _is_derivable_provenance(provenance):
        extras["provenance"] = _normalize_provenance_paths(provenance)
    return extras


def _normalize_provenance_paths(provenance: Mapping[str, Any]) -> dict[str, Any]:
    normalized = dict(provenance)
    for key in _PROVENANCE_PATH_KEYS:
        value = normalized.get(key)
        if isinstance(value, str) and value:
            normalized[key] = _repo_relative_provenance_path(value)
    return normalized


def _repo_relative_provenance_path(path: str) -> str:
    normalized = repo_relative_path(path)
    if Path(normalized).is_absolute():
        logger.warning("provenance path is outside the repo; keeping absolute path: %s", normalized)
    return normalized


def _is_derivable_provenance(provenance: Mapping[str, Any]) -> bool:
    """Return true when ReadyMetadata.build can recreate the provenance."""

    return set(provenance).issubset({"source_workflow", "source_role"})


_MODEL_PATH_EXTS = (".safetensors", ".ckpt", ".pt", ".pth", ".gguf", ".onnx", ".bin")


def _normalize_model_path(value: Any) -> Any:
    if isinstance(value, str) and "\\" in value and value.lower().endswith(_MODEL_PATH_EXTS):
        return value.replace("\\", "/")
    return value


def _requirements_expr_for_emit(requirements: Mapping[str, Any], *, has_models: bool) -> str | None:
    retained: dict[str, Any] = {}
    for key, value in dict(requirements).items():
        if key == "models" and has_models:
            continue
        if value:
            if key == "models" and isinstance(value, (list, tuple)):
                value = [_normalize_model_path(v) for v in value]
            retained[str(key)] = value
    if not retained:
        return None
    return _format_value(retained)


def _lock_entries_by_class(lockfile_path: Path = Path("custom_nodes.lock")) -> dict[str, LockEntry]:
    by_class: dict[str, LockEntry] = {}
    try:
        entries = read_lockfile(lockfile_path)
    except (OSError, ValueError):
        return {}
    for entry in entries:
        for class_type in entry.class_set:
            by_class.setdefault(str(class_type), entry)
    return by_class


def _custom_node_packs_for_emit(
    workflow_nodes: Mapping[str, Any],
    metadata: Mapping[str, Any],
    requirements: Mapping[str, Any],
) -> dict[str, dict[str, Any]]:
    explicit = metadata.get("custom_node_packs")
    if isinstance(explicit, Mapping):
        return {str(key): dict(value) for key, value in explicit.items() if isinstance(value, Mapping)}

    by_class = _lock_entries_by_class()
    if not by_class:
        return {}

    requirement_names = {
        str(item)
        for key in ("custom_nodes", "custom_node_refs")
        for item in (requirements.get(key) or [])
        if item
    }
    grouped: dict[str, dict[str, Any]] = {}
    for node in workflow_nodes.values():
        class_type = str(getattr(node, "class_type", ""))
        entry = by_class.get(class_type)
        if entry is None:
            continue
        commit = entry.commit or entry.git_commit_sha
        if not commit:
            continue
        row = grouped.setdefault(
            entry.name,
            {
                "commit": commit,
                "url": entry.url,
                "class_schema_sha256": entry.class_schema_sha256 or entry.schema_hash,
                "classes_used": [],
                "pip_packages": list(entry.pip_packages),
                "status": "pinned" if entry.name in requirement_names or entry.slug in requirement_names else "discovered",
            },
        )
        if class_type not in row["classes_used"]:
            row["classes_used"].append(class_type)

    for row in grouped.values():
        row["classes_used"] = sorted(row["classes_used"])
        row["pip_packages"] = sorted(row["pip_packages"])
        for key in ("url", "class_schema_sha256"):
            if row.get(key) is None:
                row.pop(key, None)
    return dict(sorted(grouped.items(), key=lambda item: item[0].lower()))


def _format_ready_metadata_build(
    metadata: Mapping[str, Any],
    requirements: Mapping[str, Any],
    *,
    has_models: bool,
    has_public_inputs: bool,
    custom_node_packs: Mapping[str, Any] | None = None,
    output_node_class_type: str | None = None,
) -> list[str]:
    template_id = str(metadata.get("ready_template") or metadata.get("workflow_template") or "ready_template")
    raw_capability = str(metadata.get("capability") or "unknown")
    if raw_capability == "unknown" and output_node_class_type:
        from vibecomfy.templates import _derive_output_kind  # local import to avoid circular import at module load
        derived = _derive_output_kind(output_node_class_type)
        if derived:
            raw_capability = derived
    capability = raw_capability
    output_prefix = str(metadata.get("output_prefix") or template_id)
    lines = [
        "READY_METADATA = ReadyMetadata.build(",
        f"    capability={capability!r},",
    ]
    if has_public_inputs:
        lines.append("    inputs=PUBLIC_INPUT_METADATA,")
    if has_models:
        lines.append("    models=MODELS,")
    if output_prefix != template_id:
        lines.append(f"    output_prefix={output_prefix!r},")
    requirements_expr = _requirements_expr_for_emit(requirements, has_models=has_models)
    if requirements_expr is not None:
        lines.append(f"    requirements={requirements_expr},")
    if custom_node_packs:
        lines.append(f"    custom_node_packs={_format_value(dict(custom_node_packs))},")
    for key, value in _metadata_extras_for_emit(metadata).items():
        lines.append(f"    {key}={_format_value(value)},")
    lines.append(")")
    return lines


