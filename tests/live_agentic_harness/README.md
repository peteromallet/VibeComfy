# Live Agentic Tests

This directory is for **live agentic tests only**: real executor paths with
real model/provider calls.

A test belongs here only when the subject-under-test is a real model or agent
using production-like tools, and the evidence comes from the actual run. Fake or
faking actors, deterministic builders, scripted `messages.jsonl`, and structural
contract scenarios do not belong here.

The selected live lane is fixed by `scenario_manifest.json`. Before starting
scenario subprocesses, the runner validates descriptor IDs/paths/hashes,
source-workflow IDs/paths/hashes, and exact directory membership. A missing,
changed, duplicate, or stray descriptor fails preflight. `--manifest` can select
another equally strict manifest for an explicit scenario directory.

Deterministic real-workflow agentic scenarios live in
`tests/structural_harness/` as **structural agentic tests**:

```bash
python -m tests.structural_harness.runner --mode structural --actor fake --tag run
```

## Operator Commands

Run all live-headless scenarios in this directory:

```bash
python -m tests.live_agentic_harness.runner --tag live-headless-smoke --json
```

Run against an explicit scenario directory and output root:

```bash
python -m tests.live_agentic_harness.runner \
  --tag live-headless-smoke \
  --scenarios-dir tests/live_agentic_harness/scenarios \
  --output-base out/agentic \
  --json
```

Run every scenario through the bounded two-step pipeline (classify → execute)
instead of the full research → implement → reply pipeline:

```bash
python -m tests.live_agentic_harness.runner \
  --tag live-headless-two-step --pipeline-mode two_step --json
```

`--pipeline-mode {full,two_step}` is the explicit selector: when set, an
ambient `VIBECOMFY_EXECUTOR_PIPELINE_MODE` can never displace it and the
selector is forwarded to every scenario subprocess.  When omitted, each
scenario descriptor's `pipeline_mode` key (or `_tags.pipeline_mode`) applies,
then the product default (`full`).  Every two-step scenario that does not
carry a `session_id` gets a stable per-window session id minted by the
adapter (deterministic from the scenario id, so retries and repeated runs of
the same window reuse the same session).  The effective `pipeline_mode` is
recorded on every scenario summary and the run summary; two-step summaries
also record the `session_id` used.

Each scenario writes artifacts under `out/agentic/<tag>/<scenario_id>/` and is
then checked by `tests.live_agentic_harness.guard.guard_output_dir`. A live success
requires `flow_kind=live_agentic_headless`, `live=true`, `status=success`,
`dispatcher=real`, and `model_behavior=agentic`. Fake/faking dispatchers and
non-agentic model behavior are rejected for live-headless artifacts.

Blocked provider readiness is a valid harness outcome but not a live success.
It should produce `status=blocked_prerequisite` in `flow_metadata.json` and a
nonzero runner exit when any scenario is blocked.

For the full boundary matrix, `live=false` versus `dry_run` semantics, dry-run
CLI invocation, blocked-prerequisite smoke checks, browser e2e commands, and
subprocess integration contract, see
`../../docs/testing/headless-agentic-harnesses.md`.

## Paired full/two-step comparison (B07)

`tests.live_agentic_harness.compare_pipeline_modes` (Pro B07) pairs a `full`
and a `two_step` run per scenario — both legs run the IDENTICAL locked
classification decision (frozen once by `--capture-classifications` into
`classification_lock.json`), with separate durable session roots per mode.

Validate the deterministic wiring without any model calls:

```bash
python -m tests.live_agentic_harness.compare_pipeline_modes \
  --manifest tests/live_agentic_harness/two_step_50_manifest.json --validate-only
```

The live paired runs are NOT part of the gate and are executed by the host
after the final sense-check:

```bash
python -m tests.live_agentic_harness.compare_pipeline_modes \
  --manifest tests/live_agentic_harness/two_step_50_manifest.json --tag two-step-50 \
  --capture-classifications --max-workers 4 --json
python -m tests.live_agentic_harness.compare_pipeline_modes \
  --ledger current --tag two-step-ledger-57 --capture-classifications --max-workers 4 --json
```

There are two comparator lanes:

1. **50-lane** — `two_step_50_manifest.json` references ALL 100 canonical
   descriptors with strict validation intact; 50 included / 50 excluded.
2. **57-ledger lane** — `ledger_scenario_ids()` (`vibecomfy/intent/_ledger.py`).
   The only valid `--ledger` labels are `current` (stable alias) and
   `ir-everywhere-57-v3`; `ir-everywhere-57` (and `-v2`) are INVALID legacy
   labels and must never be used for reconciliation
   (`tests/live_agentic_harness/ledger_selection.py` owns this contract).

`tests/test_live_agentic_two_step_comparison.py` covers the deterministic
contract — manifest count/hash validation, lock completeness + route
equality, pair completeness, comparator bookkeeping WITHOUT model calls, and
honest treatment of blocked provider/infra results — and skips with explicit
markers until the Pro bootstrap artifacts land.

## Rollout order

Enable two-step routes in this order (adapt stays opt-in — reported, never
auto-enabled):

1. **respond / inspect** — the non-inferiority gate routes; lowest edit risk,
   highest determinism.  These must meet the gate before anything else.
2. **simple revise / reorganise** — bounded single-edit routes on workflows
   with clean schema coverage.
3. **bounded research** — research-backed edits, still within the bounded
   two-step budget.
4. **adapt** — reported and measured in comparisons, but OPT-IN only; it is
   never enabled by default until the earlier tiers hold.
