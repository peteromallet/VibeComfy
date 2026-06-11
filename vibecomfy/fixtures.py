"""Smoke-fixture management for the corpus matrix runs.

This module is the single source of truth for the small input fixtures (audio
clips, guide videos) used by the runpod corpus matrix. Two paths are exposed:

* ``copy_smoke_fixtures(target)`` -- the primary path. Copies the committed
  fixtures from ``workflow_corpus/input/`` into ``target``. Idempotent.
* ``regenerate_smoke_fixtures(target)`` -- the fallback path. Generates
  synthetic fixtures (sine-wave WAV, audio-bearing 256x256 H.264 videos) using
  ``pyav``, ``Pillow`` and the stdlib ``wave`` module. Used only when the
  committed assets are missing or when ``VIBECOMFY_FIXTURES_REGENERATE=1`` is
  set.

A small ``__main__`` is provided so matrix bootstrap shell scripts can call::

    python -m vibecomfy.fixtures copy --target input
    python -m vibecomfy.fixtures regenerate --target input

The module is intentionally light on imports: ``pyav``, ``Pillow`` and ``wave``
are imported lazily inside ``regenerate_smoke_fixtures`` so that ``copy``-only
callers do not pay for them.
"""

from __future__ import annotations

import argparse
import os
import shutil
import sys
from pathlib import Path

from vibecomfy.utils import find_repo_root

__all__ = [
    "FIXTURE_ROOT",
    "SMOKE_FIXTURES",
    "GUIDE_VIDEOS",
    "available_fixtures",
    "copy_smoke_fixtures",
    "regenerate_smoke_fixtures",
]


# Resolve the committed fixture root relative to the repository checkout.
FIXTURE_ROOT: Path = (find_repo_root() / "workflow_corpus" / "input").resolve()


# Names of the committed video fixtures expected to carry an audio stream.
GUIDE_VIDEOS: tuple[str, ...] = (
    "ltx_smoke_guide.mp4",
    "wolf_interpolated.mp4",
    "bubble.mp4",
    "10.mp4",
)


# All committed smoke fixtures the matrix's bootstrap relies on. The image
# assets here mirror what the legacy heredoc generator used to synthesize so
# the fallback path remains a drop-in replacement.
SMOKE_FIXTURES: tuple[str, ...] = (
    "speech_smoke.wav",
    *GUIDE_VIDEOS,
)


def available_fixtures() -> dict[str, Path]:
    """Return a mapping of committed fixture name -> committed path.

    Only entries whose committed source actually exists on disk are included.
    Useful for tests and for callers that want to know what is available
    without triggering a copy.
    """

    out: dict[str, Path] = {}
    for name in SMOKE_FIXTURES:
        candidate = FIXTURE_ROOT / name
        if candidate.is_file():
            out[name] = candidate
    return out


def _files_match(src: Path, dst: Path) -> bool:
    """Cheap idempotency check: same size + same mtime (rounded)."""

    if not dst.is_file():
        return False
    try:
        s = src.stat()
        d = dst.stat()
    except OSError:
        return False
    if s.st_size != d.st_size:
        return False
    # Allow whole-second mtime drift to survive cross-fs copies.
    return int(s.st_mtime) == int(d.st_mtime)


def copy_smoke_fixtures(target_input_dir: Path) -> list[Path]:
    """Copy committed smoke fixtures into ``target_input_dir``.

    Idempotent. Falls back to ``regenerate_smoke_fixtures`` (with a printed
    warning) if any committed fixture is missing, or if the
    ``VIBECOMFY_FIXTURES_REGENERATE=1`` environment variable is set.

    Returns the list of paths that exist in the target directory after the
    operation (in stable order).
    """

    target_input_dir = Path(target_input_dir)
    target_input_dir.mkdir(parents=True, exist_ok=True)

    if os.environ.get("VIBECOMFY_FIXTURES_REGENERATE") == "1":
        print(
            "[vibecomfy.fixtures] VIBECOMFY_FIXTURES_REGENERATE=1; using "
            "synthetic fallback path.",
            file=sys.stderr,
        )
        return regenerate_smoke_fixtures(target_input_dir)

    available = available_fixtures()
    missing = [name for name in SMOKE_FIXTURES if name not in available]
    if missing:
        print(
            f"[vibecomfy.fixtures] missing committed fixtures {missing!r} under "
            f"{FIXTURE_ROOT}; falling back to regenerate path.",
            file=sys.stderr,
        )
        return regenerate_smoke_fixtures(target_input_dir)

    written: list[Path] = []
    for name, src in available.items():
        dst = target_input_dir / name
        if _files_match(src, dst):
            written.append(dst)
            continue
        shutil.copy2(src, dst)
        written.append(dst)
    return written


# ---------------------------------------------------------------------------
# Fallback: synthesize fixtures when committed copies are unavailable.
# ---------------------------------------------------------------------------


def _synthesize_speech_smoke(target: Path) -> None:
    import math
    import wave

    sample_rate = 16000
    duration_seconds = 2
    with wave.open(str(target), "w") as wav:
        wav.setnchannels(1)
        wav.setsampwidth(2)
        wav.setframerate(sample_rate)
        frames = bytearray()
        for index in range(sample_rate * duration_seconds):
            value = int(12000 * math.sin(2 * math.pi * 220 * index / sample_rate))
            frames.extend(value.to_bytes(2, "little", signed=True))
        wav.writeframes(bytes(frames))


def _build_smoke_image():
    from PIL import Image, ImageDraw

    image = Image.new("RGB", (256, 256), (36, 42, 52))
    draw = ImageDraw.Draw(image)
    draw.rectangle((52, 52, 204, 204), outline=(235, 96, 74), width=8)
    draw.ellipse((90, 78, 166, 154), fill=(95, 168, 136))
    draw.line((40, 220, 216, 180), fill=(240, 210, 110), width=6)
    return image


def _synthesize_guide_video(out_path: Path, audio_path: Path) -> None:
    import av
    from PIL import ImageDraw

    image = _build_smoke_image()

    container = av.open(str(out_path), mode="w")
    try:
        vstream = container.add_stream("libx264", rate=8)
        vstream.width = 256
        vstream.height = 256
        vstream.pix_fmt = "yuv420p"

        # Mono AAC audio at 16kHz to match speech_smoke.wav.
        astream = container.add_stream("aac", rate=16000)
        try:
            astream.layout = "mono"
        except Exception:
            # Older pyav releases expose the layout via the codec context only.
            astream.codec_context.layout = "mono"

        for index in range(5):
            frame_image = image.copy()
            frame_draw = ImageDraw.Draw(frame_image)
            frame_draw.rectangle(
                (20 + index * 18, 20, 72 + index * 18, 72),
                fill=(80, 130, 220),
            )
            frame = av.VideoFrame.from_image(frame_image)
            for packet in vstream.encode(frame):
                container.mux(packet)
        for packet in vstream.encode():
            container.mux(packet)

        if audio_path.is_file():
            in_audio = av.open(str(audio_path))
            try:
                in_astream = in_audio.streams.audio[0]
                resampler = av.AudioResampler(format="fltp", layout="mono", rate=16000)
                for frame in in_audio.decode(in_astream):
                    for resampled in resampler.resample(frame):
                        for packet in astream.encode(resampled):
                            container.mux(packet)
            finally:
                in_audio.close()
        for packet in astream.encode():
            container.mux(packet)
    finally:
        container.close()


def regenerate_smoke_fixtures(target_input_dir: Path) -> list[Path]:
    """Generate synthetic smoke fixtures into ``target_input_dir``.

    Creates a sine-wave ``speech_smoke.wav`` and four short H.264 guide videos
    with that audio muxed in. Used as a fallback when committed assets are not
    available (e.g. clean clones that haven't pulled LFS-style assets) and as
    an explicit regenerate path for tests.
    """

    target_input_dir = Path(target_input_dir)
    target_input_dir.mkdir(parents=True, exist_ok=True)

    written: list[Path] = []

    audio_target = target_input_dir / "speech_smoke.wav"
    _synthesize_speech_smoke(audio_target)
    written.append(audio_target)

    for name in GUIDE_VIDEOS:
        out_path = target_input_dir / name
        _synthesize_guide_video(out_path, audio_target)
        written.append(out_path)

    return written


# ---------------------------------------------------------------------------
# CLI entrypoint
# ---------------------------------------------------------------------------


def _main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(prog="python -m vibecomfy.fixtures")
    sub = parser.add_subparsers(dest="cmd", required=True)

    p_copy = sub.add_parser("copy", help="Copy committed smoke fixtures into TARGET (fallback to regenerate).")
    p_copy.add_argument("--target", required=True, type=Path)

    p_regen = sub.add_parser("regenerate", help="Synthesize smoke fixtures into TARGET (no committed-copy step).")
    p_regen.add_argument("--target", required=True, type=Path)

    p_list = sub.add_parser("list", help="List the committed fixtures discovered on disk.")

    args = parser.parse_args(argv)

    if args.cmd == "copy":
        written = copy_smoke_fixtures(args.target)
    elif args.cmd == "regenerate":
        written = regenerate_smoke_fixtures(args.target)
    elif args.cmd == "list":
        for name, path in available_fixtures().items():
            print(f"{name}\t{path}")
        return 0
    else:  # pragma: no cover - argparse enforces choices
        parser.error(f"unknown command {args.cmd!r}")
        return 2

    for path in written:
        print(path)
    return 0


if __name__ == "__main__":
    raise SystemExit(_main())
