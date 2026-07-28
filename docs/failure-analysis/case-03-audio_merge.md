# Failure Analysis: Case 03 — audio_merge (Baseline Rejected)

**Workflow:** `video/ltx2_3_iamccs_audio_extend_low_ram`
**Feature removed:** `audio_merge`
**Verdict:** `BASELINE_REJECTED` (golden itself failed the compile gate)
**Case dir:** `out/l7-canon10-parallel/cases/88be0ddc68ae/`

---

## TL;DR

The golden workflow uses three IAMCCS custom-node classes that are **not in the cached object_info** and **not resolvable by the on-demand schema resolver** (the Comfy Registry has no entry for the IAMCCS pack). The baseline gate ran **without `VIBECOMFY_ON_DEMAND_SCHEMAS=1`**, so it never even tried the on-demand ladder — but even if it had, **it would still have failed** because the on-demand resolver's Rung 1 (`resolve_missing_nodes`) queries the Comfy Registry API, which does not know about IAMCCS. This is a **schema-resolution gap**, not a wiring gap: the infrastructure to resolve unknown classes exists but **cannot resolve these particular classes** because no registry-to-pack mapping is configured for IAMCCS.

---

## 1. Unknown Node Classes

Three classes in the golden workflow (`source/golden.ui.json`) are unrecognized by the cached object_info:

| Class | Appearances (node IDs) | Pack |
|-------|----------------------|------|
| `IAMCCS_AudioExtender` | 21, 35, 49 | IAMCCS (LTXVideo audio extension) |
| `IAMCCS_AudioExtensionMath` | 20, 34, 48 | IAMCCS |
| `IAMCCS_AudioTimelineGate` | 30, 44 | IAMCCS |

**Evidence** (`proof/baseline.json`):
```json
"compile_error": "unknown class: IAMCCS_AudioExtender. Run 'nodes lookup ...' unknown class: IAMCCS_AudioExtensionMath. ... unknown class: IAMCCS_AudioTimelineGate..."
```

---

## 2. Are These Resolvable by On-Demand Schema Resolver?

**No — and the on-demand resolver was not even consulted.**

### Wiring gap (env var not set)

The baseline gate (`vibecomfy/demo_factory/baseline.py`) has an opt-in for on-demand resolution:

```python
def _on_demand_enabled() -> bool:
    return os.environ.get("VIBECOMFY_ON_DEMAND_SCHEMAS") == "1"
```

The L7 campaign runner (`run_campaign.py`) does **not** set `VIBECOMFY_ON_DEMAND_SCHEMAS=1`. The child `vibecomfy port check --json` process therefore never receives `--resolve-on-demand`. **The resolver was never consulted.**

### Schema-resolution gap (even if consulted, would still fail)

Even with `--resolve-on-demand`, the `OnDemandInstallSchemaProvider` (`vibecomfy/schema/on_demand.py`) would fail on these classes because:

1. **Rung 1** calls `resolve_missing_nodes(class_type)` which queries the **Comfy Registry API** for a pack mapping.
2. The **IAMCCS pack is not registered in the Comfy Registry** — no candidate URL is returned.
3. Without a pack URL, the resolver cannot clone → parse → extract schema.
4. The resolver returns `None` for all three classes.

**Verified:** Searching the codebase for IAMCCS references in `vibecomfy/registry/` returns zero hits — no local registry entry, no hardcoded mapping, no fallback URL.

### What *does* know about these nodes

- **`ready_templates/video/ltx2_3_iamccs_audio_extend_low_ram.py`** — the ready-template Python definition, which calls `raw_call('IAMCCS_AudioExtender', ...)` etc.
- **`ready_templates/sources/custom_nodes/ltxvideo/iamccs/IAMCCS_LTX23_BEST_3SEG_AUDIOEXT_30S_FREE_LOW_RAM.json`** — the original source workflow JSON.
- **`docs/megaplan_chains/excellence_epic/evidence/widget_n_classification_20260528.json`** — contains widget classification evidence for these exact class types.

The knowledge exists in the repo but is **not routable to the schema resolver** because no bridge from "IAMCCS class name → git clone URL" exists in the pack resolver.

---

## 3. Root Classification

**INFRA — Unresolvable custom-node pack without Registry entry.**

### Precise blocker

The on-demand schema resolver needs one of:
- **(a)** An IAMCCS entry in the Comfy Registry (upstream action — not in our control), **OR**
- **(b)** A local `pack_resolver` override or `PACK_REGISTRY` entry mapping `IAMCCS_Audio*` → git clone URL (e.g., `https://github.com/IamCCS/ComfyUI-IamCCS`), **OR**
- **(c)** Pre-computed `object_info` for the IAMCCS pack shipped as a static cache asset.

### What unblocks it

**Shortest path:** Add a `pack_resolver` override mapping `IAMCCS_*` → known git URL (find the actual IAMCCS ComfyUI pack repo). Once the resolver can clone the pack, Rung 1 (static AST parse) resolves all three classes without executing third-party code.

**Even shorter:** Pre-compute `object_info` for the IAMCCS pack and ship it in the static cache — but this rots over time as the pack evolves.

### Secondary note: the L7 runner should set `VIBECOMFY_ON_DEMAND_SCHEMAS=1`

Even for packs that *are* in the Registry, the baseline gate would silently skip on-demand resolution. The env var should be set by default (or forced on) in `run_campaign.py` so the baseline gate actually uses the resolver it was designed to support.

---

## Artifacts referenced

- `proof/baseline.json` — compile error listing 3 unknown classes
- `receipts/001_baseline_proving.json` — empty data (gate failed before any attempt)
- `source/golden.ui.json` — golden workflow with IAMCCS nodes
- `logs/case3.log` — confirms ALL nodes emitted as schema-less (strict=False)
- `vibecomfy/demo_factory/baseline.py` — `_on_demand_enabled()` at line 61
- `vibecomfy/schema/on_demand.py` — `_resolve_pack()` at line 160 queries Comfy Registry only
