from __future__ import annotations

import argparse
import inspect
from pathlib import Path

import pytest

from vibecomfy.commands.session import _config_from_args
from vibecomfy.contracts.runtime import RuntimeDependencyError, RuntimeRequirements
from vibecomfy.registry.static_contract import extract_ready_template_contract, reconcile_ready_template_source
from vibecomfy.runtime.dependencies import compare_runtime, sync_runtime
from vibecomfy.runtime.run import run_embedded_with_session
from vibecomfy.runtime.session import EmbeddedSession, ServerSession, VibeSession
from vibecomfy.workflow import VibeWorkflow, WorkflowRequirements, WorkflowSource


def test_runtime_declaration_normalizes_and_roundtrips() -> None:
    runtime = RuntimeRequirements.from_dict(
        {
            "comfyui": {"commit": "abc"},
            "python": {"version": ">=3.11"},
            "packages": {"torch": "==2.4.0"},
            "launch": {"flags": ["--lowvram", "--lowvram"]},
            "custom_nodes": [{"name": "Pack", "commit": "deadbeef"}],
        }
    )
    assert runtime is not None
    assert runtime.to_dict() == {
        "comfy_commit": "abc",
        "python_version": ">=3.11",
        "packages": {"torch": "==2.4.0"},
        "launch_flags": ["--lowvram"],
        "custom_nodes": [{"name": "Pack", "commit": "deadbeef"}],
    }


def test_runtime_declaration_rejects_legacy_contradictions() -> None:
    with pytest.raises(RuntimeDependencyError, match="contradict"):
        RuntimeRequirements.from_dict(
            {"comfy_commit": "new"}, legacy_comfy_commit="old"
        )
    with pytest.raises(RuntimeDependencyError, match="contradict"):
        RuntimeRequirements.from_dict(
            {"packages": {"torch": "==2"}},
            legacy_python_env={"torch": "==1"},
        )


def test_workflow_requirements_accept_runtime_mapping() -> None:
    requirements = WorkflowRequirements(runtime={"packages": {"numpy": ">=1"}})
    workflow = VibeWorkflow("runtime", WorkflowSource("runtime"), requirements=requirements)
    assert workflow.requirements.runtime is not None
    assert workflow.requirements.runtime.python_packages == {"numpy": ">=1"}
    assert workflow.semantic_projection()["requirements"]["runtime"] == {
        "packages": {"numpy": ">=1"}
    }


def test_compare_runtime_reports_matching_and_one_warning() -> None:
    runtime = RuntimeRequirements.from_dict(
        {"python_version": ">=3.11", "packages": {"numpy": ">=1.0"}}
    )
    assert runtime is not None
    report = compare_runtime(
        runtime,
        target={
            "python_version": "3.11.9",
            "packages": {"numpy": "1.26.0"},
        },
    )
    assert report["status"] == "matching"
    assert report["warnings"] == []

    drift = compare_runtime(runtime, target={"python_version": "3.10", "packages": {}})
    assert drift["status"] == "incompatible"
    assert drift["ok"] is False
    assert len(drift["warnings"]) == 1
    assert {item["status"] for item in drift["checks"]} == {"incompatible", "missing"}


def test_sync_runtime_is_idempotent_and_verifies() -> None:
    runtime = RuntimeRequirements.from_dict({"packages": {"numpy": "==1.26.0"}})
    assert runtime is not None
    calls: list[tuple[list[str], bool]] = []
    target = {"packages": {}}
    verified = {"packages": {"numpy": "1.26.0"}}
    report = sync_runtime(
        runtime,
        target=target,
        installer=lambda specs, offline: calls.append((specs, offline)),
        verify=lambda: verified,
    )
    assert report["synced"] is True
    assert calls == [(["numpy==1.26.0"], False)]
    again = sync_runtime(runtime, target=verified, installer=lambda *_: calls.append(([], False)))
    assert again["synced"] is False
    assert calls == [(["numpy==1.26.0"], False)]


def test_offline_sync_fails_before_installer(tmp_path: Path) -> None:
    runtime = RuntimeRequirements.from_dict({"packages": {"numpy": "==1.26.0"}})
    assert runtime is not None
    with pytest.raises(RuntimeDependencyError, match="offline"):
        sync_runtime(runtime, target={"packages": {}}, offline=True, installer=lambda *_: None)


def test_session_config_builder_returns_declared_launch_flags(tmp_path: Path) -> None:
    args = argparse.Namespace(
        port=8188,
        memory_profile=None,
        vram_policy=None,
        cache_policy=None,
        disable_smart_memory=False,
        warm_policy=None,
        reserve_vram_gb=None,
        input_directory=None,
        output_directory=None,
        temp_directory=None,
        ready_timeout_sec=None,
        launch_flags=["--use-ck-attention", "--disable-comfy-compiler"],
        runtime_root=tmp_path,
    )

    config = _config_from_args(args)

    assert config["locality"] == "managed_local_server"
    assert config["launch_flags"] == ["--use-ck-attention", "--disable-comfy-compiler"]


def test_sync_runtime_reobserves_without_injected_verifier(
    monkeypatch: pytest.MonkeyPatch, tmp_path: Path
) -> None:
    runtime = RuntimeRequirements.from_dict({"packages": {"numpy": "==1.26.0"}})
    assert runtime is not None
    (tmp_path / ".venv" / "bin").mkdir(parents=True)
    (tmp_path / ".venv" / "bin" / "python").write_text("fake", encoding="utf-8")
    (tmp_path / ".vibecomfy-managed").write_text(
        "vibecomfy-managed-runtime-v1\n", encoding="utf-8"
    )
    observed = iter(({"packages": {"numpy": "1.25.0"}}, {"packages": {"numpy": "1.26.0"}}))
    calls = 0
    def observe(**kwargs):
        nonlocal calls
        calls += 1
        return kwargs.get("target") or next(observed)
    monkeypatch.setattr(
        "vibecomfy.runtime.dependencies.inspect_runtime_target",
        observe,
    )

    report = sync_runtime(runtime, runtime_root=tmp_path, installer=lambda *_: None)

    assert report["status"] == "matching"
    assert report["synced"] is True
    assert calls == 3


def test_runtime_comparison_uses_unverified_external_target() -> None:
    runtime = RuntimeRequirements.from_dict(
        {"packages": {"torch": "==2.10.0"}, "launch_flags": ["--flag"]}
    )
    assert runtime is not None

    report = compare_runtime(runtime, target={})

    assert report["ok"] is True
    assert report["status"] == "unverified"
    assert {check["status"] for check in report["checks"]} == {"unverified"}


def test_model_comparison_requires_path_identity() -> None:
    runtime = RuntimeRequirements.from_dict(
        {"models": [{"name": "model.safetensors", "subdir": "unet", "target_path": "unet/model.safetensors"}]}
    )
    assert runtime is not None

    report = compare_runtime(
        runtime,
        target={
            "models": {
                "model.safetensors": {
                    "name": "model.safetensors",
                    "filename": "model.safetensors",
                    "subdir": "vae",
                    "target_path": "vae/model.safetensors",
                    "present": True,
                }
            }
        },
    )

    assert report["status"] == "different"
    assert report["ok"] is True


def test_static_runtime_contradiction_has_source_location(tmp_path: Path) -> None:
    source = "READY_REQUIREMENTS = {'runtime': {'comfy_commit': 'new', 'comfyui': {'commit': 'old'}}}\n"

    (tmp_path / "workflow.py").write_text(source, encoding="utf-8")
    extracted = extract_ready_template_contract(tmp_path / "workflow.py")
    diagnostic = next(item for item in extracted["diagnostics"] if item["code"] == "static_runtime_contract_invalid")
    assert diagnostic["location"]["source_path"] == str(tmp_path / "workflow.py")
    assert diagnostic["location"]["line"] == 1

    reconciled = reconcile_ready_template_source(source, source_path=tmp_path / "workflow.py")
    diagnostic = next(item for item in reconciled["diagnostics"] if item["code"] == "static_runtime_contract_invalid")
    assert diagnostic["location"]["line"] == 1
    assert diagnostic["location"]["path"] == "requirements.runtime"


def test_static_metadata_runtime_and_legacy_python_env_contradiction(tmp_path: Path) -> None:
    source = (
        "READY_METADATA = ReadyMetadata.build("
        "requirements={'runtime': {'packages': {'torch': '==2'}}}, "
        "python_env={'torch': '==1'})\n"
    )
    path = tmp_path / "workflow.py"
    path.write_text(source, encoding="utf-8")

    extracted = extract_ready_template_contract(path)

    diagnostic = next(
        item for item in extracted["diagnostics"]
        if item["code"] == "static_runtime_contract_invalid"
    )
    assert diagnostic["location"]["source_path"] == str(path)
    assert diagnostic["location"]["path"] == "requirements.runtime"


def test_sync_runtime_only_installs_nonmatching_packages() -> None:
    runtime = RuntimeRequirements.from_dict(
        {"packages": {"numpy": "==1.26.0", "pandas": "==2.2.0"}}
    )
    assert runtime is not None
    calls: list[list[str]] = []
    report = sync_runtime(
        runtime,
        target={"packages": {"numpy": "1.26.0", "pandas": None}},
        installer=lambda specs, _offline: calls.append(specs),
        verify=lambda: {"packages": {"numpy": "1.26.0", "pandas": "2.2.0"}},
    )

    assert report["status"] == "matching"
    assert calls == [["pandas==2.2.0"]]


def test_public_session_surfaces_expose_dependency_mode() -> None:
    for fn in (VibeSession.run, EmbeddedSession.run, ServerSession.run, run_embedded_with_session):
        assert inspect.signature(fn).parameters["dependency_mode"].kind is inspect.Parameter.KEYWORD_ONLY
