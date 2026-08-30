"""Tests for snapshot canonicalization + CLI round-trip (T8)."""
from __future__ import annotations

import argparse
import hashlib
import json
import subprocess
import sys
from pathlib import Path

import pytest

import vibecomfy.commands.test as test_commands
from vibecomfy.errors import CheckoutRequiredError
from vibecomfy.testing.fixtures import make_workflow_factory
from vibecomfy.testing.snapshot import canonicalize_api, load_recipe_build
from vibecomfy.workflow import VibeNode, VibeWorkflow


REPO_ROOT = Path(__file__).resolve().parents[1]


def _tiny_recipe(tmp_path: Path, *, directives: str = "") -> Path:
    p = tmp_path / "tiny_recipe.py"
    p.write_text(
        directives
        + """
from vibecomfy.workflow import VibeEdge, VibeNode, VibeWorkflow, WorkflowSource

def build():
    wf = VibeWorkflow(id='tiny', source=WorkflowSource(id='tiny'))
    wf.nodes['1'] = VibeNode(id='1', class_type='CheckpointLoaderSimple', inputs={'ckpt_name': 'x.safetensors'})
    wf.nodes['2'] = VibeNode(id='2', class_type='SaveImage', inputs={'filename_prefix': 'out'})
    wf.edges.append(VibeEdge(from_node='1', from_output=0, to_node='2', to_input='images'))
    return wf
""".lstrip(),
        encoding='utf-8',
    )
    return p


def test_regenerate_snapshots_check_exits_zero():
    """The committed snapshot baselines stay in sync with the regenerator."""
    result = subprocess.run(
        [sys.executable, "-m", "tools.regenerate_snapshots", "--check"],
        capture_output=True,
        text=True,
        cwd=str(REPO_ROOT),
        timeout=120,
    )
    assert result.returncode == 0, result.stdout + result.stderr


def test_vibecomfy_test_verify_recipes_passes():
    result = subprocess.run(
        [sys.executable, "-m", "vibecomfy.cli", "test", "verify", str(REPO_ROOT / "tests" / "fixtures" / "recipes"), "--json"],
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


def _workflow_source(helper_module: str) -> str:
    return (
        "from vibecomfy.workflow import VibeNode, VibeWorkflow, WorkflowSource\n"
        "def build():\n"
        f"    from {helper_module} import VALUE\n"
        "    wf = VibeWorkflow(id='loader', source=WorkflowSource(id='loader'))\n"
        "    wf.nodes['1'] = VibeNode(id='1', class_type='SaveImage', inputs={'value': VALUE})\n"
        "    return wf\n"
    )


def test_cli_loader_uses_canonical_sibling_and_same_stem_isolation(tmp_path: Path):
    """The CLI inherits the canonical loader's sibling and path isolation."""
    first = tmp_path / "first"
    second = tmp_path / "second"
    for directory, value in ((first, "'first'"), (second, "'second'")):
        directory.mkdir()
        helper_module = "helper"
        (directory / f"{helper_module}.py").write_text(f"VALUE = {value}\n", encoding="utf-8")
        (directory / "recipe.py").write_text(_workflow_source(helper_module), encoding="utf-8")

    first_api = test_commands._build_compiled_api(first / "recipe.py")
    second_api = test_commands._build_compiled_api(second / "recipe.py")

    assert first_api["1"]["inputs"]["value"] == "first"
    assert second_api["1"]["inputs"]["value"] == "second"


def test_canonical_loader_supports_workflow_fallback_and_cleans_failed_module(tmp_path: Path):
    workflow_path = tmp_path / "workflow.py"
    workflow_path.write_text(
        "from vibecomfy.workflow import VibeNode, VibeWorkflow, WorkflowSource\n"
        "WORKFLOW = VibeWorkflow(id='fallback', source=WorkflowSource(id='fallback'))\n"
        "WORKFLOW.nodes['1'] = VibeNode(id='1', class_type='SaveImage', inputs={})\n",
        encoding="utf-8",
    )
    loaded = load_recipe_build(workflow_path)
    assert isinstance(loaded, VibeWorkflow)
    assert test_commands._build_compiled_api(workflow_path)["1"]["class_type"] == "SaveImage"

    broken_path = tmp_path / "broken.py"
    broken_path.write_text("raise RuntimeError('broken recipe')\n", encoding="utf-8")
    digest = hashlib.sha1(str(broken_path.resolve()).encode("utf-8")).hexdigest()[:12]
    module_name = f"vibecomfy_recipe_{broken_path.stem}_{digest}"
    with pytest.raises(RuntimeError, match="broken recipe"):
        load_recipe_build(broken_path)
    assert module_name not in sys.modules

    missing_entry_path = tmp_path / "missing_entry.py"
    missing_entry_path.write_text("VALUE = 1\n", encoding="utf-8")
    digest = hashlib.sha1(str(missing_entry_path.resolve()).encode("utf-8")).hexdigest()[:12]
    module_name = f"vibecomfy_recipe_{missing_entry_path.stem}_{digest}"
    with pytest.raises(RuntimeError, match=r"must define `build\(\)`"):
        load_recipe_build(missing_entry_path)
    assert module_name not in sys.modules


def test_wheel_shaped_user_recipe_works_from_neutral_cwd_and_applies_directives(
    tmp_path: Path,
    monkeypatch: pytest.MonkeyPatch,
    capsys: pytest.CaptureFixture[str],
) -> None:
    """User paths do not require a checkout, even under a ready_templates name."""
    user_dir = tmp_path / "ready_templates"
    user_dir.mkdir()
    recipe = user_dir / "directed.py"
    recipe.write_text(
        "# vibecomfy-snapshot: ignore-field SaveImage.filename_prefix\n"
        + _tiny_recipe(tmp_path).read_text(encoding="utf-8"),
        encoding="utf-8",
    )
    neutral_cwd = tmp_path / "neutral-cwd"
    neutral_cwd.mkdir()
    monkeypatch.chdir(neutral_cwd)

    def no_checkout() -> Path:
        raise CheckoutRequiredError("checkout required")

    monkeypatch.setattr(test_commands, "find_repo_root", no_checkout)
    args = argparse.Namespace(path=str(recipe), force=False, json=True)
    assert test_commands._cmd_test_snapshot(args) == 0
    snapshot_payload = json.loads(capsys.readouterr().out)
    assert snapshot_payload["ok"] is True
    sidecar = recipe.with_suffix(".py.snapshot.json")
    assert "filename_prefix" not in json.loads(sidecar.read_text(encoding="utf-8"))["2"]["inputs"]

    verify_args = argparse.Namespace(path=str(user_dir), json=True)
    assert test_commands._cmd_test_verify(verify_args) == 0
    assert json.loads(capsys.readouterr().out)["ok"] is True


def test_unmapped_checkout_ready_template_is_rejected_from_neutral_cwd(
    tmp_path: Path,
    monkeypatch: pytest.MonkeyPatch,
    capsys: pytest.CaptureFixture[str],
) -> None:
    checkout = tmp_path / "checkout"
    ready_dir = checkout / "ready_templates" / "image"
    ready_dir.mkdir(parents=True)
    (checkout / "pyproject.toml").write_text(
        "[project]\nname = 'vibecomfy'\n", encoding="utf-8"
    )
    (checkout / "tests" / "snapshots").mkdir(parents=True)
    recipe = ready_dir / "not_in_registry.py"
    recipe.write_text("# vibecomfy-snapshot: ignore-node SaveImage\n", encoding="utf-8")
    neutral_cwd = tmp_path / "neutral-cwd"
    neutral_cwd.mkdir()
    monkeypatch.chdir(neutral_cwd)

    def no_cwd_checkout() -> Path:
        raise CheckoutRequiredError("checkout required from CWD")

    monkeypatch.setattr(test_commands, "find_repo_root", no_cwd_checkout)
    args = argparse.Namespace(path=str(recipe), force=True, json=True)
    assert test_commands._cmd_test_snapshot(args) == 2
    payload = json.loads(capsys.readouterr().out)
    assert payload["error"] == "uncatalogued_ready_template"
    assert not recipe.with_suffix(".py.snapshot.json").exists()


def test_curated_ready_scope_matrix_covers_root_nested_snapshot_diff_and_verify(
    tmp_path: Path,
    monkeypatch: pytest.MonkeyPatch,
    capsys: pytest.CaptureFixture[str],
) -> None:
    """Checkout-owned ready paths never fall through to user-recipe semantics."""
    checkout = tmp_path / "checkout"
    ready_root = checkout / "ready_templates"
    mapped_dir = ready_root / "image"
    mapped_dir.mkdir(parents=True)
    (checkout / "pyproject.toml").write_text(
        "[project]\nname = 'vibecomfy'\n", encoding="utf-8"
    )
    (checkout / "tests" / "snapshots").mkdir(parents=True)
    mapped = mapped_dir / "mapped.py"
    mapped.write_text("# mapped\n", encoding="utf-8")
    canonical_api = {"1": {"class_type": "SaveImage", "inputs": {}}}
    monkeypatch.setattr(test_commands, "_stem_map", lambda: {"mapped": "image/mapped"})
    monkeypatch.setattr(test_commands, "_build_compiled_api", lambda _: canonical_api)
    (tmp_path / "neutral").mkdir()
    monkeypatch.chdir(tmp_path / "neutral")

    def no_checkout() -> Path:
        raise CheckoutRequiredError("neutral CWD")

    monkeypatch.setattr(test_commands, "find_repo_root", no_checkout)
    assert test_commands._curated_repo_root(ready_root.resolve()) == checkout.resolve()
    assert test_commands._curated_repo_root(mapped_dir.resolve()) == checkout.resolve()

    # The mapped nested file uses canonical snapshots and never gets a user sidecar.
    snapshot_args = argparse.Namespace(path=str(mapped), force=True, json=True)
    assert test_commands._cmd_test_snapshot(snapshot_args) == 0
    capsys.readouterr()
    assert not mapped.with_suffix(".py.snapshot.json").exists()
    diff_args = argparse.Namespace(path=str(mapped), json=True)
    assert test_commands._cmd_test_diff(diff_args) == 0
    capsys.readouterr()
    assert test_commands._cmd_test_verify(argparse.Namespace(path=str(mapped_dir), json=True)) == 0
    capsys.readouterr()

    # The ready root and an unmapped nested file are curated scope, not user recipes.
    unmapped = mapped_dir / "unmapped.py"
    unmapped.write_text(
        "# vibecomfy-snapshot: ignore-node SaveImage\n", encoding="utf-8"
    )
    for args, command in (
        (argparse.Namespace(path=str(ready_root), force=True, json=True), test_commands._cmd_test_snapshot),
        (argparse.Namespace(path=str(unmapped), force=True, json=True), test_commands._cmd_test_snapshot),
        (argparse.Namespace(path=str(ready_root), json=True), test_commands._cmd_test_diff),
        (argparse.Namespace(path=str(unmapped), json=True), test_commands._cmd_test_diff),
    ):
        assert command(args) == 2
        assert json.loads(capsys.readouterr().out)["error"] == "uncatalogued_ready_template"
    assert test_commands._cmd_test_verify(argparse.Namespace(path=str(ready_root), json=True)) == 2
    verify_payload = json.loads(capsys.readouterr().out)
    assert verify_payload["error"] == "uncatalogued_ready_template"
    assert str(unmapped.resolve()) in verify_payload["uncatalogued"]
    assert not unmapped.with_suffix(".py.snapshot.json").exists()


def test_verify_rejects_missing_and_zero_snapshot_targets(
    tmp_path: Path,
    capsys: pytest.CaptureFixture[str],
) -> None:
    missing = tmp_path / "missing"
    code = test_commands._cmd_test_verify(argparse.Namespace(path=str(missing), json=True))
    assert code == 2
    assert json.loads(capsys.readouterr().out)["error"] == "invalid_target"

    empty = tmp_path / "empty"
    empty.mkdir()
    code = test_commands._cmd_test_verify(argparse.Namespace(path=str(empty), json=True))
    assert code == 1
    payload = json.loads(capsys.readouterr().out)
    assert payload["error"] == "no_snapshots"
    assert payload["ok"] is False


def test_snapshot_update_pytest_flag_is_not_advertised() -> None:
    from vibecomfy.cli import build_parser

    with pytest.raises(SystemExit):
        build_parser().parse_args(["test", "snapshot", "recipe.py", "--vibecomfy-snapshot-update"])


def test_canonicalize_api_is_byte_stable():
    """canonicalize_api on the same input twice produces the same bytes."""
    wf = make_workflow_factory()(id="stable")
    wf.nodes["1"] = VibeNode(id="1", class_type="CheckpointLoaderSimple", inputs={"ckpt_name": "x.safetensors"})
    api = wf.compile("api")
    a = canonicalize_api(api)
    b = canonicalize_api(api)
    assert a == b
