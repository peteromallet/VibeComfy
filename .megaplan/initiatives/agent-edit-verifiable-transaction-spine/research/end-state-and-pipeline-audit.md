# VibeComfy Agent-Edit End State and Pipeline Audit

Status: architecture analysis
Date: 2026-07-13
Scope: ComfyUI agent-edit, including deterministic workflow reorganisation

Companion audit: [Routing, Research, and Execution Handoff Audit](./routing-research-pipeline-audit.md)

## Executive intent

VibeComfy agent-edit should become a trustworthy graph transformation system
with an AI-assisted planning surface, not an AI system whose narrative is
treated as proof that a graph edit is correct.

The end state is a pipeline in which evidence is normalized with provenance,
intent is made explicit, proposed changes are represented canonically,
deterministic validators prove the relevant safety and task invariants, preview
shows the exact candidate, and Apply is an atomic verified commit. Models may
suggest meaning and edits; deterministic contracts decide what is permitted and
what actually happened.

The same principle applies to workflow reorganisation: semantic labels may
influence presentation, but active graph topology must constrain the result.

## The end state in one line

```text
capture and reconcile evidence
  -> classify intent and establish proof obligations
  -> research with provenance where necessary
  -> plan against a typed canonical graph
  -> execute bounded transformations
  -> validate structure, semantics, and task satisfaction
  -> preview the exact candidate
  -> atomically apply and verify
  -> persist a replayable evidence trail
```

## Current state compared with the target

| Current tendency | Target state |
| --- | --- |
| Multiple graph and schema representations are trusted opportunistically | One normalized evidence graph records values, endpoint types, schema facts, provenance, conflicts, and freshness |
| Class names and titles frequently stand in for semantics | Typed ports, active reachability, schema categories, and execution position establish context; names are fallback evidence |
| A node is assigned one global role | Intrinsic operation and contextual stage are separate, and repeated stage instances are supported |
| Large layouts may substitute semantic wall order for dependency order | Semantic rank is a soft preference projected onto hard topology constraints |
| Disabled and bypassed nodes remain active topology anchors | Physical topology and effective runtime topology are modeled separately |
| Candidate quality is often expressed through aggregate warning thresholds | Local correctness invariants block individually misleading candidates |
| Server acceptance and browser canvas application are separate commits | Apply is a two-phase transaction with post-apply serialization and rollback |
| Preview is a visual approximation over a frozen baseline | Preview is the exact candidate, bound to the current baseline, and invalidated on drift |
| Diagnostic artifacts differ by route and often omit decision traces | Every route persists a discoverable evidence manifest, decision traces, gates, and replay inputs |
| Tests often prove structural validity or current-output stability | Oracles prove task satisfaction, semantic correctness, lifecycle parity, and recovery behavior |

## Part I: workflow reorganisation end state

### Desired user experience

After selecting **Reorganise**, the user should be able to trust the structural
shape of the candidate and spend review time only on aesthetic preferences such
as spacing, compactness, grouping, color, or whether related controls should be
stacked.

The user should not need to check whether preprocessing was placed after its
sampler, whether independent pipelines were interleaved, or whether the reviewed
candidate differs from the applied result.

### Structural guarantees

1. **Active dependency flow is truthful.** Every edge between stages in the
   condensed execution DAG moves forward, apart from explicitly identified loop
   feedback.
2. **Repeated stages are representable.** A workflow may contain Sampling 1,
   Decode/Bridge, Preparation 2, Sampling 2, and Final Decode without collapsing
   those nodes into global role buckets.
3. **Branches remain branches.** Fork regions, sibling lanes, reconvergence, and
   joins are derived from topology. A join appears after all of its branches.
4. **Disconnected pipelines remain separate.** Weakly connected components are
   packed as independent islands unless an explicit shared anchor relates them.
5. **User constraints remain authoritative.** Pinned nodes and valid explicit
   placement constraints are respected in every workflow size, or the candidate
   fails with a precise conflict.
6. **Inactive topology is visible but not authoritative.** Muted and bypassed
   nodes are preserved visually while effective execution stages are derived
   from runtime behavior.
7. **Geometry is safe.** Primary nodes and unrelated groups do not overlap,
   minimum gutters are enforced, and helper furniture stays near its resolved
   edge corridor.
8. **The layout is a fixed point.** Reorganising the organised result produces
   the same snapped positions, sizes, groups, colors, and flags.
9. **Preview equals Apply.** The serialized canvas after Apply matches the exact
   layout candidate reviewed by the user.

### Contextual classification

A node's intrinsic operation must be modeled separately from its pipeline
position. For example, an image resize may be:

- initial media preparation;
- ControlNet, IPAdapter, or vision-reference preparation;
- preparation between two sampling passes; or
- final output postprocessing.

The operation name alone cannot identify the stage. The classifier must inspect
typed lineage into sampler inputs, ancestry from sampler or decode outputs,
branch membership, and cross-stage use. When a node spans stages, it should be
represented as shared or as a bridge rather than forced into a misleading role.

### Reorganisation gaps found in the current implementation

The audit identified these recurring error families:

1. Lexical classification collisions such as `VAEEncode` becoming a Loader,
   `ConditioningCombine` becoming an Output, or a resource loader becoming a
   sampler because a downstream class name contains `sampler`.
2. Endpoint names, endpoint-declared types, live schema types, and link types are
   not reconciled into one evidence record.
3. Disabled and bypassed node modes do not affect effective topology.
4. Subgraph container ports are not connected to definition boundary ports in a
   hierarchical execution graph.
5. Set/Get, reroute, and virtual-wire ambiguity can silently remove or invent
   effective reachability.
6. Large-workflow mode replaces dependency ranks with title-derived wall ranks
   and collapses disconnected islands.
7. The deterministic plan creates one section per role rather than repeated
   stage instances.
8. Aggregate backward-edge and crossing thresholds allow a single important
   sequencing contradiction to pass.
9. Large mode ignores pinned nodes and softens several geometry failures.
10. Deterministic turns do not persist per-node classification and placement
    traces equivalent to the model-loop transcript.

## Part II: overall agent-edit pipeline end state

### Foundational diagnosis from the independent pipeline review

An independent read-only audit using GPT-5.6 Sol at `xhigh` reasoning reached a
more specific version of the same conclusion: the repository contains many of
the right safety primitives, but the shipped product path does not compose them
into one authoritative transaction.

The most important contradiction is that the active `batch_repl` path derives
typed edit operations internally, but commonly publishes a whole-graph V1
candidate instead of a cumulative top-level delta. Protocol selection is then
inferred from whether that top-level delta exists. As a result, the strongest
scoped conflict detection, untouched-field preservation, deterministic replay,
and browser Apply machinery are present but are often bypassed by real product
turns.

This changes the priority of the work. Improving classifiers, prompts, or
individual validators remains useful, but it cannot establish end-to-end trust
until every applyable product turn has one canonical mutation authority:

```text
candidate = apply(immutable_submit_graph, cumulative_typed_delta)
```

Preview, validation, acceptance, application, recovery, and audit must all
consume that same delta-derived, content-addressed mutation plan. No subsystem
should independently reconstruct what the edit means.

The review ranked the remaining systemic risks as follows:

1. **Preview, acceptance, and canvas application are different executions.** A
   failed or malformed scoped preview can fall back to a whole-graph path, while
   server acceptance may occur before local canvas mutation succeeds.
2. **Authoritative replay evidence and redacted audit evidence are conflated.**
   Immutable source bytes need a separate content-hashed store; redaction belongs
   only in derived human-readable audit views.
3. **Turn durability is not yet a complete transaction protocol.** Allocation,
   supersession, response publication, idempotency, and crash recovery need a
   journal with generations, leases, and prepared/finalized receipts.
4. **Identity is not fully anchored to the live editing substrate.** Stable,
   scope-qualified identities must be bootstrapped on the canvas and preserved
   in the model projection; mutable numeric IDs must not be a silent fallback.
5. **Intent, provider routing, and execution policy are not closed independent
   contracts.** Unknown or stale classification must never become applyable, and
   readiness must describe the same provider path that execution will use.
6. **Research and schema evidence can be promoted beyond its authority.** Live
   schema generations should outrank installed snapshots, which should outrank
   content-hashed workflow observations and research prose.
7. **Planning can fail open on partial intent.** Every user requirement needs an
   obligation state such as `not_required`, `required_supported`,
   `required_unsupported`, or `satisfied`; unsupported required work blocks
   completion.
8. **Validation labels overstate what was proven.** Apply safety, queue validity,
   task satisfaction, and runtime readiness are separate four-state proofs:
   `pass`, `fail`, `not_run`, or `unknown`.
9. **Cancellation and status are partly presentational.** Aborting a browser
   request does not necessarily cancel backend work, and status should be derived
   from immutable lifecycle events rather than optimistic response fields.
10. **Tests prove components more often than shipped composition.** CI needs real
    browser turns that assert protocol selection, delta replay equality,
    untouched-byte preservation, scoped conflict behavior, crash recovery, and
    reload reconciliation together.

### 1. Evidence integrity

The browser snapshot, UI link records, serialized node endpoints, live
`object_info`, registry or provisional schemas, API graph, sidecars, session
baseline, and user-visible canvas state are different evidence sources. They
must not be flattened without provenance.

The target is a normalized evidence ledger in which every material fact carries:

- source and timestamp or revision;
- scope-qualified stable identity;
- confidence or authority;
- schema and endpoint interpretations;
- conflicts and the rule used to resolve them;
- freshness binding to the structural graph hash.

Unresolved identities, dangling links, ambiguous helper channels, duplicate IDs,
and incompatible endpoint evidence must become diagnostics rather than silently
disappearing.

### 2. Intent and route contracts

Intent classification should produce explicit proof obligations rather than only
a route label. Examples include:

- which user-stated outcomes must be true;
- which graph regions may change;
- which runtime behaviors must remain invariant;
- whether research or schema hydration is required;
- whether the request is layout-only, functional, operational, or explanatory;
- what evidence is sufficient to present a candidate.

Routing confidence must not silently broaden authority. Ambiguous intent should
either be resolved from the graph and conversation or result in a focused
clarification before mutation.

### 3. Research and schema provenance

Research should fill named evidence gaps, not become a generic prelude to every
edit. Every precedent, node schema, model reference, or registry result should
record why it was selected, which claim it supports, its compatibility limits,
and whether it is authoritative, provisional, or merely suggestive.

A proposed edit must not become more trusted merely because a precedent exists.
Compatibility with the current graph, installed environment, and live node
schema remains a separate deterministic obligation.

### 4. Planning and execution

The model-facing plan should compile into a canonical, bounded transformation
language. Every operation should have:

- stable targets;
- expected preconditions;
- allowed fields and scopes;
- typed inputs and outputs;
- deterministic diagnostics;
- an inverse or recovery strategy where practical.

Models should not need to infer undocumented mutation syntax from teaching
errors. Failed operations should return exact available choices, affected refs,
and the smallest repairable unit without accidentally rewarding repeated blind
guessing.

### 5. Validation and task satisfaction

Validation has three distinct responsibilities:

1. **Transformation safety:** no unauthorized or malformed mutation occurred.
2. **Graph validity:** topology, schemas, required inputs, models, and runtime
   constraints remain valid.
3. **Task satisfaction:** the requested outcome is demonstrably present and
   contradictory outcomes are absent.

Passing one layer must never be presented as proof of another. Candidate
eligibility should be derived from named proof obligations and explicit waivers,
not a broad collection of mostly advisory metrics.

### 6. Candidate lifecycle and durability

The session baseline, candidate, browser canvas, preview cache, and acceptance
record form one state machine. The target lifecycle is:

```text
submitted -> evaluated -> candidate_ready -> review_bound
          -> apply_prepared -> canvas_verified -> committed
```

Any graph mutation during review invalidates or explicitly rebases the candidate.
Apply should not advance the authoritative server baseline until the browser has
serialized and verified the candidate. Failures must restore both server and
canvas state or leave a clearly recoverable prepared transaction.

### 7. Preview and UX trust

Preview must answer three questions directly:

1. What will change?
2. Why is each change proposed?
3. What has been proven, warned about, or left uncertain?

For whole-graph or layout candidates, preview should frame the relevant old and
new bounds, avoid double-rendering unchanged furniture, and show the exact target
positions and groups. Apply eligibility must react immediately to baseline drift.

### 8. Observability and replay

Each turn should persist an artifact manifest rather than promise fixed files
that only some routes generate. A complete trace should make it possible to
reconstruct:

- captured evidence and graph hashes;
- intent and proof obligations;
- research queries and provenance;
- model requests and responses when a model was used;
- deterministic classifier, planner, and placement decisions;
- attempted transformations and engine diagnostics;
- every gate and waiver;
- preview and applied projections;
- recovery or rollback activity.

The user-facing report should link to the smallest useful evidence rather than
requiring source-code archaeology.

## Target architecture

The target architecture is one transaction spine with six separable layers:

1. **Evidence ledger** — normalized, provenance-bearing, revision-bound graph,
   schema, environment, and session facts.
2. **Intent contract** — authorized scope, desired outcome, invariants, and proof
   obligations.
3. **Planning layer** — AI or deterministic proposal expressed in a canonical
   transformation or layout plan.
4. **Execution engine** — bounded mutations with preconditions and complete
   diagnostics.
5. **Proof and candidate layer** — structural, semantic, task, and presentation
   validators produce an immutable review candidate.
6. **Transactional UI commit** — exact preview, prepared Apply, canvas
   serialization, verification, commit, and rollback.

Its concrete flow is:

```text
live canvas snapshot
  -> identity bootstrap
  -> immutable turn-input manifest
  -> policy-validated intent and obligation ledger
  -> provenance-bound research/schema bundle
  -> cumulative typed delta
  -> deterministic apply and proof ladder
  -> immutable candidate and mutation-plan hash
  -> scoped compare-and-swap prepare
  -> identical browser application and verification
  -> durable finalize receipt
```

### Evidence precedence

Evidence precedence should be explicit and domain-specific. A useful default is:

```text
live verified schema and endpoint agreement
  > canonical graph and effective topology
  > explicit user constraints and valid plan ownership
  > installed-node and environment facts
  > classifier inference
  > existing titles and groups
  > original geometry
  > lexical fallback
```

Explicit user intent controls authorization and desired outcome, but it does not
override graph validity or permit impossible slot types. Existing UI furniture
may guide presentation but cannot contradict execution ordering.

### Hard invariants

- Candidate equals deterministic application of the cumulative delta to the
  immutable submit bytes.
- Every graph address resolves exactly once by scope-qualified stable identity.
- Every new applyable product turn uses the canonical delta protocol; it cannot
  silently downgrade to whole-graph V1.
- Preview-plan hash equals applied-plan hash.
- Authoritative artifacts are content-addressed and digest-verified on every
  read; redacted audit views are never replay authority.
- No mutation outside the authorized scope.
- No unexplained loss, invention, or retargeting of graph edges.
- No accepted candidate whose required evidence is stale or contradictory.
- No active inter-stage edge moves backward, except declared feedback.
- No primary node overlap or unintended group overlap.
- No candidate whose after-assessment is worse than its baseline on a required
  quality dimension without an explicit reviewable waiver.
- No server commit before post-apply browser verification.
- Preview projection equals applied projection.
- Reject restores the exact baseline.
- Replaying the same accepted request is idempotent.
- Every Apply decision can be reconstructed from durable evidence.
- No completion may publish after supersession or cancellation.
- Every eligibility bit references a current proof artifact and distinguishes
  `pass`, `fail`, `not_run`, and `unknown`.

## Implementation sequence and exit criteria

### Phase 0: collapse onto one mutation protocol

Publish the ordered operations landed by `batch_repl` as one canonical,
cumulative top-level delta. Derive candidate, preview, Apply, and acceptance
evidence from that delta. Disable implicit V1 and whole-graph fallback for all
new applyable turns.

Exit criteria:

- every new applyable product turn is explicitly V2;
- `candidate == apply(submit, delta)` is checked server-side;
- browser preview and Apply consume the same mutation-plan hash;
- malformed or missing delta evidence fails closed instead of widening scope.

### Phase 1: normalized evidence, identity, and integrity diagnostics

Build one evidence ledger for UI endpoints, link records, schemas, node modes,
subgraph boundaries, helpers, virtual wires, sidecars, and baseline revisions.
Separate immutable replay artifacts from redacted audit projections, and
bootstrap scope-qualified stable identities onto the live canvas.

Exit criteria:

- every edge resolves both endpoints or emits a diagnostic;
- physical and effective runtime topology are both available;
- schema and endpoint conflicts are visible;
- helper contraction preserves non-helper reachability or fails closed;
- scoped identities and sidecars are revision-bound;
- every authoritative artifact is atomically written, manifested, hashed, and
  verified before use.

### Phase 2: contextual stage, closed routing, and obligation modeling

Separate intrinsic operation from contextual stage, identify actual execution
anchors, derive repeated stages, branch regions, joins, loops, and disconnected
components, and attach explicit proof obligations to routes.

Exit criteria:

- multi-pass workflows produce repeated ordered stages;
- muted alternatives do not affect active stage counts;
- ambiguous cross-stage nodes become shared or diagnostic;
- every active inter-stage edge respects the stage DAG;
- unknown intent is non-applyable, and intent route, provider route, and
  execution policy are recorded independently;
- every required user outcome has a deterministically checkable obligation.

### Phase 3: constrained layout and canonical transformations

Project semantic preferences onto topology and user constraints. Make mutation
operations canonical, typed, preconditioned, and fully diagnosable.

Exit criteria:

- topology remains a hard constraint in every graph size;
- pinned and scoped constraints are respected;
- zero unintended overlaps;
- exact fixed-point layout idempotence;
- operations cannot modify fields outside their declared contract.

### Phase 4: proof-driven candidate gates

Replace blanket soft gates with named obligations and narrowly scoped waivers.
Separate safety, validity, task satisfaction, and aesthetic assessment.

Exit criteria:

- an Apply-eligible candidate cannot simultaneously have a failing
  after-assessment;
- each waived issue is explicit and reviewable;
- large graphs meet the same correctness invariants as small graphs;
- semantic and task oracles cover representative custom-node workflows;
- safety, queue validity, task satisfaction, and runtime readiness are reported
  independently with honest four-state proof results.

### Phase 5: journaled transactional preview and Apply

Bind preview to the live baseline, prepare server acceptance, apply to canvas,
serialize and compare, then commit or roll back. Use append-only lifecycle
events, monotonic generations, idempotency leases, and
`prepared -> canvas_applied -> finalized` receipts so crashes and reloads can
be reconciled deterministically.

Exit criteria:

- canvas edits during review immediately invalidate or rebase eligibility;
- whole-graph and scoped Apply share post-apply verification;
- injected failures at every Apply step restore a coherent state;
- preview and applied canonical projections are equal;
- duplicate submissions produce at most one provider execution;
- superseded or cancelled turns cannot publish candidates;
- crash injection at every publication boundary is recoverable by replay.

### Phase 6: evidence-grade observability and corpus testing

Persist route-appropriate traces and expand tests from structural fixtures to
real lifecycle and semantic oracles.

Exit criteria:

- every turn publishes an artifact manifest and gate trace;
- deterministic routes are as diagnosable as model-backed routes;
- large, branched, multi-stage, scoped, bypassed, stale, and conflicting-schema
  fixtures are covered;
- browser replay proves preview, Apply, Reject, rebase, and recovery behavior.

## Do not regress

The following existing strengths should be preserved:

- layout-only structural no-op checks and manifest-backed preview/apply;
- durable turn allocation, graph hashes, idempotency records, and stale-baseline
  defenses;
- canonical node identities and explicit scope handling;
- bounded edit execution with concrete diagnostics and available choices;
- reviewable candidate lifecycle with explicit Apply and Reject;
- separation between research, planning, execution, and validation contracts;
- preservation of the pristine user graph until a candidate is accepted;
- deterministic offline reorganisation support;
- browser and server test harnesses capable of exercising lifecycle behavior;
- failure artifacts that already retain raw model requests and responses for
  model-backed turns.

## Definition of done

The project is complete when a user can treat agent-edit as a verifiable editor:

- the model may be wrong without the system becoming wrong;
- incomplete evidence produces uncertainty or a blocked candidate, not a
  confident mutation;
- every accepted edit demonstrably satisfies its authorized task contract;
- the reviewed candidate is exactly what appears on the canvas;
- failures are atomic, recoverable, and diagnosable;
- unfamiliar custom nodes degrade conservatively through typed topology instead
  of collapsing into arbitrary name-based categories.

At that point, model quality primarily affects how quickly VibeComfy finds a good
edit. It no longer determines whether the editor can preserve truth.
