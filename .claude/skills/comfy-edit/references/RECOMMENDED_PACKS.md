# Recommended Node Packs

Essential community packs with high-quality, well-documented nodes.

## ComfyUI-KJNodes (by kijai)

**Source**: https://github.com/kijai/ComfyUI-KJNodes
**Author**: kijai (Banadoco lead)
**Nodes**: 114+ | **Downloads**: 2.3M+

### Essential Nodes

| Node | Use Case |
|------|----------|
| SetNode / GetNode | Clean wire routing, reduce clutter |
| GrowMaskWithBlur | Inpainting mask refinement |
| ColorToMask | Select colors from images |
| ConditioningMultiCombine | Combine multiple prompts |
| CrossFadeImages | Video transitions |
| SplineEditor | Draw animation curves |
| BatchCLIPSeg | Text-guided batch segmentation |

### Categories
- **Mask Creation**: Shape, gradient, Voronoi, fluid, text, audio-reactive
- **Image Processing**: Resize, grid layouts, color match, batch ops
- **Workflow Utils**: Constants, Set/Get, string operations
- **Interactive**: Spline editor, points editor

### Install
```bash
cd ComfyUI/custom_nodes
git clone https://github.com/kijai/ComfyUI-KJNodes
```

---

## ComfyUI_Fill-Nodes (by filliptm)

**Source**: https://github.com/filliptm/ComfyUI_Fill-Nodes
**Author**: filliptm
**Nodes**: 195+

### Categories

| Category | Count | Highlights |
|----------|-------|------------|
| VFX | 16 | Glitch, dither, halftone, pixel sort, ASCII, Shadertoy |
| Image | 31 | Anime line extract, aspect crop, batch tools |
| Audio | 15 | BPM analyzer, beat sync, audio-reactive effects |
| Video | 10 | FILM/RIFE interpolation, ProRes export, crossfade |
| Captioning | 11 | Ollama captioner, CSV tools, caption saver |
| AI/API | 20 | GPT Vision, DALL-E 3, Gemini, Runway, Fal.ai |
| KSampler | 7 | XYZ plot, enhanced samplers |
| PDF | 10 | PDF to images, merge, encrypt |
| Utility | 27 | Code node, JS node, math, switches |

### Essential Nodes

| Node | Use Case |
|------|----------|
| FL_Glitch | Glitch art effects |
| FL_Dither | Retro dithering |
| FL_PixelSort | Pixel sorting effect |
| FL_Audio_BPM_Analyzer | Sync to music beats |
| FL_Audio_Music_Video_Sequencer | Music video creation |
| FL_RIFE / FL_FILM | Frame interpolation |
| FL_CodeNode | Custom Python in workflow |
| FL_InpaintCrop / FL_Inpaint_Stitch | Smart inpaint workflow |

### Install
```bash
cd ComfyUI/custom_nodes
git clone https://github.com/filliptm/ComfyUI_Fill-Nodes
pip install -r ComfyUI_Fill-Nodes/requirements.txt
```

---

## ComfyUI-Purz (by purzbeats)

**Source**: https://github.com/purzbeats/ComfyUI-Purz
**Author**: purzbeats (ComfyUI Tutor & Community Manager)
**Nodes**: 20+

### Categories

| Category | Nodes |
|----------|-------|
| Interactive | 42-effect real-time filter with WebGL |
| Color | B&W conversion, color adjust |
| Transform | Rotate, flip/mirror |
| Effects | Blur, pixelate, edge detection |
| Patterns | Checkerboard, stripes, polka dots, grid, gradient, noise |
| Animated | Animated versions of all patterns |

### Workflows

| Workflow | Description |
|----------|-------------|
| Vid2Vid 2024 | AnimateLCM + AnimateDiff v3 |
| Subject Masking | Replace subjects in video |
| Background Masking | Replace backgrounds in video |
| SVD Simple | Basic image-to-video |
| SVD 8x Extension | Extended video with interpolation |

### Install
```bash
cd ComfyUI/custom_nodes
git clone https://github.com/purzbeats/ComfyUI-Purz

# Workflows
git clone https://github.com/purzbeats/purz-comfyui-workflows
```

---

## ComfyUI_RyanOnTheInside (by ryanontheinside)

**Source**: https://github.com/ryanontheinside/ComfyUI_RyanOnTheInside
**Author**: ryanontheinside
**Focus**: Audio/MIDI reactive, particles, optical flow

### Audio Feature Extraction

| Node | Use Case |
|------|----------|
| ROTI_AmplitudeEnvelope | Volume tracking for reactive effects |
| ROTI_RMSEnergy | Smooth energy measurement |
| ROTI_SpectralCentroid | Frequency/brightness analysis |
| ROTI_OnsetDetection | Beat/transient detection |
| ROTI_ChromaFeatures | Tonal/harmonic analysis |
| ROTI_TrackSeparation | Isolate vocals, drums, bass, instruments |

### MIDI Processing

| Node | Use Case |
|------|----------|
| ROTI_MIDIVelocity | Note intensity control |
| ROTI_MIDIPitch | Pitch-based modulation |
| ROTI_MIDINoteOnOff | Trigger on note events |
| ROTI_MIDICC | Control Change parameter mapping |

### ACEStep Audio Generation

| Node | Use Case |
|------|----------|
| ACEStepRepaintGuider | Audio inpainting - regenerate regions |
| ACEStepExtendGuider | Extend audio before/after |
| ACEStepHybridGuider | Combined repaint + extend |

### Flex Features (Dynamic Modulation)

| Node | Use Case |
|------|----------|
| FlexFeaturePulse | Rhythmic pulsing effects |
| FlexFeatureBounce | Elastic bounce modulation |
| FlexIPAdapter | Audio-reactive IPAdapter |
| FlexMask | Audio-reactive masks |

### Particles & Optical Flow

| Node | Use Case |
|------|----------|
| ParticleEmitter | Spawn particles |
| ParticleGravityWell | Attraction/repulsion forces |
| ParticleVortex | Swirling motion |
| OpticalFlowMask | Motion-based masks |

### Install
```bash
cd ComfyUI/custom_nodes
git clone https://github.com/ryanontheinside/ComfyUI_RyanOnTheInside
pip install -r ComfyUI_RyanOnTheInside/requirements.txt
```

---

## Steerable-Motion (by Banodoco)

**Source**: https://github.com/banodoco/Steerable-Motion
**Author**: Banodoco team (kijai, pom, community)
**Focus**: Image-to-video interpolation, creative motion control

### Core Concept

"A paintbrush, not a button" - travel between batches of images with controllable motion. Uses AnimateDiff + IP-Adapter + SparseCtrl or Wan + VACE approaches.

### Two Approaches

| Approach | Technology | Best For |
|----------|------------|----------|
| AnimateDiff | IP-Adapter + SparseCtrl | Stylized, artistic motion |
| Wan + VACE | Video Anchor Continuation | Realistic, coherent video |

### Pre-configured Workflows

| Workflow | Style |
|----------|-------|
| **Smooth n' Steady** | Fluid motion - **start here** |
| Rad Attack | Realistic motion reproduction |
| Slurshy Realistiche | Realistic, blended appearance |
| Chocky Realistiche | Realistic, blocky transitions |
| Liquidy Loop | Smooth flowing, seamless loops |
| VACE Travel | Wan-based anchor/continuation |
| SuperBeasts POM | Pom's smooth batch creative |

### Key Nodes

| Node | Use Case |
|------|----------|
| BatchCreativeInterpolation | Drive video from image batches |
| VACETravel | Wan-based image interpolation |
| VACEAnchorImage | Create starting anchors |
| VACEContinuation | Chain continuations for video |

### Dependencies
- AnimateDiff Evolved (Kosinkadink)
- ComfyUI-Advanced-ControlNet
- IPAdapter_plus (Cubiq)
- Frame Interpolation (Fizzledorf)
- ComfyUI-WanVideoWrapper (Kijai)

### Install
```bash
cd ComfyUI/custom_nodes
git clone https://github.com/banodoco/Steerable-Motion

# Use ComfyUI Manager to install dependencies
# Then download required models via Manager
```

### Related Tool
**Dough** - Simplified creative interface for Steerable Motion
https://github.com/banodoco/Dough

---

## Quick Comparison

| Pack | Strength | Best For |
|------|----------|----------|
| KJNodes | Workflow utils, masks | Clean workflows, regional prompting |
| Fill-Nodes | VFX, audio, video | Music videos, glitch art, effects |
| Purz | Patterns, tutorials | Learning, pattern generation |
| RyanOnTheInside | Audio/MIDI, particles | Music videos, audio-reactive art |
| Steerable-Motion | Image→video interpolation | Keyframe animation, creative video |

## Combined Search

All nodes from these packs are in the MCP registry. Search examples:
- `comfy_search("glitch")` → FL_Glitch, effects
- `comfy_search("audio reactive")` → FL_Audio_*, ROTI_*, KJ audio nodes
- `comfy_search("mask grow")` → GrowMaskWithBlur
- `comfy_search("pattern animated")` → Purz animated patterns
- `comfy_search("midi")` → ROTI_MIDI* nodes
- `comfy_search("onset")` → ROTI_OnsetDetection
- `comfy_search("particle")` → ParticleEmitter, forces
- `comfy_search("track separation")` → ROTI_TrackSeparation, FL_Audio_Separation
- `comfy_search("steerable motion")` → BatchCreativeInterpolation, workflows
- `comfy_search("VACE")` → VACETravel, VACEAnchorImage, VACEContinuation
- `comfy_search("smooth n steady")` → workflow_smooth_n_steady
