# Case 04: face_detailer — Forensic Analysis (v2 Stabilized Run)

**TL;DR: TRUE ABSENCE → PAIRING failure.** The golden `edit/flux2_klein_9b_image_edit_base` contains zero nodes matching `"face"` or `"detailer"` at any nesting level. The skip verdict is correct. No FaceDetailer node exists in any ready_template in the corpus. The campaign pairing in `run_campaign.py:65` is invalid for the current golden corpus. This is not a matcher bug, not a fixer bug — it is a **PAIRING** failure: we asked the agent to re-add a feature that was never there.

---

## 1. False-Skip Check: Golden Node Inventory

**Source:** `ready_templates/sources/official/edit/flux2_klein_9b_image_edit_base.json`

**Top-level nodes (8 total), as seen by `find_feature_node_ids()`:**

| ID | Type | Matches `"face"`? | Matches `"detailer"`? |
|---|---|---|---|
| 9  | `SaveImage` | ✗ | ✗ |
| 94 | `SaveImage` (muted) | ✗ | ✗ |
| 81 | `LoadImage` | ✗ | ✗ |
| 76 | `LoadImage` | ✗ | ✗ |
| 97 | `MarkdownNote` | ✗ | ✗ |
| 99 | `MarkdownNote` | ✗ | ✗ |
| 75 | `7b34ab90-…` (UUID subgraph wrapper) | ✗ | ✗ |
| 92 | `65c22b29-…` (UUID subgraph wrapper) | ✗ | ✗ |

**Subgraph-internal types (deduplicated, ~22 unique):** `KSamplerSelect`, `Flux2Scheduler`, `CFGGuider`, `SamplerCustomAdvanced`, `VAEDecode`, `VAEEncode`, `RandomNoise`, `UNETLoader`, `CLIPLoader`, `CLIPTextEncode`, `VAELoader`, `EmptyFlux2LatentImage`, `ImageScaleToTotalPixels`, `GetImageSize`, `ReferenceLatent`, `LoadImage`.

**None contain `"face"` or `"detailer"` (case-insensitive).** The matcher function `_node_matches_feature()` (creative.py:672) lowercases the type name and checks `"face" in ntype` / `"detailer" in ntype` — both fail for every node. Even if the matcher recursed into subgraph definitions (which it does not), no match would be found.

**Verdict: ✅ True absence — skip is mechanically correct.**

---

## 2. Re-Pairing Target Search

Searched all `.json` files under `ready_templates/sources/` for `FaceDetailer`, `face_detailer`, `FaceDetailerPipe`:

| Search | Hits |
|---|---|
| `FaceDetailer` (exact class type) | **0** |
| `face_detailer` (feature label) | **0** |
| `FaceDetailerPipe` (pipe variant) | **0** |

The object_info cache in `ComfyUI-Hotshot@stub.json` contains a `FaceDetailerPipe` stub (category `hotshot/stub`, not `impact`/`face`), but this was derived from a Hotshot workflow JSON, not from an installed Impact Pack — and no ready_template actually uses it.

The `docs/plans/all-installable-nodes.md` reference (cited in the v1 analysis) does not exist in the current repo. No workflow in the corpus contains a FaceDetailer of any variant.

---

## 3. Canonical FaceDetailer Node Shape

| Attribute | Value |
|---|---|
| **Source pack** | `ComfyUI-Impact-Pack` (ltdrdata) |
| **Primary class type** | `FaceDetailer` |
| **Pipe variant** | `FaceDetailerPipe` (stub exists in cache, not used in any template) |
| **Keyword match** | ✅ `_node_matches_feature("FaceDetailer", "face_detailer")` → `True` (tested at `test_demo_factory_creative.py:28`) |
| **Category** | `impact` / `face` (custom node, no fixed category in cache) |
| **Key inputs** | `image`, `model`, `clip`, `vae`, `positive`/`negative` (CONDITIONING), `bbox_detector`, `sam_model_opt` |
| **Key outputs** | `image`, `mask`, `detailer_hook` |
| **Function** | Detect faces → crop → refine (secondary detail pass) → composite back |

The keyword fallback (`"face"` substring) is confirmed working by unit test and would match any face-related type broadly. But no such type exists in the golden.

---

## 4. Root Classification

**PAIRING — True absence.**

The campaign tuple `("edit/flux2_klein_9b_image_edit_base", "face_detailer")` in `run_campaign.py:65` pairs a feature type with a workflow that never had it. The Flux.2 Klein 9B image-edit pipeline is a clean single-pass edit (image in → VAE encode → UNet → VAE decode → image out) with no face refinement phase. There is nothing to remove, so the case correctly skips.

**The pairing itself is the defect.** It likely originates from a design assumption that image-edit workflows *should* have a face-detailer post-pass, but the actual golden is a minimal stock ComfyUI workflow without one.

**Actionable recommendations:**

1. **Source or create a FaceDetailer golden.** Either find a ComfyUI-Impact-Pack example with FaceDetailer, promote it via `scripts/promote_demo_scenario.py`, and re-pair; or augment the existing golden by materializing a FaceDetailer pass into it (per the materialization dependency noted in plans).
2. **Replace the pair.** Swap to a workflow known to contain a FaceDetailer node (none currently exists — needs external sourcing).
3. **Lower priority.** This case will always skip until a suitable workflow is available. It inflates the "skipped" count but causes no false behavior.

---

## 5. Stabilized Run Notes (v2)

This analysis is against the **l7-canon10-stabilized** run, meaning the v2_delta pipeline break was already fixed upstream. The skip is stable across runs — changing nothing about the infrastructure changes the outcome, because the root cause is entirely in the campaign pairing table.
