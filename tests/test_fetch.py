from __future__ import annotations

from contextlib import contextmanager
from pathlib import Path

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


def test_local_path_accepts_ready_template_directory_alias(tmp_path: Path) -> None:
    assert fetch.local_path(
        {"name": "model.safetensors", "directory": "diffusion_models"},
        root=tmp_path,
    ) == tmp_path / "diffusion_models" / "model.safetensors"


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
