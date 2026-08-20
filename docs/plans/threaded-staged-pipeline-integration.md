# Threaded + staged agent pipeline integration plan

## Outcome

Ship two deliberation drivers over one execution kernel:

```text
raw UI / API / envelope
          |
          v
   named ingest door
          |
          v
 VibeWorkflow + revision
          |
          +-----------------------+
          |                       |
          v                       v
 staged driver              threaded driver
 classify -> research       one durable execute-agent
 -> implement -> reply      conversation across follow-ups
          |                       |
          +-----------+-----------+
                      |
                      v
 shared render / tools / evidence / EditSession / validation
                      |
                      v
       accepted batch + reply + closed-turn checkpoint
                      |
                      v
              durable apply + emit_ui_json
```

The mode chooses deliberation only. It must not choose a graph representation,
mutation engine, replay implementation, evidence format, candidate lifecycle, or
response envelope.

Use `main` as the eventual merge target, but use `ir-everywhere` as the semantic
foundation. Keep the staged driver as the default and call the additional mode
`threaded`; `two_step` no longer describes the implemented behavior after commit
`1fe948a8` removed its classifier call.

## Source state and merge decision

| Source | Tip at planning time | Role |
| --- | --- | --- |
| `main` | `79fdc18e` | Eventual target; four commits not in either feature branch |
| `ir-everywhere` | `85a3cda0` | Shared IR and strongest staged architecture |
| `two-step-megado` | `2d105859` | Threaded prototype and experimental evidence |
| `sol3-improvements` | `b3c6d466` | Ancestor/control only; no unique work to merge |

`ir-everywhere` and `two-step-megado` diverged after `c8407a8e`: the former has
52 unique commits and the latter 48. A synthetic merge has seven direct textual
conflict files and materially more semantic conflicts in `core.py`, contracts,
the provider/backend, render/emit, profiles, and test contracts. Therefore:

- Do not merge or rebase `two-step-megado` wholesale.
- Merge `ir-everywhere` first.
- Port the final threaded invariants and focused tests onto that substrate.
- Treat experiment configuration, findings, and dirty research changes as
  separate evidence, not production code.

## Architectural laws

1. **One graph authority.** After named ingest, only `VibeWorkflow` may represent
   the working graph. Raw JSON is immutable ingress/egress evidence.
2. **One edit authority.** Every authoring surface lowers to canonical ops and
   advances the graph through the same transactional `EditSession` gateway.
3. **One accepted delta.** The accepted batch is the durable delta. Reply, judge,
   replay, result graph, and emitted UI must describe the same closed checkpoint.
4. **One renderer.** Census, surface, topology, diff, and judge lenses come from
   the shared renderer; judge visibility is a subset of reply visibility.
5. **One tool/evidence authority.** Both drivers use the same tool registry,
   typed evidence ledger, server-side artifact bodies, and exact claim-reference
   validation.
6. **One durable lifecycle.** Existing session, lease, idempotency, stale-turn,
   candidate, accept/reject, and frontend rehydration owners remain authoritative.
7. **No mode leakage below orchestration.** Render, edit, validate, replay, emit,
   and persistence code must not branch on staged versus threaded.
8. **Threaded is a bounded agent loop, not a single inference.** Post-edit prose
   is generated only after the host accepts the delta and returns post-edit facts.
9. **Self-assessment is never authority.** Deterministic validation is mandatory;
   semantic judging remains independent where policy requires it.

## Ownership map

| Concern | Owner after integration | Rule |
| --- | --- | --- |
| Mode selection and dispatch | `executor/core.py` | One dispatch seam only |
| Shared per-request state | Small `ExecutionContext` value | IR, revision, tools, evidence, profile, telemetry |
| Staged deliberation | Existing staged functions/driver | Preserve typed stage handoffs |
| Threaded deliberation | `executor/threaded.py` | Continuation policy only; no graph/replay implementation |
| Durable thread transcript | Existing agent session/turn store | Extend it; do not create a second `two_step_*` store |
| Editing | `porting/edit` + `EditSession` | All frontends lower to canonical ops |
| Rendering and facts | `porting/render.py` | Shared lenses and fact IDs |
| Emission | `porting/emit/ui.py` | Pure exit door |
| Tools and evidence | `executor/tool_specs.py` + shared ledger | Registration once, host-enforced capabilities |
| Public result | Existing `ExecutorResult`/durable response | Add mode metadata; no parallel response type |

Avoid a framework-heavy class hierarchy. A shared immutable context plus two
runner functions (or a tiny strategy protocol) is sufficient.

## Integration sequence

### M0 - Preserve every source exactly

Before integration work:

1. Record current tips and diff fingerprints again; the live checkout is active
   and may have changed since this plan was written.
2. Snapshot the six-file dirty payload in `/private/tmp/vc-twostep` into a
   separate safety ref without altering that live worktree. Its planning-time
   tracked-diff fingerprint was `50e345021cf6c19217474a4cfa6caf3f60b5307a`.
3. Snapshot the current checkout's tracked and untracked work separately using a
   scratch worktree; verify its original diff fingerprint and untracked list are
   byte-identical afterward.
4. Push `ir-everywhere`, `two-step-megado`, and both safety refs. Neither feature
   tip currently has a known remote containment ref.
5. Archive the fixed manifests, classification locks, benchmark results, and
   original one-step prompt as comparison evidence.

Gate M0: every source is recoverable from a pushed ref, and both live dirty
worktrees retain their exact pre-snapshot fingerprints.

### M1 - Establish the IR foundation on a clean integration branch

Create `integrate/ir-threaded` from `main`, then merge `ir-everywhere` intact.
Resolve conflicts in favor of the IR architecture while retaining newer main
behavior. Port the four main-only commits explicitly where the merge does not
already preserve them.

Before threaded code is introduced, prove:

- exactly one named ingest and retained `VibeWorkflow`;
- untouched UI byte fidelity at the exit;
- copy-on-write transactional interpretation;
- canonical accepted-batch replay and rollback;
- deterministic surface/topology/diff rendering;
- staged reply/judge lens symmetry;
- the staged pipeline is behaviorally unchanged.

Gate/rollback R1: IR laws, boundary KPI, ingest/emit corpus, edit-session/replay,
and the full practical suite are green. Tag or checkpoint this coherent state.

### M2 - Reconcile the active current-checkout work

Semantically port the current dirty work onto R1 in independent slices:

1. durable session recovery, leases, idempotency, and frontend rehydration;
2. research reliability, truthful attempt/exhaustion status, evidence retention,
   and durable research traces;
3. unrelated ControlNet/conversion changes;
4. profile changes only where they differ from the IR tip.

Do not blanket-apply the dirty diff: its highest-conflict files are precisely the
new shared seams. Each slice must have its focused tests and its own revert point.

Gate M2: staged behavior remains green and the current dirty source has an
explicit landed/deferred verdict for every path.

### M3 - Add a no-op orchestration seam

Introduce the canonical mode names `staged` and `threaded`, with `staged` as the
default. If an already-shipped caller requires compatibility, accept `full` and
`two_step` only at request/config parsing and immediately normalize them; do not
let aliases enter internal code.

Add only:

- request/config resolution;
- a single dispatch seam in `core.py`;
- mode-specific profile selection;
- additive report/profiler metadata;
- lifecycle events without changing staged event bytes.

The threaded runner may return a typed not-enabled result at this milestone.
Port concepts from `f5a45561` and `e719b8af`; do not cherry-pick the commits.

Gate M3: staged tests and serialized payload/event fixtures are byte-compatible.

### M4 - Create one shared edit and terminal-product kernel

Before adding the threaded loop, extract the prototype's reusable mechanics:

- typed tool calls and Python batches lower to the same canonical op batch;
- one transactional apply gateway enforces CAS, channels, types, bounds, and
  whole-batch atomicity;
- canonical replay lives in the shared edit layer, not in a thread store;
- accepted delta is persisted before derived sidecars;
- terminal projection reads one closed checkpoint and preserves accepted work
  even when a later continuation, reply, or validation step fails;
- exact delta/fact/evidence claim references are validated against that checkpoint.

Use the behavioral lessons from `e474ad69`, `3c8583cd`, `bcf92497`, `99d9ca18`,
`db80b52e`, `34a48964`, and `7f332f59`, but keep only failures reproducible on
the new IR substrate.

Do not port `executor/edit_tools.py` as a second mutation engine. If typed edit
tools remain useful, move their schema-to-op lowering into a thin shared adapter
under `porting/edit` and feed the same `EditSession` gateway.

Gate/rollback R2: Python and typed-tool inputs representing the same edit yield
identical canonical ops, `pi_edit(post)`, replayed IR, and UI. Stale, forged,
unknown-schema, mixed-validity, and wrong-channel cases fail closed.

### M5 - Add the threaded driver over the shared kernel

Re-port the useful behavior from `two_step.py` and `two_step_session.py` as a
thin `threaded.py` driver plus extensions to the existing durable turn store.

Preserve:

- one agent conversation identity per chat-window session;
- same-window follow-up continuity and new-window isolation;
- transcript-authoritative user/agent/tool history;
- accumulated accepted-delta, fact, and evidence references;
- per-message budgets plus cumulative session ceilings;
- separate research, edit/recovery, and final-reply continuation reserves;
- stale/concurrent request detection and idempotent replay;
- one atomic edit plus at most one model-authored replacement;
- post-acceptance reply and self-contained final-message semantics;
- closed-turn terminal checkpoint projection.

Do not preserve:

- the duplicate graph/replay implementation in `two_step_session.py`;
- obsolete eight-route/classifier scaffolding after `1fe948a8`;
- global model substitutions from `7199507c`;
- the experimental 1M-token, 200-call, 20-minute limits from `c1a3c842`;
- a separate `TwoStepExecutionReport` or `two_step_*` artifact universe.

Use one shared capability broker. In threaded mode the agent may choose its
intent within a hard host allowlist, but tool admission and budgets remain host
authority. Do not advertise tools that dispatch will deny.

Gate/rollback R3: continuity, new-window isolation, cumulative budgets,
stale/concurrent/idempotent turns, atomic zero-delta failure, accepted-delta on
post-edit failure, checkpoint isolation, replay fidelity, and claim-grounding
tests are green.

### M6 - Make the drivers cooperate without becoming two writers

Initially, mode is immutable within a chat thread and selection is explicit.
Do not add an `auto` mode until paired evidence supports a routing policy.

Define a future-compatible handoff envelope now:

- thread/session id;
- current workflow revision;
- accepted delta ids;
- evidence ledger ids;
- current user request and unresolved reason;
- no mutable graph body outside the shared IR authority.

A later threaded-to-staged escalation may occur only at a revision-bearing,
pre-mutation boundary or after a fully closed checkpoint. It must be explicit,
recorded, and idempotent. Never silently fall back, run both drivers against the
same open turn, or let two writers race.

Gate R4: the staged and threaded drivers can consume the same fixture context
and produce the same public envelope without mode checks below orchestration.

### M7 - Differential proof and rollout

Port and simplify the highest-value prototype tests and comparator assets:

- identical locked inputs for both drivers;
- compare `pi_edit(post)`, canonical delta replay, judge outcome, evidence and
  claim correctness, failure family, latency, tokens, and cost;
- never require prose equality;
- retain the original 30-case lane and its R11 regression/flips as historical
  checks, then add the IR-everywhere fixed lane;
- repeat live paired runs at least three times to distinguish durable changes
  from model variance.

Release gates:

1. Deterministic suites: 100% green, no integrity xfails or quarantines.
2. Staged compatibility: no deterministic or fixed-lane regression; staged
   remains the default.
3. Threaded preservation: at least the prototype's 13/30 R11 result and its ten
   durable flips, with no replay, claim, or accepted-delta integrity failure.
4. Eligibility: threaded must be non-inferior by route/failure family before a
   route is enabled; aggregate pass rate must not hide a family regression.
5. Operations: acceptable unsupported-claim, replacement, budget-exhaustion,
   latency/cost, and same-session reuse metrics.

Roll out default-off in this order:

1. `respond` and `inspect`;
2. simple named-field `revise` and deterministic `reorganise`;
3. bounded `research`;
4. structural/adaptive edits only after route-family non-inferiority.

Keep staged available as the explicit high-deliberation path throughout.

## Risk register

| Risk | Mitigation |
| --- | --- |
| Clean textual merge hides semantic split-brain | Re-port invariants; enforce ownership tests |
| Thread store becomes a second graph authority | Persist ids/revisions/transcript only; replay in shared edit layer |
| Typed tools become a second mutation DSL | Lower to canonical ops at one shared adapter |
| Accepted edit is lost after later failure | Persist accepted delta first; terminal projector reads closed checkpoint |
| Threaded prompt receives an unsafe union tool surface | Shared capability broker with dispatch-enforced allowlists and budgets |
| Staged regressions are masked by new fixtures | Preserve byte fixtures and locked pre-integration baselines |
| Model variance looks like an architectural win | Three paired runs and per-family analysis |
| Active dirty work is overwritten | Scratch-worktree snapshots, fingerprints, and path-level landing ledger |
| Experimental evidence-id relaxation weakens grounding | Review the six-file dirty Hivemind payload separately; exact ids by default |

## Definition of done

- Both modes run from one clean integration branch and one shared IR/edit/emit
  kernel.
- No graph, replay, evidence, response, or durable-candidate authority is
  duplicated by the threaded mode.
- Staged behavior remains the default and has no compatibility regression.
- Threaded follow-ups reuse one durable agent conversation and cannot claim or
  lose edits outside a closed accepted-delta checkpoint.
- The full deterministic suite and repeated paired live gates pass.
- Every dirty/source payload has a landed, archived, deferred, or rejected
  verdict, and all retained work is pushed before source worktrees are removed.
