# Acceptance and evidence — planning history plus future behavior

## Current corpus-completeness amendment — 2026-09-12

The current user requirement is that valid workflows work through the canonical
path. The former corpus expectation of ten intentional refusals is superseded:
cases 01, 02, 11, 13, 15 and 18 are required-positive importer regressions;
case 14 is a bounded source-format investigation; cases 10, 16 and 17 remain
refusals only for their supplied malformed/descriptive bytes. See the complete
[Astra-adjudicated corpus plan](corpus-completeness-amendment-20260912.md).

This amendment changes expected scenario outcomes, not criterion IDs, scope
owners, review stages or counters. Positive cases require source-backed
semantic/identity expectations and full edit/save/reload/export proof. Refused
cases require contextual diagnostics, no partial outputs and byte-for-byte
preservation of any existing destination pair. The prior 10/10 result remains
historical and does not satisfy this amended acceptance target.

## Required final practical validation — before completion

User explicitly reaffirmed actual end-of-run validation. This is required E2/T4 evidence under I1–I10, not another model-review stage. All items remain NOT RUN for the new amendment.

1. **Programmatic fidelity and source shape:** validate the entire freshly generated Python and companion JSON; independently assert effective values, exact edges/output slots, public outputs, identity/native scopes/provenance, and presentation-only metadata. Include malformed/missing/mixed companion refusal, valid drafts, revision protection and injected failure/rollback tests. Matching producer-generated snapshots alone is insufficient.
2. **Real entrypoints and editing pipeline:** ingest the same supported and malformed inputs through actual CLI, SDK and canvas paths. Perform an actual Comfy Node edit/apply/save/reload/export lifecycle through production persistence owners, with deterministic model responses only at the provider seam. Assert intended edits and unchanged unrelated graph content. Browser boot, intercepted backend routes, mocked callbacks or success exit codes alone do not satisfy this proof.
3. **Original workflow corpus:** rerun all 20 original inputs through the canonical path. Every valid source must produce a complete pair and full lifecycle evidence; refusal is allowed only for a documented malformed or semantically unresolved source condition. The current minimum is 16 positive pairs plus justified refusals for 10, 16 and 17, or 17 positives if case 14 is source-proven recoverable. Every unexpected defect is minimized into a regression and its original workflow is rerun after the fix.
4. **Exact H3 rehearsal:** onboard the specified H3 source, retain freshly generated Python/JSON, edit the required controls, rebuild, save/reload/export, and compare exact intended changes plus untouched wiring/identity. Regenerate unchanged inputs deterministically. Inspect the whole Python file and a rendering from the exact exported graph; retain files, hashes, command receipts and inspection findings. No manual output cleanup or bespoke restoration may stand in for the canonical path.
5. **Final integrated checks:** pass the configured full offline suite, complete browser smoke and required applicable Comfy/browser/parity checks on the final candidate under existing resource limits. Report actual commands, collected/selected counts, failures/errors, skips/deselections/xfails and reasons. Required unavailable boundaries remain blockers, not silent skips. No new live-model/GPU requirement is introduced. Rerun only affected checks after further changes while retaining unaffected evidence.

A failed requirement triggers the existing loop: isolate → fix the owning path → rerun the failing test → affected consumers → original workflow/artifact validation. Final Astra review receives that executable evidence and the exact candidate; its opinion cannot replace these tests or waive a demonstrated failure. Do not mark handoff complete while required checks fail or required artifacts are missing.

Test-signal planning supplement: [focused cleanup plan](test-signal-cleanup-plan.md)
and [six-slice Luna inventory](evidence/test-signal-audit-20260911/test-signal-audit-20260911.md).
This is preparation only; no test deletion, lane suppression or new acceptance PASS.

Current source-cleanliness amendment (2026-09-11):
[canonical-source-cleanliness-direction.md](canonical-source-cleanliness-direction.md)
supersedes the embedded-custody allowance below for the new canonical output.
I1/I2/I5 include the required v2 companion, construction-time validation and
revision/atomicity behavior; I7/I9 include shared ingress and resolution owners;
I8 includes whole-file cleanliness and concise finalization; I10 includes the
actual H3 Python/JSON pair and exported graph. Existing criterion IDs, historical
evidence and review counts are preserved. Prior green tests do not establish
these new requirements: their implementation acceptance remains NOT RUN.

S90 changes representation, not fidelity: ordered labelled custody replaces the
map/order pair and direct compatibility validation replaces the stored structure
hash. I1/I5 retain generation/custody/revision checks and same-custody swapped-pair
refusal. I8 retains whole-file structural mutation checks over supported emitted
syntax; I9 retains frozen-resolution and scoped-annotation fidelity. Selected
integration cases replace a Cartesian test matrix; all required corpus, H3 and
real entrypoint evidence remains. No PASS or added review stage is inferred.

Path-census integration: I7/I9 require CLI analysis and conversion to refer to
one admitted source/snapshot, with source/report identity assertions. I1/I5
cover v2 conversion/copy/registry consumers of the existing pair boundary.
I3/I9 require that an unresolved named output cannot silently become a slot-zero
edge on strict/canonical public export; characterize public reachability before
claiming the helper fallback is an end-to-end defect. Compare entrypoints with
matching frozen authority, preserving deliberate API/UI and recovery differences.
All new assertions remain NOT RUN; no additional approval stage is created.

This existing file is retained as the single criterion source, not a new approval gate. P IDs track plan adequacy; I IDs track executable behavior and cannot inherit a planning PASS. Source baseline and current dirty-state distinction remain in goal.md. Proposed checks Q0–Q5 are preserved in tasklist.md. The consolidated E0/E1/E2 tasks add the paused Pythonic-emission contract to this run without creating a second emitter, review stage, or cap. All new completion evidence remains missing until an exact candidate is tested.

## Planning criteria: preserved IDs and user-authorized mapping

| ID | Meaning / dependency | v3 disposition and evidence |
|---|---|---|
| P1 | Accurate source/base/dirty evidence; none | Prior evidence retained; current read-only metadata provenance.md plus readiness finding provenance.md; current source identity still requires C0 adoption/recheck; no product re-audit or evidence claim |
| P2 | Complete bounded outcome and deferrals; P1 | Same save/export/parity/docs outcome; plan.md; no newly required feature |
| P3 | Tasks, owners, dependencies, behavior/proof; P2 | v4 readiness: T1/T2 are test-first against current H3/export entrypoints, T2 owns the missing Q2 module, and T3 retains independent preparation from C0; run.yaml/tasklist.md/I criteria |
| P4 | Operational budgets/source/authority; P1 | Refined: explicit cumulative review/oracle ceilings, historical counts and restart rules; run.yaml/status.md |
| P5 | Adequate planning challenge and review-policy consistency; P2,P3,P4 | Historical independent discovery/contract/Astra evidence preserved; new skill does not require rerunning certification merely to edit a plan. v3 coordinator checks configuration/packet consistency, not a new oracle verdict |
| P6 | Practical example, sequence, estimate and explicit unknowns; P2,P3,P5 | Same 20→30 example, two-segment path and estimate in plan.md |

Previous frozen P PASS entries, review counts and rulings are archived under the original run history (counts and surviving dispositions summarized in status.md). No historical rejection, critique or correction is removed. Delivery evidence for the current candidate is recorded in the run evidence directory and summarized below; final integrated review remains pending.

## Prospective implementation criteria

| ID | Required behavior and relevant negative case | Dependencies | Required evidence | Current status |
|---|---|---|---|---|
| I1 | Canonical save/reload preserves intended semantic content and stable identity. Existing supported normalization is explicit and occurs before bundle/sidecar/revision construction. Returned bundle, reloaded Python, sidecar binding and revision inputs agree. Inject unexpected node/edge/widget loss and assert refusal with both existing destination files unchanged; include sidecar-present case | none | Q0/Q1; actual before/after semantic projections and pair-binding assertions on exact candidate; failure fixture asserting unchanged destinations | NOT RUN / MISSING |
| I2 | Incomplete/missing-model drafts can save without queue readiness. One representative unknown/custom class with UID/widgets/raw properties/edges preserves supported payload through existing owner or returns explicit refusal before replacement; no blanket rejection or invented result interface | I1 | Q1 fixture contrasting draft persistence with readiness; opaque fixture result and any permitted normalization/refusal diagnostic | NOT RUN / MISSING |
| I3 | Draft JSON/Python inputs export via needed authority/layout-sidecar checks without forced canonical persistence. Preserve --out, --persist-sidecar, --from/breadcrumb layout, strict refusal, visible force-drop, recovery/trust and preview no-write; API export remains projection. The legacy layout sidecar (.layout.json) is distinct from I1's canonical Python/.vibe.json pair. | I1,I2 | Q2 temp-directory positive/negative fixtures in the new tests/test_canonical_export_integrity.py; named scenarios test_draft_json_export_without_readiness, test_draft_python_export_without_readiness, test_explicit_out_does_not_write_sidecar, test_persist_sidecar_updates_layout_store, test_from_and_breadcrumb_preserve_layout, test_strict_refusal_is_explicit, test_force_drop_is_visible, test_preview_is_no_write; cover API/recovery/trust behavior with existing or added assertions. A layout-store write alone is not canonical-pair evidence. | NOT RUN / MISSING |
| I4 | Equivalent Python/typed field changes yield same admitted semantics and untouched UIDs; reports may differ. Actual no-op semantics and atomic rejection/history behavior remain. Refactor only demonstrated mismatch | none; changed shared publication assumptions depend on I1 | Q3 positive parity and rejected-edit fixtures, one-field 20→30 preservation case; canonical delta and untouched-node assertions, not identical narrative strings | NOT RUN / MISSING |
| I5 | Existing durable revision/precondition protection and both approved server/embedded execution transports remain; no stale revision becomes newly accepted. No new concurrency subsystem required | I1,I3,I4 | Q3/Q5 relevant existing stale/revision/runtime cases plus source dependency inspection; reuse matching valid receipts, never claim mocked transport checks prove live GPU execution | NOT RUN / MISSING |
| I6 | Named docs and CLI help describe actual draft/save/export/apply/queue, normalization/provenance/revision and optional persistence behavior | I1,I2,I3,I4,I5 | Q4 source/help comparison + implementation/test references; grep success alone is insufficient | NOT RUN / MISSING |
| I7 | Stay within existing rule owners and agreed scope: no editor/normalization framework, forced persistence lifecycle, redundant gates or speculative compatibility layer. Preserve North Star invariants applicable to stage scope | none; assess only completed stage scope, whole integration at final | Scoped diff/entrypoint evidence; every new abstraction justified by a current criterion. Preferences/alternative designs alone are optional. Final additionally assesses integrated strategy, simplicity and North Star alignment | NOT RUN / MISSING |
| I8 | Natural Python source is topological and editable: meaningful constructor calls use variables/output handles and one authoritative field expression; ordinary calls contain no routine `_id`/`_uid`, raw node-ID links, native-port payloads, `wf.connect`, or whole-node replay. Editing an emitted constructor/default/public control changes the rebuilt graph and is not overwritten later. Behavioral and identity fidelity supersede importer-shaped exact syntax. | C0,E0,E1; T1/T3 integrate the candidate | E0 baseline and E1/T3 evidence from existing `tests/test_porting_emitter.py`, `tests/test_h3_generated_editability.py`, `tests/test_native_subgraph_expansion.py`, `tests/test_native_h3_boundary_mapping.py`, `tests/test_h3_schema_widgets.py`, and `tests/test_workflow_bundle.py`; AST/source-shape checks paired with rebuild/edit semantic and identity assertions. No completion claim from the current `_id`/`wf.connect` baseline. | NOT RUN / MISSING |
| I9 | Resolver-owned reroutes/value helpers lower or disappear consistently across canonical/ready/scratchpad paths without semantic loss; effective behavior, public I/O, fanout, output slots, aliases, subgraphs, identity/provenance/native-port custody, and unknown/malformed schema fail-closed diagnostics remain correct. Unexpected loss refuses atomically and leaves prior destinations unchanged. | C0,T0,E0,E1; T1/T2/T3 integrate shared publication, export, and parity evidence | E0 failing baseline plus E1/T1/T3 focused evidence using the existing emitter/native-subgraph/H3/bundle suites named for I8, existing edit/revision tests, and exact semantic/custody comparisons. Preserve authored helper provenance in custody without executable helper calls; no routine value replay or duplicate semantic authority. | NOT RUN / MISSING |
| I10 | The exact saved `assets/h3/MiniMax_H3_AV_EncodeDecode_Inpaint.json` regenerates through the shared canonical path into reviewable Python; the practical test edits prompt, prepared source, video/audio mask controls, duration, and seed, rebuilds, compares effective wiring/values/output/custody against the expected edited graph, and proves deterministic regeneration. Guides/CLI state the actual native-expansion, unresolved-schema, and runtime boundaries truthfully. | E1,T1,T2,T3; E2 then T4 | Reproducible source hash, generated `.py`, normal command output, edited values, semantic/identity comparison, deterministic re-emission record, and documentation references. Static graph generation is not a GPU/video-quality claim. A failed practical check blocks completion. | NOT RUN / MISSING |

I1/I2/I3/I7/I8/I9 are the intermediate scope after C0/T0/E0/E1/T1/T2; final includes all I IDs including I10. I7 at intermediate never demands future T3/T4 work. Changes invalidate only affected criteria and stated downstream dependencies; criterion IDs and review counters survive renaming/restarts. An actual integration change broadens the affected evidence, not the budget. The acceptance contract is behavioral plus identity/provenance fidelity; importer-shaped exact syntax is no longer authoritative.

## Exact-candidate evidence override — 2026-09-12

The planning table above intentionally preserves the pre-delivery `NOT RUN /
MISSING` snapshot. For candidate `20fa4baa372f44c905b9daa869ad8c0de7e5160d`,
the effective status of every criterion is `EVIDENCE RECORDED — final review
pending`, with the following exact receipts:

| Criteria | Evidence |
| --- | --- |
| I1–I5 | `evidence/full-suite-current-20fa4baa.md`, focused integrity lane, and the atomic pair/revision tests |
| I6–I7 | CLI/help/parity evidence and `evidence/ir-boundary-20fa4baa.txt` (`IR boundary: clean`) |
| I8–I9 | `evidence/focused-integrity-20fa4baa.md` and `evidence/h3-current-final-20260912/source-inspection.txt` |
| I10 | `evidence/corpus-and-h3-current-20fa4baa.md` and `evidence/h3-current-final-20260912/` |

The full suite is `10,560 passed, 195 skipped, 35 deselected, 1 xfailed, 0
failed`. The corpus has 17 complete pairs and three contextual refusals (10,
16, 17), with case 14’s frontend serialization evidence still provisional.
No criterion is marked `PASS` until the configured independent final review
disposition is recorded. Missing live frontend/ComfyUI/GPU/provider execution
remains an explicit environment boundary, not a silently accepted success.

## Outcomes and evidence discipline

PASS requires adequate exact-candidate evidence and no unresolved blockers. REWORK names a source-backed contract violation, implementation defect or required evidence gap attributable to the deliverable. UNKNOWN covers inaccessible/mismatched identity/evidence; it consumes the attempted round and cannot imply PASS. Optional improvement, out_of_scope and stale_or_repeated remain nonblocking with a recorded disposition.

Each real packet includes one row per scoped I ID with command, inputs/environment, result, evidence path/digest, and explicit MISSING entries. Worker summaries and old planning approvals are not executable proof. The coordinator routes clear defects; disputed findings and exceptions go to the configured oracle. No weakened criterion or hidden extra review is permitted at a budget cap.

## Clean-source acceptance clarification — user inspection request

I8/I9 apply to the whole generated authoring file, not just build(). Moving the replay tail into a large CUSTODY dictionary is not acceptance. The one deterministic custody declaration contains only bindings/IDs and necessary schema/provenance/exceptional reference facts; it contains no runtime input/widget values, whole-node snapshots, graph edge arrays, raw UI payload or serialized source graph. Required native-port facts must not be repeated in ordinary calls and again in custody. Generated source has no post-construction wf.nodes[...] input/widget/metadata/native-field replay; the existing internal finalization mechanism may apply verified custody without generating such a tail.

Meaningful prompt, model, source, mask and interval controls are permitted as named values. A JSON-valued node input is not itself a defect; repeating it in constructor literals and later restoration is. Each runtime value has one authoritative expression, shared by references where reused. E0/E1 AST and declaration-content assertions prove this distinction; E2/I10 opens the actual whole H3 file and rejects merely relocating the old clutter. No arbitrary line/byte limit or new serialization/storage service is introduced. D1's return condition remains if necessary custody cannot be preserved under this contract.

## Astra sense-check acceptance clarification — 2026-09-09

These two in-scope evidence requirements close the explicitly requested clean-Python/elegant-ingestion end state. They add no architecture, task family, product authorization or review stage. Exact-candidate evidence is recorded in the run evidence directory; final Astra review remains the last disposition.

## Current candidate evidence status — final review pending

I1, I2, I3, I4, I5, I6, I7, I8, I9 and I10: `EVIDENCE RECORDED — final review pending`.
The configured and expanded affected test gates are green, and the final review
packet supplies the criterion-by-criterion commands, inputs, results and hashes.

The `NOT RUN / MISSING` cells in the prospective table preserve the pre-delivery
planning snapshot. For the exact 2026-09-11 candidate, the override is now
effective: I1–I10 have evidence recorded, with no criterion marked PASS until
the configured independent reviews complete.

### I10 / E2 — inspect the exact visible result

After editing and rebuilding the actual generated H3 file, save/reload it and materialize/export its UI graph through the normal public boundary. Record the exact Python, exported graph and presentation-sidecar identities. Assert the expected nodes, effective links, public ports, supported subgraph/instance representation and preserved presentation fields by stable identity; account explicitly for supported native expansion and normalization. Inspect the whole generated Python and the graph rendered from that exact exported artifact, including its subgraph/boundary detail, and retain a screenshot or rendered view plus a short criterion-linked inspection finding. Reject unreadable replay/custody clutter, missing or misbound ports, unintended flattening of a supported authored structure, or lost presentation. Use an already available viewer/rendering path; no UI redesign, runtime provisioning or GPU output-quality claim. Missing visual evidence remains MISSING, not PASS.

### I7 / I9 — prove one ingestion owner

Record a short source-backed call-path map for the existing CLI conversion, SDK onboarding and canvas capture entrypoints, naming the common normalization/schema-authority, emitter and publication owners and the legitimate wrapper differences. Exercise the same supported draft fixture and one malformed boundary/schema fixture through those real entrypoints. Compare admitted semantics, identity/native-port custody and semantic refusal reason, allowing different report formatting and explicitly optional presentation persistence. The normal H3 conversion must consume that same owner path without an H3-only bypass or restoration patch. A shared output formatter alone is not proof of shared ingestion. Reuse existing owners; no global ingestion migration or new facade is required.

Use a malformed authority/boundary case, not a missing model: draft persistence must remain independent of runtime readiness. E0 records the owner map/baseline, E1 fixes only demonstrated owner splits, and T3 executes the cross-entrypoint regression through Q5.

### Optional I8 / I9 test selection — edit inside a nested definition

Extend the existing depth-two/repeated-instance subgraph fixture with a real edit to a constructor/default in the emitted nested definition, then reload and re-emit the edited file. Assert the expected effective change, retained per-instance overrides, untouched sibling/scoped UIDs, interface and boundary bindings, fanout and output slots, and API/GraphBuilder parity. Apply the whole-file clean-source/custody checks inside generated definition helpers as well as build(). Keep malformed-boundary refusal coverage. Public-argument overrides alone do not satisfy this source-edit case.

The nested-definition fixture is an optional strong test choice within existing I8/I9, not an additional blocker; other adequate evidence can satisfy the existing contract. E2 produces the required I10 presentation and inspection evidence.

## Astra final repair-completeness adjudication — 2026-09-12

The amended plan is sufficient in scope; Astra identified three explicit
regression requirements to add within the existing task owners. These are
completion requirements, not a new framework, task family, review stage or
budget:

1. **Identity and pair integrity (P0):** prove source UID/provenance →
   companion → rebuild → exported-graph mappings, including positions and
   scoped identities; refuse missing, swapped and stale companions; and prove
   failed publication preserves an existing pair byte-for-byte. A matching
   regenerated digest alone is insufficient.
2. **Recursive context recovery (P0):** prove repeated builds, exception
   cleanup, caller-context restoration and sibling-instance isolation through
   the existing recursive kernel. Investigate semantic digest differences
   field-by-field; never weaken these checks to build-success assertions.
3. **Independent corruption counterexamples (P1):** for each repaired
   behavior, retain a negative control that changes a value, removes a fanout
   destination, swaps a nonzero output slot or crosses sibling scope. The
   virtual-wire contract must continue rejecting distinct competing producers.

The current execution adds these checks under E1/T1/T3 and the existing
workflow-context, bundle, recursive, output-slot and virtual-wire suites.
Case 14 remains conditional on the bounded matching-frontend load/export
experiment; conversion success alone does not establish recovery. Stop on
identity loss, unexplained semantic drift, leaked context, fabricated or
dropped endpoints, partial publication or missing lifecycle evidence.

## Correction evidence — implementation commit `955d5f01`

The three findings above were repaired within the existing owners. Recursive
companion custody is now closed at the definition, constructor-record and
port-shape boundaries; the emitter only carries definition identity plus the
typed structural witness. The scratchpad loader compiles current source bytes
on every pair load, and the rewrite regression proves that authored positions
and Markdown annotations survive a semantic edit.

The 17 positive corpus cases each have original/edited/reloaded/exported and
repeat-regeneration artifacts in
`evidence/corpus-lifecycle-f239-rework-20260912/`. Cases 10, 16 and 17 have
independent refusal receipts in
`evidence/refusal-lifecycle-rework2-20260912/`, including unchanged existing
candidate bytes and zero partial outputs. H3’s corrected pair and exact
exported graph are in `evidence/h3-current-final-20260912/`; its presentation
contains 7 positioned records and 4 annotations, and the exported graph has
20 nodes and 25 links.

The deterministic configured suite on the corrected commit reports **10,562
passed, 195 skipped, 35 deselected, 1 xfailed, 0 failed** with empty stderr;
the IR boundary scan reports `IR boundary: clean`. The recorded Astra final
review remains `REWORK` because the review ceiling was exhausted before this
correction; no new review approval is implied.

## Astra high custom-node emission rework — required closure — 2026-09-13

The explicit Astra-high adjudication reopened the cleanliness obligations
that the historical H3 artifact does not satisfy. The artifact contains five
raw calls: four LanPaint classes whose schemas are proven by the pinned
registry source, and unresolved `MiniMaxH3ImageToVideo`. I8/I9/I10 therefore
remain not closed by the previous green suite or corpus receipts.

### I8 — typed imports and calls

E0/T3 must freeze source/version/digest/reason per class, separating backend
field order from frontend-added widget positions. E1 must reuse the existing
discovery/codegen/registration path to provide bounded importable LanPaint
wrappers for `LanPaint_SamplerCustomAdvanced`, `LanPaint_AVDecode`,
`LanPaint_AVEncode` and `LanPaint_VideoMaskEditor`. The emitter must produce
complete imports and typed constructors for every proven class across the
shared paths. Dynamic editor choices must not be fabricated; the trailing
sampler UI button must not become a backend argument.

### I9 — residual fallback and finalization contract

Every remaining `raw_call` must carry an exact class/source/reason allowlist
entry. MiniMax is the current unresolved positive control; a missing wrapper
registration, incompatible schema or missing import is a failure, not an
ordinary unresolved fallback. Tests must cover forwarding/omission, output
arity/names/types, nonzero output slots, malformed/conflicting schema refusal,
unchanged destination bytes and zero partial outputs.

Finalization must preserve semantics rather than force one spelling: use
`output_node` only when its inferred artifact metadata is lossless; preserve
explicit `OutputSpec` for explicit null artifact metadata, empty outputs and
ordered multi-output declarations. Whole-file checks reject custody/replay,
duplicate authority, oversized closing expressions and incomplete imports.

### I10 — fresh practical validation

T1/T2/T3/E2/T4 must regenerate the exact H3 and affected corpus through normal
CLI/SDK/canvas entrypoints, then prove source shape, semantic values/edges,
identity/UIDs, provenance, nested/native subgraphs, editability,
save/reload/export, atomicity/refusal/rollback and deterministic repeat
generation. Record inspection of the exact whole Python file and exported
graph. Add or extend existing tests only; no new task ID or review stage.

Closure requires the current implementation plus fresh evidence for all three
end-state fixes together: typed custom-node imports, elimination of avoidable
raw calls, and a clean semantics-aware finalizer.

## Final implementation and validation evidence — 2026-09-13

The latest exact candidate is
`e81239c9540aa47c117c4238eb0c97b3690ea2b9`. This section supersedes earlier
`NOT RUN / MISSING` snapshots for implementation evidence while preserving
their historical record. It does not manufacture a reviewer PASS after the
configured review ceiling.

| Scope | Result | Evidence |
| --- | --- | --- |
| I1–I9 implementation and regression coverage | Green: 10,603 passed, 195 skipped, 35 deselected, 2 xfailed, 0 failed | `evidence/full-suite-final-green-attempt-20260913/`; affected lane 240 passed / 6 skipped |
| I8 source cleanliness | Green on fresh H3 source: typed wrapper imports, zero `raw_call(` calls, no custody/replay/`wf.connect`/direct graph restoration, concise finalizer | `evidence/h3-final-e81239c9-20260913/h3.py`, `edited/preserved-inspection.txt` |
| I9 identity, presentation and atomic lifecycle | Green for edited H3 pair: 20 nodes, 25 links, unique UIDs, four Markdown-note annotations, seven presentation records, canonical pair reload | `evidence/h3-final-e81239c9-20260913/edited/h3-edited-preserved.*` |
| I10 exact H3 rehearsal | Green locally for convert → edit → bundle rebuild → save/reload → UI export → exact inspection → deterministic regeneration | `evidence/h3-final-e81239c9-20260913/` |
| Corpus extension | 30 additional deterministic pseudo-random Hivemind-derived sources: 27 complete pairs, 3 source-level refusals, 0 partial outputs | `evidence/hivemind-workflow-corpus-30-random-e81239c9-20260913/summary.json` and `selection.json` |

The final full-suite command exited `0` with **10,603 passed and 0 failed**;
warnings/skips/deselections remain reported rather than hidden. The original
50-source replay remains **46 successful pairs and 4 source-level refusals**;
the additional 30-source sample reproduces three of those known refusal
classes (`bypass_no_match`, duplicate `seed_override`, `bypass_ambiguous`) and
adds no new failure class. No claim is made that malformed or semantically
ambiguous source bytes should be force-repaired.

The final evidence is implementation-complete but not a new independent review
PASS. Historical final-review `REWORK` and exhausted review/oracle ceilings
remain preserved. Live GPU/media execution and the unavailable frontend/
ComfyUI boundary remain explicit environment blockers, not skipped acceptance
claims.

## Post-audit correction evidence — 2026-09-13

The exact 30-case Luna audit and the user-authorized Astra adjudication found
two generator-produced duplicate model requirement names. Correction commit
`baff8dc932a2afaba71fbea5cd18b00348abe16b` adds shared reconciliation across
conversion, ready-template finalization and v2 pair canonicalization. It keeps
authored duplicates when they are part of the contract, removes stale edited
names, adds inferred names once, and preserves explicit empty requirements.

| Scope | Result | Evidence |
| --- | --- | --- |
| Focused correction matrix | 338 passed, 0 failed | `evidence/requirement-reconciliation-20260913/receipt.md` |
| Exact 30-source replay after correction | 27 complete pairs, 3 source-level refusals, 0 unexpected results, 0 partial outputs | `evidence/hivemind-workflow-corpus-30-post-requirement-fix-20260913/` |
| Case `17dc9bc3ed806c24` | `BerrysMix.vae.safetensors` emitted once | `evidence/luna-model-requirements-20260913/17dc9bc3ed806c24/canonical.py` |
| Case `62682a77ae33b43a` | Five distinct model names emitted once each | `evidence/luna-model-requirements-20260913/62682a77ae33b43a/canonical.py` |
| Full suite | 10,608 passed, 195 skipped, 35 deselected, 1 xfailed, 0 failed/errors | `evidence/requirement-reconciliation-20260913/receipt.md` |

This is implementation evidence, not a new formal reviewer PASS. The existing
historical review dispositions and exhausted lifetime ceilings remain intact.

## Publication receipt — 2026-09-13

The validated implementation branch is published to the authorized fork
`HannahSubmarine/VibeComfy` at `otto/unified-workflow-integrity-20260909`, with
open PR [#157](https://github.com/peteromallet/VibeComfy/pull/157) targeting
`main`. Publication is complete; merge, deployment and production cutover
remain outside scope.

## Openability/refusal acceptance amendment — 2026-09-14

The current user direction and Astra adjudication add this bounded behavioral
distinction to I1/I2/I3/I7/I8/I9/I10 without changing their IDs:

1. JSON syntax-invalid input must refuse before any output is written.
2. Parseable ComfyUI-origin or retained-UI source that can be preserved must
   yield a complete, explicitly classified open/draft artifact, even if its
   executable projection remains unresolved.
3. Execution promotion must remain refused for a missing or ambiguous bypass
   source, duplicate labels whose semantics are not proven, dangling endpoint,
   missing node definition, or other source-specific unresolved condition.
4. Draft support must preserve authored nodes, modes, edges, positional widget
   values, identity and provenance; it must not invent connections, drop
   widgets, or add raw graph replay to canonical Python.
5. A reconstructed UI artifact must be labelled reconstructed and must retain
   the source envelope; it cannot claim byte-identical original ComfyUI-file
   fidelity.

The exact 30-case replay is the required regression corpus. Its three current
refusals are `bypass_no_match`, duplicate `seed_override`, and
`bypass_ambiguous`. Amended evidence must report per-case syntax/shape/UI/
execution classification, frontend load/serialize result, artifact kind,
graph/UID/provenance preservation, atomicity and deterministic repeat outcome.
The existing 27 complete pairs are a regression floor, not optional coverage.
The local browser harness is not sufficient by itself because it substitutes
`loadGraphData`; the frontend experiment must use the pinned official loader or
an exact source-backed fixture without GPU/model execution.

## Openability amendment execution result — 2026-09-14

The amendment is implemented and validated. The final deterministic full suite
exited `0` with **10,609 passed, 195 skipped, 35 deselected, 1 xfailed, 0
failed**. The new authored-graph draft regression passed independently
(`1 passed`).

The exact 30-case replay now produces **30 complete Python/companion pairs, 30
open drafts, 27 compile-clean drafts, 3 explicitly compile-unresolved drafts,
and 0 partial outputs**. All 30 Python files parse, all 30 companions parse,
and all 30 pairs reload through `load_bundle`. The three formerly refused cases
preserve node IDs, authored UIDs, modes, and edges exactly (`3/3`). Their
execution diagnostics remain narrow and source-specific: `bypass_no_match`
for `0eb67659bfc4dc63`, and provider-free preserved-draft `bypass_dangling`
for `4eebf3dc07942c52` and `506ebdde037e22d8`; no connection or widget value
was invented or removed.

The complete receipt is
`.otto/runs/unified-workflow-integrity-20260909/receipts/openability-30-final-20260914.md`.
The result proves VibeComfy draft opening/reload, not official ComfyUI
frontend load/serialize: the captured inputs are VibeComfy envelopes with
ComfyUI provenance, not original LiteGraph files, and the local harness is not
an official frontend loader.
