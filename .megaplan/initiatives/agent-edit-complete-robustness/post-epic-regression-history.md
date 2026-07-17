# Appendix: Why Regressions Appeared After the Transaction-Spine Epic

## Conclusion

The regressions appeared after **Agent Edit Verifiable Transaction Spine**
because the epic crossed from permissive canvas mutation into strict
transactional verification before the system had one defined representation
boundary between:

1. the authored candidate graph;
2. the live native ComfyUI/LiteGraph graph;
3. the graph ComfyUI serializes after mutation; and
4. the graph and hashes persisted by the backend.

Before the epic, Apply accepted the turn and then mutated the canvas without
requiring the native post-Apply serialization to equal the authored candidate.
That path looked reliable because ComfyUI normalization differences were
silently tolerated. The epic correctly made those differences observable, but
its first implementation treated different representations as though they were
identical. Some resulting failures were newly introduced regressions; others
were older defects exposed by the stronger checks.

## Commit Evidence

- `86c09135` prepared the transaction-spine epic and required exact
  preview/Apply parity, browser serialization verification, and rollback.
- `c54c530d` landed Sprint 2 across 38 files, adding approximately 11,484 lines.
  It added 637 lines to `vibecomfy_roundtrip.js`, 2,032 to backend `session.py`,
  409 to the lifecycle reducer, and 459 to the reorganisation compiler.
- `c54c530d` created `canonical_hash.js`, but independent canonicalization and
  structural-projection implementations remained in `vibecomfy_roundtrip.js`,
  `scope_resolver.js`, and Python `session.py`.
- The new browser hash owner imported Node-only `node:crypto`, preventing the
  real browser extension from loading. `14dcdb1c` repaired that immediately,
  followed by the Chromium boot gate in `2b0546b5`. This demonstrates that the
  Node/fake-LiteGraph tests did not prove the shipped browser composition.
- The following repair sequence landed immediately after the epic:
  `b815d693`, `e60104f5`, `8297bbbd`, `b09973be`, `3a4ba4e7`,
  `3340b631`, `6af23890`, `25f40242`, `31a77663`, `bce8d960`,
  `a5b5ba17`, and `424a031b`. Their subjects include completing transaction
  routing, consolidating candidate authority, preserving authority through
  rehydrate, repairing Apply/Undo recovery, and making layout transactional.
  The milestone had therefore merged before the transaction model had one
  complete owner and one exhaustive lifecycle.

## Incident Mapping

### `eb45e0ef…`: dynamic `vibecomfy.exec`

The agent and edit engine behaved correctly: the code node and its link landed
as two canonical operations with no diagnostics. Apply then failed because the
post-Apply native structural hash differed from the candidate structural hash.

ComfyUI reconstructs dynamic `vibecomfy.exec` sockets, widget values, and
properties during native node creation. The candidate representation and native
serialization were semantically equivalent but byte/projection different. The
new verifier exposed this latent normalization mismatch and rolled back a valid
edit. The incident repair's `graph_projection.js` explicitly normalizes dynamic
`exec.io`, confirming the representation mismatch.

### `a66422e6…`: layout verification and group identity

This incident combined a false verification contract with a real identity bug:

- the historical candidate contained multiple id-less groups with the same
  title, including duplicate `Prompt / Text` groups;
- the compiler sidecar emitted title, bounds, color, and membership, but no
  stable group ID or scope path;
- the browser adapter used ID, then title, then array index as group identity;
  and
- native group serialization did not preserve all compiler-only membership and
  scope fields.

Duplicate titles could therefore alias during Apply, while whole-graph equality
also compared fields the native adapter could not preserve. The correct repair
is the versioned `layout_verification_v1` / `browser_layout_v1` projection,
stable group IDs, and rejection of title/index fallback.

### Loose `Displays / Labels` group

This was not created by the transaction protocol itself. It is a latent
pre-epic heuristic from `08e7dba4`: `_wall_section_rank` and
`_huge_wall_band` consulted presentation text before generated bucket identity.
Consequently, `Displays / Labels` matched the generic `label` rule and moved to
the far-right/footer band.

Sprint 2 changed reorganisation broadly, and `558994a6` later restored
pre-spine behaviour, including this old heuristic. The durable rule is that
stable semantic bucket identity outranks titles.

### Workflow-tab state leakage

The underlying scope-switch defect predates the epic. The snapshot logic from
`6fd3c8bd` stored multiple workflows inside one singleton panel state and
restored snapshots with merge semantics. For a new workflow without a snapshot,
the switch changed only a few fields; phase, session, turn, transcript, and
progress could remain from the departed workflow until asynchronous rehydrate.

The epic added more in-flight phases, receipts, and recovery state to the same
singleton, making the old isolation defect more visible and consequential. A
fresh scope must begin from canonical fresh state, and asynchronous work must
be fenced by a monotonic workflow-activation token.

### Post-prepare recovery failures

The first transactional implementation did not give every durable state an
actionable successor. Examples included treating finalize-start as
`FINALIZED`, invalidating candidate authority on some failures, and attempting
automatic rollback without preserving recovery authority when rollback or
finalize was ambiguous.

The missing distinction between `FINALIZING`, terminal `FINALIZED`, and
`RECOVERY_REQUIRED` was another sign that the lifecycle was implemented as
branches inside the orchestration shell rather than as one exhaustive
transaction controller.

## Ranked Foundational Causes

1. **Equality preceded equivalence.** Strict hashes were enforced before
   authored, native, serialized, and persisted graphs had an explicit versioned
   semantic projection.
2. **Ownership was only partially migrated.** Hashing, projection, native
   mutation, lifecycle, and recovery remained distributed across the roundtrip
   shell, scope resolver, adapter, reducer, and Python mirrors.
3. **Transactions remained singleton orchestration.**
   `vibecomfy_roundtrip.js` continued coordinating workflow state, native graph
   access, Apply, verification, finalize, rollback, rehydrate, and Undo instead
   of delegating to a workflow-scoped controller.
4. **Stable identity was optional.** Titles and indexes remained fallback
   identity, and presentation text remained layout authority.
5. **The integration gate was weaker than the architecture.** Tests exercised
   components and a fake LiteGraph harness, but not real ComfyUI
   prepare → Apply → serialize → verify → finalize and rollback composition.
6. **The epic coupled too many boundaries.** Transaction persistence, browser
   lifecycle, canonical hashing, native Apply, rollback, and reorganisation were
   changed together, making partial migration and broad rollback likely.

## Introduced Regressions Versus Exposed Defects

The result was mixed:

- The epic directly introduced the browser hash import failure, incomplete
  transaction/recovery ordering, and false post-Apply verification failures.
- It exposed latent dynamic-node normalization, title-based group identity, and
  workflow snapshot-isolation defects that the earlier permissive Apply path did
  not check.
- The loose `Displays / Labels` placement predates the epic, but the post-epic
  restoration commit re-exposed it.

## Corrective Architectural Boundary

Recurrence prevention requires:

- one native graph adapter owning capture, normalization, mutation,
  serialization, restoration, and native capability checks;
- one versioned projection registry for structural, layout, and workflow
  verification, with browser/Python parity fixtures;
- canonical operations carrying declared precondition and postcondition
  projection versions;
- mandatory stable identities with no title or array-index fallback;
- one workflow-scoped edit controller with activation and asynchronous commit
  fencing;
- an exhaustive recovery table for every post-prepare state;
- static guardrails forbidding duplicate graph, hash, projection, and
  transaction ownership; and
- a pinned real-ComfyUI success and failure-injection composition suite as a
  release gate.

The current incident repairs are necessary and directionally correct, but the
initiative is complete only when these ownership and composition boundaries are
enforced rather than documented by convention.

## 2026-07-17 Accepted Prevention Checkpoint

The C0–C1 checkpoint now closes the representation-contract prerequisites that
made the transaction-spine regressions difficult to reason about:

- layout, materialization, and inverse relations are versioned and mirrored in
  JavaScript and Python from shared goldens;
- canonical numeric edge cases and restoration digests fail closed with
  cross-language parity;
- persisted legacy authority crosses one explicit migration boundary instead
  of weakening current validation;
- the shared browser fixture factory preserves the exact operation list and
  order, including remove-link/upsert-link rewires; and
- the private plan builder is isolated from native/runtime imports and proven
  externally to make zero native calls.

The workflow-tab symptom also exposed a second stale-work boundary: queued
render callbacks and global diagnostic mirrors could outlive their panel or
workflow activation. The accepted scheduler fence binds queued work and
observability to the concrete panel plus activation identity, revokes replaced
cycles, and prevents a late callback from satisfying current-panel evidence.
The formerly failing race passes in the full browser suite and in two complete
roundtrip-file repetitions.

This checkpoint deliberately stops before the ownership cure is complete. No
native-authority row transferred: S3 remains 0/27, all seven S4-debt rows remain
open, and C2 must still make the native consumer/deletion/ledger change as one
atomic cut. Real ComfyUI mutation and rollback proof also remains later work.
