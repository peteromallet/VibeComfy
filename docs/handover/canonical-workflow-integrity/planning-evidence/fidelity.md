> Historical planning evidence, not executable product certification. Source line numbers refer to the audited baseline. Local receipt/manifest references in this note are provenance descriptions; the compact history and exact published source identity are in ../history.md and ../provenance.md.

# Fidelity exploration

The frozen dirty diff's identity-only publication change is too broad. `VibeWorkflow.semantic_projection()` includes nodes, UIDs, inputs/widgets, mode, semantic metadata, native socket rosters, edges, definitions, virtual wires, requirements, inputs, outputs, and variants (`vibecomfy/workflow.py:764-845`). Matching workflow ID plus successful load therefore does not establish preservation.

The dirty “drift” fixture (`tests/test_workflow_bundle.py:914-928`) is a useful counterexample, but its loss has a known root: `PreviewAny` is in `UI_ONLY_CLASS_TYPES`; `_prepare_workflow_for_emit` strips UI-only classes unless a fidelity-mode node has a live edge into a non-UI-only node (`vibecomfy/porting/emit/emit_constants.py:105-107`; `vibecomfy/porting/emit/emit_prepare.py:84-108`). A disconnected `PreviewAny` is therefore intentionally classified as decorative by the current emitter. The clean checkout already has an acceptance test proving the narrow rule: terminal `PreviewAny` is removed, while a wired `PreviewAny` passthrough and both edges survive with equal semantic digest (`tests/test_porting_emitter.py:362-410`). The source docs record the same B7 root/fix (`docs/local_agent_text_to_graph_blockers.md:122-138`). This is acceptable lossy presentation normalization only when the classification is explicit; it does not justify accepting arbitrary digest drift.

Unknown/custom preservation remains a separate gap. The documented B9 finding says schema-canonicalization can drop or misalign unknown/v3 nodes and proposes passthrough (`docs/local_agent_text_to_graph_blockers.md:155-164`). Existing tests prove schema-less `PreviewAny` passthrough, not arbitrary unknown classes. Do not blanket reject unknown nodes or blanket allow them: preserve their raw node payload and classify Queue readiness separately where a preservation path exists; otherwise return a draft/degraded diagnostic.

Minimal implementation contract:

1. Keep staged semantic equality for ordinary canonical publication.
2. Add a narrowly named normalization result for the existing disconnected UI-only rule. It should report dropped UIDs/classes and allow only that allowlist; any other node, edge, input, widget, mode, requirement, definition, virtual-wire, or semantic-metadata delta fails publication.
3. Keep UI-only layout changes in `ui_digest`; do not make canvas normalization a semantic exception.
4. Add one regression fixture with a disconnected `PreviewAny` plus a meaningful `Integer`: publication succeeds with an explicit dropped-node diagnostic. Add a connected `PreviewAny → sink` fixture asserting semantic equality. Add a custom unknown node carrying widgets/properties and assert save/reload preserves its class, UID, payload, and edges (or yields an explicit degraded result).

Exact proposed checks:

```text
python -m pytest -q tests/test_porting_emitter.py::test_canonical_emitter_filters_only_edges_to_removed_ui_only_nodes tests/test_workflow_bundle.py::test_real_converter_backed_public_capture_roundtrips_pair tests/test_workflow_bundle.py::test_canonical_roundtrip_preserves_explicit_none_input_default
python -m pytest -q tests/test_workflow_bundle.py tests/test_porting_emitter.py
```

The first command is the cheap acceptance tier; the second is the bounded regression tier. No tests or product files were changed during this exploration.
