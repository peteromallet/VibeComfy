# MEGADO B01 REWORK (oracle issues 1–6) — [HARD], executor: GPT-5.6 Sol, workspace-write

Repo: /Users/peteromalley/Documents/reigh-workspace/vibecomfy-oracle (branch oracle-run). You MAY modify files and run tests. Skip formatters/linters/full suites; run focused tests only. The B01 implementation from `e33f0260` is already in the tree — fix the oracle issues on top of it, do not revert.

## Oracle issues (from `.oracle/checkins/batch-B01.md`, all lines vs `e33f0260`)

### 1. Parallel evidence format must go
`vibecomfy/executor/contracts.py:122-209` defines the canonical `ModelAttemptEvidence`; `coerce_model_attempts` at `:212-222` normalizes. But `Report` still exposes BOTH canonical `model_attempts` AND legacy `model_response` (`:2302-2309`, serialized `:2354-2358`), and `vibecomfy/executor/core.py:105-128,223-238` retains a second parse-evidence vocabulary that can emit legacy `{"turns":[{"error":...}]}`.
Fix: migrate/remove the legacy `model_response` parallel evidence — one canonical persisted format. Keep any field needed for back-compat in the report but derive it FROM `model_attempts`; no second vocabulary in core.

### 2. Truthful attempt numbers across provider-level batch retries
`vibecomfy/comfy_nodes/agent/provider.py:1492-1505`: batch retries append worker-local attempts without renumbering → `[attempt=1, attempt=1]` after a retry instead of `[1,2]`.
Fix: assign monotonically increasing attempt numbers across the full retry sequence (renumber on append or carry a running counter).

### 3. Observed zero tokens vs zero-filled unavailable usage
`vibecomfy/comfy_nodes/agent/worker.py:156-163` accepts zero-filled usage even when `n_calls == 0`; `_dispatch_turn` supplies that normalized zero usage → unobserved usage appears as `completion_tokens=0` and authorizes retry.
Fix: distinguish OBSERVED zero tokens (call returned, usage reported 0) from UNAVAILABLE usage (no usage observed — `n_calls==0` or usage absent). Only observed zero tokens may authorize the fresh-transport retry; unavailable usage must not.

### 4. Redaction: complete Authorization header values
`vibecomfy/executor/contracts.py:47-50,84-97` turns `Authorization: Basic dXNlcjpwYXNz` into `Authorization: <redacted> dXNlcjpwYXNz` — the credential survives after the marker.
Fix: redact the ENTIRE header value for every scheme (Basic, Bearer, ApiKey, custom): `Authorization: <redacted>`. Add a Basic-auth negative fixture.

### 5. Never raw-copy parse-failed artifacts
`vibecomfy/agent/artifacts.py:102-116` raw-copies an entire JSON/JSONL artifact after any parse error — malformed artifacts containing secrets persist verbatim.
Fix: on parse failure, do NOT raw-copy; sanitize (run the same redaction) or omit the body entirely (keep a bounded note). Add malformed-JSON and malformed-JSONL regressions proving secrets cannot persist.

### 6. Unsupported-route provenance must be `unknown`, never inferred
`vibecomfy/comfy_nodes/agent/provider.py:901-905` preserves arbitrary routes; `runtime.py:321-333` silently maps any unmapped route to Hermes; `:472-486` assigns OpenRouter provenance; unsupported non-Hermes paths get an inferred `_ARNOLD_MODEL` at `runtime.py:350-370`.
Fix: serialize unsupported-route provenance as explicit `unknown` with NO fallback inference — no silent Hermes mapping, no OpenRouter assignment, no `_ARNOLD_MODEL` inference. Add a route-plumbing regression exercising an unsupported route end to end (not just a manually constructed contract).

## Verification (run, retain output)
```bash
.venv/bin/python -m pytest -p no:rerunfailures -q tests/test_executor_classify_only.py tests/test_executor_contracts.py tests/test_executor_flows.py tests/test_agent_runtime_adapter.py tests/test_headless_agent_artifacts.py tests/test_live_agentic_runner_persistence.py tests/test_runtime_worker_retry.py
```
Expected exit 0 (the rerunfailures plugin binds a socket and cannot run here — disable it). Add fixtures for each fix above so the suite covers them.

## Report
Return: per-issue changes (files + line refs), fixture names added, pytest output. Do NOT commit.
