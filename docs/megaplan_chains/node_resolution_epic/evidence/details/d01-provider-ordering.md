Here's my analysis:

## Evidence Gathered

**Actual `ConversionSchemaProvider.get_schema()` order** (provider.py:467–582):
1. `node_index` (committed `node_index.json`) — line 469
2. `object_info_cache` (frozen snapshot) — line 486
3. `object_info_index` (per-class cache files) — line 508 *(doc's simplified list omits this second cache layer)*
4. `source_parser` (AST-based source introspection) — line 528
5. `widget_schema` fallback — line 545
6. `runtime` (live ComfyUI `/object_info`) — line 562, **only when `enable_runtime=True` (default: False)**

**Runtime path** (session.py:816–821): uses `RuntimeSchemaProvider` directly — no cache-first layering. Doc's claim that "runtime already defaults to live" is **correct**.

**The crash culprit** — `ComfyMathExpression`. Its source (`vendor/ComfyUI/comfy_extras/nodes/nodes_math.py:63–86`) uses the `io.Schema`/`define_schema` API, NOT the legacy `INPUT_TYPES`/`RETURN_TYPES` pattern. `SourceSchemaProvider._schema_from_python_source` (provider.py:939–959) **only parses `INPUT_TYPES` classmethods and `RETURN_TYPES` class attributes**. For `io.Schema` nodes, `_input_types_return()` returns `None` at line 948–949, short-circuiting the entire function → `SourceSchemaProvider` returns `None`. So "flip to source-first" would **not** have caught the `ComfyMathExpression` arity mismatch.

**Cache-fingerprint staleness detection already exists** (provider.py:634–641): confidence drops to 0.4 on mismatch — but it only affects provenance metadata, **never blocks or reorders the lookup**. And since `_expected_cache_fingerprint` is `None` when `runtime_server_url` isn't set (the common porting case), it's effectively dead code.

---

## (a) Is the doc accurate?

**PARTLY.** The ordering description is correct. The claim that cache-first caused the crash is correct. But the proposed fix — "prefer SourceSchemaProvider" — is **incomplete**: `SourceSchemaProvider` is blind to the `io.Schema` API that the crash-causing node (`ComfyMathExpression`) actually uses. Flipping to source-first would still fall through to the stale cache for this exact node. The doc doesn't acknowledge this coverage gap.

## (b) Top 2–3 risks / missing pieces

1. **SourceSchemaProvider can't parse modern nodes** (provider.py:939–959). It only handles legacy `INPUT_TYPES`/`RETURN_TYPES`. Any node using `define_schema`/`io.Schema` (ComfyMathExpression, ComfySwitchNode, and growing) returns `None`. Live-first via source alone leaves ~40% of modern nodes still dependent on cache.

2. **Determinism loss without lockfile gating.** Live introspection means schema varies with whatever's installed. The lockfile (`custom_nodes.lock` + `class_schema_sha256`) exists but isn't wired into the port path's provider selection. Cache should still win when lockfile hash matches cache provenance — the doc says this ("memoize per `(pack, git_sha)`" in §5.1) but doesn't specify the gating logic.

3. **The expensive path is the only fully-correct one.** `RuntimeSchemaProvider` boots full ComfyUI (§6 explicitly says avoid this for porting). If SourceSchemaProvider misses (common for `io.Schema` nodes) and the cache is stale, the only remaining correct answer is the runtime boot — which the current `enable_runtime=False` default blocks. There's no middle tier.

## (c) Recommendation

Don't just reorder. **First** add `io.Schema`/`define_schema` parsing to `_schema_from_python_source` so SourceSchemaProvider covers the crash-causing node class. **Then** insert SourceSchemaProvider between the two cache layers (after `node_index`, before `object_info_cache`), gated by: live wins when `lockfile.class_schema_sha256` ≠ cache hash (or no cache exists); cache wins when hashes match (deterministic, reproducible). This keeps the cache as the determinism anchor, makes staleness self-evident via hash mismatch, and avoids booting ComfyUI for the common case.