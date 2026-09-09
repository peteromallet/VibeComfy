# H3 schema and widget fixes

The H3 source was checked against `/tmp/h3-port-check.json`. The three owned
schema/widget failures were caused by stale or incomplete authoring metadata:

- `ResolutionSelector` now records the official `multiple` advanced control as
  `widget_2` (the preview row has no serialized value slot).
- `LanPaint_SamplerCustomAdvanced` now records its five named controls plus a
  final `None` slot for the serialized star-button UI action. The action is
  retained for positional alignment and is never emitted as a runtime input.
- `ComfyMathExpression` now treats `values.a`/`values.b` and so on as the
  declared `values` auto-grow input. A populated dotted value satisfies the
  controller's required row, while dotted fields are accepted only for this
  class and shape.

The changes are in `vibecomfy/_compile/_widgets.py` and
`vibecomfy/schema/validate.py`; the historical object-info cache entries were
left unchanged. Focused coverage is in `tests/test_h3_schema_widgets.py`.

The generated H3 Python surface also uses named controls for
`MiniMaxH3ImageToVideo` (`prompt`, `width`, `height`, `length`),
`LanPaint_VideoMaskEditor` (`video`, `keyframes`, `audio_mask`), and
`LanPaint_AVDecode` (`blend_overlap`, `audio_crossfade`). Evidence is the
official ComfyUI source at
`https://github.com/Comfy-Org/ComfyUI/blob/master/comfy_extras/nodes_minimax_h3.py`
and LanPaint source at
`https://github.com/scraed/LanPaint/blob/master/src/LanPaint/nodes.py`.

Validation: `pytest -q tests/test_h3_schema_widgets.py tests/test_schema.py`
was run; the focused tests passed while the broader schema suite was still
running in the shared worktree. No native-subgraph or normalization files were
edited by this fix.
