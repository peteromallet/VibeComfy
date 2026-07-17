# M2 C0–C1 contract-checkpoint adversarial gate

Status: **RESOLVED AND ACCEPTED 2026-07-17.** This pre-mortem's blockers were
converted into executable C0/C1 contracts, shared negative matrices, static
ownership/dependency guards, and compatibility tests. Subordinate to
`m2-native-adapter.md`, `m2-slices-3-4-implementation.md`, and
`m2-contract-checkpoint.md`.

## Dependency order and import direction

```text
JS canonical_hash.js                     Python _canonical_contract_primitives.py
        ↓                                      ↓
layout_operation_v1.js                   layout_operation_v1.py
mutation_materialization_v1.js           mutation_materialization_v1.py
        ↓                                      ↓
prepared_authority_v1.js                 projection_registry_v1.py
                                               ↓
                                        candidate_transaction.py
        ↓
_prepared_plan_builder_v1.mjs (C1 tests only; no production importer)
```

The Python leaf may import the standard library only. Contract modules import
the leaf, never the registry, candidate builder, adapter, or each other. The
registry imports the two contract validators; the aggregate builder imports
the registry and contract normalizers for minting. No reverse edge is allowed.
`projection_registry_v1.py` must re-export the exact relocated objects; tests
assert object identity as well as behavior and existing exception codes.

Implementation order is strict: canonical primitive relocation and regression
proof; layout grammar/golden; materialization grammar/golden; restoration and
prepared-authority binding; candidate transaction minting/parity; then the C1
private plan proof. No C1 code lands against a red or ambiguous C0.

## Contract blockers that must be resolved before implementation

1. **Geometry digests do not yet have a cross-language numeric contract.** JS
   uses `JSON.stringify` number spelling; Python uses `json.dumps`. They differ
   for `1.0`, `-0.0`, exponent thresholds, and some large/small doubles. Both
   also treat booleans differently during numeric/integer checks (`bool` is an
   `int` in Python). Define one JSON-number domain and canonical formatter,
   normalize negative zero, reject booleans, NaN and infinity before hashing,
   and prove boundary values in one shared golden. Key-order parity alone is
   insufficient.
2. **The materialization is index-bound but not operation-bound.** Its digest
   covers only `{contract_version, wire_version, entries}`. An entry at index 0
   can be transplanted between unrelated forward or inverse deltas whose index
   0 is `add_node`. Bind the envelope to the accompanying canonical delta
   digest, or bind every entry to a canonical source-op fingerprint. The
   validator must recompute that binding; array position plus `kind` is not
   enough.
3. **`widgets_values` is specified as an object although native ComfyUI
   serialization normally uses an array.** Freeze the actual supported wire
   shape from incident/native fixtures. If both representations are necessary,
   use an explicit tagged closed union; do not accept an untyped JSON value.
4. **Inverse validity is prose, not a grammar.** “A forward op cloned as its own
   inverse” is neither a complete nor reliable test. Define the exact causal
   inverse relation for all six structural and four layout operations,
   including ordering, removed-node links/materialization, group payloads, and
   no-op cases. Bind the inverse to the forward operation digest and
   precondition digest so a valid inverse cannot be replayed onto another
   candidate. C0 validates a supplied/built inverse; C1 never invents one.
5. **Compensation presence parity conflicts with prepare-time identity.** The
   candidate-time compensation payload is required to contain `lease_nonce`
   and `generation`, yet those are minted only by prepare and candidate
   authority explicitly may not infer them. Either bind a candidate-time
   compensation commitment that prepare seals with its new fence, or make the
   fenced compensation prepared-only and validate its derivation. Do not place
   guessed prepare identity inside candidate authority merely because it is
   nested.
6. **Operation schemas remain open.** Current canonical-delta validators check
   required fields but accept unknown per-op keys; authority `operation` and
   top-level envelopes also accept extras. That permits `candidateGraph`,
   `candidate_graph`, implicit links, or alternate values to ride beside the
   validated contract. Close the existing JS/Python delta op schemas in their
   current owners, and close authority/operation keys per family. Never create
   a second local allowlist in the new modules.
7. **`opaque` can become a mutation-language escape hatch.** It must remain a
   namespaced, uninterpreted extension payload and must never be spread/merged
   into a native node, plan entry, operation, link, or graph. Validate the
   strict JSON domain recursively; prohibit reserved construction/topology
   keys at its boundary or define a versioned extension namespace registry.
8. **Transition equality differs by language and does not prove presence
   parity.** JS `JSON.stringify` is key-order-sensitive; Python mapping equality
   is not. Both current `prepared.get(key)` styles equate absent and explicit
   null. Use the shared canonical representation for value equality and a
   separate own-key/presence check for every optional field.
9. **C1 has no frozen `PlanShape`.** Define its closed plan schema before
   coding: source op index/kind, stable identities/named endpoints, exact op
   values, materialization reference/fingerprint, and already-bound inverse/
   compensation references. It contains no candidate graph, native ID, live
   handle, factory, callback, or executable closure.
10. **Sentinel counts cannot be self-attested.** The builder must not return a
    hard-coded `sentinelCounts: 0`. Counters are owned by the external harness;
    tests snapshot them before/after calling the builder. Static imports also
    prove the builder has no app, DOM, LiteGraph, adapter, serialization, or
    mutation dependency.
11. **Receipt strings are not proof of nested integrity.** Current authority
    validation can accept a syntactically valid hex digest without recomputing
    every nested body it is supposed to attest. Layout, materialization,
    inverse, and compensation bodies must each be normalized and rehashed,
    then their outer duplicate digest/reference must be checked against that
    recomputation. A generic restoration `digest(payload|ref)` helper must not
    blur the distinct closed schemas for inverse payloads, compensation
    payloads, and legacy journal references.

## Non-negotiable schema and digest invariants

- Every envelope and nested op/payload has an exact key set. Missing, extra,
  explicit-null-when-absent, wrong type, and unknown enum are distinct tested
  refusals where the contract distinguishes them.
- Normalize first; digest exactly the returned normalized body excluding only
  its digest field. Validation recomputes from normalized data and returns the
  same recursively frozen/plain shape in JS and Python.
- All values are strict JSON: string keys, null/boolean/string/finite number,
  arrays, and plain mappings only. Reject undefined, functions, symbols,
  BigInt, tuples/sets/bytes, non-string mapping keys, cycles, custom objects,
  and non-finite numbers rather than applying language-specific string fallbacks.
- Contract hashes use the ASCII-safe canonical profile explicitly on both
  sides. Session/projection hashing's non-ASCII profile is not silently reused.
- Lowercase hex64 is required everywhere. A duplicate outer digest must equal
  the inner recomputed digest; there is never a “trusted provided digest.”
- Restoration payloads are closed by their discriminant. `payload` and `ref`
  are not interchangeable shapes, and a permissive shared digest helper is
  not a validator.
- The golden corpus stores normalized input/body, canonical JSON text or bytes,
  and expected digest so parity tests compare more than a final hex string.
- `source_op_index` is a non-negative safe integer, not boolean, and is checked
  against the exact bound forward or inverse op array. Entry order is either
  declared semantic and preserved, or normalized by index in both languages;
  it cannot remain unspecified.
- `node_id` is a construction token, not stable semantic identity. Only `uid`
  and stable group `id` cross identity boundaries; native IDs never become
  lookup fallback authority.

## CandidateGraph and native-write tripwires

C0/C1 production changes may not contain `candidateGraph`, `candidate_graph`,
`originalGraph`, graph snapshots, implicit `links`, or graph-derived values in
any contract/preflight/plan signature. Candidate preview evidence remains
outside authority. Static scans must follow aliases, destructuring, computed
properties, nested payload keys, object spread, and re-exports—not only exact
parameter names.

C1 imports only pure C0 owners and the canonical hash leaf. It performs no
graph acquisition, serialize/configure/load, factory call, add/remove/connect,
widget/socket/group/geometry assignment, revision, repaint, or callback
installation. The old production path remains untouched; no consumer imports
the private builder and no adapter public method is added.

## Adversarial golden and test matrix

- Numeric parity: `0`, `-0.0`, `1`, `1.0`, safe-integer edges, exponent
  boundaries, subnormal/large finite values, booleans-as-number, NaN/infinity.
- Unicode parity: non-ASCII values, BMP/non-BMP keys, surrogate-edge strings,
  and different insertion order yielding identical canonical bytes.
- Closedness at every level, including extra `candidateGraph`, `links`,
  materialization-authoritative fields, nested reserved keys in opaque, and
  absent-vs-null optional keys.
- Materialization transplant between two forward deltas and between forward
  and inverse deltas must fail despite matching source index/kind.
- Multiple/interleaved add-node entries, shuffled entry order, duplicate index,
  wrong op kind, inverse re-add, and opaque preservation without merging.
- Exact causal inverse positives/negatives for every op; wrong forward digest,
  wrong precondition, wrong order, self-clone, missing removed links/group data.
- Compensation candidate/prepare transition with real minted lease/generation;
  tampered fence, presence mismatch, wrong projection/scope/ref/digest.
- JS/Python authority objects with different key insertion order must agree;
  absent versus explicit null must fail identically.
- C1 positive and every refusal case leave harness-owned counters at zero and
  return a recursively frozen closed plan/diagnostic only.

## Stop conditions

Stop C0 if numeric canonicalization, materialization-to-delta binding, inverse
relation, compensation sealing, or closed op schemas remain prose-only; if the
hash-leaf relocation changes object identity/behavior; or if new modules create
an import cycle. Stop C1 if any plan value must be read from candidate/native
graph state, if the builder needs a runtime import/callback, or if zero native
calls are asserted by its own output rather than externally observed.

C0–C1 is accepted only as contracts plus an isolated plan proof. It does not
transfer S3/S4 ownership, route consumers, execute mutation, generate runtime
inverse state, or prove real ComfyUI behavior.

## Resolution record — 2026-07-17

All eleven pre-implementation blockers above were resolved in the accepted
checkpoint: one shared numeric domain, operation-bound materialization,
explicit dynamic-widget wire support, causal inverse grammar with
`inverse_delta_v2` rewire witnesses, prepare-owned compensation fencing,
closed schemas, opaque passthrough without native merge authority,
presence-aware transition parity, a closed frozen plan, external sentinel
ownership, and nested digest recomputation.

The final adversarial gates passed in both language mirrors and in the broad
browser composition. The scheduler-fence follow-up additionally proved that a
late callback from a replaced panel or departed workflow cannot render, advance
flush evidence, or overwrite panel-affine diagnostics. This resolution record
does not weaken the stop condition: C2 remains one atomic native-owner cut,
with S3 at 0/27 and all seven S4-debt rows still open.
