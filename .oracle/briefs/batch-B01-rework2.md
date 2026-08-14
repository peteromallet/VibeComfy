# MEGADO B01 REWORK 2 (oracle issues 4+5) — Flash executor

Repo: /Users/peteromalley/Documents/reigh-workspace/vibecomfy-oracle (branch oracle-run). Python: `.venv/bin/python`. You have file/web/terminal tools. Skip formatters/linters/full suites; run focused tests only. B01 is in the tree at `a8d4974a` — fix on top, do not revert.

## Issue A — harness retry trusts stale flags (oracle finding 4)

`tests/live_agentic_harness/runner.py:266`: after typed classification returns no match, the runner still trusts preexisting `failure_class == "infra_empty_response"` and `retryable_infra is True` persisted flags. A summary with those flags PLUS canonical `malformed_json` evidence with zero tokens returns retryable — reproduced: `_provider_infra_failure_class(summary) -> None` but `_is_retryable_infra_summary(summary) -> True`.

Fix: derive retryability directly from the CANONICAL typed evidence (`model_attempts` failure type + observed completion tokens) on EVERY decision; never trust inherited `failure_class`/`retryable_infra` flags. Add a conflicting-flags regression: persisted `failure_class=infra_empty_response` + `retryable_infra=True` but canonical evidence `malformed_json` → NOT retryable.

## Issue B — artifact sanitization misses ordinary string leaves (oracle finding 5)

`vibecomfy/agent/artifacts.py:62`: sanitization applies only when the KEY is sensitive (`*_key`, `token`, `authorization` variants, `endpoint`, `raw_response_preview`). Parsed artifacts can persist secrets embedded in ordinary fields — reproduced: `{"content": "Authorization: Basic dXNlcjpwYXNz", "url": "https://example.test/v1?token=url-secret"}` persists BOTH unchanged.

Fix: sanitize authorization headers and credential-bearing URLs in EVERY persisted string leaf, including ordinary `content`, `message`, `error`, `url` fields — recursively walk the artifact, and on any string: redact full `Authorization: <scheme> <credential>` header values (every scheme), redact credential-like URL query params (token/key/sig/signature/api_key/apikey/secret + auth header inside url values), and leave everything else untouched. Add negative fixtures: a parsed JSON artifact and a synthesized response both containing secrets in ordinary fields must come out fully redacted.

## Verification (run, retain output)

```bash
.venv/bin/python -m pytest -p no:rerunfailures -q tests/test_headless_agent_artifacts.py tests/test_live_agentic_runner_persistence.py tests/test_runtime_worker_retry.py
```

Add your new fixtures to those files so the slice covers them. Expected exit 0.

## Report
Return: exact changes (files + line refs), fixture names, pytest output. Do NOT commit.
