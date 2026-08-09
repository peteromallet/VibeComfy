# Plan: make campaign baselines structural, not server-specific

## ⚠️ Refinement — structural policy applies to the CANDIDATE too; pre-existing nodes are never rejectable

Added after tracing the candidate evaluation path (supersedes the baseline-only scoping in the
"Anti-gaming and oracle independence" section near the end of this doc).

**1. The fix must cover candidate Gate 1, not only the baseline gate.**
`_evaluate` (`vibecomfy/demo_factory/case.py:453`) calls the SAME `port_check_graph` on the
candidate (`case.py:456`) and feeds `cand_ok` as BOTH `execution_safe` and `output_reachable`
into the oracle (`case.py:466,468`). Oracle Gate 1 (`_gate_execution_safety`,
`vibecomfy/demo_factory/oracle.py:211`) is a hard first-pass gate: `if not execution_safe:
return passed=False` (`oracle.py:219`) → immediate `REJECTED` (`oracle.py:93`), before any
witness gate runs. A baseline-only fix therefore only relocates the rejection:
`baseline_rejected` → fixer runs → `REJECTED` at candidate Gate 1, zero new accepts. To let
these cases reach the witness gates, **Gate 1 must use the structural checker too**. This
supersedes the earlier "do not pass `structural_safe` as candidate `execution_safe`" guidance.

**2. Pre-existing nodes are never rejectable.** A node present in the golden/broken graph
BEFORE the edit is part of the user's real workflow — it exists on the user's machine. Being
unresolved/uncategorised on THIS dev server is an environment-coverage gap, not a fixer-quality
signal. Rule: **a node that existed before the edit must never cause rejection** — at the
baseline OR the candidate gate — regardless of schema availability. Concretely:
- Baseline gate: every node in the golden is pre-existing → tolerate all `schema_unavailable`
  classes (the golden IS the user's graph).
- Candidate Gate 1: classify each unresolved node as PRE-EXISTING (its class type appears in
  `case.golden` / `case.broken`) vs FIXER-INTRODUCED. Pre-existing → never blocks. Only a
  fixer-INTRODUCED node that resolves nowhere may be flagged.

**Anti-gaming is preserved** because the repair-quality decision rests on the INDEPENDENT
witness gates (Gate 2 fault removal, Gate 3 repair postcondition, Gate 5 non-no-op, + LLM
judge), none of which read `execution_safe`. Relaxing Gate 1 for pre-existing/unresolvable
nodes cannot manufacture an accept — the candidate still must actually repair the fault. The
sole execution-side signal retained is "the fixer introduced a node that resolves nowhere,"
which catches hallucinated nodes without penalising the user's real graph.

## Recommendation

The golden baseline should answer one question: **is this a coherent graph with a reachable result boundary?** It should not answer whether the graph can execute on the developer's current ComfyUI installation.

Implement a baseline-only structural policy that:

1. validates raw graph topology and output reachability;
2. attempts live and safe on-demand schema resolution as best-effort enrichment;
3. treats a still-unresolved class as `schema_unavailable`, not as structural failure;
4. treats asset-backed enum mismatches as environment warnings;
5. hard-fails only evidence-backed structural defects, including malformed raw edges and a genuinely missing, non-defaultable required input under a credible version-compatible schema; and
6. leaves fixer-candidate checking and the oracle unchanged.

Do not install node packs or download assets to prove a golden. Installation is an execution-environment concern and would make an offline gate slow, stateful, and machine-dependent.

## Evidence and counts

The audit enumerated:

- `out/demo-candidate-factory/20260729-multinode-batch2/cases/*/proof/baseline.json`
- `out/demo-candidate-factory/20260729-splice-wxx-fixed/cases/*/proof/baseline.json`

The four cause buckets overlap within cases. Counts therefore must not be summed to obtain the number of rejected cases.

| Campaign | Total | Passed | Rejected | Unsafe + reachable | Unsafe + unreachable | Safe + unreachable |
| --- | ---: | ---: | ---: | ---: | ---: | ---: |
| `20260729-multinode-batch2` | 20 | 11 | 9 | 7 | 1 | 1 |
| `20260729-splice-wxx-fixed` | 41 | 35 | 6 | 5 | 1 | 0 |
| Combined | 61 | 46 | 15 | 12 | 2 | 1 |

The following occurrence counts are exact for the diagnostics visible in the persisted `compile_error` summaries:

| Cause | Batch 2 cases / visible occurrences | Splice cases / visible occurrences | Combined cases / visible occurrences |
| --- | ---: | ---: | ---: |
| Unknown or uninstalled class | 7 / 15 | 2 / 6 | 9 / 21 |
| Missing required input | 3 / 6 | 4 / 10 | 7 / 16 |
| Enum or asset-list mismatch | 2 / 5 | 2 / 2 | 4 / 7 |
| Edge/API compile failure | 1 / 1 | 0 / 0 | 1 / 1 |
| Separate reachability failure | 2 cases | 1 case | 3 cases |

`port_check_graph` saves only the first three hard messages and truncates each to 120 characters (`baseline.py:125-140`). The occurrence counts are consequently lower bounds on the underlying diagnostics. The case counts and outcomes are the robust historical measures. A current read-only full-report replay found hidden unresolved-class diagnostics in 8 of the 9 batch-2 rejections and all 6 splice rejections. This matters because the current policy lets an unknown-class message anywhere in the full report make every other diagnostic hard, even when the persisted summary shows only required-input or enum errors.

### Rejected-case map

Batch 2:

- `044d8f85cac4` (`M-25`): `FaceSegment` unresolved; `VHS_VideoCombine.loop_count` and `pingpong` absent.
- `1955be45449e` (`M-38`): `MaskPreview+` unresolved; `DualCLIPLoader.clip_name1` and `VAELoader.vae_name` absent from this server's lists.
- `1f9ee4dc89c4` (`M-29`): two `VHS_VideoCombine` nodes missing defaultable runtime fields in the visible summary; hidden unknown classes keep the report hard.
- `5205a623bc99` (`M-24`): `AudioEnhancementNode` and `AudioNormalizeLUFS` unresolved; `compiled_edge_missing_endpoint`.
- `aa61315cb579` (`M-33`): `Anything Everywhere` and `BiRefNetRMBG` unresolved; `WanVideoDecode.vae` absent after offline lowering.
- `b5033f4dcfce` (`M-37`): `ImpactImageBatchToImageList`, `MaskListToMaskBatch`, and `SegmDetectorCombined_v2` unresolved.
- `b7084da625f2` (`M-34`): `Efficient Loader`, `NNLatentUpscale`, and `OneButtonPrompt` unresolved.
- `e367bcefaf8b` (`M-27`): three `IAMCCS_*` classes unresolved; output heuristic fails to recognize the custom video/disk sink.
- `ebfd174a20eb` (`M-39`): three LoRA asset-list warnings; `execution_safe=true`, but the image-only output heuristic misses `ModelSave`.

Splice:

- `4da1ea4b234c`: the same three `IAMCCS_*` classes and custom output-sink miss.
- `64887eb584e9` (`M-06`): `VHS_VideoCombine` defaultable runtime fields plus a LoRA asset-list mismatch.
- `6ece655dd15a` (`M-16`): `VHS_VideoCombine` defaultable runtime fields plus a model asset-list mismatch.
- `749c1ac5effe` (`M-09`): `AudioCrop`, `ReservedVRAMSetter`, and `VantageGGUFLoader` unresolved.
- `a0e0efb62f1a` (`D-08`): two `VHS_VideoCombine` nodes missing defaultable runtime fields in the visible summary.
- `eaed9f7a0774` (`M-18`): several `VHS_VideoCombine` nodes missing `loop_count`, `pingpong`, and `save_output`.

## Diagnosis

### One boolean currently conflates two different questions

The path is:

1. `demo_factory/case.py:_baseline_gate` calls `run_baseline`.
2. `demo_factory/baseline.py:run_baseline` calls `port_check_graph`.
3. `commands/port/_check.py:build_port_check_payload` calls `porting/workbench.py:analyze_source`.
4. `PortReport.ok` is false when any diagnostic has severity `error`.
5. `baseline.py:port_check_graph` scans diagnostic **message text**, not diagnostic codes. If any error contains an “unknown class” token, the graph remains unsafe; otherwise it soft-passes all errors.
6. `run_baseline` requires that boolean and `output_reachable`.

This policy is both too strict and too permissive:

- An unresolved class makes unrelated server-specific and schema-drift diagnostics hard.
- In the absence of an unknown-class message, even a genuine edge compile error can be swept into the blanket soft-pass.
- The saved three-message summary often does not contain the hidden unknown-class diagnostic that actually kept `ok=false`.

There is no existing structural/lenient baseline mode. `--strict-ready-template` only tightens ready-template promotion. `analyze_source(mode="auto")` softens opaque component diagnostics in scratchpad mode but does not change schema errors.

### The on-demand resolver is present but bypassed and incomplete

`port check` does use the authoring provider chain. However:

- `baseline.py:_on_demand_enabled` adds `--resolve-on-demand` only when the parent already has `VIBECOMFY_ON_DEMAND_SCHEMAS=1`.
- The campaign does not set that variable.
- `_build_authoring_provider` appends `OnDemandInstallSchemaProvider` only under the same opt-in.
- `baseline.py` adds `--runtime-object-info` when `:8190` is reachable, but `_build_authoring_provider` ignores `runtime_object_info` and `server_url`. The live schema option is therefore dead on the `port check` path.

Even after wiring it, resolution cannot be a prerequisite for baseline acceptance:

- `OnDemandInstallSchemaProvider._resolve_pack` selects the first candidate with a URL and does not retry alternatives.
- The safe AST rung requires the requested workflow class key to match the Python class identifier. It misses aliases/display keys such as `MaskPreview+`, `Anything Everywhere`, `ImpactImageBatchToImageList`, and `SegmDetectorCombined_v2`.
- The configured Manager map source is not supplying the useful class-to-pack map, although Manager's `extension-node-map.json` contains the observed relationships.
- The current `on_demand.py` implements shallow-clone/static AST plus separately gated stub-import. Contrary to the older design description, transitive-dependency and version-retry rungs are not implemented there; they are deferred/future work.

A read-only check against an existing Impact Pack clone resolved `MaskListToMaskBatch` through the safe parser, but alias-named Impact classes did not resolve. This is useful enrichment, not a reliable gate.

### Required input diagnostics need provenance, defaults, and version context

There are two paths:

- `workbench.py:_known_runtime_required_input_diagnostics` emits committed runtime-contract errors, notably for `VHS_VideoCombine`.
- `schema/validate.py:validate_api_against_schema` emits `missing_required_input` from a resolved schema.

The observed `VHS_VideoCombine` fields have schema defaults (`loop_count=0`, `pingpong=false`, `save_output=true`). They may still need explicit materialization to queue on a particular runtime, but their absence does not make the source UI graph structurally incoherent. They should remain visible as execution-readiness warnings.

Conversely, a required input with no default can be structural, but only when the schema is credible for the workflow's node-pack version and the raw UI graph exposes that obligation. `WanVideoDecode.vae` illustrates why: the raw node has no `vae` socket and the workflow contains an `Anything Everywhere` broadcast helper. Hard rejection before resolving helper semantics or version drift is not justified.

### Asset enums describe one machine's inventory

`schema/validate.py` currently exempts dynamic image/video file pickers but intentionally keeps model/checkpoint enums hard. The campaign failures show why that is wrong for a structural golden check: `clip_name*`, `vae_name`, `lora_name`, and custom model selectors enumerate files available when `/object_info` was captured. A real path from a ready template or corpus workflow can be absent from the developer server while remaining structurally valid.

Semantic enums remain different. An invalid sampler mode, scheduler, crop policy, or other behavior selector can indicate a real incompatibility and must not be blanket-relaxed.

### The observed edge error is an ingest false positive

In `5205a623bc99`, the raw UI links are coherent. Node `6` (`LazySwitchKJ`) has a widget literal `["1897", 1]`. The offline normalizer assigns that widget to `on_false`; `convert_to_vibe_format` then treats any numeric-looking two-item list as an API edge and manufactures `1897.1 -> 6.on_false`. Node `1897` is not in the raw graph, producing `compiled_edge_missing_endpoint`.

The right decision is not “all compile errors are warnings.” Preserve widget-versus-edge provenance, fix this conversion ambiguity, and keep raw dangling endpoints hard.

### Output reachability is image-only

`baseline.py:_find_output_node` accepts only class names containing `Save...Image` or `Preview...Image`. It misses:

- `ModelSave` in `ebfd174a20eb`;
- `IAMCCS_VideoCombineFromDir` in the IAMCCS cases;
- audio/video/model outputs generally, despite broader output knowledge already existing in `metadata.py:OUTPUT_NODE_NAMES` and `templates.py:_OUTPUT_KIND_HEURISTIC`.

The “unreachable output” guard is correct, but its detector is not.

## Decision by cause

| Cause | Decision | Baseline behavior |
| --- | --- | --- |
| Unknown/uninstalled class | **Resolve, then relax on miss** | Try live cache/runtime and safe on-demand resolution. If no schema is available, keep the node as an opaque graph vertex and emit `schema_unavailable`; skip only checks that require that schema. Never install the pack for baseline proof. |
| Missing required input | **Resolve/default where justified; otherwise keep rejecting** | Apply trustworthy schema defaults and resolve known virtual/broadcast helpers first. Keep a hard failure only for a non-defaultable input under a credible version-compatible schema when the raw graph exposes the input obligation and provides neither a value nor a link. Runtime-only explicitness and schema-version ambiguity are warnings. |
| Widget value absent from enum/asset list | **Relax asset inventory; keep semantic enums strict** | Match the diagnostic to model-asset evidence and downgrade only environment-backed file selectors. Do not rewrite the golden value and do not install/download the asset. |
| Edge/API compile error | **Resolve conversion ambiguity; keep genuine structural failures** | Validate raw UI links independently. A missing raw endpoint, malformed slot, or irreconcilable compiled invariant hard-fails. A link manufactured from widget data is an ingest defect and must not disqualify the golden. |
| No reachable output | **Keep rejecting after fixing detection** | Recognize registered outputs, object-info `output_node`, known audio/video/model sinks, and an enabled terminal boundary with connected upstream data. Then prove an upstream path reaches it. |

## Concrete implementation plan

### 1. Split structural baseline policy from candidate execution policy

Change `vibecomfy/demo_factory/baseline.py`.

- Extract the subprocess portion of `port_check_graph` into a helper that returns the full JSON report without deciding pass/fail.
- Keep `port_check_graph` as the candidate/oracle-facing wrapper with its current behavior during this change.
- Add a separate baseline wrapper, for example `structural_check_graph`, that classifies diagnostics by `code` and `detail`, never by message substring.
- Make `run_baseline` use `structural_check_graph`.
- Do not pass the structural result into `case.py:_evaluate`; that path must continue to use candidate execution checking.

The structural classifier should return:

- `structural_safe`;
- `runtime_ready_on_current_server` as informational telemetry;
- `hard_blockers[]`;
- `warnings[]`;
- `resolved_classes[]` and `schema_unavailable_classes[]`;
- `checks_skipped_for_missing_schema[]`; and
- the full port report or a stable reference to it.

For compatibility, retain the current proof fields during migration, but stop using `execution_safe` to decide baseline acceptance. Add `structural_safe` and compute:

```text
passed = structural_safe AND output_reachable
```

Persist diagnostic codes and complete structured details in `proof/baseline.json`; keep a short human summary separately. This removes the first-three/truncation ambiguity.

Initial hard codes/categories should include:

- empty or unmaterialized graph;
- duplicate/malformed node identifiers;
- raw missing edge source/target and invalid link record/slot;
- compile invariant failures traceable to genuine raw topology;
- credible, non-defaultable required-input omissions as defined below;
- invalid output index when both endpoint schemas are credible; and
- no structurally reachable output boundary.

Baseline warnings should include:

- `unresolved_runtime_class` and `unknown_class_type` after resolution attempts;
- asset-scoped `value_not_in_enum`;
- local package/model/runtime compatibility diagnostics;
- required runtime fields with trustworthy defaults;
- schema-version ambiguity; and
- checks skipped because a class schema is unavailable.

Unknown classes must not suppress validation of known parts of the graph. Validate every edge/input for which both endpoint schemas are available and report exactly which checks were skipped at an opaque boundary.

### 2. Add an explicit raw-topology preflight and fix edge provenance

Change `vibecomfy/ingest/normalize.py` and the baseline structural helper.

- Validate UI link records directly before UI-to-API normalization: node IDs unique, link IDs well-formed/unique, endpoints present, slots numeric, and socket link references consistent.
- In `_normalize_ui_to_api`, retain per-input provenance such as `edge`, `widget`, or `literal`.
- In `_convert_to_vibe_format_impl`, treat a two-item list as an edge only when it came from a UI link socket. Preserve current link-shape behavior for a genuinely API-native graph.
- Add a regression for the `LazySwitchKJ.on_false=["1897", 1]` shape and a separate negative fixture with an actual raw dangling link.

Until the normalization fix lands, the baseline classifier may compare `compiled_edge_missing_endpoint` detail against raw link records. It may downgrade only a proven conversion-manufactured edge; it must not broadly soften `api_compile_failed`.

### 3. Make schema resolution best-effort and correctly wired

Change `vibecomfy/demo_factory/baseline.py`, `vibecomfy/commands/port/_shared.py`, and later `vibecomfy/schema/on_demand.py` / `vibecomfy/registry/pack_resolver.py`.

- Baseline structural checking should request safe on-demand resolution explicitly by default rather than depending on an ambient campaign environment variable.
- Keep `VIBECOMFY_ON_DEMAND_BOOT` off. Structural proof must not import/execute third-party packs.
- Bound the total lookup budget, use caches, record timeout/miss reasons, and continue with `schema_unavailable` on failure.
- When `--runtime-object-info` is requested, return a `CompositeSchemaProvider` with `RuntimeSchemaProvider` and the authoring provider so the live flag actually affects `port check`.
- Do not make network availability part of pass/fail.

Follow-up resolver coverage improvements:

- consume/invert Manager's current extension-node class map;
- treat punctuation/space-containing exact workflow class keys as class-name queries;
- retry ranked pack candidates instead of stopping at the first URL;
- teach the safe parser to honor static `NODE_CLASS_MAPPINGS` aliases; and
- record schema provenance/confidence/version in the report.

These improvements increase how much structure can be checked. They are not a substitute for the fail-open-on-schema-miss baseline rule.

### 4. Classify asset-backed choices explicitly

Change `vibecomfy/schema/validate.py` and reuse `vibecomfy/porting/assets.py` / `vibecomfy/model_assets.py`.

- When emitting `value_not_in_enum`, add structured choice scope such as `environment_asset` or `semantic`.
- Identify asset choices by matching node ID, class, input, and value to `AssetCandidate` evidence. `porting/assets.py:candidates_from_api_prompt` already records the input name in candidate metadata and recognizes model-like fields/suffixes.
- Extend the centralized asset-field mapping for indexed/custom selectors such as `lora_0` and known model-loader fields; do not create a baseline-local filename list.
- In structural baseline mode, downgrade only `environment_asset`.
- In normal execution validation, keep the mismatch visible/hard as appropriate for the target server.

No baseline path should replace the value with a locally installed alternative: that would mutate the meaning of the golden.

### 5. Make required-input rejection evidence-based

Change `vibecomfy/porting/workbench.py` and/or the baseline classifier.

For each required-input diagnostic, include:

- schema provider, confidence, package version, and cache/runtime identity;
- whether the input has a default;
- whether the raw UI node exposes the input as a socket or widget;
- whether a virtual/broadcast helper can supply it; and
- whether the complaint is a committed runtime queue contract rather than a graph contract.

Structural baseline classification:

1. Resolve helpers and apply schema defaults where safe.
2. If a field has a default, retain a runtime-materialization warning but do not reject the golden.
3. If schema version does not match or cannot be established, warn and mark the check inconclusive.
4. Hard-fail only when a credible schema says the input is required with no default and the raw graph exposes the obligation but supplies neither value nor edge.

This keeps genuinely incomplete known nodes out without treating the local cached schema as universal truth.

### 6. Replace the image-only output heuristic

Change `vibecomfy/demo_factory/baseline.py` and centralize output knowledge rather than adding another private list.

Detection precedence:

1. an explicit port/public-output contract;
2. object-info `output_node=true` preserved in `NodeSchema`;
3. the shared known output catalog, expanded to include model and preview sinks such as `ModelSave` and `PreviewAudio`; then
4. for extracted fragments or unresolved custom nodes, an enabled terminal node with at least one connected input and no outgoing runtime edge, recorded as a lower-confidence boundary output.

After selecting candidates, traverse upstream over validated raw links and require at least one reachable source-to-boundary path. Merely having “save” in a class name is insufficient.

The fallback is necessary for real custom side-effect sinks such as `IAMCCS_VideoCombineFromDir`, whose schema may remain unavailable. Record which rule established reachability.

## Risks and guards

### False baselines admitted

Relaxation can admit a golden whose opaque node has an invalid socket, whose custom pack version changed, or whose asset path is genuinely misspelled. That is acceptable only as **runtime unverified**, not as execution proven.

Mitigations:

- Raw graph topology is always validated.
- Known-known edges and inputs are still schema-checked.
- Skipped opaque-boundary checks are explicit in proof.
- Semantic enums remain hard.
- Non-defaultable required inputs remain hard when supported by credible raw/schema evidence.
- Output reachability is a graph traversal, not a name-only check.
- Runtime readiness remains separately reported and may still block an actual queue operation.

### Accidentally hiding genuine edge corruption

Do not downgrade `api_compile_failed` wholesale. The exception is restricted to an edge proven to have been manufactured from widget data. Raw missing endpoints and compile invariants rooted in raw links remain hard.

### Resolver latency and nondeterminism

Safe on-demand lookup can involve network and cloning. Give it a bounded aggregate budget, prefer cached evidence, and make timeout/miss a warning. Baseline outcome must be identical with the network disconnected, except that more schema-dependent checks are marked skipped.

### Anti-gaming and oracle independence

This relaxation cannot manufacture an accepted fixer result because it changes only the pre-agent golden gate. It lets the fixer run; it does not satisfy any candidate gate.

That safety depends on the policy split. ~~Today `case.py:_evaluate` calls the same `port_check_graph` used by the baseline. Do **not** globally relax that function and do not pass `structural_safe` as candidate `execution_safe`.~~ **(SUPERSEDED — see the "Refinement" section at the top: Gate 1 MUST use the structural checker too, with the pre-existing-node rule. Keeping Gate 1 on the old `port_check_graph` makes this entire fix inert for the rejected cases.)** The candidate still goes through its conversion check plus independent oracle checks for fault removal, repaired postcondition/additive witness, non-no-op behavior, collateral constraints, and any LLM/additive judge. The candidate still goes through its existing conversion check plus independent oracle checks for fault removal, repaired postcondition/additive witness, non-no-op behavior, collateral constraints, and any LLM/additive judge. Replaying the same candidate before and after the baseline change must produce the same oracle verdict.

## Verification plan

### Unit and regression tests

Add focused tests for:

1. valid raw topology + unresolved custom class + reachable output passes structural baseline with `schema_unavailable`;
2. on-demand resolution hit enables additional edge/input validation;
3. offline/on-demand miss does not change the structural outcome;
4. asset-backed enum mismatch warns while a semantic enum mismatch remains hard;
5. a defaultable `VHS_VideoCombine` field warns rather than rejects;
6. a credible non-defaultable required raw input remains hard;
7. a genuine raw dangling endpoint remains hard;
8. a link-shaped widget value remains literal and does not manufacture an edge;
9. `ModelSave`, audio/video output nodes, and an inbound unresolved custom terminal are recognized;
10. a graph with no reachable result boundary still rejects;
11. previously passing baselines remain passing; and
12. candidate `port_check_graph` and oracle verdicts are unchanged by baseline-only policy.

### Deterministic artifact replay

Before spending agent/provider calls, replay all 61 saved `source/golden.ui.json` graphs through the new structural checker.

Acceptance criteria:

- all 46 historically passing baselines still pass;
- no baseline rejects solely for `schema_unavailable`, missing local pack, or asset inventory;
- every remaining rejection names a structured raw-topology, credible required-input, or output-reachability blocker;
- the observed `5205a623bc99` edge is classified as ingest ambiguity until its provenance fix lands, then compiles without that edge; and
- the three previously unreachable goldens are recognized through `ModelSave` or connected custom terminal output evidence.

The replay should compare with and without live `:8190` and with network/on-demand disabled. Structural pass/fail must be stable; only enrichment and runtime telemetry may differ.

### Full campaign rerun

Use fresh output directories and the same fixer/provider configuration to rerun:

- multinode batch 1 (`M-01`–`M-20`);
- multinode batch 2 (`M-21`–`M-40`);
- the additive suite; and
- the debug suite.

Report, per suite:

- total, `baseline_rejected`, reached-fixer count, `infra_blocked`, `fixer_failed`, and each oracle verdict;
- baseline warning codes and schema-resolution hit/miss counts;
- accept tier among cases that reached the fixer; and
- candidate/oracle verdict comparison for cases that already reached the fixer before the change.

Release gates:

- `baseline_rejected` drops to zero for environment-only causes and to near-zero overall; any residual rejection has a reviewed structural blocker;
- the 46 historical baseline passes do not regress;
- no new `infra_blocked`;
- accepted/alternative-repair rate among reached cases stays approximately unchanged or rises;
- candidate verdicts for previously reached cases do not become more permissive merely because the baseline policy changed; and
- additional accepts come only from cases that previously never reached the fixer.

## Implementation order

1. Add structured baseline-only classification and richer proof output.
2. Add raw-topology validation and robust output-boundary detection.
3. Mark asset enums and required-input provenance/defaults.
4. Preserve widget/edge provenance to eliminate the observed false compile edge.
5. Wire live and safe on-demand providers correctly, then improve resolver coverage.
6. Run deterministic artifact replay, targeted tests, and the four campaign suites.

The single highest-leverage change is step 1: **stop deriving golden acceptance from `PortReport.ok` plus unknown-class message matching; classify the full diagnostic report under a baseline-only structural policy.** It immediately breaks the accidental coupling between an uninstalled node and every unrelated error, while preserving strict candidate/oracle evaluation.
