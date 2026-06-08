Now I have all the evidence. Here's my analysis:

---

## (a) Is the doc accurate on this point?

**PARTLY.** The doc claims `cnr_id` is "carried through" at `ui_emitter.py ~903-919`. The truth is more nuanced:

- The pass-through mechanism works, but it's at **`_resolve_furniture()` (line 243-304)** + **`_emit_litegraph_node_dict()` (line 903-905)**, not specifically at 903-919. The furniture resolver reads `properties` from the sidecar or `node.metadata['_ui']` (line 268/278), and the emitter copies the captured blob verbatim (line 903-905). Lines 909-919 overlay identity keys (`vibecomfy_uid`, `vibecomfy_id`, `Node name for S&R`) but never touch `cnr_id`/`aux_id`/`ver`. So the claim is directionally correct but imprecise about where it happens.

- The doc says vibecomfy "never parses it" — this is **correct**. Zero source references to `cnr_id` exist in `vibecomfy/vibecomfy/*.py`. It survives only as an opaque property-bag passenger.

- However, the doc's claim about the **format** is incomplete: it mentions `cnr_id`/`aux_id`/`ver` but doesn't note that `ver` is a **git commit SHA** for custom packs (not a semver), and `aux_id` is a **GitHub owner/repo** string — critical for the resolve_pack() mapping.

## (b) Top 3 concrete risks / missing pieces

**1. `resolve_pack()` has no version-pin parameter.** (pack_resolver.py:64-94)
The resolver returns `PackRef.version` = the registry's `latest_version`, not a specific commit. The workflow's `ver` field (a git SHA like `3869b0482b6...`) cannot be passed through. To install "the version the workflow was authored on" (doc §5.2), you'd need either a new `resolve_pack(slug, version=sha)` API or a post-resolution `git checkout <sha>` step. Currently `install_pack()` (node_packs_install.py:99-138) clones HEAD unconditionally.

**2. `aux_id` is completely absent from the codebase.** Zero source references. 12 corpus workflows have nodes where `cnr_id` is `null` but `aux_id` is present (e.g., `"aux_id": "yuvraj108c/ComfyUI-Video-Depth-Anything"`). The doc doesn't distinguish these as a separate resolution path, but in practice they're the only identifier on some nodes. The `aux_id` format is `owner/repo` — would need a GitHub API or URL-construction fallback distinct from the registry path.

**3. No lockfile reconciliation exists.** The lockfile (custom_nodes.lock) stores `version = "unknown"` for every entry (line 7, 21, 35, 49). There's no code that reads `cnr_id`/`ver` from a workflow and checks whether the installed pack matches. The doc's proposed flow (§5.2: "resolve each node to a pinned pack version via the registry; reconcile against the lockfile") is entirely absent — it would require a new module that extracts `cnr_id`/`ver`, calls `resolve_pack` (extended for version pinning), compares against `read_lockfile()` entries, and triggers `restore_pack()` if pinned SHA ≠ installed SHA.

**Bonus: 8% of real workflows lack provenance entirely** (wan_t2v.json, wan_i2v.json, wan13b_control_lora.json — 47 nodes across 3 files). The doc acknowledges "provenance gaps" (§7) but proposes no concrete fallback for this case.

## (c) Specific recommendation

Don't build a standalone "provenance parser." Instead, extend `resolve_pack()` with an optional `pin_version: str | None` parameter that, when provided, returns a `PackRef` with `commit=pin_version` and `version=pin_version` (skipping registry version lookup). Then add a lightweight `extract_provenance(workflow_json) → dict[str, tuple[str, str]]` that collects `(cnr_id or aux_id, ver)` per class_type. The orchestrator (§5.3) feeds this map into the extended `resolve_pack()` → `restore_pack()`. For the provenance-less tail, fall back to class-name→registry resolution with a warning, not silent "latest" — the doc's fail-closed principle (§5.4) must apply here too.