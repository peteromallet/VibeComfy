# Case 09 — Upscale (ImageScaleToTotalPixels, distilled flux): Failure Analysis

**TL;DR:** Rejected (3 attempts, all wrong). Root: **VALUE** — agent placed the upscale node at the wrong pipeline position (post-VAE-decode instead of pre-VAE-encode), used wrong widget values (`lanczos` vs `nearest-exact`), and covered only one of two output branches. Biggest lever: force the fixer to consult `prior_path` / `source_template` breadcrumbs before emitting edits — the ready_template shows the exact wiring with correct widget values on line 47-50.

---

## 1. Inquiry

> *"I had removed the upscale step from the workflow and now the output is lower resolution than it should be — it lost the detail the resize/upscale step used to add. Can you add that step back where it belongs so the output is restored? (the node type to re-add is `ImageScaleToTotalPixels`)"*

**Source:** `out/l7-canon10-stabilized/cases/220a9dedb8a7/status.json` line 6.

---

## 2. Removed Feature Node

From `source/golden.ui.json` lines 660–691:

| Property | Value |
|---|---|
| **node id** | 6 |
| **class_type** | `ImageScaleToTotalPixels` |
| **widgets_values** | `["nearest-exact"]` |
| **input** | link 55 ← node 76 (`LoadImage`, `bold_outfit_woman.jpeg`) |
| **outputs** | link 7 → node 8 (`ImageResize`), link 8 → node 40 (`VAEEncode`) |

The node sits between `LoadImage(76)` and the image-preprocessing pipeline (`ImageResize(8)`, `VAEEncode(40)`). It upscales the **input image** before it enters the edit pipeline. The `"nearest-exact"` method preserves hard edges for subsequent compositing.

In the broken workflow (`broken/broken.ui.json`), node 6 is absent. LoadImage(76) now connects directly to nodes 8 and 40 (links 58, 59), bypassing the upscale entirely. The workflow still contains two *other* `ImageScaleToTotalPixels` nodes (id=18, id=24) serving a different purpose — they upscale reference images inside the edit subgraph.

---

## 3. Per-Attempt Analysis

### Attempt 001 — Clarify (wasted)

| File | Key content |
|---|---|
| `attempts/001/classification.json` | `route: clarify`, `research: false`, `implement: false` |
| `attempts/001/response.json` | *"There are already two `ImageScaleToTotalPixels` nodes in your workflow. Could you clarify which output you want to upscale..."* |

The agent saw existing scale nodes (id=18, id=24 used for reference images) and confused them with the missing upscale step. It routed to `clarify` instead of recognizing node 6 was the one removed. No edits produced. **Research was false** — it never consulted prior_path.

### Attempt 002 — Wrong position, wrong values, extra node

| File | Key content |
|---|---|
| `attempts/002/classification.json` | `route: revise`, `research: false`, plan: *"Re-add an ImageScaleToTotalPixels node after VAEDecode and before SaveImage"* |
| `implementation_result.json` | Added node 123 with `["lanczos", 1.0, 1]` between VAEDecode(17)→node 123→SaveImage(9); node 124 similarly for second pipeline (VAEDecode 38→124→SaveImage 122) |

**Wrong placement:** Post-decode upscale changes the **output** image resolution but doesn't help the editing pipeline which operates on the latent. The original node 6 upscaled the **input** image pre-encode.

**Wrong values:** `["lanczos", 1.0, 1]` instead of golden `["nearest-exact"]`. The method `lanczos` is fine for photographic output but `nearest-exact` was chosen to avoid interpolation artifacts before compositing.

Gate outcome: `gates_passed=4/6`, `candidate_compile_error: SOFT-PASS (UNETLoader weight_dtype)`. The SOFT-PASS is pre-existing (same in baseline). The real failure is the oracle gate rejecting the wrong placement.

### Attempt 003 — Same errors, now only one branch

| File | Key content |
|---|---|
| `attempts/003/classification.json` | `route: revise`, `research: false`, plan: *"Reconnect the ImageScaleToTotalPixels node into the image output path"* |
| `implementation_result.json` | Added node 123 with `["lanczos", 1.0, 1]` between VAEDecode(17)→node 123→SaveImage(9) only. Second pipeline (38→122) untouched. |

**Still wrong position, still wrong values, now missing the second output branch entirely.** The agent regressed from covering both outputs (attempt 2) to covering only one.

---

## 4. Exact Failure Mode

All internal gates in the response (ir_validate, lower, plan, python_load, queue_validate, state_match, ui_emit, ui_fidelity, ui_load_safe) passed. The compile error `UNETLoader missing weight_dtype` is a SOFT-PASS present in the golden baseline too — it's a pre-existing template issue.

The rejection comes from **gates 5 and 6** (pipeline-run + oracle evaluation) not shown in the response.json. The receipts (`003_complete.json`: `gates_passed=4/6`) confirm the candidate was structurally valid but behaviorally wrong — the oracle correctly detected that the upscale was applied at the wrong stage with the wrong method.

No `v2_delta` errors — the pipeline stabilization held.

---

## 5. Precedent Exists

The source template referenced by `prior_path` and `source_template` breadcrumbs shows the exact correct wiring:

**`ready_templates/edit/flux2_klein_9b_image_edit_distilled.py` lines 47–50:**
```python
imagescaletototalpixels = ImageScaleToTotalPixels(
    upscale_method='nearest-exact',
    image=image,      # ← input image from LoadImage, NOT output from VAEDecode
)
```

This is the first `ImageScaleToTotalPixels` usage in the file — it takes `image` (the LoadImage output), uses `nearest-exact`. The other usages (lines 101, 117) use `lanczos` for reference images, which is where the agent likely got confused.

Additional reference workflows: `ready_templates/sources/official/edit/flux2_klein_9b_image_edit_distilled.json` (6 occurrences of `ImageScaleToTotalPixels`), `ready_templates/edit/flux2_klein_9b_image_edit_base.py`, `ready_templates/edit/flux2_klein_4b_image_edit_distilled.py`.

**Did the agent find them?** No. `research: false` in all 3 attempts. The `prior_path` and `source_template` breadcrumbs in the metadata were available but never consumed. The classifier never triggered research, so the fixer operated without any reference context.

---

## 6. Schema Resolution

`ImageScaleToTotalPixels` is a core node (`vibecomfy.nodes.core.ImageScaleToTotalPixels`), resolved via `object_info_index` schema provider. All nodes have `_vibecomfy_schema_provider: "object_info_index"`. No "unknown class" errors. The on-demand resolver was not needed but would have worked if triggered.

---

## 7. Root Classification

**PRIMARY: VALUE** — The agent added the correct node type (`ImageScaleToTotalPixels`) but at the **wrong pipeline position** (post-VAE-decode instead of pre-VAE-encode), with **wrong widget values** (`lanczos` vs `nearest-exact`), and **incomplete coverage** (one branch instead of two). The structural form was right; the semantic placement and values were wrong.

**SECONDARY: REFERENCE** — The classifier set `research: false` on all three attempts despite the workflow metadata carrying explicit `prior_path` and `source_template` breadcrumbs pointing to the correct wiring. A single research pass loading the ready_template would have shown the fixer the exact node signature and placement. The fixer cannot get the right answer if it never looks at the reference.
