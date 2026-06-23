# M4: Frontend Selector And Render Boundary

## Outcome

Make browser rendering raw-data-blind. Thread, detail, stage, candidate, and composer surfaces should consume only safe selectors/view models over the canonical transcript/detail/execution/stage/candidate model.

Overall plan difficulty: 5/5; selected profile: partnered-5; because the current frontend structure allows multiple code paths to display similar state with subtly different semantics.

## Scope

In scope:

- Define frontend selector APIs for transcript rows, response details, stage display, candidate/apply state, route/provider status, and audit affordances.
- Make chat thread rendering consume safe selectors only.
- Make candidate/apply controls consume the canonical `ApplyCandidate` projection only.
- Make expanded detail panes consume `ResponseDetail` and explicit audit affordances, not raw execution/audit payloads.
- Add tests proving render paths reject or ignore raw `batch_turns`, `debug`, `audit`, `canonical_activity.details`, raw paths, and provider payloads.
- Keep tests focused on behavior rather than implementation details.

Out of scope:

- Cosmetic redesign.
- New user-facing copy unless required by a canonical projection.
- Backend contract changes not already available from earlier milestones.
- Broad `vibecomfy_roundtrip.js` decomposition, duplicated poller deletion, and dead renderer cleanup; those belong to the next frontend module decomposition milestone.

## Locked Decisions

- Normal renderers do not inspect raw execution events, audit details, or canonical activity internals.
- Renderers consume selectors/view models, not wire payloads or compatibility aliases.
- Candidate controls consume `ApplyCandidate`; thread bubbles consume `TranscriptMessage` and `ResponseDetail`; stage UI consumes `StageSnapshot`.

## Execution Defaults

- Use reducers for state transitions and selectors for view-model reads. Do not hide transition logic in render functions.
- Compatibility fields remain only in the boundary normalizer and compatibility ledger. Render modules must not read them directly.

## Constraints

- Preserve the existing panel workflow: send prompt, show stage, show response, preview candidate, apply/reject, rehydrate, inspect explicit debug details.
- Avoid a rewrite that makes review impossible.
- Keep browser tests runnable with the current Node test harness.

## Done Criteria

- `panel_thread.js` and chat render paths consume safe selectors.
- Detail panes and candidate controls cannot consume raw execution/audit/session/debug fields.
- Forbidden raw field reads are covered by tests. Add lint/static checks when the file boundaries are stable enough to express them without brittle false positives.
- Browser tests cover normal chat, expanded details, rehydrate, candidate actions, and status display.

## Handoff Artifacts

- Selector API list and owning module names.
- Forbidden render input list.
- Tests or fixtures for hostile internal payloads.
- Inventory of duplicated frontend render/poller/state code to remove in the next milestone.

## Touchpoints

- `vibecomfy/comfy_nodes/web/vibecomfy_roundtrip.js`
- `vibecomfy/comfy_nodes/web/panel_thread.js`
- `vibecomfy/comfy_nodes/web/panel_composer.js`
- `vibecomfy/comfy_nodes/web/agent_status_poller.js`
- `vibecomfy/comfy_nodes/web/agent_turn_feed.js`
- `vibecomfy/comfy_nodes/web/agent_edit_lifecycle.js`
- `tests/browser/*.test.mjs`
