# Vision MIME candidate — 9abca467

- Base: `f9478ecf4bef9baf85d8bf6b8f8fafd6a38418a8` (tree `943f8cecfe9c7a19b1458ead6e2392d5b798189f`)
- Tip: `9abca467e88c4a9bffa2adbac46c829663d55ba7`
- Scope: `judge_vision` validates PNG/JPEG magic after raw/base64 normalization, emits `image/png` or `image/jpeg`, and raises `VisionImageError` for invalid/unsupported inputs.
- Tests: `pytest -q tests/intent/test_judge_vision_offline.py tests/intent/test_judge_text_offline.py` (12 passed); Ruff, `py_compile`, and `git diff --check` pass.
- Changed: `vibecomfy/intent/judge.py`, `tests/intent/test_judge_vision_offline.py`
