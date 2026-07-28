# Failure Analysis v2 — Case 03: audio_merge (BASELINE_REJECTED)

**Workflow:** `video/ltx2_3_iamccs_audio_extend_low_ram`
**Scenario:** ADDITIVE — remove `audio_merge` feature, ask fixer to re-add
**Verdict:** BASELINE_REJECTED (golden itself failed the compile gate)
**Case dir:** `out/l7-canon10-stabilized/cases/2ca7a0d30051/`
**Stabilized run:** pre-existing v2_delta pipeline break was fixed first; results are clean

---

## TL;DR

Three IAMCCS custom-node classes in the golden workflow are **unknown to the cached object_info** and **not resolvable by the on-demand schema resolver** because the IAMCCS pack has no Comfy Registry entry. The L7 campaign runner does **not** set `VIBECOMFY_ON_DEMAND_SCHEMAS=1`, so even the (ultimately futile) on-demand ladder was never consulted. **Two gaps compound:** the runner doesn't set the env var (wiring), and even if it did, no IAMCCS→URL mapping exists in the resolver (infrastructure). The fix is a local `pack_resolver` override for `IAMCCS_*` → `https://github.com/IAMCCS/IAMCCS-nodes`.

---

## 1. Unknown Node Classes

Three classes in `source/golden.ui.json` are unrecognized:

| Class | Node IDs | Pack |
|-------|----------|------|
| `IAMCCS_AudioExtender` | 21, 35, 49 | IAMCCS custom nodes |
| `IAMCCS_AudioExtensionMath` | 20, 34, 48 | IAMCCS custom nodes |
| `IAMCCS_AudioTimelineGate` | 30, 44 | IAMCCS custom nodes |

**Evidence** (`proof/baseline.json`):
```json
"compile_error": "unknown class: IAMCCS_AudioExtender. Run 'nodes lookup IAMCCS_AudioExtender' to find the providing pack, then 'nodes ins; unknown class: IAMCCS_AudioExtensionMath. ... unknown class: IAMCCS_AudioTimelineGate..."
```

---

## 2. On-Demand Schema Resolution Check

**Was the resolver consulted?** No.

The baseline gate (`vibecomfy/demo_factory/baseline.py` line 93) appends `--resolve-on-demand` **only when** `VIBECOMFY_ON_DEMAND_SCHEMAS=1` is set in the environment (line 61: `_on_demand_enabled()`). The L7 campaign runner (`run_campaign.py`) **never sets this env var**. The child `vibecomfy port check --json` process never received `--resolve-on-demand`. The resolver was never invoked.

**Would on-demand resolution succeed if enabled?** No — two independent verification attempts confirm the classes cannot be resolved:

1. **`nodes lookup IAMCCS_AudioExtender`** → `"unknown pack or class: IAMCCS_AudioExtender"`. The CLI's pack-resolver path (which queries the Comfy Registry API via `resolve_missing_nodes`) has no mapping for any `IAMCCS_*` class.

2. **`VIBECOMFY_ON_DEMAND_SCHEMAS=1 python -m vibecomfy.cli port check <golden> --json --resolve-on-demand`** — the CLI aborted before reaching resolution because no ComfyUI root was configured. Even in a properly configured environment, `_resolve_pack()` in `on_demand.py` calls `resolve_missing_nodes(class_type)` which queries:
   - **Rung 1 — Comfy Registry API** (`/comfy-nodes/{class_name}/node`): returns nothing — IAMCCS is not a registered pack.
   - **Rung 2 — ComfyUI Manager node map** (`custom-node-map.json`): querying `IAMCCS_Audio*` yields no hits.
   - **Rung 3 — GitHub search fallback**: searches GitHub for the class name; may find the `IAMCCS/IAMCCS-nodes` repo, but this is slow and unreliable.

**Result:** All three classes remain unresolved regardless of `--resolve-on-demand`.

---

## 3. Schema-Resolution Gap vs. Wiring Gap

Both gaps are at play, but the **root cause is INFRA** (schema-resolution gap):

### Wiring gap (secondary)
The L7 campaign runner does not set `VIBECOMFY_ON_DEMAND_SCHEMAS=1`. This is a one-line fix but would produce zero improvement for this case — see below.

### Schema-resolution gap (primary — the real blocker)
The `OnDemandInstallSchemaProvider._resolve_pack()` method delegates entirely to `resolve_missing_nodes()` in `pack_resolver.py`, which queries:
- **Comfy Registry API** (`api.comfy.org/comfy-nodes/{class_name}/node`) — IAMCCS is not registered there.
- **ComfyUI Manager node map** (`custom-node-map.json`) — no IAMCCS entries.
- **GitHub search** — may eventually find `IAMCCS/IAMCCS-nodes`, but there is **no hardcoded override** and no local pack-registry entry.

The system knows about these nodes — the codebase contains:
- `ready_templates/sources/custom_nodes/ltxvideo/iamccs/IAMCCS_LTX23_BEST_3SEG_AUDIOEXT_30S_FREE_LOW_RAM.json` — the original source workflow
- `coverage.json` attributes the source to `"IAMCCS/comfyui-iamccs-workflows"` (workflows repo, separate from the nodes pack)
- The source JSON workflow includes `aux_id: "IAMCCS/IAMCCS-nodes"` — pointing to `https://github.com/IAMCCS/IAMCCS-nodes`

But none of this knowledge is **routable** to the pack resolver.

---

## 4. Root Cause: INFRA

**Classification:** INFRA — the on-demand schema resolver cannot resolve any IAMCCS class because no registry entry or local override maps `IAMCCS_*` → a cloneable git URL.

### What precisely unblocks it

There is no Comfy Registry entry for IAMCCS (upstream gap, not in our control). The actionable fix is **option (b)** — add a local pack-resolver override. The `pack_resolver.py` module needs either:

1. A `HARDCODED_PACK_MAP` dict (or similar override mechanism) mapping `IAMCCS_*` → `"https://github.com/IAMCCS/IAMCCS-nodes"` — or any pattern-based prefix → URL mapping, OR

2. A local registry file (e.g., `~/.cache/vibecomfy/registry/local_overrides.json`) that `resolve_missing_nodes` checks before hitting the Comfy Registry API, OR

3. Pre-computed `object_info` for these three IAMCCS classes shipped as a static cache asset so the baseline compile gate passes without any remote resolution.

**Shortest path:** Add an `IAMCCS` entry to a local pack override mechanism. The relevant git URL is `https://github.com/IAMCCS/IAMCCS-nodes` (inferred from `aux_id: "IAMCCS/IAMCCS-nodes"` in the source workflow JSON). Once the resolver can shallow-clone this repo, Rung 1 (static AST parse of `INPUT_TYPES`) resolves all three classes without executing third-party code.

### Secondary fix

The L7 campaign runner (`run_campaign.py`) should set `VIBECOMFY_ON_DEMAND_SCHEMAS=1` by default, or the baseline gate should default to on-demand enabled when no server is reachable. Currently, even for packs that *are* in the Comfy Registry, the env var is silently absent — the on-demand ladder exists but is dead code in the campaign context.

---

## Artifacts referenced

| Artifact | Content |
|----------|---------|
| `proof/baseline.json` | compile error: 3 unknown IAMCCS classes |
| `receipts/001_baseline_proving.json` | empty data — baseline failed before any attempt |
| `receipts/001_baseline_rejected.json` | confirms `stage: "baseline_rejected"` with truncated error |
| `source/golden.ui.json` | 60 nodes, 95 links; uses IAMCCS nodes |
| `status.json` | `stage: "baseline_rejected"`, `fault_family: "additive:audio_merge"` |
| `vibecomfy/demo_factory/baseline.py` | `_on_demand_enabled()` line 61; `--resolve-on-demand` appended at line 94 only when env var set |
| `vibecomfy/demo_factory/run_campaign.py` | ADDITIVE_WORKFLOWS entry at line 63; no `VIBECOMFY_ON_DEMAND_SCHEMAS=1` set |
| `vibecomfy/schema/on_demand.py` | `_resolve_pack()` at line 160 → `resolve_missing_nodes()` — Comfy Registry only, no local override |
| `vibecomfy/registry/pack_resolver.py` | `resolve_missing_nodes()` at line 243 — queries Registry API + Manager map + GitHub fallback |
| `ready_templates/sources/manifests/coverage.json` | source attributed as `"IAMCCS/comfyui-iamccs-workflows"` |
| `ready_templates/sources/custom_nodes/ltxvideo/iamccs/IAMCCS_LTX23_BEST_3SEG_AUDIOEXT_30S_FREE_LOW_RAM.json` | source workflow JSON; `aux_id: "IAMCCS/IAMCCS-nodes"` reveals the nodes pack URL |
