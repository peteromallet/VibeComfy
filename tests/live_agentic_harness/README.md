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
