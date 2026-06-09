# Sprint A — Correctness spine (`premium/thorough/high +prep`)

Shared context: read `docs/megaplan_chains/node_resolution_epic/STRATEGY.md` (v2, post-review — esp. §2 spine, §3 what exists, §4 what's broken, §5 target, §8 sequencing, §9 decision log) and `docs/megaplan_chains/node_resolution_epic/testing/testing.md` (the acceptance contract). This is sprint 1 of 3 in the Node Resolution Epic. vibecomfy ports raw ComfyUI workflows (`vibecomfy/porting/`) into curated Python "ready templates"; the porter reads node schemas from an offline snapshot keyed nowhere to the node's real identity. The headline regression is `fixtures/ideogram4_t2i.json`: a `ComfyMathExpression` node whose modern `io.Schema` API declares **3** outputs (`FLOAT/INT/BOOL`), while the stale 0.18.2 snapshot has **2** — which silent-miscompiles into an opaque `ValueError: not enough values to unpack (expected 3, got 2)` four layers down.

## Outcome
Wrong or skewed schema can no longer be consumed silently. The emitter fails **closed** at its real arity site with a typed error, executed `/object_info` introspection becomes the authoritative cache generator (covering `io.Schema` nodes that AST cannot see), `build_cache` merges instead of clobbering, and the `(pack_slug, git_commit)` identity / schema-hash plumbing is built and self-validating. This **closes the Ideogram silent-miscompile crash class**.

## Scope (IN)
Grounded in STRATEGY §5 (items 1–4) and §8 (steps 1–2), using only the verified anchors from §3/§4:

1. **Fail-closed, identity-aware arity consumption at the emitter's REAL site.** The emitter takes arity from `consume.py` (`require_class_output_count`), surfaced at `emitter.py:1947,4102` — it **bypasses `ConversionSchemaProvider` entirely** (§3 row "Emitter arity source", §4.1). At that site, compare the served schema's output count against the workflow's UI-declared count: cache outputs **< UI ⇒ raise** a typed `ArityDisagreementError` (stale snapshot); cache outputs **> UI ⇒ warn** (possibly-unused outputs), do not error (§5.1). The existing `UnknownNodeSchemaError` only covers *unknown* nodes; `class_is_known()` returns True for `ComfyMathExpression` and nothing currently compares counts (`consume.py:283`, §4.2). This is ~30 lines and is **the first move** — no install, no boot, no provider-chain reorder (§8.1).
2. **Executed introspection as the authoritative cache generator.** Per-pack schemas generated from `/object_info` / `node_info()` (`nodes_math.py:64`, §2/§5.2) — the only source correct for *all* nodes including the `io.Schema`/`define_schema` API. AST source (`SourceSchemaProvider`, `provider.py:988`) is **blind to `io.Schema` (returns `None`)** and is demoted to a low-confidence stopgap. Write generated schema to an **identity-keyed** cache file (`<pack>@<commit>.json`).
3. **Real identity plumbing.** Wire `compute_schema_hash` (today dead code) into the schema path; fix the `drift.py` algorithm mismatch where the hash is compared against a *different* (file-bytes) hash so it never matches (`node_packs_lockfile.py:286`, `runtime/drift.py:164,188`, §4.3). Lookup key is **`(pack_slug, git_commit)`**; `class_schema_sha256` is a *verification* hash, not the key (§5.3, §9).
4. **Merge-on-refresh cache.** `build_cache` currently rebuilds the index wholesale and drops packs (`serialize.py:137`, §4 "Offline cache"). Make it preserve packs not present in the refresh source; per-pack version, not one global tag (§5.4).

## Locked decisions (do not relitigate)
- **Schema authority is a resolved `(pack, commit)` identity + fail-closed** — not "live vs cache," not a frozen artifact (§2). A live boot of the *wrong* ComfyUI version miscompiles identically; the defect is missing identity + fail-open consumption (§9).
- **The FIRST move is fail-closed arity-disagreement at the emitter's real site, NOT flipping the provider chain to live-first.** v1's "flip the porter live-first" is dropped: the emitter bypasses `ConversionSchemaProvider`, AST is `io.Schema`-blind, `RuntimeSchemaProvider` is cache-shadowed (`provider.py:694`); reordering would not fix the crash (§9).
- **Executed `/object_info` introspection is the authoritative generator** of identity-keyed schema; the cache is the *serving* layer; **AST source is a low-confidence stopgap blind to `io.Schema`** (§2).
- **Cache key is `(pack_slug, git_commit)`; schema-hash is a verification hash**, not a memoization key — the schema-hash was dead code with a conflicting drift algorithm (§9).
- Directionality rule for fail-closed: cache `<` UI ⇒ error; cache `>` UI ⇒ warn (§5.1). UI-vs-cache directionality is enough for step 1 — no three-source arity triangulation yet (README non-goals, §8.1).

## Open questions (resolve in build)
- Where exactly the UI-declared output count is most reliably read for a node that lives inside a subgraph definition (the fixture has two subgraphs) — pick the consume-time source already available at `emitter.py:1947,4102`.
- The minimal `io.Schema` single-node fixture for scenario 4 (testing.md "Fixtures": sprints add it) — author one that `define_schema`s known outputs.
- Whether `evidence/object_info_comfyui_0.24.0.1.json` is the merge-source for the scenario 3 core-refresh test or whether a smaller slice suffices (§7 introspection-trust note applies to *running* code, not to consuming this static dump).

## Constraints
- **Cheap porting must NOT boot ComfyUI or run `import_all_nodes_in_workspace`** (§6) — that is ~a full boot (5–30 s). Correctness comes from identity + fail-closed, not from going live per-port. Live boot is reserved for cache generation and actual execution.
- **Executed introspection runs third-party node code** — a real trust/security surface; it must be **gated** (§7). Sprint A may generate cache entries from already-trusted/already-installed sources or from the committed `evidence/` dump; it does not silently execute arbitrary downloaded packs.
- No new failures vs baseline across the full suite.
- This sprint does **not** touch install execution or provenance resolution (those are sprint B).

## Done criteria
Maps to testing.md scenarios **1–5** (Definition of done → Sprint A). The runnable gate:
- `pytest -m sprint_a docs/megaplan_chains/node_resolution_epic/testing` goes **green** (un-skip scenarios 1–5; also wire the shipped form into `tests/`).
  - **1** Arity skew → porting `ideogram4_t2i.json` either compiles with correct arity or raises typed `ArityDisagreementError`; **assert no bare unpack `ValueError`** reaches the caller.
  - **2** Fail-closed unit: `require_class_output_count` / emitter arity site raises `ArityDisagreementError` naming the node + snapshot version + remedy when cache `<` UI; **warns** (not errors) when cache `>` UI.
  - **3** Core refresh does not clobber custom packs: after refreshing core from `evidence/object_info_comfyui_0.24.0.1.json` (merge), `WanVideoModelLoader` still resolves; `build_cache` merges.
  - **4** `io.Schema` coverage: executed introspection yields `["FLOAT", "INT", "BOOL"]` for `ComfyMathExpression`; AST's `None` is no longer authoritative.
  - **5** Identity + drift: lookup key is `(pack_slug, git_commit)`; `compute_schema_hash` wired at the schema path; drift uses one consistent algorithm — no false-positive mismatches.
- **Headline behavior (AFTER A** in testing.md's NOW/AFTER table): porting `ideogram4_t2i.json` is **never** an opaque `ValueError` — either it ports to a compiling template with correct arity (cache current) **or** it fails closed with `ArityDisagreementError` naming `ComfyMathExpression`, the snapshot version, and the remedy. Silent miscompile is impossible.
- Full `pytest` shows **no new failures** vs baseline.

## Touchpoints
From §3/§4 anchors: `vibecomfy/porting/consume.py` (`require_class_output_count`, `:283`), `vibecomfy/porting/emitter.py:1947,4102`, `vibecomfy/porting/provider.py:694,988`, `vibecomfy/node_packs_lockfile.py:286` (`compute_schema_hash`), `vibecomfy/runtime/drift.py:164,188`, `vibecomfy/porting/serialize.py:137` (`build_cache`); new typed error `vibecomfy/errors.py` (`ArityDisagreementError`) and `vibecomfy/porting/object_info.py` (`check_output_arity_consensus`, `class_is_known`, `output_names`) per the gate imports; the executed-introspection generator around `nodes_math.py:64`.

## Anti-scope
- Per README "Explicit non-goals": **no universal node-schema registry**; **no SAT-solver cross-pack dependency resolver** (preflight + fail-closed only — and that preflight is sprint B); **no three-source arity triangulation in step 1** (UI-vs-cache directionality is enough); **no speculative any-backend abstraction**.
- `vibecomfy/templates.py`, `vibecomfy/runtime/eval_plan.py`, and `vibecomfy/porting/edit_apply.py` are known direct `object_info` consumers, but Sprint A's correctness fix is scoped to the raw-workflow porting emitter path. Those consumers are follow-up work outside this sprint's acceptance contract.
- This sprint does **NOT** touch install execution (`node_packs_install.py`), the `ensure-env` orchestrator, provenance parsing, version-pinning, `resolve_pack`, or snapshot demotion/auto-generation — those are sprints B and C.
- Do not boot the full runtime for porting; do not execute untrusted downloaded packs to generate cache entries.
