# R7 — Pinned Real ComfyUI Environments, Lifecycle Matrix, and CI

## Outcome

Build deterministic minimal and compatibility environments and enforce an
exhaustive real-ComfyUI lifecycle matrix in CI, with precise failure attribution,
so the fully composed runtime is proven before terminal cleanup/audit.

## Input handoff

- R3 native adapter and decisive incident evidence.
- R4 verifier fault/diff evidence.
- R5 controller/API and async-fence matrix.
- R6 recovery/Undo/legacy state matrix and crash/restart evidence.

## IN

- Build and pin a minimal ComfyUI correctness environment and a separate,
  representative custom-node compatibility environment.
- Pin ComfyUI/frontend/node-pack revisions, startup commands, fixtures, browser
  tooling, and artifact capture for deterministic reproduction.
- Exercise every supported transaction family through prepare, Apply, native
  serialization, verification, finalize, refresh, persistence, injected failure,
  inverse/compensation, rollback, recovery, and workflow switching.
- Include exact `a66422e…`, `eb45e…`, detached Displays/Labels, duplicate titles,
  dynamic nodes, converted widgets, reroutes, missing custom nodes, unsupported
  nested scopes, identical tabs, and refresh during each durable state.
- Include the recorded SD1.5 empty-canvas incident as a full submit → review →
  prepare → 7-native-node/9-link Apply → landed-plan audit → typed postcondition
  → finalize case. It must exercise native port-order divergence, `showAdvanced`,
  and zero-widget serialization; adapter-only replay is insufficient evidence.
- Restart/switch the serving VibeComfy checkout while keeping the existing
  browser document alive. Prove stale ESM cannot Submit/Apply, the UI requires a
  real document reload, and the reloaded content-addressed build completes the
  same lifecycle.
- Attribute each failure/warning to VibeComfy, ComfyUI core, or extension; narrowly
  allowlist only known compatibility-environment warnings.
- Wire minimal correctness and the required lifecycle matrix into per-PR CI;
  schedule only the justified heavier compatibility subset.
- Produce machine-readable results with environment hashes, receipts,
  projections, serialized graphs, landed prefixes, recovery outcomes, and logs.

## OUT

- Terminal duplicate/dead-owner cleanup, final proof-map completion, nine-point
  adversarial audit, or completion manifest; those are R8.
- Universal third-party compatibility or nested-scope implementation.

## Locked decisions

- Minimal-environment failures block release.
- Compatibility warnings are separately attributed; ambient console cleanliness
  is not correctness.
- Static scans cannot replace real composed behavior.
- Unsupported nested structures refuse before mutation.
- R7 must consume R6 recovery evidence, not test only happy paths.

## Open questions for the planner

- Smallest representative node-pack/version set justified by the corpus.
- Pinned supported ComfyUI/frontend version range.
- Exact per-PR versus scheduled compatibility budget while retaining full minimal correctness.

## Constraints

- Full named fixtures, not reductions; real native serialization, not mocks.
- Failure injection must preserve attribution and recovery evidence.
- Preserve protected files and all earlier architectural gates.

## Done criteria

- Pinned environments reproduce from clean state with recorded hashes.
- Every supported transaction family passes success, failure, refresh, switch,
  rollback, recovery, and persistence in minimal real ComfyUI.
- Every named incident/adversarial fixture passes in full form.
- The SD1.5 case finalizes from an empty real canvas, and injected link,
  projection, and rollback failures leave durable step-level receipts.
- Compatibility matrix is deterministic, representative, and precisely attributed.
- CI blocks on minimal correctness and required lifecycle failures; scheduled
  compatibility jobs retain artifacts and clear ownership.
- Two independent acceptances verify the matrix is composed, not mock/wrapper evidence.

## Touchpoints

ComfyUI launchers/checkouts, Playwright/E2E, CI workflows, fixtures, compatibility
ledger, artifact storage, failure attribution, and lifecycle/recovery harnesses.

## Anti-scope

No universal compatibility promise, terminal audit shortcut, nested support,
console-clean proxy, broad warning allowlist, reduced fixture, mocked native
serialization, or protected-file change.

## Output handoff and proof artifacts

- Pinned correctness/compatibility environment definitions and hashes.
- `r7-real-comfy-lifecycle-matrix.json` covering the exhaustive composed runtime.
- Compatibility attribution ledger and CI job/artifact map.
- Acceptance explicitly handed to R8; R8 cannot proceed without this matrix and
  R6 recovery evidence.

## Megaplan dial

Overall plan difficulty: **4/5**; profile: **partnered-4**; robustness: **full**;
depth: **high**; vendor: **claude** with active GLM 5.2; prep required. The
planning risk is an environment or scenario gap that hides composed runtime
failure; the architectural owners are already established.

Prep direction: inventory launchers, versions, extension noise, fixtures,
lifecycle/recovery coverage, attribution, CI topology, and reproducibility gaps.
