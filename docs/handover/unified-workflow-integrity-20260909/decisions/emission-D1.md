1. **Disposition:** **Approve with conditions; plan freeze only.** The proposed 2–3 focused engineering days is plausible. This decision does not authorize implementation or test execution.

2. **Decision/reason:** Use one shared canonical emitter that:

   - Applies the existing execution projection so reroutes and resolvable primitives disappear from executable Python.
   - Retains prepared edge bindings and emits topology once as constructor kwargs using variables/handles.
   - Emits each runtime value once and removes routine `wf.connect(...)` plus post-finalize `wf.nodes[...]` restoration.
   - Keeps unknown custom nodes as fail-closed raw calls, distinct from resolver-owned helpers.
   - Stores identity, provenance, native-port authority, and exceptional authored-channel facts in one compact custody manifest outside the ordinary graph body.

   Hiding **all `_id`/`_uid` arguments and raw IDs from ordinary node calls is achievable through a bounded contract change**: finalization or a compact custody helper must resolve variable/handle bindings to constructed nodes and apply identity afterward. Internally, runtime/source node IDs, durable and scope-qualified UIDs, schema provenance, native-port authority, and public-input/variant/interface/boundary references must remain. This deliberately replaces representation-level importer restoration with explicit executable-semantic and identity/provenance fidelity; it is not a parallel “pretty mode” or an IR migration.

3. **Concrete future task outcomes/evidence/dependency scope and normal/xhard route:** **Xhard** owns the nonlocal contract and implementation across execution projection, emitter preparation, finalization/rebinding, semantic comparison, public bindings, and identity custody. **Normal** owns focused AST tests, H3 acceptance updates, documentation, and fixture regeneration.

   Required evidence:

   - AST acceptance forbids ordinary `_id`/`_uid`, raw link lists, `wf.connect`, `wf.nodes[...]` semantic restoration, and emitted raw resolver helpers.
   - Every effective wire appears exactly once as a handle expression; no raw edge-count inference is accepted.
   - API and GraphBuilder projections, public-control edits, output-slot authority, defaults, aliases, modes, and unknown-node fail-closed behavior remain equivalent.
   - Required IDs, UIDs, provenance, native ports, variants, definitions, interfaces, boundaries, and virtual-wire custody survive through the compact binding mechanism.
   - Helper tests prove reroute/primitive consumer rewriting and retain authored helper provenance without executable helper calls.
   - Existing exact-restoration tests are explicitly split into behavioral and custody assertions; the current H3 `widget_0` failure is corrected through effective-field semantics, not waived.
   - Re-emission is deterministic by normalized AST plus semantic and identity/provenance digests.

   Scope excludes global ingest changes, wholesale IR migration, a second emitter mode, schema-provider redesign, and unrelated dirty-worktree changes.

4. **Return condition:** Return for user approval now. After authorization, return implementation only when all source-shape, semantic, identity, helper-resolution, H3, and relevant regression gates pass. If compact rebinding cannot preserve required identity/native-port authority without per-call IDs or runtime-value replay, return D1 as blocked for contract reconsideration—do not fall back to importer-shaped restoration.
