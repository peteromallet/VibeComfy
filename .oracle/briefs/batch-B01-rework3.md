# MEGADO B01 REWORK 3 (oracle finding 5) — JSON-shaped preview redaction

Repo: /Users/peteromalley/Documents/reigh-workspace/vibecomfy-oracle (branch oracle-run). Python: `.venv/bin/python`. You have file/web/terminal tools. Skip formatters/linters/full suites; run focused tests only. B01 is in the tree at `1bd1b04b` — fix on top, do not revert.

## The issue (B01 oracle FAIL, finding 5)

`redact_model_preview` in `vibecomfy/executor/contracts.py` (patterns at `:47-55,87-103`) does not recognize SENSITIVE JSON-QUOTED KEYS. Direct probe: these remain unchanged through `redact_model_preview()` and `ModelAttemptEvidence.to_dict()`:

```json
{"api_key":"sk-secret"}
{"authorization":"Basic dXNlcjpwYXNz"}
{"token":"tok-secret"}
```

The leak reaches durable artifacts because `vibecomfy/agent/artifacts.py:143-150` delegates `raw_response_preview` to the same redactor before `model_attempts.json` is written (`:428-435`).

Plain-text authorization headers and secret URL params are already covered; the gap is JSON-shaped failure previews where the secret sits in a quoted value.

## What to change

1. In `vibecomfy/executor/contracts.py` `redact_model_preview` (and any other redactor it delegates to): also redact quoted sensitive JSON fields inside the preview string — API keys (`api_key`, `apikey`, `api-key`), authorization values (`authorization`, `Authorization`, `auth`), and tokens (`token`, `access_token`, `refresh_token`), for both `"key":"value"` and `'key':'value'` quoting. Handle malformed JSON safely (never crash; best-effort redaction of recognizable patterns).
2. Confirm `vibecomfy/agent/artifacts.py:143-150` uses the fixed redactor so `model_attempts.json` cannot reintroduce the secrets.
3. Add regressions:
   - contract-level: `redact_model_preview` / `ModelAttemptEvidence.to_dict()` on a preview containing the three JSON-quoted secrets → all redacted;
   - durable: `model_attempts.json` written through the artifact path contains no `sk-secret`/Basic credential/token value.

## Verification (run, retain output)

```bash
.venv/bin/python -m pytest -p no:rerunfailures -q tests/test_executor_contracts.py tests/test_headless_agent_artifacts.py tests/test_live_agentic_runner_persistence.py
```

Add fixtures to those files so the slice covers them. Expected exit 0.

## Report
Return: exact changes (files + line refs), fixture names, pytest output. Do NOT commit.
