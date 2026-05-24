# Template Provenance Gaps (Family P)

These ready templates have no local `source_workflow` file — their `READY_METADATA.provenance.source_workflow` is either missing or points to a URL that was not cached locally. Without that source JSON, `port convert` cannot materialize them, so they accumulate emitter drift over time.

The canonical resolution path is **`port reemit`** (`python -m vibecomfy.cli port reemit <ready-id-or-path>`), which loads the template through the same loader path as `port convert` and writes it back through the current emitter. `port reemit` is a refresh, not a promotion — it skips the strict-ready, parity, schema, and model-value gates that `port convert` enforces — so a successful `port reemit` does **not** mean the template is app-parity ready. It just means the template now reflects current emitter rules.

`port reemit --all-family-p` will discover every template listed in this doc plus every ready template still emitting the legacy `WIDGET_N = ...` constant pattern.

## Resolved via `port reemit`

The templates below were re-emitted through the current emitter (commit `5189128`) and now ship `# vibecomfy: generated` markers instead of `# vibecomfy: broken-regen`. They still lack a local source JSON, so they remain technically Family P, but they are no longer stuck on stale emitter shape.

- `video/ltx2_3_runexx_lipsync_custom_audio`
- `video/ltx2_3_runexx_motion_transfer_dwpose`
- `video/ltx2_3_runexx_music_video_low_ram`
- `video/ltx2_3_runexx_talking_avatar_qwen_tts`
- `video/ltx2_3_runexx_video_to_video_extend`

To refresh again after future emitter work, run:

```bash
python -m vibecomfy.cli port reemit ready_templates/video/<template>.py
python -m vibecomfy.cli validate ready_templates/video/<template>.py
```

## Open Family P Templates

These templates still need a source JSON before they can be `port convert`'d. `port reemit` will refresh their emitter shape, but full structural fidelity (including subgraph materialization and strict-ready compliance) requires restoring the source under `workflow_corpus/`.

### `video/ltx2_3_runexx_first_last_raw_video_guide`

- **Status:** broken-regen, Family P
- **Reason:** No `source_workflow` metadata and no matching local source JSON found under `workflow_corpus/`.
- **Source URL:** Not recorded in the template metadata.
- **Attributed family signals:** Unknown — cannot attribute from current evidence without the source workflow.
- **Resolution path:** Add `READY_METADATA.provenance.source_workflow` pointing to a checked-in JSON, or restore the source JSON to `workflow_corpus/` and rerun `port convert --ready-id video/ltx2_3_runexx_first_last_raw_video_guide`. As an interim measure, `port reemit ready_templates/video/ltx2_3_runexx_first_last_raw_video_guide.py` will refresh the emitter shape without restoring structural fidelity.

### `video/wanvideo_wrapper_22_wan_animate_preprocess_kijai`

- **Status:** broken-regen, Family P
- **Reason:** No `source_workflow` metadata and no local source JSON found. The template metadata records an upstream `source_url` only.
- **Source URL:** Recorded as an upstream URL in the template; not cached locally.
- **Attributed family signals:** Family D (multi-output arity) is likely based on prior attribution, but cannot be verified without a local source. VHS_VideoCombine errors also present.
- **Resolution path:** Download and cache the upstream JSON under `workflow_corpus/community/<source>/`, set `source_workflow` in `READY_METADATA.provenance`, then rerun `port convert --ready-id video/wanvideo_wrapper_22_wan_animate_preprocess_kijai`. As an interim measure, `port reemit` will refresh the emitter shape.

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
