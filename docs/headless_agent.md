# Headless And Live Agent Boundaries And Operator Commands

This page defines the current headless agent lanes and the commands operators
can run without starting the ComfyUI server. Keep these names precise:
structural harness evidence is not live model evidence, `live=false` is not a
dry-run switch, and browser e2e coverage proves the panel path rather than the
headless path.

## Boundary Matrix

| Lane | Command family | What it proves | Needs ComfyUI server | Needs browser | Needs live model readiness |
|---|---|---|---|---|---|
| Structural harness | `python -m tests.structural_harness.runner ...` | Deterministic fake/faking contract evidence | No | No | No |
| Headless CLI/service | `python -m vibecomfy.agent ...`, `vibecomfy-agent ...` | Real executor path without HTTP route registration | No | No | Yes, unless blocked |
| Live agentic harness | `python -m tests.live_agentic_harness.runner ...` | Scenario wrapper over the headless service with live-artifact guards | No | No | Yes for success |
| Browser harness | `pytest tests/browser/...` | Browser-facing JavaScript modules in the local test harness | No | No real browser | No |
| Browser e2e | `node tests/e2e/run.mjs ...` | Real ComfyUI panel flow through Playwright Chromium | Yes | Yes | No, fixture provider is offline |

## Structural Harness

Use the structural harness for deterministic checks over routing, executor
contracts, workflow topology, readiness failure handling, and frozen evidence
that does not require a real model.

```bash
python -m tests.structural_harness.runner \
  --mode structural --actor fake --tag structural-smoke
```

Run named scenarios for a focused contract check:

```bash
python -m tests.structural_harness.runner \
  --mode structural --actor fake --tag executor-verify \
  --name explore-hotshot-xl-workflow \
  --name distilled-faster-research-route \
  --name explain-simple-workflow
```

Evidence is written under `out/agentic/reports/<tag>/`. Structural runs stamp
`flow_metadata.json` as structural contract evidence with a `fake` or `faking`
dispatcher and non-agentic model behavior. They must not be reported as live
agentic success.

## Headless CLI And Service

The CLI sets `VIBECOMFY_HEADLESS=1` before importing `vibecomfy.agent.service`.
The service enforces that flag before route-adjacent imports, so a headless run
does not register ComfyUI/aiohttp routes or require the browser panel.

```bash
python -m vibecomfy.agent \
  --query "Explain this workflow" \
  --workflow ./workflow.json \
  --output-dir out/agentic/manual/explain \
  --profile default \
  --json
```

The packaged console command exposes the same contract:

```bash
vibecomfy-agent \
  "Is there a distilled or faster way to run this?" \
  --workflow ./workflow.json \
  --output out/agentic/manual/distilled \
  --research auto \
  --json
```

Important flags:

| Flag | Meaning |
|---|---|
| `--workflow PATH` | Load a JSON workflow object into the request. |
| `--output-dir DIR`, `--output DIR` | Artifact directory for `request.json`, `response.json`, `flow_metadata.json`, and available phase artifacts. |
| `--profile NAME` | Executor profile used to resolve provider/model readiness. |
| `--live`, `--no-live` | Metadata marker only; it does not bypass readiness or disable model calls. |
| `--dry-run` | Classify-only executor mode after readiness passes; skips research, implementation, and reply phases. |
| `--research auto|required|disabled` | Harness metadata describing the expected research policy. |
| `--apply` | Signal intent to apply a produced candidate graph. |
| `--network`, `--no-network` | `--network` permits the provider-backed turn. `--no-network` refuses before provider readiness and executor dispatch because configured provider/subprocess backends are not locally attested as offline; it does not claim partial offline execution. |
| `--timeout SECONDS` | Best-effort per-turn timeout metadata/control. |
| `--json` | Print the full result envelope for tools and subprocess callers. |

Exit codes are stable:

| Exit code | Statuses |
|---|---|
| `0` | `success`, `dry_run` |
| `1` | `blocked_prerequisite` |
| `2` | `validation_failure`, `executor_failure`, CLI argument or load errors |

## `live=false` Versus `dry_run`

`live=false` and `dry_run` are separate controls.

`--no-live` records `live=false` in `flow_metadata.json`. It is provenance for
guards and reports. It does not make the run deterministic, skip provider
readiness, disable the executor, or prevent model calls by itself.

`--dry-run` records `dry_run=true` and asks the executor to run classify-only.
Readiness is still checked first because classification uses the configured
provider/model. When readiness passes, the status is `dry_run`; classification
artifacts may be written, while research, implementation, and reply artifacts
are absent unless an upstream durable turn actually produced them.

Dry-run example:

```bash
python -m vibecomfy.agent \
  --query "Would this need research or implementation?" \
  --workflow ./workflow.json \
  --dry-run \
  --output-dir out/agentic/manual/classify-only \
  --json
```

Non-live metadata example:

```bash
python -m vibecomfy.agent \
  --query "Explain this workflow" \
  --workflow ./workflow.json \
  --no-live \
  --output-dir out/agentic/manual/non-live-metadata \
  --json
```

## Blocked Checks

Missing credentials, missing provider readiness, or an unresolved profile must
produce `blocked_prerequisite`, not fake success:

```bash
python -m vibecomfy.agent \
  --query "Explain this graph" \
  --profile missing-profile \
  --output-dir out/agentic/manual/blocked \
  --json
```

Expected blocked shape:

- process exit code `1`
- result status `blocked_prerequisite`
- `response.json` with `ok=false`
- `flow_metadata.json` with `flow_kind=live_agentic_headless`,
  `dispatcher=real`, `model_behavior=agentic`,
  `status=blocked_prerequisite`, and readiness diagnostics
- no ComfyUI server, aiohttp route registration, browser tier, or Playwright

This is the CI-safe smoke path for the headless CLI/artifact contract when live
credentials are intentionally unavailable.

## Live Harness

Use the live agentic harness when a scenario should only count as success if it
produces real headless agentic artifacts:

```bash
python -m tests.live_agentic_harness.runner \
  --tag live-headless-smoke \
  --json
```

Run against an explicit scenario directory and output root:

```bash
python -m tests.live_agentic_harness.runner \
  --tag live-headless-smoke \
  --scenarios-dir tests/live_agentic_harness/scenarios \
  --output-base out/agentic \
  --json
```

Each scenario writes to `out/agentic/<tag>/<scenario_id>/` and is checked by
`tests.live_agentic_harness.guard.guard_output_dir`. A live success requires all of:

- `flow_kind=live_agentic_headless`
- `live=true`
- `status=success`
- `dispatcher=real`
- `model_behavior=agentic`

Blocked prerequisites are valid evidence that the environment was not ready,
but they are not live successes. The guard rejects fake/faking dispatchers and
non-agentic model behavior for live-headless artifacts.

## Subprocess Usage

External callers, including Astrid-style integrations, should use the CLI
subprocess contract instead of importing VibeComfy internals:

```bash
python -m vibecomfy.agent \
  --query "Explain this graph" \
  --workflow ./workflow.json \
  --output-dir "$OUTPUT_DIR" \
  --json
```

After process exit, read artifacts from `$OUTPUT_DIR`:

- `response.json` for the serialized executor/headless response
- `flow_metadata.json` for provenance, status, live/dry-run flags, and readiness
- `classification.json`, `research.json`, `implementation_payload.json`, and
  `implementation_result.json` when those phases actually ran
- copied durable turn artifacts such as `messages.jsonl`, `model_request.json`,
  and `model_response.json` only when the underlying route produced them

Treat exit code `1` plus `status=blocked_prerequisite` as an expected
environment outcome, not a malformed subprocess response.

## Browser E2E

Use browser e2e for real panel layout, scroll behavior, LiteGraph canvas state,
submit/apply flow, and overlay geometry:

```bash
node tests/e2e/run.mjs
```

Focused examples:

```bash
node tests/e2e/run.mjs -- specs/agent_panel_layout.spec.mjs
node tests/e2e/run.mjs --launcher-only
node tests/e2e/run.mjs --no-seed -- specs/agent_panel_turn.spec.mjs
```

This lane starts ComfyUI on CPU, symlinks VibeComfy into `custom_nodes`, uses
the offline fixture provider, waits for `/vibecomfy/ping` and
`/vibecomfy/agent/status`, and runs Playwright Chromium. It does not use live
model credentials and should not be used to claim live headless agent behavior.

For additional testing-lane context, see
`docs/testing/headless-agentic-harnesses.md`.
