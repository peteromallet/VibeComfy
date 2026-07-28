# Fix #2: authoritative schema binding, not another evidence search

## Position

Fix #2 should be a small construction-boundary correction with three parts: make an already-resolvable authoritative schema outrank workflow-derived provisional schema; compile high-confidence named provenance values into validated constructor bindings; and preserve the authoritative UI widget omission shape when materializing a new node. All three are achievable now. They do not require m4's atomic typed splice.

This is the minimal general fix for case 05. It is **not** a complete fix for case 09, whose current artifact has no named widget priors and selects the wrong graph role. Treating 09 as the same failure would make #2 sprawl into role inference.

## Confirmed break

The primary diagnosis is **(a), caused by provider shadowing**, with **(c) as a secondary policy gap**. It is not (b) or (d).

The evidence reaches the fixer. `_build_precedent_adaptation_prompt` serializes every slice's `widget_values` and `incident_edges` into “Role-preserving provenance priors” (`vibecomfy/comfy_nodes/agent/edit_research.py:159-183`). The adapt/revise loop invokes it (`vibecomfy/comfy_nodes/agent/edit_batch_loop_intro.py:734-747`). Case 05 attempt 002's actual `model_request.json`, not merely `research.json`, contains the complete filename, `strength: 1`, `low_mem_load: false`, and the edge to `WanVideoModelLoader.lora`. Therefore (b) is false.

The same prompt exposes `WanVideoLoraSelect` only as `widget_0`, `widget_1`, and `widget_2`. Hydration constructs workflow candidates unconditionally and installs them as `CompositeSchemaProvider(provisional, state.schema_provider)` (`edit_research.py:641-710`). `CompositeSchemaProvider.get_schema` is first-hit-wins (`vibecomfy/schema/provider.py:496-508`), so the 0.55-confidence workflow schema masks the existing `object_info_index` schema. The latter already resolves `WanVideoLoraSelect` with literal inputs `lora`, `strength`, `low_mem_load`, and `merge_loras`; on-demand installation is not needed for this class.

The artifacts show the consequence. Attempt 003 authors `{widget_0: "", widget_1: 1.0, widget_2: false}` and the candidate records `_vibecomfy_schema_provider: workflow_json_provisional`. Attempt 002 instead calls `clarify()` for the filename and strength even though both appear in that turn's model request. The system prompt creates this escape hatch: provisional values may only be copied positionally, friendly names must not be guessed, and an opaque `widget_N` should lead to clarification without corroboration (`vibecomfy/comfy_nodes/agent/provider.py:398-406`). It also says “Prefer one valid default over asking” (`:408-411`), so (c) is not a blanket ask-first rule; it is a missing rule that says an exact authoritative-name plus qualified provenance prior is sufficient corroboration.

There is no name mismatch. The authoritative names are exactly `lora`, `strength`, and `low_mem_load`. Attempt 001 even maps the same evidence to `widget_0..2`, proving the semantic correspondence, but does so by model inference rather than a contract. Thus (d) is false.

Attempt 001 also exposes a second requirement for going green, rather than merely avoiding clarification. Its node has four widget values, while the oracle's golden witness has the compact one-value vector containing only the LoRA filename. `_find_additive_witness` deliberately requires equal widget-vector length and values (`vibecomfy/demo_factory/predicates.py:91-105`). `materialize_litegraph_node` currently expands every available schema default into `merged_fields` (`vibecomfy/porting/emit/ui.py:1277-1284`), and `_build_widget_values` emits the full committed order (`:951-1031`). A correct binding can therefore still be serialized too expansively. The fix must preserve compact omission: default-equivalent trailing fields remain implicit, while positions through the last explicit non-default field remain materialized.

Case 09 is a different second data point. Its existing `ImageScaleToTotalPixels` nodes are authoritative, and the fixer sees named fields, but its `research.json` has no widget-valued provenance slice. The removed golden instance is `nearest-exact`, fed by surviving node 76 and feeding nodes 8 and 40. Attempt 003 instead adds a `lanczos` node after `VAEDecode` and before `SaveImage`. Schema precedence cannot invent the absent role and value evidence, and a provenance binder has nothing to bind.

## Scoped change

| Piece | Concrete shape and site | Bucket |
|---|---|---|
| **A1 — fallback-only provisional hydration** | In `_hydrate_research_precedent_node_schemas` (`edit_research.py:688-764`), resolve against the existing provider first, filter workflow candidate schemas to genuinely unresolved classes, and compose `CompositeSchemaProvider(state.schema_provider, provisional)`. Apply the same rule to the registry overlay at `:754-763`. Add provider tests proving `object_info_index`/live/on-demand wins and provisional remains available on a real miss. | **A** |
| **A2 — validated prior compiler** | Beside `_build_precedent_adaptation_prompt`, join slice values by selected class and exact authoritative `NodeSchema.inputs` name. Accept only literal widgets with qualifying provenance/confidence and values that pass the existing type/choice validator; reject sockets, unknown names, conflicts, and ambiguous same-class instances. Render a constructor-ready “validated restoration bindings” map, not another neutral JSON dump. Explicit user/model fields win. Update the policy at `provider.py:398-411` so such a binding is corroboration and must be consumed rather than queried again. | **A** |
| **A3 — compact authoritative widget emission** | Stop `materialize_litegraph_node` from making every schema default explicit (`emit/ui.py:1263-1323`). Emit named values in authoritative order only through the last explicit non-default/UI-required position; preserve intervening defaults when positional alignment requires them. Reuse `_build_widget_values`, with regressions for required first widget, a later explicit widget, and optional trailing defaults. | **A** |
| **B1 — typed atomic construct/splice** | m4 should carry authoritative schema, qualified priors, chosen surviving anchors, node creation, all links, and validation in one transaction. This removes model-authored positional constructors and half-built branches. | **B / m4** |
| **B2 — role/path disambiguation** | When several same-class instances or plausible insertion points exist, infer the missing active-path role and bind one source instance to surviving peers before construction. This is the reliable solution for case 09-like ambiguity. | **B / m4** |

No change is needed in the ordinary semantic alias machinery. `_resolve_add_node` already canonicalizes named fields (`vibecomfy/porting/edit/apply_resolve_add.py:40-82`), `_apply_add_node` passes them through (`apply_mutate.py:219-243`), and `_build_widget_values` can position them. The missing operation is upstream: turn qualified evidence into named fields before the model asks. A2 may initially be prompt-compiled for the smallest patch, but its output should be a structured binding map so m4 can later consume the same contract directly.

## Ordered implementation plan

1. Land A1 first. It is the single highest-leverage change for case 05: the fixer will see `lora=` and `strength=` rather than opaque positions. It also corrects a general priority inversion for every overlapping workflow schema.
2. Land A2 in the same regression. Test that the case-05-shaped prior becomes named constructor bindings, explicit request values override it, and low-confidence/conflicting/socket values do not bind. This removes model nondeterminism and the clarification loophole.
3. Land A3 before claiming oracle green. Test the resulting UI vector, not only the Python constructor or `AddNodeOp`.
4. Rerun only after those localized tests pass. Do not weaken the witness predicate.

## Risk and anti-gaming

The binder may consume only evidence already present in the public research packet. It must never inspect campaign golden graphs, hard-code `WanVideoLoraSelect`, special-case the `WanVid\...` filename, or copy a value merely because the class matches. The admissible key is: selected source instance and role, exact class, exact authoritative literal field, qualifying provenance/confidence, successful value validation, and no conflict. Explicit user intent has higher precedence. Ambiguous evidence remains unbound.

Default elision must be semantic UI serialization, not oracle accommodation: apply it uniformly from schema defaults and explicit-field presence, with no access to expected witness length. The exact edge/widget oracle remains unchanged.

## Verdict

**Case 05 can probably go green with the complete A-bucket #2 alone; case 09 cannot.** Confidence for 05 is about **85%** once A1+A2+A3 are together. A1 alone most likely stops the clarification, but attempt 001 proves that consumption without compact authoritative emission can still be rejected.

For 09, confidence from this #2 alone is below **20%**: there is no named prior to bind, and the observed failure is placement/role selection. The exact case might still be rescued pre-m4 by separately producing a source-instance slice with its three incident edges and `nearest-exact` value, but that is a provenance-selection fix outside this scoped #2. Reliable success for 09 and the broader ambiguous additive class needs m4's role-bound atomic splice.
