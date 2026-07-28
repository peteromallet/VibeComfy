# Case 05 — LoRA Loader (WanVideoLoraSelect) ADDITIVE RESTORE Failure

**TL;DR:** FIXER failed. The agent found multiple correct references (SEARCH ✅) but couldn't translate them into a working edit — it burned budget on schema resolution loops, then produced a validation error, then punted to the user for a value sitting in plain sight in the reference template.

## 1. The Inquiry

> *"I had removed the lora loader step from the workflow and now the style/character LoRA is no longer applied — the output lost the look the LoRA used to provide. Can you add that step back where it belongs so the output is restored? (the node type to re-add is `WanVideoLoraSelect`)"*

(status.json: `out/l7-canon10-stabilized/cases/13cb184e1bc2/status.json`, lines 6)

## 2. Removed Feature Node

From `source/golden.ui.json` (lines 634–668):

| Field | Golden Value |
|---|---|
| **Node** | `WanVideoLoraSelect` (id=98) |
| **widget** | `"WanVid/wan2.1-1.3b-control-lora-tile-v0.1_comfy.safetensors"` |
| **Output** | `lora` (type `WANVIDLORA`) → link 12 |
| **Target** | `WanVideoModelLoader` (id=22) input `lora` |

## 3. Per Attempt

### Attempt 001 — SchemaGap / budget exhausted
- **research.json**: Found the exact template `video/wanvideo_wrapper_13b_control_lora` (score 69) and its source workflow `ready_templates/sources/custom_nodes/wanvideo_wrapper/kijai/wan13b_control_lora.json`
- **candidate_graph**: Correctly includes `adapt_98` (WanVideoLoraSelect) wired to `adapt_22` (WanVideoModelLoader) input `lora`
- **Failure** (`implementation_result.json`, line 5–43): `batch_budget_exhausted`, classified as `SchemaGap`. The agent stated: *"I was unable to add the LoRA loader step back because I ran out of turns looking up the required schema information for the WanVideoLoraSelect node."*
- **42 remaining batches unused** — the agent hit the consecutive-error cap instead of using the on-demand schema resolver.

### Attempt 002 — ValidationError
- **Failure** (`implementation_result.json`, line 5): `"Boolean is not a canonical numeric value"` — the agent attempted an edit but the graph failed structural validation. The specific mismapped widget/input field is unclear from surface artifacts but indicates a FIXER-level mapping error between the candidate graph fields and the actual node schema.

### Attempt 003 — User clarification (capitulation)
- **Failure** (`implementation_result.json`, line 2): *"Which LoRA model file should be used? The original name is not in the current workflow."*
- The agent **asked the user for a value that existed in the reference** — `LORA_NAME = 'WanVid/wan2.1-1.3b-control-lora-tile-v0.1_comfy.safetensors'` at line 25 of `ready_templates/video/wanvideo_wrapper_13b_control_lora.py`.

## 4. Exact Failure Path

| Stage | Code | Detail |
|---|---|---|
| Attempt 001 (implement) | `batch_budget_exhausted` / `SchemaGap` | "Stopped after 7 turn(s); 43 turn(s) remaining." |
| Attempt 002 (implement) | `ValidationError` | "Boolean is not a canonical numeric value" |
| Attempt 003 (implement) | User clarification | Agent asked for LoRA filename the golden workflow already contained |

**No v2_delta errors** — stabilization held; the failures are purely in the agent's edit pipeline.

## 5. Precedent Existence

Multiple references with `WanVideoLoraSelect` exist in the repo:

1. **`ready_templates/video/wanvideo_wrapper_13b_control_lora.py`** (line 25): `LORA_NAME = 'WanVid/wan2.1-1.3b-control-lora-tile-v0.1_comfy.safetensors'` — exact LoRA name, exact wiring pattern, showing `wanvideoloraselect → wanvideomodelloader(lora=...)`
2. **`ready_templates/video/wanvideo_wrapper_21_14b_i2v.py`**: Also uses `WanVideoLoraSelect` with the same interface pattern.
3. **`ready_templates/sources/custom_nodes/wanvideo_wrapper/kijai/wan13b_control_lora.json`**: Source workflow JSON with complete wiring.
4. **Hivemind workflow #1449** ("WanVideo Text-to-Video Generation with Florence2 and Groq LLM"): Contains `WanVideoLoraSelect` + `WanVideoModelLoader` combination.

**All three attempts found these references** via the research phase (`research.json` shows `video/wanvideo_wrapper_13b_control_lora` with `source_workflow_available: true` and `source_workflow_path` pointing to the JSON). The `prior_path` and `source_template` breadcrumbs were present in the workflow metadata. SEARCH passed.

## 6. Schema Resolvability

The `WanVideoLoraSelect` node is from `ComfyUI-WanVideoWrapper` (Kijai), which is a public custom node pack. The on-demand schema resolver **could** resolve it. No "unknown class" errors appeared — instead, the agent exhausted its budget in a schema-resolution loop without successfully materializing the node schema into the edit context.

## Root Classification

**REFERENCE** (primary, with FIXER secondary). The search machinery successfully located 4+ relevant reference workflows, including the exact template that matches this case. The agent's research even included `WanVideoLoraSelect` in the candidate graph with correct wiring to `WanVideoModelLoader.inputs.lora`. But the agent could not **extract actionable details** from those references:

1. It didn't resolve the node schema from the source workflow JSON (burning budget instead).
2. It couldn't determine the correct widget values from the template (the LoRA filename was literally `LORA_NAME` in the reference Python file).
3. It produced a structural validation error when attempting the edit.
4. It finally punted by asking the user for the filename.

**Biggest lever**: Inject the golden node's widget values (or the reference template's constants) directly into the agent's context so it doesn't need to re-resolve schema or guess filenames. The agent needs a "just-add-this-node-with-these-values" prompt augmentation rather than a research-first approach for known-additive scenarios.
