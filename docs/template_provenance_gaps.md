# Template Provenance Gaps (Family P)

These ready templates have no local `source_workflow` file — their `READY_METADATA.provenance.source_workflow` is either missing or points to a URL that was not cached locally. Without that source JSON, `port convert` cannot materialize them, so they accumulate emitter drift over time.

The canonical resolution path is **`port reemit`** (`python -m vibecomfy.cli port reemit <ready-id-or-path>`), which loads the template through the same loader path as `port convert` and writes it back through the current emitter. `port reemit` is a refresh, not a promotion — it skips the strict-ready, parity, schema, and model-value gates that `port convert` enforces — so a successful `port reemit` does **not** mean the template is app-parity ready. It just means the template now reflects current emitter rules.

`port reemit --all-family-p` will discover every template listed in this doc plus every ready template still emitting the legacy `WIDGET_N = ...` constant pattern.

## Resolved: 5 runexx templates (Family P → re-emitted clean)

The five templates below were originally Family P (lacked local source JSON). Source JSONs were subsequently restored under `workflow_corpus/custom_nodes/ltxvideo/runexx/`. After Phase 3 emitter work (T4 constant renaming, T5 single-use inlining, T8 named kwargs, T12 regen), they were re-emitted clean:

- No `WIDGET_N` / `WIDGET__NAME` constants (value-derived names or inlined)
- `# vibecomfy: generated` header
- Known-class kwargs use named form where the widget alias resolver succeeds

Residual opaque patterns (documented as out-of-scope for this sprint):

- **Orphaned helper nodes in `build()`**: `raw_call('Reroute', ...)` and `raw_call('GetNode', ...)` persist because they have no incoming edges in the loaded workflow graph — the helper resolver cannot determine their source to rewire consumers. These originate from source JSONs that used Reroute/GetNode as wire jumps; the reemit path lacks the source JSON to reconstruct the edge topology.
- **`widget_N=` on known classes**: Some known ComfyUI class instances still emit `widget_0=`, `widget_1=`, etc. instead of named kwargs. The widget alias resolver depends on `WIDGET_SCHEMA` and `object_info` caches; when the alias lookup chain falls through to raw `widget_N`, the emitter preserves that form.
- **Unknown class types via `raw_call`**: Custom nodes not in the object_info cache (e.g., `Power Lora Loader (rgthree)`, `MelBandRoFormerModelLoader`, `PrimitiveBoolean`) are emitted as `raw_call(...)` with `widget_N=` kwargs — this is expected and is the correct fallback.

| Template | Status |
|---|---|
| `video/ltx2_3_runexx_lipsync_custom_audio` | Re-emitted clean. Source: `workflow_corpus/custom_nodes/ltxvideo/runexx/LTX-2.3_V2V_Just_Talk_custom_audio_lipsync.json`. Has `raw_call('Reroute',...)` in build() (orphaned). |
| `video/ltx2_3_runexx_motion_transfer_dwpose` | Re-emitted clean. Source: `workflow_corpus/custom_nodes/ltxvideo/runexx/LTX-2.3_Motion_Transfer_DWPose.json`. Has `raw_call('Reroute',...)` in build() (orphaned). |
| `video/ltx2_3_runexx_music_video_low_ram` | Re-emitted clean. Source: `workflow_corpus/custom_nodes/ltxvideo/runexx/LTX-2.3_Music_Video_Creator_Low_RAM.json`. Has `raw_call('Reroute',...)` and `raw_call('GetNode',...)` in build() (orphaned). |
| `video/ltx2_3_runexx_talking_avatar_qwen_tts` | Re-emitted clean. Source: `workflow_corpus/custom_nodes/ltxvideo/runexx/LTX-2.3_Talking_Avatar_Qwen_TTS.json`. Had `WIDGET__NAME` constant — resolved by reemit. Has `raw_call('Reroute',...)` and `raw_call('GetNode',...)` in build() (orphaned). |
| `video/ltx2_3_runexx_video_to_video_extend` | Re-emitted clean. Source: `workflow_corpus/custom_nodes/ltxvideo/runexx/LTX-2.3_V2V_Extend_Any_Video.json`. Has `raw_call('Reroute',...)` in build() (orphaned). |

To refresh again after future emitter work, run:

```bash
python -m vibecomfy.cli port reemit ready_templates/video/<template>.py
python -m vibecomfy.cli validate ready_templates/video/<template>.py
```

## In Progress: 2 Family P templates (source fetched, port convert blocked)

These two templates had no local source JSON. Source JSONs were fetched from upstream repositories and committed under `workflow_corpus/community/`. `port convert` is blocked by pre-existing strict-ready validation issues (not emitter regressions). Reemit was attempted where the template header permits it.

### `video/ltx2_3_runexx_first_last_raw_video_guide`

- **Status:** `# vibecomfy: manual`, Family P (source committed, port convert blocked)
- **Source JSON:** Fetched from RuneXX/LTX-2.3-Workflows (`First-Last-Frame/LTX-2.3_-_FLF2V_First-Last-Frame.json`), committed as `workflow_corpus/community/runexx/LTX-2.3_FLF2V_First-Last-Frame.json`.
- **Port convert status:** Blocked — strict-ready validation reports hard errors (missing model assets, unnamed output contracts). Pre-existing; not an emitter regression.
- **Reemit status:** Refused — template is marked `# vibecomfy: manual`. Reemit will not overwrite manual templates.
- **Resolution path:** The closest upstream source (`FLF2V_First-Last-Frame`) was committed. Next step: either (a) hand-migrate the manual template's `source_workflow` metadata to point to the committed JSON, remove the manual marker, and run `port convert`, or (b) generate a non-manual variant from the source and compare against the manual template.
- **Note:** The template approach ("first/last-frame image anchors plus full-length raw video frames into LTXVAddGuide") may not exactly match the upstream FLF2V source. Attribution is approximate until `port convert` succeeds.

### `video/wanvideo_wrapper_22_wan_animate_preprocess_kijai`

- **Status:** `# vibecomfy: generated`, source committed, port convert blocked, re-emitted
- **Source JSON:** Fetched from Kijai/ComfyUI-WanVideoWrapper (`wanvideo_WanAnimate_preprocess_example_02.json`), committed as `workflow_corpus/community/kijai/wan_animate_preprocess_example_02.json`.
- **Port convert status:** Blocked — strict-ready validation reports `strict_ready_unnamed_output_contract` (multi-output arity) and `schema_unknown_kwarg_hidden_by_extras` warnings. Pre-existing; not an emitter regression.
- **Reemit status:** Re-emitted successfully — now on current emitter shape.
- **Resolution path:** Source JSON committed. Reemit refreshed the template. Full `port convert` still blocked by strict-ready output contract issues (Family D multi-output arity). Next step: resolve the output contract arity (likely needs `OutputSpec` declarations for multiple unnamed outputs), then rerun `port convert`.

## How to Detect Remaining Family P Templates

```bash
python -m vibecomfy.cli port inventory --ready --json \
  | python3 -c "
import json, sys
rows = json.load(sys.stdin).get('templates', [])
p = [r for r in rows if not r.get('source_workflow')]
print(f'{len(p)} Family P templates:')
for r in p:
    print('  ', r['ready_id'])
"
```

## When to Use `port reemit` vs `port convert`

| Situation | Command |
|---|---|
| Source JSON exists under `workflow_corpus/` and you want strict-ready, parity-checked re-emission | `port convert <workflow> --ready-id <kind>/<name> --out ready_templates/<kind>/<name>.py` |
| Source JSON is missing or the template is on `# vibecomfy: broken-regen`, and you want to apply current emitter rules | `port reemit ready_templates/<kind>/<name>.py` |
| Sweep every Family P template + every template still on the legacy `WIDGET_N` constant shape | `port reemit --all-family-p` |

## Non-Goals

`port reemit` does **not** restore subgraph materialization (the embedded subgraph definitions live in the source JSON we lack), nor does it fix pre-existing schema enum mismatches or missing required inputs. Those still need a restored source JSON and a full `port convert` run. Future work: establish a workflow corpus fetcher that downloads and caches upstream source JSONs using recorded `source_url` metadata.
