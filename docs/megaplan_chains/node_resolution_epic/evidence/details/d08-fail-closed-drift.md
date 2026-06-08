Now I have all the evidence. Here's the analysis.

---

**(a) Is the doc accurate on this point?**

**Yes.** Section 4 gap #4 correctly identifies that `UnknownNodeSchemaError` (consume.py:311–330) only covers genuinely *unknown* nodes — absent from both the snapshot and the curated fallback. The `class_is_known()` check at consume.py:283 asks "is the class in the cache at all?", NOT "do the cache's declared outputs match the UI-declared outputs?" A node like `ComfyMathExpression` is *known* (it's in the cache with 2 outputs), so `class_is_known()` returns `True`, `require_class_output_count()` passes, and the emitter silently trusts the wrong arity. There is zero code comparing `_ui.outputs` count (ingest-normalized from the workflow JSON) against `class_output_count()` (snapshot). Section 5 #4's proposal is therefore the correct gap-fill.

**(b) Top 2–3 concrete risks or missing pieces:**

1. **The check has three divergent arity sources, not two.** The emitter reads arity from (i) `_ui.outputs` in `_agent_edit_raw_output_names` (emitter.py:1957–1982), (ii) `metadata.output_names` set during ingest from the schema provider (ingest/normalize.py:367–369), and (iii) `class_output_names()` (consume.py:220 via `_resolve_class_type`). These can disagree pairwise. A naïve UI-vs-cache comparison misses the case where `metadata.output_names` (ingest-time schema, which could be live or cached) also disagrees. The detection must triangulate all three, not just two.

2. **The `_schema_output_names_for_unpack` path (emitter.py:4091–4103) skips the UI-declared arity entirely.** It uses `_node_output_names` (which reads `metadata.output_names` — schema-derived, not UI-derived), then falls through to `class_output_names()`. The `_ui.outputs` check only happens in `_agent_edit_raw_output_names` (emitter.py:1957), which feeds a different code path (agent-edit comment rendering). So the unpack-emission path that actually caused the crash **would not benefit** from a check that only compares `_ui.outputs` vs cache — because this path never reads `_ui.outputs`.

3. **False positives from partial output usage.** A workflow may legitimately connect to only 1 of 3 declared outputs. The UI JSON's `outputs` array reflects the litegraph editor state, which could show 3 slots but the workflow only connects edges to 2. The check must distinguish "snapshot arity > UI arity because snapshot is stale" from "UI only declares a subset because unused outputs were trimmed." The signal is: if the snapshot declares *fewer* outputs than the UI (the actual bug case — 2 in snapshot, 3 in UI), it's definitively stale. If the snapshot declares *more*, it's ambiguous.

**(c) Specific recommendation:**

Add an `ArityDisagreementError` (sibling to `UnknownNodeSchemaError`) in `vibecomfy/errors.py`. Then add a new function in `consume.py`:

```python
def check_output_arity_consensus(class_type: str, ui_output_count: int | None) -> int:
```

Called **from `_schema_output_names_for_unpack`** (emitter.py:4091) — this is the single site that determines unpack arity and is the direct cause of the crash. Pass `ui_output_count` extracted from `_agent_edit_raw_output_names` (or `_ui.outputs` length). Inside the check:

- If `ui_output_count is None`: no UI evidence → trust snapshot (current behavior).
- If `class_is_known(class_type)` is False: raise `UnknownNodeSchemaError` (current behavior).
- If `class_output_count(class_type) < ui_output_count`: **raise `ArityDisagreementError`** naming the node, snapshot version, snapshot count, and UI count. This is the definitive stale-snapshot signal (snapshot offers fewer outputs than the workflow declares).
- If `class_output_count(class_type) > ui_output_count`: emit a **warning** (not error), because the extra outputs may simply be unused.
- If equal: return the count.

The second call site in `_agent_edit_raw_output_names` (emitter.py:1981) should also call `require_class_output_count` instead of silently using `class_output_names` when no UI/metadata names exist — it already does the right thing for genuinely-unknown nodes, but should also call `check_output_arity_consensus` for known nodes to catch the disagreement. The fix is ~30 lines, entirely in `consume.py` + two call-site changes in `emitter.py`.