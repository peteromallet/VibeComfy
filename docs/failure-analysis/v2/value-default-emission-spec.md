# Value-default emission

## Decision

Add a deterministic **value-default binder** to the named add-node construction path. The model remains responsible for selecting the node, binding its role, and wiring it; it normally omits literal widget arguments. Before an `AddNodeOp` is materialized, the binder computes each literal widget from an explicit user value, a qualified provenance prior, or the authoritative schema default, in that order.

This is option **(b), a constrained constructor**, implemented as a binding stage between batch-REPL call resolution and add-node apply. Prompt policy is a supporting control, not the mechanism. A post-construction rewrite is too late: it can silently erase legitimate user intent, operates after field provenance has been lost, and couples semantic choice to positional UI serialization. Prompt-only control has already failed empirically in case 08: the prompt contained the exact seed and scheduler, yet the model authored plausible substitutes.

The intended flow is:

`source breadcrumb → role-bound, tagged priors → ValueDefaultBinding → batch constructor/link resolution → effective named fields → schema validation → LiteGraph widget emission`

The binding result and its receipts must remain structured data. They must not be reconstructed by parsing prose from the fixer prompt.

## Binding contract

For each literal widget field on the selected class and role, the binder applies this precedence:

1. An exact value explicitly supplied by the user.
2. One unambiguous, high-confidence, schema-valid provenance prior.
3. The authoritative schema default.
4. If none exists, leave the field unset and report the missing requirement; never invent a value.

A prior is auto-applicable only when all of the following are true:

- Its per-value `provenance` is on an explicit allow-list, initially `source_template`. Future origins may be admitted only if they provide the same verified lineage and immutability guarantees; an unknown provenance string is never implicitly trusted.
- Its per-value `confidence` is exactly `high`.
- The source instance has been selected for the target role without an unresolved same-class or same-role tie.
- Its class and canonical named field match the constructor target. Provisional `widget_N` names may be retained as evidence but cannot bind a schema-named field unless authoritative widget ordering resolves the mapping.
- The field is a literal widget, not an input socket, and the value passes the authoritative schema's type, enum, range, and shape validation.
- There is no explicit user override for that class/role/field.

Conflicting values from otherwise qualified priors make that field ambiguous; confidence is not resolved by taking the first match. Low- or medium-confidence priors remain visible evidence but are not defaults. A stale, schema-incompatible, role-ambiguous, or unnamed prior is refused. If refusal leaves no prior, the declared schema default is used. If the schema has no default for a required literal, construction remains incomplete and produces a diagnostic or clarification instead of a guess.

`None` and other falsey values are real prior values, not absence. Source-observed positional shape may accompany the named bindings so that UI-only `None` slots and the source vector length can be reproduced, but only as labelled source-history metadata validated against authoritative widget ordering. The campaign's expected widget length is never an input.

## Extraordinary overrides and edit-after

An override means selecting a value different from the effective prior/default. It is allowed only with an authority receipt in one of two categories:

- **Explicit user value:** the request supplies the literal value and identifies the field sufficiently to bind it. “Use 12 steps” qualifies; “make it better” or “use more steps” does not authorize the model to choose an arbitrary number.
- **Schema-driven correction:** the prior is invalid under the authoritative current schema and there is one deterministic correction, such as lossless primitive normalization, a uniquely resolved enum alias, or replacement by the schema's declared default. If several legal corrections exist, the system uses the schema default when present or asks/defers; the model does not choose among plausible values.

Model preference, common practice, aesthetic judgment, performance tuning, and “this value seems more modern” are not extraordinary circumstances. A model-supplied constructor literal that equals the effective bound value can be normalized away as redundant. A different literal without an authority receipt is rejected with a diagnostic showing the effective value and its provenance.

Defaults are a starting state, not a straitjacket. After construction, ordinary user/manual editing remains possible. Agent-issued assignments such as `x.steps = 12` pass through the same gate: they require a user-value receipt from the request or a resolver-produced schema-correction receipt. The receipt records field, old value, new value, basis, provenance, and validation result. The model may explain an override, but its own prose cannot mint authority. A later user request containing a new explicit value creates a new receipt and can edit the already-defaulted node normally.

## Integration points

`vibecomfy/executor/provenance.py` continues to recover source instances. `vibecomfy/executor/research.py::_tag_source_widget_values` and `_build_precedent_slices` should additionally produce a normalized binding envelope keyed by class, selected role/source instance, and canonical field. It should preserve per-value provenance/confidence, conflicts, schema-validation status, source index/shape where admissible, and the reason a value was or was not eligible. The `WorkflowSlice`/research contract should carry this envelope into `research.json`; selection must never collapse multiple same-type instances by first match.

`vibecomfy/comfy_nodes/agent/edit_research.py::_build_precedent_adaptation_prompt` should render the policy plainly: omit ordinary literal widgets, wire the node, and expect qualified values to be supplied automatically. More importantly, the same structured envelope must be passed alongside the prompt through agent state. `vibecomfy/comfy_nodes/agent/edit_batch_loop_intro.py::_stage_agent_batch_repl`, where `EditSession` is constructed, should supply it as binding context. It must not rely on the model copying JSON text back into Python.

The enforcement seam is the batch-REPL construction path. Extend `EditSession` with an immutable `ValueDefaultContext`. In `_resolve.py::_resolve_add_node_call`, classify model keywords as links, placement hints, or proposed literal overrides. Before `_parse_execute.py::_lower_statement_op` creates the `AddNodeOp`—or equivalently at the start of `apply_resolve_add.py::_resolve_add_node` with the context explicitly threaded through `apply_delta`—merge the effective fields by the precedence above. The latter is the preferred shared enforcement point because every add-node caller then receives identical schema validation. `ResolvedAddNodeSpec` should carry binding/override receipts, and `apply_mutate.py::_apply_add_node` should report them in apply diagnostics.

`vibecomfy/porting/emit/ui.py::materialize_litegraph_node` already merges schema defaults before explicit fields, while `_build_widget_values` maps named fields into positional `widgets_values`. Keep those functions as serializers: feed them the effective named fields and, when qualified, source-observed raw shape metadata. They must not choose between competing priors or infer model intent. Authoritative `object_info` widget ordering remains mandatory where source positions must be preserved.

For post-construction assignments, route `SetNodeFieldOp` through the same `ValueDefaultContext` and receipt check before `_write_widget_value`. Existing edits to nodes outside this defaulted construction flow retain their normal behavior unless an active restore binding protects that field.

## Grading and anti-gaming

This mechanism will often reproduce the golden widget vector in remove→restore cases, so `vibecomfy/demo_factory/predicates.py::_find_additive_witness` should pass when the source history and golden describe the same removed node. That is legitimate restore evidence: the values came from the workflow's own breadcrumbed source state, independently of evaluation.

The existing exact type + incident-edge + positional-widget witness should remain a dedicated restore regression predicate. NORTHSTAR's product-grade oracle should instead issue tiered verdicts for schema validity, role-correct wiring, task postconditions, preservation, and optional runtime evidence. A novel valid addition must not fail merely because its values differ from a hidden golden. Restore identity and product validity are separate claims.

The evidence boundary is strict:

- The binder may read only the current graph, its verified workflow lineage, the user request, and authoritative schemas.
- It must never open campaign golden graphs, predicate payloads, expected values, or expected widget lengths.
- Every applied value is labelled `user`, `source_template`, or `schema_default`, with a receipt.
- Ambiguity refuses or falls back to a schema default; it never guesses.
- Tests should prove that removing access to the golden leaves binding results unchanged.

`predicates.py` therefore needs no value feed into the constructor. In the NORTHSTAR split, rename or isolate the current exact predicate as restore-only and add intent-based product predicates; do not weaken the exact restore check to make this feature pass.

## Implementation sequence and risk

First define the binding envelope and conflict/eligibility tests in research contracts. Then thread it into `EditSession`, enforce merging and override receipts in add-node resolution/apply, and finally teach UI emission to preserve qualified source shape without consulting evaluation state. Add focused tests for explicit user precedence, high-confidence prior use, low-confidence/conflict refusal, invalid-prior schema fallback, no-default failure, edit-after authorization, and identical results with no golden available.

The largest risk is that a source prior is historically authentic but wrong for the target: the template may have changed versions, the current graph may use a different model family, or role inference may bind the wrong same-type instance. Automatic application can then make a bad choice look authoritative and reduce useful model scrutiny. Mitigate with lineage/version hashes, authoritative current schemas, exact role binding, conflict refusal, visible receipts/diffs, and a user-editable post-bind path. Where those checks cannot establish compatibility, prefer the schema default or an unresolved diagnostic over historical fidelity.
