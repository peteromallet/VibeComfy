from __future__ import annotations

import os
import shutil
import subprocess
import sys
from pathlib import Path

import pytest

from vibecomfy.testing import smoke_fixtures as fixtures


def _require_committed_corpus() -> None:
    if not all((fixtures.FIXTURE_ROOT / name).is_file() for name in fixtures.SMOKE_FIXTURES):
        pytest.skip("source checkout has no committed smoke-fixture corpus")


def _has_audio_stream(path: Path) -> bool:
    av = pytest.importorskip("av")
    container = av.open(str(path))
    try:
        return any(stream.type == "audio" for stream in container.streams)
    finally:
        container.close()


def _audio_frame_count(path: Path) -> int:
    av = pytest.importorskip("av")
    container = av.open(str(path))
    try:
        astreams = [s for s in container.streams if s.type == "audio"]
        if not astreams:
            return 0
        total_samples = 0
        for frame in container.decode(astreams[0]):
            total_samples += frame.samples
        return total_samples
    finally:
        container.close()


def test_available_fixtures_includes_committed_assets() -> None:
    _require_committed_corpus()
    available = fixtures.available_fixtures()
    # All expected smoke fixtures must be discovered on disk; this is the
    # contract that downstream callers (matrix bootstrap) rely on.
    for name in fixtures.SMOKE_FIXTURES:
        assert name in available, f"missing committed fixture: {name}"
        assert available[name].is_file()


def test_fixture_root_is_source_checkout_relative() -> None:
    expected = (Path(__file__).resolve().parents[1] / "ready_templates/sources/input").resolve()
    assert fixtures.FIXTURE_ROOT == expected


def test_import_list_and_copy_work_without_a_checkout(
    tmp_path: Path,
) -> None:
    pytest.importorskip("av")
    pytest.importorskip("PIL")
    fake_site = tmp_path / "site-packages"
    shutil.copytree(Path(__file__).resolve().parents[1] / "vibecomfy", fake_site / "vibecomfy")
    neutral_cwd = tmp_path / "neutral-cwd"
    neutral_cwd.mkdir()
    target = tmp_path / "copied-input"
    script = """
from pathlib import Path
from vibecomfy.testing import smoke_fixtures as fixtures

assert fixtures.available_fixtures() == {}
written = fixtures.copy_smoke_fixtures(Path(__import__('sys').argv[1]))
assert {path.name for path in written} == set(fixtures.SMOKE_FIXTURES)
assert all(path.is_file() for path in written)
"""
    env = os.environ.copy()
    env["PYTHONPATH"] = str(fake_site)
    env["PYTHONNOUSERSITE"] = "1"
    result = subprocess.run(
        [sys.executable, "-c", script, str(target)],
        cwd=neutral_cwd,
        env=env,
        capture_output=True,
        text=True,
        check=False,
    )
    assert result.returncode == 0, result.stderr


def test_committed_speech_smoke_is_non_silent() -> None:
    _require_committed_corpus()
    av = pytest.importorskip("av")
    audio_path = fixtures.FIXTURE_ROOT / "speech_smoke.wav"
    assert audio_path.is_file()
    container = av.open(str(audio_path))
    try:
        astream = container.streams.audio[0]
        assert astream.sample_rate >= 8000
        assert astream.channels == 1
        # Decode at least one audio frame to confirm the file is real PCM.
        frames = list(container.decode(astream))
        assert frames, "speech_smoke.wav decoded to zero frames"
        # Sanity-check that the audio is not silence (non-zero samples).
        total_samples = sum(frame.samples for frame in frames)
        assert total_samples > 0
    finally:
        container.close()


@pytest.mark.parametrize("name", list(fixtures.GUIDE_VIDEOS))
def test_committed_guide_videos_have_audio_stream(name: str) -> None:
    _require_committed_corpus()
    pytest.importorskip("av")
    path = fixtures.FIXTURE_ROOT / name
    assert path.is_file(), f"missing committed video: {name}"
    assert _has_audio_stream(path), f"{name} has no audio stream"
    assert _audio_frame_count(path) > 0, f"{name} has zero audio samples"


def test_copy_smoke_fixtures_copies_all(tmp_path: Path) -> None:
    written = fixtures.copy_smoke_fixtures(tmp_path)
    names = {p.name for p in written}
    for expected in fixtures.SMOKE_FIXTURES:
        assert expected in names
        target = tmp_path / expected
        source = fixtures.FIXTURE_ROOT / expected
        assert target.is_file()
        if source.is_file():
            assert target.stat().st_size == source.stat().st_size
        else:
            assert target.stat().st_size > 0


def test_copy_smoke_fixtures_is_idempotent(tmp_path: Path) -> None:
    _require_committed_corpus()
    first = fixtures.copy_smoke_fixtures(tmp_path)
    # Capture mtimes after the first copy.
    mtimes_before = {p: p.stat().st_mtime for p in first}
    # Second call should be a no-op for files whose size+mtime match the source.
    second = fixtures.copy_smoke_fixtures(tmp_path)
    assert {p.name for p in first} == {p.name for p in second}
    for p in second:
        # mtime must be unchanged because the second run skipped the copy.
        assert p.stat().st_mtime == mtimes_before[p], (
            f"copy was not idempotent for {p.name}"
        )


def test_copy_falls_back_when_committed_asset_missing(
    tmp_path: Path,
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    # Point FIXTURE_ROOT at an empty dir so `available_fixtures` returns nothing.
    pytest.importorskip("av")
    pytest.importorskip("PIL")
    empty_root = tmp_path / "empty_fixture_root"
    empty_root.mkdir()
    monkeypatch.setattr(fixtures, "FIXTURE_ROOT", empty_root)
    target = tmp_path / "out"
    written = fixtures.copy_smoke_fixtures(target)
    names = {p.name for p in written}
    # The fallback regenerates a sine WAV plus the four guide videos.
    assert "speech_smoke.wav" in names
    for video in fixtures.GUIDE_VIDEOS:
        assert video in names
        assert (target / video).stat().st_size > 0


def test_regenerate_env_var_forces_fallback(
    tmp_path: Path,
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    pytest.importorskip("av")
    pytest.importorskip("PIL")
    monkeypatch.setenv("VIBECOMFY_FIXTURES_REGENERATE", "1")
    written = fixtures.copy_smoke_fixtures(tmp_path)
    # Regenerated WAV is a 220Hz sine tone; it must still be a valid PCM WAV
    # but its bytes will not match the committed clip.
    audio = tmp_path / "speech_smoke.wav"
    assert audio.is_file()
    committed = fixtures.FIXTURE_ROOT / "speech_smoke.wav"
    if committed.is_file():
        assert audio.stat().st_size != committed.stat().st_size
    names = {p.name for p in written}
    for video in fixtures.GUIDE_VIDEOS:
        assert video in names


def test_regenerate_smoke_fixtures_audio_stream_present(tmp_path: Path) -> None:
    pytest.importorskip("av")
    pytest.importorskip("PIL")
    written = fixtures.regenerate_smoke_fixtures(tmp_path)
    audio = tmp_path / "speech_smoke.wav"
    assert audio.is_file()
    assert audio.stat().st_size > 0
    for video in fixtures.GUIDE_VIDEOS:
        path = tmp_path / video
        assert path.is_file()
        assert _has_audio_stream(path), f"regenerated {video} has no audio stream"
        assert _audio_frame_count(path) > 0


def test_cli_list_smoke(capsys: pytest.CaptureFixture[str]) -> None:
    rc = fixtures._main(["list"])
    assert rc == 0
    captured = capsys.readouterr()
    if all((fixtures.FIXTURE_ROOT / name).is_file() for name in fixtures.SMOKE_FIXTURES):
        assert "speech_smoke.wav" in captured.out
    else:
        assert captured.out == ""


def test_cli_copy_smoke(tmp_path: Path) -> None:
    rc = fixtures._main(["copy", "--target", str(tmp_path)])
    assert rc == 0
    for name in fixtures.SMOKE_FIXTURES:
        assert (tmp_path / name).is_file()
