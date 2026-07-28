# Case 00 — Upscale (ImageScaleBy) — PASSED (alternative_repair)

**TL;DR: This is the trivial baseline — and it worked perfectly. The agent never needed to search. The node type was named explicitly in the user query (`ImageScaleBy`), the graph was a simple 2-node linear chain (LoadImage → SaveImage), and the widget values (`lanczos`, 2.0) were default/sensible. The classifier routed to `revise` (not `research`), skipped all retrieval, and the fixer just spliced one node into the middle. This case tells us the minimum viable path: **unambiguous node type + linear insertion point + obvious widget defaults = zero research needed**.

---

## 1. The Inquiry

> *"I had removed the upscale step from the workflow and now the output is lower resolution than it should be — it lost the detail the resize/upscale step used to add. Can you add that step back where it belongs so the output is restored? (the node type to re-add is `ImageScaleBy`)"*

## 2. What Was Re-added vs. Golden

| Aspect | Golden (node id 2) | Agent Repair (node id 4) | Match? |
|---|---|---|---|
| **Type** | `ImageScaleBy` | `ImageScaleBy` | ✅ Exact |
| **Widgets** | `["lanczos", 2.0]` | `["lanczos", 2.0]` | ✅ Exact |
| **Input** | link 1 from LoadImage IMAGE | link 4 from LoadImage IMAGE | ✅ |
| **Output** | link 2 to SaveImage IMAGE | link 5 to SaveImage IMAGE | ✅ |
| **Position** | (520, 0) | (400, 0) | ⚠️ X-offset — functionally irrelevant |
| **Size** | (320, 74) | (320, 180) | ⚠️ Height differs — no semantic impact |

The wiring topology is identical: LoadImage → ImageScaleBy → SaveImage, all IMAGE type. The agent used sequential link/node IDs (4, 5) and placed the node at a slightly different X coordinate, which is cosmetic. **The semantic repair is pixel-perfect.**

## 3. Why This Succeeded

**Research was skipped entirely.** The `classification.json` shows: `research: false`, `effort: low`, `route: "revise"`, `task: "edit_graph"`. The classifier decided this was simple enough to handle from the agent's inherent knowledge, no external reference needed.

Three factors aligned:

1. **Explicit type naming.** The query literally said `ImageScaleBy` in parentheses. No ambiguity about what node to add — contrast this with cases where the agent had to infer the node family from a vague description like "make it look better."

2. **Trivial graph topology.** The broken workflow had exactly two nodes (LoadImage → SaveImage). The insertion point was unambiguous: between them. `ImageScaleBy` has one input (`image: IMAGE`) and one output (`IMAGE`), so wiring was deterministic.

3. **Obvious widget defaults.** The golden used `lanczos` and `2.0` — these are the ComfyUI defaults for `ImageScaleBy`. The agent didn't need to discover them; they're what you'd expect from a reasonable upscale step.

The on-demand schema resolver (`_vibecomfy_schema_provider: "object_info_index"`) resolved the node's IO schema cleanly, so there was no "unknown class" failure. The `prior_path` pointing to `ready_templates/image/basic_image_upscale.py` existed but was never consulted — it wasn't needed.

## 4. What This Tells Us About the Minimum Viable Evidence Path

Case 00 is the **happy-path floor**: zero research, zero references, zero precedent consumption. The minimum viable evidence path for an additive restore is:

1. **The node type is explicitly named in the query** → no search needed.
2. **The insertion point is structurally forced** (linear chain, only one place to go) → no topology inference needed.
3. **The widget values are defaults or trivially derivable from the node name** → no parameter discovery needed.
4. **The schema resolver works** → no "unknown class" roadblock.

When any of these conditions degrade — type is ambiguous, insertion point is underdetermined, values are non-obvious — the agent must fall back to research. Case 00 shows that if the classification system correctly identifies a low-effort edit, the pipeline can execute it in one shot with zero retrieval cost. The failure mode to watch for in sibling cases is the classifier **incorrectly** routing a non-trivial case through `revise` (where lack of research causes wrong values) or, conversely, routing a trivial case through `research` (wasteful but not harmful).
