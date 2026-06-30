# Precedent Plan Routing Matrix

This note documents the M2 routing behavior for precedent-backed execution
plans. M2 constructs and forwards an existing M1 `ExecutionPlan` as adapt-route
context only. It does not enforce the plan, refuse candidates, change Apply
eligibility, or block implementation.

Implementation entry points:

- `vibecomfy.executor.execution_plan_builder.needs_precedent_plan(...)`
- `vibecomfy.executor.execution_plan_builder.build_execution_plan(...)`
- `vibecomfy.executor.core._adapt_execution_plan_note(...)`
- M1 contract: `vibecomfy.comfy_nodes.agent.execution_plan.ExecutionPlan`

## Route Matrix

`needs_precedent_plan(...)` treats `ClassifyDecision.effective_route` as the
authority. Legacy booleans and stale classifier metadata do not override the
normalized route.

| Effective route | Can trigger M2 plan construction? | Behavior |
|---|---:|---|
| `adapt` | Yes, when a qualifying signal is present | Research-backed graph edit path. After adapt research, M2 may build an M1 `ExecutionPlan` and place it under `execution_protocol_notes.execution_plan`. |
| `revise` | No | Local graph edit path. Bypasses precedent planning even if stale fields mention research, precedents, templates, or external technologies. |
| `respond` | No | Direct answer path. No research, implementation, or execution-plan context. |
| `inspect` | No | Graph inspection path. No outside precedent planning. |
| `research` | No | Research answer path. It may research workflows or nodes, but it does not build an implementation execution plan because there is no adapt candidate path in M2. |
| `clarify` | No | Clarifying-question path. No plan construction. |
| `requires_custom_nodes` | No as an effective route | The classifier normalizer rewrites this legacy/install-intent route to an executable route (`adapt`, `research`, or `respond`) before M2 routing. Only a normalized `adapt` result can qualify. |
| Any other or blank route | No | Unknown or blank routes fail closed outside the precedent-plan path. |

Legacy aliases are evaluated after normalization:

- `precedent_research` normalizes to `adapt`, so it can qualify when signals are
  present.
- `direct_edit` and `diagnose_repair` normalize to `revise`, so they bypass
  planning.
- `inspect_only` normalizes to `inspect`, so it bypasses planning.

## Adapt Signals

An `adapt` route qualifies for M2 planning when any signal source says the turn
is precedent-backed, template-backed, external-workflow-backed, custom-node
backed, or names a known external workflow technology.

Signal sources include:

- the user task/query passed to `needs_precedent_plan(...)`;
- classifier text fields such as `plan_summary`, `research_goal`,
  `known_graph_context`, `pattern_category`, `change_goal`, and `task`;
- classifier sequence fields such as `search_directions`,
  `source_preferences`, `model_families`, and `avoid`;
- optional `GraphFacts` fields such as `unknown_class_types`,
  `missing_node_packs`, `missing_models`, `socket_type_mismatches`,
  `missing_required_inputs`, `current_output_node_types`,
  `terminal_output_socket_types`, `readiness_blockers`, and `summary`.

Planning vocabulary includes terms like:

- `precedent`, `template`, `workflow`, `community example`, `example`, and
  `reference workflow`;
- `custom node` or `custom-node`;
- `external workflow` or `external-workflow`.

Known named-technology signals are currently:

- `HotShotXL`
- `Wan`
- `LTX`
- `AnimateDiff`
- `IPAdapter`
- `ControlNet`

User-named technologies are preserved as planning signals even when the current
graph does not already contain those node classes. The classifier prompt should
avoid inventing unrelated ecosystems, but it must not erase an ecosystem the
user explicitly named.

## Simple Local Edit Bypass

Simple local edits stay out of precedent planning. The effective route normally
lands as `revise`; even if such a turn is mislabeled `adapt`, it does not
qualify unless one of the adapt signals above is present.

Examples that bypass M2 planning:

- changing prompt text;
- setting a seed;
- adjusting CFG, sampler steps, sampler name, scheduler, or denoise;
- switching an existing checkpoint/model widget;
- rewiring an existing local VAE decode path;
- adding a simple local terminal such as `SaveImage`.

The bypass rule protects direct-edit latency and prevents research/planning
context from changing ordinary local graph edits.

## Current Builder Coverage

M2 routing decides whether planning should be attempted. The builder still may
return `None` when the available evidence is unsupported or insufficient.

The current deterministic builder emits a plan only for a narrow pattern:

- HotShotXL is named or evidenced;
- the target domain is video;
- the task or selected precedent establishes exactly 8 frames;
- research evidence can normalize the HotShotXL/AnimateDiff video spine.

The emitted plan uses the M1 `ExecutionPlan` contract. It includes stable
`RoleBinding`, `PlanStep`, `done_conditions`, `active_path_conditions`, and
`blocked_if` entries for:

- HotShotXL motion model presence;
- AnimateDiff context presence and motion-model wiring;
- sampler consumption of the AnimateDiff-wrapped model path;
- active 8-frame latent path;
- decoded frame path;
- video terminal consumption;
- active video output domain;
- blocked active still-image terminal output.

Unsupported evidence, such as Wan video or non-8-frame HotShotXL, returns
`None` and leaves the adapt payload otherwise unchanged.

## Serialization Location

When a qualifying adapt turn produces a plan, M2 serializes it at:

```json
{
  "execution_protocol_notes": {
    "execution_plan": {
      "plan": {
        "contract_version": "execution_plan_v1"
      },
      "provenance": {
        "builder": "vibecomfy.executor.execution_plan_builder.build_execution_plan",
        "routing": "vibecomfy.executor.execution_plan_builder.needs_precedent_plan",
        "phase": "m2_adapt_context",
        "enforced": false
      }
    }
  }
}
```

The plan is not copied to a top-level `execution_plan` key. It remains nested
with other discardable adapt research context under `execution_protocol_notes`.

If planning is not needed, unsupported, or the builder raises an internal
exception, M2 omits `execution_protocol_notes.execution_plan` and continues the
existing adapt implementation path.

## Unresolved Binding Serialization

Role bindings are explicit about what is known from the current graph:

| Current graph evidence | Binding confidence | Serialized reference |
|---|---|---|
| No current graph was supplied | `planned` | Semantic `SocketRef` with `role` and `class_type`; no node id. |
| Exactly one current graph node matches the role class | `high` | Concrete `SocketRef` with `node_id`, `role`, and `class_type`. |
| More than one node matches the role class | `low` | Semantic `SocketRef` with `role` and `class_type`; evidence includes candidates and ambiguity. |
| No node matches a required role class | `blocked` | Semantic `SocketRef` with `role` and `class_type`; evidence explains that no candidate matched. |

Conditions also use semantic `SocketRef(role=...)` references when a concrete
node id is unknown or ambiguous. M2 must not guess active-path node ids for
sampler, decoder, latent, or terminal roles.

Unresolved schema or role evidence is serialized in role evidence and normalized
plan provenance. It is visible to later evaluators instead of being hidden or
converted into a hard M2 stop.

## Schema And Runtime Provenance

Schema availability and runtime availability are provenance in M2, not hard
planning blockers.

Schema provenance records whether a role class schema came from precedent
workflow evidence or was `not_available`. Runtime provenance records whether
current graph facts reported a class as present, unknown, not reported, or not
checked. Plan steps carry these values through `schema_source` and
`runtime_availability`.

This means M2 can still construct a deterministic plan when local schema or
runtime facts are incomplete. Missing schema/runtime information should be
treated as evidence for M3 enforcement and refusal decisions, not as a reason
for M2 to skip all planning.

## M3 Boundary

M2 is an adapt-context bridge:

- it may provide a serialized M1 execution plan;
- it marks the plan provenance as `enforced: false`;
- it does not call `evaluate_execution_plan(...)` as an Apply gate;
- it does not block `handle_agent_edit(...)`;
- it does not change candidate creation, Apply eligibility, queue eligibility,
  or refusal behavior.

M3 owns enforcement. That later milestone should evaluate candidate graphs
against the plan, decide which unsatisfied conditions are blocking, and define
refusal or retry behavior for failed precedent-plan obligations.
