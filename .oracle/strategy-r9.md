# r9 improvement strategy — one-step pipeline

## Decision

Fix the **producer side of the landed-operation contract** next. The canonical
terminal product already has the only evidence that matters — `accepted_batch`
— but the public response never derives
`change_details.landed_operation_count` from it. The assessor therefore rejects
correct, landed, intent-judge-approved edits because a legacy compatibility
field is absent.

This is the highest-confidence and highest-count single RC in the r9 findings:
**five named deterministic flips**. It does not change a verdict, relax a
rubric, infer an edit from prose, or create another delta representation. It
makes the response envelope faithfully project the accepted-delta authority.

There is an evidence-integrity caveat in the supplied corpus. Batch 1 is headed
as `one-step-30-r5`, batch 4 contains only four of an asserted six scenarios,
and several digest/post-fix reassessments contradict the terminal artifacts the
findings identify as authoritative. Therefore the projection below counts only
the five scenarios for which a finding explicitly says (a) the accepted edit
landed, (b) the intent judge passed it, and (c) the missing landed count is the
decisive error. Undocumented or contradictory rows receive no score credit
(philosophy #1 and #12).

## 1. Judgment of the failure classes

### Measurement bugs — fix first, high confidence

1. **Missing landed-operation projection (five proven false failures).**

   - Producer: `vibecomfy/executor/agent_backend.py:1094-1098` creates a
     three-key `durable_response`; `vibecomfy/executor/two_step_session.py:1421-1494`
     serializes the canonical terminal product without `change_details`; and
     `vibecomfy/executor/contracts.py:2534-2606` can lift that field only if the
     producer supplied it.
   - Consumer: `tests/live_agentic_harness/assessor.py:282-287,796-825` correctly
     fails closed when a response claims `graph_unchanged=false` but supplies no
     positive landed count.
   - Judgment: **measurement-contract defect, not a model failure and not a bad
     judge verdict**. The guard's invariant is sound; the executor envelope is
     incomplete.
   - Proven affected scenarios: `audio-audio-processing-with-chatterbox-tts-and-vc-b55994`,
     `audio-tts-narration-using-indextts-2`,
     `image-animatediff-video-generation-with-vae-d20410`,
     `image-style-transfer-using-ip-adapter`, and
     `multi-3d-preview-and-image-output-workflow-d93baf`.

2. **The scored artifact can freeze at an earlier submit.**

   - `multi-image-to-video-generation-with` accepted d1 and reached a later
     successful submit, while the judged `response.json`/`final.ui.json` retained
     the earlier no-change submit.
   - Relevant boundary:
     `vibecomfy/executor/two_step_session.py:1701-1768,1771-1855` and
     `vibecomfy/agent/artifacts.py:447-521`.
   - Judgment: **measurement/finalization defect**, high-confidence pipeline
     fix, but separate from the missing-count RC. The terminal checkpoint must
     be closed before artifacts are published.

3. **A post-acceptance host-action parse failure can erase the product.**

   - `3d-generates-a-3d-mesh-from` landed d1 (`threshold=0.8`) and submitted a
     correct answer, but a later `unknown host action None` replaced it with a
     failure/unchanged artifact.
   - Relevant code: `vibecomfy/executor/agent_backend.py:418-433,815-818` and the
     common terminal projector at `agent_backend.py:670-699`.
   - Judgment: **pipeline terminal-state defect**, not a semantic model failure.
     A parse diagnostic may fail the reply, but it may not erase an already
     accepted batch.

### Pipeline capability defects — real and fixable, but lower immediate yield

1. **Render/edit binding divergence.** `resolve_target` at
   `vibecomfy/executor/edit_tools.py:262-290` accepts names/uids from the retained
   IR, yet several sessions rejected the numeric ids and class-derived names the
   render itself supplied. `_SequentialBuildSession.apply` also swallows an
   intra-batch add failure at `edit_tools.py:430-474`, so a newly added node can
   remain unresolvable in later operations in the same batch. This is a
   pipeline defect under philosophy #2/#9, not model incapacity.

   High-confidence candidate: `3d-converts-image-to-3d-model` (the intended
   `Polygon_count` edit was explicit). `3d-3d-shape-generation-and-export-workflow-8800a9`
   is also promising, but continuation exhaustion is an independent blocker.
   `audio-acestep-audio-generation-and-processing-workfl-1b1360` and
   `multi-svd-image-to-video-with-webp-and-png-output-bd3afb` require multi-op
   wiring and are contingent; the latter's post-fix node remained orphaned, so
   resolver success alone must not be scored as a flip.

2. **Missing authoritative custom-node field/port schemas.** The typed tool was
   right to reject `widget_0` and guessed ports. The capability gap is that the
   shared schema surface did not expose a named `Apply Whisper` model field for
   `audio-transcribes-audio-appends-text-regenerates`. This is a fixable
   pipeline/schema-coverage defect, but only provenance-backed runtime schema is
   acceptable; positional-widget fallback would violate philosophy #9.

3. **Continuation partitioning did not engage in the observed
   `3d-3d-shape-generation-and-export-workflow-8800a9` run.** The declared
   constants at `vibecomfy/executor/two_step.py:711-713` and admission checks at
   `vibecomfy/executor/agent_backend.py:831-845,970-1018` produced no
   `purpose_denied` event before research consumed the session cap. This is a
   pipeline enforcement defect. It is an enabler, not a standalone flip while
   target resolution also fails.

4. **Grounding failure is converted into a useless placeholder.** For
   `image-image-processing-with-sharpening-film-grain-an-9aa0f1`, the gate
   correctly detected unsupported causal claims, but the public product became
   only the violation string. The destructive replacement behavior is a
   pipeline product defect; the underlying uncited claims are still a model
   failure. Fixing the product surface must preserve the grounding failure, not
   pass the original answer.

5. **Grounded custom-node absence is mislabeled as generic no-change.**
   `3d-3d-model-generation-and-preview-workflow-cc0df7` established that
   Rodin3D Fusion was not installed, but emitted `no_change` rather than the
   already sanctioned `requires_custom_nodes` outcome. This is a response-
   contract/prompt defect. The correct result is an honest typed refusal, not a
   fabricated edit.

### Model-capability failures — prompt-fix cautiously or accept variance

- `audio-acestep-audio-generation-with-detail-daemon-f0859f`: the final answer
  over-refused despite graph-local values and a retrieved cinematic precedent.
  A prompt can emphasize bounded, explicitly qualified graph-grounded advice,
  but unsupported mechanism or numeric claims must remain disallowed.
- `multi-crops-face-previews-it-sets`: the model held a graph-grounded diagnosis
  but asked instead of making a narrow same-class edit, then guessed nonexistent
  ports. This is the philosophy #5 failure mode. Prompting may help, but no flip
  is deterministic without a concrete correct operation.
- `multi-ai-video-upscaling-with-detail-daemon-sampler-673197` and
  `image-qwen-image-inpainting-with-controlnet-09fc64`: the model made causal or
  field-name claims not licensed by retained evidence. The grounding guard and
  semantic judge behaved correctly. These are model/evidence-attachment
  failures; do not weaken the bar.
- `image-image-editing-with-qwen-image`: the link to `image2` landed, but the
  model admitted its lighting effect was unverified and the operation did not
  implement lighting/color matching. This is genuine edit quality, not harness
  failure.
- `multi-svd-image-to-video-with-webp-and-png-output-bd3afb`: even when the
  `ImageFromBatch` node becomes visible, it is orphaned and unwired. The original
  resolver failure is pipeline-owned; the surviving product is still
  semantically incomplete and must fail.

## 2. Prioritized improvement plan

### P0 — derive landed count from the canonical accepted batch

- **Files:** `vibecomfy/executor/two_step_session.py:1421-1494,1771-1855`;
  propagation at `vibecomfy/executor/two_step.py:1201-1210,1255-1262` and
  `vibecomfy/executor/contracts.py:2534-2606`.
- **Fix shape:** while serializing `TerminalProduct`, construct the durable
  response projection and set
  `change_details.landed_operation_count = len(accepted_batch)`. Overwrite any
  caller-supplied count; it is derived metadata, never an independent claim.
  Preserve other legitimate `change_details` keys. Emit `0` for an empty batch.
  Let the existing contract lift this object top-level. Do not modify
  `_landed_operation_count()` or the G0R guard.
- **Expected flips: +5, high confidence:**
  `audio-audio-processing-with-chatterbox-tts-and-vc-b55994`,
  `audio-tts-narration-using-indextts-2`,
  `image-animatediff-video-generation-with-vae-d20410`,
  `image-style-transfer-using-ip-adapter`, and
  `multi-3d-preview-and-image-output-workflow-d93baf`.
  Each finding says the intent judge passed all criteria and the missing count
  was the decisive/only mechanical error.

### P1 — close and publish the last scored message checkpoint atomically

- **Files:** `vibecomfy/executor/two_step_session.py:1701-1768,1771-1855`;
  `vibecomfy/executor/agent_backend.py:670-699,815-818`;
  `vibecomfy/agent/artifacts.py:447-521`.
- **Fix shape:** bind finalization to the closed message checkpoint; fold the
  ledger only through that checkpoint; choose the last terminal submit in that
  message; preserve any accepted batch across later diagnostics; then publish
  response, implementation result, and final UI from that single object. Add a
  bounded corrective retry for a malformed host action only when no terminal
  submit exists; after a valid submit, do not make another model output part of
  that scored message.
- **Expected flips: +2 after P0, high confidence but separate:**
  `multi-image-to-video-generation-with` and
  `3d-generates-a-3d-mesh-from`.

### P2 — enforce one render/resolver binding authority

- **Files:** `vibecomfy/executor/edit_tools.py:262-290,430-474,570-605` and
  `vibecomfy/porting/edit/_gates.py:300-312`.
- **Fix shape:** at message start assert parity between render-visible
  `{binding, uid, node_id}` and the retained IR's resolver map. A mismatch is a
  typed hydration failure and does not consume the model's replacement permit.
  In an atomic batch, resolve a new node's local alias to the uid minted by the
  preceding `add_node`; never persist that alias as a second authority and never
  fall back to raw request JSON.
- **Expected flips: +1 high confidence:**
  `3d-converts-image-to-3d-model`.
- **Contingent, not projected:**
  `3d-3d-shape-generation-and-export-workflow-8800a9`,
  `audio-acestep-audio-generation-and-processing-workfl-1b1360`, and
  `multi-svd-image-to-video-with-webp-and-png-output-bd3afb` because each has an
  additional budget, schema, or edit-completeness blocker.

### P3 — surface authoritative custom-node schemas and typed blocked outcomes

- **Files:** schema provider construction near
  `vibecomfy/executor/two_step.py:1359-1411`; named-field validation at
  `vibecomfy/executor/edit_tools.py:250-256,312-320`; refusal instructions at
  `vibecomfy/executor/prompts.py:762-794`.
- **Fix shape:** load installed runtime `object_info` into the existing composite
  provider; render and edit against that same provider. Separately require a
  proved missing named class to terminate as `requires_custom_nodes`, never
  generic `no_change`.
- **Expected flips: up to +2, conditional:**
  `audio-transcribes-audio-appends-text-regenerates` and
  `3d-3d-model-generation-and-preview-workflow-cc0df7`.

### P4 — improve act/answer behavior without relaxing grounding

- **Files:** submit/grounding loop at
  `vibecomfy/executor/agent_backend.py:1019-1058`; grounding contract at
  `vibecomfy/executor/contracts.py:2886-2945`; behavior guidance in
  `vibecomfy/executor/prompts.py:762-834`.
- **Fix shape:** require the corrective continuation to preserve supported
  graph facts, remove or qualify only unsupported claims, attach actual evidence
  ids, and answer or perform a narrow graph-local operation when the graph itself
  licenses it. Never promote an answer that still fails grounding.
- **Expected flips: 0 guaranteed; 1-2 model-variance upside:**
  `audio-acestep-audio-generation-with-detail-daemon-f0859f` and
  `multi-crops-face-previews-it-sets`. The sharpening, upscaling, and inpainting
  cases need evidence-complete content before they can honestly pass.

## 3. The ONE next implementation target

Implement **canonical landed-count projection** in `TerminalProduct`.

Conceptual contract:

```python
def terminal_durable_response(product: TerminalProduct) -> dict[str, Any]:
    response = dict(product.durable_response or {})
    details = dict(response.get("change_details") or {})
    details["landed_operation_count"] = len(product.accepted_batch)
    response["change_details"] = details
    return response
```

`TerminalProduct.to_outcome_dict()` must use that projection rather than expose
the caller's pre-projection dictionary unchanged. `two_step.py` then places the
same dictionary into `ImplementationResult.durable_response`, and
`ExecutorResult.to_dict()` performs its existing top-level lift. There is still
one durable delta: `accepted_batch`. The count is a compatibility projection of
that batch, just as `accepted_delta_ids` is derived metadata.

Required invariants and tests:

1. One accepted delta containing one op serializes landed count `1`; one delta
   containing two ops serializes `2`.
2. Empty `accepted_batch` serializes `0` and cannot claim
   `graph_unchanged=false` merely because a caller supplied a stale positive
   count.
3. A caller-supplied count is overwritten by `len(accepted_batch)`; two
   authorities cannot disagree.
4. Success, budget stop, grounding failure, and host-action parse failure all
   project the same count for the same accepted batch.
5. End-to-end `ExecutorResult.to_dict()` contains top-level
   `accepted_batch`, derived `accepted_delta_ids`, and
   `change_details.landed_operation_count`, all mutually consistent.
6. The existing G0R assessor tests remain strict. Add integration fixtures for
   the five named scenarios' response shapes; correct intent products pass,
   while `image-image-editing-with-qwen-image` and the orphaned
   `multi-svd-...-bd3afb` edit remain failed by the intent judge.

Acceptance gate: all five named P0 scenarios pass their terminal
`assessment.json` on a clean committed rerun, all six currently reported passes
remain passes, and no response can serialize a landed count different from the
number of operations in its accepted batch. Internal unit success alone is not
a flip.

## 4. What NOT to do

- Do not edit assessor verdict logic, remove G0R, infer success from prose, or
  exempt one-step responses from the landed-count requirement.
- Do not maintain a separately mutable operation count. Derive it every time
  from the canonical `accepted_batch`.
- Do not count a visible delta as semantically correct. The Qwen lighting link
  and orphaned `ImageFromBatch` must remain failed.
- Do not make the judge read private transcripts to rescue a bad public
  artifact. Produce the correct terminal product.
- Do not soften grounding, accept uncited causal claims, invent widget names,
  or treat search snippets as authoritative documentation.
- Do not accept positional `widget_N` edits or guessed ports; acquire a
  provenance-backed schema and keep names over indices.
- Do not add raw-request resolver fallbacks, parallel graph snapshots, or
  another serializer. Render, edit, replay, and assessment must share the same
  retained IR and named ingest/emit doors.
- Do not raise continuation/replacement budgets, hard-code scenario ids/uids,
  or special-case expected values.
- Do not claim the contradictory or missing batch rows are resolved. Regenerate
  their findings from immutable terminal artifacts on the implementation
  commit.

## 5. Expected score after the next implementation

**Point estimate: 11/30. Conservative range: 10-11/30.**

- Baseline supplied for r9: approximately **6/30**.
- P0 adds **five named, judge-confirmed flips**.
- The lower bound allows one live-model/regression variance loss; the acceptance
  target is 11/30 with all existing passes preserved.
- P1-P4 receive no credit in this projection. If a clean rerun demonstrates that
  the current terminal projector has already recovered the stale-submit and
  post-parse accepted batches, those scenarios may also flip under P0, yielding
  upside to roughly **13/30**; the contradictory supplied findings are not
  strong enough to book those two points in advance.

The next round should publish a scenario-by-scenario flip ledger from terminal
`assessment.json`, plus response checkpoint, accepted-batch digest, landed
count, and final-UI hash. That is the evidence required to call the measurement
contract fixed.
