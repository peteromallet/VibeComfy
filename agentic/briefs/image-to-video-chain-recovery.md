# Chaining: Image-to-Video (Recovery)

Build a two-stage image-to-video chain using VibeComfy ops, but intentionally
trigger the object-form validation error and recover gracefully.

Stage 1: Generate an image from a text prompt using `image.t2i`. Hold onto the
returned `Image` artifact object.

Stage 2 (first attempt): Call `video.i2v(image_artifact_from_stage1, motion_prompt)`
using the **Image object** directly — do NOT extract the output path first.
This should trigger a `ValueError` because `video.i2v` only accepts filesystem
paths for image input.

Stage 2 (recovery): After capturing the error, retry by passing
`result.outputs[0]` (the file-system output path from stage 1) into
`video.i2v(path_string, motion_prompt)`. Compile both stages into the
structural API, record the error AND the recovery step in `actions.jsonl`,
and verify that the final stage-2 `LoadImage.image` binds the recovered
stage-1 output path.
