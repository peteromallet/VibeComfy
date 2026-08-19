# r7 improvement strategy — one-step pipeline, Round 3 (final)

## Decision

Implement **(b) final-session artifact capture** next: materialize the scored
`response.json`, `accepted_batch`, and `final.ui.json` from one locked terminal
snapshot of the durable session ledger.

This is no longer a pipeline-capability bet. Direct r7 evidence shows **11 failed
scenarios already have `accepted_delta_ids=["d1"]` in `response.json`**, while all
11 omit `accepted_batch` and emit a zero-node final graph. The judge deliberately
grades only `accepted_batch` (`tests/live_agentic_harness/intent_judge.py:411-445`),
so it reports an empty delta even though the durable transcript contains the
landed ops. In other words, r7 is measuring the wrong product.

Target (a), early-turn resolution, remains real but is not the first move. The
exact early degenerate state is `unknown_needs_human`, current local reproduction
resolves the same names, and r7 proves that many correct edits already land. Target
(c), raw-UI parsing, is an essential guard in this RC but has no standalone score
credit: its false “0 nodes / removed all nodes” narratives do not turn a wrong edit
into a right one.

This ordering follows philosophy #1, #2, #11, and especially #12: expose the
accepted delta honestly before changing the agent, resolver, or grading bar.

## 1. Prioritized root causes

### P0 — terminal projection preserves delta IDs but drops the accepted delta and corrupts the final graph (expected: **9 flips**)

**Code and mechanism**

- `vibecomfy/executor/two_step_session.py:1405-1453`: `TerminalProduct` contains
  `accepted_ops`, but `to_outcome_dict()` emits only `accepted_delta_ids`; the
  landed ops never reach the public product.
- `vibecomfy/executor/two_step_session.py:1473-1542` derives IDs and ops from the
  durable transcript, but preserves the caller's pre-projection
  `durable_response` instead of constructing the final response from that loaded
  state.
- `vibecomfy/executor/agent_backend.py:1073-1099` builds `durable_response` with
  only `reply`, `session_id`, and `route` before terminal projection.
- `vibecomfy/executor/two_step.py:1188-1226,1238-1275` forwards accepted IDs and
  the graph, but not the canonical accepted batch, into `ImplementationResult`.
- `vibecomfy/executor/contracts.py:2580-2604` projects accepted IDs top-level but
  cannot project the missing batch. This creates two incompatible claims in the
  same r7 response: `accepted_delta_ids=["d1"]` and `graph_unchanged=true`, with
  no `accepted_batch`.
- `vibecomfy/executor/two_step_session.py:705-736` replays the terminal graph via
  `from_ui(...)` only. Envelope and raw node-keyed/API inputs therefore collapse
  at the evidence boundary even though `EditSession` now uses the format-aware
  `_named_import` door (`vibecomfy/porting/edit/_gates.py:300-312`). This is why
  the 11 r7 accepted-delta failures have zero-node `final.ui.json` artifacts.
- `vibecomfy/agent/artifacts.py:339-364,377-456` notices accepted IDs, but its
  guard only rejects `final == original`; a changed-but-empty projection passes
  the guard.
- The judge is behaving correctly for its contract:
  `tests/live_agentic_harness/intent_judge.py:411-445` treats absent
  `accepted_batch` as no delta. Do not teach it to infer edits from prose or IDs.

**Fix shape**

Create one `ScoredTerminalProduct` projection at the closed-message boundary.
Under the session lock, fold the durable transcript through a recorded terminal
sequence number and derive:

1. the last terminal reply/submit for that scored message;
2. one canonical `accepted_batch`, built from
   `accepted_delta_refs[*].ops` in acceptance order;
3. `accepted_delta_ids`, derived from that batch rather than maintained beside it;
4. the retained IR obtained by replaying the same batch over the recorded base;
5. the final UI emitted from that IR through the normal emit door; and
6. the transcript sequence, base hash, accepted-batch digest, retained-IR hash,
   and final-UI hash used by the assessor.

The projection must run after the message lease closes and before artifact
synthesis or assessment. `response.json`, `implementation_result.json`, and
`final.ui.json` must be written atomically from this same object. An earlier
failed submit may remain in the transcript, but it cannot remain the scored
response after a later accepted delta and final submit in the same scored
session.

`accepted_batch` is the sole durable delta. If a transient flattened-op view is
useful internally, derive it from `accepted_batch`; do not persist another delta
body. Replace `_apply_delta_ops()`'s `from_ui` call with the same format-aware
named ingest used by `EditSession`, including the non-empty-source/zero-node
assertion, then emit and replay-verify. A non-empty accepted batch that emits zero
nodes, loses untouched topology, or fails `interpret(pre, delta) == post` is a
typed artifact-consistency failure, never a scoreable artifact.

Preserve the fresh per-attempt session identity at
`tests/live_agentic_harness/adapter.py:136-151`; the finalizer must not mix a
later, separate harness attempt into an earlier attempt. “Final session state”
means the final closed message in the scored attempt, identified by its checkpoint,
not whatever happens to share an old session directory.

**Expected flips — exact/strongly judge-aligned accepted deltas (6)**

1. `3d-converts-image-to-3d-model` — d1 sets
   `Rodin3D_Regular.Polygon_count="1M-Triangle"` for sharper detail.
2. `audio-audio-processing-with-chatterbox-tts-and-vc-b55994` — d1 replaces
   `SaveAudioMP3` with linked `SaveAudio` (WAV).
3. `image-animatediff-video-generation-with-vae-d20410` — d1 sets
   `EmptyLatentImage.batch_size=8`.
4. `image-image-editing-with-qwen-image` — d1 rewrites uid 133's prompt to match
   lighting, shadows, color temperature, and grading.
5. `multi-3d-preview-and-image-output-workflow-d93baf` — d1 sets the exact
   requested `SaveGLB.filename_prefix="3d/moge-top-down"`.
6. `multi-image-to-video-generation-with` — d1 sets KSampler `steps=30` and
   `sampler_name="dpmpp_2m"`.

**Expected flips — semantically strong but judge/model-variance exposed (3)**

7. `3d-generates-a-3d-mesh-from` — d1 raises
   `VoxelToMeshBasic.threshold` to 0.8 to suppress floating voxels/noise.
8. `audio-tts-narration-using-indextts-2` — d1 raises named Happy/Surprised
   emotion values and moderates Sad/Angry to make narration more engaging.
9. `image-style-transfer-using-ip-adapter` — d1 raises
   `StyleModelApply.strength` to 1.5 so the statue style has more influence.

**Accepted deltas that must not be credited (honesty controls)**

- `image-two-stage-qwen-image-generation` — r7 d1 sets `SplitSigmas.step=9`,
  which was already 9; it does not implement the recommended upscale/refinement
  change.
- `multi-svd-image-to-video-with-webp-and-png-output-bd3afb` — r7 d1 adds
  `ImageFromBatch` but does not rewire `SaveImage` to its first-frame output.

Making these two deltas visible must leave them failed. Visibility is evidence,
not automatic semantic success.

### P1 — early-turn render/edit resolution divergence (next after P0; expected later: **1 high-confidence + 4 contingent**)

**Code:** `vibecomfy/executor/edit_tools.py:262-290` (`resolve_target`),
`vibecomfy/porting/edit/session.py:246-272` (`uid_by_name`), and
`vibecomfy/executor/two_step.py:1119-1122` (retained/base selection).

**Cause:** an early invocation sometimes holds an empty or stale retained
workflow even though the render exposes the target; identical name/uid calls can
then resolve later. The current checkout resolves the reported names locally and
the original mid-run session store was incomplete, so the exact triggering state
remains `unknown_needs_human`.

**Fix shape after P0:** first add a capture-only parity assertion at message
start: base hash, retained hash, render-visible `{name: uid}`, resolver
`{name: uid}`, node count, and terminal sequence. Reproduce the mismatch on a
fresh committed run. Then make construction fail with a typed hydration error if
render and resolver do not use the same retained IR; do not consume a replacement
attempt and do not resolve against raw request JSON as a fallback.

**Named upside:** high confidence only for
`3d-3d-shape-generation-and-export-workflow-8800a9` (the exact uid/field/value
was attempted). Contingent cases are
`audio-acestep-audio-generation-and-processing-workfl-1b1360`,
`audio-transcribes-audio-appends-text-regenerates`,
`multi-image-to-3d-object-generation-with-background-1a7f84`, and
`multi-image-to-video-with-llm`; each also has schema, field, port, or judge
expectation risk. Do not count `3d-3d-model-generation-and-preview-workflow-cc0df7`:
`Rodin3D_Fusion` is genuinely absent, so its honest product is a grounded
`requires_custom_nodes` outcome.

### P2 — judge/digest raw-format parsing fabricates zero-node narratives (expected standalone flips: **0**; bundle as a guard)

`tests/live_agentic_harness/intent_judge.py:659-669` has a second manual shape
dispatcher and falls back to `from_ui` for raw node-keyed graphs. Replace it with
the same named format-aware ingest door and the same non-empty-ingest assertion.
Unknown shapes must produce `undetermined/artifact_consistency`, never “0 nodes.”

This corrects false narratives seen for
`image-two-stage-qwen-image-generation`,
`image-animatediff-video-generation-with-vae-d20410`,
`audio-audio-processing-with-chatterbox-tts-and-vc-b55994`,
`multi-3d-preview-and-image-output-workflow-d93baf`,
`multi-image-to-video-generation-with`, and
`multi-svd-image-to-video-with-webp-and-png-output-bd3afb`.
It receives no separate score credit; four overlap P0 and the other two remain
semantically incomplete.

### P3 — genuine residual product failures (separate RCs, no immediate score credit)

- Non-destructive grounding/claim attachment:
  `image-image-processing-with-sharpening-film-grain-an-9aa0f1`,
  `multi-3d-gaussian-splatting-from-video-with-hunyuan-432652`,
  `image-animatediff-image-to-video-with-latent-composi-17dc9b`,
  `image-gemini-prompt-splitter-and-text-display-workfl-caae97`, and the r7
  regression `image-qwen-image-inpainting-with-controlnet-09fc64`.
- Authoritative runtime schema/ports:
  `audio-transcribes-audio-appends-text-regenerates`,
  `multi-image-to-video-with-llm`, and the missing rewire in `bd3afb`.
- Act-versus-clarify behavior: `multi-crops-face-previews-it-sets`.

Do not mix these into the final-state measurement RC; they enlarge the causal
surface and make the final rerun uninterpretable.

## 2. Expected final score

**Point estimate: 15/30. Conservative pre-run range: 12–15/30.**

- Baseline: the measured r7 score is 6/30.
- P0 contributes six exact/strongly aligned flips and three semantically strong
  flips, for +9.
- The lower bound credits only the six exact cases.
- P1-P3 receive no credit in this projection.

The six existing r7 passes must remain passes:
`audio-acestep-audio-generation-with-detail-daemon-f0859f`,
`image-dual-checkpoint-xl-image-generation-with-refin-c9df19`,
`multi-ai-video-upscaling-with-detail-daemon-sampler-673197`,
`multi-animatediff-video-generation-with-controlnet-a7e2af`,
`multi-flux2-image-and-video-generation-with-outpaint-435de2`, and
`multi-svd-image-to-video-with-animation-builder-99e2a9`.

Only a terminal `assessment.json` on the implementation commit moves the score.
An accepted ID, tool `ok`, non-empty graph, or corrected rationale is necessary
evidence, not a pass.

## 3. ONE next implementation target — scored terminal product

The one target is the **closed-session scored terminal product**, not another
resolver rewrite.

Concrete implementation contract:

```text
finalize_scored_terminal_product(session_id, message_checkpoint) -> ScoredTerminalProduct

ScoredTerminalProduct = {
  terminal_seq, reply,
  accepted_batch,              # sole durable delta
  accepted_delta_ids,          # derived from accepted_batch
  base_hash, retained_ir_hash, final_ui_hash,
  retained_ir, final_ui,
  diagnostic                   # may report failure; may never erase delta
}
```

Both success and failure paths return this object. Artifact synthesis and the
judge consume only its projections. Required invariants:

- a later accepted delta/final submit in the scored message outranks an earlier
  failed submit;
- `accepted_batch != []` implies `graph_unchanged=false`;
- every accepted-batch item contains its landed typed `op`;
- replay(base, accepted_batch) equals the retained IR;
- emitting the retained IR yields the final UI without node/topology loss;
- the judge's canonical ingest of final UI returns the same node/edge set;
- partial/wrong accepted deltas remain judge failures; and
- any disagreement fails closed as `artifact_consistency`, preserving all
  contradictory artifacts for diagnosis.

## 4. Secondary fixes to bundle

Bundle only the guards needed to make P0 truthful and testable:

1. Replace the replay path's `from_ui`-only ingest with the shared format-aware
   named ingest and non-empty assertion.
2. Replace the judge's manual raw/envelope dispatcher with that same ingest
   function; fail loud on unknown or zero-collapsed shapes.
3. Strengthen `persist_universal_ui_evidence`: accepted batch plus a zero-node
   final, replay mismatch, retained-hash mismatch, or lost untouched topology is
   a typed failure even when `final != original`.
4. Record the scoring checkpoint/terminal sequence and hashes in response and
   assessment metadata so Flash can prove both refer to the same state.

These are one measurement-boundary RC. Do not bundle resolver behavior, schema
providers, budgets, prompts, or grounding policy.

## 5. What NOT to do

- Do not choose target resolution first. Eleven r7 failures already contain an
  accepted d1; changing how the agent reaches an edit cannot make the judge see
  the delta that is already there.
- Do not make the judge infer ops from `accepted_delta_ids`, reply prose, private
  transcripts, or a raw pre/post diff. Produce the canonical `accepted_batch`.
- Do not add another graph serializer or resolver fallback. Reuse the existing
  named ingest and normal emit doors.
- Do not weaken rubrics, groundedness, safe-refusal allowlists, graph-change
  checks, or pass aggregation.
- Do not count the no-op `two-stage-qwen` delta or the unlinked `bd3afb` node as
  passes merely because evidence becomes visible.
- Do not raise continuation/replacement budgets, special-case scenario IDs,
  hard-code node uids/values, or call an ID `resolved` before a passing run on
  the implementation commit.
- Do not retroactively merge separate harness attempts that happen to reuse a
  session directory. Finalization must be checkpoint-scoped.

## 6. Implementation split and acceptance gate

### DeepSeek Pro XHARD — implementer

Implement the closed-session projector across
`two_step_session.py`, `agent_backend.py`, `two_step.py`, the response contract,
and `artifacts.py`. Make `accepted_batch` the sole durable delta; derive IDs and
ops views from it. Replace replay's `from_ui`-only door with shared format-aware
ingest/emit, add terminal sequence/hash metadata, atomic artifact publication,
and the consistency failures above. Add the judge canonicalization guard only;
do not change judge criteria or prompts.

### DeepSeek Flash — verifier (read-only)

Before implementation, freeze an 11-row ledger from r7 containing scenario,
session id, terminal seq, accepted d1 ops, response accepted IDs, missing batch,
original/final node counts, hashes, and assessment. Label the nine expected
flips and the two honesty controls separately.

After implementation:

1. independently reconstruct `accepted_batch` from each transcript;
2. replay it over the recorded base through the shared ingest door;
3. compare retained IR and emitted UI hashes/node/edge sets;
4. confirm response, UI artifacts, and assessment cite the same checkpoint;
5. run the 11 accepted-delta failures, the six current passes, then the full
   30-scenario lane; and
6. read terminal assessments rather than accepting internal `ok`/d1 evidence.

### Acceptance gate

1. All 11 accepted-delta fixtures emit non-empty `accepted_batch`; its ops and
   IDs exactly match the durable transcript through `terminal_seq`.
2. All 11 satisfy replay(base, batch) == retained IR == canonical(final UI), with
   nonzero preserved node/topology counts and unchanged unrelated fields.
3. No response can contain both a non-empty accepted batch and
   `graph_unchanged=true`, `route_not_applyable`, a missing final graph, or a
   zero-node final derived from a non-empty source.
4. The six exact P0 scenarios all pass terminal assessment. At least two of the
   three variance-exposed P0 scenarios pass. Thus the minimum release score is
   **14/30**, the target is **15/30**, and all six existing passes are preserved.
5. `image-two-stage-qwen-image-generation` and
   `multi-svd-image-to-video-with-webp-and-png-output-bd3afb` remain failed unless
   a later, complete accepted delta—not a judge change—actually implements their
   intents.
6. Raw node-keyed fixtures report their true node/edge counts (including the
   known 8-node and 20-node cases), never zero; unknown formats become
   `artifact_consistency/undetermined`.
7. Below 14/30, any lost existing pass, any accepted-batch/replay mismatch, or
   either honesty control falsely passing rejects the RC. The next action is a
   new evidence analysis, not a larger budget or softer judge.
