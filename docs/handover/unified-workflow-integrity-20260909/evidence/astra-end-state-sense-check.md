# Astra end-state sense check — 2026-09-09

Reviewed published package `docs/handover/unified-workflow-integrity-20260909` at commit `ed0d16d2a4b86d3e2750b1349a2a4e189110cbe8` in the isolated handover worktree. Read full plan, tasklist, acceptance ledger, North Star, execution-start, D1, goal, consolidation and H3 baseline; inspected relevant existing conversion/user-path/emitter/editability tests read-only. No product changes or tests executed. This is the explicitly requested extra planning review, not an oracle decision or product certification; this artifact does not reset or alter counters.

## Verdict

The architecture and clean-Python contract are sound. Two small acceptance clarifications would make the requested end state demonstrable rather than partly implied. No new architecture, task family, review stage, universal ingestion migration or GPU run is needed. The host can make these uncontested in-scope evidence corrections within E0/E1/T3/E2. A nested-source-edit test is an additional nonblocking suggestion for implementing the existing contract.

The existing whole-file clarification already closes the main cosmetic loophole: no graph dump in custody, no runtime values in custody, no post-construction replay, and one authoritative runtime expression. I8 requires actual constructor/default/public-control edits; D1 requires handle wiring once, behavioral fidelity and independent identity/native-port custody. These do not need another redesign. Keep necessary identity facts outside ordinary calls; banning all internal IDs would conflict with the preservation goal.

## 1. Visual graph end state has no required receipt

**Required evidence gap.** I10 currently requires generated Python, edits, semantic/identity comparisons and deterministic regeneration. The clean-source clarification requires opening the whole Python file, but neither I10 nor E2 explicitly requires materializing/exporting the edited graph and inspecting its visible graph/subgraph representation. The named canvas test checks persisted dictionaries, not a rendered canvas. Thus all listed evidence could pass while visible ports, group membership or presentation are wrong. This matters because the user's request includes how the result actually looks and proper subgraph representation.

Sources: `acceptance-ledger.md:31,43–45`; `execution-start.md:59–61`; `plan.md:9,29`; `tests/test_canonical_user_paths.py:121`.

**Smallest correction:** append to I10 evidence and E2 brief, with E2 still owning the work:

> After editing and rebuilding the actual generated H3 file, save/reload it and materialize/export its UI graph through the normal public boundary. Record the exact Python, exported graph and presentation-sidecar identities. Assert the expected nodes, effective links, public ports, supported subgraph/instance representation and preserved presentation fields by stable identity; account explicitly for supported native expansion and normalization. Inspect the whole generated Python and the graph rendered from that exact exported artifact, including its subgraph/boundary detail, and retain a screenshot or rendered view plus a short criterion-linked inspection finding. Reject unreadable replay/custody clutter, missing or misbound ports, unintended flattening of a supported authored structure, or lost presentation. Use an already available viewer/rendering path; no UI redesign, runtime provisioning or GPU output-quality claim. Missing visual evidence remains MISSING, not PASS.

This requires both deterministic structure/presentation assertions and actual inspection. It does not impose pixel equality, automatic layout redesign, or a new screenshot service.

## 2. A shared emitter is specified more concretely than shared ingestion

**Required evidence gap.** Goal and N4 require one canonical onboarding path/rule owner. E1 correctly owns one emitter; I9 explicitly compares helper lowering across canonical/ready/scratchpad outputs. That does not itself prove the supported ingress routes share interpretation and refusal rules. The current CLI calls `analyze_source`, `load_port_source`, then conversion; the existing cross-path user test exercises direct `from_ui`, conversion and capture on one simple valid graph, not the real CLI or a shared negative case. Existing behavior may already be correct: this is an evidence requirement, not a demand to rewrite ingestion.

Sources: `goal.md:1–3`; `northstar.md:8`; `acceptance-ledger.md:28–30`; `decisions/emission-D1.md:25`; `vibecomfy/commands/port/_convert.py:64–95`; `tests/test_canonical_user_paths.py:82–118`.

**Smallest correction:** append to I7/I9 evidence; E0 records the baseline, E1 fixes only a demonstrated owner split, and T3 integrates the proof into an existing suite run by Q5:

> Record a short source-backed call-path map for the existing CLI conversion, SDK onboarding and canvas capture entrypoints, naming the common normalization/schema-authority, emitter and publication owners and the legitimate wrapper differences. Exercise the same supported draft fixture and one malformed boundary/schema fixture through those real entrypoints. Compare admitted semantics, identity/native-port custody and semantic refusal reason, allowing different report formatting and explicitly optional presentation persistence. The normal H3 conversion must consume that same owner path without an H3-only bypass or restoration patch. A shared output formatter alone is not proof of shared ingestion. Reuse existing owners; no global ingestion migration or new facade is required.

The negative case should be malformed authority rather than merely a missing model: draft saving is deliberately allowed without execution readiness.

## Optional: make one existing source-edit test a nested definition edit

**Optional test selection within existing I8/I9, not a new blocker.** I8 requires source editing and I9/D1 preserve subgraphs. A particularly useful way to combine these requirements is a generated definition constructor edit that retains instance overrides, sibling identity and boundary references. Current depth-two tests verify unchanged round-trips and contain importer-shaped syntax expectations; E0/T3 are already assigned to migrate those assertions. The existing contract can be satisfied by other adequate evidence, so this precise fixture is not independently mandatory.

Sources: `acceptance-ledger.md:29–30`; `decisions/emission-D1.md:20–23`; `tests/test_porting_emitter.py:246–279`; `tests/test_h3_generated_editability.py:19–59`.

**Suggested worker test brief:**

> Extend the existing depth-two/repeated-instance subgraph fixture with a real edit to a constructor/default in the emitted nested definition, then reload and re-emit the edited file. Assert the expected effective change, retained per-instance overrides, untouched sibling/scoped UIDs, interface and boundary bindings, fanout and output slots, and API/GraphBuilder parity. Apply the whole-file clean-source/custody checks inside generated definition helpers as well as build(). Keep malformed-boundary refusal coverage. Public-argument overrides alone do not satisfy this source-edit case.

This is one focused regression at the existing emitter seam, not new generic subgraph support. If the existing fixture needs two instances to distinguish overrides/sibling custody, extend it minimally.

## Already adequate / optional only

- Real H3 regeneration is already mandatory and cannot use the committed historical builder. Current-main refusal is correctly marked baseline evidence, not acceptance.
- D1 already names definitions, interfaces, variants, boundaries, virtual wires, native output authority, helper provenance and deterministic re-emission. No need to duplicate that architecture in another decision.
- Atomic loss refusal, paired-file identity, draft-vs-readiness, export persistence distinctions and retained revision fencing have concrete positive/negative requirements.
- No arbitrary line count, custody byte budget, universal graph promise, second pretty mode, global ingestion consolidation, extra reviewer gate, transport rewrite or GPU generation is justified by this review.

After the two required clarifications, the plan is adequate for the requested end state: a normal public ingestion produces clean Python; a visible source edit survives rebuild/publication; equivalent supported ingress paths share the same semantic rules; required identity and subgraph relationships survive; and the exact exported graph plus the whole Python file are actually inspected. No additional planning review is needed to apply this bounded evidence wording. All implementation evidence remains NOT RUN/MISSING until delivery.
