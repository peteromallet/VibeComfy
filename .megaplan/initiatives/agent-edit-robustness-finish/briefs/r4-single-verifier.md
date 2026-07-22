# R4 — Single Apply and Rollback Verifier

## Outcome

Create `graph_apply_verifier.js` as the sole owner of transaction equivalence
and bounded mismatch evidence, and delete every inline competing decision.

## Input handoff

- R3 sole-owner adapter evidence contract and decisive incident evidence pack.
- M1 projection registry/goldens and versioned transaction contracts.

## IN

- Centralize precondition, landed-operation, postcondition, finalize, rollback,
  and mismatch comparison.
- Emit deterministic bounded projection diffs suitable for controller and
  recovery consumption.
- Delegate every projection field, identity, order, and hash rule to the registry.
- Route all existing comparisons through the verifier and delete copied helpers,
  inline verdicts, dead exports/imports, and compatibility branches.
- Inject mismatch, serialization exception, partial Apply, inverse failure, and
  compensation failure; pass all named incidents through one API.
- Ratify cross-runtime normalization for native-only host UI fields and
  equivalent zero-widget encodings. In particular, `showAdvanced` must be
  classified as non-semantic, and omitted, `null`, `[]`, and `{}` zero-widget
  representations must produce one structural projection in browser and Python.
- Replace raw ordinal `widgets_values` authority with a versioned semantic
  widget projection. Backend schema inputs remain semantic; frontend-injected
  carriers created from metadata such as core `LoadImage.image_upload` are
  `derived_native` and excluded in browser and Python. Do not solve this by
  teaching candidate synthesis to counterfeit a frontend-version-specific
  trailing `"image"` value.
- Reject a compatibility/session CAS digest as evidence for a typed
  transaction projection witness. Keep that digest only at an explicit,
  versioned compatibility boundary until its migration or retirement.
- For `delta_replay`, a matching typed postcondition and landed-plan receipt
  are the sole semantic finalize authority. Finalize must not run a second
  whole-candidate compatibility-hash equality gate; the actual native graph's
  compatibility digest may advance session CAS only after semantic success.
- Fail before native mutation when a semantic field cannot resolve to its
  native widget carrier, or when the candidate projection and typed delta do
  not describe the same field update. A getter-only layout property is not a
  workflow-field fallback.
- Treat the typed delta value as intent authority and the adapter's typed
  physical-carrier/landed receipt as execution evidence. The verifier must not
  independently infer widget indices from serialized input-descriptor ordinals
  or compare against a value obtained through that inference.
- Classify `preflight_failed` separately from partial native Apply. It requires
  zero landed operations and permits lease rollback only; any inverse/native or
  whole-graph canvas restoration is a verifier failure.
- Verify preview/apply planner parity as an authority property: both surfaces
  receive the same typed delta, projection versions, and native carrier map.
  A preview-side planner error is a typed blocker, never permission to infer a
  partial candidate through a legacy report fallback.

## OUT

Controller/API extraction, recovery product behavior, lifecycle matrix/CI,
terminal cleanup audit, UI redesign, or nested scopes.

## Locked decisions

- Adapter observes/mutates, registry defines projection meaning, verifier judges,
  and the later controller coordinates.
- Verifier never copies canonicalization; adapter never returns semantic success.
- Every post-prepare verifier failure retains reconciliation/rollback authority
  and structured evidence.

## Open questions for the planner

- Bounded diff representation for opaque extension-owned data.
- Whether proven native normalization needs a distinct repairable outcome; do
  not invent one without fixture evidence.

## Constraints

- Preserve exact projection versions and browser/Python parity.
- No free-text-only mismatch authority or second comparison owner.
- Preserve protected files and earlier gates.

## Done criteria

- Every Apply/finalize/rollback comparison calls the single verifier.
- Static/dependency tests prove no duplicate comparison/canonicalizer or dead
  verifier-era export remains.
- AST/import-call-graph ownership checks cover Python, JavaScript, and MJS;
  mutation tests inject renamed, aliased, method-based duplicate verifiers and
  canonicalizers and prove the gate fails.
- All fault exits and named fixtures pass the same public API.
- Browser/Python goldens prove native `showAdvanced` and every zero-widget
  encoding cannot create a false postcondition mismatch.
- Browser/Python and real-native goldens prove `LoadImage([filename])` and the
  frontend-materialized `LoadImage([filename, "image"])` have one semantic
  structural witness, while changing `filename` still changes that witness.
- Cross-runtime compatibility goldens compute the browser claim in JavaScript
  and verify it independently in Python for the same native graph. Tests that
  derive claimant and verifier evidence from one implementation are forbidden.
- Every mismatch receipt persists expected and actual projection versions and
  digests plus a deterministic bounded semantic diff; a generic browser-only
  mismatch string is insufficient recovery evidence.
- Hash-authority fixtures prove a compatibility/session CAS digest cannot
  satisfy a typed witness, and getter-only field fixtures fail closed before
  mutation when widget resolution is unavailable.
- A native graph whose typed postcondition matches but whose compatibility
  digest differs only by a derived UI carrier finalizes, persists that exact
  applied graph as the next CAS baseline, and accepts a follow-up submission.
- Auxiliary-widget fixtures prove descriptor/widget cardinality disagreement
  cannot shift semantic reads, and preflight fault injection proves zero canvas
  writes, zero inverse operations, and `canvas_was_mutated=false`. The exact
  img2img delta also proves preview/apply plan parity and complete node evidence.
- Focused verifier/ownership and broad browser, roundtrip, Python, and parity
  gates pass; two independent acceptances complete.

## Touchpoints

New verifier, roundtrip/lifecycle comparison paths, projection registry,
rollback helpers, diagnostics, static ownership tests, and fixtures.

## Anti-scope

No copied projection logic, adapter verdict, controller extraction, UI redesign,
generic framework, compatibility wrapper, or protected-file modification.

## Output handoff and proof artifacts

- Verifier implementation/public contract and versioned bounded-diff schema.
- Versioned hash-authority boundary, semantic-field consistency evidence, and
  preflight/no-mutation fault evidence.
- Complete verifier fault matrix and comparison-owner deletion audit consumed by R5/R6.

## Megaplan dial

Overall plan difficulty: **4/5**; profile: **partnered-4**; robustness: **full**;
depth: **high**; vendor: **claude** with active GLM 5.2; prep required. The
risk is a duplicate equivalence owner that passes narrow tests; inputs are frozen.

Prep direction: enumerate every comparison path and exceptional exit before centralizing it.
