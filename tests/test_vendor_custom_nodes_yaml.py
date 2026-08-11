"""Probe test: Does ComfyUI's ``load_extra_path_config`` honor a ``custom_nodes:`` key?

DECISION: Option (a) — YAML ``custom_nodes:`` key IS honored.

Source-code analysis (2026-06-08, Comfy-Org/ComfyUI master):
  - ``folder_paths.py`` registers ``folder_names_and_paths["custom_nodes"]``
    at module level alongside ``checkpoints``, ``vae``, ``loras``, etc.
  - ``utils/extra_config.py::load_extra_path_config`` iterates over every
    top-level key in the YAML document, then iterates over every sub-key
    inside each section and calls
    ``folder_paths.add_model_folder_path(sub_key, normalized_path)``.
  - Since ``custom_nodes`` is a valid key in ``folder_names_and_paths``,
    the call succeeds and the path is registered exactly like a model folder.

Therefore the session-level ``extra_model_paths.yaml`` injection (in session.py)
emits a YAML of the form::

    vibecomfy_library:
      custom_nodes: <path>

and ``load_extra_path_config`` registers the directory.  No option-(b)
``folder_paths.add_model_folder_path`` fallback is needed.

This test invokes the real ComfyUI loader (when available) and asserts
that a ``custom_nodes:`` key in a temp YAML is registered as a folder path.
"""

from __future__ import annotations

import sys
from pathlib import Path

import pytest

# ---------------------------------------------------------------------------
# When a HiddenSwitch ComfyUI checkout is available,
# add it to sys.path so the import below resolves.
# ---------------------------------------------------------------------------
sys.path.insert(0, str(Path(__file__).resolve().parents[1] / "vendor" / "ComfyUI"))

pytest.importorskip("comfy.cli_args", reason="requires HiddenSwitch ComfyUI runtime")

from comfy.cli_args import default_configuration
from comfy.cmd.extra_model_paths import load_extra_path_config
from comfy.cmd.folder_paths import init_default_paths
from comfy.component_model.folder_path_types import FolderNames


def test_custom_nodes_key_in_extra_model_paths_yaml_is_honored(
    tmp_path: Path,
) -> None:
    """Prove that a ``custom_nodes:`` key inside extra_model_paths.yaml causes
    the folder to be registered as a ``custom_nodes`` search path.

    Current ComfyUI contract: ``init_default_paths`` seeds the default model
    folders; each ``extra_model_paths_config`` entry is then loaded explicitly
    via ``load_extra_path_config`` (see ``comfy/cmd/main.py``), which registers
    the YAML sections as extra search paths.
    """
    custom_nodes_dir = tmp_path / "my_custom_nodes"
    custom_nodes_dir.mkdir(parents=True)

    yaml_path = tmp_path / "extra_model_paths.yaml"
    yaml_path.write_text(
        f"vibecomfy_library:\n  custom_nodes: {custom_nodes_dir}\n",
        encoding="utf-8",
    )

    config = default_configuration()
    folders = FolderNames(is_root=True)

    init_default_paths(folders, config, replace_existing=True)
    load_extra_path_config(str(yaml_path), folder_names=folders)

    assert str(custom_nodes_dir) in list(folders["custom_nodes"].paths), (
        "Expected custom_nodes dir %s to be registered after loading "
        "extra_model_paths.yaml, but it was not present in "
        "folders['custom_nodes'].paths" % custom_nodes_dir
    )
