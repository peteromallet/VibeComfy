# VibeComfy Routing, Research, and Execution Handoff Audit

Status: independent adversarial architecture audit
Date: 2026-07-13
Method: read-only GPT-5.6 Sol review at `xhigh` reasoning
Scope: browser capture through executor routing, research, schema hydration,
planning, batch execution, completion, and executor serialization

## Executive conclusion

VibeComfy's editor core is safer than its end-to-end contract. The system has
careful browser capture, closed routing, transactional batch mutation,
deterministic graph validation, durable artifacts, and stale-state defenses.
The major failures happen at handoffs: evidence is promoted beyond its
authority, required planning becomes nullable absence, task completion can be a
model assertion, and executor serialization can contradict stricter agent-edit
gates.

The most immediate defect was reproduced directly: an agent-edit response with
`queue_validate_ok=false` can emerge from executor serialization with
`queue_allowed=true`. The durable queue decision is omitted and reconstructed
from candidate presence. More broadly, the pipeline proves that a structurally
valid edit happened more reliably than it proves that the requested edit
happened.

This report complements
[end-state-and-pipeline-audit.md](./end-state-and-pipeline-audit.md). That report
concentrates on the canonical mutation transaction. This report concentrates on
the authority and information passed into and out of that transaction.

## Active pipeline and authority map

Legend: `A` authoritative artifact, `D` deterministic result, `M` model
assertion, and `I` inferred heuristic.

```text
Browser canvas
  A: graph, task, hashes, canvas token, provider/model, session, idempotency key
  -> typed ExecutorRequest and server-owned provider profile
  -> classifier
     M: route, task, search directions, change goal
     D: unknown route becomes clarify; route policy controls phases
  |
  +-- revise --------------------------------------------------------+
  |   D: implement without executor research                         |
  |   A/D: topology, readiness, and optional numeric-ID scope         |
  |                                                                   |
  +-- adapt/author --------------------------------------------------+
      M: classifier-generated retrieval query
      A: returned source records
      I: relevance, compatibility, and local-first selection
      I: first selected precedent becomes directive
      A/I: workflow-observed provisional schemas
      D?: execution plan only for a narrow supported case
                                                                     |
  -> agent-edit request/state <--------------------------------------+
     A: request, original graph, hashes, session, turn
  -> model edit prompt
     A: task, graph facts, schema signatures
     M/I: precedent, compact research context, plan hints
  -> bounded batch EditSession
     M: proposed operations and done/clarify
     D/A: parsed operations, rollback, candidate, batch logs
  -> completion gates
     D: replay, compile, topology, readiness, queue; plan if present
     M: generic semantic completion when no obligation oracle exists
  -> durable agent-edit response
     A: candidate, gates, queue/apply flags, task and batch evidence
  -> reply model
     M: user-facing narration
  -> executor serialization
     should preserve durable authority; currently narrows and reconstructs it
  -> browser review and compare-and-swap Apply
```

## Ranked findings

### 1. Critical: executor serialization broadens queue authority

Agent-edit emits distinct canvas and queue decisions plus task and batch
evidence in `edit_response_contract.py`. The executor top-level allowlist in
`executor/contracts.py` omits `canvas_apply_allowed`, `queue_allowed`,
`task_satisfaction`, `batch_turns`, and plan-status evidence. It then derives
`apply_eligible` from route plus graph presence, while
`comfy_nodes/agent/executor_response.py` maps that boolean back onto both canvas
and queue authority.

A read-only probe reproduced this contradictory response:

```text
gates.queue_validate_ok = false
queue_allowed = true
```

The public response can therefore authorize Queue contrary to its authoritative
gate trace.

### 2. Critical: required adapt planning fails open

Planning detection is broad, but the current deterministic execution-plan
builder supports a narrow HotShotXL eight-frame case and returns `None` for
other work so execution can continue. Builder errors and unsupported cases are
converted to no plan, while the absence of a plan is treated as a passing gate.

Most non-HotShot adapt or authoring requests can therefore complete without
either a supported plan or a semantic obligation proof. The contract needs to
distinguish:

```text
not_required | required_supported | required_unsupported
```

Nullable plan absence cannot carry those meanings safely.

### 3. Critical: workflow observations become queue-safe schema authority

Research-derived workflow schemas are marked provisional and non-runnable, but
they are prepended ahead of the existing provider in a first-provider-wins
composition. Their confidence is high enough to avoid the queue diagnostic's
low-confidence blocker even when provenance says `not_installed` and
`not_runtime_validated`.

An instance-specific or stale precedent can consequently shadow stronger live
schema evidence, authorize node construction, and be reported queue-safe without
runtime proof.

### 4. High: completion proves safety more than task satisfaction

The revise route's scoped evidence proves that there is a localized diff and
that topology and readiness remain acceptable. It does not generally prove a
user predicate such as “this exact field changed to this exact value” or “this
branch was inserted before sampling.”

Task-satisfaction records are mainly present when an execution plan exists, or
as advisory adapt checks. In addition, an edit followed by model clarification
can remain candidate-producing after graph gates are stamped successful. A
wrong-but-valid edit or knowingly incomplete partial edit can therefore appear
applyable.

### 5. High: precedent selection loses relevance and freshness authority

Classifier-generated search directions can replace the user's raw query.
Unknown-family or unknown-media sources survive semantic filtering. After
relevance sorting, workflow sources are reordered local-first and the first is
turned into directive grounding evidence.

The web cache also merges cross-query files without an explicit TTL, while the
selected-precedent contract lacks retrieval time and a complete content hash.
Weaker or stale local evidence can silently displace a stronger current match.

### 6. High: request identity and successful work are lost at adjacent handoffs

The browser supplies an idempotency key and `ExecutorRequest` retains it, but the
implementation payload does not forward it into edit-side turn allocation.
Retries can therefore repeat provider or edit work.

After implementation succeeds durably, the executor always invokes a reply
model. A narration-only failure can turn the overall request into a failure and
hide the valid candidate. Provider compatibility handling may also remove reply
context fields one at a time without recording the resulting evidence loss as a
contract downgrade.

### 7. Medium: a legacy endpoint bypasses the executor contract

The two VibeComfy product endpoints converge through the executor, but
`/agent/edit` still calls the edit handler directly. It retains different
classification, research, reply, and durability semantics and prevents the
executor contract from being universal.

## Cross-check against the broader audit

The independent review agrees with the broader audit's central recommendations:

- model narrative is not proof;
- research and schemas require explicit provenance and precedence;
- planning should be obligation-led;
- gates should distinguish `pass`, `fail`, `not_run`, and `unknown`;
- one canonical mutation authority should drive preview and Apply;
- Apply should be transactional and recoverable.

It qualifies one point: deterministic replay and scoped protection do run during
server-side revise construction, and unsafe revise candidates can be reset. The
larger authority loss occurs later at semantic completion, executor
serialization, and browser publication.

The broader report should also explicitly account for:

- queue authority being reconstructed incorrectly;
- the narrow nullable plan builder;
- provisional schemas becoming queue authority;
- local-first and stale precedent selection;
- applyable edit-plus-clarify outcomes;
- dropped end-to-end idempotency;
- reply failure masking durable work.

## Recommended target contracts

### `TurnInput`

Immutable graph bytes, graph hash and revision, user task, authorized scope,
provider and model, session identity, and one end-to-end idempotency key.

### `IntentDecision`

Every field tagged as `user`, `deterministic`, `model`, `inferred`, or
`override`, with authorized scope, ambiguity, route disagreement, and explicit
proof obligations.

### `ResearchManifest`

Allowed evidence tiers, exact query, live or cache origin, retrieval time,
content hash, claim-to-source links, compatibility result, and reproducible
selection decision.

### `SchemaClaim`

Distinguish a live class schema from a workflow-instance observation. Carry
schema generation, installation state, runtime-validation state, source
precedence, and conflicts. Provisional observations may support a draft but
must never independently authorize Queue.

### `PlanResult`

Use `not_required`, `required_supported`, or `required_unsupported`. Do not use
nullable absence to represent all three.

### `EditExecutionReceipt`

Before hash, cumulative typed operations, landed and failed operations, after
hash, and atomicity status.

### `CompletionProof`

Independent four-state results for transformation safety, graph validity, task
satisfaction, and runtime readiness. The durable response—not narration—owns
candidate and eligibility authority.

## Phased remediation

### Phase 1: contain authority loss

- Preserve durable queue, canvas, task, batch, and plan fields exactly through
  executor serialization.
- Forward the idempotency key end to end.
- Make edit-plus-clarify non-applyable by default.
- Preserve a durable candidate through reply or audit narration failure.
- Block `required_unsupported` plans.

Exit criteria: injected queue-block, retry, reply failure, partial clarification,
and non-HotShot adapt tests all fail or recover correctly.

### Phase 2: establish evidence authority

- Enforce schema precedence and runtime-validation status.
- Add research-cache TTLs and full content hashes.
- Record classifier query transformations and deterministic precedent selection.

Exit criteria: stale, cross-query, weak-local versus strong-external, and
provisional-schema fixtures behave reproducibly.

### Phase 3: close semantic proof

- Compile revise and adapt requests into explicit obligations.
- Bind plans to input, research, and schema hashes.
- Require deterministic satisfaction or an explicit unsupported result for each
  required obligation.

Exit criteria: wrong-field revise, substituted precedent, incomplete authoring,
and no-compatible-evidence cases cannot become applyable.

### Phase 4: prove the shipped composition

- Add real browser tests for both traced routes.
- Cover route disagreement, retries, degraded providers, and the legacy bypass.
- Publish one lossless evidence manifest across executor and agent-edit.

Exit criteria: every public eligibility bit points to a current passing proof
artifact, and no serializer or compatibility layer can broaden authority.

## Existing strengths to preserve

- browser hash, token, and epoch guards;
- server-owned provider routing;
- fail-closed unknown routes and initial gates;
- transactional batch rollback;
- deterministic replay, compilation, and revise candidate reset;
- durable model and candidate artifacts;
- enforcement for plans that do exist;
- explicit review before Apply.
