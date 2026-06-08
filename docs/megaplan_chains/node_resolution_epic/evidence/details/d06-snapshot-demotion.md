Here is my analysis.

---

## (a) Is the doc accurate on this point? **PARTLY.**

The doc correctly identifies the problem: `build_cache` replaces `index.json` wholesale (drops packs not in the source). Evidence:

- **`serialize.py:137`** — `index: dict[str, str] = {}` — starts from scratch every time.
- **`serialize.py:148-149`** — writes the new index.json covering ONLY packs in the current source dump.
- **`schemas.py:111-112`** — `_copy_structured_cache` copies ALL files including the source's `index.json`, also wholesale replace.

The doc claims "per-pack, mergeable fallback" as the target architecture. The per-pack FILE STRUCTURE exists (`<pack>@<version>.json`). But it is NOT mergeable today — the only merge code path is `_copy_single_structured_cache_file` at **`schemas.py:129-139`**, which reads the existing index and adds entries. This is a secondary path, not the primary `build_cache` flow.

The doc also claims "Core regenerated trivially from a pinned pip-installable ComfyUI." This does NOT exist. Core packs (`comfy_core`, `comfy`, `comfy_extras`) are captured as `@runpod-snapshot` — a monolithic dump pinned to ComfyUI 0.18.2 (**`comfy_metadata.json:7`**). There is zero integration with `pip install comfyui==<version>`.

The version string is hardcoded to `"runpod-snapshot"` at **`serialize.py:96`**, making per-pack versioning impossible from the `build_cache` path.

---

## (b) Top 3 concrete risks / missing pieces

1. **`build_cache` has no merge logic and cannot be patched in-place.** Lines 137-149 create a new index from scratch. Making this merge-aware requires: read existing index, classify entries by pack file, for packs in the new source overwrite their file + update index entries, for packs NOT in the new source preserve both file and index entries. Simple to code, but MUST be done — the current behavior silently drops entries.

2. **Core regeneration from pinned pip-comfy is a new subsystem.** There is no code path that does `pip install comfyui==X.Y.Z` → boot → dump `/object_info` → feed into cache. ComfyUI doesn't expose a headless `/object_info` dump without the full server. The doc's "CPU-only" assumption may not hold — ComfyUI still requires PyTorch. This is the heaviest lift in the proposal.

3. **Version collision between core and custom packs.** Currently all packs share version `"runpod-snapshot"` (**`serialize.py:96`**). In the proposed model, `comfy_core@0.24.0.json` and `ComfyUI-KJNodes@abc1234.json` coexist. But `pack_key_from_module` (**`serialize.py:29-45`**) maps `python_module="."` → `"comfy_core"`, and there's no distinction between core classes (`nodes.py`) and extras classes. Several packs map to the same ComfyUI version — the merge must handle upgrading ALL core packs atomically when the ComfyUI version changes. If only `comfy_core` is regenerated but `comfy_extras` stays at the old version, you get silent schema skew between related core classes.

---

## (c) Specific recommendation

**Implement merge in `build_cache` first** — it's the smallest change with the highest leverage. Replace lines 137-149 with: load existing `index.json` → build a `{pack_filename: [class_types]}` reverse map → for each pack in the new source, write/overwrite its file and update index entries for its classes → write the merged index. This preserves packs not in the source (stubs, local captures) while still refreshing the ones that are.

Then add a `--version` parameter to `build_cache` (line 113) that flows into `_make_cache_entry` (line 96), so the version string is no longer hardcoded. Core regeneration from pip-comfy can be a separate CLI command (`vibecomfy schemas regen-core --comfy-version 0.24.0`) that shells out to pip, boots ComfyUI CPU-only to dump `/object_info`, and feeds the result through the now-merge-capable `build_cache` with `--version="0.24.0"` and a pack filter for core packs only.