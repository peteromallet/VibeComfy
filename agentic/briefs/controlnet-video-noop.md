# ControlNet on Video Workflow (No-Op)

Apply the ControlNet patch to a simple video workflow that loads an image from "input/first-frame.png" and saves it as a video. There is no KSampler or sampling step in this workflow, so the patch should have no effect. Confirm that the patch was called, that it recognized there was nothing to do, and that the original LoadImage-to-SaveVideo structure is unchanged.
