# B09 — Deterministic full gate and 2×2 transport/profile experiment

Executor: DeepSeek V4 Flash (normal executor) for orchestration of the runs; measurement artifact written by the orchestrator.
Repo: /Users/peteromalley/Documents/reigh-workspace/vibecomfy (branch main).

## Tasks

1. Run the deterministic repository gate after all repairs.
   - Touch production/test code: none. Test-failure fixes must be routed back through the oracle to the owning earlier batch; do not patch forward inside B09.

2. Run the complete live 2×2 matrix after credentials/readiness are confirmed.
   - Matrix: `{openrouter,native} × {default,all_flash}` over all 100 scenarios in `tests/live_agentic_harness/scenarios/`, with the same runner concurrency/retry settings and unique tags.
   - Commands (the runner may exit nonzero for genuine scenario failures; a complete persisted summary is required):

```bash
.venv/bin/python -m tests.live_agentic_harness.runner --tag megado-openrouter-default --transport openrouter --profile default --max-workers 6 --infra-retries 1 --json
.venv/bin/python -m tests.live_agentic_harness.runner --tag megado-openrouter-all-flash --transport openrouter --profile all_flash --max-workers 6 --infra-retries 1 --json
.venv/bin/python -m tests.live_agentic_harness.runner --tag megado-native-default --transport native --profile default --max-workers 6 --infra-retries 1 --json
.venv/bin/python -m tests.live_agentic_harness.runner --tag megado-native-all-flash --transport native --profile all_flash --max-workers 6 --infra-retries 1 --json
```

3. Produce a durable comparison report.
   - Touch: `.oracle/measurements/transport-profile-matrix.md` (new) and, if useful, machine-readable `.oracle/measurements/transport-profile-matrix.json`.
   - Derive every number from the four persisted `run_summary.json` files and referenced attempt artifacts. Report per lane and per scenario class: first-attempt true pass, eventual-after-retry true pass, infra-adjusted pass, matcher-only failures, empty-response rate, nonzero parser-contract failures, refusal pass/fail/undetermined and judge availability, semantic-repair eligible/attempted/succeeded/repeated-fingerprint counts, resolved models, latency, tokens, estimated cost, and UI-artifact coverage.
   - Separate product failures from infra failures. Include scenario IDs behind every discrepancy and recommend whether to keep default or adopt all-Flash; do not change the product profile in this batch.

## Verification

```bash
make full-pytest
```

Expected: the non-GPU suite exits 0.

```bash
.venv/bin/python - <<'PY'
import json
from pathlib import Path
tags = (
    'megado-openrouter-default',
    'megado-openrouter-all-flash',
    'megado-native-default',
    'megado-native-all-flash',
)
for tag in tags:
    path = Path('out/agentic') / tag / 'run_summary.json'
    data = json.loads(path.read_text())
    assert data['complete'] is True, tag
    assert len(data['scenarios']) == 100, tag
print('4 complete lanes; 400 scenario results')
PY
```

Expected: exactly `4 complete lanes; 400 scenario results`.

```bash
test -s .oracle/measurements/transport-profile-matrix.md
```

Expected: exit 0.

## Acceptance criteria

- The full deterministic non-GPU suite passes.
- All four live lanes finish 100/100 scenarios; blocked or interrupted lanes are rerun/resumed before comparison.
- The nine matcher false-positive cases are no longer matcher failures, while genuine contradiction controls remain enforced.
- Failed-call evidence coverage is 100%; zero nonzero-token parser failures are labeled infra; zero uid-less `pin_opaque` emissions occur.
- The 90a1d5 preservation assertions and semantic broadcast/repointing controls remain green in the final suite.
- Repair, refusal, UI coverage, transport/model, latency, token, cost, and pass-rate metrics are all reported from evidence, with unknown values labeled unknown rather than inferred.
- The profile recommendation cites per-class quality and reliability tradeoffs; no profile flip occurs without a later oracle-approved revision.

## Report
"B09 VERDICT: PASS|FAIL|BLOCKED — <one line>" + gate outputs, lane summaries, report path, residuals. DO NOT commit measurement-only artifacts unless the orchestrator asks.
