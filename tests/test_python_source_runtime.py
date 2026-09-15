from __future__ import annotations

import copy
import importlib.metadata
import json
from pathlib import Path

import pytest

from vibecomfy.comfy_nodes.exec_node import VibeComfyExec
from vibecomfy.runtime.python_source import (
    PythonSourceError,
    SourceCapsule,
    capture_source,
    execute_source_payload,
    inspect_dependency_readiness,
    load_capsule_callable,
    loaded_source_stats,
)


def _source_package(root: Path, *, body: str = "return {'image': image * FACTOR}\n") -> Path:
    package = root / "image_tools"
    package.mkdir()
    (package / "__init__.py").write_text("", encoding="utf-8")
    (package / "helpers.py").write_text("FACTOR = 3\n", encoding="utf-8")
    (package / "pipeline.py").write_text(
        "from .helpers import FACTOR\n"
        "def process(image):\n"
        f"    {body}",
        encoding="utf-8",
    )
    return package


def test_capsule_is_deterministic_and_executes_without_original_checkout(tmp_path: Path) -> None:
    package = _source_package(tmp_path)
    capsule = capture_source(package, entrypoint="pipeline:process")
    payload = capsule.to_payload()
    assert SourceCapsule.from_payload(payload).to_payload() == payload

    package.rename(tmp_path / "original-checkout-removed")
    result = execute_source_payload(
        {**payload, "result": {"mode": "mapping", "outputs": ["image"]}},
        {"image": 4},
    )
    assert result == {"image": 12}


def test_capsule_rejects_member_tampering_before_import(tmp_path: Path) -> None:
    capsule = capture_source(_source_package(tmp_path), entrypoint="pipeline:process")
    payload = copy.deepcopy(capsule.to_payload())
    payload["manifest"]["files"][-1]["sha256"] = "0" * 64

    with pytest.raises(PythonSourceError, match="member digest mismatch"):
        SourceCapsule.from_payload(payload)


def test_capsule_requires_versioned_archive_and_snapshot_digest(tmp_path: Path) -> None:
    payload = capture_source(_source_package(tmp_path), entrypoint="pipeline:process").to_payload()

    wrong_encoding = copy.deepcopy(payload)
    wrong_encoding["archive_encoding"] = "zip"
    with pytest.raises(PythonSourceError, match="archive_encoding"):
        SourceCapsule.from_payload(wrong_encoding)

    missing_digest = copy.deepcopy(payload)
    del missing_digest["snapshot_sha256"]
    with pytest.raises(PythonSourceError, match="snapshot_sha256"):
        SourceCapsule.from_payload(missing_digest)


def test_existing_digest_cache_is_verified_before_reuse(tmp_path: Path) -> None:
    capsule = capture_source(_source_package(tmp_path), entrypoint="pipeline:process")
    cache = tmp_path / "cache"
    load_capsule_callable(capsule, cache_dir=cache)
    cached_file = (
        cache
        / f"s_{capsule.snapshot_sha256}"
        / "_vibecomfy_sources"
        / f"s_{capsule.snapshot_sha256}"
        / "image_tools"
        / "pipeline.py"
    )
    cached_file.write_text("def process(image):\n    return {'image': 0}\n", encoding="utf-8")

    with pytest.raises(PythonSourceError, match="cache digest mismatch"):
        load_capsule_callable(capsule, cache_dir=cache)


def test_missing_declared_dependency_refuses_before_import(tmp_path: Path, monkeypatch: pytest.MonkeyPatch) -> None:
    package = tmp_path / "installed_tools"
    package.mkdir()
    marker = tmp_path / "imported"
    (package / "__init__.py").write_text(
        f"from pathlib import Path\nPath({str(marker)!r}).write_text('yes')\n",
        encoding="utf-8",
    )
    (package / "pipeline.py").write_text(
        "def process(value):\n    return {'value': value + 1}\n",
        encoding="utf-8",
    )
    monkeypatch.syspath_prepend(str(tmp_path))
    payload = {
        "format": "vibecomfy.python_installed/v1",
        "entrypoint": "installed_tools.pipeline:process",
        "dependencies": [{"distribution": "vibecomfy-package-that-does-not-exist", "specifier": ""}],
        "result": {"mode": "mapping", "outputs": ["value"]},
    }

    with pytest.raises(PythonSourceError, match="missing"):
        execute_source_payload(payload, {"value": 4})
    assert not marker.exists()


def test_dependency_inspection_is_read_only_and_reports_worker_readiness(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    calls: list[str] = []

    def version(distribution: str) -> str:
        calls.append(distribution)
        if distribution == "ready-package":
            return "1.4.0"
        raise importlib.metadata.PackageNotFoundError(distribution)

    monkeypatch.setattr(importlib.metadata, "version", version)
    payload = {
        "format": "vibecomfy.python_installed/v1",
        "entrypoint": "ready_package.pipeline:process",
        "dependencies": [
            {"distribution": "ready-package", "specifier": ">=1,<2"},
            {"distribution": "missing-package", "specifier": ""},
        ],
    }

    report = inspect_dependency_readiness(payload)

    assert report["environment_bound"] is True
    assert report["install_performed"] is False
    assert report["ready"] is False
    assert [item["status"] for item in report["dependencies"]] == ["ready", "missing"]
    assert calls == ["ready-package", "missing-package"]


def test_absolute_self_import_is_actionable_for_snapshot_mode(tmp_path: Path) -> None:
    package = tmp_path / "absolute_tools"
    package.mkdir()
    (package / "__init__.py").write_text("", encoding="utf-8")
    (package / "pipeline.py").write_text(
        "import absolute_tools.helpers\n"
        "def process(value):\n    return {'value': value}\n",
        encoding="utf-8",
    )
    (package / "helpers.py").write_text("", encoding="utf-8")
    capsule = capture_source(package, entrypoint="pipeline:process")

    with pytest.raises(PythonSourceError, match="absolute self-import"):
        load_capsule_callable(capsule, cache_dir=tmp_path / "cache")


def test_more_than_64_distinct_source_revisions_remain_loadable(tmp_path: Path) -> None:
    before = loaded_source_stats()["loaded_sources"]
    for index in range(65):
        module = tmp_path / f"revision_{index}.py"
        module.write_text(
            f"def process(value):\n    return {{'value': value + {index}}}\n",
            encoding="utf-8",
        )
        capsule = capture_source(module, entrypoint=f"revision_{index}:process")
        assert load_capsule_callable(capsule, cache_dir=tmp_path / "cache") is not None
    assert loaded_source_stats()["loaded_sources"] >= before + 65


def test_exec_node_accepts_source_payload_and_keeps_exact_output_contract(tmp_path: Path) -> None:
    capsule = capture_source(
        _source_package(tmp_path, body="return {'image': image * FACTOR}\n"),
        entrypoint="pipeline:process",
    )
    source = json.dumps(
        {**capsule.to_payload(), "result": {"mode": "mapping", "outputs": ["image"]}},
        sort_keys=True,
    )
    result = VibeComfyExec().execute(
        source=source,
        io={"inputs": {"image": "INT"}, "outputs": {"image": "INT"}},
        in_0=5,
    )
    assert result[0] == 15
    assert all(value is None for value in result[1:])
