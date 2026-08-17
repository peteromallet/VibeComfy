# B02 — Cumulative budgets + provider output-cap propagation (XHARD, DeepSeek Pro)

Worktree: /private/tmp/vc-twostep (branch two-step-megado). Python: `PYENV_VERSION=3.11.11`, venv at /Users/peteromalley/Documents/reigh-workspace/vibecomfy/.venv, `PYTHONPATH=$PWD` if needed.

You are implementing the XHARD portion of batch B02. A separate DeepSeek **Flash** agent is doing the policy table + tool-gating types in `vibecomfy/executor/two_step.py` in parallel. Coordinate: use the `SessionBudget` / `BudgetUsage` / `BudgetExceeded` types the Flash agent defines in `two_step.py`; do not redefine them.

## Your tasks (frozen tasklist B02, XHARD scope — cumulative budgets + output-cap plumbing)

1. Plumb a remaining output-token cap through the provider path:
   - `vibecomfy/comfy_nodes/agent/worker.py` (~line 254): `AgentRequest` gains an optional
     `remaining_output_cap` field (or equivalent), default `None` = full-mode behavior.
   - `vibecomfy/comfy_nodes/agent/runtime.py` (~line 557 `_split_messages()`, ~573 where
     `max_tokens` is applied): apply the cap to model calls when set; `None` preserves
     existing behavior.
   - Every provider adapter the worker can dispatch to (check `comfy_nodes/agent/`
     adapters — hermes/openrouter/deepseek paths) must accept and honor the cap.
   - IMPORTANT: `_split_messages()` currently keeps only the first system message and the
     last user message. Do NOT rely on passing full assistant/tool history as ordinary
     messages — the B03 agent will flatten the transcript into the final user payload.
     Your scope is the cap field plumbing only.

2. Implement cumulative-session budget enforcement (the session AUTHORITY itself lands in
   B03's `two_step_session.py`; here provide the enforcement primitive):
   - A `SessionBudget` accumulator that tracks, across messages: aggregate output tokens,
     model continuation count, registered-tool call count, cumulative active model/tool
     wall time, accepted edit batch count, replacement attempts, user message count.
   - Fixed ceilings (frozen): 48,000 aggregate output tokens; 64 model continuations;
     64 registered-tool calls; 1,800 s cumulative wall time; 12 accepted edit batches;
     12 replacement attempts total (still at most one per message); 32 user messages.
   - On exhaustion: raise typed `BudgetExceeded`; must NOT silently reset the session.
   - Design the accumulator so B03's session authority can persist it (plain dataclass
     with a `to_dict()`/`from_dict()` or equivalent).

3. Tests:
   - Cumulative-session exhaustion cases in `tests/test_executor_two_step_policy.py`
     (or a dedicated section if the Flash agent owns that file — append, don't clobber).
   - Runtime-cap cases in `tests/test_agent_runtime_adapter.py`: cap set → applied;
     cap None → byte-identical full-mode request; cap exhausted mid-continuation → typed
     BudgetExceeded surfaces through the worker result path.

## Acceptance gate (your portion)

```bash
python -m pytest -q \
  tests/test_executor_two_step_policy.py \
  tests/test_agent_runtime_adapter.py \
  tests/test_comfy_nodes_agent_backend_spine.py
```

Plus prove with a targeted check that a `remaining_output_cap=None` request produces an
unchanged worker request shape (full-mode compat).

## Constraints
- Commit ONLY your files by path: `git add <your files> && git commit -m "B02: cumulative budgets + output-cap plumbing (Pro)"`.
- Do not start B03 work.
- Report: files changed, gate output, deviations.
