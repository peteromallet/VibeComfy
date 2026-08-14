bun(53884) MallocStackLogging: can't turn off malloc stack logging because it was not enabled.
I'll start by reading the megado skill and the B08-cut acceptance criteria, then review the executor diff as a read-only oracle.I'll pull the B08-cut delta, tasklist acceptance, and the claimed invariant sites, then run the focused test slice.The delta is 17 files, +1743/−171 — larger than the executor summary. Next I’ll read the shared invariant and the mutation/projection call sites.The invariant module is the spine of this batch. Next I’ll read the mutation, materialize, and projection call sites against that contract.Several seams look suspicious — unbounded SimpleCalculator/LTXVAddGuide, leftover append in `_ensure_input_slot`, and add-node mutating before target-slot failure. I’ll verify those next.I'll read the new fixtures and remaining call-site diffs, and run the focused test slice.I need the real SimpleCalculator / LTXVAddGuide contracts and the focused pytest run before I can call this.B08 CHECKPOINT VERDICT: PASS — One shared working-graph invariant closes the phantom-slot chain; schema cannot mint an absent output index; unknown targets no longer fabricate sockets; focused 108 + B03 pin spot-check are green.

## Focus findings

### 1. One shared invariant — PASS
`vibecomfy/porting/endpoint_invariant.py` is the single contract. Resolution (`resolution.py` `resolve_output_slot_index` / `resolve_source_endpoint` / `resolve_target_endpoint`), mutation (`assert_source_slot_in_bounds` in `apply_resolve_base.py:514` and `apply_mutate.py:158`, `_ensure_input_slot`, add-node source checks), and projection (`projection_port_name` via `_native_port_name`) all import from that module.

`resolve_working_port` (`endpoint_invariant.py:488-604`) treats working `inputs`/`outputs` as authoritative. Schema may enrich a **present** socket; an output schema hit is accepted only when `0 <= schema_index < len(working_sockets)` and the working name is the requested name, `""`, or `None`. Otherwise it returns `ghost_schema_output` / `unknown_output_slot` and never a catalog index that is not on the node. Output callers also require `isinstance(port.slot_index, int)` (`resolution.py:505, 637`).

### 2. Phantom-slot chain closed — PASS
Old path: schema index → `_apply_upsert_link` wrote `origin_slot=source.slot_index or 0` → silent no-op on OOB output/input refs → projection `"Missing stable link from port"`.

New path:
- Source slot is bounds-checked before resolve returns and again before write (`apply_resolve_base.py:514-527`, `apply_mutate.py:158-173`). `origin_slot` is the verified index, not `or 0`.
- `_ensure_output_link_reference` / `_set_input_link_reference` (`apply_links.py:343-419`) return typed `source_slot_out_of_bounds` / `target_slot_out_of_bounds` instead of silent returns.
- Ghost EmptyLatentImage `IMAGE`/`MASK` (schema slots 2 and 1, working count 1) fail in resolve with `mutation_started is False` and `original == before`.

### 3. No synthetic input fabrication for unknown names — PASS
`_ensure_input_slot` no longer appends `{"name", "type": "*"}` for an arbitrary name. Unauthorized names return `unknown_target_input` / `undeclared_synthetic_port` / the contract reason (`apply_links.py:328-335`). `test_upsert_link_rejects_unknown_target_input_without_synthetic_port` locks KSampler `not_a_real_input`. Add-node unknown inputs die in resolve as `unknown_add_node_input` before `materialize_litegraph_node`.

Authorized count-driven names may still be appended at apply-direct time (`apply_links.py:339`). That is the explicit dynamic contract, not the old carte blanche. On the product path, upsert lint still requires the name to already exist on the working node (`lint.py:979-993` via `resolve_input_slot_index`), so opportunistic append is not how the batch loop lands links.

### 4. Dynamic-port contract — PASS (one residual lint seam)
One predicate: `dynamic_port_authorized` (`endpoint_invariant.py:291-381`). Callers: `resolve_working_port`, `_ensure_input_slot`, `lint._is_dynamic_add_node_input` (replaces the old ImageConcat-only regex), `_dynamic_add_node_input_spec`. No third copy in resolution/mutation/projection.

- Count families have positive + one-past fixtures (`test_dynamic_family_ports_positive_and_one_past_boundary`). ImageConcat `image_3` at count 2 and LTX `num_images.image_2` at count 1 fail `dynamic_port_out_of_range`.
- SimpleCalculator `input_N` / LTXVAddGuide `guide_N` match the existing `schema/validate.py:465-468` precedent: lower bound `N>=1` only, no count field. Not a new carte blanche.
- Helpers: GetNode output-only, SetNode input-only, PrimitiveNode output-only, Reroute both. Direction mismatches are tested. `MysteryNode` / `Reroute.extra_slot` are rejected. There is no “has dynamic INPUT_TYPES” escape.

Residual (non-blocking): upsert lint still indexes `meta.input_names` and does not call the predicate. `reroute.value` therefore resolves in `resolve_delta` but would be `missing_target_input` if lint is on. Pre-existing lint shape; add-node lint was migrated. Not the C8 write path.

### 5. Materialize-then-validate — PASS
`materialize_litegraph_node` (`ui.py:1326-1330`) now builds inputs via `schema_input_sockets_for_unwired_node`: schema order, `input_spec_is_socket_only` only (widgets excluded), then contracted dynamic names. KSampler fixture is `["model", "positive", "negative", "latent_image"]`. ImageConcat add-node with `inputcount=3` materializes `image_1..image_3` and wires 1 and 3. Write-time bounds checks emit diagnostics, not silent returns.

### 6. Projection name-first + JS mirror — PASS
Python `_native_port_name` delegates to `projection_port_name`: preferred/canonical name, then validated index. JS `nativePortName` does the same lookup order (`projection_registry_v1.js:257-274`). Integer OOB still raises `"Missing stable link from port"` (locked in `test_m1_contracts` / `test_comfy_nodes_agent_edit`). Native six-tuples still carry integer slots, so name-first helps string ports; index fallback is bounds-checked.

Residual: Python also accepts `output_N` positional aliases; JS does not. Native links are integers, so this is unused on the C8 path.

### 7. Fail before mutation; B05 journal intact — PASS
Malformed endpoints fail in `resolve_delta` / early apply checks. `apply_delta` returns `candidate=None`. Ghost/unknown/add-node-unknown tests assert `mutation_started is False` and byte-equal original. Add-node apply errors now abort `resolve_delta` (`apply_core.py:53-59`) so a later op cannot run on a half-built ledger. B08 does not touch journal/rollback/`_frag_*` batch-loop files (`git diff --name-only` is the 17 B08 files only). Ordinary validation still fails closed without a published candidate.

### 8. Scope, whitespace, B03/B02 — PASS
`git diff --check 3772107f..32c618e1` is clean. Delta is the B08 surface (invariant, resolve/mutate/lint/ui, both projection registries, targeted tests, batch brief). No prompt/model work. B03 pin/semantic-set spot-check: **42 passed**. B02 files are not in the range; full corpus preservation was not re-run.

Executor “15 files, +953/−171” under-counts: actual **17 files, +1743/−171**, almost entirely the new 739-line invariant module. Not a scope violation.

### 9. Focused slice — PASS
Re-ran the exact filter (`-p no:rerunfailures`):

```
108 passed, 1 skipped, 452 deselected in 6.57s
```

Matches the orchestrator number. No scenario recovery count is claimed.

---

No rework list. Residuals for later, not B08 blockers: upsert lint still name-index-only; JS `output_N` alias gap; `widgets_values` lists are not read as `inputcount` (fail-closed default 2); `schema/validate.py` still has a parallel family list outside the three required sites.
