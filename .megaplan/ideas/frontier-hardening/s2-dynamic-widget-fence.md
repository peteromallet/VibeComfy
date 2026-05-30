# S2 — dynamic-widget-fence: the §6 refusal fence becomes a real module

## Outcome
Dynamic / dict-shaped community nodes (rgthree Power Lora Loader, Impact combinatorial nodes, …) either
**round-trip faithfully** or are **refused / pinned-opaque with a typed reason** — never silently
corrupted. The fence keys on *widget-shape divergence*, not just class presence.

## Why (the gremlin)
Roadmap §14 lens 3. `object_info` is a static snapshot that LIES about runtime-dynamic nodes: Power Lora
Loader's snapshot is `[None, None]` (count 2), but real graphs carry ~8 dict-shaped widget rows. The
emitter records `widget_length_check = "overflow 8>2"` and **nothing raises** — the codec ships a
mis-shaped graph with a provenance breadcrumb no gate reads. The §6 "refuse-with-reason / per-region
degradation" fence is **data-complete but gate-incomplete**: the recovery report already carries
`schema_less` / `widget_length_check` / confidence per node; nothing consumes it as a refusal.

## Scope — IN
- A **first-class IR representation for dict/row-shaped `widgets_values`** (dynamic-count widgets), so the
  rows are modeled, not positionally flattened.
- The **§6 fence as a real emit-path module**: promote `overflow` / `schema_less` / low-confidence into a
  HARD refusal keyed on widget-shape divergence (editor widget count ≠ schema-derived), with a typed reason.
- **Per-region graceful degradation**: edit the proven region, pin the unprovable node(s) opaque (reuse the
  existing `opaque()` carrier), refuse-with-reason on what won't be touched — a per-node verdict map, not a
  whole-graph boolean.
- The **Power Lora Loader falsification test** (the §14 probe) as a committed regression.

## Scope — OUT
- The GENERIC corruption-detector / refusal-spine — scratchpad-emitter **m5 owns that**. This sprint owns
  the widget-SHAPE fence + dict-widget IR; expose a clean interface m5's detector can call. Do NOT rebuild it.
- Get/Set virtual-wire semantics (m2/m5 own those).

## Locked decisions
- The fence is a per-node verdict map (safe-to-regenerate vs must-pin-opaque), not a single `strict` boolean.
- Dict/row widgets get a real IR type; positional flattening is the bug, not the contract.

## Open questions (resolve in planning)
- The dict-widget IR shape (how rows + per-row fields are modeled and round-tripped).
- The refuse-vs-pin-opaque boundary: when is a node safe-to-pin vs must-refuse-whole-graph.

## Constraints
- Offline/deterministic. Must inherit S1's trustworthy oracle gate.
- Must not regress the currently-passing official families.

## Done criteria
- The music-video Power Lora Loader graph `ingest→emit→convert_ui_to_api` **round-trips faithfully OR is
  refused with a typed reason** — never the silent `overflow` ship.
- Corpus-wide: count of `widget_length_check` containing `overflow` that reach an emitted graph → **0**.
- A dynamic-input node outside the proven set is pinned-opaque + reported, with the rest of the graph editable.

## Touchpoints
- `vibecomfy/porting/ui_emitter.py` (widget builders, `_compacted_widget_names`, the fence),
  `vibecomfy/schema/provider.py` (shape derivation), `vibecomfy/ingest/normalize.py`, IR types
  (`VibeNode.widgets`), `vibecomfy/blocks/subgraph.py` (`opaque()` carrier), `tests/`.

## Anti-scope
- Don't build the generic detector (m5). Don't refactor the schema-provider precedence beyond what the
  shape-divergence check needs. Don't touch Get/Set normalization.

## Handoff artifact
The fence module interface (per-node verdict map + typed refusal reason) that scratchpad-emitter m5's
corruption-detector and s5's felt-delta gate both call.
