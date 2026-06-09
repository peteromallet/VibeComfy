from __future__ import annotations

import asyncio
import importlib
from contextlib import asynccontextmanager
from pathlib import Path
from typing import Any

import pytest

import vibecomfy.node_packs_install as node_packs_install
import vibecomfy.runtime.session as session_module
from vibecomfy.node_packs import CustomNodePack
from vibecomfy.runtime.session import EmbeddedSession
from vibecomfy.workflow import VibeNode, VibeWorkflow, WorkflowSource

from tests._runtime_session_helpers import (
    _patch_fast_runtime_run,
    _workflow,
    fake_comfy,  # noqa: F401 -- pytest fixture imported for use in tests
)


runtime_run_module = importlib.import_module("vibecomfy.runtime.run")


def test_one_shot_run_validates_against_active_url(tmp_path: Path, monkeypatch: pytest.MonkeyPatch) -> None:
    monkeypatch.chdir(tmp_path)
    built_for: list[str | None] = []
    queued_urls: list[str] = []

    @asynccontextmanager
    async def fake_server(*, server_url=None, log_path=None, config=None):
        assert config is None
        yield "http://active-runtime.test"

    def fake_build(server_url: str | None):
        built_for.append(server_url)
        return object()

    async def fake_prepare(workflow, *, backend, schema_provider, on_unavailable, cache_only=False):
        return workflow.compile(backend=backend)

    async def fake_history(*args, **kwargs):
        return {}

    class FakeClient:
        def __init__(self, server_url: str) -> None:
            queued_urls.append(server_url)

        async def queue_prompt(self, prompt: dict[str, Any]) -> dict[str, Any]:
            return {"prompt_id": "prompt-1"}

    monkeypatch.setattr(runtime_run_module, "comfy_server", fake_server)
    monkeypatch.setattr(runtime_run_module, "_build_schema_provider", fake_build)
    monkeypatch.setattr(runtime_run_module, "_prepare_prompt_async", fake_prepare)
    monkeypatch.setattr(runtime_run_module, "ComfyClient", FakeClient)
    monkeypatch.setattr(runtime_run_module, "_wait_for_server_history", fake_history)

    asyncio.run(runtime_run_module.run(_workflow(), server_url="http://configured.test"))

    assert built_for == ["http://active-runtime.test"]
    assert queued_urls == ["http://active-runtime.test"]


def test_embedded_run_ensure_packs_invokes_install_then_reload_then_queue(
    fake_comfy,
    tmp_path: Path,
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    monkeypatch.chdir(tmp_path)
    _patch_fast_runtime_run(monkeypatch)
    pack = CustomNodePack(
        name="ExamplePack",
        repo="https://example.test/example.git",
        classes=frozenset({"ExampleNode"}),
    )
    calls: list[str] = []

    monkeypatch.setattr(node_packs_install, "missing_packs_for_workflow", lambda workflow: ([pack], []))

    def fake_install_required_packs(packs, *, force=False, restore_entries):
        assert force is False
        assert restore_entries == []
        calls.extend(f"install:{pack.name}" for pack in packs)
        return node_packs_install.InstallBatchResult(
            ok=True,
            results=tuple(
                node_packs_install.InstallResult(
                    name=pack.name,
                    status="installed",
                    git_commit_sha="abc123",
                    error=None,
                )
                for pack in packs
            ),
            preflight=node_packs_install.PipPreflightResult(ok=True),
        )

    async def fake_reload(*, reason: str) -> None:
        calls.append(f"reload:{reason}")

    async def fake_queue(self, api_dict):
        calls.append("queue")
        return {"prompt_id": "prompt-ensure", "outputs": []}

    monkeypatch.setattr(node_packs_install, "install_required_packs", fake_install_required_packs)
    monkeypatch.setattr(fake_comfy, "queue_prompt_api", fake_queue)

    async def run_case() -> None:
        session = EmbeddedSession()
        session.reload_for_nodepack_change = fake_reload  # type: ignore[method-assign]
        try:
            await session.run(_workflow(), ensure_packs=True)
        finally:
            await session.stop()

    asyncio.run(run_case())

    assert calls == ["install:ExamplePack", "reload:ensure_packs", "queue"]


def test_embedded_run_ensure_packs_prefers_lockfile_restore(
    fake_comfy,
    tmp_path: Path,
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    monkeypatch.chdir(tmp_path)
    _patch_fast_runtime_run(monkeypatch)
    pack = CustomNodePack(
        name="ExamplePack",
        repo="https://example.test/example.git",
        classes=frozenset({"ExampleNode"}),
    )
    calls: list[str] = []

    Path("custom_nodes.lock").write_text(
        "ExamplePack pinnedsha https://example.test/example.git\n",
        encoding="utf-8",
    )
    monkeypatch.setattr(node_packs_install, "missing_packs_for_workflow", lambda workflow: ([pack], []))

    def fake_install_required_packs(packs, *, force=False, restore_entries):
        assert force is False
        assert [pack.name for pack in packs] == ["ExamplePack"]
        assert len(restore_entries) == 1
        entry = restore_entries[0]
        calls.append(f"restore:{entry.name}:{entry.git_commit_sha}")
        return node_packs_install.InstallBatchResult(
            ok=True,
            results=(
                node_packs_install.InstallResult(
                    name=entry.name,
                    status="refreshed",
                    git_commit_sha=entry.git_commit_sha,
                    error=None,
                ),
            ),
            preflight=node_packs_install.PipPreflightResult(ok=True),
        )

    async def fake_reload(*, reason: str) -> None:
        calls.append(f"reload:{reason}")

    async def fake_queue(self, api_dict):
        calls.append("queue")
        return {"prompt_id": "prompt-ensure", "outputs": []}

    monkeypatch.setattr(node_packs_install, "install_required_packs", fake_install_required_packs)
    monkeypatch.setattr(fake_comfy, "queue_prompt_api", fake_queue)

    async def run_case() -> None:
        session = EmbeddedSession()
        session.reload_for_nodepack_change = fake_reload  # type: ignore[method-assign]
        try:
            await session.run(_workflow(), ensure_packs=True)
        finally:
            await session.stop()

    asyncio.run(run_case())

    assert calls == ["restore:ExamplePack:pinnedsha", "reload:ensure_packs", "queue"]


def test_embedded_run_ensure_packs_skips_reload_when_nothing_missing(
    fake_comfy,
    tmp_path: Path,
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    monkeypatch.chdir(tmp_path)
    _patch_fast_runtime_run(monkeypatch)
    calls: list[str] = []

    monkeypatch.setattr(node_packs_install, "missing_packs_for_workflow", lambda workflow: ([], []))

    def fake_install_required_packs(packs, *, force=False, restore_entries):
        raise AssertionError("install_required_packs must not be called when no packs are missing")

    async def fake_reload(*, reason: str) -> None:
        calls.append(f"reload:{reason}")

    async def fake_queue(self, api_dict):
        calls.append("queue")
        return {"prompt_id": "prompt-ensure", "outputs": []}

    monkeypatch.setattr(node_packs_install, "install_required_packs", fake_install_required_packs)
    monkeypatch.setattr(fake_comfy, "queue_prompt_api", fake_queue)

    async def run_case() -> None:
        session = EmbeddedSession()
        session.reload_for_nodepack_change = fake_reload  # type: ignore[method-assign]
        try:
            await session.run(_workflow(), ensure_packs=True)
        finally:
            await session.stop()

    asyncio.run(run_case())

    assert calls == ["queue"]


def test_embedded_run_ensure_packs_continues_without_node_index_for_builtin_workflow(
    fake_comfy,
    tmp_path: Path,
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    monkeypatch.chdir(tmp_path)
    _patch_fast_runtime_run(monkeypatch)
    calls: list[str] = []

    def missing_index(_workflow):
        raise FileNotFoundError("node_index.json not found at node_index.json; run `vibecomfy sources sync`")

    monkeypatch.setattr(node_packs_install, "missing_packs_for_workflow", missing_index)
    monkeypatch.setattr(session_module, "_node_packs_from_requirements", lambda workflow: [])

    async def fake_queue(self, api_dict):
        calls.append("queue")
        return {"prompt_id": "prompt-no-index", "outputs": []}

    monkeypatch.setattr(fake_comfy, "queue_prompt_api", fake_queue)

    async def run_case() -> None:
        session = EmbeddedSession()
        try:
            await session.run(_workflow(), ensure_packs=True)
        finally:
            await session.stop()

    asyncio.run(run_case())
    assert calls == ["queue"]


def test_embedded_run_ensure_packs_falls_back_to_declared_requirements(
    fake_comfy,
    tmp_path: Path,
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    monkeypatch.chdir(tmp_path)
    _patch_fast_runtime_run(monkeypatch)
    pack = CustomNodePack(
        name="ExamplePack",
        repo="https://example.test/example.git",
        classes=frozenset({"ExampleNode"}),
    )
    calls: list[str] = []

    def missing_index(_workflow):
        raise FileNotFoundError("node_index.json not found at node_index.json; run `vibecomfy sources sync`")

    monkeypatch.setattr(node_packs_install, "missing_packs_for_workflow", missing_index)
    monkeypatch.setattr(session_module, "_node_packs_from_requirements", lambda workflow: [pack])

    def fake_install_required_packs(packs, *, force=False, restore_entries):
        assert force is False
        assert restore_entries == []
        calls.extend(f"install:{pack.name}" for pack in packs)
        return node_packs_install.InstallBatchResult(
            ok=True,
            results=tuple(
                node_packs_install.InstallResult(
                    name=pack.name,
                    status="installed",
                    git_commit_sha="abc123",
                    error=None,
                )
                for pack in packs
            ),
            preflight=node_packs_install.PipPreflightResult(ok=True),
        )

    async def fake_reload(*, reason: str) -> None:
        calls.append(f"reload:{reason}")

    async def fake_queue(self, api_dict):
        calls.append("queue")
        return {"prompt_id": "prompt-ensure", "outputs": []}

    monkeypatch.setattr(node_packs_install, "install_required_packs", fake_install_required_packs)
    monkeypatch.setattr(fake_comfy, "queue_prompt_api", fake_queue)

    async def run_case() -> None:
        session = EmbeddedSession()
        session.reload_for_nodepack_change = fake_reload  # type: ignore[method-assign]
        try:
            await session.run(_workflow(), ensure_packs=True)
        finally:
            await session.stop()

    asyncio.run(run_case())

    assert calls == ["install:ExamplePack", "reload:ensure_packs", "queue"]


def test_embedded_run_ensure_packs_falls_back_to_workflow_class_types(
    fake_comfy,
    tmp_path: Path,
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    monkeypatch.chdir(tmp_path)
    _patch_fast_runtime_run(monkeypatch)
    calls: list[str] = []

    def missing_index(_workflow):
        raise FileNotFoundError("node_index.json not found at node_index.json; run `vibecomfy sources sync`")

    def fake_install_required_packs(packs, *, force=False, restore_entries):
        assert force is False
        assert restore_entries == []
        calls.extend(f"install:{pack.name}" for pack in packs)
        return node_packs_install.InstallBatchResult(
            ok=True,
            results=tuple(
                node_packs_install.InstallResult(
                    name=pack.name,
                    status="installed",
                    git_commit_sha="abc123",
                    error=None,
                )
                for pack in packs
            ),
            preflight=node_packs_install.PipPreflightResult(ok=True),
        )

    async def fake_reload(*, reason: str) -> None:
        calls.append(f"reload:{reason}")

    async def fake_queue(self, api_dict):
        calls.append("queue")
        return {"prompt_id": "prompt-ensure", "outputs": []}

    workflow = _workflow()
    workflow.nodes["3"] = VibeNode("3", "WanVideoVAELoader")

    monkeypatch.setattr(node_packs_install, "missing_packs_for_workflow", missing_index)
    monkeypatch.setattr(node_packs_install, "install_required_packs", fake_install_required_packs)
    monkeypatch.setattr(fake_comfy, "queue_prompt_api", fake_queue)

    async def run_case() -> None:
        session = EmbeddedSession()
        session.reload_for_nodepack_change = fake_reload  # type: ignore[method-assign]
        try:
            await session.run(workflow, ensure_packs=True)
        finally:
            await session.stop()

    asyncio.run(run_case())

    assert calls == ["install:ComfyUI-WanVideoWrapper", "reload:ensure_packs", "queue"]


def test_embedded_run_ensure_packs_raises_batch_failure_without_reload_or_queue(
    fake_comfy,
    tmp_path: Path,
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    monkeypatch.chdir(tmp_path)
    _patch_fast_runtime_run(monkeypatch)
    pack = CustomNodePack(
        name="ExamplePack",
        repo="https://example.test/example.git",
        classes=frozenset({"ExampleNode"}),
    )
    calls: list[str] = []

    monkeypatch.setattr(node_packs_install, "missing_packs_for_workflow", lambda workflow: ([pack], []))

    def fake_install_required_packs(packs, *, force=False, restore_entries):
        assert force is False
        assert restore_entries == []
        calls.extend(f"install:{pack.name}" for pack in packs)
        return node_packs_install.InstallBatchResult(
            ok=False,
            results=(
                node_packs_install.InstallResult(
                    name="ExamplePack",
                    status="failed",
                    git_commit_sha=None,
                    error="clone failed",
                ),
            ),
            preflight=node_packs_install.PipPreflightResult(ok=True),
        )

    async def fake_reload(*, reason: str) -> None:
        calls.append(f"reload:{reason}")

    async def fake_queue(self, api_dict):
        calls.append("queue")
        return {"prompt_id": "prompt-ensure", "outputs": []}

    monkeypatch.setattr(node_packs_install, "install_required_packs", fake_install_required_packs)
    monkeypatch.setattr(fake_comfy, "queue_prompt_api", fake_queue)

    async def run_case() -> None:
        session = EmbeddedSession()
        session.reload_for_nodepack_change = fake_reload  # type: ignore[method-assign]
        try:
            with pytest.raises(RuntimeError, match="ensure_packs: install failed: ExamplePack: clone failed"):
                await session.run(_workflow(), ensure_packs=True)
        finally:
            await session.stop()

    asyncio.run(run_case())

    assert calls == ["install:ExamplePack"]


def test_embedded_run_ensure_models_downloads_declared_assets(
    fake_comfy,
    tmp_path: Path,
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    monkeypatch.chdir(tmp_path)
    _patch_fast_runtime_run(monkeypatch)
    calls: list[Any] = []

    workflow = _workflow()
    workflow.metadata["model_assets"] = [
        {
            "name": "model-a.safetensors",
            "url": "https://example.test/model.safetensors",
            "directory": "checkpoints",
        }
    ]

    def fake_download_many(entries):
        calls.append(entries)
        return []

    async def fake_queue(self, api_dict):
        calls.append("queue")
        return {"prompt_id": "prompt-ensure-models", "outputs": []}

    import vibecomfy.fetch as fetch_assets

    monkeypatch.setattr(fetch_assets, "download_many", fake_download_many)
    monkeypatch.setattr(fake_comfy, "queue_prompt_api", fake_queue)

    async def run_case() -> None:
        session = EmbeddedSession()
        try:
            await session.run(workflow, ensure_models=True)
        finally:
            await session.stop()

    asyncio.run(run_case())

    assert calls == [
        [
            {
                "name": "model-a.safetensors",
                "url": "https://example.test/model.safetensors",
                "subdir": "checkpoints",
            }
        ],
        "queue",
    ]


def test_embedded_run_ensure_models_resolves_registry_assets_from_final_workflow(
    fake_comfy,
    tmp_path: Path,
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    monkeypatch.chdir(tmp_path)
    _patch_fast_runtime_run(monkeypatch)
    calls: list[Any] = []

    workflow = VibeWorkflow("asset-resolution", WorkflowSource("asset-resolution"))
    workflow.nodes["5011"] = VibeNode(
        "5011",
        "LTXICLoRALoaderModelOnly",
        inputs={"lora_name": "ltxv/ltx2/ltx-2.3-22b-ic-lora-union-control-ref0.5.safetensors"},
    )

    def fake_download_many(entries):
        calls.append(entries)
        return []

    async def fake_queue(self, api_dict):
        calls.append("queue")
        return {"prompt_id": "prompt-resolved-models", "outputs": []}

    import vibecomfy.fetch as fetch_assets

    monkeypatch.setattr(fetch_assets, "download_many", fake_download_many)
    monkeypatch.setattr(fake_comfy, "queue_prompt_api", fake_queue)

    async def run_case() -> None:
        session = EmbeddedSession()
        try:
            await session.run(workflow, ensure_models=True)
        finally:
            await session.stop()

    asyncio.run(run_case())

    assert calls == [
        [
            {
                "name": "ltxv/ltx2/ltx-2.3-22b-ic-lora-union-control-ref0.5.safetensors",
                "url": "https://huggingface.co/qqceqqq/LTX-2.3-22b-IC-LoRA-Union-Control/resolve/main/ltx-2.3-22b-ic-lora-union-control-ref0.5.safetensors",
                "subdir": "loras",
            }
        ],
        "queue",
    ]


def test_embedded_run_ensure_models_does_not_cross_resolve_same_basename_between_model_dirs(
    fake_comfy,
    tmp_path: Path,
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    monkeypatch.chdir(tmp_path)
    _patch_fast_runtime_run(monkeypatch)
    calls: list[Any] = []

    workflow = VibeWorkflow("asset-resolution", WorkflowSource("asset-resolution"))
    workflow.nodes["175"] = VibeNode(
        "175",
        "LTXVAudioVAELoader",
        inputs={"ckpt_name": "LTX23_audio_vae_bf16.safetensors"},
    )
    workflow.metadata["model_assets"] = [
        {
            "name": "LTX23_audio_vae_bf16.safetensors",
            "url": "https://huggingface.co/Kijai/LTX2.3_comfy/resolve/main/vae/LTX23_audio_vae_bf16.safetensors",
            "subdir": "checkpoints",
        }
    ]

    def fake_download_many(entries):
        calls.append(entries)
        return []

    async def fake_queue(self, api_dict):
        calls.append("queue")
        return {"prompt_id": "prompt-resolved-models", "outputs": []}

    import vibecomfy.fetch as fetch_assets

    monkeypatch.setattr(fetch_assets, "download_many", fake_download_many)
    monkeypatch.setattr(fake_comfy, "queue_prompt_api", fake_queue)

    async def run_case() -> None:
        session = EmbeddedSession()
        try:
            await session.run(workflow, ensure_models=True)
        finally:
            await session.stop()

    asyncio.run(run_case())

    assert calls == [workflow.metadata["model_assets"], "queue"]


def test_embedded_run_ensure_models_matches_declared_assets_with_normalized_paths(
    fake_comfy,
    tmp_path: Path,
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    monkeypatch.chdir(tmp_path)
    _patch_fast_runtime_run(monkeypatch)
    calls: list[Any] = []

    workflow = VibeWorkflow("asset-normalization", WorkflowSource("asset-normalization"))
    workflow.nodes["186"] = VibeNode(
        "186",
        "LoraLoaderModelOnly",
        inputs={"lora_name": r"LTX\v2\ltx-2.3-22b-distilled-1.1_lora-dynamic_fro09_avg_rank_111_bf16.safetensors"},
    )
    workflow.metadata["model_assets"] = [
        {
            "name": "LTX/v2/ltx-2.3-22b-distilled-1.1_lora-dynamic_fro09_avg_rank_111_bf16.safetensors",
            "url": "https://example.test/ltx-runexx.safetensors",
            "subdir": "loras",
        }
    ]

    def fake_download_many(entries):
        calls.append(entries)
        return []

    async def fake_queue(self, api_dict):
        calls.append("queue")
        return {"prompt_id": "prompt-normalized-models", "outputs": []}

    import vibecomfy.fetch as fetch_assets

    monkeypatch.setattr(fetch_assets, "download_many", fake_download_many)
    monkeypatch.setattr(fake_comfy, "queue_prompt_api", fake_queue)

    async def run_case() -> None:
        session = EmbeddedSession()
        try:
            await session.run(workflow, ensure_models=True)
        finally:
            await session.stop()

    asyncio.run(run_case())

    assert calls == [
        [
            {
                "name": "LTX/v2/ltx-2.3-22b-distilled-1.1_lora-dynamic_fro09_avg_rank_111_bf16.safetensors",
                "url": "https://example.test/ltx-runexx.safetensors",
                "subdir": "loras",
            }
        ],
        "queue",
    ]


def test_embedded_run_ensure_models_matches_custom_node_model_directories(
    fake_comfy,
    tmp_path: Path,
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    monkeypatch.chdir(tmp_path)
    _patch_fast_runtime_run(monkeypatch)
    calls: list[Any] = []

    workflow = VibeWorkflow("wan-custom-assets", WorkflowSource("wan-custom-assets"))
    workflow.nodes["11"] = VibeNode(
        "11",
        "LoadWanVideoT5TextEncoder",
        inputs={"model_name": "umt5-xxl-enc-bf16.safetensors"},
    )
    workflow.nodes["38"] = VibeNode(
        "38",
        "WanVideoVAELoader",
        inputs={"model_name": r"wanvideo\Wan2_1_VAE_bf16.safetensors"},
    )
    workflow.nodes["4"] = VibeNode(
        "4",
        "CLIPVisionLoader",
        inputs={"clip_name": "clip_vision_h.safetensors"},
    )
    workflow.metadata["model_assets"] = [
        {
            "name": "umt5-xxl-enc-bf16.safetensors",
            "url": "https://example.test/umt5-xxl-enc-bf16.safetensors",
            "subdir": "text_encoders",
        },
        {
            "name": "Wan2_1_VAE_bf16.safetensors",
            "url": "https://example.test/Wan2_1_VAE_bf16.safetensors",
            "subdir": "vae/wanvideo",
        },
        {
            "name": "clip_vision_h.safetensors",
            "url": "https://example.test/clip_vision_h.safetensors",
            "subdir": "clip_vision",
        },
    ]

    def fake_download_many(entries):
        calls.append(entries)
        return []

    async def fake_queue(self, api_dict):
        calls.append("queue")
        return {"prompt_id": "prompt-custom-models", "outputs": []}

    import vibecomfy.fetch as fetch_assets

    monkeypatch.setattr(fetch_assets, "download_many", fake_download_many)
    monkeypatch.setattr(fake_comfy, "queue_prompt_api", fake_queue)

    async def run_case() -> None:
        session = EmbeddedSession()
        try:
            await session.run(workflow, ensure_models=True)
        finally:
            await session.stop()

    asyncio.run(run_case())

    assert calls == [workflow.metadata["model_assets"], "queue"]


def test_embedded_run_ensure_models_resolves_cameraman_iclora_override(
    fake_comfy,
    tmp_path: Path,
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    monkeypatch.chdir(tmp_path)
    _patch_fast_runtime_run(monkeypatch)
    calls: list[Any] = []

    workflow = VibeWorkflow("asset-cameraman", WorkflowSource("asset-cameraman"))
    workflow.nodes["5011"] = VibeNode(
        "5011",
        "LTXICLoRALoaderModelOnly",
        inputs={"lora_name": "ltxv/ltx2/LTX2.3-22B_IC-LoRA-Cameraman_v1_10500.safetensors"},
    )

    def fake_download_many(entries):
        calls.append(entries)
        return []

    async def fake_queue(self, api_dict):
        calls.append("queue")
        return {"prompt_id": "prompt-cameraman-models", "outputs": []}

    import vibecomfy.fetch as fetch_assets

    monkeypatch.setattr(fetch_assets, "download_many", fake_download_many)
    monkeypatch.setattr(fake_comfy, "queue_prompt_api", fake_queue)

    async def run_case() -> None:
        session = EmbeddedSession()
        try:
            await session.run(workflow, ensure_models=True)
        finally:
            await session.stop()

    asyncio.run(run_case())

    assert calls == [
        [
            {
                "name": "ltxv/ltx2/LTX2.3-22B_IC-LoRA-Cameraman_v1_10500.safetensors",
                "url": "https://huggingface.co/Cseti/LTX2.3-22B_IC-LoRA-Cameraman_v1/resolve/main/LTX2.3-22B_IC-LoRA-Cameraman_v1_10500.safetensors",
                "subdir": "loras",
            }
        ],
        "queue",
    ]
