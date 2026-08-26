# Implementation tasklist — registry-pinned ephemeral schema capture + preflight bridge

Base: `96a9d810` on `oracle-run`. Venue: land on `main` after review PASS. New code is glue.

Frozen compose map (do not replace these):

| Need | Reuse |
|---|---|
| Pack resolve | `registry/pack_resolver.py:resolve_pack` / `resolve_missing_nodes` (`PackRef.url/version/commit`) |
| Shallow clone + LRU | `schema/on_demand.py:OnDemandInstallSchemaProvider._ensure_clone` / `_enforce_cap` |
| Rungs 1–2 | `schema/extract.py:extract_pack_schemas` (`allow_import=True` already default) |
| Persist stamp | `porting/object_info/serialize.py:build_cache` + `CacheIdentity` |
| Ledger | `commands/schemas.py:_load_provenance` / `_write_provenance` / `_attest_ingested_capture` |
| Stub wall | `ObjectInfoIndexSchemaProvider._load_index` `@stub.json` filter + `is_workflow_stub_schema` |
| Gated-class discovery | `tests/live_agentic_harness/scenario_obligations.py` (`_GATED_CLASS_RE`, `load_scenario_obligation`) |
| Throwaway pip-comfy venv pattern | `porting/object_info/core_regen.py` venv+`pip install comfyui==…` **only**; do not reuse its `main.main` HTTP path |

Do **not** persist via `tools/clone_and_extract_packs.write_cache`. That path writes `Pack@local-{sha7}.json` with **no** `source_kind` and **no** provenance row — and is how unattested extracts later get mistaken for live captures.

---

## Traceability

| Agent-goal item | Batches | North Star | Anti-pattern blocked |
|---|---|---|---|
| 1. `schemas ensure --manifest` | A, B, C | ephemeral clone → ladder → committed cache | no permanent install; no parallel extract; no stub-as-truth |
| 2. Preflight bridge + strict flag | D | honest tier; fail closed | no silent upgrade of static → runtime; stub rejection stays |
| 3. Doctor / coverage gap + exact command | E | actionable “run this command” | no unactionable wall |
| 4. Tests + SKILL.md | A–E | trust tier visible | e2e uses on-demand files, not hand-authored schemas |

---

## Canonical tokens (plan default; Q1 if oracle overrides)

Persist `CacheIdentity.source_kind` and provenance `source_kind`:

| Rung | What actually ran | Persist token |
|---|---|---|
| 1 | AST (`extract_by_ast` / method `"ast"`) | `on_demand_static` |
| 2 | Stubbed-subprocess `INPUT_TYPES()` (`extract_by_import` / method `"import"`) | `on_demand_import` |
| 3 | Pack `NODE_CLASS_MAPPINGS` against **genuine** pip `comfy` modules, in-process, **no server** | `on_demand_embedded` |

Preflight does NOT accept `on_demand_runtime`; the single stamp at `on_demand.py:193` migrates to `on_demand_import` in Batch A (no alias surface). Never persist `runtime_object_info` / `runtime_core_object_info` / `executed_object_info` / `workflow_json_stub` from this path.

Filename: `{pack}@{source_kind}-{sha7}.json` (not `@runpod-snapshot`, not `@local-{sha7}`, not `@stub.json`).

---

## Batch A — Persist glue + honest identity

**Seam:** a fake extract result can be written and re-read with the right tier. No CLI, no network, no rung 3.

**Normal.**

### Tasks

1. Add a glue module (new, thin): `vibecomfy/schema/ensure_capture.py` (name may be `on_demand_persist.py`; one module, not a parallel schema system).

2. Adapter: `extract.normalize_entry` shape (`inputs` plural, `outputs` list-of-dicts, `schema/extract.py:110`) → the raw dump `build_cache` expects (`input` singular, `output` type list, `serialize.py:71–113`). Do not teach `build_cache` a second input dialect.

3. `persist_on_demand_pack(...)` must:
   - Call `build_cache(..., identity=CacheIdentity(pack_slug, pack_version, git_commit=resolved_sha, evidence_identity=f"on_demand:{rung}:{sha}", source_kind=<token above>), full_pack_refresh=False)` — MERGE semantics. `full_pack_refresh=True` would drop other same-pack classes from the pack file and index.json, silently retargeting existing `@runpod-snapshot` index rows to on-demand (silent tier demotion — forbidden).
   - Before writing, drop from the extract result any class that already has a higher-tier capture (tier order: runtime family > on_demand_embedded > on_demand_import > on_demand_static); if ALL classes in the result are lower-tier-covered, write nothing (no-op).
   - **Index hygiene (serialize merge caveat):** `build_cache` merge re-adds every same-pack class from existing files and repoints `index[class_type]` to the new file (`serialize.py:229-230,327-333`). After `build_cache`, the glue MUST post-process `index.json`: restore every pre-existing class's index mapping to its original file unless that class was newly written by this extraction. Net effect: only newly captured classes point at `Pack@on_demand_*-{sha}.json`; a mixed pack (runtime class R + gap G) leaves `index[R]` on the runtime file while `index[G]` gains the on_demand entry.
   - After write, attest `provenance.json` packs[`filename`] with **at least**: `pack`, `repo`, `locked_commit`, `schema_sha256`, `source_kind`, `extraction_rung` (`ast`|`import`|`embedded`), `registry_pack_version`, `captured_at`. Reuse `_load_provenance`/`_write_provenance`; do not invent a second ledger.
   - Leave `repo`/`locked_commit` as the **clone’s** git remote + `rev-parse HEAD`. That is pin evidence, not a claim of runtime `/object_info`.

4. Gap definition for “lacking a live capture” (shared helper, used by ensure/doctor/preflight tests):
   - not in `index.json`, **or**
   - index maps to `@stub.json` / `source_kind==workflow_json_stub` / `pack_version==stub`, **or**
   - no provenance row, **or**
   - provenance has neither `repo` nor `locked_commit`.
   - `list_classes()` alone is **not** sufficient (current ensure bug, `schemas.py:465`).

5. Never overwrite a **higher** tier for the same class:
   - runtime family (`runtime_object_info`, `runtime_core_object_info`, `executed_object_info`, filename `@runpod-snapshot`) > `on_demand_embedded` > `on_demand_import` > `on_demand_static`.
   - Stubs/unattested count as missing (replaceable).
   - Same-or-higher on-demand: no-op that class.

6. `consume.reset_cache()` after write.

### Checkpoint A (oracle-verifiable)

- Unit tests (tmp cache dir): persist an AST extract → file `Pack@on_demand_static-<sha>.json`; each class entry `source_kind==on_demand_static`; provenance row has `repo`+`locked_commit`+`extraction_rung==ast`+`registry_pack_version`; `index.json` maps the class to that file.
- Persist an import extract → `on_demand_import`, **not** `runtime_object_info`.
- Attempting to persist on-demand over an existing `runtime_object_info` / `@runpod-snapshot` row is a no-op; runtime file unchanged.
- A `@stub.json` index row is treated as a gap.
- **Mixed-pack case:** cache contains a runtime capture for class R of pack P; ensure extracts P (R + gap class G). Assert: `index[R]` still maps to the runtime file (byte-identical mapping), `index[G]` maps to the new on_demand file, and the on_demand file does not silently shadow R.
- `pytest tests/ -k "on_demand_persist or ensure_capture" -q` green.
- Commit this batch.

---

## Batch B — Rung 3 (embedded comfy-as-library) `[XHARD]` — DEFERRED (conditional follow-on; ship A/C/D/E first with r3 fail-closed; land B only if a real manifest class reaches r3)

**Seam:** `extract_pack_schemas` can return `method=="embedded"` without starting a server. No CLI yet.

**[XHARD] evidence:** no `extract_by_embedded` / `on_demand_embedded` exists (`extract.py:52–58` methods are `"import"|"ast"|""`). Closest code (`core_regen.py:91–152`) **starts `main.main` and hits `/object_info`** when `import main` succeeds — forbidden here (“NO server, no serve, no GPU”). Custom-pack `NODE_CLASS_MAPPINGS` against genuine `comfy` modules is net-new. Wrong implementation recreates a runtime-looking capture from a server boot.

**Non-goal boundary:** do not build pip/uv ComfyUI *runtime provisioning*. Throwaway venv, extract, delete.

### Tasks

1. Factor **only** the throwaway-venv + `pip install comfyui=={version}` helper out of `core_regen.py` so both regen-core and rung 3 share it. Do not share `_OBJECT_INFO_CAPTURE_SCRIPT`.

2. Add `extract_by_embedded(pack_dir, *, pack_name, version, only_classes=None, comfy_version, timeout, scratch_dir) -> (entries, "embedded")`:
   - Create venv under `tempfile.TemporaryDirectory` (or sandbox child); pip-install pinned `comfyui=={comfy_version}` (`core_regen.py:32,48` package template).
   - In a **child** interpreter: import real `comfy` / `nodes`; put `pack_dir` on `sys.path`; load pack `NODE_CLASS_MAPPINGS`; call `INPUT_TYPES()`; emit object_info-shaped JSON. **No** `main.main`, **no** bind, **no** `/object_info` HTTP, **no** GPU device init (fail closed if the child tries to serve).
   - Parent never imports `comfy`.
   - Always rmtree the venv (ephemeral). Do not install the pack into the user env.
   - Timeout env-tunable; default longer than import’s 120s (pip). On `TimeoutExpired`, return empty + failure string (do not crash the ladder).

3. Extend `extract_pack_schemas`:
   - Keep current order: import (if `allow_import`, **default True**) → AST if `entries` empty.
   - New: if still empty and `allow_embedded=True` (default **False** on the function; ensure will pass True), run rung 3.
   - `ExtractResult.method` becomes `"import"|"ast"|"embedded"|""`.
   - Do not change `OnDemandInstallSchemaProvider` gating (`VIBECOMFY_ON_DEMAND_BOOT`) — that is the live authoring ladder, not persist.

4. Unit tests with a **fake runner** (mirror `test_core_regen_runner_installs_pinned_comfyui_and_captures_object_info` in `tests/test_schemas_ensure.py:281–312`): assert pip command, assert child `-c` script does not reference `main.main` / `urlopen` / port `8188`, assert method `"embedded"`. No real PyPI in unit tests.

### Checkpoint B

- `rg 'extract_by_embedded|allow_embedded|on_demand_embedded' vibecomfy/schema/extract.py` hits the new API.
- Fake-runner test proves no server path.
- `extract_pack_schemas(..., allow_import=True, allow_embedded=True)` on a pack that succeeds at import never calls embedded (rung 3 is miss-only).
- Existing `tests/test_on_demand_resolver.py` still green (rung 1/2/LRU unchanged).
- Commit this batch.

---

## Batch C — `schemas ensure --manifest`

**Seam:** one command fills gaps for a comparison manifest and leaves LRU-bounded clones. Depends on A. (B is DEFERRED; this command ships with r3 fail-closed — `--no-embedded` semantics default until B lands.)

**Normal** (CLI glue; r3 is fail-closed unavailable until Batch B lands (if ever)).

### Tasks

1. Extend `register()` in `commands/schemas.py:643–648`:
   - Keep positional `template` (back-compat).
   - Add `--manifest PATH` (comparison manifest: `entries[].id`, as in `threaded_comparison_manifest_final50.json`).
   - Exactly one of template / `--manifest` required.
   - `--json`, `--comfy-version` (rung 3 pin; flag or env `VIBECOMFY_EMBEDDED_COMFY_VERSION` only — fail closed naming both if r3 is needed and unset (no core-cache sniffing)).
   - `--no-embedded` to skip rung 3; rung 2 **cannot** be turned off on this command (operator: r2 default-ON). Do not honor `VIBECOMFY_ON_DEMAND_BOOT=0` here.

2. Manifest gated-class discovery: reuse `load_scenario_obligation` + `_GATED_CLASS_RE`. Do not copy the regex. Input is the comparison manifest path; classes come from each entry’s source workflow + declared requirements. Template path keeps `_extract_class_types_from_template`.

3. For each missing live capture (Batch A helper):
   1. `resolve_pack(class_type)` / `resolve_missing_nodes` → `PackRef` with `url`. Registry REST is **pack metadata + optional provisional schema**; do **not** persist `/nodes/.../schema` as cache truth (provisional only, `pack_resolver.py:817`).
   2. Clone via `OnDemandInstallSchemaProvider._ensure_clone` (sandbox `~/.cache/vibecomfy/schema-sandbox`, LRU `max_packs=64` / `max_bytes=2GiB`). Do **not** use `.tmp_packs` / `clone_and_extract_packs.clone_pack`.
   3. `extract_pack_schemas(..., allow_import=True, import_timeout=120)` — NO `allow_embedded` kwarg (it does not exist until deferred Batch B lands; passing it TypeErrors). `--no-embedded` is accepted as a no-op placeholder documented as "r3 not yet available"; if a class can only be served by r3, fail closed naming deferred B.
   4. Map `result.method` → persist token; `git rev-parse HEAD` + remote URL + registry `PackRef.version`.
   5. `persist_on_demand_pack` (Batch A).
   6. `_enforce_cap()` after each pack (LRU preserved; no permanent install).

4. Fail closed:
   - Registry miss / clone fail / all rungs empty → non-zero exit (text **and** `--json`; fix current `emit`→0 swallow at `schemas.py:567–568`).
   - Message names the class, the failed step, and the exact retry: `vibecomfy schemas ensure --manifest <abs-or-given-path>`.
   - Never write a hollow/stub schema to close a gap.

5. Rewire the existing template `ensure` extraction off `tools.clone_and_extract_packs.process_pack` onto this glue (same persist/identity). Leave the standalone ETL tool untouched (out of scope).

6. Tests in `tests/test_schemas_ensure.py` that actually call `_cmd_schemas_ensure` (today they only inline the diff, lines 738–791):
   - noop when attested capture exists.
   - missing class → mocked `resolve_pack` + mocked clone dir + real `extract_pack_schemas` on a fixture pack → `build_cache` file + provenance.
   - r2 default: `allow_import` True even if `VIBECOMFY_ON_DEMAND_BOOT` is unset.
   - stub-indexed class is a gap.
   - `--json` failure is non-zero.
   - No network in this file.

### Checkpoint C

- `vibecomfy schemas ensure --help` shows `--manifest`.
- Fixture: missing gated class, mocked registry+clone, ensure writes `on_demand_*` + provenance, then `get_class` / index provider returns it; `@stub.json` still filtered.
- `rg 'clone_and_extract_packs' vibecomfy/commands/schemas.py` is empty.
- Commit this batch.

---

## Batch D — Preflight bridge `[XHARD]`

**Seam:** obligations preflight accepts persisted on-demand tiers as **themselves**, rejects stubs, strict stays runtime-only. Depends on A’s on-disk shape.

**[XHARD] evidence:** this is the R3 trust boundary. Today `_resolve_schema_locally` (`scenario_obligations.py:804–808`) only allows declaration `source=="authoritative_object_info"`, then `_provenance_row` (`777–780`) treats **any** file with `repo` or `locked_commit` as live capture — **it never reads cache `source_kind`**. Persisting on-demand with a git pin and leaving this gate unchanged would silently upgrade AST/import to “authoritative object_info” (North Star anti-pattern; campaign R3).

Preflight stays **local-only / no network**. It must **not** call `OnDemandInstallSchemaProvider.get_schema` (that clones). Acceptance is of **Batch A files**.

### Tasks

1. Expand declaration `source` allowlist to:
   `authoritative_object_info` | `on_demand_static` | `on_demand_import` | `on_demand_embedded`. (No alias: `on_demand_runtime` is invalid; stamp migrated in Batch A.)

2. After `ObjectInfoIndexSchemaProvider.get`:
   - Read the cache entry’s `source_kind` (from the pack JSON, not `NodeSchema.source_provider`, which index provider overwrites to `object_info_index` at `provider.py:592–604`).
   - Require `entry.source_kind` to match the **declared** source exactly (no aliases). A declaration of `authoritative_object_info` is **not** satisfied by `on_demand_*` (no masquerade). A declaration of `on_demand_static` is **not** satisfied by `on_demand_import` either (don’t upgrade).
   - Still require provenance `repo` or `locked_commit` (pin). Also require provenance `source_kind` to match the entry (if present).
   - Put the actual tier on the preflight payload: `resolution[scenario_id][class_type] = {ok, source_kind, extraction_rung, locked_commit}` (single surface: parallel `resolution_tiers` map; boolean payload untouched).

3. Stub rejection unchanged: keep `@stub.json` index filter. Add an explicit fail if a resolved file is stub-shaped (`source_kind==workflow_json_stub` or filename suffix) so a future index bug cannot pass.

4. Strict / runtime-only flag (**new**; current `require_schema_resolution` is a no-op, `scenario_obligations.py:949`):
   - `preflight_scenario_obligations(..., runtime_only: bool | None = None)`.
   - Env `VIBECOMFY_OBLIGATION_RUNTIME_ONLY=1` (do not reuse the dead `VIBECOMFY_OBLIGATION_SCHEMA_CHECK`).
   - When set: only `authoritative_object_info` declarations + runtime family cache `source_kind` (or `@runpod-snapshot` / `runtime_core` filenames) pass. On-demand is a violation naming the strict flag and `schemas ensure` is **not** claimed as enough.

5. Fail-closed copy: missing on-demand evidence must include `vibecomfy schemas ensure --manifest <that manifest>`.

6. Do **not** rewrite campaign `SCHEMA_EVIDENCE_REQUIREMENTS` for IndexTTS/LayerMask (they already have runtime captures). Do **not** change assessment rubrics.

7. Tests in `tests/test_scenario_obligation_preflight.py` + `tests/test_p4_objectinfo_caches.py`:
   - tmp cache: on-demand attested file + declaration `source=on_demand_static` → preflight ok; payload records `on_demand_static`.
   - same file vs declaration `authoritative_object_info` → fail (no masquerade).
   - `@stub.json` indexed+attested → fail.
   - `runtime_only=True` rejects on-demand even if declared `on_demand_*`.
   - existing FINAL5 IndexTTS/LayerMask still pass (runtime pins).
   - FINAL50 unproven classes still fail until declarations+captures exist (Batch E fixture, not silent pass).

### Checkpoint D

- `rg "only 'authoritative_object_info' is authoritative" tests/live_agentic_harness/scenario_obligations.py` is gone; allowlist is explicit.
- Tests above green.
- `pytest tests/test_scenario_obligation_preflight.py tests/test_p4_objectinfo_caches.py -q` green.
- Commit this batch.

---

## Batch E — Doctor gap reporting, docs, e2e

**Seam:** a previously blocked **fixture** manifest goes ensure → preflight green using only on-demand captures. SKILL.md documents the flow.

**Normal.**

### Tasks

1. Shared `format_schema_gap(manifest_path, missing_classes) -> str` ending with the exact command  
   `vibecomfy schemas ensure --manifest <path>`.

2. `schemas validate-coverage`: add `--manifest`. Report gated classes lacking live captures (Batch A helper). Exit **1** when `--manifest` and gaps exist (template positional keeps today’s exit 0 for back-compat). JSON includes `missing_classes`, `ensure_command`.

3. `vibecomfy doctor <path>`: on `unknown_class_type` / missing schema, print the same ensure command (workflow/template path: `vibecomfy schemas ensure <template>` if that’s the input; if a manifest is not in hand, still print the templates form plus “or `--manifest <comparison.json>`”). Do not make doctor clone or extract.

4. `docs/agent-skill/SKILL.md`: one section, mechanical:
   - missing capture blocks preflight;
   - `vibecomfy schemas ensure --manifest <m>` (registry → ephemeral clone → r1/r2/r3 → cache + provenance tier);
   - preflight accepts `on_demand_*` as those tiers; `@stub.json` never;
   - campaign-grade: `VIBECOMFY_OBLIGATION_RUNTIME_ONLY=1`;
   - doctor / `schemas validate-coverage --manifest` print the command.
   - Do not edit `docs/plans/**`.

5. E2E (deterministic, no GPU, network gated):
   - Track a tiny comparison-manifest fixture + one synthetic gated class + a local fixture pack (not a hand-authored `@stub.json` presented as live).
   - Empty tmp cache → preflight fails with the ensure command → `ensure --manifest` (registry mocked; extract real on fixture pack) → preflight green; recorded tier is `on_demand_static` or `on_demand_import`.
   - Optional host-only (skip if `api.comfy.org` unreachable — stop condition): one real UNPROVEN class (e.g. from `image-generates-a-2x2-seed-variation`) against the registry. If registry is down: `blocked`, do not fake schemas.

6. Evidence matrix (commit in `.oracle/evidence/` or test docstrings, not `docs/plans/**`): command, source_kind, commit, rung, preflight verdict, strict verdict, stub verdict.

7. Host once: `pytest tests/ -k "schema or on_demand or obligation" -q` and full suite.

### Checkpoint E (done criteria)

- All four agent-goal items present in code.
- Focused pytest green; host full suite once.
- Fixture manifest: missing → ensure → preflight green **using only on-demand captures**.
- SKILL.md section exists.
- Final oracle review of the four-item contract.

### Sync after PASS (authorization)

- Push `oracle-run` to origin (no force).
- Fast-forward `main` to the reviewed merge; record refspec.
- No deploy.

---

## Synchronization

```
A persist identity
    → C ensure --manifest (r3 fail-closed; B deferred)
            → D preflight allowlist (can start after A; must not merge before A’s on-disk shape is stable)
                → E doctor + SKILL + e2e
```

Do not rescan/rewrite A–C while D is in flight. Each batch is one commit. If D review finds a stamp bug, reopen A (that is the honesty contract), don’t patch D to “treat on-demand as authoritative_object_info”.

---

## Additional areas to explore (max 3, only if material)

1. **Rung 3 feasibility of PyPI `comfyui` as a library** — can a child venv `import nodes` + load a third-party pack’s `NODE_CLASS_MAPPINGS` without GPU and without `main.main`? If the package always pulls torch-GPU or always serves, rung 3 must fail closed with that reason rather than boot a server. **Do this before implementing Batch B.**
2. **Default `--comfy-version` pin** — confirm `0.24.0.1` (hiddenswitch / `comfy_core@object_info_comfyui_0.24.0.1.json`) is still the intended library pin, or require the flag always.
3. *(skip unless 1 fails)* Registry `GET /nodes/{id}/versions/{v}/schema` completeness. Already known to be provisional (`pack_resolver.py:817`, `ProvisionalRegistrySchemaProvider`). **Must not** become cache truth even if it looks complete.

---

## Open questions (oracle)

1. **Rung-2 persist token.** Agent goal persist list is `on_demand_import`; live provider and North Star say `on_demand_runtime`; planning-brief item 2 says `on_demand_runtime`. RESOLVED: persist `on_demand_import`; preflight accepts only canonical tiers (no `on_demand_runtime`).

2. **Campaign UNPROVEN declarations.** FINAL50 stays red until `SCHEMA_EVIDENCE_REQUIREMENTS` rows exist with `source=on_demand_*`. Non-goal says no assessment-rubric edits. Plan default: **fixture e2e only**; do not add campaign rows in this run. If the oracle wants a real previously-blocked scenario green, authorize adding declarations (not rubrics) for one subset id (candidate: `image-generates-a-2x2-seed-variation`).

3. **Rung 3 if pip `comfyui` is missing / version unset.** Plan default: skip rung 3 with an explicit failure string; do not fall back to server regen-core; overall class remains missing (fail closed). Confirm vs hard-require `--comfy-version` whenever `--manifest` is used.

---

## North Star check (anti-patterns)

| Anti-pattern | How this plan avoids it |
|---|---|
| Hand-authored / stub as authoritative | Gaps never filled with `@stub.json`; stub filter stays; e2e extract from fixture pack source |
| Permanent pack installs / venvs | Clone sandbox LRU; r3 `TemporaryDirectory`; no `nodes ensure` install path |
| Unactionable preflight wall | Every miss names `vibecomfy schemas ensure --manifest <m>` |
| Parallel schema systems | No new parser; ladder + `build_cache` + existing ledger |
| Silent tier upgrade | Distinct `source_kind`; declaration must match entry; `authoritative_object_info` ⇏ on-demand; strict flag |

Aligned progress: A makes the stamp honest; C shortens “blocked: missing capture” to one command; D lets the harness run **without lying**; E makes the command discoverable.

---

## Effort and huge-run

**Not a huge run** (≪ 2 weeks). Best effort: **4–7 focused days**

- A: 0.5–1d  
- B: DEFERRED (1.5–2.5d if ever needed)  
- C: 1d  
- D: 0.5–1d  
- E: 0.5–1d  

Rung 3 exploration (item 1) may cut B if pip-comfy cannot load packs without serving; then ship r1+r2 ensure + fail-closed r3 stub and re-scope r3 — still not a huge run.

---

## Classification per batch

| Batch | Class | Why |
|---|---|---|
| A Persist + identity | **normal** | Glue around `build_cache` / provenance; load-bearing but local |
| B Rung 3 embedded | **[XHARD]** | Net-new extract; must not reuse `core_regen` server; process-isolated genuine `comfy` |
| C `ensure --manifest` | **normal** | CLI + existing resolve/clone/extract |
| D Preflight bridge | **[XHARD]** | Trust boundary of the R3 incident; smallest wrong patch masquerades on-demand as runtime |
| E Doctor, SKILL, e2e | **normal** | Reporting + fixture |

Implementer model per operator: Normal = ox-alpha; [XHARD] = Grok 4.6.

