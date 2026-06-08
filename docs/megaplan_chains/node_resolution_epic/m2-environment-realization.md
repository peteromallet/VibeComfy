# Sprint B — Environment realization (`partnered/thorough/high +prep`)

Shared context: read `docs/megaplan_chains/node_resolution_epic/STRATEGY.md` (esp. §5 items 5–6, §6 light/efficient, §7 risks, §8 steps 3 & 5) and `docs/megaplan_chains/node_resolution_epic/testing/testing.md`, plus the **m1 handoff** (the identity-keyed cache + fail-closed arity spine this sprint builds on). This is sprint 2 of 3. With Sprint A correctness locked, Sprint B delivers the user-facing capability: **drop in a workflow → it installs what it needs and ports/runs.**

## Outcome
A workflow can be realized into an environment: provenance is parsed to learn *which* packs a workflow needs, install execution is hardened (no false "refreshed" on a clone-ok/pip-fail, a cross-pack pip preflight before mutating the env), and one idempotent `ensure-env(workflow)` orchestrator composes parse → resolve → install/verify → executed-introspect → identity-keyed cache, collecting per-pack failures instead of aborting on the first.

## Scope (IN)
Grounded in STRATEGY §5 (items 6 + the provenance-*parsing* half of 5) and §8 (steps 3 & 5), using only the verified anchors from §3/§4:

1. **Harden install execution** (`node_packs_install.py:115,142,163`, §4.6). Fix the state-machine bug: a clone-succeeds/pip-fails pack leaves a dir that on retry hits `_refresh_existing` and **skips pip** while reporting "refreshed" — add a **state sentinel** so an incompletely-installed pack is never reported installed. Add a **cross-pack `pip install --dry-run --report` preflight** that catches conflicts **before** mutating the env (per-pack bare unpinned installs are last-wins and guarantee conflicts at scale, §7). The batch loop must **collect per-pack failures**, not abort on first failure with a polluted env (§5.6).
2. **Provenance parsing → which packs.** `cnr_id` / `aux_id` / `ver` are carried through but **never parsed** (`pack_resolver.py:220`, §4.5). Add an `extract_provenance(workflow)` that parses the per-class provenance into the required pack set fed to `ensure-env`. This sprint parses provenance to determine *which* packs; **version-pinned resolution from `ver` is Sprint C** (here, the registry's class→pack resolution is sufficient to name the set).
3. **`ensure-env(workflow)` orchestrator** (`vibecomfy/runtime/ensure_env.py`, §5.6, §8.5). Compose the hardened pieces: parse provenance → resolve the `(pack, …)` set → idempotent install/verify → executed-introspect → write the identity-keyed cache from Sprint A → ready to port/run. **Idempotent** (re-running is a no-op / `noop`), provenance-scoped (only the packs *this* workflow needs, §6), per-pack failure collection in the result.
4. **End-to-end compile** of the headline workflow: after `ensure-env(ideogram4_t2i.json)`, the port compiles to a strict-ready template structurally equivalent to `fixtures/ideogram4_t2i.expected_emit.py` (scenario 12-compile).

## Locked decisions (do not relitigate)
- **Preflight + fail-closed, not a solver.** Cross-pack conflicts are handled by a joint `pip --dry-run --report` preflight (caught before mutation) — **not** a SAT-style cross-pack dependency resolver (§7, README non-goals). Still-not-fully-solvable is acceptable; loud is the bar.
- **Provenance-scoped install only** — install the packs a given workflow needs, not the world (§6).
- **Per-pack failure collection, not fail-fast** — the batch loop must not abort on first failure and must not leave a polluted env silently (§5.6).
- **Executed introspection runs third-party code** — gated trust surface (§7); `ensure-env` is the sanctioned place it runs (cache generation + execution are the only two reasons to go live, §6).
- The Sprint A spine is fixed: identity key is `(pack_slug, git_commit)`, fail-closed arity stays in force. Sprint B feeds that cache; it does not change its contract.

## Open questions (resolve in build)
- Exact sentinel representation for "clone-ok/pip-fail" (marker file vs lockfile state) — pick the one that round-trips through `_refresh_existing` (`node_packs_install.py:142`).
- How aggressively to fail on a `pip --dry-run` *conflict* vs surface-and-continue — default to surfacing in the result and blocking the conflicting pack, not the whole batch.
- The synthetic clone-ok/pip-fail fixture and the minimal multi-pack-conflict fixture (testing.md "Fixtures": sprints add them).
- For provenance-less / `aux_id`-only classes encountered here, name them in the result; the *resolution* path for them is Sprint C (§5.5, §8.4).

## Constraints
- **Cheap porting must NOT boot ComfyUI / run `import_all_nodes_in_workspace`** (§6). Live boot is reserved for `ensure-env` cache generation and actual execution.
- **Executed introspection runs third-party node code** — must be gated (§7); do not imply sandboxed execution that does not exist.
- No new failures vs baseline across the full suite.
- This sprint does **not** do version-pinning, `aux_id`-owner/repo git resolution, local-first git, the provenance-less *warning* path, or snapshot demotion/auto-generation — those are Sprint C.

## Done criteria
Maps to testing.md scenarios **6, 7, 8** + **12 (compile)** (Definition of done → Sprint B). The runnable gate:
- `pytest -m sprint_b docs/megaplan_chains/node_resolution_epic/testing` goes **green** (un-skip scenarios 6, 7, 8, 12-compile; wire shipped form into `tests/`).
  - **6** `ensure_env(str(IDEOGRAM))` resolves → installs → verifies → introspects; result `.ok` with `.installed`; re-running returns `.noop` (idempotent); per-pack failures collected, not fail-fast.
  - **7** Install robustness: a clone-ok/pip-fail pack is **not** reported installed (sentinel); a cross-pack `pip --dry-run` preflight catches conflicts before mutating the env.
  - **8** Provenance → packs: `extract_provenance(json.loads(IDEOGRAM))` parses `cnr_id`/`aux_id`/`ver` into a per-class pack set.
  - **12 (compile)** `port_convert_workflow(...)` on `ideogram4_t2i.json` returns `compile_ok and strict_ready_ok`.
- **Headline behavior (AFTER B** in testing.md's NOW/AFTER table): `ensure-env(ideogram4_t2i.json)` resolves + installs the needed packs (idempotent, partial-failure collected), then the port compiles and — where a runtime is available — the workflow executes.
- Full `pytest` shows **no new failures** vs baseline.

## Touchpoints
From §3/§4 anchors: `vibecomfy/node_packs_install.py:115,142,163` (state sentinel, preflight, batch loop), `vibecomfy/registry/pack_resolver.py:220` (provenance carried but unparsed — parse here, pin in C), new `vibecomfy/runtime/ensure_env.py` (orchestrator + result type per the gate import), new `vibecomfy/porting/provenance.py` (`extract_provenance` per the gate import); reads the Sprint A identity-keyed cache and the executed-introspection generator (`nodes_math.py:64`).

## Anti-scope
- Per README "Explicit non-goals": **no perfect cross-pack dependency solver** (preflight + fail-closed only); **no universal node-schema registry**; **no speculative any-backend abstraction**.
- This sprint does **NOT** touch version-pinning (`resolve_pack(pin_version=...)`, git-checkout-SHA from `ver`), the `aux_id` owner/repo resolution path, local-first git resolution, the provenance-less explicit-warning / low-confidence path, or snapshot demotion / auto-generation — those are Sprint C.
- Do not re-open the Sprint A spine: do not change the `(pack_slug, git_commit)` cache key, the fail-closed arity rule, or the AST-demotion decision.
- Do not imply sandboxed execution of third-party packs; gate it, do not pretend to isolate it.
