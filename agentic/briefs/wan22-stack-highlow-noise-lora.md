# Put my 2-stage LoRA on the Wan 2.2 high/low-noise video workflow

Start from the `video/wanvideo_wrapper_22_14b_i2v_kijai` image-to-video workflow.

I trained a LoRA and I have no idea how to wire it in. This Wan 2.2 setup confuses
me because it runs the video in two stages: there's a high-noise stage and a
low-noise stage, and each stage uses its own copy of the model. I want my LoRA to
actually affect the whole generation, which (as I understand it) means it has to be
applied to BOTH stages, not just one of them — if it only hits one stage the result
comes out half-baked and inconsistent.

Please add my LoRA to both the high-noise model and the low-noise model. Use a
slightly stronger setting on the high-noise stage and a slightly gentler one on the
low-noise stage. Then give me back the resulting video output path and confirm the
workflow is wired up and finalized.
