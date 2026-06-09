# Swap the tiled VAE decode in the LTX image-to-video workflow

Start from the ready template `video/ltx2_3_i2v`.

My renders out of this workflow keep coming out with a faint grid / checkerboard
pattern over the video, and the seams shift around between frames. I'm pretty
sure it's the tiled video decode step — it splits the frames into tiles and
stitches them back together, and the tiling settings are clearly wrong for my
clips.

I don't want to fiddle with tile counts or overlap. Just decode the whole thing
in one pass instead. Replace the tiled decode with a plain, ordinary video
decode, and leave everything else in the workflow exactly as it is — same image
input, same prompts, same sampling, same audio, same final saved video.

The result has to still produce the same finished video at the end — the decode
that feeds the saved output should now be the regular one-pass decode, reading
from the exact same place the tiled decode read from, so nothing downstream
ends up disconnected.
