# Live-agentic corpus revisions

This log distinguishes query/coverage revisions from descriptors whose original
scenario intent remains matched. `scenario_manifest.json` records the same split
as `revision_status: revised|matched`.

## D13

Three edit descriptors were revised because their original requests targeted
controls that the referenced source workflow does not expose. No scenario was
replaced and all three retain their original source workflow and modality.

| Scenario | Before | After | Coverage retained |
| --- | --- | --- | --- |
| `video-video-inpainting-with-spline-based-cut-and-dra-485ff2` | Set nonexistent inpaint denoising strength to `0.6`; expected no graph change. | Set `INPAINT_InpaintWithModel` seed from `534667941392889` to `42`, keep control fixed; graph change and desired-outcome judge required. | Low-level video-inpainting parameter edit without disturbing spline/composite stages. |
| `video-image-to-video-conversion-with-moonvalley-d7853c` | Change frame count/FPS for five seconds, though Moonvalley exposes neither; expected no graph change. | Change Moonvalley generation steps from `100` to `80`, preserve prompt adherence `7`; graph change and desired-outcome judge required. | Low-level Moonvalley generation parameter edit and downstream video-save integrity. |
| `multi-3d-preview-and-image-output-workflow-d93baf` | Make a normal-map `PreviewImage` top-down as though it were a camera-controlled 3D preview; expected no graph change. | Change `SaveGLB` filename prefix from `3d/ComfyUI` to `3d/moge-top-down`, preserving mesh and both normal-preview branches; graph change and desired-outcome judge required. | Low-level 3D output parameter edit and multi-branch integrity. |

The 35 research/explain/diagnose descriptors received semantic answer rubrics
without changing their original queries or source workflows, so they remain
`matched`. The two non-product smoke scenarios were marked as health controls;
that classification change is not a query rewrite.
