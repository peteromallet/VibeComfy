# Wan 2.2 image-to-video, with a high-res second pass

Start from the `video/wan22_i2v_comfy_lightx2v` workflow. It already turns a
still image into a short Wan 2.2 video and saves it.

I want to add a **second, high-resolution refinement pass** on top of the
existing one. The idea is the classic Wan 2.2 "2-pass" setup:

1. Let the existing pipeline do its normal first pass to produce the video latent.
2. **Take that first pass's result, upscale it to a larger resolution**, and run
   it through **another sampling pass at low denoise** so it sharpens and adds
   detail without throwing away what the first pass produced.
3. The video that gets decoded and saved should be the **refined** one, not the
   original first-pass result.

The crucial part: the second pass has to build *on the first pass's output* —
it should be refining the video the base workflow already generated, not
generating a brand-new video from scratch. Keep everything else (the input
image, the prompt, the models) as it is in the base workflow.
