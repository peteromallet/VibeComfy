# General add-functionality architecture

## Position

Build a **hybrid of retrieval, compiled capability recipes, and a deterministic adaptive constructor**. The runtime source of truth should be the compiled recipe, not a retrieved workflow and not an LLM-authored graph. Retrieval is valuable for discovering candidate implementations and showing the planner relevant evidence; corpus mining is valuable for proposing reusable fragments. Neither is reliable enough to decide capability boundaries, compatibility, or placement by itself.

The central product abstraction is not “restore a node” and not even “insert a subgraph.” It is:

`user intent + target workflow facts + available assets` → `family-specific capability variant` → `bound construction plan` → `atomic validated candidate`.

The LLM should classify the request, extract user parameters, and resolve genuinely semantic ambiguity. It should never author positional widget vectors, socket indexes, or a multi-turn construction. This corrects the conclusion of `splice-primitive-bet-assessment.md`: exact-history splice remains a useful restoration feature, but it is not the architecture for novel additions.

## The catalog should contain capability variants, not node aliases

A top-level **capability** is a semantic contract such as `apply_lora`, `two_pass_refinement`, `post_upscale`, or `pose_guidance`. Each capability has one or more reviewed **variants** selected by model family, backend, graph shape, installed packs, and asset availability. The executable unit is therefore “capability × family × topology,” not “class + defaults.”

Each variant should declare:

- an identity, version, user-facing parameters, and effect contract;
- applicability predicates: media/model family, task mode, required installed classes/packs, compatible schema or pack versions, and forbidden combinations;
- a role-labelled fragment: new nodes, named literal fields, typed internal edges, and semantic roles rather than source node IDs;
- boundary ports and anchor predicates, such as `active_model_before_sampler`, `first_pass_latent`, or `final_images_before_save`;
- an edit policy: insert, branch, replace an edge, or wrap an active path;
- parameter policies distinguishing required user assets, derived values, portable safe defaults, and example-only values that must never be copied;
- postconditions proving that the constructed branch is active and reaches the requested output;
- evidence: supporting template IDs/source paths, source slice hashes, pack commits, class-schema hashes, and validation status.

This representation preserves distinctions the corpus proves are real. `LoraLoaderModelOnly` wraps a model path in Qwen/LTX-style graphs; `WanVideoLoraSelect` can feed `WanVideoModelLoader.lora`; newer WanVideoWrapper graphs use `WanVideoLoraSelectMulti` plus `WanVideoSetLoRAs`. LTX IC-LoRA is a larger guide-conditioning capability, not another spelling of LoRA. Likewise, LTX two-stage refinement is a chain containing latent separation, model upscaling, reconditioning, and a second sampler, whereas native Wan 2.2 high/low sampling uses paired models and a split schedule. A class-name synonym table would encode false equivalences.

The existing search corpus is the retrieval seed: `SearchEntry` already carries model families and adaptation-pattern tags, and the provenance sliver can recover named values and local edges. `WorkflowSlice` is a useful extraction record. The current `creative.py` feature rules are only candidate generators: “refinement” matches almost any sampler, “upscale” also catches input normalization, and “audio” collapses muxing, latent conditioning, concatenation, and joint generation.

## Mine proposals; promote recipes

Mining should be an offline compiler with review, not an unattended production learner.

First normalize every ready template and its source workflow through authoritative schemas. Then identify candidate capability regions using metadata, search aliases, class/category signals, asset references, and typed dataflow. Prefer **differential mining** within a family: compare a base workflow with a LoRA/control/two-stage sibling, factor their common host skeleton, and treat the graph delta as a recipe proposal. Extract the bounded subgraph, both sides of each boundary edge, named fields, socket types, pack provenance, and asset requirements. The shipped slice extraction is a substrate, but its edge record needs both endpoint roles/slots and link type rather than only a local socket and peer class.

Next classify each literal as user input, asset reference, derived value, portable default, or source-specific decoration. Prompts, seeds, preview state, absolute paths, and example filenames are not defaults. Validate the proposal by reconstructing the capability in held-out compatible workflows and by checking its semantic postconditions. A human should approve the initial variants because the 64-template corpus has excellent implementation evidence but insufficient labels for reliably inferring intent boundaries.

Recipes stay correct through fingerprints and continuous revalidation. A recipe records the source template hash, expected pack/version or commit, and schema hashes, but the current authoritative provider governs field names, ordering, defaults, and socket compatibility. CI should re-resolve every class and named field, materialize the recipe against fixtures, and quarantine it on drift. On-demand schema resolution can help migrate a recipe; a provisional or remotely discovered schema is authoring evidence, not proof that the node is installed and runnable.

## Constructor and integration point

Add a native capability-planning layer above the edit primitives, for example under `vibecomfy/porting/edit/construct.py` with catalog/matching code in `vibecomfy/capabilities/`. Do not put capability knowledge into `emit/ui.py`, per-class imperative handlers, or prompt text.

The path should be:

1. Detect the target workflow’s family and active output-producing paths.
2. Retrieve applicable recipe variants and reject incompatible or unavailable ones.
3. Bind recipe roles to concrete target nodes/edges using typed sockets, reachability, stage position, task mode, and uniqueness—not first same-class match.
4. Bind user values and assets; use a recipe default only where its policy permits.
5. Preflight every class, named field, required input, link type, asset, pack, and postcondition.
6. Lower the bound plan to ordinary edit operations with symbolic fresh-node handles.
7. Execute on a private ledger and publish only after all structural, queue, capability, and runtime gates pass.

`apply_resolve_add.py` should remain the authority for aliases, named literal validation, and socket compatibility. `apply_mutate.py` should remain deterministic node/link materialization. `emit/ui.py::materialize_litegraph_node` should serialize from the authoritative schema; it should not choose functionality. The constructor eliminates model-authored `widget_N` values before they exist.

The current batch REPL demonstrates rollback and fresh graph-name binding, but the product API should not generate synthetic Python to exploit it. Introduce symbolic handles such as `new:refiner` and a native transaction executor that preallocates or resolves identities while applying ordered operations. This is required for edges between multiple new nodes and outgoing rewires. The transaction should retain ordinary landed operations and receipts for auditability, but a late link or postcondition failure must discard the whole candidate. The existing `PrecedentAdaptationPlan` can inform a new `BoundCapabilityPlan`; its current first-slice/first-role matching and whole-source copying are not safe runtime planning.

The hardest problem is **semantic anchor binding**. Named fields solve ABI correctness, not deciding which model branch, sampler stage, latent, conditioning path, or output the user meant. A wrong branch can be schema-valid, runnable, and visibly different. The planner must fail closed or ask one focused question when active-path evidence does not produce a unique binding.

## Grading without a golden twin

Replace the additive witness with a three-layer capability contract:

1. **Runnable:** UI and schema validation, UI→IR→API conversion, required-input and queue checks, installed pack/model/asset checks, and a bounded real execution producing the expected artifact.
2. **Semantically active:** recipe-specific graph invariants. A LoRA must apply the requested available asset at a valid strength to the model/CLIP path consumed by an output-producing sampler. A refinement pass must consume the first pass, use a valid later-stage schedule, and feed decode/save. Dead parallel branches fail.
3. **Intended effect:** execution traces prove the capability nodes ran and causally contributed to the delivered artifact. Objective requests also get artifact checks. Subjective claims such as “better quality” require held-out multimodal scoring and ultimately blind human preference; output difference alone is not success.

Report the layers separately. The benchmark should start from workflows that never contained the feature, use held-out user requests/assets, and grade against expert-authored semantic rubrics that permit multiple valid implementations. Include negative cases for missing assets, unsupported families, ambiguous branches, and incompatible packs. Keep the restore campaign as a construction regression, not a product-quality headline.

## MVP, sequence, and estimate

A credible first vertical is:

- LoRA for Qwen/native model-only, LTX 2.3 model-only, and WanVideoWrapper;
- two-stage refinement for LTX 2.3 initially;
- Wan high/low refinement only after the paired-model and schedule contract is explicit.

Do not include generic “audio” yet; the corpus already contains at least four different intents that need separate product language.

Sequence the work as catalog schema plus differential extractor; native symbolic transaction executor; LoRA variants with asset preflight; LTX refinement with active-path binding; then semantic predicates, real execution fixtures, drift CI, and held-out evaluation. For one senior engineer this is **5–7 weeks**, including adversarial and live-family validation. A LoRA-only two-family slice could land in roughly 2–3 weeks, but should not be presented as general add-functionality.

## Anti-gaming and product risk

Public templates, schema metadata, pack registries, and installed-asset inventories are legitimate product knowledge. Hidden campaign goldens, removed-node loci, expected widget lengths, and test-specific filenames/classes are not. Recipes must be source-provenanced and capability-general; evaluators must accept alternative implementations satisfying the same semantic contract.

Asset values come only from the user, an explicit available inventory, or a declared downloadable requirement. Missing assets produce an honest blocked/needs-asset result, never an invented filename. A constructor must not silently substitute a different capability merely because it can make a runnable graph.

The largest slip risk is optimizing for “valid graph changed” instead of “requested effect is active on the intended path.” The architecture should make semantic postconditions and causal runtime evidence first-class; otherwise the catalog merely industrializes plausible-looking wrong edits.
