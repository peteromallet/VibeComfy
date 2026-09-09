# Node Pack Reconciliation

Agent workflow for resolving unresolved class types, widget aliases, and model registry
gaps that block `port check` from clearing before `port convert` can run.

## Overview

Node reconciliation is a deterministic report over the candidate that will be loaded or converted. Run `vibecomfy nodes reconcile --workflow <workflow> --json` against the same local schema, pack, model, and runtime context; it reports evidence and remediation without mutating the workflow or treating raw API JSON as an execution source.

`port check <workflow>` gates `port convert` — if the report has any `severity="error"`
diagnostic, the emitter will not run. The four most common gate-blocking error codes and
their fixes are:

| Code | Root cause | Fix location |
|---|---|---|
| `unresolved_runtime_class` | Class not in any known pack | `vibecomfy/node_packs.py` |
| `unknown_class_type` | Class not in object_info cache | `vibecomfy/porting/cache/object_info/` + `index.json` |
| `unknown_input widget_N` | Widget alias not resolved | `vibecomfy/porting/widget_schema.py` + `widget_aliases.py` |
| `value_not_in_enum` | Model filename not in snapshot enum | `vibecomfy/schema/validate.py` SCHEMA_VALIDATION_SKIP_CLASSES |

`nodes reconcile --workflow <wf> --json` produces a structured fix-plan with one
remediation per audit row. The action categories are:

- `declare-pack`: add a `CustomNodePack` entry in `vibecomfy/node_packs.py`
- `install-pack`: run `vibecomfy nodes install <pack>`
- `refresh-schema`: run `vibecomfy nodes refresh-template <path>`
- `register-widget-alias`: edit `widget_schema.py` + `widget_aliases.py`
- `register-model`: add enum entry in `vibecomfy/registry/models.yaml`
- `defer-as-out-of-scope`: community-unknown class; document exception

## Step-by-step agent workflow

### 1. Run `nodes reconcile` to enumerate issues

```bash
python -m vibecomfy.cli nodes reconcile --workflow <wf> --json
```

Read the `remediations` array. For each unique `class_type`, determine the category.

### 2. Fix `unresolved_runtime_class` — declare the pack

If the class is from a known GitHub repository, add a `CustomNodePack` to the
`_STATIC_NODE_PACKS` tuple in `vibecomfy/node_packs.py`:

```python
CustomNodePack(
    name="ComfyUI-PackName",
    repo="https://github.com/author/ComfyUI-PackName.git",
    classes=frozenset({"ClassTypeA", "ClassTypeB"}),
    pip_packages=("some-pip-dep",),  # only if required
),
```

Classes that are Comfy built-ins (not from any custom pack) belong in
`CORE_COMFY_CLASSES` in `vibecomfy/node_packs/_install.py`. For ComfyUI's special
runtime handles (`PrimitiveNode`, `Reroute`), add them to the `comfy-core-fallback`
entry in `vibecomfy/node_packs/_defs.py`.

### 3. Fix `unknown_class_type` — add to object_info cache

The schema validator independently checks each class type against `object_info` cache
files under `vibecomfy/porting/cache/object_info/`. Two sub-cases:

**Sub-case A: Pack has a real runpod snapshot**
Add the class to the correct `<pack>@runpod-snapshot.json` (or `@local-<hash>.json`).
Stub entries for cache satisfy the `unknown_class_type` gate but may cause
`unknown_input` cascade errors if the stub defines fewer inputs than the workflow uses.

**Sub-case B: No snapshot available — create a stub file**
Create `vibecomfy/porting/cache/object_info/<Pack>@stub.json` with minimal entries:
```json
{
  "ClassName": {
    "category": "<pack>",
    "description": "Stub entry — replace with real object_info snapshot",
    "inputs": {"required": {}, "optional": {}},
    "outputs": [],
    "name": "ClassName"
  }
}
```

After creating or modifying a cache file, update `index.json` by running:
```python
python3 -c "
import json, os
cache_dir = 'vibecomfy/porting/cache/object_info/'
with open(cache_dir + 'index.json') as f:
    idx = json.load(f)
for fname in os.listdir(cache_dir):
    if not fname.endswith('.json') or fname in ('index.json', 'provenance.json'): continue
    with open(cache_dir + fname) as f:
        data = json.load(f)
    for cls in data:
        if cls not in idx:
            idx[cls] = fname
with open(cache_dir + 'index.json', 'w') as f:
    json.dump(idx, f, indent=2, sort_keys=True)
"
```

If stub schemas cause `unknown_input` cascade errors for every input the workflow
passes, add the class to `SCHEMA_VALIDATION_SKIP_CLASSES` in
`vibecomfy/schema/validate.py` with a note pointing here.

### 4. Fix `unknown_input widget_N` — register widget alias

Two edits are required:

**Edit 1:** Add the class to `WIDGET_SCHEMA` in `vibecomfy/porting/widget_schema.py`:
```python
"ClassName": ["input_0", "input_1", None, "input_3", ...],
```
`None` marks a UI-only slot (e.g. `control_after_generate`, hidden preview). The list
must match the `widgets_values` array order in the source ComfyUI UI JSON.

**Edit 2:** Add the class to `COMPILE_WIDGET_ALIAS_CLASS_TYPES` in
`vibecomfy/porting/widget_aliases.py` so the resolver activates for that class.

To find the correct widget order, use the `object_info_widget_order` from the pack's
object_info cache file, which lists all input slots in widgets_values order and uses
`None` for link-only slots.

### 5. Fix `value_not_in_enum` for model-loader inputs

Model-loader enum values (e.g. `WanVideoModelLoader.model`) reflect files present on
the RunPod instance when the snapshot was taken. Template model paths often differ.

Three options in order of preference:

1. **Update the template** to use a model filename present in the schema enum.
2. **Add the filename to the snapshot** if it is a commonly used model.
3. **Add to `SCHEMA_VALIDATION_SKIP_CLASSES`** with a note explaining why the enum
   mismatch is expected (e.g., schema snapshot predates the model version in use).

```python
# vibecomfy/schema/validate.py
SCHEMA_VALIDATION_SKIP_CLASSES: dict[str, str] = {
    "ClassName": "reason - see docs/node_pack_reconciliation.md",
}
```

This suppresses only `unknown_input` and `value_*` codes for that class — it does not
suppress `missing_required_input` or `unknown_class_type`.

### 6. Fix dynamic inputs (`ImageConcatMulti.image_3`, etc.)

Some classes use dynamic input counts driven by a widget (e.g. `inputcount`). The
static schema only shows the base set; `image_3` is created at runtime when
`inputcount=3`. Add the class to `SCHEMA_VALIDATION_SKIP_CLASSES`.

### 7. Remaining blockers — emitter family issues

Once all pack/schema/alias fixes are applied, remaining `port check` errors fall into
emitter family categories:

| Family | Symptom | Resolution |
|---|---|---|
| **C** | `UnboundLocalError` in `port convert` | Fix subgraph function name collision |
| **E** | Missing required inputs in generated code | Fix widget assignment in emitter |
| **F** | `SetNode`/`GetNode`/`Reroute` in emitted output | Fix helper resolver pre-pass |
| **I** | UUID-class component not materialized | Apply materialize-as-inline-function policy |
| **P** | No local source JSON | Template stays on broken-regen; document |

`known_runtime_required_input_missing` for `VHS_VideoCombine` is a Family E issue —
the emitter does not capture all required widget values from source JSON. The fix is
to regenerate affected templates after the emitter correctly writes `frame_rate`,
`loop_count`, `filename_prefix`, `format`, `pingpong`, `save_output` from
`widgets_values`.

### 8. Community-unknown classes — defer and document

If a class has no identifiable public repository (e.g. `IAMCCS_*`, `ClownSampler_Beta`
from an unreleased pack, enterprise-only nodes), record the exception:
- Add a row to `docs/templates/strict_ready_exceptions.md` / `docs/templates/strict_ready_exceptions.json`
- Mark the template status as `J-deferred: community-unknown` in coverage notes
- Do not add a stub cache entry for classes with no known upstream

## Packs added during T4 reconciliation (2026-05-24)

### Newly declared packs (vibecomfy/node_packs.py)

| Pack | GitHub | Classes |
|---|---|---|
| `comfy-core-fallback` | comfyanonymous/ComfyUI | `PrimitiveNode`, `Reroute` |
| `ComfyUI-MelBandRoformer` | kijai/ComfyUI-MelBandRoformer | `MelBandRoFormerModelLoader`, `MelBandRoFormerSampler` |
| `ComfyUI-Florence2` | kijai/ComfyUI-Florence2 | `DownloadAndLoadFlorence2Model`, `Florence2Run` |
| `ComfyUI-GIMM-VFI` | kijai/ComfyUI-GIMM-VFI | `DownloadAndLoadGIMMVFIModel`, `GIMMVFI_interpolate` |
| `ComfyUI-Custom-Scripts` | pythongosssss/ComfyUI-Custom-Scripts | `ShowText\|pysssss`, `MathExpression\|pysssss` |
| `ComfyUI-Easy-Use` | yolain/ComfyUI-Easy-Use | `easy showAnything`, `easy cleanGpuUsed` |
| `ComfyUI_Comfyroll_CustomNodes` | Suzie1/ComfyUI_Comfyroll_CustomNodes | `CR Float To Integer` |
| `comfy_mtb` | melMass/comfy_mtb | `Audio Duration (mtb)`, `Audio To Text (mtb)`, `Load Whisper (mtb)` |

### Expanded packs

- **`ComfyUI-WanVideoWrapper`**: added WanVideoTeaCache, WanVideoVRAMManagement, WanVideoAddS2VEmbeds, WanVideoClipVisionEncode, WanVideoContextOptions, WanVideoImageToVideoMultiTalk, ReCamMaster* classes, MultiTalk* classes, FantasyTalking*, Wav2Vec*, NormalizeAudioLoudness
- **`ComfyUI-LTXVideo`**: added GemmaAPITextEncode, GetVideoComponents, LTXAddVideoICLoRAGuide*, LTXFloatToInt, LTXICLoRALoaderModelOnly, LTXVAddGuide*, LTXVAddLatent*, LTXVAudioVideoMask, LTXVGemmaCLIPModelLoader, LTXVImgToVideoConditionOnly, LTXVLatentUpsampler, LTXVPreprocessMasks, LTXVSetVideoLatentNoiseMasks, LTXVTiledVAEDecode, LTXVAddGuideMulti
- **`ComfyUI-KJNodes`**: added AddLabel, ColorMatch, FloatConstant, ImageBatchExtendWithOverlap, ImageBatchMulti, ImageConcatFromBatch, ImageConcatMulti, ImagePadKJ*, ImageResizeKJ, InsertLatentToIndexed, LazySwitchKJ, LTX2MemoryEfficientSageAttentionPatch, LTX2SamplingPreviewOverride, LTXVAudioVideoMask, LoadAndResizeImage, LoadVideosFromFolder, MaskPreview, VRAM_Debug, WidgetToString
- **`ComfyUI-VideoHelperSuite`**: added VHS_LoadAudio, VHS_LoadAudioUpload, VHS_LoadVideoFFmpeg/Path, VHS_SelectEveryNth*, VHS_SplitImages, VHS_VideoInfo*
- **`comfyui_controlnet_aux`**: added DepthAnythingPreprocessor

### Widget schema entries added (vibecomfy/porting/widget_schema.py)

Added widget order entries for: `AddLabel`, `DownloadAndLoadDepthAnythingV2Model`,
`EmptyImage`, `GetImageRangeFromBatch`, `ImageConcatMulti`, `ImagePadKJ`, `ImageResizeKJ`,
`ReCamMasterPoseVisualizer`, `TextEncodeAceStepAudio1.5`, `WanVideoEmptyEmbeds`,
`WanVideoEncode`, `WanVideoEnhanceAVideo`, `WanVideoExperimentalArgs`,
`WanVideoReCamMaster*`, `WanVideoSLG`, `WanVideoTeaCache`, `WanVideoVACEEncode`,
`WanVideoVACEModelSelect`, `WanVideoVACEStartToEndFrame`, `WanVideoVRAMManagement`,
`WidgetToString`.

### Stub cache files created

| File | Classes |
|---|---|
| `ComfyUI-Florence2@stub.json` | DownloadAndLoadFlorence2Model, Florence2Run |
| `ComfyUI-GIMM-VFI@stub.json` | DownloadAndLoadGIMMVFIModel, GIMMVFI_interpolate |
| `ComfyUI-MelBandRoformer@stub.json` | MelBandRoFormerModelLoader, MelBandRoFormerSampler |
| `ComfyUI-Custom-Scripts@stub.json` | ShowText\|pysssss, MathExpression\|pysssss |
| `comfyui_controlnet_aux@stub.json` | DWPreprocessor, CannyEdgePreprocessor, DepthAnythingPreprocessor |

Stub classes are added to `SCHEMA_VALIDATION_SKIP_CLASSES` in
`vibecomfy/schema/validate.py` to prevent cascade `unknown_input` errors until a real
runpod snapshot is available.

### CORE_COMFY_CLASSES additions (vibecomfy/node_packs/_install.py)

Added ~50 Comfy built-in classes confirmed from comfy_core/comfy_extras object_info
snapshots: AudioConcat, AudioEncoderEncode/Loader, BasicScheduler,
CheckpointLoaderSimple, ComfyMathExpression, ComfySwitchNode, ConditioningZeroOut,
CreateVideo, EmptyAceStep1.5LatentAudio, EmptyAudio, EmptyImage, GetVideoComponents,
ImageBlend, ImageBatchExtendWithOverlap, ImageBatchMulti, KSampler, LoadAudio,
LoadVideo, LoadVideosFromFolder, LTXVAdd/Img/Latent/Preprocess/Set* classes,
MaskPreview, MaskToImage, ModelSamplingAuraFlow/SD3, NormalizeAudioLoudness,
PreviewAudio/Image, PrimitiveInt/String/Node, Reroute, ResizeImageMaskNode,
SaveAudioMP3, SaveVideo, SetLatentNoiseMask, SimpleMath+, SolidMask,
StringConcatenate, TextEncodeAceStepAudio1.5, TextGenerateLTX2Prompt,
TrimAudioDuration, VAEDecode/Audio/Encode, VRAM_Debug.

## Deferred / community-unknown classes

| Class | Status | Reason |
|---|---|---|
| `ClownSampler_Beta` | J-deferred | No public pack identified; used in ltx2_3_t2v/i2v |
| `MultimodalGuider` | J-deferred | Part of unreleased LTX2.3 distilled sampler pack |
| `GuiderParameters` | J-deferred | Part of unreleased LTX2.3 distilled sampler pack |
| `IAMCCS_*` | J-deferred | Enterprise/private pack; no public repo |
| `FB_Qwen3TTSVoiceClone*` | J-deferred | Uncertain provenance |
| `FL_ChatterboxTurboTTS` | J-deferred | Uncertain provenance |

## Known snapshot drift issues

| Class | Snapshot | Issue |
|---|---|---|
| `WanVideoModelLoader` | `@runpod-snapshot` | Predates `vace_model` optional input |
| `WanVideoSampler` | `@runpod-snapshot` | 14-item WIDGET_SCHEMA misses item at index 14 in newer versions |
| `VHS_VideoCombine` | `@runpod-snapshot` | Correct schema; templates missing widget values (emitter Family E) |
| `ImagePadKJ` | `@runpod-snapshot` | `pad_mode` accepts RGB strings (`'255,255,255'`) not in enum |
| `WanVideoVACEModelSelect` | `@runpod-snapshot` | Model enum captures only HiddenSwitch-local VACE file |
| Florence2/GIMM-VFI/MelBandRoformer/pysssss/controlnet_aux stubs | stub files | No runpod snapshot; all inputs suppressed via SCHEMA_VALIDATION_SKIP_CLASSES |
