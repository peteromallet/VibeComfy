# Messaging Boundary Cleanup

## Outcome

Make VibeComfy's agent panel messaging architecture cleanly separate user-facing transcript/detail data from internal execution/audit data, so raw batch-turn text, statements, diagnostics, budgets, and model-internal progress cannot leak into normal UI render paths.

The delivered result should preserve the immediate leak fix already made locally, then replace scattered negative filters with explicit state compartments and selector/projection APIs.

## Scope

In scope:

- Define and implement a frontend state split for:
  - user-facing transcript messages,
  - safe response details,
  - internal execution events from `batch_turns` and `vibecomfy.agent_edit.turn`,
  - durable lifecycle statuses,
  - audit/debug references.
- Add selector/projection functions that are the only normal path from backend/agent payloads into chat bubbles and detail panes.
- Move batch/websocket event ingestion away from renderable `panel.state.turns` usage.
- Keep audit/debug download functionality working, but make it explicit and separate from normal bubble details.
- Add tests that use sentinel internal strings and prove they do not appear in collapsed or expanded normal UI.
- Preserve candidate review, apply/reject, rehydrate, field-change, failure, clarify, respond, and research-route behavior.
- Consume the canonical contracts, identity model, and boundary normalizer produced by the contracts/view-model milestone.

Out of scope:

- Redesigning the panel visual layout.
- Reworking the backend agent execution engine.
- Removing audit artifacts or developer diagnostics entirely.
- Changing model/provider routing.
- Broad frontend decomposition unrelated to the messaging boundary.
- Touching graph preview overlay behavior except where tests need to verify no messaging regression.
- Canonicalizing apply/provider/field-change contracts beyond what is needed to consume the prior milestone's APIs.

## Locked Decisions

- Use the four-layer conceptual model:
  - `TranscriptMessage`: user-facing conversation only.
  - `ResponseDetail`: safe expandable details only.
  - `ExecutionEvent`: internal batch/websocket execution feed.
  - `AuditArtifact`: explicit debug/download evidence.
- Do not introduce a second vocabulary for these concepts; if a new local name is needed, document why it is not a canonical contract.
- Normal rendering code must consume `TranscriptMessage` and `ResponseDetail`, not raw `ExecutionEvent`.
- The projection boundary is one-way:
  - `ExecutionEvent + backend result -> safe TranscriptMessage / ResponseDetail`.
- Batch turns remain available only to internal execution/audit consumers and explicit audit/debug surfaces. They must not be reachable through renderable transcript/detail selectors.
- The current local patch that deletes the old batch-row renderer and filters batch entries out of bubble detail rendering is a valid starting point, not the final architecture.

## Execution Defaults

- Replace normal use of `panel.state.turns` with separate transcript/detail/execution/status buckets. Retain `panel.state.turns` only as a compatibility mirror if caller evidence proves it is still required, and list it in the compatibility ledger.
- `message.canonical_activity.details` is not renderer input. Convert only safe entries through `ResponseDetail`; keep raw details under audit/debug.
- Developer/debug UI exposes raw internals only behind explicit debug or audit affordances, never by default in normal chat/detail panes.
- Backend chat rehydrate must project through safe transcript/detail/session contracts before the browser sees it. Frontend sanitization is a second line of defense, not the primary boundary.

## Constraints

- Do not regress the current verified behavior:
  - `node --test tests/browser/active_row_rendering.test.mjs`
  - `node --test tests/browser/roundtrip_smoke.test.mjs`
- Maintain compatibility with current backend response shapes during migration.
- Keep the change incremental and reviewable; avoid a giant panel rewrite.
- Normal UI must never render raw internal sentinel values from:
  - websocket `message`,
  - `done_summary`,
  - `statements[].source`,
  - statement diagnostics,
  - budgets,
  - exit modes,
  - provider/raw payload metadata.
- Audit/debug functionality may retain internals only through explicit audit/report surfaces.

## Done Criteria

- Normal chat rendering only reads from safe transcript/detail selectors.
- The selectors are the canonical selector/normalizer APIs from the contracts/view-model milestone, or documented adapters over them.
- Internal batch/websocket events live in an internal execution store or are otherwise structurally unreachable from normal renderers.
- Bubble detail rendering no longer reads raw `panel.state.turns` or raw `message.canonical_activity.details` directly.
- Existing browser suites pass.
- New boundary tests prove internal sentinel strings are absent from collapsed chat, expanded details, the below-thread/history mount, and rehydrated chat UI.
- Audit/download tests prove raw execution data is still available only through explicit audit/debug paths.
- Any temporary compatibility mirror is documented and has a clear deletion path.

## Handoff Artifacts

- Browser/default-render forbidden-field list covering raw execution, debug, audit, path, and provider payload fields.
- Selector API names consumed by thread rendering and detail panes.
- Inventory of remaining compatibility mirrors and deletion triggers.
- Tests proving the default browser render cannot reach raw execution events.

## Touchpoints

- `vibecomfy/comfy_nodes/web/panel_thread.js`
- `vibecomfy/comfy_nodes/web/vibecomfy_roundtrip.js`
- `vibecomfy/comfy_nodes/web/agent_turn_feed.js`
- `vibecomfy/comfy_nodes/web/agent_edit_lifecycle.js`
- `vibecomfy/comfy_nodes/web/diagnostics_reporting.js`
- `tests/browser/active_row_rendering.test.mjs`
- `tests/browser/roundtrip_smoke.test.mjs`
- Any backend chat/session contract code needed to prevent raw execution details from entering `/vibecomfy/agent-edit/chat`.

## Anti-Scope

- Do not change Comfy graph mutation semantics.
- Do not alter Apply/Reject eligibility rules except where selector boundaries require data plumbing changes.
- Do not remove existing audit downloads.
- Do not introduce new UI copy for internal execution progress unless it is produced by an explicit safe projection.
- Do not expose raw model prose as a progress label.

## Prep Notes

The immediate leak fix removed the legacy visible batch-row renderer from `panel_thread.js` and added an `entry_type !== "batch"` filter in `turnEntriesForBubbleDetail`. Codex independently reviewed the architecture and agreed with the direction, but flagged that the current boundary is still enforced by scattered filters and shared state rather than by typed projection/selector APIs.

The next sprint should make render paths structurally unable to see internal execution events.
