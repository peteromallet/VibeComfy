# Agent Edit: Complete Robustness Architecture

## Execution model routing

- Easy delegated work: DeepSeek Pro.
- Medium delegated work: GPT-5.6 Luna.
- Hard delegated work: Claude Code routed through GLM 5.2 (`claude:glm-5.2`).
- Exceptional escalation only: GPT-5.6 Sol.

This routing applies to execution of the plan; it does not change the product
architecture or acceptance criteria below.

## Purpose

This document defines the work required to make VibeComfy Agent Edit robust
across graph edits, layout reorganisation, workflow-tab switching, native
ComfyUI serialization, verification, finalization, rollback, and recovery.

It follows three related production incidents:

1. A `Displays / Labels` group was placed far away from the main workflow.
2. Agent panel state leaked into a newly opened workflow tab.
3. A valid `vibecomfy.exec` code-node edit appeared to Apply, then disappeared
   because post-Apply verification rejected it and rolled it back.

The immediate incident fixes repair important shared invariants. They do not,
by themselves, complete the intended architectural separation. The objective
of this plan is to eliminate the conditions that allow new variations of these
failures to recur.

## Incident lessons

### Detached `Displays / Labels` group

The compiler had already assigned the section a stable `displays` bucket.
Later placement logic inspected its human-readable title, matched the word
`Labels`, and reclassified it into a distant footer lane.

The deeper fault was competing authority:

- Stable classification said one thing.
- A later display-text heuristic was allowed to reinterpret it.
- No enforced invariant stated that stable identity outranks presentation text.

### Workflow-tab state leakage

VibeComfy reused a singleton panel across workflow tabs. A scope switch changed
some scope fields but did not atomically replace the complete scope-local state.
A new workflow could therefore temporarily inherit the previous workflow's
phase, session, turn, transcript, history, progress, and candidate state.

In-flight responses from the departed workflow also retained authority to
commit against the shared panel.

The deeper fault was an incomplete lifecycle boundary:

- Workflow identity was not bound to the complete UI state aggregate.
- Scope activation did not revoke prior asynchronous authority.
- Fresh scope initialization and exact-scope restoration were not distinct,
  atomic operations.

### Dynamic code-node Apply rollback

The agent produced a valid edit. The engine accepted the new
`vibecomfy.exec` node and its links. During Apply, ComfyUI rebuilt the node's
dynamic `io` widget into a different serialized representation. The backend
correctly excluded this derived UI metadata from structural identity, while a
separate browser implementation still hashed it.

The browser therefore interpreted a representation-only normalization as an
executable graph mismatch and rolled back the valid edit.

The deeper fault was duplicated semantic authority:

- Browser and backend independently defined structural equivalence.
- Native ComfyUI normalization was not isolated behind an adapter.
- Derived UI metadata leaked into execution-semantic verification.

## Shared foundational problem

The earlier architectural epics created valuable transaction machinery and
extracted several frontend modules. However, the highest-risk decisions still
had multiple or ambiguous owners:

- graph identity;
- structural and layout projection;
- native LiteGraph normalization;
- graph mutation;
- Apply and rollback verification;
- workflow scope ownership;
- asynchronous commit authority;
- transaction lifecycle coordination.

The resulting architecture could have a correct canonical decision in one
layer and then reinterpret it in another.

The core robustness rule is:

> Every consequential identity, projection, mutation, verification, and
> lifecycle decision must have exactly one authoritative owner.

## Target architecture

```text
Agent intent
  → canonical delta
  → workflow-scoped controller
  → native ComfyUI graph adapter
  → operation-specific verification
  → finalize or verified rollback
```

The supporting transaction flow is:

```text
canonical delta
  → declared projection contract
  → native graph adapter
  → one Apply/rollback verifier
  → durable transaction aggregate
  → real ComfyUI composition tests
```

## Required architectural work

### 1. Establish one native graph adapter

Create `intent_graph_adapter.js` as the only browser module permitted to:

- capture the live LiteGraph graph;
- normalize native ComfyUI serialization;
- apply canonical deltas;
- perform explicit whole-workflow replacement when a contract permits it;
- preserve stable node and group identity;
- produce structural and layout projections;
- construct inverse deltas or restoration plans;
- serialize the resulting live graph for verification.

Other modules, including `vibecomfy_roundtrip.js`, lifecycle reducers, panel
components, and transport code, must not inspect or mutate LiteGraph directly.

This adapter is the boundary between VibeComfy intent and ComfyUI's native,
extension-influenced representation.

### 2. Complete the projection registry

Every operation must declare what successful application means.

| Operation family | Verification contract |
| --- | --- |
| Prompt, widget, seed, or model changes | `structural_v1` |
| Node and link changes | `structural_v1` |
| Layout reorganisation | `layout_v1` plus structural no-op |
| Full workflow replacement | Explicit `workflow_v1` |
| Rollback | The same projection family used by the forward operation |

Each projection must define:

- included fields;
- excluded fields;
- default, missing, and null normalization;
- stable identity rules;
- ordering rules;
- native ComfyUI normalization;
- projection name and version;
- matching browser and Python fixtures;
- behavior for unsupported structures.

There must be no unqualified “canonical graph hash.” Every hash must identify
its projection purpose and version.

### 3. Make canonical deltas the sole mutation language

Preview, Apply, Undo, rollback, and recovery should execute the same canonical
operation vocabulary.

Each prepared transaction should contain:

```json
{
  "delta_contract": "delta_v1",
  "verification_projection": "structural_v1",
  "expected_precondition_hash": "...",
  "expected_postcondition_hash": "...",
  "inverse_delta": [],
  "rollback_projection": "structural_v1"
}
```

The precise schema may differ, but the transaction must explicitly carry:

- the forward operation;
- the applicable scope;
- its precondition;
- its postcondition;
- its inverse or restoration strategy;
- the verification projection and version.

Whole-graph loading must not remain an implicit parallel mutation path. If it
is required, it should be represented as a deliberate, versioned operation
with explicit verification and rollback semantics.

### 4. Introduce a workflow-scoped controller

Create `agent_edit_controller.js` and give every workflow its own state
aggregate:

```text
WorkflowEditContext
├── workflow ID
├── activation epoch
├── active session
├── lifecycle state
├── candidate transaction
├── draft and transcript
├── queue guard
├── undo/recovery context
└── in-flight operation ownership
```

The controller alone should coordinate:

- submit;
- prepare;
- Apply;
- verify;
- finalize;
- reject;
- rollback;
- Undo;
- rehydrate;
- workflow activation;
- workflow deactivation;
- cancellation and late-result rejection.

An asynchronous result may commit only when all of the following still match:

- workflow identity;
- activation epoch;
- operation identity;
- submit/apply epoch;
- session and candidate transaction identity.

`vibecomfy_roundtrip.js` should become bootstrap, event wiring, and view
composition rather than the transaction coordinator.

### 5. Make recovery exhaustive and actionable

Every post-prepare state must have a deterministic recovery path.

| Durable state | Required recovery |
| --- | --- |
| Prepared, canvas untouched | Resume Apply or cancel safely |
| Canvas mutated, not verified | Verify or rollback |
| Canvas verified, not finalized | Retry finalize or rollback |
| Finalize failed | Preserve evidence and offer retry or rollback |
| Rollback prepared | Complete rollback |
| Rollback failed | Show exact unresolved projection difference and retain recovery authority |
| Browser refreshed mid-transaction | Reconstruct state from durable receipts |
| Workflow switched mid-transaction | Revoke the old activation without corrupting either workflow |

A generic terminal `ERROR` with no safe next action is not an acceptable
post-prepare outcome.

### 6. Make stable identity mandatory

For nodes, groups, scopes, workflow tabs, sessions, turns, candidates, and
transactions:

- titles are labels, not identities;
- positions are never identities;
- array order is not identity unless explicitly declared by a contract;
- native-generated IDs are normalized at the adapter boundary;
- duplicate group titles are harmless;
- stable IDs survive Apply, serialize, refresh, rehydrate, and rollback;
- planner-only metadata is excluded from native verification unless explicitly
  part of a declared projection.

Stable classification and identity must always outrank later heuristics based
on presentation text.

### 7. Add enforceable ownership guardrails

Static architecture tests should reject future duplication.

- Only the projection registry defines graph projections.
- Only the native adapter reads or writes LiteGraph.
- Only the verifier compares transaction preconditions and postconditions.
- Only the workflow controller coordinates transaction lifecycle.
- Only the API module owns Agent Edit transport.
- No module contains a copied canonicalizer with a “must stay in sync”
  comment.
- `vibecomfy_roundtrip.js` cannot define hashing, graph mutation,
  verification, rollback, or transaction-state coordination.
- Stable identities cannot fall back to human titles.

Documentation is insufficient here. These constraints should fail CI when
violated.

### 8. Build a clean real-ComfyUI composition gate

Create a minimal, pinned ComfyUI installation for deterministic browser tests.
Keep a separate compatibility matrix for representative third-party node
packs.

For every transaction family, the composition gate should:

1. Load a real workflow through ComfyUI.
2. Submit or inject a candidate.
3. Prepare the transaction.
4. Apply through actual LiteGraph.
5. Serialize through actual ComfyUI.
6. Verify the declared projection.
7. Finalize.
8. Refresh and prove persistence.
9. Repeat with injected failures.
10. Verify rollback and recovery.

Required fixtures include:

- the `a66422e…` layout-normalization incident;
- the `eb45e…` dynamic-exec incident;
- the detached `Displays / Labels` placement incident;
- duplicate group titles;
- empty and structurally identical workflow tabs;
- workflow switching during every transaction phase;
- dynamic nodes that rebuild sockets or widgets;
- converted widgets;
- reroutes;
- missing custom nodes;
- unsupported nested scopes;
- refresh during prepared, verified, finalizing, and rollback states.

## Current foundation already implemented

The incident work provides a useful base:

- centralized browser graph projection;
- explicit versioned layout verification;
- stable group IDs for layout verification;
- native normalization of `vibecomfy.exec` dynamic `io`;
- rejection of unsupported nested-scope layouts;
- fresh workflow state on first activation;
- exact-scope snapshot restoration;
- monotonic workflow activation epochs;
- late asynchronous response rejection;
- actionable transaction recovery states;
- exact regression fixtures for known incidents;
- real ComfyUI Apply/finalize and rollback coverage.

These changes should remain acceptance gates for the larger architecture.

## Open questions and unknowns

The target architecture is reasonably clear. The principal unknowns concern
native ComfyUI behavior, migration, and product semantics.

### Native serialization inventory

We need to identify which node families mutate their serialized representation
during `configure()`, extension hooks, or refresh:

- dynamic inputs and outputs;
- converted widgets;
- extension-added properties;
- reroutes;
- groups;
- subgraphs;
- Node 2.0 representations;
- custom-node lifecycle hooks;
- frontend-generated defaults and identifiers.

`vibecomfy.exec` is a proven example, but it is unlikely to be the only one.

The result should be a compatibility ledger that states which fields are:

- execution-semantic;
- layout-semantic;
- derived UI state;
- native defaults;
- extension-owned opaque data;
- unsupported.

### Whole-workflow replacement

We need to decide whether any operations genuinely require
`loadGraphData()`-style replacement instead of canonical delta application.

If the answer is yes, full replacement needs:

- a formal operation contract;
- explicit scope rules;
- declared precondition and postcondition projections;
- a deterministic inverse or snapshot restoration contract;
- native composition tests.

### Nested scopes and subgraphs

The current safe behavior is rejection until the adapter supports them.
Supporting them requires decisions about:

- scope-qualified identities;
- recursive projections;
- cross-scope links;
- group identity inside scopes;
- active subgraph canvas ownership;
- partial Apply and rollback;
- workflow-tab state while editing a nested canvas.

This likely deserves a separate epic after the root-scope transaction system is
stable.

### Undo semantics

We need a product decision on whether Undo is:

- canvas-local and transient;
- workflow-context persistent;
- or durable transaction-journal state that survives refresh.

That decision affects inverse-delta persistence, scope restoration, and
recovery contracts.

### Legacy transaction migration

Existing sessions and prepared transactions may use older hash and projection
contracts. We need an explicit policy:

- continue them under their original version;
- migrate them with a verified conversion;
- or mark them safely non-resumable and provide rebaseline or rollback.

Silent reinterpretation under a newer projection is unsafe.

### Browser and Python equivalence

We need to minimize logic duplicated across languages. Ideally, projection
contracts and fixtures should be generated from one declarative schema.

Where equivalent implementations are unavoidable:

- cross-language golden fixtures are mandatory;
- every projection version must be tested in both runtimes;
- CI must fail when browser and Python hashes diverge.

### Test environment separation

The current development ComfyUI checkout contains unrelated conflicting and
missing extensions. This makes global browser-console cleanliness an unreliable
product gate.

We need:

1. A minimal deterministic environment for VibeComfy correctness.
2. A compatibility environment containing selected major node packs.
3. An explicit allowlist for known third-party warnings in compatibility runs.
4. Separate failure attribution for VibeComfy, ComfyUI core, and third-party
   extensions.

## Proposed epic

### Deliverable 1: Native adapter and projection registry

- Extract all LiteGraph access into `intent_graph_adapter.js`.
- Complete the projection registry and versioned contracts.
- Inventory native normalization behavior.
- Add cross-language fixtures and ownership tests.

Exit criteria:

- No graph projection or LiteGraph mutation exists outside its owner.
- All current incident fixtures pass through actual ComfyUI serialization.

### Deliverable 2: Workflow controller and verifier

- Create `agent_edit_controller.js`.
- Extract transaction coordination from `vibecomfy_roundtrip.js`.
- Create one Apply/rollback verifier.
- Bind all asynchronous commits to workflow activation and transaction
  identity.

Exit criteria:

- Workflow switches are atomic in every lifecycle phase.
- `vibecomfy_roundtrip.js` owns no transaction decisions.

### Deliverable 3: Recovery and migration

- Complete deterministic recovery for every post-prepare state.
- Define Undo durability.
- Version or migrate legacy transactions.
- Add exact diagnostic diffs for failed rollback verification.

Exit criteria:

- Every durable nonterminal state has a safe automated or user-actionable next
  step.
- Refresh cannot strand a transaction in an ambiguous state.

### Deliverable 4: Real-ComfyUI composition matrix

- Build the minimal pinned ComfyUI test environment.
- Add all incident and failure-injection fixtures.
- Add representative custom-node compatibility runs.
- Enforce architecture and composition gates in CI.

Exit criteria:

- Prepare → Apply → serialize → verify → finalize passes for every supported
  transaction family.
- Failure injection proves verified rollback and refresh recovery.
- Unsupported structures are rejected before mutation.

## Definition of complete robustness

The work is complete only when:

1. Every identity and projection has one authoritative owner.
2. Every graph mutation uses a declared canonical operation.
3. Native ComfyUI normalization cannot create false verification failures.
4. Every workflow has isolated state and asynchronous authority.
5. Every post-prepare failure has deterministic recovery.
6. Stable IDs always outrank presentation heuristics.
7. Browser and backend projection results are proven equivalent.
8. Real ComfyUI tests cover success, failure, refresh, switching, and rollback.
9. Static guardrails prevent the architecture from drifting back toward
   duplicate ownership.

Until these conditions hold, individual incident fixes should be described as
strong foundational repairs rather than a complete architectural resolution.
