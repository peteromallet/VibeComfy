# Add a model speed-up to the Wan text-to-video workflow

Start from the ready template `video/wanvideo_wrapper_21_14b_t2v`.

In that workflow the video model is loaded, then a LoRA is layered onto it, and the
combined model is what actually drives the sampler. I want to add a model
optimization step (a torch-compile / model-modifier pass) so the model runs faster.

The important part: the optimization has to apply to the base model **before** the
LoRA is layered on, so that the sped-up version covers the whole model **plus** the
LoRA — not just the bare model and not only the part after the LoRA. In other words,
the optimization should sit ahead of the LoRA step, and everything after it (the
LoRA, the existing block-swap, and the sampler) should keep getting the fully
combined model exactly as before.

Please wire it in at the correct point and leave the rest of the pipeline working.
