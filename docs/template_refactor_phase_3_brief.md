# Phase 3 sprint brief — VibeComfy template refactor: emitter readability + Family P resolution

Drafted 2026-05-24 after Phase 1 (family fixes A-K) and Phase 2 (in flight: doctor readability, def-build cosmetics, public input naming) addressed structural and cosmetic gaps. Phase 3 attacks the **two emitter-readability gaps Phase 1's emitter improvements left behind** plus the **structural path to resolve Family P templates** that surfaced today via `port reemit` (commit `05219ed`).

## 1. Outcome

After Phase 3:

- Generated templates no longer carry `WIDGET_N = 'value'` opaque constants; they carry semantic constants (`VAE = 'vae'`) hoisted only when re-used.
- Node call sites use named kwargs where the alias is known (`node.threshold=False`) instead of positional `widget_0=False`.
- `GetNode`/`SetNode` broadcast pairs and `Reroute` passthroughs are resolved at IR-transform time and never reach emission.
- Family P templates (no source workflow, or broken source) have a documented, tested resolution path that uses `port reemit` + targeted source patches.
- The 5 RuneXX runexx templates re-emitted today are cleaner, smaller, and the remaining unresolved widgets / opaque UUIDs are documented (or fixed at source).

## 2. Scope (IN)

Hour estimates are honest. Lower-end design choices priced.

### Block A — Broadcast helper resolution (Family F+)

- **A1.** Implement `_resolve_broadcast_helpers()` IR pre-emission pass that inlines `SetNode`/`GetNode` pairs by matching their `widget_0` slot name. For each `SetNode(widget_0=name, value=X)`, find all `GetNode(widget_0=name)` consumers, rewrite their downstream edges to point at `X`, then drop both nodes. **3-5 h**.
- **A2.** Extend the existing `_resolve_helper_nodes_for_emission()` (Phase 1 T7) to also fold `Reroute` nodes when they arrive as opaque `raw_call('Reroute', ...)` — currently only typed Reroute is recognized. **1-2 h**.
- **A3.** Add tests covering each helper class: a typed Reroute, a `raw_call('Reroute', ...)`, a SetNode/GetNode pair, and a chain of three Reroutes. **1-2 h**.

### Block B — Widget naming improvements

- **B1.** Level 1 — name constants by their *value*, not their slot. `WIDGET_0 = 'vae'` becomes `VAE = 'vae'`. Slugify the value (`vae_audio` → `VAE_AUDIO`); dedup with numeric suffix only on real collision. **2-3 h**.
- **B2.** Level 2 — don't hoist single-use strings. If a string constant is referenced exactly once, inline it at the call site. **2-3 h**.
- **B3.** Snapshot tests + regenerate all 64 templates. **1-2 h**.

### Block C — Widget kwargs at call sites

- **C1.** When `widget_aliases.py` (or the object_info cache) knows the named field for a positional widget on a class, emit the kwarg with the named field instead of `widget_N`. Example: `LTXVPreprocessMasks(widget_0=False, widget_1=False, widget_2='max')` → `LTXVPreprocessMasks(invert_input_masks=False, fill_masks=False, edge_processing='max')`. **3-5 h**.
- **C2.** When the alias is unknown, fall through to `widget_N` (current behavior) but emit a readability diagnostic (`widget_alias_unknown`) so Phase 2's doctor tier can flag it. **1 h**.

### Block D — Runtime object_info population

- **D1.** New CLI: `vibecomfy nodes refresh-object-info [--server-url URL]` that queries a running Comfy server's `/object_info` endpoint and writes per-pack snapshots to `vibecomfy/porting/cache/object_info/<pack>@<version>.json`. Optional vendoring step — agents/CI may run it once when a pack is added. **3-5 h**.
- **D2.** Hook `port convert` and `port reemit` to consult the refreshed cache when resolving widget aliases. Falls back to current `widget_aliases.py` static map if cache miss. **2-3 h**.

### Block E — Family P resolution sprint

- **E1.** Run `port reemit --all-family-p` after Blocks A/B/C land. Verify the runexx-5 templates re-emit with named kwargs, no `WIDGET_N` constants, and no opaque GetNode/SetNode/Reroute. **1 h**.
- **E2.** For the 2 templates in `docs/template_provenance_gaps.md` (`first_last_raw_video_guide`, `wanvideo_wrapper_22_wan_animate_preprocess_kijai`): fetch source workflows where available (e.g. RuneXX repo per Phase 2 evidence: `https://huggingface.co/RuneXX/LTX-2.3-Workflows`), patch missing required widgets (`VHS_VideoCombine` filename_prefix/format/loop_count/etc.), commit under `workflow_corpus/community/runexx/`, run full `port convert`. **2-3 h**.

### Block F — RuneXX upstream coordination

- **F1.** Open an issue against `RuneXX/LTX-2.3-Workflows` documenting the unnamed subgraph UUIDs in `Talking-Avatar-TTS/LTX-2.3_-_I2V_T2V_Talking_Avatar_(voice_clone_with_Qwen-TTS).json` and similar workflows. Suggest named GroupNode subgraphs for editor-readability AND for downstream tools (VibeComfy, ComfyScript) to emit cleaner code. **0.5 h**.
- **F2.** Document the AudioEnhancementNode / AudioNormalizeLUFS / Label (rgthree) / "easy showAnything" / "MelBandRoformer" custom-node dependencies in `vibecomfy/node_packs.py` so future port checks resolve them. **1-2 h**.

**Total honest IN scope: 21.5 - 36 hours**, midpoint ~28h. **~3-4 days of focused work.**

## 3. Scope (OUT)

Anti-scope — tempting items that should NOT land in Phase 3:

- **Live ComfyUI runtime as a hard dependency.** Block D's runtime object_info population is OPTIONAL (cache-based fallback). Templates must still convert/regen offline when no Comfy is reachable.
- **Subgraph-as-Python-function emission.** The current `raw_call("uuid", ...)` shape for unnamed subgraphs is OK; promoting them to named Python functions is its own architectural workstream (see `docs/python_composition_dsl_plan.md`).
- **Strict-ready CI promotion of widget_alias_unknown.** B-block diagnostic should stay warning-only until a release cycle of soaking, like Phase 2's doctor codes.
- **A full source-workflow audit / patching campaign.** Block E is bounded to the 5 runexx + 2 documented gaps; broader source-quality work is a follow-up.
- **Reigh-worker capability contract updates.** Phase 3 emission changes should not touch `template_index.json`'s public input/output names; if they do, treat as a blocker.

## 4. Locked decisions

- **Constant naming (B1)** — uppercase-slugified value, numeric suffix only on collision. NOT camelCase, NOT type-prefixed. Source: today's discussion of `VAE_NAME` (current good) vs `WIDGET_0` (current bad).
- **Single-use inlining (B2)** — inline only if reference count is exactly 1. Don't second-guess for readability of 2+ references.
- **Widget kwarg fallback (C2)** — when alias is unknown, keep current `widget_N` shape AND emit `widget_alias_unknown` diagnostic. Don't silently swallow.
- **Object_info cache is canonical (D)** — when both `widget_aliases.py` (static) and object_info cache (refreshed) have an entry, **cache wins** (it reflects the actual deployed pack). Static map is a starter / fallback.
- **`port reemit` for Family P** — the canonical resolution path. Source-JSON-required regen is not a hard requirement going forward. Documented in `docs/template_provenance_gaps.md` (today's commit `86a7878`).

## 5. Open questions

These MUST be resolved during Phase 3 execution, not before:

- **Q1.** For Block A1, when a `SetNode`/`GetNode` pair has multiple SetNodes with the same `widget_0` name (visual aliasing across the graph), which one wins? Recommend: warn + first-by-node-id, but verify with corpus inspection.
- **Q2.** For Block C1, when a class has both a named field AND a `widget_aliases.py` entry that contradict (rare but possible), which wins? Recommend: cache wins (per locked decision), but emit a diagnostic so we catch it.
- **Q3.** For Block D1, what's the minimum Comfy server version the `/object_info` endpoint contract is stable against? If unstable, vendor an integration test.
- **Q4.** For Block E2, are the source workflows on RuneXX's HF repo licensed for commit into our `workflow_corpus/`? Verify before downloading and committing.
- **Q5.** Does Block C1 break any existing tests that assert `widget_N=value` literally? Audit `tests/test_porting_emitter.py` and snapshot tests before regen.

## 6. Constraints

- **`template_index.json` shape stability** — public input/output names should not change as a side effect of widget-kwarg renaming. Phase 2's Block E is finishing the public-input naming canon; Phase 3 must respect that contract. Run `tools/refresh_template_index --check` after each block.
- **Reigh-worker blast radius** — zero per Phase 1's verified audit. C1's kwarg renaming is internal to template body; not exposed via `template_index.json[*].id` or public inputs.
- **Phase 2 sequencing** — Phase 3 must come AFTER Phase 2 lands its doctor readability codes (Block B from Phase 2 brief) and the `READY_OUTPUTS` module-level lift (Block C from Phase 2 brief). Doing Phase 3 first would chase moving emitter behavior.
- **Backward compat** — generated templates must continue to load + validate after re-emission. If a test relied on `WIDGET_0`, fix the test to use the new constant.
- **No new dependencies** — Block D should use only `httpx` (already in deps) for the optional Comfy query.
- **Atomic-write discipline** — `port reemit` and any new emitter writers must use the existing temp-file + parity-check + `Path.replace()` pattern (carry-over from Phase 1).

## 7. Done criteria

- All 64 ready templates re-emitted with: zero `WIDGET_N` constants where the value has a known alias; named kwargs at call sites where the alias is known; no opaque `raw_call('GetNode', ...)` or `raw_call('SetNode', ...)`; resolved `Reroute` chains.
- New CLI `vibecomfy nodes refresh-object-info` works against a local Comfy or accepts `--server-url` to query elsewhere. Cache files land under `vibecomfy/porting/cache/object_info/`.
- `tests/test_porting_emitter.py::test_widget_kwargs_named_when_alias_known` and companion tests pass.
- `tests/test_broadcast_helper_resolution.py` (new) pins SetNode/GetNode/Reroute inlining against fixture workflows.
- `port reemit --all-family-p` runs idempotently (second invocation produces no diff).
- `docs/template_provenance_gaps.md` updated: 5 runexx-5 marked resolved (or with explicit follow-up notes); 2 originally-listed templates' status updated.
- `docs/widget_alias_resolution.md` (new): documents the alias-resolution precedence (cache > static > raw widget_N) and the `widget_alias_unknown` diagnostic code.
- `template_index.json` byte-identity preserved on public input/output names; only template-body shape changes.

## 8. Touchpoints

- `vibecomfy/porting/emitter.py` — Blocks A1, A2, B1, B2, C1, C2.
- `vibecomfy/porting/helpers.py` — Block A2 (additive resolver registry).
- `vibecomfy/porting/widget_aliases.py` — Block C2 (fallback path).
- `vibecomfy/porting/cache/object_info/` — Block D1 (new cache writes).
- `vibecomfy/porting/reemit.py` — Block E1 (re-emit invocation surface).
- `vibecomfy/commands/nodes.py` — Block D1 (new `refresh-object-info` verb).
- `vibecomfy/commands/__init__.py` — explicit registration of new verb.
- `tests/test_porting_emitter.py`, `tests/test_porting_convert.py`, `tests/test_port_reemit.py` (extended), `tests/test_broadcast_helper_resolution.py` (new), `tests/test_widget_kwargs_resolution.py` (new), `tests/test_object_info_cache.py` (new).
- `tools/refresh_template_index.py` — verify shape stability after each block.
- `workflow_corpus/community/runexx/` — Block E2 (patched sources).
- `vibecomfy/node_packs.py` — Block F2 (custom-node pack declarations).
- `docs/template_provenance_gaps.md`, `docs/widget_alias_resolution.md` (new), `docs/template_porting_workbench.md` (update).
- `AGENTS.md` — note the new resolution precedence.

## 9. Sizing verdict

**Honest hour total: 21.5 - 36 hours, midpoint ~28 h. ~3-4 days of focused work.**

This justifies a **1-week `partnered/full +feedback` megaplan**. Rationale:

- Block D (runtime object_info) is the highest-design-risk piece. It's the foundation for clean widget resolution; getting the cache shape + precedence right is worth premium critique.
- Blocks A and C touch the emitter shape — same code path that Phase 0/1/2 have been iterating on. Heavy test coverage and snapshot diffs needed.
- Blocks B1/B2 are mechanical but cross-cutting (all 64 templates regenerated). +feedback profile's review/rework loop catches accidental semantic changes.
- Block E is the validation that the whole stack works end-to-end on the templates that have been broken-regen for two sprints.

`directed/full` would skip prep + gate + review — fine for mechanical-only work, but Block D's design choices benefit from the full critique/revise loop.
`premium/full` would be overkill — there's no novel architectural risk; the design calls are mostly locked by Phase 0-2 conventions.

Sequencing: **A1 → A2 → A3 (helpers first, smallest blast radius) → B1 → B2 → B3 (renaming + regen) → D1 → D2 (object_info infrastructure) → C1 → C2 (kwargs, depends on D) → E1 (runexx-5 validation) → E2 (source patching) → F1 → F2 (upstream + node packs).**

If Phase 2 surfaces unexpected complexity, Phase 3 absorbs the overflow as additional slack — it is the natural buffer for emitter-shape work.

## 10. Out-of-band follow-ups (not in scope, document only)

Three things that came up today but DON'T belong in Phase 3:

- **ComfyScript integration / comparison tooling.** Today we transpiled the runexx talking_avatar workflow through both VibeComfy and ComfyScript (`/tmp/runexx_talking_avatar_comfyscript.py`, 91 lines vs VibeComfy's 476). VibeComfy is the production tool; ComfyScript is a useful comparison renderer. Worth a `docs/comfyscript_comparison.md` write-up but not a Phase 3 scope item.
- **Megaplan subprocess centralization (tickets `01KSDH58ZPT54VWH7VXQ6PP4X3` + `01KSDJCRSASA09HTABBHWY0FMZ`).** Lives in `~/Documents/megaplan/`, not VibeComfy. Its own sprint.
- **Subgraph-as-Python-functions emission.** Per `docs/python_composition_dsl_plan.md`. Architectural workstream of its own.
