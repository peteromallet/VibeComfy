# VibeComfy template refactor — next plan

Last updated 2026-05-23 by session `ef046b94`.

> **See also: [`template_refactor_phase_0_preplan.md`](./template_refactor_phase_0_preplan.md)** — proposes a 2-week pre-plan sprint that builds the test infrastructure, lifts the type safety, fixes the documentation lies, and absorbs the original Phase 1's 9 cleanup steps entirely. After the pre-plan lands, the original Phase 1 has zero residual work; what was originally called Phase 2 (family fixes) is now Phase 1. **Recommended ordering: Phase 0 (this preplan) → Phase 1 (family fixes).**

## What landed this session

- **Megaplan -1431** — Scratchpad emitter rewrite. Replaced `_node(wf, '<uuid>', '<id>', widget_N=…)` with typed-wrapper natural-Python form (`KSampler(seed=…)`). 34/34 `test_cli_port.py` passing, 69/71 `test_ready_templates.py`.
- **Megaplan -1726** — `directed/light` cleanup. Dropped `output_type=` arg, hoisted `OUTPUT_SPEC` to module level, fixed latent `_KNOWN_TOP_LEVEL_NAMES` bug (`PUBLIC_INPUT_METADATA` was missing from the set in both `static_contract.py:403` and `refresh_template_index.py:123`). 176 passed.
- **Megaplan -1912** — `partnered/full` single-source-of-truth refactor. Introduced `public('name', default=...)` decorator + `PublicSentinel`. Migrated 41 of 64 templates to pure inline form. Exited as `awaiting_human` because 23 LTX2.3/ACE/Wanvideo templates couldn't regenerate (pre-existing subgraph-inlining bugs); those got pragmatically marked `# vibecomfy: manual` with `SymbolicNodeRef` shim inlined locally.
- **Megaplan harness bug fixes (committed in `~/Documents/megaplan/`):**
  - Bug A — `_record_lifecycle_failure` preserves plan state on driver-lifecycle exits (commit `6ec0f27e`).
  - Bug B — healthy-wait polls no longer consume iteration budget (commit `6ec0f27e`).
  - Bug C — orphan-active-step recovery via `_clear_orphaned_active_step` + `_quarantine_phase_outputs` (commit `5bba6fd1`).
  - Critique-system gap — new `prerequisite_ordering` check at `megaplan/audits/robustness.py` catches the exact brief-contradiction class that bit -1912. Default `max_critique_concurrency` bumped 5→6 to keep parallel critique wall-time flat.

## Current migration state (verified on disk)

| State | Count | Marker |
|---|---|---|
| Pure inline `public()` form | 41 | `# vibecomfy: generated - converted by tools/convert_ready_templates.py` |
| Manual w/ `SymbolicNodeRef` shim + `PUBLIC_INPUTS = {...}` dict | 23 | `# vibecomfy: manual - retired ref()/SymbolicNodeRef shim inlined` |
| Plain `# vibecomfy: generated` (no suffix — likely emitter regression) | 1 | `z_image_img2img.py` |

**Zero non-manual templates import `ref` from `vibecomfy.templates`.** The 23 manual templates each carry a byte-identical local copy of `SymbolicNodeRef` instead.

## Cross-repo blast radius — verified

Three DeepSeek audits (`bz1118v5p`, `be0icjdgm`, `bz1mb26zm`) confirmed:

- **reigh-worker**: only reads `templates[*].id` from `template_index.json` (loaders.py:316-318). Hardcoded numeric node IDs in `vibecomfy_adapter.py` operate on ComfyUI workflow JSON, not on VibeComfy template source.
- **reigh-app + reigh-worker-orchestrator**: zero VibeComfy template-source reads. Templates are opaque kebab-case strings stored in SQL `metadata->>'template_id'`.

The refactor is bounded entirely inside VibeComfy as long as `template_index.json` preserves `templates[*].id`.

## Five-lens audit, my filter applied

| Wart | Lens | My priority | Why |
|---|---|---|---|
| `wf.node('K', model=public('foo', default=1))` silently drops `pending_publics` at `workflow.py:304` | 2 (fresh eyes) | **High** | Real bug — public() registration silently lost on a documented entry point |
| `_UNSUPPORTED → None` collapse at `static_contract.py:736` | 5 (sharp edges) | **High** | "Dynamic default" and "no default" become indistinguishable downstream |
| `SymbolicNodeRef` duplicated in core + 23 templates byte-identically | 1 (archaeology) | **High** | Maintenance horror — change one, must update 24 |
| `node()` and `ready_node()` annotated `-> Any` (templates.py:100, ready_template.py:236) | 4 (type safety) | **High** | 30-min change, propagates real types to every generated wrapper call site |
| Zombie deprecation cluster: `apply_ready_template_policy`, `bind_input`, `bind_output`, `ref()` | 1 + 5 | **Medium** | All four emit `PendingDeprecationWarning` but `finalize()` suppresses them — warned-about, suppressed, unremovable |
| `_at()` exported in `templates.py:999` `__all__` with zero non-legacy callers | 1 | **Medium** | Cleanest delete |
| `tools/format_as_python.py:430-530` — explicitly retained dead code (~100 lines) | 1 | **Medium** | Clean delete |
| `static_contract.py:71` — `PUBLIC_INPUT_METADATA` leg never matches | 1 | **Medium** | Phantom symbol; also `refresh_template_index.py:127` |
| `OUTPUT_SPEC` missing from 25 of 64 templates | 3 (consistency) | **Medium** | Emitter should always emit |
| Section comments (`# Loaders`, `# Sampling`) in 8 of 64 templates, mis-categorized in 3+ | 1 + 3 | **Medium** | Strip from emitter entirely — typed-wrapper names self-document |
| `MODEL_NAME[_N]` opaque positional constant names | scan | **High** | Field-name-derived (`UNET_NAME`, `VAE_NAME`, `CLIP_NAME`) is the cleanest readability win when scanning templates. Emitter already knows the kwarg name at the use site. |
| `WIDGET_0[_N]` constants — opaque positional names for semantic string values (e.g. `WIDGET_0_10 = 'ref_image'`) | scan | **High** | 286 in shim templates + ~21 per pure-form template that has a SetNode/GetNode workflow. Most are SetNode/GetNode labels and disappear entirely once the broadcast resolver pass lands (Family F). Verified by audit `b4zyypc0c`. |
| `raw_call('GetNode', ...)` / `raw_call('SetNode', ...)` surviving in generated code | scan | **High** | **`AGENTS.md:503-510` is aspirational — the helper-stripping pass is NOT implemented.** `helpers.py:34-39` has the logic but it's only called from `workflow.py:442` (runtime), never from the emitter. The emitter puts GetNode/SetNode in `FALLBACK_CLASS_TYPES` at `emitter.py:123-130` and emits as `raw_call(...)` unconditionally. Affects shim + pure-form templates alike (716 calls in shims, 60+ per affected pure-form). Fix = new pre-emission broadcast-resolver pass at `emitter.py:1889` using existing `helpers.py:46-96` infrastructure (`collect_broadcast_sources`, `broadcast_name`). 4-6 hours. Verified by audit `b4zyypc0c`. |
| Documentation lies — `AGENTS.md:503-510` says helper nodes are stripped; they aren't | doc audit | **Medium** | Either implement the stripping (above) or correct the doc. If the broadcast-resolver pass lands, this resolves automatically. If not, fix the doc explicitly so future readers don't trust it. |
| `DEFAULT_NEGATIVE` vs `DEFAULT_PROMPT_2` for the same semantic field | 3 | Low | Cosmetic naming divergence |
| Bare `ValueError`/`RuntimeError` raises (~30+ sites) | 4 | Low | `VibeComfyError` hierarchy exists; just migrate. Tedious. |
| `__all__` missing template-author primitives in `vibecomfy/__init__.py` | 4 | Low | Cosmetic |
| `json.loads → None` returning to dict-iterator at `emitter.py:1290` | 5 | Low | Narrow trigger |

**Rejected from audits** (my own filter):
- "Atomic write data loss risk" — `NamedTemporaryFile` + `Path.replace()` is fine; only the orphan-on-`KeyboardInterrupt` is real (hygiene, not data loss).
- ContextVar race in concurrent `build()` — hypothetical, no current async server consumer.
- `@singledispatch` for `isinstance` chains — premature abstraction, hides flow.
- `TypedDict` everywhere — overcalled; reserve for the contract descriptor only.
- `MODEL_NAME_N` "fragile numbering" — fine for now.
- "No round-trip test" — known documented limitation per `AGENTS.md:503-510`.
- Cryptic error messages / too-tight Path/enum validation — minor polish, not warts.

## Phase 1 — quick high-leverage wins

In this order; verify tests between each step:

1. ~~**Retire `ref()`/`SymbolicNodeRef` from `vibecomfy/templates.py`.**~~ **DONE** by agent `a5e65ca668bbc724b`. Verified `hasattr(vibecomfy.templates, 'SymbolicNodeRef') == False` and `hasattr(vibecomfy.templates, 'ref') == False`. The 23 manual templates carry local `SymbolicNodeRef` shims; the core `InputSpec.resolve_node_id` and `_resolve_output_node` paths converted from `isinstance` checks to duck-typed `.resolve(namespace, wf)` + `.label` protocol.
2. **`node()` and `ready_node()` typed `-> _NodeBuilder`.** `_NodeBuilder` is already fully typed at `workflow.py:636`. Two annotation changes + add the import where needed. Likely ~0-3 downstream callers need fixing where they relied on the looseness. Estimated 30 min.
3. **Fix `wf.node()` discarding `pending_publics`.** Either make it consume the dict like the free `node()` does, OR raise on `public()` sentinel detection inside `wf.node()` directing the user to the typed-wrapper class. Picking *raise* is safer — surfaces the footgun loudly rather than silently registering. Estimated 30 min.
4. **Fix `_UNSUPPORTED → None` collapse at `static_contract.py:736`.** Serialize `_UNSUPPORTED` as `{"dynamic": true}` or similar tagged form so downstream code can distinguish. Update consumers at lines 748+. Estimated 30 min.
5. **Strip section comments from emitter.** `# Loaders`, `# Sampling`, `# Conditioning`, etc. — they're heuristics in textual form, mis-categorize in 3+ templates, and the typed-wrapper class names already self-document. Remove the emission path; regenerate. Estimated 20 min.
6. **Clean deletes** (parallel — all are zero-risk):
   - Remove `_at` from `templates.py:999` `__all__`.
   - Delete `tools/format_as_python.py:430-530` dead block.
   - Remove `PUBLIC_INPUT_METADATA` leg from `static_contract.py:71` and `refresh_template_index.py:127`.
7. **Retire the zombie deprecation cluster.** Either delete `apply_ready_template_policy`, `bind_input`, `bind_output` entirely (preferred, after grepping for any unsuppressed callers), or unsuppress the warnings to expose remaining callers. Estimated 45 min including caller migration.
8. **Rename `MODEL_NAME[_N]` → field-name-derived constants** (`UNET_NAME`, `VAE_NAME`, `CLIP_NAME`, `LORA_NAME`, etc.). The emitter already knows the kwarg name at the use site (`VAELoader(vae_name=...)`); use that as the constant. Collisions get numeric suffix (`VAE_NAME`, `VAE_NAME_2`). Single visually-striking readability win when scanning templates. Emitter change ~50-100 LOC in the constant-block emission path. Estimated 45 min including regen.
9. **Lock the manual-template duck-typed shim contract.** Define `typing.Protocol` (+`@runtime_checkable`) in `vibecomfy/templates.py` for the `.resolve(namespace, wf)` + `.label` shape that the 23 manual templates' inlined `SymbolicNodeRef` classes implement. Add a runtime check at the resolution sites (`InputSpec.resolve_node_id`, `_resolve_output_node`) so a desynced shim raises immediately rather than silently failing. Estimated 30 min.

**Estimated total: 3-4 hours of focused work.** (Step 1 already done.)

**Note**: WIDGET_N constant renaming is intentionally NOT in Phase 1 because most `WIDGET_N` constants live in shim templates and disappear as a free byproduct of Phase 1 Family F (helper-stripping pass in subgraphs). Adding it here would mean renaming constants that get deleted later. Defer to post-Phase 1 cleanup, if any survive.

## Phase 1 — 23-template emitter fix (separate session)

Subagent `a5e65ca668bbc724b` diagnosed 4 distinct emitter bug families (with file:line evidence) that block regen of the 23 manual templates. Each family is a focused engineering task:

**Family E — proxyWidgets ordering in subgraph materialization (10 templates).** Highest-impact single fix. `vibecomfy/porting/emitter.py:1595, 2337` walks the *inner* node's `widgets_values` positionally when materializing a subgraph, instead of honouring the outer subgraph instance's `properties.proxyWidgets` ordering. Result: emitted `steps=770044821593082` is actually the inner KSampler's `seed`. Fix = use `properties.proxyWidgets` to map widget slots correctly. Affected: `image/z_image`, `video/ltx2_3_runexx_*` (5 files), `video/wanvideo_wrapper_13b_recammaster`, `…13b_vace`, `…21_14b_v2v_infinitetalk`, `…22_s2v_context_window`, `…22_s2v_framepack_pose`. Estimated 2-4 hours.

**Family A — register_input id-map (refined by spike `byb48xrh6`).** The fix is a **one-line emitter change** at `emitter.py:2149`: replace `old_id` with `var_names.get(old_id, repr(old_id))`. The shared-helpers path at line 2145 already does exactly this — the non-shared path was missed during refactor. **1-2 hours including test additions.** *However*: spike `bzgmb3ubh` surfaced that Family A's failure path is partly latent in production (only fires when `registered_inputs` is explicitly passed). This may mean some of the 8 templates attributed to Family A are misdiagnosed — re-verify per attributions in Phase 0 pre-E.2 before scoping the fix. Independent of Family E.

**Family B — register_input re-pointed at wrong runtime node (2 templates).** `audio/ace_step_1_5_t2a_song`, `ltx2_3_iamccs_audio_extend_low_ram`. Likely fixed as a byproduct of Family A. Estimated 1 hour.

**Family C — materialized subgraph function name collides with build() local (1 template).** `edit/qwen_image_edit`. Fix = mangle the subgraph function name (prefix `_subgraph_` or similar). Estimated 30 min.

**Family D — multi-output arity mismatch (1 template).** `wanvideo_wrapper_22_wan_animate_preprocess_kijai`. Kijai preprocess returns single Handle but emitted code unpacks 5. Fix = use `nodes/_generated/kjnodes.py`'s `_outputs=` declaration to inform tuple unpacking. Estimated 1 hour.

**Family F — Helper-node resolver (`SetNode`/`GetNode`/`Reroute`) + Note/MarkdownNote stripping. Universal scope.** Audit `b4zyypc0c` corrected my earlier hypothesis: the helper-stripping pass **isn't implemented at all** in the emitter. `AGENTS.md:503-510` claims it happens but `helpers.py:34-39` (`helper_stripped_nodes()`) is only called from `workflow.py:442` (runtime Workflow), never from the emission pipeline. The emitter explicitly puts these helpers in `FALLBACK_CLASS_TYPES` at `emitter.py:123-130` and emits them as `raw_call(...)` unconditionally.

Affects all 64 templates whose source workflow used SetNode/GetNode/Reroute — confirmed in 14 of 23 shims (716 raw_call instances) AND in pure-form `ltx2_3_runexx_talking_avatar_qwen_tts` (60 instances), `wanvideo_wrapper_21_14b_fun_control` (6), `wanvideo_wrapper_21_14b_flf2v` (4).

Fix: add a pre-emission resolver pass at `emitter.py:1889` (before the topo-order loop in `_emit_body`) that handles three helper-node classes:
- **`SetNode`/`GetNode` (broadcast pattern)**: build a `label → source-variable` map from SetNode nodes, rewrite GetNode consumers' input edges to point at sources directly, remove both from topo order.
- **`Reroute` (pass-through)**: same shape as SetNode/GetNode but unary — replace each Reroute's consumer edges with direct reference to the Reroute's input source.
- ~~**`Note` / `MarkdownNote`**~~ — **DROPPED FROM SCOPE.** Spike `b7hg9tci3` verified these are already correctly stripped by `UI_ONLY_CLASS_TYPES` filter at `emitter.py:1234`. Not Family F work.

Spike `b7hg9tci3` also found **Reroute IS partially stripped already** — `ltx2_3_t2v.json` has Reroutes in source but the emitted `.py` has zero. Reroute only survives in 4 wanvideo wrapper templates (5 raw_call instances). This points at a code-path gap, not missing logic. **Pre-Family-F investigation (30 min)**: trace why Reroute is stripped in `ltx2_3_t2v` emission but survives in wanvideo wrappers. The difference identifies the exact wiring fix.

The SetNode/GetNode resolution infrastructure already exists at `helpers.py:46-96` (`collect_broadcast_sources`, `broadcast_name`) — needs wiring into the emitter. **Estimate: 5-8 hours** (was 4-7, refined). SetNode/GetNode: 4-6h. Reroute: +1-2h if it's a new resolver, +30-60min if just wiring the existing logic into the bypassed code path (more likely given the spike's evidence). Note/MarkdownNote: 0h, already solved. Independent of Family E.

**Family G — WIDGET_0[_N] opaque positional constants (286 in shims, ~21 per affected pure-form template).** Module-level constants like `WIDGET_0_10 = 'ref_image'` named positionally by widget index, with semantic string values. Most are SetNode/GetNode labels — they disappear automatically when Family F resolves the broadcast pairs into direct edges. The remaining few (non-broadcast widget literals) can be inlined or renamed by value. **Likely a free byproduct of Family F**, not its own work item — but verify the residual count after Family F lands.

**Family H — 1 outlier template with malformed `# vibecomfy: generated` marker.** `ready_templates/image/z_image_img2img.py` has the bare `# vibecomfy: generated` marker (no `- converted by tools/convert_ready_templates.py` suffix). Lens 3 flagged as likely emitter regression. Investigate what's different about this template, fix the emitter to produce a uniform marker, or document the divergence. Estimated 30 min.

**Family I — opaque UUID-typed subgraph components (NEW, surfaced by spike `bzgmb3ubh`).** `image/z_image` has a `9b9009e4-...` UUID component that can't be inlined by the subgraph materialization path — separate from Family E's proxyWidgets ordering bug, but co-located in z_image. May affect other templates with UUID-typed GroupNodes. Pre-E.3 in Phase 0 traces one example and determines whether this is a 5th family or a Family E variant. **Estimate (if separate family): 2-4 hours** for inlining opaque components or marking them as strict-ready exceptions. **Maybe 0 hours** if Phase 0 reclassifies under Family E.

**Family J — pre-existing missing-node-class errors (NEW, surfaced by spike `bzgmb3ubh`).** `audio/ace_step_1_5_t2a_song` is blocked by `unresolved_runtime_class` for `PrimitiveNode` and `unknown_input widget_14` on `TextEncodeAceStepAudio1.5` BEFORE Family B can fire. May be a missing custom-node pack installation, a custom-node-pack schema gap, or both. **Estimate: 1-3 hours** depending on whether it's a "install missing pack" fix or a "node-pack schema update" fix. Affects an unknown subset of the 23 (Family B was claimed at 2 templates; may be larger).

**Family K — scratchpad emitter parity (NEW, absorbed from Phase 2 audit).** `port convert <source.json> --out scratchpad.py` (without `--ready-id`) still emits the legacy `_node(wf, '<uuid>', '<id>', widget_0=…, widget_1=…)` shape instead of typed-wrapper natural-Python form. Same `emitter.py` code region as Families A/E/F so it lands cheapest here. Fix = wire `emit_scratchpad_python` through the typed-wrapper natural-Python path (`KSampler(seed=…)`) with the small difference that scratchpads skip `READY_METADATA`, `PUBLIC_INPUTS`, and `ModelAsset` declarations. Resolve `widget_N` aliases via existing `widget_aliases` module + `object_info`; unknowns become warnings. **Estimate: 4-8 hours** including a round-trip test (`port convert workflow_corpus/.../z_image.json --out /tmp/x.py` → `load_workflow_any` succeeds → compile parity check). Conditional 0-4h for fixing any `test_cli_port.py` fixtures that hardcode the old shape (depends on whether the 12 failures fu:B.2 claims are real on current tip).

**Plan attribution gaps (NEW, surfaced by spike `bzgmb3ubh`):**
- 4 runexx templates not explicitly assigned to any family in this doc: `custom_audio`, `lipsync_custom_audio`, `music_video_low_ram`, `video_to_video_extend`. Phase 0 pre-E.2 verifies their actual failure modes.
- Family E listed 11 templates but claimed 10; Family A listed 9 but claimed 8. Likely overlap (templates fail multiple families). Pre-E.2 produces the canonical attribution table.

## Phase 1 attack order — REVISED 2026-05-24 per Pre-E.2 findings

**Phase 0's `docs/family_attribution_verified.md` invalidated the original
4-family taxonomy.** Only Family C and Family E are verified by live dry-runs.
The real picture is 9 buckets (A, B, C, D, E, F, I, J, K, P), and **Family J
(missing node-pack schemas) is the dominant blocker** — about half of the 23
broken templates can't be observed at all because `port check` hard-errors on
unresolved runtime classes (`PrimitiveNode`, `ClownSampler_Beta`, `IAMCCS_*`,
`DWPreprocessor`, etc.) before any emitter family fix can fire.

**Total estimated: 30-50 hours** (widened from 22-38h to absorb Family J as a
prerequisite step + the durable reconciliation tooling). Worth its own megaplan
with `partnered/full +feedback` profile after Phase 0 lands.

### Family J prerequisite — node-pack reconciliation PROCESS (NEW)

Family J is not a one-off "install missing packs" task. It needs durable
tooling because new templates and pack updates will surface this same class of
failure indefinitely. Phase 1.0 builds a node-pack reconciliation process
before any family fixes ship:

- **Audit command**: `vibecomfy nodes audit --workflow <wf> --json` reports
  every unresolved runtime class, every `unknown_input widget_N` on a known
  class, every missing model enum value, and classifies each as one of:
  pack-not-installed / pack-installed-but-stale-schema / widget-alias-missing /
  model-registry-gap / community-node-unknown.
- **Fix-plan generator**: `vibecomfy nodes reconcile <wf> --json` proposes a
  remediation step per audit row: `nodes install <pack>`, `nodes refresh-schema
  <pack>`, `widgets register <class> <field>`, `models register <key>`, or
  `defer-as-out-of-scope`.
- **Documentation**: `docs/node_pack_reconciliation.md` codifies the workflow
  for an agent encountering an unresolved class.
- **Apply to known cases**: run the new tool against the 23 broken templates,
  produce the fix plan, execute the durable fixes, leave per-template
  exceptions documented. Expected: ~half of A/B unblocked once J resolves.
- **Estimate: 6-10 hours** (durable tooling pays back forever; the actual fixes
  against the 23 templates are cheap once the tool exists).

### Reordered family-attack sequence (evidence-based)

In this order:

1. **Family J first — node-pack reconciliation process + apply to 23
   templates** (6-10h). Unblocks observability of A/B/D for the rest of
   Phase 1. Required for any subsequent dry-run-driven fix.
2. **Family C** (subgraph function name collision, verified for
   `edit/qwen_image_edit`). Pre-plan E.3 fixture
   `family_c/subgraph_build_name_collision.json` pins behavior. **30 min — 1h**.
3. **Family E** (proxyWidgets ordering in subgraph materialization, verified
   for 8 source workflows by raw topology). Pre-plan E.1 fixture
   `family_e/proxy_widgets_subgraph.json` pins behavior. **2-4h**.
4. **Family F completion** (Set/Get broadcast resolver already partially
   shipped per Phase 0 F.4; Reroute still surfaces as runtime-class
   precondition in several runexx templates). Pre-plan E.4 fixture
   `family_f/set_get_broadcast.json` pins behavior. **2-4h** for the Reroute
   wiring gap.
5. **Family I — opaque UUID component handling** (NEW, separate from E).
   Decisive case: `image/z_image` node 76 has UUID class type with
   proxyWidgets, hidden model filenames in widget_7/8/9. Decide policy:
   inline-as-Python-function OR mark as strict-ready exception OR replace with
   declared runtime class. Pre-plan I fixture
   `porting/opaque_component.json` pins behavior. **3-5h**.
6. **Family K** (scratchpad emitter parity) — wires `emit_scratchpad_python`
   through the same typed-wrapper path. Same `emitter.py` region as A/E/F;
   cheaper while context is hot. Round-trip test added. **4-8h**.
7. **Family A** — re-evaluate after J unblocks observability. **1-2h IF still
   needed** (Pre-E.2 found A's 8/9 template attribution unverified; may be
   collapsed into C or J after reconciliation).
8. **Families B + D** — re-evaluate after J unblocks observability. **1-2h
   IF still needed** (B blocked behind J; D's source unavailable locally).
9. **Family G fallout cleanup** — inline or rename any WIDGET_N constants that
   survived Family F. **30 min — 1h**.
10. **Family H** — outlier template marker fix for
    `ready_templates/image/z_image_img2img.py`. **30 min**.

### Family P (provenance gaps) — OUT OF SCOPE for Phase 1

Pre-E.2 found ~8 templates have no local `source_workflow` JSON to dry-run-port
from. Without source, they cannot be regenerated by `port convert`; the only
options are hand-authoring or restoring upstream sources. **Phase 1 carves
these out**: list them in `docs/template_provenance_gaps.md` as a separate
follow-up. Restoring sources can be done from git history or upstream Comfy
repos in a later session. These templates stay on `broken-regen` marker until
sources land.

### Worker stability configuration

Phase 0 hit the default `SHANNON_STREAM_READ_TIMEOUT=240s` watchdog mid-review
when Claude Opus 4.7 paused to think. Phase 1's review phase faces the same
risk. **Set `SHANNON_STREAM_READ_TIMEOUT=1800` in the profile or environment
before launch.** A profile-config commit lives in `~/Documents/megaplan/` as
follow-up (also captures the related `DEFAULT_PHASE_IDLE_TIMEOUT_SECONDS=1800`
backstop already committed as `512b4172`).

### Post-Phase-2 cleanup deliverables (explicit, ~3-4 hours)

These are NOT optional follow-ups — they're the work that makes Phase 1 actually shippable:

**P2.1 Marker rollback for the 23 templates.**
After Family A+E+F regenerate the 23 templates to pure form, update their marker from `# vibecomfy: manual - retired ref()/SymbolicNodeRef shim inlined` (or `# vibecomfy: broken-regen`, depending on Phase 0 G's decision) back to `# vibecomfy: generated`. The emitter does this automatically on regen for templates without the `manual` marker — but the 23 currently have the manual marker, which the emitter respects (refuses to overwrite). Step: temporarily flip the markers, run regen, verify output, commit. 30 min mechanical.

**P2.2 Delete the 23 inlined `SymbolicNodeRef` class shims.**
Each of the 23 templates has a byte-identical `class SymbolicNodeRef:` inlined at the top. After P2.1's regen, these blocks should be gone automatically. Verify with `grep -c "^class SymbolicNodeRef" ready_templates/**/*.py` → should be 0. If any remain, they're a regen bug. 15 min verify.

**P2.3 Retain the duck-typed protocol as future-manual-template guard (refined per adversarial review).**
After P2.2, no current caller remains. But per LD1 in Phase 0, `# vibecomfy: manual` is reserved for future hand-authored templates. If those templates ever need symbolic node references (e.g., a hand-authored template that uses string-based bindings instead of inline Handle objects), the `.resolve()` + `.label` protocol becomes load-bearing again.

**Decision: keep `SymbolicRefProtocol` (from pre-plan D.2) and the `isinstance(_, SymbolicRefProtocol)` checks at `InputSpec.resolve_node_id` and `_resolve_output_node`.** The runtime cost is one isinstance check per finalize — negligible. The future-proofing value is real. Add a comment at the Protocol definition explicitly stating "kept as the API surface for hand-authored manual templates."

Original "30 min retire" reclassified as 5 min documentation update.

**P2.4 Reigh worker post-validation** (refined by spike `b2u5nrsko`).
Original concern: Family A's register_input id-map fix may renumber nodes; reigh-worker hardcodes ~35 numeric IDs in `vibecomfy_adapter.py`. Refined finding: **~35 of those IDs are top-level workflow nodes that Family A's subgraph-inlining fix does NOT touch.** Only **9 subgraph-internal IDs in 2 workflows** are at conditional risk:

- `edit/qwen_image_edit`: `102:76`, `102:77`, `102:88` (image-input rewiring at `vibecomfy_adapter.py:690-692`), `102:103`, `102:106` (step counts at `:695-696`)
- `video/wan22_animate_native_first_stage`: `232:63`, `232:62`, `232:230`, `232:15` (animate-subgraph internals at `:1307-1311`)

Failure mode if Family A renumbers these: loud `KeyError` on `workflow.nodes['102:76']` at scratchpad build time. Not silent corruption.

Step: run `python -m vibecomfy.cli port export <wf> --to json` on these 2 workflows post-Family-A. Use `jq` (not `grep`) against the parsed JSON — ComfyUI API JSON uses node IDs as object keys, and naive grep could false-positive on widget literals. The 9 specific IDs should each appear as a key in the nodes dict:

```bash
jq -e '.nodes | has("102:76") and has("102:77") and has("102:88") and has("102:103") and has("102:106")' exported_qwen.json
jq -e '.nodes | has("232:63") and has("232:62") and has("232:230") and has("232:15")' exported_animate.json
```

Spot-check 2 top-level IDs as sanity (`'78'` in qwen_image_edit, `'1'` in basic_image_upscale) to confirm Family A's renumbering scope is bounded to subgraph-internal.

**Estimate: 1 hour audit + 0-2 hours conditional patch** (down from 1-4h). If mismatches surface, reigh-worker patches are mechanical at known call sites (no architectural change needed).

**P2.5 Golden snapshot updates.**
Phase 0 A.1 pinned emitter output for 5-8 representative source JSONs. Phase 1 changes emitter behavior intentionally — most goldens will change. Step:
- `python -m tools.convert_ready_templates --all --write` to regenerate
- Inspect the golden diffs: only the intentional changes (helper-stripping, proxyWidget ordering, id-mapping) — no semantic regressions
- Update the goldens, commit with the family number in the message

If diffs contain unexpected changes, that's a real regression. 1 hour expected, +1-2 if regressions found.

**P2.6 Cookbook + plugin sweep.**
Subagent A migrated `docs/cookbook/02_*.py` and `06_*.py`. Audit the rest:
- All `docs/cookbook/*.py` files (likely 5-10 more)
- `recipes/**/*.py` if any
- `vibecomfy_extras/**/*.py` if any
- Any documentation that shows code examples

Grep for `PUBLIC_INPUTS`, `PUBLIC_INPUT_METADATA`, `ref(`, `SymbolicNodeRef`, `raw_call('GetNode'`, `raw_call('SetNode'`. Migrate or delete. 1-2 hours.

**P2.7 `template_index.json` regeneration.**
Family F resolves ~1000+ raw_call('GetNode'/'SetNode') into direct edges. The index will shrink. Family A re-maps node ids. The index will see node-id changes per template. Phase 0 A.3 pins byte-identity — those pins will need updating. Run `python -m tools.refresh_template_index` to regenerate the committed `template_index.json`, diff for sanity. Verify downstream consumers (Reigh worker reads only `templates[*].id` — that should stay stable). 30 min.

### Adjacent follow-ups (not Phase 1 scope, file separately)

- **`apply_ready_template_policy` external-caller audit.** Phase 1 step 7 (pre-plan F) retires the zombie deprecations from canonical paths. But unsuppressed external callers (user recipes, plugins, vibecomfy_extras) may exist. Grep + migrate if found.
- **`tools/_legacy/narrate_template.py` retirement.** Lens 1 archaeology flagged this as 8000+ lines of legacy emission logic still imported by `check_pack_provenance.py`. Separate cleanup task.
- **`tools/format_as_python.py` full-file retirement.** Phase 0 F.3 deletes only the dead block (lines 430-530). The whole file is legacy — consider full deletion after Phase 1.
- **Performance/index-size measurement.** Family F's resolver runs on every conversion. Measure port-convert wall-clock before/after. Optimize if significant slowdown.
- **`blocks/__init__.py:65` raw-string-refs deprecation.** Lens 5 flagged this. Different system from `ref()`. Decide: retire now or later.

## Phase 3 — polish (low-priority, optional)

- Migrate bare `ValueError`/`RuntimeError` raises to `VibeComfyError` subclasses (~30+ sites in `workflow.py` + `emitter.py`).
- Add `InputSpec`, `OutputSpec`, `ModelAsset`, `ReadyMetadata`, `new_workflow`, `node`, `finalize` to `vibecomfy/__init__.py:__all__`.
- Rename `DEFAULT_PROMPT_2` → `DEFAULT_NEGATIVE` in 20 templates that produce negative prompts (consistency).
- Fix `json.loads → None` returning to dict-iterator at `emitter.py:1290`.
- Add a `_NodeBuilder` generic over output-tuple types so `model, clip, vae = CheckpointLoaderSimple(...)` type-checks (lens 4 deeper item; multi-day).

## What we explicitly aren't doing tonight

- **The bigger architectural reset (Option 2)** — making templates pure data with no `def build()` and one generic interpreter. That's the "highly elegant" destination but it's a multi-week epic. The current codegen-with-ContextVar architecture is honest, working, and improved. Filing for future.
- **Reigh worker / app / orchestrator changes** — verified by audits as zero blast radius. Don't touch them.
- **Adding new typed-wrappers, model registry entries, custom-node packs, recipes, patches, or blocks.** Out of scope.

## Open questions (resolve in Phase 1 execution)

- For step 3 (wf.node + public()): should the typed-wrapper path silently route through `wf.node` internally? If so, `wf.node` *must* preserve `pending_publics` rather than raise. Audit the typed-wrapper call path before picking raise-vs-consume.
- For step 5 (strip section comments): some users may have learned to scan templates by section. Surface this as a breaking change in the commit message; it's purely cosmetic but visible.
- For step 7 (retire zombie deprecations): are there external consumers (e.g., user recipes under `recipes/` or `vibecomfy_extras/`) that call the deprecated APIs directly? Grep before deleting.

## Commit strategy

When Phase 1 lands:
- One commit per numbered step (atomic units).
- Each commit message includes the wart-list reference (e.g., "Retire ref()/SymbolicNodeRef (Phase 1 step 1)").
- Run focused tests (`tests/test_cli_port.py tests/test_ready_templates.py tests/test_porting_emitter.py tests/test_porting_convert.py tests/test_templates_module.py tests/test_strict_ready_gate.py`) between each commit.
- Regenerate templates only at step 5 (section-comment strip) and at the end. Don't regen between every step — wastes time and clutters diffs.
