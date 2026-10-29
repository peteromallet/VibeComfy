"""Thin user entries over canonical imported workflow bundles."""
from __future__ import annotations

import json
import os
import re
import shutil
import tempfile
from pathlib import Path
from typing import Any

_ENTRY_ID = re.compile(r"^[A-Za-z0-9][A-Za-z0-9._-]*$")
_OUTPUT_KINDS = {
    "SaveImage": "image", "PreviewImage": "image", "SaveVideo": "video",
    "VHS_VideoCombine": "video", "SaveAudio": "audio", "SaveAudioMP3": "audio",
    "PreviewAudio": "audio", "SaveAnimatedWEBP": "video", "SaveWEBM": "video",
}
# Roles describe the loader, not an inferred catalog model. Target-side model
# resolution remains the generation backend's responsibility.
LOADER_ROLES = {
    "CheckpointLoaderSimple": "checkpoint", "UNETLoader": "diffusion_model",
    "UnetLoaderGGUF": "diffusion_model", "WanVideoModelLoader": "diffusion_model",
    "CLIPLoader": "text_encoder", "DualCLIPLoader": "text_encoder",
    "DualCLIPLoaderGGUF": "text_encoder", "LoadWanVideoT5TextEncoder": "text_encoder",
    "VAELoader": "vae", "VAELoaderKJ": "vae", "WanVideoVAELoader": "vae",
    "LoraLoader": "lora", "LoraLoaderModelOnly": "lora", "ControlNetLoader": "controlnet",
    "CLIPVisionLoader": "vision_encoder", "LatentUpscaleModelLoader": "upscaler",
}

_MEDIA_LOADER_FIELDS = {
    ("LoadImage", "image"): "image",
    ("LoadAudio", "audio"): "audio",
    ("LoadVideo", "file"): "video",
    ("VHS_LoadVideo", "video"): "video",
    ("VHS_LoadVideoFFmpeg", "video"): "video",
}


def media_loader_kind(class_type: str, field: str) -> str | None:
    """Return the media kind of a known filename picker."""
    return _MEDIA_LOADER_FIELDS.get((class_type, field))


def entries_dir() -> Path:
    return Path(os.environ.get("VIBECOMFY_ENTRIES_DIR", "~/.vibecomfy/entries")).expanduser()


def _validate(manifest: Any) -> dict[str, Any]:
    if not isinstance(manifest, dict) or set(manifest) != {"id", "kind", "modes", "bundle", "needs", "binds", "defaults"}:
        raise ValueError("entry must contain exactly id, kind, modes, bundle, needs, binds and defaults")
    if not isinstance(manifest["id"], str) or not _ENTRY_ID.fullmatch(manifest["id"]):
        raise ValueError("invalid entry id")
    if manifest["kind"] not in {"image", "video", "audio"}:
        raise ValueError("invalid entry kind")
    modes = manifest["modes"]
    allowed = {"image": {"t2i", "i2i", "edit", "inpaint", "outpaint", "upscale"}, "video": {"t2v", "i2v", "flf", "v2v", "video-edit"}, "audio": {"tts", "music", "sfx"}}
    if not isinstance(modes, list) or any(not isinstance(m, str) or m not in allowed[manifest["kind"]] for m in modes) or len(set(modes)) != len(modes):
        raise ValueError("invalid entry modes")
    if not isinstance(manifest["bundle"], str) or not manifest["bundle"].strip():
        raise ValueError("entry bundle must be a path")
    if not isinstance(manifest["needs"], list) or not all(isinstance(n, dict) for n in manifest["needs"]):
        raise ValueError("entry needs must be a list of objects")
    if not isinstance(manifest["binds"], dict) or not all(isinstance(k, str) and k and ((isinstance(v, str) and v) or (isinstance(v, dict) and set(v) == {"node", "field"} and all(isinstance(x, str) and x for x in v.values()))) for k, v in manifest["binds"].items()):
        raise ValueError("entry binds must map names to public inputs or node/field targets")
    if not isinstance(manifest["defaults"], dict):
        raise ValueError("entry defaults must be an object")
    return manifest


def load_entry(path: str | Path) -> dict[str, Any]:
    path = Path(path).expanduser()
    if path.is_dir():
        path = path / "entry.json"
    manifest = _validate(json.loads(path.read_text(encoding="utf-8"))).copy()
    bundle = Path(manifest["bundle"]).expanduser()
    manifest["bundle"] = str((path.parent / bundle).resolve())
    return manifest


def discover_entries(directory: str | Path | None = None) -> list[dict[str, Any]]:
    root = Path(directory).expanduser() if directory is not None else entries_dir()
    return [load_entry(path) for path in sorted(root.glob("*/entry.json"))]


def infer_output_kind(workflow: Any) -> str:
    """Infer the artifact kind from output nodes, ignoring auxiliary previews."""
    nodes = list(workflow.runtime_nodes().values())
    kinds = {_OUTPUT_KINDS[node.class_type] for node in nodes if node.class_type in _OUTPUT_KINDS and not node.class_type.startswith("Preview")}
    if not kinds:
        kinds = {_OUTPUT_KINDS[node.class_type] for node in nodes if node.class_type in _OUTPUT_KINDS}
    if len(kinds) != 1:
        raise ValueError(f"workflow output kind is ambiguous or unknown: {sorted(kinds)}")
    return kinds.pop()


def draft_entry(workflow: Any, entry_id: str, *, bundle: str = "bundle", input_ambiguities: dict[str, list[dict[str, str]]] | None = None) -> dict[str, Any]:
    kind = infer_output_kind(workflow)
    # InputSpec and its aliases are the source of binding names; translation
    # to catalog options is owned by the generation catalog.
    binds = {name: name for name, item in workflow.inputs.items() if name == item.name}
    for name in input_ambiguities or {}:
        binds.pop(name, None)
    has_image = "image" in (input_ambiguities or {}) or any(name in binds or any(name in i.aliases for i in workflow.inputs.values()) for name in ("image", "input_image"))
    has_video = "video" in (input_ambiguities or {}) or any(name in binds or any(name in i.aliases for i in workflow.inputs.values()) for name in ("video", "input_video"))
    modes = [] if kind == "audio" else [{"image": "edit" if has_image else "t2i", "video": "v2v" if has_video else "i2v" if has_image else "t2v"}[kind]]
    from vibecomfy.model_assets import _referenced_model_values
    needs = []
    if kind == "audio":
        needs.append({"role": None, "ambiguity": "audio mode is unknown; choose tts, music, or sfx"})
    needs.extend({"role": None, "ambiguity": f"multiple targets for {name}", "candidates": candidates} for name, candidates in (input_ambiguities or {}).items())
    for reference in _referenced_model_values(workflow):
        role = LOADER_ROLES.get(reference["class_type"])
        needs.append({**reference, "role": role, **({"ambiguity": "unknown loader role"} if role is None else {})})
    return _validate({"id": entry_id, "kind": kind, "modes": modes, "bundle": bundle, "needs": needs, "binds": binds, "defaults": {}})


def import_as_entry(source: str | Path, entry_id: str, directory: str | Path | None = None) -> dict[str, Any]:
    from vibecomfy.porting.import_service import import_workflow_bytes
    from vibecomfy.security.provenance import Provenance
    from vibecomfy.workflow_bundle import emit_bundle, load_bundle

    if not isinstance(entry_id, str) or not _ENTRY_ID.fullmatch(entry_id):
        raise ValueError("invalid entry id")
    root = Path(directory).expanduser() if directory is not None else entries_dir()
    destination = root / entry_id
    if destination.exists() or destination.is_symlink():
        raise FileExistsError(f"entry already exists: {destination}")
    source_path = Path(source).expanduser()
    is_json = source_path.is_file() and source_path.suffix.lower() == ".json"
    artifacts = import_workflow_bytes(source_path.read_bytes(), workflow_id=entry_id, infer_inputs=True) if is_json else None
    root.mkdir(parents=True, exist_ok=True)
    staging = Path(tempfile.mkdtemp(prefix=f".{entry_id}.", dir=root))
    try:
        folder = staging / "bundle"
        folder.mkdir()
        if artifacts is not None:
            (folder / "workflow.py").write_bytes(artifacts.python_bytes)
            (folder / "workflow.vibe.json").write_bytes(artifacts.companion_bytes)
            (folder / "source.json").write_bytes(artifacts.source_bytes)
        else:
            canonical = load_bundle(source_path, trust=Provenance.USER_CONFIRMED)
            emit_bundle(canonical.workflow, folder / "workflow.py", canonical.provenance)
        workflow = load_bundle(folder / "workflow.py", trust=Provenance.USER_CONFIRMED).workflow
        manifest = draft_entry(workflow, entry_id, input_ambiguities=artifacts.report.get("input_ambiguities") if artifacts else None)
        (staging / "entry.json").write_text(json.dumps(manifest, indent=2) + "\n", encoding="utf-8")
        if destination.exists() or destination.is_symlink():
            raise FileExistsError(f"entry already exists: {destination}")
        os.rename(staging, destination)
    except BaseException:
        shutil.rmtree(staging, ignore_errors=True)
        raise
    return load_entry(destination)
