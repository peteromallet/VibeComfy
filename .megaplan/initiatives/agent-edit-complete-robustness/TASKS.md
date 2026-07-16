# Execution Task and Proof Ledger

This is the operator-facing ledger. Milestone plans may add finer-grained
tasks, but they may not weaken these requirements.

## M0 — Incident foundation

- [x] Classify every dirty file as intended baseline or unrelated.
- [x] Keep `scorecard.png` out of all epic commits.
- [x] Restore or replace the two skipped rollback-diagnostic assertions.
- [x] Run and record focused browser, Python, and ownership suites.
- [x] Prove each exact incident fixture fails before its fix and passes now.
- [x] Record clean-environment versus ambient-extension browser results.
- [x] Add a machine-readable baseline gate manifest.
- [x] Commit the baseline independently before architecture extraction.

## M1 — Contracts

- [x] Add a single projection registry with typed/versioned names.
- [x] Version `structural_v1`, `layout_v1`, and explicit `workflow_v1` policy.
- [x] Bind every operation to forward and rollback projections.
- [x] Make delta version, scope, precondition, postcondition, inverse strategy,
      and projection version mandatory in prepared authority.
- [x] Ratify Undo durability semantics.
- [x] Ratify legacy transaction migration/version behavior.
- [x] Encode stable identity rules for every entity class.
- [x] Add browser/Python golden fixture equivalence.
- [x] Reject unknown versions and unsupported root/nested scope combinations.

## M2 — Native adapter

- [x] Slice 1: inventory and freeze native graph access in the versioned
      machine ledger, with source-derived ownership/schema guardrails.
- [x] Slice 2: create the dependency-injected typed public boundary in
      `intent_graph_adapter.js` and route the bounded capture/projection/
      revision/repaint responsibilities through it.
- [ ] Move live graph capture, native normalization, stable-ID handling,
      mutation, restoration planning, and serialization behind the adapter.
- [ ] Route preview, Apply, rollback, Undo, and recovery through canonical ops.
- [ ] Eliminate forward whole-graph replacement.
- [x] Inventory native normalization behavior and field semantics for the S1
      authority freeze; later migration dispositions remain S3–S6 work.
- [x] Add bounded S1/S2 adapter ownership guardrails; the final sole-owner gate
      remains Slice 6 work.
- [ ] Prove all supported delta operations through real LiteGraph.

Slices 1–2 are accepted with 77/77 focused tests, 519/519 browser contracts,
238 roundtrip passes plus 2 intentional legacy skips, and a 78-row/120-mapping
machine ledger. M2 remains open for Slices 3–6.

## M3 — Verifier

- [ ] Create `graph_apply_verifier.js`.
- [ ] Centralize precondition, landed-operation, postcondition, finalize,
      rollback, and mismatch comparison.
- [ ] Emit structured bounded projection diffs.
- [ ] Remove all duplicate inline verification decisions.
- [ ] Add partial-mutation, serialization, inverse, and restore fault injection.
- [ ] Pass every incident fixture through the same public verifier API.

## M4 — Workflow controller and API

- [ ] Create `agent_edit_api.js` as sole transport owner.
- [ ] Create `agent_edit_controller.js` as sole transaction coordinator.
- [ ] Maintain one complete `WorkflowEditContext` per workflow.
- [ ] Fence every async commit by workflow, activation, operation, submit/apply,
      session, turn, candidate, and transaction identity.
- [ ] Preserve lifecycle reducer as transition authority.
- [ ] Reduce `vibecomfy_roundtrip.js` to bootstrap/events/view composition.
- [ ] Prove workflow switching during every phase and late-result rejection.

## M5 — Recovery, Undo, and migration

- [ ] Encode an executable recovery action for every durable nonterminal state.
- [ ] Implement the ratified Undo semantics.
- [ ] Reconcile ambiguous prepare/finalize responses from durable receipts.
- [ ] Preserve recovery authority across refresh and workflow switching.
- [ ] Show exact unresolved projection differences after rollback failure.
- [ ] Enforce legacy version policy without silent reinterpretation.
- [ ] Prove recovery actions are fenced and idempotent.

## M6 — Real ComfyUI and CI

- [ ] Build a pinned minimal ComfyUI correctness environment.
- [ ] Build a separate representative custom-node compatibility environment.
- [ ] Cover every supported transaction family end to end.
- [ ] Cover failure, refresh, switching, rollback, and persistence.
- [ ] Cover all named incident and adversarial fixtures.
- [ ] Attribute failures separately to VibeComfy, ComfyUI core, or extensions.
- [ ] Add static ownership and title-identity regression gates.
- [ ] Wire the full browser suite and composition matrix into CI.

## Final nine-point audit

- [ ] Every identity and projection has one authoritative owner.
- [ ] Every graph mutation uses a declared canonical operation.
- [ ] Native ComfyUI normalization cannot cause false verification failures.
- [ ] Every workflow has isolated state and asynchronous authority.
- [ ] Every post-prepare failure has deterministic recovery.
- [ ] Stable IDs always outrank presentation heuristics.
- [ ] Browser and backend projections are proven equivalent.
- [ ] Real ComfyUI covers success, failure, refresh, switching, rollback, and
      persistence.
- [ ] Static guardrails prevent duplicate ownership from returning.
