# Verify-r5 — strategy-r5 implementation verification (DeepSeek Flash, read-only verifier)

- **Branch:** `two-step-megado` · **Worktree:** `/private/tmp/vc-twostep`
- **Implementer:** DeepSeek Pro XHARD (RC-P0) · **Verifier:** DeepSeek Flash (read-only — no code edits; scratch scripts under `/tmp`)
- **Run under verification:** `one-step-30-r5` (30-scenario live agentic harness, commit `bcf92497` at freeze)
- **Status:** freeze + flip ledger COMPLETE · diff review / tests / replay check PENDING (awaiting RC-P0 commit)

---

## 1. Reproduction matrix — frozen BEFORE implementation (HEAD `bcf92497`)

Reproduction harness: `/tmp/vc_r5_freeze.py` (read-only; calls the exact executor doors — `render_text(graph, lenses=("surface","topology"))`/`_coerce_workflow` for the render side, `EditSession(dict(graph))` for the edit side, `resolve_target` from `edit_tools.py:262-290` for the rejection surface).

| # | Input shape | Fixture source | Source node count | Render uid/name set (IR) | EditSession uid/name set (IR) | Current failure | render==edit? |
|---|-------------|----------------|-------------------|--------------------------|-------------------------------|-----------------|---------------|
| 1 | **Vibe envelope** (`nodes` dict + version) | `out/agentic/one-step-30-r5/attempts/audio-acestep-audio-generation-and-processing-workfl-1b1360/attempt_1/<same>/request.json` → `graph` | **46** | **46** (uids `10,115,116,13,132,137,138,139,…`; incl. `115=VAEDecodeAudio`, `146=AudioSeparation`, `155=VocalAndSoundRemoverNode`, `216=FrequencyFilterPreset`) | **0** | `EditSession` IR empty → `resolve_target('vaedecodeaudio')` → `unknown_target: no node in the current render resolves to 'vaedecodeaudio'.` (uid `115` rejected the same way) | **FALSE** |
| 2 | **LiteGraph UI list** (`nodes` list) | `tests/fixtures/agent_edit/flat.json` | **7** | **7** (`1=CheckpointLoaderSimple … 7=SaveImage`) | **7** (identical set) | none — UI-list path works today | **TRUE** |
| 3 | **Bare API** (numeric top-level node ids, `class_type` entries) | `out/agentic/one-step-30-r5/attempts/audio-transcribes-audio-appends-text-regenerates/attempt_1/<same>/request.json` → `graph` | **11** | **11** (uids `25,48,49,50,51,52,71,72,…`; incl. `71=Apply Whisper`) | **0** | `EditSession` IR empty → `resolve_target('apply_whisper')` → `unknown_target: no node in the current render resolves to 'apply_whisper'.` (uid `71` same) | **FALSE** |

**Dominant failure (confirmed at freeze):** `EditSession` yields **0 nodes** for envelope and bare-API graphs while the render path sees the full set (46/11). Both doors ingest the same raw dict; `vibecomfy/porting/edit/_gates.py:300-307` (`_workflow_from_ui` → `from_ui(use_comfy_converter=False)`) silently empties non-UI graphs, while `render._coerce_workflow` (`render.py:110-144`) dispatches by shape. Every edit op on those shapes fails `unknown_target`/`unknown_graph_name`; the agent misattributes to stale bindings; no Δ lands; the judge grades the empty Δ. Two ingest authorities (philosophy #2 violation), product evidence cannot land (#1), correct actions are prevented (#5).

Relevant code doors at freeze (all as described in strategy-r5):
- `vibecomfy/porting/edit/_gates.py:300-307` — broken door (`from_ui(..., use_comfy_converter=False)`)
- `vibecomfy/porting/render.py:110-144` — correct door (shape dispatch)
- `vibecomfy/ingest/normalize.py:1260-1292` — `_named_import` (candidate single authority)
- `vibecomfy/executor/two_step.py:1359-1368` — `_two_step_edit_session` (`except Exception: return None` swallows ingest errors)
- `vibecomfy/agent/artifacts.py:336-397` — `_route_projects_final_from_original` (P1: `graph_unchanged=true` outranks non-empty `accepted_delta_ids`)
- `vibecomfy/executor/edit_tools.py:262-290` — `resolve_target` rejection surface

---

## 2. Flip ledger — 9 expected-pass candidates (P0+P1) with residual risk

Terminal artifact path (all verified present at freeze, verdict = terminal `assessment.json` truth):

`out/agentic/one-step-30-r5/attempts/<scenario>/attempt_1/<scenario>/assessment.json`

| # | Scenario | Confidence | Terminal verdict @ freeze | Residual risk (strategy §1, verbatim intent) |
|---|----------|-----------|---------------------------|-----------------------------------------------|
| 1 | `3d-3d-shape-generation-and-export-workflow-8800a9` | high | FAIL — `correct_node_targeted=true`, `correct_parameter_changed=false`, `value_semantically_matches_intent=false`, `response_ok=false` (64/64 budget) | None named; exact target+value (`UltraShapeRefine.shape_refine_strength=0.4`) already attempted; budget exhaustion is downstream of empty IR |
| 2 | `3d-converts-image-to-3d-model` | high | FAIL — all four criteria false | Value enum still needs schema validation before acceptance (`Polygon_count` `"800K-Triangle"` unverified against schema) |
| 3 | `audio-acestep-audio-generation-and-processing-workfl-1b1360` | high | FAIL — `correct_node_targeted=false` (agent used exact render names/uids) | None named; exact render names/uids + existing `remove_hiss` building block (AudioFilter uid 214, FrequencyFilterPreset uid 216) were used |
| 4 | `audio-transcribes-audio-appends-text-regenerates` | high | FAIL — `correct_node_targeted=false` | None named; simple named widget edit `Apply Whisper` `tiny→base` (bare-API shape — mandatory per strategy test #2) |
| 5 | `image-animatediff-video-generation-with-vae-d20410` | high | FAIL — `correct_node_targeted=false` | None named; simple named widget edit `EmptyLatentImage.batch_size 16→8` |
| 6 | `image-image-editing-with-qwen-image` | high | FAIL — `correct_node_targeted=false` | None named; correct prompt node/field (`TextEncodeQwenImageEditPlus` uid 133) + concrete lighting-continuity edit attempted (bare-API shape) |
| 7 | `3d-generates-a-3d-mesh-from` | **contingent** | FAIL — `response_ok=false` (`unknown host action None`), `correct_node_targeted=false` | **Independent residual risk:** terminal `_parse_host_action` failure (`agent_backend.py:408-423`) — expected to flip only if the accepted edit prevents the downstream malformed final action; parse error is not fixed by this RC |
| 8 | `audio-audio-processing-with-chatterbox-tts-and-vc-b55994` | **contingent** | FAIL — `correct_node_targeted=false`, `no_orphaned_wiring=false` | MP3→WAV replacement (`SaveAudioMP3`→`SaveAudio`) is correct, but deletion-call syntax degraded after rejection; a resolved base helps, **not guarantees**, acceptance |
| 9 | `audio-tts-narration-using-indextts-2` | **contingent** | FAIL — `correct_node_targeted=false` (d1 accepted but projected away) | **Also needs P1** accepted-delta/final-artifact consistency guard (bundled in this RC); rewire `QwenEmotionNode → IndexTTSEngineNode.emotion_control` correct |

**Explicit non-flip (do not credit to P0):** `3d-3d-model-generation-and-preview-workflow-cc0df7` — shares the empty-IR symptom but `Rodin3D_Fusion` is absent from the 922-class object_info cache and the request is not representable; the correct product is a grounded `requires_custom_nodes` outcome (P2, not in this RC).

**Scoring rule (strategy §6.5):** RC is score-moving at **≥7 of 9 flips** with no regression among existing passes; record terminal verdict + mechanism per flip; below 7 → new evidence analysis, not bar-softening. Strategy projection: point estimate 8 flips (10–12/30); do **not** claim all 9 from unit tests — #7–#9 carry explicit residual risk.

---

## 3. Diff review — RC-P0 (PENDING — no RC-P0 commit at last check; HEAD `bcf92497`)

Criteria checklist (filled on implementer commit):

| Criterion | Expected change | Verdict |
|-----------|-----------------|---------|
| **Single dispatch authority** | Render (`render._coerce_workflow`) and EditSession (`_gates._workflow_from_ui`) call the SAME internal dispatcher (`_named_import` or equivalent centralized helper); envelope→`from_envelope`, UI→`from_ui(use_comfy_converter=False)`, API→`from_api`; `schema_provider` preserved on UI/API | PENDING |
| **No raw-graph resolver fallback** | Resolution uses retained IR only; no fallback to render raw graph / parallel UI snapshot (strategy §5) | PENDING |
| **No judge/rubric/assessor edits** | No changes under `tests/live_agentic_harness/` (assessor.py, intent_judge.py, scenarios), no prompts/budgets/grounding policy changes | PENDING |
| **No swallowed ingest error** | `_two_step_edit_session` (`two_step.py:1359-1368`) propagates typed ingest failure to a typed execute/request failure; broad `except Exception: return None` removed | PENDING |
| **Non-empty guard** | `_assert_nonempty_ingest_preserved`: compare source node cardinality by detected shape (envelope mapping / UI list / API mapping); unknown shape raises; positive source count → 0 decoded nodes raises | PENDING |

---

## 4. Targeted tests (PENDING — run after RC-P0)

Strategy §3 lists (to run/inspect):
1. `tests/test_porting_edit_session.py` — envelope fixture full IR + named/uid resolution + widget edit
2. `tests/test_porting_edit_session.py` — bare-API fixture (mandatory)
3. UI fixture stays on offline `from_ui` round-trip
4. Unknown shape / positive-count-to-zero fail closed with specific diagnostic
5. `tests/test_executor_two_step_continuity.py` — real typed tool runtime, one edit accepted (envelope + API), full graph retained
6. `tests/test_headless_agent_artifacts.py` — `accepted_delta_ids=['d1']` + erroneous `graph_unchanged=true` never writes `final=original`
7. Parity assertion: render uid/node set == EditSession uid/node set for all three shapes

## 5. Independent replay-equality check (PENDING)

Plan (executed after RC-P0): take envelope fixture `image-animatediff-video-generation-with-vae-d20410` (12 nodes) and bare-API fixture `audio-transcribes-audio-appends-text-regenerates` (11 nodes); ingest through the new EditSession door; apply one named edit; replay the accepted delta over the original via the same replay authority; assert the emitted final graph equals the replayed projection (uid/node set + values), and assert `final.ui.json`-equivalent output is not projected from original when `accepted_delta_ids` is non-empty.
