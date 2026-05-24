# Template Provenance Gaps (Family P)

These ready templates have no local `source_workflow` file — their `READY_METADATA.provenance.source_workflow` is either missing or points to a URL that was not cached locally. They cannot be regenerated or port-converted until the source is restored.

They remain on **broken-regen** status indefinitely until the provenance gap is resolved.

## Family P Templates

### `video/ltx2_3_runexx_first_last_raw_video_guide`

- **Status:** broken-regen, Family P
- **Reason:** No `source_workflow` metadata and no matching local source JSON found under `workflow_corpus/`.
- **Source URL:** Not recorded in the template metadata.
- **Attributed family signals:** Unknown — cannot attribute from current evidence without the source workflow.
- **Resolution path:** Add `READY_METADATA.provenance.source_workflow` pointing to a checked-in JSON, or restore the source JSON to `workflow_corpus/` and rerun `port convert --ready-id video/ltx2_3_runexx_first_last_raw_video_guide`.

### `video/wanvideo_wrapper_22_wan_animate_preprocess_kijai`

- **Status:** broken-regen, Family P
- **Reason:** No `source_workflow` metadata and no local source JSON found. The template metadata records an upstream `source_url` only.
- **Source URL:** Recorded as an upstream URL in the template; not cached locally.
- **Attributed family signals:** Family D (multi-output arity) is likely based on prior attribution, but cannot be verified without a local source. VHS_VideoCombine errors also present.
- **Resolution path:** Download and cache the upstream JSON under `workflow_corpus/community/<source>/`, set `source_workflow` in `READY_METADATA.provenance`, then rerun `port convert --ready-id video/wanvideo_wrapper_22_wan_animate_preprocess_kijai`.

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

## Non-Goals

These templates are **not** addressed by the emitter family fixes (C, E, F, I). The emitter cannot generate correct Python without a local source workflow. No port-convert dry-run was possible for these; they are excluded from all dry-run evidence tallies.

Future work: establish a workflow corpus fetcher that downloads and caches upstream source JSONs using recorded `source_url` metadata.
