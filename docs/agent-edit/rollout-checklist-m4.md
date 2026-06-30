# M4 Rollout Checklist

## Rollout Gates

Do not roll out the M4 plan-backed enforcement unless all required gates below
are satisfied by T12 final validation or by equivalent newer evidence.

| Gate | Required evidence | Current M4 evidence |
|---|---|---|
| Contract/evaluator stability | `/root/.pyenv/versions/3.11.11/bin/python3 -m pytest tests/test_execution_plan_contracts.py tests/test_execution_plan_evaluator.py -q` passes | Baseline: 7 passed |
| Builder/runtime stability | `/root/.pyenv/versions/3.11.11/bin/python3 -m pytest tests/test_execution_plan_builder.py tests/test_execution_plan_runtime.py -q` passes | Baseline: 39 passed |
| Ordinary executor routes | `/root/.pyenv/versions/3.11.11/bin/python3 -m pytest tests/test_execution_plan_builder.py tests/test_executor_flows.py -q` passes | T6: 180 passed, 2 warnings |
| HotShotXL sidecar fail-closed | `tests/test_comfy_nodes_agent_edit.py` no longer fails `test_handle_agent_edit_hotshotxl_sidecar_done_remains_non_applyable` | T3/T7: sidecar failure removed |
| Complete HotShotXL plan acceptance | Runtime plus agent-edit coverage shows `plan_validate_ok=true` and separate `queue_blocked_warning` | T4: complete-plan queue-warning test was not among failures |
| Retry guardrail | Premature `done()` is refused with compact feedback and corrected plan succeeds within retry budget | T5 coverage added and passed within file run |
| Public response compatibility | No public top-level `execution_plan`; legacy aliases, debug gates, artifact refs, failed-plan non-applyability remain stable | T7 coverage added; file run had only pre-recorded non-T7 failures |
| Structural evidence or limitation | Structural HotShotXL graph evidence captured, or exact local limitation plus semantic fallback documented | T8: M4 structural module passed; direct HotShotXL structural path limited by missing `sisypy` |
| Live evidence | Capture when available; otherwise record as info-level unavailable/skipped | T9: command deselected live tests without `--run-live`; not a must-pass blocker |

## Pre-Rollout Verification Commands

Run the scoped final validation sequence once in the foreground:

```bash
/root/.pyenv/versions/3.11.11/bin/python3 -m pytest tests/test_execution_plan_contracts.py tests/test_execution_plan_evaluator.py -q
/root/.pyenv/versions/3.11.11/bin/python3 -m pytest tests/test_execution_plan_builder.py tests/test_execution_plan_runtime.py -q
/root/.pyenv/versions/3.11.11/bin/python3 -m pytest tests/test_executor_flows.py -q
/root/.pyenv/versions/3.11.11/bin/python3 -m pytest tests/test_comfy_nodes_agent_edit.py -q
/root/.pyenv/versions/3.11.11/bin/python3 -m pytest tests/test_structural_golden_m4.py -q
```

When live prerequisites are intentionally enabled and the environment supports
repo live-test opt-in, run the live harness with the project-approved live flag
as a separate info-level evidence capture. The exact M4 command
`/root/.pyenv/versions/3.11.11/bin/python3 -m pytest tests/test_agentic_harness_live.py -q`
was already attempted and deselected all three live tests.

## Artifact Inspection Checklist

For a rejected sidecar-only HotShotXL turn:

- `response.json` has `gates.plan_validate_ok=false`.
- `response.json` has `debug.gates.plan_validate_ok=false`.
- Public candidate/apply aliases do not imply applyability.
- `execution_plan_status.ok=false` and `execution_plan_status.blocking=true`.
- `execution_plan_status.failed_condition_ids` names the disconnected active
  path condition, such as the video terminal or active output condition.
- `task_satisfaction` contains a failed `execution_plan` check.
- `artifacts.execution_plan` points to `execution_plan.json`.
- `artifacts.plan_evaluation` points to `plan_evaluation.json`.
- `debug.execution_plan_artifacts.execution_plan.sha256` and
  `debug.execution_plan_artifacts.plan_evaluation.sha256` are present.
- `model_response.json` persists the compact refused-`done()` plan feedback.

For a complete HotShotXL turn:

- `response.json` has `gates.plan_validate_ok=true`.
- `response.json` has `debug.gates.plan_validate_ok=true`.
- `plan_evaluation.json` has `ok=true` and `blocking=false`.
- Queue blockers, if present, remain under queue/apply state and appear as
  `apply_eligibility.reason="queue_blocked_warning"`.
- Queue blockers do not change `plan_validate_ok`.

For a non-plan route smoke check:

- Prompt text edit remains a `revise` route.
- Seed edit remains a `revise` route.
- CFG edit remains a `revise` route.
- Sampler-step edit remains a `revise` route.
- Simple model-name edit remains a `revise` route.
- Simple local rewire remains a `revise` route.
- Simple output-node edit remains a `revise` route.
- None of the above calls research, calls `build_execution_plan`, serializes
  `execution_protocol_notes.execution_plan`, or exposes a public top-level
  `execution_plan`.
- Candidate/apply eligibility remains the ordinary route result, with no
  plan-backed no-candidate reason.

## Compatibility Checks

- Existing public response consumers must continue to read `outcome.kind` as
  one of `candidate`, `noop`, `clarify`, or `error`.
- Candidate aliases and apply aliases remain available for legacy consumers.
- Plan-backed responses expose plan state through `execution_plan_status`,
  `gates.plan_validate_ok`, `debug.gates.plan_validate_ok`, artifact paths, and
  debug artifact refs.
- Plan-backed responses do not expose a public top-level `execution_plan`.
- Executor payloads put plans only under
  `execution_protocol_notes.execution_plan.plan`.
- Branches that still treat executor notes as advisory must ignore or hydrate
  the nested payload; they must not invent a second response shape.
- Queue validation stays outside the execution-plan semantic gate.

## Rollback Signals

Rollback or disable the plan-backed enforcement path if any of these appear:

- A disconnected HotShotXL/AnimateDiff sidecar returns applyable or candidate
  aliases that imply applyability.
- `done()` succeeds while `plan_evaluation.json` reports `ok=false` or
  `blocking=true`.
- `plan_validate_ok` is missing from `gates` or disagrees with
  `debug.gates.plan_validate_ok`.
- Complete HotShotXL active-path candidates fail semantic plan validation while
  the evaluator artifact shows all required conditions satisfied.
- Queue blockers are reclassified as execution-plan failures without explicit
  deterministic graph obligations.
- Ordinary prompt, seed, CFG, sampler-step, model, local rewire, or output-node
  edits start receiving nested execution-plan payloads.
- Public responses start exposing a top-level `execution_plan`.
- `execution_plan.json` or `plan_evaluation.json` artifacts are absent for a
  plan-backed turn.

## Limitation Handling

- Missing direct HotShotXL structural evidence is acceptable only when the
  exact harness limitation is recorded: local structural adapter collection
  depends on missing `sisypy`, and the approved M4 structural command covers
  M4 Wan/LTX scenarios rather than the `_M6_BUILDERS` HotShotXL scenario.
- Missing live/agentic evidence is info-level when the exact command and
  deselection reason are recorded.
- Do not fix unrelated dirty-tree or broad-suite failures during rollout unless
  T12 shows they block the HotShotXL sidecar fail-closed, complete-plan
  acceptance, ordinary-route boundary, or public response compatibility gates.
