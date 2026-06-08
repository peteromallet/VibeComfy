# Testing & Acceptance — Node Resolution Epic

This is the **acceptance contract** for the epic. A sprint is not "done" until
its gates here are green. The headline regression is the real workflow that
started all this — `fixtures/ideogram4_t2i.json` — and every behavioral claim in
[`../STRATEGY.md`](../STRATEGY.md) maps to a scenario below.

`test_node_resolution_acceptance.py` is the executable form of this document:
one test per scenario, marked by the sprint that makes it pass. Until then each
gate test `skip`s with a pointer back to the relevant section here. As each
sprint lands, its tests are un-skipped and **also wired into `tests/`** (the
canonical home for the shipped suite); this folder remains the spec + fixtures.

## How to run

```bash
cd "$(git rev-parse --show-toplevel)"
# the living gate checklist (skips = not-yet-implemented):
pytest docs/megaplan_chains/node_resolution_epic/testing -v
# per sprint:
pytest -m sprint_a docs/megaplan_chains/node_resolution_epic/testing -v
```

---

## Headline regression — the Ideogram-4 workflow

**Fixture:** `fixtures/ideogram4_t2i.json` (real, 119 KB; uses `io.Schema` nodes,
two subgraphs, multiple node packs).
**Reference:** `fixtures/ideogram4_t2i.expected_emit.py` — the compiling Python
the porter produced once the schema was correct (0.24.0.1). A successful port
should be structurally equivalent to this.

| Stage | What happens when you port `ideogram4_t2i.json` |
|---|---|
| **NOW (baseline bug)** | Build fails with `ValueError: not enough values to unpack (expected 3, got 2)` — `ComfyMathExpression` is in the cache with **2** outputs, the workflow declares **3** (`io.Schema` added `BOOL`). A silent schema error that surfaces as an opaque crash 4 layers down. |
| **AFTER A** | **Never** an opaque `ValueError`. Either (a) it ports to a compiling template with correct arity when the cache is current, **or** (b) it fails **closed** with a typed `ArityDisagreementError` naming `ComfyMathExpression`, the snapshot version, and the remedy. Silent miscompile is impossible. |
| **AFTER B** | `ensure-env(<workflow>)` resolves + installs the packs the workflow needs (idempotent, partial-failure collected), then the port compiles and — where runnable — the workflow executes. |
| **AFTER C** | Ports against the **authored** pack versions (from each node's `cnr_id`/`ver`), not "latest". |

---

## Scenario matrix

Each row is one acceptance test. "Gate" = the sprint that must make it pass.

| # | Scenario | Fixture | NOW | Gate | Target behavior (the assertion) |
|---|---|---|---|---|---|
| 1 | **Arity skew → no silent miscompile** | `ideogram4_t2i.json` | opaque `ValueError` | **A** | Port either compiles with correct arity, or raises typed `ArityDisagreementError`; **assert no bare unpack `ValueError`** ever reaches the caller. |
| 2 | **Fail-closed unit (known node, cache < UI)** | `ComfyMathExpression` (cache=2, UI=3) | silent fallthrough | **A** | `require_class_output_count`/emitter arity site raises `ArityDisagreementError` naming node + snapshot version + remedy when cache outputs < UI-declared outputs; **warns (not errors)** when cache > UI (unused outputs). |
| 3 | **Update core without clobbering custom packs** | core refresh + `wan_t2v.json` | refresh drops custom packs | **A** | After refreshing core schema, custom-pack classes (e.g. `WanVideoModelLoader`) still resolve. `build_cache` merges, never wholesale-replaces the index. |
| 4 | **`io.Schema` coverage** | a `define_schema` node | AST source returns `None` | **A** | Executed introspection (not AST) yields correct outputs for `io.Schema` nodes; the cache generated from it is authoritative. |
| 5 | **Identity + drift detection works** | any installed pack | `version="unknown"`, schema-hash dead | **A** | Lookup key is `(pack_slug, git_commit)`; `compute_schema_hash` is wired at install; drift check uses one consistent algorithm — no false-positive mismatches. |
| 6 | **`ensure-env(workflow)` installs needed packs** | a workflow needing custom packs | fragments only, no flow | **B** | One idempotent call resolves → installs → verifies → introspects. Re-running is a no-op. Per-pack failures collected, not fail-fast. |
| 7 | **Install robustness** | clone-ok/pip-fail; multi-pack | silent "refreshed" w/ missing deps; conflicts | **B** | A clone-succeeds/pip-fails pack is **not** reported installed (sentinel); a cross-pack `pip --dry-run` preflight catches conflicts **before** mutating the env. |
| 8 | **Provenance → which packs** | `ideogram4_t2i.json` | `cnr_id` carried, never parsed | **B** | Workflow provenance is parsed to determine the required pack set fed to `ensure-env`. |
| 9 | **Faithful version pinning** | workflow w/ `cnr_id`+`ver` | resolves to latest | **C** | Resolves + installs the **authored** commit (git-checkout SHA from `ver`); `aux_id` (owner/repo) handled as a distinct path; local-first git resolution offline. |
| 10 | **Provenance-less fallback** | `wan_t2v.json` (no provenance) | silent latest | **C** | Resolves by class→pack with an explicit **warning** — never silent "latest"; the run is marked low-confidence. |
| 11 | **Snapshot demotion / auto-gen** | core packs | hand-captured monolith @0.18.2 | **C** | Core schema regenerable from a pinned pip-installable ComfyUI; per-pack versioned files; no hand-captured monolith. |
| 12 | **End-to-end** | `ideogram4_t2i.json` | crash | **B** (compile) / **C** (faithful) | Ports to a strict-ready, compiling template structurally equivalent to `ideogram4_t2i.expected_emit.py`; executes where a runtime is available. |

---

## Fixtures

| Path | Role |
|---|---|
| `fixtures/ideogram4_t2i.json` | **Headline.** Real Ideogram-4 workflow — `io.Schema` arity skew + subgraphs + multi-pack. Drives scenarios 1, 8, 12. |
| `fixtures/ideogram4_t2i.expected_emit.py` | Golden reference: the compiling emit from the 0.24.0.1 run. |
| `workflow_corpus/official/video/wan_t2v.json` *(referenced, in-repo)* | Provenance-less + multi-pack. Drives scenarios 3, 10. |
| `evidence/object_info_comfyui_0.24.0.1.json` *(referenced)* | The correct 0.24 schema dump — input for the "current cache" / merge tests (scenarios 2, 3). |

Sprints add: a minimal `io.Schema` single-node fixture (scenario 4), a
`cnr_id`+`ver` pinned-version fixture (scenario 9), and a synthetic
clone-ok/pip-fail pack (scenario 7).

## Definition of done (per sprint)

- **Sprint A:** scenarios **1–5** green. (Correctness locked: no silent
  miscompile, loud staleness, update-without-clobber, `io.Schema` covered,
  real identity/drift.)
- **Sprint B:** scenarios **6–8** + **12 (compile)** green. ("Drop in a
  workflow → it installs what it needs and ports/runs.")
- **Sprint C:** scenarios **9–11** + **12 (faithful)** green. (Exact authored
  versions; snapshot self-maintaining.)
