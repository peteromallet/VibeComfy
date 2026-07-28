# Replacement additive examples for cases 02, 04, and 07

These replacements were checked against both the ready-template source and the
campaign's actual `find_feature_node_ids` matcher. Each check returned the
listed node, and `_remove_feature_fault` returned a real fault injection rather
than `None`, so none of these entries takes the `skipped_no_feature_node` path.

The set deliberately avoids the existing LTX two-stage refinement and WanVideo
LoRA passing patterns. Two replacements use the `upscale` family because the
current `audio_merge` matcher can select generic audio nodes before a real
concat/merge node, while the corpus's face-named nodes are masks or segmenters,
not genuine face-detailer passes.

## Replacement for case 02: Wan Fun Control

- **`workflow_id`:** `video/wanvideo_wrapper_21_14b_fun_control`
- **`feature_type`:** `controlnet`
- **Confirmed-present node class:** `WanVideoControlEmbeds` (node `78`)
- **Role:** Turns the encoded depth-control video into control embeddings and
  supplies them to the empty video embeds consumed by the Wan sampler. This is
  the active structural-control path, not merely a similarly named workflow.
- **Campaign verification:** `find_feature_node_ids(golden, "controlnet")`
  returned only `[("78", "WanVideoControlEmbeds")]`; fault injection reported
  `Removed controlnet (WanVideoControlEmbeds) feature from graph`.

Evidence from `ready_templates/video/wanvideo_wrapper_21_14b_fun_control.py`:

```python
wanvideoencode = WanVideoEncode(
    _id='77',
    # ...
    image=image_3,
    vae=wanvideovaeloader,
)

wanvideocontrolembeds = WanVideoControlEmbeds(
    _id='78',
    latents=wanvideoencode,
)

wanvideoemptyembeds = WanVideoEmptyEmbeds(
    _id='69',
    # ...
    control_embeds=wanvideocontrolembeds,
)
```

**Re-add prompt:**

> I had removed the ControlNet guidance step from this workflow, and now the generated video ignores the depth and structure of the guide clip. Can you add the ControlNet step back where it belongs so the scene and motion follow the control reference again?

**Proposed `ADDITIVE_WORKFLOWS` entry:**

```python
("video/wanvideo_wrapper_21_14b_fun_control", "controlnet"),
```

## Replacement for case 04: Z-Image img2img canvas scaling

- **`workflow_id`:** `image/z_image_img2img`
- **`feature_type`:** `upscale`
- **Confirmed-present node class:** `ImageScale` (node `8`)
- **Role:** Resizes the input image to the intended img2img canvas before VAE
  encoding; the sampler's initialization latent therefore depends on this
  scaling stage.
- **Campaign verification:** `find_feature_node_ids(golden, "upscale")`
  returned only `[("8", "ImageScale")]`; fault injection reported
  `Removed upscale (ImageScale) feature from graph`.

Evidence from `ready_templates/image/z_image_img2img.py`:

```python
imagescale = ImageScale(
    _id='8',
    upscale_method='lanczos',
    width=1024,
    height=1024,
    crop='center',
    image=image,
)

vaeencode = VAEEncode(_id='9', pixels=imagescale, vae=vaeloader)
```

**Re-add prompt:**

> I had removed the upscale/resize step before img2img encoding, and now the generated image no longer uses the intended canvas size: its framing and resolution are wrong and fine detail is softer. Can you add the upscale step back in the input path so the img2img result is restored?

**Proposed `ADDITIVE_WORKFLOWS` entry:**

```python
("image/z_image_img2img", "upscale"),
```

## Replacement for case 07: per-frame video enhancement

- **`workflow_id`:** `video/basic_video_enhance`
- **`feature_type`:** `upscale`
- **Confirmed-present node class:** `ImageScaleBy` (node `2`)
- **Role:** Upscales every frame between video loading and final video
  recombination. It is on the sole output route, so removing it directly
  eliminates the workflow's resolution-enhancement stage.
- **Campaign verification:** `find_feature_node_ids(golden, "upscale")`
  returned only `[("2", "ImageScaleBy")]`; fault injection reported
  `Removed upscale (ImageScaleBy) feature from graph`.

Evidence from `ready_templates/video/basic_video_enhance.py`:

```python
image, _, audio, _ = VHS_LoadVideo(_id='1', video='video_enhance_input.mp4')

imagescaleby = ImageScaleBy(
    _id='2',
    upscale_method='lanczos',
    scale_by=2.0,
    image=image,
)

vhs_videocombine = VHS_VideoCombine(
    _id='3',
    # ...
    audio=audio,
    images=imagescaleby,
)
```

**Re-add prompt:**

> I had removed the video upscale step, and now the rebuilt video stays at the source resolution and has lost the extra detail the enhancement path used to add. Can you add the upscale step back between the loaded frames and the final video output?

**Proposed `ADDITIVE_WORKFLOWS` entry:**

```python
("video/basic_video_enhance", "upscale"),
```
