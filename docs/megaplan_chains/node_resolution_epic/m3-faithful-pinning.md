# Sprint C — Faithful pinning + snapshot demotion (`partnered/full/high +prep`)

Shared context: read `docs/megaplan_chains/node_resolution_epic/STRATEGY.md` (esp. §5 item 5 + §4 item 4, §6, §7, §8 steps 4 & 6, §9) and `docs/megaplan_chains/node_resolution_epic/testing/testing.md`, plus the **m1 + m2 handoffs** (the identity-keyed cache, fail-closed arity spine, hardened install, and `ensure-env` orchestrator this sprint pins to authored versions). This is sprint 3 of 3 — durability. With A locking correctness and B realizing the environment, Sprint C makes resolution **faithful** (the exact authored versions) and retires the hand-captured monolithic snapshot.

## Outcome
A workflow ports and runs against the **authored** pack versions, not "latest": resolution pins to the commit each node declares (`ver`), handles `aux_id` (owner/repo) as a distinct git path, resolves git locally-first for offline/private packs, and **warns (never silent-latest)** on the provenance-less tail. The hand-captured monolithic snapshot (`@runpod-snapshot`, ComfyUI 0.18.2) is demoted: core schema is regenerable from a pinned pip-installable ComfyUI and custom packs are captured per-pack, versioned.

## Scope (IN)
Grounded in STRATEGY §5 (item 5, the version-pinned resolution half) + §4.4 (snapshot) and §8 (steps 4 & 6), using only the verified anchors from §3/§4:

1. **Version-pinned, provenance-driven resolution.** `resolve_pack` returns *latest* with no version param (`pack_resolver.py:220`, §3/§4.5). Add a version-pin to `resolve_pack`/install (**git-checkout SHA from `ver`**); parse `cnr_id`(slug) / `aux_id`(owner/repo) — the `aux_id` owner/repo nodes need a **distinct git resolution path** (§5.5, §7). Build on the provenance parsing landed in Sprint B; here it becomes version-faithful.
2. **Local-first git resolution.** For offline/private packs, read the installed pack's `.git` origin + HEAD to resolve identity without the registry (§5.5). Registry can't serve a pinned version and offline only works for previously-cached URLs with no TTL (§7) — local-first git is the fallback.
3. **Provenance-less fallback that warns.** ~8% of real workflows carry no provenance (§4.5, §7). Resolve those by class→pack with an **explicit warning** — never silent "latest" — and mark the run **low-confidence** (§5.5, scenario 10).
4. **Demote / auto-generate the snapshot.** The snapshot is hand-captured, monolithic, replace-on-refresh, with no path to regenerate from executed introspection at a pinned version (`serialize.py:96`, `comfy_metadata.json:7`, §4.4). Make **core schema regenerable from a pinned pip-installable ComfyUI** (CPU-bound, explicitly **not** "light", §5.4) and capture custom packs **per-pack, versioned** — no hand-captured monolith (§8.6). Reuse the merge-on-refresh `build_cache` from Sprint A (`serialize.py:137`).
5. **Faithful end-to-end.** Porting `ideogram4_t2i.json` pins each node to its `cnr_id`/`ver` commit (scenario 12-faithful).

## Locked decisions (do not relitigate)
- **Faithful pinning = git-checkout SHA from `ver`**, with `aux_id` (owner/repo) as a distinct path and **local-first git** for offline/private packs (§5.5). The registry cannot serve a pinned version (§7); do not assume it can.
- **Provenance-less ⇒ explicit warning + low-confidence, never silent-latest** (§5.5).
- **Snapshot demotion is real, not cosmetic**: core regenerated from a pinned pip-comfy (accepted as CPU-bound, not light); custom packs per-pack versioned; the monolith is gone (§5.4, §8.6).
- Reuse the Sprint A `(pack_slug, git_commit)` identity, merge-on-refresh `build_cache`, and fail-closed arity, and the Sprint B hardened install + `ensure-env` — Sprint C pins them to authored versions, it does not re-open them.
- **Executed introspection runs third-party node code** — gated trust surface (§7); regenerating core/custom schemas runs that code only at the sanctioned ensure/regen step.

## Open questions (resolve in build)
- Which `ver` field shape to trust as the commit SHA across `cnr_id` vs `aux_id` provenance variants — resolve against the `cnr_id`+`ver` pinned-version fixture (testing.md "Fixtures": sprints add it).
- How to express "low-confidence" in the run result so callers can branch on it (flag vs structured warning) — keep it surfaced, not buried.
- Whether core regen targets a single pinned ComfyUI version or a small supported set — pin one explicit version for the gate (`schemas regen-core --comfy-version …`); cross-reference `docs/comfy_version_support.md`.
- `aux_id`-only packs with no `cnr_id`: the GitHub/owner-repo resolution path (§7) — keep it distinct from the registry slug path.

## Constraints
- **Cheap porting must NOT boot ComfyUI / run `import_all_nodes_in_workspace`** (§6). Core regen from pinned pip-comfy is explicitly the heavy, reserved path — not the per-port read.
- **Executed introspection / schema regen runs third-party node code** — must be gated (§7); do not imply sandboxed execution that does not exist.
- No new failures vs baseline across the full suite.
- Pinning is faithful-by-default but must degrade loudly (warn) on the provenance-less tail — never silently to latest.

## Done criteria
Maps to testing.md scenarios **9, 10, 11** + **12 (faithful)** (Definition of done → Sprint C). The runnable gate:
- `pytest -m sprint_c docs/megaplan_chains/node_resolution_epic/testing` goes **green** (un-skip scenarios 9, 10, 11, 12-faithful; wire shipped form into `tests/`).
  - **9** Faithful version pinning: resolves + installs the **authored** commit (git-checkout SHA from `ver`), not latest; `aux_id` (owner/repo) handled as a distinct path; local-first git resolution offline.
  - **10** Provenance-less fallback: `workflow_corpus/official/video/wan_t2v.json` resolves by class→pack with an **explicit warning** (not silent latest); run marked low-confidence.
  - **11** Snapshot demotion / auto-gen: core schema regenerable from a pinned pip-installable ComfyUI; per-pack versioned files; no hand-captured monolith.
  - **12 (faithful)** Porting `ideogram4_t2i.json` pins each node to its `cnr_id`/`ver` commit.
- **Headline behavior (AFTER C** in testing.md's NOW/AFTER table): `ideogram4_t2i.json` ports against the **authored** pack versions (from each node's `cnr_id`/`ver`), not "latest".
- Full `pytest` shows **no new failures** vs baseline.

## Touchpoints
From §3/§4 anchors: `vibecomfy/registry/pack_resolver.py:220` (add version-pin + `aux_id` path + local-first git + provenance-less warning), `vibecomfy/porting/serialize.py:96` (snapshot regen) and `:137` (merge-on-refresh `build_cache`), `comfy_metadata.json:7` (hand-captured monolith metadata to demote); builds on Sprint B's `vibecomfy/porting/provenance.py` and `vibecomfy/runtime/ensure_env.py`, and the Sprint A `(pack_slug, git_commit)` identity / cache; cross-reference `docs/comfy_version_support.md`.

## Anti-scope
- Per README "Explicit non-goals": **no universal node-schema registry**; **no perfect cross-pack dependency solver** (preflight + fail-closed only); **no three-source arity triangulation**; **no speculative any-backend abstraction**.
- This sprint does **NOT** re-open Sprint A (fail-closed arity, `(pack_slug, git_commit)` identity, `io.Schema`/AST-demotion, merge-on-refresh contract) or Sprint B (install hardening internals, the `ensure-env` composition, provenance *parsing* shape) — it pins them to authored versions and demotes the snapshot.
- Do not build a TTL'd offline registry cache or a registry-side pinned-version server (§7 says the registry can't pin — use git-checkout-SHA / local-first git instead).
- Do not imply sandboxed execution of third-party packs during regen; gate it, do not pretend to isolate it.
