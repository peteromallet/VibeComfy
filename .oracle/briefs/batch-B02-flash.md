# B02 — Route policy, tool gating, host budgets (Flash portion)

Worktree: /private/tmp/vc-twostep (branch two-step-megado). Python: `PYENV_VERSION=3.11.11`, venv at /Users/peteromalley/Documents/reigh-workspace/vibecomfy/.venv, `PYTHONPATH=$PWD` if needed.

You are implementing the Flash portion of batch B02. A separate DeepSeek **Pro** agent is doing the XHARD tasks (cumulative budgets + provider-wide output-cap propagation through worker.py/runtime.py/adapters) in parallel. Coordinate only through the shared files listed below — if you touch the same file, keep your changes to your scope and do not clobber.

## Your tasks (frozen tasklist B02, Flash scope)

1. In `vibecomfy/executor/two_step.py`, add frozen types:
   - `TwoStepRoutePolicy`
   - `MessageBudget`
   - `SessionBudget`
   - `BudgetUsage`
   - `BudgetExceeded`
   (These are policy/type definitions. The Pro agent implements enforcement plumbing.)

2. Define `TWO_STEP_ROUTE_POLICIES` with the authoritative route table:
   - `clarify`, `respond`: no tools; 2k output; 30s.
   - `inspect`: `node_schema`; 4k; two calls; 60s.
   - `research`: Hivemind, registry, schema, templates, policy-enabled web; 8k; 180s.
   - `requires_custom_nodes`: registry and schema; 4k; 90s.
   - `revise`: schema, templates, suggestions, layout, Python; 8k; 180s.
   - `adapt`: all ten tools and Python; 12k; 240s.
   - `reorganise`: layout and Python; 6k; 120s.

3. Assert:
   ```python
   set(TWO_STEP_ROUTE_POLICIES) == set(_ROUTE_BEHAVIORS)
   ```
   Import `_ROUTE_BEHAVIORS` lazily (do NOT move or duplicate the full-mode route authority).

4. Exact per-tool caps (frozen):
   hivemind_search 3, hivemind_get 4, registry_lookup 2, node_schema 4,
   ready_template_list 2, ready_template_load 2, rank_edit_targets 2,
   suggest_seed_nodes 2, layout_hints 2, web_search 1 (denied unless explicitly enabled).
   Aggregate per-message tool calls: clarify/respond 0, inspect 2, research 8,
   requires_custom_nodes 3, revise 6, adapt 8, reorganise 2.

5. Tool catalogs: build with `tool_catalog_docs(phase=None, allowed_names=effective_route_tools)` —
   do NOT pass `phase="research"` (node_schema and template tools are implement-phase at
   tool_specs.py:760/771; phase="research" would hide them). Enforce the route allowlist
   BEFORE handler invocation or budget consumption. `web_search` denied unless existing
   policy enables it (no production owner enables it today).

6. Per-message budget checks before/after every model/tool call: route slice, aggregate
   output tokens, per-tool caps, apply/replacement counters, wall clock. (Cumulative
   session ceilings are the Pro agent's job — provide the `SessionBudget` type and a
   hook/accumulator the Pro agent can wire, but do not implement session persistence.)

7. Tests:
   - `tests/test_executor_two_step_policy.py`
   - `tests/test_executor_two_step_tools.py`
   - Runtime-cap cases in `tests/test_agent_runtime_adapter.py` (the Pro agent owns the
     runtime plumbing; write the test contract for `remaining_output_cap` if that's your
     scope overlap — coordinate).

## Acceptance gate (run the policy/tools portion)

```bash
python -m pytest -q \
  tests/test_executor_two_step_policy.py \
  tests/test_executor_two_step_tools.py \
  tests/test_executor_hivemind_tools.py \
  tests/test_executor_lookup_tools.py \
  tests/test_executor_layout_hints.py
```

Prove: exact route coverage, exact advertised catalogs, denial-before-dispatch, disabled
web policy, per-message budget families, aggregate-token exhaustion, per-tool caps.

## Constraints
- Commit ONLY your portion: `git add -A && git commit -m "B02: route policy + tool gating (Flash)"`.
  If the Pro agent's files are mid-edit in the working tree, stage only YOUR files by path.
- Do not start B03 work.
- Report: files changed, gate output, deviations.
