Now I have all the pieces. Here's my assessment:

---

## (a) Is the doc accurate on this point? **PARTLY**

**The doc's core claim** in Section 5 #1 + Section 6 is that "in-process node enumeration" should be preferred over booting a server, and that this would be lighter/faster than the current live `/object_info` path. The diagnosis of the problem (Section 4 #1) is correct: `ConversionSchemaProvider` (`provider.py:467-582`) checks `node_index → object_info_cache → source_parser → widget_schema → runtime (last, off by default)`. Runtime is the lowest-priority fallback for porting, and that's exactly the root-cause bug.

But the doc's **prescription** is imprecise in three ways:

1. **"In-process node enumeration" is NOT light.** `import_all_nodes_in_workspace()` (`vendor/ComfyUI/comfy/nodes/package.py:163-230`) does a full recursive import of `comfy_extras.nodes` (hundreds of modules including `nodes_glsl`, `nodes_audio`, etc.), plus all entry-point custom nodes. This has the **same import cost** as a full ComfyUI boot, minus only the HTTP server startup and model-management init. The doc implies it's a cheap alternative; it isn't. After the imports, individual `node_info()` calls (`vendor/ComfyUI/comfy/cmd/node_info.py:8-55`) are cheap (~microseconds), but you pay the import tax upfront.

2. **A single-node schema without a full boot IS possible — via AST.** The `SourceSchemaProvider` (`provider.py:211-231`) already reads `INPUT_TYPES()` returns and `RETURN_TYPES`/`RETURN_NAMES` class attributes by parsing `.py` files with the `ast` module. This requires zero imports. The doc barely mentions it and proposes the heavy in-process import instead, missing that AST introspection could be improved (e.g., better handling of dynamic `INPUT_TYPES()`) to cover more nodes without any boot cost.

3. **The existing codebase already has a live-first path — but only for execution.** `RuntimeSchemaProvider` (`provider.py:665-710`) boots `comfyui serve` and hits `/object_info`. The execution path uses this. The porting path doesn't. The doc is right to want unification, but creating a third mechanism (in-process enumeration wired into `ConversionSchemaProvider`) is more complex than just moving `RuntimeSchemaProvider` up the precedence chain in `ConversionSchemaProvider.get_schema()`.

---

## (b) Top 2-3 concrete risks / missing pieces

1. **In-process import time:** `import_all_nodes_in_workspace()` is 5-30s cold (depends on how many custom-node packs are installed) vs. `SourceSchemaProvider`'s ~50ms per file. The doc's "light & efficient" mandate is violated if the in-process approach becomes the default for `ConversionSchemaProvider`. The strategy conflates "don't boot a server" with "don't do heavy imports" — the imports ARE the heavy part.

2. **OpenGL/glfw import-time `RuntimeError` in `nodes_glsl.py:70`:** `_check_opengl_availability()` raises when `glfw` or `PyOpenGL` are missing. This is swallowed by `import_all_nodes_in_workspace(raise_on_failure=False)` (line 111/139 in `package.py`) but still logged as an error. On macOS, `_init_glfw` bails early (line 173). This means GLSL node schemas are simply absent from the in-process mapping — a silent degradation, not a crash. The av/cv2 dylib clash is a pip-environment issue that manifests at import time for specific nodes; similarly swallowed with `raise_on_failure=False`. Neither is a hard blocker, but both silently reduce schema coverage.

3. **No selective/single-node import mechanism.** ComfyUI's node package structure (`comfy_extras/nodes/`) is monolithic — you can't import just `KSampler`'s module without importing the entire `comfy_extras.nodes` package. A "light" in-process approach would need a way to import only the specific module containing the target class. The doc proposes "memoize per `(pack, git_sha)`" but doesn't address the import granularity problem — the existing `class_schema_sha256` in the lockfile is per-pack, not per-class.

---

## (c) Specific recommendation

**Don't build an in-process import path for porting.** Instead:

1. **Flip `ConversionSchemaProvider` precedence** so `RuntimeSchemaProvider` (when available — i.e., a warm server or quick `comfyui serve` boot) is checked *before* cached snapshots. This directly closes the staleness bug and requires zero new infrastructure — it's a ~10-line change in `provider.py:467-582`.

2. **For the "no server" case, improve `SourceSchemaProvider`** (AST-based). Add a `RETURN_TYPES`/`RETURN_NAMES` dynamic-eval fallback for nodes where the AST literal-eval fails (e.g., when `INPUT_TYPES()` calls a helper function). This is the genuinely zero-boot path that satisfies "visualize stays cheap."

3. **Reserve in-process `import_all_nodes_in_workspace`** for the `ensure-env` orchestrator (Section 5 #3 prox) — run it once after installing packs, cache the result as the per-pack `class_schema_sha256`-keyed snapshot, and never run it again for schema lookups on a warm cache.