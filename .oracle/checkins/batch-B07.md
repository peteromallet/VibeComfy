B07 CHECKPOINT VERDICT: PASS — explicit transport pin authoritative, ambient selection eliminated, decision doc honest (INCONCLUSIVE, OpenRouter retained as policy), no-flag default pinned to OpenRouter; 33 focused tests green.
I'll review B07-lite as a read-only oracle: first load the megado/oracle guidance and the batch tasklist, then inspect the B06→B07 diff against the seven review focuses.The review is read-only and tightly coupled to the B06→B07 delta, so I’ll validate the tasklist, the commit range, and the focused test slice myself rather than re-delegate the gate.HEAD includes the original B07 commit plus a later FAIL record and rework2. Next I’ll read the B07-lite acceptance criteria and the actual transport plumbing.Previous FAIL was probe confounders plus a residual env-skip. I’ll now verify whether rework2 actually closed those holes in the code, tests, and decision doc.Selector and env-skip look present. Next I’ll read runner/runtime/tests and run the focused transport slice.Plumbing looks coherent so far. I’ll read the remaining resolution paths, inspect the probe report against the decision doc, and run the focused tests.The remaining risk is whether Hermes still honors `provider="openrouter"` over the pinned `base_url`. I’ll check worker dispatch, research/phase paths, and run the focused tests.Tests are green (33 passed). I’ll confirm the exact user filter, whether the Flash slug is just the default classify model, and that provenance/redaction still hold.B07 CHECKPOINT VERDICT: PASS — Selector, pin precedence, ambient isolation, B01 provenance, and an honest INCONCLUSIVE OpenRouter-as-policy decision all hold; live probe numbers stay non-comparable.

## Focus findings

### 1. Selector plumbing — PASS
`--transport {openrouter,native}` is threaded CLI → `run_tag` → child argv + pinned env → `run_single` → `adapter._ensure_transport_env` → `VIBECOMFY_TRANSPORT` → `runtime._explicit_transport` → `_base_url_for_route` / `_hermes_credential_for` / `_build_agent_kwargs`.

- `runner.py:508` / `:550` resolve `transport=None` to `_HARNESS_DEFAULT_TRANSPORT` (`openrouter`) before spawn.
- `runner.py:604–606` always forwards `--transport` and `env=_pinned_child_env(transport)`.
- Classify and reply go through `provider.run_model_turn` → `runtime.run_model_turn` → `_build_agent_kwargs`. Implement/batch go through `run_agent_turn*` → the same builder. Research is Hivemind/local corpus, not a Hermes transport phase.
- `test_transport_flag_and_pinned_child_env_survive_subprocess_isolation` locks child flag + stripped transport keys.

No Hermes phase with an explicit pin falls back to an inherited base URL. The four-phase regression still loops `_build_agent_kwargs` rather than calling `run_classify_turn` / `run_agent_turn` / `run_reply_turn`; those entry points share the builder, so this is a test-shape nit, not a hole.

### 2. Ambient credentials cannot silently change transport — PASS
Pinned child env strips `_TRANSPORT_SELECTING_ENV_KEYS` and keeps `OPENROUTER_API_KEY` / `DEEPSEEK_API_KEY`. Runtime and adapter both skip those keys when hydrating `~/.hermes/.env` / the local credential file (the previous residual). `_ensure_transport_env` rewrites `VIBECOMFY_OPENROUTER_BASE_URL` unconditionally.

Conflicting-key lock is present: OpenRouter key + `--transport native` → `https://api.deepseek.com/v1` + `DEEPSEEK_API_KEY` on kwargs, worker observation, and `_runtime_provider_transport` (`test_transport_native_pin_wins_over_ambient_openrouter_key_on_all_phases`).

No-flag default is now OpenRouter, not ambient native: `test_transport_omitted_resolves_to_openrouter_default_not_ambient_native` asserts the child gets `--transport openrouter`, ambient `VIBECOMFY_TRANSPORT=native` is stripped, and the run record is `openrouter`.

Direct `run_headless_scenario(transport=None)` still honors an already-set `VIBECOMFY_TRANSPORT` env pin (adapter priority: arg → env pin → default). That is an operator pin, not a credential. The harness path never leaves that door open.

### 3. Explicit pin authoritative over route default — PASS
`_base_url_for_route` is pin-first (`runtime.py:464–471`): native pin → `https://api.deepseek.com/v1`; openrouter pin → canonical OpenRouter; route default only when unset. `_hermes_credential_for` prefers `DEEPSEEK_API_KEY` under a native pin so a stale `sk-or-*` cannot win. `_is_native_deepseek_endpoint` is pin-first too.

Corrected lock: `test_transport_native_pin_wins_over_route_openrouter_default` (`route="openrouter"` + pin → native endpoint/key/slug). The older `test_explicit_openrouter_route_cannot_be_hijacked_by_generic_endpoint_or_key_overrides` still protects the **unpinned** product OpenRouter route; it does not re-lock route-over-pin.

### 4. B01 provenance consumed — PASS
No second attempt schema. Runner copies child `model_attempts` and records selection separately as `summary["transport"]`. `test_observed_transport_provenance_passthrough_matches_selection` asserts no rewrite.

Live probe attempts (even the confounded B06 ones) carry requested/resolved model, provider, transport, endpoint, finish reason, tokens, attempt — 79/79 native and 60/60 OpenRouter rows have the required keys. Failure previews still go through `ModelAttemptEvidence` redaction; no `sk-or-` / bearer material in attempt previews. The “redacted native key” assert still uses `DEEPSEEK_API_KEY="***"` as the actual key value — sloppy comment, not a second format.

### 5. Probe comparability and written decision — PASS (INCONCLUSIVE, as required)
Precommitted set is real: 10 IDs, `profile=default` (classify/reply flash, implement/research pro — not an all-Flash profile), `max_workers=2`, timeout 1800, `infra_retries=1`. Descriptor SHAs still match the current scenario files. No prompt rewrite in the B07 range. Historical typed-empty evidence correctly marked unrestored.

The only matched report (`out/b07-probe/probe_report.json`, recorded HEAD `19f57396`) remains **not** a quality comparison:

| Arm | Observed == selected? | What it actually measured |
| --- | --- | --- |
| native | **false** — all 30 `agent_turn` rows → OpenRouter | pre-rework route-default leak |
| openrouter | true | 10/10 credit-dead (`ProviderCreditError` / “not enough credits” / 403 key-limit), typed as `infra_empty_response` |

Rework2 did the right thing: `.oracle/measurements/b07-transport-decision.md` retains OpenRouter **as policy**, marks the probe **INCONCLUSIVE**, names both confounders, and tells B09 to pass `--transport openrouter` explicitly. It does not cite 1/10 or empty-rate as quality. No second OpenRouter 10-lane was run.

### 6. Scope — PASS
`git diff --stat 19f57396..1e401e2b` is 12 B07 files (briefs, previous FAIL check-in, decision doc, probe script, adapter, runner, two test files, `runtime.py`, `provider.py`). `git diff --check 19f57396..dcb135d6` and `19f57396..1e401e2b` are both clean. No all-Flash profile, no prompt rewrite.

### 7. Focused slice — PASS
```
33 passed, 43 deselected in 3.91s
```
(`-p no:rerunfailures`, exact user `-k transport|provenance|ambient|redact|endpoint|openrouter|native`). One more than the executor’s “32” because rework2 added the default-transport / env-skip tests; they match the same filter.

`--help | grep --transport` prints the usage synopsis **and** the option help line (`--transport {openrouter,native}`). Selector is present; argparse always emits both.

---

Previous FAIL items are closed: honest decision doc, no credit-dead re-run, adapter env-skip mirror, no-flag default pinned to OpenRouter. Do not start B08 on a “native has no advantage” finding. Retain OpenRouter; treat B07’s live numbers as non-comparable.
