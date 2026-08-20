# VibeComfy structural cleanup master plan

Status: **planning only — do not execute yet**<br>
Prepared: 2026-08-20<br>
Intended branch family: `desloppify/*`
Primary audience: a competent programmer who knows Python and JavaScript but does not already know VibeComfy's architecture.

## 1. Outcome

Clean the codebase without changing VibeComfy's user-visible behavior, persisted session formats, workflow semantics, or public extension/API surfaces.

The desired end state is not merely “smaller files.” It is a codebase where:

- each important concept has one named owner;
- dependencies point from neutral domain code toward adapters, not back toward UI or HTTP modules;
- `VibeWorkflow` is the canonical graph representation between ingest and projection;
- backend transaction authority is explicit and recoverable;
- frontend state transitions, network effects, and DOM rendering are separate concerns;
- executor orchestration is headless and reaches ComfyUI through injected ports;
- compatibility façades are small, labelled, tested, and scheduled for retirement;
- generated, vendor-like, fixture, cache, and authored code are classified correctly;
- tests protect behavior and contracts instead of preserving accidental file structure;
- Desloppify's strict score improves honestly after the implementation queue is completed and rescanned.

This document is an execution plan. It does **not** authorize implementation, commits, deletion, migration, or a Desloppify rescan.

### 1.1 End-state in plain language

The finished codebase should feel like a set of understandable systems connected through explicit contracts, not a collection of large files connected through historical imports and compatibility accidents.

#### To a contributor

A programmer should be able to answer these questions quickly:

- Where is the canonical workflow graph? `VibeWorkflow`.
- Where are graph edits made? One edit-session/edit-gateway boundary.
- Where is a session transaction decided? One transaction application service over an authoritative lifecycle log.
- Where is an HTTP route implemented? A thin transport handler calling an application service.
- Where is executor behavior orchestrated? A small headless phase orchestrator using injected host ports.
- Where is frontend state changed? One event/lifecycle store.
- Where is UI rendered? Pure view-model and DOM/canvas render modules that do not normalize transport payloads or make network decisions.
- Where do node schemas and widget names come from? One canonical `NodeSchema` type, a reused provider, and one documented widget-resolution result/precedence.
- Why does a shim still exist? Its ledger row names the consumer, owner, test, and removal condition.

#### Backend end-state

- `session.py`, `routes.py`, `edit.py`, provider, and contract modules are small public façades or cohesive owners, not mixed application monoliths.
- Session primitives, durable artifacts, transaction application, turn transitions, validation, and public projections have one-way dependencies.
- The append-only lifecycle log is the named transaction authority; indexes and receipt snapshots are rebuildable projections.
- Route modules parse/serialize HTTP and delegate to independently testable application services.
- Provider/runtime configuration, credentials, readiness, errors, and model-attempt evidence have neutral owners instead of parallel policies.
- Batch editing receives explicit typed capabilities instead of a large globals-based namespace.

#### Executor end-state

- `run_executor` remains the public entry point, but classify, research, implement, and reply are typed phases.
- Executor core imports no ComfyUI route, UI-owned agent module, provider credential loader, or browser contract.
- Session context, phase events, model calls, and host behavior arrive through explicit ports bound by the ComfyUI adapter.
- Failures have one neutral vocabulary and explicit mappings at provider, executor, route, and frontend boundaries.

#### Frontend end-state

- `roundtrip_extension.js` registers the extension; the roundtrip shell only composes capabilities and preserves deliberate public exports.
- Transport normalization, lifecycle transitions, flow effects, graph adapters, selectors, and renderers are separate.
- There is one canonical transcript/detail/transaction state; legacy mirrors survive only behind a documented compatibility projection.
- Submit/apply/reject/rebaseline flows emit events and obligations rather than directly mutating arbitrary panel state and DOM.
- Global listeners and host prototype wrappers have idempotent install/uninstall ownership.
- Preview rendering has one deliberate product contract, with code, tests, and docs agreeing on canvas/DOM behavior.

#### Graph, schema, and porting end-state

- Named ingest produces one retained `VibeWorkflow`; API and UI JSON are boundary projections, not alternate authorities.
- Furniture/editor evidence has an explicit carrier and loss model instead of leaking into several representations unnoticed.
- Reorganise facts, topology, ownership, local/global placement, collision policy, metrics, and hashes are cohesive compiler stages behind a stable façade.
- The UI emitter orchestrates identity, links/sockets, widgets, evidence, layout reconciliation, refusals, and validation through dedicated modules.
- Layout code never imports emitter internals.
- Hash families stay semantically distinct and are named by what they measure.
- Known-schema socket mistakes fail closed with evidence; schema-less best effort is explicit.

#### Shim and generated-code end-state

- There are zero unclassified shims.
- Remaining shims are either supported public façades, intentional host/optional-dependency boundaries, time-bounded migration bridges, or generator-owned outputs.
- No compatibility façade owns hidden domain behavior.
- Generated Python/JavaScript outputs are changed through deterministic generators and freshness/parity gates, never hand-edited.

#### Testing and delivery end-state

- Each module/package has fast focused tests, each subsystem has an adjacent shard, and broad/full suites run only at integration seams.
- Import, persisted-format, generated-parity, served-code, browser-state, and performance boundaries have explicit gates.
- Every cleanup package has an independent review and completion receipt.
- Desloppify reports the finished state only after the queue completes; strict-score improvement reflects actual architecture, not exclusions or wontfix bookkeeping.

### 1.2 Difficulty legend

- Untagged packages may still be hard, but they are bounded enough for a normal implementation agent with the package card, focused tests, and independent review.
- **`[XHARD]`** marks extremely hard work involving subtle multi-step reasoning, cross-layer authority, compatibility/persistence risk, or write-heavy changes where local correctness is not enough.
- `[XHARD]` work should be owned by a GPT-5.6 Sol manager/validator. It should delegate bounded inventory, mechanical edits, and critique to cheaper agents where useful, but retain architectural judgment and validate the integrated result.
- Every `[XHARD]` task requires the high-risk review path in §15.10 and a chunk/oracle gate before dependent work starts.
- A large file is not automatically `[XHARD]`; difficulty comes from semantic coupling and blast radius.

## 2. How to use this plan

### 2.1 Read this before starting any package

1. Read the package's goal, prerequisites, scope, non-goals, steps, gates, and rollback notes.
2. Confirm that every prerequisite package is complete.
3. Re-check the named files because line numbers and working-tree state may have changed.
4. Run the package's baseline tests before editing.
5. If a baseline test already fails, record the failure and classify it before making changes.
6. Implement only the package in progress.
7. Run focused tests, then adjacent tests, then static checks.
8. Commit one coherent package at a time when commit authorization exists.

### 2.2 Package sizing

Packages are intended to take roughly half a day to two working days. If a package cannot be explained in one sentence, reviewed as one conceptual change, or rolled back independently, split it before implementation.

Parent IDs that describe several slices are planning epics, not executable packages. Before execution, assign suffix IDs such as `F44a`, `F44b`, and `F44c`. Every suffix needs its own allowed files, prerequisites, exact tests, acceptance gates, rollback, and estimate of no more than two days.

### 2.3 Terms used below

- **Authority**: the one representation or module whose value is treated as correct.
- **Projection**: a derived representation produced from an authority, such as UI JSON produced from `VibeWorkflow`.
- **Façade**: a compatibility module that preserves old imports or function signatures while delegating to newer modules.
- **Port**: an injected interface used by neutral code to call host-specific behavior.
- **Characterization test**: a test that records current behavior before internals move.
- **Fresh-process test**: a subprocess test used to expose import order, module-global state, or environment side effects.
- **Migration seam**: temporary compatibility code with an explicit removal condition.
- **CAS (compare-and-swap)**: accept a write only if the expected prior identity still matches.
- **IR (intermediate representation)**: `VibeWorkflow`, the canonical in-memory graph between import and projection.
- **Rehydrate**: rebuild frontend/session state from durable backend data.
- **Furniture evidence**: editor-only layout information such as positions, sizes, groups, reroutes, and viewport state.
- **Object-info**: ComfyUI node schema metadata used to resolve inputs, outputs, and widgets.
- **V1/V2**: legacy and current persisted transaction/session contract generations; both remain readable during cleanup.

## 3. Starting state and constraints

### 3.1 Important current hotspots

The following sizes are orientation signals, not proof that a file is badly designed:

| File | Approximate current size | Main concern |
|---|---:|---|
| `vibecomfy/comfy_nodes/web/vibecomfy_roundtrip.js` | 9,912 lines | UI composition, session recovery, submit/apply orchestration, graph integration, and rendering remain mixed |
| `vibecomfy/porting/reorganise/compile.py` | 7,232 lines | Multiple compiler phases remain in one module after placement extraction |
| `vibecomfy/comfy_nodes/agent/session.py` | 4,544 lines | Compatibility façade still owns major lifecycle behavior despite the integrated lock/storage/journal/thread extraction foundations |
| `vibecomfy/comfy_nodes/web/agent_edit_lifecycle.js` | 3,954 lines | State authority and projection complexity |
| `vibecomfy/porting/emit/ui.py` | 4,301 lines | Schema resolution, layout reconciliation, node/link emission, and refusal evidence are mixed |
| `vibecomfy/comfy_nodes/agent/contracts.py` | 2,745 lines | Several contract families and public projections share one module |
| `vibecomfy/comfy_nodes/web/panel_thread.js` | 2,522 lines | Thread projection and rendering responsibilities need classification |
| `vibecomfy/executor/core.py` | 3,056 lines | Phase orchestration plus compatibility and host fallbacks |
| `vibecomfy/executor/contracts.py` | 2,612 lines | Multiple cross-layer contract families |
| `vibecomfy/comfy_nodes/agent/routes.py` | 2,261 lines | HTTP registration, request parsing, services, fixtures, and settings mixed |
| `vibecomfy/comfy_nodes/agent/edit_batch_repl.py` | 2,214 lines | Explicit module now exists, but still receives a very wide implicit dependency container |
| `vibecomfy/comfy_nodes/agent/provider.py` | 2,057 lines | Prompting, route policy, dispatch, readiness, and credential persistence mixed |

Large `vibecomfy/nodes/*.py` files must be classified as generated, mirrored, declarative, or authored before they enter the cleanup queue. Do not refactor them merely because they are large.

### 3.2 Improvements already present

Do not repeat work that is already complete:

- session locks, storage, and transaction-journal code have private modules;
- agentic replay filesystem/service code has been extracted from routes;
- executor host ports and a ComfyUI adapter boundary exist;
- the edit façade imports real `_frag_*` modules; the old runtime source-string assembly is gone;
- repeated edit-batch helpers were consolidated;
- roundtrip extension registration has been extracted;
- frontend diagnostics, watchdog maps, and render gateways are consumer-scoped;
- reorganise placement logic has a private module;
- patch application and telemetry have idempotency coverage;
- workflow conversion copies caller-owned graph and raw evidence at its boundary.

These are foundations, not completion receipts. Several still depend back on their old façade and therefore need a second-stage dependency cleanup rather than another blind extraction. The integrated replay below records exactly which claims are current, partial, blocked, or resolved.

### 3.3 Non-negotiable compatibility constraints

- Existing V1 and V2 persisted sessions remain readable.
- Lifecycle logs remain authoritative if that is the current contract; indexes and receipt snapshots must not silently become authorities.
- Existing HTTP paths and response field names remain stable unless a separate migration is approved.
- `edit.py`'s frozen public surface remains available during migration.
- `run_executor` remains the executor's public orchestration entry point.
- Headless imports must not begin importing ComfyUI, route registration, provider credentials, or browser-owned modules.
- Graph edits must not mutate caller-owned workflow or raw UI evidence accidentally.
- Local imports that preserve headless operation or monkeypatch behavior must not be removed without replacement tests.
- Current user work and concurrent untracked files must not be overwritten or folded into cleanup commits accidentally.

### 3.4 Current execution status: STOP

Do not start cleanup in the present checkout.

At plan-writing time, `desloppify/worst-offenders` contains dozens of modified and untracked paths overlapping session, routes, executor, frontend, graph, tests, and active architecture documents. There are also other worktrees and concurrent processes. This is active integration state, not disposable cleanup residue.

Before execution is authorized:

1. Select an approved base commit containing the work that should be cleaned.
2. Create or designate a dedicated cleanup branch/worktree.
3. Capture the current branch, HEAD, `git status --porcelain=v2`, tracked diff, untracked-path manifest and hashes, worktree list, branch refs, Desloppify state, and active plan/lock ownership.
4. Classify every dirty path using `P00`.
5. Obtain an explicit landing decision for the uncommitted swarm extractions and active migration documents.
6. Start each implementation package from a clean status; do not use reset, clean, stash deletion, or worktree deletion to manufacture cleanliness.

The plan file itself may be reviewed and revised in the current tree. Production cleanup may not begin here until this stop condition is cleared.

### 3.5 PR154/PR156/local-replay preservation and integration receipts

This reconciliation is planning evidence only. It does not authorize cleanup, deletion, reset, stash, commit, migration, or a Desloppify rescan.

| Receipt | Preservation fact |
|---|---|
| `4abeb90d` | Preserved the pre-PR154 local structural-work checkpoint. |
| `654373b7` | Preserved the intermediate PR154/local-integration checkpoint. |
| `368a332a` | PR156 code head before its CI-only follow-up: canonical accessors for edit-IR retained data. |
| `25f12eea` | Current PR156 remote tip; exports the configured Python interpreter into `browser-smoke`. |
| `49dd66d4` | Integrated PR156 code head `368a332a` with the local structural replay. |
| `1136f7cb` | Test correction aligning runtime expectations with integrated defaults. |
| `25260147` | Closed replay-schema, compact-prompt, and typed empty-worker-response contract gaps found by adjacent verification. |
| `58727689` | Local replay CI correction: includes upstream's later `browser-smoke` interpreter export plus the same protection for standalone `browser-contracts`. |
| `9eca3ed1` | Initial post-PR156 cleanup-plan reconciliation submitted to independent CR-0A review. |
| `cf29bd1a` | Corrected CR-0A's runtime-contract and dependency-gate findings; 2 sensitive nodeids and all 45 runtime-adapter tests passed, Markdown links passed, and `git diff --check` was clean. |
| `CR-0A: continue` | Independent GPT-5.6 Sol reviewer accepted the corrected reconciliation; the reviewer did not implement, manage, or verify the integration. |
| `d30c5d59` | Merged current PR156 tip `25f12eea` into the local integration branch; pre/post tree hashes were identical because `58727689` already contained the upstream hunk. |
| `CR-0A latest-head recheck: continue` | The same independent Sol reviewer confirmed exact ancestry, tree identity, receipts, and targeted browser evidence after the PR tip advanced. |
| Final integration location | Branch `integrate/pr156-local-cleanup-20260820`, worktree `/private/tmp/vibecomfy-pr156-local-integration`. |
| Live tree | Original live worktree `/Users/peteromalley/Documents/reigh-workspace/vibecomfy` is preserved unchanged. |

The final branch/worktree is not yet an approved cleanup base: P00 remains blocking because six other dirty worktree payloads and one active test worktree still require ownership/landing decisions. The `session.py` PR156 conflict is resolved and its focused integration tests pass, but this does not complete B33–B35 because the façade and reverse dependencies remain. The preservation chain is evidence that work was not discarded; it is not evidence that any cleanup package is done.

#### Integrated verification receipts

| Area | Evidence | Result and disposition |
|---|---|---|
| PR156 follow-up preservation | Virtual-wire, pipeline readiness/recovery, compatibility seams, typed edit COW, canonical retained access | All six PR156 fixes present after local replay; virtual-wire 3 passed, typed edit COW 9 passed, readiness/materialization 3 passed |
| Session and pipeline conflict | Session/pipeline plus virtual-wire/pipeline focused shards | 73 passed, then 15 passed; no unresolved conflict remains |
| Backend/executor integration | Threaded, contracts, flows, profiles, host boundary, routes, session, runtime-adapter shards | 509 passed/6 contract gaps; the six exact failures were fixed without weakening tests, then 6 exact nodeids plus affected 9/201/45/19-test shards passed |
| Frontend integration | Lifecycle/canonical/response/parity; migration/M1/ownership/dependency; smoke/pipeline/graph projection | 441 passed; 65 passed; 275 passed with 2 skipped; browser contracts 576 passed; final `make browser-smoke` 1,653 passed/2 skipped/0 failed |
| PR156 CI reproduction | `m1_contracts.test.mjs` with configured and missing Python | Reproduced `null !== 0` only with missing interpreter; Makefile now exports `VIBECOMFY_PYTHON="$(PYTHON)"`; exact 17, browser-contract 576, and final browser-smoke 1,653 passed/2 skipped/0 failed |
| Reorganise/patch integration | Focused/golden reorganise plus ControlNet/patch suites | 191 passed |
| Graph/IR baseline | Workflow/convert/virtual-wire and IR-law/boundary/edit shards | 104 passed/4 failed/3 skipped and 94 passed/9 failed. Two failures require an absent external corpus fixture; the remaining bypass/static-boundary/inverse/legacy-envelope/undo failures are P03 evidence for G54/G58/G60/G63, not silently accepted completion |
| Documentation paths | `tools.check_markdown_links` | Passed on the integrated tree; anchor validation remains a separate prerequisite |

### 3.6 Integrated replay reconciliation ledger

Status vocabulary: **resolved** means the stated package behavior is evidenced and no material follow-up remains; **current** means the architectural decision or classification is valid but implementation work remains; **partial** means a bounded slice landed while the package goal remains open; **blocked** means prerequisites or a fail-closed gate prevent safe continuation; **superseded** means the original plan statement is replaced by the current contract; **new prerequisite** means this package must be added before mutation.

| Package | Status | Current evidence | Remaining goal or blocker |
|---|---|---|---|
| `P00` | blocked | Integrated branch/worktree receipts above; six dirty worktree payloads plus one active test worktree remain outside an ownership ledger. | Assign owner/landing decision to every dirty path and choose a clean execution worktree. |
| `P00A` | accepted by `CR-0A`, including latest-head recheck | Checkpoint, intermediate, current PR156 tip, tree-identical ancestry merge, local replay, correction, CI, conflict, verification receipts, and both independent `continue` verdicts are recorded above. | P00 still separately blocks on the six dirty payloads and active test worktree; P01–P03 require completed P00 as well as this acceptance. |
| `A25` | partial | `contracts.py`, `_frag_response_contract.py`, generated JS, `tools/generate_agent_contract_js.py`, `tests/test_agent_contract_codegen.py`, browser response/canonical-delta tests. | Freeze one matrix covering Python/JS fields, `accepted_batch`, mode, paid submit, virtual-wire sidecar, fixtures, and legacy projections; pair with B38/F42. |
| `A26` | partial | `comfy_adapter.js`, `intent_graph_adapter.js`, projection registry, graph projection, ownership tests. | Freeze canonical IR/raw UI/furniture/sidecar/refusal ownership; shell and emitter still duplicate graph semantics. |
| `B33` | partial | `_session_storage.py` and `_session_transaction_journal.py` exist; storage tests cover persistence. | Remove implementation imports back into `session.py` (including `structural_graph_hash` and journal `session as host`) while preserving façade names. |
| `B34` | partial/blocked | Transaction storage/backend-spine tests and journal/artifact helpers exist. | Prove lifecycle log authority, rebuildable receipts/indexes, independent transaction service, and recovery/corruption policy. |
| `B35` | partial/blocked | Allocation/idempotency/CAS behavior is covered through session/backend-spine tests. | Extract typed transition service and complete concurrency/replay matrix; depends on B34. |
| `B36` | partial | `_agentic_replay_service.py` and replay route tests prove one bounded extraction; `routes.py` remains 2,261 lines. | Split registration/common parsing and remaining submit/chat/actions/demo/nodepack/settings/research/rating families. |
| `B37` | blocked | `edit_batch_repl.py` still resolves a 71-name `EditBatchReplDeps` surface; dependency test characterizes it. | Replace globals-derived namespace with typed capabilities; retain compatibility builder until all callers migrate. |
| `B38` | partial | Contract aliases/reexports and generated response compatibility remain covered; `contracts.py` remains monolithic. | Split semantic contract families without changing wire fields; coordinate with F42/A25. |
| `B39` | blocked | Session/routes/contracts/edit/provider façades remain substantial. | Complete public/temp/dead wrapper audit; deletion belongs to S71–S75 only after owners and receipts exist. |
| `F42` | partial | Generated JS freshness and canonical `accepted_batch`/delta tests exist. | Remove duplicate normalization and add served-code plus full cross-layer compatibility proof. |
| `F43` | partial | Lifecycle has canonical compartments and rehydrate/idempotency tests. | Collapse `chatMessages`/`turns`/`history` mirrors behind one projection with explicit removal conditions. |
| `F44` | partial/blocked | Lifecycle race/recovery fixes landed; `agent_edit_lifecycle.js` remains monolithic. | Split scope/chat/candidate/transaction/submit domains; transaction slice waits for B34/B35. |
| `F45` | partial | Submit-flow/dependency factories landed; apply/rebaseline still carry wide dependency lists. | Introduce typed capability bundles for submit/apply/reject/rebaseline. |
| `F46` | partial/blocked | Adapter/projection ownership tests exist; `vibecomfy_roundtrip.js` remains 9,912 lines with graph algorithms. | Move dynamic IO/link/field/target/mutation semantics behind A26/G58/G60 gates. |
| `F47` | partial | `roundtrip_extension.js`, diagnostics/watchdog factories, dependency-isolation tests. | Centralize global side-effect managers with idempotent install/uninstall. |
| `F48` | partial/blocked | Closure/ownership tests exist; no complete wrapper ledger or served browser proof. | Classify every shell export and prove served open→submit→apply/reject/rebaseline before S76. |
| `G50` | current/blocked | UI → `GraphInventoryFacts` → `LayoutPlanV1` → patch exists in reorganise modules/tests. | Make D05 furniture-carrier/loss-model decision before long-term IR authority or deletion. |
| `G51` | partial | `canonical_coords.py` and emitter rounding intentionally differ and have tests. | Remove layout imports of emitter helpers; preserve separate snap vs emitted-round semantics. |
| `G52` | blocked | `NodeSchema` is duplicated in `schema/types.py` and `schema/provider.py`. | Establish one runtime type identity and provider reexport before schema consumers move. |
| `G53` | partial | `WidgetNameResolution` precedence is implemented/tested in `compact_resolver.py`. | Decide curated `WIDGET_SCHEMA` authority and add confidence/refusal evidence to the result. |
| `G54` | partial | Graph-facts/furniture and normal-ingest tests exist. | Add explicit side-by-side characterization and loss model. |
| `G55` | partial | Structural/topology/plan hash helpers and deterministic tests exist. | Add named semantic hash ledger (including furniture/layout distinction) without silently changing identity. |
| `G56` | partial | `_placement.py` extracts bounded placement/topology helpers. | Extract remaining compiler topology/ownership phases with golden/determinism/monkeypatch proof. |
| `G57` | partial | Local placement extraction landed. | Separate wall/global placement and collision repair/metrics from compiler. |
| `G58a` | partial | Identity/remapping helpers and emitter tests exist. | Finish behavior-preserving identity extraction; defer edge/socket/reroute/broadcast/dynamic-port semantics. |
| `G58b` | blocked | Edge/socket/reroute/broadcast/dynamic-port logic remains in emitter. | Wait for G60 known-schema fail-closed proof and MIG-G1/MIG-G2 receipts. |
| `G59` | blocked | Emitter still combines widgets, evidence, layout, validation, and refusal. | Split only after G53/G58b/A26; preserve golden UI/API/refusal behavior. |
| `G60` | blocked | `emit/ui.py:_resolve_output_slot_and_type` still returns slot 0/empty type for unresolved names. | Add known-schema missing-output refusal; retain slot-0 best effort only for schema-less nodes. |
| `G61` | current/partial | Generated headers, shim generator, and node-shim tests exist. | Keep source-of-truth classification; generator `--check`/output-dir/regeneration gate remains S77. |
| `G62` | current/partial | Reorganise and porting/layout engines remain distinct. | Characterize their intentional differences and prevent accidental authority merging. |
| `G63` | blocked | No MIG-G1/MIG-G2/MIG-G3 receipt artifacts; migration docs are plans. | Produce explicit receipts before deleting raw UI/furniture/browser/Python/edit compatibility paths. |
| `E60` | partial | Typed `ExecutorHostPorts`, phase result contracts, and host-boundary tests exist. | Isolate typed inputs/outputs for each phase; core remains a phase monolith. |
| `E61` | partial | Fresh-process/injected host-boundary tests exist. | Remove `_default_host_ports`/compatibility loading only after port replacement proof. |
| `E62` | partial | `agent_research_stage.py`, shadow/evidence tests, Hivemind adapters. | Finish typed classify/research handoff with retry/redaction/shadow evidence. |
| `E63` | blocked | Implement/reply remain `_run_implement`/`_run_reply` in `executor/core.py`. | Extract durable implement/reply phases after B34/E60/E61 while retaining `run_executor` as sole public entry. |
| `E64` | partial | Host/config compatibility adapters remain in core. | Complete façade/config ownership and cache/import audit. |
| Markdown-link gate | resolved path gate / new anchor prerequisite | `tools/check_markdown_links.py`, Makefile docs target, and historical repairs in `fb2c0b19`, `bced7477`, `a0d441f3`, `31eb1408`; current path checker passes. | Checker validates target paths only, not `#L...` anchors. Add an anchor audit/validator before treating docs hygiene as complete. |
| Stale hotspot/count snapshot | superseded | The pre-replay line-count table was replaced with the measured checkpoint counts above. | Refresh counts only at a new approved base; never use line-count drift as a cleanup authorization. |

### 3.7 Cross-layer compatibility gates

These gates are part of A25/A26 and must be cited by B38, F42, F46, G58/G60/G63, E60/E63, and the relevant shim packages.

1. **Accepted batch authority.** `accepted_batch` is the sole durable edit authority. `delta_ops_envelope`/`delta_ops` are derived legacy serializers only; no validator, reducer, or transaction service may consult them as authority. Preserve the serializer until MIG-G2/S74 and prove Python, generated JS, browser, and persisted-fixture parity.
2. **Pipeline mode (`pipeline_mode`).** `staged` and `threaded` are canonical. `full` and `two_step` are ingress aliases only. Resolve once at `run_executor`; readiness, recovery, submit body, and response metadata must agree. Staged may omit mode for wire compatibility; threaded reports `report.executor.orchestration_mode`. No mode branch belongs below orchestration.
3. **Paid-submit confirmation (`paid_submit`).** `vibecomfy_roundtrip.js` must confirm provider cost before the first paid submit, always confirm welcome-example prompts, persist acknowledgement only through delegated `_lsGet`/`_lsSet`, ask again if storage is unavailable, and leave draft state untouched on cancel. Add dedicated browser tests before F45/F47/F48 completion.
4. **Virtual-wire sidecar.** Conversion captures virtual wires before copying caller data, publishes `metadata["virtual_wires"]` only after successful conversion, and never mutates caller metadata on failure. The sidecar is derived editor evidence, not graph authority. Preserve `tests/test_virtual_wire_round_trip.py` and agent-edit safety coverage through G50/G58/G63.

### 3.8 Corrected plan assertions

- “Extracted session storage/journal” means a partial foundation until those modules stop importing `session.py` for implementation helpers.
- “Layout never imports emitter” is not currently true; layout sizing/placement and executor layout hints still use emitter helpers.
- “One canonical `NodeSchema`” is not currently true; provider and `schema/types.py` define duplicate classes.
- “Known-schema socket mistakes fail closed” is not currently true; unresolved named outputs still have slot-0 fallback in `emit/ui.py`.
- “MIG-G1/MIG-G2/MIG-G3” are required receipts, not claims implied by migration documents; none is present in this integration tree.

## 4. Architectural laws

Every implementation package must preserve these laws.

### Law 1 — One owner per concept

Hashes, state names, route aliases, failure kinds, provider errors, transaction events, and public response fields each need one canonical definition. Other modules may adapt or re-export; they must not independently redefine them.

### Law 2 — Dependencies point toward adapters

Preferred backend direction:

```text
neutral primitives and contracts
    -> provider/runtime adapters
    -> agent application services
    -> HTTP handlers
    -> ComfyUI route registration
```

Preferred executor direction:

```text
executor contracts and phase orchestration
    -> injected ExecutorHostPorts
    -> ComfyUI executor adapter
```

Preferred graph direction:

```text
source evidence
    -> ingest
    -> VibeWorkflow
    -> validated transformation/layout plan
    -> API or UI projection
```

Preferred frontend direction:

```text
transport payload
    -> contract normalization
    -> lifecycle transition
    -> view model
    -> DOM/canvas render
```

Arrows above describe runtime/data flow. Import dependencies should point toward lower-level primitives and contracts: high-level consumers import lower-level modules, while neutral modules never import their HTTP, browser, or ComfyUI consumers.

### Law 3 — Derived files are not authorities

Receipt snapshots, indexes, cached object-info payloads, view models, and rendered graphs are derived. Every derived form needs a named source and a rebuild or invalidation rule.

### Law 4 — Compatibility is explicit and temporary

Every façade wrapper added during cleanup must state:

- which old import/signature it preserves;
- which new implementation owns the behavior;
- which tests protect compatibility;
- when the wrapper can be removed.

### Law 5 — Split by responsibility, not line count

A split is successful only when the new module has a coherent responsibility, a smaller dependency set, and independent tests. Moving code into a new file while importing the old façade back from every function is a migration step, not the final architecture.

### Law 6 — Behavior gates precede movement

Characterize public behavior, import boundaries, persisted data, and monkeypatch seams before moving implementations.

## 5. Program map

The cleanup is divided into dependency-ordered waves.

| Wave | Purpose | Packages |
|---|---|---|
| 0 | Preserve and measure | `P00`–`P03`, with `[XHARD] P00A` reconciliation freeze |
| 1 | Repair known correctness/performance debt | `C10`–`C13` |
| 2 | Define cross-cutting authority | `A20`–`A26` |
| 3 | Remove backend dependency inversions | `B30`–`B39` |
| 4 | Decompose frontend state/effects/rendering | `F40`–`F48` |
| 5 | Clarify graph, porting, schema, and layout pipeline | `G50`–`G63` |
| 6 | Finish executor and contract boundaries | `E60`–`E64` |
| 7 | Retire shims and repair tests, imports, zones, and stale documentation | `S70`–`S78`, `T70`–`T75` |
| 8 | Resolve the queue and rescan | `R80`–`R82` |

The package identifiers are stable references. If a package is split later, use suffixes such as `B34a` and `B34b`.

### 5.1 XHARD dispatch index

The plan contains **23 `[XHARD]` execution units**. This index is the dispatch and review overlay; the package cards remain authoritative for scope, prerequisites, tests, and acceptance. `[XHARD-REVIEW]` is a separate label for integration reviews that require big-picture architectural judgment; it does not turn bounded package diff review or ordinary verifier runs into XHARD work.

| Unit | Why it is XHARD | Required ownership | Required decision/review gate |
|---|---|---|---|
| `P00A` | Reconciles preserved PR154/PR156 work with local structural replay without losing ownership, provenance, or unresolved conflict state | GPT-5.6 Sol manager/validator independent of the integration implementer | `[XHARD-REVIEW] CR-0A`; receipts, dirty-path ledger, compatibility/authority ledger, and clean-base decision |
| `A25` | Freezes a generated Python/JavaScript wire contract while both runtimes and persisted payloads must remain in parity | GPT-5.6 Sol manager/validator; delegate inventories and parity checks | `CR-2`; generated freshness and cross-language parity evidence |
| `A26` | Defines the browser/graph projection boundary across canonical IR, raw UI evidence, furniture, and lossy projections | GPT-5.6 Sol manager/validator with graph and frontend reviewers | `CR-2`, then re-check at `CR-5` |
| `B34` | Makes the append-only lifecycle log executable transaction authority without losing recovery or V1/V2 readability | GPT-5.6 Sol manager/validator with persistence reviewer | `CR-3`; persistence fixtures, replay, rollback, and recovery proof |
| `B35` | Separates turn allocation and state transitions under concurrency while preserving durable ordering | GPT-5.6 Sol manager/validator with concurrency reviewer | `CR-3`; transition matrix and concurrent/replay tests |
| `B37` | Replaces a wide, implicit batch-REPL host namespace without breaking dynamic capabilities or monkeypatch seams | GPT-5.6 Sol manager/validator; delegate capability census and mechanical plumbing | `CR-3`; frozen-surface and explicit-capability proof |
| `B38` | Splits several public contract families that are imported across backend, executor, routes, tests, and frontend generation | GPT-5.6 Sol manager/validator paired with `F42` | `CR-3`; import, re-export, generated, and wire compatibility proof |
| `F42` | Makes generated selectors/contracts authoritative across Python and served JavaScript without creating a second source of truth | GPT-5.6 Sol manager/validator paired with `B38` | `CR-2` and `CR-4`; generator freshness and served-code proof |
| `F43` | Collapses transcript/detail compatibility mirrors into one state authority while preserving hydration and recovery | GPT-5.6 Sol manager/validator with frontend-state reviewer | `CR-4`; two-consumer, rehydrate, and legacy-projection evidence |
| `F44d` | Extracts transaction receipt/apply/rollback/recovery lifecycle behavior whose frontend projection must match backend authority | GPT-5.6 Sol manager/validator; execute only after the earlier `F44` slices | `CR-4`; backend/frontend transaction parity and recovery tests |
| `F46` | Moves graph semantics out of a served shell while maintaining host integration, selection, mutation, and replacement behavior | GPT-5.6 Sol manager/validator with graph and browser reviewers | `CR-4`, then re-check at `CR-5` |
| `G50` | Makes the architectural decision for graph versus furniture authority and its loss model | GPT-5.6 Sol architecture owner; research may be delegated | Human gate `D05`; `CR-2` and `CR-5` |
| `G53` | Defines widget-resolution precedence across schemas, UI evidence, defaults, serialization, and failure behavior | GPT-5.6 Sol manager/validator with schema reviewer | Human gate `D03`; `CR-2` and `CR-5` |
| `G55` | Renames and separates hash semantics without changing identity, cache, comparison, or compatibility behavior | GPT-5.6 Sol manager/validator with compatibility reviewer | Human gate `D07`; `CR-5`; golden and cross-process hash proof |
| `G56` | Extracts topology and ownership from a large compiler while preserving deterministic graph facts and private seams | GPT-5.6 Sol manager/validator; delegate bounded characterization/extraction | `CR-5`; compiler golden, determinism, and monkeypatch proof |
| `G57` | Extracts local/wall layout and collision policy whose geometry is coupled across compiler phases | GPT-5.6 Sol manager/validator with geometry reviewer | `CR-5`; golden geometry, invariants, and determinism proof |
| `G58b` | Separates edge/socket/reroute/broadcast/dynamic-port resolution where a small error silently changes workflow meaning | GPT-5.6 Sol manager/validator; execute only after `G58a` and `G60` | `CR-5`; known-schema fail-closed and schema-less evidence |
| `G59` | Decomposes widget, evidence, layout reconciliation, refusal, and validation policy at the API/UI projection boundary | GPT-5.6 Sol manager/validator with emitter/schema reviewer | `CR-5`; golden UI/API, refusal, and round-trip proof |
| `G63` | Gates active IR migration milestones and decides when legacy graph paths can safely disappear | GPT-5.6 Sol validator independent of the migration implementers | `CR-5`; explicit `MIG-G1`/`MIG-G2`/`MIG-G3` receipts |
| `E60` | Establishes typed phase contracts that constrain every later executor extraction and host boundary | GPT-5.6 Sol manager/validator with executor reviewer | `CR-6`; contract, import-boundary, and failure-mapping proof |
| `E62b` | Extracts research orchestration with tools, retries, evidence, redaction, and shadow behavior | GPT-5.6 Sol manager/validator; execute after `E62a` | `CR-6`; deterministic research/evidence and failure-path tests |
| `E63` | Extracts implement/reply phases while preserving durable handoff, edit behavior, and response semantics | GPT-5.6 Sol manager/validator with backend adapter reviewer | `CR-6`; end-to-end phase and host-port evidence |
| `S74` | Removes or consolidates deployed route/field/state compatibility bridges whose consumers may be persisted or external | GPT-5.6 Sol manager/validator with independent compatibility reviewer | Human gates `D04`/`D06` where applicable; `CR-7` |

For each row, the Sol owner must first split work into reviewable packages of at most two days. The Sol owner may delegate characterization, inventories, mechanical moves, focused test writing, and adversarial review, but it retains authority over the end-to-end contract and must produce the completion receipt. No `[XHARD]` unit may be inferred complete from a green focused test alone.

The absence of an `[XHARD]` tag does not mean “easy.” It means the work is sufficiently bounded to use the normal implementer plus independent-review path. For example, `C13`, `F47`, `G60`, and `S77` remain risk-sensitive, but their intended changes have narrower authority and compatibility scope.

## 6. Wave 0 — preserve and measure

### P00 — Working-tree ownership ledger

**Estimate:** 0.5 day
**Purpose:** ensure cleanup never overwrites or misattributes current work.

**Steps**

1. Record current branch, HEAD, worktrees, modified files, untracked files, and active merge/rebase state.
2. Record active agent/dev/test processes and PIDs that may write, hold ports, mutate caches, or create resource contention.
3. Classify every modified/untracked file as user work, prior cleanup work, concurrent work, generated output, or unknown.
4. Record an owner and landing decision for every file.
5. Do not delete, stash, reset, or commit unknown work.
6. Decide whether execution will continue on the existing `desloppify/worst-offenders` branch or a clean descendant/worktree.

**Acceptance criteria**

- every dirty file appears in the ledger;
- no unknown file is included in a cleanup commit;
- concurrent documents are explicitly protected;
- the chosen execution branch/worktree is documented.

**Rollback:** documentation-only; no code mutation.

### [XHARD] P00A — PR154/PR156/local replay integration freeze

**Estimate:** 1 day read-only reconciliation
**Prerequisite:** verified preservation snapshot `4abeb90d`. `P00` may remain in progress while it classifies independent dirty worktrees.

Freeze the provenance and ownership boundary between the preserved PR154 checkpoint, PR156, and the local structural replay before any implementation package is dispatched. This package is a planning gate, not a cleanup implementation.

**Required receipts**

- `4abeb90d` — preserved pre-PR154 local structural work;
- `654373b7` — preserved intermediate PR154/local-integration state;
- `368a332a` — PR156 code head before the CI-only follow-up;
- `25f12eea` — current PR156 remote tip containing the `browser-smoke` interpreter export;
- `49dd66d4` — integrated PR156 code head `368a332a` plus local replay;
- `1136f7cb` — runtime expectation correction;
- `25260147` — adjacent-verification contract corrections;
- `58727689` — local configured-Python correction for both `browser-smoke` and standalone `browser-contracts`;
- `9eca3ed1` — initial post-PR156 cleanup-plan reconciliation submitted to independent CR-0A review;
- `cf29bd1a` — correction of CR-0A's runtime-contract and dependency-gate findings;
- `CR-0A: continue` — independent GPT-5.6 Sol acceptance after the bounded correction and requested verification;
- `d30c5d59` — tree-identical ancestry merge of current PR156 tip `25f12eea`;
- `CR-0A latest-head recheck: continue` — independent confirmation that the CI-only upstream advance leaves the accepted reconciliation valid;
- branch/worktree: `integrate/pr156-local-cleanup-20260820` at `/private/tmp/vibecomfy-pr156-local-integration`;
- original live worktree `/Users/peteromalley/Documents/reigh-workspace/vibecomfy` unchanged.

**Steps**

1. Record the exact base/head/replay chain, final branch/worktree, and original-live-tree protection.
2. Reconcile every staged/dirty/unresolved path to one owner and landing decision; preserve the six other dirty worktree payloads and one active test worktree as protected inputs.
3. Record the resolved `session.py` conflict and focused evidence without treating façade edits as completed B33–B35 extraction.
4. Update the package status table, compatibility gates, and authority ledger with concrete files/tests and remaining blockers.
5. Produce a clean descendant/worktree recommendation. Do not mutate code, tests, generated outputs, caches, or the live tree.

**Acceptance criteria**

- all receipts above are recorded and their preservation meaning is explicit;
- no dirty payload is silently folded into cleanup ownership;
- P00A may be accepted independently of P00; P00 remains separately blocking until the six other payloads and active test worktree have decisions;
- every affected package has a status and a concrete next goal;
- an independent `[XHARD-REVIEW]` gate accepts the reconciliation before P01–P03 or mutation work proceeds.

**Rollback:** documentation-only; restore the prior plan text if the reconciliation is superseded. Never reset or delete the preserved worktrees.

### P01 — Public surface and monkeypatch inventory

**Estimate:** four read-only slices of 0.5–1 day
**Prerequisites:** completed `P00`; accepted `P00A`/`CR-0A`

Inventory:

- Python public imports and re-exports;
- JavaScript exports used by browser tests or external harnesses;
- route paths and response fields;
- `edit.py` frozen names;
- functions monkeypatched by tests;
- subprocess/import-order expectations;
- persisted session and workflow fixture versions.

Execute as `P01a` backend/session/routes, `P01b` executor/provider/runtime, `P01c` frontend/browser, and `P01d` graph/porting/schema. Merge their ledgers only after duplicate surface names are reconciled.

**Acceptance criteria**

- each planned extraction names the surface it must preserve;
- intentional local imports are distinguished from accidental cycles;
- compatibility tests exist or are assigned to a later characterization package.

### P02 — Authority and derived-data ledger

**Estimate:** four read-only slices of 0.5–1 day
**Prerequisites:** completed `P00`; accepted `P00A`/`CR-0A`

Create a table for:

- workflow graph, raw UI evidence, API projection, and UI projection;
- session state, candidate transaction, lifecycle log, receipts, and turn records;
- executor request/result, agent response, and frontend normalized response;
- object-info source, index, shard, in-memory cache, and resolved schema;
- layout inputs, placement plan, and emitted geometry.

For every item record its authority, readers, writers, validation rule, rebuild rule, and compatibility version.

Use the same backend, executor, frontend, and graph slices as `P01`; add one integration pass to resolve cross-layer claims.

### P03 — Baseline test and performance ledger

**Estimate:** four authorized slices of 0.5–1 day plus integration
**Prerequisites:** completed `P00`; accepted `P00A`/`CR-0A`

Record commands and current results for:

- workflow/convert/patch tests;
- reorganise and UI-emitter tests;
- session/transaction/replay/route tests;
- executor boundary and phase tests;
- frontend lifecycle, ownership, harness-closure, and smoke tests;
- fresh-process import checks;
- object-info cold/warm lookup timings;
- representative roundtrip and agent-edit timings.

Execute separate backend/session, executor/provider, frontend/browser, and graph/porting/schema baselines so one overloaded command cannot hide which area is slow or failing.

Do not “fix while measuring.” Existing failures must be classified before Wave 1.

`P00`–`P02` are read-only inventories. `P03` may execute tests only after explicit execution authorization and must use an isolated artifact/cache location where supported. It may not regenerate sources, rewrite checked-in caches, mutate worktrees/branches, or invoke destructive Make targets.

## 7. Wave 1 — known correctness and performance debt

### C10 — Fail malformed roundtrip payloads closed

**Estimate:** 0.5–1 day
**Prerequisites:** `P01`, `P02`, `P03`

**Problem:** malformed graph shapes can be normalized into a successful roundtrip response instead of producing a typed error.

**Likely files**

- `vibecomfy/comfy_nodes/agent/routes.py` or the extracted roundtrip service introduced later;
- ingest/normalization validation modules;
- `tests/test_comfy_roundtrip_route.py`.

**Steps**

1. Identify the earliest boundary that can distinguish malformed transport input from a valid empty graph.
2. Add a characterization test for malformed `nodes`, links, widgets, and envelope shapes.
3. Validate before permissive normalization destroys evidence.
4. Return the standard typed failure envelope without leaking raw payload data.

**Done when**

- malformed transport shapes never return `{graph, report, version}` success;
- valid empty workflows still work;
- failure kind and public fields match the shared error contract.

### C11 — Preserve dynamic exec input links during UI emission

**Estimate:** 1–1.5 days
**Prerequisites:** `P02`, `P03`

**Problem:** repeated or dynamic `in_N` links can be refused as dangling because declared exec IO and emitted socket resolution disagree.

**Steps**

1. Characterize repeated inputs, sparse input indexes, widget-derived IO, and raw-UI generic port pools.
2. Decide whether declared exec `io` or raw UI evidence is authoritative for each case.
3. Resolve physical input sockets once, before global link emission.
4. Keep refusal fail-closed when no declared or evidenced socket exists.

**Done when**

- linked `in_N` references survive API -> IR -> UI -> IR roundtrip;
- no link targets a nonexistent emitted socket;
- refusal diagnostics retain endpoint evidence for genuinely malformed graphs.

### C12 — Validate and propagate the integrated `16384` runtime default

**Estimate:** 0.5 day
**Prerequisite:** `P02`

The PR156 integration freezes `16384` as the characterized current baseline: production and its direct contract test must both state the value literally so changing the implementation alone cannot silently weaken the test. Inventory every projection in Python, TOML, environment handling, status output, and tests; then make them derive from one named authority without replacing literal boundary assertions with self-referential constants.

Before changing the value in the future, record the decision owner, rationale, compatibility impact, migration/rollout expectation, and the concrete boundary assertions that must change. A different product decision is allowed, but it is an explicit contract change rather than cleanup drift.

### C13 — Cache schema providers and object-info shards safely

**Estimate:** two slices of 1–2 days
**Prerequisites:** `P02`, `P03`

**Problem:** schema lookup synchronously reconstructs providers and parses multi-megabyte shards. Under contention, this can consume a large part of request/test time.

This parent epic has two distinct cache layers:

- `C13a` — provider lifecycle/configuration cache: reuse provider instances by configuration identity; preserve on-demand settings, environment/monkeypatch isolation, request/session injection, and provider precedence;
- `C13b` — object-info index/shard cache: cache parsed files, detect replacement, define invalidation/reset, and handle malformed/partial files safely.

**Steps**

1. Measure provider construction, index lookup, shard read, JSON parse, schema construction, and consensus independently.
2. Add a cache keyed by canonical path plus file identity (`mtime_ns`, size, and format/fingerprint as appropriate).
3. Reuse provider instances within a request/session boundary.
4. Define invalidation for file replacement, runtime fingerprint changes, and explicit refresh.
5. Keep cold lookup behavior deterministic and fail closed for malformed cache files.
6. Require atomic replacement or an equivalent process-safe write protocol, with concurrent-reader and replacement/invalidation tests.

**Done when**

- warm object-info lookup performs no additional shard filesystem read or JSON parse;
- source-provider misses, refresh, and network-disabled paths have separate explicit expectations;
- cache invalidates after a shard replacement;
- same-size or same-mtime replacement is covered according to the chosen file-identity rule;
- concurrent readers cannot observe a partially written cache;
- provider configuration changes and test monkeypatches cannot reuse an incompatible cached provider;
- performance gates use both CPU time and wall time so host contention is visible.

## 8. Wave 2 — cross-cutting authority

### A20 — Canonical vocabulary catalog

**Estimate:** 1 day
**Prerequisites:** `P01`, `P02`

Catalog and assign owners for:

- session and transaction state names;
- lifecycle event names;
- route names and aliases;
- model transport names;
- failure kinds and retryability;
- graph, plan, candidate, transaction, and idempotency identities;
- public response field allowlists.

This package produces decisions and characterization tests, not mass movement.

### A21 — Hash and identity ownership

**Estimate:** 1–1.5 days
**Prerequisite:** `A20`

Confirm the inputs and owners of payload hash, graph hash, structural hash, layout hash, plan hash, candidate stable key, generation, lease nonce, and idempotency key. Remove only exact duplicate implementations after fixture parity is proven.

### A22 — Failure taxonomy map

**Estimate:** 1 day
**Prerequisite:** `A20`

Map provider exceptions, `FailureKind`, executor phase errors, route envelopes, and frontend diagnostics. The target is a neutral vocabulary plus explicit layer adapters, not one giant exception class.

### A23 — Transport/domain/projection contract map

**Estimate:** 1.5 days
**Prerequisite:** `A20`

Classify similarly named results and outcomes across agent contracts, executor contracts, provider responses, route responses, and frontend normalization. Rename or move only after wire-format and semantic differences are documented.

### A24 — Import-boundary contract

**Estimate:** 1 day
**Prerequisites:** `P01`, `A20`

Define allowed package directions and add fresh-process checks for the most important boundaries. Avoid an all-or-nothing cycle ban until intentional compatibility imports have migration replacements.

### [XHARD] A25 — Python/JavaScript contract freeze

**Estimate:** 1 day
**Prerequisites:** `A20`, `A22`, `A23`

Freeze the wire vocabulary, generated-source ownership, compatibility aliases, transaction fields, route fields, and malformed-payload rules used by both Python and JavaScript.

`B38` and `F42` form one coordinated contract migration. Neither is complete until Python re-exports, generated JavaScript, hand-written selectors, fixtures, and parity tests land together.

### [XHARD] A26 — Graph/browser projection boundary freeze

**Estimate:** 1 day
**Prerequisites:** `P02`, `A21`

Name the owner and result shape for:

- graph identity;
- link/socket resolution;
- dynamic-I/O normalization;
- widget resolution;
- refusal evidence;
- browser graph mutation versus backend UI emission.

`F46`, `G58`, and `G59` may not redefine these independently. Their package cards must reference this frozen boundary.

## 9. Wave 3 — backend and agent architecture

### B30 — Break the `porting.edit.ops` / `agent.provider` cycle

**Estimate:** 1–1.5 days
**Prerequisites:** `P01`, `A22`, `A24`

**Current inversion:** `porting/edit/ops.py` imports provider exceptions while `agent/provider.py` imports delta parsing/schema helpers from `ops.py`.

**Target**

- introduce a neutral provider-error module;
- move `MalformedModelJSON`, `MissingRequiredField`, and related neutral types there;
- re-export them from `agent.provider` for compatibility;
- make edit parsing depend only on neutral errors.

**Acceptance criteria**

- importing `porting.edit.ops` does not import provider/runtime;
- exception identity remains compatible for `isinstance` checks;
- provider imports and serialized errors remain stable.

### B31 — Neutral model-attempt evidence

**Estimate:** 1 day
**Prerequisites:** `A23`, `A24`

Move model-attempt evidence, endpoint normalization, and redaction to a neutral module usable by provider, runtime, and executor. Preserve the old executor-contract import through a re-export during migration.

### B32 — Unify route, model, transport, and credential policy

**Estimate:** 1.5–2 days
**Prerequisites:** `A20`, `B30`

Create one neutral runtime-config owner for route aliases, route descriptors, model/transport selection, dotenv parsing, and credential presence. Provider readiness, runtime dispatch, and browser status must use the same normalized decision.

**Special risk:** runtime currently hydrates environment state during import. Characterize clean-process behavior before moving or delaying it.

This is a parent epic. Execute as:

- `B32a` — route/model/transport vocabulary and selection, 1–1.5 days;
- `B32b` — credential presence, dotenv parsing, readiness/status agreement, 1–1.5 days;
- `B32c` — import-time environment hydration decision and subprocess migration, 1 day.

### B33 — Extract session primitives without changing storage

**Estimate:** 1.5–2 days
**Prerequisites:** `P01`, `P02`, `A21`, `A24`

Move safe path components, session/turn path builders, canonical JSON/hash helpers, filenames/schema constants, atomic JSON helpers, and clock hooks into a neutral session-primitives module.

Then change `_session_storage.py`, `_session_transaction_journal.py`, `_artifact_store.py`, `_turn_state_machine.py`, and `_v2_scoped_validation.py` to import primitives directly instead of importing `session.py` dynamically.

**Done when**

- extracted storage/artifact modules do not import `session` for primitives;
- `session.py` still exposes old helper names;
- no on-disk format changes;
- monkeypatch compatibility is either preserved or replaced by explicit injected hooks.

### [XHARD] B34 — Make transaction authority executable

**Estimate:** 2 days
**Prerequisites:** `B33`, `A20`

Separate transaction artifact persistence from transaction application services.

**Target responsibilities**

- artifact module: candidate transaction, append-only lifecycle log, receipt snapshots, index rebuilding;
- transaction service: prepare, canvas verification, finalize, rollback, cancellation, reconciliation;
- `session.py`: compatibility delegates only.

**Acceptance criteria**

- lifecycle log authority is enforced by every reader;
- receipts and indexes are demonstrably rebuildable;
- no route treats a snapshot as authority;
- corrupt/truncated artifacts fail closed or recover according to an explicit rule.

Execute as:

- `B34a` — artifact authority/readers/index rebuilding, 1.5–2 days;
- `B34b` — prepare/verify/finalize/rollback application service, 1.5–2 days;
- `B34c` — cancellation, reconciliation, corruption, and recovery policy, 1–1.5 days.

### [XHARD] B35 — Isolate turn allocation and transition rules

**Estimate:** 1.5–2 days
**Prerequisite:** `B34`

Extract allocation, idempotency, accept/reject/rebaseline, CAS checks, and transition validation behind typed services. Maintain read compatibility for legacy V1 state; keep V2 writes fail closed.

### B36 — Split route handlers from registration

**Estimate:** 1.5–2 days
**Prerequisites:** `B32`, `B34`, `B35`

Create independently importable handler/service families for submit, actions, chat, roundtrip, demo, replay, node-pack installation, settings, credentials, contribution, and rating. Keep aiohttp/ComfyUI registration in one registration module.

`routes.py` remains a temporary façade so existing imports and tests continue to work.

Execute as:

- `B36a` — registration plus common request/response parsing, 1–1.5 days;
- `B36b` — submit, chat, accept/reject/rebaseline/finalize handlers, 1.5–2 days;
- `B36c` — demo, replay, node packs, settings, credentials, contributions, and rating, split again if its file set exceeds two days.

### [XHARD] B37 — Replace the batch REPL globals container

**Estimate:** 2 days
**Prerequisites:** `P01`, `B30`, `B32`

Replace the 71-name dependency lookup from `edit.py` globals with a typed host split into cohesive ports such as graph editing, provider calls, memory/research, reporting, and response construction.

Keep the existing globals-based builder as a compatibility fallback until every call path uses the explicit host.

### [XHARD] B38 — Split agent contracts by semantic family

**Estimate:** 2 days
**Prerequisites:** `A22`, `A23`, `B34`, `B35`

Candidate families:

- edit/transaction state contracts;
- failure contracts;
- turn outcomes and diagnostics;
- public response projections;
- graph/widget repair helpers.

`agent/contracts.py` remains a re-export façade. JSON field names and allowlists do not change in this package.

Execute as:

- `B38a` — edit/transaction state and failure contracts, 1.5–2 days;
- `B38b` — outcomes, diagnostics, public projections, and graph/widget helpers, split if required.

This work is paired with `F42` under `A25`; Python movement must not strand generated JavaScript or hand-written selectors.

### B39 — Backend façade retirement audit

**Estimate:** five subsystem slices of 0.5 day
**Prerequisites:** `B30`–`B38`

For every wrapper in `session.py`, `routes.py`, `edit.py`, `provider.py`, and `contracts.py`, choose one outcome:

- public compatibility surface: retain and document;
- temporary migration seam: add removal condition;
- unused/private wrapper: remove with import and behavior proof.

Do not measure success solely by façade line count. Measure dependency direction and number of owners.

Execute as separate session, routes, edit, provider/runtime, and contract/executor cards. Actual shim deletion is owned by the matching `S71`–`S75` ledger entry.

## 10. Backend-focused verification matrix

Run the exact commands selected during `P03`; at minimum cover:

- session storage, transaction, recovery, CAS, and migration fixtures;
- accept/reject/rebaseline route behavior;
- replay path traversal and artifact selection;
- provider readiness, credential redaction, route normalization, and dispatch agreement;
- batch edit protocol and frozen façade names;
- executor headless imports and injected host ports;
- failure serialization and public allowlists;
- fresh-process tests for environment hydration and import order.

Every backend package must also pass `python -m compileall -q vibecomfy`, targeted Ruff checks, and `git diff --check` before it is considered complete.

Planned focused command groups, to be confirmed during `P03`:

```bash
# Session, transactions, recovery, and route sanitization
python -m pytest \
  tests/test_comfy_nodes_agent_session.py \
  tests/test_comfy_nodes_agent_transaction_storage.py \
  tests/test_routes_session_sanitization.py -q

# Routes and replay
python -m pytest \
  tests/test_agent_route_families.py \
  tests/test_agentic_replay_routes.py -q

# Executor contracts, flows, and host boundary
python -m pytest \
  tests/test_executor_contracts.py \
  tests/test_executor_flows.py \
  tests/test_executor_host_boundary.py \
  tests/test_executor_profiles.py -q

# Edit façade and batch protocol
python -m pytest \
  tests/test_cleanup_surface_manifest.py \
  tests/test_edit_batch_repl_dependencies.py \
  tests/test_agent_tool_surface.py -q
```

Run broad backend-spine and research-shadow suites as wave gates, not as the only focused proof. Execute timeout-sensitive cases under bounded host load.

## 11. Frontend cleanup packages

### Frontend target shape

```text
ComfyUI and browser adapters
    -> transport and generated wire-contract normalization
    -> canonical panel store and selectors
    -> submit/apply/reject/rebaseline flow services
    -> view-model projection
    -> DOM and canvas renderers
```

`roundtrip_extension.js` should own registration only. `vibecomfy_roundtrip.js` should become a temporary composition façade, not a second application layer.

### F40 — Reconcile frontend docs, endpoints, and state owners

**Estimate:** 0.5–1 day
**Prerequisites:** `P01`, `P02`, `A20`, `A23`

Produce three current-state tables before changing code:

1. Endpoint matrix covering executor submit, legacy agent-edit submit, accept/finalize bridge, reject, rebaseline, chat, status, credential, research, replay, and rating paths.
2. State-owner matrix covering canonical lifecycle compartments and compatibility fields such as `chatMessages`, `turns`, `history`, and detail snapshots.
3. Prior-plan status table for the dated frontend split-brain and overlay cleanup documents.

**Important discrepancy to resolve:** older cleanup documents say DOM preview chips were removed, while current `panel_overlay.js`, shell wrappers, and static tests deliberately require them.

**Acceptance criteria**

- no endpoint appears under two unexplained names;
- every frontend field has one writer or an explicit compatibility owner;
- old recommendations are labelled current, resolved, or superseded using current code evidence;
- no production behavior changes in this package.

### F41 — Decide the preview rendering contract

**Estimate:** 1 day
**Prerequisite:** `F40`

Choose one product-supported design:

- canvas overlay only; or
- intentional canvas plus DOM-chip composition.

If DOM chips stay, document why both layers exist and move all invocation, invalidation, and diagnostic ownership into `panel_overlay.js`. If they go, remove the renderer, shell refresh wrapper, tests, and stale DOM cleanup together.

**Likely files**

- `vibecomfy/comfy_nodes/web/panel_overlay.js`;
- `vibecomfy/comfy_nodes/web/vibecomfy_roundtrip.js`;
- preview ownership and smoke tests;
- dated frontend cleanup docs.

**Done when**

- exactly one overlay owner exists;
- candidate invalidation clears every supported visual layer;
- an old render cannot overwrite a newer candidate;
- code, tests, and docs describe the same product behavior.

### [XHARD] F42 — Make generated wire contracts and selectors authoritative

**Estimate:** 1.5–2 days
**Prerequisites:** `F40`, `A22`, `A23`, `A25`

**Current overlap:** rebaseline recovery and other payload shapes are interpreted in generated JavaScript, hand-written response normalization, lifecycle code, and shell helpers.

**Target ownership**

- Python agent contracts: canonical wire vocabulary;
- generated JS: canonical snake_case shapes and constants;
- hand-written response contract: legacy/camelCase compatibility pre-pass and public selectors;
- lifecycle: consumes normalized selectors and does not normalize wire objects again.

**Steps**

1. Inventory every local field reader and alias normalization helper.
2. Add malformed/legacy/canonical fixtures before movement.
3. Remove lifecycle-local and shell-local re-normalization one family at a time.
4. Regenerate JS and require byte-for-byte reproducibility.

**Done when**

- one normalization path owns each response family;
- malformed payloads fail closed consistently;
- canonical projections contain no legacy aliases;
- Python and generated JS parity tests pass.

This package is coordinated with `B38`. Do not land Python contract movement or generated-JS changes independently.

### [XHARD] F43 — Collapse transcript and detail compatibility mirrors

**Estimate:** 1.5–2 days
**Prerequisite:** `F42`

**Current overlap:** lifecycle compartments such as `transcriptMessages`, `responseDetails`, `executionEvents`, `auditArtifacts`, and `debugDiagnostics` coexist with `chatMessages`, `turns`, `history`, and detail snapshots.

**Steps**

1. Select canonical compartments and selectors.
2. Migrate `panel_thread.js`, diagnostics, submit promotion, rehydrate, and rating consumers.
3. Put any unavoidable legacy aliases behind one compatibility projection.
4. Prevent new direct writes to compatibility fields.
5. Add a deletion condition and test for each remaining mirror.

**Done when**

- rehydrate is idempotent;
- optimistic and durable messages reconcile exactly once;
- diagnostics and renderers use selectors, not raw mirrors;
- no stale scope snapshot resurrects a removed compatibility field.

### F44 — Split lifecycle domains behind one event façade

**Estimate:** five slices of 1–2 days each
**Prerequisite:** `F43`

Keep the public `transition(panel, event, payload)` API initially. The executable slices are:

1. `F44a` — scope activation and fencing, 1–1.5 days;
2. `F44b` — chat rehydrate and transcript ingestion, 1.5–2 days;
3. `F44c` — candidate invalidation and eligibility, 1–1.5 days;
4. **`[XHARD] F44d`** — transaction receipts, apply, rollback, and recovery, 1.5–2 days, after `B34` and `B35`;
5. `F44e` — submit, stop, abort, and orphan recovery if still coupled, 1–1.5 days.

**Target modules** may include `lifecycle_scope.js`, `lifecycle_chat.js`, `lifecycle_candidate.js`, `lifecycle_transaction.js`, and `lifecycle_submit.js`.

**Acceptance criteria per slice**

- the slice is a pure transition over explicit state/payload;
- no DOM, fetch, timers, or ComfyUI graph access enters the reducer;
- obligations describe effects without performing them;
- existing lifecycle event names and state projections remain stable;
- domain tests pass independently and through the façade.

### F45 — Replace wide flow dependencies with capability bundles

**Estimate:** 1.5–2 days per flow family
**Prerequisite:** `F44`

`agent_apply_flow.js` currently receives roughly 68 dependencies and `agent_rebaseline_undo.js` roughly 45. Replace flat lists with small named capabilities, not one untyped mega-object.

Candidate capabilities:

- lifecycle transition/commit;
- transaction transport;
- graph runtime;
- canvas verification;
- session identity;
- rendering notifications;
- diagnostics;
- compatibility bridge.

Apply the pattern as `F45a` submit, `F45b` apply/finalize, and `F45c` reject/rebaseline, each with its own card and no more than two days.

**Done when**

- each flow can run with fake transport, timers, graph adapter, and lifecycle ports;
- flows emit events/obligations rather than directly rendering;
- watchdog maps remain consumer-owned;
- endpoint strings and transaction rules are not duplicated across flows.

### [XHARD] F46 — Move graph semantics out of the shell

**Estimate:** 1.5–2 days per semantic family
**Prerequisites:** `F42`, `F45`, `A26`

Move duplicate exec-I/O normalization, link normalization, field lookup, inverse-link helpers, target resolution, serialization repair, and graph mutation into `comfy_adapter.js` or a dependency-light pure graph module.

Keep thin shell exports temporarily for compatibility. Execute separately as `F46a` dynamic-I/O/serialization normalization, `F46b` link/field/target resolution, and `F46c` graph mutation/identity delegation.

**Done when**

- one dynamic-I/O normalization path exists;
- one graph mutation path exists;
- preview and apply share stable identity rules;
- native group identity never falls back to display title/index;
- the shell contains composition, not graph algorithms.

### F47 — Extract panel composition and global side-effect managers

**Estimate:** 1.5–2 days
**Prerequisites:** `F43`, `F45`

Extract panel DOM construction from the shell and centralize ownership for:

- document mouse listeners;
- browser `onerror` and unhandled-rejection capture;
- API event listeners;
- LiteGraph prototype patches;
- global debug hooks;
- graph/configure fallbacks.

Each manager needs idempotent install plus uninstall or reference-counted replacement behavior.

**Done when**

- setup can run twice safely;
- replacing a panel/runtime removes or fences old callbacks;
- old-scope callbacks cannot mutate the current panel;
- extension bootstrap remains dependency-injected and registration-only.

### F48 — Frontend façade classification and served-code proof

**Estimate:** 1 day
**Prerequisites:** `F41`–`F47`

Classify every wrapper/export in `vibecomfy_roundtrip.js` as public, temporary, or dead. Do not remove delegates in this package; actual shim removal belongs to `S76`. Then verify staged dependency closure, served assets, ComfyUI reload behavior, and a real browser path from open through submit, preview, and apply/reject/rebaseline.

**Frontend gates**

At minimum, use the exact commands established in `P03` for:

- ownership and lifecycle static checks;
- generated contract parity and malformed payloads;
- chat rehydration and transcript reconciliation;
- transaction/apply/rebaseline behavior;
- graph adapter and dynamic IO;
- scheduler activation fencing and dependency isolation;
- harness dependency closure;
- complete browser smoke and real served-code verification.

**Planned focused commands — confirm paths during `P03`**

These parent-level recipes are not sufficient to authorize a suffix package. Before execution, `P03` must assign exact allowed files, commands, expected results, acceptance criteria, and rollback independently to every suffix such as `F44a` or `F46b`.

```bash
# F40/F41 — ownership and preview contract
node --test \
  tests/browser/ownership_contract.test.mjs \
  tests/browser/frontend_ownership_regression.test.mjs \
  tests/browser/lifecycle_ownership_static.test.mjs \
  tests/browser/preview_overlay_ownership_static.test.mjs

# F42 — generated and hand-written response contract
python -m pytest \
  tests/test_agent_contract_codegen.py \
  tests/test_comfy_nodes_agent_contracts.py -q
node --test \
  tests/browser/agent_edit_response_contract.test.mjs \
  tests/browser/agent_edit_response_malformed.test.mjs \
  tests/browser/payload_contracts.test.mjs \
  tests/browser/m1_contracts.test.mjs

# F43/F44 — transcript and lifecycle
node --test \
  tests/browser/chat_rehydration.test.mjs \
  tests/browser/agent_edit_lifecycle_transcript.test.mjs \
  tests/browser/agent_edit_lifecycle.test.mjs \
  tests/browser/agent_lifecycle_commit.test.mjs \
  tests/browser/agent_lifecycle_parity.test.mjs

# F45 — submit/apply/rebaseline flows
node --test \
  tests/browser/submit_flow_ownership.test.mjs \
  tests/browser/agent_edit_transaction.test.mjs \
  tests/browser/agent_lifecycle_commit.test.mjs \
  tests/browser/roundtrip_smoke.test.mjs

# F46 — graph ownership and dynamic IO
node --test \
  tests/browser/comfy_adapter_ownership.test.mjs \
  tests/browser/dynamic_io_smoke.test.mjs \
  tests/browser/intent_graph_adapter.test.mjs \
  tests/browser/graph_projection.test.mjs \
  tests/browser/canonical_delta.test.mjs

# F47/F48 — runtime isolation, closure, and browser integration
node --test \
  tests/browser/frontend_browser_boundary.test.mjs \
  tests/browser/dependency_isolation.test.mjs \
  tests/browser/panel_runtime_scoped.test.mjs \
  tests/browser/panel_scheduler_activation_fence.test.mjs \
  tests/browser/harness_dependency_closure.test.mjs
make browser-smoke
```

Expected result for each executable slice: every named focused test passes, no new browser-global listener survives teardown, and the full smoke gate is green before frontend shim removal begins.

## 12. Graph, porting, schema, and generated-code packages

### Graph target shape

```text
named importer
    -> retained VibeWorkflow
    -> one EditSession/edit gateway
    -> shared facts and render inputs
    -> compile or emit projection
    -> raw API/UI/envelope only at boundaries
```

Copy-on-write/immutable editing is a post-migration target at the applicable IR gate; public IR immutability is not assumed in near-term extraction packages.

Reorganisation currently follows an intentional UI-evidence path through `GraphInventoryFacts`. Do not replace it with direct IR input until furniture ownership is defined by the active IR migration.

### [XHARD] G50 — Graph and furniture authority decision record

**Estimate:** 1 day
**Prerequisites:** `P02`, `A21`

Compare normal ingest and reorganise fact extraction for node identity, edges, helper roles, widget values, modes, subgraphs, virtual wires, groups, reroutes, and raw furniture evidence.

Choose and document the short-term boundary:

```text
UI JSON -> GraphInventoryFacts -> LayoutPlanV1 -> candidate patch
```

and the possible long-term boundary:

```text
VibeWorkflow + FurnitureEnvelope -> GraphInventoryFacts -> LayoutPlanV1
```

Do not implement the long-term path until the IR migration defines furniture ownership.

### G51 — Extract canonical coordinate primitives

**Estimate:** 1–1.5 days
**Prerequisite:** `P03`

The repository already has two intentionally different coordinate semantics:

- integer snapping in `porting/canonical_coords.py`;
- two-decimal emitted-coordinate rounding in `emit/ui.py`, also used by layout hints.

Do not collapse them under one ambiguous helper. Name them separately, for example `snap_coord()` and `canonicalize_emitted_coord()`, in dependency-light leaf modules. Audit `porting/layout`, `layout_store.py`, `lowering.py`, `emit/ui.py`, and `executor/layout_hints.py` before moving imports.

**Done when**

- no layout module imports the UI emitter;
- emitted UI JSON remains byte-identical;
- integer-snap and float-precision goldens remain distinct;
- position, group, layout-store, layout-hint, lowering, and reorganise geometry tests pass.

### G52 — Consolidate `NodeSchema` type identity

**Estimate:** 0.5–1 day
**Prerequisites:** `P01`, `C13`

Inventory imports of both definitions. Enrich the dependency-light `schema/types.py::NodeSchema` as the canonical type; have `schema/provider.py` re-export it. Keep provenance as neutral fields/types and never make `schema.types` import provider/runtime/ComfyUI code.

**Done when**

- providers return the canonical class;
- importing `vibecomfy.schema.types` loads no runtime, client, server, provider, or ComfyUI modules;
- existing four-argument construction, equality/repr, serialization, and provenance behavior remain compatible;
- callers no longer need to guess which schema model they received;
- serialization and provider precedence are unchanged.

### [XHARD] G53 — Define one widget-resolution result and precedence

**Estimate:** two slices of 1–2 days
**Prerequisites:** `C13`, `G52`

Extend the existing `WidgetNameResolution` rather than introducing a third result type. It must distinguish semantic names, raw UI slots, compact values, provenance, confidence, and refusal evidence.

First characterize the current precedence exactly:

```text
metadata.input_aliases
    -> _ui.widgets
    -> _ui.inputs[].widget
    -> committed WIDGET_SCHEMA
    -> semantic names
    -> provider aliases
    -> object-info fallback
```

Then make an explicit product/architecture decision about whether committed `WIDGET_SCHEMA` remains authoritative curated UI evidence or becomes fallback evidence. Do not silently change the current “curated aliases win” behavior.

Execute as:

- `G53a` — characterization, decision, and result contract;
- `G53b` — emitter/edit/layout consumer adoption.

**Done when**

- raw slot count is never confused with compact widget count;
- metadata aliases, `_ui` sources, semantic/provider aliases, hidden/leading `None` padding, duplicate names, stale schema, and schema-less cases are explicit;
- emitter and edit paths consume the same resolution contract;
- curated alias authority/fallback status matches the recorded decision.

### G54 — Characterize reorganise fact extraction against normal ingest

**Estimate:** 1–2 days
**Prerequisites:** `G50`, `G53`

Add side-by-side characterization for representative UI workflows, including helpers, groups, reroutes, subgraphs, dynamic IO, widgets, and virtual wires. Enumerate intentional differences rather than forcing parity prematurely.

**Done when**

- every additional graph/facts/evidence view has a named owner, input contract, loss model, and structural-no-op/roundtrip relationship;
- every fact omitted from `VibeWorkflow` is identified as furniture/editor evidence or a defect;
- direct-IR migration has a written input/output contract but is not yet implemented.

### [XHARD] G55 — Extract and rename reorganise hash semantics

**Estimate:** 1 day
**Prerequisite:** `A21`

First inventory every hash consumer and existing payload. Move compatibility digest implementations into a cohesive module without changing bytes. Only then introduce clearer `topology_hash`, `layout_furniture_hash`, and `plan_hash` semantics through explicit adapters.

**Done when**

- existing digest fixtures and compatibility callers remain stable;
- tests record which identities change for topology, node position/size/flags, group geometry/color, widgets, and plan edits;
- any new clearer identity is not silently substituted for the existing `structural_hash`;
- plan, transaction, agent-contract, and browser hashes remain separate;
- naming/docs match actual payloads.

### [XHARD] G56 — Extract reorganise topology and ownership

**Estimate:** 2 days
**Prerequisites:** `G54`, `G55`

Move SCC/rank/island/component logic and section ownership/classification policy from `compile.py` into cohesive modules. Preserve `compile_layout_plan()` and existing private compatibility imports during migration.

**Done when**

- role purity, sampler relations, disconnected islands, section ranks, and ownership tests pass;
- deterministic output remains byte-identical;
- no new compiler/import cycle appears.

### [XHARD] G57 — Extract local layout, wall layout, and collision policy

**Estimate:** three slices of 1–2 days
**Prerequisite:** `G56`

The executable slices are:

1. `G57a` — local section templates and sidecars, 1.5–2 days;
2. `G57b` — global wall/huge-workflow placement policy, 1.5–2 days;
3. `G57c` — node/group collision repair and quality metrics, 1.5–2 days.

Preserve the orchestrator's deliberate fallback compile behavior and make that fallback typed and observable.

**Done when**

- geometry, huge-workflow, sidecar, pinned-node, overlap, gutter, idempotence, and fixed-point tests pass;
- repeated compile produces identical coordinates;
- fallback policy is visible in results/diagnostics rather than hidden in exception flow.

### G58 — Split emitter identity and link/socket resolution

**Estimate:** two slices of 1.5–2 days
**Prerequisites:** `G51`, `G53`, `A26`; `G58b` also requires `G60` and migration gates `MIG-G1`/`MIG-G2` from `G63`

Execute as `G58a` behavior-preserving ID/UID remapping extraction, then **`[XHARD] G58b`** edge normalization, reroutes, broadcasts, dynamic exec ports, and socket resolution. Each slice is 1.5–2 days. Any semantic identity/link change waits for the migration gates.

`emit_ui_json()` remains the only public entry point.

**Done when**

- no identity mapping changes;
- no link silently changes endpoints or socket type;
- dynamic exec inputs preserve declared links;
- refusal codes and endpoint evidence remain stable.

### [XHARD] G59 — Split emitter widget, evidence, layout, and validation policy

**Estimate:** four slices of 1–2 days
**Prerequisites:** `G53`, `G58b`, `A26`; semantic redirection requires `MIG-G1`/`MIG-G2`, and projection-path deletion requires `MIG-G3`

The executable slices are:

1. `G59a` — widget reconstruction, 1.5–2 days;
2. `G59b` — raw UI and widget-shape evidence, 1.5–2 days;
3. `G59c` — layout/group reconciliation, 1.5–2 days;
4. `G59d` — typed refusals and structural/parity validation, 1.5–2 days.

**Done when**

- compact/raw widget domains remain distinct;
- prior UI evidence is copied and never mutated;
- editor-only data is either preserved, explicitly dropped, or refused;
- emitted JSON and refusal details remain stable for existing fixtures and fuzz tests.

### G60 — Make socket fallback policy explicit

**Estimate:** 0.5–1 day
**Prerequisite:** `G58a`

Current `_resolve_output_slot_and_type()` can return slot zero for an unresolved named output even when a schema exists. Change it to return a typed unresolved-name refusal for known-schema misses; retain slot-zero best effort only when the schema is genuinely absent.

The required sequence is `G58a -> G60 -> G58b`. Add cases for known-schema missing names, schema-less nodes, output aliases, dynamic exec ports, and attempted-remap refusal evidence.

### G61 — Classify and gate generated node shims

**Estimate:** 0.5 day
**Prerequisite:** `P00`

Files such as `nodes/core.py`, `kjnodes.py`, `wanvideowrapper.py`, and `ltxvideo.py` carry generated-file headers and are produced by `tools.generate_node_shims`.

**Actions — classification only**

- identify generator inputs, manifests, and dynamic exports;
- classify these as generator-owned generated code, not authored monoliths or external vendor source;
- defer freshness, regeneration, and stale-output mutation to `S77`;
- preserve authored dynamic exports from `nodes/__init__.py`.

Ownership boundary: `G61` decides classification and source-of-truth policy; `S77` changes generator/regeneration behavior; `T70` configures health-tool zones. Each generated surface gets one ledger row and one implementation owner.

### G62 — Audit the relationship between layout engines

**Estimate:** 1 day research decision, implementation separately
**Prerequisites:** `G50`, `G54`

Start from the documented decision that the semantic reorganiser and topology-first layout engine are separate policies that may share neutral geometry helpers. Compare consumers, inputs, output contracts, and duplicated primitives. Recommend merging or retirement only if new behavioral proof overturns that decision; do not reopen it by default.

### [XHARD] G63 — IR migration compatibility gate

**Estimate:** 0.5 day
**Prerequisites:** `G54`, `G62`

Define named cleanup gates that cite, rather than rename, the source-plan milestones:

- `MIG-G1` — retained `VibeWorkflow` and named ingest proven by the applicable IR-everywhere milestone plus threaded/staged M1/R1 evidence;
- `MIG-G2` — one edit gateway and accepted delta/batch proven by the applicable IR-everywhere edit/batch milestone plus threaded/staged M4/R2 evidence;
- `MIG-G3` — one projection/render path and durable lifecycle proven by the applicable IR-everywhere renderer/raw-path milestone plus threaded/staged M6/R4 evidence.

Before any raw-UI mutation path, `GraphInventoryFacts` adapter, furniture carrier, browser/Python mirror, or compatibility edit module is deleted or semantically redirected, require the applicable gate evidence. Otherwise mark the cleanup item blocked by migration rather than forcing it.

### Graph/porting planned test recipes

Confirm exact paths and baseline results during `P03`.

```bash
# Graph ingest and workflow authority
python -m pytest \
  tests/test_workflow_core.py \
  tests/test_porting_normalize_ingest.py \
  tests/test_porting_convert.py -q

# Schema/provider/object-info/widget resolution
python -m pytest \
  tests/test_schema.py \
  tests/test_object_info_schema.py \
  tests/test_compact_widget_resolver.py -q

# UI emitter, parity, dynamic links, and fuzz
python -m pytest \
  tests/test_porting_ui_emitter.py \
  tests/test_ui_emitter_parity.py \
  tests/property/test_emitter_fuzz.py \
  tests/test_comfy_roundtrip_route.py -q

# Reorganise facts, compiler, orchestration, and product route
python -m pytest \
  tests/test_reorganise_graph_facts.py \
  tests/test_reorganise_compile.py \
  tests/test_reorganise_goldens.py \
  tests/test_reorganise_orchestrate.py \
  tests/test_reorganise_skill.py -q

# Generated node shims — use the S77 dry-run/output-dir facility or a disposable copied worktree
python -m pytest tests/test_node_shims.py -q
```

Additional required assertions:

- provider construction/read/parse counts for cold, warm, miss, refresh, and network-disabled cases;
- `NodeSchema` fresh-process import closure and constructor/equality compatibility;
- exact widget precedence fixture table;
- known-schema unresolved output refusal versus schema-less best effort;
- prior workflow/raw UI evidence remains unmodified;
- layout-only reorganise is a structural no-op;
- stale patch refusal and fallback diagnostics remain typed;
- generated inventory matches `nodes/__init__.py` without writing the working tree.

## 13. Executor phase and contract packages

### [XHARD] E60 — Define typed phase boundaries

**Estimate:** 1 day
**Prerequisites:** `A22`, `A23`, `B31`, `B38`

Write explicit input/output contracts for classify, research, implement, and reply. Document which evidence is durable, public, redacted, provider-specific, or internal.

No phase movement occurs until these contracts have characterization tests.

### E61 — Inject session context and event sinks

**Estimate:** 1–1.5 days
**Prerequisites:** `B33`, `E60`

Extend neutral host ports so executor core does not need compatibility imports of `agent.edit` for session context or `server.PromptServer` for websocket events.

**Done when**

- headless executor import loads no ComfyUI/agent UI modules;
- session context and phase events are supplied through typed ports;
- the ComfyUI adapter remains the production binder;
- compatibility shims remain temporarily patchable.

### E62 — Extract classify and research phases

**Estimate:** two slices of 1.5–2 days
**Prerequisites:** `E60`, `E61`

Execute as `E62a` classify phase and **`[XHARD] E62b`** research phase, each 1.5–2 days. Preserve route behavior, prompt/tool evidence, bounded retries, redaction, and research-shadow behavior.

### [XHARD] E63 — Extract implement and reply phases

**Estimate:** two slices of 1.5–2 days
**Prerequisites:** `B34`, `E60`, `E61`

Execute as `E63a` durable implementation handoff and `E63b` result/failure/reply assembly, each 1.5–2 days. Keep `run_executor` as the only public orchestration entry point.

### E64 — Executor façade and configuration audit

**Estimate:** 1 day
**Prerequisites:** `B32`, `E62`, `E63`

Classify compatibility forwarding functions and `_DEFAULT_HOST_PORTS` caching. Ensure configuration defaults come from one authority and that no phase imports HTTP routes, browser contracts, or ComfyUI registration.

## 14. Test architecture, generated zones, and documentation packages

### 14.1 Shim cleanup policy

“Shim” includes more than files containing that word. The cleanup inventory must cover:

- compatibility façades and re-export modules;
- forwarding functions that preserve monkeypatch locations;
- aliases for old class, exception, route, field, and state names;
- local/lazy imports used to break cycles or preserve headless imports;
- route bridges such as accept-to-finalize compatibility;
- frontend shell wrappers that delegate to extracted modules;
- fallback adapters and legacy migration paths;
- generated node shim modules and their generator;
- tests and manifests that freeze shim surfaces.

A shim is not automatically bad. Each shim must be assigned exactly one disposition:

| Disposition | Meaning | Required evidence |
|---|---|---|
| Remove now | No supported consumer remains | repository search, fresh-process import checks, focused behavior tests |
| Replace with explicit port | Shim hides a dependency inversion or host dependency | typed boundary plus adapter and import test |
| Retain public | It is a supported compatibility surface | documented consumer, stability test, named owner |
| Retain temporarily | Migration is incomplete | removal condition, blocking package, expiry owner |
| Generate, do not hand-edit | It is produced from an external schema/cache | generator freshness and determinism tests |
| Investigate | Ownership or consumers are unclear | bounded research package before mutation |

The goal is zero **unclassified** shims, not necessarily zero shims.

#### Current shim families to include in `S70`

| Family | Representative surfaces | Initial disposition |
|---|---|---|
| Agent edit façade | `agent/edit.py`, `_frag_*`, frozen cleanup-surface manifest | Retain public; replace wide globals-based host behind it |
| Batch REPL host | invocation-time dependency resolution in `edit_batch_repl.py` | Temporary cycle/monkeypatch seam; replace with typed capabilities |
| Session façade | `session.py` re-exports and late-bound delegates to extracted modules | Retain public; move primitives/authority out gradually |
| Lazy package exports | agent, executor, `porting.edit`, node-packs, nodes package `__init__` files | Retain unless eager import is proven safe |
| CLI/porting façades | `commands/port`, `porting/emitter.py`, layout exports, runtime server process | Retain documented public imports; migrate internal callers first |
| Registry/loader aliases | template/workflow loader and legacy module-entry names | Retain until consumer/release evidence permits removal |
| Security seed mirror | dependency-isolated literal taxonomy and back-compat alias | Retain as an intentional dependency firewall |
| Accept/finalize bridge | session, contracts metadata, routes, bridge counter | Retain until the counter stays unused for an agreed complete release cycle |
| Route/task/field aliases | legacy executor routes, research/implement/reply/intent fields, legacy response fields | Retain at wire boundary; canonicalize internal consumers |
| Executor forwarding names | `executor/core.py` patchable delegates and default host loader | Migrate callers to ports; retain until patch/import census is clean |
| Frontend projection façades | field/identity/graph projection modules, preview/hash delegates | Use canonical owner internally; retain public modules until import census is clean |
| Lifecycle commit façade | source-agnostic lifecycle commit delegate | Retain as a useful application boundary |
| Roundtrip shell delegates | re-exports and thin entry points in `vibecomfy_roundtrip.js` | Classify in `F48`; remove only through `S76` |
| Browser migration adapters | legacy response/delta/storage/route/provider/candidate readers | Retain until persisted/deployed compatibility conditions are met |
| Host integration wrappers | canvas foreground, queuePrompt, extension registration | Retain; require idempotent/reentrant installation |
| Fallback adapters | schema-less ingest/emission, cache/source fallback, layout hints | Treat as product behavior until reachability and diagnostics prove otherwise |
| Local/lazy imports | agent fragments, routes, executor adapter loading, emitter helpers, bootstrap | Classify by headless/optional/cycle/patch purpose before changing |
| Generated Python shims | `nodes/*.py`, paired `.pyi`, generator and aggregate exports | Generated-regenerate only |
| Generated JS contracts | Python-derived response contract JS | Generated-regenerate only with byte parity |

Known census question: current comments and tests appear to disagree on whether the frozen agent-edit surface contains 472 or 441 names. `S70` must resolve this from the current manifest rather than copying either number.

The executable ledger must expand representative rows to concrete file/line entries, including at least schema probe/cache fallbacks, ingest normalization fallbacks, emitter schema-less/geometry fallbacks, executor layout hints and revision evidence, provider/runtime fallbacks, scoped storage migration, response/delta adapters, monkeypatch forwarding names, and each material function-local import.

### S70 — Repository-wide shim census

**Estimate:** 1 day
**Prerequisites:** `P00`, `P01`, `A24`

Create a machine-readable or Markdown ledger containing:

`shim_id | path:line | kind | old/public surface | implementation owner | consumer evidence | package owner | disposition | risk | tests/verification command | blocker | removal condition`

Search Python and JavaScript imports/exports, route registration, generated headers, compatibility comments, forwarding wrappers, deprecated names, fallback branches, local imports, monkeypatch tests, and frozen manifests. Do not rely only on the literal word `shim`.

**Coverage gate:** every compatibility façade, re-export, alias, route bridge, local import, monkeypatch seam, fallback adapter, frontend delegate, generated shim, test freeze, and manifest freeze is either inventoried or explicitly marked not applicable with evidence.

Each shim receives exactly one implementation owner and one cleanup package. Other packages may consume its ledger entry but may not independently delete or redefine it.

### S71 — Remove proven dead forwarding wrappers

**Estimate:** 0.5–1 day per subsystem
**Prerequisites:** `S70`, relevant subsystem façade audit

First reconcile historical deletion claims for the old testing/YAML/schema/runtime-config/research-engine/source-assembler shims against the current tree. Then remove only wrappers with no supported import, monkeypatch, route, persisted-data, browser, or plugin consumer. Keep deletion commits separate from implementation movement.

### S72 — Replace dependency-hiding shims with ports

**Estimate:** 1–2 days per boundary
**Prerequisites:** `S70`, `A24`

Priority candidates include:

- executor host/session/event compatibility forwarding;
- session extracted modules importing back through `session.py`;
- batch REPL globals-based dependency resolution;
- provider/runtime late imports that conceal the edit/provider cycle;
- frontend global side-effect and graph-runtime delegates.

Each replacement must reduce dependency direction, not merely exchange several functions for one untyped `deps` bag.

Execute as independent cards tied to their owning architecture packages:

- `S72a` session delegate inversion after `B33`–`B35`;
- `S72b` provider/edit/runtime cycles after `B30`/`B32`;
- `S72c` executor forwarding/host boundaries after `E60`–`E64`;
- `S72d` frontend host/global delegates after `F45`–`F47`.

### S73 — Consolidate re-export façades

**Estimate:** 1 day per façade family
**Prerequisites:** `S70`, completed implementation extraction

For `session.py`, `routes.py`, `edit.py`, agent/executor contracts, executor core, and the frontend roundtrip shell:

1. group re-exports by supported public family;
2. eliminate duplicate aliases;
3. move semantic fallback logic into the implementation owner;
4. document public versus temporary names;
5. add a surface test generated from the ledger where appropriate.

### [XHARD] S74 — Route, field, and state compatibility bridges

**Estimate:** 1–2 days
**Prerequisites:** `F40`, `A20`, `A23`, `A25`, `B34`, `B35`, `B38`, `F42`, `S70`

Inventory legacy route spellings, accept/finalize bridges, camel/snake field aliases, V1/V2 state readers, and compatibility response projections.

Do not remove a bridge until:

- current producers and consumers are known;
- persisted fixtures no longer require it or a migration exists;
- served/browser clients have a compatibility window or usage evidence;
- fail-closed behavior remains intact.

Execute as `S74a` backend transaction/route bridges, `S74b` executor route/task/field aliases, and `S74c` browser response/storage/state adapters. These slices must not edit the same contract façade concurrently.

### S75 — Local-import and monkeypatch shim cleanup

**Estimate:** 1 day per subsystem
**Prerequisites:** `S70`, `T72`

Classify every important function-local import and patchable forwarding name as:

- required for headless import;
- required to avoid a known cycle pending a named fix;
- required public monkeypatch seam;
- obsolete workaround.

Replace obsolete cases with ordinary imports only after fresh-process and monkeypatch tests prove equivalence. Keep intentional cases documented rather than repeatedly “cleaning” and reintroducing them.

### S76 — Frontend shell delegates and global installers

**Estimate:** 1–2 days
**Prerequisites:** `F42`–`F48`, `S70`

Remove shell wrappers that merely duplicate adapter/lifecycle/overlay/diagnostic behavior. Retain only stable public exports and composition wiring. Global installers must expose idempotent ownership and cleanup rather than hiding repeated installation behind flags scattered across `window`, `api`, prototypes, graph objects, and runtime state.

### S77 — Generated node shim cleanup

**Estimate:** 1 day
**Prerequisites:** `G61`, `S70`, `T70`

Generated node shims are cleaned at their source:

- verify generator input ownership and cache provenance;
- add or verify a supported `--output-dir`/`--check`/dry-run mode; until then, run regeneration only in a disposable copied worktree because the current generator writes the real nodes directory;
- make output ordering and formatting deterministic;
- validate `.py` and `.pyi` pairs;
- remove stale generated modules only through the generator with a valid manifest;
- ensure `nodes/__init__.py` exports match generated inventory;
- enforce “generated — do not hand-edit” headers;
- exclude generated size/duplication from authored-structure scoring;
- add a regeneration-with-no-diff gate.

Do **not** manually split or rewrite `nodes/core.py`, `kjnodes.py`, `wanvideowrapper.py`, or similar generated modules.

### S78 — Shim disposition completeness audit

**Estimate:** 1 day
**Prerequisites:** `S71`–`S77`

Repeat the census and require every remaining shim to have a supported consumer, owner, test, and disposition. “Temporary” shims must point to a blocking package and removal condition. Any unclassified shim reopens the queue; retained supported shims do not count as a failure.

### T70 — Zone classification

**Estimate:** 0.5 day
**Prerequisite:** `P00`

Classify authored production, generated shims, checked-in object-info data/cache, fixtures, scripts, and external/vendor-like content. Configure health tooling so generated size does not distort subjective structure scoring.

### T71 — Replace structure-locking tests selectively

**Estimate:** 1–2 days per subsystem
**Prerequisite:** `P01`

Inventory tests that assert source text, AST placement, private helper location, exact wrapper names, or module-global shape.

Retain static tests when they genuinely protect packaging, generated-file parity, import closure, single ownership, or forbidden dependencies. Replace accidental structure locks with public behavior, import-boundary, or generated-manifest tests.

### T72 — Fresh-process import and side-effect harness

**Estimate:** 1.5 days
**Prerequisite:** `A24`

Add reusable subprocess checks for:

- forbidden imports after loading neutral modules;
- environment mutation during runtime/provider import;
- duplicate route/extension/listener registration;
- module-global cache isolation and reset;
- ComfyUI-absent headless operation.

### T73 — Performance and resource-aware test gates

**Estimate:** 1 day
**Prerequisite:** `P03`

Record CPU time, wall time, host load, cache cold/warm state, and process count for schema and executor timing gates. Keep exact-test reruns separate from heavily parallel test waves so resource contention is not mistaken for a regression.

### T74 — Documentation status and compatibility ledger

**Estimate:** 1 day
**Prerequisite:** all subsystem packages in the current wave

For each older architecture/cleanup plan, mark recommendations:

- current;
- resolved;
- superseded;
- blocked by active migration;
- intentionally deferred.

Update the compatibility ledger with every retained façade, alias, route bridge, persisted format, and browser mirror.

### T75 — Dead-path deletion queue

**Estimate:** one independently reviewable deletion per 0.5–1 day package
**Prerequisites:** `T71`, `T72`, subsystem façade audits

Delete only after proving zero consumers with repository search, import tests, behavior tests, fixture tests, and served-code checks where applicable. Never mix dead-path deletion with a major extraction.

## 15. Dependency and concurrency schedule

### 15.1 Sequential critical path

When the schedule names a parent epic such as `B34`, `F44`, or `G59`, it means every suffix required by the dependent package is complete. Executable cards must replace parent shorthand with precise suffix prerequisites before work begins.

```text
(P00 completed) + ([XHARD] P00A -> [XHARD-REVIEW] CR-0A accepted)
    -> P01/P02/P03
    -> C10/C11/C12/C13
    -> A20 -> A21/A22/A23/A24/A25/A26
    -> early inversions: B30/B31/B32/B33, F40/F41/F42, G50/G51/G52/G53
    -> state and authority: B34/B35, F43/F44, G54/G55
    -> migration/refusal gates: G58a -> G60 -> G58b, plus G63
    -> application splits: B36/B37/B38, F45/F46/F47, G56/G57/G59
    -> executor phases: E60/E61/E62/E63/E64
    -> façade and test cleanup: B39/F48/G60-G63/T70-T75
    -> shim disposition: S70 -> S71/S72/S73/S74/S75/S76/S77 -> S78
    -> R80/R81/R82
```

### 15.2 Parallel-safe groups

Parallel work is allowed only after prerequisites and ownership checks pass.

Likely safe groups:

- `C10`, `C12`, `G51`, and `G61` touch separate authorities after baseline capture;
- `B30`, `F41`, and `G52` can run concurrently after cross-cutting vocabulary decisions;
- backend transaction work and frontend preview work can run concurrently if neither changes shared response contracts;
- reorganise extraction and frontend panel composition can run concurrently after graph/frontend contract ownership is frozen;
- generated-zone classification and documentation status work are always read-only relative to active code packages.

Not parallel-safe:

- `B38` contract movement with `F42` generated-wire changes;
- `B34/B35` transaction movement with `F43/F44` transaction-state projection changes;
- `C13/G52/G53` when they touch schema type/provider APIs;
- `F46` graph movement with `G58/G59` emitter contract movement unless an explicit shared interface is frozen;
- any two packages modifying the same façade or frozen manifest.

Shim work may run in parallel only when ledger ownership and files are disjoint. `S73`, `S75`, and `S76` frequently touch the same façades/import surfaces and must be serialized per subsystem. `S74a`/`S74b`/`S74c` may run concurrently only if Python contract generation and shared route/field vocabularies are frozen and owned by one coordinator.

### 15.3 Per-package execution checklist

Before editing:

- [ ] prerequisites complete;
- [ ] file ownership confirmed against current dirty tree;
- [ ] package branch/worktree identified;
- [ ] baseline focused tests recorded and run;
- [ ] pre-existing failures classified;
- [ ] public surfaces and persisted formats listed;
- [ ] rollback point available.

During implementation:

- [ ] change only the package scope;
- [ ] add characterization before moving unclear behavior;
- [ ] keep compatibility delegates thin;
- [ ] avoid opportunistic formatting or unrelated renaming;
- [ ] record every new façade and removal condition;
- [ ] preserve derived-data invalidation/rebuild rules.

Before marking complete:

- [ ] focused tests pass;
- [ ] adjacent subsystem tests pass;
- [ ] fresh-process/import gates pass when relevant;
- [ ] persisted fixtures pass when relevant;
- [ ] performance comparison recorded when relevant;
- [ ] syntax/compile, targeted lint, and `git diff --check` pass;
- [ ] diff contains no unknown concurrent work;
- [ ] rollback notes and compatibility ledger updated;
- [ ] logical commit recorded only if authorized.

When commits are authorized, create one logical commit per executable suffix package using `cleanup(<PACKAGE-ID>): <summary>`. Record commit hash, changed-file list, exact test receipt, reviewer verdict, and rollback command in the package card. Roll back only that package commit/delegation path; never reset the shared branch or discard unrelated work.

### 15.4 Stop/go rule

Stop the package and investigate before continuing if:

- a persisted fixture changes unexpectedly;
- a wire field, route path, hash, or refusal code changes without an approved contract decision;
- a neutral import begins loading ComfyUI, routes, provider credentials, or browser modules;
- a façade grows new domain logic;
- a new module must import the old façade for most of its behavior;
- baseline and post-change failures cannot be distinguished;
- concurrent work changes a file owned by the package;
- resource contention makes timing evidence meaningless.

### 15.5 Batch card template

Create one card before starting every package or package slice.

```markdown
# <PACKAGE-ID> — <short title>

Status: proposed | ready | in_progress | blocked | done | superseded
Owner:
Base commit:
Branch/worktree:
Estimate:

## Why
<one plain-language paragraph>

## Prerequisites
- <completed package/decision>

## Allowed files
- <exact path or narrowly defined directory>

## Forbidden files/zones
- <concurrent work, generated output, unrelated areas>

## Compatibility surfaces
- <imports, routes, fields, persisted formats, JS exports, monkeypatch seams>

## Baseline evidence
- Command:
- Expected/current result:
- Known pre-existing failures:

## Implementation steps
1. <one verifiable action>

## Acceptance gates
- [ ] <behavior/import/fixture/performance condition>

## Rollback
<how to restore delegation or revert this package independently>

## Completion receipt
- Commit:
- Changed files:
- Focused tests:
- Adjacent tests:
- Static checks:
- Deferred findings:
```

Maintain a program dashboard with:

```text
ID | title | owner | prerequisites | allowed files | status | tests | commit | blockers
```

### 15.6 Test tiers

| Tier | When | Purpose | Examples |
|---|---|---|---|
| 0 — preflight | before a batch | establish ownership and a clean comparison | status/diff/worktree inventory, generated-zone checks, `git diff --check` |
| 1 — syntax/import | during a batch | catch cycles and import effects quickly | Python compile/import, Node syntax, fresh-process boundaries, import-linter contracts |
| 2 — focused behavior | before commit | prove the changed responsibility | package-specific session, route, executor, browser, schema, emitter, or reorganise tests |
| 3 — wave gate | after related packages | catch adjacent integration regressions | subsystem suite, browser contracts/smoke, fixture/parity checks |
| 4 — expensive/environmental | only when authorized | full or real-environment confidence | full pytest, Playwright/e2e, live ComfyUI, GPU, RunPod, network-backed tests |

Warnings:

- inspect Make targets before running them; broad targets may write coverage/cache artifacts or perform cleanup;
- specifically inspect/avoid `root-clean`, `clean-artifacts`, coverage-producing `fast`, and dependency-installing or live-environment e2e targets unless the package card authorizes their side effects;
- do not run GPU/network/live-provider tests as an automatic refactor gate;
- rerun timeout failures under bounded host load before classifying them;
- do not update a frozen manifest merely to make a structural test pass without deciding whether the surface is still supported.

### 15.7 Execution readiness

This master plan is **roadmap-ready** and can guide the full cleanup one package at a time. It is not yet legal to dispatch mutation agents in the current checkout because §3.4 and `[XHARD] P00A` are STOP conditions. The integration reconciliation itself also requires an independent `[XHARD-REVIEW] CR-0A` before Wave 0 inventories can be accepted.

Readiness has three levels:

| Level | Meaning | Current state |
|---|---|---|
| Roadmap-ready | target architecture, package order, risks, and gates are defined | Ready |
| Wave-ready | ownership, decisions, baselines, and suffix package cards for one wave are complete | Wave 0 can be prepared only after P00A and CR-0A; mutation waves are conditional |
| Dispatch-ready | one suffix package has exact files, tests, rollback, reviewer, and a clean worktree | Not until `P00`/P00A, `P01`–`P03`, and their review gates clear |

The program manager may prepare packages just in time. It does not need to pre-author every suffix card before Wave 0, but it may not dispatch an implementer from a parent epic description alone.

### 15.8 Agent roles and ownership

Use distinct roles so the author is not the only judge of the change.

#### Program manager

The root/lead agent owns:

- the dependency queue and dashboard;
- file ownership and concurrency decisions;
- product/architecture decision escalation;
- selection of implementer, reviewer, and verifier;
- test-resource scheduling;
- failure classification and package completion receipts;
- wave integration and final reporting.

The manager should mostly coordinate, review conclusions, and integrate receipts rather than doing wide research in the main thread.

#### Researcher

A read-only researcher:

- inspects a bounded question;
- returns evidence and a decision recommendation;
- does not edit, format, regenerate, or “helpfully” fix nearby code;
- is preferred for unknown imports, consumers, compatibility, and prior-plan reconciliation.

GPT-5.6 Luna is appropriate for inventory, evidence gathering, and focused review. Escalate only packages with unusually difficult architectural or correctness risk.

#### Implementer

One implementer owns one executable suffix package and its allowlisted files. The implementer:

- reproduces baseline behavior;
- adds characterization tests before moving unclear behavior;
- implements only the package goal;
- runs Tier 1 plus focused Tier 2 tests;
- returns a changed-file list, test receipt, risks, and unresolved questions;
- does not declare the package complete.

#### Independent reviewer

A reviewer who did not author the diff checks:

- whether the package goal was actually achieved;
- dependency direction and authority ownership;
- unintended behavior, wire, persistence, hash, or import changes;
- whether tests were weakened or updated merely to accommodate the refactor;
- compatibility façade growth and removal conditions;
- diff scope and unrelated churn;
- rollback viability.

The reviewer should be read-only by default and return blocking versus non-blocking findings. The implementer receives a fix pass; the same reviewer then checks the correction.

#### Verifier/integrator

The verifier runs adjacent or wave-level tests after review. This may be the program manager or a dedicated agent, but should not be the package implementer for high-risk packages.

**One-writer rule:** only one agent may edit a given file or public façade at a time. Read-only reviewers may work concurrently. Test agents may run concurrently only under the resource policy below.

### 15.9 Package lifecycle

Every executable package follows this state machine:

```text
proposed
  -> researched
  -> decision_ready
  -> ready
  -> implementing
  -> author_verified
  -> independent_review
  -> correction (zero or more loops)
  -> integration_verified
  -> done
```

#### Gate 0 — Ready check

- prerequisites and product decisions complete;
- exact suffix card exists;
- allowed/forbidden files defined;
- clean package worktree established;
- baseline commands and expected outcomes recorded;
- reviewer and test shard assigned;
- no overlap with another writer.

#### Gate 1 — Characterization

The implementer or a prior researcher proves current behavior, imports, persisted fixtures, and compatibility seams. If the baseline is red, stop and classify it before editing.

#### Gate 2 — Implementation

The implementer makes the smallest complete architectural change that achieves the package outcome. “Smallest complete” means no half-migrated second authority, not the fewest changed lines.

#### Gate 3 — Author verification

Run syntax/import checks and focused tests only. The author records exact commands, pass/fail counts, duration, skipped tests, and environment caveats.

#### Gate 4 — Independent review

The reviewer reads the plan card, baseline, and diff. Blocking findings return the package to correction. Test changes receive special scrutiny: behavior expectations may change only when the package includes an approved contract decision.

#### Gate 5 — Adjacent verification

After review is clean, the verifier runs the adjacent subsystem shard. The author should not pre-emptively run every adjacent or full suite.

#### Gate 6 — Completion receipt

The manager checks scope, tests, review resolution, compatibility ledger, rollback, and commit. Only then mark the package done and unblock dependants.

### 15.10 Review depth by risk

| Risk | Examples | Required review |
|---|---|---|
| Low | docs/status, generated-zone classification, leaf helper extraction with byte parity | implementer self-check + manager diff review |
| Medium | cohesive module extraction with stable façade, listener ownership, route registration split | independent architecture reviewer + focused/adjacent tests |
| High | persisted session/transaction authority, wire/generated contracts, hashes/identity, schema precedence, emitter socket/refusal behavior, graph mutation, shim/route removal | independent domain reviewer + compatibility reviewer or explicit second-pass checklist + wave integration gate |

High-risk packages include at least `C10`–`C13`, `A21`–`A26`, `B34`/`B35`/`B38`, `F42`–`F46`, `G53`/`G55`/`G58`–`G60`, `E60`–`E63`, `S74`, and `S77`.

Reviewers must answer:

1. What became the single owner?
2. Which old owner stopped owning behavior?
3. Are old and new paths accidentally both live?
4. Did import direction improve?
5. Did any compatibility surface change?
6. Did any test get weaker or more implementation-specific?
7. Are failure/refusal paths still fail closed?
8. Can the package be reverted independently?

### 15.10A Review difficulty legend and XHARD-review protocol

- **Ordinary package review:** bounded diff review by a read-only reviewer; Luna is the default for inventories, implementation, focused verification, and bounded domain review. It does not require Sol escalation.
- **`[XHARD-REVIEW]`:** an integration review that requires big-picture architectural judgment across authorities, compatibility, persistence, served code, or migration gates. It is distinct from `[XHARD]` implementation and must not be attached to an ordinary package diff review or verifier test run.
- Every `[XHARD-REVIEW]` reviewer must be an independent GPT-5.6 Sol reviewer who did not implement or manage the reviewed chunk. The Sol reviewer consumes package receipts, the compatibility/authority ledgers, focused and adjacent evidence, and the relevant integration receipts.
- Every `[XHARD-REVIEW]` returns exactly one verdict: `continue`, `correct`, `replan`, or `stop`, with blocking evidence and the smallest required next gate. A green test alone is never a verdict.

### 15.11 Chunk-level review milestones

Do not wait until the end to discover architectural drift. Pause for an integration review at these seams:

| Review | Class | When | Independent reviewer and inputs | Required verdict question |
|---|---|---|---|---|
| `CR-0A` | `[XHARD-REVIEW]` | Immediately after `P00A`, before P01–P03 | GPT-5.6 Sol not involved in integration management; preservation receipts, dirty-path ledger, package status table, and clean-base recommendation | Is provenance/ownership frozen without discarding live work? |
| `CR-0` | ordinary integration review | After `P00`–`P03` | Read-only reviewer; worktree ledger, authority ledger, baseline receipts | Is the base/worktree safe and are baselines trustworthy? |
| `CR-1` | ordinary integration review | After `C10`–`C13` | Domain reviewer; focused correctness/performance receipts | Are known failures resolved without hiding them? |
| `CR-2` | `[XHARD-REVIEW]` | After `A20`–`A26`, `B30`–`B33`, `F40`–`F42`, `G50`–`G53` | Independent GPT-5.6 Sol; authority/compatibility ledgers, generated parity, schema/widget, graph/browser and focused/adjacent receipts | Are cross-language and graph/browser authorities coherent before movement? |
| `CR-3` | `[XHARD-REVIEW]` | After `B34`–`B39` | Independent GPT-5.6 Sol; lifecycle-log/transaction receipts, V1/V2 fixtures, CAS/replay tests, façade ledger | Is session/transaction authority independent and are façades dependency-correct? |
| `CR-4` | `[XHARD-REVIEW]` | After `F43`–`F48` | Independent GPT-5.6 Sol; frontend state/served-code ledger, browser ownership/rehydration/closure and adjacent receipts | Is there one frontend state/effect/render path with safe served-code behavior? |
| `CR-5` | `[XHARD-REVIEW]` | After `G54`–`G63` | Independent GPT-5.6 Sol; graph/IR/hash/emitter/refusal ledgers, golden/parity tests, MIG receipts | Are graph facts, layout, schema, emitter refusal, and migration gates coherent? |
| `CR-6` | `[XHARD-REVIEW]` | After `E60`–`E64` | Independent GPT-5.6 Sol; phase contracts, host-boundary/import receipts, durable handoff and adjacent tests | Is executor core headless, phase-typed, and durably handed off? |
| `CR-7` | `[XHARD-REVIEW]` | Before `S71`–`S78` deletion work | Independent GPT-5.6 Sol; complete shim/compatibility ledger, consumer census, persisted/served evidence, rollback receipts | Are all shims classified and removal conditions actually satisfied? |
| `CR-8` | `[XHARD-REVIEW]` | Before `R82` | Independent GPT-5.6 Sol; all wave receipts, authority/compatibility ledgers, queue and final integration evidence | Is the final architecture/queue coherent enough for rescan? |

Each chunk review uses the named reviewer class and produces the required verdict. `[XHARD-REVIEW]` cannot be performed by the package author, package manager, or ordinary verifier.

### 15.12 Test sharding and resource policy

The objective is strong coverage without every agent running the full suite.

#### Implementer shard

Run:

- syntax/compile/import checks relevant to changed files;
- the smallest focused tests that directly prove the package;
- targeted new characterization tests.

Target runtime: ideally under five minutes; split large commands where failure localization improves.

#### Reviewer/adjacent shard

After the diff is accepted, a separate verifier runs tests for immediate consumers and public façades. Target runtime: under fifteen minutes where practical.

#### Wave shard

Run once after a coherent group, not after every package:

- backend session/routes wave;
- frontend browser-contract/smoke wave;
- graph/schema/emitter/reorganise wave;
- executor wave;
- shim/fresh-process/generated wave.

#### Full suite

Run only:

- at explicitly named high-risk integration milestones if justified;
- before final rescan/release;
- after any change with genuinely repository-wide contract impact.

Do not make every implementer wait for or rerun it.

#### Host resource limits

- at most one broad Python suite at a time;
- at most two focused CPU-heavy suites concurrently when they use separate temp/cache directories;
- do not run broad browser, full Python, schema benchmarks, and GPU/live tests together;
- serialize tests that share object-info caches, generated outputs, ComfyUI ports, browser profiles, or persisted fixtures;
- record host load/process count for timeout/performance classifications;
- terminate or defer a redundant test shard through the manager, not ad hoc by another agent.

#### Failure classification

Every red result is classified as:

- introduced regression;
- reproduced baseline failure;
- unrelated concurrent change;
- environment/resource failure;
- flaky/undetermined.

Only the first category automatically blocks on code. Flaky or environmental classifications require evidence and a bounded rerun; they may not be silently ignored.

### 15.13 Decision gates requiring human/architecture-owner judgment

Subagents may research and recommend, but must not silently choose:

- `D01` — preview canvas-only versus canvas+DOM chips (`F41`);
- `D02` — any future change from the integrated canonical `16384` runtime token default (`C12`);
- `D03` — whether committed `WIDGET_SCHEMA` remains authoritative curated evidence (`G53a`);
- `D04` — removal window for accept/finalize and other deployed route bridges (`S74`);
- `D05` — long-term furniture carrier at the IR/reorganise boundary (`G50`/`G63`);
- `D06` — any public façade, route, field, persisted format, or browser mirror removal;
- `D07` — any semantic hash replacement rather than compatibility naming/extraction (`G55`).

The decision record must name the owner, rationale, alternatives rejected, compatibility impact, and packages unblocked.

### 15.14 Implementer dispatch template

```text
Role: implementation agent
Package: <exact suffix ID>
Author: <implementer identity>
Bounded reviewer: <independent read-only reviewer; not the author>
Verifier: <adjacent/wave test verifier; not the author for high-risk work>
Sol manager: <GPT-5.6 Sol manager/validator when the package is `[XHARD]`; otherwise named program manager>
Independent Sol XHARD reviewer: <required only at a named `[XHARD-REVIEW]` gate; must not implement or manage the chunk>
Plan sections to read: <links/headings>
Goal: <one measurable outcome>
Prerequisites/decisions: <completed IDs>
Allowed files: <exact list>
Forbidden files/zones: <exact list>
Compatibility surfaces: <imports/routes/fields/formats/exports>
Baseline commands/results: <exact receipt>
Required focused tests: <exact commands and expected result>
Do not: broaden scope, run full suite, edit generated output, change unrelated tests,
commit, or touch concurrent work unless the package card explicitly authorizes it.
Return: changed files, concise design summary, exact tests/results/durations,
remaining risks, and any blocker. Do not declare completion.
```

### 15.15 Reviewer dispatch template

```text
Role: independent read-only reviewer
Package: <exact suffix ID>
Author: <implementer identity>
Bounded reviewer: <your identity; independent of author>
Verifier: <adjacent/wave verifier identity>
Sol manager: <package manager/validator identity>
Independent Sol XHARD reviewer: <identity at the named `[XHARD-REVIEW]` gate, or `not applicable` for bounded review>
Read: package card, baseline receipt, diff, compatibility ledger entries
Review for: goal completion, single ownership, dependency direction, behavior/wire/
persistence/hash/import compatibility, test quality, scope creep, rollback.
Classify findings: blocking | non-blocking | question.
Do not edit or run the full suite.
Return: verdict (accept/correct/replan/stop), evidence with file:line, and the smallest
required correction/test set.
```

For a named `[XHARD-REVIEW]`, dispatch a separate read-only GPT-5.6 Sol reviewer with the author, bounded reviewer, verifier, and Sol manager identities recorded. The XHARD reviewer must consume the package receipts plus authority/compatibility ledgers and focused/adjacent evidence, then return `continue`, `correct`, `replan`, or `stop`. Luna remains the default for ordinary inventories, implementation, focused verification, and bounded review.

## 16. Risk register

Initial high-risk items:

| Risk | Why it matters | Default mitigation |
|---|---|---|
| Persisted-session incompatibility | Existing users may lose recovery or transaction history | Fixture parity and no schema movement during structural packages |
| Compatibility-wrapper explosion | File splitting can increase indirection without reducing coupling | Every wrapper needs an owner and removal condition |
| Import-order regression | Runtime environment hydration and ComfyUI registration have side effects | Fresh-process import tests before and after each boundary change |
| Dual graph authority | Raw UI, API JSON, and IR can silently disagree | Authority ledger and boundary validation before projection |
| Frontend split-brain state | Lifecycle, panel state, and DOM can independently claim truth | One transition owner and render-only view models |
| Static tests preserve accidents | AST/source-text tests can block healthy movement | Replace with behavior/import/packaging tests where possible |
| Generated code consumes cleanup effort | Giant mirrored registries may be mistaken for authored design debt | Zone classification before scoring or refactoring |
| Resource-contention false failures | Concurrent test load can cause timeouts unrelated to a change | Record CPU and wall time; rerun exact failures under bounded load |

## 17. Desloppify queue and rescan protocol

Use one honest `scan -> triage -> execute complete queue -> rescan` cycle.

### R80 — Establish or reconcile the baseline

**Estimate:** 0.5 day
**Prerequisites:** `P00`, approved clean worktree

Before scanning, record Desloppify version, commit, worktree status, scope/options, exclusions, zone classifications, and existing `.desloppify` state ownership.

If an existing queue is active, reconcile completed cleanup work with it first. Do not overwrite state merely to get a fresh score. A new baseline is appropriate only when the previous queue is complete or when tool version, scope, or exclusions have materially changed.

Never delete `.desloppify` state, locks, backups, progression files, or scan receipts as presumed cleanup debris. Reconcile or archive them only through an explicitly authorized state-migration step.

### R81 — Triage and execute the approved queue

**Estimate:** planning 0.5–1 day; execution is the sum of approved packages
**Prerequisite:** `R80`

`R81` is a planning/triage umbrella, not one executable implementation package. Actual work is performed only through separately sized package cards from Waves 1–7.

Assign every finding one status:

- confirmed defect;
- intentional compatibility;
- generated/vendor/cache;
- duplicate finding;
- needs evidence.

Map confirmed findings to stable package IDs, owners, allowed files, prerequisites, tests, and rollback instructions. Resolve findings only with the attestation/evidence required by `desloppify next`.

Do not rescan after each commit. Detector churn and cascades are expected; finish the approved queue first.

### R82 — Final rescan and subjective review

**Estimate:** 1 day plus review runtime
**Prerequisites:** every approved implementation/shim/test package complete; wave gates green

Run the final scan and unbiased subjective review only after:

- focused and adjacent tests pass;
- generated/config validation is complete;
- compatibility and authority ledgers match the code;
- docs are current;
- no cleanup-owned uncommitted changes remain.

Report overall, strict, objective, and verified scores honestly. New findings become the next triage cycle rather than being hidden or rushed into the completed queue.

## 18. Prior-plan disposition

Existing documents remain evidence, not automatic instructions.

| Prior material | Current disposition |
|---|---|
| `structural-smell-swarm-findings-2026-07-09.md` | Useful evidence; source-string edit assembly is resolved, session façade dependency remains partially resolved |
| `deeper-badness-greenfield-swarm-2026-07-09.md` | Retain its warning against line-count-only splitting; revalidate historical failure claims |
| frontend split-brain and overlay plans | Mixed: single overlay ownership is partly resolved, but “DOM chips removed” conflicts with current code/tests |
| `canonical-graph-elegance-plan.md` | Largely landed architectural law; retain named ingest, serialized IR envelope, and lossy compile principles |
| `ir-everywhere-migration.md` | Active constraint; blocks deletion of raw-UI/edit compatibility paths before milestones land |
| `threaded-staged-pipeline-integration.md` | Treat as active/concurrent until ownership is confirmed; preserve one graph/edit/delta/renderer/lifecycle laws |
| loose-work consolidation records | Historical; current dirty tree and worktrees require a new ownership ledger |
| technical-debt megaplan/area digest | Useful batch protocol and generated-code classification; verify item status against current code |

Also reconcile historical `execution-log.md` and `resolutions-digest.md` records. A prior `PASS` means “recorded historically” until reproduced on the approved base; it does not prove the current dirty checkout is clean.

Each recommendation copied into an implementation package must be labelled `current`, `partially resolved`, `resolved`, `superseded`, `blocked`, or `intentional` with present-code evidence.

## 19. Definition of done

The program is complete only when:

- the implementation queue is empty;
- every package has focused and adjacent regression evidence;
- persisted V1/V2 fixtures remain readable;
- public route, Python import, JavaScript export, and response-field compatibility is proven;
- CLI/porting public imports and supported monkeypatch seams are proven;
- generated Python `.py`/`.pyi` inventory and generated JavaScript contract parity are proven from their generators;
- extension/global installer behavior is idempotent and safe across replacement/reload;
- cross-layer import rules pass in fresh processes;
- graph and transaction authority ledgers match actual code;
- compatibility façades contain no unclassified wrappers;
- generated/vendor/cache zones are correctly configured;
- known correctness failures are resolved or explicitly deferred with evidence;
- a full Desloppify scan and unbiased subjective review have been performed **after**, not during, queue execution;
- strict-score changes are reported honestly, including any remaining accepted debt.

## 20. Planning status

- Backend/agent/executor research: integrated.
- Frontend research: integrated.
- Graph/porting/schema research: integrated.
- Integration/test-program review: integrated.
- Repository-wide shim research census: integrated; executable file/line ledger `S70` remains a required pre-mutation package.
- Independent clarity, frontend, graph/migration, shim, and execution-readiness reviews: integrated.
- Plain-language architectural and contributor end-state: integrated.
- `[XHARD]` classification, GPT-5.6 Sol ownership, and decision/review gates: integrated for 23 execution units, including P00A.
- `[XHARD-REVIEW]` governance: CR-0A independently returned `continue` for both the corrected reconciliation and the later tree-identical PR156-tip provenance recheck. CR-2 through CR-8 are execution-time gates; ordinary package reviews and verifier runs remain distinct.
- Agent roles, independent review loops, chunk gates, test sharding, resource limits, and dispatch templates: integrated.
- Cleanup execution: **not authorized and not started**.
