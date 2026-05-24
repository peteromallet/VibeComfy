# Phase 0: Pre-plan sprint — foundations that make Phase 1 trivial

Two weeks of foundational work that pays for itself by making every subsequent change safer, faster, and more reviewable. Without this, Phase 1 ships as a series of nervous emitter edits with no regression net. With it, the emitter becomes a refactor-friendly module instead of an undertested fragile path.

(Numbering note: originally there were three phases — Phase 0 preplan, Phase 1 cleanup steps, Phase 2 family fixes. Phase 1 was entirely absorbed into Phase 0 during verification, and Phase 2 was renumbered to Phase 1. So this doc has two phases: Phase 0, and Phase 1 = family fixes.)

## Why this exists

Earlier in the session I identified 12+ underlying warts that will make Phase 1 harder than they need to be. Quoting:
- "The 15 failing tests are unknown what they actually pin" — every emitter change could break more, and we don't know in advance. (Phase 0a gate note: 13 failures across tests/test_ready_templates.py + tests/test_porting_emitter.py + tests/test_porting_convert.py, plus 2 in tests/test_templates_module.py = 15 total.)
- "Subgraph materialization is fragile and undertested" — Phase 1's Families A+E+F all touch this region, and the 23 broken templates ARE the only test surface
- "No automated round-trip test for `port convert`" — known doc'd limitation; regressions slip through
- "Bare `ValueError`/`RuntimeError` raises (~30+ sites)" — every Phase 1 debug session involves reading stack traces blind
- "Five separate test suites + 64 template files to keep green" — 90+ seconds per iteration; discourages tight feedback loops
- "23 manual templates have a load-bearing duck-typed protocol" — silently desyncable
- "`AGENTS.md:503-510` is aspirational, not implemented" — documentation lies about behavior

These aren't blockers individually. Together they turn every Phase 1 task into a slog. The pre-plan sprint addresses them as a coherent unit.

## Outcome

At the end of two weeks:

1. **Comprehensive test net** catches emitter regressions, roundtrip drift, and `template_index.json` byte changes automatically.
2. **The 15 failing tests are categorized** (13 in the three main test files + 2 in test_templates_module.py = 15 total), either fixed (if valid invariants) or deleted (if pinning intermediate refactor state).
3. **Per-family fixture tests** exist for each Phase 1 emitter bug — minimal repros that fail today, will pass after the fix lands.
4. **Documentation matches code**. `AGENTS.md` corrected. New `ARCHITECTURE.md` lays out the codegen-with-ContextVar + runtime-executor-for-index + duck-typed-shim design explicitly.
5. **Type safety lifted**: `node()` / `ready_node()` return `_NodeBuilder` instead of `Any`. `typing.Protocol` locks the manual-template shim contract.
6. **Useful errors**: bare `ValueError`/`RuntimeError` raises in `workflow.py` + `emitter.py` migrated to `VibeComfyError` subclasses with `next_action` hints.
7. **Phase 1 is half done as a side effect**: steps 2, 3, 4, 5, 6, 9 land during pre-plan as natural prerequisites.
8. **Marker semantics decided**: `# vibecomfy: manual` vs `# vibecomfy: broken-regen` disambiguated.

## Investment vs. payback

Phase 0 is 45-60 hours of work (revised honest sum, accounting for the combined B+step7 overlap and other savings). Phase 1 is 18-30 hours. The 2-3× ratio is uncomfortable looking only at "Phase 0 derisks Phase 1." That framing undersells what Phase 0 builds.

The honest decomposition:

- **One-time Phase-1-derisking value (~15-20h of Phase 0)**: Pre-E source-JSON restoration, Pre-E.2 attribution verification, E per-family fixtures, B test categorization. These exist to make Phase 1 mechanical. Pay back ONCE.
- **Lasting infrastructure value (~30-40h of Phase 0)**: A test net (golden output, roundtrip, byte-identity, load-and-validate sweep), C documentation hygiene + ARCHITECTURE.md, D type safety, F cleanups, G marker semantics. These survive past Phase 1 — they catch the NEXT refactor, and the next, indefinitely.

The ratio for the one-time portion vs. Phase 1 is roughly 1:1 (~18h pays back ~18-30h of mechanical work). The lasting portion is justified by the next ~3-5 emitter refactors, each of which avoids re-doing this work. Frame the megaplan brief to reflect this — without it, the planner may try to trim "lasting" deliverables thinking they're over-investment.

## Pre-launch citation verification (~30 min)

Before Phase 0 kicks off: walk every numbered file:line citation in BOTH docs and verify each still resolves to the described code. `AGENTS.md:503-510` was claimed-but-not-implemented — that precedent generalizes to every other citation in these docs. Line numbers drift across worktrees and across emitter changes since the spike audits ran.

```bash
# rough check: list all file:line cites in both docs
grep -oE "[a-zA-Z_/]+\.py:[0-9]+(-[0-9]+)?" docs/template_refactor_phase_0_preplan.md docs/template_refactor_next_plan.md | sort -u
```

For each cite: read the referenced lines, confirm they still describe what the doc claims. Update or remove citations that drifted. **No Phase 0 work starts until this is done.**

**Correction note (2026-05-23 — Phase 0a gate executed):** `tools/format_as_python.py:430-530` is NOT active variable-naming logic. The earlier verification that claimed those lines were active was a misdiagnosis. The entire first `format_as_python` definition at lines 388-613 (including `_node` at L539 and `_apply_overrides` at L573) is dead — unreachable due to Python late-binding shadowing by the wrapper `def format_as_python` at line 614, which delegates to `vibecomfy.porting.emitter.emit_ready_template_python`. All callers (`tools/convert_ready_templates.py:257`, `tests/test_porting_emitter.py:23,591`) resolve to the L614 wrapper. The "430-530 dead block" claim is essentially correct; the "active" diagnosis was wrong. The dead block extent is the entire L388-613 range, not just 430-530.

## Week 1 — Foundations + Investigation

### Phase 0 ordering note (per adversarial review)

Within Phase 0, **run F (emitter cleanups + regen) BEFORE A.3 (template_index byte-identity pins)**. F.4 (strip section comments) and F.5 (`MODEL_NAME[_N]` rename) regenerate templates and mutate `template_index.json`. If A.3's snapshots are pinned BEFORE F lands, the snapshots become stale immediately. Order: D (type lift) → F (cleanups + single regen) → A (test infra pinning the post-cleanup shape).

Within A.3 specifically: pick the 10 representative templates strategically — prefer templates whose `template_index.json` entry is NOT affected by F.4/F.5 mutations, OR snapshot post-F.4/F.5. Otherwise the byte-identity test becomes "update freely" muscle memory.

### A. Test infrastructure (2-3 days)

Build the regression net that doesn't exist today.

**A.1 Golden-output regression test for `port convert`**
Pick 5-8 representative source JSONs spanning families (z_image, wan_t2v, basic_image_upscale, ltx2_3 sample, wanvideo_wrapper sample, ace_step audio). Snapshot their current `port convert` output as committed `tests/snapshots/port_convert/*.py.expected`. New test: run `port convert <source>` and assert byte-identical output. Updates by intent (commit a new snapshot when emitter behavior intentionally changes). Catches Phase 0 F.4 + F.5 + Phase 1 family-fix emitter changes immediately.

**A.2 Roundtrip pin test**
For 5 templates: `port convert <source.json> → out.py`, `load_workflow_any("out.py") → wf`, `wf.compile("api") → api_json`, assert structurally equivalent to `<source.json>` (same node class counts, edge shape multisets, public-input keys). Catches regressions Family A would cause when register_input id-mapping changes.

**A.3 `template_index.json` byte-identity test**
For 10 representative templates, pin the current `public_inputs`, `public_outputs`, `artifact_expectations`, `requirements`, `custom_node_packs`, `models` JSON shape. Test asserts post-regen JSON matches. Catches `refresh_template_index --check` flakes from Phase 1 step 5 (strip section comments) and ensures Reigh-worker's only dependency (`templates[*].id`) stays stable.

**A.4 Load-and-validate sweep**
One pytest fixture that walks `ready_templates/**/*.py`, imports each, calls `build()`, calls `wf.finalize_metadata()`. 64 implicit smoke tests. Currently scattered across multiple test files. Fast (most templates load in <50ms; total ~3-5s per run). Catches "I broke `templates.py` in a way that breaks every template" instantly.

**Deliverables**: 4 new test modules under `tests/`. Commits: one per test type.

### B. The 15 failing tests — verified by spike `b5ko3foci` (~2-2.5 hours, not 1 day)

Subagent A's \"pre-existing casualties\" claim is **verified**: all 15 are category R (rewrite), zero category I (real invariant violations), zero referencing retired `ref`/`SymbolicNodeRef`.

**B.1 — Simple snapshot/expectation updates (~1.5 hours total)**

13 of 15 tests pin assertions that became stale during the refactor (emitter no longer emits `InputSpec`, `PUBLIC_INPUTS(**locals())`, etc.; templates renamed inputs like `frames→length`, `fps→output_fps`). Each is 5-15 min — update the assertion to match new shape. These 13 live in `tests/test_ready_templates.py` + `tests/test_porting_emitter.py` + `tests/test_porting_convert.py`:

- `test_ready_templates.py::test_protected_template_index_contracts_match_built_contracts` (10 min)
- `test_ready_templates.py::test_ltx_lightricks_templates_static_index_includes_built_public_inputs` (5 min)
- `test_ready_templates.py::test_native_wan_animate_template_declares_frame_count_binding` (10 min)
- `test_ready_templates.py::test_ltx_first_last_travel_iclora_control_exposes_worker_patch_points` (10 min)
- `test_ready_templates.py::test_ltx_lightricks_first_last_parity_exposes_worker_patch_points` (15 min)
- 6× `test_porting_emitter.py` snapshot pins (5-10 min each ≈ 45 min)
- `test_porting_convert.py::test_ready_template_uses_shared_helpers_and_passes_import_build_compile_parity` (5 min)

**B.2 — Static-contract extractor architectural question (~30-60 min total)**

The two remaining tests (`test_static_contract_extracts_public_inputs_from_inputspec`, `test_public_input_metadata_round_trips_through_static_contract`) live in `tests/test_templates_module.py` (not in the three main files) and reveal that `extract_ready_template_contract` (`static_contract.py:L70-98`) walks the legacy `PUBLIC_INPUTS`/`PUBLIC_INPUT_METADATA` dicts AND `bind_input`/`register_input` calls — but **has no handler for inline `public()` calls nested inside node constructors.**

Per the megaplan -1912 design, the runtime executor in `refresh_template_index.py` replaced AST extraction for public inputs. So `extract_ready_template_contract` is either:
- (a) Still called by other code paths (`port check`, `doctor`, capability_contracts?) that DO need public-input extraction — in which case extending it to handle `public()` is necessary (60-90 min as the spike estimated, but the work IS architectural debt).
- (b) Legacy for public-input extraction — only `READY_METADATA`/`MODELS`/`OUTPUT_SPEC` extraction is current — in which case the failing tests should be deleted (15 min) or rewritten to exercise the runtime-executor path (30 min).

**10-min investigation during B execution** picks between (a) and (b):
```bash
grep -rEn "extract_ready_template_contract|\.public_inputs" --include='*.py' vibecomfy/ tools/ tests/
```
List every caller; categorize as "needs public-input extraction" vs. "uses other contract fields only." Pick the path that minimizes code surface.

**B.3 Output**: a table in `docs/test_failures_categorization.md` with per-test verdict + action.

**Updated combined estimate**: B (2-2.5h) + step 7 (2-3h) = **4-5.5h total** (down from 11h separately).

### C. Documentation hygiene (1-2 days)

**C.1 Fix `AGENTS.md:503-510`.** It currently claims helper nodes are stripped during conversion. They aren't. Either:
- (a) Implement the stripping as part of pre-plan (this is Phase 1 Family F; pull it forward), or
- (b) Correct the doc to say "helper nodes survive in generated code unless their source workflow explicitly omits them; see Family F TODO."

Pick (b) for the doc-fix scope; Family F still lives in Phase 1 (4-6h work).

**C.2 Audit other docs for similar lies.** Run a grep over `AGENTS.md`, `CLAUDE.md`, `docs/**/*.md` for claims of behavior; spot-check 10 against actual code. Flag every mismatch as a doc-or-implementation TODO.

**C.3 Write `docs/ARCHITECTURE.md`** (8-9h realistic per spike `a043ed8d6078b4ac3`). Currently the design has to be reverse-engineered from code. Lay out:
- The codegen-with-ContextVar architecture (what `new_workflow()` does, how typed wrappers consume the ContextVar)
- The runtime-executor-for-index design (`refresh_template_index.py` imports and executes each template)
- The duck-typed shim for manual templates (`.resolve()` + `.label` protocol)
- The `public()` sentinel + `pending_publics` resolution dance
- Known limitations (helper-stripping TODO, roundtrip caveats, manual marker conflation)

3-5 pages. The reference document a new contributor reads first.

**Spike-derived structure (per `a043ed8d6078b4ac3`):** split into research + writing phases. ~2h upfront reading `templates.py` (densest file), `workflow.py`, `workflow_context.py`, `registry/ready_template.py`, `refresh_template_index.py`. Then ~6-7h drafting all 5 sections back-to-back to amortize the read cost and keep terminology consistent. Sections 3 (duck-typed shim) and 5 (known limitations) are DeepSeek-draftable from existing code + CLAUDE.md inputs; sections 1, 2, 4 need real architectural understanding and shouldn't be DeepSeek'd cold.

### D. Type-safety lift (1 day)

**D.1 `node()` and `ready_node()` → `_NodeBuilder`.**
Two annotation changes. `_NodeBuilder` is already fully typed at `workflow.py:636`. Propagates real types through every generated wrapper. Phase 1 step 2 promoted to pre-plan; 30 min including test run.

**D.2 `typing.Protocol` for manual-template shim.**
Define `class SymbolicRefProtocol(Protocol): label: str; def resolve(self, namespace, wf) -> Any: ...` with `@runtime_checkable`. Add `isinstance(_, SymbolicRefProtocol)` checks at `InputSpec.resolve_node_id` and `_resolve_output_node`. The 23 manual templates' inlined shims implement the protocol; the runtime check catches desyncs immediately. Phase 1 step 9 promoted; 30 min.

**D.3 Bare `ValueError` → `VibeComfyError` migration.**
~30+ sites in `workflow.py` and `emitter.py`. Each gets an appropriate `VibeComfyError` subclass + `next_action` hint. Tedious but mechanical. Phase 1 step (not listed in original plan, was Phase 3) promoted to pre-plan because Phase 1 debug sessions need the better errors. Estimated 2 hours.

## Week 2 — Per-family coverage + selected fixes + cleanup

### Pre-E. Re-verify family attribution + restore source JSONs (~2-3 hours, surfaced by spikes `bzgmb3ubh` + `byb48xrh6`)

**Pre-E.1 — Restore missing source JSONs to worktree** (10 min).
The scratchpad-emitter worktree's `workflow_corpus/` is missing the `custom_nodes/` subdirectory (containing `flux2/`, `ltxvideo/`, `qwen_tts/`, `wanvideo_wrapper/`). These exist in the main `/Users/peteromalley/Documents/reigh-workspace/vibecomfy/workflow_corpus/custom_nodes/` checkout. Without them, `port convert` can't process the 23 broken templates' sources. Copy or symlink: `ln -s /Users/peteromalley/Documents/reigh-workspace/vibecomfy/workflow_corpus/custom_nodes workflow_corpus/custom_nodes` (or `cp -r` if symlinks cause issues).

**Pre-E.2 — Re-verify family attribution for all 23 templates** (~2 hours). **HARD CHECKPOINT: no E.1-E.4 fixture authoring starts until this lands and the resulting `docs/family_attribution_verified.md` is reviewed.** Per adversarial review, fixture work targeted at the wrong families wastes 5-7h of work. If Pre-E.2 finds new families or substantially different counts, the fixture plan in E rescopes before starting.
Spike `bzgmb3ubh` found gaps in the current attribution:
- 4 runexx templates unassigned to any family (`custom_audio`, `lipsync_custom_audio`, `music_video_low_ram`, `video_to_video_extend`).
- Family E "10 claimed, 11 listed" / Family A "8 claimed, 9 listed" — counts don't reconcile.
- `z_image` has compound failure: Family E (proxyWidgets) **plus** an opaque UUID-typed component (`9b9009e4-...`) that prevents clean inlining. Family E alone won't make it pass.
- `ace_step_1_5_t2a_song` (claimed Family B) is blocked by pre-existing hard errors: `unresolved_runtime_class` for `PrimitiveNode`, `unknown_input widget_14` on `TextEncodeAceStepAudio1.5`. Conversion blocks before Family B can fire.
- Spike `byb48xrh6` suggests some Family A attributions may be wrong (the bug path is partly latent in production).

Step: with source JSONs restored, run `python -m vibecomfy.cli port convert <source>.json --ready-id <kind>/<name> --dry-run --json` on each of the 23 templates. Capture the exact error. Re-categorize against the 4 (or now possibly 5+) families.

**Output**: `docs/family_attribution_verified.md` with per-template verdict, primary family, secondary failures, and "blocking precondition" if applicable (e.g., ace_step's PrimitiveNode issue blocks Family B test).

**Pre-E.3 — Investigate the 5th issue (opaque UUID components)** (~30 min).
`z_image` and possibly others have opaque UUID-typed subgraph components that can't be inlined. Is this a 5th family (let's call it Family I — opaque-component handling)? Or is it Family E variant? Trace one example (`z_image`'s `9b9009e4-...` component) and decide.

**Pre-E.4 — Investigate ace_step's pre-existing hard errors** (~30 min).
`PrimitiveNode` and `widget_14` on `TextEncodeAceStepAudio1.5` are not Family B bugs — they're missing-node-class issues. Fix or document as a separate prerequisite (Family J — node-pack-missing-class)? Or are these node classes in a custom-node pack that's not yet installed?

### E. Per-family fixture tests for Phase 1 (~6 hours — verified by spike `bwldnt30h`)

**Spike `bwldnt30h` hand-crafted a working Family F fixture in 40 minutes**, including reading the API JSON format, writing the 4-node JSON, iterating until clean import, and verifying the bug exhibits with clean signal. Revised estimates per family below. Original "2-3 days" was 4× pessimistic for simple families; the E fixture (subgraph with proxyWidgets) is structurally harder and gets a higher cushion.

The 23 broken-regen templates are giant LTX/Wan workflows; debugging Family E by re-running them is slow. Build minimal repros.

**E.1 Family E fixture** (proxyWidgets ordering in subgraph materialization)
A hand-crafted source JSON with one subgraph proxying 2-3 widgets in non-sequential order. Test: `port convert <fixture.json>` and assert the materialized subgraph function's kwargs match the proxyWidgets mapping. Today: fails (emitter walks positionally). After Family E fix: passes.

**E.2 Family A fixture** (register_input id-map preservation)
A source JSON where node IDs in the source don't match the rebuilt workflow's IDs. Test: regen + load + assert `register_input` calls reference nodes that actually exist. Today: fails with `target node 'X' does not exist`. After fix: passes.

**E.3 Family B/C/D fixtures**
B (register_input re-pointed at wrong node after subgraph inlining), C (materialized subgraph function name collides with build() local), D (multi-output arity mismatch). One small fixture each.

**E.4 Family F fixture** (GetNode/SetNode broadcast resolver) — **40 min** (verified by spike)
A 4-node JSON: LoadImage → SetNode(label='reference_image') → GetNode(label='reference_image') → SaveImage. Test: `port convert <fixture.json>` and assert the output contains zero `raw_call('GetNode', ...)` and zero `raw_call('SetNode', ...)` calls — the broadcast is resolved into direct edges. Today: fails (emitter emits raw_calls). After Family F: passes. Reference fixture at `/tmp/fixture_family_f.json`.

**Per-fixture time estimates** (Family F validated; rest extrapolated with caution):
- E.1 (Family E, proxyWidgets in subgraph): 90-180 min (structurally hardest — nested subgraph entry/exit, proxyWidget ordering metadata)
- E.2 (Family A, register_input id-map): ~45 min (simple shape)
- E.3 Family B variant: ~45 min
- E.3 Family C (name collision): ~60 min (needs subgraph)
- E.3 Family D (multi-output arity): ~45 min
- E.4 Family F: 40 min (verified)
- **Total: 5-7 hours**

**Deliverables**: 6 fixture source JSONs + 6 focused test functions. Each fails today, will pass after the corresponding Phase 1 family fix lands.

### F. Selected Phase 1 steps promoted to pre-plan (2 days)

Steps that are easier to do BEFORE further emitter work, or that defend later changes:

**F.1 Fix `wf.node()` discarding `pending_publics`** (Phase 1 step 3 promoted).
The lens 2 footgun. Either consume the dict like the free `node()` does, OR raise on `PublicSentinel` detection. Raising is safer — exposes the misuse loudly. 30 min.

**F.2 Fix `_UNSUPPORTED → None` collapse** at `static_contract.py:736` (Phase 1 step 4 promoted).
Serialize `_UNSUPPORTED` as `{"dynamic": true}` tagged form. Update consumers. 30 min.

**F.3 Clean deletes** (Phase 1 step 6 promoted).
`_at` from `__all__`, `tools/format_as_python.py:430-530` dead block, `PUBLIC_INPUT_METADATA` phantom leg in `static_contract.py:71` + `refresh_template_index.py:127`. Zero-risk. 30 min.

**F.4 Strip section comments from emitter** (Phase 1 step 5 promoted).
`# Loaders`, `# Sampling`, etc. mis-categorize in 3+ templates and the typed-wrapper class names self-document. Easier to do BEFORE Phase 1 emitter changes than after (less reviewer-noise in Phase 1 diffs). 20 min + regen.

**F.5 Rename `MODEL_NAME[_N]` → field-name-derived constants** (Phase 1 step 8 promoted).
Per the spike + user prioritization, this is a high-value readability win. Emitter knows the kwarg name at the use site (`VAELoader(vae_name=...)`); use that as the constant name (`VAE_NAME`, `UNET_NAME`, `CLIP_NAME`, `LORA_NAME`). Collisions get numeric suffix (`VAE_NAME`, `VAE_NAME_2`). ~50-100 LOC emitter change in the constant-block emission path. Done WITH F.4 since both share the same regen pass — one regeneration, one snapshot update for both. 45 min + shared regen.

### G. Marker semantics (half day)

**G.1 Decide**: should `# vibecomfy: manual` mean "intentionally hand-authored" exclusively, with `# vibecomfy: broken-regen` for the 23 shim templates? OR keep the conflation and document it?

**G.2 Implement the decision**:
- If splitting: rename the 23 shims' marker. Update `tools/convert_ready_templates.py` to recognize both. Update `ARCHITECTURE.md`.
- If keeping conflated: just document.

**G.3 Add a CI check**: every template has exactly one of {`# vibecomfy: generated`, `# vibecomfy: manual`, `# vibecomfy: broken-regen`} on line 1. Catches the 1 outlier (`z_image_img2img.py` with bare `# vibecomfy: generated`).

### H. Slack budget — run all tests, fix surprises (~1 day budget; treat as the explicit reserve)

This is the sprint's slack, not a deliverable with hidden scope. By the end of week 2 the new test net should be green. Anything that breaks is real debt surfacing — fix the small ones, file the large ones. If H runs short of work, end the sprint early. If it overflows, the items above were under-estimated and the sprint extends; no shame.

## Week 1 → Week 2 stop point (explicit review checkpoint)

After Week 1 lands (A test infra + B test triage + Pre-E + start of E + initial F/D promotions), **pause for a 30-min review** before committing to Week 2:

- Does A.4's load-and-validate sweep show 64/64 templates loading cleanly, or did it surface 10+ broken? If broken: testability work needs to extend; defer hygiene (C, D.3, G, remaining F).
- Did Pre-E.2 confirm 4-6 families or surface 8+? If 8+: E rescopes; that may consume Week 2's full budget.
- Did B's test categorization match the spike's "all R, ~2-2.5h" claim? If categorization revealed real invariant violations (category I) hiding, deal with those before hygiene.

The checkpoint output is a 1-paragraph decision: continue with hygiene, defer hygiene to a follow-up sprint, or extend testability. Skip the checkpoint and march straight into Week 2 only if Week 1 lands clean.

## Numbering note: Phase 1 absorbed entirely

Originally there were three phases: Phase 0 (this preplan), the old Phase 1 (9 cleanup steps), and Phase 2 (family fixes). Through the verification spikes, **the old Phase 1 was entirely absorbed into Phase 0**:

- ~~Step 1~~ done in-session (subagent `a5e65ca668bbc724b`)
- ~~Step 2~~ promoted to D.1 (`node()` → `_NodeBuilder` typing)
- ~~Step 3~~ promoted to F.1 (`wf.node()` discards `pending_publics`)
- ~~Step 4~~ promoted to F.2 (`_UNSUPPORTED → None` collapse)
- ~~Step 5~~ promoted to F.4 (strip section comments)
- ~~Step 6~~ promoted to F.3 (clean deletes)
- ~~Step 7~~ folded into Phase 0 step B (zombie deprecation cluster overlaps with 15-test cleanup; combined B+step7 ≈ 4-5.5h)
- ~~Step 8~~ promoted to F.5 (`MODEL_NAME[_N]` → field-name-derived)
- ~~Step 9~~ promoted to D.2 (`typing.Protocol` for shim contract)

**The old Phase 1 has zero residual work.** The remaining phase after this preplan sprint is what was previously called **Phase 2 — renumbered as Phase 1** in `template_refactor_next_plan.md`. Below and elsewhere in this doc, "Phase 1" refers to the family fixes (formerly Phase 2) unless explicitly marked as "old Phase 1" or "Phase 1 step N".

## What Phase 1 (family fixes) looks like after pre-plan

Originally 11-18 hours of subgraph debugging. After pre-plan:

- **Each family has a minimal failing test fixture.** Iteration loop: write fix → run fixture → verify → move on.
- **`AGENTS.md` no longer misleads** about helper stripping; F's scope is explicit.
- **`ARCHITECTURE.md` documents** the codegen-with-ContextVar + runtime-executor design so contributors know the mental model.
- **Errors during debugging are informative** (`VibeComfyError` subclasses with `next_action` hints), not bare `ValueError`.
- **The 64-template load-and-validate sweep** catches "I broke every template" immediately instead of finding out 30 minutes into running the full test suite.

**Family F (helper resolver, now covering SetNode/GetNode + Reroute + Note/MarkdownNote) is 4-7 hours**, with the fixture test bounding iteration.

**Family E (proxyWidgets ordering) is still 2-4 hours**, with a fixture test it converges fast.

**Family A (register_input id-map) is still 2-3 hours.**

**Plus the explicit post-Phase-2 cleanup deliverables (P2.1–P2.7):** marker rollback, SymbolicNodeRef shim deletion, duck-typed protocol retirement, Reigh worker post-validation, golden snapshot updates, cookbook sweep, `template_index.json` regen. Adds ~3-5 hours.

**Phase 1 total: 14-19 hours.** This is the honest count after surfacing the post-cleanup work that was previously hiding implicitly. Pre-pre-plan estimate of 8-13 hours was too low because it didn't account for marker rollback, Reigh validation, golden updates, or cookbook migration. The fixture tests still help — they reduce uncertainty inside the family fixes — but the total scope was always larger than the bare emitter changes.

The pre-plan investment still pays back: without it, Phase 1 is "14-19 hours of uncertain emitter debugging plus a scramble through cleanup." With it, Phase 1 is "14-19 hours of mechanical execution against fixture tests that catch regressions on every iteration."

## Sizing + recommendation

This pre-plan sprint is itself **megaplan-sprint-sized work** (~2 weeks). Per the `megaplan-decision` skill:

- **Profile: `partnered`** (Claude planner + critique + revise + review, DeepSeek executor). Reasoning: multiple architectural decisions (marker semantics, doc structure, test design) need real Claude judgment. Execution is mostly mechanical (write tests, write docs, do clean deletes) — DeepSeek is fine.
- **Robustness: `full`**. Brief has multiple sub-deliverables; critique needs to catch "you wrote the golden test wrong" or "your protocol definition has the wrong shape." Not `thorough` — none of this is data-migration or security-critical.
- **Depth: `low`**. Decisions are clear; planner doesn't need `medium` deliberation.
- **`+feedback` flag**: yes. This is exactly the case where per-stage ratings let us decide if the tier was right for the next refactor sprint.

**Notation: `partnered/full +feedback`.**

Run inside a subagent (off the main thread) so the harness's multi-phase orchestration doesn't clutter the active conversation. Megaplan-cloud isn't needed — local execution is fine for a 2-week sprint with no GPU.

## Locked decisions (settled before launch)

These were open questions during planning; locked here so the planner doesn't reinvent them.

**LD1 — Marker semantics: split, don't conflate.**
The 23 broken-regen templates get a new marker `# vibecomfy: broken-regen` (replacing the current `# vibecomfy: manual - retired ref()/SymbolicNodeRef shim inlined`). `# vibecomfy: manual` is reserved for intentionally hand-authored content (zero today; future-only). Rationale: the conflation actively confused readers during this session; the cognitive cost of two-marker-mental-model is real and recurring; future-proofing keeps `manual` clean for actual hand-authored content. The regen tool (`tools/convert_ready_templates.py`) extends its recognized-marker set to `{generated, manual, broken-regen}`, refusing to overwrite both `manual` and `broken-regen` templates. After Phase 1 unblocks the 23, their marker auto-flips to `generated` (P2.1) and the `broken-regen` value disappears.

**LD2 — Test categorization policy: default to rewrite, delete only when invariant is obsolete.**
For each of the 15 failing tests in B's investigation:
- If the test pins an intermediate-state shape but the underlying invariant still matters (e.g., a snapshot test where the snapshot is wrong but regression-checking the snapshot is still valuable) → **rewrite** to pin the new shape.
- If the test asserts behavior of a removed function / obsoleted contract → **delete**.
- If the test fails only because its target template is broken-regen → **mark as expected-to-pass-after-Phase-2**, don't delete.
Rationale: tests cost nearly nothing to maintain when correctly-targeted; bugs cost a lot when slipping through; bias toward preservation is principled. The categorization output (`docs/test_failures_categorization.md`) names each test's verdict explicitly so "rewrite" doesn't mean rubber-stamping.

**LD3 — Per-family fixture minimality: hand-crafted, ~5-20 nodes per fixture.**
Each E.x fixture is a hand-crafted JSON workflow exhibiting one specific bug family — the smallest workflow that reliably reproduces. Target sizes:
- E.1 (Family E, proxyWidgets ordering): ~8 nodes (1 subgraph, 2 proxied widgets in non-sequential order).
- E.2 (Family A, register_input id-map): ~3 nodes (1 loader, 1 use, 1 register_input).
- E.3 Family B variant: ~5 nodes.
- E.3 Family C (name collision): ~6 nodes.
- E.3 Family D (multi-output arity): ~3 nodes.
- E.4 (Family F, broadcast resolver): ~4 nodes (1 SetNode + 1 GetNode + 1 consumer).
Total ~30 nodes across all 6 fixtures. Rationale: small fixtures keep CI fast (<100ms per fixture); single-family isolation gives clean fail-signal; debugging a 5-node failure takes minutes vs. 30 for a 100-node template. The 2-3 hour fixture-authoring cost pays back across every Phase 1 iteration. **Do NOT use existing broken templates as fixtures** — they fail for multiple reasons (multi-family confounding) and obscure which fix is needed.

## What this pre-plan explicitly does NOT do

- **Doesn't fix any Phase 1 emitter family.** That's still Phase 1 work. Pre-plan only adds the fixture tests that gate it.
- **Doesn't touch the 23 broken-regen templates' content.** They stay in shim form until Phase 1 lands.
- **Doesn't address the bigger architectural reset** (Option 2: templates as pure data, no `def build()`). Multi-week epic; future work.
- **Doesn't change Reigh worker / app / orchestrator.** Audits confirmed zero blast radius.
- **Doesn't ship new typed wrappers, recipes, patches, or blocks.** Out of scope.
- **Doesn't add new CLI commands.** Existing surface stays.

## Why this beats "just do Phase 1 + 2 directly"

| Risk | Without pre-plan | With pre-plan |
|---|---|---|
| Phase 1 step 5 (strip section comments) breaks `template_index.json --check` | Discover mid-regen, scramble | A.3 catches before you commit |
| Phase 1 Family A changes register_input behavior, breaks Reigh adapter | Found after Reigh deploys & breaks prod | E.2 fixture pins behavior; Reigh-relevant invariants in A.3 |
| Phase 1 Family E fix accidentally breaks Family A behavior | Family A regresses silently, found weeks later | E.1 + E.2 fixtures both run; regression caught immediately |
| 15 mystery test failures absorb 1+ Phase 1 step | Each step incurs guesswork | B's table tells you exactly what each pins |
| Debug a Family F failure with no `next_action` hint | Read stack trace blind | D.3 errors point you at the fix surface |
| Subagent A's "all 23 marked manual" gets re-litigated when someone adds a real manual template | Confusion, marker re-architecture mid-Phase-2 | G decides upfront, splits or documents |

The pre-plan sprint pays its 2 weeks back by making Phase 1 (the family fixes) a focused ~14-19h execution against fixture tests, instead of an uncertain ~20-25h of nervous emitter edits without a regression net.


---

# Phase 0a citation gate — corrections applied (2026-05-23)

## 1. `tools/format_as_python.py:430-530` dead-block status

**Verdict:** The "dead" claim is **correct**. Lines 430-530 are within the first `format_as_python` definition (L388-613), shadowed by the wrapper `def format_as_python` at L614 that delegates to `vibecomfy.porting.emitter.emit_ready_template_python`. The full dead extent is L388-613 (including `_node` at L539, `_apply_overrides` at L573). All callers (`tools/convert_ready_templates.py:257`, `tests/test_porting_emitter.py:23,591`) bind to the L614 wrapper. The earlier "active variable-naming logic" diagnosis was a misdiagnosis — the code looks active in isolation but is never callable. **F.3 dead-block delete removes L388-613 entirely.**

## 2. Real codegen site for F.4/F.5 (section comments + constant hoisting)

**Plan attribution:** `tools/format_as_python.py` (WRONG)
**Actual location:** `vibecomfy/porting/emitter.py` — `_ROLE_CLASSIFICATION` at L209-253 (section comments), `_hoist_constants` at L388-560 (model-name/mode/prompt constant hoisting, including `MODEL_NAME`/`DEFAULT_PROMPT` etc.). Section comment emission at L1888-1915. F.4/F.5 edits to the dead first `format_as_python` would have zero effect on emitted output.

## 3. D.2 isinstance-check sites

**Plan attribution:** `vibecomfy/workflow.py`, `vibecomfy/registry/static_contract.py` (WRONG)
**Actual location:** `vibecomfy/templates.py` — `InputSpec.resolve_node_id` at L398, `_resolve_output_node` at L655. Both already use duck-typed `.resolve(namespace, wf)` + `.label` protocol. The `SymbolicRefProtocol` definition can live in `workflow.py` near IR types as planned, but the `isinstance(_, SymbolicRefProtocol)` checks must be added in `templates.py` where the duck-typed interaction occurs.

## 4. D.3 bare-raise migration scope

**Plan grep:** `grep -nE "raise (ValueError|RuntimeError)" vibecomfy/workflow.py vibecomfy/registry/static_contract.py tools/format_as_python.py` (INCOMPLETE)
**Must also include:** `vibecomfy/porting/emitter.py` (3 bare raises) and `vibecomfy/templates.py` (9 bare raises). The step title says "emitter sites" but the concrete grep omits emitter.py. Total: workflow.py 14, emitter.py 3, templates.py 9, static_contract.py 0, format_as_python.py 2 (dead). Criterion #4 ("no remaining bare raises") requires all five files.

## 5. F.2 `_UNSUPPORTED → None` sites

**Plan describes:** Single-site at `static_contract.py:736`
**Actual:** At least 4 comparison sites — L736 (`value`), L748 (`default`), L767 (`output_type`), L777 (`positional_name`). All collapse `_UNSUPPORTED` to `None` with subtly different semantics. All must serialize as `{"dynamic": true}` for a consistent contract shape, not just L736.

## 6. 15 vs 13 failing tests — reconciled

The brief's "15 failing tests" is **correct** for the full suite:
- **13 failures** across `tests/test_ready_templates.py` + `tests/test_porting_emitter.py` + `tests/test_porting_convert.py`
- **2 failures** in `tests/test_templates_module.py` (`test_static_contract_extracts_public_inputs_from_inputspec`, `test_public_input_metadata_round_trips_through_static_contract`)
- **= 15 total**

## 7. Plan step-level file attribution errors (per SD8 expansion)

| Step | Plan says | Correct location |
|------|-----------|-----------------|
| Step 3 (D.2) | `workflow.py`, `static_contract.py` | `templates.py` (L398, L655) for isinstance checks |
| Step 4 (D.3) | `workflow.py`, `static_contract.py`, `tools/format_as_python.py` | Must add `emitter.py`, `templates.py` |
| Step 8 (F.4+F.5) | `tools/format_as_python.py` | `vibecomfy/porting/emitter.py` |

## 8. Citations verified as accurate

All 28 file:line citations extracted from both docs were read and verified against current code. The following were confirmed accurate (minor line-drift within ~5 lines tolerated):

- workflow.py:304 — wf.node() discarding _pending (coerce_node_kwargs returns _pending which is silently dropped)
- workflow.py:442 — helper_stripped_nodes() called from runtime_nodes()
- workflow.py:636 — _NodeBuilder dataclass definition
- static_contract.py:71 — PUBLIC_INPUT_METADATA legacy leg in extract_ready_template_contract
- static_contract.py:736 — _UNSUPPORTED to None collapse in _extract_public_call
- templates.py:100 — node() returns Any (line 94 function signature, line 100 return annotation)
- templates.py:979 — _at exported in __all__ (doc said L999, actual L979; 20-line drift)
- refresh_template_index.py:123 — _KNOWN_TOP_LEVEL_NAMES frozenset definition
- refresh_template_index.py:127 — PUBLIC_INPUT_METADATA in the frozenset (actual L128; 1-line drift)
- helpers.py:34-39 — is_helper_class_type(), helper_stripped_nodes()
- helpers.py:46-96 — collect_helper_diagnostics(), collect_broadcast_sources()
- emitter.py:123-130 — FALLBACK_CLASS_TYPES: frozenset containing SetNode, GetNode, Note, MarkdownNote, Reroute, PrimitiveNode
- emitter.py:1234 — _prepare_workflow_for_emit strips UI_ONLY_CLASS_TYPES
- emitter.py:1290 — json.loads() returning None on exception
- emitter.py:1595 — _subgraph_default_args: defaults[inputs[index].name] = value (positional walk, no proxyWidgets)
- emitter.py:1889 — section comment emission loop (emitted_sections tracking)
- emitter.py:2149 — register_input with old_id reference (non-shared path)
- ready_template.py:236 — ready_node() returns Any
- blocks/__init__.py:65 — raw-string-refs deprecation warning
- AGENTS.md:503-510 — helper-stripping claim (roundtrip-specific, survives in generated code)

Cross-repo citations (loaders.py:316-318, vibecomfy_adapter.py:690-692) not verified (reigh-worker, not in worktree).

## 8a. Citation drifted: static_contract.py:403

The next_plan.md line 10 cites static_contract.py:403 for _KNOWN_TOP_LEVEL_NAMES. The actual location is static_contract.py:680 (the frozenset definition with PUBLIC_INPUT_METADATA at L684). Line 403 is the _extract_output_spec function docstring, not the _KNOWN_TOP_LEVEL_NAMES frozenset. This is a 277-line line-number drift — likely the file was restructured since the megaplan -1726 work that fixed the _KNOWN_TOP_LEVEL_NAMES bug. The semantic claim (PUBLIC_INPUT_METADATA is now in the set) is correct; only the line number is stale. Recommend updating the next_plan.md citation to static_contract.py:680.

All other citations remain accurate. No citations required removal.
