from __future__ import annotations

import importlib.util
import sys
from pathlib import Path

import pytest

from vibecomfy.workflow import VibeWorkflow


READY_ROOT = Path("ready_templates")
RECOGNIZED_LINE1_MARKERS = {
    "# vibecomfy: generated",
    "# vibecomfy: manual",
    "# vibecomfy: broken-regen",
}


def _ready_template_paths() -> list[Path]:
    return [
        path
        for path in sorted(READY_ROOT.glob("*/*.py"))
        if path.name != "__init__.py" and not path.name.startswith("_")
    ]


READY_TEMPLATE_PATHS = _ready_template_paths()
BROKEN_REGEN_SHIMS = [
    path
    for path in READY_TEMPLATE_PATHS
    if path.read_text(encoding="utf-8").splitlines()[0] == "# vibecomfy: broken-regen"
]


def _template_id(path: Path) -> str:
    return path.relative_to(READY_ROOT).with_suffix("").as_posix()


def _load_module(path: Path):
    module_name = f"_vibecomfy_load_sweep_{path.stem}_{abs(hash(path.as_posix()))}"
    spec = importlib.util.spec_from_file_location(module_name, path)
    if spec is None or spec.loader is None:
        raise ImportError(f"could not load {path}")
    module = importlib.util.module_from_spec(spec)
    sys.modules[module_name] = module
    try:
        spec.loader.exec_module(module)
    finally:
        sys.modules.pop(module_name, None)
    return module


def test_ready_template_sweep_covers_all_repo_templates() -> None:
    assert len(READY_TEMPLATE_PATHS) == 64
    assert len(BROKEN_REGEN_SHIMS) == 16


def test_ready_templates_have_exactly_one_line1_marker() -> None:
    for path in READY_TEMPLATE_PATHS:
        line1 = path.read_text(encoding="utf-8").splitlines()[0]
        matches = [marker for marker in RECOGNIZED_LINE1_MARKERS if line1 == marker]
        assert matches == [line1], f"{path} must have exactly one recognized line-1 marker"


@pytest.mark.parametrize("template_path", READY_TEMPLATE_PATHS, ids=_template_id)
def test_ready_template_import_build_and_finalize_metadata(template_path: Path) -> None:
    module = _load_module(template_path)
    build = getattr(module, "build", None)

    assert callable(build)
    workflow = build()
    assert isinstance(workflow, VibeWorkflow)

    # Broken-regen shims are intentionally skipped by the emitter regen path,
    # but they must keep loading and building so app/runtime smoke coverage is
    # not silently narrowed while Phase 1 fixes generated output families.
    if template_path in BROKEN_REGEN_SHIMS:
        assert workflow.id == _template_id(template_path)

    workflow.finalize_metadata()
