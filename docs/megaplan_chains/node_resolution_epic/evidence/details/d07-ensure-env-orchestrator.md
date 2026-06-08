Here's my analysis:

---

**(a) Is the doc accurate on this point? PARTLY.**

The doc says "The pieces (resolve → install → introspect) exist but aren't strung together" (Section 4 gap #3). This is half-true. Some fragments exist, but the claim in Section 5 #3 that the orchestrator is merely "composing existing fragments" understates the gap considerably. Two of the four necessary pipeline stages are entirely missing.

**What exists:**
- **Resolve**: `missing_packs_for_workflow` (`node_packs_install.py:172-189`) maps workflow nodes → class_types → packs via `resolve_node_packs`. Registry-backed class→pack resolution works (`pack_resolver.py:64-94`).
- **Install**: `install_pack` / `restore_pack` (`node_packs_install.py:99-162`) with lockfile pinning (`node_packs_lockfile.py`).
- **Introspect (live)**: `RuntimeSchemaProvider` (`session.py:821`) hits `/object_info`. Used in the run path but not in the install path.
- **CLI stub**: `_cmd_nodes_ensure` (`commands/nodes.py:317-350`) strings resolve→install together, but misses version pinning, introspection, and idempotency.
- **Inline ensure-packs**: `EmbeddedSession.run(ensure_packs=True)` (`session.py:241-277`) is the closest thing to an orchestrator — it checks compatibility, resolves missing, installs/restores, reloads, runs. But it's explicitly labeled "Dev convenience only" (line 251), doesn't use provenance versions, and doesn't introspect post-install (it reloads and trusts).

**What's entirely missing:**
- **Provenance → version resolution**: `cnr_id`/`aux_id`/`ver` from ComfyUI workflow `properties` are captured into `_ui` metadata (`ingest/normalize.py:235,259`) but **never parsed**. Zero references to `cnr_id` exist in the entire codebase. `_cmd_nodes_ensure` calls `install_pack(name=pack.name)` with no version constraint — it installs whatever HEAD happens to be.
- **Post-install live introspection**: `_cmd_nodes_ensure` prints "call session.reload_for_nodepack_change(...)" (line 348). It never boots Comfy to verify the installed pack's schemas match expectations.

---

**(b) Top 2-3 risks / missing pieces:**

1. **No version provenance path.** `install_pack` (`node_packs_install.py:99`) accepts `name` and `repo` but no `version` or `commit` parameter. `_refresh_existing` (`node_packs_install.py:163-171`) snapshots current HEAD into the lockfile without checking if it matches a desired version. Without parsing `cnr_id`/`ver` from workflow JSON and plumbing it through to install, the orchestrator cannot do faithful version-pinned installs — the doc's entire premise for "provenance-driven version resolution."

2. **No idempotency.** `_cmd_nodes_ensure` (`commands/nodes.py:338-345`) unconditionally calls `install_pack` for every resolved pack. `install_pack` re-snapshots the lockfile on every call even if already installed (`_refresh_existing` at line 163-171: "refreshed" even when nothing changed). There's no "is the correct version of this pack already present?" fast-path.

3. **No partial-failure semantics.** `_cmd_nodes_ensure` (`commands/nodes.py:344-345`) returns `1` on first pack failure. `EmbeddedSession` (`session.py:274`) raises `RuntimeError` on first failure. A workflow needing 5 packs where 1 fails gets zero installed — no rollback, no retry, no best-effort continuation.

---

**(c) Specific recommendation:**

Build the orchestrator as a standalone function (not buried in `EmbeddedSession.run`) with this pipeline: **parse provenance → resolve (pack, version) set → idempotent install/verify → live-introspect → return schema map**. The key piece to write first: a `_parse_workflow_provenance(workflow) → dict[str, (str, str)]` that extracts `(cnr_id → pack_slug, ver)` from `_ui.properties` on each node, then a version-aware `install_pack_at_version(name, commit)` that calls `install_pack` + `restore_pack` to pin to a specific SHA. Wire `_cmd_nodes_ensure` to use these, add a `--check` mode that reports "already installed at correct version" vs "needs install/upgrade," and collect failures per-pack instead of failing-fast.