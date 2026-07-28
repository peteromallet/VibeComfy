# Case 01: refinement_pass — Rejected

**TL;DR:** Verdict **rejected** (3 attempts). Root class **SEARCH** — research surfaced only one of two `ManualSigmas` sigma schedules, so the agent re-added the correct node type and wiring but with the **wrong refinement sigma schedule** (copying the first-stage schedule instead of the shorter refinement schedule).

---

## 1. The Inquiry

```
"I had removed the refinement pass step from the workflow and now the refinement pass is gone — the output is rougher and less polished than the two-stage result used to be. Can you add that step back where it belongs so the output is restored? (the node type to re-add is `ManualSigmas`)"
```

*Source: `status.json` line 6*

---

## 2. The Removed Feature Node (Golden)

The golden workflow (`source/golden.ui.json`) has **two** `ManualSigmas` nodes — the broken workflow (`broken/broken.ui.json`) retained only the first and removed the second:

| Node | vibecomfy_id | Class Type | Widget (sigma schedule) | Golden ID |
|------|-------------|-----------|------------------------|-----------|
| n11 (kept) | `ManualSigmas_30` | `ManualSigmas` | `"1.0, 0.99375, 0.9875, 0.98125, 0.975, 0.909375, 0.725, 0.421875, 0.0"` | 4984 |
| **n12 (removed)** | `ManualSigmas_31` | `ManualSigmas` | **`"0.85, 0.7250, 0.4219, 0.0"`** | 4985 |

Wiring in golden: n11 (4984) → link 42 → first SamplerCustomAdvanced (4829, slot 3 SIGMAS).  
n12 (4985) → link 43 → **second** SamplerCustomAdvanced (4971, slot 3 SIGMAS) — the refinement pass sigma source.

The broken workflow has last_node_id=5000 (LTXFloatToInt), link 42 exists, **link 43 is absent**.

*Sources: `source/golden.ui.json` lines 1744–1805 (`ManualSigmas_30`/`_31`), links 42–43; `broken/broken.ui.json` confirms n11 present, n12 absent.*

---

## 3. Per Attempt: What the Agent Actually Re-added

### Attempt 001
- **Added node**: id=5001, type=`ManualSigmas`, schema_provider=`workflow_json_provisional`
- **Widgets**: `["1.0, 0.99375, 0.9875, 0.98125, 0.975, 0.909375, 0.725, 0.421875, 0.0"]` — **matches first-stage schedule, NOT the refinement schedule**
- **Wiring**: 5001(0 SIGMAS) → link 48 → 4971(3 SIGMAS) — **correct target** (second-stage SamplerCustomAdvanced)
- **Verdict**: rejected (gates_passed=4/6, candidate compiled SOFT-PASS)

### Attempt 002
- **Did NOT add a ManualSigmas**. Added `LTXVTiledVAEDecode` (id=5000) instead. last_node_id=5000 (unchanged from broken). Completely missed the target.
- **Verdict**: rejected

### Attempt 003
- **Identical to attempt 001**: id=5001, same wrong sigma schedule, same correct wiring.
- **Verdict**: rejected

*Sources: `attempts/001|003/implementation_result.json` nodes[5001]; `attempts/002/implementation_result.json` links[47] shows LTXVTiledVAEDecode.*

---

## 4. The Exact Failure

**Failure type: Oracle rejection** (structural gates passed, but oracle found delta mismatch).

- Receipt (`receipts/001_complete.json`): `"verdict": "rejected"`, `"gates_passed": 4`, `"gates_total": 6`
- Compilation: `"candidate_execution_safe": true`, `"candidate_compile_error": "SOFT-PASS ... Node 5000 (LTXFloatToInt) has unknown input rounding."` — this is a pre-existing soft issue, not the rejection cause.
- No `v2_delta` ValueError found. The oracle compared the candidate graph to the golden and **detected the sigma schedule mismatch** (candidate has 9-value schedule where golden requires 4-value refinement schedule).

The candidate compiled and executed safely but produced incorrect widget values, causing oracle rejection.

*Sources: `receipts/001_complete.json`; `proof/baseline.json`.*

---

## 5. Precedent (Do References Exist?)

**Yes, multiple references exist:**

1. `ready_templates/sources/custom_nodes/ltxvideo/lightricks_2_3/LTX-2.3_T2V_I2V_Two_Stage_Distilled.json` — the **canonical source** for this exact workflow, containing **two** `ManualSigmas` nodes: id=4984 (9-value schedule for first stage) and id=4985 (4-value schedule `"0.85, 0.7250, 0.4219, 0.0"` for refinement stage).
2. An external workflow (`LTX 2.3 T2V I2V Single Stage Distilled Full.json`) also contains `ManualSigmas` with the 9-value schedule.

**Research findings per attempt:**
- **Attempt 001**: Research (`implementation_payload.json`) found the ready_template `video/ltx2_3_lightricks_two_stage` (relevance_score=873, source_workflow_available=true), **but the key_values only captured one sigma schedule**: `ManualSigmas=1.0, 0.99375, 0.9875, 0.98125, 0.975, 0.909375, 0.725, 0.421875, 0.0` — this came from the external single-stage workflow, not from the two-stage source. The refinement sigma schedule `0.85, 0.7250, 0.4219, 0.0` was **not surfaced in key_values**.
- **Attempts 002 & 003**: Similar research patterns. The ready_template was found each time but the **second (refinement) sigma schedule was never extracted into research key_values**.

The research found the correct template but the key_value extraction only captured one of the two `ManualSigmas` nodes.

*Sources: `attempts/001/implementation_payload.json` research_sources (key_values); `ready_templates/sources/custom_nodes/ltxvideo/lightricks_2_3/LTX-2.3_T2V_I2V_Two_Stage_Distilled.json` lines 792–840.*

---

## 6. Schema

The re-added node used `schema_provider: "workflow_json_provisional"` (attempts 001, 003) rather than `"object_info_index"`. This indicates the on-demand schema resolver was **not engaged** — the schema was synthesized from the workflow JSON rather than resolved from the node registry. No "unknown class" errors occurred because `ManualSigmas` is a core ComfyUI node and its schema is well-known, but the provisional schema path suggests the resolver pipeline didn't validate the node's widget types against the installed/computed schema.

---

## Root Classification

### PRIMARY: **SEARCH**

**Justification:** The ready_template source workflow (`LTX-2.3_T2V_I2V_Two_Stage_Distilled.json`) exists in the repo and contains **two** `ManualSigmas` nodes with distinct sigma schedules. The research pipeline found this template (relevance_score=873, source_workflow_available=true) but **only extracted one sigma schedule into key_values** — the single-stage schedule from a different workflow. The refinement sigma schedule (`0.85, 0.7250, 0.4219, 0.0`) was never conveyed to the fixer. The fixer correctly added a `ManualSigmas` node wired to the second-stage sampler but defaulted to the only sigma schedule it saw (the first-stage one). This is a **search/feature-extraction** gap: the evidence existed but was incompletely surfaced.

### Secondary: VALUE

The agent got the node type right, the wiring right, but the **sigma widget values wrong**. Even with perfect search, if the research doesn't differentiate between first-stage and refinement sigma schedules, the fixer cannot produce the correct values.
