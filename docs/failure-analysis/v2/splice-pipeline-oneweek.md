<!-- Auto-extracted from the Codex one-week task-batch pass. The v0 fast-path for the real-additive-editor epic. -->

## One-week batch

Scope: roughly 9–10 person-days. The schedule assumes two implementation lanes after Day 1. With one engineer, commit the manifest-forwarding lane first and treat the anchor lane as stretch.

Batch-wide rule: production decisions may use only the inquiry, current broken graph, generically retrieved precedent evidence, its content hash, and authoritative runtime schemas. No `prior_path`, golden graph, fixture ancestry, campaign node IDs, hard-coded node types, widget values, filenames, prompts, model names, seeds, or sigma strings.

### Easy

#### W-01 — Anti-gaming scanner and perturbation helpers

- **What it does:** Adds reusable assertions rejecting forbidden manifest/prompt fields and proving that renumbering source IDs or mutating widgets, filenames, prompts, and sigma values does not change the projected topology.
- **Touches:** `tests/test_executor_research.py:2035-2118`; `tests/test_comfy_nodes_agent_edit.py:16585-16942`.
- **Difficulty:** `easy` — isolated test utilities with no production behavior.
- **Depends on:** None.
- **Effort:** 3–4 hours.
- **Hot-path risk:** None directly. This becomes a mandatory guard for shared REPAIR/ADDITIVE/MULTINODE/DEBUG changes.
- **Anti-gaming:** Explicitly rejects `prior_path`, golden/fixture ancestry, source or campaign IDs, widget literals, filenames/paths, prompts, model names, sigma strings, and case-specific class lists.

#### W-02 — Singular focused-manifest contract

- **What it does:** Adds an optional `TopologyManifest` to the existing adaptation plan. The shallow contract contains local symbols, precedent-derived canonical class types, internal edges, role/class/socket boundary selectors, existing validation verdicts, confidence, and an opaque evidence hash. Enforce one manifest, complete-or-reject serialization, and explicit size bounds such as 64 nodes/128 edges/16 anchors—never silent truncation.
- **Touches:** `vibecomfy/executor/contracts.py:960-1054`, `:1689-1750`; `tests/test_executor_contracts.py:2165-2488`.
- **Difficulty:** `easy` — backward-compatible dataclasses and serialization invariants.
- **Depends on:** W-01.
- **Effort:** Half-day.
- **Hot-path risk:** `contracts.py` is shared. Keep the field optional and legacy output byte-compatible when absent; all four paths run through W-03.
- **Anti-gaming:** The public contract has no fields capable of carrying paths, source/target IDs, literals, fixture metadata, or `candidate_graph`; canonical classes must carry retrieved-evidence provenance.

#### W-04 — Pure validated-candidate projector

- **What it does:** Diffs an already validated `candidate_graph` against the target graph, assigns fresh local symbols (`n1`, `n2`, …), retains only added-node class types, and emits internal edges only for two-item `[known_node_id, output_slot]` references between added nodes. Scalar/list literals are discarded. Existing bindings are transformed into ID-free role/class/socket boundary selectors.
- **Touches:** candidate synthesis at `vibecomfy/executor/research.py:3511-3593`; plan assembly at `:4069-4098`; tests at `tests/test_executor_research.py:2518-2879`.
- **Difficulty:** `easy` — a pure, deterministic projection over existing accepted data.
- **Depends on:** W-01, W-02.
- **Effort:** Half-day.
- **Hot-path risk:** None until W-05 integrates it. Perturbation tests cover all four path inputs.
- **Anti-gaming:** Only link-shaped inputs are topology. Widgets, filenames, prompts, seeds, models, sigma strings, source IDs, target IDs, `prior_path`, and golden facts are unconditionally dropped.

#### W-08 — Deterministic cut-edge enumeration

- **What it does:** For a lean source segment `S`, emits every edge with exactly one endpoint in `S` once: outside→inside is inbound; inside→outside is outbound. Retains direction, input name, output slot, generic role evidence, and authoritative socket type when available.
- **Touches:** new helper beside `vibecomfy/executor/research.py:3278-3323`; tests at `tests/test_executor_research.py:2518-2879`.
- **Difficulty:** `easy` — a small graph-set operation with exhaustive property tests.
- **Depends on:** W-01.
- **Effort:** 3–4 hours.
- **Hot-path risk:** None before W-11. Tests prove invariance under ordering, ID renumbering, widgets, filenames, and fixture changes.
- **Anti-gaming:** Segment edges come solely from the retrieved source graph; no known repair slice, golden topology, `slice_node_ids`, or `prior_path` may define `S`.

### Medium

#### W-03 — Four-category release guard

- **What it does:** Establishes cheap, non-live smoke coverage for REPAIR, ADDITIVE, MULTINODE, and DEBUG, plus characterization of current positive controls. Assert route semantics, prompt isolation, legacy fallback, and that fixture construction data never reaches research or the fixer.
- **Touches:** category definitions at `vibecomfy/demo_factory/run_campaign.py:39-80`, `:83-261`; four loops at `:1183-1218`; shared gates at `vibecomfy/demo_factory/case.py:415-483`; tests beside `tests/test_demo_factory_multinode.py:65-421`.
- **Difficulty:** `medium` — test-only, but spans four execution routes and becomes the release gate.
- **Depends on:** W-01.
- **Effort:** 6–8 hours.
- **Hot-path risk:** No production changes. REPAIR and DEBUG must keep their direct/revise prompts; ADDITIVE without a manifest and existing MULTINODE positives retain legacy behavior.
- **Anti-gaming:** Fixture locators and `slice_node_ids` may create damage only; the smoke runner asserts they are absent from classification, research, protocol notes, prompts, and application inputs.

#### W-06 — Manifest-aware fixer prompt

- **What it does:** Replaces the deliberate topology exclusion with one bounded JSON manifest and instructions to preserve its nodes, internal edges, and boundary selectors. Widget values may come only from the user request, authoritative schema defaults, or separately qualified existing priors. Keep legacy prose only when no manifest exists.
- **Touches:** `vibecomfy/comfy_nodes/agent/edit_research.py:80-94`, current lossy/path-bearing rendering at `:125-299`; prompt tests at `tests/test_comfy_nodes_agent_edit.py:16585-16942`.
- **Difficulty:** `medium` — one prompt surface with contained routing tests.
- **Depends on:** W-02, W-05.
- **Effort:** 4–6 hours.
- **Hot-path risk:** Gate injection to canonical `adapt`. REPAIR/DEBUG revise prompts remain unchanged; ADDITIVE/MULTINODE use the manifest only when W-05 emitted a valid one.
- **Anti-gaming:** Do not reuse the provenance block at `edit_research.py:173-198` or selected-slice paths at `:129-148`; both can leak forbidden values. Assert the prompt contains neither raw `candidate_graph` nor ancestry data.

#### W-07 — Protocol allowlist and dependency derivation

- **What it does:** Preserves the complete singular manifest through the actual ADAPT-path compact protocol notes and derives runtime dependencies from `nodes[].canonical_class_type`. Adds a dedicated manifest compactor so the generic depth/list limits cannot silently truncate a 40-node delta. Legacy candidate/slice class discovery remains fallback-only.
- **Touches:** `vibecomfy/comfy_nodes/agent/edit_batch_loop_intro.py:244-338`, especially allowlist `:289-305`; current class-only use at `:341-484`; session setup `:656-720`; tests at `tests/test_comfy_nodes_agent_edit.py:4268-4508`, `:16865-16942`.
- **Difficulty:** `medium` — contained protocol and dependency-preflight change.
- **Depends on:** W-02, W-05.
- **Effort:** 4–6 hours.
- **Hot-path risk:** Prefer manifest classes only when a complete manifest exists; otherwise preserve current REPAIR/ADDITIVE/MULTINODE/DEBUG behavior. Reject oversize manifests instead of applying partial topology.
- **Anti-gaming:** Dependency discovery may verify retrieved classes against runtime inventory but cannot introduce classes from goldens, filenames, fixture labels, or `prior_path`.

#### W-09 — Lean inquiry-role and socket matcher

- **What it does:** Seeds a small source component from generic inquiry terms and roles, grows through feature-control/transform nodes until the first role-bearing model/conditioning/latent/sampler/output boundary, then matches its cut edges only when direction, role, concrete socket type, endpoint existence, and target-input uniqueness agree. Unknown, wildcard, dynamic, or tied matches fail closed. There are no calibrated weights.
- **Touches:** role logic at `vibecomfy/executor/research.py:3203-3275`; current first-match code at `:3278-3323`; schema/socket substrate at `vibecomfy/porting/edit/apply_resolve_add.py:212-280`; source-record limitation at `vibecomfy/ingest/workflow_source.py:33-45`.
- **Difficulty:** `medium` — one narrow matcher with table-driven cases; intentionally avoids global optimization.
- **Depends on:** W-08.
- **Effort:** One day.
- **Hot-path risk:** Initially remains a pure helper. It must consult authoritative schemas because `WorkflowNodeRecord` has no typed outputs. Unknown types reject rather than invoking permissive compatibility.
- **Anti-gaming:** Roles are inferred generically from inquiry, sockets, schema, class metadata, and neighborhood. No depth/ReCam-specific class table, workflow filename, case ID, golden node type, or `prior_path`.

#### W-10 — Mandatory boundary-coverage gate

- **What it does:** Requires every mandatory cut edge to have exactly one hard-gated binding before candidate synthesis or manifest emission. Records explicit diagnostics for unknown type, direction mismatch, occupied input, ambiguity, and uncovered boundaries.
- **Touches:** semantic validation at `vibecomfy/executor/research.py:3418-3508`, especially the current weak binding check at `:3463-3508`; tests at `tests/test_executor_research.py:2518-3034`.
- **Difficulty:** `medium` — a bounded validator once W-08/W-09 provide structured results.
- **Depends on:** W-02, W-08, W-09.
- **Effort:** Half-day.
- **Hot-path risk:** Activate only for the new manifest-capable splice path. Non-manifest REPAIR/ADDITIVE/MULTINODE/DEBUG retain their existing validation during the migration.
- **Anti-gaming:** Coverage is computed from retrieved cut edges and current graph ports, never from the number or shape of golden repair edges.

#### W-12 — Targeted replay and Day-7 measurement gate

- **What it does:** First reruns the six targeted cases, then W-03, then the exact 40-case campaign. Compares verdicts and fingerprints with the July 28 baseline and distinguishes:
  1. manifest never emitted,
  2. manifest reached the prompt but batch REPL failed to apply it,
  3. candidate applied but oracle rejected it,
  4. regression outside target cases.
- **Touches:** campaign loops at `vibecomfy/demo_factory/run_campaign.py:1183-1218`; baseline summary `out/demo-candidate-factory/20260728-all40-par/all40_results.json:1`; target statuses such as `cases/bee83462150b/status.json:3-12` and `cases/05d07d0df6b7/status.json:3-13`.
- **Difficulty:** `medium` — operationally straightforward, but live execution and triage can consume a day.
- **Depends on:** W-03, W-05, W-06, W-07, W-11.
- **Effort:** One day.
- **Hot-path risk:** This is the release gate. The historical 40 are 10 ADDITIVE, 20 MULTINODE, and 10 DEBUG, so W-03 supplies the otherwise-missing REPAIR guard immediately before the campaign.
- **Anti-gaming:** Compare outcomes only after execution. Historical verdicts/goldens are measurement oracles, never research, prompt, ranking, binding, or application inputs.

### Difficult

#### W-05 — Emit one projected manifest on the research hot path

- **What it does:** When—and only when—the existing candidate has `structural_validation=pass`, `semantic_validation=pass`, and a nonempty `candidate_graph`, runs W-04 and attaches one complete manifest to the adaptation plan. Keeps current retrieval, three-slice behavior, warnings, and all legacy fields/fallbacks.
- **Touches:** `_build_adaptation_plan` at `vibecomfy/executor/research.py:3821-4098`, especially acceptance `:3953-4008`; research result assembly `:4865-4905`; serialization `vibecomfy/executor/contracts.py:960-1054`, `:1689-1750`; protocol handoff `vibecomfy/executor/core.py:1180-1284`.
- **Difficulty:** `difficult` — multi-file research→contract hot-path integration with regression-sensitive serialization.
- **Depends on:** W-03, W-04.
- **Effort:** Two days including targeted tests.
- **Hot-path risk:** High but contained by pass-gating and optional fields. REPAIR/DEBUG normally emit no manifest; ADDITIVE and MULTINODE fall back unchanged when validation fails or projection rejects.
- **Anti-gaming:** The projector receives only the current graph, already retrieved/validated candidate, existing bindings, and evidence hash. It must not open `golden.ui.json`, promote `prior_path`, or use fixture ancestry to select nodes or edges.

#### W-11 — Replace endpoint anchors with lean cut-edge bindings

- **What it does:** For manifest-capable additive research, stops treating the first/last sorted source nodes as anchors. Runs W-09/W-10 before synthesis, builds bindings from actual typed cut edges, and synthesizes only after complete unique coverage. Preserve old `WorkflowSlice` fields for compatibility, but ignore their numeric endpoint anchors on this path.
- **Touches:** endpoint selection at `vibecomfy/executor/research.py:2722-2855`, especially `:2826-2835`; greedy binding `:3278-3323`; integration at `:3924-4008`; tests `tests/test_executor_research.py:2518-3034` and `tests/test_demo_factory_multinode.py:216-349`.
- **Difficulty:** `difficult` — changes candidate acceptance in the shared synthesis path and requires multi-case integration tests.
- **Depends on:** W-03, W-09, W-10.
- **Effort:** Two days.
- **Hot-path risk:** Highest anchor-lane risk. Gate it to manifest-capable additive research; fail closed on ambiguity instead of broadening behavior. W-03 must remain green after every integration step, with special attention to accepted MULTINODE controls.
- **Anti-gaming:** Generic retrieval sources only. The breadcrumb/provenance branch at `research.py:2684-2719`, including `prior_path`, cannot supply topology. No special cases for `depth_controlnet`, ReCamMaster, known node IDs, filenames, or golden boundaries.

### Very difficult

None. If W-09 encounters dynamic/wildcard sockets or requires weighted global matching, reject those candidates and defer them to T-15 rather than expanding the week into a very-difficult task.

## Day-by-day schedule

This uses two lanes after the guards land.

- **Day 1 — Guards first:** W-01, W-02, and baseline W-03. Capture the current four-category results before production changes.
- **Day 2 — Pure building blocks:** W-04 in the manifest lane; W-08 and the first half of W-09 in the anchor lane.
- **Day 3 — Start integration:** W-05 research/contract integration; finish W-09 and implement W-10.
- **Day 4 — Complete manifest emission:** finish W-05 and its contract/research tests; begin W-06/W-07. In parallel, begin W-11.
- **Day 5 — Complete both handoffs:** finish W-06 and W-07; continue W-11. Run targeted deterministic tests after each shared-code change.
- **Day 6 — Integration buffer:** finish W-11, rerun W-03, and perform the six targeted case preflight. Fix only regressions or defects within the declared lean algorithms—no dynamic matcher or transactional-splice expansion.
- **Day 7 — Measurement gate:** W-12: run the four-category guard, then rerun the full 40-case campaign into a fresh output directory. Compare verdicts/fingerprints to `20260728-all40-par`; ship only if existing non-target green cases stay green.

## Realistic expected outcome

The planning forecast is **4 of the 18 genuine repair failures flipped**, with a credible **3–6 range**.

The four highest-confidence cases already produced nonempty candidates, bindings, and both validation passes:

- `latent_refinement`
- `accelerated_audio_conditioning`
- `reference_motion_guidance`
- `synchronized_soundtrack`

They failed after synthesis because topology was not forwarded. For example, `latent_refinement` has passing validation and a candidate at `cases/bee83462150b/attempts/001/research.json:1848-1859,4276-4277`.

`depth_controlnet` and `camera_reframing` provide **0–2 upside**, not a commitment. Both currently fail before candidate construction with empty bindings, so the lean anchors must first make synthesis pass and then rely on the same non-transactional fixer application.

The normalization/UUID cases do not move. Nor should the remaining selection failures or the single-node fixer-misuse case be expected to improve accidentally.

## Biggest risk to the week

The fixer may receive a correct focused manifest and still fail to reproduce it through the existing batch REPL. Without T-24/T-25, there is no atomic manifest-level application primitive—only model-generated batches applied through `EditSession`.

Day 7 must therefore record whether each miss occurred before manifest emission, during prompt consumption, during batch application, or at the oracle. If the manifest consistently arrives but application fails, that is strong evidence to prioritize transactional splice next.

## What the week delivers even if results under-perform

Even with fewer than three flips, the week leaves:

- a production-real anti-gaming scanner and four-category release gate;
- a bounded, ID/widget/path-free topology contract;
- a verified projection of accepted synthesis into actionable structure;
- explicit cut-edge and binding diagnostics rather than first/last-node guessing;
- evidence separating research failure from application failure;
- concrete sizing evidence for whether the next investment is T-15 matcher calibration or T-24/T-25 transactional application.

## Explicitly deferred

- **T-06:** recursive cross-version subgraph inlining; UUID-as-class cases remain failing.
- **T-15:** calibrated 45/25/15/10/5 matcher, global bipartite optimization, dynamic/wildcard policy.
- **T-19:** manifest canonicalization and deduplication.
- **T-20:** source-budget/ranking calibration; emit one manifest and retain current retrieval limits.
- **T-24/T-25:** transactional splice architecture and atomic lowering; use existing batch REPL.
- Full T-13/T-16 general extraction/matching, multi-manifest T-21 ranking, and T-26 union/stale-retry policy remain outside the week.
