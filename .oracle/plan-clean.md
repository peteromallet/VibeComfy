Execution protocol: complete each batch, run its gates, commit only its scope, submit the full checkpoint diff to the oracle, and rework until `PASS`. Do not start the next batch early.

### Batch A — Canonical corpus regeneration `[XHARD]`

Depends on resolving corpus ownership in Open Question 1.

Tasks:

1. Add a durable corpus migrate/check command, e.g. `scripts/migrate_external_workflow_corpus.py`.

   - Process only versioned envelopes; skip the two `*.layout.json` sidecars.
   - Decode fail-closed through `VibeWorkflow.from_envelope()`.
   - Resolve mode as first-class → `_ui.mode` → `metadata.mode` → `0`.
   - Write `node.mode`, remove both legacy mode copies, remove `compiled_api`, serialize only through `to_envelope()`.
   - Stage all output before replacement; emit a machine-readable delta report.
   - Permit only `compiled_api` deletion, first-class mode addition, legacy-mode deletion, and—recommended—`groups: []` addition. The latter follows automatically from the dataclass writer ([workflow.py:172](/Users/peteromalley/Documents/reigh-workspace/vibecomfy-oracle2/vibecomfy/workflow.py:172), [workflow.py:253](/Users/peteromalley/Documents/reigh-workspace/vibecomfy-oracle2/vibecomfy/workflow.py:253)).

2. Regenerate all 2,797 envelope files under `external_workflows/corpus/*.json`.

   - Preserve file count and filenames.
   - Make all 135,385 node modes explicit; the 754 formerly mode-less nodes become `mode: 0`.
   - Leave `_ui` intact except for deleting `_ui.mode`.
   - Do not perform a geometry regeneration here.

3. Update the preservation checker.

   - `scripts/check_b02_rich_preservation.py`: project first-class `entry.mode` first, retain legacy fallback for old/synthetic fixtures, replace dispatcher calls with `from_envelope`/`from_api`, and emit through `wf.groups` rather than `groups=` ([checker:89](/Users/peteromalley/Documents/reigh-workspace/vibecomfy-oracle2/scripts/check_b02_rich_preservation.py:89), [checker:262](/Users/peteromalley/Documents/reigh-workspace/vibecomfy-oracle2/scripts/check_b02_rich_preservation.py:262)).

4. Re-anchor corpus tests:

   - `tests/test_b02_rich_preservation.py`
   - `tests/test_porting_normalize_ingest.py`
   - `tests/test_ingest_external_workflows.py`
   - `tests/test_workflow_core.py`

   Remove `compiled_api` preconditions and metadata-mode assertions; prove the two-node execution view is freshly derived by `compile("api")` ([test_porting_normalize_ingest.py:657](/Users/peteromalley/Documents/reigh-workspace/vibecomfy-oracle2/tests/test_porting_normalize_ingest.py:657)).

5. Add the fast structural invariant to `Makefile`’s maintained `check` path; CI already runs `make ci` ([ci.yml:44](/Users/peteromalley/Documents/reigh-workspace/vibecomfy-oracle2/.github/workflows/ci.yml:44), [Makefile:111](/Users/peteromalley/Documents/reigh-workspace/vibecomfy-oracle2/Makefile:111)).

   - If CI must hydrate the corpus, also touch `.github/workflows/ci.yml`.
   - If the corpus becomes tracked, touch `.gitignore`, `.gitattributes` if required, and add `external_workflows` to `ROOT_ALLOWLIST` ([.gitignore:26](/Users/peteromalley/Documents/reigh-workspace/vibecomfy-oracle2/.gitignore:26), [Makefile:62](/Users/peteromalley/Documents/reigh-workspace/vibecomfy-oracle2/Makefile:62)).

6. Run the Hivemind upload only after resolving the update semantics in Open Question 3. No uploader code change is otherwise required: dispatch already uses `from_envelope` ([upload_external_workflows_to_hivemind.py:339](/Users/peteromalley/Documents/reigh-workspace/vibecomfy-oracle2/scripts/upload_external_workflows_to_hivemind.py:339)).

Acceptance:

- Exactly 2,797 envelopes and unchanged filenames.
- Every envelope decodes and round-trips idempotently.
- Filename equals `canonical_form(compile("api"))` hash prefix; canonical form considers only execution fields ([canonical.py:65](/Users/peteromalley/Documents/reigh-workspace/vibecomfy-oracle2/vibecomfy/testing/canonical.py:65)).
- No envelope contains `compiled_api`, `metadata.mode`, or `_ui.mode`.
- Every node has integer first-class `mode`.
- B02 checker reports zero mismatches/UID-less emissions.
- `git diff --check`, focused corpus tests, and `make ci` pass.

### Batch B — Remove `convert_to_vibe_format` `[XHARD]`

Keep private `_named_import` for genuinely polymorphic file/PNG loaders; delete only the judged public dispatcher.

Production/tooling files:

- Delete dispatcher: `vibecomfy/ingest/normalize.py`.
- Remove public import/export: `vibecomfy/ingest/__init__.py`.
- API → `from_api`:  
  `scripts/ingest_external_workflows.py`, `tools/convert_ready_templates.py`, `tools/format_as_python.py`, `vibecomfy/registry/ready_template.py`, `vibecomfy/scratchpad_loader.py`, API route in `vibecomfy/comfy_nodes/agent/routes.py`.
- UI → `from_ui`:  
  `vibecomfy/demo_factory/fixer.py`, round-trip route in `vibecomfy/comfy_nodes/agent/routes.py`, `vibecomfy/porting/edit/_gates.py`.
- Explicit envelope/API branch:  
  `vibecomfy/comfy_nodes/agent/_frag_ingest.py`, `vibecomfy/comfy_nodes/agent/graph_normalization.py`.
- Checker: `scripts/check_b02_rich_preservation.py`.
- Rename stale comments and recognize `from_api` wrappers:  
  `vibecomfy/porting/emit/ui.py`, `emit_kwargs.py`, `node_kwargs.py`, `vibecomfy/registry/ready.py`.
- Update live—not historical—docs:  
  `docs/agent-edit/session-contract.md`, `docs/runtime/incompatibilities.md`, `docs/security/agent_data_boundary.md`, `docs/security/capability_taxonomy.md`, `docs/text-to-graph/mvp.md`.

Tests requiring call/import migration:

- `tests/edgecases/`: `test_backward_compat.py`, `test_concurrency.py`, `test_determinism.py`, `test_json_formats.py`, `test_model_assets.py`, `test_multi_output.py`, `test_pack_drift.py`, `test_runtime_failures.py`, `test_subgraph_corners.py`, `test_type_system.py`.
- `tests/security/`: `test_agent_context_boundary.py`, `test_ingest_provenance.py`, `test_integration.py`.
- `tests/parity/test_independent_readback.py`
- `tests/live_agentic_harness/intent_judge.py`
- `tests/test_agent_edit_safety.py`
- `tests/test_codemod_hypothesis.py`
- `tests/test_comfy_roundtrip_route.py`
- `tests/test_compile_invariance.py`
- `tests/test_demo_factory_structural_baseline.py`
- `tests/test_emitted_artifacts_open.py`
- `tests/test_exec_normalize.py`
- `tests/test_finalize_metadata.py`
- `tests/test_ingest_external_workflows.py`
- `tests/test_ingest_snapshot.py`
- `tests/test_intent_nodes.py`
- `tests/test_layer4_smoke.py`
- `tests/test_layout_delta.py`
- `tests/test_metadata_registration.py`
- `tests/test_porting_edit_session.py`
- `tests/test_porting_emitter.py`
- `tests/test_porting_normalize_ingest.py`
- `tests/test_porting_ui_emitter.py`
- `tests/test_position_fidelity.py`
- `tests/test_ready_templates.py`
- `tests/test_reconcile.py`
- `tests/test_run_command.py`
- `tests/test_schema.py`
- `tests/test_schema_validate.py`
- `tests/test_subgraph_emission_contract.py`
- `tests/test_ui_emitter_parity.py`
- `tests/test_ui_emitter_widget_shape_verdict.py`
- `tests/test_walking_skeleton.py`
- `tests/test_workflow_core.py`

Re-anchor equivalence tests on fixture invariants—IDs, classes, UIDs, modes, groups, edges, and compiled view—not on the deleted dispatcher. Add the public-surface guard beside the existing detector guard ([test_workflow_core.py:1769](/Users/peteromalley/Documents/reigh-workspace/vibecomfy-oracle2/tests/test_workflow_core.py:1769)).

Acceptance:

- `rg 'convert_to_vibe_format' --glob '*.py'` finds only the intentional negative guard, if any.
- `vibecomfy.ingest` exposes `from_envelope`, `from_ui`, and `from_api`, but not the dispatcher.
- Offline paths remain offline; no new live-ComfyUI dependency.
- Generated scratchpad and subprocess source use `from_api`.
- Focused ingest, security, ready-template, scratchpad, porting, and B02 gates pass.

### Batch D+E — Emit/port consumes IR authority `[XHARD]`

Files:

- `vibecomfy/porting/emit/ui.py`
- `vibecomfy/commands/port/_export.py`
- `vibecomfy/porting/layout_store.py`
- `scripts/check_b02_rich_preservation.py`
- Tests: `test_porting_ui_emitter.py`, `test_cli_port.py`, `test_ui_emitter_prior_payload.py`, `test_layout_store.py`, `test_porting_synthetic_fixtures.py`, `test_porting_normalize_ingest.py`, `test_ui_layout.py`.

Tasks:

- Make `_resolve_furniture()` obtain mode exclusively through `_get_node_mode(node)`. Sidecar and metadata retain authority only for flags, colors, properties, and title ([ui.py:249](/Users/peteromalley/Documents/reigh-workspace/vibecomfy-oracle2/vibecomfy/porting/emit/ui.py:249), [workflow.py:1156](/Users/peteromalley/Documents/reigh-workspace/vibecomfy-oracle2/vibecomfy/workflow.py:1156)).
- Remove `emit_ui_json(groups=...)`; emission starts from a deep copy of `wf.groups`.
- Reconcile the selected preserve store’s groups into `workflow.groups` immediately after `_resolve_preserve_source()`, then remove `groups=sidecar_groups` from export ([port/_export.py:445](/Users/peteromalley/Documents/reigh-workspace/vibecomfy-oracle2/vibecomfy/commands/port/_export.py:445)).
- Make `write_layout()` read first-class `wf.groups`, not `wf.metadata["groups"]` ([layout_store.py:171](/Users/peteromalley/Documents/reigh-workspace/vibecomfy-oracle2/vibecomfy/porting/layout_store.py:171)).
- Preserve current source precedence: fresh → sidecar plus `--from` entry overrides → `--from` → sidecar → breadcrumb.

Acceptance:

- Conflicting sidecar, `_ui`, metadata, and field modes cannot make compile and emit disagree.
- Modes 0/2/4 work with the single legacy `_ui` fallback.
- Sidecar geometry/furniture other than mode remains unchanged.
- Sidecar-only, `--from`, conflict, breadcrumb, and `--fresh` group cases pass.
- `port convert` writes `wf.groups`.
- No live `emit_ui_json(..., groups=...)` calls remain.
- Focused port/UI/layout tests and B02 pass.

### Batch C — First-class geometry `[XHARD]`

Frozen simplification: do not perform a second corpus regeneration. Old envelopes populate first-class geometry during decode from `_ui`.

Files:

- Model/ingest: `vibecomfy/workflow.py`, `vibecomfy/ingest/normalize.py`.
- Consumers: `vibecomfy/porting/layout_store.py`, `vibecomfy/porting/lowering.py`, `vibecomfy/porting/convert.py`, `vibecomfy/porting/layout/reconcile.py`, `vibecomfy/porting/emit/ui.py`.
- Tests:  
  `test_workflow_core.py`, `test_porting_normalize_ingest.py`, `test_layout_store.py`, `tests/intent/test_static_lowering.py`, `test_porting_convert.py`, `test_porting_synthetic_fixtures.py`, `test_virtual_wire_round_trip.py`, `test_reconcile.py`, `test_porting_ui_emitter.py`, `test_porting_ui_materialize.py`, `test_position_fidelity.py`, `test_compile_invariance.py`, `tests/live_agentic_harness/source_layouts.py`.

Tasks:

- Add optional `VibeNode.pos` and `VibeNode.size`, default `None`.
- Populate them from UI/API `_ui` during ingest; envelope decode prefers node-level values and falls back to legacy `_ui`.
- Replace geometry descents in layout-store writing, lowering clones, virtual-wire capture, reconcile position matching, and UI emission.
- Explicitly copy `mode`, `pos`, and `size` in lowering’s manual node constructor.
- Do not alter `layout/reconcile.py:505`: that `_ui` access hashes subgraph properties/input schema, not geometry ([reconcile.py:498](/Users/peteromalley/Documents/reigh-workspace/vibecomfy-oracle2/vibecomfy/porting/layout/reconcile.py:498)).

Acceptance:

- UI ingest through live and offline converters yields identical geometry.
- Old/new envelopes round-trip; first-class values win conflicts.
- Copy is deep; compile output is geometry-invariant.
- Lowering clone offsets/sizes, virtual-wire capture, nearest-node reconcile, sidecar serialization, and emitted coordinate canonicalization remain stable.
- Focused suite, B02, `make ci`, and full pytest pass.

### Batch K — Declare workflow context token

Files:

- `vibecomfy/workflow.py`
- `vibecomfy/templates.py`
- `tests/test_workflow_core.py`
- `tests/test_templates_module.py`
- `tests/test_workflow_context.py`

Tasks:

- Add `_workflow_context_token: Any = field(default=None, init=False, repr=False, compare=False)`.
- Replace token-related `getattr`/`hasattr`, dynamic creation, and deletion with direct access/assignment.
- Ensure `copy()` always produces `_workflow_context_token is None`; use a deepcopy memo for an actively bound `contextvars.Token`.
- Prove the field is absent from constructor, repr, equality, and envelope.

Acceptance:

- Context enter/exit, eager binding/finalize, nesting, exception cleanup, and async isolation remain green.
- Bound and unbound workflow copies succeed and are unbound.
- No token leaks into `to_envelope()`.

### Final release gate

- Corpus invariant command and full B02 checker.
- `make ci`
- `make full-pytest`
- `git diff --check`
- Static searches for deleted dispatcher, legacy corpus mode stores, and `groups=` emission overrides.
- Final oracle review of the complete diff against the explicit defer/leave-alone list.

Explicitly untouched: id-map authority, requirements/diagnostics split, typed metadata/groups, mode enum, slots, JS consumers, full compile/emit unification.

## 2. Additional areas to explore for full clarity

1. **Corpus ownership and hydration.** The worktree has no `external_workflows/`; the populated sibling checkout has the 2,797 envelopes, while the path is ignored in clean clones. Establish whether the PR tracks ~466 MB, force-adds a data artifact, or hydrates a pinned corpus in CI.

2. **Regeneration delta contract.** A plain `from_envelope().to_envelope()` also adds `groups: []` to every old envelope. Recommended: allow it as canonical schema completion; suppressing it would make the migration bypass the sole writer.

3. **Manifest consistency.** The sibling manifest contains 2,798 rows but references missing `corpus/355b418f7449ba25.json`. Determine whether to reconstruct it from shadow data or record it as pre-existing drift.

4. **Hivemind update semantics.** Default upload skips existing rows, so “run upload” would not refresh regenerated payloads. Prove one-row update/upsert behavior with `--only` and `--verify` before the full operation.

5. **Group member reconciliation.** `store_from_ui_json()` converts group member IDs to UIDs ([layout_store.py:425](/Users/peteromalley/Documents/reigh-workspace/vibecomfy-oracle2/vibecomfy/porting/layout_store.py:425)); emission must decide whether to map those back to emitted LiteGraph IDs or omit nonstandard membership.

6. **Geometry validation.** Decide whether first-class `pos`/`size` accept only two finite numeric values and fail closed on malformed versioned envelopes. Recommended: strict for envelopes, tolerant absence for UI/API ingest.

7. **Generic loader boundary.** Retain `_named_import`: file, PNG, and registry loaders genuinely accept multiple formats ([workbench.py:716](/Users/peteromalley/Documents/reigh-workspace/vibecomfy-oracle2/vibecomfy/porting/workbench.py:716)). Duplicating its shape branches would reduce elegance.

8. **Ready-template producers.** The brief omitted `tools/format_as_python.py` and `tools/convert_ready_templates.py`; both own API-shaped paths and belong in Batch B. No ready-template source or index regeneration is otherwise justified.

## 3. Open questions / potential issues

1. **Where will the corpus live for review and CI?** This blocks Batch A. Recommended: a pinned hydration artifact if the 466 MB corpus is intentionally excluded from Git; never allow the CI assertion to skip when absent.

2. **Is `groups: []` an allowed corpus delta?** Recommended: yes, because suppressing it contradicts the “single writer” design.

3. **How are existing Hivemind resources updated?** `--skip-existing` prevents refresh; disabling it may duplicate rows unless `add_resource` is an upsert.

4. **Should the missing manifest corpus file be repaired?** Recommended: isolate it from the schema migration unless its shadow source deterministically reconstructs the same canonical hash.

5. **Does dropping `groups=` mean the emitter parameter itself, or only the command call?** The frozen tasklist interprets the verdict as deleting the override entirely; five additional callers/tests must therefore migrate to `wf.groups`.

6. **What is the exact geometry type?** Recommended: `list[float] | None`, normalized to two finite coordinates while preserving `None` for absent evidence.

7. **Should K-minor fix copying a bound workflow?** Recommended: yes. Current `deepcopy` cannot copy a bound `contextvars.Token`, and the fix is local to the token declaration/copy contract.
