# Case 06 — Upscale (ResizeImageMaskNode): Failure Analysis

**TL;DR:** Rejected (3 attempts, all `ValidationError`). Root: **FIXER** — a sibling `ResizeImageMaskNode` (id=3) with identical wiring and widget value sat right next to the gap in the same graph; the agent had a perfect in-graph reference yet still produced broken connections. The single biggest lever is improving the fixer's ability to copy a node pattern from a co-existing sibling.

---

## 1. Inquiry

> *"I had removed the upscale step from the workflow and now the output is lower resolution than it should be — it lost the detail the resize/upscale step used to add. Can you add that step back where it belongs so the output is restored? (the node type to re-add is `ResizeImageMaskNode`)"*

**Source:** `out/l7-canon10-parallel/cases/6fb00ab9ef61/status.json` line 6.

---

## 2. Removed Feature Node

From `source/golden.ui.json` lines 42–80:

| Property | Value |
|---|---|
| **node id** | 2 |
| **class_type** | `ResizeImageMaskNode` |
| **widgets_values** | `["scale by multiplier"]` |
| **input** | link 42 ← node 49 (`ResizeImagesByLongerEdge`, longer_edge=1536) |
| **output** | link 2 → node 5 (`ImagePadForOutpaint`) |

The node is the **first** of two identical `ResizeImageMaskNode`s in a `frames_split_view` subgraph. The second one (id=3) was **not removed** and is still present in the broken graph with identical widget: `["scale by multiplier"]`.

---

## 3. Per-Attempt Analysis

### Attempt 001 — Timeout
- **Classification** (`attempts/001/classification.json`): `research: false`, `route: revise`, `task: edit_graph`
- **Result** (`attempts/001/implementation_result.json`): **TimeoutError** — agent timed out after 180s, graph unchanged.
- **No payload produced** — the model never returned edits.

### Attempt 002 — Wrong Target
- **Classification** (`attempts/002/classification.json`): `research: false`, `plan_summary`: *"Reconnect the existing ResizeImageMaskNode (id=3) into the image processing pipeline..."*
- **Result** (`attempts/002/implementation_result.json`): **ValidationError** — `"Missing stable link from port"`
- **Analysis:** The agent confused the surviving node (id=3) with the removed one (id=2). It tried to re-wire id=3, which was already correctly wired, producing dangling links instead. 6 LLM calls consumed.

### Attempt 003 — Correct Intent, Broken Execution
- **Classification** (`attempts/003/classification.json`): `research: false`, plan correctly says *"Re-add the ResizeImageMaskNode..."*
- **Result** (`attempts/003/implementation_result.json`): **ValidationError** — same `"Missing stable link from port"`
- **Analysis:** Only 3 LLM calls, low token spend ($0.0028). The agent **did** attempt to add a new node but produced broken wiring. The classifier didn't push research (`research: false`), so no reference context was supplied. However, an identical-node template was **on-screen** (node id=3).

---

## 4. Exact Failure Mode

All non-timeout attempts failed at the **structural gate**: `ValidationError` with `"Missing stable link from port"` (attempts 002 and 003).

- **No v2_delta ValueError** — the delta was not the issue.
- **No oracle rejection** — candidate never got that far.
- **No "unknown class"** — schema resolver was not needed; `ResizeImageMaskNode` was already present in the graph via id=3.
- **No receipt errors** — `proof/receipts/` directory does not exist (no receipts generated for this case).

The `proof/baseline.json` confirms the **golden compiles clean** (output_reachable=true, 60 nodes, 83 links).

---

## 5. Precedent Existence

**Yes — abundant.** There are **43 files** in `ready_templates/` containing `ResizeImageMaskNode`. Most critically:

1. **`ready_templates/video/ltx2_3_runexx_first_last_frame.py`** — the **exact template** this case derives from. Lines 98–106 show both nodes with `resize_type='scale by multiplier'` wired via `input` positional arg. The `frames_split_view` subgraph is documented at lines 91–95.
2. **`ready_templates/video/ltx2_3_runexx_first_last_frame.layout.json`** — layout confirms `_vibecomfy_schema_provider: "object_info_index"` (schema was resolvable).
3. **`ready_templates/sources/custom_nodes/ltxvideo/runexx/LTX-2.3_FLF2V_First_Last_Frame.json`** — the source JSON the template materializes from.

**Did the agent find any?** No. All three attempts had `research: false` in classification. The classifier opted to skip research entirely (route: "revise", which edits in-place without fetching references). The agent never read the template files.

---

## 6. Schema Resolution

The on-demand schema resolver was **not engaged** for this node. Reason: `ResizeImageMaskNode` (id=3) was already in the broken graph, so the resolver had schema from the existing node. No `"unknown class"` or unresolved signals appear in any artifact. The baseline (`proof/baseline.json`) shows `"compile_error": "SOFT-PASS"` — the graph compiles structurally.

---

## 7. Root Classification

**PRIMARY: FIXER** — The fixer could not correctly re-add and wire a `ResizeImageMaskNode` despite having a **perfect in-graph reference** (the surviving sibling node id=3 at `pos [1560, 368]` with identical type `ResizeImageMaskNode` and widget `"scale by multiplier"`). The classifier's `research: false` decision didn't help (SEARCH is a secondary contributor), but the fixer's inability to copy a trivial pattern from a co-located node is the decisive bottleneck. Attempt 002 confused node identities; attempt 003 produced broken links despite correct intent. The fixer needs to recognize and replicate co-existing sibling nodes as implicit templates.

**Secondary: SEARCH** — Even if fixer improved, the classifier should have enabled research (`research: true`) for an additive-edit case where a specific node type is named in the inquiry. The reference template was available at a known path.
