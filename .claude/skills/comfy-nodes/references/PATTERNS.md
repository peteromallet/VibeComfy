# ComfyUI Workflow Patterns

Common node combinations (recipes) for building workflows.

## Image Generation

### Basic txt2img
```
CheckpointLoaderSimple
  → CLIPTextEncode (positive)
  → CLIPTextEncode (negative)  
  → EmptyLatentImage
  → KSampler
  → VAEDecode
  → SaveImage
```

### img2img
```
LoadImage
  → VAEEncode
  → KSampler (denoise: 0.5-0.8)
  → VAEDecode
  → SaveImage
```

### Inpainting
```
LoadImage + LoadImage (mask)
  → VAEEncodeForInpaint
  → KSampler
  → VAEDecode
  → SaveImage
```

## ControlNet

### Basic ControlNet
```
LoadControlNet
  → ControlNetApply
      ├─ positive conditioning
      └─ control image (preprocessed)
  → KSampler
```

### Multi-ControlNet
```
ControlNetApply (depth)
  → ControlNetApply (canny)
      → KSampler
```

### Preprocessors
- Canny: `CannyEdgePreprocessor`
- Depth: `DepthAnythingPreprocessor`, `MiDaS-DepthMapPreprocessor`
- Pose: `DWPreprocessor`, `OpenposePreprocessor`
- Lineart: `LineArtPreprocessor`

## Upscaling

### Simple Upscale
```
LoadUpscaleModel (4x-UltraSharp, RealESRGAN)
  → ImageUpscaleWithModel
  → SaveImage
```

### Hi-Res Fix (2-pass)
```
KSampler (low res)
  → VAEDecode
  → ImageScale (1.5x)
  → VAEEncode
  → KSampler (denoise: 0.4-0.6)
  → VAEDecode
  → SaveImage
```

## LoRA

### Single LoRA
```
CheckpointLoaderSimple
  → LoraLoader (model, clip)
  → CLIPTextEncode
  → KSampler
```

### LoRA Stack
```
LoraLoader
  → LoraLoader
  → LoraLoader
  → KSampler
```

## Video / Animation

### AnimateDiff
```
CheckpointLoaderSimple
  → ADE_LoadAnimateDiffModel
  → ADE_ApplyAnimateDiffModel
  → KSampler (batch latent)
  → VAEDecode
  → VHS_VideoCombine
```

### Frame Interpolation
```
LoadVideo
  → RIFE_Interpolate
  → SaveVideo
```

### Video2Video
```
VHS_LoadVideo
  → VAEEncode (per frame)
  → KSampler (denoise: 0.3-0.5)
  → VAEDecode
  → VHS_VideoCombine
```

## Flux Specific

### Flux txt2img
```
UNETLoader (flux model)
  → DualCLIPLoader (t5xxl + clip_l)
  → CLIPTextEncode
  → EmptySD3LatentImage
  → KSampler (euler, normal scheduler)
  → VAEDecode
  → SaveImage
```

### Flux with LoRA
```
UNETLoader
  → LoraLoader
  → KSampler
```

## Wan / LTX Video

### Wan Text-to-Video
```
WanModelLoader
  → WanTextEncode
  → WanSampler
  → WanDecode
  → SaveVideo
```

### LTX Video
```
LTXVLoader
  → LTXVTextEncode
  → LTXVSampler
  → LTXVDecode
  → SaveVideo
```
