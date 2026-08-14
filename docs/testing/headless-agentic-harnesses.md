# Headless And Live Harness Runbook

This runbook separates the local test lanes that touch VibeComfy's agent
surface. Keep the lane names precise: a structural harness pass is not proof of
live model behavior, and a headless dry run is not the same thing as
`live=false`.

## Lane Boundaries

| Lane | Command family | Subject under test | Requires ComfyUI server | Requires browser | Requires live model readiness |
|---|---|---|---|---|---|
| Structural harness | `python -m tests.structural_harness.runner ...` | Deterministic fake/faking builders and frozen evidence | No | No | No |
| Headless agent CLI | `python -m vibecomfy.agent ...` or `vibecomfy-agent ...` | Real executor path without ComfyUI HTTP routes | No | No | Yes, unless it intentionally records `blocked_prerequisite` |
| Live agentic harness | `python -m tests.live_agentic_harness.runner ...` | Scenario wrapper over the headless service with strict live-artifact guard | No | No | Yes for success |
| Browser harness | `pytest tests/browser/...` | JavaScript/browser-facing modules under a node/jsdom-style harness | No | No real browser | No |
| Browser e2e | `node tests/e2e/run.mjs ...` | Real ComfyUI process plus Playwright Chromium panel tests | Yes, launcher starts it | Yes | No, fixture provider is offline |

## Structural Harness

Use the structural harness when you need deterministic evidence for routing,
executor contracts, workflow topology, readiness failure handling, or
regressions that can be frozen without a real model.

```bash
python -m tests.structural_harness.runner \
  --mode structural --actor fake --tag structural-smoke
```

Run a named subset when you are checking a focused contract:

```bash
python -m tests.structural_harness.runner \
  --mode structural --actor fake --tag executor-verify \
  --name explore-hotshot-xl-workflow \
  --name distilled-faster-research-route \
  --name explain-simple-workflow
```

Evidence lands under `out/agentic/reports/<tag>/`. Structural runs stamp
`flow_metadata.json` with `flow_kind=structural_contract`, a `fake` or `faking`
dispatcher, and non-agentic model behavior. They must never be treated as live
agentic proof.

### Agent-judgment evidence scenarios (V01 suite)

The eight end-to-end agent-judgment scenarios (revise without forced research,
empty-graph authoring, research-only decision memo, headless ambiguity
`needs_input`, schema drift + approved normalization, Hivemind rate limiting,
invalid emitted socket, queue refusal with a valid runtime probe) exercise the
classify → research → implement → apply/validate → queue → reply spine through
the deterministic fake actor:

```bash
python -m tests.structural_harness.runner \
  --mode structural --actor fake --tag v02-release \
  revise-without-forced-research empty-graph-authoring \
  research-only-decision-memo headless-ambiguity-needs_input \
  schema-drift-approved-normalization hivemind-rate-limiting \
  invalid-emitted-socket queue-refusal-valid-runtime-probe
```

Evidence-pack proof level for these runs is `validated`: the F01 evidence-pack
validation resolves every citation against the IDs actually returned by the
tools, and a dangling citation fails the scenario. The scenarios freeze
request, stage packages, evidence pack, tool trace, diagnostics, and final
effect; the assessor scores effects and evidence, never exact node recipes or
prose.

### Assessment: evidence over narrative

Scoring is evidence-over-narrative everywhere the harness touches the agent
surface (`tests/live_agentic_harness/assessor.py` +
`research_assessment.py`). Research-route scenarios enforce:

- **Question-before-search** — the evidence ledger records the question before
  any tool call; an un-asked search does not count.
- **Query relevance** — tool queries must match the recorded question.
- **Hivemind invoked when required** — research-route scenarios require a
  Hivemind call; no local-search path may substitute for it.
- **Citations resolvable** — every cited evidence ID must resolve to an ID the
  tools actually returned (the citation resolver reports zero dangling IDs).
- **Evidence-pack capture** — grounding is reconstructed from the pack (tool
  inputs, result IDs, fetched records, ledger, final diff), not from reply
  prose. "Prose never gates."

Effect scoring means shared-source edit errors and prose wording never penalize
a scenario; a landing edit with resolvable evidence passes even when it is not
the exact recipe the oracle would have picked.

## Headless Agent CLI

The headless CLI sets `VIBECOMFY_HEADLESS=1` before importing the service so it
does not register ComfyUI/aiohttp routes. It writes redacted artifacts to
`--output-dir`:

```bash
python -m vibecomfy.agent \
  --query "Explain this workflow" \
  --workflow ./workflow.json \
  --output-dir out/agentic/manual/explain \
  --profile default \
  --json
```

The packaged script exposes the same surface:

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
| `--workflow PATH` | Attach a JSON workflow object to the request. |
| `--output-dir DIR`, `--output DIR` | Artifact directory for `request.json`, `response.json`, `flow_metadata.json`, and phase artifacts when available. |
| `--profile NAME` | Executor profile used to resolve provider/model readiness. |
| `--live`, `--no-live` | Metadata marker only; it does not skip readiness or model execution. |
| `--dry-run` | Classify-only executor run; skips research, implementation, and reply phases after classification. |
| `--research auto|required|disabled` | Harness metadata describing the expected research policy. |
| `--apply` | Signals intent to apply a produced candidate graph. |
| `--network`, `--no-network` | Allows or disallows network use by phases that support it. |
| `--timeout SECONDS` | Best-effort per-turn timeout metadata/control. |
| `--json` | Print the full result envelope for tools and subprocess callers. |

Exit codes are stable for operators and subprocess integrations:

| Exit code | Statuses |
|---|---|
| `0` | `success`, `dry_run` |
| `1` | `blocked_prerequisite` |
| `2` | `validation_failure`, `executor_failure`, CLI argument/load errors |

## `live=false` Versus `dry_run`

`live=false` and `dry_run` answer different questions.

`--no-live` sets `flow_metadata.json` field `live=false`. It is a provenance
marker used by guards and reports. It does not make the run deterministic, does
not bypass provider readiness, and does not turn off model calls by itself.

`--dry-run` sets `dry_run=true` and calls the executor in classify-only mode.
Readiness is still checked first because classification uses the configured
provider/model. When readiness passes, the output status is `dry_run`,
`classification.json` may be written, and research/implementation artifacts are
absent unless an upstream durable turn actually produced them.

Dry-run invocation:

```bash
python -m vibecomfy.agent \
  --query "Would this need research or implementation?" \
  --workflow ./workflow.json \
  --dry-run \
  --output-dir out/agentic/manual/classify-only \
  --json
```

Non-live metadata invocation:

```bash
python -m vibecomfy.agent \
  --query "Explain this workflow" \
  --workflow ./workflow.json \
  --no-live \
  --output-dir out/agentic/manual/non-live-metadata \
  --json
```

## Blocked-Prerequisite Checks

Missing credentials, an unresolved profile, or provider readiness failure should
produce a mechanical blocked result, not a fake success. This is expected when
live prerequisites are absent:

```bash
python -m vibecomfy.agent \
  --query "Explain this graph" \
  --profile missing-profile \
  --output-dir out/agentic/manual/blocked \
  --json
```

Expected shape:

- process exit code `1`
- result status `blocked_prerequisite`
- `response.json` with `ok=false`
- `flow_metadata.json` with `flow_kind=live_agentic_headless`,
  `dispatcher=real`, `model_behavior=agentic`, `status=blocked_prerequisite`,
  and readiness diagnostics
- no import of the ComfyUI server or browser tier

Use this path for CI-safe smoke checks of the CLI/artifact contract when live
credentials are intentionally unavailable.

## Live Agentic Harness

Use the live agentic harness for scenario-level headless runs that should count
only when real agentic artifacts are produced:

```bash
python -m tests.live_agentic_harness.runner \
  --tag live-headless-smoke \
  --json
```

Run against a custom scenario directory:

```bash
python -m tests.live_agentic_harness.runner \
  --tag live-headless-smoke \
  --scenarios-dir tests/live_agentic_harness/scenarios \
  --output-base out/agentic \
  --json
```

The harness writes each scenario to
`out/agentic/<tag>/<scenario_id>/` and then applies
`tests.live_agentic_harness.guard.guard_output_dir`. A live success requires all of:

- `flow_kind=live_agentic_headless`
- `live=true`
- `status=success`
- `dispatcher=real`
- `model_behavior=agentic`

The guard rejects `fake` or `faking` dispatchers and non-agentic model behavior
for live-headless artifacts. Blocked prerequisites are valid evidence, but they
are not live successes.

## Subprocess Use

External tools, including Astrid-style callers, should prefer the CLI
subprocess contract instead of importing VibeComfy internals:

```bash
python -m vibecomfy.agent \
  --query "Explain this graph" \
  --workflow ./workflow.json \
  --output-dir "$OUTPUT_DIR" \
  --json
```

Subprocess callers should read artifacts from `$OUTPUT_DIR` after process exit:

- `response.json` for the serialized executor/headless response
- `flow_metadata.json` for provenance, status, live/dry-run flags, and readiness
- `classification.json`, `research.json`, `implementation_payload.json`, and
  `implementation_result.json` when those phases actually ran
- copied durable turn artifacts such as `messages.jsonl`, `model_request.json`,
  and `model_response.json` only when the underlying route produced them

Treat exit code `1` plus `status=blocked_prerequisite` as an expected
environment outcome, not a malformed subprocess response.

## Browser E2E

Use browser e2e when the change touches real panel layout, scroll behavior,
LiteGraph canvas state, submit/apply flow, or overlay geometry:

```bash
node tests/e2e/run.mjs
```

Focused examples:

```bash
node tests/e2e/run.mjs -- specs/agent_panel_layout.spec.mjs
node tests/e2e/run.mjs --launcher-only
node tests/e2e/run.mjs --no-seed -- specs/agent_panel_turn.spec.mjs
```

This lane starts ComfyUI on CPU, symlinks VibeComfy into `custom_nodes`, uses the
offline fixture provider, waits for `/vibecomfy/ping` and
`/vibecomfy/agent/status`, and runs Playwright Chromium. It does not use live
model credentials and should not be used to claim live agentic behavior.

For full setup details and options, see
`../agent-edit/e2e-real-browser-tier.md`.
