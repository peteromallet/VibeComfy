# vibecomfy: generated
# Review candidate: generated from the native UI graph; edit `build(...)` inputs.
# vibecomfy: surface=canonical
"""Reviewable Python projection of the MiniMax H3 native UI workflow.

Source: ``MiniMax_H3_AV_EncodeDecode_Inpaint.json`` (native subgraph expanded
to 24 source nodes / 28 links before executable projection).  This file is a
Python graph builder, not a GPU result.  The unresolved schema items are kept
in ``READY_METADATA.provenance['unresolved_schema']``; validation/runtime
installation must not be inferred from this review artifact.
"""
from __future__ import annotations

from vibecomfy.templates import InputSpec, ReadyMetadata, new_workflow, node as raw_call
from vibecomfy.workflow import VibeWorkflow
from vibecomfy.nodes.core import BasicGuider, BasicScheduler, CLIPLoader, ComfyMathExpression, KSamplerSelect, PrimitiveFloat, PrimitiveInt, RandomNoise, ResolutionSelector, SaveVideo, UNETLoader, VAELoader


AUDIO_VAE_NAME = 'minimax_h3_audio_vae_fp32.safetensors'
CLIP_NAME = 'qwen3vl_32b_minimax_h3_int8_convrot.safetensors'
DEFAULT_PROMPT = 'PRIESTESS OF THE BLUE HOUR — Dance Music Video\n\nHigh-end 2D anime cinematic look, dance music-video style — delicate, refined hand-drawn animation: fine precise linework with elegant variation in line weight, soft watercolor and airbrush shading instead of hard cel shadows, subtle gradient tints across skin and fabric, gentle film grain, volumetric haze, anamorphic framing, shallow depth of field. The palette is restrained and premium: deep blue-hour dusk, muted neon accents, and the dancer\'s warm white-and-gold as the only saturated warmth. Evoking the delicate hand-drawn elegance of Makoto Shinkai\'s character work and KyoAni\'s refined, graceful linework — never crude, never exaggerated. This is the centerpiece dance sequence of an anime music video: each motion is emotional, fluid, alive.\n\nScene overview: at blue-hour dusk on an empty rain-wet plaza between glowing towers, the dancer moves alone, choreography building from stillness to explosive, every move landing on the musical beats. Her long blonde hair catches the wind; her white-and-gold priestess vestments — layered robes with gold trim, church embroidery, a small pendant at her neck — flare and settle with each motion. Beside her, a cute toy bear — soft plush, glass-button eyes, stitched paws — floats gently, emitting a faint golden glow and a trail of tiny twinkling stars and light particles that drift and spin in the air, catching the neon light like miniature fireflies, reweaving into a halo orbit as she moves. No transformation, no destruction — just her, her dance, the bear, and the city\'s glow.\n\nCharacter design: slender, graceful proportions; a refined, gentle face with soft features and a serene, slightly devout expression — eyes half-lidded, calm; long blonde hair rendered strand by strand, flowing and luminous; her signature white-and-gold priestess outfit drawn with fine elegant lines, layers of cloth that lift and settle beautifully in motion.\n\n0s–1.5s Shot 1 — The Stillness — wide shot: the dancer stands motionless at the center of the plaza, eyes closed, wind catching her hair and the hem of her robes, city lights and mist behind her. The toy bear floats at her side, its button eyes glowing softly, a warm radiance pulsing from its little chest, and a ring of golden sparkles circles it slowly. Behind her, the towers shimmer with neon; the wet pavement mirrors the sky. She breathes — the bear\'s glow flickers gently.\n\n1s–2.5s Shot 2 — The Unfolding — she begins to move: a slow arm extension turning into a spin, long hair sweeping through the air. Her robes flare with the rotation, white cloth catching the blue light, gold trim tracing glowing arcs; the floating sparkles and starlight spiral with her like a comet of tiny lights, one cluster passing close to the camera, its warm glints reflecting in the bear\'s glassy eyes. She opens her eyes — serene, focused — as she completes the turn. Neon light trails and passing cars streak softly behind her, a slight slow-motion feel.\n\n2.5s–4s Shot 3 — The Leap — fast footwork into a leaping turn, body stretching mid-air, robes and hair streaming upward like wings, the halo of golden particles exploding outward and reforming as she twists, the toy bear tumbling playfully through the air alongside her. Wet pavement reflections flash below, softly blurred; the city\'s glow blooms around her silhouette as she soars through the frame. The motion is fluid, weightless, precise — every beat landing.\n\n4s–5s Shot 4 — The Landing — freeze: she lands softly, the momentum settling through her body, robes settling around her, the sparkling lights returning to the bear, which floats down and nestles gently at her side. She strikes the final pose — one arm extended, palm open, head tilted, eyes lowered, a quiet smile. Her lips part and she whispers, "I am the hour." — silhouette against the glowing city, the last tiny star drifting down past her face, holding. Only the shimmer of heat and city light in the air, and the bear\'s soft glow fading.\n\nCamera: each shot its own angle, cuts clean and hard, no dissolves — precise cuts on the beat with a slight, elegant frame jitter on each accent hit; soft lens bloom where the sparkles catch the light; the golden glow of the bear as a secondary light source alongside the blue-hour dusk, warm highlights tracing her profile and the edges of her robes.\n\nAudio: a restrained, atmospheric score — wind, distant city ambience, footsteps on wet pavement, a soft tinkling chime accompanying the bear\'s sparkles on each accent beat, low strings and piano underneath, an accent hit on each beat, the score bursting at 4s as she lands, closing the final 1s in near-silence with only the wind, her breathing, her soft whisper fading, and the faint rustle of plush fur settling.\n\nNo text, subtitles, logos or watermarks of any kind, no 3D-CG or cel-shaded video-game look, no photorealism, no rough or crude linework — keep the delicate hand-drawn 2D anime texture with fine, elegant lines throughout.'
UNET_NAME = 'minimax_h3_fl2va_pruned_fp8_scaled.safetensors'
VIDEO_VAE_NAME = 'minimax_h3_video_vae_fp16.safetensors'
SOURCE_VIDEO = 'Masked_LoadMe.mp4'
MASK_KEYFRAMES = '{"0":"lanpaint_kf_1786525157475_0.png","41":"lanpaint_kf_1786525157475_41.png","42":"lanpaint_kf_1786525157475_42.png","56":"lanpaint_kf_1786525157475_56.png","64":"lanpaint_kf_1786525157475_64.png","65":"lanpaint_kf_1786525157475_65.png","66":"lanpaint_kf_1786525157475_66.png","70":"lanpaint_kf_1786525157475_70.png","78":"lanpaint_kf_1786525157475_78.png","82":"lanpaint_kf_1786525157475_82.png","83":"lanpaint_kf_1786525157475_83.png","86":"lanpaint_kf_1786525157475_86.png","87":"lanpaint_kf_1786525157475_87.png","88":"lanpaint_kf_1786525157475_88.png","89":"lanpaint_kf_1786525157475_89.png","92":"lanpaint_kf_1786525157475_92.png","98":"lanpaint_kf_1786525157475_98.png","106":"lanpaint_kf_1786525157475_106.png","112":"lanpaint_kf_1786525157475_112.png","115":"lanpaint_kf_1786525157475_115.png","116":"lanpaint_kf_1786525157475_116.png","117":"lanpaint_kf_1786525157475_117.png","121":"lanpaint_kf_1786525157475_121.png","122":"lanpaint_kf_1786525157475_122.png","123":"lanpaint_kf_1786525157475_123.png"}'
AUDIO_INTERVALS = '[{"start":3.7479933970546644,"end":5.161482918309433}]'


PUBLIC_INPUT_METADATA = {
    'model': InputSpec(node='105::6', field='unet_name', default=UNET_NAME),
    'steps': InputSpec(node='105::9', field='steps', default=20),
    'prompt': InputSpec(node='105::104', field='prompt', default=DEFAULT_PROMPT),
    'duration': InputSpec(node='105::111', field='value', default=5),
    'seed': InputSpec(node='171', field='value', default=0),
    'lp_steps': InputSpec(node='105::159', field='LanPaint_NumSteps', default=5),
}

READY_METADATA = ReadyMetadata.build(
    capability='video',
    template_id='MiniMax_H3_AV_EncodeDecode_Inpaint',
    inputs=PUBLIC_INPUT_METADATA,
    requirements={'models': ['minimax_h3_audio_vae_fp32.safetensors', 'minimax_h3_fl2va_pruned_fp8_scaled.safetensors', 'minimax_h3_video_vae_fp16.safetensors', 'qwen3vl_32b_minimax_h3_int8_convrot.safetensors']},
    _native_subgraph_provenance={'source_sha256': 'bdd3dc3b8ada880291418a622778e6e0bac2072ecf93064898f0cacdbe295715', 'source_kind': 'comfyui_native_subgraph'},
    _native_subgraph_diagnostics=[{'kind': 'repaired_output_backlink', 'link_id': 199, 'node_id': '107', 'slot': 1}, {'kind': 'expanded_native_subgraph', 'instance_id': '105', 'definition': 'Image to Video (MiniMax H3)'}],
    provenance={'source': 'MiniMax_H3_AV_EncodeDecode_Inpaint.json', 'source_kind': 'comfyui_native_subgraph', 'source_sha256': 'bdd3dc3b8ada880291418a622778e6e0bac2072ecf93064898f0cacdbe295715', 'native_expansion': '24 nodes / 28 links', 'diagnostics': [{'kind': 'repaired_output_backlink', 'link_id': 199, 'node_id': '107', 'slot': 1}, {'kind': 'expanded_native_subgraph', 'instance_id': '105', 'definition': 'Image to Video (MiniMax H3)'}], 'unresolved_schema': ['MiniMaxH3ImageToVideo (ComfyUI core PR #15224)', 'CLIPLoader enum minimax (current stale schema cache)']},
)

def build(*, model=UNET_NAME, steps=20, prompt=DEFAULT_PROMPT, duration=5,
          seed=0, lp_steps=5, source_video=SOURCE_VIDEO,
          mask_keyframes=MASK_KEYFRAMES, audio_intervals=AUDIO_INTERVALS) -> VibeWorkflow:
    """Build an editable H3 graph with the named controls exposed as keywords."""
    wf = new_workflow(READY_METADATA, source_path=__file__)

    # Outputs
    savevideo = SaveVideo(
        _id='92',
        filename_prefix='video/MiniMax_H3',
        format='auto',
        codec='auto',
        video=['105::168', 0],
        _uid='92',
        _native_ports={'native_input_names': ['video'], 'native_output_names': ['video'], 'native_input_types': ['VIDEO'], 'native_output_types': ['VIDEO'], 'native_input_optional': [False], 'native_input_asset_kinds': None, 'native_output_slots': None},
    )

    width, height = ResolutionSelector(
        _id='115',
        aspect_ratio='16:9 (Widescreen)',
        megapixels=0.4,
        multiple=32,
        _uid='115',
        _native_ports={'native_input_names': [], 'native_output_names': ['width', 'height'], 'native_input_types': [], 'native_output_types': ['INT', 'INT'], 'native_input_optional': [], 'native_input_asset_kinds': None, 'native_output_slots': None},
    )

    lanpaint_videomaskeditor = raw_call('LanPaint_VideoMaskEditor', '164',
        video='Masked_LoadMe.mp4',
        keyframes='{"0":"lanpaint_kf_1786525157475_0.png","41":"lanpaint_kf_1786525157475_41.png","42":"lanpaint_kf_1786525157475_42.png","56":"lanpaint_kf_1786525157475_56.png","64":"lanpaint_kf_1786525157475_64.png","65":"lanpaint_kf_1786525157475_65.png","66":"lanpaint_kf_1786525157475_66.png","70":"lanpaint_kf_1786525157475_70.png","78":"lanpaint_kf_1786525157475_78.png","82":"lanpaint_kf_1786525157475_82.png","83":"lanpaint_kf_1786525157475_83.png","86":"lanpaint_kf_1786525157475_86.png","87":"lanpaint_kf_1786525157475_87.png","88":"lanpaint_kf_1786525157475_88.png","89":"lanpaint_kf_1786525157475_89.png","92":"lanpaint_kf_1786525157475_92.png","98":"lanpaint_kf_1786525157475_98.png","106":"lanpaint_kf_1786525157475_106.png","112":"lanpaint_kf_1786525157475_112.png","115":"lanpaint_kf_1786525157475_115.png","116":"lanpaint_kf_1786525157475_116.png","117":"lanpaint_kf_1786525157475_117.png","121":"lanpaint_kf_1786525157475_121.png","122":"lanpaint_kf_1786525157475_122.png","123":"lanpaint_kf_1786525157475_123.png"}',
        audio_mask='[{"start":3.7479933970546644,"end":5.161482918309433}]',
        _uid='164',
        _native_ports={'native_input_names': [], 'native_output_names': ['video', 'mask', 'audio_mask'], 'native_input_types': [], 'native_output_types': ['VIDEO', 'MASK', 'MASK'], 'native_input_optional': [], 'native_input_asset_kinds': None, 'native_output_slots': None},
    )

    # Inputs
    primitiveint = PrimitiveInt(
        _id='171',
        value=0,
        control_after_generate='fixed',
        _uid='171',
        _native_ports={'native_input_names': [], 'native_output_names': ['INT'], 'native_input_types': [], 'native_output_types': ['INT'], 'native_input_optional': [], 'native_input_asset_kinds': None, 'native_output_slots': None},
    )

    ComfyMathExpression(
        _id='105::107',
        expression='max(5, round(a * 24)) + (5 - (max(5, round(a * 24)) % 17)) % 17',
        _uid='105::107',
        _native_ports={'native_input_names': ['values.a', 'values.b'], 'native_output_names': ['FLOAT', 'INT', 'BOOL'], 'native_input_types': ['FLOAT,INT,BOOLEAN', 'FLOAT,INT,BOOLEAN'], 'native_output_types': ['FLOAT', 'INT', 'BOOLEAN'], 'native_input_optional': [False, True], 'native_input_asset_kinds': None, 'native_output_slots': None},
        **{'values.a': ['105::111', 0]},
    )

    # Loaders
    vaeloader = VAELoader(
        _id='105::11',
        vae_name=VIDEO_VAE_NAME,
        _uid='105::11',
        _native_ports={'native_input_names': ['vae_name'], 'native_output_names': ['VAE'], 'native_input_types': ['COMBO'], 'native_output_types': ['VAE'], 'native_input_optional': [False], 'native_input_asset_kinds': None, 'native_output_slots': None},
    )

    primitivefloat = PrimitiveFloat(
        _id='105::111',
        value=5,
        _uid='105::111',
        _native_ports={'native_input_names': ['value'], 'native_output_names': ['FLOAT'], 'native_input_types': ['FLOAT'], 'native_output_types': ['FLOAT'], 'native_input_optional': [False], 'native_input_asset_kinds': None, 'native_output_slots': None},
    )

    cliploader = CLIPLoader(
        _id='105::13',
        clip_name=CLIP_NAME,
        type='minimax',
        device='default',
        _uid='105::13',
        _native_ports={'native_input_names': ['clip_name'], 'native_output_names': ['CLIP'], 'native_input_types': ['COMBO'], 'native_output_types': ['CLIP'], 'native_input_optional': [False], 'native_input_asset_kinds': None, 'native_output_slots': None},
    )

    reroute = raw_call('Reroute', '105::146',
        _un257=['105::11', 0],
        _uid='105::146',
        _native_ports={'native_input_names': [None], 'native_output_names': [None], 'native_input_types': ['*'], 'native_output_types': ['VAE'], 'native_input_optional': [False], 'native_input_asset_kinds': None, 'native_output_slots': None},
    )

    reroute_2 = raw_call('Reroute', '105::148',
        _un260=['105::24', 0],
        _uid='105::148',
        _native_ports={'native_input_names': [None], 'native_output_names': [None], 'native_input_types': ['*'], 'native_output_types': ['VAE'], 'native_input_optional': [False], 'native_input_asset_kinds': None, 'native_output_slots': None},
    )

    lanpaint_samplercustomadvanced = raw_call('LanPaint_SamplerCustomAdvanced', '105::159',
        LanPaint_NumSteps=5,
        LanPaint_Lambda=5,
        LanPaint_StepSize=0.2,
        LanPaint_PromptMode='Image First',
        LanPaint_Info='LanPaint Custom Sampler Adv.',
        guider=['105::16', 0],
        latent_image=['105::166', 0],
        noise=['105::15', 0],
        sampler=['105::17', 0],
        sigmas=['105::9', 0],
        _uid='105::159',
        _native_ports={'native_input_names': ['noise', 'guider', 'sampler', 'sigmas', 'latent_image', 'LanPaint_NumSteps'], 'native_output_names': ['output', 'denoised_output'], 'native_input_types': ['NOISE', 'GUIDER', 'SAMPLER', 'SIGMAS', 'LATENT', 'INT'], 'native_output_types': ['LATENT', 'LATENT'], 'native_input_optional': [False, False, False, False, False, False], 'native_input_asset_kinds': None, 'native_output_slots': None},
    )

    basicguider = BasicGuider(
        _id='105::16',
        conditioning=['105::104', 0],
        model=['105::6', 0],
        _uid='105::16',
        _native_ports={'native_input_names': ['model', 'conditioning'], 'native_output_names': ['GUIDER'], 'native_input_types': ['MODEL', 'CONDITIONING'], 'native_output_types': ['GUIDER'], 'native_input_optional': [False, False], 'native_input_asset_kinds': None, 'native_output_slots': None},
    )

    # Sampling
    ksamplerselect = KSamplerSelect(
        _id='105::17',
        sampler_name='euler',
        _uid='105::17',
        _native_ports={'native_input_names': [], 'native_output_names': ['SAMPLER'], 'native_input_types': [], 'native_output_types': ['SAMPLER'], 'native_input_optional': [], 'native_input_asset_kinds': None, 'native_output_slots': None},
    )

    vaeloader_2 = VAELoader(
        _id='105::24',
        vae_name=AUDIO_VAE_NAME,
        _uid='105::24',
        _native_ports={'native_input_names': ['vae_name'], 'native_output_names': ['VAE'], 'native_input_types': ['COMBO'], 'native_output_types': ['VAE'], 'native_input_optional': [False], 'native_input_asset_kinds': None, 'native_output_slots': None},
    )

    unetloader = UNETLoader(
        _id='105::6',
        unet_name=UNET_NAME,
        weight_dtype='default',
        _uid='105::6',
        _native_ports={'native_input_names': ['unet_name'], 'native_output_names': ['MODEL'], 'native_input_types': ['COMBO'], 'native_output_types': ['MODEL'], 'native_input_optional': [False], 'native_input_asset_kinds': None, 'native_output_slots': None},
    )

    basicscheduler = BasicScheduler(
        _id='105::9',
        scheduler='simple',
        steps=20,
        denoise=1,
        model=['105::6', 0],
        _uid='105::9',
        _native_ports={'native_input_names': ['model'], 'native_output_names': ['SIGMAS'], 'native_input_types': ['MODEL'], 'native_output_types': ['SIGMAS'], 'native_input_optional': [False], 'native_input_asset_kinds': None, 'native_output_slots': None},
    )

    minimaxh3imagetovideo = raw_call('MiniMaxH3ImageToVideo', '105::104',
        clip=['105::13', 0],
        length=['105::107', 1],
        prompt=DEFAULT_PROMPT,
        vae=['105::11', 0],
        widget_1=1344,
        widget_2=768,
        widget_3=73,
        _uid='105::104',
        _native_ports={'native_input_names': ['clip', 'vae', 'first_frame', 'last_frame', 'prompt', 'width', 'height', 'length'], 'native_output_names': ['positive', 'LATENT'], 'native_input_types': ['CLIP', 'VAE', 'IMAGE', 'IMAGE', 'STRING', 'INT', 'INT', 'INT'], 'native_output_types': ['CONDITIONING', 'LATENT'], 'native_input_optional': [False, False, True, True, False, False, False, False], 'native_input_asset_kinds': None, 'native_output_slots': None},
    )

    randomnoise = RandomNoise(
        _id='105::15',
        control_after_generate='randomize',
        _uid='105::15',
        _native_ports={'native_input_names': ['noise_seed'], 'native_output_names': ['NOISE'], 'native_input_types': ['INT'], 'native_output_types': ['NOISE'], 'native_input_optional': [False], 'native_input_asset_kinds': None, 'native_output_slots': None},
    )

    lanpaint_avencode = raw_call('LanPaint_AVEncode', '105::166',
        audio_vae=['105::148', 0],
        vae=['105::146', 0],
        _uid='105::166',
        _native_ports={'native_input_names': ['video', 'vae', 'audio_vae', 'mask', 'audio_mask'], 'native_output_names': ['latent'], 'native_input_types': ['VIDEO', 'VAE', 'VAE', 'MASK', 'MASK'], 'native_output_types': ['LATENT'], 'native_input_optional': [False, False, False, False, False], 'native_input_asset_kinds': None, 'native_output_slots': None},
    )

    lanpaint_avdecode = raw_call('LanPaint_AVDecode', '105::168',
        audio_vae=['105::148', 0],
        samples=['105::159', 0],
        vae=['105::146', 0],
        blend_overlap=7,
        audio_crossfade=0.02,
        _uid='105::168',
        _native_ports={'native_input_names': ['samples', 'video', 'vae', 'audio_vae', 'mask', 'audio_mask'], 'native_output_names': ['video', 'audio'], 'native_input_types': ['LATENT', 'VIDEO', 'VAE', 'VAE', 'MASK', 'MASK'], 'native_output_types': ['VIDEO', 'AUDIO'], 'native_input_optional': [False, False, False, False, False, False], 'native_input_asset_kinds': None, 'native_output_slots': None},
    )

    wf.connect('115.0', '105::104.width')
    wf.connect('115.1', '105::104.height')
    wf.connect('171.0', '105::15.noise_seed')
    wf.connect('164.0', '105::166.video')
    wf.connect('164.1', '105::166.mask')
    wf.connect('164.2', '105::166.audio_mask')
    wf.connect('164.0', '105::168.video')
    wf.connect('164.1', '105::168.mask')
    wf.connect('164.2', '105::168.audio_mask')
    wf = wf.finalize(PUBLIC_INPUT_METADATA, output_node=savevideo, output_type='SaveVideo', name='video', artifact_kind='video', mime_type='video/mp4', expected_cardinality='one', filename_prefix='video/MiniMax_H3')
    wf.nodes['105::104'].inputs = {'clip': ['105::13', 0], 'vae': ['105::11', 0], 'length': ['105::107', 1], 'prompt': 'PRIESTESS OF THE BLUE HOUR — Dance Music Video\n\nHigh-end 2D anime cinematic look, dance music-video style — delicate, refined hand-drawn animation: fine precise linework with elegant variation in line weight, soft watercolor and airbrush shading instead of hard cel shadows, subtle gradient tints across skin and fabric, gentle film grain, volumetric haze, anamorphic framing, shallow depth of field. The palette is restrained and premium: deep blue-hour dusk, muted neon accents, and the dancer\'s warm white-and-gold as the only saturated warmth. Evoking the delicate hand-drawn elegance of Makoto Shinkai\'s character work and KyoAni\'s refined, graceful linework — never crude, never exaggerated. This is the centerpiece dance sequence of an anime music video: each motion is emotional, fluid, alive.\n\nScene overview: at blue-hour dusk on an empty rain-wet plaza between glowing towers, the dancer moves alone, choreography building from stillness to explosive, every move landing on the musical beats. Her long blonde hair catches the wind; her white-and-gold priestess vestments — layered robes with gold trim, church embroidery, a small pendant at her neck — flare and settle with each motion. Beside her, a cute toy bear — soft plush, glass-button eyes, stitched paws — floats gently, emitting a faint golden glow and a trail of tiny twinkling stars and light particles that drift and spin in the air, catching the neon light like miniature fireflies, reweaving into a halo orbit as she moves. No transformation, no destruction — just her, her dance, the bear, and the city\'s glow.\n\nCharacter design: slender, graceful proportions; a refined, gentle face with soft features and a serene, slightly devout expression — eyes half-lidded, calm; long blonde hair rendered strand by strand, flowing and luminous; her signature white-and-gold priestess outfit drawn with fine elegant lines, layers of cloth that lift and settle beautifully in motion.\n\n0s–1.5s Shot 1 — The Stillness — wide shot: the dancer stands motionless at the center of the plaza, eyes closed, wind catching her hair and the hem of her robes, city lights and mist behind her. The toy bear floats at her side, its button eyes glowing softly, a warm radiance pulsing from its little chest, and a ring of golden sparkles circles it slowly. Behind her, the towers shimmer with neon; the wet pavement mirrors the sky. She breathes — the bear\'s glow flickers gently.\n\n1s–2.5s Shot 2 — The Unfolding — she begins to move: a slow arm extension turning into a spin, long hair sweeping through the air. Her robes flare with the rotation, white cloth catching the blue light, gold trim tracing glowing arcs; the floating sparkles and starlight spiral with her like a comet of tiny lights, one cluster passing close to the camera, its warm glints reflecting in the bear\'s glassy eyes. She opens her eyes — serene, focused — as she completes the turn. Neon light trails and passing cars streak softly behind her, a slight slow-motion feel.\n\n2.5s–4s Shot 3 — The Leap — fast footwork into a leaping turn, body stretching mid-air, robes and hair streaming upward like wings, the halo of golden particles exploding outward and reforming as she twists, the toy bear tumbling playfully through the air alongside her. Wet pavement reflections flash below, softly blurred; the city\'s glow blooms around her silhouette as she soars through the frame. The motion is fluid, weightless, precise — every beat landing.\n\n4s–5s Shot 4 — The Landing — freeze: she lands softly, the momentum settling through her body, robes settling around her, the sparkling lights returning to the bear, which floats down and nestles gently at her side. She strikes the final pose — one arm extended, palm open, head tilted, eyes lowered, a quiet smile. Her lips part and she whispers, "I am the hour." — silhouette against the glowing city, the last tiny star drifting down past her face, holding. Only the shimmer of heat and city light in the air, and the bear\'s soft glow fading.\n\nCamera: each shot its own angle, cuts clean and hard, no dissolves — precise cuts on the beat with a slight, elegant frame jitter on each accent hit; soft lens bloom where the sparkles catch the light; the golden glow of the bear as a secondary light source alongside the blue-hour dusk, warm highlights tracing her profile and the edges of her robes.\n\nAudio: a restrained, atmospheric score — wind, distant city ambience, footsteps on wet pavement, a soft tinkling chime accompanying the bear\'s sparkles on each accent beat, low strings and piano underneath, an accent hit on each beat, the score bursting at 4s as she lands, closing the final 1s in near-silence with only the wind, her breathing, her soft whisper fading, and the faint rustle of plush fur settling.\n\nNo text, subtitles, logos or watermarks of any kind, no 3D-CG or cel-shaded video-game look, no photorealism, no rough or crude linework — keep the delicate hand-drawn 2D anime texture with fine, elegant lines throughout.'}
    wf.nodes['105::104'].widgets = {}
    wf.nodes['105::104'].metadata = {'schema_source': {'provider': 'ComfyUI core source', 'path': 'https://github.com/Comfy-Org/ComfyUI/blob/master/comfy_extras/nodes_minimax_h3.py', 'cache_path': None, 'server_url': None, 'package': 'comfy_core', 'version': 'master', 'hash': None, 'confidence': 0.95}, 'provenance': 'official_source', 'keep_defaults': ['prompt', 'width', 'height', 'length']}
    wf.nodes['105::104'].native_input_names = ['clip', 'vae', 'first_frame', 'last_frame', 'prompt', 'width', 'height', 'length']
    wf.nodes['105::104'].native_output_names = ['positive', 'LATENT']
    wf.nodes['105::104'].native_input_types = ['CLIP', 'VAE', 'IMAGE', 'IMAGE', 'STRING', 'INT', 'INT', 'INT']
    wf.nodes['105::104'].native_output_types = ['CONDITIONING', 'LATENT']
    wf.nodes['105::104'].native_input_optional = [False, False, True, True, False, False, False, False]
    wf.nodes['105::104'].native_input_asset_kinds = None
    wf.nodes['105::104'].native_output_slots = None
    wf.nodes['105::107'].inputs = {'values.a': ['105::111', 0], 'expression': 'max(5, round(a * 24)) + (5 - (max(5, round(a * 24)) % 17)) % 17'}
    wf.nodes['105::107'].widgets = {}
    wf.nodes['105::107'].metadata = {'schema_source': {'provider': '', 'path': None, 'cache_path': None, 'server_url': None, 'package': None, 'version': None, 'hash': None, 'confidence': 0.0}, 'provenance': 'untrusted_source', 'keep_defaults': ['expression']}
    wf.nodes['105::107'].native_input_names = ['values.a', 'values.b']
    wf.nodes['105::107'].native_output_names = ['FLOAT', 'INT', 'BOOL']
    wf.nodes['105::107'].native_input_types = ['FLOAT,INT,BOOLEAN', 'FLOAT,INT,BOOLEAN']
    wf.nodes['105::107'].native_output_types = ['FLOAT', 'INT', 'BOOLEAN']
    wf.nodes['105::107'].native_input_optional = [False, True]
    wf.nodes['105::107'].native_input_asset_kinds = None
    wf.nodes['105::107'].native_output_slots = None
    wf.nodes['105::11'].inputs = {'vae_name': 'minimax_h3_video_vae_fp16.safetensors'}
    wf.nodes['105::11'].widgets = {}
    wf.nodes['105::11'].metadata = {'schema_source': {'provider': '', 'path': None, 'cache_path': None, 'server_url': None, 'package': None, 'version': None, 'hash': None, 'confidence': 0.0}, 'provenance': 'untrusted_source', 'keep_defaults': ['vae_name']}
    wf.nodes['105::11'].native_input_names = ['vae_name']
    wf.nodes['105::11'].native_output_names = ['VAE']
    wf.nodes['105::11'].native_input_types = ['COMBO']
    wf.nodes['105::11'].native_output_types = ['VAE']
    wf.nodes['105::11'].native_input_optional = [False]
    wf.nodes['105::11'].native_input_asset_kinds = None
    wf.nodes['105::11'].native_output_slots = None
    wf.nodes['105::111'].inputs = {'value': 5}
    wf.nodes['105::111'].widgets = {}
    wf.nodes['105::111'].metadata = {'schema_source': {'provider': '', 'path': None, 'cache_path': None, 'server_url': None, 'package': None, 'version': None, 'hash': None, 'confidence': 0.0}, 'provenance': 'untrusted_source', 'keep_defaults': ['value']}
    wf.nodes['105::111'].native_input_names = ['value']
    wf.nodes['105::111'].native_output_names = ['FLOAT']
    wf.nodes['105::111'].native_input_types = ['FLOAT']
    wf.nodes['105::111'].native_output_types = ['FLOAT']
    wf.nodes['105::111'].native_input_optional = [False]
    wf.nodes['105::111'].native_input_asset_kinds = None
    wf.nodes['105::111'].native_output_slots = None
    wf.nodes['105::13'].inputs = {'clip_name': 'qwen3vl_32b_minimax_h3_int8_convrot.safetensors', 'type': 'minimax', 'device': 'default'}
    wf.nodes['105::13'].widgets = {}
    wf.nodes['105::13'].metadata = {'schema_source': {'provider': '', 'path': None, 'cache_path': None, 'server_url': None, 'package': None, 'version': None, 'hash': None, 'confidence': 0.0}, 'provenance': 'untrusted_source', 'keep_defaults': ['clip_name', 'device', 'type']}
    wf.nodes['105::13'].native_input_names = ['clip_name']
    wf.nodes['105::13'].native_output_names = ['CLIP']
    wf.nodes['105::13'].native_input_types = ['COMBO']
    wf.nodes['105::13'].native_output_types = ['CLIP']
    wf.nodes['105::13'].native_input_optional = [False]
    wf.nodes['105::13'].native_input_asset_kinds = None
    wf.nodes['105::13'].native_output_slots = None
    wf.nodes['105::146'].inputs = {'_un257': ['105::11', 0]}
    wf.nodes['105::146'].widgets = {}
    wf.nodes['105::146'].metadata = {'schema_source': {'provider': '', 'path': None, 'cache_path': None, 'server_url': None, 'package': None, 'version': None, 'hash': None, 'confidence': 0.0}, 'provenance': 'untrusted_source'}
    wf.nodes['105::146'].native_input_names = ['_un257']
    wf.nodes['105::146'].native_output_names = [None]
    wf.nodes['105::146'].native_input_types = ['*']
    wf.nodes['105::146'].native_output_types = ['VAE']
    wf.nodes['105::146'].native_input_optional = [False]
    wf.nodes['105::146'].native_input_asset_kinds = None
    wf.nodes['105::146'].native_output_slots = None
    wf.nodes['105::148'].inputs = {'_un260': ['105::24', 0]}
    wf.nodes['105::148'].widgets = {}
    wf.nodes['105::148'].metadata = {'schema_source': {'provider': '', 'path': None, 'cache_path': None, 'server_url': None, 'package': None, 'version': None, 'hash': None, 'confidence': 0.0}, 'provenance': 'untrusted_source'}
    wf.nodes['105::148'].native_input_names = ['_un260']
    wf.nodes['105::148'].native_output_names = [None]
    wf.nodes['105::148'].native_input_types = ['*']
    wf.nodes['105::148'].native_output_types = ['VAE']
    wf.nodes['105::148'].native_input_optional = [False]
    wf.nodes['105::148'].native_input_asset_kinds = None
    wf.nodes['105::148'].native_output_slots = None
    wf.nodes['105::15'].inputs = {'control_after_generate': 'randomize'}
    wf.nodes['105::15'].widgets = {}
    wf.nodes['105::15'].metadata = {'schema_source': {'provider': '', 'path': None, 'cache_path': None, 'server_url': None, 'package': None, 'version': None, 'hash': None, 'confidence': 0.0}, 'provenance': 'untrusted_source', 'keep_defaults': ['control_after_generate']}
    wf.nodes['105::15'].native_input_names = ['noise_seed']
    wf.nodes['105::15'].native_output_names = ['NOISE']
    wf.nodes['105::15'].native_input_types = ['INT']
    wf.nodes['105::15'].native_output_types = ['NOISE']
    wf.nodes['105::15'].native_input_optional = [False]
    wf.nodes['105::15'].native_input_asset_kinds = None
    wf.nodes['105::15'].native_output_slots = None
    wf.nodes['105::159'].inputs = {'noise': ['105::15', 0], 'guider': ['105::16', 0], 'sampler': ['105::17', 0], 'sigmas': ['105::9', 0], 'latent_image': ['105::166', 0], 'LanPaint_NumSteps': 5, 'LanPaint_Lambda': 5, 'LanPaint_StepSize': 0.2, 'LanPaint_PromptMode': 'Image First', 'LanPaint_Info': 'LanPaint Custom Sampler Adv.', 'unused_widget_5': 'lanpaint_star_button'}
    wf.nodes['105::159'].widgets = {}
    wf.nodes['105::159'].metadata = {'schema_source': {'provider': '', 'path': None, 'cache_path': None, 'server_url': None, 'package': None, 'version': None, 'hash': None, 'confidence': 0.0}, 'provenance': 'untrusted_source', 'keep_defaults': ['LanPaint_Info', 'LanPaint_Lambda', 'LanPaint_NumSteps', 'LanPaint_PromptMode', 'LanPaint_StepSize', 'unused_widget_5']}
    wf.nodes['105::159'].native_input_names = ['noise', 'guider', 'sampler', 'sigmas', 'latent_image', 'LanPaint_NumSteps']
    wf.nodes['105::159'].native_output_names = ['output', 'denoised_output']
    wf.nodes['105::159'].native_input_types = ['NOISE', 'GUIDER', 'SAMPLER', 'SIGMAS', 'LATENT', 'INT']
    wf.nodes['105::159'].native_output_types = ['LATENT', 'LATENT']
    wf.nodes['105::159'].native_input_optional = [False, False, False, False, False, False]
    wf.nodes['105::159'].native_input_asset_kinds = None
    wf.nodes['105::159'].native_output_slots = None
    wf.nodes['105::16'].inputs = {'model': ['105::6', 0], 'conditioning': ['105::104', 0]}
    wf.nodes['105::16'].widgets = {}
    wf.nodes['105::16'].metadata = {'schema_source': {'provider': '', 'path': None, 'cache_path': None, 'server_url': None, 'package': None, 'version': None, 'hash': None, 'confidence': 0.0}, 'provenance': 'untrusted_source'}
    wf.nodes['105::16'].native_input_names = ['model', 'conditioning']
    wf.nodes['105::16'].native_output_names = ['GUIDER']
    wf.nodes['105::16'].native_input_types = ['MODEL', 'CONDITIONING']
    wf.nodes['105::16'].native_output_types = ['GUIDER']
    wf.nodes['105::16'].native_input_optional = [False, False]
    wf.nodes['105::16'].native_input_asset_kinds = None
    wf.nodes['105::16'].native_output_slots = None
    wf.nodes['105::166'].inputs = {'vae': ['105::146', 0], 'audio_vae': ['105::148', 0]}
    wf.nodes['105::166'].widgets = {}
    wf.nodes['105::166'].metadata = {'schema_source': {'provider': '', 'path': None, 'cache_path': None, 'server_url': None, 'package': None, 'version': None, 'hash': None, 'confidence': 0.0}, 'provenance': 'untrusted_source'}
    wf.nodes['105::166'].native_input_names = ['video', 'vae', 'audio_vae', 'mask', 'audio_mask']
    wf.nodes['105::166'].native_output_names = ['latent']
    wf.nodes['105::166'].native_input_types = ['VIDEO', 'VAE', 'VAE', 'MASK', 'MASK']
    wf.nodes['105::166'].native_output_types = ['LATENT']
    wf.nodes['105::166'].native_input_optional = [False, False, False, False, False]
    wf.nodes['105::166'].native_input_asset_kinds = None
    wf.nodes['105::166'].native_output_slots = None
    wf.nodes['105::168'].inputs = {'samples': ['105::159', 0], 'vae': ['105::146', 0], 'audio_vae': ['105::148', 0]}
    wf.nodes['105::168'].widgets = {}
    wf.nodes['105::168'].metadata = {'schema_source': {'provider': 'LanPaint source', 'path': 'https://github.com/scraed/LanPaint/blob/master/src/LanPaint/nodes.py', 'cache_path': None, 'server_url': None, 'package': 'LanPaint', 'version': 'master', 'hash': None, 'confidence': 0.95}, 'provenance': 'official_source', 'keep_defaults': ['blend_overlap', 'audio_crossfade']}
    wf.nodes['105::168'].native_input_names = ['samples', 'video', 'vae', 'audio_vae', 'mask', 'audio_mask']
    wf.nodes['105::168'].native_output_names = ['video', 'audio']
    wf.nodes['105::168'].native_input_types = ['LATENT', 'VIDEO', 'VAE', 'VAE', 'MASK', 'MASK']
    wf.nodes['105::168'].native_output_types = ['VIDEO', 'AUDIO']
    wf.nodes['105::168'].native_input_optional = [False, False, False, False, False, False]
    wf.nodes['105::168'].native_input_asset_kinds = None
    wf.nodes['105::168'].native_output_slots = None
    wf.nodes['105::17'].inputs = {'sampler_name': 'euler'}
    wf.nodes['105::17'].widgets = {}
    wf.nodes['105::17'].metadata = {'schema_source': {'provider': '', 'path': None, 'cache_path': None, 'server_url': None, 'package': None, 'version': None, 'hash': None, 'confidence': 0.0}, 'provenance': 'untrusted_source', 'keep_defaults': ['sampler_name']}
    wf.nodes['105::17'].native_input_names = []
    wf.nodes['105::17'].native_output_names = ['SAMPLER']
    wf.nodes['105::17'].native_input_types = []
    wf.nodes['105::17'].native_output_types = ['SAMPLER']
    wf.nodes['105::17'].native_input_optional = []
    wf.nodes['105::17'].native_input_asset_kinds = None
    wf.nodes['105::17'].native_output_slots = None
    wf.nodes['105::24'].inputs = {'vae_name': 'minimax_h3_audio_vae_fp32.safetensors'}
    wf.nodes['105::24'].widgets = {}
    wf.nodes['105::24'].metadata = {'schema_source': {'provider': '', 'path': None, 'cache_path': None, 'server_url': None, 'package': None, 'version': None, 'hash': None, 'confidence': 0.0}, 'provenance': 'untrusted_source', 'keep_defaults': ['vae_name']}
    wf.nodes['105::24'].native_input_names = ['vae_name']
    wf.nodes['105::24'].native_output_names = ['VAE']
    wf.nodes['105::24'].native_input_types = ['COMBO']
    wf.nodes['105::24'].native_output_types = ['VAE']
    wf.nodes['105::24'].native_input_optional = [False]
    wf.nodes['105::24'].native_input_asset_kinds = None
    wf.nodes['105::24'].native_output_slots = None
    wf.nodes['105::6'].inputs = {'unet_name': 'minimax_h3_fl2va_pruned_fp8_scaled.safetensors', 'weight_dtype': 'default'}
    wf.nodes['105::6'].widgets = {}
    wf.nodes['105::6'].metadata = {'schema_source': {'provider': '', 'path': None, 'cache_path': None, 'server_url': None, 'package': None, 'version': None, 'hash': None, 'confidence': 0.0}, 'provenance': 'untrusted_source', 'keep_defaults': ['unet_name', 'weight_dtype']}
    wf.nodes['105::6'].native_input_names = ['unet_name']
    wf.nodes['105::6'].native_output_names = ['MODEL']
    wf.nodes['105::6'].native_input_types = ['COMBO']
    wf.nodes['105::6'].native_output_types = ['MODEL']
    wf.nodes['105::6'].native_input_optional = [False]
    wf.nodes['105::6'].native_input_asset_kinds = None
    wf.nodes['105::6'].native_output_slots = None
    wf.nodes['105::9'].inputs = {'model': ['105::6', 0], 'scheduler': 'simple', 'steps': 20, 'denoise': 1}
    wf.nodes['105::9'].widgets = {}
    wf.nodes['105::9'].metadata = {'schema_source': {'provider': '', 'path': None, 'cache_path': None, 'server_url': None, 'package': None, 'version': None, 'hash': None, 'confidence': 0.0}, 'provenance': 'untrusted_source', 'keep_defaults': ['denoise', 'scheduler', 'steps']}
    wf.nodes['105::9'].native_input_names = ['model']
    wf.nodes['105::9'].native_output_names = ['SIGMAS']
    wf.nodes['105::9'].native_input_types = ['MODEL']
    wf.nodes['105::9'].native_output_types = ['SIGMAS']
    wf.nodes['105::9'].native_input_optional = [False]
    wf.nodes['105::9'].native_input_asset_kinds = None
    wf.nodes['105::9'].native_output_slots = None
    wf.nodes['115'].inputs = {'aspect_ratio': '16:9 (Widescreen)', 'megapixels': 0.4, 'multiple': 32}
    wf.nodes['115'].widgets = {}
    wf.nodes['115'].metadata = {'schema_source': {'provider': '', 'path': None, 'cache_path': None, 'server_url': None, 'package': None, 'version': None, 'hash': None, 'confidence': 0.0}, 'provenance': 'untrusted_source', 'keep_defaults': ['aspect_ratio', 'megapixels', 'multiple']}
    wf.nodes['115'].native_input_names = []
    wf.nodes['115'].native_output_names = ['width', 'height']
    wf.nodes['115'].native_input_types = []
    wf.nodes['115'].native_output_types = ['INT', 'INT']
    wf.nodes['115'].native_input_optional = []
    wf.nodes['115'].native_input_asset_kinds = None
    wf.nodes['115'].native_output_slots = None
    wf.nodes['164'].inputs = {'video': 'Masked_LoadMe.mp4', 'keyframes': '{"0":"lanpaint_kf_1786525157475_0.png","41":"lanpaint_kf_1786525157475_41.png","42":"lanpaint_kf_1786525157475_42.png","56":"lanpaint_kf_1786525157475_56.png","64":"lanpaint_kf_1786525157475_64.png","65":"lanpaint_kf_1786525157475_65.png","66":"lanpaint_kf_1786525157475_66.png","70":"lanpaint_kf_1786525157475_70.png","78":"lanpaint_kf_1786525157475_78.png","82":"lanpaint_kf_1786525157475_82.png","83":"lanpaint_kf_1786525157475_83.png","86":"lanpaint_kf_1786525157475_86.png","87":"lanpaint_kf_1786525157475_87.png","88":"lanpaint_kf_1786525157475_88.png","89":"lanpaint_kf_1786525157475_89.png","92":"lanpaint_kf_1786525157475_92.png","98":"lanpaint_kf_1786525157475_98.png","106":"lanpaint_kf_1786525157475_106.png","112":"lanpaint_kf_1786525157475_112.png","115":"lanpaint_kf_1786525157475_115.png","116":"lanpaint_kf_1786525157475_116.png","117":"lanpaint_kf_1786525157475_117.png","121":"lanpaint_kf_1786525157475_121.png","122":"lanpaint_kf_1786525157475_122.png","123":"lanpaint_kf_1786525157475_123.png"}', 'audio_mask': '[{"start":3.7479933970546644,"end":5.161482918309433}]'}
    wf.nodes['164'].widgets = {}
    wf.nodes['164'].metadata = {'schema_source': {'provider': 'LanPaint source', 'path': 'https://github.com/scraed/LanPaint/blob/master/src/LanPaint/nodes.py', 'cache_path': None, 'server_url': None, 'package': 'LanPaint', 'version': 'master', 'hash': None, 'confidence': 0.95}, 'provenance': 'official_source', 'keep_defaults': ['video', 'keyframes', 'audio_mask']}
    wf.nodes['164'].native_input_names = []
    wf.nodes['164'].native_output_names = ['video', 'mask', 'audio_mask']
    wf.nodes['164'].native_input_types = []
    wf.nodes['164'].native_output_types = ['VIDEO', 'MASK', 'MASK']
    wf.nodes['164'].native_input_optional = []
    wf.nodes['164'].native_input_asset_kinds = None
    wf.nodes['164'].native_output_slots = None
    wf.nodes['171'].inputs = {'value': 0}
    wf.nodes['171'].widgets = {'widget_1': 'fixed'}
    wf.nodes['171'].metadata = {'schema_source': {'provider': '', 'path': None, 'cache_path': None, 'server_url': None, 'package': None, 'version': None, 'hash': None, 'confidence': 0.0}, 'provenance': 'untrusted_source', 'keep_defaults': ['value', 'widget_1']}
    wf.nodes['171'].native_input_names = []
    wf.nodes['171'].native_output_names = ['INT']
    wf.nodes['171'].native_input_types = []
    wf.nodes['171'].native_output_types = ['INT']
    wf.nodes['171'].native_input_optional = []
    wf.nodes['171'].native_input_asset_kinds = None
    wf.nodes['171'].native_output_slots = None
    wf.nodes['92'].inputs = {'video': ['105::168', 0], 'filename_prefix': 'video/MiniMax_H3', 'format': 'auto', 'codec': 'auto'}
    wf.nodes['92'].widgets = {}
    wf.nodes['92'].metadata = {'schema_source': {'provider': '', 'path': None, 'cache_path': None, 'server_url': None, 'package': None, 'version': None, 'hash': None, 'confidence': 0.0}, 'provenance': 'untrusted_source', 'keep_defaults': ['codec', 'filename_prefix', 'format']}
    wf.nodes['92'].native_input_names = ['video']
    wf.nodes['92'].native_output_names = ['video']
    wf.nodes['92'].native_input_types = ['VIDEO']
    wf.nodes['92'].native_output_types = ['VIDEO']
    wf.nodes['92'].native_input_optional = [False]
    wf.nodes['92'].native_input_asset_kinds = None
    wf.nodes['92'].native_output_slots = None
    wf.inputs.clear()
    wf.register_input('model', '105::6', 'unet_name', 'minimax_h3_fl2va_pruned_fp8_scaled.safetensors', type=None, default=None, required=False, range=None, aliases=(), media_semantics=None, allow_missing_target=False)
    wf.inputs['model'].default = None
    wf.register_input('steps', '105::9', 'steps', 20, type=None, default=None, required=False, range=None, aliases=(), media_semantics=None, allow_missing_target=False)
    wf.inputs['steps'].default = None
    public_output_0 = wf.outputs[0]
    wf.outputs.clear()
    public_output_0.output_type = 'SaveVideo'
    public_output_0.name = None
    public_output_0.artifact_kind = None
    public_output_0.mime_type = None
    public_output_0.filename_prefix = None
    public_output_0.expected_cardinality = None
    wf.outputs.append(public_output_0)
    wf.requirements.models = ['minimax_h3_audio_vae_fp32.safetensors', 'minimax_h3_fl2va_pruned_fp8_scaled.safetensors', 'minimax_h3_video_vae_fp16.safetensors', 'qwen3vl_32b_minimax_h3_int8_convrot.safetensors']
    wf.requirements.custom_nodes = []
    wf.requirements.missing_models = []
    wf.requirements.missing_nodes = ['BasicGuider', 'BasicScheduler', 'CLIPLoader', 'ComfyMathExpression', 'KSamplerSelect', 'LanPaint_AVDecode', 'LanPaint_AVEncode', 'LanPaint_SamplerCustomAdvanced', 'LanPaint_VideoMaskEditor', 'MarkdownNote', 'MiniMaxH3ImageToVideo', 'PrimitiveFloat', 'PrimitiveInt', 'RandomNoise', 'Reroute', 'ResolutionSelector', 'SaveVideo', 'UNETLoader', 'VAELoader']
    wf.requirements.unsupported = []
    wf.strict_types = False
    # The emitter restores source semantics above. Apply the public controls
    # last so changing a build argument cannot be silently overwritten.
    wf.nodes['105::6'].inputs['unet_name'] = model
    wf.nodes['105::9'].inputs['steps'] = steps
    wf.nodes['105::104'].inputs['prompt'] = prompt
    wf.nodes['105::111'].inputs['value'] = duration
    wf.nodes['171'].inputs['value'] = seed
    wf.nodes['105::159'].inputs['LanPaint_NumSteps'] = lp_steps
    wf.nodes['164'].inputs.update({'video': source_video, 'keyframes': mask_keyframes, 'audio_mask': audio_intervals})
    for name, node_id, field, value in (
        ('model', '105::6', 'unet_name', model),
        ('steps', '105::9', 'steps', steps),
        ('prompt', '105::104', 'prompt', prompt),
        ('duration', '105::111', 'value', duration),
        ('seed', '171', 'value', seed),
        ('lp_steps', '105::159', 'LanPaint_NumSteps', lp_steps),
        ('source_video', '164', 'video', source_video),
        ('mask_keyframes', '164', 'keyframes', mask_keyframes),
        ('audio_intervals', '164', 'audio_mask', audio_intervals),
    ):
        wf.register_input(name, node_id, field, value, type=None, default=value,
                          required=False, range=None, aliases=(), media_semantics=None,
                          allow_missing_target=False)
    return wf
