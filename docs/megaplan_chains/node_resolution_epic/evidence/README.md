# Evidence — Node Resolution Epic

The review record behind [`../STRATEGY.md`](../STRATEGY.md). The strategy was
pressure-tested by a 12-agent panel, and every load-bearing claim was then
verified directly against the code (see STRATEGY.md §9). This folder is that
audit trail.

## Architecture reviews (overall direction)

- [`architecture-review-codex.md`](./architecture-review-codex.md) — Codex / GPT-5.5, high reasoning effort.
- [`architecture-review-opus.md`](./architecture-review-opus.md) — Claude Opus.

Both reviewed independently and **converged**: the spine is `(pack, commit)`
**identity**, not "live vs cache"; "live-first for porting" is wrong; lead with
**fail-closed/arity-disagreement**, not a provider reorder; and both flagged
(citing the same lines) that the emitter/runtime paths are cache-shadowed.

## Detail probes (one per design point)

`details/d01`–`d10` — DeepSeek V4 Pro agents, each pressure-testing one slice
against the code. `briefs/` holds the exact brief each was given (+ the
architecture-review prompt). `details/_fan_report.json` is the run report.

The decisive detail findings, all **verified true**:
- **d01 / d10:** the emitter takes arity from `consume.py` (`emitter.py:1947`), **bypassing `ConversionSchemaProvider`** → reordering the provider chain does not fix the crash.
- **d01:** the crash node `ComfyMathExpression` uses `io.Schema`; the AST source provider returns `None` for it → only *executed* introspection is authoritative.
- **d04:** `compute_schema_hash` is dead code and `drift.py` compares a different (file-bytes) hash → the "identity hash" must be built, not wired.
- **d03:** install has a silent clone-ok/pip-fail corruption path + no cross-pack dep resolution.
- **d08:** the fail-closed gap is the *known-node arity-disagreement* case; pins the exact emitter site.

## Generated artifact

- [`object_info_comfyui_0.24.0.1.json`](./object_info_comfyui_0.24.0.1.json) (1.4 MB) — the node-schema dump from **ComfyUI 0.24.0.1** (the hiddenswitch pip-installable fork), captured CPU-only. This is the dump that, when merged into the cache, made the Ideogram port compile (`ComfyMathExpression` → 3 outputs). It seeds Sprint A/C. *Regenerable; safe to `.gitignore` if its size is unwanted in-tree.*
