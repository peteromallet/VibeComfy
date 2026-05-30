# Template Porting Workbench

The porting workbench is the first stop when importing or repairing a ComfyUI workflow for VibeComfy. Run it before hand-editing a converted template, before spending RunPod time, and whenever a raw workflow fails with missing custom nodes, schema errors, model asset problems, helper nodes, or positional `widget_N` ambiguity.

The steady-state output should be Python: an editable scratchpad or a ready-template candidate. Raw JSON is source material, not the long-term authoring surface.

The converter writes atomically: emitted text goes to a temp file in the target directory, is re-validated and parity-checked, then replaced via `Path.replace()` only when all gates pass. Failed conversions leave pre-existing files byte-for-byte unchanged. Templates marked `# vibecomfy: manual` on their first line are never overwritten.

## Quick Start

```bash
python -m vibecomfy.cli port check <workflow> --json
python -m vibecomfy.cli port convert <workflow> --out out/scratchpads/<id>.py --json
python -m vibecomfy.cli port convert <workflow> --ready-id <kind>/<name> --out ready_templates/<kind>/<name>.py --json
python -m vibecomfy.cli port inventory --ready --json
```

Use `<workflow>` as a ready id, scratchpad path, raw JSON path, or indexed workflow reference. `port check` is offline by default and cheap enough to run before every manual template edit and before every RunPod validation attempt.

There is one promotion path for durable templates: source workflow -> `port check` -> scratchpad when investigation is needed -> `port convert --ready-id <kind>/<name>` or hand-authored Python -> static index refresh -> local validation and strict-ready gates. Raw JSON is retained as source evidence; compiled API JSON is runtime output, not the template source of truth.

## When To Use Each Command

| Need | Command |
| --- | --- |
| Preflight a source workflow before editing or RunPod | `python -m vibecomfy.cli port check <workflow> --json` |
| Turn raw JSON or an indexed workflow into editable Python | `python -m vibecomfy.cli port convert <workflow> --out out/scratchpads/<id>.py --json` |
| Produce a ready-template candidate | `python -m vibecomfy.cli port convert <workflow> --ready-id <kind>/<name> --out ready_templates/<kind>/<name>.py --json` |
| Validate an authored scratchpad or ready template | `python -m vibecomfy.cli validate <scratchpad-or-template.py>` |
| Diagnose runtime readiness and suggested fixes | `python -m vibecomfy.cli doctor <workflow>` |
| See custom-node packs to install | `python -m vibecomfy.cli nodes install-plan <workflow>` |
| Reconcile and fetch final runtime model assets | `python -m vibecomfy.cli run <workflow> --runtime embedded` |
| Fetch authored model asset metadata only | `python -m vibecomfy.cli fetch <workflow>` |
| Check model URLs without downloading bodies | `python -m vibecomfy.cli port check <workflow> --head-check-models --json` |

`--head-check-models` is opt-in. It performs HEAD requests only, follows redirects, records status codes, and does not download model bodies. Keep normal `run`, `doctor`, `validate`, and `fetch` behavior offline unless you intentionally ask for URL checks.

Embedded `run` reconciles model assets by default. It inspects the final built workflow after scratchpad patches, resolves model-picker values such as `ckpt_name`, `vae_name`, `unet_name`, and `lora_name` through authored `model_assets` and `vibecomfy/registry/models.yaml`, downloads/stages resolved files, and fails before queueing if a referenced asset cannot be resolved. Use `--no-ensure-models` only for compile-only work where downloads are intentionally disabled.

## What `port check` Reports

The report is a stable JSON object with provenance, source hash, workflow shape, node counts, diagnostics, custom-node pack suggestions, model asset candidates, optional URL check results, artifacts, and recommendations.

It catches the failure classes that previously surfaced only after conversion or on a GPU:

- helper and UI-only nodes such as `Note`, `MarkdownNote`, `SetNode`, and `GetNode`;
- unresolved helper broadcasts before compile can silently drop them;
- missing real runtime class types and matching node-pack suggestions;
- unknown classes, missing required inputs, invalid link shapes, and schema type mismatches;
- filename-only or missing model asset URLs;
- duplicate model URL targets and opt-in HEAD failures such as 404 or license-gated responses;
- unresolved positional `widget_N` aliases using widget-only schemas so link-only sockets do not shift widget positions.

Helper/UI classes are never treated as installable missing packs. They produce helper diagnostics. Real unresolved runtime classes remain hard porting errors.

## Convert Modes

Scratchpad mode is the default and is the right choice while investigating a workflow:

```bash
python -m vibecomfy.cli port convert workflow_corpus/community/example.json \
  --out out/scratchpads/example.py \
  --json
```

Ready-template mode is explicit because it creates a curated candidate with template identity:

```bash
python -m vibecomfy.cli port convert workflow_corpus/community/example.json \
  --ready-id image/example \
  --out ready_templates/image/example.py \
  --json
```

The converter validates emitted Python by importing the module, calling `build()`, compiling API output, and running schema validation when a provider is available. Ready-template output uses the v2.6 context-bound form:

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

### Dry-Run And Diff Modes

Use `--dry-run` to inspect conversion output and parity evidence without touching the filesystem:

```bash
python -m vibecomfy.cli port convert workflow_corpus/community/example.json \
  --out out/scratchpads/example.py \
  --dry-run --json
```

Use `--diff` to get a unified diff and JSON diff metadata alongside the write:

```bash
python -m vibecomfy.cli port convert workflow_corpus/community/example.json \
  --out out/scratchpads/example.py \
  --diff --json
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

1. Keep the raw JSON in `workflow_corpus/.../<id>.json` when it is useful source material.
2. Run `port check <json> --json` and resolve hard diagnostics before conversion.
3. Convert to an editable scratchpad first when the graph needs investigation.
4. Convert with `--ready-id <kind>/<id>` or hand-author `ready_templates/<kind>/<id>.py` when the workflow becomes reusable.
5. Add or update the `workflow_corpus/manifests/coverage.json` row with `id`, `path`, `media`, `task`, `coverage_tier`, and `ready_template: true`.
6. Refresh the static discovery index:

```bash
python -m tools.refresh_template_index
python -m tools.refresh_template_index --check
```

Then validate the Python template:

```bash
python -m vibecomfy.cli validate ready_templates/<kind>/<id>.py
python -m vibecomfy.cli port check ready_templates/<kind>/<id>.py --strict-ready-template --json
python -m pytest -q tests/test_ready_templates.py tests/test_runpod_matrix.py tests/test_cli.py
```

For `coverage_tier: required` or app-active templates, strict-ready gates prohibit missing `with new_workflow(...) as wf:` blocks, explicit `Wrapper(wf, ...)` calls in ready-template builds, wrapper-eligible `node(wf, ...)` calls, schema-default kwargs, single-output `_outputs=` or named `.out("NAME")`, legacy ready-template helper imports, missing custom-node pack provenance commits, hidden schema-backed widgets, missing or broken public input targets, missing or unnamed public outputs, hidden model filenames, and opaque UUID component classes. If a violation cannot be fixed in the same change, document an exact exception with owner, ticket, final category, expiration, and removal condition before relying on it.

Editing internals of a Python template does not require a manifest or index
change unless its identity, category, task, coverage tier, custom-node
requirements, model requirements, or reusable capability changes. Adding,
renaming, or removing a ready template must update `coverage.json` and
`template_index.json`; `tools.refresh_template_index --check` catches drift.

## Live Validation Loop

Run this order while porting:

1. `port check <workflow> --json`
2. `nodes install-plan <workflow>` when unresolved runtime classes appear
3. `fetch <workflow>` when declared models are missing
4. `port convert <workflow> --out out/scratchpads/<id>.py --json`
5. `validate out/scratchpads/<id>.py`
6. `doctor out/scratchpads/<id>.py`
7. focused RunPod validation only after the local report has no hard porting errors

The RunPod corpus matrix writes an offline port report and a port-convert preview next to existing logs so GPU failures can be traced back to cheap local preflight results. Those reports are advisory artifacts; they do not make network checks mandatory.

## Battle Targets

Use a small source workflow first to verify the path quickly, then run the current production-parity target:

```bash
python -m vibecomfy.cli port check image/z_image --json
python -m vibecomfy.cli port check video/wanvideo_wrapper_22_wan_animate_preprocess_kijai --json
```

Add `--head-check-models` only when you specifically need URL reachability diagnostics.

## Roadmap

The first useful slice is intentionally pragmatic: source loading, helper stripping, custom-node pack inference, model asset analysis, opt-in URL HEAD checks, widget alias diagnostics, Python emission, CLI preflights, doctor guidance, and RunPod report artifacts.

Remaining work belongs in later batches:

- broaden CLI and parity tests across simple and WanAnimate paths;
- expand docs and agent guidance as new failure modes land;
- keep improving schema/object-info coverage for custom nodes;
- promote recurring RunPod failures into deterministic local checks where possible.

## Emit a UI view / round-trip

`port export --to ui` emits a litegraph-compatible UI JSON envelope from a Python workflow. It preserves positions and furniture by default: when a prior UI JSON or layout-store sidecar exists, matched nodes keep their exact positions, and groups/notes/reroutes/bypass/subgraphs are carried forward. Pass `--fresh` to skip preservation and re-layout from scratch.

The identity scheme uses the `vibecomfy_uid` stamped in each node's `properties` plus the layout-store sidecar. A node whose uid appears in both the prior store and the current IR keeps its prior position byte-for-byte. New nodes receive engine-placed positions via the M4 layout engine.

Furniture coverage: groups, notes (via `extra.notes`), reroutes, GetNode/SetNode broadcast pairs, bypass edges, and subgraph inner-node definitions are all preserved through the sidecar envelope and re-emitted in the UI JSON.

Gate guarantees: the offline gate (wiring + object_info) catches structural problems; the ComfyUI/RunPod gate validates editor-faithfulness by round-tripping the emitted UI JSON through the vendored ComfyUI converter. When the converter produces a byte-different result, the refusal-spine raises `RefusedEmit` and the CLI prints the diff to stderr (exit code 3).

Caveats: the round-trip depends on uid stability. If a node's uid changes between emits (e.g., after a hand-edit that regenerated the graph), its prior position is lost and the node receives a new engine-placed position.

## Canonical loop and conflict-merge

The round-trip operates in three states:

1. **In-sync.** The prior UI JSON and the Python IR agree — all uids present in one are present in the other. Positions are preserved exactly.
2. **Python-ahead.** The Python IR has nodes the UI JSON does not (new nodes added via `wf.node(...)` or `wf.add_node(...)`). New nodes receive auto-placed positions; existing nodes keep their positions. The change report lists them under `new_auto_placed`.
3. **Editor-ahead (REFUSE).** The prior UI JSON has nodes the Python IR does not (someone edited in ComfyUI after the last `port export`). VibeComfy refuses with:

  ```
  port export refused: editor is ahead — N node(s) exist in the prior UI JSON but not in the Python IR: uid=<uid> class=<class>[, uid=<uid> class=<class>]. Re-run `port convert <prior.json>` to import them, or pass --force-drop to discard explicitly.
  ```

The canonical loop:

```
editor .json → port convert → Python (.py + uid=) → edit structure → port export --to ui → editor
```

The K3 plane-separation rule: the editor owns layout (positions, groups, notes, reroutes); Python owns structure (nodes, edges, widgets). The round-trip preserves layout plane data across structure edits and re-lays out cleanly when no prior layout exists.

Divergence rules: when a uid is present in the prior store but absent from the IR, VibeComfy checks whether the uid was authored by a prior VibeComfy emit (via the breadcrumb `extra.vibecomfy.prior_path`). If yes, the node was deleted in Python — it appears in the change report's `removed` list. If no (the prior_path differs or is absent), the node is conservatively treated as editor-added, and `EditorAheadError` is raised.

Two escape hatches for the editor-ahead state:
- `port convert <prior.json>` — import the editor-only nodes into Python, then re-export.
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

## `port convert --keep-virtual-wires`

By default, `port convert` resolves GetNode/SetNode/Reroute helpers into direct edges, producing clean Python with only execution nodes. This is the right choice for most authored code — the Python representation stays minimal and the editor view is reconstructed from the layout sidecar at emit time.

Pass `--keep-virtual-wires` to emit explicit `wf.node("GetNode"…)` / `wf.node("SetNode"…)` / `wf.node("Reroute"…)` calls in the generated `.py`. Use this when editor-faithfulness requires those nodes to survive in the Python source (e.g., for collaborative workflows where the Python representation must stay structurally identical to the editor view). The trade-off: the Python source becomes larger and carries UI-only nodes, but the IR-level round-trip is invariant — the flat execution graph emitted from both paths is structurally equivalent.

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
