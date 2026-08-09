<!-- Auto-extracted from Codex design/decomposition pass. Source of truth for the additive-splice-pipeline epic. -->

The coherent fix is a typed, evidence-preserving splice pipeline: normalize every retrieved workflow before reasoning about it; extract the smallest inquiry-relevant component; derive typed anchors from its actual cut edges; emit several validated topology manifests; then apply one transactionally. None of these stages should consult fixture ancestry.

## Fix A — source-ingestion normalization

### Evidence: what mangled the samples

- **`quantized_generation_head` (`68920e773786`)**: the selected Flux precedent contains `7b34ab90-…` as a runtime `class_type`, so semantic validation rejects it as unresolved (`cases/68920e773786/attempts/003/research.json:89-109`). In the source it is actually a subgraph instance whose definition lives under `definitions.subgraphs` (`ready_templates/sources/custom_nodes/flux2/flux2_klein_9b_gguf_t2i.json:111,225-228`). The generated recipe proves the hidden topology is a real loader/conditioning/sampler/decode chain (`ready_templates/image/flux2_klein_9b_gguf_t2i.py:16-77`).

- **`source_guided_editing` (`1540f3fa3ba3`)**: attempt 1 represents the entire Qwen edit precedent as one `LoadImage`, points `source_workflow_path` at Python, then reports `source_records_missing` (`cases/1540f3fa3ba3/attempts/001/research.json:67-77,347-357`). The recipe actually contains two edit encoders, VAE encoding, model conditioning, sampling, and decode (`ready_templates/edit/qwen_image_edit.py:22-84`). This collapse is caused by provenance collecting only instances matching one target class (`executor/provenance.py:51-88`), after which `_build_precedent_slices` deliberately creates one-node slices (`executor/research.py:2753-2815`); later, `_selected_source_records` tries to reopen the `.py` path through a JSON-only loader (`research.py:3163-3172`; `ingest/workflow_source.py:78-97`).

- **`second_reference` (`6718878faf57`)**: its strongest source exposes both `7b34ab90-…` and `65c22b29-…` as unresolved classes (`cases/6718878faf57/attempts/001/research.json:207-234`). They are two subgraph definitions, the latter explicitly accepting `reference_image1` and `reference_image2` (`ready_templates/sources/official/edit/flux2_klein_4b_image_edit_base.json:491-494,1949,2029-2041`). The Python materialization exposes the missing second-reference branch: resize → VAE encode → two additional `ReferenceLatent` nodes (`ready_templates/edit/flux2_klein_9b_image_edit_base.py:81-153`).

- **`continuation_assembly` (`1210df57d0c7`)**: attempt 3 reduces the correct Python precedent to singleton `LTXVConcatAVLatent` slices and then cannot JSON-load the Python file (`cases/1210df57d0c7/attempts/003/research.json:41-51,6970-6985`). The recipe contains the exact assembly sought: `AudioConcat`, `ImageBatchExtendWithOverlap`, and `VHS_VideoCombine` (`ready_templates/video/ltx2_3_runexx_video_to_video_extend.py:466-503`). Alternate source slices retain extensive `GetNode`/`SetNode` plumbing (`research.json:576-640`), because the offline converter follows only explicit links and blindly promotes each UI `node.type` into `class_type` (`ingest/normalize.py:115-168`).

- **Additional confirmed casualty: `last_frame_guide`**. Its source reaches validation with a workflow-local UUID plus `GetNode` and `SetNode` among the unresolved classes (`cases/9263e74f689e/attempts/002/research.json:3806-3821`); the source contains the matching subgraph definition and extensive proxy network (`LTX-2.3_Motion_Transfer_DWPose.json:2987,10161-10164`). `reference_motion_guidance` is also proxy-heavy, although its recorded primary failure is topology handoff rather than normalization alone.

### Concrete design

Add `normalize_precedent_source(retrieved: RetrievedPrecedent) -> NormalizedPrecedent` in `vibecomfy/ingest/workflow_source.py`:

```text
NormalizedPrecedent {
  source_ref, source_kind, content_hash, retrieval_rank,
  records: WorkflowNodeRecord[],
  ports: TopologyPort[],
  edges: TypedEdge[],
  origin_by_node_id: {normalized_id: SourceOrigin},
  transforms: NormalizationStep[],
  warnings, completeness
}
```

`WorkflowNodeRecord` must gain named/indexed typed outputs; `TypedEdge` carries both endpoint IDs, socket names/indexes/types, and an evidence reference. `SourceOrigin` preserves the hash plus top-level instance/subgraph/inner-node coordinates.

Normalization proceeds as follows:

1. Decode API, UI JSON, or trusted ready-template Python.
2. Recursively inline `definitions.subgraphs`: namespace inner IDs as `instance:inner`, bind public subgraph inputs/outputs to outer links, rewrite boundary edges, remove the UUID container, and reject cycles or excessive nesting.
3. Resolve `SetNode`/`GetNode` pairs by scoped broadcast key, replace each Get consumer with the Set node’s true upstream typed source, then remove both proxies. Collapse `Reroute` and equivalent one-in/one-out helpers similarly. Ambiguous setters or incompatible wildcard types mark only the dependent region incomplete.
4. For a retrieved, trusted ready-template Python path, load it through the existing ready registry and compile its `VibeWorkflow` to API (`registry/ready.py:113-153`; `workflow.py:738-762`). Never execute arbitrary retrieved Python; untrusted Python is statically lowered in a sandboxed future implementation or returned as `untrusted_python_not_expanded`.
5. Canonicalize class names and run resolver checks only after expansion and proxy collapse. Preserve widget literals in a separate evidence channel, not in topology.

Insert this before slice construction at `research.py:4816-4850`. Replace the provenance singleton topology branch at `research.py:2753-2815`; provenance instances may remain widget-prior evidence only. Cache normalized precedents by content hash, and change `_selected_source_records` (`research.py:3163-3172`) to select from that cache. `_validate_candidate_semantics` then receives clean records instead of rejecting formatting artifacts (`research.py:3451-3461`).

**Production-real:** the only input is the generically retrieved artifact, its format, and hash. There is no breadcrumb lookup, fixture path promotion, or golden comparison.

**Risks:** subgraph boundary formats vary across ComfyUI versions; nested definitions, scoped same-name broadcasts, disabled helpers, unions, and wildcard sockets need corpus-driven tests. Regression tests should compare normalization with the retrieved artifact’s compiled topology, never with repair goldens.

## Fix C — role-bearing cut-edge anchors

### Evidence and insertion point

`WorkflowSlice` currently contains only two anchor node IDs (`contracts.py:876-899`). `_build_precedent_slices` chooses the first and last normalized records (`research.py:2826-2830`), which are merely sorted node IDs (`workflow_source.py:230-255`). `_source_anchor_records` then restricts binding to those nodes, and `_build_anchor_bindings` takes the first target sharing a substring-derived role without testing the actual edge direction or socket type (`research.py:3278-3323`).

That directly explains:

- **`depth_controlnet`**: rank 1 has `WanVideoControlnetLoader`, `MiDaS-DepthMapPreprocessor`, and `WanVideoControlnet`, but anchors nodes `11`/`118`—a text encoder and `INTConstant`—and is rejected as `anchor_binding_missing` (`cases/05d07d0df6b7/attempts/003/research.json:184-257`). The broken graph exposes the useful retained model loader/sampler boundary (`broken/broken.ui.json:245-336`).

- **`camera_reframing`**: the correct candidate contains camera pose, visualizer, and camera-embed nodes but receives numeric-order anchors `11`/`105`; both it and ReCamMaster are rejected (`cases/6d07e584881a/attempts/001/research.json:719-819`). ReCamMaster’s actual boundary is typed: retained `LATENT` feeds the camera component, whose `WANVIDIMAGE_EMBEDS` output feeds the sampler (`wan13b_recammaster.json:1882-1958,2292-2314`). The broken graph already has `WanVideoEncode.samples: LATENT` and `WanVideoSampler.image_embeds: WANVIDIMAGE_EMBEDS` (`broken/broken.ui.json:444-483,925-938`).

Replace `_build_anchor_bindings` after clean records are obtained at `research.py:3924-3957` with:

```text
extract_inquiry_local_segment(source, inquiry, target) -> FocusedSegment
derive_cut_edge_anchors(segment, source, target) -> RoleAnchor[]
```

Seed nodes from inquiry terms and required functional roles. Connect seeds through the shortest typed paths. Stop expansion when an outside source port has a strong equivalent in the broken graph; otherwise absorb that dependency into the segment. For segment node set `S`, every edge with exactly one endpoint in `S` is a cut edge:

- outside → inside becomes an inbound boundary anchor;
- inside → outside becomes an outbound boundary anchor.

Use roles:

- `model_provider`, `model_transform`, `sampler`;
- `conditioning_provider`, `conditioning_transform`;
- `latent_provider`, `latent_transform`;
- `media_input:image|video|audio`;
- `feature_control:depth|pose|reference|camera|lora`;
- `decoder`, `output_sink`, `preview`;
- `utility_proxy`, `annotation`, `unknown`.

Infer roles from authoritative schema and socket types first, then socket names, class metadata/name, and finally neighborhood. Match cut edges globally against broken-graph ports: hard-gate direction, socket compatibility, existence, and input cardinality; then maximum-weight bipartite assignment using approximately 45% socket type, 25% role, 15% socket name, 10% family/media compatibility, and 5% neighborhood/open-input evidence. Unlike today’s first-match choice (`research.py:3304-3307`), this preserves consistency across multiple edges.

When no semantic role is clear, an exact non-wildcard type may become `typed_passthrough:<TYPE>` only if its target match is unique, capped at medium confidence. For wildcard/proxy boundaries, expand outward until a typed boundary appears. Remaining ambiguity emits alternative manifests or an evidence-only rejection.

**Production-real:** matching uses only normalized retrieved topology, the inquiry, runtime schemas, and the current broken graph. IDs never have to correspond across workflows.

**Risks:** dynamic sockets and several same-type samplers require calibrated score margins; complete cut-edge coverage, not merely one bound target, must replace the current weak validation at `research.py:3463-3508`.

## Fix B — topology manifests end-to-end

### Evidence and contract

The handoff is demonstrably lossy. `latent_refinement` produced a 48-node candidate with both validations passing, yet its fingerprint records `candidate_graph_consumption_mode: none` (`cases/bee83462150b/attempts/001/research.json:1859,4276-4277`; `failure_fingerprint.json:3-18`). `accelerated_audio_conditioning` and `subject_isolation` also produced passing candidates (`cases/8c371e7618b1/attempts/002/research.json:36,437-438`; `cases/150502bb7f5c/attempts/002/research.json:169,1796-1797`).

Research presently tries only three slices and stops at the first pass (`research.py:3326-3327,3889-4009`). The fixer prompt explicitly excludes the full graph, summarizes up to twelve raw slices, and truncates required nodes to ten (`edit_research.py:84-93,150-171,210-230`). The batch loop retains class lists for dependency discovery but omits topology from its compact prompt schema (`edit_batch_loop_intro.py:289-307,432-484`).

Add to `executor/contracts.py`:

```text
TopologyManifest {
  manifest_id,
  source {path, content_hash, retrieval_rank, tier},
  nodes [{symbol, canonical_class_type, resolver_status,
          evidence_ref, confidence}],
  internal_edges [{from_symbol, output_socket, to_symbol, input_socket,
                   evidence_ref, confidence}],
  boundary_anchors [{direction, symbol, symbol_socket,
                     broken_graph_node_id, broken_class_type, broken_socket,
                     source_anchor_ref, confidence}],
  inquiry_coverage {required_roles, covered_roles},
  validation {verdict, class_resolution, socket_checks,
              cut_edge_coverage, anchor_binding, reasons},
  confidence
}
TopologyManifestSet {
  target_graph_hash, manifests[1..3], rejections[]
}
```

Build it in `_build_topology_manifest_set` beside/replacing `_build_adaptation_plan` at `research.py:3821-4098`, invoked at `research.py:4865-4870`. Add it to `ResearchResult` beside the structured precedent fields (`contracts.py:1698-1713`).

Evaluate up to twelve ranked, normalized sources until three distinct full-pass manifests exist; emit at most three. Rank by complete role/cut-edge coverage, exact socket matches, resolver strength, retrieval rank, then smaller delta. Deduplicate with a widget-free, ID-free canonical hash over class-colored, port-labeled nodes, internal edges, and boundary role/direction/socket signatures. Merge duplicate evidence; discard supersets whose extra nodes add neither inquiry roles nor boundaries. The twelve-source search limit and score weights need prototype calibration.

“Focused” is now precise: inquiry-role seeds plus minimal connecting paths, stopping at FIX C’s bindable cut edges, after FIX A has removed pseudo-nodes. Existing target-equivalent backbone nodes remain outside the manifest.

### Communication and application

Replace the current raw-slice prose with bounded JSON containing all 1–3 manifests:

> These are ranked, independently sourced candidate topologies, not a prescribed winner. Select the compatible manifest; preserve its nodes, internal edges, and named boundary bindings. Supply only widget values from the user request, schema defaults, or separately qualified source priors. Do not combine manifests unless their roles and target sockets are disjoint and the union revalidates.

Keep excluding the whole `candidate_graph`; a compact set of alternatives preserves the anti-bias intent while retaining actionable evidence. Add `topology_manifests` to the allowlist at `edit_batch_loop_intro.py:289-307`, and derive dependency classes from `nodes[].canonical_class_type`.

`AddNodeOp` is the correct lowering primitive—it mints fresh IDs and UIDs (`porting/edit/apply_mutate.py:219-257`) and validates sockets (`apply_resolve_add.py:212-280`)—but it is not a sufficient fixer-facing interface because manifest symbols do not yet have UIDs and the operation must be atomic. Add internal `EditSession.splice_manifest(manifest_id, widget_values_by_symbol)` / `SpliceManifestRequest`; do not add a seventh persisted canonical op, since the delta contract deliberately has six (`porting/edit/ops.py:58-65`).

On a cloned ledger:

1. Recheck target graph hash and every named broken-node/class/socket anchor.
2. Resolve all classes and validate only the supplied widget values.
3. Add all nodes, capturing fresh UIDs.
4. Resolve manifest symbols and lower every internal and boundary edge to `UpsertLinkOp`.
5. Run full guard and queue validation; commit only if all operations pass.
6. Persist the landed canonical `AddNodeOp`/`UpsertLinkOp` sequence for replay.

A manifest is high-confidence only if every evidence reference matches its source hash, all classes resolve, every internal socket is compatible, every mandatory cut edge uniquely binds, and all required inquiry roles are covered. The fixer chooses the highest-ranked compatible manifest. It may combine only disjoint-role/disjoint-target-input manifests after validating their union. Incomplete manifests stay in `rejections`; stale hashes, missing anchors, unresolved classes, or socket mismatches trigger another generic research pass rather than partial application or invention.

**Production-real:** manifests contain no widget values, filenames, sigma strings, golden types, or fixture metadata. Their topology comes exclusively from generic retrieval evidence and their bindings from the current user graph.

## Composition

```text
generic retrieval
  → FIX A: normalize/in-line/collapse into a typed evidence graph
  → inquiry-local seed and minimal-path extraction
  → FIX C: compute cut edges and role+socket bindings
  → FIX B: validate, rank, dedupe, emit 1–3 focused manifests
  → fixer selects and supplies widget values only
  → transactional manifest splice lowers to canonical edit ops
  → guard/queue validation and commit
```

This turns the repair from “find evidence, then ask the fixer to reinvent it” into “find several defensible structures, prove how each attaches, and let the fixer adapt values.”
