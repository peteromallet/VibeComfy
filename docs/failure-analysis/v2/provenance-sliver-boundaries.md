# Boundary assessment: additive-evidence provenance sliver

## Position

The sliver is correctly scoped as an evidence improvement, not an additive-editor completion project. Its primary acceptance test—role-preserving, provenance-tagged evidence on a template-derived workflow outside the demo corpus—is the right guardrail. However, four “impossible” items are framed too absolutely. I1–I4 should remain outside the one-week delivery guarantee, but their descriptions must distinguish an information limit from a deferred dependency and must not imply that m4 alone resolves every case. I5 is correctly bounded.

The current code supports that distinction. `executor/research.py` is local-corpus-first and never reads `extra.vibecomfy.source_template` or `prior_path`. `WorkflowSlice` carries node IDs, types, anchors, and paths, but not named values, incident edges, roles, or value provenance. `_build_precedent_slices()` also deduplicates sources by `class_type`. Meanwhile, route normalization makes `revise` research-free and `adapt` research-backed. The breadcrumb is emitted at graph level by `porting/emit/ui.py`, and the edit path preserves it as ready metadata, but research does not consume it. There is no `vibecomfy/executor/provenance.py`; the existing porting and security provenance modules describe different concepts and should not be overloaded for evidence provenance.

## I1 — Guarantee cases 01/08/09 pass

**Verdict: reframe.**

Rejecting a demo-pass guarantee as a sliver acceptance criterion is correct. Saying the missing guarantee is simply “m4 typed construction” is not.

- Case 01 already lands the correct node and second-pass wiring; it chooses the first-pass sigma schedule. This is chiefly per-instance evidence and role binding, not failed construction.
- Case 08 lands the correct topology but uses a provisional positional schema. It needs authoritative schema resolution and named construction. Its current exact failure also includes seed identity and extra positional fields; an incidental seed mismatch should not make an otherwise valid novel edit incorrect.
- Case 09 is wrong in stage, interpolation method, and branch coverage. It primarily needs m1 intent postconditions and m2 placement/coverage, then m4 to land and repair the candidate.

“Pass” must therefore be mode-specific. The product oracle should accept any candidate satisfying EditIntent, including valid non-identical values where the request leaves them open. A dedicated restore-regression oracle may require canonical functional settings and topology when the user explicitly asks to restore behavior and trustworthy provenance exists. That does not authorize putting golden answers in the fixer prompt: evidence remains tagged priors, while the oracle independently evaluates the result. Case 01’s refinement schedule and case 09’s stage remain functional failures; case 08’s arbitrary seed identity should be diagnostic rather than a product-validity blocker.

An end-to-end guarantee belongs after m1, m2, m3/sliver, m4, and authoritative resolution are integrated. The sliver should promise evidence fidelity, not case outcomes.

## I2 — Fix fixer-failure cases 05/06

**Verdict: reframe.**

Both cases are construction-blocked, but calling them “not evidence failures” is inaccurate.

Case 05 found the exact template and even represented the correct `WanVideoLoraSelect → WanVideoModelLoader.lora` relationship. It then exhausted turns in schema loops, emitted a boolean/numeric validation error, and finally asked for a filename present in the source template. Better actionable evidence can remove the last information failure, but it cannot provide a dependable named constructor or repair malformed fields. Completion requires unified schema resolution plus m4’s schema-named construction and intent-condition retry feedback.

Case 06 is more decisively construction-bound. The agent repeatedly tried to mutate a surviving sibling’s non-editable widget, attempted positional construction, and then followed an irrelevant IAMCCS precedent. Provenance-first evidence would expose the two sibling branches and prevent the bad precedent detour, but m2 must identify the missing branch/anchor and m4 must create and splice the new node safely.

Thus 05/06 remain outside the sliver’s completion promise, but the sliver is still a necessary upstream fix. They are mixed evidence/construction failures, not proof that evidence is irrelevant.

## I3 — Additive edits on provenance-less workflows

**Verdict: reframe.**

Full provenance-less editing is genuinely outside this one-week sliver; it is not inherently condemned to the currently weak corpus path. Provenance is one high-confidence prior, not a prerequisite for editing. Case-00-shaped additions are already decidable from the request, current graph, and schema, and the planned novel-addition benchmark explicitly removes `prior_path`.

The correct fallback ladder is:

1. derive EditIntent and hard postconditions;
2. inspect the current graph for roles, insertion loci, and compatible siblings;
3. resolve the authoritative schema on demand for named fields, socket types, enums, and defaults;
4. use role-compatible sibling/default values as tagged priors;
5. search the corpus/Hivemind only for residual semantic uncertainty;
6. construct and repair against intent conditions.

Schema resolution establishes legality, not purpose: it cannot decide pre-encode versus post-decode placement or invent a domain-specific model choice. When residual high-impact uncertainty remains, the correct fallback is clarification or a typed no-op, not a confident guess. The sliver must at least preserve this fallback contract and must not make provenance presence the sole research gate. The epic owns making that ladder reliable.

## I4 — Pick a value with ambiguous roles and no signal

**Verdict: reframe.**

If there is genuinely no disambiguating signal, confident selection is impossible even after m2 and m4. Those milestones may discover a signal and can apply a choice; they cannot manufacture evidence.

“Surface-and-tag” is always correct for the evidence layer, but not always for execution. If alternatives change a hard task condition—stage, branch, model file, control mode, destructive resolution, or preservation—the executor should clarify, or refuse to mutate when no safe clarification is available. Passing ambiguous priors to a fixer and letting it choose is merely hidden guessing. Autonomous choice is appropriate only for incidental/reversible values, or when every remaining candidate is equivalent under the hard postconditions. M1 must encode acceptable uncertainty and expose a `needs_clarification`/reviewable outcome; m2 supplies role evidence; m4 applies only a sufficiently justified decision.

## I5 — Aesthetic or quality judgment

**Verdict: correctly-bounded.**

Aesthetics are outside both the sliver and this epic. They become correctness only when the user states a qualitative postcondition—match a reference style, remove visible banding, preserve legibility—or an artifact violates a functional threshold. Merely asking for an upscaler, sampler, or refinement pass does not make one aesthetically preferred setting a hard requirement.

Later quality work should be an optional evidence tier with explicit user criteria, repeated or seeded runs where stochasticity matters, feature-specific artifact checks, and human/reference/perceptual review where appropriate. A generic beauty score or golden-value identity must never gate additive-edit correctness.

## Missed boundaries

The sliver should add these explicit limits:

- **Target capability identity:** provenance lookup starts only after the request is mapped to a class or typed capability family. It does not solve compound-subgraph discovery or ambiguous labels. Broadening substring matchers remains forbidden.
- **Singular, versionless provenance:** graph-global `source_template`/`prior_path` cannot represent workflows composed from several templates, pasted subgraphs, or a source changed after emission. Limit “high confidence” to verified single-lineage graphs; the full solution needs per-region/node lineage and a content/version hash.
- **Unreadable or unsafe provenance:** breadcrumb resolution needs canonical allowed roots and distinct `missing`, `stale`, `outside_allowed_roots`, and `unparseable` outcomes. A failed provenance load must fall through without suppressing usable corpus precedents.
- **References are not values:** API inputs shaped as node/output references, asset/model paths, and list-valued literals must be typed separately. The sliver may extract an edge’s endpoint class/socket/role; m2/m4 must rebind IDs and validate socket compatibility. Source node IDs must never be copied.
- **Named-field authority:** without an authoritative schema, positional `widget_0` evidence is provisional. Schema-known extraction may be a strong prior; schema-less/raw extraction must be labeled low-confidence. This is why resolver unification cannot remain after evidence and construction.
- **Bounded “all instances”:** preserve all relevant same-type instances inside deterministic neighborhoods, across competing sources, with explicit truncation. Whole-workflow dumps can overflow fixer context while technically satisfying “all instances.”
- **Confidence and gating:** the sliver can ship heuristic roles and uncertainty triggers, but calibrated confidence and dependable risk gating require m1’s constraint taxonomy and m2’s role model. False certainty is a boundary, not an implementation detail.

None of these permits copying golden values. Only the restore oracle may require historical functional identity; fixer evidence remains general, typed, and provenance-tagged.

## Milestone ordering sanity-check

The semantic dependency chain is sound as **resolver precursor → m1 contract → m2 placement → m3 evidence → m4 construction → m6 runtime → m7 benchmark**. PLAN’s numbered placement of resolver unification at m5 is wrong. Named evidence cannot reliably distinguish literals from links without schema, and m4 explicitly needs resolved schemas. NORTHSTAR already calls resolver unification a precursor; `chain.yaml` should enforce that fact rather than leave it as prose.

Keep m1 first after the resolver: downstream planning and repair need a non-golden definition of success. Keep m2 before m3 so precedent roles bind to real target anchors instead of heuristics fabricating certainty. Keep m4 after both. Runtime belongs after candidates can land. M1 should build only the minimal validity-graded scaffold needed to develop the contract; m7 should remain the full restore/novel benchmark rebuild.

The sliver and m3 are **complementary, not redundant**. The sliver is an early down-payment: breadcrumb lookup, role-preserving payload plumbing, heuristic labels, tags, and conservative gating. M3 must consume—not reimplement—that work, replacing heuristic roles with m2 output, aligning constraints/priors with m1, handling lineage and fallback boundaries, and hardening the handoff. Finally, the current initiative chain tracks only m1–m4; resolver, runtime, and benchmark successor work must be explicitly tracked or the epic will appear complete while three boundary-resolving milestones remain outside it.
