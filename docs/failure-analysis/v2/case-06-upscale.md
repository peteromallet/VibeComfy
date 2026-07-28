# Case 06 — Upscale (fixer_failed)

**TL;DR:** VERDICT=fixer_failed | ROOT=FIXER | biggest lever: the agent fixated on `widget_1` on a surviving sibling node instead of inserting the *missing* `ResizeImageMaskNode`, never read the source template that literally shows the correct two-node wiring, and burned 3 attempts on impossible field edits and irrelevant IAMCCS workflows.

---

## 1. Inquiry

> *"I had removed the upscale step from the workflow and now the output is lower resolution than it should be — it lost the detail the resize/upscale step used to add. Can you add that step back where it belongs so the output is restored? (the node type to re-add is `ResizeImageMaskNode`)"*

Location: `out/l7-canon10-stabilized/cases/8569d2538f93/status.json` (lines 6-7).

## 2. Removed Feature Node

**Class:** `ResizeImageMaskNode` (node id=2, uid=n32, "ResizeImageMaskNode_1")

**Golden widget values** (`source/golden.ui.json` lines 78-80):
```
["scale by multiplier"]
```
No multiplier value passed — the default behaviour in the workflow is `resize_type='scale by multiplier'` wired between the image input and `ImagePadForOutpaint`.

There are **two** `ResizeImageMaskNode` instances in the golden workflow (nodes id=2 on branch 1, id=3 on branch 2). The "broken" workflow (`broken/broken.ui.json`) retains only node id=3 (uid=n33). Node id=2 — the one on the first image branch — was removed, breaking the `input → ResizeImageMaskNode → ImagePadForOutpaint` chain on that side.

## 3. Per Attempt — What the Agent Did

### Attempt 001 (editor session `f41d0d0f...`)
- **Result:** `"I could not produce a safe graph edit from the available workflow precedent and current authoring surface. The graph is unchanged."`
- **What happened:** The agent zeroed in on the *surviving* node (id=3, uid=n33) and repeatedly tried `resizeimagemasknode.widget_1 = 2.0`, which failed with `non_widget_field_not_editable` (6 times across 5 batch turns). It never created a new node. It searched for `ResizeImageMaskNode` schema repeatedly but kept reissuing the same broken statement.

### Attempt 002 (editor session `0ea6dae4...`)
- **Result:** Clarified with: *"ResizeImageMaskNode is already in the graph (wired to imagepadforoutpaint_2). Where did the removed upscale step originally sit — on the second image branch, or after the decode?"* — 0 operations landed.
- **What happened:** The agent tried to create a *new* `ResizeImageMaskNode` with positional args (`positional_args_not_allowed` error), then fell back to the same `widget_1 = 2.0` cycle on the existing node, then asked for clarification.

### Attempt 003 (editor session `a881ae6b...`)
- **Result:** *"This edit requires custom-node classes that could not be found in the live ComfyUI runtime or Comfy Registry: IAMCCS_VAEDecodeTiledSafe, ..."* — stopped before authoring.
- **What happened:** The adaptation plan matched to the wrong workflow slice (`video/ltx2_3_iamccs_audio_image_to_video`), requiring 14 IAMCCS custom nodes that don't exist in the runtime. The agent never recovered.

## 4. Exact Failure

**Final gate status** (attempt 002 `flow_metadata.json`):
- `plan_validate_ok`: true (only green gate)
- ALL other gates: **false** — `ir_validate_ok`, `lower_ok`, `python_load_ok`, `queue_validate_ok`, `ui_emit_ok`, `ui_fidelity_ok`, `ui_load_safe_ok`

**Receipt:** `receipts/003_repair_failed.json` — `"error": "fixer failed"`

**Oracle verdict:** `rejected` (status.json line 5).

**No v2_delta errors** — the stabilization held. This is a pure fixer failure.

## 5. Precedent Availability

**References exist abundantly:**

| Path | Content |
|------|---------|
| `ready_templates/video/ltx2_3_runexx_first_last_frame.py` (lines 98-106) | Shows **both** `ResizeImageMaskNode` calls: `resize_type='scale by multiplier'`, wired to `input` / `input_2` |
| `ready_templates/video/ltx2_3_t2v.py` (line 154) | Another LTXV workflow with `ResizeImageMaskNode` |
| `ready_templates/sources/custom_nodes/ltxvideo/ltx2_3_single_stage_distilled_full.json` (line 1301) | Source JSON with the node wired correctly |
| `ready_templates/image/basic_image_upscale.py` | Standalone upscale example |

**The agent's `request.json` included:**
```json
"prior_path": "ready_templates/video/ltx2_3_runexx_first_last_frame.py",
"source_template": "video/ltx2_3_runexx_first_last_frame"
```

**Did the agent consume these?** No. The `research.json` shows the adaptation plan matched 5 workflow slices, but **none** from the direct source template `ltx2_3_runexx_first_last_frame.py`. Attempt 003 went to a completely irrelevant IAMCCS workflow. The agent never read its own `prior_path` breadcrumb — the file that literally defines the correct wiring of both `ResizeImageMaskNode` instances.

## 6. Schema Resolvability

`ResizeImageMaskNode` was **resolvable** via the provisional schema system. The agent's `search(focus_types=["ResizeImageMaskNode"])` queries returned:
```python
def ResizeImageMaskNode(widget_0: STRING = ..., widget_1: FLOAT = ..., widget_2: STRING = ..., input_: IMAGE,MASK) -> resized:MASK:
```
No "unknown class" errors. The schema engine worked correctly. The agent simply misused it — kept targeting `widget_1` via `set_node_field` (which rejects widget-backed fields) instead of creating a new node with keyword arguments.

## Root Cause: FIXER

**One-line justification:** The agent never added the missing node because it fixated on editing a field on a surviving sibling node, failed to read the source template breadcrumb that shows the exact two-node wiring, and burned down to unresolvable IAMCCS dependencies when the adaptation plan matched the wrong workflow.

**Breakdown:**
1. **SEARCH** — ✗ The agent found the schema but didn't read `prior_path`/`source_template` files which contain exact wiring. The adaptation `all_slices` never included the direct template.
2. **REFERENCE** — ✗ `prior_path` was passed in the request but never consulted during execution.
3. **FIXER** — ✗ PRIMARY FAILURE. The agent couldn't distinguish "add a new node" from "edit an existing node's field." It kept trying `widget_1 = 2.0` which the system correctly rejected. It never issued a `ResizeImageMaskNode(...)` constructor call with correct kwargs.
4. **VALUE** — N/A (no node was created to have wrong values).
5. **INFRA** — Schema resolver and editor engine worked correctly.
6. **PAIRING** — The LM misidentified which node was the problem node (confused uid=n32 with uid=n33).

**Biggest lever:** Teach the agent to read its own `prior_path` / `source_template` breadcrumbs before attempting edits, and to recognize when the inquiry says "re-add" (`AdditiveRestorer`) versus "edit widget" — it should create a new node, not mutate a surviving node's hidden fields.
