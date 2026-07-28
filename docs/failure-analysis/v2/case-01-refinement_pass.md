# Case 01 — Refinement Pass (ManualSigmas)

**TL;DR: VALUE failure — agent correctly re-added the ManualSigmas node type and wiring but copied the FIRST-pass sigma schedule (9 values) instead of the SECOND-pass schedule (4 values). The reference exists plainly in the ready template. Biggest lever: instruct the fixer to extract node-specific widget values from the source template by node_id, not just type.**

---

## 1. The Inquiry

> *"I had removed the refinement pass step from the workflow and now the refinement pass is gone — the output is rougher and less polished than the two-stage result used to be. Can you add that step back where it belongs so the output is restored? (the node type to re-add is `ManualSigmas`)"*

**Source:** `out/l7-canon10-stabilized/cases/7b3de797e29a/status.json`, line 6.

The inquiry explicitly names `ManualSigmas` as the node type to re-add.

---

## 2. Removed Feature Node

The golden workflow (`source/golden.ui.json`) contains **two** `ManualSigmas` nodes:

| Node ID | vibecomfy_id | Widget (sigmas string) | Wiring |
|---------|-------------|-----------------------|--------|
| 4984 | `ManualSigmas_30` | `"1.0, 0.99375, 0.9875, 0.98125, 0.975, 0.909375, 0.725, 0.421875, 0.0"` | Link 42 → SamplerCustomAdvanced 4829, slot 3 (SIGMAS) — **first pass** |
| 4985 | `ManualSigmas_31` | `"0.85, 0.7250, 0.4219, 0.0"` | Link 43 → SamplerCustomAdvanced 4971, slot 3 (SIGMAS) — **second pass** |

The broken workflow (`broken/broken.ui.json`) removed **node 4985** (second-pass sigma node) and link 43. Node 4984 (first-pass) survived. The agent needed to re-add the second-pass ManualSigmas only.

---

## 3. Per Attempt — What Was Re-Added

### Attempt 001 — NO-OP
- **Result:** `"No safe revise candidate is available, so I left the graph unchanged. Evidence: 1 missing required input(s)."`
- **Gate failure:** All structural gates (`ir_validate_ok`, `lower_ok`, `python_load_ok`, `queue_validate_ok`, `ui_fidelity_ok`) = false. The revision evidence pipeline found no candidate (`no_changes`).
- **Root:** The agent classified this as `revise` (edit_graph) with `research: false`. It never fetched the schema; the v2_delta registry produced zero candidates because the broken graph's second-pass SamplerCustomAdvanced (4971) already had input slot 3 unlinked — the diff engine didn't see a "missing" node. It was an infra-gap in the candidate-generation pipeline for additive patterns. (Attempt 001 is INFRA: the v2_delta registry couldn't produce an additive candidate for a missing sigma node.)

### Attempt 002 — Added ManualSigmas with WRONG sigma schedule
- **Node added:** `id=5001`, type `ManualSigmas`, vibecomfy_id `ManualSigmas_0`, uid `n36`.
- **Wiring:** Output → Link 48 → SamplerCustomAdvanced 4971, slot 3 (SIGMAS) — **correct wiring**.
- **Widget values:** `["1.0, 0.99375, 0.9875, 0.98125, 0.975, 0.909375, 0.725, 0.421875, 0.0"]`
- **Schema provider:** `workflow_json_provisional` (not the on-demand resolver — the agent draft-created the node from scratch rather than looking up the schema via the resolver).
- **Comparison to golden:** The golden second-pass node (4985) uses `"0.85, 0.7250, 0.4219, 0.0"` — a 4-value refinement schedule. The agent used the **9-value first-pass schedule** from node 4984.

### Attempt 003 — Identical to attempt 002
- Same node 5001, same wrong sigma schedule, same wiring. The fixer re-requested with the same research result and produced the same payload.

---

## 4. Exact Failure Mode

Both attempts 002 and 003:
- **Gates passed:** 4/6 (structural compilation succeeded — `candidate_execution_safe: true`)
- **Compile error:** SOFT-PASS only (lora_name issue, unknown rounding input — pre-existing warnings, not blocker)
- **Verdict:** `rejected` — the **oracle** rejected.

The receipts (`receipts/002_complete.json` and `receipts/003_complete.json`) confirm: `"verdict": "rejected", "gates_passed": 4, "gates_total": 6`.

The rejection was **not** a structural-gate failure or v2_delta error (the pipeline stabilization held). The oracle determined that the re-added node did not match the golden: **correct type + correct wiring, but wrong sigma schedule**.

---

## 5. Precedent Existence & Consumption

**Precedent exists.** The ready template at:
- `ready_templates/video/ltx2_3_lightricks_two_stage.py` (line 96): `manualsigmas_2 = ManualSigmas(_id='4985', sigmas='0.85, 0.7250, 0.4219, 0.0')`
- Source workflow: `ready_templates/sources/custom_nodes/ltxvideo/lightricks_2_3/LTX-2.3_T2V_I2V_Two_Stage_Distilled.json`

**Did the agent find it?** Yes. Both attempt 002 and 003's `implementation_payload.json` (research context) show successful retrieval of the primary template (`video/ltx2_3_lightricks_two_stage`) with `relevance_score: 730` and `strong_relevance_match: false` (for 002) and `relevance_score: 526` (for 003). The adapt pattern `two_pass_refinement` was tagged. The `prior_path` and `source_template` breadcrumbs in the graph metadata were also available.

**Did the agent consume them correctly?** No. The research produced the correct template and source workflow paths, but the agent extracted the **first-pass** sigma schedule (9 values from node 4984) instead of the **second-pass** schedule (4 values from node 4985). The agent used `workflow_json_provisional` schema provider rather than resolving the actual schema or extracting values by node ID from the template.

---

## 6. Schema Resolution

The `ManualSigmas` node type was correctly resolved — no "unknown class" errors. The schema provider `workflow_json_provisional` indicates the agent created the node from a draft/provisional schema rather than using the on-demand schema resolver. The node compiled and passed structural gates. The failure was purely in **widget value accuracy**, not schema resolution.

---

## Root Class: VALUE

**Primary verdict:** VALUE failure.

**One-line justification:** The agent correctly identified the node type (ManualSigmas), correct wiring (SIGMAS output to second-pass SamplerCustomAdvanced slot 3), and correct structural scope, but inserted the **wrong sigma schedule** (9-value first-pass schedule instead of 4-value second-pass schedule). The precedent existed in the ready template with exact values — the agent found it but failed to extract node-specific widget values by ID.

**Secondary class:** REFERENCE — the agent found the precedent document but failed to extract the correct sigma values by node_id. The research context retrieved the right template but the fixer didn't drill into per-node widget values.

**Biggest lever:** When re-adding a specific node that exists in a source template with a known node_id (e.g., `4985`), the fixer should extract widget values by node_id from the template AST or source JSON rather than inferring them. The golden schema for ManualSigmas takes a `sigmas` string — without the correct second-pass schedule the refinement pass behaves identically to the first pass, neutralizing the two-stage benefit.
