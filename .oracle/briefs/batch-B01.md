# MEGADO BATCH B01 [HARD] — Typed failures and unified attempt provenance

Repo: /Users/peteromalley/Documents/reigh-workspace/vibecomfy-oracle (branch oracle-run). This is a [HARD] task — you are the executor (GPT-5.6 Sol, workspace-write). You may modify files and run tests. Skip formatters/linters/full suites; run focused tests only.

## Context
G0-T4 already added failed-call evidence (parse_reason, raw preview, finish reason, tokens, model, phase, endpoint) at classify+reply, and G0R closed the scorer/narrator. B01 makes model-attempt evidence a UNIFIED contract across success AND failure, typed, with redaction. B07-lite consumes this contract — do not create a second metadata format.

## Tasks (from .oracle/tasklist.md B01)

1. **One additive model-attempt evidence contract** across worker, runtime, provider/backend, executor, artifacts, and harness.
2. **Distinguish failure types**: empty response; malformed non-empty JSON; non-JSON content; missing required fields; timeout; capacity/provider failure.
3. **Persist on every successful AND failed attempt**: phase and attempt; requested and resolved model; adapter; actual provider and transport; normalized endpoint; finish reason; token usage.
4. **Persist bounded raw previews only for failures** (never for success).
5. **Fix the three success-path runtime stripping seams** (find where successful-call provenance is currently stripped/dropped in runtime/worker/agent_backend) and merge worker-observed metadata into batch audit metadata and final report artifacts.
6. **Permit a fresh-transport retry ONLY for typed empty responses** — never derive infra status from response wording (G0-T3 already gates on completion_tokens==0; keep that).
7. **Serialize unavailable non-Hermes provenance as `unknown`**; never infer.

## Key files
- vibecomfy/comfy_nodes/agent/worker.py, runtime.py, provider.py
- vibecomfy/executor/agent_backend.py, core.py, contracts.py, provenance.py
- vibecomfy/agent/artifacts.py
- tests/test_agent_runtime_adapter.py, tests/test_headless_agent_artifacts.py, tests/test_executor_contracts.py, tests/test_live_agentic_runner_persistence.py

## Verification (run, retain output)
```bash
.venv/bin/python -m pytest -q tests/test_executor_classify_only.py tests/test_executor_contracts.py tests/test_executor_flows.py tests/test_agent_runtime_adapter.py tests/test_headless_agent_artifacts.py tests/test_live_agentic_runner_persistence.py tests/test_runtime_worker_retry.py
```
Expected exit 0. Add focused tests for the typed failure distinctions and success-path provenance (fixtures: empty vs malformed non-empty vs non-JSON vs missing-field vs timeout vs capacity).

## Acceptance
- Every failure type serializes distinctly.
- Successful classify, reply, and batch calls retain provenance through final artifacts.
- Requested vs resolved model remain distinct across routing/retries.
- Typed empty evidence reaches the existing retry; malformed non-empty stays product_fail.
- Unsupported routes report explicit unknowns.
- Redaction: keys, authorization data, secret URL params cannot persist (negative fixture).

## Report
Return: contract shape (field names), files changed, failure-type taxonomy, success-path seam fixes, redaction proof, pytest output. Do NOT commit.
