from __future__ import annotations

import json
from pathlib import Path
from types import SimpleNamespace
from typing import Any

import pytest

import vibecomfy.fetch as fetch_module
import vibecomfy.node_packs as node_packs_module
from vibecomfy.runtime.prepared import (
    build_plan,
    prepare_workflow,
    read_declaration,
)


def _workflow(*, custom_nodes: tuple[str, ...] = ()) -> Any:
    return SimpleNamespace(
        requirements=SimpleNamespace(models=[], custom_nodes=list(custom_nodes))
    )


@pytest.mark.parametrize(
    ("assignment", "expected"),
    [
        (
            "PREPARE",
            {
                "models": [{"name": "prepare.safetensors", "subdir": "checkpoints"}],
                "custom_nodes": ["prepare-pack"],
            },
        ),
        (
            "READY_REQUIREMENTS",
            {
                "models": [{"name": "ready.safetensors", "subdir": "loras"}],
                "custom_nodes": ["ready-pack"],
            },
        ),
    ],
)
def test_read_declaration_reads_literal_assignments_without_importing(
    tmp_path: Path, assignment: str, expected: dict[str, Any]
) -> None:
    declaration_path = tmp_path / "declaration.py"
    declaration_path.write_text(
        f"{assignment} = {expected!r}\n"
        "SIDE_EFFECT = __import__('module_that_must_not_be_imported')\n"
        "READY_METADATA = build_metadata()\n",
        encoding="utf-8",
    )

    assert read_declaration(declaration_path) == expected


def test_build_plan_normalizes_declared_requirements_and_lists_actions() -> None:
    model = {"name": "checkpoint.safetensors", "subdir": "checkpoints"}
    plan = build_plan(
        _workflow(custom_nodes=("metadata-pack",)),
        reference="image/example.py",
        declaration={
            "models": [model],
            "custom_nodes": ["z-pack", "a-pack", "z-pack", ""],
            "python_packages": ["torch", "numpy", "torch"],
        },
    )

    assert plan.workflow == "image/example.py"
    assert plan.models == (model,)
    assert plan.custom_nodes == ("a-pack", "z-pack")
    assert plan.python_packages == ("numpy", "torch")
    assert plan.actions == (
        {"kind": "custom_nodes", "status": "planned", "count": 2},
        {"kind": "models", "status": "planned", "count": 1},
        {"kind": "python_packages", "status": "declared", "count": 2},
    )
    assert plan.declaration_source == "PREPARE/READY_REQUIREMENTS"


def test_build_plan_reconciles_registry_model_without_authored_url() -> None:
    plan = build_plan(
        _workflow(),
        reference="image/example.py",
        declaration={
            "models": [
                {"name": "qwen_3_4b.safetensors", "subdir": "text_encoders"}
            ]
        },
    )

    [model] = plan.models
    assert model["url"].endswith(
        "/Comfy-Org/z_image_turbo/resolve/main/split_files/text_encoders/qwen_3_4b.safetensors"
    )


def test_prepare_workflow_dry_run_does_not_write_download_or_install(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    def unexpected_download(*args: Any, **kwargs: Any) -> Any:
        raise AssertionError("dry-run called the model downloader")

    def unexpected_pack_lookup(*args: Any, **kwargs: Any) -> Any:
        raise AssertionError("dry-run planned custom-node installation")

    def unexpected_install(*args: Any, **kwargs: Any) -> Any:
        raise AssertionError("dry-run installed a custom-node pack")

    monkeypatch.setattr(fetch_module, "download_many", unexpected_download)
    monkeypatch.setattr(node_packs_module, "missing_packs_for_workflow", unexpected_pack_lookup)
    monkeypatch.setattr(node_packs_module, "install_required_packs", unexpected_install)

    runtime_root = tmp_path / "runtime"
    result = prepare_workflow(
        _workflow(),
        reference="image/example.py",
        runtime_root=runtime_root,
        declaration={
            "models": [{"name": "checkpoint.safetensors", "subdir": "checkpoints"}],
            "custom_nodes": ["example-pack"],
        },
        dry_run=True,
    )

    assert result.dry_run is True
    assert result.prepared is False
    assert result.receipt_path is None
    assert not runtime_root.exists()


def test_prepare_workflow_serializes_receipt_with_fake_preparation_seams(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    download_calls: list[tuple[list[dict[str, Any]], Path]] = []
    install_calls: list[tuple[tuple[Any, ...], tuple[Any, ...], Path, Path]] = []
    model = {"name": "checkpoint.safetensors", "subdir": "checkpoints"}
    fake_pack = SimpleNamespace(name="example-pack")

    def fake_download_many(entries: list[dict[str, Any]], *, root: Path) -> list[Path]:
        download_calls.append((entries, root))
        return [root / entries[0]["subdir"] / entries[0]["name"]]

    def fake_missing_packs(workflow: Any) -> tuple[list[Any], list[str]]:
        return [fake_pack], []

    def fake_install_required_packs(
        packs: list[Any], *, install_root: Path, lockfile_path: Path, restore_entries: list[Any]
    ) -> Any:
        install_calls.append((tuple(packs), tuple(restore_entries), install_root, lockfile_path))
        return SimpleNamespace(
            ok=True,
            results=(
                SimpleNamespace(
                    name="example-pack",
                    status="installed",
                    git_commit_sha="abc123",
                    error=None,
                ),
            ),
        )

    monkeypatch.setattr(fetch_module, "download_many", fake_download_many)
    monkeypatch.setattr(node_packs_module, "missing_packs_for_workflow", fake_missing_packs)
    monkeypatch.setattr(node_packs_module, "install_required_packs", fake_install_required_packs)

    runtime_root = tmp_path / "runtime"
    (runtime_root).mkdir(parents=True)
    (runtime_root / "custom_nodes.lock").write_text(
        "# Generated by vibecomfy nodes lock.\n"
        "example-pack abc123 https://example.test/example-pack.git\n",
        encoding="utf-8",
    )
    result = prepare_workflow(
        _workflow(),
        reference=tmp_path / "workflow.py",
        runtime_root=runtime_root,
        declaration={"models": [model], "custom_nodes": ["example-pack"]},
        session_id="session-1",
    )

    assert result.prepared is True
    assert result.model_paths == (
        str(runtime_root / "ComfyUI" / "models" / "checkpoints" / "checkpoint.safetensors"),
    )
    assert result.node_results == (
        {
            "name": "example-pack",
            "status": "installed",
            "git_commit_sha": "abc123",
            "error": None,
        },
    )
    assert download_calls == [
        ([model], runtime_root / "ComfyUI" / "models"),
    ]
    assert install_calls == [
        (
            (fake_pack,),
            (
                node_packs_module.read_lockfile(runtime_root / "custom_nodes.lock")[0],
            ),
            runtime_root / "custom_nodes",
            runtime_root / "custom_nodes.lock",
        ),
    ]

    receipt_path = Path(result.receipt_path or "")
    assert receipt_path == runtime_root / "out" / "preparations" / "workflow-session-1.json"
    receipt = json.loads(receipt_path.read_text(encoding="utf-8"))
    assert receipt == result.to_json()
    assert receipt["ok"] is True
    assert receipt["plan"]["models"] == [model]
