# Widget Alias Resolution

This document describes how `resolve_widget_name_with_provenance()` in
`vibecomfy/porting/widget_aliases.py` maps positional `widget_N` keys to
semantic field names during port conversion, and documents the dual-coverage
analysis of the two curated sources.

## Precedence ordering

Resolution runs five steps, stopping at the first hit.  **Curated-static
sources win over object_info** — a deliberate safety design to protect known
widget schemas from being overwritten by snapshot drift.

| Step | Source | Notes |
|------|--------|-------|
| 1 | `input_aliases` metadata on the node | Per-node alias list embedded by the workflow author or codemod |
| 2 | `WIDGET_SCHEMA` in `widget_schema.py` | Curated positional list; link-only sockets intentionally excluded |
| 3 | `WIDGET_SEMANTIC_NAMES` in `widget_schema.py` | Semantic patches for Primitive* nodes |
| 4 | Schema provider (authoring schema) | Compiled from installed custom-node `INPUT_TYPES` |
| 5 | Object_info cache (`consume.py`) | Guarded by `_object_info_position_is_safe()` sentinel check |
| — | raw `widget_N` passthrough | Emitted as-is; triggers `schema_backed_widget_alias_not_resolved` warning |

**Do not invert this order.**  WIDGET_SCHEMA excludes link-only sockets by
design; if object_info were consulted first it would shift widget positions
for any class whose object_info snapshot includes link inputs before widget
inputs (see Dual-coverage findings below).

## Why object_info is consulted last

Consulting object_info **last** (after curated WIDGET_SCHEMA) is a deliberate safety
design, not an ordering preference.  The sentinel guard `_object_info_position_is_safe()`
in `vibecomfy/porting/consume.py` checks whether an object_info snapshot's widget
positions match the curated schema before trusting it as a fallback.

**Sentinel-shift problem.** Object_info snapshots return the full input order —
including link-only sockets (MODEL, CLIP, VAE, IMAGE, LATENT, CONDITIONING, MASK,
AUDIO, VIDEO).  WIDGET_SCHEMA intentionally **excludes** those link sockets.
If object_info were consulted first, a `widget_0` lookup for `BasicScheduler`
would return `None` (the MODEL link input at position 0) instead of `scheduler`,
shifting every downstream widget name by one.

`_object_info_position_is_safe()` catches this by comparing the object_info order
against WIDGET_SCHEMA.  When they diverge at any index (as they do for 64 of the
112 curated classes), the guard prevents object_info from silently corrupting
the positional lookup — raw `widget_N` with a warning is safer than a wrong name.

### Guard conditions

| Condition | Result |
|-----------|--------|
| Class not in WIDGET_SCHEMA | Object_info is the only authority — used directly |
| Class in WIDGET_SCHEMA + orders match | Object_info confirms curated schema — safe to use |
| Class in WIDGET_SCHEMA + orders diverge | Guard blocks object_info — falls through to raw `widget_N` |

## Dual-coverage analysis (2026-05-25)

Analysis run against `vibecomfy/porting/cache/object_info/index.json` and
`vibecomfy/porting/widget_schema.py` at branch `scratchpad-emitter`.

| Metric | Count |
|--------|-------|
| WIDGET_SCHEMA classes | 112 |
| object_info cache classes | 1 401 |
| Classes in both | **112** (100 % of WIDGET_SCHEMA) |
| WIDGET_SCHEMA-only (no OI) | 0 |
| Divergent widget orders | **64** |

**All 112 WIDGET_SCHEMA classes have matching object_info coverage.**  Zero
classes are curated without a snapshot counterpart, confirming the cache is
a valid authoritative source for fallback lookup.

### Why 64 classes diverge

Every divergence follows the same pattern: `WIDGET_SCHEMA` lists widget-only
positions while `object_info_widget_order()` returns `None` for link-only
sockets at earlier positional indices.

Example — `BasicScheduler`:

```
WIDGET_SCHEMA:            ['scheduler', 'steps', 'denoise']
object_info_widget_order: [None, 'scheduler', 'steps', 'denoise']
```

The `None` at position 0 is the `MODEL` link input, excluded from
WIDGET_SCHEMA by design.  If object_info were consulted first the positional
lookup for `widget_0` → `scheduler` would instead return `None` (link input
dropped), shifting all widget names by one.

Some community nodes (`CannyEdgePreprocessor`, `DWPreprocessor`) return an
empty object_info order because their snapshot did not include the full widget
list for that environment.  WIDGET_SCHEMA fills the gap.

**Conclusion:** divergences are expected and correct.  WIDGET_SCHEMA is the
primary widget-only authority; object_info is the fallback for classes not in
WIDGET_SCHEMA.

## Diagnostic codes

The emitter **reuses** `schema_backed_widget_alias_not_resolved` rather than minting
a new code (SD3 compliance).  No `widget_alias_unknown` diagnostic exists.

| Code | File | Meaning |
|------|------|---------|
| `schema_backed_widget_alias_not_resolved` | `diagnostics/readability.py:49,172,181` | A `widget_N` field in a **curated** (WIDGET_SCHEMA-backed) class stayed unresolved after all five resolution steps. This is the **primary** widget-alias diagnostic — it fires at emission time when the emitter knows the class has a schema but could not resolve the positional key. |
| `widget_alias_unresolved` | `commands/nodes.py:801` | General unresolved alias during the `nodes audit` offline schema-analysis pass. Fires for **any** class (not just curated ones) when the schema provider has no matching alias. This is the offline/discovery diagnostic — broader than `schema_backed_widget_alias_not_resolved`. |
| `compiled_widget_input_missing` | `commands/nodes.py:801` | A widget input **expected** by the compiled schema is absent in the emitted output. Fires after `widget_alias_unresolved` when the missing input would make the compiled API dict invalid for the runtime. |

**How they relate:** `widget_alias_unresolved` is the broad offline scan (any class,
any provider).  `schema_backed_widget_alias_not_resolved` is the narrower,
emission-time check limited to classes that appear in WIDGET_SCHEMA — these
are the ones the emitter *should* be able to resolve, so an unresolved hit here
is always worth investigating.  `compiled_widget_input_missing` is the runtime
consequence — a missing input that would break execution.

Under `--strict-ready-template`, `schema_backed_widget_alias_not_resolved` is
escalated to a hard error for schema-backed classes.

## Refreshing the object_info cache

Run this when you have access to a live ComfyUI server (local embedded or
RunPod) to pull a fresh `object_info` snapshot:

```bash
python -m vibecomfy.cli nodes refresh-object-info
# or with explicit server:
python -m vibecomfy.cli nodes refresh-object-info --server-url http://127.0.0.1:8188
# write to a non-default directory:
python -m vibecomfy.cli nodes refresh-object-info --cache-dir /tmp/fresh-oi
```

The command fetches `/object_info`, writes per-pack files as
`<pack>@<version>.json` (default version: `live-snapshot`), and updates
`index.json`.  The committed `@runpod-snapshot.json` files remain on disk.

Offline convert and regen are unaffected: the committed cache files are
unchanged until you explicitly run `refresh-object-info`.

## Authoring guidance

- When adding a new class to `WIDGET_SCHEMA`, exclude all link-only socket
  names (`MODEL`, `CLIP`, `VAE`, `IMAGE`, `LATENT`, `CONDITIONING`, `MASK`,
  `AUDIO`, `VIDEO`).
- Use `port check --strict-ready-template` before promoting a template; it
  escalates unresolved `widget_N` to hard errors for schema-backed classes.
- `port simulate --rule widget_alias` tests the alias-resolution rule across
  the full corpus without writing files.
