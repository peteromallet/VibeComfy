# Canonical source cleanliness direction

Status: direction adopted; implementation and validation are active.

Current authorization: **delivery approved**, per the user's latest instruction
on 2026-09-11 to refine and execute the existing plan end to end. Dispatch
implementation and required product validation under the active Megado run.
Earlier preparation-only statements are historical and do not override this
authorization.

This document is the current amendment to the unified plan. Its custody-v2
requirements supersede older embedded-custody allowances in the tasklist and
acceptance ledger. Existing I1–I10 IDs and review history remain in force;
historical passing implementation evidence does not certify this amendment.

Date: 2026-09-11

Project: VibeComfy

## Decision

The canonical user-facing artifact is exactly one readable generated Python
workflow and one generalized sibling JSON bundle:

```text
workflow.py
workflow.vibe.json
```

Do not introduce a `vibe.py` workflow wrapper, rename every workflow to
`vibe.py`, or add another executable sibling. Astra reviewed that question at
medium effort and recommended no `vibe.py`: the existing owners already cover
workflow construction, finalization, bundle loading, and registry discovery.
Another executable layer would complicate source authority, restricted loading,
copy-to-recipe behavior, and the one-Python contract without improving clarity.

The user's explicit cleanliness requirement supersedes the earlier advisory to
keep custody embedded in Python.

The existing `.layout.json` remains a separate legacy/layout-store format. It is
not a canonical dependency and must not carry executable custody.

## North Star

Generated Python is the human editing surface. It should read like an ordinary,
well-structured Python workflow:

- readable constants and public inputs;
- explicit typed constructors and output handles;
- direct handle-based connections;
- concise, understandable finalization;
- no hidden serialized workflow behind the readable calls.

The partner JSON is machine-readable custody and presentation data. It may be
large, but it must be closed, deterministic, inspectable, and incapable of
overriding the Python workflow's runtime values or topology.

The reconstructed `VibeWorkflow` remains the semantic authority consumed by the
shared editing kernel and existing execution transports. The bundle is a source
container, not an execution registry.

## Authority split

### Python owns

- runtime constructor values, including prompts, model names, seeds, masks,
  durations, and other editable controls;
- semantic topology and handle connections;
- public input declarations;
- readable `READY_METADATA` capability, template identity, model assets,
  requirements, and provenance declarations;
- meaningful variants and other graph-level semantic declarations;
- the final output declaration.

The intended tail is approximately:

```python
def build() -> VibeWorkflow:
    wf = new_workflow(READY_METADATA, source_path=__file__)

    # readable constructors and handle connections

    savevideo = SaveVideo(
        filename_prefix="video/MiniMax_H3",
        format="auto",
        codec="auto",
        video=lanpaint_avdecode.out(0),
    )

    wf.strict_types = False
    return wf.finalize(PUBLIC_INPUT_METADATA, output_node=savevideo)
```

The exact emitted source may retain other real semantic declarations when a
workflow requires them, but it must not contain custody or replay machinery.

### JSON owns

The generalized `.vibe.json` v2 bundle owns two strictly separated sections:

1. `custody`: non-derivable identity, native schema, provenance, channel, slot,
   and helper facts required to reconstruct the Python workflow faithfully.
2. `presentation`: the existing layout/canvas/groups/node-decoration/link
   data used to materialize the UI projection.

The JSON must not contain runtime values, an alternative executable graph,
topology/edge arrays used as semantic authority, whole-node snapshots, raw UI
payloads, encoded replay instructions, or a duplicate `READY_METADATA` object.

### What can disappear

- `CANONICAL_CUSTODY` and `HELPER_CUSTODY` declarations from generated Python;
- the long `canonical_bindings` dictionary, replaced by validated build-local
  binding discovery;
- duplicated `canonical_requirements`, with requirements normalized through
  `READY_METADATA`;
- `canonical_outputs` where `output_node=savevideo` or verified terminal
  declarations preserve the exact output contract; autodetection is permitted
  only when the source output contract is unspecified, never for explicit
  no-output or ordered multi-output declarations;
- any custody field that can be safely derived from the constructors and the
  pinned schema without weakening identity or fail-closed behavior.

Helper custody is removed from Python, not discarded. Non-derivable helper
identity/provenance remains in the JSON; helper records never instantiate nodes
or restore topology.

## Proposed JSON v2 shape

The exact schema is to be implemented as a closed versioned contract within the
existing `WorkflowBundle` owner. The intended shape is:

```json
{
  "format_version": 2,
  "bind": {
    "workflow_identity": "MiniMax_H3_AV_EncodeDecode_Inpaint",
    "generation_id": "...",
    "custody_digest": "..."
  },
  "custody": {
    "scopes": [
      {
        "scope_path": "",
        "nodes": [
          {"label": "resolutionselector", "id": "...", "class_type": "ResolutionSelector"},
          {"label": "savevideo", "id": "...", "class_type": "SaveVideo"}
        ],
        "helpers": []
      }
    ]
  },
  "presentation": {
    "nodes": {},
    "links": [],
    "groups": [],
    "canvas": {}
  }
}
```

This is a structural example, not a complete valid H3 manifest; required custody
fields are omitted for illustration. S90 replaces the earlier separate node map
and construction-order list with one ordered sequence of labelled records.

Closed-schema rules:

- reject unsupported versions, unknown keys, duplicate JSON keys, invalid
  identities, non-finite numbers, and malformed nested values;
- store each scope's construction order once, as the node-record sequence;
  derive transient label lookup maps internally and reject duplicate labels;
- require complete, unique, scope-local node binding coverage;
- add the scope-local `label` and retain allowed node custody fields: `id`, `uid`, `class_type`,
  `native_ports`, restricted `metadata`, `widget_channels`,
  `none_input_fields`, `none_widget_fields`, `output_slot_names`, and optional
  `construction_output_names`;
- restrict native port carriers to the existing seven fields and validate their
  lengths, nullability, and slot references;
- restrict helper records to identity plus optional provenance/native ports;
- keep presentation foreign keys and class witnesses closed and validated;
- never let presentation or custody create semantic edges or overwrite Python
  constructor values.

`READY_METADATA` carries a small typed bundle marker with format/version,
deterministic pair-generation identity and custody digest. It remains a readable
contract, not a container for the manifest itself.

## Loading, editing, and publication

`new_workflow()` must obtain and validate the companion custody capsule before
the first constructor runs. The generated Python should not contain JSON
parsing, private loader wrappers, custody variables, or binding dictionaries.

The loader should:

1. resolve the sibling `.vibe.json` using the source path and bundle authority;
2. validate the v2 envelope, pair-generation match and custody digest;
3. seed the existing construction-time custody mechanism;
4. let normal constructors remain the sole runtime/value authority;
5. resolve labels to live build-local objects during finalization;
6. apply identity/schema/helper custody atomically;
7. revalidate semantic, presentation, provenance, and revision evidence.

Compare supported construction shape directly against the ordered custody
records: scope paths, labels, classes, order and relevant schema witnesses.
Validate complete one-to-one coverage and scoped identity against actual
constructed objects. Do not persist a separate `structure_digest`. Support the
emitter's constructor, handle-alias/output-unpacking and nested-definition
patterns, including repeated instances and agreed source edits; do not infer
arbitrary Python or rely only on outer-build locals.

Compatibility excludes prompt/model/seed/mask/duration values, formatting and
comments, so valid value edits remain loadable with unchanged JSON. Unsupported
structural changes refuse with a regeneration diagnostic. Retain custody
integrity and deterministic pair-generation identity: equal custody alone cannot
detect swapped companions from different publications. Generation identifies a
publication, not a hash comparison against current editable Python bytes. Derive
it deterministically from publication content excluding its own marker fields;
do not use random IDs or timestamps. Accepted runtime and presentation edits
update existing revision evidence without breaking construction compatibility.

Python, custody, and presentation data must be staged and validated together
before publication. Missing, malformed, stale, or mixed-generation companions
must fail closed and leave existing destinations unchanged. Existing revision
and approval protections remain in force; the custody digest participates in
revision identity where custody itself changes.

`copy-to-recipe` must copy and associate both members of the canonical pair.
Registry discovery and restricted loading must resolve the pair through the same
bundle owner.

The required-companion rule applies to Python declaring the v2 bundle contract.
Keep existing legacy reading behavior explicit; an unmarked legacy Python file
does not acquire a new required companion merely by being opened. Emit v2 for
the new canonical surface. This is a version check in the existing owner, not
a migration service. JSON export's optional `.layout.json` persistence remains
a separate contract from canonical Python pair publication.

Presentation link records may reference and decorate Python-derived edges;
they must never recreate an absent semantic edge. Reject invalid references.
Two filesystem replacements are recoverable pair publication, not a simultaneous
transaction: validate the staged pair, reject mixed generations during reads,
and roll back replacement failures. Exercise the interleaving explicitly.

## Whole-file cleanliness contract

Cleanliness applies to the complete generated file, not just `build()` or the
visible constructor region. The checker must inspect module declarations,
constants, metadata, nested callable definitions, graph-level declarations, and
the final tail.

It must reject:

- custody payloads under any variable name, including renamed or disguised
  dictionaries;
- `CANONICAL_CUSTODY`, `HELPER_CUSTODY`, and giant `canonical_*` finalizer
  arguments in generated workflows;
- importer-shaped `_id`, `_uid`, `_native_ports`, raw ID links, or `wf.connect`
  in ordinary generated calls;
- whole graph snapshots, raw UI payloads, encoded/parsed graph substitutes,
  inline JSON loaders, and post-construction replay assignments;
- duplicate runtime values where a later metadata/custody expression can
  overwrite the constructor authority;
- extra executable workflow siblings such as a generated `vibe.py` wrapper.

It must allow:

- explicit imports from the existing API;
- readable constants and public metadata;
- meaningful constructor values and handle expressions;
- necessary nested definitions;
- concise output/finalization declarations;
- unavoidable long literal tokens, provided surrounding syntax is formatted
  clearly.

Use the active emitter's formatting conventions: its current multiline-call
heuristic is 88 characters or more than three kwargs, its long-line diagnostic
threshold is 120, and metadata currently uses `pprint` width 110. There is no
repository-wide Black/Ruff formatter contract. Extend the existing formatting
helpers across declarations and the finalizer; do not add a formatter dependency
on an assumed policy. Permit unavoidable long literal tokens while wrapping
surrounding syntax. Do not impose a total file byte or line limit. Inspect
declaration contents, not merely variable names.

## Required evidence

Apply the contract to the actual H3 artifact and representative flat,
unknown-schema, multi-output, and depth-two nested workflows.

### Source and manifest

- generated Python contains no custody declarations or giant finalizer;
- partner JSON is deterministic and closed-schema valid;
- repeated regeneration produces byte-identical Python/JSON for unchanged input;
- the pair loads through registry, direct bundle, restricted loader, and
  copy-to-recipe paths.

### Fidelity and editing

- unchanged reconstruction preserves semantic IR, API and GraphBuilder parity,
  IDs/UIDs, native ports, provenance, public inputs, outputs, helpers, and
  presentation;
- H3 prompt, seed, model, mask, duration, and audio interval edits survive
  rebuild without custody regeneration;
- nested-scope bindings preserve interfaces, fanout, output slots, and sibling
  identities;
- custody mismatch, missing sidecar, malformed JSON, invalid binding, and
  mixed-generation pair are rejected before replacement;
- old approvals/revisions are rejected after an accepted semantic or custody
  change.

### Cleanliness checker robustness

Mutation cases must include renamed custody variables, hidden module-level
payloads, nested-definition replay, duplicated runtime values, a giant
finalizer, and a sibling executable wrapper. The checker must fail each case for
the right structural reason rather than relying on a name-only heuristic.

## Implementation batches

1. **Bundle v2 boundary**

   Add the closed parser, custody projection, preconstruction loading, scope
   binding, digest rules, and atomic pair publication within `WorkflowBundle`.
   Keep `.layout.json` separate and preserve the shared editing/runtime owners.

2. **Clean emitter and finalizer**

   Stop emitting custody/helper literals and canonical binding maps. Consolidate
   requirements into `READY_METADATA`, replace output metadata with the concise
   output declaration after exact parity proof, and keep all runtime values in
   constructors.

3. **Whole-file acceptance tests**

   Replace tests that require embedded custody with v2 pair tests. Add AST,
   declaration-content, formatting, duplicate-authority, nested-definition,
   malformed-pair, rollback, and editable-value regression coverage.

4. **H3 regeneration and full validation**

   Regenerate the exact H3 Python/JSON pair, inspect both artifacts, record
   hashes and semantic/identity evidence, run the configured focused checks,
   then run the complete suite on the final candidate.

## Markdown notes

Astra's adjudication is to keep ordinary `Note`, `MarkdownNote`, and
`Label (rgthree)` content in typed `presentation.annotations` in the partner
JSON. Notes are preservation data, not executable custody and not workflow
semantic metadata. Preserve authored Markdown, whitespace, Unicode, and empty
strings exactly once in explicit content fields; do not hide note text in
arbitrary widget snapshots.

The classification is role-based rather than class-name-based. Text consumed
by a runtime node remains an ordinary readable Python constant/constructor
value with an explicit graph connection. A UI-only class must not conceal a
live dependency; an unsupported connected-note case must be diagnosed.
Workflow requirements, capability declarations, and trusted provenance remain
in Python `READY_METADATA`. Imported attribution prose remains an annotation
with literal content. Defer generalized document/reference machinery and inferred
metadata links; matching prose must never be inferred as a reference.

Annotations need stable, scope-qualified identity and explicit attachment to a
workflow, subgraph definition, instance, node, or group. Definition notes and
instance notes must remain distinct through expansion. Geometry remains layout
data, but `.layout.json` must not become the owner of note content. Presentation
edits should change presentation/bundle revision evidence without changing
runtime semantics or structural compatibility.

The current sidecar allowlist and capture path do not yet carry note content,
so existing UI-only-node preservation is not proof of exact note round-trip.
The v2 implementation must add annotation content and test import → bundle →
UI, edit → save → reload, nested-scope isolation, exact identity/text
preservation, deterministic regeneration, malformed-reference refusal, and
semantic invariance under presentation-only edits.

## Validation phase

The plan includes a named validation phase before completion. It is part of the
implementation acceptance contract, not an additional review process:

1. **Corpus preflight:** classify each source as supported conversion or
   intentional refusal; validate shape/schema, primitive types, link endpoints,
   native recursive boundaries, output arity, virtual-wire ports, and note role.
2. **Conversion/atomicity:** convert the representative corpus and require
   positive Python/partner-JSON pairs, stable structured diagnostics for
   negative cases, no partial writes, and byte-identical regeneration.
3. **Artifact cleanliness:** inspect whole-file Python and closed-schema JSON;
   reject embedded custody/helper payloads, duplicated runtime values, and
   implicit note metadata. Verify typed presentation annotations and exact note
   content/identity.
4. **Semantic/identity/parity:** compare topology, interfaces, IDs/UIDs,
   native ports, helpers, provenance, widgets, model assets, and output slots.
   Primitive coercion, recursive boundaries, unknown endpoints, virtual-wire
   mismatches, parity drift, and unknown workflow shapes each need a named
   regression fixture.
5. **Editing/regeneration:** edit runtime controls and notes, save/reload/export,
   and regenerate. Presentation-only edits must not alter execution semantics;
   valid drafts must not require custody regeneration.
6. **CLI/SDK/canvas gate:** exercise the same pair through all three ingestion
   surfaces, including nested note scope and malformed-input refusal. Exit only
   with required positives passing, intentional refusals proven, affected tests
   green, and the broad suite run once on the integrated candidate.

The 20-workflow diagnostic corpus and its raw receipts are recorded in
`evidence/workflow-conversion-corpus-20260911-20/`. It is baseline evidence for
the validation design, not a claim that the not-yet-implemented custody-v2
cleanliness contract already passes.

## Corpus adjudication

Astra reviewed the complete 20-case receipt set. The ruling is to retain the
external-custody direction and extend the existing plan, not add a new
architecture. Cases 12, 19, and 20 are definite fidelity defects to fix:
preserve switch-value absence/channel semantics, authored model-path strings
and proven output arity, and the missing `VHS_VideoCombine.audio` edge.
Cases 01, 16, 17, and 18 require source-versus-importer tracing before deciding
between a fix and intentional refusal. Cases 02, 11, 13, 14, and 15 are valid
refusals under the explicit-boundary policy unless supported boundary
counterparts are added. Case 10 is a malformed-shape negative and does not
prove depth-two support.

The detailed corpus table, failure taxonomy, regression matrix, minimum
20/20 acceptance rule, and Astra decision receipt are in
`evidence/workflow-conversion-corpus-20260911-20/README.md`.

## Astra follow-up: finalization, widget names, and annotations

Astra reviewed Cases 07 and 08 and confirmed that the architecture is settled;
the remaining work is implementation and evidence. External `.vibe.json` v2
custody, preconstruction loading, concise finalization, and typed presentation
annotations are already the adopted solutions. The current large finalizers
prove that those solutions are still pending, not that another executable layer
is needed.

For the common single-output case, emit only:

```python
wf = wf.finalize(PUBLIC_INPUT_METADATA, output_node=savevideo)
return wf
```

The finalizer contract must also represent explicit zero-output and ordered
multi-output workflows with a small typed declaration of live handles when
needed. It must preserve output order, slots, names, and kinds, and distinguish
explicit no-output from unspecified/autodetected output. It must not contain
custody, binding maps, duplicated requirements, loader machinery, or serialized
output records. In particular, do not silently replace Case 07's explicit
`canonical_outputs=[]` with terminal autodetection.

### Widget-name resolution policy

Existing capability correction from the registry/source investigation:
automatic discovery and backend schema extraction already exist. Reuse
`vibecomfy/registry/pack_resolver.py`,
`vibecomfy/schema/on_demand.py:185` and
`vibecomfy/schema/extract.py`. The on-demand provider resolves a package,
acquires its source with pin/cache checks, uses static source parsing and can
optionally call runtime `INPUT_TYPES()` in a subprocess. Shared extraction also
has an optional embedded-Comfy rung. Do not build another registry investigator.
Existing `tests/test_pack_resolver.py`, `tests/test_on_demand_resolver.py` and
`tests/test_extract_embedded.py` cover these mechanisms; this inspection did
not execute them or invoke discovery/downloads.

The narrower remaining question is whether the discovered backend schema and
its provenance establish each serialized compact-widget position, including
frontend-added controls. Backend field order alone does not prove that mapping.
Reuse the existing compact resolver and evidence hierarchy documented in
`docs/failure-analysis/widget_name_resolution_design.md:252`; test the wiring
and provenance through canonical conversion before proposing additional code.

The current provider split is concrete: `AuthoringSchemaProvider` includes
on-demand resolution by default unless disabled (`schema/provider.py:1028`),
whereas ordinary `port convert` constructs the intentionally offline
`ConversionSchemaProvider` (`commands/port/_shared.py:246`,
`schema/provider.py:1055`). That provider has local/index/cache/source/widget
and optional runtime sources, but no on-demand rung. Reuse an explicit bounded
schema-resolution/preflight step before freezing the conversion snapshot, then
consume its pinned evidence through the existing deterministic provider. Do
not blindly replace the conversion provider with the authoring provider or
introduce ambient network resolution during rebuilds.

Prepare a fixture-backed regression in which a missing local class is found by
the existing resolver, its source schema is captured with provenance, and the
canonical conversion receives proven field names; repeat with resolution
disabled/unavailable and with ambiguous frontend positions. Verify that later
rebuilds do not fetch or change the frozen mapping. Case 07 records an empty
schema provider and confidence 0.0 for relevant unresolved nodes; that proves
missing evidence in that conversion, not that the investigator is absent or
that invoking it would necessarily resolve every IAMCCS widget. No live
registry availability or successful IAMCCS source extraction was tested here.

Case 07's `IAMCCS_*` nodes provide useful evidence (`aux_id`, pinned `ver`,
`Node name for S&R`, and `ue_properties.widget_ue_connectable`), but matching
counts or JSON dictionary order does not prove positional serialization order.
The local object-info cache has no entries for the three named IAMCCS classes.

Resolve each serialized widget position only through a proven mapping:

1. Accept explicit source position/name evidence only when its serialization
   contract is known and validated.
2. Otherwise consult object-info/schema data for the exact pack, class, and
   pinned revision, including frontend-added controls, linked-widget behavior,
   optional fields, and dynamic widgets.
3. If necessary, inspect the exact pinned custom-node backend/frontend source;
   a latest registry entry, generated stub, cache filename, or similarly named
   class is insufficient provenance.
4. Treat UE keys as candidates/corroboration unless a verified producer-version
   contract proves their order and completeness. Conflicts must not be guessed.
5. Record pack/revision, schema/source digest, serialization contract,
   per-position mapping, and resolution reason in the existing evidence/custody
   projection, then freeze that resolution for rebuilds and edits.

Use categorical confidence: `proven`, `unresolved`, or `conflicting`. Emit real
field names for proven positions. Retain `widget_N` only where the position and
channel remain exactly preservable, with a concise contextual explanation. If
ambiguity prevents faithful reconstruction, refuse. Never infer names from
values or silently reorder/compact linked channels. Dropping a proven mapping
is an importer defect; retaining `widget_N` despite a proven mapping is an
emitter readability defect; a lossless unresolved position is a valid fallback.

### UI-only calls, notes, and helpers

Ordinary `Note`, `MarkdownNote`, and UI-only `Label (rgthree)` nodes belong in
typed `presentation.annotations` in the partner JSON. Case 07's label titles
and Case 08's six note bodies must be preserved exactly with stable
scope-qualified identity, attachment, and typed style/layout fields. JSON is
the sole authored-content owner. Python may contain a short locator comment,
but must not duplicate full note bodies or parse comments back into annotations.

A class with proven runtime behavior, or text consumed by a runtime node, remains
an explicit Python constructor and connection. Connected UI-only cases must be
diagnosed rather than dropped. Reroutes and helpers use the same role analysis:
semantic connectivity stays in Python handles; non-derivable helper identity and
schema stay in custody; visual routing stays in presentation. Neither section
may recreate semantic edges.

### Required regressions

The validation phase must add whole-file AST/content/format checks for disguised
custody, replay, duplicate runtime authority, giant finalizers, UI-only raw
calls, and executable siblings. Widget fixtures must cover pinned-schema
success, explicit source ordering, UE-only ambiguity, conflicting or
version-mismatched schemas, duplicate/partial names, unavailable schemas, and
dynamic/frontend controls. Reordering UE object keys must not change assignments;
linked widgets, null versus absent values, and serialized positions must survive
import/edit/reload/export without channel shifts.

Case 07 must preserve all fifteen label titles, and Case 08 all six note bodies,
including Markdown, whitespace, Unicode, empty strings, style, and nested
definition/instance attachments. Presentation-only edits must leave semantic IR,
API/GraphBuilder output, runtime values, topology, and structural compatibility
unchanged while updating presentation/revision evidence. The 20-case corpus,
prior failure conditions, deterministic regeneration, atomic refusal, H3 edits,
and CLI/SDK/canvas parity remain required. No additional review process or
XHARD assignment is warranted by this decision.

## Code-owner audit and implementation seams — 2026-09-11

Four Luna medium explorers inspected the major areas, then a second wave traced
specific gaps and corrected preliminary claims. This was factual plan discovery;
no product tests or completion reviews were run. Source was
`c43e870d6c15ac9a31c0141d3212ae3a032d86ac`, including this untracked direction
document and the existing untracked corpus evidence. Product source was clean.
Detailed findings and their dispositions are in the historical run receipt
`/Users/hannahomalley/Documents/Codex/2026-09-08/goal-continue-the-existing-megado-plan/VibeComfy-integrity/.otto/runs/unified-workflow-integrity-20260909/receipts/canonical-cleanliness-luna-audit-20260911.md` (artifact unavailable in this checkout).
The prepared Megado brief
`/Users/hannahomalley/Documents/Codex/2026-09-08/goal-continue-the-existing-megado-plan/VibeComfy-integrity/.otto/runs/unified-workflow-integrity-20260909/briefs/canonical-cleanliness-prepared.md` (artifact unavailable in this checkout)
records the latest delivery authority, source custody, task routes,
estimate and review-history constraints.

The implementation must use these existing owners. File references are relative
to the repository and refer to the inspected candidate, not future line numbers.

| Element | Existing owner / evidence | Required amendment and proof |
| --- | --- | --- |
| Import and native boundaries | `ingest/normalize.py:2344` (`from_ui`); `ingest/native_subgraph.py:125`; `porting/workbench.py:717`; `commands/port/_convert.py:93` | Keep source admission and supported native expansion here; compare actual entrypoints with the same positive and malformed fixtures. Unsupported native encodings and supported nested IR are distinct coverage cases. |
| Python emission | `porting/emit/entrypoints.py:34`; `porting/emit/emit_ready.py:833,966`; `porting/emit/emit_kwargs.py:978` | Use the shared prepared execution projection and constructor emitter. Remove custody/finalizer clutter here; do not introduce a second pretty emitter or restore values later. |
| Widget names and channels | `porting/widgets/compact_resolver.py:150`; `porting/widgets/aliases.py:48` | Extend the existing resolution result with proven/unresolved/conflicting evidence. Freeze positions, names and channels for canonical reconstruction. In current code an all-positional frozen table falls through to ambient providers; v2 must preserve an explicitly frozen unresolved result. Test identical rebuilds with providers changed or unavailable. |
| Capsule and pair validation | `workflow_bundle.py:124,1391,1693`; `templates.py:263` | Validate the closed v2 capsule before constructors, seed the existing construction context, and check ordered scoped binding coverage. Current loading executes Python before reading v1 presentation. |
| Final outputs and requirements | `templates.py:1187,1251,1296`; `workflow.py:992`; `porting/emit/emit_ready.py:1306,2505` | Preserve exact outputs through concise declarations, including explicit empty versus unspecified and null fields. Test workflow output declarations separately from a node's output ports/tuple unpacking. Normalize requirements once through existing ready metadata without replaying stale model values. |
| Annotations | `workflow_bundle.py:724,1940`; `porting/emit/ui.py:4623`; `porting/emit/emit_constants.py:105` | Extend capture, closed validation and materialization together. Current field copying omits note bodies. Apply the settled role policy before dropping UI-only nodes; test connected text and exact scoped annotations. |
| Publication and revisions | `workflow_bundle.py:1541,1834`; `tests/test_workflow_bundle.py:735,1072` | Add custody to revision identity and validate the actual staged pair. Reuse rollback injection tests; add mixed-generation reader refusal and unchanged destination bytes on failure. |
| Loader consumers | `scratchpad_loader.py:110`; `porting/convert.py:948`; `registry/ready.py:249`; `commands/copy_to_recipe.py:34` | Thread logical source identity and verified companion through conversion, restricted loading, registry, workbench and copying. Current conversion stages Python alone; copy-to-recipe copies Python alone. |
| Editing and preview | `porting/edit/session.py:197`; `porting/emit/emit_agent_edit.py:29`; `runtime/eval/core.py:26` | Keep retained IR and the shared editing kernel authoritative. Carry pair context only where Python is reconstructed or persisted; an ephemeral in-memory preview does not need file publication. |

Paths in the owner column beginning with `ingest`, `porting`, `templates`,
`workflow`, `scratchpad_loader`, `registry`, `commands`, or `runtime` are under
`vibecomfy/`; test paths are under the repository root.

### Routing: reuse the existing canonical resolver

The canonical path already has the generalization needed here:
`VibeWorkflow._execution_projection()` (`vibecomfy/workflow.py:1656`) delegates
helper lowering through `_resolve_projection_helpers()` to
`vibecomfy/_compile/_resolve.py:47`. It owns reroutes/passthroughs, scoped Set/Get
broadcasts and value primitives, including invalid literal, cycle, ambiguous
and unresolved-source diagnostics. API and GraphBuilder consume the same
execution projection. Canonical virtual-wire legs have a separate existing
owner at `workflow.py:3592`; native UI boundary expansion belongs to ingestion.
Do not combine these distinct representations into a new routing framework.

`porting/reorganise/graph_facts.py:1075` and `porting/emit/ui.py:3538` compute
presentation-specific effective topology. Their duplicate-looking logic is not
proof that canonical Python bypasses the resolver. Preserve authored helper
display where intended. Compare effective endpoints, slots, fanout and scoped
diagnostics across execution and flat-display projections; do not demand the
same raw node/edge lists from authored presentation. Consolidate only a
demonstrated divergent rule, through the existing owner.

Test ordinary links, transitive reroutes, Set/Get scope isolation, primitives,
cycles, ambiguous sources, missing sources, native sentinels and virtual-wire
port mismatches with explicit expectations. Case 12 is primarily a value/channel
defect, Case 20 an edge-preservation defect, and Case 18 a virtual-wire/native
roster investigation; a generic route rewrite would not establish any of those
fixes. Supported Python-owned depth-two IR must have a positive fixture separate
from intentionally refused native UI encodings.

### Pair loading across temporary and in-memory source

Use one internal verified load context within the existing bundle/loader path,
carrying logical source identity, v2 status and the selected companion. During
staging, provide the staged companion explicitly: setting `logical_path` alone
could still read the previous destination JSON. A temporary filename must not
select a random or stale sibling. Direct, restricted, registry and workbench
loads consume the same validated capsule. String-based source editing receives
that context without embedding the capsule into generated Python.

Release construction/custody contexts on success and on failures before
finalization, preserving an enclosing context when nested. Test a failed build
followed immediately by a valid build in the same test/context; pytest's global
cleanup between tests must not hide a leak. Test repeated definition instances
and duplicate local labels in different scopes. Scope binding must not depend
on the outer build frame or JSON object key ordering.

Do not add a session-wide custody owner, require persistence for ephemeral
previews, or add a new concurrency subsystem. The configured single-writer
implementation/publication discipline and existing revision protections remain.
Concurrent-writer concerns require a demonstrated in-scope caller before any
locking redesign; reader interleaving and existing rollback behavior are tested
within this amendment.

### Test structure and gap closure

Extend the existing suites with small parameterized fixtures and shared assertion
helpers. Each expectation states the values/types, direct edges and slots,
public outputs, scoped identity and diagnostic that must survive. Do not derive
both expected and actual results from the emitter being tested. Hand-authored
expected API fixtures are useful independent oracles; supplement them with
source-backed identity, native-port and annotation expectations. API/GraphBuilder
agreement and semantic digests are additional evidence, not the sole oracle.

| Layer | Existing suites/helpers to extend | New proof required |
| --- | --- | --- |
| 1. Local contracts | `test_porting_emitter.py`, `test_workflow_bundle.py`, widget resolver tests | Whole-file AST/content/readability mutation tests; closed v2 schema; pinned naming and exact channel positions; explicit zero/single/ordered-multiple outputs; annotation content and references. Test legitimate JSON-valued runtime arguments and long literals as positive controls. |
| 2. Semantic fidelity | `test_template_roundtrip.py` (`_explicit_api_comparison`, class/topology counters), `test_ui_emitter_parity.py`, native-subgraph/H3 tests | Independent expected topology/values/types plus identity and ports. Cases 12/19/20 get minimized regressions and original-corpus checks. Route tests compare effective semantics, without requiring presentation and execution node lists to match. |
| 3. Lifecycle and edits | `test_porting_edit_kernel.py`, `test_porting_edit_revision_lifecycle.py`, `test_porting_edit_recursive.py`, bundle rollback tests | Python/typed parity before refactoring; valid runtime edits with unchanged JSON; presentation-only edits leave semantics unchanged; nested identity and interfaces; stale approvals; malformed/missing/mixed companions; staged-path selection; exception cleanup and unchanged destinations. |
| 4. Real entrypoints | `test_canonical_user_paths.py`, `test_canonical_export_integrity.py`, existing canvas route/browser fixtures | Same supported source and malformed authority/boundary source through actual CLI conversion, public SDK onboarding and canvas capture/materialization. Compare semantics, custody and refusal codes; presentation persistence/report formatting may differ. Keep converter/schema inputs local and pinned. Mocking a converter or session transaction alone does not prove ingress parity. |
| 5. Integrated artifacts | `test_h3_generated_editability.py`, H3 fixture/schema/boundary suites, 20-case corpus | Exact H3 pair and exported graph; real source edits; deterministic pair regeneration; recorded whole-file and graph inspection. All 20 outcomes must match justified expectations, including no partial writes for refusals. Seven prior positive snapshots remain baseline until regenerated as v2. |

Suite names in this table are under `tests/`. Reuse existing browser/canvas
probes when available; do not replace a missing canvas observation with a claim
based on a mocked transport. Missing-model drafts are positive persistence
cases, not malformed-input negatives. The existing local canonical-user-path
test disables the Comfy converter and its canvas test exercises transaction
persistence; retain that useful coverage with its actual scope.

Use table-driven perturbations rather than an unrestricted combinatorial
matrix: reorder JSON object keys; change schema availability; alter one runtime
value; edit one annotation; swap one companion; remove one edge; introduce a
duplicate scoped identity; fail at each existing publication injection seam.
Every perturbation has an explicit expected invariant or refusal. Add one
valid depth-two/repeated-instance fixture in the supported representation;
Case 10's malformed input and unsupported native boundary encodings do not
satisfy that positive case.

Run focused tests as each change lands and rerun the failing test first while
diagnosing, followed by its affected dependency coverage. Use Python 3.11+,
`PYTHONHASHSEED=0`, the configured environment and fixture-backed schemas with
on-demand fetching disabled. Preserve existing plugin configuration and
300/600/900-second check limits and the 1 GiB output ceiling. Reuse the existing
bounded full-suite execution arrangement, recording collection/partition
coverage if necessary; do not silently omit tests to fit a timeout. Run the
configured full offline suite once on the integrated candidate. Any required
failure is fixed and retested; report skips, deselections and expected failures
separately with their reasons. Do not enable live-provider, RunPod or Comfy smoke
opt-ins or infer offline safety from `not gpu` alone.

### Execution order within the existing batches

1. E0/T3: establish minimized fidelity, output, resolver and loader-context
   baselines first, including Python/typed parity. Prepare fixtures in parallel.
2. T1 plus bounded emitter integration: implement the v2 parser, verified load
   context, scope bindings and publication within existing owners; then switch
   the shared emitter/finalizer and its real consumers together. Shared files
   use one writer. Normal work stays Luna medium; preserve the existing Sol E1
   assignment only for its original coupled kernel or a justified hard issue.
3. T1/T2/T3: integrate pinned resolution and annotations, fix the demonstrated
   corpus defects at their actual owner, and run lifecycle/entrypoint tests.
   Route consolidation is conditional on the source-backed owner analysis,
   not a prerequisite invented for every import.
4. E2/T4: regenerate H3 and all corpus expectations, inspect exact artifacts,
   reconcile public docs/help, and run the final integrated checks.

This refines the existing four batches, not a second task system. Local tests
belong with each implementation change, rather than waiting for batch 3.
Remaining uncertainty is concentrated in pinned custom-widget serialization
evidence and source tracing for Cases 01/16/17/18. Give each a bounded fixture
and normal-worker investigation; retain explicit refusal where faithful
reconstruction cannot be established. No plan-only discovery result is a PASS
for the implementation.

## S90 — adopted Astra simplification ruling

Astra high adjudicated the proposals on 2026-09-11. This section and the revised
v2 schema above supersede the earlier map-plus-order and stored-structure-hash
sketches. The decision receipt is historical provenance at
`/Users/hannahomalley/Documents/Codex/2026-09-08/goal-continue-the-existing-megado-plan/VibeComfy-integrity/.otto/runs/unified-workflow-integrity-20260909/receipts/S90-20260911-astra.md` (artifact unavailable in this checkout).
It records the outcome. Preparation remains complete; implementation is NOT RUN.

| Adopted simplification | Required boundary |
| --- | --- |
| Reuse registry/source acquisition in bounded preflight | Capture pinned evidence before freezing; no ambient acquisition on rebuild, no general frontend interpreter, and no guessed widget positions. |
| One ordered labelled custody sequence per scope; no persisted structure hash | Direct shape checks and one-to-one actual-object binding remain mandatory, including nested/repeated instances. Retain custody digest, deterministic generation and existing revision identity. |
| Limit binding discovery to supported emitted patterns | Preserve constructor/handle aliases, output unpacking, nested definitions and agreed edits; outer-build locals alone are insufficient. |
| Bounded whole-file cleanliness acceptance | Check supported emitted syntax and prohibited data roles in every scope. Unknown emitted forms fail acceptance explicitly. Retain mutation and independent fidelity tests; no universal adversarial Python analyzer or second security system. Existing legacy loads and valid edits are not narrowed. |
| Typed records for the three observed annotation kinds | Exact text, supported style, scoped attachments, definition/instance identity and connected-text classification remain required. Defer generalized documents and reference resolution. |
| Fixtures per invariant plus selected interactions | Retain real CLI/SDK/canvas positives/refusals, all 20 corpus outcomes, exact H3 edit/export/inspection and the configured offline suite. Avoid the full Cartesian product. |
| Existing routing, legacy reads and publication owners | No new route framework, migration service, revision ledger, session custody owner or locking redesign. Test actual drift, reader interleaving and rollback. |

Do not simplify by dropping identity/native ports, guessing names, enabling
ambient fallback after freezing, replacing explicit outputs with autodetection,
replaying runtime values/edges from JSON, or substituting mocked transports for
real ingress evidence. Add the same-custody/different-generation swapped-pair
negative alongside incompatible-constructor and reordered-JSON-key fixtures.

These are bounded reductions, not evidence of a literal 90%-benefit/10%-effort
result. Keep the 4–7 focused engineer-day estimate plus 1–2 contingency; fidelity
defects and coupled pair-loading integration still require work. Existing task
IDs and routes remain: E0/T3 baselines; T1 bundle; E1/T1 bounded emitter
integration; T1/T2/T3 resolution/annotations/corpus fixes; E2/T4 final artifacts.
Normal work remains normal; the original Sol E1 hard kernel is not rerun merely
because of this amendment. No new review stage is added.

Return for adjudication only on a concrete required-workflow, valid-edit,
scope-identity or publication counterexample that these boundaries cannot
preserve, or insufficient pinned evidence where lossless fallback is impossible.
Routine implementation choices and prescribed corrections need no reassurance
review. Execution still awaits the user's instruction.

## Workflow path census — prepared cleanup candidates

Three Luna medium explorers traced onboarding, JSON output and publication at
the same source HEAD. Findings and host qualifications are recorded in the historical receipt
`/Users/hannahomalley/Documents/Codex/2026-09-08/goal-continue-the-existing-megado-plan/VibeComfy-integrity/.otto/runs/unified-workflow-integrity-20260909/receipts/workflow-path-census-20260911.md` (artifact unavailable in this checkout).
There is one shared semantic representation and common lower-level owners,
but several orchestration/publication paths. The aim is one owner per invariant,
not one function for every source and output format. This census ran no tests.

| Path seam | Finding and bounded follow-up within existing tasks |
| --- | --- |
| CLI analysis then conversion | `commands/port/_convert.py:64,93` and `porting/workbench.py:105` load the source twice. Prepare a one-admission regression that also asserts report/source identity, then reuse the admitted source/snapshot. Avoid divergent reads or schema observations between reporting and emission. E0/T3 characterization, normal integration. |
| Converter and copy-to-recipe publication | `porting/convert.py:948` and `commands/copy_to_recipe.py:34` publish/copy Python outside the pair owner. Reuse existing `WorkflowBundle` pair validation/publication for v2, including ready-ID loads. Already part of T1/T2; do not create another publisher. |
| CLI UI export versus bundle materialization | `commands/port/_export.py:496` calls the lower-level UI emitter with legacy preservation context; `workflow_bundle.py:1420` uses validated bundle presentation. Test equivalent semantics and refusal under matching authority. Preserve optional legacy layout, draft export and recovery behavior; consolidate only proven drift. T2/T3. |
| Unresolved output handles | `porting/emit/ui.py:1629` ends in a slot-zero fallback; `workflow.py:3382` raises `unknown_output_handle`. Characterize whether the fallback reaches strict/canonical public exports despite upstream checks. Required invariant: no silent rewiring to slot zero. If reproduced, fix the responsible existing owner with a minimized regression. Do not infer a demonstrated public failure from helper source alone. T2/T3. |
| Canvas and SDK admission context | Direct canvas roundtrip, durable ingress, SDK loading and capture reach common normalizers with different wrappers/provider choices. Compare the same supported draft and malformed boundary with one frozen provider; preserve legitimate error/report/provenance adapters. Refactor only an evidenced semantic split. T3. |

API JSON uses `compile("api")`; GraphBuilder shares the execution projection.
ComfyUI canvas JSON uses `emit_ui_json`/bundle materialization and retains
presentation. Compare effective edges, slots, fanout and scope where appropriate,
not raw display node lists. Current `.layout.json` writes are distinct from the
future required `.vibe.json` companion: their separation alone is not proof of
a broken pair transaction. Ephemeral edit previews remain non-authoritative;
accepted edit publication already uses capture/bundle owners.

These are factual cleanup candidates and targeted tests inside the existing
plan, not an added audit/review stage or authorization to implement.

## Adjacent smell triage — bounded within implementation

The owner census is sufficient to prepare implementation. The user subsequently
requested a bounded Luna investigation of the four risks below; that factual
inspection is now part of the authorized delivery work. It does not authorize
another general audit. Distinguish source-backed findings from
untested hypotheses and reuse existing coverage when implementing later.

| Risk worth checking | Smallest useful check / existing task | Stop rule |
| --- | --- | --- |
| Failure quietly becomes success | Exercise malformed schema, unknown output and missing v2 companion through real strict/canonical entrypoints. Check semantic refusal code and unchanged destinations; keep explicit recovery/draft behavior distinct. T2/T3. | Passing public-boundary checks close the issue; do not rewrite every exception handler. |
| Cached or global state leaks between workflows | Load two workflows sequentially in one context, including failed-first/successful-second and repeated class names with distinct pinned evidence. Assert scope/custody/provider isolation and no post-freeze acquisition. T1/T3. | Fix only the owning cache/context if a counterexample is demonstrated; no new cache framework. |
| A read or preview changes the authored workflow | Snapshot input IR and destination bytes before analysis, UI materialization and dry-run; assert they remain unchanged. Reuse existing non-mutation/preview tests. E0/T2/T3. | Ephemeral derived objects are valid; avoid a repository-wide immutability refactor. |
| Runtime edits leave duplicate stale declarations | Change a model/seed/output control and check constructor authority, public defaults, requirements/readiness and revision through reload/export. Exact output nulls and annotations remain separately owned. E1/T1/T3. | Consolidate only duplicated authority demonstrated by the fixture; do not redesign readiness or metadata wholesale. |

Schema acquisition versus conversion, publication versus copying, and direct
versus bundle UI export are already assigned in the current tasklist. They do
not warrant additional investigations under new names. Update docs/help from
the proven implementation in T4 so legacy descriptions do not become a competing
contract. Leave universal schema/frontend interpretation, global API unification,
broad legacy removal and unrelated refactors out of scope. No new model review
or implementation authorization follows from this triage.

## Adjacent-smell investigation outcomes

The requested four-topic Luna inspection is complete at source-inspection level.
Receipt and result custody are recorded in the historical receipt
`/Users/hannahomalley/Documents/Codex/2026-09-08/goal-continue-the-existing-megado-plan/VibeComfy-integrity/.otto/runs/unified-workflow-integrity-20260909/receipts/adjacent-smell-investigation-20260911.md` (artifact unavailable in this checkout).
The metadata agent's result was unavailable after interruption; a bounded host
source trace completed that topic. No product tests or implementation ran.

| Disposition | Prepared action inside existing tasks |
| --- | --- |
| Source-backed failed-build context gap | T1/T3: a build failing before finalization can retain its non-null workflow-context token. Exercise failed-first/successful-second through the actual loader in one test/context, so global test cleanup cannot conceal it. Restore context at the owning boundary while preserving nested-context policy. |
| Source-reachable non-strict UI fallback | T2/T3: unresolved named outputs can reach slot-zero fallback in non-strict UI materialization. Strict schema-less rejection already exists. Test schema-less and sufficiently-schematized unknown names at real UI boundaries; require no silent semantic rewiring. Malformed provider output structure needs its own characterized negative, not an assumption of failure. |
| Unproven class-cache cross-workflow risk | T1/T3: test same class with distinct frozen schema evidence before changing templates' class-keyed carrier caches. Existing object-info witness invalidation and context snapshot restoration remain; no global cache redesign. |
| Duplicate requirement restoration confirmed in source | E1/T1/T3: current finalize derives requirements, then restores saved canonical requirement lists. Verify an edited model in both compiled values and current readiness/requirements; preserve historical provenance separately. This supports already-planned removal of duplicated canonical requirements, not a claim that runtime constructor values are overwritten. |
| Canonical materialization/preview protections found | Reuse existing detached-copy/non-mutation coverage; no preview mutation was established. analysis.trace returns live node objects, but its observed CLI caller only reads them. Dry-run nested fields alias another view in the same detached result. Neither observation alone justifies an API deep-copy refactor; defer absent a mutating consumer or violated contract. |
| Missing v1 sidecar ruled out as a defect | Preserve established optional presentation behavior. Malformed present sidecars already refuse; required v2 companion behavior remains a separate planned contract. |

A source-backed counterexample is ready for a regression test but is not an
executed reproduction. Keep failures/refusals and hypotheses distinct in the
acceptance ledger. No new task family, review stage or general audit is required;
remaining action is the prepared characterization and implementation sequence
once execution is authorized.

## Focused test-signal amendment — adopted 2026-09-11

The [test-signal cleanup plan](test-signal-cleanup-plan.md) integrates six Luna
medium inventories (541 test-bearing files, explicitly mixed inspection depth)
and the single user-authorized Astra high ruling into E0/T1/T2/T3/E1/E2/T4.
Use existing test owners and lanes; prioritize exact source/semantic/identity
expectations and real Comfy Node editing/persistence boundaries. Preserve all
tests until replacements demonstrate the old invariant and unique failures.
No deletion quota, testing framework, new review stage or broad cleanup
prerequisite is added. Deferred tests remain in their existing lanes.

The supplemental plan owns the concrete candidates and retirement mapping,
whole-generated-file checks with legitimate-source positive controls, exact
20-case/H3 validation loop and final configured full-suite obligation. Pair
publication checks require mixed-generation refusal between replacements,
not simultaneous filesystem replacement. Legacy loading, valid drafts,
supported edits, revision and rollback contracts remain unchanged. All new
implementation/validation evidence remains NOT RUN.

## Non-goals

- no `vibe.py` workflow wrapper or filename convention;
- no new editor, normalization framework, or execution transport;
- no second semantic graph representation in JSON;
- no forced GPU/runtime provisioning;
- no production deployment, merge, push, or cutover;
- no extra review process beyond the configured Megado contract.

## Review fixtures

The accompanying `evidence/workflow-review-set-20260911/` directory is a
read-only review corpus generated through the current canonical conversion
path. It intentionally contains ten varied source workflows and generated
Python snapshots for visual/API review. These artifacts are not custody-v2
acceptance evidence: the external partner-JSON boundary described above is
still planned, and current generated Python may contain the legacy embedded
custody representation.

## Astra high rework adjudication — 2026-09-13

The user-authorized Astra-high decision changes the raw-call conclusion for
the inspected H3 artifact. Its five raw calls comprise four LanPaint classes
with pinned, source-backed schemas and one still-unresolved
`MiniMaxH3ImageToVideo`. The LanPaint calls must be routed through the
existing discovery/codegen/registration path so the generated file has
typed constructors and complete custom-node imports. The MiniMax call remains
an allowed fallback only with a durable class/source/reason record; its
signature must not be guessed.

The pinned LanPaint archive is registry `2.1.0`, digest
`c56e8494b3db225817f95ea06de53564721f1ac5376168afb7358e29205e8b5b`, and the
inspected source SHA is
`d9bf9bccbb68ad0504b4be753c4dcb61164b0cf342dc59f1f87f0f0040f80334`.
Evidence covers `LanPaint_SamplerCustomAdvanced`, `LanPaint_AVDecode`,
`LanPaint_AVEncode` and `LanPaint_VideoMaskEditor`; the latter's dynamic
choices remain unresolved unless independently proven by frontend/runtime
evidence.

The existing task IDs absorb this rework: E0/T3 freeze per-class provenance
and backend-versus-frontend widget contracts; E1 reuses wrapper discovery and
codegen to register a bounded `vibecomfy.nodes.lanpaint` module; E1/T1
fixes only demonstrated shared emitter/import/schema seams; T1/T2/T3/E2/T4
regenerate and validate the exact H3 and affected corpus. No runtime wrapper
synthesis, all-pack generation, second emitter, new representation or new
review stage is added.

Finalization remains semantics-aware: use `output_node` only when inferred
metadata is exactly lossless; preserve explicit `OutputSpec` for explicit
null artifact metadata, empty outputs and ordered multi-output declarations.
Closure requires AST proof of typed imports/calls, an exact residual raw-call
allowlist, source/semantic/identity/failure tests, and fresh H3 editing,
save/reload/export, whole-file/graph inspection and deterministic
regeneration. These checks cover the three cleanliness issues together:
custom-node imports, avoidable raw calls, and the closing finalizer form.
