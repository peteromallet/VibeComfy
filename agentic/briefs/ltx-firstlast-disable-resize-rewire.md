# Disable the resize on the LTX first-last-frame workflow

Start from the ready workflow `video/ltx2_3_runexx_first_last_frame`. It is an
LTX 2.3 first-last-frame video workflow: you give it a first frame and a last
frame and it interpolates a clip between them.

Right now the input frames get run through a resize step before they reach the
rest of the pipeline, which downsizes them. I want to **disable that resize on
the frames** and keep the original resolution. The frames should flow straight
through to whatever was reading the resized version, at their native size,
with nothing left half-connected.

In short: turn off the resize on the first-last-frame inputs so the downstream
stages consume the original-resolution frames directly, and make sure the
workflow still queues cleanly afterward.
