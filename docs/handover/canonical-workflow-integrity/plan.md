# Canonical workflow integrity — executable plan v3

Planning only. [run.yaml](./run.yaml) owns role/model bindings, stage scopes and every review/oracle ceiling. [agent_goal.md](./agent_goal.md) owns authority; [northstar.md](./northstar.md) remains unchanged. Current Megado semantics replace the old process, not the product objective.

## First useful outcome

A user can change `ksampler.steps` from 20 to 30, save/reload or export, and retain unrelated nodes, connections, widget values and presentation except for an explicitly supported normalization. Returned bundle, on-disk content, sidecar binding and revision agree. Unsupported loss refuses before replacing either destination. An unfinished graph stays saveable without model/runtime readiness.

Actual consumers are the Python SDK/authoring surface, CLI import/export, live agent Python-batch route, available typed-edit API and Comfy canvas. Existing server/embedded transports consume approved revisions. The evidence does not establish user counts or all external callers. Preserve working public flags/contracts and existing user files; do not build shims/deprecation machinery for hypothetical consumers or delete compatibility APIs without caller evidence. No production migration or deployment is in scope.

Required now: one save-integrity fix, targeted export consistency, test-led parity, accurate docs. Remove unnecessary handoffs and share existing rules. Defer generic frameworks, broad custom-node support, alternate interpreters, new CAS APIs without callers, new compatibility layers, transport changes and template migration.

## Segment 1 — save/export correctness

C0 is ordinary setup at delivery start: inspect HEAD, staged/unstaged binary diffs and relevant untracked bytes, compare the audited evidence, preserve newer work and record the adopted implementation base. Existing Git/run tools suffice. No custom custody program, separate setup gate, reset/stash/discard shortcut or silent exclusion of dirty work.

T0 reuses the known disconnected UI-only PreviewAny rule and wired-passthrough evidence. Resolve just one opaque/custom-node fixture using existing raw metadata/preservation or explicit refusal, within <=0.5 engineer-day; keep a short finding only if a decision remains to record. No new catalog or general policy.

T1 uses the existing emitter-preparation owner before constructing canonical bundle/sidecar/revision. Preserve unconditional staged equality against that exact intended result. Verify returned/reloaded content and sidecar/revision binding, including a sidecar-present case; injected unexpected node/edge/widget loss must leave the previous destination pair intact. Accepted normalization identifies affected content using existing diagnostics. It is not permission for arbitrary digest drift.

T2 shares needed authority, source and sidecar/materialization checks at public export without imposing persistence of canonical Python/bundle artifacts on plain export. Preserve --out, explicit --persist-sidecar, --from/breadcrumb layout, strict refusal, visible --force-drop, recovery/trust and preview no-write behavior. Draft UI export needs no queue readiness; API JSON remains a projection.

T1 and T2 shared-file mutations serialize. Test preparation can overlap; labels do not create global barriers. S1_READY means C0/T0 resolved, T1/T2 integrated and their required affected checks passed with exact candidate evidence. The save_export_completion stage catches a producer/export mismatch or wrong revision binding before substantial dependents build on it. It examines implementation, missing behavior and evidence, not later documentation/parity completion.

## Segment 2 — parity, docs and final integration

T3 tests equivalent Python/typed semantic outcomes and untouched UIDs through the existing interpreter/apply gate. Preserve supported no-op behavior and atomic rejection; reports can differ. Refactor only an actual mismatch. Existing revision fencing and both transports are regressions to retain, not new subsystems. Independent T3 test preparation can start after C0; changes consuming a failed Segment 1 invariant wait for its resolution. No shared-file race or stale checkpoint work.

T4 describes settled save/export/apply/queue boundaries and public APIs in the named docs/help. Run the one final affected matrix after all required tasks integrate. ALL_REQUIRED_WORK_AND_TESTS means C0–T4 complete, required I evidence present and tests passed.

The final stage sees the full integration diff and all criteria, including source-to-publication-to-consumer interactions, strategy, simplicity and North Star alignment. It reuses unchanged first-stage approvals rather than repeating the first whole review. No extra integration stage would expose a distinct risk, so there are only the two agreed boundaries. Caps are in run.yaml, are ceilings rather than quotas, and include correction rounds/restarts. Model binding does not itself make either stage XHARD.

## Coordinator mandate and oracle escalation

The coordinator drafts mechanical briefs, dispatches ready work, maintains source/evidence identities and counters, runs prescribed checks, and advances on uncontested PASS with required tests passing. It routes clear in-scope defects to the normal worker and affected tests. Reviewers are independent leaves, never the implementer; they cannot change scope or budgets. Binding the same model to reviewer and oracle does not merge those responsibilities.

Only contract_violation, implementation_defect and required_evidence_gap block. Optional improvement, out_of_scope and stale_or_repeated findings are recorded without expanding work. A design preference alone is not a blocker; strategic complexity blocks only if it violates an explicit contract/non-goal or causes a concrete defect. Missing/inaccessible candidate evidence stays MISSING/UNKNOWN.

Oracle triggers: consequential ambiguity not settled by the mandate; new evidence changing data/interface/authority or architecture; contested findings; unclear XHARD classification; failed required checks beyond the prescribed correction path; or two failed substantive corrections without progress. A routine test failure with an obvious in-scope fix or an uncontested PASS is not a reassurance request. The coordinator must not dismiss blockers, waive tests, make architecture/scope exceptions or enlarge budgets.

Keep decision request/reply together under a stable D-ID in status.md. Request: (1) exact decision; (2) why instructions/prior ruling do not settle it; (3) new evidence with source/test identities and prior ruling; (4) recommendation plus main alternative/tradeoff; (5) blocked work and recurrence count. Reply: disposition proceed/change approach/investigate/blocked; decision and reason; concrete scoped next action; return condition. Investigate must name the uncertainty and evidence sought.

Every oracle response, including diagnosis or inconclusive output, consumes its separately configured lifetime budget. Reuse a ruling when no decision/new evidence exists. If the same decision returns twice without new evidence/action, no third reconsideration: diagnose brief/mandate/worker/tool failure and repair, decompose or use a bounded experiment. Ten consecutive checks without substantive progress are an alarm, not diligence. Pause only dependents; pause all work only for overall scope/authority/correctness. At a cap, continue useful authorized corrections/tests or independent work but do not cross the unpassed gate or relabel another call. Seek only the user budget/authority change actually needed. Oracle-requested model review consumes both applicable budgets.

## Review packet assembly

Use review-packet-template.md, copied from the current skill, only when an actual delivery stage/round is ready. This planning update defines inputs; it creates no executable certification packet or packet-building service.

| Packet content | Exact artifact source |
|---|---|
| Role, lens, trigger, stage/overall remaining counts | run.yaml plus durable attempt entries in status.md |
| Full North Star, requirements and authority | northstar.md verbatim; current agent_goal.md |
| Scoped expected behavior, dependencies and proof | I IDs selected from acceptance-ledger.md, including every required scenario |
| Decisions/non-goals and tasks | this plan, tasklist.md, relevant concrete oracle rulings |
| Candidate changes | actual implementation base/candidate SHA/tree or snapshot manifest, read-only location, one relevant changed-path/integration census, full scoped diff; final includes full run diff |
| Criterion-to-test evidence | one row per scoped I ID: exact command, input/environment identity, result and receipt path/digest; NOT RUN/MISSING until actual evidence exists |
| Prior findings and corrections | accepted issue/evidence/outcome and oracle rulings; affected criterion dependency closure; no persuasive verdict narratives |

First round checks the complete stage scope. Later rounds contain the actual correction diff, affected integration proof and full accessible contract; unaffected approvals survive. Before dispatch mechanically verify accessible frozen identities, section/criterion coverage and passing stage-trigger checks. If tests are known incomplete, do the work first; do not outsource known incompleteness to a reviewer. If a real evidence gap must be reviewed, mark it explicitly. Save one immutable packet+manifest per actual invocation; no separate packet approval gate.

## Estimate and remaining uncertainty

Segment 1: 4–5.5 focused engineer-days including ordinary setup and the <=0.5-day opaque-case decision. Segment 2: 2–3 days, leveraging existing parity/fence/transport coverage. Ordinary total 6–8.5; separate contingency 1–2; budget 7–10.5 eight-hour engineer-days (1.4–2.1 five-day weeks), not agent elapsed time. Process clarification adds no implementation feature or scheduled review, so the estimate is unchanged. Thresholds do not generate gates.

No unsettled product-direction choice. Implementation unknowns: reconcile ongoing dirty-source work; preserve or explicitly refuse the representative opaque case; discover whether parity needs any correction; prove pure export can reuse checks without incidental persistence. Each is owned by C0/T0–T3 with tests and existing refusal paths. The published source snapshot contains later changes than the audit; inspect current behavior before applying fixes. No product certification is implied. Material new scope/authority evidence uses the oracle protocol rather than an unbounded contingency.
