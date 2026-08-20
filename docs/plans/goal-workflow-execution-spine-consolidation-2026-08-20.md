# GOAL: Execute the workflow execution-spine consolidation

Execute the complete plan in
`docs/plans/workflow-execution-spine-consolidation-plan-2026-08-20.md` from
G0 through G7. Work one bounded card at a time, use the required receipt-
producing external subagents for implementation and review, integrate only
reviewed commits, and finish with one independently assessed live comparison
of the exact fifty scenarios through both staged and threaded modes (100
legs). Do not create another Megaplan plan or epic for this work.

Writing this goal document does not begin execution. No test, fetch, process,
worktree mutation, paid model call, candidate write, or branch push is
authorized by authoring this document. Execution starts only after the
operator authorizes the goal and G0 establishes its immutable boundary.

**Operator directive (2026-08-20):** The operator overrode the finale
scenario count. The authoritative G7 live run MUST cover FIFTY (50)
scenarios × two modes (staged + threaded) = 100 concurrent live legs, not
the locked five. Authoritative G7 manifest:
`tests/live_agentic_harness/threaded_comparison_manifest_final50.json`.
The locked final-five remain the first five r5-comparable core entries and
stay independently locked in
`tests/live_agentic_harness/threaded_comparison_manifest_final5.json`.
Concurrency is 10 = 10 waves. No merge to `main` and no live promotion.
This supersedes prior “exactly five” / “final-five immutable” *finale-count*
wording only; all other plan/goal law stands.

## Outcome

Produce one coherent successor to integration SHA `5fc6be9d` with one
evidence-bound workflow execution spine:

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

Staged and threaded may deliberate differently, but they must share graph
meaning, schema meaning, operation admission, accepted-delta authority,
replay, terminal state, and evidence contracts. Prose, tool-call sequences,
and stochastic edit choices need not be identical.

The successor must:

- retain one canonical `VibeWorkflow` after ingress and preserve UI/API bytes
  as lossless boundary evidence;
- freeze schema source, identity, content, precedence, generation, and
  conflicts at turn ingress, using the same snapshot for authoring and replay;
- allow unknown untouched nodes to survive unrelated edits while blocking only
  operations whose touched closure depends on unsupported schema;
- route DSL, typed tools, linter, candidate builder, preview, Apply, and replay
  through one typed operation-admission result;
- make `accepted_batch`/canonical operations the sole mutation authority;
- distinguish `applied`, `clarify`, `no_candidate`, `authority_rejected`,
  `no_op`, and `infra_failure` without collapsing them into generic failure;
- make replay mismatches reproducible from durable inputs and bounded diffs;
- assign transport, tool, protocol, durable, and harness retries to one owner
  each with attempt identity, deadlines, cost, and idempotency evidence;
- expose equivalent typed research facts from both modes without forcing equal
  research orchestration;
- make mixed-shape, stale-path, cross-turn, and fallback-as-final assessment
  impossible;
- discover required custom-node/schema/runtime inputs before paid model work;
- delete obsolete/duplicate execution-spine shims, migrate their supported
  consumers, and retain only compatibility shims with a named consumer,
  contract test, owner, and removal condition, while preserving unrelated
  cleanup work; and
- stop before merge to `main` or live promotion.

Completion requires all 100 final live legs to be genuine product passes. A
completed process, an infrastructure completion, or a report claiming success
is not a pass.

## Authoritative inputs

- Execution plan:
  `docs/plans/workflow-execution-spine-consolidation-plan-2026-08-20.md`.
  It is the source of truth for G0–G7 order, prerequisites, allowances,
  acceptance criteria, test shards, and review gates.
- Planning/integration worktree:
  `/private/tmp/vibecomfy-pr156-local-integration`.
- Planning branch:
  `integrate/pr156-local-cleanup-20260820`.
- Current integration SHA: `5fc6be9d`.
- Remote: `https://github.com/peteromallet/VibeComfy.git`.
- Recommended execution branch: `fixer/workflow-execution-spine-consolidation`.
  Push only with `git push origin HEAD:fixer/workflow-execution-spine-consolidation`.
  Never infer the target from a local branch name.
- Protected, unrelated cleanup authority:
  `docs/plans/codebase-structural-cleanup-master-plan.md`, its goal/log/evidence,
  dirty worktrees, the primary checkout, and active Astrid, maintenance,
  Megaplan, test, or runtime state.
- Read-only r5 baseline evidence:
  `/private/tmp/vibecomfy-dualpath-five-run-20260820-r5`.
  Extract only minimal redacted fixtures and digests; never commit bulky live
  output.

The plan's exact final-five semantic set remains the r5-comparable core and
must not be replaced by the first five entries of the current six-entry
comparison manifest:

1. `audio-tts-narration-using-indextts-2`
2. `image-image-editing-with-qwen-image`
3. `live-graph-explanation-smoke`
4. `multi-video-based-character-replacement-using`
5. `speed-distillation-research`

Those five are entries 1–5 of the authoritative fifty-entry G7 manifest
`tests/live_agentic_harness/threaded_comparison_manifest_final50.json`.
T0.1 committed the independently locked
`tests/live_agentic_harness/threaded_comparison_manifest_final5.json`; leave
it and the canonical six-entry manifest unchanged.

If this goal and the execution plan disagree, preserve the plan's safety
constraint, record the conflict, and resolve it before mutation.

## Mandatory model routing through the receipt-producing wrapper

The orchestrator only advances the deterministic card state machine, launches
routed subagents, checks receipts mechanically, and relays reviewed results.
All substantive work must be performed by external subagents. The
orchestrator must not research implementation details, write briefs, edit
code/docs/tests, run tests, classify findings, implement revisions, review
diffs, integrate commits, push branches, validate evidence, or make
architecture/policy/merge judgments.

After T0.3, every dispatch uses:

```bash
python "$INTEGRATION_WORKTREE/scripts/run_workflow_execution_spine_agent.py" \
  --task-id="$TASK_ID" --role="$AGENT_ROLE" --label="$TASK_LABEL" \
  --model-route="$MODEL_ROUTE" \
  --query-file="$BRIEF_PATH" \
  --project-dir="$TASK_WORKTREE" \
  --allowance-file="$ALLOWANCE_PATH" \
  --evidence-dir="$EVIDENCE_DIR" --timeout=3600
```

The wrapper must invoke the absolute launchers and record their process/model
evidence. Luna uses `codex:gpt-5.6-luna` for inventories, briefs, ordinary
`[HARD]` implementation/review/revision, focused tests, integration/push,
evidence, and report assembly. Grok 4.6 uses model route `grok-4.6` for every
`[XHARD]` implementation, `[XHARD-REVIEW]`, material judgment,
`[XHARD-REVISION]`, and final recommendation.

The absolute launcher path for Luna and the T0.3 bootstrap is:

```text
/Users/peteromalley/.codex/skills/subagent-launcher/launch_hermes_agent.py
```

The wrapper invokes Grok 4.6 through:

```text
/Users/peteromalley/.codex/skills/subagent-launcher/launch_omp_agent.py
```

The sole bootstrap exception is the Luna subagent that implements T0.3,
invoked through that absolute launcher with its native metadata capture. After
T0.3, direct launcher calls are invalid. If a required model is unavailable,
record the exact error, check configuration, retry once, and stop at that
card if it remains unavailable.

## Judgment and review-revision routing

Any material choice—authority, schema precedence, identity, replay,
concurrency, compatibility, public terminal state, retry safety, evidence
sufficiency, card split, scope change, or residual-risk disposition—goes to a
fresh Grok 4.6 judgment subagent through the wrapper with label
`[XHARD-REVIEW]`. Luna encountering such a choice stops without mutation and
returns `JUDGMENT_REQUIRED`.

No agent reviews its own implementation. Every reviewer emits finding IDs and
proposes `[HARD-REVISION]` or `[XHARD-REVISION]`. A revision is a new
evidence-linked card, never an orchestrator edit. HARD is permitted only for a
confined fix under a frozen contract; any authority, persistence, replay,
concurrency, schema, compatibility, or ambiguous fix is XHARD. The complete
task diff receives a fresh independent re-review after every revision. A task
cannot integrate while a must finding lacks a closed finding → classification
→ revision → re-review chain, or a Grok receipt accepting the residual risk.

## Brief, file allowance, worktree, and integration discipline

Every brief is prepared by a Luna subagent and mechanically checked by the
wrapper. It contains only the task ID/goal, base SHA, selected source hunks,
exact allowed production/test files, integrated prerequisites, forbidden
behavior, plan acceptance criteria, focused commands/disposable root,
mutation authorization, and required receipt output.

Each card has a fresh clean worktree from the latest reviewed integration SHA.
No stash, destructive reset, force-push, blanket checkout, or unrelated commit
is permitted. Parallelism is allowed only for plan-approved cards with
disjoint frozen production, test, fixture, export, and generated-file
allowances. A fresh Luna integration subagent integrates only after review
passes, in G0–G7 dependency order, and pushes explicitly to the execution
branch. Semantic conflicts return `JUDGMENT_REQUIRED` to Grok.

## First action: G0

Before any fetch, test, process action, paid call, or candidate/artifact write,
complete T0.0 source custody and immutable baselines. Capture refs, worktrees,
processes, interpreter/package identities, schema sources, fixture mounts,
manifests, model routes, protected state, and disposable roots. Preserve the
r5 artifacts unchanged and record only their observed disposition. G0 must
also prove the current base/remote relationship and establish safety refs for
all protected concurrent work.

After T0.0 and T0.1, T0.3 creates the receipt wrapper, evidence validator,
machine-readable manifest, and frozen test-shard manifest. Only then does T0.2
run the first Grok contract/overlap review through that wrapper. G0 does not
begin implementation cards until the independent Luna review and fresh Grok
review pass.

## Required execution sequence

1. **G0 — Freeze source, regressions, contracts, and evidence.** Complete
   T0.0, T0.1, T0.3, then T0.2; freeze the exact final-five core and the
   T0.4-amended authoritative final50 G7 manifest, preserve r5 regression
   fixtures, and pass independent Luna plus Grok gates.
2. **G1 — Canonical graph and schema context.** Implement/review immutable
   `WorkflowSnapshot` and `SchemaSnapshot`, including lossless sidecar,
   touched-only schema blocking, and no ambient replay lookup.
3. **G2 — Operation, checkpoint, and replay authority.** Implement/review one
   operation-admission gateway, closed checkpoint/typed terminal projector,
   reproducible replay, idempotency, concurrency, and crash recovery.
4. **G3 — Retry and batch-protocol boundaries.** Freeze nested retry ownership,
   deadline/attempt evidence, strict batch-fence behavior, correction limits,
   and accepted-batch authority. Luna handles ordinary retry work; Grok owns
   the XHARD protocol implementation/review.
5. **G4 — Staged/threaded observable parity.** Share typed research facts,
   graph/schema identity, accepted delta, terminal state, failure family,
   artifacts, and idempotency while retaining distinct deliberation drivers.
6. **G5 — Artifact, assessor, scenario, run isolation, and shim retirement.**
   Implement lineage manifests, canonical semantic assessment, pre-paid-call
   scenario obligations, concurrent cache/provider/session/output isolation,
   and the reviewed removal or explicit ownership of every execution-spine
   compatibility shim.
7. **G6 — Deterministic validation.** Luna freezes and runs focused shards once
   each, then owns the singleton broad suite. A fresh Grok reviews the complete
   base-to-head diff and evidence before G7.
8. **G7 — Final fifty staged plus fifty threaded.** Luna performs no-model
   preflight, one authoritative concurrent 50x2 run (100 legs, concurrency
   10 = 10 waves), and evidence assembly. Fresh Grok performs the final
   review/recommendation. No merge or promotion occurs automatically.

## Focused, batch, broad, and final-live test ownership

Implementers run only their card's focused tests. Ordinary reviewers run only
their batch shard. A dedicated Luna validator runs the frozen G6 shards once,
in order, with explicit disposable roots and source/interpreter/environment
digests. Every failure is classified with base/head evidence; introduced or
contract-drift failures block G7.

The broad suite has one atomic owner/key, `broad_suite_once_v1`, and runs only
after focused shards and before the G6 Grok review:

```bash
python -m pytest -q
```

The final fifty preflight is no-model and must validate exactly fifty entries:

```bash
python -m tests.live_agentic_harness.compare_pipeline_modes \
  --validate-only \
  --manifest tests/live_agentic_harness/threaded_comparison_manifest_final50.json
```

One dedicated Luna live-run owner invokes exactly once, with no duplicate
authoritative invocation:

```bash
python -m tests.live_agentic_harness.compare_pipeline_modes \
  --run \
  --manifest tests/live_agentic_harness/threaded_comparison_manifest_final50.json \
  --output-base "$DISPOSABLE_FINAL_OUTPUT_ROOT" \
  --tag final-50x2 \
  --concurrency 10
```

The run must submit all 100 isolated legs concurrently (10 waves of 10),
reconstruct results in manifest order, and record locked-input/schema/graph/
delta/candidate/receipt/terminal/assessment lineage, failures, retries,
latency, calls, tokens, cost, and artifact digests. The assessor must mark
all 100 required scenario legs and all 50 scenario pairs as genuine product
passes. Infrastructure completion, `undetermined`, or a synthetic/recovered
success does not satisfy G7.

## Progress record and evidence manifest

Maintain:

```text
docs/plans/workflow-execution-spine-consolidation-execution-log-2026-08-20.md
docs/plans/workflow-execution-spine-consolidation-evidence/manifest.json
docs/plans/workflow-execution-spine-consolidation-evidence/test-shards.json
```

After every card and gate, append task/gate disposition, input/output SHA,
wrapper invocation/model/PID/timestamps/exit, brief/result digests, commit and
files, tests/evidence, findings and revisions, and next unblocked card. Commit
the log at each completed batch. The machine-readable manifest is completion
authority and must validate task/gate/shard uniqueness, dependency order,
model routing, reviewer independence, finding chains, artifact digests,
singleton broad suite, final-five core integrity, final50 integrity, and
exactly 100 final leg receipts.

## Stop and escalation conditions

Stop the affected card and preserve evidence when:

- G0 cannot prove source custody, base ancestry, or final-five identity;
- a required Luna or Grok launcher remains unavailable after one retry;
- a pre-code XHARD review does not pass;
- an unresolved must finding lacks a closed revision chain;
- a card needs an authority, schema, identity, replay, retry, or compatibility
  decision absent from the plan;
- a test would write a project, candidate, source-workflow, or live-runtime
  root;
- source/schema/candidate/receipt lineage is contradictory or unverifiable;
- live protected state changes during isolated work; or
- any final50 leg is infrastructure-blocked, undetermined, falsely assessed,
  schema-unready, replay-unreproducible, or otherwise not a genuine product
  pass.

Do not weaken contracts, merge fences, infer missing evidence, substitute a
model, or count a retry as a second authoritative final run. Re-route ordinary
difficulty to the correct subagent; route every material ambiguity to Grok.

## Done when

The goal is complete only when:

- G0 through G7 have explicit passing dispositions;
- the retained `WorkflowSnapshot` and immutable `SchemaSnapshot` are the sole
  graph/schema authorities for authoring and replay;
- one operation gateway, accepted delta, closed checkpoint, replay receipt,
  and typed terminal projector govern both modes;
- retry ownership, deadlines, idempotency, crash recovery, and batch protocol
  evidence are complete and independently reviewed;
- every route has lineage-bound artifacts and the assessor uses structured
  evidence without prose or mixed-representation inference;
- every execution-spine shim is deleted, collapsed, migrated, or retained in
  a reviewed compatibility ledger with a named consumer, test, owner, and
  removal condition; no shim independently grants mutation authority; the
  repository-wide census maps every other shim to an exact structural-cleanup
  `S71`–`S77` owner for later `S78` completeness review, without falsely
  claiming those unrelated cards are complete;
- all required focused shards pass, the singleton broad suite is recorded, and
  the evidence validator exits zero;
- the exact final fifty scenarios have exactly 100 unique concurrent leg
  receipts, and all 100 are genuinely assessed product passes;
- every reviewer finding has an independent closed revision chain or Grok
  disposition;
- protected concurrent state and the canonical six-entry manifest remain
  unchanged;
- the execution branch and log are pushed explicitly; and
- a Luna report-assembly subagent reports the successor SHA, evidence manifest,
  residual risks, final50 results (with final5 first-five comparability), and
  Grok's separate merge/default recommendation. The orchestrator only relays
  that reviewed handoff.

Do not claim completion because agents returned, commits exist, tests are
green, or the 100 live processes completed. Completion means the coherent,
replayable, evidence-bound execution spine and the independently verified
fifty-plus-fifty product end-state are present.
