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
- Extend that case through Apply/finalize and a follow-up submission: the
  structural fingerprint changes while workflow UUID, scope, session, and
  transcript remain; the follow-up reuses the original session; refresh
  restores the transcript and exact generation/lease.
- In that consecutive-turn case, leave turn 1's finalized receipt in browser
  persistence, return turn 2 as `candidate_ready` with zero transaction
  receipts, and run chat restore plus reconcile. Turn 2 must remain reviewable
  with Apply/Reject enabled, both turns visible, null generation/lease, and no
  interrupted-Apply/finalizing projection from turn 1.
- Exercise SD1.5 → SDXL semantic updates for `ckpt_name`, `width`, `height`,
  and `filename_prefix` against getter-only native node properties. All updates
  must land through native widgets, with unresolved fields and candidate/delta
  disagreement refusing before mutation.
- Exercise SD1.5 → img2img on a real KSampler whose serialized
  `control_after_generate` widget has no `inputs` descriptor. Updating `denoise`
  must resolve the named native carrier (without shifting to `scheduler`), and
  candidate/delta disagreement must fail in preflight with no canvas mutation,
  inverse delta, node disappearance, or whole-graph restore. Before Apply, the
  real preview must remain canonical-delta-derived and show both added nodes,
  the removed latent node, the rewire, and the denoise edit.
- In that same real img2img case, assert native `LoadImage` construction expands
  `image_upload` metadata to its auxiliary serialized carrier while the typed
  semantic postcondition still matches and finalizes. Also mutate the semantic
  filename to prove normalization does not hide a real workflow change. The
  successful native serialization must become the durable compatibility
  baseline, and an immediate follow-up submit must pass CAS without rebaseline.
  Capture the real JavaScript `post_apply_hash` from the finalize request and
  require Python to recompute the same digest; a Python-generated stand-in does
  not satisfy this acceptance case.
- For that exact img2img transaction, inject an exception and page-context loss
  after prepare at every boundary through the first native write (snapshot,
  semantic scoped read, Undo capture, adapter entry, and immediately after
  `mutation_started`). Assert durable checkpoint evidence, no stranded prepared
  lease, and a verified unchanged, restored, or finalized canvas.
- Drop the prepare response, hard-reload the tab, kill the renderer, and serve a
  different frontend build after prepare. Prove build attestation rejects stale
  code, the unchanged precondition can Resume Apply on the same generation and
  lease, an already-landed postcondition resumes finalize, and the lease
  watchdog prevents indefinite `prepared` state.
- Inject a same-workflow `/chat` 500 and prove messages remain visible with a
  retry path. Then prove a confirmed missing session clears only that workflow,
  legacy fingerprint-qualified keys migrate, and equal graphs under different
  workflow UUIDs remain isolated.
- Add stale-response, malformed/schema/projection failure, v1-key-wins,
  malformed legacy-key, and no-broad-key-search variants.
- Restart/switch the serving VibeComfy checkout while keeping the existing
  browser document alive. Prove stale ESM cannot Submit/Apply, the UI requires a
  real document reload, and the reloaded content-addressed build completes the
  same lifecycle.
- Fast-forward the runtime checkout without restarting and prove `/info` still
  reports the loaded startup commit/code digest. Then restart and require a new
  process-start id plus matching backend module path/digest before testing.
  Fail on multiple VibeComfy custom-node roots or ambiguous route winners.
- Run the native browser graph through the actually registered HTTP
  `/prepare` and `/finalize` routes—not mocked transports or direct session
  calls—and require the JavaScript claim to match Python verification. Assert
  the independent browser/Python parity suites are collected by required PR CI.
- Boot through ComfyUI's real absolute-path custom-node loader and fail if alias
  and canonical imports produce distinct module objects, globals, or locks.
- Attribute each failure/warning to VibeComfy, ComfyUI core, or extension; narrowly
  allowlist only known compatibility-environment warnings.
- Wire minimal correctness and the required lifecycle matrix into per-PR CI;
  schedule only the justified heavier compatibility subset.
- Produce machine-readable results with environment hashes, receipts,
  projections, serialized graphs, landed prefixes, recovery outcomes, and logs.
  Each conversation-lifecycle row records before/after workflow UUID, scope ID,
  fingerprint, session ID, binding-storage key, transcript count/digest,
  finalized generation/lease and its durable source, HTTP/action
  classification, and zero cross-workflow messages.

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
- No finalized composer notice appears, the finalized state does not add a chat
  message, and a follow-up preserves the prior transcript/session.
- Consecutive-turn rehydrate proves receipt ownership isolation: empty turn-2
  receipts cannot resurrect turn-1 `CANVAS_VERIFIED` state or hide the new
  candidate.
- The getter-only width case applies successfully through the widget carrier;
  fail-closed variants make zero native writes.
- The KSampler auxiliary-widget case applies `denoise` to the exact native
  carrier and records its carrier witness; its injected preflight failure rolls
  back only the lease with an empty landed prefix and unchanged canvas. Preview
  and Apply expose identical authoritative plan coverage for the full img2img
  mutation; no legacy preview fallback is accepted.
- The real LoadImage case records both server candidate serialization and native
  post-Apply serialization, proves only the UI-only upload carrier is excluded,
  and completes `canvas_verified` plus finalize without a false projection
  mismatch.
- Post-prepare fault injection proves the transaction supervisor always emits a
  terminal compensation/recovery receipt; recovery decisions use durable
  `preflight_complete`/`mutation_started` evidence plus typed pre/post
  projections, never volatile panel phase.
- The machine matrix validates its required identity/transcript/receipt-source
  schema and covers every rehydrate and migration classification above.
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
