# r6 improvement strategy — one-step pipeline, Round 2

## Decision

Make the accepted Δ survive every terminal boundary and become the sole authority for the response and `final.ui.json`.

This outranks the three candidate themes named in the brief. The `budget_or_retry_exhaustion` label is numerically dominant, but three of those failures already landed the exact edit before the budget error; four more non-budget failures also have a correct Δ in the retained IR. The immediate defect is therefore not “the agent failed to act,” but “the product and measurement discarded the action.” One accepted-Δ authority fix has seven named, already-proven flips. By comparison, per-purpose budgeting has one standalone likely flip plus several enabling cases; target-resolution hardening has one direct reproduced flip and a non-reproduced hydration discrepancy; custom-schema coverage is spread across unrelated packs and is conditional on authoritative metadata.

This ordering follows philosophy #1/#2/#11/#12: repair the evidence door before trying to make the model do more work.

## 1. Prioritized root causes

### P0 — accepted work is lost at failure and outer-response boundaries (expected: **7 flips**)

**Code:**

- `vibecomfy/executor/agent_backend.py:658-676`: `_failure_outcome` returns a reply and exception but omits `state.accepted_delta_ids()`, the current retained graph, evidence ids, and current budget.
- `vibecomfy/executor/two_step.py:1158-1182`: the `not outcome.ok` branch constructs `ExecutorResult.failure` without the accepted Δ or implementation graph.
- `vibecomfy/executor/two_step.py:1193-1223`: the success path puts Δ ids only in `report.execute.accepted_delta_ids`.
- `vibecomfy/comfy_nodes/agent/_frag_response_contract.py:1211-1212,1223-1224` and `vibecomfy/comfy_nodes/agent/executor_durable.py:158-159`: legacy outer projection can still stamp `graph_unchanged=true` / `route_not_applyable`.
- `vibecomfy/agent/artifacts.py:339-378,433-436`: `_accepted_delta_ids()` reads only a top-level field, so the existing consistency guard is blind to the nested canonical report.

**Mechanism:** there are two authorities. The editor transcript/retained IR says `delta_accepted` and contains the edit; the outer response and UI pair say “unchanged.” On a second apply, continuation exhaustion, or finalization failure, the failure constructor also throws away work already committed. The judge correctly grades the artifact it receives; changing the judge would conceal the defect.

**Fix shape:** introduce one terminal projection from the durable session state. Both success and failure paths must call it. It must return the accepted batch ids/ops, retained graph, evidence ids, budget, and terminal diagnostic. From that projection:

1. `accepted_delta_ids != []` implies `graph_unchanged=false`; no route/prose field may override it.
2. The top-level compatibility field is derived from `report.executor.execute.accepted_delta_ids`, not maintained independently.
3. `final.ui.json` is emitted from the retained IR through the normal emit door and replay-verified against `original + accepted_batch`.
4. After the first accepted apply, any attempt to exceed the one-apply message cap becomes a **soft commit stop**: keep the first Δ, prohibit further tools for that message, request/construct the final reply, and return a successful edited product with the extra attempt recorded as unapplied. Do not turn a verified edit into `ok=false` because the model tried to do more.
5. If parsing, budget, or grounding still fails after an accepted apply, preserve the accepted product and its truthful diagnostic. Never fabricate an unchanged graph. A diagnostic may fail the reply contract, but it cannot erase the edit.
6. If replay does not equal the retained/final projection, fail closed with the existing typed artifact-consistency family; do not write either graph as if it were authoritative.

**Seven expected flips, all backed by an already accepted, judge-aligned Δ:**

1. `audio-audio-processing-with-chatterbox-tts-and-vc-b55994` — Δ d1 replaces `SaveAudioMP3` with `SaveAudio`; retained IR is correct.
2. `image-animatediff-video-generation-with-vae-d20410` — Δ d1 changes `EmptyLatentImage.batch_size` from 16 to 8.
3. `image-image-editing-with-qwen-image` — Δ d1 changes uid 133's prompt to match lighting, shadows, color temperature, tone, and exposure; the later apply-cap error currently erases it.
4. `image-style-transfer-using-ip-adapter` — Δ d1 sets `StyleModelApply` uid 12 `strength=2.0`; the later apply-cap error currently erases it.
5. `image-two-stage-qwen-image-generation` — Δ d1 changes `LatentUpscaleBy` uid 53 from `bislerp` to `bilinear`; the later apply-cap error currently erases it.
6. `multi-3d-preview-and-image-output-workflow-d93baf` — Δ d1 sets `SaveGLB.filename_prefix='3d/moge-top-down'`; only the outer projection says unchanged.
7. `multi-image-to-video-generation-with` — Δ d1 sets KSampler uid 3 to 30 steps and `dpmpp_2m`; only the outer projection says unchanged.

**Explicit non-credits:**

- `image-image-comparison-and-enhancement-with-florence-007018` has a real Δ, but it only adds five `ImageBlend` nodes; the requested independent slider wiring is missing. Preserve it as partial evidence, but do not project a pass.
- `audio-tts-narration-using-indextts-2` has a real earlier Δ, but the added Qwen emotion node is dead-ended and the attempted rewire uses a nonexistent output. Visibility is not correctness.
- `3d-generates-a-3d-mesh-from` has a promising `threshold=0.8` Δ only in a resumed transcript after the judged assessment timestamp. It is a regression test for state preservation, not an expected flip until a clean rerun proves it.

### P1 — one undifferentiated continuation/retry pool lets research consume the ability to edit or answer (incremental expected: **1**, with one additional contingent case)

**Code:** `vibecomfy/executor/two_step.py:690,716,760-763` defines/enforces one `max_model_continuations=64`; `vibecomfy/executor/agent_backend.py:678-692` charges every model turn to it; `vibecomfy/executor/two_step_session.py:874-903` folds prior budget records back into a reused session; per-message adapt apply/replacement caps originate at `vibecomfy/executor/two_step.py:321-322` and are terminally checked in `agent_backend.py:779-791`.

**Fix shape after P0:** retain the total 64 ceiling but partition admission by purpose, not by tool count: research/discovery 40, edit/recovery 16, final synthesis/reply 8. Research may not borrow the edit/reply reserve. A successful apply closes research for that message and enters reply-only mode. Repeated timeout/no-results for the same class/query family must transition to graph-local action or a grounded terminal outcome, not restart the same search. Start each harness attempt with a fresh budget epoch/session id; production conversation history may remain durable, but an r4/r5 test budget must not starve an r6 measurement.

**Expected flip:**

- `image-dual-checkpoint-xl-image-generation-with-refin-c9df19` — reserve synthesis capacity and reuse the 337 collected results instead of returning a count-only budget stub. This remains conditional on the final reply citing its model claims, so the expected increment is one, not guaranteed.

**Contingent, not in the projection:**

- `multi-image-to-3d-object-generation-with-background-1a7f84` — a bounded research-to-edit transition can recover the already grounded `VHS_VideoCombine` uid 8 GIF→WebP alpha-preserving edit, but the r6 agent instead pursued unschematized Rembg fields. Require a clean run before credit.
- `3d-3d-shape-generation-and-export-workflow-8800a9`, `audio-transcribes-audio-appends-text-regenerates`, `multi-crops-face-previews-it-sets`, and `multi-image-to-video-with-llm` also hit a budget, but budgeting alone cannot resolve their missing target/field/port authority. Do not count them here.

### P2 — the typed reference contract does not fully match what the render/tool result teaches (expected: **1**)

**Code:** `vibecomfy/executor/edit_tools.py:262-290` accepts a binding, bare uid, or numeric node id but not a render-style `uid:` prefix or dict reference; `edit_tools.py:574-587,664-686` turns two semantic resolution misses into a terminal no-candidate latch; `edit_tools.py:648-653` labels minted uids as `bindings`; class-derived names come from `vibecomfy/porting/edit/session.py:241-270` / `vibecomfy/porting/emit/emit_kwargs.py:200-233`.

**Fix shape:** normalize only the exact render-visible `uid:<uid>` spelling to the retained-IR uid; reject dict references as malformed arguments with the accepted syntax and without consuming a semantic replacement; return both the minted uid and the actual class-derived binding after `add_node`; and assert render/session revision parity before dispatch. For `edit_batch`, treat `add_node(name=...)` as an operation-local alias only: after the add sub-op mints a uid, the sequential COW builder resolves later sub-ops' use of that alias to the canonical class-derived binding/uid. The alias must not be persisted as a second session name map. Resolution still uses the retained/sequential IR—never a raw-graph fallback.

**Expected flip:**

- `multi-svd-image-to-video-with-webp-and-png-output-bd3afb` — the agent had the correct `ImageFromBatch(batch_index=0,length=1)` insertion, but used dict, `uid:4`, and title-as-binding spellings until the two-strike latch blocked the correct retry.

**Not credited yet:** the bare `target='2'` failure in `3d-3d-shape-generation-and-export-workflow-8800a9`, and analogous failures in `3d-converts-image-to-3d-model` / `audio-acestep-audio-generation-and-processing-workfl-1b1360`, prove a render/session hydration divergence, not a missing bare-uid parser branch—the current checkout already resolves bare uids. First reproduce the revision mismatch in the run environment; do not add a second resolver authority to chase it.

### P3 — authoritative custom-node schemas/ports are absent (expected later: **3 conditional flips**, zero in the immediate score)

**Code:** provider composition enters the edit session at `vibecomfy/executor/two_step.py:1359-1411`; named-field validation is at `vibecomfy/porting/edit/_op_validate.py:107-163`; unknown add-node classes are produced at `vibecomfy/porting/edit/_interpret.py:489`; live/authoring provider construction also exists in `vibecomfy/comfy_nodes/agent/_frag_orchestration.py:338-400`.

**Fix shape:** ingest provenance-backed runtime `object_info`/installed-pack schema into the existing composite provider and render named fields/ports from that same provider. Do not infer ports from guessed indices or invent cache rows. Distinguish a class genuinely not installed from a provider that merely failed to load it.

**Conditional flips after authoritative coverage exists:**

- `audio-transcribes-audio-appends-text-regenerates` — expose `Apply Whisper.model`, allowing `tiny→base`.
- `multi-crops-face-previews-it-sets` — expose the actual `ReActorFaceSwap` target-image input and LoadImage output, allowing the graph-local missing-edge repair.
- `multi-image-to-video-with-llm` — expose `String Replace (mtb)` / `StringFunction|pysssss` ports so the hardcoded append node can be bypassed.

Do not count `3d-3d-model-generation-and-preview-workflow-cc0df7` from schema work alone: `Rodin3D_Fusion` may genuinely be unavailable, in which case the honest product is a grounded capability outcome rather than a fabricated edit. Likewise, do not count `DetailDaemonSamplerNode`, `HWMInference`, or `AudioFilter` from schema work alone. DetailDaemon/HWM questions require mechanistic documentation beyond field names; AudioFilter also shares the unresolved render/session revision issue.

### P4 — claims are not consistently attached to the evidence already collected (expected later: **2**, separate RC)

**Code:** `vibecomfy/executor/contracts.py:2741,2856-2915` enforces grounding; `vibecomfy/executor/agent_backend.py:899-924` retries then fails closed; the semantic judge receives only UI inventory at `tests/live_agentic_harness/intent_judge.py:1302,1310-1316`.

**Fix shape:** require submit-time `claim_refs` to cite the successful `node_schema`/retrieved-document ids used by the answer, and retain the substantive answer separately from the guard diagnostic. Do not declare `hivemind_search` snippets authoritative and do not let an uncited answer bypass the gate.

**Expected restorations:**

- `image-gemini-prompt-splitter-and-text-display-workfl-caae97` — the ClaudeNode availability claim exactly matched `node_schema(ClaudeNode)` but submitted empty evidence ids.
- `image-animatediff-image-to-video-with-latent-composi-17dc9b` — the r5 answer passed; the r6 answer was replaced by the numeric-grounding guard despite a successful `node_schema(LatentComposite)` call. Credit only after the recommendation-shaped numeric claim cites applicable evidence.

`image-image-processing-with-sharpening-film-grain-an-9aa0f1`, `multi-3d-gaussian-splatting-from-video-with-hunyuan-432652`, and `audio-acestep-audio-generation-with-detail-daemon-f0859f` remain unprojected: their required mechanistic claims lack a proven authoritative evidence source, and DetailDaemon also has a digest-vs-assessment discrepancy.

## 2. Expected score after the immediate implementation

**Point estimate: 12/30 passing. Conservative range: 11–13/30.**

- Baseline is the terminal r6 score: 5/30.
- P0 contributes seven named flips with already-landed, judge-aligned edits: `chatterbox`, `animatediff-vae`, `qwen-image-edit`, `ip-adapter`, `two-stage-qwen`, `3d-preview`, and `multi-image-to-video-generation`.
- The 12/30 point estimate gives no credit to P1-P4 and assumes all five current r6 passes remain passes.
- The 11 lower bound allows one “landed but semantically judged differently” variance loss.
- The 13 upper bound credits the cheap P2 resolver hardening for `multi-svd-image-to-video-with-webp-and-png-output-bd3afb` after a terminal passing assessment.

Do not advertise 13+ from unit tests. Round 1 projected 10–12 but delivered 5; only terminal `assessment.json` results on the implementation commit move the score.

## 3. ONE next implementation target — accepted-Δ terminal projection

Implement one shared function, conceptually:

```python
project_terminal_product(
    *, session_store, session_id, edit_runtime, route,
    reply, failure=None, claim_validation=None,
) -> TerminalProduct
```

`TerminalProduct` must contain the canonical accepted ids and ops from the transcript, the replayed retained graph, evidence/lens ids, current budget, reply, and optional failure diagnostic. It is used by normal submit, budget stop, parse failure, grounding failure, and outer response construction. There must be no separate success-only state extractor.

The projector's invariants are:

- accepted ids are derived by transcript replay, not copied from model prose;
- retained graph hash equals replay(`base_graph`, accepted ops);
- non-empty accepted ids imply a graph-bearing edited product and `graph_unchanged=false`;
- zero accepted ids imply no edit claim;
- `report.execute.accepted_delta_ids`, top-level compatibility ids, candidate/final graph, and artifact manifest are projections of that one object;
- after acceptance, a second edit/apply is a recorded soft stop, not a destructive terminal error;
- replay mismatch or missing retained graph fails closed without writing false evidence.

Required tests:

1. Accepted edit + second apply-cap attempt returns the first Δ and its graph, with `ok=true`, and records the second attempt as unapplied.
2. Accepted edit + continuation exhaustion, host-action parse failure, and grounding failure each preserve identical accepted ids and replayed graph; only the diagnostic/reply status differs.
3. A success response with ids nested under `report.execute` projects the same ids top-level and overrides stale `graph_unchanged=true` / `route_not_applyable` stamping.
4. `persist_universal_ui_evidence` emits `final.ui.json` from retained replay and rejects `final==original` for non-empty Δ.
5. Florence and IndexTTS fixtures prove that exposing a partial/wrong Δ does not itself satisfy semantic intent; the product is visible, but the assessment remains honest.

## 4. Secondary fixes to bundle

Bundle only the cheap P2 contract corrections that are directly reproduced by batch 5:

- accept exact `uid:<uid>` aliases by normalizing them to retained-IR uids;
- classify dict-shaped node refs as malformed syntax, return the legal forms, and do not consume a semantic rejection;
- make the sequential `edit_batch` builder resolve an `add_node(name=...)` alias for later sub-ops in that same atomic batch, backed by the minted uid and canonical class-derived binding but never stored as session authority;
- rename the current structured result's uid-only `bindings` payload or add explicit `{binding, uid}` entries derived after apply, so the agent is told the same class-derived name the next resolver accepts.

These changes have one credible upside scenario (`multi-svd-image-to-video-with-webp-and-png-output-bd3afb`) but are not included in the 12/30 point estimate because intra-batch new-node reference behavior still needs an end-to-end passing run.

Do not bundle broad schema ingestion or the per-purpose budget redesign into this RC. Both are real, but they enlarge the causal surface and would make a failed rerun impossible to attribute. Freeze their reproductions now; implement P1 next if P0 meets its gate.

## 5. What NOT to do

- Do not edit judges, rubrics, expected outcomes, thresholds, pass aggregation, or safe-refusal allowlists.
- Do not treat an empty Δ as success because the reply sounds right, and do not make the judge read a private transcript as a substitute for producing the correct public artifact.
- Do not raise the global continuation cap above 64. Partition purpose and reserve synthesis/edit capacity in P1.
- Do not turn research timeouts or repeated `no_results` into unbounded retries.
- Do not resolve targets against the raw request/render graph as a fallback; the retained IR remains the one authority.
- Do not accept positional `widget_N` references, guess ports, or invent custom-node schema/cache entries.
- Do not count Florence, IndexTTS, or the post-assessment mesh edit as flips merely because a Δ becomes visible.
- Do not weaken `grounding_violations`, count uncited search snippets as documentation, or surface the substantive-but-uncited answer as a passing product.
- Do not special-case any scenario id, uid, field value, or judge wording.

## 6. Implementation split and acceptance gate

### DeepSeek Flash — verifier (read-only)

Before implementation, freeze a seven-row proof ledger for the P0 scenarios: transcript/session id, accepted Δ id and canonical ops, retained-graph hash, original/final equality, current outer response fields, and exact terminal assessment. Freeze the three explicit non-credits too, so visibility is not mistaken for semantic completion.

Review the diff for one terminal projector, transcript/replay authority, no success-only extractor, no raw-graph fallback, no judge/rubric/grounding edits, and no global-cap increase. Independently replay every accepted batch over its original graph and compare it with the projected final artifact. For the P2 bundle, verify that `uid:4`, dict-ref correction, same-batch `first_frame_extractor` alias resolution, and returned `{binding, uid}` all use the retained/sequential IR.

After implementation, run the focused seven P0 scenarios, the batch-5 P2 scenario, all five current r6 passes as regression guards, and the three non-credit scenarios. Read terminal `assessment.json`; tool `ok`, a Δ id, or a unit test is not a flip.

### DeepSeek Pro XHARD — implementer

Implement the shared terminal-product projection through `agent_backend.py`, `two_step.py`, the outer response contract, and `artifacts.py`; add the soft commit stop after the first accepted apply; add replay/hash invariants and the tests in §3. Then add only the three P2 secondary corrections. Do not touch budget ceilings/partitioning, schema providers/caches, prompts, judges, scenarios, or grounding policy in this RC.

### Acceptance gate

1. Every terminal path after acceptance returns the same accepted ids, canonical ops, replayed graph, and graph hash as the transcript authority.
2. `accepted_delta_ids != []` can never coexist with `graph_unchanged=true`, `route_not_applyable`, a missing candidate/final graph, or `final.ui.json == original.ui.json`.
3. Accepted-batch replay equals the emitted final IR/UI for all seven P0 fixtures; untouched nodes, edges, slots, and widget values round-trip unchanged.
4. The second-apply soft stop returns the already-verified edit without applying the second candidate and without reporting a false failure/no-op.
5. At least **6 of the 7** P0 scenarios pass terminal assessment on a clean committed run, with **zero regressions among the 5 current r6 passes**. The target is 7/7; 6/7 is the minimum gate against model/judge variance.
6. The P2 bundle is credited only if `multi-svd-image-to-video-with-webp-and-png-output-bd3afb` passes; otherwise record it as unresolved without lowering the P0 gate.
7. Florence, IndexTTS, and the post-assessment mesh case must remain honestly classified if their visible Δ still fails the requested semantics. No bar-softening.

Below the P0 gate triggers a new evidence analysis of the failed terminal paths. It does not trigger judge changes, a larger budget, or credit for internal tool success.
