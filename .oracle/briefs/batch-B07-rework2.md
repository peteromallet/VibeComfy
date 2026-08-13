# MEGADO B07-lite REWORK 2 (oracle issues) — honest probe decision + env-skip

Repo: /Users/peteromalley/Documents/reigh-workspace/vibecomfy-oracle (branch oracle-run). Python: `.venv/bin/python`. You have file/web/terminal tools. Skip formatters/linters/full suites; run focused tests only. B07 is committed at `dcb135d6` — fix on top, do not revert.

## Oracle issues (from .oracle/checkins/batch-B07.md)

1. **Probe report is confounded — do NOT cite 1/10, 39% vs 100% empty, or "empties on both transports" as quality results.** The native arm had `observed_transport_matches_selection=false` at implement/agent_turn; the OpenRouter arm ran CREDIT-DEAD (10/10 credit rejections typed as `infra_empty_response`). Rework: commit `.oracle/measurements/b07-transport-decision.md` that:
   - (a) retains OpenRouter as product/canonical **as policy**;
   - (b) marks this probe **INCONCLUSIVE**;
   - (c) states the two confounders explicitly (native mismatch; OpenRouter credit-dead);
   - (d) instructs B09 to pass `--transport openrouter` explicitly (harness no-flag default is still native — this is a real product-correctness note: the runner's default transport must be pinned to OpenRouter, the canonical product route, NOT ambient native).
2. **Do NOT run a second OpenRouter 10-lane until credits exist.** No re-run now.
3. **Residual fix (non-blocking but cheap):** `tests/live_agentic_harness/adapter.py:20` `_load_credential_env_file` should skip `_TRANSPORT_SELECTING_ENV_KEYS` the same way `runtime._load_env_file_into_environ` does (mirror the skip so ambient `.env` cannot set `VIBECOMFY_TRANSPORT` when the explicit flag is absent AND the default is OpenRouter).

## Also fix (issue 1d implies it)
- The harness runner's DEFAULT transport (no `--transport` flag) must resolve to OpenRouter (canonical product route), not ambient/native. Add/adjust the regression that asserts the no-flag default is openrouter. Keep `--transport native` as the explicit benchmark lane.

## Verification (run, retain output)
```bash
.venv/bin/python -m pytest -p no:rerunfailures -q tests/test_agent_runtime_adapter.py tests/test_live_agentic_runner_persistence.py tests/test_headless_agent_artifacts.py -k 'transport or provenance or ambient or redact or endpoint or openrouter or native or default'
```
Expected exit 0. `.oracle/measurements/b07-transport-decision.md` present and correct.

## Report
Return: decision doc contents, the default-transport change (file:line + regression), the env-skip mirror, pytest output. Do NOT commit.
