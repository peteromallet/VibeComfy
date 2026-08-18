# Verify-r5 — strategy-r5 implementation verification (DeepSeek Flash, read-only verifier)

- **Branch:** `two-step-megado` · **Worktree:** `/private/tmp/vc-twostep`
- **Run under verification:** `one-step-30-r5` (30-scenario harness) · **RC under review:** `b39b9029` "RC-P0: one ingest dispatch authority + accepted-delta guard + typed non-empty guard" (parent `bcf92497`)
- **Status:** COMPLETE — matrix frozen BEFORE implementation; diff reviewed; tests run (incl. baseline comparison); replay check run.

---

## 1. Reproduction matrix — frozen at HEAD `bcf92497` (BEFORE RC-P0), reproduced via `/tmp/vc_r5_freeze.py` (exact executor doors: `render_text`/`_coerce_workflow`, `EditSession(dict(graph))`, `resolve_target`)

| # | Input shape | Fixture | Source nodes | Render IR uid/name set | EditSession IR uid/name set | Current failure | render==edit |
|---|-------------|---------|--------------|------------------------|-----------------------------|-----------------|--------------|
| 1 | Vibe envelope | `audio-acestep-audio-generation-and-processing-workfl-1b1360` request.graph | **46** | **46** (`115=VAEDecodeAudio`, `146=AudioSeparation`, `155=VocalAndSoundRemoverNode`, `216=FrequencyFilterPreset`, …) | **0** | `unknown_target: no node in the current render resolves to 'vaedecodeaudio'` (uid `115` same) | FALSE |
| 2 | LiteGraph UI list | `tests/fixtures/agent_edit/flat.json` | **7** | **7** | **7** (identical) | none — works today | TRUE |
| 3 | Bare API | `audio-transcribes-audio-appends-text-regenerates` request.graph | **11** | **11** (`71=Apply Whisper`, …) | **0** | `unknown_target: no node in the current render resolves to 'apply_whisper'` (uid `71` same) | FALSE |

**Dominant failure confirmed:** EditSession yields 0 nodes for envelope/API while render sees the full set — two ingest authorities (`_gates.py:300-307` `from_ui(use_comfy_converter=False)` vs `render.py:110-144` shape dispatch).

**After RC-P0 (`b39b9029`), re-measured:** envelope → **12** nodes retained (`image-animatediff-video-generation-with-vae-d20410`), bare API → **11** (`audio-transcribes…`) and **15** (`image-image-editing-with-qwen-image`). The zero-node IR is eliminated for all shapes; render/edit node sets now match. **The remaining blocker moved downstream** (see §4): typed-tool edits on real graphs fail `unknown_field`, and the API emit-exit guard fails `verification_failed` — both reproducible with the exact executor construction.

---

## 2. Flip ledger — 9 expected-pass candidates (P0+P1) with residual risk

Terminal artifact path (all present; verdict = `assessment.json` truth): `out/agentic/one-step-30-r5/attempts/<scenario>/attempt_1/<scenario>/assessment.json`

| # | Scenario | Confidence | Verdict @ freeze | Residual risk (strategy §1) | Flip status after RC-P0 code review |
|---|----------|-----------|------------------|------------------------------|--------------------------------------|
| 1 | `3d-3d-shape-generation-and-export-workflow-8800a9` | high | FAIL (`correct_node_targeted=true`, 64/64 budget) | none named | **BLOCKED** — `shape_refine_strength` named-field edit → `unknown_field` (no schema provider wired into `_two_step_edit_session`) |
| 2 | `3d-converts-image-to-3d-model` | high | FAIL | value enum needs schema validation | **BLOCKED** — `Polygon_count` → `unknown_field` |
| 3 | `audio-acestep-audio-generation-and-processing-workfl-1b1360` | high | FAIL | none named | **BLOCKED** — multi-op wiring edit → `unknown_field`/`unknown_target` on real IR |
| 4 | `audio-transcribes-audio-appends-text-regenerates` | high | FAIL | none named | **BLOCKED** — `model` on `Apply Whisper` → `unknown_field` (verified) |
| 5 | `image-animatediff-video-generation-with-vae-d20410` | high | FAIL | none named | **BLOCKED** — `batch_size` on `EmptyLatentImage` → `unknown_field` (verified) |
| 6 | `image-image-editing-with-qwen-image` | high | FAIL | none named | **BLOCKED** — `prompt` on `TextEncodeQwenImageEditPlus` → `unknown_field` (verified) |
| 7 | `3d-generates-a-3d-mesh-from` | contingent | FAIL (`unknown host action None`) | terminal parse error independent | **BLOCKED** — same `unknown_field` chain + independent parse risk |
| 8 | `audio-audio-processing-with-chatterbox-tts-and-vc-b55994` | contingent | FAIL (`no_orphaned_wiring=false`) | add+remove syntax degraded | **BLOCKED** — `add_node`/`remove_node` may pass validation but API emit-exit slot loss blocks acceptance |
| 9 | `audio-tts-narration-using-indextts-2` | contingent | FAIL (d1 projected away) | needs P1 guard | **BLOCKED** — same chain; P1 guard itself is correctly implemented and unit-tested |

**Explicit non-flip:** `3d-3d-model-generation-and-preview-workflow-cc0df7` — `Rodin3D_Fusion` absent from the 922-class cache; correct product is a grounded `requires_custom_nodes` refusal (P2, out of scope). Unchanged.

**Projection:** as committed, **0 of 9 flips can be credited from RC-P0** — the ingest door is fixed (necessary), but no real-graph edit can land yet (see §4). This is **below the ≥7 acceptance gate** → triggers a new evidence analysis per strategy §6.5, not bar-softening. The live rerun has NOT been executed; this verdict is from code-level reproduction with the exact executor construction, not from terminal `assessment.json` of a rerun.

---

## 3. Diff verdict — RC-P0 `b39b9029` (12 files, +907/−27; .oracle + code + tests only)

| Criterion | Evidence | Verdict |
|-----------|----------|---------|
| **Single dispatch authority** | `_gates.py:300-307` `_workflow_from_ui` now calls `_named_import(..., schema_provider=self.schema_provider, use_comfy_converter=False)` + guard; `render._coerce_workflow` (render.py:110-144) dropped its copied branch table and calls the same `_named_import` + guard. Three named decoders (`from_envelope`/`from_ui`/`from_api`) remain the doors (normalize.py `_named_import`). | **PASS** |
| **No raw-graph resolver fallback** | `resolve_target` (edit_tools.py:262-290) unchanged — retained IR only; no new fallback to raw graph/UI snapshot added anywhere in the diff. | **PASS** |
| **No judge/rubric/assessor edits** | Commit touches only ingest/render/two_step/artifacts + 3 test files; zero changes under `tests/live_agentic_harness/`, `prompts.py`, `contracts.py`, budgets, scenarios. | **PASS** |
| **No swallowed ingest error** | `_two_step_edit_session` (two_step.py:1359-1373): `except Exception: return None` removed; `WorkflowIngestError(kind="workflow_ingest")` propagates to the typed `ExecutorResult.failure` boundary (generic handler maps `exc.kind`). | **PASS** |
| **Non-empty guard** | `_assert_nonempty_ingest_preserved` (normalize.py): shape-aware `_source_node_count` (envelope mapping / UI list / API `class_type` entries); unknown shape raises; `source>0 and decoded==0` raises `WorkflowIngestError`; legitimately empty graphs allowed (unit-tested). | **PASS** |

**P1 accepted-delta guard (bundled):** `artifacts.py` — non-empty `accepted_delta_ids` outranks `graph_unchanged=true`/unchanged routes; `final==original` with accepted ids raises typed `ArtifactConsistencyError(kind="artifact_consistency")` and never writes. Correct as far as it goes (the strategy also asked for a replay-equality verification inside the guard; implemented as a final==original equality check instead — the replay equality is independently verified here in §5 and by the continuity test).

**Overall diff verdict: 5/5 PASS on the stated criteria** — the diff is faithful, minimal, and well-scoped. **However, the acceptance gate is NOT met** (see §4): the strategy's own test #5 fails, and real-graph edits cannot land.

---

## 4. Targeted test results (RC-P0 `b39b9029` vs baseline `bcf92497`, same 3 files)

| | bcf92497 (baseline, separate worktree) | b39b9029 (RC-P0) |
|---|---|---|
| `test_porting_edit_session.py` + `test_executor_two_step_continuity.py` + `test_headless_agent_artifacts.py` | **13 failed / 298 passed / 2 skipped** | **14 failed / 311 passed / 2 skipped** |

- **+13 passes = the new RC-P0 tests** (format-aware ingest dispatch, parity, unknown-shape/zero-decode fail-closed, artifacts accepted-delta tests) — all green.
- **The 13 pre-existing failures are IDENTICAL at baseline** (gate/primitive class tests, `_DescribeMixin._find_link_to_target_in_ledger` missing, etc.) → **not RC-P0 regressions.**
- **The single new failure is RC-P0-scoped and blocks the acceptance gate:**
  `test_executor_two_step_continuity.py::test_two_step_edit_session_typed_runtime_accepts_edit_for_envelope_and_api` — **API leg fails** `verification_failed: Candidate changed an out-of-delta node`. Root cause (reproduced): the API fixture's COW re-emit loses slot metadata on schema-less emit (`inputs[0].type CLIP→UNKNOWN`, `outputs[0].name CONDITIONING→output_0`, `outputs[0].type CONDITIONING→''` for uid 2), so the emit-exit guard sees untouched-node changes. Envelope leg of the same test passes.

**Independent real-graph checks through the exact executor construction (`_two_step_edit_session` + `EditToolRuntime.dispatch`):**
- Ingest: 12/11/15 nodes retained (envelope/API/API) — **the core fix works.**
- `edit_node emptylatentimage.batch_size=8`, `apply_whisper.model='base'`, `textencodeqwenimageeditplus.prompt=…` → **all fail `unknown_field`** ("field 'batch_size' is not a schema input/widget of node 'EmptyLatentImage' (uid '9')").
- Why: real graphs store widgets positionally (`widget_0..N`, `raw_widgets` list); the validator (`_op_validate._validate_set_node_field`) accepts only schema-declared or literally-present named fields; `_two_step_edit_session` constructs `EditSession(dict(graph))` with **no schema_provider** (grep: only construction site, two_step.py:1373). Wiring `get_schema_provider("auto")` did NOT fix it in this environment — the offline provider serves 0 classes (though the live loop's `node_schema` tool demonstrably served `batch_size, height, width` in the transcript, so schema exists in the live environment but never reaches `EditSession`). The render shows `widget_N` for these graphs and `widget_N` refs are rejected by philosophy #9 → **no typed edit can land on real graphs through the executor path as committed.**

---

## 5. Independent replay-equality check

**Method:** envelope fixture (the RC-P0 continuity test's synthetic envelope — the only fixture where an edit can currently land), real typed runtime, then: accepted Δ replay (`apply_edits_cow(original, landed_ops)`) vs the session's post-edit state and emitted UI.

**Result: PASS.**
- `edit_node ksampler.seed=99` → accepted, `delta_id=d1`.
- Replay node set == final node set: **True**; node 2 widgets `{'seed': 99, …}` identical in replay and final.
- `final_ui == replay_ui` (JSON byte-equal): **True**.
- Untouched nodes preserved (node 1 `width==512`, node 3 present): **True**.

**Limitation (recorded, not glossed):** real request graphs cannot yet reach an accepted Δ (unknown_field chain, §4), so replay equality could only be proven on the synthetic envelope. The check will need to be re-run on a real fixture after the executor wires a schema provider into `_two_step_edit_session` (and the API emit-exit slot-loss is addressed).

---

## 6. Verdict summary

1. **Matrix:** frozen before implementation; zero-node IR for envelope/API confirmed and eliminated by RC-P0 (render/edit sets now match).
2. **Flip ledger:** all 9 candidates still FAIL; as committed, **0 flips creditable** (below the ≥7 gate) → per strategy §6.5, this triggers another evidence analysis, not bar-softening.
3. **Diff:** 5/5 criteria PASS (single authority, no raw-graph fallback, no judge/rubric edits, typed failure propagation, non-empty guard) + P1 guard correctly implemented.
4. **Tests:** +13 new passes, 0 regressions (13 pre-existing failures identical at baseline); **one new RC-P0 failure** — continuity test API leg (`verification_failed`, emit-exit slot loss).
5. **Replay equality:** PASS on the synthetic envelope; not yet provable on real fixtures.

**Root gap to close for the next RC (evidence-backed):** wire a schema provider (or a `raw_widgets`-based named-field mapping) into `_two_step_edit_session`/`EditSession` so named fields resolve on real positional-widget IRs; and make the API emit path retain slot metadata across COW so the emit-exit guard passes for bare-API graphs. Without both, no candidate in the flip ledger can move.
