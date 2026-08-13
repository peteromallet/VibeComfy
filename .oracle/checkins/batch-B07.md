bun(47310) MallocStackLogging: can't turn off malloc stack logging because it was not enabled.
I'll start by reading the megado oracle-gate instructions and the B07-lite tasklist so the review stays on the stated acceptance criteria.I have the B07-lite acceptance criteria. Next I’ll pull the exact commit range, oracle artifacts, and the transport plumbing so the gate is based on the code, not the executor write-up.The range is nine files and a clean whitespace check. I'll read the selector, pin, and probe paths in parallel and run the focused test slice.Plumbing is in place. Next I’ll hunt for the written OpenRouter decision, read the new tests, and run the focused slice.The surviving probe report is still on B06 (`19f57396`) and the native arm shows transport mismatches. I’ll verify whether that was re-run after the precedence fix, then inspect provenance and run the focused tests.The native probe mixed `classify`/`reply` on DeepSeek with `agent_turn` on OpenRouter. I’m tracing whether that `agent_turn` path still bypasses the pin after the rework.B07 CHECKPOINT VERDICT: FAIL — plumbing and tests hold, but the matched probe is not a comparable transport experiment, so the 1/10 “no native advantage” decision is rejected.

## Focus findings

### 1. Selector plumbing — PASS
`--transport {openrouter,native}` is wired CLI → `run_tag` → child argv → `run_single` → `adapter._ensure_transport_env` → `VIBECOMFY_TRANSPORT` → `runtime._explicit_transport` → `_base_url_for_route` → `_build_agent_kwargs`.

- `runner.py`: `_pinned_child_env` + `cmd += ["--transport", transport]` + `env=child_env`.
- `run_single` forwards `transport=` into `run_headless_scenario`.
- Classify / reply / implement / batch all build kwargs through `_build_agent_kwargs`. Research is Hivemind/local corpus, not a Hermes transport phase.
- `test_transport_flag_and_pinned_child_env_survive_subprocess_isolation` asserts the child flag and stripped env.

No phase with an explicit `--transport` falls back to an inherited base URL. The four-phase regression only loops `_build_agent_kwargs` four times (it does not call `run_classify_turn` / `run_agent_turn` / `run_reply_turn`), but those entry points share that builder.

### 2. Ambient credentials cannot silently change transport — PASS, with a residual
Pinned child env strips `_TRANSPORT_SELECTING_ENV_KEYS` and keeps `OPENROUTER_API_KEY` / `DEEPSEEK_API_KEY`. Runtime skips those keys when hydrating `~/.hermes/.env`. `_ensure_transport_env` rewrites `VIBECOMFY_OPENROUTER_BASE_URL` unconditionally.

Conflicting-key regression exists: OpenRouter key + `--transport native` → `https://api.deepseek.com/v1` + `DEEPSEEK_API_KEY` on kwargs, worker, and `_runtime_provider_transport`.

Residual, not blocking: `adapter._load_credential_env_file` (`adapter.py:20`) still hydrates **every** unset key from `brain-of-bndc/.env` when `DEEPSEEK_API_KEY` is missing, including `VIBECOMFY_TRANSPORT`. Explicit `--transport` still wins because the argument is first. Runtime’s hermes-env skip is not mirrored here.

### 3. Explicit pin authoritative over route default — PASS
`_base_url_for_route` is pin-first:

```464:471:vibecomfy/comfy_nodes/agent/runtime.py
    transport = _explicit_transport()
    if transport == "native":
        return _NATIVE_DEEPSEEK_BASE_URL
    if transport == "openrouter":
        return _CANONICAL_OPENROUTER_BASE_URL
    if (route or "").strip().lower() == "openrouter":
        return _CANONICAL_OPENROUTER_BASE_URL
    return _OPENROUTER_BASE_URL
```

That is the inversion. `_hermes_credential_for` prefers `DEEPSEEK_API_KEY` under a native pin so a stale `sk-or-*` cannot win.

Corrected lock: `test_transport_native_pin_wins_over_route_openrouter_default` (`route="openrouter"` + pin → native endpoint/key/slug). The older `test_explicit_openrouter_route_cannot_be_hijacked_by_generic_endpoint_or_key_overrides` still protects the **unpinned** product OpenRouter route; it does not re-lock route-over-pin.

### 4. B01 provenance consumed — PASS
No second attempt schema. Runner copies child `model_attempts` and records selection separately as `summary["transport"]`. `test_observed_transport_provenance_passthrough_matches_selection` asserts no rewrite.

Live probe attempts (even the confounded ones) carry requested/resolved model, provider, transport, endpoint, finish reason, tokens, attempt. Failure previews still go through `ModelAttemptEvidence` redaction (`<redacted>` test unchanged). The new “redacted native key” assert uses `DEEPSEEK_API_KEY="***"` as the actual key value — sloppy comment, not a second format.

### 5. Probe comparability and written decision — FAIL
Precommitted set is real: 10 IDs, `profile=default`, `max_workers=2`, timeout 1800, `infra_retries=1`, descriptor SHAs match the current scenario files, no all-Flash profile, no prompt rewrite. Historical typed-empty evidence is correctly marked unrestored.

The only matched report (`out/b07-probe/probe_report.json`, gitignored) is **not** evidence for a transport quality call:

| Arm | Recorded HEAD | Result | Observed == selected? |
| --- | --- | --- | --- |
| native | `19f57396` (B06), not `dcb135d6` | 1/10 pass, 31/79 typed-empty | **false** — `agent_turn` → `https://openrouter.ai/api/v1` |
| openrouter | same | 0/10, 60/60 typed-empty | true |

The native leak is exactly the pre-rework route-default bug (classify/batch/reply native; implement `agent_turn` OpenRouter). That report was not regenerated after the precedence fix.

The OpenRouter arm is not an empty-rate measurement. All 10 scenarios are `infra_empty_response` with *“account does not have enough credits for the requested token budget.”* 100% empty / 0/10 is a billing wipe, typed as empty.

There is no committed decision artifact (no `.oracle/measurements/`). The only “written decision” is the commit subject claiming OpenRouter canonical because native showed no advantage (1/10). That comparison is invalid. Task 6 still **requires** retaining OpenRouter unless a later oracle approves a measured advantage — the correct action, the wrong reason.

### 6. Scope — PASS
`git diff --stat 19f57396..dcb135d6` is 9 B07 files (briefs, probe script, adapter, runner, two test files, `runtime.py`, `provider.py`). `git diff --check` is clean. No all-Flash profile, no prompt rewrite.

### 7. Focused slice — PASS
```
32 passed, 43 deselected in 5.25s
```
(`-p no:rerunfailures`, `-k transport|provenance|ambient|redact|endpoint|openrouter|native`)

`--help | grep -- '--transport {openrouter,native}'` prints the usage synopsis plus the option help line. Selector is present.

---

## Issues (rework)

1. **`out/b07-probe/probe_report.json` (recorded commit `19f57396`; native mismatches at implement/`agent_turn`)**
   Do not cite 1/10, 39% vs 100% empty, or “empties on both transports” as a quality result.
   **Rework:** commit `.oracle/measurements/b07-transport-decision.md` that (a) retains OpenRouter as product/canonical **as policy**, (b) marks this probe **INCONCLUSIVE**, (c) states the two confounders (native `observed_transport_matches_selection=false`; OpenRouter 10/10 credit-reject typed as `infra_empty_response`), (d) tells B09 to pass `--transport openrouter` explicitly (harness no-flag default is still native).

2. **No second OpenRouter 10-lane until credits exist.** A credit-dead re-run will reproduce 0/10 and waste the lane. Native-only live smoke on `dcb135d6` is optional; `test_transport_native_pin_wins_over_route_openrouter_default` already locks the fixed precedence.

3. **Residual, not blocking:** `adapter._load_credential_env_file` should skip `_TRANSPORT_SELECTING_ENV_KEYS` the same way `runtime._load_env_file_into_environ` does.

Do not start B08 on a “native has no advantage” finding. Retain OpenRouter; treat B07’s live numbers as non-comparable.
