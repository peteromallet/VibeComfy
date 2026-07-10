# Diff-over-Original: Bridge Design Note

**Status:** Design note — scoped bridge investigation, not an active implementation.
**Date:** 2026-07-10
**Context:** Agent-Edit Correctness Sprint (Phases 1–4 concrete contract fixes)
**North Star reference:** [solution-spec.md](agent-edit/solution-spec.md), [concrete-tree.md](agent-edit/concrete-tree.md)

---

## 1. What "diff-over-original" means

The **diff-over-original** approach preserves the user's original LiteGraph UI JSON
as the authoritative substrate and applies only a structured field diff (a typed
delta of `set_widget`, `connect`, `add_node`, etc.) to produce a candidate. The
candidate is the verbatim original plus exactly the declared changes — no lossy
canonicalization pass, no full-graph re-serialization, no schema-dependent
reconstruction of untouched nodes.

This is the architecture described in the existing concrete-tree solution spec
(S1/S2) and the solution-spec `apply(original_ui, delta) -> candidate_ui` model.
It is the Epic North Star's preferred long-term path.

---

## 2. How it could reduce sampler-settings brittleness

Today's edit path:

1. Ingest the original workflow → canonical Python IR (lossy — lowers helpers,
   renumbers ids, strips unknown nodes).
2. Agent reads the canonical view and emits a full-file replacement.
3. The replacement is re-serialized through the same lossy path.
4. Widget deltas are inferred by diffing the full-file replacement against the
   original, using positional `widget_N` slot mapping.

**Sampler-settings brittleness** enters at step 4: a `widget_N` index can shift if the
schema changes, a new input is added, or the canonical rebuild reorders fields. An
edit to `widget_3` (which is `sampler_name` for today's KSampler) silently hits the
wrong slot under schema drift.

Under **diff-over-original**, steps 2–4 become:

1. Agent sees a uid-annotated projection of the *original* UI (field names by
   schema, not `widget_N`).
2. Agent returns a typed delta: `set_widget { uid: "KS-42", field: "sampler_name", value: "euler" }`.
3. `apply(original_ui, delta)` mutates only the targeted field — no position-based
   slot resolution, no re-serialization of untouched nodes.

The mechanic that eliminates brittleness: **field identity is by semantic name, not
widget slot index.** A diff named by `sampler_name` always hits the correct widget
regardless of schema-internal ordering, because the apply function resolves through
the schema's `compact_widget_names_for_node` mapping, not through a positional
`widgets_values[]` offset.

Unchanged KSampler nodes (the most common case for a single-edit turn) carry their
entire original `widgets_values` array verbatim — no risk of accidentally reordering
`control_after_generate` relative to `seed` during a re-serialize.

---

## 3. This is a bridge, not a replacement

The current Shared Prompt/Engine Contract (the `settings_contract.py` helper +
`edit_batch_memory.py` prompt vocabulary + `apply_field_aliases.py` engine
diagnostics + `edit_batch_reports.py` diagnostic detail formatting) is the
**canonical correctness path for this sprint**. It works within the existing
full-file-replacement architecture and is producing passing deterministic
regression tests (see task T5: 17 KSampler batch-path regression tests passing).

Diff-over-original is a **documented bridge direction** for a future phase when we
cut over to a delta-based edit contract. It is not a competing contract. Covers
the same fields, the same vocabulary, the same KSampler widget set — just resolved
through a different apply mechanism.

Concretely, the shared contract's `compact_widget_names_for_node` mapping (which
maps `sampler_name` → `widget_3`, `scheduler` → `widget_4`, etc.) is exactly the
bridge that makes both architectures consistent: it gives the current full-file path
semantic field resolution, and it provides the field-to-slot mapping that a future
diff-over-original `apply` function would use.

> **Bridge framing (per SD3):** This diff-over-original investigation is scoped to
> a design note and must not block the concrete correctness fixes in Phases 1–4.
> The North Star allows scoped temporary bridges when documented and tested.

---

## 4. Avoid implementation unless hard tests require it

The Epic assumptions explicitly state:

> "Diff-over-original work is scoped as a bridge/design note and does not
> contradict the Epic North Star."

Implementation is deferred because:

1. **The existing full-file path is passing correctness gates.** The 35+ KSampler
   deterministic regression tests (from T5), the engine diagnostic tests (T3/T4),
   the prompt vocabulary tests (T2), and the browser lifecycle tests (T10/T11/T12)
   all validate that the current architecture produces correct sampler-settings
   edits with the right field names, enum validation, and queue-validation gating.

2. **A cut-over to diff-over-original would require the entire Phase 1–2 stack**
   (identity-at-ingest, address-preserving read view, typed delta prompt, pure
   `apply(original_ui, delta)`, full-UI untouched-outside-delta assertion) which is
   multiple sprints of work. Blocking this sprint on that cut-over would violate
   SD3.

3. **The hard correctness tests for this sprint** (deterministic batch-REPL
   randomization, enum/field validation diagnostics, browser-normalized diagnostic
   presentation) **pass under the current architecture.** No failing test requires
   a diff-over-original apply to pass.

If a future hard test were to require diff-over-original (e.g., a regression that
proves untouch nodes must be byte-identical to the original, which the current
lossy path cannot satisfy on certain unknown-node-pack graphs), this design note
provides the documented path forward: extend `settings_contract.py` with a
`apply_field_diff(original_ui, delta) -> candidate_ui` function that uses the same
`compact_widget_names_for_node` mapping already in place.

---

## 5. Relationship to other sprint artifacts

| Artifact | Relationship |
|---|---|
| `settings_contract.py` (T1) | Supplies the field-name resolution that both current and diff-over-original apply paths share. |
| `edit_batch_memory.py` (T2) | Uses the shared contract for field names; the same named vocabulary feeds a diff-over-original delta. |
| `apply_field_aliases.py` (T3) | Engine diagnostics expose `valid_fields` in compact names; these names are already the diff-over-original field keys. |
| `edit_batch_reports.py` (T4) | Diagnostic detail (choices, valid_fields) is format-independent — applies to both architectures. |
| `widget_shape_fence.py` (T7) | The `PIN_OPAQUE` path for collateral nodes is a micro-example of the diff-over-original principle: carry raw UI forward for untouched nodes. The fence logic is a stepping stone to full-substrate preservation. |
| `concrete-tree.md` | Existing design doc covering the full Phase 0–4 migration to diff-over-original. |
| `solution-spec.md` | The root-level spec for the delta-based architecture. |

---

## 6. Summary

- **Diff-over-original eliminates positional widget-slot brittleness** by resolving
  field edits through semantic names (`sampler_name`, `seed`, `steps`) rather than
  `widget_N` offsets, and by carrying the original `widgets_values` array verbatim
  for untouched nodes.
- **It is a documented bridge, not a replacement** for the shared prompt/engine
  contract that this sprint establishes and validates.
- **Implementation is deferred** unless future hard tests require it — none of the
  current deterministic regression tests need it, and the current architecture
  passes all correctness gates.
- **The shared contract's field-name mapping is the common foundation** that makes
  both the current full-file path and a future diff-over-original path consistent
  with each other.
