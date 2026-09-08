# Independent review — vision MIME candidate `9abca467`

## Verdict: REWORK

### Blocker

`_decode_vision_image` only checks a prefix (`judge.py:59-63`), so it accepts
malformed and truncated data as if it were an image.  In bounded probes, all of
the following were accepted and sent to the public `judge_vision` request path:

* PNG signature only (`89 50 4e 47 0d 0a 1a 0a`)
* JPEG signature only (`ff d8 ff`)
* a valid Pillow PNG/JPEG truncated by one byte
* a signature followed by arbitrary bytes (`...not-an-image`)

That contradicts the `VisionImageError` contract/docstring (“malformed”) and
the helper docstring’s “truthful MIME type” claim.  The added tests use
`PNG = signature + b"fixture"` and `JPEG = signature + b"fixture"`, so they
prove media-type routing and base64 normalization but explicitly do not prove
that malformed/truncated/polyglot inputs are rejected.  Add genuine PNG/JPEG
fixtures and negative cases, then validate the full format (or a deliberately
documented minimum structure) before emitting a MIME type.  Preserve the
existing `VisionImageError`/`ValueError` failure surface.

### Contract review

* Raw `bytes` and `bytearray` are normalized correctly; standard base64
  strings are decoded strictly and re-encoded canonically.
* PNG and JPEG magic prefixes route to `image/png` and `image/jpeg` correctly
  for well-formed inputs.  No explicit MIME argument exists in this API.
* Data-URI strings (`data:image/png;base64,...`) and whitespace-wrapped base64
  are rejected.  This is acceptable only because the documented public input
  contract is raw bytes or a base64 string; if data URIs are intended inputs,
  that contract and tests need to be extended explicitly.
* The new exception is a `ValueError` subclass, so callers retaining a broad
  `ValueError` boundary remain compatible; no prior documented invalid-image
  exception was found.

### Evidence

* Receipt: `.oracle/runs/codebase-health-20260829/checkpoints/vision-mime-candidate-9abca467.md`
* `pytest -q tests/intent/test_judge_vision_offline.py`: **7 passed**
* Focused neighbor run (`test_judge_vision_offline.py`, text offline, panel,
  edit correctness): **21 passed, 1 skipped**
* `git diff --check`, `py_compile`, and Ruff: **pass**

