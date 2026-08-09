from __future__ import annotations

import sys
from pathlib import Path

import pytest

sys.path.insert(0, str(Path(__file__).resolve().parents[1] / "vendor" / "ComfyUI"))

pytest.importorskip("comfy.cli_args", reason="requires HiddenSwitch ComfyUI runtime")

from comfy.cli_args import default_configuration
from comfy.cmd.extra_model_paths import load_extra_path_config
from comfy.cmd.folder_paths import init_default_paths
from comfy.component_model.folder_path_types import FolderNames


def test_init_default_paths_loads_extra_model_paths_config(tmp_path: Path) -> None:
    """``init_default_paths`` plus ``load_extra_path_config`` register the
    extra_model_paths.yaml entries on the given folder set.

    Current ComfyUI contract: ``init_default_paths`` seeds the default model
    folders; each ``extra_model_paths_config`` entry is then loaded explicitly
    via ``load_extra_path_config`` (see ``comfy/cmd/main.py``), which registers
    the YAML sections as extra search paths.
    """
    models_root = tmp_path / "models"
    (models_root / "vae").mkdir(parents=True)
    extra_model_paths = tmp_path / "extra_model_paths.yaml"
    extra_model_paths.write_text(
        f"comfyui:\n  base_path: {models_root}/\n  vae: vae\n",
        encoding="utf-8",
    )
    config = default_configuration()
    folders = FolderNames(is_root=True)

    init_default_paths(folders, config, replace_existing=True)
    load_extra_path_config(str(extra_model_paths), folder_names=folders)

    assert str(models_root / "vae") in list(folders["vae"].paths)
