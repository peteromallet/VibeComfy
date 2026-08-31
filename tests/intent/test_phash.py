"""Offline pHash calibration tests — no GPU, no network.

Fixture generation script (run once to regenerate the PNGs in
tests/intent/fixtures/_phash_samples/):

    import os, random
    from PIL import Image, ImageDraw

    random.seed(42)
    outdir = "tests/intent/fixtures/_phash_samples"

    # --- 5 near-identical pairs ---

    # near_01: same circle, slightly different fill (dark blue vs slightly lighter blue)
    for idx, fill in enumerate([(0, 0, 180), (0, 0, 185)]):
        img = Image.new("RGB", (64, 64), (255, 255, 255))
        d = ImageDraw.Draw(img)
        d.ellipse([12, 12, 52, 52], fill=fill, outline=(0, 0, 0))
        img.save(f"{outdir}/near_01_{chr(97+idx)}.png")

    # near_02: same rectangle, 1px diagonal shift
    for idx, offset in enumerate([0, 1]):
        img = Image.new("RGB", (64, 64), (255, 255, 255))
        d = ImageDraw.Draw(img)
        d.rectangle([8 + offset, 8 + offset, 56 + offset, 56 + offset],
                     fill=(200, 50, 50), outline=(0, 0, 0))
        img.save(f"{outdir}/near_02_{chr(97+idx)}.png")

    # near_03: same vertical lines, 1px length difference
    for idx, dy in enumerate([0, 1]):
        img = Image.new("RGB", (64, 64), (255, 255, 255))
        d = ImageDraw.Draw(img)
        for i in range(3):
            x = 10 + i * 20
            d.line([x, 10, x, 54 + dy], fill=(0, 120, 0), width=3)
        img.save(f"{outdir}/near_03_{chr(97+idx)}.png")

    # near_04: same polygon, 1px different vertex
    for idx, x2_offset in enumerate([0, 1]):
        img = Image.new("RGB", (64, 64), (255, 255, 255))
        d = ImageDraw.Draw(img)
        d.polygon([(16, 10), (48 + x2_offset, 10), (40, 40), (24, 40)],
                   fill=(150, 100, 200), outline=(0, 0, 0))
        img.save(f"{outdir}/near_04_{chr(97+idx)}.png")

    # near_05: same filled arc, slightly different end angle (270 vs 275 degrees)
    for idx, end_angle in enumerate([270, 275]):
        img = Image.new("RGB", (64, 64), (255, 255, 255))
        d = ImageDraw.Draw(img)
        d.pieslice([10, 10, 54, 54], start=0, end=end_angle,
                    fill=(255, 150, 30), outline=(0, 0, 0))
        img.save(f"{outdir}/near_05_{chr(97+idx)}.png")

    # --- 5 clearly-different pairs ---

    # diff_01: circle vs square
    img = Image.new("RGB", (64, 64), (255, 255, 255))
    ImageDraw.Draw(img).ellipse([12, 12, 52, 52], fill=(0, 100, 200))
    img.save(f"{outdir}/diff_01_a.png")
    img = Image.new("RGB", (64, 64), (255, 255, 255))
    ImageDraw.Draw(img).rectangle([12, 12, 52, 52], fill=(200, 50, 50))
    img.save(f"{outdir}/diff_01_b.png")

    # diff_02: filled green circle on white vs yellow square on black
    img = Image.new("RGB", (64, 64), (255, 255, 255))
    ImageDraw.Draw(img).ellipse([8, 8, 56, 56], fill=(80, 180, 80))
    img.save(f"{outdir}/diff_02_a.png")
    img = Image.new("RGB", (64, 64), (0, 0, 0))
    ImageDraw.Draw(img).rectangle([20, 20, 44, 44], fill=(255, 255, 0))
    img.save(f"{outdir}/diff_02_b.png")

    # diff_03: horizontal lines vs vertical lines
    img = Image.new("RGB", (64, 64), (255, 255, 255))
    d = ImageDraw.Draw(img)
    for y in range(8, 56, 8):
        d.line([8, y, 56, y], fill=(100, 50, 150), width=2)
    img.save(f"{outdir}/diff_03_a.png")
    img = Image.new("RGB", (64, 64), (255, 255, 255))
    d = ImageDraw.Draw(img)
    for x in range(8, 56, 8):
        d.line([x, 8, x, 56], fill=(200, 150, 50), width=2)
    img.save(f"{outdir}/diff_03_b.png")

    # diff_04: red triangle vs blue checkerboard
    img = Image.new("RGB", (64, 64), (255, 255, 255))
    ImageDraw.Draw(img).polygon([(32, 6), (6, 54), (58, 54)], fill=(220, 30, 30))
    img.save(f"{outdir}/diff_04_a.png")
    img = Image.new("RGB", (64, 64), (255, 255, 255))
    d = ImageDraw.Draw(img)
    for row in range(8):
        for col in range(8):
            if (row + col) % 2 == 0:
                d.rectangle([col * 8, row * 8, (col + 1) * 8, (row + 1) * 8],
                             fill=(30, 80, 200))
    img.save(f"{outdir}/diff_04_b.png")

    # diff_05: thick diagonal vs scattered dots
    img = Image.new("RGB", (64, 64), (255, 255, 255))
    ImageDraw.Draw(img).line([4, 4, 60, 60], fill=(0, 0, 0), width=8)
    img.save(f"{outdir}/diff_05_a.png")
    img = Image.new("RGB", (64, 64), (255, 255, 255))
    d = ImageDraw.Draw(img)
    random.seed(123)
    for _ in range(40):
        x, y = random.randint(4, 60), random.randint(4, 60)
        r = random.randint(2, 5)
        d.ellipse([x - r, y - r, x + r, y + r],
                   fill=(random.randint(0, 255), random.randint(0, 255), random.randint(0, 255)))
    img.save(f"{outdir}/diff_05_b.png")
"""

from __future__ import annotations

import pytest
from pathlib import Path

pytest.importorskip(
    "PIL",
    reason="pHash calibration tests require the optional [intent] Pillow dependency",
)
from vibecomfy.intent.render_diff import phash_distance, calibrate_threshold

FIXTURE_DIR = Path(__file__).parent / "fixtures" / "_phash_samples"

NEAR_PAIRS = [(f"near_{i:02d}_a.png", f"near_{i:02d}_b.png") for i in range(1, 6)]
DIFF_PAIRS = [(f"diff_{i:02d}_a.png", f"diff_{i:02d}_b.png") for i in range(1, 6)]


@pytest.mark.intent_ci
class TestPhashCalibration:
    """Verify calibrate_threshold separates near-identical from clearly-different pairs."""

    def test_all_fixtures_exist(self) -> None:
        """All 20 fixture files are present on disk."""
        for a_name, b_name in NEAR_PAIRS + DIFF_PAIRS:
            assert (FIXTURE_DIR / a_name).is_file(), f"Missing fixture: {a_name}"
            assert (FIXTURE_DIR / b_name).is_file(), f"Missing fixture: {b_name}"

    def test_calibrate_threshold_separates_pairs(self) -> None:
        """calibrate_threshold finds a T where max(same) <= T < min(diff)."""
        same_dists: list[int] = []
        for a_name, b_name in NEAR_PAIRS:
            d = phash_distance(FIXTURE_DIR / a_name, FIXTURE_DIR / b_name)
            same_dists.append(d)

        diff_dists: list[int] = []
        for a_name, b_name in DIFF_PAIRS:
            d = phash_distance(FIXTURE_DIR / a_name, FIXTURE_DIR / b_name)
            diff_dists.append(d)

        threshold = calibrate_threshold(same_dists, diff_dists)
        max_same = max(same_dists)
        min_diff = min(diff_dists)

        # The threshold must cleanly separate the two sets
        assert max_same <= threshold < min_diff, (
            f"calibrate_threshold returned {threshold} but "
            f"max(same)={max_same}, min(diff)={min_diff}"
        )

    def test_phash_distance_identical_file_zero(self) -> None:
        """phash_distance returns 0 when both paths point to the same file."""
        # Use the first near-pair "a" image — any fixture works
        path = FIXTURE_DIR / "near_01_a.png"
        assert phash_distance(path, path) == 0, (
            "phash_distance on identical file should be 0"
        )

    def test_every_near_pair_below_every_diff_pair(self) -> None:
        """Every near-identical pair distance is strictly less than every diff-pair distance."""
        near_dists = [
            phash_distance(FIXTURE_DIR / a, FIXTURE_DIR / b)
            for a, b in NEAR_PAIRS
        ]
        diff_dists = [
            phash_distance(FIXTURE_DIR / a, FIXTURE_DIR / b)
            for a, b in DIFF_PAIRS
        ]

        for nd in near_dists:
            for dd in diff_dists:
                assert nd < dd, (
                    f"Near-pair distance {nd} is not less than diff-pair distance {dd}"
                )
