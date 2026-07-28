# Case 08: refinement_pass — WanVideoSampler Additive Restore

**TL;DR: REJECTED — VALUE failure. Agent correctly identified type and wiring topology across all 3 attempts but used provisional/default widget values instead of the golden's exact sigma/scheduler/seed configuration. The on-demand schema resolver was never engaged (`workflow_json_provisional` instead of `object_info_index`), and the agent never extracted the golden node's widget values from the reference workflow that was found.**

---

## 1. The Inquiry

> *"I had removed the refinement pass step from the workflow and now the refinement pass is gone — the output is rougher and less polished than the two-stage result used to be. Can you add that step back where it belongs so the output is restored? (the node type to re-add is `WanVideoSampler`)"*

Source: `status.json` line 6, case_id `bcabbfe618f8`.

## 2. Removed Feature Node (Golden)

**Node 27** (`source/golden.ui.json` lines 296–358):
- **class_type:** `WanVideoSampler`
- **schema_provider:** `"object_info_index"` (on-demand resolver)
- **widgets_values:** `[4, 1, null, 1057359483639287, "fixed", null, "dpm++_sde", null, null, ""]`
  - steps=4, cfg=1, seed=1057359483639287, control_after_generate="fixed", scheduler="dpm++_sde"
- **Wiring:** model←WanVideoSetBlockSwap (70, link 19), image_embeds←WanVideoImageToVideoEncode (63, link 12), text_embeds←WanVideoTextEncode (16, link 2), samples→WanVideoDecode (28, link 5)

## 3. Per Attempt — What Was Re-Added

### Attempt 001 — ValidationError
- `implementation_result.json` lines 3–11: `"Boolean is not a canonical numeric value"` — agent produced syntactically invalid widget values. Failed at implement stage; no candidate reached evaluation.

### Attempt 002 — Wrong Values (11 widgets)
- **Node 71** (`implementation_result.json` lines 824–883): WanVideoSampler, schema_provider=`"workflow_json_provisional"`
- **widgets_values:** `[10, 1.0000000000000002, 1.0000000000000002, 325999519217108, "randomize", true, "unipc", 0, 1, "", "comfy"]`
- **Mismatches vs golden:** steps=10≠4, seed=325...≠105..., control="randomize"≠"fixed", scheduler="unipc"≠"dpm++_sde", extra shift/fields
- **Wiring:** Correct topology (model←70, image_embeds←63, text_embeds←16, output→28)

### Attempt 003 — Better But Still Wrong Values (15 widgets)
- **Node 71** (`implementation_result.json` lines 824–894): WanVideoSampler, schema_provider=`"workflow_json_provisional"`
- **widgets_values:** `[4, 1.0, 5.0, 0, "fixed", true, "dpm++_sde", 0, 1, false, "comfy", 0, -1, false, ""]`
- **Matches golden:** steps=4 ✓, cfg≈1 ✓, control="fixed" ✓, scheduler="dpm++_sde" ✓
- **Still wrong:** seed=0≠1057359483639287, shift=5.0 (golden null), 10 extra positional values the golden doesn't expose
- **Wiring:** Correct topology (same as attempt 002)

## 4. Exact Failure

**Receipt `003_complete.json`:** `verdict: "rejected"`, `gates_passed: 5 / 6`.

The 6th gate (oracle widget-value comparison) failed because the re-added WanVideoSampler's widget values do not match the golden values. The seed (0 vs 1057359483639287), shift, and extra fields all diverge. The compile-stage soft-pass notes (`"SOFT-PASS (nodes resolve; runtime concerns only): Node 30 (VHS_VideoCombine)..."`) are a pre-existing baseline issue and not the cause of rejection — the baseline also carries them (`proof/baseline.json` line 5).

The candidate graph is structurally sound: the agent correctly spliced the WanVideoSampler between WanVideoSetBlockSwap/WanVideoImageToVideoEncode/WanVideoTextEncode (inputs) and WanVideoDecode (output). **No v2_delta errors present** — the stabilization held.

## 5. Precedent Exists — And Was Found

The repo has **43 files** referencing `WanVideoSampler` under `ready_templates/`, including the exact source workflow:

1. `ready_templates/sources/custom_nodes/wanvideo_wrapper/kijai/wan21_14b_i2v.json` — the golden's source (referenced by `prior_path` breadcrumb)
2. `ready_templates/video/wanvideo_wrapper_21_14b_i2v.py` — the python template
3. `ready_templates/sources/custom_nodes/wanvideo_wrapper/kijai/wan21_14b_t2v.json` — sibling t2v workflow

The agent's `research.json` for attempt 003 found all of these (lines 12–43 show the exact `prior_path` match with `source_workflow_path` pointing to `wan21_14b_i2v.json`). **The agent found the right references** in every attempt. However, it never extracted the golden node's widget values from them — it fell back to `workflow_json_provisional` schema provider, generating default/provisional values instead of the golden's exact configuration.

## 6. Schema Resolution

The re-added node's `_vibecomfy_schema_provider` was set to `"workflow_json_provisional"` (attempt 003 line 868) rather than `"object_info_index"` (as in the golden). **The on-demand schema resolver was never invoked.** The agent produced a structural skeleton of the node from its internal knowledge of WanVideoSampler's inputs/outputs, but the provisional schema had a different widget layout (15 fields vs 10 in the golden), causing value misalignment.

No "unknown class" errors — `WanVideoSampler` is a known node and the agent recognized it.

## Root Class: VALUE

The wiring topology (SEARCH + FIXER) works correctly — the agent consistently placed the WanVideoSampler with the right connections. The search (SEARCH + REFERENCE) found the right workflows. The breakdown is **VALUE**: the agent produces default/provisional widget values instead of consuming the exact values from the golden workflow or the source template. The on-demand schema resolver (which would return the authoritative schema with correct default values and widget ordering) was never engaged.

**Primary lever:** Force the agent to query the on-demand schema resolver (`object_info_index`) for any re-added node, then map widget values from the golden reference onto the resolved schema rather than emitting provisional values.
