---
type: brief
slug: sprint-1
title: Authority Preservation and Canonical Candidate
epic: agent-edit-verifiable-transaction-spine
created_at: '2026-07-13T21:26:07.861108+00:00'
---

# Sprint 1: Authority Preservation and Canonical Candidate

## Outcome

Every new applyable agent-edit turn has one lossless, fail-closed authority chain
from browser submission through executor serialization. Queue, canvas, task,
plan, and lifecycle decisions cannot be broadened or lost at handoffs, and the
durable candidate is reproducibly derived from the cumulative normalized delta.

This sprint is containment plus contract consolidation. It must make the known
handoff contradictions impossible before Sprint 2 builds transactionality on
top of them.

## Starting Evidence

- `../research/end-state-and-pipeline-audit.md`
- `../research/routing-research-pipeline-audit.md`
- Existing `.megaplan/initiatives/agent-edit-canonical-deltas/` work is baseline,
  not a parallel authority model.
- Existing `.megaplan/initiatives/vibecomfy-trust-correctness-2026-07/` work and
  corrective commits on `main` are baseline and must not be reverted.

## In Scope

- Publish the ordered operations landed by `batch_repl` as one cumulative
  top-level V2 delta.
- Normalize or reject every delta before persistence.
- Derive the candidate from immutable submit bytes plus that delta and verify
  replay equality server-side.
- Preserve canvas/queue authority, task satisfaction, batch receipts, plan
  status, and proof artifacts exactly through executor serialization.
- Remove eligibility reconstruction from route and candidate presence.
- Introduce explicit plan states: `not_required`, `required_supported`, and
  `required_unsupported`.
- Introduce independent four-state completion proofs for transformation safety,
  graph validity, task satisfaction, and runtime readiness.
- Add an initial obligation ledger covering user-stated outcomes and authorized
  scope.
- Make edit-plus-clarify non-applyable unless all required obligations are
  independently satisfied.
- Forward one idempotency key through routing, research, provider execution,
  editing, reply, persistence, and commit.
- Separate durable implementation success from optional reply narration. Reply
  failure must preserve the candidate and authoritative status.
- Enforce evidence precedence and prevent provisional workflow observations from
  authorizing Queue.
- Record research query transformations, freshness, content hashes,
  compatibility, and deterministic precedent selection.
- Route the legacy direct-edit endpoint through the canonical contract or make it
  explicitly non-applyable with a documented removal path.
- Add composition tests for the exact known failure families from both audit
  documents.

## Out of Scope

- The full browser prepare/finalize transaction and crash journal.
- Wholesale replacement of all graph or evidence representations.
- Complete semantic oracles for arbitrary requests.
- Broad reorganisation compiler changes.
- Generic frontend redesign.
- Removing historical V1 artifact readability; a read-only migration adapter is
  allowed.

## Locked Decisions

- The durable agent-edit response is the sole eligibility authority.
- New applyable turns do not use implicit V1 or best-effort whole-graph fallback.
- Narration is presentation, never transaction authority.
- Missing required proof is `unknown` or `not_run`, never an inferred pass.
- Provisional schemas may help draft a candidate but cannot establish runtime
  readiness.
- Compatibility bridges are isolated, tested, observable, and carry deletion
  criteria.
- The milestone must test the composed public routes, not only individual gates
  and serializers.
- Preserve the newer lifecycle and trust contracts already on `main`.

## Open Questions for Planning

- Where should immutable submit bytes and canonical delta receipts live so
  redacted audit views never become replay authority?
- What is the smallest deterministic obligation vocabulary that covers common
  revise/adapt turns without pretending to be universal semantic validation?
- Should the legacy endpoint be wrapped immediately or retired after one
  compatibility release?
- Which historical persisted V1 turns require read-only preview support?
- Which research cache TTLs should vary by evidence tier?

## Constraints

- Overall difficulty: 5/5.
- Profile: `partnered-5`; robustness: `full`; depth: `high`; vendor: `codex`.
- Preserve current graph identity, stale-baseline guards, batch rollback, and
  explicit Apply/Reject behavior.
- Do not weaken strict validation to improve completion rate.
- Avoid duplicating Python and JavaScript delta semantics; use generated schemas
  or explicit parity fixtures.
- Core tests must run without GPU or model execution.
- Treat existing V2 schema work as the baseline to complete, not rewrite.

## Done Criteria

- A reproduced `queue_validate_ok=false` response remains
  `queue_allowed=false` at every public boundary.
- Every new applyable turn includes a normalized cumulative V2 delta.
- The server asserts replay equality between submit graph plus delta and the
  persisted candidate.
- Malformed or missing delta evidence cannot widen into whole-graph Apply.
- Non-HotShot required planning produces `required_unsupported`, not a passing
  absent plan.
- Edit-plus-clarify is non-applyable when any required obligation is incomplete.
- Duplicate requests execute provider/edit work at most once.
- Reply-model failure still returns the durable candidate and authoritative
  proof state.
- Provisional or non-runtime-validated schemas cannot authorize Queue.
- Stale local precedent cannot displace stronger current evidence without a
  recorded deterministic reason.
- Both public product routes share the same eligibility contract.
- Python contract, artifact replay, browser response, and composed route tests
  pass.
- A durable handoff records schema/version, eligibility ownership, proof states,
  artifact hashes, retained bridges, deletion criteria, and exact test commands.

## Primary Touchpoints

- `vibecomfy/executor/contracts.py`
- `vibecomfy/executor/core.py`
- `vibecomfy/executor/agent_backend.py`
- `vibecomfy/executor/research.py`
- `vibecomfy/executor/execution_plan_builder.py`
- `vibecomfy/comfy_nodes/agent/edit_response_contract.py`
- `vibecomfy/comfy_nodes/agent/executor_response.py`
- `vibecomfy/comfy_nodes/agent/executor_durable.py`
- `vibecomfy/comfy_nodes/agent/execution_plan.py`
- `vibecomfy/comfy_nodes/agent/edit_research.py`
- `vibecomfy/comfy_nodes/agent/edit_batch_loop_apply.py`
- `vibecomfy/comfy_nodes/agent/edit_batch_loop_finish.py`
- `vibecomfy/comfy_nodes/agent/session.py`
- `vibecomfy/porting/edit/schemas/v2/`
- `vibecomfy/porting/edit/session.py`
- Contract, artifact-replay, characterization, and browser lifecycle tests.

## Anti-Scope

- Do not hide contradictions by renaming fields.
- Do not add another eligibility mirror.
- Do not treat candidate presence as proof.
- Do not broaden schema confidence to keep Queue enabled.
- Do not undertake unrelated module cleanup.
