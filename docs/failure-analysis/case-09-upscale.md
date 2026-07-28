# Case 09 Failure Analysis: upscale (rejected)

**TL;DR:** Verdict `rejected` after 3 attempts. Root: **VALUE** — agent guessed `lanczos` instead of golden's `nearest-exact`. Single biggest lever: the ready_template source (`flux2_klein_9b_image_edit_distilled.py` line 48) explicitly shows `upscale_method='nearest-exact'`; the agent never researched it (`research: false` across all attempts).

---

## 1. The Inquiry

> *"I had removed the upscale step from the workflow and now the output is lower resolution than it should be — it lost the detail the resize/upscale step used to add. Can you add that step back where it belongs so the output is restored? (the node type to re-add is `ImageScaleToTotalPixels`)"*

Source: `status.json` line 6.

---

## 2. The Removed Feature Node

**File:** `source/golden.ui.json`

The golden has 3 `ImageScaleToTotalPixels` nodes. The *removed* one (feature node) is:

| Property | Value |
|---|---|
| `vibecomfy_id` | `ImageScaleToTotalPixels_5` |
| `vibecomfy_uid` | `n8` |
| `Node name for S&R` | `ImageScaleToTotalPixels` |
| `widgets_values` | `["nearest-exact"]` |
| Input | link 55 from node 76 (LoadImage) IMAGE |
| Output | links 7,8 to nodes 10,11 (GetImageSize ×2) IMAGE |
| Position | `[520.0, 184.0]` |

The other two `ImageScaleToTotalPixels` nodes (uids `n20`, `n26`) use `"lanczos"` — they upscale *reference images*, not the output image.

**Reference in source template** (`ready_templates/edit/flux2_klein_9b_image_edit_distilled.py` line 47–50):
```python
imagescaletototalpixels = ImageScaleToTotalPixels(
    upscale_method='nearest-exact',
    image=image,
)
```

The `ImageScaleToTotalPixels` node has 3 widget fields: `upscale_method`, `megapixels`, `resolution_steps`. The golden only sets `upscale_method='nearest-exact'`; megapixels and resolution_steps use defaults (not serialized as widgets).

---

## 3. Per-Attempt Analysis

### Attempt 001
- **Classification:** `research: false, route: revise`
- **Node added:** `ImageScaleToTotalPixels` (uid `n43`, id 123)
- **Widgets:** `["lanczos", 2.0, 1]` — **WRONG upscale_method** (should be `nearest-exact`)
- **Wiring:** VAEDecode (id=17, uid=n19) → new node 123 → SaveImage (id=9, uid=n41) ✓ (correct branch, post-VAE)
- **File:** `attempts/001/implementation_result.json` lines 2281–2295

### Attempt 002
- **Classification:** `research: false, route: revise` (identical structure)
- **Node added:** Same type, same wiring, widgets `["lanczos", 1.0, 1]` — still wrong upscale_method
- **File:** `attempts/002/implementation_result.json` lines 2281–2295

### Attempt 003
- **Classification:** `research: false, route: revise` (identical structure)
- **Model changed:** `deepseek/deepseek-v4-pro` (upgrade from flash)
- **Result:** Applied 4 edit ops (2 ImageScaleToTotalPixels nodes + 2 link rewirings) but `graph_unchanged: true, no_candidate_reason: "no_changes"` — the edits produced a structurally identical graph to attempt 002
- **File:** `attempts/003/response.json` lines 648–651

---

## 4. Exact Failure

**Receipt verdicts** (both `001_complete.json` and `002_complete.json`):
```json
{
  "verdict": "rejected",
  "gates_passed": 4,
  "gates_total": 6,
  "candidate_execution_safe": true,
  "candidate_compile_error": "SOFT-PASS (nodes resolve; runtime concerns only): ..."
}
```

The candidate compiled safely (no structural-gate failure, no v2_delta ValueError). The oracle **rejected** on semantic comparison: the re-added `ImageScaleToTotalPixels` node's `upscale_method='lanczos'` does not match the golden's `upscale_method='nearest-exact'`. This is a **VALUE** rejection — correct node type, correct wiring/branch, but wrong functional parameter.

---

## 5. Precedent

**References DO exist in the database.** The repository has abundant `ImageScaleToTotalPixels` examples:

1. **`ready_templates/edit/flux2_klein_9b_image_edit_distilled.py`** (line 47–50): The literal source template for this exact workflow uses `upscale_method='nearest-exact'`
2. **`ready_templates/edit/flux2_klein_4b_image_edit_base.py`** (line 48, 98, 113): Three `ImageScaleToTotalPixels` calls, all using `'nearest-exact'`
3. **`ready_templates/edit/flux2_klein_4b_image_edit_distilled.py`** (line 48, 144, 160): Three more using `'nearest-exact'`
4. **`ready_templates/sources/official/edit/flux2_klein_9b_image_edit_distilled.json`** (line 1341): The official source JSON with `"nearest-exact"` widget value

All 3 attempts set `research: false` — the agent **never searched for reference workflows**. This is a SEARCH sub-failure (no research was attempted), but the primary failure is VALUE because the agent chose `lanczos` by default instead of consulting the schema/template.

---

## 6. Schema

**The node's schema was resolvable.** The implementation payload shows `_vibecomfy_schema_provider: "object_info_index"` on the added node — the on-demand resolver was engaged correctly. No "unknown class" errors. The schema defines 3 widget fields: `upscale_method` (enum: nearest-exact, bilinear, lanczos, etc.), `megapixels` (float, default 1.0), `resolution_steps` (int, default 1). The agent used valid enum values but the **wrong specific value**.

---

## Root Classification

**VALUE** — The agent correctly identified the node type (`ImageScaleToTotalPixels`), placed it in the right position (post-VAEDecode, feeding SaveImage), and wired it correctly. But it used `upscale_method='lanczos'` instead of the golden's `upscale_method='nearest-exact'`. The reference template for this exact workflow (`flux2_klein_9b_image_edit_distilled.py` line 48) explicitly shows `nearest-exact` — the agent never researched it (`research: false` across all 3 attempts), relying on a plausible guess (`lanczos` from the other upscale nodes in the graph) that happened to be wrong for this specific node.
