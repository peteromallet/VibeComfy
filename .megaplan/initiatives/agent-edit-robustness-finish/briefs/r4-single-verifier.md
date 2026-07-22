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
- All fault exits and named fixtures pass the same public API.
- Browser/Python goldens prove native `showAdvanced` and every zero-widget
  encoding cannot create a false postcondition mismatch.
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
- Complete verifier fault matrix and comparison-owner deletion audit consumed by R5/R6.

## Megaplan dial

Overall plan difficulty: **4/5**; profile: **partnered-4**; robustness: **full**;
depth: **high**; vendor: **claude** with active GLM 5.2; prep required. The
risk is a duplicate equivalence owner that passes narrow tests; inputs are frozen.

Prep direction: enumerate every comparison path and exceptional exit before centralizing it.
