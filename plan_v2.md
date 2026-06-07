# Implementation Plan: M3 — Corpus proof + polish (P3 + P2) — Revision 2

## Overview

The `EditSession` surface (render → apply_batch → done) is fully implemented and tested against synthetic mini-graphs. Const-fold (`_fold_constant`) and bounded-`for` (`_expand_for` over `range()`) are already wired. What remains is (a) a new byte-identity harness that drives the five canonical edit cases through the real RuneXX/LTX-2.3 corpus graphs, asserting gates A/B/C on each, and (b) polish on const-fold / bounded-`for` edge cases, diff-render presentation, `describe()` formatting, and group-inference that the corpus run surfaces.

The corpus graphs (RuneXX ~200 nodes, LTX-2.3 t2v/i2v ~100+ nodes) use many custom node types (`LTXVCropGuides`, `LTXVAudioVAELoader`, UUID-typed subgraph wrappers, etc.) that have no schemas in the test environment. `socket_types_compatible(None, None) → True` means unknown types do not block wiring, so we can build a lightweight adapter that infers socket-type facts from the graph's own link structure — enough to satisfy the type-aware resolution that `apply_batch` performs when it resolves `.SLOT` references and checks `socket_types_compatible`. The harness never needs to construct brand‑new custom nodes; it only adds/edits nodes whose schemas are either known or trivially inferable from the links already present in the graph.

---

## Phase 1: Corpus harness foundation

### Step 1: Corpus-schema adapter (`tests/support/corpus_schema.py`)
**Complexity: 2** — new helper module, ~120 lines

1. **Create** `tests/support/corpus_schema.py` with a `graph_inferred_schema_provider(raw_ui_json)` factory that produces an object with `get_schema(class_type) → NodeSchema | None`.

2. **Inspect** every link in the raw UI JSON (both top-level `links` and links inside `definitions.subgraphs[*].links`). Links come in two formats: array `[link_id, origin_id, origin_slot, target_id, target_slot, type]` and dict `{...}`. For each link:
   - Find the origin node and target node (by `id`) in the appropriate scope (top-level `nodes` or subgraph `nodes`).
   - Record `(origin_node_type, origin_slot_index) → socket_type` for output slots. The origin slot index is the positional index in the origin node's `outputs` array (or the link's `origin_slot` field).
   - Record `(target_node_type, target_slot_name) → socket_type` for input slots. The target slot name is the `name` field from the target node's `inputs` array entry at the target slot index.
   - **Dual-index for input slots**: also record `(target_node_type, target_label) → socket_type` where `target_label` is the `label` field. LTX graphs (especially proxy-widget inputs on subgraph wrappers) use `label` (e.g., `"width"`, `"height"`) as the primary display identifier. When resolving an input slot, check `name` first, then fall back to `label`.

3. **Build** two lookup dicts from step 2:
   - `_out_types: dict[tuple[str, int], str]` keyed by `(class_type, output_slot_index)`.
   - `_in_types: dict[tuple[str, str], str]` keyed by `(class_type, input_slot_name_or_label)`.

4. **Return** a provider whose `get_schema(class_type)` returns a minimal `NodeSchema` with:
   - `inputs`: a dict mapping every known input slot name/label to an `InputSpec(type=inferred_type)`.
   - `outputs`: a list of `OutputSpec(type=inferred_type, name=slot_name)` for every known output slot index.
   - Any fields that appear as `widgets_values` slots are NOT included in the schema (they're handled by the existing widget-value path, not the type-checking path).

5. **Add** explicit core schemas for well-known types needed by canonical edits. These override the inferred schemas and are defined inline in the adapter module:
   - `SaveImage`: inputs `images: IMAGE`, `filename_prefix: STRING`; no outputs.
   - `SaveVideo`: inputs `video: VIDEO`, `filename_prefix: STRING`; no outputs.
   - `LoadImage`: outputs `IMAGE`, `MASK`.
   - `CLIPTextEncode`: inputs `text: STRING`, `clip: CLIP`; outputs `CONDITIONING`.
   - `VAEDecode`: inputs `samples: LATENT`, `vae: VAE`; outputs `IMAGE`.
   - `KSampler`: inputs `model: MODEL`, `positive: CONDITIONING`, `negative: CONDITIONING`, `latent_image: LATENT` plus widget inputs; outputs `LATENT`.
   - `DualCLIPLoader`: outputs `CLIP`.
   - `VAELoader`: outputs `VAE`.
   - `SetNode` / `GetNode`: passthrough virtual nodes — output type = input type (inferred from links).
   - `Reroute`: passthrough — output type = input type (inferred from links; type is `*` which is compatible with everything).

6. **Test** the adapter in `tests/support/test_corpus_schema.py`:
   - Load `workflow_corpus/official/video/ltx2_3_t2v.json`, build the provider.
   - Assert `get_schema("LTXVCropGuides")` returns non-None.
   - For every link in the graph, verify that `socket_types_compatible(origin_type, target_type) → True`.
   - Load `workflow_corpus/custom_nodes/ltxvideo/runexx/LTX-2.3_Talking_Avatar_Qwen_TTS.json`, repeat the link-type-check assertion.

### Step 2: RuneXX LTX byte-identity harness (`tests/test_porting_edit_runexx_ltx.py`)
**Complexity: 4** — new test module, ~400 lines, five canonical cases with A/B/C assertions, multiple corpus fixtures

Sources:
- `workflow_corpus/custom_nodes/ltxvideo/runexx/LTX-2.3_Talking_Avatar_Qwen_TTS.json` (RuneXX, ~200 nodes, 1 subgraph "Calculate Frames" with UUID `63e8c999-...`)
- `workflow_corpus/official/video/ltx2_3_t2v.json` (LTX t2v, ~100 nodes, 1 subgraph "Text to Video (LTX-2.3)" with UUID `b94257db-...`, wrapper node id 267)
- `workflow_corpus/official/video/ltx2_3_i2v.json` (LTX i2v, ~100 nodes, similar subgraph structure)

Build a parametrized harness class `TestRunexxLTXByteIdentity` that:

1. **Fixture loading helper** — loads a corpus JSON, normalizes it (`normalize_to_api` + `convert_to_vibe_format` via `EditSession._workflow_from_ui`), creates an `EditSession` with the graph-inferred schema provider from Step 1, calls `render()`, and pre-seeds `uid_by_name` / `name_by_uid` from the render output (`_extract_uid_name_pairs`).

2. **Canonical case (a) — add+wire** (green where blind-JSON failed). On each of the three corpus graphs, find a suitable anchor (a node with a known output type) and add a terminal node (`SaveImage` on an IMAGE-typed output, e.g. after `VAEDecode`; `SaveVideo` on a VIDEO-typed output), wiring it to the anchor's output. Assert A (byte-identity — untouched nodes identical), B (compile-isomorphism over touched region), C (summary mentions the added node and the new edge).

3. **Canonical case (b) — two-line splice**. On the LTX t2v graph, identify two directly-connected nodes with compatible types (e.g., `LTXVLatentUpsampler` (outputs `LATENT`) → `LTXVImgToVideoInplace` (inputs `latent: LATENT`)). Splice a synthetic passthrough node between them: add a `VAEDecode`-then-`VAEEncode`-style pair that reads `LATENT` and outputs `LATENT`, or use a simple `Reroute`-like passthrough added via `add_node` + `upsert_link` + rewire. The splice approach is:
   - Remove the original link between source and target.
   - Add the new node.
   - Insert two new links: source → new node, new node → target.
   - Assert A (untouched nodes identical), B (touched region isomorphic), C (summary mentions the splice).

4. **Canonical case (c) — 5-node add**. On the RuneXX graph, find an existing node with a `STRING` or `INT` output (e.g., a `PrimitiveString` or `PrimitiveInt` node). Add a chain of 3–5 synthetic `SetNode`/`GetNode` passthrough nodes (or `Reroute` nodes, which have schemas in the adapter) wired in sequence, terminating at an existing consumer. The chain uses only types whose schemas are in the adapter. Assert left-to-right placement order (each successive node is positioned `right_of` the previous), A/B/C.

5. **Canonical case (d) — subgraph-internal edit**. The LTX t2v subgraph ("Text to Video (LTX-2.3)", UUID `b94257db-...`) contains a `RandomNoise` node (id 216) with widget `noise_seed` (widgets_values[0]). The harness:
   - Resolves the subgraph's scope_path using the existing `_scope_path_by_name` helper (from `test_porting_edit_corpus.py`) which searches `EditLedger.ingest(ui).scopes` for a subgraph whose `graph.get('name')` matches.
   - Uses `describe()` with the fully-qualified scope+name to inspect `RandomNoise` (the emitter names it by its type, e.g., `RandomNoise` — the harness may need to resolve the name from the render output).
   - Applies a field edit: `random_noise.noise_seed = 99999` (changing the seed widget value).
   - Asserts A/B/C.

6. **Canonical case (e) — Reroute-into-subgraph variant**. The RuneXX graph has ~5 `Reroute` nodes and one subgraph "Calculate Frames" (UUID `63e8c999-...`). The wrapper node in the main graph has `type = "63e8c999-..."` and proxy inputs (matching the subgraph's `inputs` array). The harness:
   - Iterates over all Reroute nodes in the main graph (type `"Reroute"`).
   - For each Reroute, traces its output links. A link `[link_id, reroute_id, 0, wrapper_id, wrapper_slot, type]` means the Reroute feeds that proxy input.
   - Identifies the subgraph input that the Reroute-sourced link maps to (by matching the wrapper's input slot name to the subgraph's input name).
   - Finds an alternative source node in the main graph with a compatible output type.
   - Rebinds the Reroute's input (`upsert_link` from the alternative source to the Reroute's input).
   - Asserts A/B/C.
   - Also verifies that `del reroute` on a substrate `Reroute` is refused with a `original_virtual_node_immutable` diagnostic (confirming the existing contract).

7. **Empty-done regression** — with zero ops, `done()` passes A/B/C on all three graphs.

Each case returns the `DoneResult` for inspection, and the test asserts `result.ok is True`, `result.diagnostics == ()`, and that the summary text contains a recognizable sentence for each landed op.

---

## Phase 2: Polish surfaced by corpus run

### Step 3: Const-fold / bounded-`for` edge cases and diff-render (`vibecomfy/porting/edit_session.py`)
**Complexity: 2** — targeted fixes in one file, plus one new test

Polish items, driven by what the corpus run surfaces (fix only what breaks or produces ugly output):

1. **Const-fold polish** — `_fold_constant` already handles `BinOp` on `{Add, Sub, Mult, Div, FloorDiv, Mod}`. Corpus-run edge: `str + str` concatenation (e.g., `filename_prefix = "agent-edit/" + "corpus"`). The existing `_apply_binop` helper uses `operator.add` which handles string concatenation; verify it works end-to-end. Also verify `Div` on two ints returns a float (Python 3 behavior), which is fine for ComfyUI float fields. If `ZeroDivisionError` escapes, add a `constant_fold_failed` diagnostic instead of a crash.

2. **Bounded-`for` polish** — currently only `for n in range(N)` is supported in `_constant_range_values` at line 2343. The design doc (§3) envisioned `for n in <search-result>` (iterating over a prior `search()` list) and literal-list iteration `for n in [literal, ...]`. **If the corpus run surfaces a concrete need for literal-list iteration** (e.g., looping over sampler names `["euler", "heun"]`), add AST expansion for `for n in <constant_list>`:
   - **AST form**: Unroll at plan time: each iteration produces a copy of the loop body with `n` replaced by the constant value. This preserves placement inference (each unrolled statement gets its own `near=` anchor) and name binding (no new scoping constructs).
   - **Guard**: If the list contains more than `max_for_iterations` elements, emit a `for_iteration_cap_exceeded` diagnostic.
   - **If the corpus does NOT surface this need**, do NOT add it (anti-scope: no new grammar forms). The `_constant_range_values` rejection message `"Only for-loops over range(...) are allowed."` stays as-is.

3. **Diff-render** — `apply_batch` returns `BatchResult` with per-statement results and diagnostics, but no structured diff of what changed. Add a `BatchResult.render_diff() → str` method that produces a compact diff view (lines changed, field before→after) suitable for agent feedback. Drive its format from existing `_summarize_op` logic. This is a presentation concern only — no new edit logic.

### Step 4: `describe()` formatting and group-inference edge cases (`vibecomfy/porting/edit_session.py`)
**Complexity: 2** — formatting and placement inference refinements

1. **`describe()` polish** — `NodeDescriptor` is rich but its `__repr__` is the default dataclass dump. Add a `describe_formatted(name) → str` method to `EditSession` or a `NodeDescriptor.__str__` that renders a human-readable block (class_type, uid, mode, pos, inputs with socket types and link status, outputs with link counts). Verify it renders cleanly on nodes from the corpus graphs.

2. **Group-inference edge cases** — the placement module `infer_add_node_anchor_hint` already infers group membership from the anchor node. Check that:
   - (a) A node added with `near=X` inherits X's group.
   - (b) A 5-node pipeline cluster gets one shared group (all nodes share the anchor's group).
   - (c) A splice-placed node gets the group of the downstream node (prefer downstream because it's closer to the output; if downstream has no group, try upstream; if neither has a group, leave ungrouped with a diagnostic). This resolves the ambiguity when both sides have different groups.
   - Test these edge cases directly in the harness or in a dedicated placement test.

---

## Phase 3: Full suite validation

### Step 5: Run focused + porting suites and confirm no regressions
**Complexity: 1** — execution-only step

1. **Run** the adapter test: `pytest tests/support/test_corpus_schema.py -v` — must pass.
2. **Run** the new harness: `pytest tests/test_porting_edit_runexx_ltx.py -v` — all five canonical cases plus empty-done regression must pass.
3. **Run** the existing focused suite: `pytest tests/test_porting_edit_session.py tests/test_porting_edit_corpus.py tests/test_porting_edit_apply.py tests/test_porting_edit_ops.py tests/test_porting_edit_ledger.py tests/test_porting_edit_projection.py -v` — 100% green.
4. **Run** the broader porting suite: `pytest tests/test_porting_emitter.py tests/test_porting_ui_emitter.py tests/test_subgraph_emission_contract.py tests/test_virtual_wire_round_trip.py -v` — no regressions.
5. **If any regression surfaces**, fix it before declaring the harness green.

---

## Execution Order

1. **Step 1** (corpus schema adapter) — foundation needed before the harness can load corpus graphs.
2. **Step 2** (byte-identity harness) — harness *code* is implemented next; the code depends on Step 1. **Test-passing for Step 2 is deferred to Step 5.** The harness code can be written and iteratively fixed during Steps 3/4 without requiring a green run at Step 2's completion boundary.
3. **Step 3** (polish: const-fold, bounded-for, diff-render) — fixes surfaced by running the harness; applied to `edit_session.py`.
4. **Step 4** (polish: describe, group-inference) — fixes surfaced by running the harness; applied to `edit_session.py`.
5. **Step 5** (full suite validation) — after all edits land, all suites must pass.

## Validation Order

1. `pytest tests/support/test_corpus_schema.py -v` (added in Step 1).
2. `pytest tests/test_porting_edit_runexx_ltx.py -v` (Step 2 — the gate, validated in Step 5).
3. `pytest tests/test_porting_edit_session.py -v` (existing, must stay green).
4. `pytest tests/test_porting_edit_corpus.py tests/test_porting_edit_apply.py tests/test_porting_edit_ops.py tests/test_porting_edit_ledger.py tests/test_porting_edit_projection.py -v`.
5. `pytest tests/test_porting_emitter.py tests/test_porting_ui_emitter.py tests/test_subgraph_emission_contract.py tests/test_virtual_wire_round_trip.py -v`.
