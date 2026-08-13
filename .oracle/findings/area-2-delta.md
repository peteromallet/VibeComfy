# Area 2 — Regeneration delta (empirically verified on 3 envelopes)
- Exact per-file roundtrip delta: + top-level groups:[] (VibeWorkflow.groups default_factory=list, serialized by _to_plain); − compiled_api (not a dataclass field, never serialized); + top-level mode on EVERY node (value = _ui.mode then metadata.mode else 0); metadata/_ui keys+values UNCHANGED; all other fields identical.
- On-disk files stay alphabetically sorted: ingest writes json.dumps(sort_keys=True) — roundtrip+rewrite keeps them sorted.
- Regenerating TODAY (before Batch B) already writes first-class mode: _from_api_impl sets VibeNode.mode=_node_mode_from_metadata(metadata) and to_envelope serializes it — NO Batch B dependency.
- ingest_external_workflows.py:255 feeds normalized Comfy API dict into convert_to_vibe_format(api_workflow, source_path, workflow_id) → _from_api_impl → VibeWorkflow → to_envelope persisted.
- Risks: compiled_api silently dropped on regenerated files (IR unaffected — from_envelope ignores it — but raw-JSON consumers break); every node gains mode → large diff noise (~2800 files); non-sort_keys rewrite would reorder files.
- The *.layout.json files are layout-store format, NOT envelopes (no 'nodes' key) — from_envelope rejects them; skip in regen.
