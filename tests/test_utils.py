"""Tests for vibecomfy.utils.atomic_write_json."""

from __future__ import annotations

import json
import os
from pathlib import Path
from unittest import mock

import pytest

import vibecomfy.utils as utils
from vibecomfy.utils import atomic_write_json


def test_find_repo_root_falls_back_to_installed_package_root(monkeypatch: pytest.MonkeyPatch) -> None:
    """Installed wheels remain importable when launched outside a checkout."""
    utils.find_repo_root.cache_clear()
    monkeypatch.setattr(Path, "is_file", lambda self: False)
    assert utils.find_repo_root() == Path(utils.__file__).resolve().parent.parent
    utils.find_repo_root.cache_clear()


class TestAtomicWriteJson:
    """Tests for crash-safe atomic JSON writes."""

    def test_valid_json_replacement_produces_correct_content(self, tmp_path: Path) -> None:
        """Writing valid data replaces the target file with correct JSON content."""
        target = tmp_path / "data.json"
        data = {"key": "value", "nested": {"a": 1}}

        result = atomic_write_json(target, data)

        assert result == target
        assert target.exists()
        content = json.loads(target.read_text(encoding="utf-8"))
        assert content == data

        # Verify indent=2, default=str was used
        raw = target.read_text(encoding="utf-8")
        assert "  " in raw  # indentation present

    def test_temp_file_is_cleaned_up_after_success(self, tmp_path: Path) -> None:
        """No .tmp file is left behind after a successful write."""
        target = tmp_path / "settings.json"
        atomic_write_json(target, {"a": 1})

        tmp_files = list(tmp_path.glob("*.tmp"))
        assert len(tmp_files) == 0

    def test_original_file_untouched_on_failure(self, tmp_path: Path) -> None:
        """When fsync raises OSError, the original file is not modified."""
        target = tmp_path / "config.json"
        original_data = {"original": True}
        atomic_write_json(target, original_data)

        original_content = target.read_text(encoding="utf-8")

        # Now try to write new data but inject an fsync failure
        with mock.patch("os.fsync", side_effect=OSError("disk full")):
            with pytest.raises(OSError, match="disk full"):
                atomic_write_json(target, {"new": "data"})

        # Original file content is intact
        assert target.read_text(encoding="utf-8") == original_content
        loaded = json.loads(target.read_text(encoding="utf-8"))
        assert loaded == original_data

    def test_temp_file_cleaned_up_after_injected_failure(self, tmp_path: Path) -> None:
        """Stale .tmp file is removed even after a crash."""
        target = tmp_path / "report.json"
        atomic_write_json(target, {"initial": True})

        with mock.patch("os.fsync", side_effect=OSError("disk full")):
            with pytest.raises(OSError):
                atomic_write_json(target, {"new": "data"})

        # No .tmp remnants
        tmp_files = list(tmp_path.glob("*.tmp"))
        assert len(tmp_files) == 0

    def test_stale_temp_file_removed_before_write(self, tmp_path: Path) -> None:
        """If a .tmp file already exists (simulating prior crash), it is removed."""
        target = tmp_path / "out.json"
        tmp_path_file = target.with_suffix(target.suffix + ".tmp")
        tmp_path_file.write_text("stale", encoding="utf-8")

        atomic_write_json(target, {"fresh": True})

        # The stale .tmp is gone, target has fresh data
        assert not tmp_path_file.exists()
        assert json.loads(target.read_text(encoding="utf-8")) == {"fresh": True}

    def test_creates_parent_directory(self, tmp_path: Path) -> None:
        """Atomic write creates parent directories if they don't exist."""
        target = tmp_path / "nested" / "deep" / "data.json"
        atomic_write_json(target, {"created": True})

        assert target.exists()
        assert json.loads(target.read_text(encoding="utf-8")) == {"created": True}

    def test_handles_non_serializable_objects_via_default_str(self, tmp_path: Path) -> None:
        """default=str fallback handles non-JSON-serializable objects."""
        target = tmp_path / "complex.json"
        data = {"path": Path("/some/path"), "num": 42}

        atomic_write_json(target, data)

        loaded = json.loads(target.read_text(encoding="utf-8"))
        assert loaded["path"] == "/some/path"
        assert loaded["num"] == 42

    def test_returns_path_object(self, tmp_path: Path) -> None:
        """Return value is the final Path."""
        result = atomic_write_json(tmp_path / "x.json", {})
        assert isinstance(result, Path)
        assert result.name == "x.json"
