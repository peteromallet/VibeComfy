# B01 — Mode plumbing and dispatch toggle

Worktree: /private/tmp/vc-twostep (branch two-step-megado). Python: `PYENV_VERSION=3.11.11` with the repo venv at /Users/peteromalley/Documents/reigh-workspace/vibecomfy/.venv (set `PYTHONPATH=$PWD` if needed; check how other tests run first).

You are implementing batch B01 of the two-step pipeline mode megado run. Follow the frozen tasklist exactly (`.oracle/tasklist.md` → B01). Do NOT touch files outside B01's scope.

## Tasks

1. `vibecomfy/executor/contracts.py`:
   - Add `PipelineMode = Literal["full", "two_step"]`.
   - Add typed `PipelineModeRequestError` and `PipelineModeConfigurationError`.
   - Add `coerce_pipeline_mode()` and `resolve_pipeline_mode(request, environ=None)`.
   - Add optional `ExecutorRequest.pipeline_mode`.
   - Validate direct construction and `from_payload()`.
   - Preserve omission in `to_dict()` when unspecified.

2. `vibecomfy/agent/contracts.py`:
   - Add optional `HeadlessAgentRequest.pipeline_mode`.
   - Carry it through parsing and `to_executor_request()`.

3. `vibecomfy/executor/core.py`:
   - Resolve mode once for profiler/report use.
   - Preserve the existing classify and `answer_only` behavior.
   - Add the only orchestration branch immediately after the current `answer_only` block (before research begins — see core.py around 1865-1928):
     `if pipeline_mode == "two_step": return _run_two_step(...)`
   - Keep the existing research → implement → reply block structurally untouched.
   - For `classify_only`: full mode emits its existing skipped events; two-step emits only `execute: skipped`.
   - IMPORTANT guard: do NOT resolve the optional `execute` profile before the `classify_only` return.

4. Add `vibecomfy/executor/two_step.py` with the typed entrypoint seam and a test-injectable outcome boundary. Real execution lands in B03–B04, so this file should define the `_run_two_step(...)` signature, the `PipelineMode` resolution call, and a stub/typed result path that tests can inject into. Keep it minimal — no policy, prompt, or session logic yet.

5. Add `tests/fixtures/payload_contracts/agent_executor_two_step_request.json`; do NOT rewrite the existing request fixture merely to include an optional field.

6. Add:
   - `tests/test_executor_pipeline_mode.py`
   - Mode round-trip cases to `tests/test_executor_contracts.py`
   - Branch/classify-only cases to `tests/test_executor_classify_only.py`

## Acceptance gate

```bash
python -m pytest -q \
  tests/test_executor_pipeline_mode.py \
  tests/test_executor_contracts.py \
  tests/test_executor_classify_only.py \
  tests/test_executor_flows.py
```

Must prove:
- Request beats environment.
- Environment beats default.
- Invalid request value is a request error.
- Invalid environment value is a configuration error.
- Default is full.
- `classify_only` never resolves or invokes `execute`.
- `answer_only` reaches two-step only after its edit-forbidding rewrite.
- Full-mode phase calls and event payloads are unchanged.

Also run `git diff --check` and make sure existing executor tests still pass (`tests/test_executor_flows.py` is in the gate; if a broader smoke is cheap, run `tests/test_agent_executor_response.py` too).

## Constraints
- Commit only this batch's scope: `git add -A && git commit -m "B01: two-step mode plumbing + toggle"`.
- Do not start B02 work.
- Report: what changed (files), gate output (pass counts), any deviations from the tasklist.
