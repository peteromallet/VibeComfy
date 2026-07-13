---
type: anchor
anchor_type: north_star
slug: agent-edit-verifiable-transaction-spine
title: 'North Star: Agent Edit Verifiable Transaction Spine'
created_at: '2026-07-13T21:26:07.860595+00:00'
---

# North Star: Agent Edit Verifiable Transaction Spine

## End State

VibeComfy agent-edit is a verifiable graph editor. Models may propose incorrect
or incomplete changes, but the system cannot turn those mistakes into
authorized mutations.

Every applyable turn follows one auditable path:

```text
immutable submit graph
  + authorized intent and obligations
  + cumulative normalized V2 delta
  = immutable candidate and mutation-plan hash
  -> exact preview
  -> prepared browser apply
  -> canvas serialization and verification
  -> durable finalize or rollback
```

Reorganisation uses the same substrate. Typed active topology is authoritative;
semantic labels and existing geometry are preferences. Multi-pass stages,
branches, joins, inactive paths, disconnected islands, pinned nodes, and
irregular node widths are represented truthfully.

## Non-Negotiables

- `candidate == apply(immutable_submit_graph, cumulative_typed_delta)`.
- Every new applyable turn is explicitly V2; malformed or missing delta evidence
  fails closed.
- Durable response fields, not narration or candidate presence, own canvas and
  queue authority.
- The preview mutation-plan hash equals the applied mutation-plan hash.
- Queue eligibility can never be broader than the durable queue proof.
- Transformation safety, graph validity, task satisfaction, and runtime
  readiness independently report `pass`, `fail`, `not_run`, or `unknown`.
- Required unsupported work blocks applyability; nullable plan absence is never
  interpreted as success.
- Live verified schemas outrank installed snapshots, which outrank content-hashed
  workflow observations. Provisional schemas cannot independently authorize
  Queue.
- One end-to-end idempotency key covers routing, research, provider execution,
  editing, reply, and commit.
- No server commit occurs before browser serialization verifies the exact
  candidate.
- Active topology is a hard reorganisation constraint at every workflow size.
- Layout-only changes preserve the structural graph hash.
- Reorganisation is deterministic and reaches an exact snapped fixed point.
- Pinned nodes and valid explicit placement constraints are honored or produce a
  precise conflict.
- Every Apply decision and recovery action is reconstructible from durable
  artifacts.

## Explicit Non-Goals

- Do not redesign the whole agent panel.
- Do not replace the Python batch-edit DSL.
- Do not build a universal semantic oracle for arbitrary natural language.
- Do not create a general-purpose graph-drawing engine for arbitrary cyclic
  graphs.
- Do not rewire workflows merely to make their layout prettier.
- Do not require GPU or model execution for the core correctness suite.
- Do not repeat work already landed by the canonical-delta or reorganisation
  initiatives; use it as the migration baseline.

## Allowed Temporary Bridges

- Historical V1 turn artifacts may remain readable through an isolated,
  read-only adapter with telemetry, explicit deletion criteria, and no authority
  over new applyable turns.
- The legacy direct-edit route may temporarily wrap the canonical contract, but
  it may not reconstruct eligibility or persist an alternative response shape.
- Unknown custom nodes may use provisional evidence for drafting only; Queue
  remains unavailable until runtime evidence satisfies the canonical proof.

Every bridge must be named in the Sprint 1 handoff with an owner, observable use
count, and deletion condition.

## Drift Signals

- A serializer reconstructs eligibility from route or candidate presence.
- An applyable product path falls back to whole-graph V1.
- Preview or Apply independently reconstructs edit meaning.
- Narration failure hides or invalidates durable successful work.
- Workflow-observed provisional schemas shadow live runtime evidence.
- A required plan is represented as `None` and treated as passing.
- A layout mode replaces dependency order with title or role order.
- Large graphs receive weaker topology, pin, overlap, or correctness gates.
- One wide node reserves horizontal space across unrelated vertical bands when
  a complete straight column could fit safely.
- Tests prove components but not the shipped browser-to-server composition.
