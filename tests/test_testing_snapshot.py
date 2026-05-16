"""Tests for snapshot canonicalization + CLI round-trip (T8)."""
from __future__ import annotations

import subprocess
import sys
from pathlib import Path

import pytest

from vibecomfy.testing.fixtures import make_workflow_factory
from vibecomfy.testing.snapshot import canonicalize_api
from vibecomfy.workflow import VibeNode


REPO_ROOT = Path(__file__).resolve().parents[1]


def _tiny_recipe(tmp_path: Path) -> Path:
    p = tmp_path / "tiny_recipe.py"
    p.write_text(
        """
from vibecomfy.workflow import VibeNode, VibeWorkflow, WorkflowSource

def build():
    wf = VibeWorkflow(id='tiny', source=WorkflowSource(id='tiny'))
    wf.nodes['1'] = VibeNode(id='1', class_type='CheckpointLoaderSimple', inputs={'ckpt_name': 'x.safetensors'})
    wf.nodes['2'] = VibeNode(id='2', class_type='SaveImage', inputs={'images': ['1', 0], 'filename_prefix': 'out'})
    return wf
""".lstrip(),
        encoding='utf-8',
    )
    return p


def test_regenerate_snapshots_check_exits_zero():
    """The committed snapshot baselines stay in sync with the regenerator."""
    result = subprocess.run(
        [sys.executable, str(REPO_ROOT / "scripts" / "regenerate_snapshots.py"), "--check"],
        capture_output=True,
        text=True,
        cwd=str(REPO_ROOT),
        timeout=120,
    )
    assert result.returncode == 0, result.stdout + result.stderr


def test_vibecomfy_test_verify_recipes_passes():
    result = subprocess.run(
        [sys.executable, "-m", "vibecomfy.cli", "test", "verify", str(REPO_ROOT / "recipes"), "--json"],
        capture_output=True,
        text=True,
        cwd=str(REPO_ROOT),
        timeout=120,
    )
    assert result.returncode == 0, result.stdout + result.stderr


def test_user_recipe_snapshot_round_trip(tmp_path: Path):
    recipe = _tiny_recipe(tmp_path)
    # snapshot
    r1 = subprocess.run(
        [sys.executable, "-m", "vibecomfy.cli", "test", "snapshot", str(recipe)],
        capture_output=True, text=True, cwd=str(REPO_ROOT), timeout=60,
    )
    assert r1.returncode == 0, r1.stderr
    # verify
    r2 = subprocess.run(
        [sys.executable, "-m", "vibecomfy.cli", "test", "verify", str(tmp_path)],
        capture_output=True, text=True, cwd=str(REPO_ROOT), timeout=60,
    )
    assert r2.returncode == 0, r2.stderr


def test_canonicalize_api_is_byte_stable():
    """canonicalize_api on the same input twice produces the same bytes."""
    wf = make_workflow_factory()(id="stable")
    wf.nodes["1"] = VibeNode(id="1", class_type="CheckpointLoaderSimple", inputs={"ckpt_name": "x.safetensors"})
    api = wf.compile("api")
    a = canonicalize_api(api)
    b = canonicalize_api(api)
    assert a == b
