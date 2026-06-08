Here is my assessment:

---

## (a) Is the doc accurate on this point? **PARTLY NO**

The doc claims the lockfile fields (`git SHA + version + class_schema_sha256 + class_set + pip_packages`) are sufficient for schema drift detection, memoization, and exact reproduction. The code tells a different story:

**Drift detection broken in two ways:**
1. `compute_schema_hash` (`node_packs_lockfile.py:286`) — hashes the canonical *schema projection* (inputs/outputs/order). This function is **never called in any production code path** (only `tests/test_nodes_lock.py:326`). The schema_hash values in `custom_nodes.lock` were populated externally/manually.
2. `_compute_pack_schema_hash` (`runtime/drift.py:277-300`) — hashes **all .py file bytes** in the pack directory. These two hash functions compute fundamentally different values and will **never match**. If drift detection actually runs, schema_hash comparison always produces false-positive mismatches.

**Memoization key not wired:** The `class_schema_sha256` is proposed as the memoization key in §5#1 ("Memoize per (pack, git_sha) using the lockfile's class_schema_sha256 as the cache key"), but no code uses it that way. The schema cache system (`vibecomfy/porting/cache/object_info/`) uses pack name + version as filenames, not the hash. The `ConversionSchemaProvider` (line 467) looks up schemas from `node_index.json` first, then object_info cache — no hash-keyed memoization exists.

**Reproduction holes confirmed:**
- `version = "unknown"` for **every single pack** in `custom_nodes.lock` (lines 7, 21, 35, 49, 62, 76, 90, 102, 117, 131)
- `pip_packages` are unpinned top-level names only: e.g., `["opencv-python-headless", "transformers"]` (line 15) — no version constraints, no transitive deps, no hashes
- No ComfyUI core version pin
- No Python/torch/CUDA version info

---

## (b) Top 3 concrete risks

1. **`compute_schema_hash` is dead code.** It exists (`node_packs_lockfile.py:286`), is stable/deterministic, but has zero production callers. The lockfile's schema_hash values are orphaned — they were populated by an unknown external process and will never be refreshed by any automated pipeline. When a pack's schema changes, the hash won't update.

2. **Drift detection's schema comparison is an algorithm mismatch.** `_compute_pack_schema_hash` (file-content SHA-256, `drift.py:289-298`) is compared against `compute_schema_hash` output (schema-projection SHA-256, `node_packs_lockfile.py:287-293`). These are different algorithms producing different hashes for the same pack. Every schema drift check that runs will flag a false mismatch.

3. **`version` is universally "unknown" — no semantic version pinning.** Combined with unpinned transitive pip deps, the lockfile can reproduce the exact git commit of each pack but NOT the Python environment. A `pip install` of `transformers` without a version pin will resolve to whatever is latest at install time, making environments non-reproducible.

---

## (c) Specific recommendation

Wire `compute_schema_hash` into the install path. Add a call at `node_packs_install.py:136-137` (after `_lock_entry_for_pack`) that:
1. Introspects the freshly installed pack's `/object_info` (or uses `SourceSchemaProvider`) to get live class schemas
2. Calls `compute_schema_hash` on the result
3. Passes it into `LockEntry(..., class_schema_sha256=hash)` so it's persisted

Then fix `_compute_pack_schema_hash` (`drift.py:277`) to use the SAME `compute_schema_hash` function (not a file-content hash), OR add a separate field (`source_sha256` already exists for file-level integrity). The two hash semantics (schema shape vs. source bytes) must not be conflated in one comparison.