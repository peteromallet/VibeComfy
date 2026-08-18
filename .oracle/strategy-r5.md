# r5 improvement strategy — one-step pipeline

## Decision

Fix the edit-session ingest door first. It is the only root cause with multi-scenario leverage and it is directly reproduced: the render path sees the real graph while `EditSession` retains a zero-node IR. The immediate RC should include the accepted-delta/final-artifact consistency guard because it is cheap, adjacent, and necessary to make the fix measurable. Do not change the judge, relax grounding, or raise budgets in this RC.

## 1. Prioritized root causes

### P0 — edit session ingests the request through the wrong named door (expected: 7–9 flips; point estimate: 8)

- **Code:** `vibecomfy/porting/edit/_gates.py:300-307`, reached through `vibecomfy/porting/edit/session.py:224-225` and `vibecomfy/executor/two_step.py:1099-1101,1359-1368`. The visible failure is emitted by `vibecomfy/executor/edit_tools.py:262-290`.
- **Cause:** `_workflow_from_ui` always calls `from_ui(..., use_comfy_converter=False)`. Envelope and bare-API inputs therefore silently become zero-node workflows. Rendering independently dispatches by shape at `vibecomfy/porting/render.py:132-140`, so names and uids shown to the agent do not exist in the editor's retained IR. This violates philosophy #1 (the product evidence cannot land), #2 (two ingest authorities), #5 (a correct action is prevented), and #6 (rejection substitutes for mechanical verification).
- **Fix shape:** use one internal format-aware ingest dispatcher for render and edit: envelope → `from_envelope`, LiteGraph UI → `from_ui(..., use_comfy_converter=False)`, bare API → `from_api`. Preserve `schema_provider` on UI/API paths. Reject unknown shapes, and reject a non-empty source node set that decodes to zero nodes. Do not allow `_two_step_edit_session` to turn this typed ingest failure into `None` and silently continue without editing.
- **Host proposal, refined:** dispatching `_workflow_from_ui` with `detect_workflow_shape` like `render.py:132-138` is directionally correct, but `envelope → from_envelope; else → from_ui` is incomplete. Batch 2 proves that bare-API graphs also decode to zero nodes (`audio-transcribes-audio-appends-text-regenerates`, `image-image-editing-with-qwen-image`). The implementation must have all three branches. Copying the dispatch into a second site also preserves the authority split; prefer the existing internal `_named_import(...)` in `vibecomfy/ingest/normalize.py:1260-1292` (offline converter mode), and have render and edit delegate to that same helper or an equivalently centralized internal helper.
- **Expected flips, high confidence:**
  - `3d-3d-shape-generation-and-export-workflow-8800a9` — exact target and value (`UltraShapeRefine.shape_refine_strength=0.4`) were already attempted.
  - `3d-converts-image-to-3d-model` — correct target/field were attempted; value enum still needs schema validation before acceptance.
  - `audio-acestep-audio-generation-and-processing-workfl-1b1360` — exact render names/uids and an existing `remove_hiss` building block were used.
  - `audio-transcribes-audio-appends-text-regenerates` — simple named widget edit, `Apply Whisper` `tiny→base`.
  - `image-animatediff-video-generation-with-vae-d20410` — simple named widget edit, `EmptyLatentImage.batch_size 16→8`.
  - `image-image-editing-with-qwen-image` — correct prompt node/field and concrete lighting-continuity edit were attempted.
- **Expected flips, contingent but included in the 7–9 range:**
  - `3d-generates-a-3d-mesh-from` — the threshold diagnosis was correct; expected to flip if the accepted edit prevents the downstream malformed final action, but the terminal parse error is an independent residual risk.
  - `audio-audio-processing-with-chatterbox-tts-and-vc-b55994` — the MP3→WAV replacement is correct, but deletion-call syntax degraded after rejection; a resolved base should help, not guarantee, acceptance.
  - `audio-tts-narration-using-indextts-2` — the intended rewire is correct, but this also needs the P1 artifact-consistency guard below.
- **Explicit non-flip:** `3d-3d-model-generation-and-preview-workflow-cc0df7` shares the empty-IR symptom but should not be credited to P0. `Rodin3D_Fusion` is absent and the request is not representable; the correct product is a grounded `requires_custom_nodes` outcome, not an edit.

### P1 — accepted delta can be hidden by response projection (incremental expected: 0–1; bundle with P0)

- **Code:** `vibecomfy/agent/artifacts.py:336-397`.
- **Cause:** `_route_projects_final_from_original` treats `graph_unchanged=true` as authoritative even when `accepted_delta_ids` is non-empty. In `audio-tts-narration-using-indextts-2`, `d1` was accepted, but `final.ui.json` was projected from the original, so the judge correctly saw an empty delta. This violates philosophy #1 and #12.
- **Fix shape:** accepted delta evidence outranks prose. If `accepted_delta_ids` is non-empty, never project `final=original`; load the retained/candidate graph and verify that replaying the accepted batch over original equals the final edit projection. If the candidate is missing or replay does not match, fail closed with a typed artifact-consistency error rather than fabricating unchanged evidence.
- **Expected scenario:** `audio-tts-narration-using-indextts-2` (shared with P0; do not double-count it in the score).

### P2 — safe refusal is mislabeled as `no_change` (expected: 1 later flip)

- **Code:** refusal instructions at `vibecomfy/executor/prompts.py:762-773`, permissive self-assessment contract at `vibecomfy/executor/contracts.py:2062-2079`, and current assessor routing at `tests/live_agentic_harness/assessor.py:719-731`.
- **Cause:** the agent proved the class absent but emitted `no_change`, so the already-allowed grounded-refusal judge was never reached.
- **Fix shape:** tighten the product contract so a refusal grounded by a failed named `node_schema`/registry lookup is emitted as `requires_custom_nodes`; validate the label before submission. Do **not** infer refusal from prose in the assessor and do not broaden the assessor allowlist.
- **Expected scenario:** `3d-3d-model-generation-and-preview-workflow-cc0df7`.

### P3 — terminal budget fallback discards a substantive research answer (expected: 1 later flip, after tracing)

- **Code:** `vibecomfy/executor/agent_backend.py:549-570` and the `session_model_continuations` loop/budget in `vibecomfy/executor/agent_backend.py:573-975` / `vibecomfy/executor/two_step.py` budget checks.
- **Cause:** `image-dual-checkpoint-xl-image-generation-with-refin-c9df19` produced substantive replies, then three windows re-researched until 64/64 and replaced the product with a research-count stub. The earlier answer also contained uncited model names, so blindly retaining it would violate philosophy #12.
- **Fix shape:** first trace why a substantive reply did not terminate the research route. Then retain only the latest reply that has already passed claim-reference and grounding validation; on budget exhaustion return that validated product, never a count-only stub. Do not merely increase the cap.
- **Expected scenario:** `image-dual-checkpoint-xl-image-generation-with-refin-c9df19`.

### P4 — DetailDaemon question has no evidence surface compatible with its rubric (expected: 1 later flip, not part of this RC)

- **Code:** grounding rule `vibecomfy/executor/contracts.py:2860-2915`, prompt constraint `vibecomfy/executor/prompts.py:829-834`, and missing `DetailDaemonSamplerNode` coverage in `vibecomfy/porting/cache/object_info/comfy_core@object_info_comfyui_0.24.0.1.json`.
- **Cause:** the rubric requires mechanism and numeric trade-offs; the gate correctly requires evidence; no schema or authoritative fetched documentation exists. The final answer is therefore honest but vacuous.
- **Fix shape:** add a real, retrievable evidence source for the installed DetailDaemon node pack (schema plus authoritative documentation/precedent that actually supports mechanism and settings), then cite it. Schema names/ranges alone are insufficient for causal claims.
- **Expected scenario:** `audio-acestep-audio-generation-with-detail-daemon-f0859f`.

## 2. Expected score after the immediate RC

**Point estimate: 11/30 passing**, provisional because the r5 run is not final.

- Observed baseline: approximately 3/30 passing.
- P0 + bundled P1: eight expected flips from the nine named candidates above.
- Conservative range: **10–12/30**. Ten assumes only seven edit flips; twelve assumes all nine candidates flip.
- Do not add P2–P4 to the immediate projection. They are separate one-scenario targets and need their own evidence/run. If all three later fixes are proven, the evidence-backed upside becomes roughly 14–15/30, not a claimed score.

The immediate RC is successful only if terminal `assessment.json` verdicts move. Unit tests and accepted tool calls are necessary evidence, not scenario passes.

## 3. Next implementation target — ONE change

**Target:** make `EditSession` retain the same format-aware IR that render sees.

Concrete design:

```python
def _workflow_from_ui(self, raw_graph: Mapping[str, Any]) -> VibeWorkflow:
    workflow = _named_import(
        dict(raw_graph),
        schema_provider=self.schema_provider,
        use_comfy_converter=False,
    )
    _assert_nonempty_ingest_preserved(raw_graph, workflow)
    return workflow
```

`_assert_nonempty_ingest_preserved` should compare source node cardinality by detected shape (envelope mapping, UI list, or API node mapping), not merely `bool(raw_graph)`, because a metadata-bearing graph may legitimately contain zero nodes. Unknown shapes must raise. For a stronger one-authority result, make `render._coerce_workflow` call the same internal dispatcher instead of retaining a copied branch table. Keep the three named decoders as the actual doors.

Also change `_two_step_edit_session` (`two_step.py:1359-1368`) so ingest errors become a typed execute/request failure; the current broad `except Exception: return None` recreates the same silent no-edit behavior and defeats the guard.

Tests to add/update:

1. `tests/test_porting_edit_session.py`: envelope fixture enters `EditSession` with the full node/edge/uid set; a render-visible name and uid resolve; a named widget edit lands without losing untouched nodes.
2. `tests/test_porting_edit_session.py`: bare-API fixture does the same. This is mandatory; the host's envelope-only proposal would miss it.
3. Existing LiteGraph UI fixture remains on the offline `from_ui` path and preserves current round-trip behavior.
4. Unknown shape and a positive source node count decoded as zero nodes fail closed with a specific ingest diagnostic.
5. `tests/test_executor_two_step_continuity.py`: `_two_step_edit_session` plus the real typed tool runtime accepts one edit for both envelope and API inputs, returns `d1`, and retains the entire original graph plus the edit.
6. `tests/test_headless_agent_artifacts.py`: `accepted_delta_ids=['d1']` combined with erroneous `graph_unchanged=true` must persist the candidate/retained graph or fail closed; it must never write `final=original`.
7. Add a parity assertion: the uid/node set used by `render_text(raw)` equals the uid/node set held by `EditSession(raw)` for envelope, UI, and API fixtures.

## 4. Secondary fixes to bundle

Bundle only these two adjacent safeguards:

- **Accepted-delta projection invariant (P1):** cheap, directly reproduced, and required for honest measurement of `audio-tts-narration-using-indextts-2`.
- **Typed non-empty-ingest guard:** cheap and prevents this defect from returning as a silent zero-node/no-edit session.

Do **not** bundle an `image-dual-checkpoint` budget change. The artifacts explicitly leave the multi-window termination mechanism as `unknown_needs_human`, and the saved substantive answer contains ungrounded names. First obtain a trace and prove a candidate reply passed grounding; otherwise retaining it just exchanges a budget failure for a philosophy #12 failure.

## 5. What not to do

- Do not change intent/refusal judges, expected outcomes, thresholds, scenario rubrics, or pass aggregation to manufacture flips.
- Do not broaden `allowed_safe_refusal_outcome_kinds` or infer `requires_custom_nodes` from persuasive prose. Fix the emitted product contract.
- Do not weaken `grounding_violations`, permit uncited causal claims, or allow unsupported numeric recommendations for DetailDaemon/refiner answers.
- Do not raise the 64-continuation cap or loosen the two-rejection limit as the ingest fix. Those are downstream amplifiers, not the root cause.
- Do not add resolver fallbacks against the render's raw graph or parallel UI snapshot. That creates a third authority; resolution must use the retained IR.
- Do not special-case the twelve scenario ids or hard-code their node uids/values.
- Do not claim all nine P0 candidates have flipped from unit tests. `3d-generates-a-3d-mesh-from`, `audio-audio-processing-with-chatterbox-tts-and-vc-b55994`, and `audio-tts-narration-using-indextts-2` have explicit residual risks.
- Do not modify the object-info cache with invented DetailDaemon metadata. Only ingest provenance-backed schema/docs.

## 6. Implementation split and acceptance gate

### DeepSeek Flash — verifier/analyst (read-only)

- Before implementation, freeze the three-shape reproduction matrix: input shape, source node count, render uid/name set, EditSession uid/name set, and current failure.
- Turn the nine expected candidates into a flip ledger with the exact terminal artifact path and the residual risk noted above.
- Review the implementer's diff for a single dispatch authority, no raw-graph resolver fallback, no judge/rubric edits, and no swallowed ingest error.
- After implementation, run/inspect the targeted tests and independently verify the emitted final graph equals accepted-delta replay. On the live rerun, read terminal `assessment.json`, not executor `ok`.

### DeepSeek Pro XHARD — implementer

- Implement the centralized three-shape ingest used by EditSession (and render if needed to eliminate duplicated dispatch).
- Add the non-empty decode guard and typed failure propagation.
- Add the accepted-delta/final-artifact consistency guard.
- Add the tests listed above in one RC-scoped commit. Do not touch prompts, budgets, assessors, scenarios, or grounding policy.

### Acceptance gate

1. Targeted unit/integration tests pass for envelope, UI, and bare API.
2. Reproductions that were `0` nodes now retain their exact source node counts; render and edit uid/name sets match.
3. A named edit and uid edit both land, accepted-delta replay equals the retained/final edit projection, and untouched nodes/edges remain present.
4. Contradictory `accepted_delta_ids != []` plus `graph_unchanged=true` can no longer produce `final=original`.
5. Run from a clean committed HEAD and rerun the twelve analyzed scenarios plus the three current passing regression guards. Accept the RC as score-moving at **at least seven of the nine P0 candidate flips**, with no regression among existing passes. Record the terminal verdict and mechanism for every flip; below seven triggers another evidence analysis, not bar-softening.
