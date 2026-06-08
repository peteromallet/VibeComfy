Here is my analysis.

---

**How the install chain actually works (from code):**

1. **`install_pack()`** (node_packs_install.py:99-138): resolves the pack, checks if dir exists. If new: runs `cm-cli install <name>` as first choice; if cm-cli is unavailable or fails, falls back to `_install_pack_via_clone` (git clone + `pip install <bare_pkg_names>`). Then writes lockfile.

2. **`_install_pack_via_clone()`** (line 139-148): `git clone` → `pip install *pack.pip_packages` (bare names, no version constraints) → lockfile write. If the pack came from a raw `repo=` URL (not the registry), `pack` is `None` and **pip deps are silently skipped** (line 142: `if pack and pack.pip_packages`).

3. **`restore_pack()`** (line 149-162): git checkout pinned SHA → `pip install` bare packages. Same no-constraints problem.

4. **`_refresh_existing()`** (line 163-171): if dir exists, only updates lockfile pin — **never re-runs pip install**. A pack whose pip deps were broken by a later install is permanently stale.

5. **`_cmd_nodes_ensure()`** (commands/nodes.py:338-345): sequential loop: `for pack in packs: install_pack(name=pack.name)`. No pre-resolution, no atomicity, no rollback. First failure aborts with `return 1`, leaving prior packs installed and env potentially polluted.

6. **`check_pack_pin_compatibility()`** (custom_node_refs.py:80-130): only checks git version/commit alignment between workflow `custom_node_refs` and lockfile. **Zero pip dependency awareness.** It's purely a pin-mismatch detector, not a compatibility check.

---

### (a) Is the doc accurate on this point?

**Partly.** The doc correctly lists install execution as "EXISTS" (Section 3) and honestly admits in Section 7: *"cm-cli helps but there's no preflight compatibility check."* However, the doc **understates** the severity. It treats this as a "known hard part" while presenting the install chain as ready building-block material for the proposed `ensure-env` orchestrator (Section 5.3). The code reveals the install chain is far more fragile than the doc suggests — it's single-pack-at-a-time with no dependency resolution, no rollback, and a hidden state-machine bug where a pip-failed clone masquerades as "installed" on retry (line 115 short-circuits to `_refresh_existing` which skips pip reinstall). This isn't merely "no preflight check" — it's structurally unfit for multi-pack co-install.

### (b) Top 2-3 concrete risks / missing pieces

1. **No cross-pack pip dependency resolution — silent runtime corruption.** `pip install` calls are per-pack, bare package names with no version constraints (node_packs.py:15, e.g. `("transformers", "einops", "timm")`). Pack A needs `transformers>=4.45`, pack B needs `transformers<4.35` — last install wins. No `pip check`, no `--dry-run`, no constraint file, no shared resolution. At 10-30 packs, this is guaranteed to produce silent runtime failures, not loud errors.

2. **Partial-failure state-machine bug.** If `git clone` succeeds but `pip install` fails (line 140-143), the pack dir exists. On retry, line 115 enters `_refresh_existing` which **skips pip install entirely** (lines 163-171) — only updates the lockfile. The pack reports `"refreshed"` with no error, but its pip deps are uninstalled. The env looks healthy, the lockfile is current, the runtime blows up inexplicably.

3. **No atomicity or rollback in batch install.** `_cmd_nodes_ensure` (commands/nodes.py:338) is a naive sequential loop. If pack 8 of 15 fails, packs 1-7 are installed (potentially with conflicting pip deps), the env is polluted, and there is no snapshot/restore mechanism. The only recovery is manual cleanup of `custom_nodes/` directories and `pip uninstall`.

### (c) Specific recommendation

**Before building `ensure-env(workflow)`**, add a `pip install --dry-run --report` preflight that collects ALL pip packages across ALL required packs, resolves them jointly (e.g., via `pip install --dry-run --report /dev/stdout <all-packages> | jq`), and fails-closed before touching the env. This is cheap, uses only stdlib+pip, and catches the dominant failure mode. Pair it with: (a) a fix for the clone-succeeds/pip-fails state-machine bug (store a `.vibecomfy_install_state` sentinel in the pack dir that records whether pip completed), and (b) make the batch loop collect all results before deciding pass/fail, rather than aborting on first error with a half-installed env.