"""Tests for vibecomfy.local_library — resolver, writer, validators."""
from __future__ import annotations

import tomllib
from pathlib import Path

import pytest

from vibecomfy.local_library import (
    Slot,
    SlotState,
    resolve,
    resolved_path,
    validate_custom_nodes_dir,
    validate_models_dir,
    write_slot,
)


@pytest.fixture()
def resolver_isolation(tmp_path: Path, monkeypatch: pytest.MonkeyPatch) -> Path:
    """Clear local-library env vars and redirect Path.home() to tmp_path.

    Prevents developer environment from leaking into resolver tests.
    """
    for var in (
        "VIBECOMFY_CUSTOM_NODES_DIR",
        "VIBECOMFY_MODELS_ROOT",
        "COMFY_MODELS_ROOT",
    ):
        monkeypatch.delenv(var, raising=False)
    monkeypatch.setattr(Path, "home", staticmethod(lambda: tmp_path))
    return tmp_path


# ── Precedence: env > repo > global ──────────────────────────────────────────


def test_env_beats_repo_and_global(resolver_isolation: Path, monkeypatch: pytest.MonkeyPatch, tmp_path: Path) -> None:
    repo = tmp_path / "repo"
    repo.mkdir()
    (repo / "vibecomfy.toml").write_text('[library]\ncustom_nodes = "/repo-path"\n')
    global_cfg = tmp_path / ".vibecomfy" / "config.toml"
    global_cfg.parent.mkdir(parents=True, exist_ok=True)
    global_cfg.write_text('[library]\ncustom_nodes = "/global-path"\n')

    monkeypatch.setenv("VIBECOMFY_CUSTOM_NODES_DIR", "/env-path")
    r = resolve(Slot.custom_nodes, repo_root=repo)
    assert r.state is SlotState.SET
    assert r.path == Path("/env-path").resolve()
    assert "env:" in r.source


def test_repo_beats_global(resolver_isolation: Path, tmp_path: Path) -> None:
    repo = tmp_path / "repo"
    repo.mkdir()
    (repo / "vibecomfy.toml").write_text('[library]\ncustom_nodes = "/repo-path"\n')
    global_cfg = tmp_path / ".vibecomfy" / "config.toml"
    global_cfg.parent.mkdir(parents=True, exist_ok=True)
    global_cfg.write_text('[library]\ncustom_nodes = "/global-path"\n')

    r = resolve(Slot.custom_nodes, repo_root=repo)
    assert r.state is SlotState.SET
    assert r.source == "repo"


def test_global_used_when_no_env_or_repo(resolver_isolation: Path, tmp_path: Path) -> None:
    global_cfg = tmp_path / ".vibecomfy" / "config.toml"
    global_cfg.parent.mkdir(parents=True, exist_ok=True)
    global_cfg.write_text('[library]\ncustom_nodes = "/global-path"\n')

    r = resolve(Slot.custom_nodes)
    assert r.state is SlotState.SET
    assert r.source == "global"


def test_unset_when_no_config(resolver_isolation: Path) -> None:
    r = resolve(Slot.custom_nodes)
    assert r.state is SlotState.UNSET


# ── Tri-state parsing ─────────────────────────────────────────────────────────


def test_set_state_returns_path(resolver_isolation: Path, monkeypatch: pytest.MonkeyPatch) -> None:
    monkeypatch.setenv("VIBECOMFY_CUSTOM_NODES_DIR", "/some/path")
    r = resolve(Slot.custom_nodes)
    assert r.state is SlotState.SET
    assert r.path == Path("/some/path").resolve()


def test_disabled_state_from_env(resolver_isolation: Path, monkeypatch: pytest.MonkeyPatch) -> None:
    monkeypatch.setenv("VIBECOMFY_CUSTOM_NODES_DIR", "none")
    r = resolve(Slot.custom_nodes)
    assert r.state is SlotState.DISABLED
    assert r.path is None


def test_unset_state_when_missing(resolver_isolation: Path) -> None:
    r = resolve(Slot.custom_nodes)
    assert r.state is SlotState.UNSET
    assert r.path is None


# ── Sentinel env values (case-insensitive) ────────────────────────────────────


@pytest.mark.parametrize(
    "sentinel",
    ["none", "off", "disabled", "NONE", "OFF", "DISABLED", "None", "Off", "  none  "],
)
def test_env_sentinels_produce_disabled(
    resolver_isolation: Path,
    monkeypatch: pytest.MonkeyPatch,
    sentinel: str,
) -> None:
    monkeypatch.setenv("VIBECOMFY_CUSTOM_NODES_DIR", sentinel)
    r = resolve(Slot.custom_nodes)
    assert r.state is SlotState.DISABLED


def test_models_primary_env_var(resolver_isolation: Path, monkeypatch: pytest.MonkeyPatch) -> None:
    monkeypatch.setenv("VIBECOMFY_MODELS_ROOT", "/vibe-models")
    r = resolve(Slot.models)
    assert r.state is SlotState.SET
    assert r.source == "env:VIBECOMFY_MODELS_ROOT"


def test_models_fallback_env_var(resolver_isolation: Path, monkeypatch: pytest.MonkeyPatch) -> None:
    monkeypatch.delenv("VIBECOMFY_MODELS_ROOT", raising=False)
    monkeypatch.setenv("COMFY_MODELS_ROOT", "/comfy-models")
    r = resolve(Slot.models)
    assert r.state is SlotState.SET
    assert r.source == "env:COMFY_MODELS_ROOT"


# ── Writer round-trip: preserves [other] section and unrelated [library] keys ─


def test_write_slot_preserves_other_section(resolver_isolation: Path, tmp_path: Path) -> None:
    """[other] section survives write_slot()."""
    repo = tmp_path / "r"
    repo.mkdir()
    toml_path = repo / "vibecomfy.toml"
    toml_path.write_text('[other]\nkey = "value"\n\n[library]\ncustom_nodes = "/old"\n')

    write_slot(Slot.custom_nodes, "/new", repo=repo)

    data = tomllib.loads(toml_path.read_text())
    assert data.get("other", {}).get("key") == "value", "unrelated [other] section was lost"
    assert data["library"]["custom_nodes"] == "/new"


def test_write_slot_preserves_unrelated_library_keys(resolver_isolation: Path, tmp_path: Path) -> None:
    """Non-target keys inside [library] survive write_slot()."""
    repo = tmp_path / "r"
    repo.mkdir()
    toml_path = repo / "vibecomfy.toml"
    toml_path.write_text('[library]\ncustom_nodes = "/old"\nmodels = "/existing-models"\n')

    write_slot(Slot.custom_nodes, "/new-cn", repo=repo)

    data = tomllib.loads(toml_path.read_text())
    assert data["library"]["custom_nodes"] == "/new-cn"
    assert data["library"]["models"] == "/existing-models", "sibling models key was lost"


def test_write_slot_creates_missing_parent_dirs(tmp_path: Path, monkeypatch: pytest.MonkeyPatch) -> None:
    """write_slot() creates parent directories via mkdir(parents=True)."""
    monkeypatch.setattr(Path, "home", staticmethod(lambda: tmp_path))
    repo = tmp_path / "deep" / "nested"
    repo.mkdir(parents=True)

    written = write_slot(Slot.models, "/some-models", repo=repo)
    assert written.exists()


def test_write_slot_creates_global_config(resolver_isolation: Path, tmp_path: Path) -> None:
    """write_slot() without repo= creates ~/.vibecomfy/config.toml."""
    written = write_slot(Slot.custom_nodes, "/my-nodes")
    assert written == tmp_path / ".vibecomfy" / "config.toml"
    data = tomllib.loads(written.read_text())
    assert data["library"]["custom_nodes"] == "/my-nodes"


def test_write_slot_updates_existing_global_config(resolver_isolation: Path, tmp_path: Path) -> None:
    """Second write_slot() call overwrites without losing first-written key."""
    write_slot(Slot.custom_nodes, "/cn")
    write_slot(Slot.models, "/mo")

    cfg = tmp_path / ".vibecomfy" / "config.toml"
    data = tomllib.loads(cfg.read_text())
    assert data["library"]["custom_nodes"] == "/cn"
    assert data["library"]["models"] == "/mo"


# ── Corrupt TOML → UNSET with source='error:...' and no raise ────────────────


def test_corrupt_global_toml_returns_unset_with_error_source(
    resolver_isolation: Path, tmp_path: Path
) -> None:
    global_cfg = tmp_path / ".vibecomfy" / "config.toml"
    global_cfg.parent.mkdir(parents=True, exist_ok=True)
    global_cfg.write_text("this is [[ definitely not valid toml !!!!")

    r = resolve(Slot.custom_nodes)
    assert r.state is SlotState.UNSET
    assert r.source.startswith("error:")


def test_corrupt_repo_toml_returns_unset_with_error_source(
    resolver_isolation: Path, tmp_path: Path
) -> None:
    """Corrupt repo TOML propagates to resolve()'s outer handler — returns error, never raises."""
    repo = tmp_path / "r"
    repo.mkdir()
    (repo / "vibecomfy.toml").write_text("not valid [[[ toml")

    r = resolve(Slot.custom_nodes, repo_root=repo)
    assert r.state is SlotState.UNSET
    assert r.source.startswith("error:")


# ── Validators: ok / looks_real signals ──────────────────────────────────────


def test_validate_custom_nodes_ok_with_subdirectory(tmp_path: Path) -> None:
    d = tmp_path / "cn"
    d.mkdir()
    (d / "some_node").mkdir()
    assert validate_custom_nodes_dir(d) == "ok"


def test_validate_custom_nodes_ok_with_py_file(tmp_path: Path) -> None:
    d = tmp_path / "cn"
    d.mkdir()
    (d / "node.py").write_text("# node")
    assert validate_custom_nodes_dir(d) == "ok"


def test_validate_custom_nodes_looks_real_when_empty(tmp_path: Path) -> None:
    d = tmp_path / "cn"
    d.mkdir()
    assert validate_custom_nodes_dir(d) == "looks_real"


def test_validate_custom_nodes_missing(tmp_path: Path) -> None:
    assert validate_custom_nodes_dir(tmp_path / "nonexistent") == "missing"


def test_validate_custom_nodes_not_a_directory(tmp_path: Path) -> None:
    f = tmp_path / "file.txt"
    f.write_text("x")
    assert validate_custom_nodes_dir(f) == "not_a_directory"


def test_validate_models_ok_with_known_subdir(tmp_path: Path) -> None:
    d = tmp_path / "models"
    d.mkdir()
    (d / "checkpoints").mkdir()
    assert validate_models_dir(d) == "ok"


def test_validate_models_looks_real_when_no_known_subdirs(tmp_path: Path) -> None:
    d = tmp_path / "models"
    d.mkdir()
    (d / "some-unknown-subdir").mkdir()
    assert validate_models_dir(d) == "looks_real"


def test_validate_models_looks_real_when_empty(tmp_path: Path) -> None:
    d = tmp_path / "models"
    d.mkdir()
    assert validate_models_dir(d) == "looks_real"


def test_validate_models_missing(tmp_path: Path) -> None:
    assert validate_models_dir(tmp_path / "nonexistent") == "missing"


# ── resolved_path helper ──────────────────────────────────────────────────────


def test_resolved_path_returns_none_for_unset(resolver_isolation: Path) -> None:
    assert resolved_path(Slot.custom_nodes) is None


def test_resolved_path_returns_none_for_disabled(
    resolver_isolation: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    monkeypatch.setenv("VIBECOMFY_CUSTOM_NODES_DIR", "off")
    assert resolved_path(Slot.custom_nodes) is None


def test_resolved_path_returns_path_for_set(
    resolver_isolation: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    monkeypatch.setenv("VIBECOMFY_CUSTOM_NODES_DIR", "/my-nodes")
    assert resolved_path(Slot.custom_nodes) == Path("/my-nodes").resolve()
