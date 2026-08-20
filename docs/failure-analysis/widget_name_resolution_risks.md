# Widget Name Resolution Risks

Independent review date: 2026-06-29. Scope: blast radius of changing widget-name to `widgets_values` index resolution, especially `ui_widget_value_names_for_class`, `_widget_index_for_field`, `_widget_index_from_input_stubs`, `resolve_widget_name_with_provenance`, and object-info widget-name extraction.

## Executive Risk

The highest-risk part is not choosing a better fallback list. It is preserving a strict provenance boundary between three different concepts that are currently interleaved:

- raw object-info input order, including link sockets and `None` UI-only placeholders;
- compact `widgets_values` order, which must be 1:1 with serialized values;
- per-node LiteGraph UI evidence, which may have `widgets_values` but no trustworthy widget names.

The fix must be tightening: accurate names may unlock edits, but unknown or unproven names must remain unknown. ACN is the proof. The graph has `widgets_values=[0.6, 0, 0.75]`, but neither `_ui.inputs` nor the checked-in object-info entry names slot 0 as `strength`; object-info instead says the compact names are `["mask_optional", "timestep_kf", "latent_kf_override"]`. A naive fallback that "names whatever position seems plausible" will make the agent more confident while still editing the wrong parameter.

## Evidence Reproduction

### ACN_AdvancedControlNetApply

Scenario: [image-sd3-image-generation-with-controlnet-19d221.json](../../tests/live_agentic_harness/scenarios/image-sd3-image-generation-with-controlnet-19d221.json)

Graph node: `external_workflows/corpus/19d221f074b42462.json:1465`

Raw facts from the graph:

```text
node 60 class_type=ACN_AdvancedControlNetApply
_ui.widgets_values=[0.6, 0, 0.75]
widgets={"widget_0": 0.6, "widget_1": 0, "widget_2": 0.75}
_ui.inputs names=[positive, negative, control_net, image, mask_optional, timestep_kf,
                  latent_kf_override, weights_override, model_optional, vae_optional]
```

Current resolver facts:

```text
ui_widget_value_names_for_class("ACN_AdvancedControlNetApply")
  -> ["mask_optional", "timestep_kf", "latent_kf_override"]
object_info_widget_order
  -> ["positive", "negative", "control_net", "image", "mask_optional",
      "timestep_kf", "latent_kf_override", "weights_override"]
```

Reproduction against the raw source workflow:

```text
set_node_field node 60 latent_kf_override=0.5
  resolves widget_index=2 and mutates widgets_values [0.6, 0, 0.75] -> [0.6, 0, 0.5]

set_node_field node 60 strength=0.5
  fails: unknown_node_field ACN_AdvancedControlNetApply does not expose field 'strength'
```

Why `strength` is missing: this repo's selected object-info cache entry is a stub, [ComfyUI-Hotshot@stub.json](../../vibecomfy/porting/cache/object_info/ComfyUI-Hotshot@stub.json). It has required sockets `positive`, `negative`, `control_net`, `image`; optional rows `latent_kf_override`, `mask_optional`, `timestep_kf`, `weights_override`; and no `strength`. Worse, it classifies `mask_optional` as `FLOAT` even though the LiteGraph input row says `MASK`. This is not a simple "link-only type filtered out" case. It is incomplete or wrong stub data, so a fix cannot infer `strength` from object-info. It needs a higher-confidence source, class-specific schema, or no name.

### SVD_img2vid_Conditioning

Scenario: [video-svd-image-to-video-generation-fc240f.json](../../tests/live_agentic_harness/scenarios/video-svd-image-to-video-generation-fc240f.json)

Graph node: `external_workflows/corpus/fc240f1c4331a5e5.json:630`

Raw facts from the current graph:

```text
node 12 class_type=SVD_img2vid_Conditioning
_ui.widgets_values=[1024, 576, 14, 127, 6, 0]
widgets={"widget_0": 1024, "widget_1": 576, "widget_2": 14,
         "widget_3": 127, "widget_4": 6, "widget_5": 0}
_ui.inputs names=[clip_vision, init_image, vae]
```

Current resolver facts:

```text
ui_widget_value_names_for_class("SVD_img2vid_Conditioning")
  -> ["width", "height", "video_frames", "motion_bucket_id", "fps", "augmentation_level"]
object_info_widget_order
  -> ["clip_vision", None, None, "width", "height", "video_frames",
      "motion_bucket_id", "fps", "augmentation_level"]
```

Reproduction against the raw source workflow:

```text
set_node_field node 12 motion_bucket_id=200
  resolves widget_index=3 and mutates widgets_values [1024, 576, 14, 127, 6, 0]
  -> [1024, 576, 14, 200, 6, 0]
```

This differs from the shared brief: in the checked-in scenario graph, `motion_bucket_id` is already at compact value index 3. Index 6 is its raw object-info position after `clip_vision` and two placeholders. That discrepancy is itself a blast-radius risk: parts of the codebase use compact order and parts use raw order.

## Consumers And Assumptions

### Porting widget schema facade

[vibecomfy/porting/widgets/schema.py](../../vibecomfy/porting/widgets/schema.py)

- `effective_widget_names_for_class` returns curated `WIDGET_SCHEMA`, or raw `object_info_widget_order` when `allow_object_info_fallback=True`.
- `ui_widget_value_names_for_class` returns curated `WIDGET_SCHEMA`, or compact `object_info_widget_value_order` when fallback is allowed.
- Current assumption: curated entries are already aligned to `widgets_values`; object-info fallback must be compacted for field edits because link sockets do not consume `widgets_values`.
- Change impact: if this function starts using per-node `_ui` names or raw object-info order, every field edit and graph-inspection row can shift. It must not return raw object-info names to callers that write list indices.

### Object-info extraction and filtering

[vibecomfy/porting/object_info/consume.py](../../vibecomfy/porting/object_info/consume.py)

- `_WIDGET_LIKE_TYPES` removes link-only sockets; `_LITERAL_WIDGET_TYPES` keeps scalar widgets.
- `object_info_widget_order` returns reconciled raw `object_info_widget_order`, including `None` UI-only slots and link inputs, from [line 461](../../vibecomfy/porting/object_info/consume.py).
- `object_info_widget_value_order` compacts to literal widget names only at [line 511](../../vibecomfy/porting/object_info/consume.py).
- `_input_spec_is_widget_value` treats `FLOAT`, `INT`, `STRING`, enum/list choices, etc. as widget values and rejects socket-like uppercase types at [line 537](../../vibecomfy/porting/object_info/consume.py).
- `_iter_input_specs` ignores `hidden` and uses `input_order_all` when present, otherwise sorted names at [line 710](../../vibecomfy/porting/object_info/consume.py).
- Change impact: adding `hidden` or changing sort/order changes schema, strict-ready, and emit behavior. Treating unknown uppercase custom types as widget values or link-only can either over-accept fake names or drop real widgets.

### Apply path

[`vibecomfy/porting/edit/_resolve.py`](../../vibecomfy/porting/edit/_resolve.py#L1491) (`_resolve_target_field`; split replacement for the historical `apply_resolve_base.py`)

- `_resolve_target_field` canonicalizes the requested field, checks raw input slots, then resolves the widget value at [`_resolve.py:1491`](../../vibecomfy/porting/edit/_resolve.py#L1491).
- `_widget_index_for_field` in [`widget_slots.py:31`](../../vibecomfy/porting/edit/widget_slots.py#L31) delegates to the compact resolver (`allow_object_info_fallback=True`).
- `_widget_index_from_input_stubs` at [`widget_slots.py:65`](../../vibecomfy/porting/edit/widget_slots.py#L65) only runs if the raw input slot's `widget.name` equals the requested field. The current ACN/SVD `_ui.inputs` rows do not have `widget` dicts, so this recovery does not help.
- `apply_edit_cow` applies the resolved field to the IR widget/input channel at [`_ir_utils.py:709`](../../vibecomfy/porting/edit/_ir_utils.py#L709), replacing the historical `_apply_set_node_field` mutation seam.
- Change impact: more accurate names will immediately route model edits to different physical slots. That is desired only when the source is proven 1:1 with `widgets_values`. A wrong longer list is dangerous because `_write_widget_value` will grow `widgets_values`, creating shape overflow.

### Graph inspection and agent rendering

[`vibecomfy/executor/graph_inspection.py`](../../vibecomfy/executor/graph_inspection.py#L252) (`_widgets_from_ir`; current graph-inspection replacement for the historical `projection.py`)

- `_widgets_from_ir` labels each `widgets_values[index]` using the compact widget resolver; if the list is short, it recovers from named widget/input carriers.
- This is why ACN can be shown as `mask_optional=0.6`, `timestep_kf=0`, `latent_kf_override=0.75`.
- [emit_prepare.py](../../vibecomfy/porting/emit/emit_prepare.py) renders Python-call kwargs for the agent. For `widget_N`, it calls `resolve_widget_key_with_provenance` using `metadata.input_aliases` or `_ui_widget_aliases`.
- `_ui_widget_aliases` only reads `item["widget"]["name"]` from `_ui.inputs`, and returns `None` if alias count does not cover the highest `widget_N` key at [emit_constants.py:1062](../../vibecomfy/porting/emit/emit_constants.py).
- `_translate_widget_for_key` delegates to `resolve_widget_key_with_provenance` at [emit_constants.py:855](../../vibecomfy/porting/emit/emit_constants.py).
- Change impact: if projection, Python rendering, and apply use different provenance ladders, the agent can be shown one field, lint another, and mutate a third. The fix must make these surfaces agree or explicitly mark unresolved positions as `widget_N`.

### Compile widget aliasing

[vibecomfy/_compile/_widgets.py](../../vibecomfy/_compile/_widgets.py)

- Compile layer intentionally excludes object-info fallback: comments at [lines 1-8](../../vibecomfy/_compile/_widgets.py) say object-info fallback belongs to conversion/emission, not Layer 1.
- `resolve_widget_name_with_provenance` precedence is per-node `input_aliases`, committed `WIDGET_SCHEMA`, semantic patches, schema provider, then unresolved `widget_N` at [line 760](../../vibecomfy/_compile/_widgets.py).
- `apply_positional_widget_aliases` rewrites `widget_N` keys in node inputs at [line 805](../../vibecomfy/_compile/_widgets.py).
- `_compile/_resolve.py` updates raw `_ui.widgets_values` after folding Primitive helper values by using its own `_widget_index_for_field`, which checks committed schema, `metadata.input_aliases`, then `_ui.inputs[].widget.name` at [line 350](../../vibecomfy/_compile/_resolve.py).
- Change impact: if porting starts trusting object-info where compile does not, parity can pass/fail differently from runtime compile. If compile starts using object-info, it weakens a deliberate Layer 1 boundary.

### Porting widget aliases and parity

[vibecomfy/porting/widgets/aliases.py](../../vibecomfy/porting/widgets/aliases.py)

- Porting alias resolver includes object-info fallback, but `_object_info_position_is_safe` only allows an object-info index when there is no `None` before it at [line 108](../../vibecomfy/porting/widgets/aliases.py).
- `unresolved_widget_aliases` scans API prompt inputs for unresolved `widget_N` at [line 218](../../vibecomfy/porting/widgets/aliases.py).
- `widget_alias_suggestions` builds suggested schema entries and pads to observed widget count at [line 282](../../vibecomfy/porting/widgets/aliases.py).
- [parity.py](../../vibecomfy/porting/parity.py) canonicalizes `widget_N` keys. It can prefer caller-provided `class_widget_aliases`; otherwise it calls porting `resolve_widget_name_with_provenance` at [line 104](../../vibecomfy/porting/parity.py).
- Change impact: overly broad alias resolution can mask a bad conversion by canonicalizing both original and generated graphs through the same wrong name. Parity should prefer independent schema-source aliases where available, not a candidate-derived map.

### strict_ready

[vibecomfy/porting/strict_ready.py](../../vibecomfy/porting/strict_ready.py)

- `_schema_backed_widget_diagnostics` converts unresolved schema-backed `widget_N` aliases into `strict_ready_unresolved_widgets` errors at [line 319](../../vibecomfy/porting/strict_ready.py).
- `_hidden_model_filename_diagnostics` lets a model filename remain under `widget_N` only if per-node `metadata.input_aliases` has a non-`None` alias for that index at [line 391](../../vibecomfy/porting/strict_ready.py).
- `_class_widget_aliases` only trusts `node.metadata["input_aliases"]` at [line 413](../../vibecomfy/porting/strict_ready.py).
- Change impact: adding names can silence strict-ready unresolved-widget and hidden-model diagnostics. That is good only if the names are independently proven; it is gaming if a fix populates aliases from the same wrong map used to emit.

### emit/ui.py and widget_shape_fence

[vibecomfy/porting/emit/ui.py](../../vibecomfy/porting/emit/ui.py)

- `_widget_names_for_emission` intentionally uses raw `object_info_widget_order`, not compact value order, because `convert_ui_to_api` consumes serialized `widgets_values` positionally against raw object-info order with `None` slots.
- `_full_widget_name_count` establishes the schema widget count for the widget-shape fence using committed schema, raw provider order, or provider schema at [line 806](../../vibecomfy/porting/emit/ui.py).
- `_build_widget_values` rebuilds `widgets_values` from node widgets/inputs and raw captured widget values at [line 844](../../vibecomfy/porting/emit/ui.py).
- `derive_widget_shape_evidence` computes `candidate_widget_count`, `schema_widget_count`, overflow, and explicit overflow at [line 1681](../../vibecomfy/porting/emit/ui.py).
- `emit_ui_json` runs the fence pre-pass before emitting any nodes at [line 2049](../../vibecomfy/porting/emit/ui.py).

[vibecomfy/porting/widget_shape_fence.py](../../vibecomfy/porting/widget_shape_fence.py)

- `decide_widget_shape` pins unchanged identity-matched raw UI, allows carefully bounded observed/static recovery, refuses explicit overflow, and refuses dynamic/widget-delta cases without full raw evidence.
- `_static_refusal_reasons` marks overflow, schema-less dynamic widgets, low-confidence dynamic widgets, and dict-row widgets at [line 278](../../vibecomfy/porting/widget_shape_fence.py).
- `_has_full_raw_ui_payload` requires `id`, `type`, and `widgets_values` at [line 363](../../vibecomfy/porting/widget_shape_fence.py).
- Change impact: a more accurate name list can make `candidate_widget_count` or `schema_widget_count` change. That can be a good tightening if it exposes real overflow, but it can mis-flag valid graphs if dynamic UI-only widgets are represented as missing schema names. It can also over-loosen if "no `_ui` means skip validation" is introduced.

### emit/signatures.py

[vibecomfy/porting/emit/signatures.py](../../vibecomfy/porting/emit/signatures.py)

- Signature rows are schema-provider input order, not `widgets_values` order.
- `_build_input_signature_fields` iterates `schema.inputs.items()` at [line 206](../../vibecomfy/porting/emit/signatures.py).
- `ObjectInfoIndexSchemaProvider` orders schema inputs from object-info widget order via `_order_object_info_inputs` at [schema/provider.py:1112](../../vibecomfy/schema/provider.py).
- Change impact: if schema input order is changed to match compact widget values, agent node catalogs and compatibility displays change. This may help named parameter selection, but it must not imply link sockets are editable widgets.

### emit/subgraph.py

[vibecomfy/porting/emit/emit_subgraph.py](../../vibecomfy/porting/emit/emit_subgraph.py)

- `_positional_ui_widget_names` tries explicit `widgets`, `widget_inputs`, `input_aliases`, `properties.proxyWidgets`, committed schema, object-info raw order, then `_ui.inputs[].widget.name`.
- It maps names by value position and blocks `None` schema positions from being overwritten.
- `_ui_widget_values_by_name` returns `raw_values[index]` for any non-`None` name at [line 915](../../vibecomfy/porting/emit/emit_subgraph.py).
- Change impact: because it currently enumerates raw object-info by index, SVD-style raw order can label compact value index 3 as `width` if earlier link/placeholder entries are not compacted. This is a likely hidden consumer to audit with tests.

### Browser/front-end live node handling

Browser code resolves live node widget names against `node.widgets`, not object-info:

- [comfy_adapter.js](../../vibecomfy/comfy_nodes/web/comfy_adapter.js) reads/writes by `findSlotIndex(node.widgets, rest[0], "name")`.
- [vibecomfy_roundtrip.js](../../vibecomfy/comfy_nodes/web/vibecomfy_roundtrip.js) reads named widget slots from live `node.widgets`.
- [panel_overlay.js](../../vibecomfy/comfy_nodes/web/panel_overlay.js) also matches widget names/labels.

Change impact: if Python-side names diverge from live `node.widgets`, server-side apply can accept names that the browser cannot highlight/read/write, or vice versa.

## Regression Risks

1. **Raw order accidentally used as value order.** SVD raw object-info order puts `motion_bucket_id` at position 6, but compact `widgets_values` puts it at 3. Any fix that swaps `ui_widget_value_names_for_class` to raw `object_info_widget_order` will break SVD and every node with leading link sockets or `None` placeholders. Fence impact: stricter only by accident; likely bad false overflow or wrong slot mutation.

2. **Stub/schema errors become authoritative.** ACN object-info says value index 0 is `mask_optional`, but graph behavior and user intent indicate 0 is ControlNet strength. If the fix "trusts object_info unless `_ui.widgets` exists", ACN remains wrong and the agent gets stronger but false names. Fence impact: may pass current length checks while preserving semantic corruption.

3. **`widgets_values` gets extended instead of rejected.** `_write_widget_value` appends `None` up to any resolved index. A longer-but-wrong name list can turn a typo or raw-order index into a larger serialized vector. Fence impact: good only if explicit overflow remains an error; bad if recovery/pinning is broadened to carry it forward.

4. **strict_ready pass count is gamed.** Populating `metadata.input_aliases` from an unproven map silences `_schema_backed_widget_diagnostics` and `_hidden_model_filename_diagnostics`. Fence impact: looser, forbidden.

5. **Parity masks the same bug on both sides.** Parity canonicalizes `widget_N` through alias maps. If the same derived map is used for original and generated graphs, wrong names can compare equal. Fence impact: not directly stricter; this is a false-negative gate.

6. **Agent-render/apply mismatch.** If render is fixed to show `strength` but apply still uses `ui_widget_value_names_for_class`, the agent will correctly request `strength` and receive `unknown_node_field`. If apply is fixed but render is not, the agent may never choose the right field. This changes all named-widget scenarios.

## Gaming Surface: Do Not Weaken These Assertions

These gates must remain tight:

- `apply_resolve_base.py:220`: unknown field must stay an error when no input, widget index, widget key, or schema input proves it.
- `apply_resolve_base.py:234`: non-widget fields must remain non-editable through `set_node_field`.
- `apply_mutate.py:420`: any path that reaches list mutation must have a proven bounded index; do not let arbitrary names synthesize high indices.
- `widget_shape_fence.py:196`: explicit widget overflow must remain refusal unless existing narrow recovery conditions prove it is safe.
- `widget_shape_fence.py:234`: missing full raw UI/raw widget/layout evidence must continue blocking pinning when there is a widget or link delta.
- `strict_ready.py:319`: unresolved schema-backed positional widgets must remain strict-ready errors.
- `strict_ready.py:391`: hidden model filenames under unresolved `widget_N` must remain errors.
- `parity.py:92`: independent `class_widget_aliases` should remain preferred for parity guardrails; do not compare both sides through candidate-derived aliases.

Forbidden "fix" shapes:

- fallback to "any name that appears anywhere in `_ui.inputs`";
- skip validation when `_ui` is absent;
- treat `raw_widgets.length == len(names)` as proof of semantic correctness;
- fabricate aliases from `widgets_values` type/default matching without provenance;
- downgrade unknown fields to positional best-effort edits;
- add `input_aliases` just to silence strict-ready.

## Edge Cases

- **No `_ui`.** Programmatic/new nodes may have schema but no serialized widget payload. Correct behavior is schema/default regeneration only when schema confidence and expected count are known; otherwise unresolved `widget_N` must stay unresolved. Do not skip the fence.

- **Object-info order differs from serialized order.** SVD demonstrates raw order includes link sockets/placeholders while `widgets_values` is compact. Emit needs raw order for `convert_ui_to_api`; apply needs compact value order. These must stay separate APIs.

- **Dynamic or conditional widgets.** `widget_shape_fence` already treats dict-row dynamic widgets and overflow as special. Dynamic model-loader-dependent widgets can vary length. A fix must preserve raw payload when unchanged and refuse changed dynamic widget surfaces without full evidence.

- **Widget also connected as input.** `_resolve_set_node_field` may remove an overriding link when the raw input slot is linked. If name resolution changes, automatic link removal can delete the wrong link. `_widget_index_from_input_stubs` must only count actual widget stubs, not every nullable input row.

- **Hidden/UI-only widgets.** `None` entries are real positions for emission but not named editable fields. A fix must preserve `None` for slot count and never expose it as a friendly name.

- **ACN missing strength.** The current cache has no `strength`; the graph's `_ui.inputs` also has no `strength`; only `widgets_values[0]=0.6` hints at strength semantically. That is insufficient. The safe result is "unresolved/unknown" unless a higher-confidence AdvControlNet schema or per-node widget metadata names slot 0.

- **Duplicate names.** Any name map with duplicates is unsafe for write routing. First-match behavior would silently pick one slot.

- **Mapping-form `widgets_values`.** `_widget_value_for_field` and `_write_widget_value` support mapping form. A fix for list indices must not regress dict-key widgets.

## Agent-Rendering Feedback Loop

The harness has 100 scenario files. A query scan found about 25 graph-changing tasks that likely edit a named widget parameter, including strength, steps, scheduler, frames, fps, motion bucket, prompt text, denoise, LoRA strength, output format, and dimensions. This is an estimate from scenario query text, not a semantic execution trace.

High-risk examples:

- `image-sd3-image-generation-with-controlnet-19d221`: ControlNet strength, ACN custom node.
- `video-svd-image-to-video-generation-fc240f`: `motion_bucket_id`, core SVD node.
- `image-image-to-image-with-controlnet-and-dwpreproces-49d057`: ControlNet strength.
- `video-anime-video-to-video-with-controlnet-and-openp-cb5cd2`: ControlNet conditioning strength.
- `video-wan-alpha-video-generation-with-lora-and-gguf-6a9e20`: LoRA model strength.
- `multi-image-to-video-generation-with.json`: sampling steps and sampler.
- `video-wan2-2-text-to-video-with-dual-unet-and-model-03fced`: steps for both UNETs.

Accurate names could fix many of these because the agent currently edits by field name. It can also surface new failures: if an accurate but unfamiliar custom-node name replaces a generic `widget_N`, the model may choose the wrong "strength" among multiple strength-like controls; if render shows fields that apply rejects, the agent can get stuck; if render hides unresolved widgets entirely, the agent loses valid positional editing ability for simple cases.

## Recommendations To The Implementer

1. **Keep two explicit orders.** Maintain separate APIs/types for raw object-info slot order and compact `widgets_values` order. Do not allow raw order to flow into apply/index lookup.

2. **Prefer per-node serialized widget names only when they are truly aligned.** `node.widgets`, `widget_inputs`, `input_aliases`, or `properties.proxyWidgets` can be strong evidence. Plain `_ui.inputs[].name` is not enough; ACN and SVD show input rows can be link sockets or non-widget rows.

3. **Fail closed on semantic gaps.** ACN `strength` cannot be inferred from current evidence. The safe fix leaves it unresolved until a real AdvControlNet schema/curated entry is added.

4. **Make render, lint, projection, apply, parity, and strict-ready share provenance semantics.** They can expose different views, but each name should carry a source and a confidence/tightness decision. Do not let one path silently accept a name another path rejects.

5. **Add regression tests around gate tightness, not just pass count.** Tests should assert SVD compact index 3, ACN `strength` remains unknown without authoritative schema, ACN current misleading names are not presented as authoritative, overflow is refused, and strict-ready unresolved aliases are not silenced by candidate-derived aliases.

Single highest-risk codepath: `vibecomfy/porting/edit/apply_resolve_base.py:207 -> apply_slots._widget_index_for_field -> ui_widget_value_names_for_class -> apply_mutate._write_widget_value`. This is where a displayed or model-chosen name becomes a physical serialized index, and a wrong answer mutates the graph without necessarily tripping the full-UI guard.
