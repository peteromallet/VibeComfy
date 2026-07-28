# Case 08 — refinement_pass (WanVideoSampler)

**TL;DR:** Verdict `rejected` (5/6 gates) — root class **VALUE**. The agent added the correct node type (`WanVideoSampler`) with correct wiring (model/image_embeds/text_embeds in → samples out to decoder) but used entirely wrong widget values (steps=20, cfg=6, seed=42, scheduler=unipc) instead of the golden's (steps=4, cfg=1, seed=1057359483639287, scheduler=dpm++_sde). The on-demand schema resolver was bypassed in favor of `workflow_json_provisional`. Attempts 2 and 3 then failed with INFRA issues (timeout, malformed parse).

---

## 1. The Inquiry

From `status.json` line 6:
> "I had removed the refinement pass step from the workflow and now the refinement pass is gone — the output is rougher and less polished than the two-stage result used to be. Can you add that step back where it belongs so the output is restored? (the node type to re-add is `WanVideoSampler`)"

The inquiry explicitly tells the agent the node type is `WanVideoSampler`.

## 2. The Removed Feature Node (Golden)

**File:** `source/golden.ui.json`, node id=27
- **Class type:** `WanVideoSampler`
- **Widget values:** `[4, 1, null, 1057359483639287, "fixed", null, "dpm++_sde", null, null, ""]`
  - Position 0 (steps): 4
  - Position 1 (cfg): 1
  - Position 3 (seed): 1057359483639287
  - Position 4 (control_after_generate): "fixed"
  - Position 6 (scheduler): "dpm++_sde"
- **Inputs:** model (link 19 ← WanVideoSetBlockSwap), image_embeds (link 12 ← WanVideoImageToVideoEncode), text_embeds (link 2 ← WanVideoTextEncode)
- **Outputs:** samples (link 5 → WanVideoDecode), denoised_samples (unconnected)

## 3. Per Attempt: What the Agent Re-Added

### Attempt 1 — **Candidate produced but wrong values**

**File:** `attempts/001/implementation_result.json`, node id=71
- **Class type:** `WanVideoSampler` ✅ (correct)
- **Wiring:** model←WanVideoSetBlockSwap, image_embeds←WanVideoImageToVideoEncode, text_embeds←WanVideoTextEncode, samples→WanVideoDecode ✅ (identical to golden)
- **Widget values:** `[20, 6, 5, 42, "fixed", true, "unipc", 0, 1, "", "comfy_chunked", 0, -1, true]` ❌
  - steps=20 (golden: 4), cfg=6 (golden: 1), seed=42 (golden: 1057359483639287), scheduler="unipc" (golden: "dpm++_sde")
- **Schema provider:** `"workflow_json_provisional"` — the on-demand resolver was NOT engaged. The schema was inferred from a reference workflow JSON, not resolved from the actual node definition.

### Attempt 2 — **TimeoutError**

**File:** `attempts/002/implementation_result.json`
- Error: "The model did not respond in time. The graph is unchanged."
- Failure: Timeout after 180s at the "implement" stage.

### Attempt 3 — **MalformedModelJSON**

**File:** `attempts/003/implementation_result.json`
- Error: "The model response could not be parsed. The graph is unchanged."
- Failure: Model output lacked the required ` ```batch ` fenced block.

## 4. Exact Failure Mode

**File:** `receipts/001_complete.json`
```
gates_passed: 5, gates_total: 6, verdict: "rejected"
candidate_execution_safe: true
candidate_compile_error: "SOFT-PASS (nodes resolve; runtime concerns only)"
```

The candidate passed 5 of 6 gates including the structural compilation gate. The single failing gate was the **oracle** — the semantic equivalence check that compares widget values against the golden. The graph compiled and wired correctly but produced wrong sampling parameters. No `v2_delta` ValueError was involved; this was a pure oracle rejection.

## 5. Precedent Existence & Research Quality

**References DO exist in the DB.** The agent found them but picked a bad one:

| Source | Path | WanVideoSampler Widgets? |
|--------|------|--------------------------|
| ready_template | `ready_templates/video/wanvideo_wrapper_22_5b_ovi_audio_i2v.py` | Found (attempts 1,3) |
| ready_template | `ready_templates/sources/custom_nodes/wanvideo_wrapper/kijai/wan21_14b_i2v.json` | Golden source — accessible |
| hivemind | Workflow id 1481 "HuMo_2nd_pass" | Found (attempt 1) |
| hivemind | Workflow id 1372 "Ovi testing" | Found (attempt 2) |

All 3 attempts' `research.json` files show successful retrieval of WanVideoSampler-containing workflows. However, the research surfaced the *Ovi audio* workflow (wan22_5b_ovi_audio_i2v) which has completely different widget values (steps=50, cfg=4, scheduler=unipc) — the agent copied these alien values instead of the golden's. The actual golden source template (`wan21_14b_i2v.json` at the same repo path) was never directly consulted for its widget values.

## 6. Schema Resolution Failure

The attempt 1 candidate node 71 shows `"_vibecomfy_schema_provider": "workflow_json_provisional"` — not `"object_info_index"`. This means the on-demand schema resolver (which can resolve ANY public node even if not installed) was **not engaged**. Instead, the agent's edit session schema was provisionally derived from a reference workflow JSON, which carried wrong default values. This is the proximal cause of the wrong widget values: the fixer worked from an incorrect semantic model of what a WanVideoSampler should look like.

## 7. Root Classification

**PRIMARY: VALUE** — The agent correctly identified the node type (`WanVideoSampler`), correctly wired all three inputs (model, image_embeds, text_embeds) and the output (samples → decoder). The graph compiled (5/6 gates). But every widget value was wrong: steps (20 vs 4), cfg (6 vs 1), seed (42 vs 1057359483639287), scheduler (unipc vs dpm++_sde). The fixer applied the right structure with wrong functional parameters.

**SECONDARY: INFRA** — Attempts 2 and 3 never produced candidates due to model timeout and malformed JSON parsing, wasting 2/3 of the retry budget.

**BIGGEST LEVER:** Force the on-demand schema resolver (`object_info_index`) for re-added nodes instead of falling back to `workflow_json_provisional`. The schema was resolvable but wasn't fetched. Also: the research pipeline should prefer the *exact source template* of the case (wan21_14b_i2v) over loosely-related Ovi-audio workflows.
