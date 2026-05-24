# Documentation Audit TODOs

Batch 9 spot-checked behavior claims in `AGENTS.md`, `CLAUDE.md`, and `docs/**/*.md` against current code. The goal was to record mismatches without widening implementation scope.

| Claim | Checked Against | Verdict | TODO |
|---|---|---|---|
| `AGENTS.md` roundtrip limitations said helper/UI nodes are stripped during conversion. | Generated-template behavior and current helper/UI roundtrip caveat. | Mismatch fixed in `AGENTS.md`. | Implement Family F helper stripping in Phase 1, while preserving the JSON -> Python -> JSON caveat. |
| `CLAUDE.md` carries the same helper/UI stripping wording. | `CLAUDE.md` project-doc text and current emitter behavior. | Mismatch remains. | Mirror the corrected `AGENTS.md` wording into `CLAUDE.md` when doc ownership permits. |
| `new_workflow()` creates a ContextVar-backed workflow context for generated templates. | `vibecomfy/templates.py:68`, `vibecomfy/workflow_context.py:18-39`. | Accurate. | None. |
| `node()` can omit `wf` inside `with new_workflow(...) as wf:`. | `vibecomfy/templates.py:95-120`. | Accurate. | None. |
| Raw `wf.node()` should not silently accept `public()` sentinels. | `vibecomfy/workflow.py:343-358`. | Accurate after T5. | None. |
| `refresh_template_index.py` imports and executes ready templates for runtime contract extraction. | `tools/refresh_template_index.py:50-66`, `vibecomfy/registry/static_contract.py:158-284`. | Accurate. | None. |
| Generated-template conversion refuses `# vibecomfy: manual` templates. | `tools/convert_ready_templates.py` manual gate observed in T8. | Accurate. | None. |
| Ready-template index should contain 64 templates, with 41 generated and 23 manual/broken-regen shims. | A.4 sweep counts in `tests/test_template_load_sweep.py`. | Accurate post-F. | None. |
| `wf.strict_types` enables socket-compatibility warnings on connect. | `vibecomfy/workflow.py:133`, `vibecomfy/workflow.py:373`. | Accurate. | None. |
| Attempt snapshots are written before every queue boundary. | `AGENTS.md` runtime narrative; runtime session code was not fully audited in this batch. | Unverified. | Audit runtime attempt-writing code before relying on "every queue boundary" as a hard guarantee. |
