# Capability transfer: recasting the real-additive-editor epic

## Position and overlap verdict

The hypothesis is correct: the epic's product goals and guardrails stand, m2 stands, but m3 and m4 need a paradigm-level recast. The current chain is close in prerequisites and wrong at its executable seam.

M3 currently improves the evidence shown to a fixer: it retrieves provenance/corpus neighborhoods, preserves same-class instances, attaches values and incident edges, and labels roles. That fixes lossy retrieval, but it never isolates a capability region, records its internal topology, computes typed boundary ports, abstracts source node identities, or emits a reusable artifact. `provenance.py::collect_type_instances` and `research.py::_build_precedent_slices` are extractor seeds; their primary product is still a descriptive `WorkflowSlice`, often a one-node instance, not a replayable module.

M4 explicitly remains “the fixer lands its plans.” Schema-named `add_node`, deterministic link materialization, sibling splice, branch diagnostics, and intent-condition feedback are valuable lowering and validation primitives. They do not constitute transfer. There is no module input, multi-node atomic plan, boundary matching, class translation, or deterministic parameter binding. Outside the narrow sibling case, the architecture still gives an LLM better evidence and hopes it authors the right graph.

This also corrects `add-functionality-architecture.md`. Keep its typed boundaries, parameter policies, authoritative schema use, atomic transaction, and semantic postconditions. Reject its reviewed `capability × family × topology` catalog: that is an enumerated implementation table. The durable abstraction is a corpus-extracted `CapabilityModule`; family is provenance and validation context, never a lookup dimension.

## Milestone recast

### M1: add an effect/interface obligation

Do not put implementation classes or a complete module schema in `EditIntent`. Add a target-derived effect contract: consumed and produced socket types/roles, input→output lineage, cardinality, intended active-path coverage, and whether the effect wraps, replaces, augments, or branches an existing flow. “Transform the active `MODEL` path and return `MODEL` to all targeted samplers” is an intent obligation; “insert `LoraLoaderModelOnly`” is not. This makes the existing compatible-socket and postcondition checks precise without coupling intent to a recipe.

### M2: retain scope

M2 is already the replay-side crux. Its role labeling, type-compatible locus enumeration, branch coverage, and anchor binding should return ranked bindings from module boundary ports to concrete target edges/sockets. That is a clarification of its consumer, not a new milestone.

### M3: capability-module extraction and structuring

Rename m3 from role-preserving evidence to **capability-module extraction**. It should:

- normalize source graphs against authoritative schemas and identify a capability delta;
- segment the delta from the host generation spine;
- retain module-internal topology while replacing concrete node IDs with local keys;
- compute every crossing edge as a typed boundary port;
- extract named parameters and classify them as user-required, asset, derived, portable default, source prior, or decoration;
- retain observed classes, family context, schema hashes, source hashes, method, and confidence as evidence;
- emit a versioned `CapabilityModule`, with `WorkflowSlice` remaining diagnostic substrate;
- accept a module only if the typed cut is complete, its schemas validate, and it can reconstruct its source delta; emit held-out target fixtures for m4 replay.

Extraction must fail closed on entangled or ambiguous deltas. “No module extracted” is better than turning incidental loader, preview, or memory changes into a capability.

### M4: deterministic typed-contract replay

Rename m4 to **capability-module resolution and replay**. Given `EditIntent`, a target graph, and a module, it should:

1. ask m2 for active-path boundary bindings;
2. resolve every abstract internal node to an installed, authoritative schema;
3. bind user parameters, then qualified defaults/priors;
4. preflight all required sockets, literals, assets, packs, coverage, and postconditions;
5. lower the entire module to symbolic `AddNodeOp`/link operations and apply it atomically;
6. validate structural integrity, boundary preservation, active-path contribution, preservation fence, and intent postconditions;
7. try deterministic alternative bindings/resolutions, using an LLM only to resolve genuine semantic ambiguity.

`apply_resolve_add.py` and `apply_mutate.py` are the right substrate: they already canonicalize named fields, consult schemas, check socket compatibility, order inputs by schema, and mint links deterministically. Module preflight must be stricter than interactive editing: its currently non-fatal missing-required-input warnings become fatal before an atomic replay. Sibling splice becomes an optimization, not m4's center.

## Segmentation: differential first, structural confirmation

The corpus supports differential extraction as a controlled bootstrap, not as the general answer:

- Official `ready_templates/sources/official/video/wan_t2v.json` → `wan_i2v.json` has seven stable spine nodes and a clean conditioning/latent-producer replacement.
- `ready_templates/image/z_image.py` → `z_image_img2img.py` preserves the loader/conditioning/model/sampler/decode spine and replaces the empty latent with load→scale→encode. It is semantically clean despite flat-versus-subgraph representation noise.
- `ltx2_3_lightricks_first_last_parity.py` → `ltx2_3_lightricks_first_last_two_stage_lowvram.py`, corroborated by the raw single/two-stage LTX sources with 20 stable node/class anchors, exposes refinement/upscale. The diff is contaminated by loader, attention, resize, and decode changes, so it needs structural pruning.
- Wan 2.2 5B I2V → I2V ControlNet has 11 stable spine nodes and a visible ControlNet chain, but also changes input modality plumbing, text encoding, and assets. The T2V/I2V ControlNet pair preserves 20 ControlNet/spine nodes and proves module invariance, but does not isolate ControlNet itself.
- Runexx first/last → first/middle/last has 124 stable anchors, yet Set/Get and calculator plumbing make the raw delta noisy.

There is no clean same-family ±LoRA pair. LoRA is usually baked into model setup or distillation. Basic image/video upscale templates are clean standalone exemplars, not add/no-add counterfactuals. Flux base/distilled is a useful negative control: near-identical topology and changed model parameters do not imply a transferable capability.

The first extractor should align by stable identity where available, then by class plus typed neighborhood; factor the common active output-producing spine; take connected delta closures between divergence and rejoin points; compute the typed cut; and reject decorations, dormant branches, and unrelated infrastructure changes. Structural checks must prove a coherent cut, dominance/rejoin behavior, active-path membership, and source reconstruction.

Pure structural spine segmentation is not viable first: articulation, reachability, dominators, and typed endomorphisms can find plausible regions but cannot name why a region exists or distinguish capability from infrastructure. Use it to confirm differentials now and as a later fallback, augmented by repeated-subgraph mining across many workflows.

## The keystone representation

A module contract should contain:

```yaml
identity: {module_id, version, free_text_effect}
provenance:
  {source_workflows, extraction_method, source_family_context,
   schema_hashes, confidence}
interface:
  ports:
    - {key, direction: consume|produce, normalized_type, observed_raw_type,
       required, arity, active_path, role_constraints, continuity_group,
       attaches_to: {node_key, socket_name, socket_index}}
  splice: {mode: wrap_edge|replace_producer|augment_input|side_branch,
           coverage, bypass_policy}
graph:
  nodes:
    - {local_key, observed_class, inferred_role,
       required_input_signatures, required_output_signatures,
       literal_field_constraints, parameter_bindings}
  internal_edges: [{from_key, from_port, to_key, to_port, socket_type}]
parameters:
  - {key, target: {node_key, field_name}, value_type, domain,
     required, binding_precedence,
     default_or_prior, provenance, asset_requirement}
postconditions:
  {boundary_lineage, targeted_consumers, reachability, forbidden_bypass,
   preservation_scope}
```

Socket names and source classes are evidence, not identity. The replay key is direction + normalized type + arity + active-path/role constraints + continuity. A continuity group expresses, for example, that a consumed `MODEL` must emerge as the transformed `MODEL`; type equality alone cannot express that. Module descriptors may remain corpus-derived free text for retrieval—no hand-built capability taxonomy is required—while the structural contract is authoritative for execution.

## Family translation and its reliability ceiling

Replay should prefer the observed class when it is installed and schema-valid. Otherwise enumerate authoritative registry schemas and strictly unify each abstract node's required input/output signature, literal-slot types/domains, and required-input completeness. Rank survivors using corpus-derived evidence: observed substitutions, neighborhood similarity, category/description, target-family co-occurrence, pack availability, and socket-name agreement. Mine raw-type compatibility/equivalence from actual corpus connections and adapters; do not encode feature/family pairs.

Only a unique high-confidence resolution may auto-replay. Unknown or wildcard types must not count as translation proof: the current permissive `socket_types_compatible` is suitable for allowing a link, not proving semantic equivalence. Exact or unusually shaped signatures can be reliable. Common `MODEL→MODEL`, `LATENT→LATENT`, and `IMAGE→IMAGE` endomorphisms are inherently ambiguous; schemas describe ABI, not behavior. For these, cross-family translation remains reviewable or `translation_unresolved` until repeated corpus evidence or runtime traces disambiguate it. General means one mechanism with honest refusal, not universal success.

## Epic sequence, realistic boundary, and anti-gaming

Keep four milestones. Amend m1, leave m2, make m3's gates extraction→typed-cut completeness→structuring→source reconstruction plus held-out fixture emission, and make m4's gates exact-class replay→unique schema-signature translation→atomic lowering→held-out transfer→semantic-active validation. Use Wan, Z-Image, LTX, ControlNet, and LoRA only as acceptance and negative cases. Do not define build scope as a list of family-feature pairs.

The hardest part is not emission; it is isolating the causal capability region and resolving behaviorally equivalent classes from schemas that expose only types. A realistic epic promise is high-confidence module extraction, exact/uniquely-resolved replay, deterministic refusal on ambiguity, and structural/task-tier verdicts with honest `runtime_unverified`—not arbitrary cross-family transfer.

The existing anti-gaming rules survive unchanged: public corpus values remain labelled priors, hidden goldens never enter extraction or replay, exact restore stays a regression, and evaluation is effect-based. The new slip risk is a “capability library” quietly becoming a golden-derived recipe catalog: source IDs/literals or benchmark-specific family keys can masquerade as general modules. Prevent that with provenance, train/evaluation source separation, ID abstraction, parameter classification, held-out replay, alternative-valid-construction grading, and an explicit ban on extracting from the benchmark's withheld twin.
