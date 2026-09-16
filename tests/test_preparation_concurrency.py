from __future__ import annotations

import threading
from pathlib import Path
from types import SimpleNamespace
from typing import Any

import pytest

import vibecomfy.fetch as fetch_module
from vibecomfy.runtime.prepared import PreparationError, prepare_workflow


def _workflow() -> Any:
    return SimpleNamespace(
        metadata={},
        nodes={},
        runtime_nodes=lambda: {},
        requirements=SimpleNamespace(models=[], custom_nodes=[]),
    )


def test_download_many_overlaps_downloads_and_preserves_declaration_order(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    entries = [
        {"name": "first.safetensors", "subdir": "checkpoints", "url": "https://first"},
        {"name": "second.safetensors", "subdir": "checkpoints", "url": "https://second"},
    ]
    entered = threading.Barrier(2)
    second_finished = threading.Event()
    overlap_observed = threading.Event()
    active = 0
    active_lock = threading.Lock()

    monkeypatch.setattr(fetch_module, "is_present", lambda entry, *, root=None: False)

    def fake_download(
        entry: dict[str, Any], *, root: Path, **_: Any
    ) -> Path:
        nonlocal active
        with active_lock:
            active += 1
            if active == 2:
                overlap_observed.set()
        try:
            entered.wait(timeout=2)
            if entry["name"] == "second.safetensors":
                second_finished.set()
            else:
                assert second_finished.wait(timeout=2)
            return root / entry["subdir"] / entry["name"]
        finally:
            with active_lock:
                active -= 1

    monkeypatch.setattr(fetch_module, "download", fake_download)

    assert fetch_module.download_many(entries, root=tmp_path, max_workers=2) == [
        tmp_path / "checkpoints" / "first.safetensors",
        tmp_path / "checkpoints" / "second.safetensors",
    ]
    assert overlap_observed.is_set()


@pytest.mark.parametrize("worker_count", [0, -1, True, 1.5, "2", None])
def test_download_many_rejects_invalid_worker_counts(worker_count: Any) -> None:
    with pytest.raises(ValueError, match="positive integer"):
        fetch_module.download_many([], max_workers=worker_count)


def test_prepare_workflow_deduplicates_exact_model_declarations_before_download(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    model = {
        "name": "checkpoint.safetensors",
        "subdir": "checkpoints",
        "url": "https://example.test/checkpoint",
    }
    calls: list[tuple[list[dict[str, Any]], Path, int]] = []

    def fake_download_many(
        entries: list[dict[str, Any]], *, root: Path, max_workers: int, **_: Any
    ) -> list[Path]:
        calls.append((entries, root, max_workers))
        return [root / entries[0]["subdir"] / entries[0]["name"]]

    monkeypatch.setattr(fetch_module, "download_many", fake_download_many)

    workflow = _workflow()
    workflow.metadata["model_assets"] = [model, dict(model)]
    result = prepare_workflow(
        workflow,
        reference=tmp_path / "workflow.py",
        runtime_root=tmp_path / "runtime",
        ensure_packs=False,
    )

    assert result.plan.models == (model,)
    assert calls == [
        (
            [model],
            tmp_path / "runtime" / "ComfyUI" / "models",
            2,
        )
    ]


def test_prepare_workflow_rejects_conflicting_destination_before_download(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    conflicting_models = [
        {
            "name": "checkpoint.safetensors",
            "subdir": "checkpoints",
            "url": "https://example.test/first",
            "sha256": "a" * 64,
        },
        {
            "name": "checkpoint.safetensors",
            "subdir": "checkpoints",
            "url": "https://example.test/second",
            "sha256": "b" * 64,
        },
    ]

    def unexpected_download(*args: Any, **kwargs: Any) -> Any:
        raise AssertionError("conflicting declarations reached the downloader")

    monkeypatch.setattr(fetch_module, "download_many", unexpected_download)

    with pytest.raises(PreparationError, match="destination collision"):
        workflow = _workflow()
        workflow.metadata["model_assets"] = conflicting_models
        prepare_workflow(
            workflow,
            reference=tmp_path / "workflow.py",
            runtime_root=tmp_path / "runtime",
            ensure_packs=False,
        )


def test_prepare_workflow_never_infers_missing_model_url_from_registry(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    import vibecomfy.registry.models_loader as models_loader

    def unexpected_registry_lookup(*_args: Any, **_kwargs: Any) -> Any:
        raise AssertionError("runtime preparation must not consult the model registry")

    monkeypatch.setattr(models_loader, "load_registry", unexpected_registry_lookup)
    monkeypatch.setattr(models_loader, "resolve_model_entry", unexpected_registry_lookup)

    workflow = _workflow()
    workflow.metadata["model_assets"] = [{
        "name": "registry-only.safetensors",
        "subdir": "checkpoints",
    }]

    with pytest.raises(PreparationError, match="could not resolve URLs"):
        prepare_workflow(
            workflow,
            reference=tmp_path / "workflow.py",
            runtime_root=tmp_path / "runtime",
            ensure_packs=False,
        )


def test_prepare_workflow_rejects_unsupported_model_revision_before_download(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    def unexpected_download(*args: Any, **kwargs: Any) -> Any:
        raise AssertionError("unsupported model revision reached the downloader")

    monkeypatch.setattr(fetch_module, "download_many", unexpected_download)
    workflow = _workflow()
    workflow.metadata["model_assets"] = [{
        "name": "model.safetensors",
        "subdir": "checkpoints",
        "url": "https://example.test/model.safetensors",
        "hf_revision": "rev1",
    }]

    with pytest.raises(PreparationError, match="unsupported revision selector"):
        prepare_workflow(
            workflow,
            reference=tmp_path / "workflow.py",
            runtime_root=tmp_path / "runtime",
            ensure_packs=False,
        )


def test_prepare_workflow_passes_authored_custom_node_ref_to_installer(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    import vibecomfy.node_packs as node_packs

    pack = node_packs.CustomNodePack(
        "ExamplePack", "https://catalog.example/example.git", frozenset({"ExampleNode"})
    )
    workflow = _workflow()
    workflow.requirements.custom_nodes = ["ExamplePack"]
    workflow.metadata["requirements"] = {
        "custom_node_refs": [{
            "slug": "example-pack",
            "source": "git",
            "url": "https://authored.example/example.git",
            "version": "v1.2.3",
            "commit": "feedfacefeedfacefeedfacefeedfacefeedface",
        }]
    }
    install_calls: list[dict[str, Any]] = []

    monkeypatch.setattr(node_packs, "read_lockfile", lambda _path: [])
    monkeypatch.setattr(
        node_packs,
        "missing_packs_for_workflow",
        lambda _workflow, lockfile_path: ([pack], []),
    )
    monkeypatch.setattr(node_packs, "preflight_pip_requirements", lambda _packs: node_packs.PipPreflightResult(ok=True))

    def fake_install(packs: Any, **kwargs: Any) -> Any:
        install_calls.append(kwargs)
        return node_packs.InstallBatchResult(
            ok=True,
            results=(node_packs.InstallResult("ExamplePack", "installed", "feedfacefeedfacefeedfacefeedfacefeedface", None),),
            preflight=node_packs.PipPreflightResult(ok=True),
        )

    monkeypatch.setattr(node_packs, "install_required_packs", fake_install)

    prepare_workflow(
        workflow,
        reference=tmp_path / "workflow.py",
        runtime_root=tmp_path / "runtime",
        ensure_models=False,
        ensure_packs=True,
    )

    assert len(install_calls) == 1
    authored = install_calls[0]["install_refs_by_name"]["ExamplePack"]
    assert authored.url == "https://authored.example/example.git"
    assert authored.version == "v1.2.3"
    assert authored.commit == "feedfacefeedfacefeedfacefeedfacefeedface"
