<!-- Auto-extracted from Codex design/decomposition pass. Source of truth for the additive-splice-pipeline epic. -->

## Batch-wide invariants

All line references below were verified against the current checkout. Every task must obey these rules:

- Production inputs are limited to the generically retrieved artifact and its content hash, the inquiry, runtime schemas, and the current broken graph. `prior_path`, fixture locators, `slice_node_ids`, repair goldens, and fixture ancestry must never affect eligibility, ranking, segmentation, binding, or application.
- Structural manifests contain no widget literals. Canonical class types are allowed only when derived from retrieved topology and runtime resolution—never hard-coded from a golden. Fixer-facing JSON must omit filenames/paths, source node IDs, golden values, sigma strings, and `candidate_graph`.
- Source paths may remain in private audit metadata, but the fixer receives an opaque source reference plus content hash.
- Any task touching `research.py`, `contracts.py`, the fixer prompt/batch loop, or `EditSession` must run the T-01 four-category guard.

## Foundational tests / regression guards to build first

Build T-01, T-02, T-03, and T-18 before changing the hot path.

Preserve and extend these existing suites:

- Source normalization: `tests/test_executor_research.py:2035-2118`
- Precedent synthesis: `tests/test_executor_research.py:2518-3034`
- Contract serialization and candidate suppression: `tests/test_executor_contracts.py:2165-2488`
- MULTINODE retry and dependency behavior: `tests/test_demo_factory_multinode.py:216-349`
- Atomic edit application: `tests/test_porting_edit_apply.py:866-1218`
- EditSession transactions and replay: `tests/test_porting_edit_session.py:2519-2957`, `4103-4468`
- Fixer prompt/protocol behavior: `tests/test_comfy_nodes_agent_edit.py:16585-16935`

Existing tests that use exact repository node IDs, `slice_node_ids`, widget values, or fixture locators remain characterization tests only. They are not evidence that the new pipeline is production-real.

# Easy

### T-02 — Reusable topology and anti-gaming assertions

- **What it does:** Add pure test helpers that assert typed-edge integrity, complete origin/evidence coverage, absence of unresolved UUID/Get/Set/Reroute nodes in complete regions, manifest bounds, and forbidden-field absence. Add perturbation helpers that renumber IDs and mutate widgets/filenames while expecting identical structural results.
- **Touches:** `tests/test_executor_research.py:2035-2118`; `tests/test_comfy_nodes_agent_edit.py:16585-16935`.
- **Difficulty:** `easy` — isolated test utilities with no production behavior.
- **Depends on:** None.
- **Effort:** Half-day.
- **Risk to the hot path:** None directly. The scanner must detect `prior_path`, paths/filenames, widget values, sigma strings, golden IDs/types, and fixture ancestry without treating legitimately retrieved/resolved class types as forbidden.

### T-03 — Normalized topology contracts

- **What it does:** Add `NormalizedPrecedent`, `TopologyPort`, `TypedEdge`, `SourceOrigin`, and `NormalizationStep`; extend `WorkflowNodeRecord` with named/indexed typed outputs. Define completeness and warning semantics, including region-local incompleteness.
- **Touches:** `vibecomfy/ingest/workflow_source.py:16-75`, especially `WorkflowNodeRecord` at `:33-45`; tests at `tests/test_executor_research.py:2035-2118`.
- **Difficulty:** `easy` — dataclasses, serialization, and invariants are mechanical and pure.
- **Depends on:** T-02.
- **Effort:** Half-day.
- **Risk to the hot path:** Shared records are consumed by `research.py`; preserve backward-compatible defaults and existing `to_dict()` keys. Widgets must remain a separate evidence channel, not appear in typed topology.

### T-14 — Deterministic cut-edge enumeration

- **What it does:** Implement the pure rule for segment set `S`: emit each edge with exactly one endpoint in `S` once, classifying outside→inside as inbound and inside→outside as outbound. Preserve both typed endpoint sockets and evidence references.
- **Touches:** New helper beside anchor logic in `vibecomfy/executor/research.py:3278-3323`; tests near `tests/test_executor_research.py:2518-2879`.
- **Difficulty:** `easy` — a small graph-set operation with exhaustive property tests.
- **Depends on:** T-03.
- **Effort:** Hours.
- **Risk to the hot path:** No integration yet. Perturbation tests must prove independence from node ordering, numeric IDs, widgets, filenames, and fixture ancestry.

### T-18 — Topology manifest contracts

- **What it does:** Add `TopologyManifest` and `TopologyManifestSet`, including nodes, internal edges, boundary anchors, inquiry coverage, validation, rejections, confidence, target hash, and the 1–3 manifest bound. Add an optional `topology_manifests` field to `ResearchResult`.
- **Touches:** `vibecomfy/executor/contracts.py:876-1054`, `:1690-1750`; tests at `tests/test_executor_contracts.py:2165-2488`.
- **Difficulty:** `easy` — typed fields and serialization with explicit bounds.
- **Depends on:** T-02.
- **Effort:** Half-day.
- **Risk to the hot path:** `contracts.py` is shared. Keep the field optional and preserve legacy serialization until migration completes; private audit provenance may retain a source path, but public/fixer serialization must redact it.

# Medium

### T-01 — Four-category baseline regression matrix

- **What it does:** Add one cheap, non-live smoke case for each REPAIR, ADDITIVE, MULTINODE, and DEBUG path, plus a production-real corpus subset. Assert route semantics, unchanged single-node/debug behavior, and no fixture ancestry entering research or fixer inputs.
- **Touches:** `vibecomfy/demo_factory/run_campaign.py:40-80`, `:97-115`, `:261-280`, `:1183-1218`; `tests/test_demo_factory_multinode.py:65-421`; new category tests beside it.
- **Difficulty:** `medium` — test-only work, but it spans four campaign runners and establishes the release gate.
- **Depends on:** T-02.
- **Effort:** Day.
- **Risk to the hot path:** None in production. Existing hard-coded campaign locators and `slice_node_ids` may construct test damage, but must never be passed as research evidence or used as a success oracle.

### T-04 — Source decoder and trusted ready-template dispatch

- **What it does:** Implement `normalize_precedent_source()` format dispatch for API JSON, UI JSON, and registry-owned ready templates. A trusted ready template is resolved by canonical registry identity and compiled to API without queueing/running the workflow; arbitrary or untrusted `.py` returns `untrusted_python_not_expanded`.
- **Touches:** `vibecomfy/ingest/workflow_source.py:78-177`; `vibecomfy/registry/ready.py:113-153`; `vibecomfy/workflow.py:738-762`; trust boundary `vibecomfy/security/loader_provenance.py:23-58`.
- **Difficulty:** `medium` — one ingestion surface with a security-sensitive but contained dispatch policy.
- **Depends on:** T-03.
- **Effort:** Day.
- **Risk to the hot path:** No `research.py` integration yet. Never feed a retrieved path directly to `importlib`; tests must prove untrusted Python is not imported and no Comfy execution is queued.

### T-10 — Content-hash normalization cache

- **What it does:** Cache `NormalizedPrecedent` by actual artifact-content hash and make `_selected_source_records` read normalized cached records instead of reopening `source_workflow_path` with the JSON-only loader. Verify evidence references match the cache key.
- **Touches:** `vibecomfy/executor/research.py:2309-2330`, `:2433-2462`, `_selected_source_records` at `:3163-3172`; `vibecomfy/ingest/workflow_source.py:78-100`.
- **Difficulty:** `medium` — a contained cache/access-path replacement with deterministic tests.
- **Depends on:** T-04, T-09.
- **Effort:** Day.
- **Risk to the hot path:** Alters record selection. Cache misses must fail closed without falling back to `.py` JSON loading, `prior_path`, or fixture discovery; run T-01.

### T-12 — Authoritative role taxonomy and inference

- **What it does:** Define the requested role taxonomy and infer roles in priority order: authoritative schema/socket type, socket name, class metadata/name, then neighborhood. Return evidence and confidence for every inference.
- **Touches:** Existing heuristic roles at `vibecomfy/executor/research.py:3203-3275`; schema consumers around `vibecomfy/porting/edit/apply_resolve_add.py:212-280`.
- **Difficulty:** `medium` — one coherent inference module with table-driven tests.
- **Depends on:** T-03.
- **Effort:** Day.
- **Risk to the hot path:** No binding replacement yet. Avoid golden class-name tables; class-name hints may be generic fallback evidence only, never a hard gate.

### T-17 — Full cut-edge coverage validator

- **What it does:** Replace the weak “some target was bound” check with validation that every mandatory cut edge has exactly one legal binding, all internal sockets are compatible, required roles are covered, and evidence hashes agree. Incomplete results become explicit rejections.
- **Touches:** `_validate_candidate_semantics` at `vibecomfy/executor/research.py:3418-3508`, especially current weak binding check at `:3463-3508`.
- **Difficulty:** `medium` — a bounded validator once cut edges and matcher output exist.
- **Depends on:** T-14, T-16, T-18.
- **Effort:** Day.
- **Risk to the hot path:** Changes pass/fail behavior in research. Keep old paths green by requiring this validator only for topology-manifest candidates during migration; run T-01.

### T-22 — Bounded manifest JSON for the fixer prompt

- **What it does:** Replace raw slice prose, required-node truncation, and path/widget leakage with bounded JSON for all 1–3 manifests. State that manifests are alternatives; the fixer preserves topology and supplies widgets only from the request, schema defaults, or separately qualified priors.
- **Touches:** `vibecomfy/comfy_nodes/agent/edit_research.py:80-299`; tests at `tests/test_comfy_nodes_agent_edit.py:16585-16935`.
- **Difficulty:** `medium` — one prompt assembler and its serialization tests.
- **Depends on:** T-18, T-21.
- **Effort:** Day.
- **Risk to the hot path:** Touches the fixer prompt. Keep direct-edit prompts empty and REPAIR/DEBUG behavior unchanged; assert absence of `candidate_graph`, filenames, paths, source IDs, widgets, sigma strings, and fixture metadata.

### T-23 — Batch-loop manifest allowlist and dependency derivation

- **What it does:** Add `topology_manifests` to compact execution-protocol notes and derive runtime dependencies from `nodes[].canonical_class_type`. Stop relying on `candidate_graph` or legacy selected-slice class lists when manifests exist.
- **Touches:** `vibecomfy/comfy_nodes/agent/edit_batch_loop_intro.py:289-307`, `:394-484`, session setup at `:706-720`.
- **Difficulty:** `medium` — a contained protocol and dependency-preflight update.
- **Depends on:** T-18, T-21.
- **Effort:** Day.
- **Risk to the hot path:** Touches the fixer batch loop. Preserve legacy fallback for non-manifest turns until T-27 passes; dependency discovery must not turn retrieved classes into prescribed/golden choices.

# Difficult

### T-05 — [SPIKE] ComfyUI subgraph-format variance matrix

- **What it does:** Survey real workflows across supported ComfyUI versions and codify boundary representations, nested definitions, public input/output bindings, disabled nodes, cycles, and depth limits. Produce executable characterization cases before sizing the inliner.
- **Touches:** `ready_templates/sources/custom_nodes/flux2/flux2_klein_9b_gguf_t2i.json:111,226-228`; `ready_templates/sources/official/edit/flux2_klein_4b_image_edit_base.json:257,342,492-494,1949`; tests at `tests/test_executor_research.py:2035-2118`.
- **Difficulty:** `difficult` — corpus investigation and cross-version format classification take several days.
- **Depends on:** T-02, T-03, T-04.
- **Effort:** Multi-day.
- **Risk to the hot path:** Spike only. Corpus paths are test inputs, never production selectors; T-06 must be resized after this spike.

### T-07 — [SPIKE] Proxy, broadcast, union, and wildcard behavior

- **What it does:** Characterize scoped `SetNode`/`GetNode`, duplicate setters, nested scopes, disabled helpers, Reroute variants, unions, wildcards, fan-in, and fan-out. Define when only a dependent region becomes incomplete versus when normalization must reject the source.
- **Touches:** Existing limited helper resolver `vibecomfy/porting/subgraph_resolve.py:45-116`; offline converter `vibecomfy/ingest/normalize.py:115-168`; tests near `tests/test_porting_edit_apply.py:1744-1809`.
- **Difficulty:** `difficult` — behavior varies by workflow dialect and needs corpus-backed policy decisions.
- **Depends on:** T-02, T-03.
- **Effort:** Multi-day.
- **Risk to the hot path:** Spike only. No setter keys, class names, or workflow filenames may become production special cases; T-08 is resized from this result.

### T-08 — Scoped Get/Set and passthrough collapse

- **What it does:** Resolve unambiguous scoped broadcasts to their true upstream source, remove `SetNode`/`GetNode`, and collapse typed one-in/one-out Reroute equivalents. Preserve origin/evidence chains and isolate ambiguous or type-incompatible regions as incomplete.
- **Touches:** `vibecomfy/ingest/workflow_source.py:100-177`; reusable precedent at `vibecomfy/porting/subgraph_resolve.py:52-116`; converter behavior at `vibecomfy/ingest/normalize.py:115-168`.
- **Difficulty:** `difficult` — nontrivial graph rewriting with scope and partial-completeness semantics.
- **Depends on:** T-06, T-07.
- **Effort:** 2–4 days.
- **Risk to the hot path:** Ingestion only until T-11. Never resolve by filename or known workflow ancestry; use scoped keys, topology, and types exclusively.

### T-09 — Post-expansion typing, resolution, and evidence completion

- **What it does:** Enrich normalized nodes with input/output port names, indexes, types, and cardinality after all inlining/collapse. Canonicalize class names and run resolver checks only then; record regional completeness and evidence for every surviving structural fact.
- **Touches:** `vibecomfy/ingest/workflow_source.py:230-255`; current premature UI conversion at `vibecomfy/ingest/normalize.py:125-166`; current class rejection at `vibecomfy/executor/research.py:3451-3461`.
- **Difficulty:** `difficult` — combines schema enrichment, dynamic ports, resolver behavior, and evidence integrity.
- **Depends on:** T-06, T-08, T-12.
- **Effort:** 2–4 days.
- **Risk to the hot path:** Resolver timing changes can alter candidate acceptance. Unresolved dynamic/union sockets fail closed or remain locally incomplete; never infer types from goldens.

### T-11 — Integrate normalization before slice construction

- **What it does:** Normalize every ranked workflow source before slices, replace the provenance singleton topology branch, and carry normalized records/edges forward. Provenance instances may remain qualified widget-prior evidence, but cannot determine topology or source eligibility.
- **Touches:** Provenance source branch `vibecomfy/executor/research.py:2684-2719`; `_build_precedent_slices` at `:2722-2850`, especially singleton branch `:2753-2815`; integration point `:4811-4850`.
- **Difficulty:** `difficult` — multi-file research hot-path replacement affecting every precedent route.
- **Depends on:** T-01, T-10.
- **Effort:** 3–4 days.
- **Risk to the hot path:** Directly touches `research.py`. Preserve non-workflow and legacy non-splice behavior; forbid fallback to `prior_path` or fixture ancestry; run the full T-01 matrix.

### T-13 — Inquiry-local minimal typed segment extraction

- **What it does:** Implement `extract_inquiry_local_segment()`: seed from inquiry terms and required roles, join seeds over shortest typed paths, absorb dependencies until a strong target equivalent exists, and leave target-equivalent backbone nodes outside.
- **Touches:** New helpers beside `vibecomfy/executor/research.py:3278-3323`; invoked from the current source-processing area `:3924-3957`.
- **Difficulty:** `difficult` — graph search, stopping policy, role evidence, and ambiguity handling require careful tests.
- **Depends on:** T-09, T-12, T-14.
- **Effort:** 2–4 days.
- **Risk to the hot path:** Not active until T-21. Segment choice must be invariant under IDs/widgets/filenames and must not consult known repair slices.

### T-16 — Global gated anchor matcher

- **What it does:** Implement maximum-weight bipartite matching between source cut edges and target ports. Hard-gate direction, socket compatibility, existence, and input cardinality before scoring; support unique exact-type `typed_passthrough` at medium confidence and emit alternatives on ambiguity.
- **Touches:** Replace greedy `_build_anchor_bindings` at `vibecomfy/executor/research.py:3294-3323`; integration site `:3953-3957`.
- **Difficulty:** `difficult` — a global optimizer with hard constraints and detailed diagnostics.
- **Depends on:** T-15.
- **Effort:** 2–4 days.
- **Risk to the hot path:** Binding behavior changes substantially. Matcher features must be generic schema/topology evidence; calibrated examples cannot become hidden class-name or fixture rules.

### T-19 — ID/widget-free manifest canonicalization and deduplication

- **What it does:** Build a canonical structural signature over class-colored, port-labeled nodes, internal edges, and boundary role/direction/socket signatures. Merge evidence for duplicates and prune supersets whose extra nodes add no inquiry role or boundary.
- **Touches:** New helpers beside `_build_adaptation_plan` at `vibecomfy/executor/research.py:3821-4098`; contract tests near `tests/test_executor_contracts.py:2165-2488`.
- **Difficulty:** `difficult` — graph canonicalization and safe superset pruning need adversarial tests.
- **Depends on:** T-18.
- **Effort:** 2–4 days.
- **Risk to the hot path:** No builder integration yet. Hashes must be invariant under IDs, widget mutation, and filenames while still distinguishing socket direction and multiplicity.

### T-20 — [SPIKE] Twelve-source cap and manifest ranking calibration

- **What it does:** Evaluate real retrieved workflows to calibrate the 12-source search budget, stopping after three distinct full passes, and ordering by coverage, exact sockets, resolver strength, retrieval rank, then smaller delta. Record sensitivity and resize T-21 if the bound is inadequate.
- **Touches:** Current three-slice retry limit at `vibecomfy/executor/research.py:3326-3327`; first-pass loop at `:3889-4009`; campaign corpus in `vibecomfy/demo_factory/run_campaign.py:40-280`.
- **Difficulty:** `difficult` — real-corpus calibration crosses retrieval quality, latency, and topology diversity.
- **Depends on:** T-11, T-13, T-17, T-19.
- **Effort:** Multi-day.
- **Risk to the hot path:** Spike only. Calibration cases must be held-out evaluations, not production filename/class overrides.

### T-21 — Build and emit `TopologyManifestSet`

- **What it does:** Implement `_build_topology_manifest_set()`, evaluate up to the calibrated source bound, retain at most three distinct full-pass manifests, and serialize incomplete candidates only under `rejections`. Add the set to `ResearchResult`.
- **Touches:** Replace/beside `_build_adaptation_plan` at `vibecomfy/executor/research.py:3821-4098`; invocation at `:4865-4870`; result assembly at `:4894-4905`; `vibecomfy/executor/contracts.py:1690-1750`.
- **Difficulty:** `difficult` — multi-file research→contract hot-path change combining A, C, validation, ranking, and deduplication.
- **Depends on:** T-11, T-13, T-17, T-18, T-19, T-20.
- **Effort:** 3–4 days.
- **Risk to the hot path:** High. Stage it alongside the legacy adaptation plan until T-27 passes, then retire the old candidate-graph path; run T-01 after every integration change.

### T-26 — Fixer selection, stale retry, union policy, and queue gate

- **What it does:** Select the highest-ranked compatible manifest; allow unions only when roles and target inputs are disjoint and the union revalidates. Stale target/source hashes, missing anchors, unresolved classes, or socket mismatch trigger another generic research pass—never partial application or invention—and successful splices must pass queue validation.
- **Touches:** Fixer prompt call at `vibecomfy/comfy_nodes/agent/edit_batch_loop_intro.py:782-795`; session setup at `:680-720`; queue validation at `vibecomfy/comfy_nodes/agent/edit_orchestration.py:132-176`, `:230-244`.
- **Difficulty:** `difficult` — crosses research retry policy, fixer selection, application, and final validation.
- **Depends on:** T-21, T-22, T-23, T-25.
- **Effort:** 3–4 days.
- **Risk to the hot path:** Direct fixer-loop change. Non-manifest REPAIR/ADDITIVE/MULTINODE/DEBUG turns must retain current behavior; no failure may fall back to a golden, filename, or fixture-derived choice.

### T-27 — Production-real end-to-end campaign proof

- **What it does:** Exercise normalization→segment→anchors→manifest→transactional splice on real retrieved artifacts covering subgraphs, Python ready templates, proxy-heavy workflows, dynamic sockets, multiple boundaries, rollback, and replay. Run the full four-category matrix and verify legacy single-node/debug paths remain green.
- **Touches:** `tests/test_executor_research.py:2035-3034`; `tests/test_demo_factory_multinode.py:216-421`; `tests/test_porting_edit_session.py:2519-2957`, `4103-4468`; `tests/test_comfy_nodes_agent_edit.py:16585-16935`.
- **Difficulty:** `difficult` — broad multi-layer verification and failure triage across the full pipeline.
- **Depends on:** T-26 and all preceding implementation tasks.
- **Effort:** 3–4 days.
- **Risk to the hot path:** This is the release gate. Test damage may use fixtures, but the running pipeline receives only the inquiry, current graph, retrieved artifacts, hashes, and schemas.

# Extremely difficult

### T-06 — Recursive cross-version subgraph inliner

- **What it does:** Recursively inline `definitions.subgraphs`, namespace inner IDs as `instance:inner`, bind public inputs/outputs, rewrite boundary edges, remove UUID containers, and detect cycles/depth explosions. Preserve origin coordinates and evidence through every rewrite.
- **Touches:** `vibecomfy/ingest/workflow_source.py:100-177`; existing limited resolver `vibecomfy/porting/subgraph_resolve.py:52-116`; source fixtures identified in T-05.
- **Difficulty:** `extremely difficult` — foundational graph rewriting across format variants with high silent-corruption risk.
- **Depends on:** T-05.
- **Effort:** Week+; resize after T-05.
- **Risk to the hot path:** Kept behind normalization until T-11. Unknown boundary formats must fail closed or mark only affected regions incomplete; never special-case known fixture UUIDs or filenames.

### T-15 — [SPIKE] Dynamic-socket and matcher-weight calibration

- **What it does:** Prototype the 45/25/15/10/5 scoring model against real ambiguous graphs, multiple same-type samplers, dynamic sockets, unions, cardinality conflicts, and wildcard boundaries. Establish score margins, ambiguity policy, and when outward expansion is mandatory.
- **Touches:** Current greedy matcher at `vibecomfy/executor/research.py:3294-3323`; schema compatibility at `vibecomfy/porting/edit/apply_resolve_add.py:212-280`; cut-edge tests from T-14.
- **Difficulty:** `extremely difficult` — explicitly calibration-heavy and prone to plausible but wrong bindings.
- **Depends on:** T-12, T-13, T-14, T-01.
- **Effort:** Week.
- **Risk to the hot path:** Spike only. Weights and margins must be corpus-generic; no per-workflow class, filename, node-ID, or fixture exceptions. T-16 is sized after this spike.

### T-24 — [SPIKE] Transactional splice architecture

- **What it does:** Prototype `SpliceManifestRequest` plus a parser-visible `splice_manifest("M1")` macro backed by internal `EditSession.splice_manifest()`. `M1` is the prompt-local opaque handle for the displayed candidate: naming it is explicit acceptance, so ranked evidence never auto-applies. The preview uses the current graph's Python-y idiom but is non-executable and widget-free (`# m02 = CLIPTextEncode(text=?)`); aliases are collision-free with current-graph names. Determine how the session clones state, validates graph/evidence hashes and complete anchors, reserves symbol→UID bindings for following ordinary field assignments, and commits atomically while remaining replayable. Prove that no seventh persisted canonical operation is required.
- **Touches:** fixer projection at `vibecomfy/comfy_nodes/agent/edit_research.py:91-130` and `edit_batch_loop_intro.py:138-228`; parser/resolver at `vibecomfy/porting/edit/_parse.py` and `_resolve.py`; `vibecomfy/porting/edit/session.py:112-158`; transaction snapshot/rollback at `vibecomfy/porting/edit/_parse_execute.py:50-158`; atomic apply substrate `vibecomfy/porting/edit/apply_core.py:87-149`; canonical vocabulary `vibecomfy/porting/edit/ops.py:58-65`.
- **Difficulty:** `extremely difficult` — architectural work spanning mutable session state, minted identities, guards, and replay.
- **Depends on:** T-02, T-18.
- **Effort:** Week; T-25 is resized from the prototype.
- **Risk to the hot path:** Keep the spike behind an opt-in manifest lane. The preview and handle must not expose paths, source IDs, widget values, sigma strings, or fixture/golden tokens, and must not look like executable node-construction instructions. A zero-anchor manifest fails closed with an actionable `manifest_unanchored` diagnostic; stale hash and ambiguous/missing anchors likewise direct generic re-research, never manual reconstruction.

### T-25 — Atomic `EditSession.splice_manifest()` lowering

- **What it does:** Treat `splice_manifest("M1")` plus its following ordinary `mNN.field = value` statements as one planned transaction. On cloned state, recheck graph/evidence hash and complete named anchors; resolve classes; collect required widget bindings from those existing `set_node_field` statements plus allowed schema defaults/qualified priors; add nodes while capturing UIDs and binding collision-free aliases; lower internal and boundary edges to `UpsertLinkOp`; apply the field sets; run full guards; then commit UI, ledger, names, touched sets, and landed canonical ops together. Persist only the existing canonical ops. Do not add a `dict(...)` kwargs form: it duplicates `set_node_field` and makes multinode value editing unlike the single-node path that already works.
- **Touches:** `vibecomfy/porting/edit/session.py:112-158`; `vibecomfy/porting/edit/ops.py:177-199`; add-node mutation `vibecomfy/porting/edit/apply_mutate.py:219-329`; socket validation `vibecomfy/porting/edit/apply_resolve_add.py:212-280`; full replay/gates `vibecomfy/porting/edit/_gates.py:27-156`.
- **Difficulty:** `extremely difficult` — high-risk transactional mutation with fresh identities, multi-edge lowering, rollback, and deterministic replay.
- **Depends on:** T-17, T-21, T-23, T-24.
- **Effort:** Week+.
- **Risk to the hot path:** Directly extends `EditSession`. Any failed splice or trailing field assignment leaves the session byte-for-byte unchanged. Missing required values, zero/incomplete anchors, stale hashes, unresolved classes, or socket mismatches produce typed, actionable refusal diagnostics and never fall back to partial application, implicit-on-`done()`, or model-authored reconstruction; existing non-manifest batch editing remains unchanged.

## Recommended build order

A dependency-respecting sequence, with spikes treated as sizing gates:

1. **Guards and contracts:** T-02 → T-01 → T-03 → T-18  
2. **Normalization dispatch:** T-04  
3. **Subgraph track:** T-05 → resize → T-06  
4. **Proxy track:** T-07 → resize → T-08  
5. **Typed normalization:** T-12 → T-09 → T-10 → T-11  
6. **Segment and boundaries:** T-14 → T-13  
7. **Anchor calibration and implementation:** T-15 → resize → T-16 → T-17  
8. **Manifest structure:** T-19  
9. **Source-budget calibration:** T-20 → resize → T-21  
10. **Fixer communication:** T-22 → T-23  
11. **Transactional application:** T-24 → resize; after T-17 + T-21 + T-23 are green, T-25  
12. **Selection and final gates:** T-26  
13. **Release proof:** T-27

T-24 can spike the transaction and agent surface in parallel once T-18 exists. T-25 must not integrate with the fixer until segmentation/anchor coverage (T-17), anchored manifest construction (T-21), and communication (T-23) are green: an atomic splice cannot compensate for an unbounded or zero-anchor slice.
