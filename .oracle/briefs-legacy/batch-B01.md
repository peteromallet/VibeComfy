# B01 — Truthful classification and typed model-failure evidence (HARD — grok)

Executor: grok (GPT-class, per user directive: grok is the extremely hard task doer).
Repo: /Users/peteromalley/Documents/reigh-workspace/vibecomfy (branch main).
Work in place; DO NOT commit. Run the verification commands yourself; report PASS/FAIL with outputs.

## Tasks

1. **Remove the fake classification fallback and make phase failure explicit.**
   - Touch as required: `vibecomfy/executor/core.py`, `vibecomfy/executor/contracts.py`, `vibecomfy/executor/agent_backend.py`, `vibecomfy/executor/provenance.py`, `vibecomfy/agent/artifacts.py`, `tests/test_executor_contracts.py`, and focused executor/artifact tests.
   - Replace failure-time `ClassifyDecision.respond_only()` artifacts with `classification_status: success|failed` and a nullable decision/plan. Preserve a typed phase failure without inventing `intent=respond` or `route=respond`.
   - Keep successful public response compatibility where it is truthful; update internal/report contracts deliberately rather than smuggling a sentinel `ClassifyDecision` through them.

2. **Type empty provider responses and persist complete failed-call provenance.**
   - Touch as required: `vibecomfy/comfy_nodes/agent/worker.py`, `vibecomfy/comfy_nodes/agent/runtime.py`, `vibecomfy/comfy_nodes/agent/provider.py`, `vibecomfy/executor/agent_backend.py`, `vibecomfy/agent/artifacts.py`, `tests/test_agent_runtime_adapter.py`, `tests/test_headless_agent_artifacts.py`.
   - Distinguish `empty_response` from malformed nonempty JSON. Retry empty responses as fresh transport attempts; keep reply-side exhaustion as a presentation warning where the product contract allows it.
   - Every failed model call must persist: phase, parse reason, zero/nonzero completion-token flag (and count when known), finish reason, bounded raw preview, requested and resolved model, adapter/provider, and endpoint/base URL. Never persist credentials.

3. Make infra retry classification evidence-based.
   - Touch: `tests/live_agentic_harness/runner.py`, `tests/test_live_agentic_runner_persistence.py`.
   - Classify a parse failure as retryable infrastructure only when evidence says `completion_tokens == 0` and `parse_reason == empty` (or the equivalent typed fields). The phrase "could not be parsed" alone is insufficient. A nonzero-token parser/contract failure stays `product_fail` and does not receive the subprocess infra retry.

## Verification (run all; exit 0 expected)

```bash
.venv/bin/python -m pytest -q \
  tests/test_executor_classify_only.py \
  tests/test_executor_contracts.py \
  tests/test_executor_flows.py \
  tests/test_agent_runtime_adapter.py \
  tests/test_headless_agent_artifacts.py \
  tests/test_live_agentic_runner_persistence.py \
  -k 'classification_failure_is_nullable_and_truthful or empty_worker_output_is_typed_empty_response or nonempty_invalid_json_remains_malformed_model_json or failed_model_call_artifact_has_complete_provenance or zero_token_empty_parse_is_retryable_infra or nonzero_token_parse_failure_is_product_fail or parse_phrase_without_evidence_is_product_fail'
```

```bash
.venv/bin/python -m pytest -q tests/test_executor_classify_only.py tests/test_executor_contracts.py tests/test_executor_flows.py tests/test_agent_runtime_adapter.py tests/test_headless_agent_artifacts.py tests/test_live_agentic_runner_persistence.py tests/test_runtime_worker_retry.py
```

## Acceptance criteria

- A classify exception produces `classification_status=failed` and no fabricated decision, intent, or route.
- Empty output and malformed nonempty JSON are distinct typed failures at the worker, executor, artifact, and runner boundaries.
- 100% of deterministic failed-call fixtures contain the complete provenance field set; previews are bounded and secrets are absent.
- Zero-token/empty parse evidence becomes `retryable_infra` and reaches the existing retry; nonzero-token parse failures and phrase-only summaries remain `product_fail` with one attempt.
- Existing timeout/capacity retries and soft-search-429 non-retry controls remain green.

## Report
"B01 VERDICT: PASS|FAIL|BLOCKED — <one line>" + per-task changes (file:line), verification outputs, residuals. DO NOT commit.
