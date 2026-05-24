# Agent-readable templates — v2 project plan

**Status:** active
**Started:** 2026-05-17
**Owner:** POM
**Megaplan ticket:** `01KRVVCNW5NV08FBJT9GC81553`
**Smoke-test template:** `ready_templates/video/ltx2_3_first_last_frame_travel_iclora_control.py`

This plan executes the second iteration of the agent-readable template format project. It assumes the v1 codemod (`tools/narrate_template.py`) has been built, run on the LTX template, and critiqued by three independent subagents. This document captures every decision from that loop and lays out the architecture, phases, contracts, and success criteria for v2.

Read this document end-to-end before working on any phase. Every phase assumes the others; the interface contracts below are load-bearing.

---

## 1. Why this exists

VibeComfy's `ready_templates/**/*.py` files are how users (and LLM agents acting on their behalf) configure ComfyUI workflows in Python instead of JSON. There are currently 64 templates in the repo. Reading them end-to-end as an LLM agent is hard: variables are named after node *classes* not their *role*, output slots are positional (`.out(0)` / `.out(1)`) with no slot semantics, widget aliases are opaque (`widget_0=11` for community nodes), tunables are scattered throughout the build function, and branch selection (e.g. which of canny/pose/depth/raw control mode is active) is implicit in graph topology.

The goal is a representation that an LLM agent can read cold, understand without cross-referencing external schemas, and edit safely. The bar is functional: an agent told "change the negative prompt" should make that change in one place; an agent told "switch the control mode" should not have to hunt through 500 lines of wiring.

---

## 2. What we settled on in the v1 loop

These are decisions. Phases below assume them. Do not relitigate.

### 2.1 The Narrative Python form is canonical

A design session prototyped three styles in parallel (Narrative Python — verbose hand-authored with discipline; Declarative Data — dict literals walked by a generic builder; Dataflow DSL — operator overloading like `model = UNETLoader() >> LoraLoader() >> Sage()`). **Narrative was chosen** because:

- It introduces ~zero new concepts for agents to learn.
- DSL pays for elegance with primary-input ambiguity for community nodes, escape-hatch frequency, and novelty cost.
- Declarative's superpower (structural diffing) is better expressed as a generated projection from Narrative than as the source itself.

Declarative Data may exist later as a `port export --form declarative` projection for tooling, but it's lower priority and out of scope for v2.

### 2.2 JSON in `workflow_corpus/` is canonical source-of-truth

Python templates are a generated artifact. `port convert` is the compiler. The migration path is: re-emit from JSON when the JSON changes, atomic-swap the Python file.

Hand-curated knowledge that can't be inferred from JSON (intent prose, intentional forks, reversed-port warnings) lives in `READY_METADATA["annotations"]` keyed by node id; the emitter injects entries as inline comments at the matching call site. This is how human knowledge survives regeneration.

### 2.3 The six convergence points

All three design styles in the v1 loop independently converged on these as the agent-readability floor. The Narrative form must deliver all six:

1. **Hoist tunables to module-top constants** (`PARAMS` dict).
2. **Variables named by role, not class** (`final_model_with_ic_lora` not `ic_lora`).
3. **Real widget names instead of `widget_N`** (blocked on schema work — MP-6).
4. **Slot semantics visible at every `.out(N)` call site** (trailing `# outputs:` comments or named-slot access).
5. **Stage grouping with banner comments** matching pipeline order.
6. **Branch selection as data, not topology** (`PARAMS["control_mode"]` should be the switch, not just a label).

---

## 3. What v1 taught us

The v1 codemod was built, run on the LTX template, and critiqued by three subagents from independent angles. Convergent findings:

### 3.1 Silent contract regression (the critical bug)

The v1 codemod blindly rewrote variable references in `register_input` calls. The original `register_input("negative", "11", "text", negative.node.inputs["text"])` became `register_input("prompt_embedding_11", "11", "text", ...)` in v1 output. This breaks the public input contract — `READY_METADATA["unbound_inputs"]` still maps `"negative" → "11.text"`, but the registered name is now `"prompt_embedding_11"`. Anything in Reigh that asks "what's your `negative` input?" fails silently.

**Lesson:** the codemod's rewrite pass must distinguish variable references from string-literal arguments. The first argument of `register_input` is a public name, not a variable reference, and must be preserved verbatim.

### 3.2 Authorial intent was discarded then poorly reconstructed

The original LTX template named variables `negative`, `positive`, `first_strength`, `last_strength`, `guide_canny`, `guide_pose`, `guide_depth`. The v1 codemod renamed these to `prompt_embedding_11`, `prompt_embedding_16`, `param_float_2110`, `param_float_2108`, and six indistinguishable `resized_image_*` clones. Information the human author had encoded was thrown away and replaced with inferior heuristic output.

**Lesson:** prefer the original variable name when it's more specific than the class-derived fallback. One rule: `if original_name not in CLASS_DERIVED_PATTERNS: keep it`.

### 3.3 Added ceremony didn't earn its keep

The v1 codemod added a `ID = {...}` sidecar dict (73 lines) to map role names → node ids. All three critique agents flagged it as pure indirection. It creates a three-place-of-truth problem (ID dict + call site + `unbound_inputs`), makes simple edits (add/delete a node) require touching two locations, and the section banners inside the ID dict duplicate the banners inside `build()`.

**Lesson:** inline ids at the call site (`id="187"` as a kwarg or positional). Subtractive transformations are safer than additive ones.

### 3.4 Codemod missed semantic foot-guns

Three real bug-magnets in the LTX template are silently propagated by v1:

- **Port-polarity inversion on `LTXVConditioning`**: inputs are `(negative, positive)`, outputs are `(positive, negative)`. Downstream code correctly uses `.out(1)` for negative, but a copy-paste edit could silently flip polarity.
- **Chain bypass on `LTX2_NAG`**: branches off the bare UNet at id 187, not the LoRA → sage → FFN → tuner stack. The MODEL PATCH STACK banner presents the six nodes vertically as if they're chained; they aren't.
- **Branch-selection theater**: `PARAMS["control_mode"] = "canny"` is wired to a `PrimitiveString` (id 6000) with zero downstream consumers. The actual branch selection happens by which `resized_image_*` is wired into `LTXAddVideoICLoRAGuide.image`. Editing the PARAMS value does *nothing*.

**Lesson:** a static analyzer needs to detect these patterns and inject inline warnings. The codemod alone cannot. This is the largest design shift from v1 → v2.

---

## 4. Architecture for v2 — three tiers

The v1 codemod was a single-pass mechanical transformation. v2 splits the work across three tiers, each with a different reliability profile:

### Tier 1 — programmatic gates (binary, fully automated)

Hard pass/fail checks that never need agent judgment. If any fail, the template doesn't ship.

- **Compiled API parity**: `wf.compile("api")` from original == migrated, byte-for-byte.
- **`unbound_inputs` parity**: same set of public input names, same `(node_id, field)` tuples.
- **`register_input` first-arg preservation**: every public name from the original appears in the migrated file.
- **Strict-ready gate**: `port check --strict-ready-template` passes on the migrated file.
- **Imports and builds**: smoke test.
- **`vibecomfy.cli validate`** passes.

### Tier 2 — analyzer-driven flags (programmatic detection, agent judgment on resolution)

The static analyzer surfaces patterns; the agent (via the migration skill) decides what to do about each one.

Five rules in v2:

1. **Port-polarity inversion**: for any node where output port labels are a permutation of input arg labels in the same call, flag.
2. **Chain bypass**: in a patch chain of length ≥ 3, flag any downstream consumer that connects to the head instead of the tail.
3. **Unwired primitives**: `PrimitiveString` / `PrimitiveFloat` / `INTConstant` with zero outgoing edges.
4. **Branch-selector groups**: when N ≥ 2 nodes of the same class feed a single input slot on one sink, group them.
5. **Magic-constant twins**: two literals matching across structurally-symmetric paths feeding parallel slots.

### Tier 3 — semantic checklist (full agent judgment via skill)

A migration skill walks an agent through a structured checklist per template. Each checklist item demands cited evidence (file:line citations, metadata field references) rather than a judgment call. The agent produces the migrated file plus a per-template report.

Checklist domains:

- **Naming audit** — for each variable named with the class-derived fallback, is there a more specific name available in the original?
- **Knowledge transfer from `READY_METADATA`** — `runtime_note`, `approach`, `ltx_best_practices` may contain knowledge that belongs inline.
- **Original-author signal preservation** — variable names, inline comments, intentional structural choices.
- **App-parity review** (for `coverage_tier: required` only) — cross-reference the Reigh worker capability contract.
- **Runtime evidence** (for `coverage_tier: required` only) — focused RunPod validation post-migration.

The skill outputs a structured per-template report (~150 words) that becomes part of the migration PR.

---

## 5. The seven phases

| Phase | Deliverable | Estimate | Depends on | Parallelizable |
|---|---|---|---|---|
| 1 | Parity gate (`--verify` flag) | ~2 hours | — | Yes (with 2, 4) |
| 2 | Static analyzer (`--analyze` flag) | ~1 day | — | Yes (with 1, 4) |
| 3 | Migration skill | ~1 day | 2 (analyzer JSON), 4 (codemod CLI) | No (sequential) |
| 4 | Codemod v2 (`--mode annotate` + `--mode restructure`) | ~1 day | 2 (analyzer JSON contract) | Yes (with 1, 2) if contract is locked |
| 5 | Run end-to-end on LTX template | ~30 min | 1, 2, 3, 4 | No |
| 6 | Critique loop (3 parallel subagents) | ~30 min | 5 | No |
| 7 | Synthesize + decide ship/iterate/rethink | ~30 min | 6 | No |

**Total work**: 3–4 days sequenced, 2–3 with parallelism.

### Phase 1 — parity gate

**File**: `tools/narrate_template.py` (extend existing tool with `--verify` subcommand).

**CLI**:
```
python -m tools.narrate_template --verify <original.py> <candidate.py>
```

**Behavior**:
1. Import `build` from both files (use `importlib.util.spec_from_file_location`).
2. Call each `build()` to produce a `VibeWorkflow`.
3. Call `wf.compile("api")` on each.
4. Compare API dicts using deep equality; on mismatch, emit a structured JSON diff identifying the divergent node id and field.
5. Compare `wf.unbound_inputs` (or equivalent) — every key must map to the same `(node_id, field)` tuple.
6. Parse the candidate file's AST and confirm every `register_input("<name>", ...)` first-arg from the original appears as a first-arg in the candidate.
7. Exit 0 on success, exit 1 with structured JSON failure report on any failure.

**Failure JSON schema** (locked — phases 3, 4 depend on this):
```json
{
  "status": "fail",
  "checks": {
    "api_dict_parity":     {"pass": false, "diff": [{"path": "210.inputs.num_images.index_1", "original": 0, "candidate": null}]},
    "unbound_inputs_parity": {"pass": true},
    "register_input_preservation": {"pass": false, "missing": ["negative"]}
  }
}
```

**Success test**: run `--verify` against the existing v1 output at `ready_templates/video/ltx2_3_first_last_frame_travel_iclora_control_narrative.py` vs. the original. Must report `register_input_preservation: pass: false, missing: ["negative"]`.

**Anti-goals**: don't make this verbose, don't add subcommands beyond `--verify`, don't validate semantics beyond the three checks above.

### Phase 2 — static analyzer

**File**: `tools/narrate_template.py` (extend with `--analyze` subcommand).

**CLI**:
```
python -m tools.narrate_template --analyze <file.py> [--json]
```

**Behavior**: Parse the AST + (optionally) build the workflow to get edge information. Run five rules; emit structured JSON.

**Analyzer JSON schema** (locked — phases 3, 4 depend on this):
```json
{
  "file": "ready_templates/video/ltx2_3_first_last_frame_travel_iclora_control.py",
  "findings": {
    "port_polarity_inversions": [
      {
        "node_id": "10",
        "class_type": "LTXVConditioning",
        "input_arg_order": ["negative", "positive"],
        "output_port_order": ["positive", "negative"],
        "evidence": "node 10 takes (negative, positive) but its outputs are labelled (positive, negative)",
        "suggested_comment": "WARNING: outputs are (positive, negative) — order is reversed vs the (negative, positive) input args."
      }
    ],
    "chain_bypasses": [
      {
        "bypassing_node_id": "197",
        "bypassing_class": "LTX2_NAG",
        "chain_head_id": "187",
        "chain_head_class": "UNETLoader",
        "skipped_node_ids": ["186", "226", "228", "229", "5011"],
        "skipped_classes": ["LoraLoaderModelOnly", "PathchSageAttentionKJ", "LTXVChunkFeedForward", "LTX2AttentionTunerPatch", "LTXICLoRALoaderModelOnly"],
        "evidence": "node 197 takes model=187.out(0) but a 5-node patch chain exists downstream of 187",
        "suggested_comment": "CHAIN BYPASS: takes UNETLoader directly; does NOT inherit the LoRA/sage/FFN/tuner/IC-LoRA patches."
      }
    ],
    "unwired_primitives": [
      {
        "node_id": "6000",
        "class_type": "PrimitiveString",
        "literal_value": "canny",
        "evidence": "node 6000 has zero outgoing edges",
        "suggested_comment": "UNUSED: no downstream consumers — this is a label only, runtime no-op."
      }
    ],
    "branch_selector_groups": [
      {
        "sink_node_id": "5012",
        "sink_class": "LTXAddVideoICLoRAGuide",
        "sink_input": "image",
        "active_branch_node_id": "5028",
        "alternative_branch_node_ids": ["6101", "6102", "6103"],
        "evidence": "4 ImageResizeKJv2 outputs converge on sink 5012.image; only one is wired",
        "suggested_comment": "BRANCH SELECTION: 'image=' picks which control branch is active. Currently wired to node 5028 (canny). Alternatives: 6101 (raw), 6102 (pose), 6103 (depth)."
      }
    ],
    "magic_constant_twins": [
      {
        "node_ids": ["2108", "2110"],
        "classes": ["PrimitiveFloat", "PrimitiveFloat"],
        "value": 0.8,
        "downstream_sinks": [{"node": "210", "field": "num_images.strength_1"}, {"node": "210", "field": "num_images.strength_2"}],
        "evidence": "two PrimitiveFloat nodes with literal 0.8 feed parallel inputs strength_1 / strength_2 on the same sink",
        "suggested_comment": "COUPLED: matches partner literal by convention. Hoist to PARAMS as first_anchor_strength / last_anchor_strength."
      }
    ]
  }
}
```

**Success test**: run `--analyze` on the original LTX template. Must catch all four foot-guns documented in v1 critique (LTXVConditioning reversal, NAG bypass, unwired control_mode primitive, branch-selector group on 5012). Magic-constant twins should catch the 0.8/0.8 anchor strengths.

**Anti-goals**: no false positives on simple cases. Don't flag every multi-output node as port-polarity-inverted. Don't flag every primitive as unwired unless it genuinely has zero outgoing edges. Each rule needs a minimal-evidence threshold (e.g. chain-bypass only fires when chain length ≥ 3).

### Phase 3 — migration skill

**File**: `.claude/skills/migrate-template/SKILL.md` plus any supporting prompts.

**Invocation**: `Skill(skill="migrate-template", args="<template_path>")`.

**Behavior**:
1. Run `tools/narrate_template.py --analyze <template>` and parse the JSON.
2. For each Tier 2 finding, surface as a checklist item; require agent to either (a) write an annotation explaining intent (added to `READY_METADATA["annotations"]`), or (b) flag as a bug/needs-attention.
3. Walk the agent through the Tier 3 checklist (naming audit, knowledge transfer, original-author signal preservation, app-parity if required tier).
4. Run `tools/narrate_template.py --mode <chosen> <template> --out <candidate>` to produce the candidate file.
5. Run `tools/narrate_template.py --verify <original> <candidate>` to confirm gate pass.
6. Emit the per-template report.

**Per-template report format**:
```markdown
## Template: <ready_id>

### Tier 1 gates
- [ ] Compiled API parity
- [ ] unbound_inputs parity
- [ ] register_input preservation
- [ ] Strict-ready gate
- [ ] Validate
- [ ] Imports + builds

### Tier 2 flags (analyzer)
For each finding: ✅ resolved (how) / ⚠️ needs attention (why)

### Tier 3 changes (semantic)
- Restored N original variable names: [list]
- Hoisted N values to PARAMS: [list]
- Moved N values back inline (placeholders): [list]
- Added N annotations: [list]

### App-parity (required tier only)
Reigh worker contract: <path> — ✅ unchanged / ⚠️ needs update

### Runtime evidence (required tier only)
RunPod focused validation: ⏳ pending / ✅ passing (<evidence link>)
```

### Phase 4 — codemod v2

**File**: `tools/narrate_template.py` (extend with `--mode annotate` and `--mode restructure`).

**CLI**:
```
python -m tools.narrate_template --mode annotate <input.py> [--out <output.py>]
python -m tools.narrate_template --mode restructure <input.py> [--out <output.py>]
```

**`--mode annotate`** (pure additive, zero structural change):
- Read original file.
- Run `--analyze` to get findings.
- Inject inline comments from each finding's `suggested_comment` at the matching call site.
- Add trailing `# outputs: 0=NAME, 1=NAME` comments **only** for nodes with ≥ 2 outputs OR where slot name differs from slot type.
- Drop the `# TODO: schema not in index` markers (instead, single summary line at top of `build()`).
- No renames, no PARAMS hoisting, no ID dict, no banners.
- Must pass `--verify` against original.

**`--mode restructure`** (layered on annotate output):
- Apply all `--mode annotate` changes.
- Apply these three rules and only these three:
  1. **Prefer original variable names** when more specific than class-derived. Heuristic: if the original name appears in `{class_name.lower(), f"{class_name.lower()}_{id}", f"param_{type}_{id}", f"resized_image_{id}"}` etc., it's class-derived; replace with role-based name. Otherwise keep it.
  2. **Drop the `ID = {...}` sidecar dict.** Inline `id="187"` at the call site as a kwarg or as the second positional argument.
  3. **Hoist to PARAMS only `unbound_inputs` entries that aren't runtime-overridden placeholders.** Placeholders (input file paths for `LoadImage` / `LoadVideo` / `LoadAudio`) stay inline at the load node; tunables (seeds, dims, prompts, strengths) hoist.
- No new section banners beyond what annotate adds.
- No `_at` rename — keep `_node` helper.
- Output must be within ±15% of original line count.
- Must pass `--verify` against original.

**Hard constraint**: the codemod cannot rewrite the first argument of `register_input` calls. That's the bug from v1; v2 must explicitly preserve it.

**Anti-goals**: no new abstractions beyond the three rules. If a code change isn't covered by an explicit rule, don't make it.

### Phase 5 — run end-to-end on LTX

Sequence:
1. `python -m tools.narrate_template --analyze <original> --json > /tmp/ltx_analysis.json`
2. `Skill("migrate-template", "<original>")` — produces candidate + report.
3. Read candidate file.
4. Confirm `--verify` green.
5. Hand off to Phase 6.

### Phase 6 — critique loop

Three parallel critique subagents on the v2 output, briefed to compare against v1 output (which still exists at `..._narrative.py`):

1. **"Did the analyzer catch what it should have?"** — verify each of the four v1 foot-guns was caught and properly handled. Identify false positives and false negatives.
2. **"Is the report trustworthy?"** — read the per-template report cold; could a reviewer who hasn't seen the migration sign off based on this report alone?
3. **"Is v2 actually agent-readable?"** — re-run the three concrete tasks (change negative prompt; switch control mode; add a LoRA). Compare friction map to v1.

### Phase 7 — synthesize and decide

Three outcomes:
- **Ship**: v2 is good enough to generalize across the corpus.
- **Iterate**: specific gaps remain; ~1–2 more days.
- **Rethink**: deeper structural problem surfaced.

---

## 6. Interface contracts (locked)

These exist so phases 1, 2, 4 can be built in parallel without each other's output.

- **Analyzer JSON schema** — see Phase 2 above.
- **Verify failure JSON schema** — see Phase 1 above.
- **Codemod CLI** — `--mode annotate|restructure` takes input path, writes output path, exit 0 on success.
- **Per-template report format** — see Phase 3 above.

Any phase that changes one of these contracts must update this document and notify the other phases.

---

## 7. Success criteria

Concrete bar for declaring v2 ready to scale to the corpus:

| Criterion | Pass condition |
|---|---|
| Parity gate | Catches v1's `register_input` bug on the existing `..._narrative.py`; passes on v2 output |
| Analyzer recall | Surfaces ≥ 4 of the foot-guns identified in v1 critique |
| Analyzer precision | < 20% false-positive rate on LTX template |
| Output line count | ~520–580 vs. v1's 705 |
| Variable name fidelity | ≥ 80% of original variable names preserved when more specific than heuristic |
| Report trustworthiness | Critique agents accept the report as sufficient evidence |
| Cold-read task friction | Critique agent's friction-map for v2 has materially fewer items than for v1 |
| Codemod register_input handling | First argument of `register_input` is preserved verbatim; verified by parity gate |

---

## 8. Risks and mitigations

- **Analyzer over-flags**: each rule needs a minimal-evidence threshold (e.g. chain-bypass only on chains ≥ 3 nodes; magic-constant twins only when downstream sinks are structurally symmetric).
- **Skill becomes rubber-stamp**: every checklist item requires cited evidence, not a yes/no judgment.
- **v1 problems return in different clothes**: hard line-count cap on codemod output (±15% of original).
- **Parity gate is too coarse**: byte-identical API doesn't catch metadata drift; add `coverage_tier` and `annotations` parity checks if needed.
- **Original-name heuristic misclassifies**: when in doubt, keep the original; agent can rename via the skill checklist.

---

## 9. References

- **v1 codemod**: `tools/narrate_template.py` (current state — to be extended in phases 1, 2, 4)
- **v1 output**: `ready_templates/video/ltx2_3_first_last_frame_travel_iclora_control_narrative.py`
- **LTX original (smoke-test template)**: `ready_templates/video/ltx2_3_first_last_frame_travel_iclora_control.py`
- **Project CLAUDE.md**: `/Users/peteromalley/Documents/reigh-workspace/vibecomfy/CLAUDE.md`
- **Megaplan ticket**: `01KRVVCNW5NV08FBJT9GC81553` (`.megaplan/tickets/`)
- **Strict-ready exceptions**: `docs/strict_ready_exceptions.json`
- **Emitter (for `_ROLE_CLASSIFICATION` and other useful bits)**: `vibecomfy/porting/emitter.py:86-125`
- **Widget schema (for `widget_N` resolution)**: `vibecomfy/porting/widget_schema.py`
- **Strict-ready policy**: `vibecomfy/registry/ready_template.py`

---

## 10. Out of scope for v2

- The Declarative Data projection (`port export --form declarative`).
- Corpus-wide migration (only after v2 is proven on LTX).
- MP-6 schema integration (separate workstream; the analyzer should degrade gracefully when schemas are missing).
- Per-template RunPod evidence collection (Phase 5 is local validation only; required-tier RunPod evidence is a post-ship migration concern).
- Reigh worker contract updates (only triggered if app-parity check fails in Phase 3 skill).

---

## 11. Phase status tracker

| Phase | Status | Owner | Notes |
|---|---|---|---|
| 1 — parity gate | not started | — | DeepSeek V4 Pro agent dispatch |
| 2 — analyzer | not started | — | DeepSeek V4 Pro agent dispatch |
| 3 — migration skill | not started | — | sequential after 2 + 4 |
| 4 — codemod v2 | not started | — | DeepSeek V4 Pro agent dispatch |
| 5 — run end-to-end | not started | — | — |
| 6 — critique loop | not started | — | — |
| 7 — synthesize | not started | — | — |
