# Final Epic Summary

## Outcome

The M1-M4 research-plan-execute epic now has typed execution-plan contracts,
deterministic plan construction for the HotShotXL precedent case, runtime
semantic enforcement during agent edit execution, public response guardrails,
and rollout evidence/documentation for M4.

The North Star was to make precedent-backed agent edits reliable by converting
research evidence into an explicit execution plan, evaluating candidate graphs
deterministically, and refusing completion/applyability while critical graph
conditions remain unsatisfied. M4 ties that end state to concrete regression
evidence.

## Milestone Summary

M1 established the shared contract surface:

- `ExecutionPlan`
- `PlanCondition`
- `PlanEvaluation`
- deterministic evaluator behavior
- fail-closed version handling

M2 routed precedent-backed adapt requests into the deterministic builder:

- normalized `adapt` route is the only route that can qualify;
- ordinary `revise`, `respond`, `inspect`, `research`, and `clarify` routes
  bypass planning;
- plans are serialized only under
  `execution_protocol_notes.execution_plan.plan`.

M3 enforced plans at runtime:

- agent-edit hydrates nested execution-plan payloads;
- candidate graphs are evaluated against the plan;
- `execution_plan.json` and `plan_evaluation.json` are persisted;
- `plan_validate_ok` becomes an explicit gate;
- failed required/critical plan conditions suppress applyability;
- compact plan feedback is fed into active plan-backed retries.

M4 proved rollout readiness and guardrails:

- HotShotXL sidecar-only `done()` fails closed and no longer appears as a
  successful/applyable edit.
- Complete HotShotXL active-path edits pass semantic validation.
- Queue validation remains separate from semantic plan validation.
- Ordinary local edits keep their old route behavior and do not receive plan
  payload leakage.
- Public response shape remains compatible with existing consumers.
- Docs now explain the contract, routing matrix, response shape, validation
  boundary, regression evidence, rollout checklist, and extension workflow.

## Concrete Evidence

Recorded execution artifacts live under:

- `.megaplan/plans/m4-regression-rollout-and-20260630-0530/`

Key evidence files:

- `plan_v1.meta.json`: success criteria and changed-surface expectations.
- `baseline.json`: broader baseline collection failures and baseline command.
- `execution_batch_1.json`: focused baseline results.
- `execution_batch_3.json`: sidecar fail-closed fix verification.
- `execution_batch_4.json`: complete HotShotXL semantic validation evidence.
- `execution_batch_5.json`: retry feedback evidence.
- `execution_batch_6.json`: ordinary route no-leak evidence.
- `execution_batch_7.json`: public response compatibility evidence.
- `execution_batch_8.json`: structural evidence and structural limitation.
- `execution_batch_9.json`: live/agentic readiness and deselection limitation.
- `execution_batch_10.json`: updated docs evidence.

Exact command highlights:

```bash
/root/.pyenv/versions/3.11.11/bin/python3 -m pytest tests/test_execution_plan_contracts.py tests/test_execution_plan_evaluator.py -q
/root/.pyenv/versions/3.11.11/bin/python3 -m pytest tests/test_execution_plan_builder.py tests/test_execution_plan_runtime.py -q
/root/.pyenv/versions/3.11.11/bin/python3 -m pytest tests/test_executor_flows.py -q
/root/.pyenv/versions/3.11.11/bin/python3 -m pytest tests/test_comfy_nodes_agent_edit.py -q
/root/.pyenv/versions/3.11.11/bin/python3 -m pytest tests/test_structural_golden_m4.py -q
/root/.pyenv/versions/3.11.11/bin/python3 -m pytest tests/test_agentic_harness_live.py -q
```

Observed pass evidence:

- contract/evaluator baseline: 7 passed;
- builder/runtime baseline: 39 passed;
- executor-flow baseline: 139 passed;
- ordinary route builder/executor verification: 180 passed, 2 warnings;
- structural M4 module: 13 passed, 3 warnings;
- HotShotXL sidecar-specific failing test removed after the fail-closed fix;
- complete HotShotXL plan queue-warning test not among post-T4 failures;
- public response contract coverage added and verified in the full
  `tests/test_comfy_nodes_agent_edit.py` file run.

## Remaining Limitations

- Seven `tests/test_comfy_nodes_agent_edit.py` failures remained after the M4
  HotShotXL/public-contract fixes. They were recorded as non-T11 scope and must
  be classified by T12 against the baseline rather than fixed opportunistically.
- Direct HotShotXL structural graph evidence was not captured by
  `tests/test_structural_golden_m4.py`; that module passed but covers M4
  Wan/LTX scenarios, while `hotshot-16-frames-agent-edit` is registered under
  `_M6_BUILDERS`.
- The local direct HotShotXL structural harness path is limited by the baseline
  `tests/test_structural_harness_adapter.py` collection error for missing
  `sisypy`.
- Live/agentic evidence is info-level only. The provider readiness probe passed,
  but the exact approved live command deselected all live tests without the
  repo's live opt-in flag.

## Extension Guidance

Future precedent-backed patterns should follow the same path:

1. Add route-signal vocabulary only for normalized `adapt`.
2. Add deterministic builder evidence and a golden execution-plan fixture.
3. Express semantic obligations with the shared `ExecutionPlan` contract.
4. Add evaluator/runtime fixtures for complete, disconnected, missing-path, and
   unsupported evidence cases.
5. Add ordinary-route bypass tests near the new vocabulary.
6. Keep executor plan payloads nested under
   `execution_protocol_notes.execution_plan`.
7. Keep queue/runtime availability separate from deterministic semantic plan
   validation unless the condition is an explicit graph obligation.

## Final State

The epic has reached the intended M1-M4 shape: precedent-backed edits can carry
an explicit plan, runtime validation refuses disconnected sidecar completions,
ordinary edits stay ordinary, and rollout has concrete guardrails. T12 remains
the authoritative final validation/classification step before shipping.
