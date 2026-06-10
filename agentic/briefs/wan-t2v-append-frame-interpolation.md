# Smooth out the wan_t2v video with frame interpolation

Start from the `video/wan_t2v` workflow. It generates a short clip at about 16
frames per second, which looks a little choppy.

I want to add frame interpolation (the RIFE / FILM / GIMM kind of "in-between
frames" smoothing) so the final saved video plays back smoother — roughly
double the frame rate.

The interpolation has to happen on the actual rendered frames of the video,
after they've been turned into images — it should take the decoded frames,
generate the extra in-between frames, and then that smoothed sequence is what
gets assembled and saved as the output video. The saved clip should be the
smoothed version, not the original choppy frames.

Keep everything else about the workflow the same.
