"""Tests for ``vibecomfy.comfy_backend`` version-matrix loading and commit reading.

Covers:
- Loading the checked-in ``version_matrix.json`` with all expected fields.
- Missing matrix file → ``FileNotFoundError``.
- Malformed JSON → ``json.JSONDecodeError``.
- Missing required string fields → ``ValueError``.
- Wrong field types → ``TypeError``.
- Memoization behaviour.
- ``read_vendored_commit()`` graceful-degradation paths.
"""
from __future__ import annotations

import json
import os
import tempfile
from importlib import metadata as importlib_metadata
from pathlib import Path

import pytest

from vibecomfy.comfy_backend import (
    ComfyCompatibility,
    ComfyCompatibilityError,
    VersionMatrix,
    check_comfy_compatibility,
    load_version_matrix,
    read_live_comfy_version,
    read_vendored_commit,
    require_comfy_compatibility,
    reset_matrix_cache,
)


# ---------------------------------------------------------------------------
# Helpers
# ---------------------------------------------------------------------------

_VALID_MATRIX: dict = {
    "schema_version": "1.0",
    "supported_comfyui_version": "hiddenswitch-pinned",
    "pinned_comfyui_commit": "f7b38d2eb97207cd834bcc3eb2e8b1d447b96c68",
    "vendor_path": "vendor/ComfyUI",
    "object_info_fingerprint": None,
}


def _write_matrix(path: Path, data: dict) -> None:
    path.write_text(json.dumps(data), encoding="utf-8")


# ---------------------------------------------------------------------------
# Checked-in file
# ---------------------------------------------------------------------------


def test_load_checked_in_version_matrix() -> None:
    """The repo root ``version_matrix.json`` loads with all expected fields."""
    reset_matrix_cache()
    matrix = load_version_matrix()

    assert isinstance(matrix, VersionMatrix)
    assert matrix.schema_version == "1.0"
    assert matrix.supported_comfyui_version == "hiddenswitch-pinned"
    assert matrix.pinned_comfyui_commit == "f7b38d2eb97207cd834bcc3eb2e8b1d447b96c68"
    assert matrix.vendor_path == "vendor/ComfyUI"
    assert matrix.object_info_fingerprint is None


def test_memoization_returns_same_instance() -> None:
    """Repeated calls to ``load_version_matrix()`` return the same object."""
    reset_matrix_cache()
    m1 = load_version_matrix()
    m2 = load_version_matrix()
    assert m1 is m2


# ---------------------------------------------------------------------------
# Missing matrix
# ---------------------------------------------------------------------------


def test_missing_matrix_raises_filenotfounderror(monkeypatch) -> None:
    """If the matrix file does not exist, a ``FileNotFoundError`` is raised."""
    reset_matrix_cache()

    import vibecomfy.comfy_backend as cb

    fake_root = Path(tempfile.mkdtemp())
    monkeypatch.setattr(cb, "_REPO_ROOT", fake_root)
    monkeypatch.setattr(cb, "_find_version_matrix_path", lambda: fake_root / "nonexistent.json")

    with pytest.raises(FileNotFoundError, match="version_matrix.json"):
        load_version_matrix()


# ---------------------------------------------------------------------------
# Malformed JSON
# ---------------------------------------------------------------------------


def test_malformed_json_raises_jsondecodeerror(monkeypatch) -> None:
    """If the matrix file contains malformed JSON, propagate the error."""
    reset_matrix_cache()

    import vibecomfy.comfy_backend as cb

    with tempfile.NamedTemporaryFile(mode="w", suffix=".json", delete=False) as tf:
        tf.write("{not valid json")
        bad_path = tf.name

    try:
        monkeypatch.setattr(cb, "_REPO_ROOT", Path(bad_path).parent)
        monkeypatch.setattr(cb, "_find_version_matrix_path", lambda: Path(bad_path))

        with pytest.raises(json.JSONDecodeError):
            load_version_matrix()
    finally:
        os.unlink(bad_path)


# ---------------------------------------------------------------------------
# Wrong root type (e.g. a JSON array instead of object)
# ---------------------------------------------------------------------------


def test_array_root_raises_typeerror(monkeypatch) -> None:
    """A JSON array at the root raises ``TypeError``, not a cryptic key error."""
    reset_matrix_cache()

    import vibecomfy.comfy_backend as cb

    with tempfile.NamedTemporaryFile(mode="w", suffix=".json", delete=False) as tf:
        json.dump([1, 2, 3], tf)
        array_path = tf.name

    try:
        monkeypatch.setattr(cb, "_REPO_ROOT", Path(array_path).parent)
        monkeypatch.setattr(cb, "_find_version_matrix_path", lambda: Path(array_path))

        with pytest.raises(TypeError, match="JSON object"):
            load_version_matrix()
    finally:
        os.unlink(array_path)


# ---------------------------------------------------------------------------
# Missing required fields
# ---------------------------------------------------------------------------


@pytest.mark.parametrize(
    "drop_key,expected_message",
    [
        ("schema_version", "schema_version"),
        ("supported_comfyui_version", "supported_comfyui_version"),
        ("pinned_comfyui_commit", "pinned_comfyui_commit"),
        ("vendor_path", "vendor_path"),
    ],
)
def test_missing_required_field_raises_valueerror(
    monkeypatch, drop_key: str, expected_message: str
) -> None:
    """Each required string key must be present; missing → ``ValueError``."""
    reset_matrix_cache()

    import vibecomfy.comfy_backend as cb

    data = dict(_VALID_MATRIX)
    del data[drop_key]

    with tempfile.NamedTemporaryFile(mode="w", suffix=".json", delete=False) as tf:
        json.dump(data, tf)
        matrix_path = tf.name

    try:
        monkeypatch.setattr(cb, "_REPO_ROOT", Path(matrix_path).parent)
        monkeypatch.setattr(cb, "_find_version_matrix_path", lambda: Path(matrix_path))

        with pytest.raises(ValueError, match=expected_message):
            load_version_matrix()
    finally:
        os.unlink(matrix_path)


# ---------------------------------------------------------------------------
# Wrong field types
# ---------------------------------------------------------------------------


@pytest.mark.parametrize(
    "field_name,bad_value",
    [
        ("schema_version", 42),
        ("supported_comfyui_version", ["list", "not", "string"]),
        ("pinned_comfyui_commit", {"not": "a string"}),
        ("vendor_path", True),
    ],
)
def test_wrong_field_type_raises_typeerror(
    monkeypatch, field_name: str, bad_value
) -> None:
    """Each required string field must actually be a string; wrong type → ``TypeError``."""
    reset_matrix_cache()

    import vibecomfy.comfy_backend as cb

    data = dict(_VALID_MATRIX)
    data[field_name] = bad_value

    with tempfile.NamedTemporaryFile(mode="w", suffix=".json", delete=False) as tf:
        json.dump(data, tf)
        matrix_path = tf.name

    try:
        monkeypatch.setattr(cb, "_REPO_ROOT", Path(matrix_path).parent)
        monkeypatch.setattr(cb, "_find_version_matrix_path", lambda: Path(matrix_path))

        with pytest.raises(TypeError, match=field_name):
            load_version_matrix()
    finally:
        os.unlink(matrix_path)


def test_bad_fingerprint_type_raises_typeerror(monkeypatch) -> None:
    """``object_info_fingerprint`` must be null or an object; string → ``TypeError``."""
    reset_matrix_cache()

    import vibecomfy.comfy_backend as cb

    data = dict(_VALID_MATRIX)
    data["object_info_fingerprint"] = "not_an_object"

    with tempfile.NamedTemporaryFile(mode="w", suffix=".json", delete=False) as tf:
        json.dump(data, tf)
        matrix_path = tf.name

    try:
        monkeypatch.setattr(cb, "_REPO_ROOT", Path(matrix_path).parent)
        monkeypatch.setattr(cb, "_find_version_matrix_path", lambda: Path(matrix_path))

        with pytest.raises(TypeError, match="object_info_fingerprint"):
            load_version_matrix()
    finally:
        os.unlink(matrix_path)


def test_null_fingerprint_is_accepted(monkeypatch) -> None:
    """``object_info_fingerprint: null`` is valid and stored as ``None``."""
    reset_matrix_cache()

    import vibecomfy.comfy_backend as cb

    data = dict(_VALID_MATRIX)
    data["object_info_fingerprint"] = None

    with tempfile.NamedTemporaryFile(mode="w", suffix=".json", delete=False) as tf:
        json.dump(data, tf)
        matrix_path = tf.name

    try:
        monkeypatch.setattr(cb, "_REPO_ROOT", Path(matrix_path).parent)
        monkeypatch.setattr(cb, "_find_version_matrix_path", lambda: Path(matrix_path))

        matrix = load_version_matrix()
        assert matrix.object_info_fingerprint is None
    finally:
        os.unlink(matrix_path)


def test_dict_fingerprint_is_accepted(monkeypatch) -> None:
    """``object_info_fingerprint: {...}`` is stored as a dict."""
    reset_matrix_cache()

    import vibecomfy.comfy_backend as cb

    data = dict(_VALID_MATRIX)
    data["object_info_fingerprint"] = {"KSampler": "abc123", "CLIPTextEncode": "def456"}

    with tempfile.NamedTemporaryFile(mode="w", suffix=".json", delete=False) as tf:
        json.dump(data, tf)
        matrix_path = tf.name

    try:
        monkeypatch.setattr(cb, "_REPO_ROOT", Path(matrix_path).parent)
        monkeypatch.setattr(cb, "_find_version_matrix_path", lambda: Path(matrix_path))

        matrix = load_version_matrix()
        assert matrix.object_info_fingerprint == {
            "KSampler": "abc123",
            "CLIPTextEncode": "def456",
        }
    finally:
        os.unlink(matrix_path)


# ---------------------------------------------------------------------------
# read_vendored_commit() graceful degradation
# ---------------------------------------------------------------------------


def test_read_vendored_commit_no_vendor_dir(monkeypatch) -> None:
    """When no vendored ComfyUI directory exists, return ``None``."""
    import vibecomfy.comfy_backend as cb

    monkeypatch.setattr(cb, "_find_vendored_comfy_dir", lambda: None)
    assert read_vendored_commit() is None


def test_read_vendored_commit_not_a_git_repo(monkeypatch, tmp_path) -> None:
    """When the directory exists but has no ``.git``, return ``None``."""
    import vibecomfy.comfy_backend as cb

    # Create an empty non-git directory
    fake_vendor = tmp_path / "ComfyUI"
    fake_vendor.mkdir()
    monkeypatch.setattr(cb, "_find_vendored_comfy_dir", lambda: fake_vendor.resolve())

    # git should fail inside a non-repo directory
    result = read_vendored_commit()
    assert result is None


def test_read_vendored_commit_real_repo(monkeypatch, tmp_path) -> None:
    """When a real git repo exists, return its HEAD SHA."""
    import subprocess

    import vibecomfy.comfy_backend as cb

    # Create a real git repo with one commit
    repo = tmp_path / "ComfyUI"
    repo.mkdir()
    subprocess.run(["git", "init"], cwd=str(repo), capture_output=True, check=True)
    subprocess.run(
        ["git", "config", "user.email", "test@test"], cwd=str(repo), capture_output=True
    )
    subprocess.run(
        ["git", "config", "user.name", "Test"], cwd=str(repo), capture_output=True
    )
    (repo / "README.md").write_text("# test")
    subprocess.run(["git", "add", "."], cwd=str(repo), capture_output=True, check=True)
    subprocess.run(
        ["git", "commit", "-m", "init"], cwd=str(repo), capture_output=True, check=True
    )

    expected_sha = subprocess.run(
        ["git", "rev-parse", "HEAD"],
        cwd=str(repo),
        capture_output=True,
        text=True,
        check=True,
    ).stdout.strip()

    monkeypatch.setattr(cb, "_find_vendored_comfy_dir", lambda: repo.resolve())

    result = read_vendored_commit()
    assert result == expected_sha
    assert len(result) == 40  # full SHA


# ---------------------------------------------------------------------------
# Coarse S1 compatibility checker
# ---------------------------------------------------------------------------


def test_check_comfy_compatibility_matches_pinned_commit(monkeypatch) -> None:
    import vibecomfy.comfy_backend as cb

    reset_matrix_cache()
    monkeypatch.setattr(cb, "read_vendored_commit", lambda: _VALID_MATRIX["pinned_comfyui_commit"])
    monkeypatch.setattr(cb, "read_live_comfy_version", lambda: None)

    compatibility = check_comfy_compatibility()

    assert compatibility == ComfyCompatibility(
        ok=True,
        reason_code="ok",
        expected={
            "commit": _VALID_MATRIX["pinned_comfyui_commit"],
            "version": _VALID_MATRIX["supported_comfyui_version"],
        },
        actual={
            "commit": _VALID_MATRIX["pinned_comfyui_commit"],
            "version": None,
        },
        safe_families=[],
    )


def test_check_comfy_compatibility_reports_commit_skew(monkeypatch) -> None:
    import vibecomfy.comfy_backend as cb

    reset_matrix_cache()
    monkeypatch.setattr(cb, "read_vendored_commit", lambda: "deadbeef" * 5)
    monkeypatch.setattr(cb, "read_live_comfy_version", lambda: None)

    compatibility = check_comfy_compatibility()

    assert compatibility.ok is False
    assert compatibility.reason_code == "comfyui_version_skew"
    assert compatibility.expected["commit"] == _VALID_MATRIX["pinned_comfyui_commit"]
    assert compatibility.actual["commit"] == "deadbeef" * 5
    assert compatibility.safe_families == []


def test_check_comfy_compatibility_uses_version_when_vendor_missing(monkeypatch) -> None:
    import vibecomfy.comfy_backend as cb

    reset_matrix_cache()
    monkeypatch.setattr(cb, "read_vendored_commit", lambda: None)
    monkeypatch.setattr(cb, "read_live_comfy_version", lambda: _VALID_MATRIX["supported_comfyui_version"])

    compatibility = check_comfy_compatibility()

    assert compatibility.ok is True
    assert compatibility.reason_code == "ok"
    assert compatibility.actual == {
        "commit": None,
        "version": _VALID_MATRIX["supported_comfyui_version"],
    }


def test_check_comfy_compatibility_missing_matrix_is_typed(monkeypatch) -> None:
    import vibecomfy.comfy_backend as cb

    reset_matrix_cache()
    monkeypatch.setattr(cb, "load_version_matrix", lambda: (_ for _ in ()).throw(FileNotFoundError("missing")))
    monkeypatch.setattr(cb, "read_vendored_commit", lambda: None)
    monkeypatch.setattr(cb, "read_live_comfy_version", lambda: None)

    compatibility = check_comfy_compatibility()

    assert compatibility.ok is False
    assert compatibility.reason_code == "comfyui_version_matrix_missing"
    assert compatibility.expected == {"commit": None, "version": None}
    assert compatibility.safe_families == []


def test_check_comfy_compatibility_invalid_matrix_is_typed(monkeypatch) -> None:
    import vibecomfy.comfy_backend as cb

    reset_matrix_cache()
    monkeypatch.setattr(cb, "load_version_matrix", lambda: (_ for _ in ()).throw(ValueError("bad matrix")))
    monkeypatch.setattr(cb, "read_vendored_commit", lambda: None)
    monkeypatch.setattr(cb, "read_live_comfy_version", lambda: None)

    compatibility = check_comfy_compatibility()

    assert compatibility.ok is False
    assert compatibility.reason_code == "comfyui_version_matrix_invalid"
    assert compatibility.expected == {"commit": None, "version": None}
    assert compatibility.safe_families == []


def test_require_comfy_compatibility_raises_typed_error(monkeypatch) -> None:
    import vibecomfy.comfy_backend as cb

    mismatch = ComfyCompatibility(
        ok=False,
        reason_code="comfyui_version_skew",
        expected={"commit": "expected", "version": "pinned"},
        actual={"commit": "actual", "version": "other"},
        safe_families=[],
    )
    monkeypatch.setattr(cb, "check_comfy_compatibility", lambda: mismatch)

    with pytest.raises(ComfyCompatibilityError, match="comfyui_version_skew") as excinfo:
        require_comfy_compatibility()

    assert excinfo.value.compatibility == mismatch


def test_read_live_comfy_version_prefers_installed_distribution(monkeypatch) -> None:
    import vibecomfy.comfy_backend as cb

    class _FakeMeta:
        @staticmethod
        def version(name: str) -> str:
            if name == "comfyui":
                return "1.2.3"
            raise importlib_metadata.PackageNotFoundError

    monkeypatch.setattr(cb, "importlib_metadata", _FakeMeta)
    assert read_live_comfy_version() == "1.2.3"
