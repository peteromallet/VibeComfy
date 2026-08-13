# 1. Tasklist for the remaining project

## Scope decisions

- B02 and elegance P0–P10 remain closed through `0f515870`.
- The checkout contains exactly **100** scenario JSON files, not 150. The exploration finding claiming 150 is rejected by direct inventory.
- The apparent no-change population is **40**:
  - 35 semantic research/explain/diagnose scenarios;
  - 2 explicit health controls: `live-graph-explanation-smoke` and `speed-distillation-research`;
  - 3 mislabeled edits with `apply:true`, a `desired` rubric, and `expect_graph_changed:false`.
- Add no separate answer-quality batch. D13 authors the rubrics; B06 implements one tri-state semantic-answer judge.
- Replace the speculative B08 decision gate with the now-justified deterministic C8/C9 endpoint-integrity batch.
- Keep cut:
  - semantic repair turns and fingerprints;
  - generic prompt cleanup/compression;
  - all-Flash profiles;
  - the 400-run matrix;
  - speculative interrupted-run resume.
- Expand B01’s single provenance contract to successful and failed calls. B07 consumes it rather than creating a second evidence system.
- Historical `out/agentic/` and `external_workflows/` are absent. Deterministic fixes may proceed, but scenario-level recovery, baseline, or stochasticity claims require those artifacts.
- Each batch ends in a binary read-only oracle checkpoint. Rework the owning batch until `PASS`.

---

## G0R — Truthful scorer/narrator and formal re-verdict

### Tasks

1. Remove the remaining `"unchanged"` implementation-message substring gate.
2. Restore the structural expected-edit guard:
   - `graph_unchanged=false` requires a positive integer `landed_operation_count`;
   - missing, malformed, or zero fails closed;
   - non-edits and accepted grounded refusals are exempt.
3. Ensure narrator artifact-write failures cannot replace an already-selected narrator response.
4. Remove the narrator prompt contradiction around `validation.passed`.
5. Preserve regressions for:
   - provider-exception evidence;
   - nullable failed classification;
   - no invented route, task, or intent.
6. If authoritative prior artifacts are restored, deterministically rescore them and produce the residual class inventory without new model calls. Otherwise record historical re-binning as unavailable; do not infer it from documentation.

### Acceptance

- No substring matcher, narrator phrasing, or implementation message gates scoring.
- Prose affects semantic quality only through B06’s explicit rubric-driven judge.
- Zero/missing landed-operation fixtures fail structurally.
- Narrator artifact-write failure preserves the selected response.
- The nine former matcher cases have zero matcher failures, though independent structured failures may remain.
- Focused G0 tests pass.

### Oracle checkpoint

Review scorer/narrator changes and focused fixtures. Record `PASS` as the formal G0 verdict, plus either a reconciled historical rescore or an explicit “source artifacts unavailable” statement.

---

## B01 — Typed failures and unified attempt provenance `[HARD]`

### Tasks

1. Introduce one additive model-attempt evidence contract across worker, runtime, provider/backend, executor, artifacts, and harness.
2. Distinguish:
   - empty response;
   - malformed non-empty JSON;
   - non-JSON content;
   - missing required fields;
   - timeout;
   - capacity/provider failure.
3. Persist on every successful and failed attempt:
   - phase and attempt;
   - requested and resolved model;
   - adapter;
   - actual provider and transport;
   - normalized endpoint;
   - finish reason;
   - token usage.
4. Persist bounded raw previews only for failures.
5. Fix the three success-path runtime stripping seams and merge worker-observed metadata into batch audit metadata and final report artifacts.
6. Permit a fresh-transport retry only for typed empty responses. Never derive infrastructure status from response wording.
7. Serialize unavailable non-Hermes provenance as `unknown`; never infer it.

### Acceptance

- Every failure type serializes distinctly.
- Successful classify, reply, and batch calls retain provenance through final artifacts.
- Requested and resolved models remain distinct across routing/retries.
- Typed empty evidence reaches the existing retry; malformed non-empty results remain product failures.
- Unsupported routes report explicit unknowns.
- Redaction proves keys, authorization data, and secret URL parameters cannot persist.

### Oracle checkpoint

Trace representative successful and failed calls end to end. Reject parallel evidence formats or inferred fields.

---

## D13 — Corpus integrity, satisfiability, and semantic rubrics `[HARD]`

### Tasks

1. Check in an authoritative manifest for the current 100 scenarios:
   - stable ID;
   - path;
   - descriptor SHA-256;
   - inclusion status;
   - source-workflow ID and hash where applicable.
2. Make runner discovery consume the manifest rather than an unrestricted glob. Reject missing, changed, duplicate, or unmanifested files.
3. Audit scenario/query/schema/operation/rubric coherence, prioritizing all anomalous or revised cases.
4. Correct the three mislabeled edits:
   - set edit/change expectations truthfully if satisfiable;
   - otherwise rewrite or replace them while preserving coverage;
   - never let them pass as no-ops.
5. Classify the remaining 37 query non-edits:
   - 35 semantic product scenarios receive explicit expected-answer criteria;
   - the smoke and speed-distillation cases become explicit health controls.
6. Ensure every retained edit `desired` block feeds an active judge.
7. Record every rewrite/replacement and preserve matched-versus-revised reporting.
8. Provision `external_workflows/` before accepting satisfiability or source hashes.

### Acceptance

- The manifest selects exactly 100 unique ID/stem-matched scenarios.
- The 40 no-change-routed cases reconcile as 35 semantic non-edits, 2 health controls, and 3 corrected edits.
- The three edits cannot pass without a judged graph change or legitimate grounded refusal.
- All 35 semantic non-edits have evidence-backed rubrics.
- Health controls are excluded from semantic-product rates.
- Stray scenario files cannot silently change the lane.
- Source-workflow hashes resolve before D13 passes.

### Oracle checkpoint

Review the manifest, all three corrected edits, the two controls, rubric coverage, and every rewritten/replaced case.

---

## B04 — Real-schema authority

### Tasks

1. Introduce one small helper that composes real/runtime schemas first and provisional schemas only as gap-fillers.
2. Migrate all four verified provisional-first sites:
   - `_frag_research.py:874`;
   - `_frag_response_contract.py:793`;
   - `_frag_batch_loop.py:910`;
   - `edit_batch_repl.py:1115`.
3. Assert precedence across all seven construction sites for both `get_schema()` and merged `schemas()`.
4. Add a cross-turn regression for `_frag_response_contract.py:793`, which currently poisons both session and state.
5. Retain mechanism-level enum regressions for add and set. Do not add new combo-validation machinery unless a post-precedence reproduction still bypasses existing pre-mutation validation.

### Acceptance

- All seven sites are real-first.
- Session schema authority remains real-first across turns.
- Provisional `widget_N` names and empty choices cannot shadow real semantic names/choices.
- Invalid enum values are rejected before mutation for add and set.
- Missing local asset filenames remain warning-only.

### Oracle checkpoint

Review the shared helper, all seven callers, cross-turn behavior, and pre-mutation enum fixtures. Stop here if precedence alone closes the reproduced failures.

---

## B03 — Canonical semantic pin comparison `[HARD]`

### Tasks

1. Add fixtures for:
   - flat Set/Get fan-out;
   - 1:1 reroute lowering;
   - loop-cloned consumer UIDs;
   - nested subgraphs;
   - multi-output nodes;
   - genuine removed, repointed, or orphaned consumers.
2. Replace raw UID-keyed multiset comparison with one canonical semantic-set helper:
   - preserve input/output port identity;
   - dedupe multiplicity;
   - normalize reroutes to terminal endpoints;
   - normalize loop-cloned UIDs to their canonical consumer UID.
3. Feed the canonical before/after sets into the pin fence.
4. Refuse when semantic sets genuinely differ or endpoint resolution is ambiguous/unresolved.
5. Preserve canonical before/after sets in diagnostics.
6. Do not revive dead link-count refusal strings or construct a second topology abstraction.

### Acceptance

- Multiplicity-only Set/Get expansion passes.
- Equivalent reroute, loop-clone, link-renumbering, and nested lowering passes.
- Added, removed, repointed, orphaned, or output-port-changed consumers refuse.
- Unresolved/cyclic paths terminate deterministically and fail closed.
- Multi-output identity is preserved.
- B02 preservation tests remain green.

### Oracle checkpoint

Require both false-positive and true-topology-change fixtures to pass before B05-lite.

---

## B05-lite — Journaled unexpected-exception rollback `[HARD]`

### Tasks

1. Create a loop-entry rollback journal covering:
   - existing mutable session snapshot;
   - `value_default_context`;
   - UI payload, batch accumulators, budget, and exit fields;
   - exact bytes-or-absence of rendered Python, candidate UI, model request/response, and messages artifacts.
2. Cover the full mutating path through apply, render, `done()`, and final evidence promotion with one exception boundary.
3. On unexpected exception:
   - restore session state;
   - restore files byte-for-byte;
   - truncate appended state;
   - close the allocated durable turn as aborted;
   - re-raise.
4. Persist a separate bounded typed abort diagnostic after restoration.
5. Buffer telemetry until commit where practical; otherwise emit an explicit abort marker and ensure no event claims the rolled-back candidate committed.
6. Add no repair call, retry loop, or fingerprint.

### Acceptance

- Faults after mutation, render, candidate write, `done()`, and finalization restore exact pre-batch state and file existence.
- Ledger, hashes, name maps, and candidate state match the restored graph.
- No partial candidate is observable.
- Durable turns do not remain allocated-but-unrecorded.
- Telemetry cannot report rolled-back work as committed.
- Ordinary validation failures are unchanged.
- No additional model call occurs.

### Oracle checkpoint

Review the fault-injection matrix and byte-level before/after evidence.

---

## B06 — Universal UI evidence and semantic adjudication `[HARD]`

### Tasks

1. Persist authoritative `original.ui.json` and `final.ui.json` for every adjudicated route. Unchanged/refused/clarify routes explicitly project final from original.
2. Replace refusal-kind auto-acceptance with tri-state grounded-refusal adjudication:
   - supported blocker and no representable edit → pass;
   - unsupported/fabricated inability → fail;
   - missing evidence or judge outage → undetermined.
3. Implement one rubric-driven tri-state answer judge for the 35 D13 semantic non-edits:
   - grounded, relevant, correct response → pass;
   - hallucinated, wrong, irrelevant, vacuous, or empty-but-valid response → fail;
   - unavailable evidence/judge outage → undetermined.
4. Keep the two health controls structurally scored and separately reported.
5. Ensure the three corrected edits use the edit-intent judge.
6. Never use prose substrings as evidence.

### Acceptance

- Refusal fixtures produce pass/fail/fail/undetermined for grounded, unsupported, fabricated, and outage cases.
- A healthy but false explanation fails.
- Judge outage never passes.
- Every selected semantic non-edit has a rubric and judge result.
- All routes carry original/final UI evidence.
- Only `pass` satisfies a semantic scenario.

### Oracle checkpoint

Review refusal and semantic-answer fixture packs, evidence availability, and control/product separation.

---

## B07-lite — Explicit transport experiment

### Tasks

1. Add the smallest explicit harness selector, preferably `--transport {openrouter,native}`.
2. Eliminate ambient-credential transport selection.
3. Consume B01’s actual successful/failed provenance; do not create another metadata format.
4. If historical call artifacts are restored, determine their actual transports rather than trusting readiness labels.
5. Run an approximately ten-scenario empty-heavy matched native/OpenRouter experiment on the same commit, scenario set, profile, and configuration.
6. Keep OpenRouter canonical unless a material repeatable advantage receives later oracle approval.

### Acceptance

- Ambient credentials cannot silently change transport.
- Every attempt reports requested/resolved model, provider, transport, endpoint, finish reason, tokens, and attempt.
- Secrets remain redacted.
- The experiment reports scenario IDs, typed-empty rate, attempts, latency, and configuration digest.
- No all-Flash profile or prompt rewrite is introduced.
- A written decision retains OpenRouter or proposes a separately approved change.

### Oracle checkpoint

Review comparability and provenance before accepting any transport conclusion.

---

## B08-cut — Deterministic endpoint integrity `[HARD]`

Prompt/model quality work remains cut. This batch replaces it with the verified C8/C9 editor fix.

### Tasks

1. Add regressions for:
   - catalog output name absent from the working node’s outputs;
   - schema-derived source index out of bounds;
   - add-node link resolution;
   - unknown target input;
   - valid named multi-input/output links;
   - the late `Missing stable link from port` signature.
2. Make working-graph ports authoritative during endpoint resolution. Schema may validate or enrich but cannot return a slot absent from the node.
3. Add one shared pre-mutation endpoint invariant for upsert-link and add-node links.
4. Bounds-check source slots before `_apply_upsert_link`.
5. Remove synthetic input fabrication for unknown target names.
   - Legitimate dynamic inputs require an explicit node/schema contract.
6. Define ONE shared, concrete dynamic-port contract covering the verified node families (count-driven: `ImageConcatMulti` `image_N`, `LTXVImgToVideoInplaceKJ` `num_images.*`, `SimpleCalculator` `input_N`, `LTXVAddGuide` `guide_N`, `SimpleCalculatorKJ` payload vars, `in_N` fixed slots; helpers/proxies: `Reroute`, `GetNode`, `SetNode`, `PrimitiveNode`; dynamic `INPUT_TYPES` custom nodes) — a single predicate used by resolution, mutation, and projection (not a duplicated list at three sites). A port is valid iff present in `node["outputs"]`/`["inputs"]`, or the class matches the dynamic contract AND the schema-fallback slot is bounds-verified before link write.
7. Materialize declared ports during node construction, not opportunistically during link application (materialize-then-validate: build schema input sockets into `inputs` at `ui.py:1325` symmetric with outputs, then keep write-time bounds checks but emit diagnostics instead of silent returns at `apply_links.py:303/314`).
7. Resolve projection ports by canonical name with a validated index fallback.
8. Return typed pre-apply diagnostics instead of creating malformed links and failing during projection.

### Acceptance

- Malformed endpoints fail before mutation and roll back cleanly.
- No undeclared synthetic ports are created.
- Valid named links project correctly despite serialized ordering differences.
- Resolver, mutation, and projection share one endpoint invariant.
- C8/C9 mechanism regressions and relevant porting/edit suites pass.
- No scenario recovery count is claimed without restored run artifacts.

### Oracle checkpoint

Reject redundant defensive layers or any prompt-based workaround. Confirm one coherent invariant covers resolution, mutation, and projection.

---

## B09 — Reproducible final gate and report

### Tasks

1. Preflight required ignored data:
   - `external_workflows/` is mandatory for the canonical run;
   - historical `out/agentic/` is mandatory only for historical comparison and flaky-ID claims.
2. Emit:
   - the authoritative 100-scenario ID/file/SHA manifest;
   - source-workflow per-file hashes and `primary_source`;
   - one aggregate corpus digest;
   - commit and configuration digests.
3. Extend the B02 preservation summary or make B09 preflight the sole corpus-hash owner. Do not maintain two hash systems.
4. Embed commit, selection, configuration, and corpus digests in `run_summary.json`.
5. Cite report evidence by stable scenario ID and SHA, never checkout-relative artifact paths.
6. Run deterministic gates:
   - focused G0R/B01/D13/B04/B03/B05/B06/B07/B08 tests;
   - complete non-GPU suite;
   - B02/elegance preservation suite.
7. Run one canonical 100-scenario lane with explicit transport, profile, models, concurrency, timeout, and exactly one typed-empty infrastructure retry.
8. Report:
   - suite first-attempt and eventual rates over 100;
   - semantic-product rates over 98, excluding the two health controls;
   - the frozen infra-adjusted semantic rate;
   - health-control results separately;
   - refusal pass/fail/undetermined;
   - provenance and UI coverage;
   - matched versus D13-revised subsets;
   - remaining Class C/D ceiling.
9. Once comparable prior artifacts are restored, choose at most 5–10 scenarios with final-verdict flip rate `0.25–0.75`. Repeat only those until each has three comparable observations including B09. Exclude repeats from headline arithmetic.
10. If prior artifacts remain absent, name no flaky scenarios and make no regression-versus-variance claim.
11. Correct documentation drift:
   - update the complete-picture status/table and G0 verdict;
   - add supersession banners to historical sections;
   - mark the canonical-graph elegance plan landed;
   - remove stale “missing rich ingest” claims from the improvement document;
   - verify commit/work mapping before citing `192d4b8f` or `0f515870`.

### Acceptance

- All deterministic suites pass.
- The corpus and manifest preflight passes before model calls.
- The canonical lane completes exactly 100 manifest-selected scenarios.
- Report arithmetic reproduces from persisted artifacts.
- Product rates exclude health controls.
- Historical comparisons are made only from portable, hashed evidence.
- Flaky scenarios are reported as inconclusive/variance, not pass or fail.
- Documentation no longer describes landed work as in flight.
- The cumulative oracle verdict is `PASS`.

### Oracle checkpoint

Perform cumulative diff review, reproduce report arithmetic, verify manifests/provenance, and issue final `PASS` only after all earlier checkpoints remain satisfied.

# 2. New areas to explore

1. **Add-node port materialization:** confirm all declared ports exist before link resolution.
2. **Abort-event semantics:** determine whether the telemetry sink can buffer events or needs an explicit aborted-attempt record.
3. **Pinned edge semantics:** verify muted/bypassed broadcast helpers, duplicate Set names, and named-versus-indexed multi-output mappings.
4. **Artifact lineage:** recover the exact external corpus and historical run directories, then verify their commit/config ancestry.
5. **Flaky-set derivation:** compute scenario-level flips only after comparable historical artifacts are available.
6. **Documentation commit mapping:** establish which commit resolved the previously cited 16 regressions before documenting it.

# 3. Open questions / potential issues

1. Where will the ignored `external_workflows/` corpus be provisioned for D13 and B09?
2. Are authoritative historical `out/agentic/` runs available? Without them, historical re-binning, exact C8 recovery, and flaky-ID selection remain unavailable.
3. Which transport is canonical? The plan retains OpenRouter pending B07 evidence.
4. Does the infra-adjusted denominator exclude only final typed persistent-empty failures? This policy must be frozen before B09.
5. Can telemetry events be buffered transactionally, or must rollback emit compensating abort records?
6. Which model judges semantic non-edit answers, and what availability threshold makes a lane reportable rather than broadly `undetermined`?
7. Do the three mislabeled edits become satisfiable after B04/B08, or must any be rewritten or replaced?
