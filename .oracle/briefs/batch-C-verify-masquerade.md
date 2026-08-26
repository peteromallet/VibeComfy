# VERIFY — tier masquerade + North Star anti-patterns (read-only)

You are ox-alpha attacking Batch C at HEAD `5f3e635f` in
`/Users/peteromalley/Documents/reigh-workspace/vibecomfy-oracle`.
Do NOT edit source. Do not commit. Read-only plus optional tmp-dir python probes.

North Star anti-patterns to hunt:
1. Silent tier upgrade / masquerade (AST labeled runtime; import labeled runtime_object_info; on_demand_runtime leftover)
2. Stub-as-truth (hollow/@stub.json written to close a gap)
3. Permanent installs (`.tmp_packs`, venv, `nodes ensure`, clone outside sandbox LRU)
4. Parallel schema systems (new parser; persist via `clone_and_extract_packs.write_cache`)

## Do this

Read `git diff b430bbcb..5f3e635f -- vibecomfy/commands/schemas.py tests/test_schemas_ensure.py`.
Also read Batch A glue `vibecomfy/schema/ensure_capture.py` (SOURCE_KIND_BY_RUNG, persist_on_demand_pack) as used by C.

Attack vectors — attempt each, cite file:line, report whether blocked:

A. Map extract method `"ast"` → `runtime_object_info` or `on_demand_runtime`.
B. Map `"import"` → `runtime_object_info` (must be `on_demand_import`).
C. Pass `allow_embedded=True` (must NOT; Batch B deferred; TypeError if passed).
D. Write a stub/hollow schema when extract returns empty.
E. Persist registry `/nodes/.../schema` provisional as cache truth.
F. Honor `VIBECOMFY_ON_DEMAND_BOOT=0` to skip rung 2 (must ignore; r2 always on).
G. `emit(...)` then implicit return 0 on failure (must exit 1 for text AND `--json`).
H. Use `.tmp_packs` or `clone_and_extract_packs.clone_pack` / `process_pack`.
I. Skip `_enforce_cap()` after clone (permanent sandbox growth).
J. Filename `@local-{sha7}` or `@runpod-snapshot` or `@stub.json` from this path.

Also confirm:
- `--no-embedded` is a documented no-op; r3 miss names deferred Batch B + both `--comfy-version` and `VIBECOMFY_EMBEDDED_COMFY_VERSION` when unset.
- Retry command is `vibecomfy schemas ensure --manifest <path>`.
- Gated-class discovery imports `_GATED_CLASS_RE` (not a copied regex).
- Exactly-one of template / `--manifest`.

If you can, a tiny python probe in a tmp cache that tries to persist an AST extract and prints the resulting `source_kind` + filename. No network.

## Return (max 400 words)

For each A–J: BLOCKED or OPEN + file:line.
North Star disposition: ALIGNED / NOT ALIGNED.
Any masquerade path that actually writes a higher-tier stamp is a blocking finding.
KISS note: only if C invents a second persist path around Batch A.
