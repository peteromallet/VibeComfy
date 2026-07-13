---
type: brief
slug: sprint-2
title: Transactional Apply and Topology-Truthful Reorganisation
epic: agent-edit-verifiable-transaction-spine
created_at: '2026-07-13T21:26:07.861389+00:00'
---

# Sprint 2: Transactional Apply and Topology-Truthful Reorganisation

## Outcome

Preview and Apply become one recoverable transaction, and reorganisation
produces layouts whose stage order, grouping, and geometry are constrained by
effective graph topology rather than blunt global role or width buckets.

Sprint 2 depends on the merged Sprint 1 handoff. It must consume the canonical
delta, eligibility, proof, and artifact contracts rather than creating a second
transaction model.

## Starting Evidence

- `../research/end-state-and-pipeline-audit.md`
- `../research/routing-research-pipeline-audit.md`
- Sprint 1's durable handoff and merged implementation.
- Existing `.megaplan/initiatives/reorganise-comfy-workflow/` work and current
  reorganisation compiler tests are baseline.

## In Scope

- Create an immutable, content-addressed mutation plan consumed identically by
  preview, acceptance, browser Apply, and verification.
- Implement lifecycle states `submitted`, `candidate_ready`, `review_bound`,
  `apply_prepared`, `canvas_verified`, `finalized`, plus explicit recoverable
  failure and rollback states.
- Add scoped compare-and-swap prepare, browser mutation, serialization
  comparison, finalize, rollback, and reload reconciliation.
- Add append-only lifecycle events, monotonic generations, idempotency leases,
  cancellation/supersession guards, and prepared/finalized receipts.
- Normalize reorganisation evidence for endpoint names, declared/live/link
  types, physical versus effective topology, muted/bypassed modes, Set/Get and
  virtual wires, reroute contraction, subgraph boundary ports, and stable scoped
  identities.
- Separate intrinsic node operation from contextual pipeline stage.
- Derive repeated stages, branches, joins, loops, shared bridges, and
  disconnected components from active topology.
- Replace global role walls and aggregate backward-edge tolerances with a
  topology-constrained stage DAG.
- Preserve pins and explicit placement constraints in all workflow sizes.
- Implement band-aware column packing: columns stay straight; a complete column
  may dovetail only when its full vertical footprint fits; a wide node reserves
  width only in intersecting vertical bands; placement uses actual rectangles
  and interval occupancy rather than one maximum width for an entire row.
- Make group geometry and group preview part of the exact candidate.
- Align the minimum horizontal group gutter with the configured vertical group
  gutter unless a preset explicitly overrides it.
- Add deterministic gates for active backward edges, unintended overlap, pin
  violations, structural hash changes, and fixed-point idempotence.
- Add browser, crash-injection, and representative workflow-corpus tests.

## Out of Scope

- A general-purpose graph-drawing system for arbitrary cyclic graphs.
- Semantic understanding of every custom node class.
- Automatic graph rewiring or Set/Get conversion.
- Broad visual redesign of the agent panel.
- Runtime generation or GPU validation.
- Perfect global crossing minimization; correctness and stable local packing
  come first.

## Locked Decisions

- Active topology is hard; roles, titles, groups, and existing geometry are soft
  preferences.
- Physical and effective runtime topology remain separately inspectable.
- Exact coordinates are compiler-owned.
- A node's operation and contextual stage are distinct fields.
- Repeated stages are first-class; there is no single global pre-sampler or
  post-process bucket.
- A single active inter-stage contradiction blocks the candidate; aggregate
  quality thresholds cannot waive it.
- Dovetail packing moves a complete straight column as a unit, never individual
  nodes into a jagged pseudo-column.
- Whole-graph and scoped Apply share post-apply serialization verification.
- The server baseline advances only after the browser verifies the exact
  mutation plan.

## Open Questions for Planning

- Should interval/sweep-line packing extend the current compiler or be isolated
  as a deterministic packing module?
- How should explicit loop feedback be represented so valid cycles do not look
  like stage-order violations?
- How do bypass semantics differ among relevant custom-node families?
- Should subgraph child layout be committed in one nested mutation plan or as
  parent/child components sharing one root hash?
- What durable storage owns prepared transactions and lease recovery?
- Which canonical projection should browser/server equality use while ignoring
  harmless serialization ordering?

## Constraints

- Overall difficulty: 5/5.
- Profile: `partnered-5`; robustness: `thorough`; depth: `high`; vendor: `codex`.
- Layout-only candidates preserve runtime behavior and structural graph hash.
- Compiler output is deterministic across machines and reaches an exact snapped
  fixed point.
- Unfamiliar nodes degrade conservatively through typed topology and explicit
  uncertainty.
- Large workflows receive the same correctness gates as small ones.
- Core graph and browser tests run without GPU/model files.
- Sprint 1 contracts are dependencies and cannot be bypassed.

## Done Criteria

- The previewed mutation-plan hash equals the hash consumed by browser Apply.
- Canvas mutation during review invalidates eligibility.
- Failure injection at every prepare/apply/serialize/finalize boundary leaves
  either the exact baseline or a deterministic recoverable prepared transaction.
- Reload reconciles prepared and finalized receipts without double application.
- Duplicate Apply is idempotent; superseded or cancelled turns cannot publish or
  finalize.
- Resize/preprocessor nodes are staged by lineage before the sampler they feed,
  not by lexical operation name.
- Samplers are not placed inside prompt/conditioning groups when active topology
  establishes a later stage.
- Decode/output stages appear after their producing sampler.
- Multi-pass workflows produce repeated Preparation/Sampling/Decode instances.
- Muted sampler alternatives do not determine active ordering.
- Disconnected workflows remain separate islands.
- Pinned nodes are preserved or yield an explicit conflict.
- Uneven-width fixtures demonstrate band-aware dovetailing while each column
  remains straight.
- Group boxes render in preview and match the applied result.
- Horizontal and vertical minimum gutters meet the configured contract.
- Reorganising the result again produces identical snapped positions, groups,
  colors, sizes, and flags.
- Browser tests prove Preview, Apply, Reject, drift invalidation, rollback,
  reload recovery, and group parity.

## Primary Touchpoints

- `vibecomfy/comfy_nodes/web/agent_edit_lifecycle.js`
- `vibecomfy/comfy_nodes/web/agent_lifecycle_commit.js`
- `vibecomfy/comfy_nodes/web/vibecomfy_roundtrip.js`
- `vibecomfy/comfy_nodes/web/preview_diff_core.js`
- `vibecomfy/comfy_nodes/web/panel_overlay.js`
- `vibecomfy/comfy_nodes/agent/session.py`
- `vibecomfy/comfy_nodes/agent/reorganise.py`
- `vibecomfy/porting/reorganise/graph_facts.py`
- `vibecomfy/porting/reorganise/classify.py`
- `vibecomfy/porting/reorganise/compile.py`
- `vibecomfy/porting/reorganise/validate.py`
- `vibecomfy/porting/reorganise/assess.py`
- `vibecomfy/porting/reorganise/orchestrate.py`
- Reorganisation facts/classification/compiler/golden tests and browser
  lifecycle/preview/end-to-end tests.

## Anti-Scope

- Do not weaken topology gates for visual compactness.
- Do not restore title-derived wall ordering for large graphs.
- Do not solve whitespace with per-node masonry that destroys straight columns.
- Do not special-case only the reported resize node or sampler fixture.
- Do not report server acceptance before browser verification.
- Do not let preview use an approximate or separately reconstructed layout.
