# B07 — Explicit transport selection and actual runtime provenance

Executor: DeepSeek V4 Flash (normal executor).
Repo: /Users/peteromalley/Documents/reigh-workspace/vibecomfy (branch main).
Work in place; DO NOT commit. Run the verification commands yourself; report PASS/FAIL with outputs.

## Tasks

1. Add an explicit benchmark transport option while keeping product routing canonical.
   - Touch: `tests/live_agentic_harness/runner.py`, `tests/live_agentic_harness/adapter.py`, `tests/test_live_agentic_runner_persistence.py`, and adapter tests.
   - Add `--transport {openrouter,native}` and plumb it explicitly into each scenario process. Default product/harness behavior must not silently switch because a credential happens to exist. `openrouter` resolves to OpenRouter's canonical endpoint; `native` resolves to `https://api.deepseek.com/v1` and uses the native key/model normalization.

2. Record actual, stage-resolved transport/model provenance.
   - Touch as required: `vibecomfy/comfy_nodes/agent/runtime.py`, `vibecomfy/comfy_nodes/agent/worker.py`, `vibecomfy/agent/artifacts.py`, `tests/test_agent_runtime_adapter.py`, `tests/test_headless_agent_artifacts.py`.
   - For every model turn record stage, requested and resolved model, adapter, provider, normalized base URL/endpoint, and transport. The report must reflect the values actually sent to the adapter, not readiness labels or environment intent. Redact keys and query parameters.

## Verification (run all; exit 0 expected)

```bash
.venv/bin/python -m pytest -q \
  tests/test_agent_runtime_adapter.py \
  tests/test_live_agentic_runner_persistence.py \
  tests/test_headless_agent_artifacts.py \
  -k 'explicit_transport or actual_runtime_provenance or transport_does_not_follow_ambient_credential or transport_provenance_redacts_secrets'
```

```bash
.venv/bin/python -m tests.live_agentic_harness.runner --help | grep -F -- '--transport {openrouter,native}'
```

Expected: one matching help line and exit 0.

## Acceptance criteria

- The same scenario can be deliberately run on either transport without `VIBECOMFY_FORCE_MODEL` and without mutating the judge model.
- OpenRouter is the canonical default; native DeepSeek is an explicit benchmark lane.
- Runtime evidence identifies actual adapter/provider/base URL/model for classify, research, implement, and reply where those stages run.
- No API key, authorization header, or URL secret appears in artifacts.

## Report
"B07 VERDICT: PASS|FAIL|BLOCKED — <one line>" + per-task changes (file:line), verification outputs, residuals. DO NOT commit.
