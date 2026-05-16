"""Example 3 — pytest-vibecomfy plugin auto-collects this file."""
from vibecomfy import load_workflow_any


def test_z_image_compiles():
    return load_workflow_any("image/z_image")   # auto-wrapped with assert_compiles_cleanly
