# H3 current-main baseline

This is planning/baseline evidence, not completion proof.

- Base: `20975e25f0401b64f51dfeef5d1250cfbd97600f`
- Input: `assets/h3/MiniMax_H3_AV_EncodeDecode_Inpaint.json`
- Input SHA-256: `2dd64fe26c42281962e434841c458cc935b1d1858e83093b882bbaeb02dc3121`
- Result: `port check` and `port convert` failed closed; no fresh Python was written.
- Blocking facts: unresolved `MiniMaxH3ImageToVideo`, unavailable CLIP `minimax` enum, and unresolved H3/LanPaint schema inputs.
- Raw JSON `inspect`/`analyze` refused because canonical Python authority is required.
- Runtime doctor reported embedded/managed `not_ready` and external `unverified`.
- No tests, installs, schema provisioning, model downloads, server/provider/GPU calls, or source edits were part of the baseline.

The existing committed-main H3 builder is only a comparison artifact and must not be presented as fresh conversion evidence or as proof of E1/E2.

Upstream source: [LanPaint MiniMax H3 AV inpainting workflow](https://github.com/scraed/LanPaint/blob/32cf848e93971da380d868936e007f5611218bee/example_workflows/MiniMax_H3_AV_EncodeDecode_Inpaint.json). The exact included bytes are bound by the input hash above. The existing main builder is at `comfy-inspection/MiniMax_H3_AV_EncodeDecode_Inpaint.py` in the project; it is not substituted for the failed conversion.
