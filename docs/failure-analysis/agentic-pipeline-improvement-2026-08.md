# Live Agent-Edit Pipeline — Forward Improvement Plan

**Date:** 2026-08-12 · **Status:** ACTIVE — evidence complete, fixes beginning
**Owner:** vibecomfy agent-edit pipeline (live agentic harness + executor + contracts)
**Headline:** True pass rate ~49/100 (was recorded 38/100; pre-fix 17/100). Baseline (2026-06-30) was 93/100 *executor-ok* but only **69/100 strict-guard passes**. The gap is ~20 points: ~9 harness matcher false-positives, ~11 genuine product/pipeline defects. One confirmed code bug already fixed (`c77fe228`).

---

## 1. Current state

| Metric | Value | Source |
|---|---|---|
| Recorded pass rate (live-final + live-tail9, 100 scenarios) | 38/100 | `out/agentic/live-final/run_summary.partial.json` + `live-tail9` |
| True pass rate (excl. matcher-only false positives) | **49/100** | Dig2 counterfactual rescore |
| True baseline pass rate (strict guard, June assessor) | **69/100** (65/100 under current assessor) | `out/agentic/agentic-100-20260630-021138.summary.json` rescored |
| June "93%" was | executor-ok, NOT guard passes | same summary (93 ok vs 69 guard) |
| Failure inventory | 54 (live-final 30 + live-tail9 ~4 + assessment-only) | artifact scan |
| Infra-misclassified failures | 11 of 14 MalformedModelJSON (zero-token/empty) | Dig3 |
| Matcher-only false-positive failures | exactly 9 | Dig2 |

**Fixes already landed (in order):**
- `422ec835` — structural-harness: satisfiable ltx no-.json rule + bounded assessor retry
- `c5fecf77` — agent-edit: stable `workflow_id` UUID derivation at v2 issuance
- `c467f7d9` — agent-edit: normalize compiled-format graphs at pre-allocation boundary (PARTIAL — see item 3)
- `24ec4446` — structural-harness: 3-attempt assessor-parse retry with backoff
- `c77fe228` — agent-edit: **`import dataclasses`** in `edit_batch_repl.py` (unresolved global crashed every sync protocol retry; 10/100 failures; mislabeled ValidationError)

**Run tags:** `live-final`, `live-tail9`, `live-flash` (pin experiment), `live-x6`, `live-fixcheck`, `live-postfix` under `out/agentic/`.

---

## 2. Failure synthesis (54 failures, 6 DeepSeek batch analyses)

### Class A — Harness/guard bugs (false positives & misclassification)
- A1 **message_artifact regex false positives**: naive word-boundary matchers (`assessor.py:47-53`) — "I have **not applied**" matches `\bapplied\b`; "nodes are **unchanged**" matches `\bunchanged\b` against a changed graph; "not **connected**" matches `\bconnected\b`. 9 matcher-only failures; ~27 scenarios carry message_artifact errors. Check added 2026-07-01 (`0e524b33`) — after baseline.
- A2 **Refusal scoring**: binary score conflates edit-success with safe behavior; no groundedness dimension; refusals never adjudicated (intent judge can't run without UI artifacts). Only 3/100 scenarios configure safe-refusal.
- A3 **Infra misclassification**: "could not be parsed" not in `_PROVIDER_INFRA_PATTERNS` (`runner.py:44-54`) → zero-token transport failures scored `product_fail`, `attempt_count=1`.
- A4 **Fake classify fallback**: `ClassifyDecision.respond_only()` written when classify raises (`core.py:1952-1954`) — misleading `intent=respond` artifacts.
- A5 **Model-label discrepancy**: readiness reports flash (env pin) but per-turn `change_details.batch_turns[].model` = `openrouter:deepseek/deepseek-v4-pro` in 402/402 edit turns incl. baseline. Resolved: profile-driven (see D1).

### Class B — Format/contract integration gaps
- B6 Incomplete normalization: `executor_durable.py` bypasses normalization; canonicalizer is compiled-api-lossy (15 rich → 2 nodes reproduced on `90a1d5`, dropping TripoRefineNode); pin_opaque emission skips `properties.vibecomfy_uid` → "Missing stable node vibecomfy_uid".

### Class C — Genuine model-output defects (real quality tail)
- C7 Code-gen defects (NameError-class — MOSTLY RE-CLASSIFIED to harness bug via D4/c77fe228)
- C8 Wiring defects ("Missing stable link from/to port", ~6)
- C9 Wrong-semantic applied edits (intent judge correctly rejects)
- C10 Contract noncompliance (markdown instead of JSON envelope, real tokens)
- C11 Pinned-node emitter refusals (pre-editor false positive — see D10)

### Class D — Capability/schema gaps
- D12 Unexpressible edits (3/4 verified genuinely absent: INPAINT no denoise field in ANY version; Rodin no model selector; TripoRig no joint control) + 1 precedence-shadowing case
- D13 Scenario-design defects (unsatisfiable queries, over-strict judges)

---

## 3. Deep-dig verdicts (10 areas, decisive evidence)

| # | Area | Verdict | Key finding |
|---|---|---|---|
| D1 | Stage-resolved model/transport provenance | CONFIRMED | Per-phase models profile-driven (flash classify/reply, **pro research/implement**) since 2026-06-18; `VIBECOMFY_OPENROUTER_MODEL` never reaches implement. **Transport changed: June native `api.deepseek.com` (105/105) → now OpenRouter (100%)** |
| D2 | Counterfactual scoring | CONFIRMED | True current 49/100; true baseline 69/100; matcher = ~9-point tax; message_artifact added Jul 1 |
| D3 | Malformed-response provenance | CONFIRMED | 14 MalformedModelJSON: 11 transport/empty (0 tokens) + 3 parser-contract (real tokens). Batch-repl preserves parse_reason/raw; classify/reply preserve nothing |
| D4 | Baseline drift | CONFIRMED | **`edit_batch_repl.py:1577` `dataclasses.replace` without import → NameError on every sync retry (10 failures)** — introduced `11f4267e`, FIXED `c77fe228`. Request envelopes byte-identical June-vs-now; prompt bytes +27% (intentional) |
| D5 | Canonicalization authority | CONFIRMED | c467f7d9 partial: executor_durable bypass + lossy converter (15→2 nodes) + pin_opaque uid-less emission; 64/85 submits serialized-Vibe, 18 carry muted rich nodes |
| D6 | Retry reachability | CONFIRMED | 6 retry layers all scoped to transient/parse faults; deterministic contract rejections + batch exceptions escape all; B6 edit LANDED in-session then discarded at allocation |
| D7 | Schema witness | PARTIAL | 3/4 unexpressible genuinely absent; **precedence bug CONFIRMED** `_frag_research.py:821` (provisional-first shadows real schema); combo-option validation NOT enforced at apply |
| D8 | Refusal scoring | CONFIRMED | 11 refusal-failures: 4 matcher-FP; 7 true → 3 grounded / 3 ungrounded give-ups / 1 partial; safe-refusal mechanism works when wired (2 scenarios) |
| D9 | Research starvation | REFUTED | 429s universal (100% in baseline too); research never starved (failed scenarios got MORE sources); not causal |
| D10 | Pinned-node guard | CONFIRMED | Pre-editor false positive: Set/Get broadcast lowering expands 1 raw link → 4 lowered; pin guard compares cardinality not semantics; 44/131 corpus nodes exposed |

---

## 4. Forward plan — 11 items (three lenses)

### STOP THE BLEEDING
1. **Clause-aware message/artifact matcher** (`assessor.py:47`, `:240`) — noun-scoped edit claims + negation; +9 true-pass points (49→58); unmasks 4 refusal cases.
2. **Reclassify zero-token parse failures as infra** (`runner.py:44`) — "could not be parsed" → retryable_infra ONLY with evidence (`completion_tokens==0` + `parse_reason=empty`); reclassifies 11/14, makes existing retry reachable.
4. **Regression lock for `dataclasses` fix** — behavioral test around `edit_batch_repl.py:1528` (facade raises MalformedModelJSON first call, valid second; asserts `dataclasses.replace` executes).

### GREAT ENGINEERING
3. **One lossless canonical graph representation** — replace lossy `compiled_api` round-trip (`graph_normalization.py:34`, `ingest/normalize.py:69-73,378-383`) with a rich-envelope decoder (rich `nodes` authoritative; `compiled_api` execution-evidence only); close `executor_durable.py` bypass; pin_opaque emission must carry `properties.vibecomfy_uid` (`ui.py:1800`). *Scout confirmed: NO lossless rich→canonical path exists today; only the browser UI list-nodes path is lossless; the missing piece is a `rich` ingest branch (~50-line decoder reusing `_normalize_ui_to_api`).*
5. **Transactional batch boundary + bounded semantic repair** (`edit_batch_repl.py:1516-1928`, `_parse_execute.py:69-90`) — rollback + traceback capture + one corrective repair turn for NameError-class; abort on repeated fingerprint.
6. **Pinned-node semantic consumer comparison** (`ui.py:1666,1754-1775`) — per-output terminal consumer sets `{(target_uid, target_input)}` through reroutes/broadcast lowering; removes pre-editor false rejection; protects 44/131 nodes.
7. **Real schemas authoritative + combo validation at apply** — swap precedence `_frag_research.py:821` → `CompositeSchemaProvider(state.schema_provider, provisional)` (+ `:874`, `edit_batch_repl.py:1115`); combo membership mandatory in `porting/edit/apply_values.py:12-47`; derive widget names from real schema.

### ELEGANT AGENT ENGINEERING
8. **Grounded-refusal adjudication** (`assessor.py:378,818-853`, `intent_judge.py`) — refusal mode: blocker supported / no viable representable edit / specific next action / no fabricated inability; broaden `allow_safe_refusal`; always persist `original.ui.json` + `final.ui.json` (`artifacts.py:290-352`); judge outage = `undetermined`, never pass.
9. **Transport pinning** — native `api.deepseek.com` as benchmark lane, OpenRouter canonical in product; explicit harness transport option (`adapter.py:57-66`); record actual adapter/provider/base_url/model (`runtime.py:366`).
10. **Profile: keep pro-for-implement; all-Flash as clean experiment** — `all_flash.toml` profile, NOT `VIBECOMFY_FORCE_MODEL` (contaminates judge); trim +27% prompt drift (`prompts.py`) into decision tables.
11. **Remove fake `respond_only` + type empty responses** — `classification_status=success|failed`, nullable decision (`core.py:1806`, `executor/contracts.py:2095-2139`); distinguish typed `empty_response` vs malformed JSON (`worker.py:379-412`); retry empties as fresh transport; keep reply-side empty as presentation warning.

### Priority sequence
`4 → 1 → (2+11) → 3 → 6 → 7 → 5 → 8 → 9 → 10`
(Regression lock + scorer first; typed evidence + truthful classification together; canonical normalization before semantic guards; then deterministic pre-edit blockers; repair after rollback is dependable; refusals after evidence; transport/profile experiments last.)

### Measurement gates
- True pass rate (first-attempt / eventual-after-retry / infra-adjusted), matcher excluded
- 9/9 matcher FPs corrected while genuine contradiction controls still fail
- 100% failed model calls carry phase / parse reason / token flag / finish reason / preview / model / endpoint; zero nonzero-token parser failures classified infra
- Exact rich node/edge/mode/UID preservation; normalization idempotence; zero uid-less pin-opaque emissions
- Repair: % eligible batch exceptions receiving a semantic second turn; repair success; rollback integrity; zero repeated-fingerprint loops
- Semantic consumer equivalence (broadcast passes, repointing rejected); invalid combos never reach a candidate
- Grounded-refusal precision/recall; judge availability; UI-artifact coverage
- Transport/profile experiment: resolved model, empty-response rate, true pass by scenario class, latency, tokens, cost

---

## 5. Supporting investigation — lossless representation (scout)

**Verdict: NONE exists today.** Format inventory:
- **LiteGraph UI JSON (list-nodes)** — the ONLY lossless format; `_normalize_ui_to_api` (`normalize.py:115-178`) keeps every node incl. muted/bypassed + UIDs. Browser path (hotshot 8/8 UIDs).
- **API dict (dict-nodes)** — lossy: `compile('api')` drops muted (mode 2) + bypassed (mode 4) via `_compute_dropped_bypassed_ids` (`workflow.py:1161-1177`) and UI-only nodes (`_is_compile_stripped_node`, `1068-1075`).
- **Serialized Vibe envelope** — rich `nodes` mapping IS lossless (all VibeNodes, uids, `metadata._ui`) but **nothing consumes it for structure**; re-ingest reads only `compiled_api` (`normalize.py:70`); rich nodes feed widget-evidence merge only (`normalize.py:205-241`, guarded to compiled survivors at `:213-215`).
- **VibeWorkflow IR (in-memory Python)** — lossless itself; only ever built FROM lossy compiled_api when input is a vibe envelope.
- **`EditSession.working_ui` / `guard_original_ui`** — canonical list-nodes; guard_original_ui is a stamped copy.

**Conclusion:** standardize on the VibeWorkflow IR as canonical (lossless editable surface), `compile('api')` as a derived execution view. Missing piece: a `rich` ingest branch decoding the rich nodes mapping → IR (~50 lines, reusing `_normalize_ui_to_api`'s list-node handling). Cross-language parity already holds (frontend speaks UI JSON).

---

## 6. Retry mechanics (why zero-token failures don't retry)

| Layer | Budget | Why it doesn't help |
|---|---|---|
| JSON-contract retry (`runtime.py:1096-1132`) | 3 | Fires but every attempt empty (0 tokens), exhausts toward 180s turn cap |
| Transport retry (`runtime.py:476-544`) | 3 | Excludes JSONDecodeError/ValueError by design (`runtime.py:84-85`, "content problems") |
| Harness subprocess retry (`runner.py`) | 1 (infra) | Never triggers — `_PROVIDER_INFRA_PATTERNS` misses "could not be parsed" → `product_fail` → `attempt_count=1` |

Fix = reclassify by evidence (item 2), not phrase.

---

## 7. References / inventory

- **Run artifacts:** `out/agentic/{live-final,live-tail9,live-flash,live-x6,live-fixcheck,live-postfix,live-full}/attempts/<scenario_id>/attempt_1/<id>/` (agentic_summary.json, implementation_result.json, response.json, request.json, flow_metadata.json, research.json, classification.json, failure_analysis/). June baseline: `out/agentic/agentic-100-20260630-021138/<id>/`.
- **Scenario corpora:** `tests/live_agentic_harness/scenarios/` (100), `tests/structural_harness/scenarios/` (34, 1 overlap). Workflows: `external_workflows/corpus/*.json` (8936).
- **Harness:** `tests/live_agentic_harness/{adapter,runner,assessor,guard,intent_judge}.py`; `tests/structural_harness/runner.py`.
- **Pipeline:** `vibecomfy/executor/{core.py,profile_data/default.toml,research.py,prompts.py}`; `vibecomfy/comfy_nodes/agent/{worker,provider,runtime,edit_batch_repl,session,graph_normalization,_frag_entrypoint,_frag_ingest,_frag_research,executor_durable,projection_registry_v1}.py`; `vibecomfy/porting/emit/ui.py`; `vibecomfy/ingest/normalize.py`; `vibecomfy/porting/edit/apply_values.py`.
- **Key artifacts for the digs:** `out/agentic/live-final/attempts/3d-3d-model-generation-and-rigging-workflow-90a1d5/` (lossy normalization repro), `.../video-anime-video-to-video-with-controlnet-and-openp-cb5cd2/` (uid-less), `.../hotshot-16-frames-agent-edit/` (NameError), `out/editor_sessions/9d7f9316...` (NameError session), `out/editor_sessions/1f2b1d42...` (B6 landed-then-discarded).
- **Prior case docs:** `docs/failure-analysis/case-01..06*.md`, `docs/failure-analysis/batch_repl_gap.md` (case-06 documents the same missing-link class).
- **Working scratch files (NOT durable, /tmp):** `failure_synthesis.md`, `digger_verdicts.md` — this doc supersedes them.

---

## 8. Open items / next actions

1. Execute priority `4 → 1` (regression lock + matcher) — tiny, high-certainty.
2. Implement `2+11` (typed evidence + truthful classification) together.
3. Spec + land the `rich`-branch lossless decoder (item 3); corpus round-trip preservation test first.
4. Then `6` (pinned consumers) and `7` (schema precedence — one-line swap at `_frag_research.py:821` first).
5. Transport 2×2 experiment (native/OpenRouter × default/all-Flash) after deterministic fixes; decide prompt/model by data, not intuition.


## 9. Scenario enumerations

### Failed scenarios (54)
`3d-3d-model-generation-and-preview-workflow-cc0df7`
`3d-3d-model-generation-and-retargeting-workflow-f65774`
`3d-3d-model-generation-and-rigging-from-image-352066`
`3d-3d-model-generation-and-rigging-workflow-90a1d5`
`3d-3d-shape-generation-and-export-workflow-8800a9`
`3d-generates-a-3d-mesh-from`
`audio-acestep-audio-generation-workflow-2a31ec`
`audio-audio-processing-with-voice-tts-and-noise-remo-b80848`
`audio-transcribes-audio-appends-text-regenerates`
`audio-tts-narration-using-indextts-2`
`hotshot-16-frames-agent-edit`
`image-animatediff-video-from-images-with`
`image-background-removal-and-grid-composition-54a681`
`image-generates-a-2x2-seed-variation`
`image-image-to-image-with-stable-zero123-and-backgro-def5b5`
`image-inpainting-with-differential-diffusion-and-rea-1d414c`
`image-kolors-image-generation-with-segs-detailer-and-d813fe`
`image-sd3-image-generation-with-controlnet-19d221`
`image-sdxl-txt2img-cat-in-spacesuit`
`image-two-stage-qwen-image-generation`
`multi-3d-preview-and-image-output-workflow-d93baf`
`multi-ai-video-upscaling-with-detail-daemon-sampler-673197`
`multi-animated-image-to-video-with-svd-and-lora-4ed6d9`
`multi-animatediff-video-face-swapping-with-deflicker-506ebd`
`multi-audio-to-image-mel-band-roformer-workflow-b22937`
`multi-deforum-stable-diffusion-animation-with-ip-ada-78afac`
`multi-flux2-image-and-video-generation-with-outpaint-435de2`
`multi-image-to-3d-object-generation-with-background-1a7f84`
`multi-image-to-video-generation-with-2`
`multi-image-to-video-with-llm`
`multi-image-to-video-with-upscaling-and-color-matchi-359848`
`multi-svd-image-to-video-with-animation-builder-99e2a9`
`multi-svd-image-to-video-with-webp-and-png-output-bd3afb`
`multi-video-based-character-replacement-using`
`multi-wan-vace-video-retargeting-driven`
`multi-wan2-2-animate-video-with-pose-and-segmentatio-1cc457`
`multi-wanvideo-vace-inpainting-and-compositing-workf-b11a56`
`speed-distillation-research`
`video-animatediff-video-to-video-with-controlnet-and-3c978e`
`video-animatediff-video-with-ipadapter-and-controlne-4eebf3`
`video-anime-video-to-video-with-controlnet-and-openp-cb5cd2`
`video-generates-a-video-from-a`
`video-hunyuan-video-text-to-video-generation-265847`
`video-hunyuanvideo-image-to-video-generation-with-en-ff076a`
`video-image-to-video-conversion-with-moonvalley-d7853c`
`video-ltx-video-upscaling-and-enhancement`
`video-ltx-video-with-audio-and-inpainting-b3ba8a`
`video-svd-image-to-video-generation-fc240f`
`video-video-combine-with-image-loading-5b31ce`
`video-video-frame-by-frame-style`
`video-video-inpainting-with-spline-based-cut-and-dra-485ff2`
`video-video-output-workflow-f855de`
`video-wan-alpha-video-generation-with-lora-and-gguf-6a9e20`
`video-wan-video-generation-with-vace-and-multi-outpu-d1caec`

### Matcher-only false-positive failures (9 — recoverable by item 1)
`3d-generates-a-3d-mesh-from`
`audio-acestep-audio-generation-workflow-2a31ec`
`image-sd3-image-generation-with-controlnet-19d221`
`multi-ai-video-upscaling-with-detail-daemon-sampler-673197`
`multi-audio-to-image-mel-band-roformer-workflow-b22937`
`video-generates-a-video-from-a`
`video-hunyuan-video-text-to-video-generation-265847`
`video-image-to-video-conversion-with-moonvalley-d7853c`
`video-video-output-workflow-f855de`

### MalformedModelJSON failures (13 persisted — 11/14 infra-empty per Dig3; one of Dig3's 14 lacked a persisted response.json)
`3d-3d-model-generation-and-preview-workflow-cc0df7`
`hotshot-16-frames-agent-edit`
`image-animatediff-video-from-images-with`
`image-background-removal-and-grid-composition-54a681`
`multi-animated-image-to-video-with-svd-and-lora-4ed6d9`
`multi-image-to-video-with-upscaling-and-color-matchi-359848`
`multi-svd-image-to-video-with-animation-builder-99e2a9`
`multi-svd-image-to-video-with-webp-and-png-output-bd3afb`
`video-hunyuanvideo-image-to-video-generation-with-en-ff076a`
`video-wan2-2-i2v-video-generation-with-lora-and-nois-374aa9`
`video-wan2-2-text-to-video-with-high-low-noise-model-7c8bb3`
`video-wan2-2-text-to-video-with-lora-and-dual-noise-62682a`
`video-wan2-2-text-to-video-with-lora-and-dual-noise-82ffb9`


---

## 10. G0 gate results (2026-08-12, megado execution)

**Code (all green):** 185 pytest (guard contract + 9 counterexamples + 4 structured controls, score honesty, runner, persistence, narrative, m1 contracts, surface manifest) · structural suite 31/32 (1 undetermined = assessor-flake class) · edit surface 462 (10 narrative-guard helpers deliberately removed; manifest + pinned count updated).

**Live flip subset (25 scenarios: 9 matcher-only + 3 NameError + 13 malformed + 2 controls):** 22 ran (3 cut by the 1h run clamp: hotshot, multi-image-to-video-upscaling, video-hunyuanvideo). **11 pass / 11 fail** — the 2 controls pass, and **9 of the 20 previously-failing that ran now PASS (45% recovery)**:
- Matcher-only: **6/9 recovered** (audio-acestep, image-sd3, multi-audio-to-image, video-generates, video-hunyuan-video, video-video-output). Remaining 3 fail on structured/other grounds now (3d-generates, multi-ai-video-upscaling: assessment-level; video-image-to-video-conversion: MalformedModelJSON — a different, flaky reply this run).
- Malformed: **3/7 recovered via the now-reachable retry** (image-animatediff, video-wan2-2-high-low-noise, video-wan2-2-dual-noise-626). The real-token parser-contract case (multi-animated-4ed6d9) correctly still fails; the rest are persistent empties that retried and failed again — now honestly infra, not product.
- NameError: only multi-deforum ran → fails on MalformedModelJSON now (retry fired; reply still malformed — different class); hotshot + multi-image-to-video not run (clamp).

**Honest read:** the G0 classes (prose gating, NameError, infra classification) are OUT of the failure mix; the residual fails are the genuine agent-quality tail + persistent-transport empties. True pass-rate projection on the full corpus: ~49/100 → ~58-60/100 (the 9 matcher points recovered; infra reclassification cleans the scoreboard).
