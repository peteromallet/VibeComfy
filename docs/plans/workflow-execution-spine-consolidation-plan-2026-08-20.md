# Workflow execution-spine consolidation plan

**Date:** 2026-08-20
**Status:** execution-ready; not started
**Planning base:** `5fc6be9dbe811df77e43d440ad087440e8bd57b5`
**Goal:** `docs/plans/goal-workflow-execution-spine-consolidation-2026-08-20.md`
**Future log:** `docs/plans/workflow-execution-spine-consolidation-execution-log-2026-08-20.md`
**Future evidence:** `docs/plans/workflow-execution-spine-consolidation-evidence/`

**Operator override (2026-08-20):** The operator directed that the
authoritative G7 finale is **50 scenarios × 2 modes (staged + threaded) =
100 concurrent live legs**, at concurrency **10 = 10 waves**. This supersedes
prior “exactly five” / “final-five immutable” *finale-count* wording only.
The locked final-five remain the r5-comparable core subset (final50 entries
1–5) and stay independently locked. All other plan law — the fourteen
contracts, schema closure, terminal semantics, T0.2 overlap freeze,
retry/evidence/lineage, and protected concurrent work — is unchanged. The
§13 “final-five inputs contradictory” stop rule is waived only for this
operator-authorized count amendment.

## 1. Outcome

Build one evidence-bound workflow execution spine:

```text
raw UI/API payload
  -> one shape-aware ingest
  -> immutable WorkflowSnapshot
       retained VibeWorkflow + lossless raw sidecar + layout + lineage
       immutable, content-addressed SchemaSnapshot
  -> staged or threaded deliberation
  -> one operation-admission gateway
  -> one accepted delta and closed checkpoint
  -> one replay/authority verification
  -> one typed terminal projector
  -> lineage-bound artifacts and assessment
```

Staged and threaded may deliberate differently. For each leg, they must use the
same authorities for graph meaning, schema meaning, operation admission,
accepted delta, replay, terminal state, and evidence. They are not required to
produce byte-identical prose, tool calls, or edits when stochastic deliberation
can validly choose different solutions.

The successor must:

- render every model-facing Python workflow view from the retained canonical
  `VibeWorkflow`, never from a convenient raw artifact;
- preserve UI/API JSON losslessly as a boundary sidecar, including unknown
  custom-node and frontend data;
- freeze schema source, identity, content, precedence, and conflicts at turn
  ingress, and use that same snapshot for authoring and replay;
- permit unknown nodes to load, render, explain, execute where the target
  runtime supports them, and survive unrelated edits untouched;
- block only operations whose schema-dependent closure is unsupported;
- make the DSL, typed tools, linter, candidate builder, preview, Apply gate,
  and replay consume one operation-admission result;
- distinguish `applied`, `clarify`, `no_candidate`, `authority_rejected`,
  `no_op`, and `infra_failure` without collapsing them into generic no-change;
- make every replay mismatch reproducible from durable inputs and a bounded
  canonical diff;
- assign transport, tool, protocol, durable, and harness retries to one owner
  each, with attempt identity, wall-clock budget, cost, and idempotency proof;
- expose the same typed research facts from both modes without forcing the
  same research orchestration;
- make mixed-representation, stale-path, and cross-turn assessment impossible;
- declare required custom-node/schema/runtime inputs before paid model work;
- remove every obsolete or duplicate execution-spine shim and give each
  retained compatibility shim a named consumer, contract, owner, and removal
  condition, while preserving unrelated cleanup work;
  and
- end with fifty locked scenarios run once through staged and once
  through threaded, 100 concurrent live legs total at concurrency 10 =
  10 waves, honestly assessed and independently reviewed.

## 2. Confirmed starting failures

The r5 paired run completed ten legs: five product passes and five failures.
Root-cause work established:

1. The assessor mixed a UI original with an API final, decoded both as UI, and
   fabricated 21/41 `remove_node` operations.
2. The isolated worktree used an incomplete cwd-relative schema cache even
   though valid IndexTTS/Qwen schemas existed in another local snapshot.
3. `LayerMask: SegmentAnythingUltra V3` had no authoritative schema in the
   checked caches, repository, or live `/object_info` source.
4. An intentional no-candidate clarification was forced through candidate
   replay and relabelled as a server replay failure.
5. A threaded candidate was rejected by a replay hash that cannot be reproduced
   from any persisted input; the mismatching intermediate/provider state was
   not saved.
6. A 480-second timeout was described as retryable but immediately raised;
   the direct comparison path did not own a semantic retry.
7. Threaded research emitted multiple `batch` fences twice; strict parsing
   correctly failed closed, but no tool/evidence work executed.
8. Both modes share the edit host but project research, no-candidate, reply,
   and artifact evidence differently.

The plan fixes ownership and evidence. It does not restore positional
`widget_N` guessing, weaken replay, merge ambiguous fences, treat prose as
evidence, or block a whole workflow because an untouched node is unknown.

## 3. Authoritative inputs and preservation

### 3.1 Source boundary

- Planning worktree: `/private/tmp/vibecomfy-pr156-local-integration`
- Planning branch: `integrate/pr156-local-cleanup-20260820`
- Planning SHA: `5fc6be9dbe811df77e43d440ad087440e8bd57b5`
- Remote: `https://github.com/peteromallet/VibeComfy.git`
- Observed remote `main`: `054bce5bdc9c63d68ac7e6141063e1f029a70dcb`

At planning time, `origin/main` contained PR154/PR155 merge commits and was not
an ancestor of `5fc6be9d`. A read-only merge simulation was conflict-free and
produced exactly the `5fc6be9d` tree. G0 must re-fetch and re-prove this.

Execution starts in a fresh clean worktree from a human-authorized base that
contains current `origin/main` and `5fc6be9d`. If obtaining it requires a merge
commit or history rewrite not already authorized, stop. Never force-push,
reset, stash/delete, discard, or reconstruct preserved history.

Recommended execution branch and explicit push target:

```text
fixer/workflow-execution-spine-consolidation
git push origin HEAD:fixer/workflow-execution-spine-consolidation
```

Do not work directly on `main`; final merge/default selection is separate.

### 3.2 Protected concurrent work

These are separate work and must not be staged, rewritten, or absorbed:

- `docs/plans/codebase-structural-cleanup-master-plan.md`;
- `docs/plans/goal-codebase-structural-cleanup-2026-08-20.md`;
- `docs/plans/codebase-structural-cleanup-execution-log-2026-08-20.md`;
- `docs/plans/codebase-structural-cleanup-evidence/`;
- dirty or active worktrees, including the primary checkout;
- active Astrid, maintenance, Megaplan, test, or runtime state; and
- large r5 outputs, except as read-only evidence.

This plan is the focused correctness owner for the r5 execution-spine gaps.
The structural-cleanup master plan remains the repository-wide owner for shims,
generated code, and unrelated debt. Overlapping cleanup packages must serialize
behind the relevant reviewed commit from this plan; do not run overlapping
`A21/A26`, `B34/B35/B37`, `G52/G53/G58/G59/G63`, `E60/E62/E63`, `S72/S74`,
or harness-authority edits concurrently against the same files.

Historical threaded/IR plans are evidence, not execution authorities. Preserve
their settled law that `run_executor` is the sole orchestration entry and mode
branches do not leak below orchestration.

### 3.3 Exact final-five semantic set (r5-comparable core of final50)

The authoritative G7 finale is fifty scenarios × two modes. The locked
final-five remain the first five r5-comparable core entries of
`tests/live_agentic_harness/threaded_comparison_manifest_final50.json`; they
are the same semantic five used by r5, not the first five of the current
six-entry comparison manifest:

| Scenario | r5 locked input SHA-256 |
|---|---|
| `audio-tts-narration-using-indextts-2` | `c099f40b9208579ce320a0e5bcd9c579b78265f3639f828059efee41c26fb28d` |
| `image-image-editing-with-qwen-image` | `dc1062c6fd00ef18395d403ce725964c1d68e354ba9ac6ed56278b835fae20f3` |
| `live-graph-explanation-smoke` | `d93e79a71bd0bf6c496744ba81a1f9af9ee7672467a83d6100ffe638c3cd538c` |
| `multi-video-based-character-replacement-using` | `625ed91eacf070e1d531a806b69b8221bf7a02f1e5c2a42b98502b0ae48ac63d` |
| `speed-distillation-research` | `52b36af605acb7728c5809ac0961e901c5bc2fecc1f91f167911428a5d2efa7a` |

G0 mechanically rederives descriptor, source-workflow, query/interaction, and
locked-input digests. The table identifies the intended r5-comparable core
but does not authorize stale evidence. T0.1 committed the exact five-entry
manifest `threaded_comparison_manifest_final5.json`; it remains unchanged
as the independently locked core. T0.4 committed the authoritative fifty-
entry manifest `threaded_comparison_manifest_final50.json` with those five
entries first, plus 45 additional real VibeComfy ready-template/corpus
workflows. Leave the canonical six-entry manifest intact.

Read-only baseline output:

```text
/private/tmp/vibecomfy-dualpath-five-run-20260820-r5
```

Do not commit bulky live output. Extract minimal redacted regression fixtures
and content digests before the disposable directory can disappear.

## 4. Non-negotiable contracts

1. One retained `VibeWorkflow` is semantic graph authority after ingress.
2. Raw UI/API remains lossless boundary evidence, not a second semantic graph.
3. One immutable `SchemaSnapshot` binds authoring and replay for a turn.
4. Missing schema blocks only an operation's schema-dependent touched closure.
5. `accepted_batch`/canonical operations are the sole mutation authority.
6. One operation gateway admits or rejects add/remove/field/link/mode/layout
   operations with a typed reason and evidence references.
7. Redacted audit, narration, model prose, and assessment never authorize Apply.
8. One mode-neutral terminal projector reads one closed checkpoint.
9. Original, schema, delta, candidate, receipt, response, and assessment share
   scenario/session/turn/baseline lineage.
10. Mode changes deliberation only; authority and evidence contracts are shared.
11. Unknown evidence remains unsupported/undetermined, never guessed green.
12. Retrying cannot duplicate provider/tool/edit effects.
13. Missing required scenario setup is not a product pass and is discovered
    before paid calls.
14. No execution card promotes live behavior or merges to `main` automatically.

## 5. Model, review, and revision routing

- `[HARD]`: bounded work under a frozen contract.
- `[XHARD]`: architecture, authority, compatibility, persistence, concurrency,
  replay, schema, or public-terminal work.
- `[HARD-REVIEW]`: independent GPT-5.6 Luna review.
- `[XHARD-REVIEW]`: fresh independent Grok 4.6 review returning exactly
  `continue`, `correct`, `replan`, or `stop`.
- `[HARD-REVISION]` / `[XHARD-REVISION]`: fresh evidence-linked repair agent;
  the complete card diff is independently re-reviewed afterward.

Luna owns inventories, briefs, workspace preparation, ordinary implementation
and review, focused validation, mechanical integration/push, evidence, and
report assembly. Grok 4.6 owns XHARD implementation, material judgments, XHARD
review/revision, and final recommendation.

Every XHARD card requires a fresh Grok pre-code contract review, a different
Grok implementer, focused failure injection, and a fresh Grok post-code
adversarial review. No agent reviews or integrates its own work. A Luna
encountering a material judgment returns `JUDGMENT_REQUIRED` without mutation.

## 6. Required execution sequence

### G0 — Freeze source, failures, contracts, and evidence

#### T0.0 `[HARD]` Source custody and baseline

Record refs, HEAD/status/untracked files, all worktrees, relevant processes,
Python/Node/package identities, schema sources, fixture mounts, scenario
manifests, model routes, and protected state. Create a fresh execution worktree
and disposable artifact/cache root. Prove the root is not a project, candidate,
source-workflow, or live runtime root.

Run the existing comparison `--validate-only` and focused baseline shards
before production mutation. Record pre-existing failures with base/head proof.

#### T0.1 `[HARD]` Freeze r5 regressions and final-five identity

Create minimal deterministic fixtures for:

- mixed UI/API assessment and fake removal;
- intentional no-candidate clarification;
- TTS schema visibility across isolated worktrees;
- missing touched LayerMask schema and untouched unknown preservation;
- the saved replay mismatch and currently successful deterministic replay;
- the 480-second attempt ledger; and
- repeated multiple-fence output.

Create `tests/live_agentic_harness/threaded_comparison_manifest_final5.json`
with exactly the five rederived entries. Prove the six-entry manifest unchanged
and final-five validation makes zero model calls.

#### T0.3 `[HARD]` Receipt wrapper and evidence validator

Create these files during execution:

```text
 scripts/run_workflow_execution_spine_agent.py
 scripts/validate_workflow_execution_spine_evidence.py
 docs/plans/workflow-execution-spine-consolidation-evidence/manifest.json
 docs/plans/workflow-execution-spine-consolidation-evidence/test-shards.json
```

The wrapper records invocation/model/PID, task/role/label, command, allowance,
base SHA, brief/result digests, timestamps, exit, commit, and evidence. It
rejects overlapping active allowances. The validator enforces dependency
order, model routing, reviewer independence, finding/revision/re-review chains,
artifact digests, test singleton keys, final-five integrity, one authoritative
live invocation, and exactly 100 final leg receipts.

The Luna implementation of T0.3 is the sole direct-launch bootstrap exception.
All subsequent dispatch uses the wrapper.

#### T0.2 `[XHARD-REVIEW]` Contract and overlap freeze

After T0.3 enables the wrapper, fresh Grok reviews the fourteen contracts,
operation-level schema closure, terminal transition semantics, final benchmark
identity, and serialization with the structural-cleanup effort. `continue` is
required.

**G0 gate:** independent Luna review plus fresh Grok XHARD review.

### G1 — Canonical graph and schema context

#### T1.1 `[XHARD]` Immutable `WorkflowSnapshot`

Extend the existing snapshot owner unless pre-code review proves a new module is
necessary. Freeze canonical `VibeWorkflow`, source representation/digest,
semantic hash version, layout reference, raw sidecar, stable identity/topology,
and session/turn lineage. Define canonical JSON/hash behavior and opaque/UI-only
field preservation.

Primary allowance: `vibecomfy/ingest/snapshot.py`, `normalize.py`, shared agent
ingest/state adapters, and focused snapshot/IR/inspection tests.

Acceptance: UI, API, and `{prompt: API}` detect shape once; inputs are never
mutated; model Python, inspection, comparison, and replay consume the retained
snapshot; opaque unknown-node data survives projection.

```bash
python -m pytest -q \
  tests/test_ingest_snapshot.py \
  tests/test_snapshot_api_workflows.py \
  tests/test_ir_laws.py \
  tests/test_graph_inspection.py
```

#### T1.2 `[XHARD]` Immutable `SchemaSnapshot`

Freeze runtime/cache/request identity, content digest, precedence, generation,
conflicts, timestamp/version, per-class schema, and missing classes at ingress.
Precedence is explicit request snapshot, verified connected `/object_info`, then
configured content-addressed cache. Workflow observation is non-authoritative.
Replay cannot perform a fresh ambient lookup.

Define `touched_schema_classes(operation, snapshot)` for field, add/remove,
link/socket, mode, and layout operations. Unknown untouched nodes remain
preserved. Any operation whose validity depends on unknown endpoint/node schema
fails closed.

Acceptance: isolated worktrees resolve proven TTS/Qwen schemas; LayerMask stays
unsupported until exact pack schema is supplied; no positional alias becomes
durable authority without a proven name.

```bash
python -m pytest -q \
  tests/test_schema.py \
  tests/test_porting_provenance.py \
  tests/security/test_provenance.py \
  tests/test_shared_authority_canonicalization.py
```

**G1 `[XHARD-REVIEW]`:** one graph, one schema snapshot, lossless sidecar,
touched-only blocking, and no ambient replay lookup.

### G2 — Operation, checkpoint, and replay authority

#### T2.1 `[XHARD]` One operation-admission gateway

Use one operation-level result:

```text
admit_operation(snapshot, canonical_operation)
  -> allowed | rejected(typed_reason, evidence_refs, touched_scope)
```

DSL, typed tools, lint, candidate building, browser preview, Apply, and replay
consume it. Invalid proposals may remain in debug/model evidence but never enter
the accepted delta or externally visible candidate. Mixed-validity batches are
atomic. No whole-graph fallback widens authority.

```bash
python -m pytest -q \
  tests/test_porting_edit_kernel.py \
  tests/test_porting_edit_apply.py \
  tests/test_porting_edit_ops.py \
  tests/test_porting_edit_delta_contract.py
```

#### T2.2 `[XHARD]` Closed checkpoint and typed terminal projector

Freeze this transition table before implementation:

| Checkpoint/evidence state | Terminal state | Graph/apply rule |
|---|---|---|
| accepted delta + verified replay | `applied` | authoritative candidate |
| valid request, zero semantic change | `no_op` | original graph |
| intentional clarification, no candidate | `clarify`/`no_candidate` | original graph; not replay failure |
| candidate or replay rejected | `authority_rejected` | rejected candidate retained only as audit |
| infrastructure failure before acceptance | `infra_failure` | original graph |
| accepted checkpoint, later reply failure | `applied` with grounded fallback prose | never discard accepted work |
| crash after delta/receipt boundary | recovered typed state | lifecycle/receipt decides; no guessing |

Both modes use this projector. Narrative source may differ; state, accepted
delta, graph, eligibility, reason, and evidence references may not.

#### T2.3 `[XHARD]` Reproducible replay and concurrency

Persist submit/delta/candidate/recomputed projections and hashes, schema
snapshot, canonicalization/replay versions, bounded diff, attempt identity, and
protected full-graph reference when needed. Make provider/cache/capture state
request-scoped or prove isolation.

Test duplicate same-turn requests, stale turn, duplicate idempotency key, crash
after delta before receipt, crash after receipt before projection, changed
ambient cache, concurrent independent sessions, and process-global
contamination.

```bash
python -m pytest -q \
  tests/test_authority_receipts.py \
  tests/test_authority_replay_sequential.py \
  tests/test_agent_edit_artifact_replay.py \
  tests/test_comfy_nodes_agent_transaction_storage.py \
  tests/test_comfy_nodes_agent_session.py
```

**G2 `[XHARD-REVIEW]`:** attack duplicate authority, accepted-delta drift,
terminal ambiguity, privacy, replay nondeterminism, idempotency, and recovery.

### G3 — Retry and batch-protocol boundaries

#### T3.1 `[HARD]` Nested retry ownership

Freeze separate owners and total wall-clock budgets for provider transport,
research tools, malformed-protocol correction, durable transaction resume, and
harness infrastructure retries. A fresh Grok judgment decides whether a
side-effect-free timed-out model request may retry once; it is not assumed
universally safe. Every attempt records identity, nesting, deadline, cost,
remote uncertainty, and side-effect/idempotency evidence.

The 480-second case must either retry safely within the same durable identity
or end with a truthful typed exhaustion explaining why retry was unsafe.

```bash
python -m pytest -q \
  tests/test_runtime_worker_retry.py \
  tests/test_executor_contracts.py \
  tests/test_comfy_nodes_agent_contracts.py
```

#### T3.2 `[XHARD]` Batch protocol and accepted-batch authority

Specify no fence, malformed response, multiple fences, valid batch plus prose,
empty batch, duplicate batch, and valid-first/invalid-second behavior. Keep
exactly-one-fence parsing fail-closed; prefer native structured responses where
supported; never merge multiple fences or rerun an accepted batch. Reserve one
bounded correction opportunity before the first call and persist its prompt,
output, and disposition.

`accepted_batch` remains sole Apply authority; whole candidate and legacy delta
surfaces are derived compatibility views.

```bash
python -m pytest -q \
  tests/test_executor_stage_contracts.py \
  tests/test_agent_edit_artifact_replay.py \
  tests/test_comfy_nodes_agent_edit.py -k 'batch or protocol or accepted_batch'

node --test \
  tests/browser/agent_edit_response_contract.test.mjs \
  tests/browser/canonical_delta.test.mjs \
  tests/browser/payload_contracts.test.mjs
```

**G3 review:** independent Luna for T3.1; fresh Grok XHARD review of combined
retry/protocol/idempotency behavior.

### G4 — Staged/threaded observable parity

#### T4.1 `[XHARD]` Shared research evidence contract

Both modes expose attempted/never, model turns, executed tool calls/statuses,
evidence IDs/artifacts, grounded/exhausted/timeout/unsupported, remaining
budget/deadline, and compact handoff ledger. Staged retains a separate research
phase; threaded retains its durable combined conversation. Do not require equal
call counts or evidence bytes.

#### T4.2 `[HARD]` Staged adapter

Make classify, research, implement, no-candidate, and reply consume/produce the
shared snapshot, research, checkpoint, and terminal contracts. Preserve wire
compatibility and separate reply-model behavior.

#### T4.3 `[HARD]` Threaded adapter

Prove classifier-free routing, graphless research, answer-only inspection,
attached-graph edit, continuation/recovery, and terminal projection use shared
contracts without entering staged classification.

```bash
python -m pytest -q \
  tests/test_executor_flows.py \
  tests/test_agent_research_shadow.py \
  tests/test_executor_threaded_contracts.py \
  tests/test_executor_threaded_mode.py \
  tests/test_executor_threaded_sessions.py \
  tests/test_executor_threaded_edits.py \
  tests/test_pipeline_mode_surface.py

node --test \
  tests/browser/pipeline_mode_surface.test.mjs \
  tests/browser/agent_lifecycle_parity.test.mjs
```

**G4 `[XHARD-REVIEW]`:** compare typed route, graph/schema identity, accepted
delta validity, terminal state, failure family, evidence, idempotency, and cost;
never compare prose as correctness.

### G5 — Artifact, assessor, run isolation, and shim retirement

#### T5.1 `[XHARD]` Artifact lineage manifest

Digest-link source commit, request, source representation, workflow snapshot,
schema snapshot, prompt/tool contract, model/provider/transport, research,
accepted delta, candidate, replay proof, terminal response, and assessment by
scenario/session/turn/baseline. Fallbacks carry a reason and cannot impersonate
a candidate/final graph.

#### T5.2 `[XHARD]` Canonical semantic assessor

The assessor accepts typed snapshots/deltas, not arbitrary graph dictionaries.
All UI/API/wrapped-API carriers pass through the common constructor. A graph
pair requires matching lineage. If unchanged or no accepted delta/candidate,
the intent judge does not synthesize an edit. Missing or contradictory evidence
is `undetermined`, never empty graph, pass, or fabricated removal.

#### T5.3 `[HARD]` Scenario obligations and preflight

Each final scenario declares purpose/change, invariants, research requirements,
custom-node classes, schema/runtime provenance, prompt/tool contract, and
admissible infrastructure failures. Audio and multi-video require exact TTS and
LayerMask schema evidence before paid calls. Safe refusal is useful behavior but
does not satisfy a final scenario that requires an edit.

#### T5.4 `[XHARD]` Concurrent comparison isolation

Make schema/provider caches, capture registries, usage ledgers, reply requests,
session/turn IDs, and artifact roots request-scoped/thread-safe, or isolate legs
in processes. Preserve simultaneous submission and deterministic manifest-order
reconstruction; do not serialize to hide races.

#### T5.5 `[XHARD]` Execution-spine shim retirement

Begin from the structural plan's repository-wide `S70` census contract, then
inventory every compatibility façade, lazy re-export, positional alias,
mode-specific adapter, legacy delta/candidate projection, monkeypatch seam,
and wrapper-on-wrapper in the files changed by G1–G5 and all transitive public
callers. Reconcile the result against a repository-wide search so no shim can
disappear between the two plans. Classify each as:

- delete now because no supported consumer remains;
- collapse into the canonical owner because it duplicates authority;
- migrate a named internal consumer, then delete;
- retain temporarily for a named external/public consumer; or
- out of scope here and owned by an exact `S71`–`S77` structural-cleanup card.

Remove all execution-spine shims in the first three classes. Every retained
shim must have one canonical downstream owner, an explicit compatibility test,
a ledger entry naming the consumer and frozen behavior, a deprecation/removal
condition, and proof that it cannot grant authority or change semantics. Emit
a complete disposition manifest that maps every repository-wide `S70` row to
this card or one exact `S71`–`S77` owner; `S78` must be able to prove there are
zero unclassified rows. This focused goal does not independently execute
unrelated `S71`–`S77` cards or claim their completion. No
new positional `widget_N` inference, ambient-schema fallback, whole-candidate
authority path, staged/threaded fork below orchestration, or wrapper chain may
be retained merely because an old test observes it.

The Luna inventory is mechanical; keep/delete decisions affecting a public
surface or monkeypatch/import contract require fresh Grok judgment. Serialize
overlap with the structural-cleanup master plan and update its compatibility
ledger/ownership marker only through that plan's reviewed integration path.

```bash
python -m pytest -q \
  tests/test_agent_edit_compatibility_ledger.py \
  tests/test_cleanup_surface_manifest.py \
  tests/test_api_surface.py \
  tests/test_executor_host_boundary.py \
  tests/test_agent_runtime_adapter.py \
  tests/test_pipeline_mode_surface.py \
  tests/edgecases/test_backward_compat.py

node --test tests/browser/legacy_authority_migration.test.mjs
```

```bash
python -m pytest -q \
  tests/test_headless_agent_artifacts.py \
  tests/test_live_agentic_assessor_score_honesty.py \
  tests/test_live_agentic_harness_guard_contract.py \
  tests/test_headless_harness_scenarios_contract.py \
  tests/test_agent_obligation_ledger.py \
  tests/test_live_agentic_threaded_comparison.py

node --test tests/browser/agent_lifecycle_commit.test.mjs
```

**G5 `[XHARD-REVIEW]`:** attack mixed shapes, stale paths, cross-turn evidence,
fallback-as-final, shared-state races, false verdicts, paid calls before schema
readiness, duplicate authority hidden behind shims, compatibility regressions,
retained shims without a proven consumer/removal condition, and any shim row
missing an exact this-plan or `S71`–`S77` owner.

### G6 — Deterministic validation

#### T6.1 `[HARD]` Freeze canonical test shards

Map every changed production behavior and changed/new test to one shard. Freeze
exact selectors, commands/digests, order, interpreter/environment, timeout, and
disposable roots in `test-shards.json`.

#### T6.2 `[HARD]` Run focused integration shards once

One Luna validator runs, in order: ingest/IR; schema/provenance;
edit/delta; checkpoint/replay/session; retry/protocol; staged/threaded executor;
artifact/assessor/comparator; browser contracts. Classify every failure as
introduced, pre-existing, environmental, or contract drift with base/head
evidence. Introduced failures block G7.

#### T6.3 `[HARD]` Singleton broad suite

After focused shards, one dedicated Luna owns atomic key `broad_suite_once_v1`:

```bash
python -m pytest -q
```

No implementer or reviewer runs the full suite. Any change to the canonical
broad command requires fresh Grok judgment before execution.

#### G6 `[XHARD-REVIEW]`

Fresh Grok reviews the complete base-to-head diff, failure classifications,
compatibility, evidence integrity, and readiness for paid validation.

### G7 — Final fifty staged plus fifty threaded

G7 is strictly serial.

#### T7.1 `[HARD]` Environment and no-model preflight

Prove clean reviewed SHA; interpreter/package identities; explicit disposable
output/cache roots; exact fifty-entry hashes of
`tests/live_agentic_harness/threaded_comparison_manifest_final50.json` with
the locked final-five as entries 1–5; required schema provenance;
credential/route readiness without secret exposure; unique independent
session/turn IDs; prompt/tool/model/provider/transport identities; concurrency
`10` (100 legs = 10 waves); frozen provider budget; and no existing
authoritative live receipt.

```bash
python -m tests.live_agentic_harness.compare_pipeline_modes \
  --validate-only \
  --manifest tests/live_agentic_harness/threaded_comparison_manifest_final50.json
```

The receipt must prove zero model calls.

#### T7.2 `[HARD]` One authoritative concurrent 50x2 live run

One Luna live-run owner invokes exactly once:

```bash
python -m tests.live_agentic_harness.compare_pipeline_modes \
  --run \
  --manifest tests/live_agentic_harness/threaded_comparison_manifest_final50.json \
  --output-base "$DISPOSABLE_FINAL_OUTPUT_ROOT" \
  --tag final-50x2 \
  --concurrency 10
```

All 100 legs are submitted before awaiting results, in 10 waves of 10 legs.
Each pair gets independent input copies, sessions, caches, receipts, and
output roots. Harness infrastructure retries, if enabled, are frozen and
recorded separately; they do not silently replace the authoritative attempt.
There is no second authoritative G7.2 run.

#### T7.3 `[HARD]` Assess and report

For every one of the 100 unique legs record product pass/fail/undetermined
versus infrastructure blocked; actual mode/route; graph/schema/delta/candidate/
receipt/final lineage; terminal state; research obligations; unsupported
claims; latency, calls, tokens, cost, retries, start/end time; artifact
paths/digests; and assessor proof. Assess all 50 scenario pairs. Compare
accepted-delta equality only as a diagnostic unless fully deterministic model
execution was proven.

#### G7 `[XHARD-REVIEW]` Final recommendation

Fresh Grok verifies exactly fifty pairs / 100 unique leg receipts, identical
locked input and schema authority per pair, honest assessment, all 100 required
scenario outcomes passing, no hidden schema/replay/timeout/protocol/assessor
failure, all deterministic gates green, and protected state unchanged. It
returns `continue`, `correct`, `replan`, or `stop` plus a separate merge/default
recommendation. Luna assembles the reviewed report. No automatic merge or live
promotion occurs.

## 7. Dependency graph and allowed parallelism

```text
T0.0 -> T0.1 -> T0.3 -> T0.2 -> G0
                               |
                               v
                     T1.1 -> T1.2 -> G1
                               |
                               v
                     T2.1 -> T2.2 -> T2.3 -> G2
                               |
                               v
                     T3.1 ----+---- T3.2 -> G3
                               |
                               v
                     T4.1 -> T4.2 -> T4.3 -> G4
                               |
                               v
                     T5.1 -> T5.2 -> T5.3 -> T5.4 -> T5.5 -> G5
                               |
                               v
                     T6.1 -> T6.2 -> T6.3 -> G6
                               |
                               v
                     T7.1 -> T7.2 -> T7.3 -> G7
```

The graph is deliberately mostly serial because the cards converge on shared
authority boundaries. Parallel work is permitted only when the plan and a
Luna allowance-preparation receipt establish that production files, tests,
exports, fixtures, generated surfaces, and persistent evidence are disjoint.
At most these research/review activities may normally overlap:

- read-only call-site inventories for T1.1 and T1.2 after T0.3;
- read-only retry and batch-protocol inventories before T3.1/T3.2;
- read-only staged and threaded adapter inventories before T4.2/T4.3; and
- test-shard inventory while the final G5 review is running, without freezing
  T6.1 until G5 passes.

T1.1/T1.2, T2.1/T2.2/T2.3, T4.2/T4.3, T5.1/T5.2/T5.4, all integrations, and
all G6/G7 actions serialize. If a card discovers an unlisted shared helper,
fixture, export, cache, or test file, its agent stops and returns the overlap;
the allowance is not widened informally.

## 8. Card lifecycle and review ownership

Every implementation card follows the same evidence-bound lifecycle:

1. A Luna workspace agent creates a clean task worktree from the latest
   reviewed integration SHA and atomically registers an exact file allowance.
2. A Luna brief agent writes the bounded brief from this card, the accepted
   prior receipts, and the frozen allowance.
3. For XHARD work, a fresh Grok performs pre-code contract review. `continue`
   is required before mutation.
4. The routed implementer edits only allowed files, runs only card-focused
   tests, commits one coherent change, and returns a receipt.
5. A different routed reviewer examines the exact commit and production call
   paths. Test counts alone are not a review.
6. Each must finding becomes a distinct evidence-linked revision card. A
   fresh Luna may handle a mechanical repair under the frozen contract;
   authority, schema, replay, concurrency, compatibility, terminal, or
   cross-module repairs are XHARD and go to fresh Grok.
7. A new independent reviewer re-reviews the complete card diff after every
   revision. No open must finding may integrate.
8. A fresh Luna integration agent applies the reviewed commit in dependency
   order, runs only the named batch shard, records the new integration SHA,
   and pushes with the explicit refspec. Semantic conflicts return
   `JUDGMENT_REQUIRED` for Grok.

Reviewer ownership is therefore fixed: Luna reviews ordinary bounded cards;
Grok reviews every XHARD card, every material judgment, each explicitly
XHARD-designated batch gate, and the whole-system G6/G7 XHARD gates. Ordinary
batch gates remain Luna-owned. An implementer never reviews, integrates, or
closes findings on its own work. The orchestrator advances state and relays
receipts; it does not substitute personal implementation or judgment.

## 9. Brief and file-allowance contract

Each subagent brief contains only:

1. task/gate ID, label, role, and exact goal;
2. task worktree and immutable base SHA;
3. prerequisite integration SHAs and accepted review receipts;
4. exact allowed production, test, fixture, documentation, and evidence files;
5. forbidden files, behaviors, and non-goals;
6. acceptance criteria copied from this plan;
7. focused commands and explicit disposable roots;
8. mutation, commit, integration, push, live-call, and secret permissions;
9. expected counterexample/failure-injection proof; and
10. required result: commit, changed files, commands/results, evidence paths,
    rejected alternatives, residual risks, and any `JUDGMENT_REQUIRED` item.

The wrapper rejects overlapping active allowances and any result whose changed
files exceed its allowance. Tests may read repository fixtures but every
state-writing test uses a new explicit disposable directory. No agent may
write the r5 baseline, project checkout, source workflow corpus, candidate,
ComfyUI runtime, or another card's evidence root.

## 10. Receipt-producing subagent wrapper

After T0.3, all substantive dispatch uses the repository wrapper. It invokes
the absolute launcher from the installed `subagent-launcher` skill and records
the resolved child model and process identity.

Ordinary Luna example:

```bash
python "$EXECUTION_WORKTREE/scripts/run_workflow_execution_spine_agent.py" \
  --task-id="$TASK_ID" --role="$AGENT_ROLE" --label="$TASK_LABEL" \
  --model-route=codex:gpt-5.6-luna \
  --query-file="$BRIEF_PATH" \
  --project-dir="$TASK_WORKTREE" \
  --allowance-file="$ALLOWANCE_PATH" \
  --evidence-dir="$EVIDENCE_DIR" --timeout=7200
```

XHARD Grok 4.6 example:

```bash
python "$EXECUTION_WORKTREE/scripts/run_workflow_execution_spine_agent.py" \
  --task-id="$TASK_ID" --role="$AGENT_ROLE" --label="$TASK_LABEL" \
  --model-route=grok-4.6 \
  --query-file="$BRIEF_PATH" \
  --project-dir="$TASK_WORKTREE" \
  --allowance-file="$ALLOWANCE_PATH" \
  --evidence-dir="$EVIDENCE_DIR" --timeout=7200
```

The T0.3 bootstrap Luna is invoked directly through:

```text
/Users/peteromalley/.codex/skills/subagent-launcher/launch_hermes_agent.py
```

The wrapper invokes Grok 4.6 through:

```text
/Users/peteromalley/.codex/skills/subagent-launcher/launch_omp_agent.py
```

The Luna bootstrap's exact command, native metadata, stdout/stderr digests,
PID, resolved model,
timestamps, exit, brief/result digests, and commit are registered as the first
receipt before the wrapper is enabled. Direct launcher calls after that point
are invalid. If the requested model route fails, a Luna configuration agent
checks the launcher/model once and retries once; persistent unavailability
stops the affected card rather than substituting a model.

## 11. Test ownership and cost discipline

- Implementers run only the focused commands on their card.
- Card reviewers inspect production paths and run only the named focused or
  batch counterexample shard needed to test a finding.
- Integration agents run one bounded batch shard after applying reviewed work.
- T6.2 has one owner for the frozen focused shard sequence.
- T6.3 has one owner and one atomic receipt for the broad Python suite.
- Browser tests are a separate frozen shard; they do not trigger the Python
  broad-suite singleton.
- G7 has one no-model preflight owner, one live-run owner, one assessment
  owner, and one independent Grok final reviewer.
- No live model calls occur before G7.2. The final comparison uses a frozen
  provider/model/budget configuration, captures call/token/cost receipts, and
  stops at its declared cap.

For each shard, record the exact command and digest, selector set, source SHA,
interpreter/runtime/package identities, environment digest, disposable root,
start/end timestamps, exit, result, and artifact digest. A changed command is
a new invocation, not the original shard receipt.

## 12. Durable execution record

Maintain:

```text
docs/plans/workflow-execution-spine-consolidation-execution-log-2026-08-20.md
docs/plans/workflow-execution-spine-consolidation-evidence/manifest.json
docs/plans/workflow-execution-spine-consolidation-evidence/test-shards.json
```

After each card/gate, append task disposition, input/output SHA, model route,
launcher command, wrapper invocation ID/PID/timestamps/exit, brief/result
digests, commit/files, tests/evidence, findings/revisions/re-review, residual
risks, and next unblocked card. Commit the log at every completed gate. The
Markdown log is the human handoff and compaction seam; the JSON manifest is
machine authority.

Validate with:

```bash
python scripts/validate_workflow_execution_spine_evidence.py \
  docs/plans/workflow-execution-spine-consolidation-evidence/manifest.json
```

The validator rejects duplicate task/gate/shard/live-run records, wrong model
routing, self-review, incomplete finding chains, missing artifacts/digests,
unmapped changed behavior/tests, changed final-five identity, more than one
authoritative live invocation, fewer or more than 100 unique final leg
receipts, missing latency/cost data, and a final verdict based only on process
completion rather than scenario assessment.

## 13. Stop and escalation conditions

Stop the affected card, preserve evidence, and do not integrate when:

- the current base cannot be proven to preserve both authorized `origin/main`
  and `5fc6be9d` content without an unauthorized history operation;
- protected dirty/concurrent work changes or enters an allowance;
- Luna or Grok remains unavailable after one configuration check and retry;
- an XHARD pre-code review does not return `continue`;
- any must finding remains open or a revision lacks independent re-review;
- a card needs a new authority, schema-precedence, compatibility, retry,
  persistence, concurrency, or public-terminal decision;
- an operation cannot identify its schema-dependent touched closure;
- replay cannot be reproduced from persisted inputs;
- a test would write a project, source corpus, candidate, live runtime, or r5
  evidence root;
- the final50 inputs (or the locked final5 core subset), schema authority,
  provider/model route, budget, or secrets readiness are contradictory
  (the operator-authorized T0.4 finale-count amendment is the sole waived
  instance of the old “final-five inputs contradictory” count stop);
- G7 preflight records any model call or paid call starts before it passes;
- a second authoritative final live invocation would be required; or
- evidence suggests cross-leg/session/cache contamination.

Ordinary difficulty is not a stop condition. Re-brief or split a card without
changing semantics. Any material split/reclassification goes to fresh Grok. If
the same must finding survives three verified revisions, route the complete
evidence to fresh Grok adjudication rather than forcing acceptance.

## 14. Done when

The work is complete only when:

- G0 through G7 have explicit passing dispositions;
- canonical graph, schema, operation, checkpoint, replay, retry, terminal,
  research, artifact, and assessment owners are implemented and documented;
- unknown untouched nodes remain usable and unsupported touched operations
  fail closed with precise evidence;
- the r5 mixed-shape, schema-source, no-candidate, replay, timeout, and
  multiple-fence failures have deterministic regressions;
- staged and threaded use the same authority contracts while retaining their
  intended orchestration differences;
- every changed behavior/test maps to one passing frozen shard and the one
  authoritative broad suite passes;
- every implementation, review, revision, integration, test, judgment, live
  run, and report artifact has a valid routed subagent receipt;
- every must finding has a closed revision/re-review chain;
- the evidence validator exits zero;
- the exact locked fifty are submitted once through staged and once through
  threaded in one concurrency-10 invocation (100 legs = 10 waves);
- exactly 100 unique legs complete and all 100 are independently assessed as
  satisfying their required product outcome—not merely finishing a process;
- final reporting includes per-mode latency, cost, calls, tokens, retries,
  terminal state, failure family, and evidence lineage;
- protected work and external runtime/project state are unchanged;
- fresh Grok G7 review has no unresolved must finding and issues a separate
  merge/default recommendation; and
- the reviewed integration SHA, execution log, and evidence manifest are
  pushed explicitly to the execution branch.

Do not claim completion because all subagents returned, the harness exited
zero, 100 legs produced files, or a majority passed. Completion is the
reviewed, evidence-bound end-state above with 100 genuinely successful final
scenario outcomes. Live promotion and merging to `main` remain separate human
decisions.
