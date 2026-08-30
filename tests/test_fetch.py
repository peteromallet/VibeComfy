from __future__ import annotations

from concurrent.futures import ThreadPoolExecutor
from contextlib import contextmanager
from pathlib import Path
from threading import Barrier

import pytest

import vibecomfy.fetch as fetch


ENTRY = {
    "name": "model.safetensors",
    "url": "https://example.test/model.safetensors?download=true",
    "subdir": "checkpoints",
}


class FakeResponse:
    def __init__(self, status_code: int = 200, chunks: list[bytes] | None = None) -> None:
        self.status_code = status_code
        self._chunks = chunks or [b"model-bytes"]

    def iter_bytes(self):
        yield from self._chunks


@contextmanager
def fake_stream(response: FakeResponse):
    yield response


def test_models_root_prefers_vibecomfy_env(monkeypatch: pytest.MonkeyPatch, tmp_path: Path) -> None:
    monkeypatch.setenv("VIBECOMFY_MODELS_ROOT", str(tmp_path / "vibe"))
    monkeypatch.setenv("COMFY_MODELS_ROOT", str(tmp_path / "comfy"))

    assert fetch.models_root() == tmp_path / "vibe"


def test_models_root_accepts_directory_extra_model_paths_env(monkeypatch: pytest.MonkeyPatch, tmp_path: Path) -> None:
    monkeypatch.delenv("VIBECOMFY_MODELS_ROOT", raising=False)
    monkeypatch.delenv("COMFY_MODELS_ROOT", raising=False)
    monkeypatch.setenv("COMFYUI_EXTRA_MODEL_PATHS_PATH", str(tmp_path / "shared-models"))

    assert fetch.models_root() == tmp_path / "shared-models"


def test_models_root_ignores_yaml_extra_model_paths_env(monkeypatch: pytest.MonkeyPatch, tmp_path: Path) -> None:
    monkeypatch.delenv("VIBECOMFY_MODELS_ROOT", raising=False)
    monkeypatch.delenv("COMFY_MODELS_ROOT", raising=False)
    monkeypatch.setenv("COMFYUI_EXTRA_MODEL_PATHS_PATH", str(tmp_path / "extra_model_paths.yaml"))

    assert fetch.models_root() != tmp_path / "extra_model_paths.yaml"


def test_models_root_local_library_config_beats_fallback(
    monkeypatch: pytest.MonkeyPatch, tmp_path: Path
) -> None:
    """SET local_library config wins over the ComfyUI/models hardcoded fallback."""
    monkeypatch.delenv("VIBECOMFY_MODELS_ROOT", raising=False)
    monkeypatch.delenv("COMFY_MODELS_ROOT", raising=False)
    monkeypatch.delenv("COMFYUI_EXTRA_MODEL_PATHS_PATH", raising=False)

    config_models = tmp_path / "my-models"
    config_models.mkdir()

    import vibecomfy.local_library as _ll
    monkeypatch.setattr(_ll, "resolved_path", lambda slot, **_kw: config_models)

    assert fetch.models_root() == config_models


def test_models_root_extra_model_paths_dir_beats_local_library_config(
    monkeypatch: pytest.MonkeyPatch, tmp_path: Path
) -> None:
    """COMFYUI_EXTRA_MODEL_PATHS_PATH (as a directory) beats SET local_library config."""
    monkeypatch.delenv("VIBECOMFY_MODELS_ROOT", raising=False)
    monkeypatch.delenv("COMFY_MODELS_ROOT", raising=False)
    env_models = tmp_path / "env-models"
    monkeypatch.setenv("COMFYUI_EXTRA_MODEL_PATHS_PATH", str(env_models))

    config_models = tmp_path / "config-models"
    config_models.mkdir()

    import vibecomfy.local_library as _ll
    monkeypatch.setattr(_ll, "resolved_path", lambda slot, **_kw: config_models)

    assert fetch.models_root() == env_models


def test_download_skips_present_file(monkeypatch: pytest.MonkeyPatch, tmp_path: Path, capsys: pytest.CaptureFixture[str]) -> None:
    monkeypatch.setenv("VIBECOMFY_MODELS_ROOT", str(tmp_path))
    path = tmp_path / "checkpoints" / "model.safetensors"
    path.parent.mkdir()
    path.write_bytes(b"present")

    assert fetch.download(ENTRY) == path
    assert capsys.readouterr().out == "skipped model.safetensors\n"


def test_download_verifies_present_file_sha256(monkeypatch: pytest.MonkeyPatch, tmp_path: Path) -> None:
    monkeypatch.setenv("VIBECOMFY_MODELS_ROOT", str(tmp_path))
    path = tmp_path / "checkpoints" / "model.safetensors"
    path.parent.mkdir()
    path.write_bytes(b"present")

    with pytest.raises(RuntimeError, match="sha256 mismatch for model.safetensors"):
        fetch.download({**ENTRY, "sha256": "0" * 64})


def test_gated_present_file_skips_sha256_verification(monkeypatch: pytest.MonkeyPatch, tmp_path: Path) -> None:
    monkeypatch.setenv("VIBECOMFY_MODELS_ROOT", str(tmp_path))
    path = tmp_path / "checkpoints" / "model.safetensors"
    path.parent.mkdir()
    path.write_bytes(b"present")

    fetch.verify({**ENTRY, "sha256": "0" * 64, "gated": True})


def test_download_writes_tmp_then_renames(monkeypatch: pytest.MonkeyPatch, tmp_path: Path) -> None:
    monkeypatch.setenv("VIBECOMFY_MODELS_ROOT", str(tmp_path))
    requested: dict[str, object] = {}

    def stream(method: str, url: str, **kwargs):
        requested.update({"method": method, "url": url, **kwargs})
        return fake_stream(FakeResponse(chunks=[b"abc", b"", b"123"]))

    monkeypatch.setattr(fetch.httpx, "stream", stream)

    path = fetch.download(ENTRY)

    assert path == tmp_path / "checkpoints" / "model.safetensors"
    assert path.read_bytes() == b"abc123"
    assert not (tmp_path / "checkpoints" / "model.safetensors.tmp").exists()
    assert requested["method"] == "GET"
    assert requested["url"] == "https://example.test/model.safetensors"
    assert requested["follow_redirects"] is True


def test_download_verifies_downloaded_file_sha256(monkeypatch: pytest.MonkeyPatch, tmp_path: Path) -> None:
    monkeypatch.setenv("VIBECOMFY_MODELS_ROOT", str(tmp_path))
    monkeypatch.setattr(fetch.httpx, "stream", lambda *_args, **_kwargs: fake_stream(FakeResponse(chunks=[b"abc"])))

    with pytest.raises(RuntimeError, match="sha256 mismatch for model.safetensors"):
        fetch.download({**ENTRY, "sha256": "0" * 64})

    assert (tmp_path / "checkpoints" / "model.safetensors").read_bytes() == b"abc"


def test_download_supports_repo_relative_target_path(monkeypatch: pytest.MonkeyPatch, tmp_path: Path) -> None:
    monkeypatch.setenv("VIBECOMFY_MODELS_ROOT", str(tmp_path / "models"))
    monkeypatch.setattr(fetch.httpx, "stream", lambda *_args, **_kwargs: fake_stream(FakeResponse(chunks=[b"aux"])))

    path = fetch.download(
        {
            **ENTRY,
            "name": "yolox_l.onnx",
            "target_path": "custom_nodes/comfyui_controlnet_aux/ckpts/yzd-v/DWPose/yolox_l.onnx",
        }
    )

    assert path == tmp_path / "custom_nodes/comfyui_controlnet_aux/ckpts/yzd-v/DWPose/yolox_l.onnx"
    assert path.read_bytes() == b"aux"


def test_download_supports_nested_destinations_and_relative_cwd_binding(
    monkeypatch: pytest.MonkeyPatch, tmp_path: Path
) -> None:
    cwd_a = tmp_path / "cwd-a"
    cwd_b = tmp_path / "cwd-b"
    cwd_a.mkdir()
    cwd_b.mkdir()
    monkeypatch.chdir(cwd_a)

    class ChdirClient:
        def stream(self, *_args, **_kwargs):
            monkeypatch.chdir(cwd_b)
            return fake_stream(FakeResponse())

    path = fetch.download(
        {
            **ENTRY,
            "subdir": "diffusion_models/WanVideo",
            "name": "2_2/model.safetensors",
        },
        root=Path("models"),
        client=ChdirClient(),
    )
    expected = cwd_a / "models/diffusion_models/WanVideo/2_2/model.safetensors"
    assert path == expected
    assert path.is_absolute() and path.read_bytes() == b"model-bytes"
    assert not (cwd_b / "models").exists()


@pytest.mark.parametrize("field", ["target_path", "subdir", "name"])
def test_download_rejects_absolute_destination_fields_before_network(
    field: str, monkeypatch: pytest.MonkeyPatch, tmp_path: Path
) -> None:
    outside = tmp_path / "outside" / "model.safetensors"
    entry = {**ENTRY, field: str(outside)}

    def unexpected_stream(*_args, **_kwargs):
        raise AssertionError("unsafe destination must fail before opening network stream")

    monkeypatch.setattr(fetch.httpx, "stream", unexpected_stream)
    with pytest.raises(ValueError, match=rf"model asset {field} must be a relative path"):
        fetch.download(entry, root=tmp_path / "checkout/models")
    assert not outside.exists()


@pytest.mark.parametrize(
    ("field", "value"),
    [
        ("target_path", "../outside/model.safetensors"),
        ("subdir", "../../outside"),
        ("name", "../../../outside/model.safetensors"),
        ("target_path", r"custom_nodes\\pack\\model.safetensors"),
        ("subdir", "checkpoints/"),
        ("target_path", "custom_nodes/pack/."),
        ("subdir", "checkpoints/."),
        ("name", "nested/."),
    ],
)
def test_download_rejects_traversal_ambiguous_and_empty_terminal_fields(
    field: str, value: str, monkeypatch: pytest.MonkeyPatch, tmp_path: Path
) -> None:
    entry = {**ENTRY, field: value}
    monkeypatch.setattr(
        fetch.httpx,
        "stream",
        lambda *_args, **_kwargs: (_ for _ in ()).throw(
            AssertionError("unsafe destination must fail before opening network stream")
        ),
    )
    with pytest.raises(ValueError, match=rf"model asset {field} must be a relative path"):
        fetch.download(entry, root=tmp_path / "checkout/models")


@pytest.mark.parametrize("target_path", [False, True])
def test_download_rejects_preexisting_symlink_parent_escape_before_network(
    target_path: bool, monkeypatch: pytest.MonkeyPatch, tmp_path: Path
) -> None:
    checkout = tmp_path / "checkout"
    models = checkout / "models"
    outside = tmp_path / "outside"
    models.mkdir(parents=True)
    outside.mkdir()
    if target_path:
        (checkout / "custom_nodes").symlink_to(outside, target_is_directory=True)
        entry = {**ENTRY, "target_path": "custom_nodes/pack/model.safetensors"}
    else:
        (models / "checkpoints").symlink_to(outside, target_is_directory=True)
        entry = ENTRY

    monkeypatch.setattr(
        fetch.httpx,
        "stream",
        lambda *_args, **_kwargs: (_ for _ in ()).throw(
            AssertionError("unsafe destination must fail before opening network stream")
        ),
    )
    with pytest.raises(ValueError, match="resolves outside its authorized root"):
        fetch.download(entry, root=models)
    assert list(outside.iterdir()) == []


def test_local_path_canonicalizes_in_root_symlink_alias(tmp_path: Path) -> None:
    models = tmp_path / "models"
    actual = models / "checkpoints"
    actual.mkdir(parents=True)
    (models / "alias").symlink_to(actual, target_is_directory=True)

    path = fetch.local_path(
        {**ENTRY, "subdir": "alias", "name": "model.safetensors"}, root=models
    )
    assert path == actual / "model.safetensors"
    assert not path.is_symlink()


def test_download_force_replaces_existing_canonical_destination(
    monkeypatch: pytest.MonkeyPatch, tmp_path: Path
) -> None:
    models = tmp_path / "models"
    destination = models / "checkpoints/model.safetensors"
    destination.parent.mkdir(parents=True)
    destination.write_bytes(b"old")
    monkeypatch.setattr(
        fetch.httpx,
        "stream",
        lambda *_args, **_kwargs: fake_stream(FakeResponse(chunks=[b"new"])),
    )

    assert fetch.download(ENTRY, root=models, force=True) == destination
    assert destination.read_bytes() == b"new"


@pytest.mark.parametrize("mutation_stage", ["stream", "enter", "iter_bytes"])
def test_download_rechecks_destination_after_parent_symlink_mutation(
    mutation_stage: str, tmp_path: Path
) -> None:
    models = tmp_path / "models"
    parent = models / "checkpoints"
    detached = tmp_path / "detached-checkpoints"
    outside = tmp_path / "outside"
    parent.mkdir(parents=True)
    outside.mkdir()
    swapped = False

    def swap_parent() -> None:
        nonlocal swapped
        if swapped:
            return
        parent.rename(detached)
        parent.symlink_to(outside, target_is_directory=True)
        swapped = True

    class MutatingResponse(FakeResponse):
        def iter_bytes(self):
            yield b"partial"
            if mutation_stage == "iter_bytes":
                swap_parent()
            yield b"remaining"

    @contextmanager
    def stream_context():
        if mutation_stage == "enter":
            swap_parent()
        yield MutatingResponse()

    class MutatingClient:
        def stream(self, *_args, **_kwargs):
            if mutation_stage == "stream":
                swap_parent()
            return stream_context()

    with pytest.raises(ValueError, match="destination changed after authorization"):
        fetch.download(ENTRY, root=models, client=MutatingClient())
    assert list(outside.iterdir()) == []


def test_download_does_not_follow_preexisting_destination_tmp_symlink(
    monkeypatch: pytest.MonkeyPatch, tmp_path: Path
) -> None:
    models = tmp_path / "models"
    destination = models / "checkpoints/model.safetensors"
    destination.parent.mkdir(parents=True)
    outside = tmp_path / "outside.bin"
    outside.write_bytes(b"do-not-overwrite")
    tmp = destination.with_suffix(".safetensors.tmp")
    tmp.symlink_to(outside)
    monkeypatch.setattr(fetch.httpx, "stream", lambda *_args, **_kwargs: fake_stream(FakeResponse()))

    path = fetch.download(ENTRY, root=models)
    assert path == destination and destination.read_bytes() == b"model-bytes"
    assert outside.read_bytes() == b"do-not-overwrite" and tmp.is_symlink()


def test_concurrent_downloads_use_invocation_owned_temp_files(tmp_path: Path) -> None:
    models = tmp_path / "models"
    barrier = Barrier(2)

    class ConcurrentResponse(FakeResponse):
        def iter_bytes(self):
            barrier.wait(timeout=5)
            yield b"same-model-bytes"

    class ConcurrentClient:
        def stream(self, *_args, **_kwargs):
            return fake_stream(ConcurrentResponse())

    with ThreadPoolExecutor(max_workers=2) as pool:
        futures = [
            pool.submit(fetch.download, ENTRY, root=models, client=ConcurrentClient())
            for _ in range(2)
        ]
        paths = [future.result(timeout=10) for future in futures]

    destination = models / "checkpoints/model.safetensors"
    assert paths == [destination, destination]
    assert destination.read_bytes() == b"same-model-bytes"
    assert list(destination.parent.glob(".vibecomfy-download-*.tmp")) == []


def test_local_path_accepts_ready_template_directory_alias(tmp_path: Path) -> None:
    assert fetch.local_path(
        {"name": "model.safetensors", "directory": "diffusion_models"},
        root=tmp_path,
    ) == tmp_path / "diffusion_models" / "model.safetensors"


@pytest.mark.parametrize("subdir", ["", None, 0])
def test_local_path_rejects_explicit_malformed_subdir_without_directory_fallback(
    subdir: object, tmp_path: Path
) -> None:
    with pytest.raises((KeyError, ValueError), match="model asset"):
        fetch.local_path(
            {
                "name": "model.safetensors",
                "subdir": subdir,
                "directory": "vae",
            },
            root=tmp_path,
        )


def test_download_removes_tmp_after_stream_failure(monkeypatch: pytest.MonkeyPatch, tmp_path: Path) -> None:
    monkeypatch.setenv("VIBECOMFY_MODELS_ROOT", str(tmp_path))

    class BrokenResponse(FakeResponse):
        def iter_bytes(self):
            yield b"partial"
            raise RuntimeError("stream failed")

    monkeypatch.setattr(fetch.httpx, "stream", lambda *_args, **_kwargs: fake_stream(BrokenResponse()))

    with pytest.raises(RuntimeError, match="stream failed"):
        fetch.download(ENTRY)

    assert not (tmp_path / "checkpoints" / "model.safetensors.tmp").exists()
    assert not (tmp_path / "checkpoints" / "model.safetensors").exists()


def test_download_uses_hf_token_header_and_omits_empty_header(monkeypatch: pytest.MonkeyPatch, tmp_path: Path) -> None:
    monkeypatch.setenv("VIBECOMFY_MODELS_ROOT", str(tmp_path))
    seen_headers: list[dict[str, str]] = []

    def stream(_method: str, _url: str, **kwargs):
        seen_headers.append(kwargs["headers"])
        return fake_stream(FakeResponse())

    monkeypatch.setattr(fetch.httpx, "stream", stream)
    monkeypatch.delenv("HF_TOKEN", raising=False)
    fetch.download({**ENTRY, "name": "without-token.safetensors"})
    monkeypatch.setenv("HF_TOKEN", "secret-token")
    fetch.download({**ENTRY, "name": "with-token.safetensors"})

    assert seen_headers == [{}, {"Authorization": "Bearer secret-token"}]


@pytest.mark.parametrize(
    ("status_code", "error_type", "message"),
    [
        (401, PermissionError, "License-gated download blocked for https://example.test/model.safetensors"),
        (403, PermissionError, "License-gated download blocked for https://example.test/model.safetensors"),
        (404, FileNotFoundError, "Asset not found at https://example.test/model.safetensors"),
    ],
)
def test_download_maps_http_errors(
    monkeypatch: pytest.MonkeyPatch,
    tmp_path: Path,
    status_code: int,
    error_type: type[Exception],
    message: str,
) -> None:
    monkeypatch.setenv("VIBECOMFY_MODELS_ROOT", str(tmp_path))
    monkeypatch.setattr(fetch.httpx, "stream", lambda *_args, **_kwargs: fake_stream(FakeResponse(status_code=status_code)))

    with pytest.raises(error_type, match=message):
        fetch.download(ENTRY)


def test_download_routes_supplied_client_without_touching_httpx_stream(
    monkeypatch: pytest.MonkeyPatch,
    tmp_path: Path,
) -> None:
    monkeypatch.setenv("VIBECOMFY_MODELS_ROOT", str(tmp_path))

    def unexpected_httpx_stream(*_args, **_kwargs):
        raise AssertionError("httpx.stream should not be used when client is supplied")

    class FakeClient:
        def __init__(self) -> None:
            self.calls: list[tuple[str, str, dict]] = []

        def stream(self, method: str, url: str, **kwargs):
            self.calls.append((method, url, kwargs))
            return fake_stream(FakeResponse(chunks=[b"from-client"]))

    monkeypatch.setattr(fetch.httpx, "stream", unexpected_httpx_stream)
    client = FakeClient()

    path = fetch.download(ENTRY, client=client)

    assert path.read_bytes() == b"from-client"
    assert client.calls[0][0] == "GET"
    assert client.calls[0][1] == "https://example.test/model.safetensors"


def test_download_many_continues_past_failure_and_raises_aggregate(
    monkeypatch: pytest.MonkeyPatch,
    tmp_path: Path,
    capsys: pytest.CaptureFixture[str],
) -> None:
    monkeypatch.setenv("VIBECOMFY_MODELS_ROOT", str(tmp_path))

    def stream(_method: str, url: str, **_kwargs):
        if "missing" in url:
            return fake_stream(FakeResponse(status_code=404))
        return fake_stream(FakeResponse(chunks=[b"ok"]))

    entries = [
        {**ENTRY, "name": "first.safetensors", "url": "https://example.test/first.safetensors"},
        {**ENTRY, "name": "missing.safetensors", "url": "https://example.test/missing.safetensors"},
        {**ENTRY, "name": "second.safetensors", "url": "https://example.test/second.safetensors"},
    ]
    monkeypatch.setattr(fetch.httpx, "stream", stream)

    with pytest.raises(RuntimeError, match="1 failures"):
        fetch.download_many(entries)

    out = capsys.readouterr().out
    assert "downloaded first.safetensors ->" in out
    assert "failed missing.safetensors: Asset not found at https://example.test/missing.safetensors" in out
    assert "downloaded second.safetensors ->" in out
    assert (tmp_path / "checkpoints" / "first.safetensors").read_bytes() == b"ok"
    assert (tmp_path / "checkpoints" / "second.safetensors").read_bytes() == b"ok"


def test_download_many_aggregates_malformed_destination_metadata(
    monkeypatch: pytest.MonkeyPatch, tmp_path: Path
) -> None:
    monkeypatch.setenv("VIBECOMFY_MODELS_ROOT", str(tmp_path / "models"))
    entries = [
        {**ENTRY, "name": "good.safetensors"},
        {**ENTRY, "name": "bad.safetensors", "target_path": "../outside.bin"},
    ]
    monkeypatch.setattr(fetch.httpx, "stream", lambda *_args, **_kwargs: fake_stream(FakeResponse()))

    with pytest.raises(RuntimeError, match="1 failures"):
        fetch.download_many(entries)
    assert (tmp_path / "models/checkpoints/good.safetensors").read_bytes() == b"model-bytes"
    assert not (tmp_path / "outside.bin").exists()
