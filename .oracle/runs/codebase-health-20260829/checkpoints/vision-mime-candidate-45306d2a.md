# Vision MIME candidate — 45306d2a

- Base: `f9478ecf4bef9baf85d8bf6b8f8fafd6a38418a8` (tree `943f8cecfe9c7a19b1458ead6e2392d5b798189f`)
- Predecessor: `9abca467e88c4a9bffa2adbac46c829663d55ba7`
- Tip: `45306d2af590d8aa9392fe8b750411844fb03251` (tree `177dc0b53c2d15a423e2c90276bc8244046296c3`)
- Scope: `judge_vision` now fully verifies Pillow-decodable PNG/JPEG payloads, requires exact PNG IEND/JPEG EOI termination, emits truthful MIME, and preserves `VisionImageError` for malformed/unsupported input.
- Tests: `pytest -q tests/intent/test_judge_vision_offline.py tests/intent/test_judge_text_offline.py tests/intent/test_edit_correctness.py tests/intent/test_render_diff_structural.py` (29 passed, 1 skipped); Ruff, `py_compile`, and `git diff --check` pass.
- Changed: `vibecomfy/intent/judge.py`, `tests/intent/test_judge_vision_offline.py`
