# Dual-mode agent executor

VibeComfy has two deliberation drivers over one authoring system:

```text
request / environment
         |
         v
   resolve mode once
      /       \
     v         v
 staged     threaded
 classify   one execute-agent conversation
 research   (no classifier call)
 implement
 reply
      \       /
       v     v
  durable agent-edit host
       |
       v
 VibeWorkflow + EditSession + canonical ops
       |
       v
 accepted delta + evidence + terminal checkpoint + UI emission
```

The mode changes deliberation only. It does not select a graph format,
mutation engine, evidence format, replay implementation, candidate lifecycle,
or response envelope.

## Modes and selection

The canonical modes are `staged` and `threaded`.

| Mode | Behavior | Intended use |
|---|---|---|
| `staged` | Classify, optionally research, optionally implement, then reply. | Default and compatibility path; explicit phase handoffs are useful for high-deliberation work. |
| `threaded` | Send the request directly to one durable execute-agent conversation. The host still controls tools, editing, validation, and the final projection. | Opt-in path for continuity and fewer orchestration handoffs. |

`run_executor()` resolves the mode exactly once, in this order:

1. `pipeline_mode` in the request;
2. `VIBECOMFY_EXECUTOR_PIPELINE_MODE` in the environment;
3. `staged`.

New callers should send only `staged` or `threaded`. The compatibility aliases
`full` -> `staged` and `two_step` -> `threaded` are accepted only while parsing
the request or environment and are immediately normalized. They are not
internal mode names. Unknown values fail as configuration/request errors;
there is no implicit `auto` mode or silent fallback.

For wire compatibility, staged responses do not gain a mode field. Threaded
responses include `report.executor.orchestration_mode = "threaded"`.

## Shared authorities

Both drivers converge on the same implementation path and must preserve these
ownership boundaries:

- `vibecomfy.executor.core.run_executor` owns mode resolution and the only
  driver dispatch branch.
- `vibecomfy.executor.threaded` owns threaded deliberation policy. It does not
  own graph state, replay, or a second edit DSL.
- `handle_agent_edit` and the ComfyUI host adapter own durable request/session
  integration, provider failure classification, usage capture, and candidate
  lifecycle.
- `VibeWorkflow` is the retained graph authority after ingress. Raw graph JSON
  is boundary evidence and emitted output, not a parallel mutable graph.
- `vibecomfy.porting.edit.EditSession` is the mutation authority. Python edits
  and typed edit tools lower to the same canonical operations and enter the
  same transactional `apply_ops()` gateway.
- The evidence ledger, rendered graph facts, reply-grounding checks, accepted
  delta, and terminal checkpoint are shared products. A driver cannot invent
  its own evidence or narrate changes outside the accepted delta.

Typed tools are deliberately thin. `typed_tools.py` validates tool-shaped
arguments, resolves visible bindings, lowers them to canonical edit ops, and
delegates to `EditSession`. Compare-and-swap revision checks and whole-batch
atomicity therefore apply equally to Python and tool-authored edits.

## Accepted work and terminal checkpoints

An accepted batch is the durable change. The terminal checkpoint:

- replays accepted history and verifies it matches the retained IR;
- derives deterministic delta IDs from canonical operations;
- freezes the result graph at a specific monotonic revision;
- records fact and evidence IDs available to the reply;
- rejects delta, fact, or evidence references that are absent from that exact
  checkpoint.

Reply projection happens after the durable implementation response closes.
If later narration or projection fails, an already accepted delta and graph
remain the authoritative result. Deterministic reply grounding replaces prose
that falsely claims an edit landed, cites nonexistent nodes, or claims beyond
the accepted change set.

No code below the orchestration seam should branch on `staged` versus
`threaded`. If a proposed change needs a mode check in edit, replay, render,
evidence, persistence, or UI emission, move the policy back into the driver.

## Continuity and recovery

Use a stable `session_id` for follow-ups in one chat window and a new ID for a
new conversation. The executor forwards that identity through the same durable
agent-edit path in both modes. The ComfyUI adapter also exposes an
orchestration-neutral transcript lifecycle; it stores messages, cumulative
budget counters, accepted delta/fact/evidence IDs, revision, and closed
checkpoints, but never a second graph body.

The durable lifecycle fails closed:

- an `expected_revision` older or newer than retained state is a stale message;
- a live per-message lease rejects a concurrent writer;
- retrying one `idempotency_key` with the same request hash replays its completed
  outcome;
- reusing that key for different input is an idempotency conflict;
- abort releases the active lease without publishing a completed turn;
- a closed session rejects further messages;
- transcript reads and appends are serialized under the shared session lock.

The HTTP route normalizes `session_id` before any durable path is allocated.
Browser recovery uses the canonical durable turn/session artifacts; it does
not reconstruct authority from transient panel state.

## Budgets

Budget values are host policy, not model suggestions.

- The general request field `max_batches` accepts integers from 1 through 250.
- Threaded mode defaults to 16 execute-agent batches.
- Threaded mode clamps any larger request to a hard production ceiling of 24.
- The threaded budget contract declares two recovery batches and one final
  projection slot as distinct purpose reserves. Final projection is not meant
  to be consumed by research.
- The shared edit kernel still enforces atomic batch and retry limits beneath
  either driver.

Do not restore the prototype's million-token, 200-call, or 20-minute limits.
Changing the production ceiling requires focused budget/recovery tests and an
operational reason, not only a model preference.

## Operator usage

Staged is the default; omitting the mode preserves existing behavior:

```json
{
  "query": "Explain this workflow",
  "session_id": "panel-4f0c"
}
```

Opt into threaded mode per request:

```json
{
  "query": "Add a preview after the decoder",
  "graph": {"nodes": [], "links": []},
  "session_id": "panel-4f0c",
  "idempotency_key": "message-0007",
  "pipeline_mode": "threaded",
  "max_batches": 16
}
```

Send that payload to `POST /vibecomfy/agent-executor`. Keep the `session_id`
stable for a follow-up and use one new `idempotency_key` per logical message.
For diagnosis or advice that must not edit, also send
`"interaction_mode": "answer_only"`; threaded mode then uses its non-editing
research capability envelope.

Headless callers can choose a process-wide mode through the environment:

```bash
VIBECOMFY_EXECUTOR_PIPELINE_MODE=threaded \
python -m vibecomfy.agent \
  --query "Inspect this workflow and make the requested safe edit" \
  --workflow ./workflow.json \
  --output-dir out/agentic/manual/threaded \
  --json
```

Prefer the request field when a process serves mixed traffic. The request value
has precedence over the environment.

## Deterministic and paired comparison

The compact comparison lane locks representative scenario descriptors, source
workflow hashes, and model-relevant inputs before comparing the two drivers.
Its CI-safe preflight makes no model calls:

```bash
python -m tests.live_agentic_harness.compare_pipeline_modes --validate-only
```

Validation checks the manifest locks, the IR projection seam, and whether the
headless adapter exposes explicit `pipeline_mode` selection. Adapter wiring is
reported as data; a live request fails before model calls when that wiring is
unavailable.

When provider readiness and adapter wiring are present, run the paired lane:

```bash
python -m tests.live_agentic_harness.compare_pipeline_modes \
  --run \
  --output-base out/compare-pipeline-modes
```

The harness gives each mode an independent copy of the same locked input. It
compares typed outcome/failure family, IR projection, canonical accepted delta,
claim/evidence integrity, latency, tokens, and estimated cost. Assistant prose
is intentionally never an equality signal. Results are written to
`comparison.json` and `comparison.md` under the selected output directory.

Treat `blocked` as an environment result, not a product pass. Evaluate results
per scenario and failure family; an aggregate win must not hide a replay,
accepted-delta, grounding, or route-family regression.

## Change checklist

Before changing either driver, verify:

1. mode aliases still disappear at ingress and staged remains the default;
2. no mode condition was added below `run_executor()` dispatch;
3. both edit surfaces produce canonical operations through `EditSession`;
4. stale, concurrent, and idempotent retries fail or replay deterministically;
5. accepted work survives later reply/projection failure;
6. claim references are present in the closed checkpoint;
7. the no-model comparison preflight passes before any paired live run.

