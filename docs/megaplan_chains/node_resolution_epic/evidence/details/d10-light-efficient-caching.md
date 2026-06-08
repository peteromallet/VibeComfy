Now I have all the evidence. Here's my pressure-test of Section 6:

---

## (a) Is the doc accurate on this point?

**Partly.** The doc's conceptual framing is sound: `class_schema_sha256` exists in the lockfile data model (`node_packs_lockfile.py:31`), per-pack cache files exist on disk at `porting/cache/object_info/<pack>@<version>.json`, and the lockfile already maps packs to their classes (`class_set`) and commit SHA. So the *scaffolding* for `(pack, git_sha)`-keyed memoization is mostly present.

But the doc's claim that `class_schema_sha256` "already gives a stable key" is misleading in two ways. First, **zero code uses `class_schema_sha256` as a lookup key** — it's stored (lockfile:124-125), preserved on upsert (lockfile:143-162), and checked for drift (`drift.py:161-162`), but no schema provider consults it. Second, `class_schema_sha256` is a derived hash of schemas — you need schemas to compute it, making it a **verification hash**, not a cold-start lookup key. For the "visualize without installing" use case, the actual lookup key must be `(pack, git_sha)`, with `class_schema_sha256` used to validate cache freshness post-hoc.

Evidence: search for `class_schema_sha256` across the codebase yields 23 hits — all are storage/read/write/drift, zero are schema-provider cache-key lookups.

---

## (b) Top 2-3 concrete risks or missing pieces

1. **The porting emitter bypasses the ConversionSchemaProvider entirely for arity.** `emitter.py:1947` calls `require_class_output_count()` which hits `consume.py`'s `_resolve_class_type()` → `index.json` → per-pack JSON files. This is the old object_info cache path, NOT the `ConversionSchemaProvider` chain the doc proposes to reorder. Flipping `ConversionSchemaProvider` to live-first (per §8 step 1) won't fix the arity-disagreement bug that caused the crash — the emitter never calls it. **File:line**: `emitter.py:1947`, `consume.py:162-168`.

2. **No mechanism to lazily install-then-resolve per-pack.** The doc says "only install what a given workflow needs (provenance-scoped)" but the current code has no orchestrator that, given `class_type`, finds its pack via registry+lockfile, installs just that pack at the right commit, then AST-parses its `INPUT_TYPES`. `SourceSchemaProvider` (`provider.py:211-231`) only scans pre-existing directories; `node_packs_install.py` installs packs but doesn't feed back into schema resolution. These are disconnected. **File:line**: `provider.py:211-231`, `node_packs_install.py:99-138`.

3. **`class_schema_sha256` is registry-dependent for cold-start.** At install time, `node_packs_install.py:205` sets `class_schema_sha256=pack.class_schema_sha256` from the `CustomNodePack` registry object. If the registry doesn't carry this hash (many packs won't), the lockfile entry has `None`. This means for uninstalled packs, you cannot verify cached schemas post-install — you'd need to compute the hash AFTER install (via `compute_schema_hash`, `lockfile.py:286`), but install defeats the "cheap path" goal. **File:line**: `node_packs_install.py:191-206`, `node_packs_lockfile.py:286-293`.

---

## (c) Specific recommendation

Use `(pack_slug, git_commit_sha)` as the cache lookup key (not `class_schema_sha256`). Resolve `class_schema_sha256` to a verification step: after retrieving a cached per-pack schema file, SHA256-hash its canonical projection and compare against the lockfile entry. Plug this as a new `LockfileSchemaProvider` inserted **before** `ObjectInfoSchemaProvider` but **after** `LocalSchemaProvider` in `ConversionSchemaProvider.get_schema()` (around `provider.py:484`). The provider reads the lockfile, maps `class_type` → pack entry → `(slug, git_sha)`, checks `cache/object_info/<slug>@<git_sha>.json` on disk, and if present with matching hash, returns schemas from it — no install, no boot. Also wire `require_class_output_count` (`consume.py:311`) to consult this same lockfile-backed cache so the emitter benefits from the fix.