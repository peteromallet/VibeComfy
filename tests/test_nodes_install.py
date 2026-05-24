from __future__ import annotations

import subprocess
from pathlib import Path
from typing import Sequence

import pytest

from vibecomfy.node_packs_lockfile import LockEntry, read_lockfile
from vibecomfy.node_packs_install import _known_schema_classes, _resolve_node_index_path, install_pack, missing_packs_for_workflow, restore_pack

_VHS_CLASSES = ("VHS_LoadAudio", "VHS_LoadAudioUpload", "VHS_LoadVideo", "VHS_VideoCombine")


def _video_helper_entry(sha: str) -> LockEntry:
    return LockEntry(
        name="ComfyUI-VideoHelperSuite",
        git_commit_sha=sha,
        url="https://github.com/Kosinkadink/ComfyUI-VideoHelperSuite.git",
        class_set=_VHS_CLASSES,
    )
from vibecomfy.workflow import VibeNode, VibeWorkflow, WorkflowSource


class FakeRunner:
    def __init__(
        self,
        *,
        sha: str = "abc123",
        porcelain: str = "",
        fail_clone: bool = False,
        fail_pip: bool = False,
        fail_cm_cli: bool = False,
        cm_cli_checkout_dir: Path | None = None,
    ) -> None:
        self.sha = sha
        self.porcelain = porcelain
        self.fail_clone = fail_clone
        self.fail_pip = fail_pip
        self.fail_cm_cli = fail_cm_cli
        self.cm_cli_checkout_dir = cm_cli_checkout_dir
        self.calls: list[list[str]] = []
        self.cwd_calls: list[str | Path | None] = []

    def __call__(
        self,
        args: Sequence[str],
        *,
        check: bool,
        capture_output: bool,
        text: bool,
        cwd: str | Path | None = None,
    ) -> subprocess.CompletedProcess[str]:
        call = list(args)
        self.calls.append(call)
        self.cwd_calls.append(cwd)
        assert check is True
        assert capture_output is True
        assert text is True
        if call[:2] == ["cm-cli", "install"]:
            if self.fail_cm_cli:
                raise subprocess.CalledProcessError(1, call, stderr="cm-cli failed")
            if self.cm_cli_checkout_dir is not None:
                (self.cm_cli_checkout_dir / ".git").mkdir(parents=True)
            return subprocess.CompletedProcess(call, 0, stdout="installed", stderr="")
        if call[:2] == ["git", "clone"]:
            if self.fail_clone:
                raise subprocess.CalledProcessError(1, call, stderr="clone failed")
            return subprocess.CompletedProcess(call, 0, stdout="", stderr="")
        if call[:4] == ["git", "-C", call[2], "status"]:
            return subprocess.CompletedProcess(call, 0, stdout=self.porcelain, stderr="")
        if call[:4] == ["git", "-C", call[2], "rev-parse"]:
            return subprocess.CompletedProcess(call, 0, stdout=f"{self.sha}\n", stderr="")
        if call[:4] == ["git", "-C", call[2], "fetch"]:
            return subprocess.CompletedProcess(call, 0, stdout="", stderr="")
        if call[:4] == ["git", "-C", call[2], "checkout"]:
            self.sha = call[4]
            return subprocess.CompletedProcess(call, 0, stdout="", stderr="")
        if len(call) >= 4 and call[1:4] == ["-m", "pip", "install"]:
            if self.fail_pip:
                raise subprocess.CalledProcessError(1, call, stderr="pip failed")
            return subprocess.CompletedProcess(call, 0, stdout="", stderr="")
        raise AssertionError(f"unexpected subprocess call: {call!r}")


def test_install_clones_and_upserts_on_success(tmp_path: Path) -> None:
    runner = FakeRunner(sha="feedface")
    lockfile = tmp_path / "custom_nodes.lock"

    result = install_pack(
        name="ComfyUI-VideoHelperSuite",
        install_root=tmp_path / "custom_nodes",
        lockfile_path=lockfile,
        runner=runner,
        cm_cli_resolver=lambda _root, _runner: None,
    )

    assert result.status == "installed"
    assert result.git_commit_sha == "feedface"
    assert runner.calls[0] == [
        "git",
        "clone",
        "https://github.com/Kosinkadink/ComfyUI-VideoHelperSuite.git",
        str(tmp_path / "custom_nodes" / "ComfyUI-VideoHelperSuite"),
    ]
    assert read_lockfile(lockfile) == [
        _video_helper_entry("feedface")
    ]


def test_install_no_lockfile_mutation_on_clone_failure(tmp_path: Path) -> None:
    runner = FakeRunner(fail_clone=True)
    lockfile = tmp_path / "custom_nodes.lock"
    original = "Existing abc https://example.test/existing.git\n"
    lockfile.write_text(original, encoding="utf-8")

    result = install_pack(
        name="ComfyUI-VideoHelperSuite",
        install_root=tmp_path / "custom_nodes",
        lockfile_path=lockfile,
        runner=runner,
        cm_cli_resolver=lambda _root, _runner: None,
    )

    assert result.status == "failed"
    assert "clone failed" in (result.error or "")
    assert lockfile.read_text(encoding="utf-8") == original


def test_install_no_lockfile_mutation_on_pip_failure(tmp_path: Path) -> None:
    runner = FakeRunner(fail_pip=True)
    lockfile = tmp_path / "custom_nodes.lock"
    original = "Existing abc https://example.test/existing.git\n"
    lockfile.write_text(original, encoding="utf-8")

    result = install_pack(
        name="ComfyUI-KJNodes",
        install_root=tmp_path / "custom_nodes",
        lockfile_path=lockfile,
        runner=runner,
        cm_cli_resolver=lambda _root, _runner: None,
    )

    assert result.status == "failed"
    assert "pip failed" in (result.error or "")
    assert lockfile.read_text(encoding="utf-8") == original


def test_install_idempotent_when_clean(tmp_path: Path) -> None:
    install_dir = tmp_path / "custom_nodes" / "ComfyUI-VideoHelperSuite"
    install_dir.mkdir(parents=True)
    runner = FakeRunner(sha="cleanhead", porcelain="")
    lockfile = tmp_path / "custom_nodes.lock"

    result = install_pack(
        name="ComfyUI-VideoHelperSuite",
        install_root=tmp_path / "custom_nodes",
        lockfile_path=lockfile,
        runner=runner,
        cm_cli_resolver=lambda _root, _runner: None,
    )

    assert result.status == "refreshed"
    assert not any(call[:2] == ["git", "clone"] for call in runner.calls)
    assert read_lockfile(lockfile) == [
        _video_helper_entry("cleanhead")
    ]


def test_install_refuses_dirty_without_force(tmp_path: Path) -> None:
    install_dir = tmp_path / "custom_nodes" / "ComfyUI-VideoHelperSuite"
    install_dir.mkdir(parents=True)
    runner = FakeRunner(porcelain=" M nodes.py\n")
    lockfile = tmp_path / "custom_nodes.lock"
    original = "Existing abc https://example.test/existing.git\n"
    lockfile.write_text(original, encoding="utf-8")

    result = install_pack(
        name="ComfyUI-VideoHelperSuite",
        install_root=tmp_path / "custom_nodes",
        lockfile_path=lockfile,
        runner=runner,
        cm_cli_resolver=lambda _root, _runner: None,
    )

    assert result.status == "skipped_dirty"
    assert not any(call[:2] == ["git", "clone"] for call in runner.calls)
    assert lockfile.read_text(encoding="utf-8") == original


def test_install_force_dirty_does_not_clone_and_upserts_head(tmp_path: Path) -> None:
    install_dir = tmp_path / "custom_nodes" / "ComfyUI-VideoHelperSuite"
    install_dir.mkdir(parents=True)
    runner = FakeRunner(sha="dirtyhead", porcelain=" M nodes.py\n")
    lockfile = tmp_path / "custom_nodes.lock"

    result = install_pack(
        name="ComfyUI-VideoHelperSuite",
        force=True,
        install_root=tmp_path / "custom_nodes",
        lockfile_path=lockfile,
        runner=runner,
        cm_cli_resolver=lambda _root, _runner: None,
    )

    assert result.status == "refreshed"
    assert not any(call[:2] == ["git", "clone"] for call in runner.calls)
    assert read_lockfile(lockfile) == [
        _video_helper_entry("dirtyhead")
    ]


def test_install_with_repo_url_infers_name_and_skips_pip_when_uncatalogued(tmp_path: Path) -> None:
    runner = FakeRunner(sha="uncatalogued")
    lockfile = tmp_path / "custom_nodes.lock"

    result = install_pack(
        repo="https://example.test/some-pack.git",
        install_root=tmp_path / "custom_nodes",
        lockfile_path=lockfile,
        runner=runner,
        cm_cli_resolver=lambda _root, _runner: None,
    )

    assert result.name == "some-pack"
    assert result.status == "installed"
    assert runner.calls[0] == [
        "git",
        "clone",
        "https://example.test/some-pack.git",
        str(tmp_path / "custom_nodes" / "some-pack"),
    ]
    assert not any(len(call) >= 4 and call[1:4] == ["-m", "pip", "install"] for call in runner.calls)
    assert read_lockfile(lockfile) == [
        LockEntry(
            name="some-pack",
            git_commit_sha="uncatalogued",
            url="https://example.test/some-pack.git",
        )
    ]


def test_install_registry_pack_fails_when_class_set_cannot_be_derived(tmp_path: Path, monkeypatch) -> None:
    import vibecomfy.node_packs_install as node_packs_install
    from vibecomfy.registry.pack_resolver import PackRef, PackResolution

    monkeypatch.setattr(
        node_packs_install,
        "resolve_pack",
        lambda name: PackResolution(
            query=name,
            query_type="slug",
            ref=PackRef(
                slug=name,
                source="comfy-registry",
                url="https://example.test/registry-pack.git",
            ),
        ),
    )
    runner = FakeRunner(sha="registryhead")
    lockfile = tmp_path / "custom_nodes.lock"

    result = install_pack(
        name="registry-pack",
        install_root=tmp_path / "custom_nodes",
        lockfile_path=lockfile,
        runner=runner,
        cm_cli_resolver=lambda _root, _runner: None,
    )

    assert result.status == "failed"
    assert "failed to derive class_set" in (result.error or "")
    assert read_lockfile(lockfile) == []


def test_install_uses_cm_cli_when_available(tmp_path: Path) -> None:
    install_dir = tmp_path / "custom_nodes" / "ComfyUI-VideoHelperSuite"
    runner = FakeRunner(sha="cmclihead", cm_cli_checkout_dir=install_dir)
    lockfile = tmp_path / "custom_nodes.lock"

    result = install_pack(
        name="ComfyUI-VideoHelperSuite",
        install_root=tmp_path / "custom_nodes",
        lockfile_path=lockfile,
        runner=runner,
        cm_cli_resolver=lambda _root, _runner: ["cm-cli"],
    )

    assert result.status == "installed"
    assert result.git_commit_sha == "cmclihead"
    assert runner.calls[0] == ["cm-cli", "install", "ComfyUI-VideoHelperSuite"]
    assert runner.cwd_calls[0] == tmp_path
    assert not any(call[:2] == ["git", "clone"] for call in runner.calls)
    assert not any(len(call) >= 4 and call[1:4] == ["-m", "pip", "install"] for call in runner.calls)
    assert read_lockfile(lockfile) == [
        _video_helper_entry("cmclihead")
    ]


def test_install_cm_cli_failure_falls_back_to_clone(tmp_path: Path) -> None:
    runner = FakeRunner(fail_cm_cli=True, sha="fallbackhead")
    lockfile = tmp_path / "custom_nodes.lock"

    result = install_pack(
        name="ComfyUI-VideoHelperSuite",
        install_root=tmp_path / "custom_nodes",
        lockfile_path=lockfile,
        runner=runner,
        cm_cli_resolver=lambda _root, _runner: ["cm-cli"],
    )

    assert result.status == "installed"
    assert ["cm-cli", "install", "ComfyUI-VideoHelperSuite"] in runner.calls
    assert [
        "git",
        "clone",
        "https://github.com/Kosinkadink/ComfyUI-VideoHelperSuite.git",
        str(tmp_path / "custom_nodes" / "ComfyUI-VideoHelperSuite"),
    ] in runner.calls
    assert read_lockfile(lockfile) == [
        _video_helper_entry("fallbackhead")
    ]


def test_install_cm_cli_succeeded_but_no_git_falls_back_to_clone(tmp_path: Path) -> None:
    runner = FakeRunner(sha="fallbackhead")
    lockfile = tmp_path / "custom_nodes.lock"

    result = install_pack(
        name="ComfyUI-VideoHelperSuite",
        install_root=tmp_path / "custom_nodes",
        lockfile_path=lockfile,
        runner=runner,
        cm_cli_resolver=lambda _root, _runner: ["cm-cli"],
    )

    assert result.status == "installed"
    assert ["cm-cli", "install", "ComfyUI-VideoHelperSuite"] in runner.calls
    assert [
        "git",
        "clone",
        "https://github.com/Kosinkadink/ComfyUI-VideoHelperSuite.git",
        str(tmp_path / "custom_nodes" / "ComfyUI-VideoHelperSuite"),
    ] in runner.calls
    assert read_lockfile(lockfile) == [
        _video_helper_entry("fallbackhead")
    ]


def test_install_falls_back_to_clone_when_cm_cli_missing(tmp_path: Path) -> None:
    runner = FakeRunner(sha="fallbackhead")
    lockfile = tmp_path / "custom_nodes.lock"

    result = install_pack(
        name="ComfyUI-KJNodes",
        install_root=tmp_path / "custom_nodes",
        lockfile_path=lockfile,
        runner=runner,
        cm_cli_resolver=lambda _root, _runner: None,
    )

    assert result.status == "installed"
    assert runner.calls[0] == [
        "git",
        "clone",
        "https://github.com/kijai/ComfyUI-KJNodes.git",
        str(tmp_path / "custom_nodes" / "ComfyUI-KJNodes"),
    ]
    assert any(len(call) >= 4 and call[1:4] == ["-m", "pip", "install"] for call in runner.calls)
    [entry] = read_lockfile(lockfile)
    assert entry.name == "ComfyUI-KJNodes"
    assert entry.git_commit_sha == "fallbackhead"
    assert entry.url == "https://github.com/kijai/ComfyUI-KJNodes.git"
    assert "ImageResizeKJv2" in entry.class_set
    assert entry.pip_packages == ("matplotlib",)


def test_restore_clones_and_checks_out_pinned_sha(tmp_path: Path) -> None:
    runner = FakeRunner()
    entry = LockEntry("ExamplePack", "pinnedsha", "https://example.test/example.git")

    result = restore_pack(entry, install_root=tmp_path / "custom_nodes", runner=runner)

    assert result.status == "installed"
    assert result.git_commit_sha == "pinnedsha"
    assert runner.calls == [
        ["git", "clone", "https://example.test/example.git", str(tmp_path / "custom_nodes" / "ExamplePack")],
        ["git", "-C", str(tmp_path / "custom_nodes" / "ExamplePack"), "checkout", "pinnedsha"],
    ]


def test_restore_installs_known_pack_pip_dependencies(tmp_path: Path) -> None:
    runner = FakeRunner()
    entry = LockEntry(
        "ComfyUI-WanVideoWrapper",
        "pinnedsha",
        "https://github.com/kijai/ComfyUI-WanVideoWrapper.git",
    )

    result = restore_pack(entry, install_root=tmp_path / "custom_nodes", runner=runner)

    assert result.status == "installed"
    assert [
        "git",
        "clone",
        "https://github.com/kijai/ComfyUI-WanVideoWrapper.git",
        str(tmp_path / "custom_nodes" / "ComfyUI-WanVideoWrapper"),
    ] in runner.calls
    assert any(call[1:4] == ["-m", "pip", "install"] and "onnx" in call for call in runner.calls)


def test_restore_existing_clean_dir_at_correct_sha_is_noop(tmp_path: Path) -> None:
    install_dir = tmp_path / "custom_nodes" / "ExamplePack"
    install_dir.mkdir(parents=True)
    runner = FakeRunner(sha="pinnedsha", porcelain="")
    entry = LockEntry("ExamplePack", "pinnedsha", "https://example.test/example.git")

    result = restore_pack(entry, install_root=tmp_path / "custom_nodes", runner=runner)

    assert result.status == "refreshed"
    assert result.git_commit_sha == "pinnedsha"
    assert not any(call[:4] == ["git", "-C", str(install_dir), "checkout"] for call in runner.calls)


def test_restore_existing_dirty_dir_returns_skipped(tmp_path: Path) -> None:
    install_dir = tmp_path / "custom_nodes" / "ExamplePack"
    install_dir.mkdir(parents=True)
    lockfile = tmp_path / "custom_nodes.lock"
    original = "ExamplePack pinnedsha https://example.test/example.git\n"
    lockfile.write_text(original, encoding="utf-8")
    runner = FakeRunner(porcelain=" M nodes.py\n")
    entry = LockEntry("ExamplePack", "pinnedsha", "https://example.test/example.git")

    result = restore_pack(entry, install_root=tmp_path / "custom_nodes", runner=runner)

    assert result.status == "skipped_dirty"
    assert lockfile.read_text(encoding="utf-8") == original
    assert not any(call[:4] == ["git", "-C", str(install_dir), "checkout"] for call in runner.calls)


def test_missing_packs_for_workflow_returns_resolved_and_unresolved(
    tmp_path: Path,
    monkeypatch,
) -> None:
    (tmp_path / "node_index.json").write_text(
        '[{"class_type": "SaveImage", "pack": "core", "inputs": {}, "outputs": []}]',
        encoding="utf-8",
    )
    monkeypatch.chdir(tmp_path)
    workflow = VibeWorkflow("missing-packs", WorkflowSource("missing-packs"))
    workflow.nodes["1"] = VibeNode("1", "SaveImage")
    workflow.nodes["2"] = VibeNode("2", "Qwen3CustomVoice")
    workflow.nodes["3"] = VibeNode("3", "UnknownCustomNode")

    packs, unresolved = missing_packs_for_workflow(workflow)

    assert [pack.name for pack in packs] == ["ComfyUI-Qwen3-TTS"]
    assert unresolved == ["UnknownCustomNode"]


def test_missing_packs_for_workflow_resolves_sam2_pack(
    tmp_path: Path,
    monkeypatch,
) -> None:
    (tmp_path / "node_index.json").write_text("[]", encoding="utf-8")
    monkeypatch.chdir(tmp_path)
    workflow = VibeWorkflow("sam2", WorkflowSource("sam2"))
    workflow.nodes["1"] = VibeNode("1", "DownloadAndLoadSAM2Model")
    workflow.nodes["2"] = VibeNode("2", "Sam2Segmentation")

    packs, unresolved = missing_packs_for_workflow(workflow)

    assert [pack.name for pack in packs] == ["ComfyUI-segment-anything-2"]
    assert unresolved == []


def test_missing_packs_for_workflow_resolves_wan_animate_preprocess_pack(
    tmp_path: Path,
    monkeypatch,
) -> None:
    (tmp_path / "node_index.json").write_text("[]", encoding="utf-8")
    monkeypatch.chdir(tmp_path)
    workflow = VibeWorkflow("wan-animate-preprocess", WorkflowSource("wan-animate-preprocess"))
    workflow.nodes["1"] = VibeNode("1", "OnnxDetectionModelLoader")
    workflow.nodes["2"] = VibeNode("2", "PoseAndFaceDetection")

    packs, unresolved = missing_packs_for_workflow(workflow)

    assert [pack.name for pack in packs] == ["ComfyUI-WanAnimatePreprocess"]
    assert unresolved == []


def test_missing_packs_for_workflow_resolves_rgthree_pack(
    tmp_path: Path,
    monkeypatch,
) -> None:
    (tmp_path / "node_index.json").write_text("[]", encoding="utf-8")
    monkeypatch.chdir(tmp_path)
    workflow = VibeWorkflow("rgthree", WorkflowSource("rgthree"))
    workflow.nodes["1"] = VibeNode("1", "Power Lora Loader (rgthree)")
    workflow.nodes["2"] = VibeNode("2", "Fast Groups Bypasser (rgthree)")

    packs, unresolved = missing_packs_for_workflow(workflow)

    assert [pack.name for pack in packs] == ["rgthree-comfy"]
    assert unresolved == []


def test_missing_packs_for_workflow_ignores_core_comfy_classes(
    tmp_path: Path,
    monkeypatch,
) -> None:
    (tmp_path / "node_index.json").write_text("[]", encoding="utf-8")
    monkeypatch.chdir(tmp_path)
    workflow = VibeWorkflow("core-classes", WorkflowSource("core-classes"))
    workflow.nodes["1"] = VibeNode("1", "LoadImage")
    workflow.nodes["2"] = VibeNode("2", "SaveImage")
    workflow.nodes["3"] = VibeNode("3", "CLIPLoader")

    packs, unresolved = missing_packs_for_workflow(workflow)

    assert packs == []
    assert unresolved == []


def test_missing_packs_for_workflow_resolves_wanvideo_i2v_helpers(
    tmp_path: Path,
    monkeypatch,
) -> None:
    (tmp_path / "node_index.json").write_text("[]", encoding="utf-8")
    monkeypatch.chdir(tmp_path)
    workflow = VibeWorkflow("wan-i2v", WorkflowSource("wan-i2v"))
    workflow.nodes["1"] = VibeNode("1", "WanVideoLoraSelect")
    workflow.nodes["2"] = VibeNode("2", "CreateCFGScheduleFloatList")
    workflow.nodes["3"] = VibeNode("3", "WanVideoTextEmbedBridge")
    workflow.nodes["4"] = VibeNode("4", "GetImageSizeAndCount")

    packs, unresolved = missing_packs_for_workflow(workflow)

    assert [pack.name for pack in packs] == ["ComfyUI-KJNodes", "ComfyUI-WanVideoWrapper"]
    assert unresolved == []


def test_missing_packs_for_workflow_includes_declared_requirements_even_when_schema_knows_nodes(
    tmp_path: Path,
    monkeypatch,
) -> None:
    (tmp_path / "node_index.json").write_text(
        '[{"class_type": "VHS_VideoCombine", "pack": "ComfyUI-VideoHelperSuite", "inputs": {}, "outputs": []}]',
        encoding="utf-8",
    )
    monkeypatch.chdir(tmp_path)
    workflow = VibeWorkflow("declared-pack", WorkflowSource("declared-pack"))
    workflow.nodes["1"] = VibeNode("1", "VHS_VideoCombine")
    workflow.requirements.custom_nodes.append("ComfyUI-VideoHelperSuite")

    packs, unresolved = missing_packs_for_workflow(workflow)

    assert [pack.name for pack in packs] == ["ComfyUI-VideoHelperSuite"]
    assert unresolved == []


def test_known_schema_classes_falls_back_to_authoring_schema_when_missing(tmp_path: Path) -> None:
    classes = _known_schema_classes(tmp_path / "node_index.json")

    assert "KSampler" in classes
    assert "SaveImage" in classes


def test_resolve_node_index_path_falls_back_to_repo_index(tmp_path: Path, monkeypatch: pytest.MonkeyPatch) -> None:
    monkeypatch.chdir(tmp_path)

    resolved = _resolve_node_index_path(Path("node_index.json"))
    repo_index = Path(__file__).resolve().parents[1] / "node_index.json"

    assert resolved.name == "node_index.json"
    if repo_index.exists():
        assert resolved.exists()
        assert resolved == repo_index
    else:
        assert resolved == Path("node_index.json")


@pytest.mark.parametrize("content", ["{", '{"class_type": "SaveImage"}'])
def test_known_schema_classes_raises_when_invalid(tmp_path: Path, content: str) -> None:
    path = tmp_path / "node_index.json"
    path.write_text(content, encoding="utf-8")

    with pytest.raises(ValueError):
        _known_schema_classes(path)
