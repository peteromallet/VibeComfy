# Template Porting Workbench

For a first import, start with [`vibecomfy import`](../guides/workflow-onboarding.md): it accepts a local JSON file or one Hivemind reference, creates an editable workflow folder, and shows the next commands. This workbench covers expert promotion and diagnosis of missing custom nodes, schema errors, model asset problems, helper nodes, or positional `widget_N` ambiguity.

The steady-state output should be Python: an editable scratchpad or a ready-template candidate. Raw JSON is source material, not the long-term authoring surface.

The converter writes atomically: emitted text goes to a temp file in the target directory, is re-validated and parity-checked, then replaced via `Path.replace()` only when all gates pass. Failed conversions leave pre-existing files byte-for-byte unchanged. Templates marked `# vibecomfy: manual` on their first line are never overwritten.

## Quick Start

```bash
vibecomfy import <workflow.json-or-hivemind-reference>
python -m vibecomfy.cli validate workflows/<id> --json
python -m vibecomfy.cli doctor workflows/<id> --json
python -m vibecomfy.cli templates create workflows/<id> --id <kind>/<name> --out ready_templates/<kind>/<name>.py --json
python -m vibecomfy.cli port inventory --ready --json
```

The imported bundle is the editable scratchpad. Diagnose it with the normal
validation commands:

```bash
python -m vibecomfy.cli validate <workflow> --json
python -m vibecomfy.cli doctor <workflow> --json
```

Use `<workflow>` as an imported bundle, Python workflow, or ready id. `validate`
and `doctor` are offline by default and cheap enough to run before every manual
template edit and before every RunPod validation attempt.

There is one promotion path for durable templates: Hivemind or local source ->
`vibecomfy import` -> inspect/edit/validate/doctor ->
`templates create --id <kind>/<name>` or
hand-authored Python -> static index refresh -> local validation and
strict-ready gates. Raw JSON is retained as source evidence; compiled API JSON
is runtime output, not the template source of truth.

## When To Use Each Command

| Need | Command |
| --- | --- |
| Import local JSON or one Hivemind revision into a local editable folder | `vibecomfy import <workflow.json-or-hivemind-reference>` |
| Validate an imported workflow before editing or RunPod | `python -m vibecomfy.cli validate <workflow> --json` |
| Diagnose runtime readiness and suggested fixes | `python -m vibecomfy.cli doctor <workflow> --json` |
| Produce a ready-template candidate | `python -m vibecomfy.cli templates create <workflow> --id <kind>/<name> --out ready_templates/<kind>/<name>.py --json` |
| Validate an authored scratchpad or ready template | `python -m vibecomfy.cli validate <scratchpad-or-template.py>` |
| Diagnose runtime readiness and suggested fixes | `python -m vibecomfy.cli doctor <workflow>` |
| See custom-node packs to install | `python -m vibecomfy.cli nodes install-plan <workflow>` |
| Reconcile and fetch final runtime model assets | `python -m vibecomfy.cli run <workflow> --runtime embedded` |
| Fetch authored model asset metadata only | `python -m vibecomfy.cli fetch <workflow>` |
| Check model URLs without downloading bodies | `python -m vibecomfy.cli doctor <workflow> --json` |

Model URL and asset diagnostics belong to `doctor` and `fetch`; keep normal
`run`, `doctor`, `validate`, and `fetch` behavior offline unless you
intentionally stage or inspect remote assets.

Embedded `run` reconciles model assets by default. It inspects the final built workflow after scratchpad patches, resolves model-picker values such as `ckpt_name`, `vae_name`, `unet_name`, and `lora_name` through authored `model_assets` and `vibecomfy/registry/models.yaml`, downloads/stages resolved files, and fails before queueing if a referenced asset cannot be resolved. Use `--no-ensure-models` only for compile-only work where downloads are intentionally disabled.

## Validation and diagnosis

`validate --json` returns a stable structural report. `doctor --json` adds
runtime readiness, custom-node, model-asset, provenance, and recommendation
details.

Together they catch failure classes that previously surfaced only after import
or on a GPU:

- helper and UI-only nodes such as `Note`, `MarkdownNote`, `SetNode`, and `GetNode`;
- unresolved helper broadcasts before compile can silently drop them;
- missing real runtime class types and matching node-pack suggestions;
- unknown classes, missing required inputs, invalid link shapes, and schema type mismatches;
- filename-only or missing model asset URLs;
- duplicate model URL targets and opt-in HEAD failures such as 404 or license-gated responses;
- unresolved positional `widget_N` aliases using widget-only schemas so link-only sockets do not shift widget positions.

Helper/UI classes are never treated as installable missing packs. They produce helper diagnostics. Real unresolved runtime classes remain hard porting errors.

## Template promotion

The imported bundle is the editable scratchpad. Once it has been reviewed and
validated, promote it explicitly:

```bash
python -m vibecomfy.cli templates create workflows/example --id image/example \
  --out ready_templates/image/example.py \
  --json
```

`templates create` validates the canonical bundle and writes only the ready
template Python/companion pair. Ready-template output uses the v2.6
context-bound form:

```python
def build():
    with new_workflow(READY_METADATA, source_path=__file__) as wf:
        model = UNETLoader(unet_name=MODELS["main"])
        SaveImage(images=model, filename_prefix="image/example")
        return wf.finalize(PUBLIC_INPUTS, output_node="9", output_type="SaveImage")
```

Generated wrappers also accept the older explicit workflow form, such as
`UNETLoader(wf, unet_name=...)`, but checked-in ready templates are expected to
use the zero-positional context form.

Ready-template candidates also run strict-ready validation with the target `ready_id` context before writing. Unexcepted strict-ready errors stop replacement before the target path is touched; JSON output includes `conversion.validation.strict_ready_ok`, `conversion.validation.strict_ready_diagnostics`, and top-level strict-ready fields for automation.

### Dry-Run

Use `--dry-run` to inspect promotion output without touching the filesystem:

```bash
python -m vibecomfy.cli templates create workflows/example --id image/example \
  --out ready_templates/image/example.py \
  --dry-run --json
```

### Manual Template Refusal

Templates whose first line contains `# vibecomfy: manual` will not be overwritten.
This is a hard gate evaluated before emission work. To regenerate a manual template,
remove the marker or use a different output path. The repository-wide v2.6 migration
used the explicit `tools.convert_ready_templates --all --write --include-manual`
override to include formerly manual templates once; normal conversions still refuse
manual markers by default.

### Port Inventory

```bash
python -m vibecomfy.cli port inventory --ready --json
```

The inventory reports readability issues across all checked-in `ready_templates/**/*.py`
files: positional `.out(<int>)` calls, `widget_N` field references, UUID class types,
local `_node` helper copies, missing output contracts, marker classification, coverage-tier
joins, and source-provenance flags. It never consults plugin, cwd-extra, or user-global
paths. The JSON output is deterministic and versioned.

`workflows list --ready --json` is intentionally cheaper than inventory and template loading. When `template_index.json` exists, it returns static repo rows from that index and does not load dynamic plugin/user template roots. Add `--include-dynamic` only for discovery sessions that need plugin/user rows; those rows are marked `source_scope: "dynamic"` and `indexed: false`.

## From JSON To Checked-In Python

Use this path for workflows that should become reusable templates:

1. Keep the raw JSON in `ready_templates/sources/.../<id>.json` when it is useful source material.
2. Import the source with `vibecomfy import <json>` and resolve diagnostics with `validate` and `doctor`.
3. Edit the generated Python bundle while investigating the graph.
4. Run `templates create workflows/<id> --id <kind>/<id> --out ready_templates/<kind>/<id>.py` or hand-author the ready template when the workflow becomes reusable.
5. Add or update the `ready_templates/sources/manifests/coverage.json` row with `id`, `path`, `media`, `task`, `coverage_tier`, and `ready_template: true`.
6. Refresh the static discovery index:

```bash
python -m tools.refresh_template_index
python -m tools.refresh_template_index --check
```

Then validate the Python template:

```bash
python -m vibecomfy.cli validate ready_templates/<kind>/<id>.py
python -m vibecomfy.cli doctor ready_templates/<kind>/<id>.py --json
python -m pytest -q tests/test_ready_templates.py tests/test_runpod_matrix.py tests/test_cli_misc.py tests/test_cli_sources_workflows_nodes.py
```

For `coverage_tier: required` or app-active templates, strict-ready gates prohibit missing `with new_workflow(...) as wf:` blocks, explicit `Wrapper(wf, ...)` calls in ready-template builds, wrapper-eligible `node(wf, ...)` calls, schema-default kwargs, single-output `_outputs=` or named `.out("NAME")`, legacy ready-template helper imports, missing custom-node pack provenance commits, hidden schema-backed widgets, missing or broken public input targets, missing or unnamed public outputs, hidden model filenames, and opaque UUID component classes. If a violation cannot be fixed in the same change, document an exact exception with owner, ticket, final category, expiration, and removal condition before relying on it.

Editing internals of a Python template does not require a manifest or index
change unless its identity, category, task, coverage tier, custom-node
requirements, model requirements, or reusable capability changes. Adding,
renaming, or removing a ready template must update `coverage.json` and
`template_index.json`; `tools.refresh_template_index --check` catches drift.

## Live Validation Loop

Run this order while porting:

1. `vibecomfy validate <workflow> --json`
2. `nodes install-plan <workflow>` when unresolved runtime classes appear
3. `fetch <workflow>` when declared models are missing
4. Edit the canonical `workflow.py` produced by import.
5. `validate <workflow> --json`
6. `doctor <workflow> --json`
7. focused RunPod validation only after local checks report no hard errors

The RunPod corpus matrix writes validation and diagnosis reports next to
existing logs so GPU failures can be traced back to cheap local checks. Those
reports are advisory artifacts; they do not make network checks mandatory.

## Battle Targets

Use a small source workflow first to verify the path quickly, then run the current production-parity target:

```bash
python -m vibecomfy.cli validate image/z_image --json
python -m vibecomfy.cli validate video/wanvideo_wrapper_22_wan_animate_preprocess_kijai --json
```

Use `fetch` only when you specifically need authored model asset metadata or
staging diagnostics.

## Roadmap

The first useful slice is intentionally pragmatic: source loading, helper
stripping, custom-node pack inference, model asset analysis, widget alias
diagnostics, Python emission, CLI preflights, doctor guidance, and RunPod
report artifacts.

Remaining work belongs in later batches:

- broaden CLI and parity tests across simple and WanAnimate paths;
- expand docs and agent guidance as new failure modes land;
- keep improving schema/object-info coverage for custom nodes;
- promote recurring RunPod failures into deterministic local checks where possible.

## Emit a UI view / round-trip

`port export --to ui` emits a litegraph-compatible UI JSON envelope from a Python workflow. It preserves positions and furniture by default: when a prior UI JSON or layout-store sidecar exists, matched nodes keep their exact positions, and groups/notes/reroutes/bypass/subgraphs are carried forward. Pass `--fresh` to skip preservation and re-layout from scratch.

When `--out` is omitted, the canonical export also refreshes the layout sidecar next to the loaded Python source. An explicit `--out` writes only that UI artifact by default; pass `--persist-sidecar` when an explicitly targeted export is intentionally authorized to update the source sidecar.

The identity scheme uses the `vibecomfy_uid` stamped in each node's `properties` plus the layout-store sidecar. A node whose uid appears in both the prior store and the current IR keeps its prior position byte-for-byte. New nodes receive engine-placed positions via the M4 layout engine.

Furniture coverage: groups, notes (via `extra.notes`), reroutes, GetNode/SetNode broadcast pairs, bypass edges, and subgraph inner-node definitions are all preserved through the sidecar envelope and re-emitted in the UI JSON.

Gate guarantees: the offline gate (wiring + object_info) catches structural problems; the ComfyUI/RunPod gate validates editor-faithfulness by round-tripping the emitted UI JSON through the installed ComfyUI converter. When the converter produces a byte-different result, the refusal-spine raises `RefusedEmit` and the CLI prints the diff to stderr (exit code 3).

Caveats: the round-trip depends on uid stability. If a node's uid changes between emits (e.g., after a hand-edit that regenerated the graph), its prior position is lost and the node receives a new engine-placed position.

## Canonical loop and conflict-merge

The round-trip operates in three states:

1. **In-sync.** The prior UI JSON and the Python IR agree — all uids present in one are present in the other. Positions are preserved exactly.
2. **Python-ahead.** The Python IR has nodes the UI JSON does not (new nodes added via `wf.node(...)` or `wf.add_node(...)`). New nodes receive auto-placed positions; existing nodes keep their positions. The change report lists them under `new_auto_placed`.
3. **Editor-ahead (REFUSE).** The prior UI JSON has nodes the Python IR does not (someone edited in ComfyUI after the last `port export`). VibeComfy refuses with:

  ```
  port export refused: editor is ahead — N node(s) exist in the prior UI JSON but not in the Python IR: uid=<uid> class=<class>[, uid=<uid> class=<class>]. Re-run `vibecomfy import <prior.json>` to import them, or pass --force-drop to discard explicitly.
  ```

The canonical loop:

```
editor .json → vibecomfy import → Python bundle → edit structure → port export --to ui → editor
```

The K3 plane-separation rule: the editor owns layout (positions, groups, notes, reroutes); Python owns structure (nodes, edges, widgets). The round-trip preserves layout plane data across structure edits and re-lays out cleanly when no prior layout exists.

Divergence rules: when a uid is present in the prior store but absent from the IR, VibeComfy checks whether the uid was authored by a prior VibeComfy emit (via the breadcrumb `extra.vibecomfy.prior_path`). If yes, the node was deleted in Python — it appears in the change report's `removed` list. If no (the prior_path differs or is absent), the node is conservatively treated as editor-added, and `EditorAheadError` is raised.

Two escape hatches for the editor-ahead state:
- `vibecomfy import <prior.json>` — import the editor-only nodes into a canonical bundle, then re-export.
- `--force-drop` — explicitly discard the editor-only nodes and proceed with emission. The dropped nodes appear in the change report's `removed_named` list with their class types.

## Covered vs deferred (v1)

**Covered:**
- `.json` ↔ Python round-trip with positions and furniture preserved.
- Widget and wiring edits keep positions for unchanged nodes.
- New nodes receive auto-placed, non-colliding positions.
- JSON-only collaboration: export UI JSON, edit in ComfyUI, re-import.
- Fresh layout for authored code that has no prior UI JSON.

**Deferred:**
- PNG-embedded workflows (the image carries its own JSON; extraction is not yet wired).
- Simultaneous conflicting edits beyond the three documented states (in-sync, Python-ahead, editor-ahead).
- Workflows hand-edited outside ComfyUI that stripped the `vibecomfy_uid` from `properties` — M5 legacy-hash matching provides best-effort recovery only.

## Virtual wires

The importer resolves GetNode/SetNode/Reroute helpers into the canonical bundle
and preserves editor furniture in the `.vibe.json` companion. Use `port export`
when you need to inspect or re-emit the UI representation.

## Loud preserve

Every `port export --to ui` prints a change summary to stderr:

```
[change-report]
  content: preserved=5 edited=2 new=1 removed=1 virtual_wires_degraded=0
  removed_named: 1 entry/ies
    uid=6 class=CLIPTextEncode
  stripped_helpers: 3
```

- **preserved** — uids that existed before and still exist, with byte-identical positions.
- **edited** — uids that existed before but whose fields changed (widget values, edges).
- **new-auto-placed** — uids that are new in this emit (engine-placed).
- **removed** — uids present before but absent now.
- **removed_named** — per-removed-uid breakdown with `class_type`.
- **stripped_helpers** — count of virtual-wire helper nodes (GetNode/SetNode/Reroute) stripped during emission.

Pass `--dry-run` to preview the report and position deltas without writing any files. The CLI prints `[dry-run] would write to <path>` to stderr and exits 0 on clean success.
