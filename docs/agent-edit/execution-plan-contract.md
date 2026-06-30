# Execution Plan Contract

This note documents the execution-plan contract implemented at:

```python
from vibecomfy.comfy_nodes.agent.execution_plan import (
    ExecutionPlan,
    PlanCondition,
    PlanEvaluation,
    PlanStep,
    RoleBinding,
    SocketRef,
    evaluate_execution_plan,
)
```

The module is the pure contract and evaluator surface. Routing, runtime
hydration, prompt retry feedback, artifact persistence, and Apply eligibility
are documented here only as consumers of this contract; they must not introduce
a parallel plan or evaluation shape.

## Public Surface

The public import path is
`vibecomfy.comfy_nodes.agent.execution_plan`. The exported constants and helpers
define the current v1 contract:

- `EXECUTION_PLAN_CONTRACT_VERSION = "execution_plan_v1"`
- `PLAN_EVALUATION_CONTRACT_VERSION = "plan_evaluation_v1"`
- `SUPPORTED_EXECUTION_PLAN_CONTRACT_VERSIONS`
- `SUPPORTED_PLAN_EVALUATION_CONTRACT_VERSIONS`
- `SUPPORTED_CONDITION_KINDS`
- `execution_plan_version_status()`
- `plan_evaluation_version_status()`
- `is_supported_execution_plan_version()`
- `is_supported_plan_evaluation_version()`
- `fail_closed_if_unsupported_plan_version()`
- `fail_closed_if_unsupported_evaluation_version()`
- `fail_closed_evaluation_for_plan_version()`
- `fail_closed_evaluation_for_evaluation_version()`
- `evaluate_execution_plan()`

All contract dataclasses are frozen. Mapping fields are recursively frozen on
construction, tuple-like values are normalized, and `to_dict()` returns
deterministic JSON-safe dictionaries with tuple values thawed as JSON arrays.
Mapping keys are serialized in stable string order.

## Dataclasses

### `SocketRef`

Stable-ish reference to a graph node socket or input. All fields are optional:

- `node_id`
- `uid`
- `var`
- `class_type`
- `socket`
- `input_name`
- `output_name`
- `index`
- `role`

`SocketRef.to_dict()` omits fields whose value is `None`.

### `RoleBinding`

Binding from a semantic plan role to an observed graph node:

- `role`
- `node_ref`
- `class_type`
- `confidence`
- `evidence`

`RoleBinding.to_dict()` emits:

```json
{
  "role": "video_terminal",
  "node_ref": {"node_id": "15", "class_type": "VHS_VideoCombine"},
  "class_type": "VHS_VideoCombine",
  "confidence": "high",
  "evidence": {}
}
```

Fields with `None` values are omitted.

### `PlanCondition`

Evaluator obligation attached to a plan or step:

- `condition_id`
- `kind`
- `criticality`
- `source`
- `target`
- `expected`
- `class_type`
- `input_name`
- `message`
- `details`

`PlanCondition.to_dict()` emits `condition_id` as `id`:

```json
{
  "id": "video.terminal.consumes_decoded_frames",
  "kind": "terminal_consumes",
  "criticality": "required",
  "source": {"node_id": "14", "class_type": "VAEDecode"},
  "target": {"node_id": "15", "class_type": "VHS_VideoCombine"},
  "input_name": "images",
  "message": "A connected video terminal must consume decoded frames.",
  "details": {}
}
```

`PlanCondition.is_required` is true for `required` and `critical`.
`PlanCondition.supported_kind` is true only when `kind` is in
`SUPPORTED_CONDITION_KINDS`.

### `PlanStep`

Authored action or obligation in an execution plan:

- `step_id`
- `kind`
- `criticality`
- `status`
- `class_type`
- `assign_to`
- `schema_source`
- `runtime_availability`
- `inputs`
- `values`
- `conditions`
- `evidence_refs`

`PlanStep.to_dict()` emits `step_id` as `id`:

```json
{
  "id": "S1",
  "kind": "add_node",
  "criticality": "required",
  "status": "planned",
  "class_type": "HotshotXLLoader",
  "assign_to": "hotshot",
  "schema_source": "object_info",
  "runtime_availability": "available",
  "inputs": {},
  "values": {},
  "conditions": [],
  "evidence_refs": []
}
```

`PlanStep.is_required` is true for `required` and `critical`.

### `ExecutionPlan`

Authoritative structural obligations for a candidate graph edit:

- `contract_version`
- `plan_id`
- `goal`
- `source_graph_hash`
- `candidate_graph_hash`
- `research_result_hash`
- `selected_precedent_id`
- `selected_precedent`
- `role_bindings`
- `required_steps`
- `done_conditions`
- `active_path_conditions`
- `blocked_if`
- `schema_provenance`
- `runtime_provenance`

`ExecutionPlan.to_dict()` always emits the full top-level shape, including
`None` hash/provenance identifiers:

```json
{
  "contract_version": "execution_plan_v1",
  "plan_id": "hotshotxl-video",
  "goal": "Generate an active 8-frame HotShotXL video output.",
  "source_graph_hash": null,
  "candidate_graph_hash": null,
  "research_result_hash": null,
  "selected_precedent_id": "precedent-hotshotxl-8f",
  "selected_precedent": {},
  "role_bindings": [],
  "required_steps": [],
  "done_conditions": [],
  "active_path_conditions": [],
  "blocked_if": [],
  "schema_provenance": {},
  "runtime_provenance": {}
}
```

`ExecutionPlan.supported_contract_version` reports whether the plan version is
supported. `ExecutionPlan.fail_closed_evaluation()` returns the same blocking
result as `fail_closed_evaluation_for_plan_version()`.

### `PlanEvaluation`

Deterministic result from checking a candidate graph against a plan:

- `contract_version`
- `plan_id`
- `ok`
- `blocking`
- `source_graph_hash`
- `candidate_graph_hash`
- `selected_precedent_id`
- `step_status`
- `failed_conditions`
- `feedback`
- `schema_provenance`
- `runtime_provenance`

`PlanEvaluation.to_dict()` always emits the full top-level shape:

```json
{
  "contract_version": "plan_evaluation_v1",
  "plan_id": "hotshotxl-video",
  "ok": false,
  "blocking": true,
  "source_graph_hash": null,
  "candidate_graph_hash": "candidate-hash",
  "selected_precedent_id": "precedent-hotshotxl-8f",
  "step_status": [],
  "failed_conditions": [],
  "feedback": "plan evaluation failed: video.terminal.consumes_decoded_frames.",
  "schema_provenance": {},
  "runtime_provenance": {}
}
```

`PlanEvaluation.supported_contract_version` reports whether the evaluation
version is supported. `PlanEvaluation.fail_closed_if_unsupported_version()`
returns the evaluation unchanged when supported, otherwise a current-version
blocking replacement.

## Supported Condition Kinds

`evaluate_execution_plan()` supports these condition kinds:

- `required_class`: at least one matching class exists, or `details.min_count`
  matching classes exist. The expected class comes from `class_type`, `expected`,
  `details.class_type`, or `details.classes`.
- `required_value`: a matching node has a widget value equal to `expected`, or
  within an expected `{ "min": ..., "max": ... }` range. Field names can come
  from `input_name`, `details.field`, `details.input`, `details.widget`,
  `details.value_name`, `details.fields`, `details.inputs`,
  `details.widgets`, or the same keys inside an expected mapping.
- `direct_edge`: a direct graph edge exists from `source` to `target`, with
  optional socket/input matching.
- `reachable_path`: `target` is reachable from `source` through graph edges.
- `direct_edge_or_reachable_path`: either `direct_edge` or `reachable_path` is
  satisfied.
- `terminal_consumes`: a terminal node consumes any input, or consumes a path
  reachable from `source`; `target`, `class_type`, and `input_name` can narrow
  which terminal and input must be used.
- `active_output_domain`: an active terminal exists for the expected domain,
  such as `VIDEO`, `IMAGE`, or `AUDIO`.
- `unconsumed_functional_outputs`: matching non-terminal nodes with output slots
  must have no more than the allowed count of unconsumed outputs. The allowed
  count comes from `details.max_count` or integer `expected`, defaulting to `0`.
- `batch_frame_count`: a matching node has the expected frame or batch count.
  Default field candidates include `amount`, `batch_size`, `context_length`,
  `frame_count`, `frame_load_cap`, `frames`, `frames_number`, `length`, and
  `num_frames`.
- `value_or_path_count`: currently evaluated with the same implementation as
  `batch_frame_count`.

Unsupported condition kinds fail closed. The evaluator records a failed
condition with critical severity and includes the supported kind list as
evidence. Unsupported `blocked_if` condition kinds also fail closed.

## Evaluator API

The evaluator signature is:

```python
evaluate_execution_plan(
    graph,
    plan,
    *,
    candidate_graph_hash=None,
) -> PlanEvaluation
```

`graph` is a Comfy/LiteGraph-shaped mapping. `plan` may be an `ExecutionPlan` or
a compatible mapping. The evaluator is pure and deterministic: it reads graph
evidence through `vibecomfy.executor.graph_inspection.inspect_graph()` and uses
the structural graph hash semantics from
`vibecomfy.comfy_nodes.agent.session.structural_graph_hash()`.

Evaluation order:

1. Fail closed immediately if the plan contract version is unsupported, newer,
   or ambiguous.
2. Inspect the graph and compute the structural graph hash.
3. If a `candidate_graph_hash` argument is supplied and does not match the
   computed structural hash, add a critical
   `candidate_structural_graph_hash` failure.
4. If the plan contains `candidate_graph_hash` and it does not match the
   evaluated graph hash, add a critical
   `plan_candidate_structural_graph_hash` failure.
5. Evaluate `done_conditions`, `active_path_conditions`, and all required-step
   conditions.
6. Evaluate `blocked_if` conditions as inverse gates: if such a condition is
   satisfied, it becomes a failure.
7. Build `step_status` from each step's conditions.

The returned `PlanEvaluation` has:

- `ok = True` only when there are no failed conditions.
- `blocking = True` when any failure has `critical` or `required` severity.
- `feedback = "plan evaluation passed."` on success.
- `feedback = "plan evaluation failed: <condition ids>."` on failure.
- `runtime_provenance.evaluator = "evaluate_execution_plan"`.
- `runtime_provenance.graph_inspection.node_count` and `edge_count`.
- `runtime_provenance.structural_graph_hash_version`.

## Fail-Closed Version Behavior

Only `execution_plan_v1` and `plan_evaluation_v1` are supported in M1.

Version helpers classify contract strings as:

- `supported`
- `newer`
- `unsupported`
- `ambiguous`

Any unknown newer, unsupported, missing, or malformed execution-plan version
blocks evaluation through a `PlanEvaluation` with:

- `ok = False`
- `blocking = True`
- `failed_conditions[0].condition_id = "execution_plan_contract_version"`
- `failed_conditions[0].severity = "critical"`
- `feedback = "plan evaluation blocked: unsupported execution plan contract version."`

Any unknown newer, unsupported, missing, or malformed plan-evaluation version is
converted to a current-version blocking result with:

- `ok = False`
- `blocking = True`
- `failed_conditions[0].condition_id = "plan_evaluation_contract_version"`
- `failed_conditions[0].severity = "critical"`
- `feedback = "plan evaluation blocked: unsupported plan evaluation contract version."`

This fail-closed behavior is intentional: a later contract version must not be
treated as applyable or complete by an older M1 evaluator.

## HotShotXL Connected-Path Obligation

The M1 HotShotXL obligation is structural. A candidate is not sufficient merely
because HotShotXL or AnimateDiff nodes exist somewhere on the canvas. The active
video-producing path must be connected end to end:

- `HotshotXLLoader` is present.
- `ADE_AnimateDiffLoaderWithContext` is present.
- The active latent path has exact 8-frame evidence.
- The HotShotXL/AnimateDiff path reaches a `VHS_VideoCombine` terminal.
- The `VHS_VideoCombine` terminal consumes decoded frames through its `images`
  input.
- The active terminal output domain is `VIDEO`.

Disconnected sidecars fail even if the sidecar contains recognizable HotShotXL
or AnimateDiff classes. An 8-frame latent that is not on the active video path
does not satisfy the obligation. A path that ends in an image terminal instead
of connected `VHS_VideoCombine` does not satisfy the obligation.

## Runtime Enforcement Boundary

The runtime accepts an execution plan only from the nested executor payload:

```json
{
  "execution_protocol_notes": {
    "execution_plan": {
      "plan": {"contract_version": "execution_plan_v1"},
      "provenance": {
        "phase": "m3_execute_enforcement",
        "enforced": true
      }
    }
  }
}
```

`execution_protocol_notes.execution_plan.plan` is hydrated into
`AgentEditState.execution_plan`, persisted as
`turns/<turn_id>/execution_plan.json`, evaluated against the current candidate
graph, and persisted as `turns/<turn_id>/plan_evaluation.json`. The public
response never exposes a top-level `execution_plan` payload.

When a plan-backed turn calls `done()`, the latest candidate is reevaluated. A
blocking failed `PlanEvaluation` refuses `done()` and feeds the model compact
plan feedback on the next execute turn only while the plan-backed turn remains
active. The prompt block is headed:

```text
Execution plan status (authoritative compact JSON):
```

The compact status is derived from `format_compact_plan_status(...)` and carries
only the stable retry fields: plan id, ok/blocking booleans, failed condition
ids, failed required step ids, and evaluator feedback. It is not a second
contract and it is not sent for non-plan prompts.

## Artifact And Debug Fields

Plan artifacts are durable evidence, not public plan payloads:

- `artifacts.execution_plan`: string path to `execution_plan.json`.
- `artifacts.plan_evaluation`: string path to `plan_evaluation.json`.
- `debug.execution_plan_artifacts.execution_plan`: artifact ref with path,
  sha256, and byte count when available.
- `debug.execution_plan_artifacts.plan_evaluation`: artifact ref with path,
  sha256, and byte count when available.
- `debug.gates.plan_validate_ok`: mirrors the public gate snapshot.

These fields may be used for diagnostics, chat/session rehydration, and rollout
evidence. Callers must not treat them as a replacement for the nested executor
payload or as permission to pass a top-level `execution_plan` through the public
response.

## Extension Guidance

To add a new precedent-backed pattern, extend the existing surfaces in order:

1. Teach `needs_precedent_plan(...)` to recognize the route signal only when the
   normalized route is `adapt`.
2. Add deterministic builder evidence in
   `vibecomfy.executor.execution_plan_builder.build_execution_plan(...)`.
3. Add or update golden plan fixtures under `tests/fixtures/execution_plans/`.
4. Add evaluator conditions using existing `PlanCondition` kinds where possible;
   if a new condition kind is required, add it to `SUPPORTED_CONDITION_KINDS`,
   document it here, and cover pass/fail/unsupported behavior.
5. Add runtime fixture coverage for connected-path pass, disconnected sidecar
   fail, artifact persistence, compact feedback, and `plan_validate_ok`.
6. Verify ordinary prompt/seed/CFG/sampler/model/rewire/output-node revise
   routes still bypass planning and do not leak nested execution-plan payloads.

Do not add a special-case Apply gate for a new pattern. New patterns must feed
the same `ExecutionPlan` -> `PlanEvaluation` -> `plan_validate_ok` chain.

## Contract Boundary

The contract module stops at public dataclasses, deterministic `to_dict()`
serialization, pure evaluator primitives, and fail-closed version behavior.

The contract module intentionally leaves these surfaces to runtime consumers:

- Classifier behavior.
- Research routing.
- Execute prompt content and model instructions.
- Runtime `done()` retry/refusal behavior.
- Runtime Apply gates and Apply eligibility.
- Candidate and evaluation artifact persistence.
- Frontend display or Apply behavior.

Those consumers must use `ExecutionPlan` and `PlanEvaluation` as the single
semantic authority. A newer milestone may add more patterns or condition kinds,
but it should not create a second plan contract, a second evaluation contract,
or a route-specific Apply semantics surface.
