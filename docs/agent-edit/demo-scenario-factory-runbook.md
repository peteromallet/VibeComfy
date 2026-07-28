# Demo Scenario Factory Runbook

This runbook is the operating contract for an agent that continuously creates,
runs, evaluates, and archives VibeComfy agent-edit demo candidates.

The factory's unit of work is not “a plausible prompt plus a graph diff.” It is
an experiment:

```text
proven-good workflow
  -> one recorded, reversible fault
  -> proof that the fault is effective
  -> a public user-shaped inquiry
  -> one or more real fixer attempts
  -> proof that the candidate did or did not repair the fault
```

The agent should repeat this loop until it reaches the operator's explicit
case, cost, or time limit. It must archive failures as carefully as successes.

## Copy-Paste Agent Brief

Give the following brief to the agent running the campaign:

```text
Read docs/agent-edit/demo-scenario-factory-runbook.md completely and operate
one demo-scenario-factory campaign exactly as specified.

Campaign goal: continually produce independently reviewable VibeComfy
broken-workflow -> inquiry -> fixer-result experiments.

Do not promote a case merely because the agent returned a candidate or wrote a
convincing explanation. A case only passes when its hidden deterministic
repair oracle passes. Behavioral claims also require the specified runtime
evidence. Record every baseline rejection, ineffective mutation, provider
failure, fixer failure, repair failure, and success in the campaign artifacts.

Only create realistic cases. The injected fault must resemble a mistake a
person, workflow author, version migration, or editing agent could plausibly
make. The public inquiry must describe only what a real user could actually
notice in the output or product. Do not invent symptoms from workflow tags or
leak the internal diagnosis into the user's wording.

Resume any incomplete case before selecting a new one. Never expose private
fault receipts, golden graphs, inverse deltas, target node IDs, or oracle
predicates to the fixer model. Keep running until the operator's stated limit
is reached.
```

The operator should add an explicit limit, for example:

```text
Stop after 25 completed cases, after five proof-complete successes, or after
$20 of recorded model/runtime cost, whichever happens first.
```

## Storage Contract

All generated material belongs under:

```text
out/demo-candidate-factory/<campaign_id>/
```

`out/` is gitignored. It may contain large graphs, transcripts, media, and
private oracle evidence without polluting the repository.

The durable repository files are:

- this runbook;
- the factory implementation and tests, once implemented;
- explicitly promoted demo assets only.

Use this campaign layout:

```text
out/demo-candidate-factory/<campaign_id>/
├── CAMPAIGN.md
├── INDEX.md
├── campaign.json
├── pool.jsonl
├── events.jsonl
├── locks/
└── cases/
    └── <case_id>/
        ├── status.json
        ├── summary.md
        ├── public/
        │   ├── scenario.json
        │   └── inquiry.md
        ├── source/
        │   ├── provenance.json
        │   ├── golden.py
        │   ├── golden.ui.json
        │   └── golden.api.json
        ├── private/
        │   ├── fault_case.json
        │   ├── fault.delta.json
        │   ├── repair.delta.json
        │   └── oracle.json
        ├── broken/
        │   ├── broken.py
        │   ├── broken.ui.json
        │   └── broken.api.json
        ├── proof/
        │   ├── baseline.json
        │   ├── fault.json
        │   ├── inverse-replay.json
        │   ├── leakage-check.json
        │   └── runtime.json
        ├── attempts/
        │   └── 001/
        │       ├── run/
        │       ├── candidate.ui.json
        │       ├── candidate.api.json
        │       ├── evaluation.json
        │       └── agent-reply.md
        ├── media/
        │   ├── golden/
        │   ├── broken/
        │   └── candidate/
        └── review/
            ├── scorecard.json
            └── promotion.md
```

The authoritative record is the case directory. `INDEX.md` is a convenient
campaign view that can always be rebuilt from `cases/*/status.json` and
`cases/*/summary.md`.

Case IDs must be opaque random identifiers. Do not encode the workflow,
mutation family, target field, or expected repair in an ID the fixer may see.

Each `status.json` moves monotonically through:

```text
SELECTED
-> BASELINE_PROVING
-> BASELINE_PROVEN
-> MUTATING
-> FAULT_PROVEN
-> FIXER_RUNNING
-> EVALUATING
-> terminal verdict
```

Write a new immutable stage receipt before advancing status. Retries go in a
new `attempts/002`, `attempts/003`, and so on; never overwrite an earlier
attempt.

## Campaign Files

### `campaign.json`

Record at least:

```json
{
  "schema_version": "demo_factory_campaign_v1",
  "campaign_id": "20260723-001",
  "created_at": "ISO-8601",
  "status": "running",
  "seed": 20260723,
  "limits": {
    "max_completed_cases": 25,
    "max_successes": 5,
    "max_cost_usd": 20
  },
  "selection": {
    "ready_weight": 0.7,
    "runtime_proven_external_weight": 0.3
  },
  "counts": {},
  "cost_usd": 0
}
```

### `INDEX.md`

Use one row per fixer attempt:

```markdown
# Demo Candidate Campaign <campaign_id>

| Case | Attempt | Source | Fault family | Inquiry | Baseline | Fault proof | Fixer | Repair oracle | Runtime | Verdict | Evidence |
|---|---:|---|---|---|---|---|---|---|---|---|---|
| c-... | 1 | video/wan_i2v | conditioning-loss | The first frame... | PASS | PASS | candidate | PASS | PASS | PASS | cases/c-.../summary.md |
```

Allowed verdicts:

- `BASELINE_REJECTED`
- `MUTATION_REJECTED`
- `INFRA_BLOCKED`
- `FIXER_FAILED`
- `REPAIR_FAILED`
- `UNDETERMINED`
- `PASS`
- `PROMOTED`

Never turn missing evidence into `PASS`. Use `UNDETERMINED`.

### `events.jsonl`

Append one machine-readable event for every state transition. Only the campaign
coordinator writes this file. Parallel workers write inside their own case
directories and return results to the coordinator.

If the campaign uses parallel workers, each worker must first create an
exclusive claim under `locks/<case_id>`. Workers never edit `INDEX.md`,
`events.jsonl`, or `campaign.json` directly. The coordinator incorporates
completed case receipts idempotently. Corrections supersede earlier events;
they do not rewrite history.

## Workflow Supply

The supply is finite at any one commit but effectively unbounded across:

- a growing ready-template library;
- thousands of external workflows;
- multiple applicable fault families;
- multiple valid mutation loci per graph;
- multiple seeds and public symptom phrasings;
- newly ingested community workflows.

Do not repeatedly test the same `(source content hash, fault family, locus,
mutation parameters)` signature.

## Realism Contract

A mutation being schema-valid does not make it a good scenario. Every case
must pass two separate realism gates.

### Fault realism

The fault must match a plausible error archetype, preferably backed by at least
one of:

- a real VibeComfy/ComfyUI incident or support conversation;
- a prior agent-edit failure transcript;
- a bug or migration failure from an issue tracker;
- an error found in a real community workflow;
- a common manual editing mistake supported by node/socket semantics;
- a version drift or renamed-slot/default change supported by exact node-pack
  history.

Good archetypes include:

- selecting the wrong one of two type-compatible outputs;
- connecting positive and negative conditioning in reverse;
- leaving export connected to an earlier stage after adding a refinement pass;
- changing a visible widget that is overridden by a linked primitive;
- adjusting FPS when the real intent requires changing frame count;
- switching model families without replacing its conditioning path;
- disabling or bypassing a preprocessor while its downstream stage remains;
- preserving a stale edge during a workflow migration.

Avoid arbitrary sabotage that a user or editing agent would be unlikely to
produce, such as deleting random nodes merely to make validation fail. Prefer
one subtle causal defect over several simultaneous defects.

Write the fault's provenance to `private/fault_case.json`:

```json
{
  "realism": {
    "archetype": "final-output-left-on-coarse-stage",
    "evidence_kind": "prior-agent-failure|real-workflow|issue|common-edit",
    "evidence_reference": "...",
    "why_plausible": "...",
    "user_observable_effect": "..."
  }
}
```

The reference may be sanitized, but it cannot be “the authoring model thought
this sounded plausible.”

### Symptom realism

The inquiry must be grounded in an observation demonstrated by the broken case.
Examples include:

- the saved image still has its original dimensions;
- the first video frame no longer resembles the supplied image;
- the exported artifact matches the coarse preview rather than the refined
  preview;
- an img2img result no longer preserves the source composition;
- a cloned voice measurably loses similarity to the reference speaker.

Do not claim “flicker,” “plastic skin,” “mask ignored,” “random noise,”
“identity loss,” or another quality symptom unless the broken execution or a
case-specific metric actually demonstrates it.

The public inquiry should normally:

- use the language of an intermediate creative-tool user, not an implementer;
- say what they expected and what they observed;
- mention relevant visible inputs or stages only if the UI exposes them;
- avoid node IDs, socket names, class names, hidden settings, and the presumed
  root cause;
- leave enough ambiguity that the fixer must inspect the graph;
- remain short enough to sound like a genuine support request.

Good:

```text
I added the second refinement pass, but the file it saves still looks exactly
like the rough first pass. Can you figure out why the refinement isn't making
it into the export?
```

Too diagnostic:

```text
Rewire SaveVideo from SamplerCustomAdvanced node 4984 to the stage-two latent
output.
```

Unsupported fiction:

```text
The output flickers badly.
```

when the scenario has never rendered or measured flicker.

### Tier A: ready templates

Start here:

```bash
vibecomfy workflows list --ready
```

Ready Python templates live under `ready_templates/`. Their original UI graphs
usually live under `ready_templates/sources/`.

Only admit baselines with:

- a declared output;
- successful validation and API compilation;
- resolved widgets and output slots;
- exact schema evidence;
- required node packs available or reproducibly installable;
- no known semantic quarantine.

### Tier B: runtime-proven external workflows

Discover candidates through:

```bash
vibecomfy workflows list
vibecomfy search "<capability or technique>" --limit 20 --json
```

Source data lives in:

- `external_workflows/manifest.json`;
- `external_workflows/corpus/*.json`;
- `external_workflow_index.json`.

An external workflow is precedent, not a good baseline, until it passes the
same baseline gates as a ready template and has a successful pinned-runtime
receipt for any behavioral claim.

### Continuing to enlarge the pool

Use the existing ingestion/search processes to add GitHub, Hivemind, Discord,
and official/custom-node example workflows. Ingestion creates candidates; it
does not certify them.

## Reproducible Random Selection

Randomness must be seeded and replayable.

1. Build `pool.jsonl` from currently eligible workflows.
2. Remove signatures already present in this campaign or earlier campaigns.
3. Enforce modality and fault-family diversity.
4. Select from the remaining pool using the campaign seed plus iteration
   number.
5. Persist the selected source record before loading or modifying the graph.

Recommended default weighting:

- 70% ready templates;
- 30% runtime-proven external workflows;
- at most one selected case per source/fault-family pair per campaign;
- no more than two final top-five cases from the same model family;
- no more than one final top-five case from the same fault family.

If no mutation is applicable, record `MUTATION_REJECTED` and select another
workflow. Do not force a fault into an unsuitable graph.

## Materializing the Golden Workflow

### Ready template

Ready templates are already Python. Copy one into the case directory for an
immutable campaign snapshot:

```bash
vibecomfy copy-to-recipe <ready_id> \
  --out <case>/source/golden.py \
  --strip-markers
```

Export its graph:

```bash
vibecomfy port export <ready_id> \
  --ready \
  --to ui \
  --out <case>/source/golden.ui.json
```

Compile/export API JSON as the execution projection. Preserve source layout
when a layout-bearing source graph exists; layout churn must not become part of
the semantic mutation.

### External UI/API workflow

The live fixer can consume the graph directly. Python is optional, but useful
for human inspection and controlled mutation:

```bash
vibecomfy port check <workflow.json> --json
vibecomfy port convert <workflow.json> \
  --out <case>/source/golden.py \
  --json
```

Export the converted Python back to UI and API, then prove parity with the
source execution projection. Reject unexplained conversion loss.

## Baseline Proof

Run the cheap gates before mutation:

```bash
vibecomfy inspect <workflow>
vibecomfy validate <workflow>
vibecomfy doctor <workflow> --json
vibecomfy analyze info <workflow>
```

Also require:

- UI-to-API conversion through the ComfyUI oracle;
- output reachability;
- exact node and field resolution;
- pinned custom-node/model environment evidence;
- a successful baseline execution when the later symptom is behavioral.

Write every result to `proof/baseline.json`. A failed baseline is
`BASELINE_REJECTED`, not a fixer failure.

## Fault Injection

Inject exactly one causal fault using the canonical typed edit operations in
`vibecomfy/porting/edit/ops.py`.

Initial operator catalog:

- required-edge cut;
- same-type conditioning polarity/source swap;
- image/reference-conditioning loss;
- final-output branch bypass;
- effective parameter corruption;
- disabled preprocessor or stage;
- wrong compatible output slot;
- stale static override masking a dynamic value.

Every operator must declare:

- applicability predicate;
- forward delta;
- inverse delta;
- affected causal slice;
- broken predicate;
- repaired predicate;
- expected user-visible effect;
- required proof tier.

Do not let an LLM freely edit JSON to create the fault. An LLM may propose
operator/locus candidates, but deterministic code must validate and apply the
chosen mutation.

## Fault Proof

Before calling the fixer:

1. Prove the forward delta landed.
2. Prove the broken predicate now fails.
3. Prove the affected value/edge is effective and output-reachable.
4. Apply the inverse delta to a copy.
5. Prove the execution projection returns to the golden projection.
6. For behavioral cases, run golden and broken with identical inputs, seed,
   model, and node versions and prove the expected divergence.

Reject observationally equivalent mutations. In particular, a visually
present edge or mask is not effective merely because it is connected.

## Public Inquiry

Generate `public/inquiry.md` only after fault proof passes.

The authoring model receives a sanitized effect card, such as:

```text
Modality: video
Observed effect: the saved artifact comes from the coarse first stage even
though the refinement stage still executes.
User expertise: intermediate
```

It must not receive:

- golden graph or Python;
- mutation operator;
- forward/inverse delta;
- node IDs, class names, field names, or socket names;
- private oracle predicates;
- expected repair.

Run a leakage check over the final inquiry and the fixer's
`model_request.json`. Persist it to `proof/leakage-check.json`.

Generate two or three candidate phrasings, then select the one that is:

1. fully supported by the observed broken evidence;
2. natural user language;
3. non-prescriptive about the repair;
4. specific enough to recognize success;
5. free of private diagnostic leakage.

Store the rejected phrasings and rejection reasons privately so the campaign
can improve its authoring policy over time.

## Running the Fixer

Create `public/scenario.json` with the broken UI graph embedded as `graph`:

```json
{
  "id": "<opaque_case_id>",
  "query": "<contents of inquiry.md>",
  "graph": {},
  "apply": true,
  "network": true,
  "timeout": 600,
  "assessment": {
    "expect_graph_changed": true,
    "skip_intent_judge": false
  }
}
```

Run one or more cases:

```bash
python -m tests.live_agentic_harness.runner \
  --tag <campaign_id> \
  --scenarios-dir <campaign>/dispatch \
  --output-base <campaign>/runner-output \
  --max-workers 5 \
  --per-scenario-timeout 1200 \
  --json
```

Copy or reference the complete durable run evidence under
`cases/<case_id>/attempts/<attempt>/run/`.

Run at least three independent attempts for candidates being considered for
the final five. Provider/rate-limit failures are `INFRA_BLOCKED` and may be
retried without changing the case.

The headless path produces a candidate but does not prove browser
Apply/finalization. Browser transaction verification is a separate promotion
gate.

## Evaluation

Evaluate in this order:

1. **Execution safety:** candidate validates, compiles, loads, and preserves a
   reachable output.
2. **Fault removal:** the hidden broken predicate is false.
3. **Repair postcondition:** the semantic repaired predicate is true.
4. **Collateral fence:** execution-relevant changes outside the allowed causal
   slice are absent.
5. **Non-no-op proof:** candidate is not observationally equivalent to the
   broken graph.
6. **Behavioral recovery:** when the inquiry makes a behavioral claim, the
   golden/broken/candidate run metric demonstrates damage and recovery.
7. **Narrative honesty:** the agent reply agrees with its actual delta and
   evidence.

Accept sound alternative repairs. Exact golden-graph restoration is a strong
reference result, not the only passing shape.

Use LLM judges only for graded semantic quality. They cannot override a failed
deterministic or runtime oracle.

## Updating `summary.md` and `INDEX.md`

Each attempt's `summary.md` should contain:

```markdown
# <case_id>: <short title>

- Source:
- Source hash:
- Fault family:
- Fault locus:
- Public inquiry:
- Baseline verdict:
- Fault-proof verdict:
- Fixer outcome:
- Repair-oracle verdict:
- Runtime verdict:
- Final verdict:
- Cost:
- Duration:

## What changed

## What the agent believed

## What the engine allowed

## Why the verdict follows from evidence

## Artifact links
```

After an attempt is fully written, add its row to `INDEX.md` and append a
completion event to `events.jsonl`. Never write the success row before its
oracle files are durable.

Do not silently edit an older ledger row to change its verdict. Append a
correction row referencing the superseded case/attempt, then rebuild the
human-readable current summary if needed.

On restart:

1. Read `campaign.json`.
2. Scan `cases/*/status.json`.
3. Resume the oldest non-terminal case.
4. Rebuild `INDEX.md` if it disagrees with case summaries.
5. Select a new case only when no resumable case remains.

## Ranking the Best Five

Hard gates come first. A case with missing causal proof cannot rank.

For proof-complete survivors, use:

- semantic proof: 35%;
- first-attempt and three-run repair stability: 25%;
- demonstrated realism and demo clarity: 15%;
- novelty: 10%;
- reproducibility: 10%;
- cost: 5%.

The top five must be diverse across source, model family, modality where
possible, and fault family.

## Promotion Gate

A case may enter `demo_scenarios.json` only when:

- its case verdict is `PASS`;
- its fault has non-LLM-only realism evidence;
- the inquiry describes an effect demonstrated by the archived broken case;
- all private/public leakage checks pass;
- behavioral claims have runtime evidence;
- at least two of three fixer attempts pass, with first-attempt success
  reported rather than hidden;
- a human has reviewed `review/promotion.md`;
- the browser preview accurately represents the archived graph pair;
- browser Apply/finalization succeeds;
- the demo bundle excludes the private fault receipt and golden oracle.

`scripts/build_demo_scenario_assets.py` currently validates packaging and graph
shape, not semantic proof. Until it is extended, the campaign proof manifest
and human approval are mandatory external gates.

## Initial Five Families

Start with:

1. `image/basic_image_upscale`: final output bypasses the upscale stage.
2. `video/wan_i2v`: effective start-image conditioning is lost.
3. `video/ltx2_3_lightricks_two_stage`: export uses the coarse pass.
4. `image/z_image_img2img`: effective denoise destroys source structure.
5. `audio/qwen3_tts_voice_clone`: reference-audio conditioning is bypassed.

The first implementation/smoke case should be `image/basic_image_upscale`
because its output-size oracle is deterministic and inexpensive.
