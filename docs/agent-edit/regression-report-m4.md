# M4 Regression Report

## Scope

M4 proves that precedent-backed HotShotXL/AnimateDiff edits fail closed when a
candidate only adds disconnected sidecars, pass semantic plan validation when
the active graph satisfies the execution plan, and do not regress ordinary
agent-edit routes.

This report is grounded in the recorded execution artifacts under
`.megaplan/plans/m4-regression-rollout-and-20260630-0530/`.

## North Star Tie-Back

The M1-M4 North Star is to make precedent-backed agent edits reliable by turning
research evidence into an explicit execution plan, evaluating candidate graphs
deterministically, and refusing completion or applyability while required graph
conditions remain unsatisfied.

M4 validates the fourth milestone: rollout coverage, docs, and guardrails. The
reference failure remains HotShotXL sidecars: adding plausible AnimateDiff/video
nodes without wiring them into the active sampler/output path must not count as
completion.

## Evidence Artifacts

Primary plan artifacts:

- `.megaplan/plans/m4-regression-rollout-and-20260630-0530/idea_snapshot.md`
- `.megaplan/plans/m4-regression-rollout-and-20260630-0530/anchors/north_star/combined.md`
- `.megaplan/plans/m4-regression-rollout-and-20260630-0530/plan_v1.meta.json`
- `.megaplan/plans/m4-regression-rollout-and-20260630-0530/final.md`
- `.megaplan/plans/m4-regression-rollout-and-20260630-0530/baseline.json`
- `.megaplan/plans/m4-regression-rollout-and-20260630-0530/execution_batch_1.json`
- `.megaplan/plans/m4-regression-rollout-and-20260630-0530/execution_batch_3.json`
- `.megaplan/plans/m4-regression-rollout-and-20260630-0530/execution_batch_4.json`
- `.megaplan/plans/m4-regression-rollout-and-20260630-0530/execution_batch_5.json`
- `.megaplan/plans/m4-regression-rollout-and-20260630-0530/execution_batch_6.json`
- `.megaplan/plans/m4-regression-rollout-and-20260630-0530/execution_batch_7.json`
- `.megaplan/plans/m4-regression-rollout-and-20260630-0530/execution_batch_8.json`
- `.megaplan/plans/m4-regression-rollout-and-20260630-0530/execution_batch_9.json`
- `.megaplan/plans/m4-regression-rollout-and-20260630-0530/execution_batch_10.json`

Runtime turn artifacts asserted by the regression tests are written under the
agent-edit session turn directory. In production/default local use that is:

- `out/editor_sessions/<session_id>/<turn_id>/execution_plan.json`
- `out/editor_sessions/<session_id>/<turn_id>/plan_evaluation.json`
- `out/editor_sessions/<session_id>/<turn_id>/response.json`
- `out/editor_sessions/<session_id>/<turn_id>/model_request.json`
- `out/editor_sessions/<session_id>/<turn_id>/model_response.json`

The HotShotXL tests use temporary session roots, so their concrete files are
pytest temp artifacts rather than persistent repo files. The tests assert the
same artifact names and response references.

## Command Evidence

Baseline, from `execution_batch_1.json`:

| Command | Result | Classification |
|---|---:|---|
| `/root/.pyenv/versions/3.11.11/bin/python3 -m pytest tests/test_execution_plan_contracts.py tests/test_execution_plan_evaluator.py -q` | 7 passed | Pass, contract/evaluator baseline |
| `/root/.pyenv/versions/3.11.11/bin/python3 -m pytest tests/test_execution_plan_builder.py tests/test_execution_plan_runtime.py -q` | 39 passed | Pass, builder/runtime baseline |
| `/root/.pyenv/versions/3.11.11/bin/python3 -m pytest tests/test_executor_flows.py -q` | 139 passed | Pass, ordinary executor baseline |
| `/root/.pyenv/versions/3.11.11/bin/python3 -m pytest tests/test_comfy_nodes_agent_edit.py -q` | 365 passed, 8 failed | Failures classified as current M4 input failures; only the HotShotXL sidecar blocker was in this milestone's fix path |

Post-fix and evidence runs:

| Command | Result | Classification |
|---|---:|---|
| `/root/.pyenv/versions/3.11.11/bin/python3 -m pytest tests/test_comfy_nodes_agent_edit.py -q` after T3 | 366 passed, 7 failed | HotShotXL sidecar blocker fixed; remaining failures recorded as non-T3 scope |
| `/root/.pyenv/versions/3.11.11/bin/python3 -m pytest tests/test_execution_plan_runtime.py tests/test_comfy_nodes_agent_edit.py -q` after T4 | 371 passed, 7 failed | Complete HotShotXL semantic validation passes; queue blocker remains separate |
| `/root/.pyenv/versions/3.11.11/bin/python3 -m pytest tests/test_comfy_nodes_agent_edit.py -q` after T5 | 366 passed, 7 failed | Retry coverage passes; remaining failures unchanged from prior classification |
| `/root/.pyenv/versions/3.11.11/bin/python3 -m pytest tests/test_execution_plan_builder.py tests/test_executor_flows.py -q` after T6 | 180 passed, 2 warnings | Ordinary prompt/seed/CFG/sampler/model/rewire/output-node routes pass without plan payload leakage |
| `/root/.pyenv/versions/3.11.11/bin/python3 -m pytest tests/test_comfy_nodes_agent_edit.py -q` after T7 | 367 passed, 7 failed | Public response contract assertions pass; remaining failures unchanged from prior classification |
| `/root/.pyenv/versions/3.11.11/bin/python3 -m pytest tests/test_structural_golden_m4.py -q` after T8 | 13 passed, 3 warnings | Structural golden M4 module passes; direct HotShotXL structural evidence not captured, limitation below |
| `/root/.pyenv/versions/3.11.11/bin/python3 -m pytest tests/test_agentic_harness_live.py -q` after T9 | exit 5, `3 deselected` | Info-level live evidence unavailable because live tests require explicit opt-in |

Provider readiness was probed before the live harness command:

```bash
/root/.pyenv/versions/3.11.11/bin/python3 - <<'PY'
import os
from vibecomfy.comfy_nodes.agent import provider
model = os.getenv('VIBECOMFY_LIVE_TEST_MODEL', 'deepseek/deepseek-chat')
keys = ('OPENROUTER_API_KEY','DEEPSEEK_API_KEY','HERMES_API_KEY','ARNOLD_API_KEY')
print('credential_presence=' + ','.join(f'{k}:{bool(os.getenv(k))}' for k in keys))
status = provider.readiness(route='openrouter', model=model)
redacted = {k:v for k,v in status.items() if 'key' not in k.lower() and 'token' not in k.lower() and 'secret' not in k.lower()}
print('readiness=' + repr(redacted))
PY
```

It found OpenRouter/DeepSeek credentials present and readiness true for
`deepseek/deepseek-chat`.

## Pass/Fail Classification

Must-pass M4 evidence:

- Pass: `ExecutionPlan` and `PlanEvaluation` contracts/evaluator baseline.
- Pass: builder/runtime focused baseline.
- Pass: executor-flow focused baseline.
- Pass: HotShotXL sidecar-only `done()` now fails closed, remains non-applyable,
  sets `plan_validate_ok=false`, exposes compact failed-plan feedback, and
  persists plan/evaluation artifacts.
- Pass: complete HotShotXL graph passes semantic plan validation with
  `plan_validate_ok=true`.
- Pass: queue validation stays separate; a complete plan can still report
  `queue_blocked_warning`.
- Pass: premature `done()` retry coverage rejects the incomplete plan, feeds
  compact feedback only while the plan-backed turn is active, and succeeds after
  correction within the retry budget.
- Pass: prompt, seed, CFG, sampler-step, model-name, local rewire, and
  output-node ordinary routes bypass precedent planning without nested
  `execution_protocol_notes.execution_plan` leakage.
- Pass: public response compatibility coverage keeps legacy aliases stable,
  avoids a public top-level `execution_plan`, exposes `debug.gates.plan_validate_ok`,
  exposes artifact refs, and suppresses applyability on failed plan validation.

Remaining test failures recorded during M4 but not fixed in this batch:

- `tests/test_comfy_nodes_agent_edit.py::test_agent_edit_batch_empty_model_response_retries_once_then_commits`
- `tests/test_comfy_nodes_agent_edit.py::test_handle_agent_edit_batch_repl_turn0_catalog_is_scoped_and_search_first`
- `tests/test_comfy_nodes_agent_edit.py::test_rejected_terminal_clarify_is_durable_budget_failure`
- `tests/test_comfy_nodes_agent_edit.py::test_rejected_terminal_clarify_after_partial_edit_fails_fast`
- `tests/test_comfy_nodes_agent_edit.py::test_handle_agent_edit_research_route_writes_agentic_messages_and_blocks_apply`
- `tests/test_comfy_nodes_agent_edit.py::test_handle_agent_edit_batch_repl_clarify_after_edit_returns_edit_and_clarify_outcome`
- `tests/test_comfy_nodes_agent_edit.py::test_handle_agent_edit_you_decide_pil_code_node_uses_classifier_summary_to_attempt_provider`

These remain classified as recorded non-HotShotXL-sidecar/non-T11 scope items
for the final validation task to classify against the fresh baseline. They are
not rollout evidence for the HotShotXL North Star unless T12 proves they now
block the M4 must-pass criteria.

Baseline broad-suite collection failures from `baseline.json`:

- `docs/testing/user_code_examples/test_01_single_template_recipe.py`
- `docs/testing/user_code_examples/test_02_dual_pass.py`
- `tests/test_structural_harness_adapter.py`

The structural harness adapter collection failure is relevant to direct
HotShotXL structural evidence because the local adapter path requires `sisypy`.

## Known Limitations

- Direct HotShotXL structural graph evidence was not captured by
  `tests/test_structural_golden_m4.py`. That module passed, but it covers the
  M4 Wan/LTX builders; `hotshot-16-frames-agent-edit` is registered under
  `_M6_BUILDERS` in `tests/structural_harness/adapter.py`.
- The direct HotShotXL structural harness path was unavailable locally because
  `tests/test_structural_harness_adapter.py` has a baseline collection error
  for missing `sisypy`.
- Live/agentic graph evidence was unavailable at info level. Credentials and
  provider readiness existed, but the exact approved command
  `pytest tests/test_agentic_harness_live.py -q` deselected the live tests
  because the repo requires a `--run-live` opt-in.
- The semantic fixture evidence is therefore the must-pass evidence for
  HotShotXL sidecar rejection and complete-plan acceptance, supported by the
  passing structural M4 module and the documented local structural limitation.

## Artifact Inspection Steps

For a plan-backed agent-edit turn, inspect:

1. `response.json`: confirm no public top-level `execution_plan`, confirm
   `gates.plan_validate_ok`, `debug.gates.plan_validate_ok`,
   `execution_plan_status`, `task_satisfaction`, `artifacts.execution_plan`,
   and `artifacts.plan_evaluation`.
2. `execution_plan.json`: confirm `contract_version` is
   `execution_plan_v1`, the expected `plan_id` is present, and required
   HotShotXL/AnimateDiff active-path conditions are encoded.
3. `plan_evaluation.json`: confirm `contract_version` is
   `plan_evaluation_v1`, `ok`/`blocking` match the response gate, and failed
   condition ids explain any refusal.
4. `model_response.json`: for rejected premature `done()`, confirm compact
   plan feedback is persisted on the current batch turn.
5. `model_request.json`: confirm plan feedback is present only for an active
   plan-backed retry and absent from later non-plan turns.

For ordinary routes, inspect the executor result and response payload for the
absence of `execution_protocol_notes.execution_plan`, top-level
`execution_plan`, and plan-backed feedback.
