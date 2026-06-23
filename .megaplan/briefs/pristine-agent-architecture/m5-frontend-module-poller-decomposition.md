# M5: Frontend Module And Poller Decomposition

## Outcome

Make `vibecomfy_roundtrip.js` an orchestration shell. Once selector/render boundaries are stable, remove duplicated renderers, duplicated status polling, stale activity-strip code, and stale frontend state mirrors without changing user-visible behavior.

Overall plan difficulty: 5/5; selected profile: partnered-5; because this milestone changes frontend ownership and can accidentally reintroduce parallel render/status paths.

## Scope

In scope:

- Decompose `vibecomfy_roundtrip.js` along real ownership boundaries: event intake, transcript state, candidate/apply state, graph preview/apply adapter, render orchestration, and route/status orchestration.
- Make `panel_composer.js` canonical for developer/settings/notice/composer rendering where it already owns those surfaces.
- Remove stale duplicated renderers from `vibecomfy_roundtrip.js`.
- Unify agent status polling and route readiness derivation behind one owner.
- Delete confirmed dead legacy activity-strip paths and stale state mirrors.
- Keep module movement reviewable and backed by behavior tests.

Out of scope:

- Introducing new canonical contracts.
- Backend module extraction.
- Cosmetic UI redesign.

## Locked Decisions

- `vibecomfy_roundtrip.js` should own orchestration only: wire events in, call normalizers/reducers/selectors, invoke graph adapters, and schedule render.
- One module owns each render surface; imports are preferred over closure-bound copies.
- One module owns route/status polling and readiness derivation.

## Execution Defaults

- File split must produce named ownership for event intake, transcript state, candidate/apply state, graph adapter, render orchestration, and route/status orchestration. Existing import patterns can influence filenames but not blur ownership.
- Legacy activity-strip artifacts are deleted unless caller evidence or a compatibility fixture proves they are still needed.

## Constraints

- Preserve send prompt, show stage, show response, preview candidate, apply/reject, rehydrate, and explicit debug workflows.
- Do not hide behavior changes inside file moves.

## Done Criteria

- `vibecomfy_roundtrip.js` exports no renderer implementations, no status polling implementation, and no candidate eligibility decision logic. It owns orchestration: wire events in, call normalizers/reducers/selectors, invoke graph adapters, and schedule render.
- Duplicated developer/settings renderer copies are removed or reduced to intentional wrappers.
- Status polling logic has one canonical owner.
- Confirmed dead activity-strip code and stale state mirrors are deleted.
- Browser tests cover normal chat, expanded details, rehydrate, candidate actions, and status display.

## Handoff Artifacts

- Frontend ownership map naming each module and its allowed responsibilities.
- Removed duplicated renderer/poller/state list.
- Remaining frontend compatibility/deletion ledger, if any.

## Touchpoints

- `vibecomfy/comfy_nodes/web/vibecomfy_roundtrip.js`
- `vibecomfy/comfy_nodes/web/panel_thread.js`
- `vibecomfy/comfy_nodes/web/panel_composer.js`
- `vibecomfy/comfy_nodes/web/agent_status_poller.js`
- `vibecomfy/comfy_nodes/web/agent_turn_feed.js`
- `vibecomfy/comfy_nodes/web/agent_edit_lifecycle.js`
- `tests/browser/*.test.mjs`
