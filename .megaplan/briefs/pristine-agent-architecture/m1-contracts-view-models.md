# M1: Canonical Contracts And View Models

## Outcome

Make the core agent panel concepts have one canonical contract each: `StageSnapshot`, `ApplyCandidate`, `FieldChange`, provider readiness, route status, and user-facing failure state. Preserve existing behavior while removing duplicate aliases and parallel derivations from normal code paths.

Overall plan difficulty: 5/5; selected profile: partnered-5; because these contracts sit between backend execution, browser rendering, persisted sessions, and preview/apply behavior.

## Scope

In scope:

- Define the canonical wire and frontend shapes for:
  - `StageSnapshot`
  - `ApplyCandidate`
  - `FieldChange`
  - structured identity: `session_id`, `turn_id`, `entry_type` or `role`, with derived string keys only at DOM/API edges
  - user-facing failure/error payloads
  - provider readiness and route status
- Define one canonical snake_case agent-edit/session wire version.
- Define named legacy adapters such as `build_legacy_agent_edit_v1(canonical)` where compatibility fields still need to be emitted.
- Define `vibecomfy/comfy_nodes/web/agent_contracts.js` as the JS boundary normalizer. It is the only normal consumer of legacy aliases.
- Add `allowLegacy=false` fixture tests proving the canonical contract stands without aliases.
- Make user-facing stage display derive from `StageSnapshot` only.
- Make preview/apply controls consume one `ApplyCandidate` projection.
- Make safe field-change rows derive from one typed server-side representation.
- Define explicit transition rules or reducers for progress/stage, candidate/apply, route/provider readiness, durable turn status, and rehydrate.
- Remove duplicate normal-path aliases such as `executor_pending`, `canvasApplyAllowed`, duplicate eligibility fields, and flattened apply booleans unless prep records caller evidence proving compatibility is still required. Retained aliases must go through named legacy adapters and the compatibility ledger.
- Keep compatibility shims only where existing persisted sessions or snapshots require them, and document deletion paths.

Out of scope:

- Rewriting the visual panel layout.
- Changing graph mutation semantics.
- Changing model/provider selection policy.
- Broad module extraction unrelated to contracts.

## Locked Decisions

- `StageSnapshot` is the only normal user-facing progress/stage model.
- `ApplyCandidate` owns candidate id, request id, graph diff summary, safe field changes, eligibility, rejection/apply state, and lifecycle status.
- `FieldChange` is canonical server-side, with frontend preview/detail rows derived from it.
- Raw provider or exception details stay out of user-facing error text by default.

## Execution Defaults

- Compatibility aliases are retained only with caller evidence, fixture coverage, and deletion trigger.
- Canonical backend contract builders start in `vibecomfy/comfy_nodes/agent/contracts.py`. Create a new narrow backend module only if using `contracts.py` would create a real import cycle or mix browser/session/audit ownership.
- Provider availability is backend-owned as `ProviderStatus`; UI route readiness is frontend-projected as `RouteStatus`. Do not collapse them.
- Stateful transitions are reducers; stateless data shaping is projection helpers. At minimum, progress/stage, candidate/apply, route/provider, durable turn, and rehydrate transitions need tests or transition tables.

## Constraints

- Preserve candidate review, apply/reject, rehydrate, failure, clarify, respond, and research-route behavior.
- Do not silently drop data needed by audit/debug surfaces.
- Avoid broad renames. Rename only canonical concepts listed in the README vocabulary or aliases proved to be actively confusing normal paths.

## Done Criteria

- There is one documented canonical shape for each target concept.
- There is a canonical wire version and named compatibility adapter boundary.
- Legacy aliases are not consumed by normal render/lifecycle code outside the boundary normalizer.
- Structured identity is used internally, with string ids derived at boundaries only.
- Stage, candidate/apply, route/provider, durable turn, and rehydrate transitions have explicit tests or transition tables.
- Normal UI code reads stage, apply eligibility, and field changes from those shapes.
- Duplicate aliases are deleted or isolated behind documented compatibility code.
- Tests cover stage preservation, apply eligibility consistency, field-change preview/apply consistency, and sanitized user-facing failures.

## Handoff Artifacts

- Canonical contract docs or comments for the agent-edit/session wire version.
- Python contract builders and named legacy adapter entry points.
- JS boundary normalizer at `vibecomfy/comfy_nodes/web/agent_contracts.js` and selector names that later milestones must consume.
- Compatibility alias ledger with owner, fixture coverage, and deletion trigger.
- Transition tests or tables for stage, candidate/apply, route/provider, durable turn, and rehydrate.

## Touchpoints

- `vibecomfy/comfy_nodes/agent/contracts.py`
- `vibecomfy/comfy_nodes/agent/edit.py`
- `vibecomfy/comfy_nodes/web/agent_contracts.js`
- `vibecomfy/comfy_nodes/web/vibecomfy_roundtrip.js`
- `vibecomfy/comfy_nodes/web/panel_thread.js`
- `vibecomfy/comfy_nodes/web/agent_edit_lifecycle.js`
- `tests/browser/roundtrip_smoke.test.mjs`
- `tests/browser/active_row_rendering.test.mjs`
