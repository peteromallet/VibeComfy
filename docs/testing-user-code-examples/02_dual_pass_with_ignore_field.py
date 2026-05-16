"""Example 2 — Dual-pass recipe with an ignore-field directive.

# vibecomfy-snapshot: ignore-field KSampler.cfg
"""
from vibecomfy import load_workflow_any


def build():
    wf = load_workflow_any("image/z_image")
    wf.set_seed(20260516)
    return wf
