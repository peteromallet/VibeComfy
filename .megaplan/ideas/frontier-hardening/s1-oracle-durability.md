# S1 — oracle-durability: make oracle drift LOUD, not silent

## Outcome
An oracle/version change or a user-vs-pinned skew **breaks loudly in CI or fences gracefully at runtime**
— it never silently degrades to VibeComfy's offline reimplementation of the converter. "Correct" is
anchored to a *recorded, versioned* ComfyUI, and our own widget-schema bumps can no longer silently
steal saved-graph positions.

## Why (the gremlin)
Roadmap §14 / §8. `comfy_converter_strict=False` is the **default happy path**: when ComfyUI's
`convert_ui_to_api` raises, ingest swallows it and falls back to `_normalize_ui_to_api` (the offline
reimpl) — the dangerous "gate stays green while real ComfyUI now renders differently" mode. The only
real oracle gate (`test_layer3_corpus_wide_convert_ui_to_api_gate`) is **opt-in and never runs in CI**
(`VIBECOMFY_COMFY_SMOKE` set nowhere). `object_info` is installation-specific, so the pinned "correct"
is not the user's "correct". Both confirmed by the 5×2 sweep, code-cited.

## Scope — IN
- Flip the ingest boundary to **`comfy_converter_strict=True` by default**, with an explicit, sequenced
  migration of every production call site that currently relies on the lenient fallback.
- Wire `test_layer3_corpus_wide_convert_ui_to_api_gate` into **required CI** (`VIBECOMFY_COMFY_SMOKE=1`).
- Commit **`version_matrix.json`** recording the pinned/vendored ComfyUI commit + a `supported_comfyui_version`.
- A **runtime version-skew detector**: compare the user's live ComfyUI/`object_info` against the pin;
  on mismatch, fence to known-safe families with a typed reason (reuse the §6 refusal vocabulary if present).
- A **saved-graph migration test**: a graph emitted under an older widget-schema still round-trips after a
  schema bump (or a forward-migration runs) — our own bumps must not orphan position/identity.

## Scope — OUT
- The V3 node-schema adapter and a full multi-version matrix (§8 later — pin ONE version now).
- The litegraph arrays→objects migration beyond what `normalize.py` already tolerates.

## Locked decisions
- Strict-by-default is the target; the offline reimpl becomes a *fallback you opt INTO*, not the default.
- The pinned ComfyUI commit is the single source of "correct"; CI runs against it.

## Open questions (resolve in planning)
- Which call sites (if any) MUST stay lenient (e.g. a deliberately-offline path) — enumerate and justify.
- Skew-detector granularity: per-class object_info fingerprint vs a coarse version string.

## Constraints
- Offline/deterministic; the CI gate needs the vendored submodule (already wired via `comfy_backend.ensure_nodes()`).
- No behavior change for graphs that already pass strict — only the FALLBACK path's silence is removed.

## Done criteria
- CI **fails** on a deliberately-mutated `convert_ui_to_api` output (the gate is live and required).
- A workflow that currently silently falls back now **raises** (or is explicitly, loudly degraded).
- Skew detector unit-tested: a fabricated version mismatch fences to safe families.
- Saved-graph migration test green: old-schema graph round-trips (or migrates) after a schema bump.

## Touchpoints
- `vibecomfy/ingest/normalize.py` (strict default + call sites), `vibecomfy/comfy_backend.py`,
  `tests/test_porting_ui_emitter.py` (Layer-3 gate), `.github/` (CI), new `version_matrix.json`,
  `vibecomfy/porting/layout_store.py` / `uid.py` (migration test surface).

## Anti-scope
- Do not build the multi-version matrix or the V3 adapter. Do not touch the codec's emit logic.
- Do not change what `convert_ui_to_api` returns — only how we react when it changes/raises.

## Handoff artifact
`version_matrix.json` + a green required oracle gate — every later sprint's `convert_ui_to_api` check
inherits a trustworthy, version-anchored truth source from here.
