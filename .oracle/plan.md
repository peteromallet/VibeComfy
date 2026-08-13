## Batch A — Canonical corpus migration `[XHARD]`

Tasks:

1. Add `scripts/migrate_external_workflow_corpus.py`.

   - Require explicit `--corpus-dir`; no repository-relative default.
   - Fail closed if the directory is absent or contains zero envelopes.
   - Process `*.json` except `*.layout.json`; reject sidecars if explicitly supplied.
   - Decode only with `from_envelope()`, serialize only with `to_envelope()` and `sort_keys=True`.
   - Stage every output before any replacement.
   - Allow exactly:
     - add `groups: []` where absent;
     - remove `compiled_api`;
     - add integer first-class `node.mode`.
   - Preserve all metadata and `_ui` content exactly, including legacy mode copies.
   - Emit a machine-readable per-file delta report; support check-only and explicit write modes.

2. Run migration against the absolute corpus path in the main checkout, never the worktree-local ignored path.

   - Migrate exactly 2,797 envelopes.
   - Leave both `*.layout.json` sidecars, filenames, manifest, and shadow data untouched.
   - Confirm 135,385 explicit modes; 754 formerly missing modes become `0`.

3. Harden `check_b02_rich_preservation.py`.

   - Require an explicit corpus directory and fail on missing/empty input.
   - Read first-class mode first with legacy fallback.
   - Use `from_envelope()` for corpus envelopes and `from_api()` for normalized API dictionaries.
   - Put groups on `wf.groups`; stop passing `groups=`.
   - Report checked/skipped counts, including two skipped sidecars.

4. Re-anchor corpus tests around derived execution state.

   - Remove `compiled_api` assumptions.
   - Preserve legacy metadata assertions rather than requiring deletion.
   - Prove execution is freshly derived by `compile("api")`.
   - Add missing/empty-directory and layout-sidecar rejection tests.

5. Make CI non-vacuous without importing the 466 MB corpus.

   - Add a small tracked representative envelope fixture directory.
   - Make the maintained `make check`/`make ci` path call the checker with that explicit directory and expected nonzero count.
   - Add a separate full-corpus target requiring explicit `CORPUS_DIR` and expected count `2797`; no fallback path.

6. Scope cuts:

   - Do not repair or rewrite the manifest. Record `355b418f7449ba25.json` as known pre-existing drift.
   - Do not upload to Hivemind and do not add upsert support. Existing rows may retain old payloads; summaries are unaffected.

Acceptance gate:

- 2,797 envelopes and two untouched layout sidecars.
- Unchanged filenames and canonical execution hashes.
- Every envelope decodes; second migration run reports zero changes.
- Delta report contains only the three permitted transformations.
- Metadata and `_ui` are unchanged.
- No envelope contains `compiled_api`; every node has integer `mode`.
- Full B02 reports zero mismatches and zero UID-less emissions.
- Missing/empty corpus checks fail.
- Focused corpus tests, `git diff --check`, and `make ci` pass.

## Batch B — Remove the public dispatcher

Tasks:

1. Remove only `convert_to_vibe_format()` from `ingest/normalize.py` and its public export. Keep the normalization module and private `_named_import()`.

2. Migrate the verified callers:

   - `from_api()`:
     - `registry/ready_template.py`
     - both paths in `tools/format_as_python.py`
     - `tools/convert_ready_templates.py`
     - `porting/edit/_gates.py`
     - API route in `comfy_nodes/agent/routes.py`
     - `scripts/ingest_external_workflows.py`
     - API path in `check_b02_rich_preservation.py`
   - `from_ui()`:
     - UI route in `comfy_nodes/agent/routes.py`
     - `demo_factory/fixer.py`
   - `from_envelope()`:
     - `comfy_nodes/agent/graph_normalization.py`
     - corpus path in `check_b02_rich_preservation.py`
   - `_frag_ingest.py`:
     - branch with `_is_vibe_envelope(raw)`;
     - envelope → `from_envelope()`, otherwise → `from_api()`.
   - `scratchpad_loader.py`:
     - rewrite both generated source strings and generated imports to use `from_api()`.

3. Leave loader boundaries unchanged.

   - `_named_import()` remains for raw dictionaries of unknown shape.
   - Ready-ID and `.py` paths continue bypassing it.
   - `workbench.py` is not a dispatcher caller and receives no migration edit.

4. Update live comments/docs and mechanically migrate affected tests. Re-anchor equivalence tests on IDs, UIDs, classes, modes, groups, edges, and compiled output.

Acceptance gate:

- `rg 'convert_to_vibe_format' --glob '*.py'` finds only an intentional negative guard.
- `vibecomfy.ingest` exposes `from_envelope`, `from_ui`, and `from_api`, not the removed dispatcher.
- `_named_import()` still handles ambiguous raw JSON/image-loader inputs.
- Generated scratchpad code imports and calls `from_api()`.
- Offline routes remain offline.
- Focused ingest, loader, security, ready-template, scratchpad, porting, and B02 tests pass.

## Batch D+E — IR-authoritative emission and groups `[XHARD]`

Tasks:

1. Make `_resolve_furniture()` obtain mode only through `_get_node_mode(node)`.

   - Sidecars and top-level metadata retain authority for flags, colors, properties, title, and geometry—not mode.
   - Keep the single legacy `_ui.mode` fallback inside `_get_node_mode()`.

2. Remove the `groups` parameter from `emit_ui_json()` and all seven callers/tests.

3. Reconcile groups into the IR immediately after `_resolve_preserve_source()`.

   - If the selected preserve store contains groups, deep-copy them into `workflow.groups`.
   - Otherwise retain the groups already present on the workflow.
   - Preserve existing fresh/sidecar/`--from`/breadcrumb precedence.

4. Remap group membership during emission.

   - Build aliases from workflow node ID, numeric source ID, `node.uid`, and captured `_ui.id`.
   - Map known group members to final LiteGraph integers through `id_remap`.
   - Preserve member order and group metadata.
   - Deterministically omit stale/unresolved members rather than emitting dangling IDs.
   - Merge IR groups before engine-generated groups and retain title deduplication.

5. Make `write_layout()` serialize `wf.groups`, not `wf.metadata["groups"]`.

Acceptance gate:

- Compile and emit agree for modes 0/2/4 despite conflicting sidecar or metadata values.
- Raw source-ID and UID-based group members both emit as correct LiteGraph integers.
- No emitted group contains dangling/string membership for emitted nodes.
- Sidecar-only, `--from`, conflict, breadcrumb, `--fresh`, removed-node, and nonnumeric-node-ID cases pass.
- `port convert` writes reconciled groups onto `wf.groups`.
- No `emit_ui_json(..., groups=...)` calls or signature remain.
- Focused port, emitter, layout, CLI, and B02 tests pass.

## Batch C — First-class geometry `[XHARD]`

Tasks:

1. Add `VibeNode.pos` and `VibeNode.size` as separate `list[float] | None` fields.

   - Each present value must contain exactly two finite numeric coordinates.
   - Absence remains `None`; never synthesize geometry.
   - Versioned envelopes reject malformed present values.
   - UI/API ingestion tolerates absent or malformed geometry by leaving the first-class field absent while retaining raw `_ui`.

2. Ingest/decode behavior:

   - UI/API ingest copies valid `_ui.pos` and `_ui.size`.
   - Envelope decode prefers node-level fields, falling back independently to legacy `_ui`.
   - First-class values win conflicts.

3. Replace geometry descents in:

   - layout-store writing;
   - lowering clones and offsets;
   - virtual-wire capture;
   - nearest-node reconciliation;
   - UI captured geometry/emission.
   - Explicitly copy `mode`, `pos`, and `size` in lowering’s manual constructor.

4. Leave the non-geometry `_ui` hash access in `layout/reconcile.py` unchanged.

5. Do not regenerate the corpus again.

Acceptance gate:

- Live and offline UI ingestion produce identical first-class geometry.
- Old and new envelopes round-trip functionally; first-class values win.
- Copies are deep and compile output is geometry-invariant.
- Missing size still triggers the existing stub-layout behavior.
- Lowering, virtual wires, reconcile matching, sidecars, and emitted coordinate canonicalization remain stable.
- Focused geometry suite, B02, `make ci`, and full pytest pass.

## Batch K — Declare the workflow context token

Tasks:

1. Add:

   ` _workflow_context_token: Any = field(default=None, init=False, repr=False, compare=False)`

2. Replace token-related `getattr`, `hasattr`, creation, and deletion with direct assignment/access.

3. Make `copy()` handle bound workflows by supplying a deepcopy memo that maps the active `contextvars.Token` to `None`. Every clone must be unbound.

Acceptance gate:

- Bound and unbound copies succeed and have token `None`.
- Constructor, repr, equality, and envelope omit the field.
- Enter/exit, eager binding, finalize, nesting rejection, exception cleanup, and async isolation pass.
- No context token leaks into serialization.

## Checkpoint structure

After each batch:

1. Commit only that batch.
2. Submit the task excerpt, diff from the prior passed checkpoint, test output, and implementation deviations to the oracle.
3. For Batch A, also attach the external-corpus delta report, counts, and before/after canonical hashes because the corpus is outside the worktree diff.
4. Oracle returns `PASS` or concrete issues.
5. Rework and resubmit until `PASS`; record the passed SHA under `.oracle/checkins/`.
6. `[XHARD]` work goes to GPT-5.6 Sol; other implementation work goes to DeepSeek Flash.

## Final release gate

- Full-corpus migration check with explicit absolute path and expected count `2797`.
- Full B02 check against that same path.
- `make ci`
- `make full-pytest`
- `git diff --check`
- Static guards for:
  - removed dispatcher;
  - removed `groups=` emitter surface;
  - sidecar/metadata mode authority in emission;
  - remaining geometry descents outside approved ingest/hash fallbacks.
- Verify manifest and Hivemind were not mutated.
- Final oracle review of the complete branch diff plus the external-corpus report.

Explicitly deferred: manifest repair, Hivemind payload refresh/upsert, tracking the 466 MB corpus, id-map redesign, typed groups/metadata, mode enum/sentinel redesign, slots, JS consumers, and full compile/emit unification.

**New exploration areas:** none.
tokens used
52,078
# Revised frozen plan

Execution order: **A → B → D+E → C → K → release gate**. Do not begin a batch until its checkpoint passes.

