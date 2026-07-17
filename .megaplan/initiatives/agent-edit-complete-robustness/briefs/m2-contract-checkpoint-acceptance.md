# M2 C0–C1 Contract Checkpoint — Executable Acceptance Checklist

Status: **ACCEPTED 2026-07-17.** Acceptance companion to
`m2-contract-checkpoint.md`. This checklist accepts C0 contracts and C1 private
plan proof only. It does not authorize C2, native execution, consumer
rerouting, ledger transfer, or an S3/S4 completion claim. The scheduler
activation fence recorded below is an adjacent panel-lifecycle safety repair,
not native-mutation cutover evidence.

## Acceptance boundary

- [ ] C0 changes only the two cross-language contracts, shared goldens,
      authority/restoration binding, the Python hash-leaf relocation, and
      their tests.
- [ ] C1 adds only the private pure plan builder, independently owned sentinel
      test instrumentation, and static ownership tests.
- [ ] C1 performs zero graph acquisition, native construction, mutation,
      serialization, repaint, inverse execution, or compensation—including in
      its harness.
- [ ] No public adapter mutation API, production consumer import, routing
      change, native-authority ledger transfer/reclassification, or
      ownership-complete wording lands.
- [ ] `comfy_adapter.js`, `vibecomfy_roundtrip.js`, `preview_picker.js`,
      `agentic_replay.js`, scope/lifecycle owners, and real ComfyUI integration
      remain outside this checkpoint except for read-only static inventory.

## Acceptance hazards that must be resolved explicitly

### Candidate-graph guard scope

The implementation spec simultaneously says that C0/C1 leave the legacy
`comfy_adapter.js` candidate-driven paths unchanged and that C1 fails if
`candidateGraph` appears in *any* preflight/apply signature. Both cannot be
true in the current tree: `preflightDeltaPlan`, `applyGraphDeltaInPlace`, and
`applyGraphLayoutInPlace` already accept it.

For this bounded checkpoint the executable interpretation is:

- [ ] New C0 contract modules and the C1 private builder contain no
      `candidateGraph`/`candidate_graph`, graph payload, or graph reference.
- [ ] The private builder accepts prepared authority only.
- [ ] No new preflight/apply/restore/inverse function or signature anywhere
      accepts candidate graph data.
- [ ] A static test freezes the exact pre-existing legacy occurrences in
      `comfy_adapter.js` as C2 deletion debt and fails on any addition, rename,
      copy, wrapper, re-export, or occurrence outside that allowlist.
- [ ] Preview-only/UI uses of candidate graphs are not falsely classified as
      native mutation authority.
- [ ] If acceptance instead requires repository-wide zero candidate-graph
      mutation signatures, stop: that is C2 consumer rerouting and contradicts
      the C0/C1 boundary. Amend the implementation spec before proceeding.

### Sentinel proof ownership

A `sentinelCounts` object manufactured and returned by the plan builder is
self-attestation, not evidence that native boundaries were untouched.

- [ ] Sentinel counters are owned by the test harness outside the builder.
- [ ] The test passes only pure validators/hash dependencies to the builder;
      it never passes a live graph, app, canvas, LiteGraph factory, or native
      callback.
- [ ] Static import guards independently prove the builder cannot reach native
      modules.
- [ ] If the builder returns a diagnostic counter mirror, tests compare it to
      the independent harness counters; the returned object is never the sole
      zero-write proof.

### Restoration `ref` and closed-key ambiguity

The spec freezes new restoration tags to payload-only closed keys while also
saying the legacy journal-reference path may retain `ref`.

- [ ] Before implementation, freeze the exact legacy tag(s) allowed to use
      `{contract_version,digest,ref}` and the exact new tags required to use
      `{contract_version,digest,payload}`.
- [ ] New `inverse_delta_v1` and `inverse_layout_operation_v1` never accept
      `ref`; legacy tags never become an escape hatch for the new contracts.
- [ ] JS and Python share positive legacy-preservation and negative mixed-key
      cases. If the allowed legacy tags cannot be named, stop and amend the
      implementation spec rather than weakening the closed schema.

### Plan-builder hash dependency name

The proposed injected name `canonicalHash` is not an export of
`canonical_hash.js`.

- [ ] Freeze an injection shape using the existing owner exports (for example,
      the exact `sha256Hex`/canonical-string primitives actually required).
- [ ] Do not add a second wrapper or new hash owner merely to satisfy the
      placeholder dependency name.

### Regression provenance and ambiguous negative codes

- [ ] Derive the regression ops directly from the tracked
      `tests/fixtures/agent_edit/a66422e6_layout_regression.json`; do not create
      a second hand-written copy of its geometry.
- [ ] Freeze one exact diagnostic for an out-of-range materialization index;
      the source brief names the condition but not its code.
- [ ] Remove the stale “item 6 reconciliation” reference or bind it to a real
      numbered invariant before acceptance evidence cites it.

Provenance clarification (2026-07-17):

- The fixture is 3,569 raw bytes. In the current branch lineage it was added by
  `070a672d4090dd34bb663a061b781f6af1e72700`; the identical blob also exists
  in the earlier non-ancestor megaplan publication commit
  `c676cbde4d31d12916f428c88de1228d2d7b4dc7`.
- `shasum -a 256 tests/fixtures/agent_edit/a66422e6_layout_regression.json`
  hashes those exact raw bytes and returns
  `09e01de2c658b33180d9836db2d925a208459cff970cb7b2aa9ae7442edd0534`.
- That value is **only the raw-file integrity hash**. It is not an expected
  structural projection, layout projection, or `layout_operation_v1`
  envelope digest and is not an implementation blocker.
- Current browser projection-registry hashes (SHA-256 over
  `canonicalSessionJsonString(build*GraphProjection(...))`) are independently
  `2bf4f6b53ac2e8d575c7d5739a1b1b143e3b1709cb61503f4523bf759bad2906`
  for both original/candidate structural projections,
  `23034668582d39c60d08b69d1348362b798c1b03ce9e625017bbbfa4daf74c4f`
  for the original layout projection, and
  `55c7c038c74ead4227f69944b156f4c569fb9a386ed11579d2a227ebe73e4d3f`
  for both candidate/native-normalized layout projections. The new layout-op
  golden must compute and store its own digest through the shared contract
  owner; it must not reuse any of these hashes across digest domains.

## C0 file and API inventory

### New owners and shared fixtures

- [ ] `vibecomfy/comfy_nodes/web/layout_operation_v1.js`
- [ ] `vibecomfy/comfy_nodes/agent/layout_operation_v1.py`
- [ ] `vibecomfy/comfy_nodes/web/mutation_materialization_v1.js`
- [ ] `vibecomfy/comfy_nodes/agent/mutation_materialization_v1.py`
- [ ] `vibecomfy/comfy_nodes/agent/_canonical_contract_primitives.py`
- [ ] `tests/fixtures/agent_edit/layout_operation_golden_v1.json`
- [ ] `tests/fixtures/agent_edit/mutation_materialization_golden_v1.json`
- [ ] Mirrored JS/Python tests load the same golden files; neither language
      carries a private copy of expected envelopes, digests, or diagnostic
      codes.

### Existing owners extended, never forked

- [ ] JS authority validation remains solely in `prepared_authority_v1.js`.
- [ ] Python authority validation remains solely in
      `projection_registry_v1.py`.
- [ ] `candidate_transaction.py` mints but does not validate a second schema.
- [ ] Canonical delta remains solely in `canonical_delta.js` and
      `porting/edit/ops.py`.
- [ ] Projection/identity/field meaning remains solely in the two projection
      registries.
- [ ] Restoration validation extends the existing authority validators; no
      second restoration owner appears.

## `layout_operation_v1` parity

### Frozen envelope and exports

- [ ] JS/Python constants are exactly `layout_operation_v1`, wire `1.0.0`,
      and the ordered four-op set below.
- [ ] Envelope keys are exactly `contract_version, wire_version, ops, digest`.
- [ ] Digest is the shared canonical hash of
      `{contract_version, wire_version, ops}` and is identical in JS/Python.
- [ ] Normalizers and asserters return deeply immutable/detached values; input
      mutation after validation cannot mutate the result.
- [ ] JS exports only the specified constants, error, normalize, compute,
      assert, and optional frozen default facade. Python mirrors them in
      snake_case.

### The four operations

- [ ] `set_node_geometry`: non-empty stable `uid`, finite `pos[2]`, optional
      finite `size[2]`, closed keys.
- [ ] `add_group`: non-empty stable `id`, finite `bounding[4]`, string `title`,
      string-or-null `color`, closed keys.
- [ ] `set_group_geometry`: stable `id` plus at least one of
      `bounding/title/color`, using the same types and closed keys.
- [ ] `remove_group`: stable `id` only.
- [ ] No title, native ID, position, class, or array index is accepted as
      identity.
- [ ] Duplicate group titles with distinct stable IDs are valid.

### Shared positive corpus

- [ ] Pos-only node geometry.
- [ ] Pos+size node geometry.
- [ ] Full group add and color-null group add.
- [ ] Group bounding-only, title-only, and color-only updates.
- [ ] Group removal.
- [ ] One ordered sequence mixing all four operations.
- [ ] Duplicate-title group additions with distinct IDs.
- [ ] `a66422e6_layout_regression.json` geometry is reduced to ops directly
      from the tracked fixture, without title matching or a second copied
      geometry corpus.
- [ ] For every case, both languages equal the golden normalized envelope and
      exact lowercase hex64 digest.

## `mutation_materialization_v1` parity

### Frozen envelope and singleton grammar

- [ ] Contract/wire are exactly `mutation_materialization_v1` / `1.0.0`.
- [ ] Envelope keys are exactly
      `contract_version, wire_version, entries, digest`.
- [ ] `MATERIALIZATION_KINDS` is the singleton frozen set/tuple `add_node`.
- [ ] Entry keys are exactly `source_op_index, kind, widgets_values, pos,
      size, opaque`; optional values obey the specified JSON-object and finite
      geometry rules.
- [ ] Entries never duplicate `uid`, `node_id`, `class_type`, `fields`,
      `inputs`, or links already authoritative in the delta.
- [ ] `opaque` round-trips unchanged and remains uninterpreted.

### Exact forward binding

- [ ] Every forward `add_node` op has exactly one entry bound to its exact
      zero-based source-op index.
- [ ] Every entry resolves to an `add_node`; non-add ops have no entries.
- [ ] Interleaving add/link/field/mode/remove ops does not shift or infer
      bindings.
- [ ] Two `add_node` ops require two distinct entries.
- [ ] No materialization entry can add an implicit link; all topology remains
      explicit canonical delta input/upsert/remove data.

### Exact inverse binding

- [ ] The same validator accepts an inverse delta whose own ops contain an
      `add_node` re-creating a forward-removed node.
- [ ] Its entry indexes the inverse ops, not the forward ops.
- [ ] No `remove_node_inverse` or inverse-only materialization kind exists.
- [ ] Forward and inverse envelope digests are independently computed and
      independently bound to their accompanying ops.

## Prepared authority, digest, and compensation parity

### Operation-family binding

- [ ] Layout authority has empty structural ops, a validated layout envelope,
      matching layout digest, layout projections, and equal structural witness.
- [ ] Structural authority rejects any layout envelope.
- [ ] Structural authority requires materialization iff forward ops contain at
      least one `add_node`; envelope and digest presence are paired.
- [ ] Layout authority rejects mutation materialization.
- [ ] Whole-operation deep equality makes nested layout/materialization fields
      immutable across candidate→prepared.

### Mandatory restoration

- [ ] Structural family binds `inverse_delta_v1` with closed payload
      `ops, mutation_materialization, mutation_materialization_digest`.
- [ ] Inverse materialization/digest are present iff inverse ops contain
      `add_node` and are cross-bound against those inverse ops.
- [ ] Layout family binds `inverse_layout_operation_v1` with closed payload
      `layout_operation, layout_operation_digest`.
- [ ] Restoration tag matches operation family.
- [ ] Restoration digest is the canonical hash of
      `{contract_version, payload}` in both languages.
- [ ] A cloned forward operation cannot pass as its own inverse.

### Optional compensation

- [ ] Compensation contract is only `baseline_snapshot_v1`, with closed
      payload keys `scope, projection, original_ref, original_digest,
      identity_fence, projection_fence`.
- [ ] It cannot exist without mandatory inverse restoration.
- [ ] Root scope, projection family, transaction/candidate IDs, generation,
      identity fence, hex64 original digest, and projection fences are bound.
- [ ] Compensation digest is canonical and byte-identical in JS/Python.
- [ ] Candidate→prepared presence parity is exact: absent remains absent;
      present remains byte-identical.
- [ ] `restoration_strategy_compensation` is the only new top-level transition
      equality key; no redundant nested keys are added.
- [ ] The complete transition key list is identical and ordered/documented in
      both validators.

## Shared fail-closed matrix

Every invalid case below must produce the exact code in JS and Python. C1 must
return the same code before all independently owned sentinel counters remain
zero.

| Invalid condition | Exact code |
| --- | --- |
| Unknown contract | `unknown_contract` |
| Unknown wire version | `unsupported_wire_version` |
| Extra/malformed layout envelope | `malformed_layout_operation` |
| Extra/malformed layout op | `malformed_layout_op` |
| Unknown layout op | `unsupported_layout_op` |
| Extra/malformed materialization envelope | `malformed_materialization` |
| Extra/forbidden materialization entry key | `malformed_materialization_entry` |
| Non-`add_node` kind | `unsupported_materialization_kind` |
| Unknown operation family | `unknown_operation_family` |
| Unknown projection | `unknown_projection_version` |
| Unknown authority version | `unknown_authority_version` |
| Non-root/nested scope or definitions | `unsupported_scope` |
| Missing stable node/group ID | `missing_identity` |
| Duplicate stable identity where uniqueness is required | `duplicate_identity` |
| Non-finite geometry | `non_finite_geometry` |
| Layout digest mismatch | `layout_operation_digest_mismatch` |
| Materialization digest mismatch | `mutation_materialization_digest_mismatch` |
| Restoration digest mismatch | `restoration_digest_mismatch` |
| Unreferenced materialization entry | `unreferenced_materialization_entry` |
| Missing entry for `add_node` | `missing_materialization_entry` |
| Duplicate source-op index | `duplicate_materialization_source_op` |
| Index targets a non-`add_node` op | `materialization_source_op_kind_mismatch` |
| Layout family has structural ops | `layout_family_requires_empty_structural_ops` |
| Structural family has layout envelope | `unexpected_layout_operation` |
| Forward `add_node` lacks materialization | `missing_materialization` |
| No forward `add_node` but materialization exists | `unexpected_materialization` |
| Layout structural witness differs | `layout_structural_witness_mismatch` |
| Candidate→prepared authority changes/presence drift | `prepared_authority_transition_mismatch` |
| Forward operation reused as inverse | `invalid_inverse_strategy` |
| Unknown restoration tag | `unknown_restoration_strategy` |
| Restoration family mismatch | `restoration_family_mismatch` |
| Missing/extra restoration payload key | `malformed_restoration_payload` |
| Unauthorized/mismatched compensation | `unauthorized_restoration` |
| Forbidden `workflow_v1` | `forbidden_projection` |

Additionally:

- [ ] Duplicate titles are a positive case, never `duplicate_identity`.
- [ ] Out-of-range materialization indexes have one frozen exact diagnostic;
      if the implementation spec does not distinguish it from kind mismatch or
      unreferenced entry, the golden must pin the chosen existing code before
      implementation proceeds.
- [ ] NaN/Infinity fixtures use a representation both JSON readers can load
      deterministically (or are constructed in mirrored test code); invalid
      JSON tokens are not treated as a cross-language golden.
- [ ] All failures occur before native acquisition as well as before mutation.

## Python hash-leaf identity and cycle proof

- [ ] `_canonical_contract_primitives.py` imports no module beneath
      `vibecomfy.comfy_nodes.agent` and contains no contract-validator imports.
- [ ] The leaf owns exactly `ContractError`, `canonical_json`,
      `canonical_json_bytes_v1`, `_hash`, and `_order_json_objects_utf16` moved
      without behavior change.
- [ ] `projection_registry_v1.py` imports and re-exports those same objects;
      identity (`is`), not merely equivalent output, is asserted for all five.
- [ ] Both new Python contract modules import primitives from the leaf, never
      from `projection_registry_v1.py`.
- [ ] Importing in each order—registry first, layout first, materialization
      first, candidate transaction first—succeeds in fresh interpreters.
- [ ] Repeated imports preserve object identity and do not partially initialize
      any validator.
- [ ] Existing canonical JSON/hash golden and authority-receipt tests remain
      byte-identical.

Required fresh-process smoke:

```bash
python - <<'PY'
from vibecomfy.comfy_nodes.agent import _canonical_contract_primitives as leaf
from vibecomfy.comfy_nodes.agent import projection_registry_v1 as registry
assert registry.ContractError is leaf.ContractError
assert registry.canonical_json is leaf.canonical_json
assert registry.canonical_json_bytes_v1 is leaf.canonical_json_bytes_v1
assert registry._hash is leaf._hash
assert registry._order_json_objects_utf16 is leaf._order_json_objects_utf16
from vibecomfy.comfy_nodes.agent import layout_operation_v1
from vibecomfy.comfy_nodes.agent import mutation_materialization_v1
from vibecomfy.comfy_nodes.agent import candidate_transaction
PY

for first in \
  vibecomfy.comfy_nodes.agent.projection_registry_v1 \
  vibecomfy.comfy_nodes.agent.layout_operation_v1 \
  vibecomfy.comfy_nodes.agent.mutation_materialization_v1 \
  vibecomfy.comfy_nodes.agent.candidate_transaction; do
  python -c "import importlib; importlib.import_module('$first'); importlib.import_module('vibecomfy.comfy_nodes.agent.projection_registry_v1'); importlib.import_module('vibecomfy.comfy_nodes.agent.layout_operation_v1'); importlib.import_module('vibecomfy.comfy_nodes.agent.mutation_materialization_v1')"
done
```

## C1 independent zero-native-call proof

### Private builder

- [ ] `_prepared_plan_builder_v1.mjs` exports only `buildPreparedPlan` and is
      not re-exported by an index/facade.
- [ ] Its input is prepared authority plus pure validator/hash dependencies;
      no candidate graph, app, canvas, graph, node, group, LiteGraph, DOM, or
      runtime callback enters.
- [ ] It imports no `comfy_adapter`, `intent_graph_adapter`, roundtrip, picker,
      replay, scope, lifecycle, panel, or harness module.
- [ ] It validates already-bound forward, inverse, restoration, and optional
      compensation digests; it does not mint an inverse from live state.
- [ ] Its plan and every nested value are frozen/detached.

### Independently owned sentinels

For every positive corpus case and every row in the fail-closed table, assert
zero calls at each boundary:

- [ ] graph/app/canvas acquisition;
- [ ] node factory/configure and group construct/configure;
- [ ] add/remove node and add/remove group;
- [ ] connect, removeLink, link-store/socket repair;
- [ ] widget, field, mode, socket, node geometry, and group geometry writes;
- [ ] `clear`, `configure`, `loadGraphData`, and any whole-graph replacement;
- [ ] native `serialize` or snapshot capture;
- [ ] graph revision/change notification;
- [ ] repaint/dirty/draw calls;
- [ ] inverse execution and compensation restore.

Each counter is initialized and asserted by the harness after the builder
returns or fails. A sentinel throw is itself a test failure: the required
count is zero, not “attempted and blocked.” No skipped sentinel is allowed.

## Static ownership and forbidden-path guards

- [ ] Exactly one JS and one Python layout contract owner.
- [ ] Exactly one JS and one Python materialization contract owner.
- [ ] Exactly the two existing prepared-authority validator owners.
- [ ] No ad-hoc `hashlib.sha256(json.dumps(...))`, `JSON.stringify` digest, or
      new canonical hash helper outside the declared owners.
- [ ] Python leaf dependency direction is enforced by AST/import test.
- [ ] No production module imports the private plan builder.
- [ ] No public export is added to `intent_graph_adapter.js` for preflight,
      apply, restore, inverse, mutation, factory, live lookup, or builder.
- [ ] New modules contain zero `candidateGraph`/`candidate_graph` references.
- [ ] A source-mapped legacy candidate-graph allowlist remains byte-for-byte
      stable and fails on new occurrences; it is labeled C2 debt, not C1
      success.
- [ ] C0 browser ownership guards live in and extend the existing
      `tests/browser/ownership_contract.test.mjs`; C1 private-builder and
      forbidden-signature guards live in
      `tests/browser/prepared_plan_builder_ownership_static.test.mjs`.
- [ ] Python leaf/hash/single-owner guards live in the focused Python contract
      suite (or a named `tests/test_contract_ownership_static.py` added to both
      focused and broad commands); they are not left as unaudited prose.
- [ ] No copied layout/materialization validation exists in
      `candidate_transaction.py` or the plan builder; both call the owners.
- [ ] No changes to the native-authority ledger claim row transfer or support.
- [ ] No C0/C1 prose says S3, S4, native ownership, rollback, or real-ComfyUI
      execution is complete.

## Focused proof commands

### C0 JavaScript

```bash
node --test \
  tests/browser/layout_operation_v1.test.mjs \
  tests/browser/mutation_materialization_v1.test.mjs \
  tests/browser/canonical_delta.test.mjs \
  tests/browser/m1_contracts.test.mjs \
  tests/browser/ownership_contract.test.mjs \
  tests/browser/frontend_ownership_regression.test.mjs
```

### C0 Python

```bash
python -m pytest -q \
  tests/test_layout_operation_v1.py \
  tests/test_mutation_materialization_v1.py \
  tests/test_m1_contracts.py \
  tests/test_candidate_transaction_layout_contract.py \
  tests/test_authority_receipts.py
```

### C1 private plan and ownership

```bash
node --test \
  tests/browser/prepared_plan_builder_v1.test.mjs \
  tests/browser/prepared_plan_builder_ownership_static.test.mjs
```

### Syntax, identity, and diff boundary

```bash
python -m compileall -q \
  vibecomfy/comfy_nodes/agent/_canonical_contract_primitives.py \
  vibecomfy/comfy_nodes/agent/layout_operation_v1.py \
  vibecomfy/comfy_nodes/agent/mutation_materialization_v1.py \
  vibecomfy/comfy_nodes/agent/projection_registry_v1.py \
  vibecomfy/comfy_nodes/agent/candidate_transaction.py

git diff --check
git diff --name-only
```

Record exact pass counts. Focused suites permit no new skip, xfail, todo, or
warning-based waiver.

## Broad regression commands

```bash
make browser-contracts
make browser-smoke
make fast
python -m tools.check_canonical_parity --all
node --test tests/browser/roundtrip_smoke.test.mjs
```

- [ ] Add the new pure browser contract and ownership tests to
      `BROWSER_CONTRACT_TESTS`; `make browser-contracts` must actually execute
      them rather than relying only on the explicit focused command.
- [ ] `make browser-smoke` runs every new browser test and has no new skip.
- [ ] `make fast` includes or is accompanied by the explicit new Python tests;
      do not assume a Makefile list contains them without checking collection.
- [ ] Record total passes, existing intentional skips, and duration for each
      broad command.

## Final C0 acceptance record

- [ ] Shared JS/Python goldens and digests are exact.
- [ ] Four layout ops and singleton materialization grammar are closed.
- [ ] Forward/inverse `add_node` bindings are exact and no implicit links exist.
- [ ] Authority, restoration, compensation, and transition parity are exact.
- [ ] Hash-leaf relocation is identity- and cycle-safe.
- [ ] No live behavior, public adapter API, consumer route, or ownership ledger
      changed.

## Final C1 acceptance record

- [ ] Private plan builder consumes prepared authority only.
- [ ] Independent counters prove zero acquisition/native/serialize/repaint/
      restore calls for every positive and invalid case.
- [ ] Frozen plans revalidate already-bound inverse/restoration digests only.
- [ ] Forbidden-path and single-owner static tests pass with the exact legacy
      C2 allowlist unchanged.
- [ ] C1 is recorded as private plan proof, not native execution or cutover.

## Non-exit statement

Passing this checklist does not transfer any of the 27 coupled S3 rows or the
seven S4 debt rows. It does not delete candidate-driven legacy paths, execute
native primitives, prove landed-prefix recovery, serialize after mutation,
execute inverse/compensation, repaint, route consumers, or prove real ComfyUI.
Those remain C2–C4 work.

## Accepted proof record — 2026-07-17

The executable checklist passed with the following final evidence:

- C0+C1 focused JavaScript: 156 passed, 0 failed, 0 skipped/todo.
- C0 focused Python: 118 passed, 0 failed; the only warning reports the local
  absence of optional `pytest-rerunfailures` and is unrelated to these tests.
- Four lifecycle compatibility suites: 294 passed.
- Harness dependency closure, legacy authority migration, inverse relation
  (including `inverse_delta_v2`), and M1 contract repair suites: 60 passed.
- `make browser-contracts`: 569 passed.
- `make browser-smoke`: 1,531 passed, 0 failed, 2 existing intentional skips.
- `node --test tests/browser/roundtrip_smoke.test.mjs`: 238 passed, 0 failed,
  2 existing intentional skips in two full-file repetitions.
- `make fast`: 584 passed, 1 existing intentional skip.
- Canonical parity: 64 templates; Arnold profile parsing: 68/68 specs.
- `git diff --check`, Python compilation/import identity, no missing staged JS
  dependency, no prepared-v0 path, shared numeric negatives, and exact
  operation order/no-dedup: passed.

The scheduler regression that previously allowed a departed panel's callback
to satisfy current-panel flush evidence is closed by a concrete
panel/workflow-activation fence and panel-affine diagnostics. Its two direct
activation-fence tests run under browser smoke, and the formerly failing race
passed in browser smoke plus both complete roundtrip repetitions.

Acceptance leaves the legacy C2 allowlist and machine ledger truthful. No
coupled S3 row or S4-debt row is transferred by this record.
