# Case 05 — LoRA Loader (WanVideoLoraSelect)

**TL;DR:** `rejected` (3 attempts) — root: **SEARCH** — the correct golden template (`wanvideo_wrapper_13b_control_lora`) exists in `ready_templates/` with the exact LoRA filename and wiring but was not surfaced in research for attempts 1–2; attempt 3 found it but then timed out during implementation.

---

## 1. Inquiry

> *"I had removed the lora loader step from the workflow and now the style/character LoRA is no longer applied — the output lost the look the LoRA used to provide. Can you add that step back where it belongs so the output is restored? (the node type to re-add is `WanVideoLoraSelect`)"*

(`out/l7-canon10-parallel/cases/bb397a3e8daf/status.json`)

## 2. Golden Feature Node

- **class_type:** `WanVideoLoraSelect`
- **Golden ID:** `98`
- **Widgets values:** `["WanVid/wan2.1-1.3b-control-lora-tile-v0.1_comfy.safetensors"]`
- **Output type:** `WANVIDLORA` → link `12`
- **Target input:** `WanVideoModelLoader` (id `22`), input slot `lora`
- **No other inputs** (no `blocks`, no `prev_lora` — standalone node)

(`out/l7-canon10-parallel/cases/bb397a3e8daf/source/golden.ui.json`, lines 634–668)

The golden template (`ready_templates/video/wanvideo_wrapper_13b_control_lora.py`, line 56) confirms:
```python
wanvideoloraselect = WanVideoLoraSelect(_id='98', lora=LORA_NAME)
```
where `LORA_NAME = 'WanVid/wan2.1-1.3b-control-lora-tile-v0.1_comfy.safetensors'`

## 3. Per-Attempt Analysis

### Attempt 001 — CLARIFY (no candidate)
- **research.json:** Found `wanvideo_wrapper_21_14b_t2v` (uses `WanVideoLoraSelectMulti`) and hivemind workflows — did **not** surface the exact golden template `wanvideo_wrapper_13b_control_lora`.
- **Agent action:** Called `search(focus_types=["WanVideoLoraSelect"])`, got a provisional schema (`widget_0: STRING, widget_1: FLOAT, widget_2: BOOLEAN; socket inputs: prev_lora, blocks`), then **requested clarification** ("Please provide the original LoRA name..."). No edits made.
- **Gate:** `gate_a=false, gate_b=false` — no candidate produced.

### Attempt 002 — LINT/COMPILE ERROR → CLARIFY (no candidate)
- **research.json:** Same search gap as 001 — did not find the correct template.
- **Agent action:** Called `search`, got schema, then attempted:
  ```
  lora_select = WanVideoLoraSelect(widget_0="", widget_1=1.0, ..., prev_lora=None)
  ```
- **Failure:** `socket_input_not_literal_widget` — `prev_lora` is a socket, not a widget. The agent passed `None` as a literal value. Node creation failed. Agent then **requested clarification again**.
- **Gate:** No candidate produced.

### Attempt 003 — TIMEOUT (no candidate)
- **research.json:** CORRECTLY found the golden template slice:
  - `ready_templates/video/wanvideo_wrapper_13b_control_lora.py` with node `98` = `WanVideoLoraSelect` properly wired to model loader's `lora` input.
  - Candidate graph showed `adapt_98`: `{"class_type": "WanVideoLoraSelect", "inputs": {"lora": "WanVid/wan2.1-1.3b-control-lora-tile-v0.1_comfy.safetensors", "low_mem_load": false, "strength": 1}}`.
- **Implementation:** The agent worker **timed out** after 180 seconds (`TimeoutError`). No edits landed.
- **Gate:** `executor_failure` in flow_metadata.

**Summary:** 0 nodes ever landed across 3 attempts. No candidate was ever submitted for oracle evaluation.

## 4. Exact Failure Mode

All three attempts failed at the **structural gate** — no candidate was ever produced (never reached compile/oracle).

- **Attempts 001, 002:** `clarification_required=true` in `implementation_result.json`. The agent concluded it couldn't proceed without the LoRA filename from the user.
- **Attempt 003:** `failure_kind: "TimeoutError"` — `"Agent worker timed out after 180 seconds."` (`attempts/003/implementation_result.json`)

No v2_delta ValueError or oracle rejection occurred. No candidate was ever submit-able.

## 5. Precedent Existence

**Yes — abundant references exist in this repo:**

| Path | Class |
|------|-------|
| `ready_templates/video/wanvideo_wrapper_13b_control_lora.py` | **Exact golden template** — `WanVideoLoraSelect(_id='98', lora='WanVid/...')` |
| `ready_templates/sources/custom_nodes/wanvideo_wrapper/kijai/wan13b_control_lora.json` | Source workflow with the node |
| `ready_templates/video/wanvideo_wrapper_13b_control_lora.layout.json` | Layout with the node wired |
| 22 other files across `ready_templates/` contain `WanVideoLoraSelect` | Various wanvideo templates |

The golden workflow's own `extra.vibecomfy.prior_path` field **explicitly points** to `ready_templates/video/wanvideo_wrapper_13b_control_lora.py`.

**Research finding:** Attempt 001's research did **not** surface this template. Attempt 002's research also missed it. Attempt 003 correctly surfaced it but timed out applying it.

## 6. Schema Resolvability

The schema WAS resolvable. Every `search(focus_types=["WanVideoLoraSelect"])` call returned:
```
# status: provisional_schema  # authoring: literal fields: widget_0...widget_4; socket inputs: prev_lora, blocks
def WanVideoLoraSelect(widget_0: STRING = ..., widget_1: FLOAT = ..., ...) -> lora:WANVIDLORA:
```

**No "unknown class" errors occurred anywhere.** The on-demand resolver (via hivemind workflow schemas) was engaged and working. The agent simply refused to use the provisional schema without a concrete LoRA filename (attempts 001–002) or timed out (attempt 003).

---

## Root Classification

**PRIMARY: SEARCH** — The correct reference template (`wanvideo_wrapper_13b_control_lora`) was not surfaced in research for the first two attempts. The golden workflow's `prior_path` and `source_template` fields explicitly point to it, but the research system returned other templates instead. Even though attempt 003 found it, the first two attempts exhausted the clarification budget and the third timed out. The single biggest lever: **surface the exact case template via `prior_path` — it directly contains the LoRA filename and wiring pattern, making user clarification unnecessary.**
