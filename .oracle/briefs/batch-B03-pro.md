# B03 — Execute prompt + thread-continuous session (XHARD, DeepSeek Pro)

Worktree: /private/tmp/vc-twostep (branch two-step-megado). Python: `PYENV_VERSION=3.11.11`, venv at /Users/peteromalley/Documents/reigh-workspace/vibecomfy/.venv, `PYTHONPATH=$PWD` if needed.

You are implementing batch B03 (all XHARD). B01 landed (`f5a45561`): `PipelineMode`,
`resolve_pipeline_mode()`, `ExecutorRequest.pipeline_mode`, the `run_executor` branch to
`_run_two_step()` in `vibecomfy/executor/two_step.py`, typed request/config errors, and a
test-injectable `_two_step_outcome(...)` boundary. B02 is in flight in parallel: policy
types + tool gating (Flash) and cumulative budgets + output-cap plumbing (Pro). Do NOT
redefine `TwoStepRoutePolicy`/`SessionBudget` if they land; import from `two_step.py`.

## Tasks

1. `vibecomfy/executor/two_step_session.py` (new):
   - Session identity keyed by normalized chat-window `session_id`.
   - Compact append-only execute transcript under the existing durable session directory.
   - Persist: accepted Δ references, lens facts, evidence ledger, replies, route history,
     cumulative budget usage (use the B02 `SessionBudget` accumulator), last retained
     workflow revision.
   - Serialize same-session messages with the existing process-safe lock
     (`vibecomfy/comfy_nodes/agent/session.py:385` — REUSE it, don't recreate).
   - Concurrent/stale message detection BEFORE model work.
   - In-process `EditSession` cache: 15-minute idle eviction, max 128 entries, LRU;
     eviction drops only the cache — durable transcript rehydratable.
   - Reconstruction only through a named ingest door + canonical Δ replay (never an
     in-memory dict as sole authority).

2. First-message browser identity:
   - `vibecomfy/comfy_nodes/web/scoped_session_storage.js` (~111): get-or-create UUIDv4
     before the first two-step POST (the server must NOT mint IDs for two-step).
   - `vibecomfy/comfy_nodes/web/agent_submit_flow.js` (~56): send the bound ID instead of
     `undefined` when in two-step mode.
   - Headless/custom two-step callers without a `session_id` → typed invalid-request error
     BEFORE classification. Never turn an expired/closed ID into a fresh session → typed
     `session_expired`.

3. `build_two_step_execute_messages()` in `vibecomfy/executor/prompts.py`:
   - Every authoritative design section (route/plan/query, current workflow render lenses,
     RESEARCH, PRECEDENT TRANSLATION, EDITING, REPLY, SELF-CHECK + final contract).
   - Explicit `STAGES AND AVAILABLE TOOLS` section (user requirement — must be prominent):
     1. `RESEARCH` — the exact research tools available for this route.
     2. `CHANGE` — the exact advisory/schema/layout tools, plus whether Python editing is allowed.
     3. `SUBMIT` — no tools; the final JSON contract only.
   - State that unavailable tools are denied by the host.
   - State the same-window continuity rule verbatim in substance.
   - Non-edit routes: explicitly say no change may be submitted.
   - Render only the route-allowed catalog (B02 policy).

4. Bounded continuation loop: `run_execute_turn()` in `vibecomfy/executor/agent_backend.py`:
   - Parse host actions: registered tool call, Python batch submission, or final contract.
   - Re-inject the compact accumulated transcript + new message into EVERY continuation.
   - CRITICAL: `_split_messages()` in `comfy_nodes/agent/runtime.py:557` keeps only the
     first system message and last user message — passing assistant/tool history as
     ordinary messages silently loses it. FLATTEN the compact transcript into the final
     user payload (or extend the worker protocol; the design doc says flatten — do that).
   - No provider-native memory.
   - One logical execute-session identity across messages and route changes.
   - Derive `research_attempt` (never/empty/thin/grounded) from the session ledger.

5. Prompt goldens: `tests/fixtures/executor/two_step_prompt_{clarify,respond,inspect,
   research,requires_custom_nodes,revise,adapt,reorganise}.txt`.

6. Tests:
   - `tests/test_executor_two_step_prompt.py`
   - `tests/test_executor_two_step_continuity.py` (initial: same-session reuse, new-window
     fresh, mid-thread route change keeps session, missing turn-1 Δ fails, budgets
     accumulate with per-message slices)
   - Browser identity coverage in the existing browser submit-flow suite.

## Acceptance gate

```bash
python -m pytest -q \
  tests/test_executor_two_step_prompt.py \
  tests/test_executor_two_step_continuity.py \
  tests/test_routes_session_sanitization.py \
  tests/test_agent_executor_durable.py
make browser-contracts   # NOT `npm test -- --runInBand` (root has no package.json)
```

Gate must inspect every prompt golden and prove the visible sequence is
`research → change → submit`, with exact tools and no union-catalog leakage.

## Constraints
- Commit ONLY this batch's scope: `git add -A && git commit -m "B03: execute prompt + thread-continuous session"`.
- Do not start B04 work.
- Report: files changed, gate output, deviations.
