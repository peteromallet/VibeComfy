"""Render local-library slot config as a ComfyUI extra_model_paths YAML file.

Called from _embedded_configuration_for_session() in session.py to inject
custom_nodes and models paths into the embedded runtime before each session
starts.  The temp directory is created ONCE at module import and cleaned up
at process exit; the YAML file is re-rendered in-place on every call so slot
changes take effect without restarting the process.
"""
from __future__ import annotations

import atexit
import tempfile
from pathlib import Path

# ── One module-level temp directory, registered with atexit once ──────────────

_TMP_DIR: tempfile.TemporaryDirectory[str] = tempfile.TemporaryDirectory(
    prefix="vibecomfy_lib_yaml_"
)
atexit.register(_TMP_DIR.cleanup)

_YAML_PATH = Path(_TMP_DIR.name) / "vibecomfy_library.yaml"

# All model-type subdirs that ComfyUI's folder_paths recognises.
_MODEL_SUBDIRS: tuple[str, ...] = (
    "checkpoints",
    "vae",
    "loras",
    "controlnet",
    "embeddings",
    "upscale_models",
    "clip_vision",
    "diffusion_models",
    "text_encoders",
    "unet",
    "configs",
)


def acquire_library_yaml() -> Path | None:
    """Return the path to the rendered YAML, or None when both slots are unset/disabled.

    Re-renders the file in-place on each call — the returned path is stable
    across calls; only the file contents change when slots are reconfigured.
    """
    from vibecomfy.local_library import Slot, resolved_path

    custom_nodes = resolved_path(Slot.custom_nodes)
    models_root = resolved_path(Slot.models)

    if custom_nodes is None and models_root is None:
        return None

    yaml_text = _render_yaml(custom_nodes, models_root)
    _YAML_PATH.write_text(yaml_text, encoding="utf-8")
    return _YAML_PATH


def _render_yaml(custom_nodes: Path | None, models_root: Path | None) -> str:
    """Emit a ComfyUI extra_model_paths YAML for the given slot values."""
    lines: list[str] = ["vibecomfy_library:"]
    if custom_nodes is not None:
        lines.append(f"  custom_nodes: {custom_nodes}")
    if models_root is not None:
        for subdir in _MODEL_SUBDIRS:
            lines.append(f"  {subdir}: {models_root / subdir}")
    return "\n".join(lines) + "\n"
