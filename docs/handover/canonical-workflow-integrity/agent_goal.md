# Goal and receiving authority

Advance the [North Star](./northstar.md): make workflow save/export preserve intended content and support drafts, then test existing Python/typed parity and document the real lifecycle. The [run configuration](./run.yaml) is the single role/model, stage and budget declaration. [Acceptance criteria](./acceptance-ledger.md) define the promised behavior; planning P outcomes are not implementation I proof.

## Handover authority

The user explicitly requested publishing all current branch work and the planning documents for another agent/person to execute this part. The preparer is authorized to snapshot current source and publish this dedicated public handover branch; it does not implement the product plan. The recipient is authorized to execute the bounded plan on a new isolated local implementation branch, run its required tests/reviews, and make local commits. On accepting the handover, change only mode from planning_only to delivery in run.yaml while preserving role assignments, criteria, stages and cumulative counters. Do not restart planning or reset spent calls.

Finish by returning the implementation commit ID, acceptance/test evidence, review outcomes and unresolved risks. Creating a PR, pushing implementation commits, merging, deploying, publishing runtime data or cutting over production is not authorized by this handover. The preparer's one public handover branch push does not grant those additional actions.

## Source

Use the exact source snapshot recorded in provenance.md/source-snapshot.json, plus this branch's handover documents. The source includes the selected branch's committed history, all 65 tracked modifications and five untracked tests present at capture. It is unverified working source, not certified implementation of this plan. Original audit BASE remains 6254cf5e88b4d16eafcc15d4b9f36253b3f8ad6b; subsequent dirty work was intentionally captured, not silently omitted. Before implementing, inspect what the newer source already satisfies and avoid reverting useful fixes merely to follow old line numbers. No access to the preparer's machine is necessary.

## Scope and preserved decisions

Preserve ordinary canonical save/reload, stable graph identity, exact bundle/reload/sidecar/revision binding and atomic refusal of unsupported loss. Draft save/export must not demand queue readiness. Plain export shares needed authority/presentation checks without mandatory canonical persistence. Keep public flags/recovery/trust and existing Python/typed interfaces, durable revision fencing, both transports. Parity changes are test-first and conditional; no speculative editor rewrite, generic normalization/result framework, new global loss toggle, blanket unknown rejection, compatibility shim, duplicate runtime gate or broad template migration. No unrelated compatibility deletion.

Use the existing emitter-preparation owner for accepted narrow normalization before constructing the expected bundle. The known PreviewAny case is historical evidence to reuse; the remaining representative opaque case is bounded as in the plan. Current source may already contain partial fixes; measure before modifying.

## Completion and limits

Delivery requires all declared I criteria with exact-candidate executable evidence and required stage PASS. Optional design preferences alone do not block. Follow plan.md for the coordinator/oracle distinction, concise decision request, correction/anti-loop and cap behavior. Missing evidence remains MISSING. Keep source and review identities frozen according to pinned Megado execution mechanics.

Use existing environment and small fixtures; focused/affected/final commands and resource limits are in tasklist.md. Resolve recipient prerequisites through dependencies.md. A missing existing environment may require ordinary local setup; do not run paid/live services or download large models. Do not silently substitute models. Scope/authority or required budget changes need user direction, not an oracle waiver.
