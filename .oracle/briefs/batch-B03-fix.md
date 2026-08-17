# B03-fix — land the two remaining B03 gate items (Flash)

Worktree: /private/tmp/vc-twostep (branch two-step-megado). Python: `PYENV_VERSION=3.11.11`, venv at /Users/peteromalley/Documents/reigh-workspace/vibecomfy/.venv, `PYTHONPATH=$PWD`.

B03 (two-step session + execute prompt + continuation loop) is implemented but its gate is
red on exactly two items. Your job: land those two fixes, run the gate green, commit.

## Fix 1 — `test_run_execute_turn_rejects_forged_delta` (Python)

File: `vibecomfy/executor/agent_backend.py`, `run_execute_turn()`.

Diagnosis from B03: the `submit` action's `state.validate_delta_references(delta_ids)`
raises `TwoStepSessionError` inside the main `try`; the `finally` clears state but the
loop RE-RAISES instead of returning the documented dict result. The test expects a
`{"ok": False, "reply": None, "route": route, "failure": exc}`-shaped dict.

Fix: wrap the `submit` validation (or the whole action dispatch) in its own
`try/except TwoStepSessionError -> return {"ok": False, "reply": None, "route": route,
"failure": exc}` so typed session errors become the documented dict result rather than
propagating. Do not swallow other exception types.

Verify: `python -m pytest -q tests/test_executor_two_step_continuity.py -k forged_delta`

## Fix 2 — one browser-contract pin (574/575)

File: likely `tests/browser/*.mjs` pins reacting to `agent_submit_flow.js`'s new
`getOrCreateBoundSessionId` destructure and/or the two new exports (`newUuidV4`,
`getOrCreateScopedSessionId`) in `scoped_session_storage.js`.

Diagnosis path: run `node --test tests/browser/*.mjs` with full output to identify the
exact failing assertion. Then either:
(a) update the pin if it is a legitimate contract extension (the browser identity work is
    intended — two-step needs a browser-owned session UUID before first POST), or
(b) preserve the prior exported surface (consume the resolver through the existing
    `deps`/injection object without changing the exported shape).

Decision rule: if the test asserts the exported surface exactly, extend the pin to the
new exports AND keep old ones; never remove existing behavior. If it asserts a static
banned-symbol/roundtrip pin that the new destructure trips, prefer (b) — route the new
dependency through the existing injection mechanism so no export/destructure surface
changes.

## Gate (must be fully green)

```bash
cd /private/tmp/vc-twostep && PYTHONPATH=$PWD /Users/peteromalley/Documents/reigh-workspace/vibecomfy/.venv/bin/python -m pytest -q \
  tests/test_executor_two_step_prompt.py \
  tests/test_executor_two_step_continuity.py \
  tests/test_routes_session_sanitization.py \
  tests/test_agent_executor_durable.py
make browser-contracts
```

## Constraints
- Commit with `git add -A && git commit -m "B03: fix forged-delta result + browser contract pin"`.
- Do not touch B04/B06/B07 scope.
- Report: the two fixes, gate output (must be green), deviations.
