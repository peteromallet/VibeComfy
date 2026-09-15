# MiniMax H3 continuation via latent masking

The checked-in source workflow is `ready_templates/sources/custom_nodes/ComfyUI-H3-Motion-Context-MultiRef/seitanism/minimax_h3_av_extension.json`. It is the Update 9 `NEW - AV Extension` example from [seitanism/ComfyUI-H3-Motion-Context-MultiRef](https://github.com/seitanism/ComfyUI-H3-Motion-Context-MultiRef), pinned to commit `361624fb406b63eb6694442eac6c895fc1533a70`.

This graph starts from a 24 fps source or H3 starter clip, encodes audiovisual context in H3 latent space, and uses `MiniMaxH3StartMaskedContext` for the first extension and `MiniMaxH3GeneratedAVMaskedContext` for later extensions. The protected prefix is copied into the target latent with a zero denoise mask; only the new tail is generated. The controller/streamer trims the protected overlap and assembles the final audiovisual output.

## Working defaults

- 24 fps constant-frame-rate input/output.
- 39 video frames of context (the shared H3 video/audio boundary).
- 8 audio feather ticks (about 0.2 s) at the end of the overlap; the rest of the overlap stays protected.
- H3 `ref2va` model for reference mode; keep references for identity/appearance, not as a substitute for latent continuation.
- Start around 0.9995 fractional V2V strength when using the separate granular V2V path; keep `BasicScheduler` denoise at 1.0.
- Describe the previous clip's ending first in every continuation prompt, hold the established state for a beat, then introduce the next action.
- Lock the seed while tuning joins, use longer 10–15 s segments, and expect visible drift/burn after roughly 30–45 s of chained generation.

## Hivemind evidence

The current `minimax_h3_chatter` discussion repeatedly distinguishes latent masking from guide/reference conditioning:

- [JalenBrunson: 39-frame overlap](https://discord.com/channels/1076117621407223829/1532625331960152124/1548624100464005173) and [39 overlap with only the last 5 frames anchored](https://discord.com/channels/1076117621407223829/1532625331960152124/1548626512138342406).
- [Lumifel: insert the previous video directly into the generated latent with masking](https://discord.com/channels/1076117621407223829/1532625331960152124/1549390138289684512).
- [Nacho.money: latent-space continuation avoids VAE decode/encode degradation and retains motion](https://discord.com/channels/1076117621407223829/1532625331960152124/1548638989395697697), with the [VAE degradation warning](https://discord.com/channels/1076117621407223829/1532625331960152124/1548634947781132311).
- [Blake37: Context Loop is nearly imperceptible to about 30 s, with burn becoming noticeable around 45 s](https://discord.com/channels/1076117621407223829/1532625331960152124/1548610228084547606).

The exact author name “cyclism” did not occur in the live search; the matching continuation discussion is the channel/thread linked above. The resource row for the RuneX updated masking workflow is [Hivemind workflow 3743](https://discord.com/channels/1076117621407223829/1533923760984555875/1542497501897166868). A second community graph with explicit chain planning is [Hivemind workflow 4018](https://raw.githubusercontent.com/ethanfel/ComfyUI-MiniMaxH3-Context-Loop/main/example_workflows/Masked%20Video%20Inpaint%20-%20MiniMax%20H3.json).

## VibeComfy status

The source is preserved as import evidence. It remains `source_only` because this checkout has no committed object-info captures for the Update 9 custom classes and no URL-bearing registry entries for the third-party H3 weights. Import it into the canonical editable bundle with:

```bash
vibecomfy import ready_templates/sources/custom_nodes/ComfyUI-H3-Motion-Context-MultiRef/seitanism/minimax_h3_av_extension.json \
  --out workflows/minimax_h3_av_extension --json
```

Strict-ready promotion should happen after those schemas and model provenance are captured; the raw graph is already preserved and reproducible from the pinned upstream commit.
