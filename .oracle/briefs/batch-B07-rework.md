# MEGADO B07-lite REWORK (executor-discovered + acceptance gap) — explicit transport pin must win

Repo: /Users/peteromalley/Documents/reigh-workspace/vibecomfy-oracle (branch oracle-run). Python: `.venv/bin/python`. You have file/web/terminal tools. Skip formatters/linters/full suites; run focused tests only. B07-lite implementation is in the working tree (uncommitted, from the Flash executor) — fix on top, do not revert.

## The gap (discovered by the executor during the probe; blocks acceptance)

The explicit `--transport` pin is NOT authoritative: `_base_url_for_route` in `vibecomfy/comfy_nodes/agent/runtime.py` applies the route-level OpenRouter default AFTER/OVER the selected transport, so an explicit `--transport native` still resolves to OpenRouter's endpoint for some routes. The probe showed the native arm's empties are confounded by this route-vs-pin precedence bug. Acceptance requires: "Ambient credentials cannot silently change transport" and every attempt's OBSERVED transport == selection.

## What to change

1. **Invert the precedence**: the explicit transport pin (from `--transport`, threaded CLI → child → adapter → runtime → every profile phase) must be AUTHORITATIVE over the route-level OpenRouter default in `_base_url_for_route` (runtime.py). When a pin exists, all phases resolve to the pinned transport; the route default applies only when no pin is set.
2. **Fix the one wrong-priority test** the executor identified (the test that locks in route-default-over-pin behavior).
3. **Add a conflicting-evidence regression**: ambient OpenRouter key present + `--transport native` → observed transport MUST be native (`https://api.deepseek.com/v1`), redacted, on classify/research/implement/reply.
4. Keep: selector plumbing CLI → child → adapter → phases; pinned child environment (no ambient .env leakage); B01 provenance consumed (no second format); ten precommitted scenario IDs + config digest; probe results + written decision retain OpenRouter as canonical (no all-Flash profile, no prompt rewrite).

## Verification (run, retain output)
```bash
.venv/bin/python -m pytest -p no:rerunfailures -q tests/test_agent_runtime_adapter.py tests/test_live_agentic_runner_persistence.py tests/test_headless_agent_artifacts.py -k 'transport or provenance or ambient or redact or endpoint or openrouter or native'
```
Expected exit 0, including the new pin-wins regression. Also:
```bash
.venv/bin/python -m tests.live_agentic_harness.runner --help | grep -F -- '--transport'
```
Expected: one matching help line, exit 0.

## Report
Return: exact change (file:line), the precedence rule, the fixed test, the new regression name, pytest output. Do NOT commit.
