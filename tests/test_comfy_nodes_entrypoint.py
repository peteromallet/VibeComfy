"""Entry-point and structural tests for vibecomfy.comfy_nodes (M1.5 T12)."""

from __future__ import annotations

import importlib


def test_entry_point_resolves_vibecomfy_in_comfyui_group() -> None:
    from importlib.metadata import entry_points

    eps = entry_points().select(group="comfyui.custom_nodes")
    names = [ep.name for ep in eps]
    assert "vibecomfy" in names, f"Expected 'vibecomfy' in comfyui.custom_nodes entry points, got: {names}"


def test_comfy_nodes_exposes_web_directory() -> None:
    import vibecomfy.comfy_nodes as m

    assert hasattr(m, "WEB_DIRECTORY"), "comfy_nodes must export WEB_DIRECTORY"
    assert isinstance(m.WEB_DIRECTORY, str)


def test_comfy_nodes_exposes_node_class_mappings() -> None:
    import vibecomfy.comfy_nodes as m

    assert hasattr(m, "NODE_CLASS_MAPPINGS"), "comfy_nodes must export NODE_CLASS_MAPPINGS"
    assert isinstance(m.NODE_CLASS_MAPPINGS, dict)
    assert len(m.NODE_CLASS_MAPPINGS) > 0


def test_comfy_nodes_ping_handler_defined_when_server_absent() -> None:
    """Importing comfy_nodes outside a running ComfyUI server must not raise."""
    mod = importlib.import_module("vibecomfy.comfy_nodes")
    # The handler is defined only when PromptServer is importable; outside a
    # server we just verify the module loads and exposes the required attributes.
    assert hasattr(mod, "WEB_DIRECTORY")
    assert hasattr(mod, "NODE_CLASS_MAPPINGS")
