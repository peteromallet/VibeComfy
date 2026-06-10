# Chaining: Image-to-Video (Positive)

Build a two-stage image-to-video chain using VibeComfy ops.
Stage 1: Generate an image from a text prompt using `image.t2i`.
Stage 2: Feed the stage-1 output image into `video.i2v` with a motion prompt.

Compile both stages, record evidence, and verify chain linkage metadata.
