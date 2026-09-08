# Acceptance and evidence — planning history plus future behavior

This existing file is retained as the single criterion source, not a new approval gate. P IDs track plan adequacy; I IDs track executable behavior and cannot inherit a planning PASS. Source baseline and adopted snapshot are recorded in provenance.md. Proposed checks Q0–Q5 are in tasklist.md.

## Planning criteria: preserved IDs and user-authorized mapping

| ID | Meaning / dependency | v3 disposition and evidence |
|---|---|---|
| P1 | Accurate source/base/dirty evidence; none | Prior planning evidence retained; published source snapshot in provenance.md; no product certification |
| P2 | Complete bounded outcome and deferrals; P1 | Same save/export/parity/docs outcome; plan.md; no newly required feature |
| P3 | Tasks, owners, dependencies, behavior/proof; P2 | Refined by current user instruction: responsibility slots + replaceable bindings; run.yaml/tasklist.md/I criteria |
| P4 | Operational budgets/source/authority; P1 | Refined: explicit cumulative review/oracle ceilings, historical counts and restart rules; run.yaml/status.md |
| P5 | Adequate planning challenge and review-policy consistency; P2,P3,P4 | Historical independent discovery/contract/Astra evidence preserved; new skill does not require rerunning certification merely to edit a plan. v3 coordinator checks configuration/packet consistency, not a new oracle verdict |
| P6 | Practical example, sequence, estimate and explicit unknowns; P2,P3,P5 | Same 20→30 example, two-segment path and estimate in plan.md |

Previous frozen P PASS entries, review counts and rulings are archived under history.md. No historical rejection, critique or correction is removed. Delivery evidence below is MISSING; no product acceptance has been passed by this update.

## Prospective implementation criteria

| ID | Required behavior and relevant negative case | Dependencies | Required evidence | Current status |
|---|---|---|---|---|
| I1 | Canonical save/reload preserves intended semantic content and stable identity. Existing supported normalization is explicit and occurs before bundle/sidecar/revision construction. Returned bundle, reloaded Python, sidecar binding and revision inputs agree. Inject unexpected node/edge/widget loss and assert refusal with both existing destination files unchanged; include sidecar-present case | none | Q0/Q1; actual before/after semantic projections and pair-binding assertions on exact candidate; failure fixture asserting unchanged destinations | NOT RUN / MISSING |
| I2 | Incomplete/missing-model drafts can save without queue readiness. One representative unknown/custom class with UID/widgets/raw properties/edges preserves supported payload through existing owner or returns explicit refusal before replacement; no blanket rejection or invented result interface | I1 | Q1 fixture contrasting draft persistence with readiness; opaque fixture result and any permitted normalization/refusal diagnostic | NOT RUN / MISSING |
| I3 | Draft JSON/Python inputs export via needed authority/sidecar checks without forced canonical persistence. Preserve --out, --persist-sidecar, --from/breadcrumb layout, strict refusal, visible force-drop, recovery/trust and preview no-write; API export remains projection | I1,I2 | Q2 temp-directory positive/negative fixtures; named scenarios test_draft_json_export_without_readiness, test_draft_python_export_without_readiness, test_explicit_out_does_not_write_sidecar, test_persist_sidecar_writes_canonical_pair, test_from_and_breadcrumb_preserve_layout, test_strict_refusal_is_explicit, test_force_drop_is_visible, test_preview_is_no_write; cover API/recovery/trust behavior with existing or added assertions | NOT RUN / MISSING |
| I4 | Equivalent Python/typed field changes yield same admitted semantics and untouched UIDs; reports may differ. Actual no-op semantics and atomic rejection/history behavior remain. Refactor only demonstrated mismatch | none; changed shared publication assumptions depend on I1 | Q3 positive parity and rejected-edit fixtures, one-field 20→30 preservation case; canonical delta and untouched-node assertions, not identical narrative strings | NOT RUN / MISSING |
| I5 | Existing durable revision/precondition protection and both approved server/embedded execution transports remain; no stale revision becomes newly accepted. No new concurrency subsystem required | I1,I3,I4 | Q3/Q5 relevant existing stale/revision/runtime cases plus source dependency inspection; reuse matching valid receipts, never claim mocked transport checks prove live GPU execution | NOT RUN / MISSING |
| I6 | Named docs and CLI help describe actual draft/save/export/apply/queue, normalization/provenance/revision and optional persistence behavior | I1,I2,I3,I4,I5 | Q4 source/help comparison + implementation/test references; grep success alone is insufficient | NOT RUN / MISSING |
| I7 | Stay within existing rule owners and agreed scope: no editor/normalization framework, forced persistence lifecycle, redundant gates or speculative compatibility layer. Preserve North Star invariants applicable to stage scope | none; assess only completed stage scope, whole integration at final | Scoped diff/entrypoint evidence; every new abstraction justified by a current criterion. Preferences/alternative designs alone are optional. Final additionally assesses integrated strategy, simplicity and North Star alignment | NOT RUN / MISSING |

I1/I2/I3/I7 are the intermediate scope; final includes all I IDs. I7 at intermediate never demands future T3/T4 work. Changes invalidate only affected criteria and stated downstream dependencies; criterion IDs and review counters survive renaming/restarts. An actual integration change broadens the affected evidence, not the budget.

## Outcomes and evidence discipline

PASS requires adequate exact-candidate evidence and no unresolved blockers. REWORK names a source-backed contract violation, implementation defect or required evidence gap attributable to the deliverable. UNKNOWN covers inaccessible/mismatched identity/evidence; it consumes the attempted round and cannot imply PASS. Optional improvement, out_of_scope and stale_or_repeated remain nonblocking with a recorded disposition.

Each real packet includes one row per scoped I ID with command, inputs/environment, result, evidence path/digest, and explicit MISSING entries. Worker summaries and old planning approvals are not executable proof. The coordinator routes clear defects; disputed findings and exceptions go to the configured oracle. No weakened criterion or hidden extra review is permitted at a budget cap.
