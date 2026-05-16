"""Example 1 — Single-template recipe with one assertion."""
from vibecomfy import load_workflow_any


def build():
    wf = load_workflow_any("image/z_image")
    wf.set_prompt("a glass teapot on basalt")
    return wf
