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
