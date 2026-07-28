# Case 04: face_detailer — Forensic Analysis

**TL;DR: TRUE ABSENCE (not a false-skip).** The golden workflow `edit/flux2_klein_9b_image_edit_base` contains **zero nodes** whose type name includes "face" or "detailer" — the skip verdict is correct. No re-pairing target exists in `ready_templates/`; the only Face*-type nodes in the repo live in video/animation workflows (`FaceMaskFromPoseKeypoints`, `FaceSegment`) and are semantically unrelated to face detailer (face refinement/enhancement). The canonical `FaceDetailer` node (ComfyUI-Impact-Pack, type `"FaceDetailer"`) is absent from all ready-templates. The plan (`docs/plans/all-installable-nodes.md:174`) explicitly acknowledges: *"no ready-template ships a FaceDetailer node"*.

---

## 1. Golden-Workload Node Inventory

**Source:** `ready_templates/sources/official/edit/flux2_klein_9b_image_edit_base.json`

**Top-level nodes (8 total):**

| ID | Type | Role |
|---|---|---|
| 9 | `SaveImage` | Output |
| 94 | `SaveImage` | Output (muted) |
| 81 | `LoadImage` | Input (logo) |
| 76 | `LoadImage` | Input (car interior) |
| 97 | `MarkdownNote` | Doc note |
| 99 | `MarkdownNote` | Subgraph label |
| 75 | `7b34ab90-…` (UUID) | Subgraph: "Image Edit (Flux.2 Klein 9B)" |
| 92 | `65c22b29-…` (UUID) | Subgraph: "Image Edit (Flux.2 Klein 9B)" (multi-input variant) |

**Subgraph-internal types (deduplicated across both subgraphs, ~22 unique):** `KSamplerSelect`, `Flux2Scheduler`, `CFGGuider`, `SamplerCustomAdvanced`, `VAEDecode`, `VAEEncode`, `RandomNoise`, `UNETLoader`, `CLIPLoader`, `CLIPTextEncode`, `VAELoader`, `EmptyFlux2LatentImage`, `ImageScaleToTotalPixels`, `GetImageSize`, `ReferenceLatent`, `LoadImage`.

**None of these types** contain the substrings `"face"` or `"detailer"` (case-insensitive). The keyword matcher in `_node_matches_feature` (`creative.py:672`) lowercases the type name and checks `"face" in ntype` / `"detailer" in ntype` — both fail for every node.

**Verdict: FALSE-SKIP check → Negative.** This is a genuine absence, not a matcher miss.

---

## 2. Re-Pairing Candidate Search

Searched all `.json` files under `ready_templates/sources/` for face/detailer nodes at both top level and inside subgraph definitions.

**Found (tangential only):**

| Workflow | Node Type | Relevance |
|---|---|---|
| `custom_nodes/wanvideo_wrapper/kijai/wan_animate.json` | `FaceMaskFromPoseKeypoints` | Video keypoint masking, not face refinement |
| `custom_nodes/ltxvideo/runexx/LTX-2.3_V2V_…` | `FaceSegment` | Segmentation, not detailer |

Neither is a valid re-pairing target. No `FaceDetailer` or `FaceDetailerPipe` node exists in any ready-template.

**Conclusion: No re-pairing target in the current corpus.** A workflow using FaceDetailer would need to be sourced externally (e.g., from ComfyUI-Impact-Pack example workflows) and promoted via `scripts/promote_demo_scenario.py`.

---

## 3. Canonical FaceDetailer Node Shape

| Attribute | Value |
|---|---|
| **Source pack** | `ComfyUI-Impact-Pack` (ltdrdata) |
| **Primary class type** | `FaceDetailer` |
| **Pipe variant** | `FaceDetailerPipe` (in object_info cache at `ComfyUI-Hotshot@stub.json:1165`) |
| **Keyword match** | ✅ `"face"` in `"facedetailer"` → `True` (tested at `test_demo_factory_creative.py:28`) |
| **Category** | `"impact"` or `"face"` (custom node, no fixed category) |
| **Key inputs** | `image` (IMAGE), `model` (MODEL), `clip` (CLIP), `vae` (VAE), `positive`/`negative` (CONDITIONING), `detailer_hook` (optional), `bbox_detector`, `sam_model_opt` |
| **Key outputs** | `image` (IMAGE), `mask` (MASK), `detailer_hook` |
| **Function** | Detects faces via bbox/SAM, crops, refines with a secondary pass (detailer), composites back |

The keyword fallback (`"face"` substring) would match *any* face-related node broadly, but the specific semantic of "face detailer" is a face-detection → crop → refine → composite pipeline, traditionally from Impact Pack. A correct fixer output would wire a `FaceDetailer` node in series after the main image output, accepting the base image + model/clip/vae and producing an enhanced image.

---

## 4. Root Classification

**PAIRING — True absence.**

The case `(edit/flux2_klein_9b_image_edit_base, face_detailer)` pairs a feature type with a workflow that has no corresponding node. The skip is mechanically correct (harness avoids removing a wrong node). However, the campaign definition in `run_campaign.py:65` paired this deliberately — likely expecting a face-detailer pass *after* the image edit. Since the golden is a clean Flux.2 image-edit pipeline (no face refinement phase), the pairing is invalid.

**Actionable finding:** Either:
1. **Replace** the pair with a workflow that actually uses FaceDetailer (none exists currently — needs to be created/promoted), or
2. **Repair** the golden by *inserting* a FaceDetailer pass first, then generating the remove-fault against it (materialization dependency per `docs/plans/all-installable-nodes.md:175`).

The second approach is more aligned with the demo-factory goal (10 varied additive cases) but requires either manual golden augmentation or a materialization pipeline.
