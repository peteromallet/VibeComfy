# B07-lite transport probe — decision (Rework 2)

Status: **INCONCLUSIVE** — do NOT cite any B07 live number as a quality result.

## 1. Decision (policy, retained)

**OpenRouter remains the product/canonical transport — as policy, not as a
measured result.** The B07 probe's live numbers are non-comparable (below) and
provide no basis for a transport-quality call in either direction. OpenRouter is
retained because it is the canonical product route; `native` remains an explicit
benchmark lane (`--transport native`) for future apples-to-apples measurement,
never a default and never a policy choice derived from this probe.

## 2. Probe verdict: INCONCLUSIVE

The only matched probe report (`out/b07-probe/probe_report.json`, recorded HEAD
`19f57396`) is **not evidence** for a transport quality comparison:

| Arm | Recorded HEAD | Result | Observed == selected? |
| --- | --- | --- | --- |
| native | `19f57396` (B06), not `dcb135d6` | 1/10 pass, 31/79 typed-empty | **false** — `agent_turn` resolved to `https://openrouter.ai/api/v1` |
| openrouter | same | 0/10, 60/60 typed-empty | true |

## 3. Confounders (explicit)

1. **Native arm: transport mismatch.** The native lane ran with
   `observed_transport_matches_selection=false` at implement/`agent_turn`: the
   implement phase resolved to the OpenRouter endpoint (the pre-rework
   route-default bug). Classify/batch/reply ran native while implement ran
   OpenRouter, so "1/10 native" is not a native measurement.
2. **OpenRouter arm: credit-dead.** All 10 OpenRouter scenarios returned
   `infra_empty_response` because of billing — *"account does not have enough
   credits for the requested token budget."* 100% empty / 0/10 is a billing
   wipe typed as empty, not an empty-rate measurement.

Therefore: do not cite 1/10, "39% vs 100% empty", or "empties on both
transports" anywhere as quality results. No second OpenRouter 10-lane may run
until credits exist (re-running credit-dead would reproduce 0/10 and waste the
lane).

## 4. Instruction to B09 (and product-correctness note)

- **B09 must pass `--transport openrouter` explicitly** on every harness
  invocation. The explicit flag is the documented canonical invocation and
  makes the transport self-documenting in the run record.
- This rework (B07 rework 2, on top of `dcb135d6`) also **pins the runner's
  no-flag default to OpenRouter**:
  - `adapter._HARNESS_DEFAULT_TRANSPORT = "openrouter"` (was `"native"`);
  - `runner.run_tag` / `runner.run_single` resolve `transport=None` to
    `_HARNESS_DEFAULT_TRANSPORT` before spawning children, so a no-flag run is
    pinned to OpenRouter and an ambient `VIBECOMFY_TRANSPORT=native` can never
    leak into the child;
  - `adapter._load_credential_env_file` mirrors
    `runtime._load_env_file_into_environ`: it skips
    `_TRANSPORT_SELECTING_ENV_KEYS`, so an ambient `.env` cannot set
    `VIBECOMFY_TRANSPORT` when the flag is absent.
- `--transport native` remains the explicit benchmark lane for a future
  credit-funded, single-variable comparison (native arm must re-run on
  `dcb135d6`+ with `observed_transport_matches_selection=true`).

## 5. Rework-2 change inventory (uncommitted at time of writing)

- `tests/live_agentic_harness/adapter.py` — env-skip mirror in
  `_load_credential_env_file`; `_HARNESS_DEFAULT_TRANSPORT = "openrouter"`.
- `tests/live_agentic_harness/runner.py` — no-flag default resolves to
  OpenRouter in `run_tag`/`run_single`; `--transport` help text updated.
- `tests/test_agent_runtime_adapter.py` — default-transport regression flipped
  to openrouter; new adapter env-skip mirror test.
- `tests/test_live_agentic_runner_persistence.py` — no-flag regression asserts
  `--transport openrouter` on the child, ambient native pin stripped, run
  records `transport: "openrouter"`.
