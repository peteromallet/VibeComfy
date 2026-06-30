# Agent Edit Validation Boundaries

## Purpose

This note describes what the agent-edit execution path validates today, what it
does not validate, and what extra checks are needed for precedent-driven
workflow edits.

## Product Path

The browser-facing product path currently uses the `batch_repl` contract:

```text
ingest_v2 -> agent_batch
```

The implementation lives in `vibecomfy/comfy_nodes/agent/edit.py`.

In this path, the model edits through `EditSession` batches and then calls
`done()`. The edit session is responsible for applying edits, rejecting invalid
statements, and validating the final candidate before the response is returned.

## Existing Structural Validation

The product path validates several important properties:

1. **Submit state is current**

   `ingest_v2` checks that the submitted graph still matches the backend
   baseline. If it does not, the turn fails with stale-state diagnostics.

2. **Edit statements must land**

   The batch loop tracks landed operations, failed operations, and query-only
   turns. It refuses premature `done()` when a search or failed edit produced no
   graph change.

3. **Candidate replay must be deterministic**

   The edit gates replay landed operations over the original graph. The
   recomputed candidate must match the session's working UI.

4. **Touched API regions must compile and compare**

   The edit gates compile the working UI and recomputed candidate to API form
   and compare the touched region for parity.

5. **Queue/apply eligibility is derived from gates**

   The response includes apply eligibility and queue blockers. Some candidates
   may be inspectable/applyable while queue remains blocked due to schema or
   confidence limits.

## Full Development Path

The older/full path is more explicit:

```text
ingest -> convert -> agent -> load_python -> lower -> validate -> emit -> summarize
```

Important validation stages:

- `load_python`: loads generated Python through the restricted generated-source
  loader.
- `lower`: lowers intent/helper constructs to a static graph.
- `validate`: calls workflow validation, schema validation when available, API
  link-shape validation, and helper diagnostics.
- `emit`: emits UI JSON and checks layout/fidelity constraints.
- `summarize`: computes queue blockers and response eligibility.

## What This Validation Proves

The current validation is strong for structural correctness:

- the graph can be represented as VibeComfy IR;
- generated/edit Python can be loaded under the expected loader;
- obvious schema and link-shape problems are caught;
- helper/lowering failures block the candidate;
- the UI candidate does not silently destroy unrelated editor state;
- apply/queue state is explicit.

## What It Does Not Prove

The current validation does not fully prove semantic task success.

It does not guarantee:

- the graph was actually run in ComfyUI;
- the graph will produce a good image/video/audio result;
- the edit matches the user's intent;
- a model-family-specific request used the right custom-node idiom;
- a precedent research result was actually followed;
- a newly added node is useful rather than merely present.

Example: a user asks to add an LTX custom-audio lipsync input. Structural
validation can prove that a candidate graph compiles and has legal links. It
does not, by itself, prove that the graph used the LTX/RuneXX custom-audio
pattern rather than an unattached generic audio loader.

## Precedent-Plan Semantic Gate

Precedent-driven edits use the shared execution-plan contract as the semantic
gate after the candidate is built. The gate is not advisory for plan-backed
turns: a blocking failed `PlanEvaluation` keeps `done()` active, feeds compact
failure guidance to the next execute turn, records artifacts, sets
`plan_validate_ok=false`, and suppresses public candidate/applyability.

Implemented output is compact status plus task-satisfaction evidence:

```json
{
  "execution_plan_status": {
    "plan_id": "plan.hotshotxl_8f.example",
    "ok": false,
    "blocking": true,
    "failed_condition_ids": ["hotshotxl.video_terminal.consumes_frames"],
    "failed_required_step_ids": ["wire-video-terminal"],
    "feedback": "plan evaluation failed: hotshotxl.video_terminal.consumes_frames."
  },
  "gates": {
    "plan_validate_ok": false
  },
  "task_satisfaction": [
    {
      "check": "execution_plan",
      "satisfaction": "fail",
      "failed_condition_ids": ["hotshotxl.video_terminal.consumes_frames"]
    }
  ]
}
```

Possible checks:

- user asked for audio input -> candidate contains an audio public input or
  audio loader;
- user asked for lipsync/custom audio -> candidate contains known audio encode
  or lipsync/custom-audio nodes;
- user asked for video edit -> candidate still contains a video output path;
- user asked for model-family-specific change -> candidate includes the
  relevant model family or custom-node pack;
- research found a precedent -> candidate contains at least one relevant
  pattern from that precedent.

Severity policy:

- hard structural failures should continue to block candidates;
- required or critical execution-plan semantic misses force another agent turn
  or block the candidate;
- low-confidence semantic misses should appear as warnings in the report.

For plan-backed HotShotXL edits, a disconnected sidecar is a semantic miss even
when the required classes are present. The active path must satisfy the plan:
HotShotXL/AnimateDiff evidence, exact frame-count evidence, decoded frame path,
and a connected video terminal. A structurally complete candidate may still
carry queue blockers; that is reported as `queue_blocked_warning` only after
`plan_validate_ok=true`.

## Relationship To Runtime Validation

Runtime validation is separate. Queueing the workflow in ComfyUI or RunPod would
catch model availability, runtime-only custom-node errors, and output-shape
issues, but it is slower and may require GPU resources.

Recommended layers:

1. Structural validation: always required before candidate response.
2. Semantic execution-plan validation: required for complex precedent-driven
   edits that carry `execution_protocol_notes.execution_plan`.
3. Runtime smoke validation: optional or explicit, especially before promoting a
   workflow to a ready template.

## Queue-Validation Anti-Scope

Queue validation is a separate layer from plan validation:

- `plan_validate_ok` answers whether the candidate structurally satisfies the
  semantic obligations in the `ExecutionPlan`.
- `queue_validate_ok` answers whether the current runtime can queue the
  workflow.
- A passed plan with queue blockers remains inspectable/applyable and reports
  `apply_eligibility.reason = "queue_blocked_warning"`.
- A failed plan is non-applyable even if queue validation would otherwise pass.

Do not move custom-node/model availability or GPU runtime checks into
`ExecutionPlan` unless they are represented as explicit, deterministic graph
obligations. Availability and execution smoke tests belong to queue/runtime
validation and rollout evidence.

## Ordinary-Route Boundary

Simple local edits do not receive execution-plan validation. Prompt, seed, CFG,
sampler-step, model-widget, simple local rewire, and simple output-node edits
route through ordinary revise behavior, bypass precedent planning, and must not
leak `execution_protocol_notes.execution_plan` or any public top-level
`execution_plan`.

This protects compatibility with direct-edit behavior and keeps the
precedent-plan gate scoped to edits that actually depend on precedent-backed
workflow semantics.

## Adding A New Pattern

When adding another precedent-backed workflow family:

1. Add routing signals for normalized `adapt` only.
2. Add builder evidence and a golden `ExecutionPlan` fixture.
3. Add evaluator expectations for complete, disconnected, missing-active-path,
   and unsupported evidence cases.
4. Add runtime tests that prove artifacts, compact feedback,
   `debug.gates.plan_validate_ok`, public response compatibility, and queue
   anti-scope.
5. Add ordinary-route bypass tests near the new vocabulary to prevent payload
   leakage.

The extension point is the existing contract/evaluator/runtime chain, not a new
semantic gate or response shape.
