# MEGADO BATCH B07-lite — Explicit transport experiment (Flash executor)

Repo: /Users/peteromalley/Documents/reigh-workspace/vibecomfy-oracle (branch oracle-run). Python: `.venv/bin/python`. You have file/web/terminal tools. Skip formatters/linters/full suites; run focused tests only.

## Context
The harness currently selects transport via ambient credentials — the adapter hydrates a local `.env` and rewrites the base URL (`tests/live_agentic_harness/adapter.py:20`), and runtime imports `~/.hermes/.env` (`vibecomfy/comfy_nodes/agent/runtime.py:196`). B01 already provides unified attempt provenance (requested/resolved model, adapter, provider, transport, endpoint, finish reason, tokens, attempt — redacted). The persistent-empty failures cluster on OpenRouter; June's baseline was native DeepSeek. This batch makes transport explicit and runs a small matched probe.

## Tasks (from .oracle/tasklist.md B07-lite)

1. **Add the smallest explicit harness selector `--transport {openrouter,native}`**.
2. **Eliminate ambient-credential transport selection** — default product/harness behavior must NOT silently switch because a credential happens to exist.
3. **Consume B01's actual successful/failed provenance** — do not create a second metadata format.
4. **If historical call artifacts are restored**, determine their actual transports rather than trusting readiness labels. (They are NOT restored — record that.)
5. **Run an approximately ten-scenario matched native/OpenRouter experiment** on the same commit, scenario set, profile, and configuration.
6. **Keep OpenRouter canonical** unless a material repeatable advantage receives later oracle approval.

## Sense-check precommit (adversary predictions — cover these FIRST)

From `.oracle/sensecheck-remaining-2026-08-13.md`:
1. **Selector must survive subprocess isolation.** `run_tag()` constructs child commands at `tests/live_agentic_harness/runner.py:543`; transport must pass explicitly CLI → child → adapter → every profile phase (classify/research/implement/reply).
2. **Ambient credentials still win.** Adapter hydrates local `.env` (`adapter.py:20`) + runtime imports `~/.hermes/.env` (`runtime.py:196`). Use a pinned child environment; test conflicting keys/base URLs (ambient key present but `--transport native` must still resolve to `https://api.deepseek.com/v1` with the native key).
3. **False comparability.** Precommit the ten scenario IDs + model/profile/concurrency/timeout + configuration digest. Assert every B01 attempt's OBSERVED transport matches selection. Since historical typed-empty evidence is absent, call this a DETERMINISTIC PROBE — not "empty-heavy" — unless the selection basis is restored.

## Key files
- `tests/live_agentic_harness/runner.py` (`run_tag` `:543`, child command construction), `adapter.py` (`:20` env hydration), `tests/test_live_agentic_runner_persistence.py`
- `vibecomfy/comfy_nodes/agent/runtime.py` (`:196` hermes env import), `worker.py`, `provider.py` (transport resolution)
- `vibecomfy/agent/artifacts.py`, `tests/test_agent_runtime_adapter.py`, `tests/test_headless_agent_artifacts.py`

## Verification (run, retain output)
```bash
.venv/bin/python -m pytest -p no:rerunfailures -q tests/test_agent_runtime_adapter.py tests/test_live_agentic_runner_persistence.py tests/test_headless_agent_artifacts.py -k 'transport or provenance or ambient or redact or endpoint or openrouter or native'
```
Plus:
```bash
.venv/bin/python -m tests.live_agentic_harness.runner --help | grep -F -- '--transport'
```
Expected: one matching help line and exit 0.

## Acceptance (from tasklist)
- Ambient credentials cannot silently change transport.
- Every attempt reports requested/resolved model, provider, transport, endpoint, finish reason, tokens, attempt.
- Secrets remain redacted.
- The experiment reports scenario IDs, typed-empty rate, attempts, latency, configuration digest.
- No all-Flash profile or prompt rewrite introduced.
- A written decision retains OpenRouter or proposes a separately approved change.

## Report
Return: selector plumbing (CLI→child→adapter→phases), the pinned-environment approach, the ten precommitted scenario IDs + digest, observed-vs-selected transport assertion, probe results, pytest output. Do NOT commit.
