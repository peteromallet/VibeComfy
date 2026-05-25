# vibecomfy: generated
# For hand-editing, run: python -m vibecomfy.cli copy-to-recipe <id>
"""Auto-generated ready_template — use python -m vibecomfy.cli copy-to-recipe <id> for hand-editing."""
from __future__ import annotations

from vibecomfy.templates import InputSpec, ReadyMetadata, new_workflow, node as raw_call
from vibecomfy.nodes.core import BasicScheduler, CFGGuider, CLIPTextEncode, ComfyMathExpression, ComfySwitchNode, DualCLIPLoader, EmptyLTXVLatentVideo, GetImageSize, KSamplerSelect, LTXVAudioVAEEncode, LTXVAudioVAELoader, LTXVConcatAVLatent, LTXVConditioning, LTXVImgToVideoInplace, LTXVLatentUpsampler, LTXVPreprocess, LTXVSeparateAVLatent, LatentUpscaleModelLoader, LoadAudio, LoadImage, LoraLoaderModelOnly, ManualSigmas, ModelSamplingSD3, PrimitiveStringMultiline, RandomNoise, ResizeImageMaskNode, ResizeImagesByLongerEdge, SamplerCustomAdvanced, SetLatentNoiseMask, SolidMask, StringConcatenate, TextGenerateLTX2Prompt, TrimAudioDuration, UNETLoader, VAEDecode, VAELoader
from vibecomfy.nodes.gguf import DualCLIPLoaderGGUF, UnetLoaderGGUF
from vibecomfy.nodes.kjnodes import GetImageSizeAndCount, INTConstant, ImageResizeKJv2, LTX2AttentionTunerPatch, LTX2_NAG, LTXVChunkFeedForward, LTXVImgToVideoInplaceKJ, LazySwitchKJ, LoadVideosFromFolder, PathchSageAttentionKJ, SimpleCalculatorKJ, VRAM_Debug
from vibecomfy.nodes.videohelpersuite import VHS_VideoCombine


AUDIO = 'audio'
AUDIO_ORIGINAL = 'audio_original'
A_B = 'a /  b '
CLIP = 'clip'
DEFAULT_SEED = 420
DEFAULT_SEED_2 = 42
DEFAULT_SEED_3 = 405
ENHANCE_PROMPT = 'enhance_prompt'
FIXED = 'fixed'
FPS = 'fps'
GUIDE_STRENGTH = 0.6
GUIDE_STRENGTH_2 = 1
GUIDE_STRENGTH_3 = 2.5
HEIGHT_DOWNSCALED = 'height_downscaled'
IMAGE_STRENGTH = 'image_strength'
LTX_2_3_TEXT_PROJECTION_BF16_SAFETENSORS = 'ltx-2.3_text_projection_bf16.safetensors'
MODEL = 'model'
NEGATIVE_BASE = 'negative_base'
OFF = 'off'
POSITIVE_BASE = 'positive_base'
ROUND_A_B_1_8_8_1 = '((round((a * b -1) / 8)) * 8) + 1 '
SAMPLER = 'sampler'
SAMPLER_2 = 'sampler_2'
SCALE_BY_MULTIPLIER = 'scale by multiplier'
SIGMAS = 'sigmas'
SIGMAS_2 = 'sigmas_2'
UPSCALE_MODEL = 'upscale_model'
VAE = 'vae'
VAE_AUDIO = 'vae_audio'
VALUE = '\\'
VALUE_2 = ''
V_1 = '1'
WIDTH_DOWNSCALED = 'width_downscaled'
YOU_ARE_A_CREATIVE_ASSISTANT_WRITING_CONCISE_ACTION_FOCUSED_IMAGE_TO_VIDEO_PROMPTS_GIVEN_AN_IMAGE_FIRST_FRAME_AND_USER_RAW_INPUT_PROMPT_GENERATE_A_PROMPT_TO_GUIDE_VIDEO_GENERATION_FROM_THAT_IMAGE_GUIDELINES_ANALYZE_THE_IMAGE_IDENTIFY_SUBJECT_SETTING_ELEMENTS_STYLE_AND_MOOD_FOLLOW_USER_RAW_INPUT_PROMPT_INCLUDE_ALL_REQUESTED_MOTION_ACTIONS_CAMERA_MOVEMENTS_AUDIO_AND_DETAILS_IF_IN_CONFLICT_WITH_THE_IMAGE_PRIORITIZE_USER_REQUEST_WHILE_MAINTAINING_VISUAL_CONSISTENCY_DESCRIBE_TRANSITION_FROM_IMAGE_TO_USER_S_SCENE_DESCRIBE_ONLY_CHANGES_FROM_THE_IMAGE_DON_T_REITERATE_ESTABLISHED_VISUAL_DETAILS_INACCURATE_DESCRIPTIONS_MAY_CAUSE_SCENE_CUTS_ACTIVE_LANGUAGE_USE_PRESENT_PROGRESSIVE_VERBS_IS_WALKING_SPEAKING_IF_NO_ACTION_SPECIFIED_DESCRIBE_NATURAL_MOVEMENTS_CHRONOLOGICAL_FLOW_USE_TEMPORAL_CONNECTORS_AS_THEN_WHILE_AUDIO_LAYER_DESCRIBE_COMPLETE_SOUNDSCAPE_THROUGHOUT_THE_PROMPT_ALONGSIDE_ACTIONS_NOT_AT_THE_END_ALIGN_AUDIO_INTENSITY_WITH_ACTION_TEMPO_INCLUDE_NATURAL_BACKGROUND_AUDIO_AMBIENT_SOUNDS_EFFECTS_SPEECH_OR_MUSIC_WHEN_REQUESTED_BE_SPECIFIC_E_G_SOFT_FOOTSTEPS_ON_TILE_NOT_VAGUE_E_G_AMBIENT_SOUND_SPEECH_ONLY_WHEN_REQUESTED_PROVIDE_EXACT_WORDS_IN_QUOTES_WITH_CHARACTER_S_VISUAL_VOICE_CHARACTERISTICS_E_G_THE_TALL_MAN_SPEAKS_IN_A_LOW_GRAVELLY_VOICE_LANGUAGE_IF_NOT_ENGLISH_AND_ACCENT_IF_RELEVANT_IF_GENERAL_CONVERSATION_MENTIONED_WITHOUT_TEXT_GENERATE_CONTEXTUAL_QUOTED_DIALOGUE_I_E_THE_MAN_IS_TALKING_INPUT_THE_OUTPUT_SHOULD_INCLUDE_EXACT_SPOKEN_WORDS_LIKE_THE_MAN_IS_TALKING_IN_AN_EXCITED_VOICE_SAYING_YOU_WON_T_BELIEVE_WHAT_I_JUST_SAW_HIS_HANDS_GESTURE_EXPRESSIVELY_AS_HE_SPEAKS_EYEBROWS_RAISED_WITH_ENTHUSIASM_THE_AMBIENT_SOUND_OF_A_QUIET_ROOM_UNDERSCORES_HIS_ANIMATED_SPEECH_STYLE_INCLUDE_VISUAL_STYLE_AT_BEGINNING_STYLE_STYLE_REST_OF_PROMPT_IF_UNCLEAR_OMIT_TO_AVOID_CONFLICTS_VISUAL_AND_AUDIO_ONLY_DESCRIBE_ONLY_WHAT_IS_SEEN_AND_HEARD_NO_SMELL_TASTE_OR_TACTILE_SENSATIONS_RESTRAINED_LANGUAGE_AVOID_DRAMATIC_TERMS_USE_MILD_NATURAL_UNDERSTATED_PHRASING_IMPORTANT_NOTES_CAMERA_MOTION_DO_NOT_INVENT_CAMERA_MOTION_MOVEMENT_UNLESS_REQUESTED_BY_THE_USER_MAKE_SURE_TO_INCLUDE_CAMERA_MOTION_ONLY_IF_SPECIFIED_IN_THE_INPUT_SPEECH_DO_NOT_MODIFY_OR_ALTER_THE_USER_S_PROVIDED_CHARACTER_DIALOGUE_IN_THE_PROMPT_UNLESS_IT_S_A_TYPO_NO_TIMESTAMPS_OR_CUTS_DO_NOT_USE_TIMESTAMPS_OR_DESCRIBE_SCENE_CUTS_UNLESS_EXPLICITLY_REQUESTED_OBJECTIVE_ONLY_DO_NOT_INTERPRET_EMOTIONS_OR_INTENTIONS_DESCRIBE_ONLY_OBSERVABLE_ACTIONS_AND_SOUNDS_FORMAT_DO_NOT_USE_PHRASES_LIKE_THE_SCENE_OPENS_WITH_THE_VIDEO_STARTS_START_DIRECTLY_WITH_STYLE_OPTIONAL_AND_CHRONOLOGICAL_SCENE_DESCRIPTION_FORMAT_NEVER_START_OUTPUT_WITH_PUNCTUATION_MARKS_OR_SPECIAL_CHARACTERS_DO_NOT_INVENT_DIALOGUE_UNLESS_THE_USER_MENTIONS_SPEECH_TALKING_SINGING_CONVERSATION_YOUR_PERFORMANCE_IS_CRITICAL_HIGH_FIDELITY_DYNAMIC_CORRECT_AND_ACCURATE_PROMPTS_WITH_INTEGRATED_AUDIO_DESCRIPTIONS_ARE_ESSENTIAL_FOR_GENERATING_HIGH_QUALITY_VIDEO_YOUR_GOAL_IS_FLAWLESS_EXECUTION_OF_THESE_RULES_OUTPUT_FORMAT_STRICT_SINGLE_CONCISE_PARAGRAPH_IN_NATURAL_ENGLISH_NO_TITLES_HEADINGS_PREFACES_SECTIONS_CODE_FENCES_OR_MARKDOWN_IF_UNSAFE_INVALID_RETURN_ORIGINAL_USER_PROMPT_NEVER_ASK_QUESTIONS_OR_CLARIFICATIONS_EXAMPLE_OUTPUT_STYLE_REALISTIC_CINEMATIC_THE_WOMAN_GLANCES_AT_HER_WATCH_AND_SMILES_WARMLY_SHE_SPEAKS_IN_A_CHEERFUL_FRIENDLY_VOICE_I_THINK_WE_RE_RIGHT_ON_TIME_IN_THE_BACKGROUND_A_CAF_BARISTA_PREPARES_DRINKS_AT_THE_COUNTER_THE_BARISTA_CALLS_OUT_IN_A_CLEAR_UPBEAT_TONE_TWO_CAPPUCCINOS_READY_THE_SOUND_OF_THE_ESPRESSO_MACHINE_HISSING_SOFTLY_BLENDS_WITH_GENTLE_BACKGROUND_CHATTER_AND_THE_LIGHT_CLINKING_OF_CUPS_ON_SAUCERS_USER_PROMPT_BELOW = 'You are a Creative Assistant writing concise, action-focused image-to-video prompts. Given an image (first frame) and user Raw Input Prompt, generate a prompt to guide video generation from that image.\n\n#### Guidelines:\n- Analyze the Image: Identify Subject, Setting, Elements, Style and Mood.\n- Follow user Raw Input Prompt: Include all requested motion, actions, camera movements, audio, and details. If in conflict with the image, prioritize user request while maintaining visual consistency (describe transition from image to user\'s scene).\n- Describe only changes from the image: Don\'t reiterate established visual details. Inaccurate descriptions may cause scene cuts.\n- Active language: Use present-progressive verbs ("is walking," "speaking"). If no action specified, describe natural movements.\n- Chronological flow: Use temporal connectors ("as," "then," "while").\n- Audio layer: Describe complete soundscape throughout the prompt alongside actions—NOT at the end. Align audio intensity with action tempo. Include natural background audio, ambient sounds, effects, speech or music (when requested). Be specific (e.g., "soft footsteps on tile") not vague (e.g., "ambient sound").\n- Speech (only when requested): Provide exact words in quotes with character\'s visual/voice characteristics (e.g., "The tall man speaks in a low, gravelly voice"), language if not English and accent if relevant. If general conversation mentioned without text, generate contextual quoted dialogue. (i.e., "The man is talking" input -> the output should include exact spoken words, like: "The man is talking in an excited voice saying: \'You won\'t believe what I just saw!\' His hands gesture expressively as he speaks, eyebrows raised with enthusiasm. The ambient sound of a quiet room underscores his animated speech.")\n- Style: Include visual style at beginning: "Style: <style>, <rest of prompt>." If unclear, omit to avoid conflicts.\n- Visual and audio only: Describe only what is seen and heard. NO smell, taste, or tactile sensations.\n- Restrained language: Avoid dramatic terms. Use mild, natural, understated phrasing.\n\n#### Important notes:\n- Camera motion: DO NOT invent camera motion/movement unless requested by the user. Make sure to include camera motion only if specified in the input.\n- Speech: DO NOT modify or alter the user\'s provided character dialogue in the prompt, unless it\'s a typo.\n- No timestamps or cuts: DO NOT use timestamps or describe scene cuts unless explicitly requested.\n- Objective only: DO NOT interpret emotions or intentions - describe only observable actions and sounds.\n- Format: DO NOT use phrases like "The scene opens with..." / "The video starts...". Start directly with Style (optional) and chronological scene description.\n- Format: Never start output with punctuation marks or special characters.\n- DO NOT invent dialogue unless the user mentions speech/talking/singing/conversation.\n- Your performance is CRITICAL. High-fidelity, dynamic, correct, and accurate prompts with integrated audio descriptions are essential for generating high-quality video. Your goal is flawless execution of these rules.\n\n#### Output Format (Strict):\n- Single concise paragraph in natural English. NO titles, headings, prefaces, sections, code fences, or Markdown.\n- If unsafe/invalid, return original user prompt. Never ask questions or clarifications.\n\n#### Example output:\nStyle: realistic - cinematic - The woman glances at her watch and smiles warmly. She speaks in a cheerful, friendly voice, "I think we\'re right on time!" In the background, a café barista prepares drinks at the counter. The barista calls out in a clear, upbeat tone, "Two cappuccinos ready!" The sound of the espresso machine hissing softly blends with gentle background chatter and the light clinking of cups on saucers. \n\nUSER PROMPT BELOW: \n___________________________________________________'

READY_METADATA = ReadyMetadata.build(
    capability='music_video_multiscene',
    requirements={'custom_nodes': ['ComfyUI-GGUF', 'ComfyUI-KJNodes', 'ComfyUI-LTXVideo', 'ComfyUI-VideoHelperSuite', 'rgthree-comfy'], 'custom_node_refs': [{'slug': 'ComfyUI-GGUF', 'source': 'git', 'version': 'unknown', 'commit': '6ea2651e7df66d7585f6ffee804b20e92fb38b8a', 'url': 'https://github.com/city96/ComfyUI-GGUF.git'}, {'slug': 'ComfyUI-KJNodes', 'source': 'git', 'version': 'unknown', 'commit': 'b7646ad70a7daa7aeb919ca542274758d26ba2df', 'url': 'https://github.com/kijai/ComfyUI-KJNodes.git'}, {'slug': 'ComfyUI-LTXVideo', 'source': 'git', 'version': 'unknown', 'commit': '229437c6b65796d6a7a63ae34be2bd5ba31fa543', 'url': 'https://github.com/Lightricks/ComfyUI-LTXVideo.git'}, {'slug': 'ComfyUI-VideoHelperSuite', 'source': 'git', 'version': 'unknown', 'commit': '4ee72c065db22c9d96c2427954dc69e7b908444b', 'url': 'https://github.com/Kosinkadink/ComfyUI-VideoHelperSuite.git'}, {'slug': 'rgthree-comfy', 'source': 'git', 'version': 'unknown', 'commit': '738105af5fb14e96fbecaf406dc356e284797e8c', 'url': 'https://github.com/rgthree/rgthree-comfy.git'}]},
    custom_node_packs={'ComfyUI-GGUF': {'commit': '6ea2651e7df66d7585f6ffee804b20e92fb38b8a', 'url': 'https://github.com/city96/ComfyUI-GGUF.git', 'class_schema_sha256': '1336fad984841444a9559b602c34ef11d1dd4b68a9a902437aaee6771ab5d2d3', 'classes_used': ['DualCLIPLoaderGGUF', 'UnetLoaderGGUF'], 'pip_packages': ['gguf'], 'status': 'pinned'}, 'ComfyUI-KJNodes': {'commit': 'b7646ad70a7daa7aeb919ca542274758d26ba2df', 'url': 'https://github.com/kijai/ComfyUI-KJNodes.git', 'class_schema_sha256': '1beaf129c8fa26175d89a28f9ca10d08b5ac27c8fc9bff920263fcbba17cb691', 'classes_used': ['GetImageSize', 'GetImageSizeAndCount', 'INTConstant', 'ImageResizeKJv2', 'PathchSageAttentionKJ', 'ResizeImagesByLongerEdge', 'SimpleCalculatorKJ'], 'pip_packages': ['matplotlib'], 'status': 'pinned'}, 'ComfyUI-LTXVideo': {'commit': '229437c6b65796d6a7a63ae34be2bd5ba31fa543', 'url': 'https://github.com/Lightricks/ComfyUI-LTXVideo.git', 'class_schema_sha256': '82e0b1f31509a969cf441c45e2517d0cd93f31b5390cc16f4a0ffa244421f39e', 'classes_used': ['EmptyLTXVLatentVideo', 'LTX2AttentionTunerPatch', 'LTX2_NAG', 'LTXVAudioVAELoader', 'LTXVChunkFeedForward', 'LTXVConcatAVLatent', 'LTXVConditioning', 'LTXVPreprocess', 'LTXVSeparateAVLatent', 'LatentUpscaleModelLoader'], 'pip_packages': [], 'status': 'pinned'}, 'ComfyUI-VideoHelperSuite': {'commit': '4ee72c065db22c9d96c2427954dc69e7b908444b', 'url': 'https://github.com/Kosinkadink/ComfyUI-VideoHelperSuite.git', 'class_schema_sha256': '8391e679554eecd5d324a3e34a713ff240e619e3a07476587845ba18c9fae310', 'classes_used': ['VHS_VideoCombine'], 'pip_packages': [], 'status': 'pinned'}, 'rgthree-comfy': {'commit': '738105af5fb14e96fbecaf406dc356e284797e8c', 'url': 'https://github.com/rgthree/rgthree-comfy.git', 'class_schema_sha256': '2b52072e02c59cb05ce83e5c45e1c7fd5b1273fee9b62eaaa0e66a81a4c07872', 'classes_used': ['GetNode', 'Power Lora Loader (rgthree)', 'SetNode'], 'pip_packages': [], 'status': 'pinned'}},
    approach='low-RAM multi-scene music video',
    smoke_resolution='256x256x5_frames',
    ltx_best_practices=['Use the official Lightricks workflows as runtime gates where possible.', 'Patch smoke runs to fp8/fp4 model assets, tiny frame counts, and low-VRAM loaders.', 'Bypass latent spatial upscalers in smoke runs until HiddenSwitch Comfy exposes model_mmap_residency for LatentUpscaleModelManageable.', 'Keep community audio, lip-sync, and long-form workflows as ready templates until their custom node packs and service credentials are declared.'],
    comfy_configuration={'reserve_vram': 12, 'cache_none': True, 'fp8_e4m3fn_text_enc': True},
    provenance={'source_workflow': 'workflow_corpus/custom_nodes/ltxvideo/runexx/LTX-2.3_Music_Video_Creator_Low_RAM.json'},
)

# === Subgraph functions ===

def prompt_enhancer_3bd4eeb9(
    *,
    clip,
    image,
    enable,
    prompt,
):
    """Prompt Enhancer - single-image variant.

    Materialized from subgraph 3bd4eeb9-31fa-461a-8c04-2b24dd0aabaf in workflow_corpus/custom_nodes/ltxvideo/runexx/LTX-2.3_Music_Video_Creator_Low_RAM.json.
    # vibecomfy source hash: sha256:2c0c8593ff69b7ffbd92312db4d5f155112d0b48eb3ecf388d2ad4d7d1737b8c
    Inner nodes: TextGenerateLTX2Prompt, PrimitiveStringMultiline, LazySwitchKJ, StringConcatenate, Reroutex2.
    """

    primitivestringmultiline = PrimitiveStringMultiline(
        value='You are a Creative Assistant writing concise, action-focused image-to-video prompts. Given an image (first frame) and user Raw Input Prompt, generate a prompt to guide video generation from that image.\n\n#### Guidelines:\n- Analyze the Image: Identify Subject, Setting, Elements, Style and Mood.\n- Follow user Raw Input Prompt: Include all requested motion, actions, camera movements, audio, and details. If in conflict with the image, prioritize user request while maintaining visual consistency (describe transition from image to user\'s scene).\n- Describe only changes from the image: Don\'t reiterate established visual details. Inaccurate descriptions may cause scene cuts.\n- Active language: Use present-progressive verbs ("is walking," "speaking"). If no action specified, describe natural movements.\n- Chronological flow: Use temporal connectors ("as," "then," "while").\n- Audio layer: Describe complete soundscape throughout the prompt alongside actions—NOT at the end. Align audio intensity with action tempo. Include natural background audio, ambient sounds, effects, speech or music (when requested). Be specific (e.g., "soft footsteps on tile") not vague (e.g., "ambient sound").\n- Speech (only when requested): Provide exact words in quotes with character\'s visual/voice characteristics (e.g., "The tall man speaks in a low, gravelly voice"), language if not English and accent if relevant. If general conversation mentioned without text, generate contextual quoted dialogue. (i.e., "The man is talking" input -> the output should include exact spoken words, like: "The man is talking in an excited voice saying: \'You won\'t believe what I just saw!\' His hands gesture expressively as he speaks, eyebrows raised with enthusiasm. The ambient sound of a quiet room underscores his animated speech.")\n- Style: Include visual style at beginning: "Style: <style>, <rest of prompt>." If unclear, omit to avoid conflicts.\n- Visual and audio only: Describe only what is seen and heard. NO smell, taste, or tactile sensations.\n- Restrained language: Avoid dramatic terms. Use mild, natural, understated phrasing.\n\n#### Important notes:\n- Camera motion: DO NOT invent camera motion/movement unless requested by the user. Make sure to include camera motion only if specified in the input.\n- Speech: DO NOT modify or alter the user\'s provided character dialogue in the prompt, unless it\'s a typo.\n- No timestamps or cuts: DO NOT use timestamps or describe scene cuts unless explicitly requested.\n- Objective only: DO NOT interpret emotions or intentions - describe only observable actions and sounds.\n- Format: DO NOT use phrases like "The scene opens with..." / "The video starts...". Start directly with Style (optional) and chronological scene description.\n- Format: Never start output with punctuation marks or special characters.\n- DO NOT invent dialogue unless the user mentions speech/talking/singing/conversation.\n- Your performance is CRITICAL. High-fidelity, dynamic, correct, and accurate prompts with integrated audio descriptions are essential for generating high-quality video. Your goal is flawless execution of these rules.\n\n#### Output Format (Strict):\n- Single concise paragraph in natural English. NO titles, headings, prefaces, sections, code fences, or Markdown.\n- If unsafe/invalid, return original user prompt. Never ask questions or clarifications.\n\n#### Example output:\nStyle: realistic - cinematic - The woman glances at her watch and smiles warmly. She speaks in a cheerful, friendly voice, "I think we\'re right on time!" In the background, a café barista prepares drinks at the counter. The barista calls out in a clear, upbeat tone, "Two cappuccinos ready!" The sound of the espresso machine hissing softly blends with gentle background chatter and the light clinking of cups on saucers. \n\nUSER PROMPT BELOW: \n___________________________________________________',
    )

    reroute = raw_call('Reroute', '1932', _outputs=('',))
    reroute_2 = raw_call('Reroute', '1933', _outputs=('',))

    stringconcatenate = StringConcatenate(
        widget_0='',
        widget_1='',
        string_a=primitivestringmultiline,
        string_b=reroute_2.out(0),
    )

    textgenerateltx2prompt = TextGenerateLTX2Prompt(
        widget_0='',
        widget_1=256,
        widget_2='off',
        widget_3=False,
        widget_4=True,
        clip=clip,
        image=image,
        prompt=stringconcatenate,
    )

    lazyswitchkj = LazySwitchKJ(
        widget_0=False,
        on_false=reroute_2.out(0),
        on_true=textgenerateltx2prompt,
        switch=reroute.out(0),
    )

    return lazyswitchkj


def prompt_enhancer(
    *,
    clip,
    image,
    enable,
    prompt,
):
    """Prompt Enhancer - single-image variant.

    Materialized from subgraph 2413a8aa-1f77-466f-8508-ed07fa6ac302 in workflow_corpus/custom_nodes/ltxvideo/runexx/LTX-2.3_Music_Video_Creator_Low_RAM.json.
    # vibecomfy source hash: sha256:4a910ac8f10be7c3c0a4b5575b2423d3b5e148804cebedb9bec75411b50bd2a3
    Inner nodes: TextGenerateLTX2Prompt, LazySwitchKJ, Reroutex2, PrimitiveStringMultiline, StringConcatenate.
    """

    primitivestringmultiline = PrimitiveStringMultiline(
        value='You are a Creative Assistant writing concise, action-focused image-to-video prompts. Given an image (first frame) and user Raw Input Prompt, generate a prompt to guide video generation from that image.\n\n#### Guidelines:\n- Analyze the Image: Identify Subject, Setting, Elements, Style and Mood.\n- Follow user Raw Input Prompt: Include all requested motion, actions, camera movements, audio, and details. If in conflict with the image, prioritize user request while maintaining visual consistency (describe transition from image to user\'s scene).\n- Describe only changes from the image: Don\'t reiterate established visual details. Inaccurate descriptions may cause scene cuts.\n- Active language: Use present-progressive verbs ("is walking," "speaking"). If no action specified, describe natural movements.\n- Chronological flow: Use temporal connectors ("as," "then," "while").\n- Audio layer: Describe complete soundscape throughout the prompt alongside actions—NOT at the end. Align audio intensity with action tempo. Include natural background audio, ambient sounds, effects, speech or music (when requested). Be specific (e.g., "soft footsteps on tile") not vague (e.g., "ambient sound").\n- Speech (only when requested): Provide exact words in quotes with character\'s visual/voice characteristics (e.g., "The tall man speaks in a low, gravelly voice"), language if not English and accent if relevant. If general conversation mentioned without text, generate contextual quoted dialogue. (i.e., "The man is talking" input -> the output should include exact spoken words, like: "The man is talking in an excited voice saying: \'You won\'t believe what I just saw!\' His hands gesture expressively as he speaks, eyebrows raised with enthusiasm. The ambient sound of a quiet room underscores his animated speech.")\n- Style: Include visual style at beginning: "Style: <style>, <rest of prompt>." If unclear, omit to avoid conflicts.\n- Visual and audio only: Describe only what is seen and heard. NO smell, taste, or tactile sensations.\n- Restrained language: Avoid dramatic terms. Use mild, natural, understated phrasing.\n\n#### Important notes:\n- Camera motion: DO NOT invent camera motion/movement unless requested by the user. Make sure to include camera motion only if specified in the input.\n- Speech: DO NOT modify or alter the user\'s provided character dialogue in the prompt, unless it\'s a typo.\n- No timestamps or cuts: DO NOT use timestamps or describe scene cuts unless explicitly requested.\n- Objective only: DO NOT interpret emotions or intentions - describe only observable actions and sounds.\n- Format: DO NOT use phrases like "The scene opens with..." / "The video starts...". Start directly with Style (optional) and chronological scene description.\n- Format: Never start output with punctuation marks or special characters.\n- DO NOT invent dialogue unless the user mentions speech/talking/singing/conversation.\n- Your performance is CRITICAL. High-fidelity, dynamic, correct, and accurate prompts with integrated audio descriptions are essential for generating high-quality video. Your goal is flawless execution of these rules.\n\n#### Output Format (Strict):\n- Single concise paragraph in natural English. NO titles, headings, prefaces, sections, code fences, or Markdown.\n- If unsafe/invalid, return original user prompt. Never ask questions or clarifications.\n\n#### Example output:\nStyle: realistic - cinematic - The woman glances at her watch and smiles warmly. She speaks in a cheerful, friendly voice, "I think we\'re right on time!" In the background, a café barista prepares drinks at the counter. The barista calls out in a clear, upbeat tone, "Two cappuccinos ready!" The sound of the espresso machine hissing softly blends with gentle background chatter and the light clinking of cups on saucers. \n\nUSER PROMPT BELOW: \n___________________________________________________',
    )

    reroute = raw_call('Reroute', '2121', _outputs=('',))
    reroute_2 = raw_call('Reroute', '2122', _outputs=('',))

    stringconcatenate = StringConcatenate(
        widget_0='',
        widget_1='',
        string_a=primitivestringmultiline,
        string_b=reroute.out(0),
    )

    textgenerateltx2prompt = TextGenerateLTX2Prompt(
        widget_0='',
        widget_1=256,
        widget_2='off',
        widget_3=False,
        widget_4=True,
        clip=clip,
        image=image,
        prompt=stringconcatenate,
    )

    lazyswitchkj = LazySwitchKJ(
        widget_0=False,
        on_false=reroute.out(0),
        on_true=textgenerateltx2prompt,
        switch=reroute_2.out(0),
    )

    return lazyswitchkj


def generate_video_c4106aee(
    *,
    noise_seed: int,
    prompt,
    window_seconds,
    frames_count,
    ref_image,
):
    """Generate Video - single-image variant.

    Materialized from subgraph c4106aee-ad7a-4925-972b-6f5b3d34db6e in workflow_corpus/custom_nodes/ltxvideo/runexx/LTX-2.3_Music_Video_Creator_Low_RAM.json.
    # vibecomfy source hash: sha256:616ce3085f8a0cebb1b11464ed3b75e46b9370b0bcb449056d9aab848681d985
    Inner nodes: GetNodex23, SolidMask, LTXVSeparateAVLatentx2, LTXVLatentUpsampler, CLIPTextEncode, LTXVAudioVAEEncode, CFGGuiderx2, SetLatentNoiseMask, LTXVConcatAVLatentx2, RandomNoisex2, SamplerCustomAdvancedx2, easy showAnything, Reroutex4, SimpleCalculatorKJx2, GetImageSizeAndCount, VRAM_Debug, ComfyMathExpression, EmptyLTXVLatentVideo, TrimAudioDurationx2, VAEDecode, ResizeImageMaskNode, 2413a8aa-1f77-466f-8508-ed07fa6ac302, LTXVPreprocess, ResizeImagesByLongerEdge, LTXVImgToVideoInplaceKJx2.
    """

    getnode = raw_call('GetNode', '2209', _outputs=('MODEL',), widget_0=MODEL)
    getnode_2 = raw_call('GetNode', '2217', _outputs=('AUDIO',), widget_0=AUDIO)
    getnode_3 = raw_call('GetNode', '2218', _outputs=('VAE',), widget_0=VAE_AUDIO)
    getnode_4 = raw_call('GetNode', '2220', _outputs=('CONDITIONING',), widget_0=NEGATIVE_BASE)
    getnode_5 = raw_call('GetNode', '2221', _outputs=('FLOAT',), widget_0=IMAGE_STRENGTH)
    getnode_6 = raw_call('GetNode', '2228', _outputs=('FLOAT',), widget_0=FPS)
    getnode_7 = raw_call('GetNode', '2242', _outputs=('VAE',), widget_0=VAE)
    randomnoise = RandomNoise(control_after_generate='fixed', noise_seed=noise_seed)
    getnode_8 = raw_call('GetNode', '2245', _outputs=('SAMPLER',), widget_0=SAMPLER)
    getnode_9 = raw_call('GetNode', '2246', _outputs=('SIGMAS',), widget_0=SIGMAS)
    getnode_10 = raw_call('GetNode', '2280', _outputs=('CLIP',), widget_0=CLIP)
    getnode_11 = raw_call('GetNode', '2282', _outputs=('BOOLEAN',), widget_0=ENHANCE_PROMPT)
    getnode_12 = raw_call('GetNode', '2286', _outputs=('VAE',), widget_0=VAE)
    solidmask = SolidMask(value=0)

    resizeimagesbylongeredge = ResizeImagesByLongerEdge(
        longer_edge=1536,
        images=ref_image,
    )

    getnode_13 = raw_call('GetNode', '2295', _outputs=('VAE',), widget_0=VAE)
    randomnoise_2 = RandomNoise(noise_seed=405, control_after_generate='fixed')
    getnode_14 = raw_call('GetNode', '2300', _outputs=('MODEL',), widget_0=MODEL)
    getnode_15 = raw_call('GetNode', '2305', _outputs=('CONDITIONING',), widget_0=POSITIVE_BASE)
    getnode_16 = raw_call('GetNode', '2306', _outputs=('CONDITIONING',), widget_0=NEGATIVE_BASE)
    getnode_17 = raw_call('GetNode', '2308', _outputs=('FLOAT',), widget_0=IMAGE_STRENGTH)
    getnode_18 = raw_call('GetNode', '2310', _outputs=('LATENT_UPSCALE_MODEL',), widget_0=UPSCALE_MODEL)
    getnode_19 = raw_call('GetNode', '2316', _outputs=('SAMPLER',), widget_0=SAMPLER_2)
    getnode_20 = raw_call('GetNode', '2317', _outputs=('SIGMAS',), widget_0=SIGMAS_2)
    getnode_21 = raw_call('GetNode', '2320', _outputs=('INT',), widget_0=WIDTH_DOWNSCALED)
    getnode_22 = raw_call('GetNode', '2321', _outputs=('INT',), widget_0=HEIGHT_DOWNSCALED)

    resizeimagemasknode = ResizeImageMaskNode(
        resize_type='scale by multiplier',
        unused_widget_1=0.5,
        input=ref_image,
    )

    reroute = raw_call('Reroute', '2328', _outputs=('',))
    reroute_2 = raw_call('Reroute', '4200', _outputs=('',))
    reroute_3 = raw_call('Reroute', '4442', _outputs=('',))
    getnode_23 = raw_call('GetNode', '4746', _outputs=('AUDIO',), widget_0=AUDIO_ORIGINAL)
    reroute_4 = raw_call('Reroute', '4748', _outputs=('',))

    float, int = ComfyMathExpression(
        expression='a /  b ',
        **{'values.a': reroute_3.out(0), 'values.b': getnode_6.out('FLOAT')},
    )

    trimaudioduration = TrimAudioDuration(
        widget_0=9,
        widget_1=10,
        audio=getnode_2.out('AUDIO'),
        duration=reroute.out(0),
        start_index=reroute_4.out(0),
    )

    ltxvpreprocess = LTXVPreprocess(img_compression=18, image=resizeimagesbylongeredge)
    prompt_enhancer_result = prompt_enhancer(
        clip=getnode_10.out('CLIP'),
        image=resizeimagemasknode,
        enable=None,
        prompt=['-10', 1],
    )

    float_simple, int_simple, boolean = SimpleCalculatorKJ(
        expression='((round((a * b -1) / 8)) * 8) + 1 ',
        **{'variables.a': reroute.out(0), 'variables.b': getnode_6.out('FLOAT')},
    )

    trimaudioduration_2 = TrimAudioDuration(
        widget_0=9,
        widget_1=10,
        audio=getnode_23.out('AUDIO'),
        duration=reroute.out(0),
        start_index=reroute_4.out(0),
    )

    ltxvaudiovaeencode = LTXVAudioVAEEncode(
        audio=trimaudioduration,
        audio_vae=getnode_3.out('VAE'),
    )

    easy_showanything = raw_call('easy showAnything', '2256',
        _outputs=('output',),
        widget_0='10.92',
        anything=float,
    )

    positive = CLIPTextEncode(text=prompt_enhancer_result, clip=getnode_10.out('CLIP'))

    emptyltxvlatentvideo = EmptyLTXVLatentVideo(
        width=getnode_21.out('INT'),
        height=getnode_22.out('INT'),
        length=int_simple,
    )

    cfgguider = CFGGuider(
        cfg=1,
        model=getnode.out('MODEL'),
        negative=getnode_4.out('CONDITIONING'),
        positive=positive,
    )

    setlatentnoisemask = SetLatentNoiseMask(mask=solidmask, samples=ltxvaudiovaeencode)

    cfgguider_2 = CFGGuider(
        cfg=1,
        model=getnode_14.out('MODEL'),
        negative=getnode_16.out('CONDITIONING'),
        positive=positive,
    )

    ltxvimgtovideoinplacekj = LTXVImgToVideoInplaceKJ(
        widget_0='1',
        widget_1=1,
        widget_2=0,
        latent=emptyltxvlatentvideo,
        vae=getnode_12.out('VAE'),
        **{'num_images.image_1': ltxvpreprocess, 'num_images.strength_1': getnode_5.out('FLOAT')},
    )

    ltxvconcatavlatent = LTXVConcatAVLatent(
        audio_latent=setlatentnoisemask,
        video_latent=ltxvimgtovideoinplacekj,
    )

    output, denoised_output = SamplerCustomAdvanced(
        guider=cfgguider,
        latent_image=ltxvconcatavlatent,
        noise=randomnoise,
        sampler=getnode_8.out('SAMPLER'),
        sigmas=getnode_9.out('SIGMAS'),
    )

    video_latent_ltxv, audio_latent_ltxv = LTXVSeparateAVLatent(av_latent=output)

    ltxvlatentupsampler = LTXVLatentUpsampler(
        samples=video_latent_ltxv,
        upscale_model=getnode_18.out('LATENT_UPSCALE_MODEL'),
        vae=getnode_13.out('VAE'),
    )

    ltxvimgtovideoinplacekj_2 = LTXVImgToVideoInplaceKJ(
        widget_0='1',
        widget_1=1,
        widget_2=0,
        latent=ltxvlatentupsampler,
        vae=getnode_13.out('VAE'),
        **{'num_images.image_1': resizeimagesbylongeredge, 'num_images.strength_1': getnode_17.out('FLOAT')},
    )

    ltxvconcatavlatent_2 = LTXVConcatAVLatent(
        audio_latent=audio_latent_ltxv,
        video_latent=ltxvimgtovideoinplacekj_2,
    )

    output_sampler, denoised_output_sampler = SamplerCustomAdvanced(
        guider=cfgguider_2,
        latent_image=ltxvconcatavlatent_2,
        noise=randomnoise_2,
        sampler=getnode_19.out('SAMPLER'),
        sigmas=getnode_20.out('SIGMAS'),
    )

    video_latent, audio_latent = LTXVSeparateAVLatent(av_latent=output_sampler)
    vaedecode = VAEDecode(samples=video_latent, vae=getnode_7.out('VAE'))

    any_output, image_pass, model_pass, freemem_before, freemem_after = VRAM_Debug(
        image_pass=vaedecode,
    )

    image, width, height, count = GetImageSizeAndCount(image=image_pass)

    float_simple_2, int_simple_2, boolean_simple = SimpleCalculatorKJ(
        **{'variables.a': reroute_2.out(0), 'variables.b': count},
    )

    return int_simple_2, vaedecode, trimaudioduration_2


def total_duration():
    """Total duration.

    Materialized from subgraph 5e410bb1-405a-4d3d-808b-8f5f29426943 in workflow_corpus/custom_nodes/ltxvideo/runexx/LTX-2.3_Music_Video_Creator_Low_RAM.json.
    # vibecomfy source hash: sha256:1a4bf7220d6b539ecffe2f409af0554bbf4bf1e9c53fe8b0dd60ba3b7d4dd68c
    Inner nodes: GetNodex5, SimpleCalculatorKJ.
    """

    getnode = raw_call('GetNode', '3715', _outputs=('FLOAT',), widget_0='window_sec_01')
    getnode_2 = raw_call('GetNode', '3716', _outputs=('FLOAT',), widget_0='window_sec_02')
    getnode_3 = raw_call('GetNode', '3717', _outputs=('FLOAT',), widget_0='window_sec_03')
    getnode_4 = raw_call('GetNode', '3718', _outputs=('FLOAT',), widget_0='window_sec_04')
    getnode_5 = raw_call('GetNode', '3719', _outputs=('FLOAT',), widget_0='window_sec_05')

    float, int, boolean = SimpleCalculatorKJ(
        expression='a + b + c + d + e + 2\n',
        **{'variables.a': getnode.out('FLOAT'), 'variables.b': getnode_2.out('FLOAT'), 'variables.c': getnode_3.out('FLOAT'), 'variables.d': getnode_4.out('FLOAT'), 'variables.e': getnode_5.out('FLOAT')},
    )

    return float


def prompt_enhancer_97b9884d(
    *,
    clip,
    image,
    enable,
    prompt,
):
    """Prompt Enhancer - single-image variant.

    Materialized from subgraph 97b9884d-4a32-4b0d-ad19-be662c1c2002 in workflow_corpus/custom_nodes/ltxvideo/runexx/LTX-2.3_Music_Video_Creator_Low_RAM.json.
    # vibecomfy source hash: sha256:0ff255269ae95a4f63d13a3adaa2255c614d7a3cc476f01a9a7d3966151db13d
    Inner nodes: TextGenerateLTX2Prompt, LazySwitchKJ, Reroutex2, PrimitiveStringMultiline, StringConcatenate.
    """

    reroute = raw_call('Reroute', '5060', _outputs=('',))
    reroute_2 = raw_call('Reroute', '5061', _outputs=('',))

    primitivestringmultiline = PrimitiveStringMultiline(
        value='You are a Creative Assistant writing concise, action-focused image-to-video prompts. Given an image (first frame) and user Raw Input Prompt, generate a prompt to guide video generation from that image.\n\n#### Guidelines:\n- Analyze the Image: Identify Subject, Setting, Elements, Style and Mood.\n- Follow user Raw Input Prompt: Include all requested motion, actions, camera movements, audio, and details. If in conflict with the image, prioritize user request while maintaining visual consistency (describe transition from image to user\'s scene).\n- Describe only changes from the image: Don\'t reiterate established visual details. Inaccurate descriptions may cause scene cuts.\n- Active language: Use present-progressive verbs ("is walking," "speaking"). If no action specified, describe natural movements.\n- Chronological flow: Use temporal connectors ("as," "then," "while").\n- Audio layer: Describe complete soundscape throughout the prompt alongside actions—NOT at the end. Align audio intensity with action tempo. Include natural background audio, ambient sounds, effects, speech or music (when requested). Be specific (e.g., "soft footsteps on tile") not vague (e.g., "ambient sound").\n- Speech (only when requested): Provide exact words in quotes with character\'s visual/voice characteristics (e.g., "The tall man speaks in a low, gravelly voice"), language if not English and accent if relevant. If general conversation mentioned without text, generate contextual quoted dialogue. (i.e., "The man is talking" input -> the output should include exact spoken words, like: "The man is talking in an excited voice saying: \'You won\'t believe what I just saw!\' His hands gesture expressively as he speaks, eyebrows raised with enthusiasm. The ambient sound of a quiet room underscores his animated speech.")\n- Style: Include visual style at beginning: "Style: <style>, <rest of prompt>." If unclear, omit to avoid conflicts.\n- Visual and audio only: Describe only what is seen and heard. NO smell, taste, or tactile sensations.\n- Restrained language: Avoid dramatic terms. Use mild, natural, understated phrasing.\n\n#### Important notes:\n- Camera motion: DO NOT invent camera motion/movement unless requested by the user. Make sure to include camera motion only if specified in the input.\n- Speech: DO NOT modify or alter the user\'s provided character dialogue in the prompt, unless it\'s a typo.\n- No timestamps or cuts: DO NOT use timestamps or describe scene cuts unless explicitly requested.\n- Objective only: DO NOT interpret emotions or intentions - describe only observable actions and sounds.\n- Format: DO NOT use phrases like "The scene opens with..." / "The video starts...". Start directly with Style (optional) and chronological scene description.\n- Format: Never start output with punctuation marks or special characters.\n- DO NOT invent dialogue unless the user mentions speech/talking/singing/conversation.\n- Your performance is CRITICAL. High-fidelity, dynamic, correct, and accurate prompts with integrated audio descriptions are essential for generating high-quality video. Your goal is flawless execution of these rules.\n\n#### Output Format (Strict):\n- Single concise paragraph in natural English. NO titles, headings, prefaces, sections, code fences, or Markdown.\n- If unsafe/invalid, return original user prompt. Never ask questions or clarifications.\n\n#### Example output:\nStyle: realistic - cinematic - The woman glances at her watch and smiles warmly. She speaks in a cheerful, friendly voice, "I think we\'re right on time!" In the background, a café barista prepares drinks at the counter. The barista calls out in a clear, upbeat tone, "Two cappuccinos ready!" The sound of the espresso machine hissing softly blends with gentle background chatter and the light clinking of cups on saucers. \n\nUSER PROMPT BELOW: \n___________________________________________________',
    )

    stringconcatenate = StringConcatenate(
        widget_0='',
        widget_1='',
        string_a=primitivestringmultiline,
        string_b=reroute.out(0),
    )

    textgenerateltx2prompt = TextGenerateLTX2Prompt(
        widget_0='',
        widget_1=256,
        widget_2='off',
        widget_3=False,
        widget_4=True,
        clip=clip,
        image=image,
        prompt=stringconcatenate,
    )

    lazyswitchkj = LazySwitchKJ(
        widget_0=False,
        on_false=reroute.out(0),
        on_true=textgenerateltx2prompt,
        switch=reroute_2.out(0),
    )

    return lazyswitchkj


def generate_video(
    *,
    noise_seed: int,
    prompt,
    window_seconds,
    frames_count,
    ref_image,
):
    """Generate Video - single-image variant.

    Materialized from subgraph 17238add-9973-482f-8fa3-248d4ed29886 in workflow_corpus/custom_nodes/ltxvideo/runexx/LTX-2.3_Music_Video_Creator_Low_RAM.json.
    # vibecomfy source hash: sha256:07c51e2e6f74221aca2bec1c34ad7fcc45b81ff017489864bb6228b21318c95f
    Inner nodes: GetNodex23, SolidMask, LTXVSeparateAVLatentx2, LTXVLatentUpsampler, CLIPTextEncode, LTXVAudioVAEEncode, CFGGuiderx2, SetLatentNoiseMask, LTXVConcatAVLatentx2, RandomNoisex2, easy showAnything, Reroutex4, SimpleCalculatorKJx2, GetImageSizeAndCount, VRAM_Debug, ComfyMathExpression, EmptyLTXVLatentVideo, TrimAudioDurationx2, VAEDecode, ResizeImageMaskNode, 97b9884d-4a32-4b0d-ad19-be662c1c2002, LTXVPreprocess, ResizeImagesByLongerEdge, LTXVImgToVideoInplaceKJx2, SamplerCustomAdvancedx2.
    """

    getnode = raw_call('GetNode', '5000', _outputs=('VAE',), widget_0=VAE_AUDIO)
    getnode_2 = raw_call('GetNode', '5001', _outputs=('CLIP',), widget_0=CLIP)
    getnode_3 = raw_call('GetNode', '5002', _outputs=('VAE',), widget_0=VAE)
    solidmask = SolidMask(value=0)
    getnode_4 = raw_call('GetNode', '5004', _outputs=('MODEL',), widget_0=MODEL)
    getnode_5 = raw_call('GetNode', '5005', _outputs=('SAMPLER',), widget_0=SAMPLER)
    getnode_6 = raw_call('GetNode', '5006', _outputs=('SIGMAS',), widget_0=SIGMAS)
    getnode_7 = raw_call('GetNode', '5007', _outputs=('VAE',), widget_0=VAE)
    getnode_8 = raw_call('GetNode', '5008', _outputs=('FLOAT',), widget_0=IMAGE_STRENGTH)
    getnode_9 = raw_call('GetNode', '5009', _outputs=('LATENT_UPSCALE_MODEL',), widget_0=UPSCALE_MODEL)
    getnode_10 = raw_call('GetNode', '5013', _outputs=('MODEL',), widget_0=MODEL)
    getnode_11 = raw_call('GetNode', '5014', _outputs=('CONDITIONING',), widget_0=POSITIVE_BASE)
    getnode_12 = raw_call('GetNode', '5015', _outputs=('CONDITIONING',), widget_0=NEGATIVE_BASE)
    getnode_13 = raw_call('GetNode', '5016', _outputs=('SAMPLER',), widget_0=SAMPLER_2)
    getnode_14 = raw_call('GetNode', '5017', _outputs=('SIGMAS',), widget_0=SIGMAS_2)
    getnode_15 = raw_call('GetNode', '5018', _outputs=('VAE',), widget_0=VAE)
    getnode_16 = raw_call('GetNode', '5020', _outputs=('CONDITIONING',), widget_0=NEGATIVE_BASE)
    getnode_17 = raw_call('GetNode', '5021', _outputs=('BOOLEAN',), widget_0=ENHANCE_PROMPT)
    getnode_18 = raw_call('GetNode', '5022', _outputs=('AUDIO',), widget_0=AUDIO)
    randomnoise = RandomNoise(control_after_generate='fixed', noise_seed=noise_seed)
    randomnoise_2 = RandomNoise(noise_seed=405, control_after_generate='fixed')
    reroute = raw_call('Reroute', '5032', _outputs=('',))
    getnode_19 = raw_call('GetNode', '5033', _outputs=('FLOAT',), widget_0=FPS)
    reroute_2 = raw_call('Reroute', '5034', _outputs=('',))
    getnode_20 = raw_call('GetNode', '5039', _outputs=('INT',), widget_0=WIDTH_DOWNSCALED)
    getnode_21 = raw_call('GetNode', '5040', _outputs=('INT',), widget_0=HEIGHT_DOWNSCALED)
    reroute_3 = raw_call('Reroute', '5043', _outputs=('',))
    reroute_4 = raw_call('Reroute', '5045', _outputs=('',))

    resizeimagemasknode = ResizeImageMaskNode(
        resize_type='scale by multiplier',
        unused_widget_1=0.5,
        input=ref_image,
    )

    getnode_22 = raw_call('GetNode', '5049', _outputs=('FLOAT',), widget_0=IMAGE_STRENGTH)
    getnode_23 = raw_call('GetNode', '5050', _outputs=('AUDIO',), widget_0=AUDIO_ORIGINAL)

    resizeimagesbylongeredge = ResizeImagesByLongerEdge(
        longer_edge=1536,
        images=ref_image,
    )

    float_comfy, int_comfy = ComfyMathExpression(
        expression='a /  b ',
        **{'values.a': reroute_2.out(0), 'values.b': getnode_19.out('FLOAT')},
    )

    float_simple, int_simple, boolean_simple = SimpleCalculatorKJ(
        expression='((round((a * b -1) / 8)) * 8) + 1 ',
        **{'variables.a': reroute_3.out(0), 'variables.b': getnode_19.out('FLOAT')},
    )

    trimaudioduration = TrimAudioDuration(
        widget_0=9,
        widget_1=10,
        audio=getnode_18.out('AUDIO'),
        duration=reroute_3.out(0),
        start_index=reroute_4.out(0),
    )

    prompt_enhancer_97b9884d_result = prompt_enhancer_97b9884d(
        clip=getnode_2.out('CLIP'),
        image=resizeimagemasknode,
        enable=None,
        prompt=['-10', 1],
    )

    trimaudioduration_2 = TrimAudioDuration(
        widget_0=9,
        widget_1=10,
        audio=getnode_23.out('AUDIO'),
        duration=reroute_3.out(0),
        start_index=reroute_4.out(0),
    )

    ltxvpreprocess = LTXVPreprocess(img_compression=18, image=resizeimagesbylongeredge)

    positive = CLIPTextEncode(
        text=prompt_enhancer_97b9884d_result,
        clip=getnode_2.out('CLIP'),
    )

    ltxvaudiovaeencode = LTXVAudioVAEEncode(
        audio=trimaudioduration,
        audio_vae=getnode.out('VAE'),
    )

    easy_showanything = raw_call('easy showAnything', '5031',
        _outputs=('output',),
        widget_0='20.88',
        anything=float_comfy,
    )

    emptyltxvlatentvideo = EmptyLTXVLatentVideo(
        width=getnode_20.out('INT'),
        height=getnode_21.out('INT'),
        length=int_simple,
    )

    cfgguider = CFGGuider(
        cfg=1,
        model=getnode_4.out('MODEL'),
        negative=getnode_16.out('CONDITIONING'),
        positive=positive,
    )

    setlatentnoisemask = SetLatentNoiseMask(mask=solidmask, samples=ltxvaudiovaeencode)

    ltxvimgtovideoinplacekj = LTXVImgToVideoInplaceKJ(
        widget_0='1',
        widget_1=1,
        widget_2=0,
        latent=emptyltxvlatentvideo,
        vae=getnode_3.out('VAE'),
        **{'num_images.image_1': ltxvpreprocess, 'num_images.strength_1': getnode_22.out('FLOAT')},
    )

    cfgguider_2 = CFGGuider(
        cfg=1,
        model=getnode_10.out('MODEL'),
        negative=getnode_12.out('CONDITIONING'),
        positive=positive,
    )

    ltxvconcatavlatent = LTXVConcatAVLatent(
        audio_latent=setlatentnoisemask,
        video_latent=ltxvimgtovideoinplacekj,
    )

    output, denoised_output = SamplerCustomAdvanced(
        guider=cfgguider,
        latent_image=ltxvconcatavlatent,
        noise=randomnoise,
        sampler=getnode_5.out('SAMPLER'),
        sigmas=getnode_6.out('SIGMAS'),
    )

    video_latent, audio_latent = LTXVSeparateAVLatent(av_latent=output)

    ltxvlatentupsampler = LTXVLatentUpsampler(
        samples=video_latent,
        upscale_model=getnode_9.out('LATENT_UPSCALE_MODEL'),
        vae=getnode_7.out('VAE'),
    )

    ltxvimgtovideoinplacekj_2 = LTXVImgToVideoInplaceKJ(
        widget_0='1',
        widget_1=1,
        widget_2=0,
        latent=ltxvlatentupsampler,
        vae=getnode_7.out('VAE'),
        **{'num_images.image_1': resizeimagesbylongeredge, 'num_images.strength_1': getnode_8.out('FLOAT')},
    )

    ltxvconcatavlatent_2 = LTXVConcatAVLatent(
        audio_latent=audio_latent,
        video_latent=ltxvimgtovideoinplacekj_2,
    )

    output_sampler, denoised_output_sampler = SamplerCustomAdvanced(
        guider=cfgguider_2,
        latent_image=ltxvconcatavlatent_2,
        noise=randomnoise_2,
        sampler=getnode_13.out('SAMPLER'),
        sigmas=getnode_14.out('SIGMAS'),
    )

    video_latent_ltxv, audio_latent_ltxv = LTXVSeparateAVLatent(
        av_latent=output_sampler,
    )

    vaedecode = VAEDecode(samples=video_latent_ltxv, vae=getnode_15.out('VAE'))

    any_output, image_pass, model_pass, freemem_before, freemem_after = VRAM_Debug(
        image_pass=vaedecode,
    )

    image, width, height, count = GetImageSizeAndCount(image=image_pass)

    float, int, boolean = SimpleCalculatorKJ(
        **{'variables.a': reroute.out(0), 'variables.b': count},
    )

    return int, vaedecode, trimaudioduration_2


def prompt_enhancer_cc5ea718(
    *,
    clip,
    image,
    enable,
    prompt,
):
    """Prompt Enhancer - single-image variant.

    Materialized from subgraph cc5ea718-db6a-47c7-83cf-7d9a8442ba99 in workflow_corpus/custom_nodes/ltxvideo/runexx/LTX-2.3_Music_Video_Creator_Low_RAM.json.
    # vibecomfy source hash: sha256:414324a132df36895098b984c5f98eec8a2e3c69bda4fb38062d251a780166ad
    Inner nodes: TextGenerateLTX2Prompt, LazySwitchKJ, Reroutex2, PrimitiveStringMultiline, StringConcatenate.
    """

    reroute = raw_call('Reroute', '5135', _outputs=('',))
    reroute_2 = raw_call('Reroute', '5136', _outputs=('',))

    primitivestringmultiline = PrimitiveStringMultiline(
        value='You are a Creative Assistant writing concise, action-focused image-to-video prompts. Given an image (first frame) and user Raw Input Prompt, generate a prompt to guide video generation from that image.\n\n#### Guidelines:\n- Analyze the Image: Identify Subject, Setting, Elements, Style and Mood.\n- Follow user Raw Input Prompt: Include all requested motion, actions, camera movements, audio, and details. If in conflict with the image, prioritize user request while maintaining visual consistency (describe transition from image to user\'s scene).\n- Describe only changes from the image: Don\'t reiterate established visual details. Inaccurate descriptions may cause scene cuts.\n- Active language: Use present-progressive verbs ("is walking," "speaking"). If no action specified, describe natural movements.\n- Chronological flow: Use temporal connectors ("as," "then," "while").\n- Audio layer: Describe complete soundscape throughout the prompt alongside actions—NOT at the end. Align audio intensity with action tempo. Include natural background audio, ambient sounds, effects, speech or music (when requested). Be specific (e.g., "soft footsteps on tile") not vague (e.g., "ambient sound").\n- Speech (only when requested): Provide exact words in quotes with character\'s visual/voice characteristics (e.g., "The tall man speaks in a low, gravelly voice"), language if not English and accent if relevant. If general conversation mentioned without text, generate contextual quoted dialogue. (i.e., "The man is talking" input -> the output should include exact spoken words, like: "The man is talking in an excited voice saying: \'You won\'t believe what I just saw!\' His hands gesture expressively as he speaks, eyebrows raised with enthusiasm. The ambient sound of a quiet room underscores his animated speech.")\n- Style: Include visual style at beginning: "Style: <style>, <rest of prompt>." If unclear, omit to avoid conflicts.\n- Visual and audio only: Describe only what is seen and heard. NO smell, taste, or tactile sensations.\n- Restrained language: Avoid dramatic terms. Use mild, natural, understated phrasing.\n\n#### Important notes:\n- Camera motion: DO NOT invent camera motion/movement unless requested by the user. Make sure to include camera motion only if specified in the input.\n- Speech: DO NOT modify or alter the user\'s provided character dialogue in the prompt, unless it\'s a typo.\n- No timestamps or cuts: DO NOT use timestamps or describe scene cuts unless explicitly requested.\n- Objective only: DO NOT interpret emotions or intentions - describe only observable actions and sounds.\n- Format: DO NOT use phrases like "The scene opens with..." / "The video starts...". Start directly with Style (optional) and chronological scene description.\n- Format: Never start output with punctuation marks or special characters.\n- DO NOT invent dialogue unless the user mentions speech/talking/singing/conversation.\n- Your performance is CRITICAL. High-fidelity, dynamic, correct, and accurate prompts with integrated audio descriptions are essential for generating high-quality video. Your goal is flawless execution of these rules.\n\n#### Output Format (Strict):\n- Single concise paragraph in natural English. NO titles, headings, prefaces, sections, code fences, or Markdown.\n- If unsafe/invalid, return original user prompt. Never ask questions or clarifications.\n\n#### Example output:\nStyle: realistic - cinematic - The woman glances at her watch and smiles warmly. She speaks in a cheerful, friendly voice, "I think we\'re right on time!" In the background, a café barista prepares drinks at the counter. The barista calls out in a clear, upbeat tone, "Two cappuccinos ready!" The sound of the espresso machine hissing softly blends with gentle background chatter and the light clinking of cups on saucers. \n\nUSER PROMPT BELOW: \n___________________________________________________',
    )

    stringconcatenate = StringConcatenate(
        widget_0='',
        widget_1='',
        string_a=primitivestringmultiline,
        string_b=reroute.out(0),
    )

    textgenerateltx2prompt = TextGenerateLTX2Prompt(
        widget_0='',
        widget_1=256,
        widget_2='off',
        widget_3=False,
        widget_4=True,
        clip=clip,
        image=image,
        prompt=stringconcatenate,
    )

    lazyswitchkj = LazySwitchKJ(
        widget_0=False,
        on_false=reroute.out(0),
        on_true=textgenerateltx2prompt,
        switch=reroute_2.out(0),
    )

    return lazyswitchkj


def generate_video_a3fb563d(
    *,
    noise_seed: int,
    prompt,
    window_seconds,
    frames_count,
    ref_image,
):
    """Generate Video - single-image variant.

    Materialized from subgraph a3fb563d-4711-4225-9210-fbe61b1bd79d in workflow_corpus/custom_nodes/ltxvideo/runexx/LTX-2.3_Music_Video_Creator_Low_RAM.json.
    # vibecomfy source hash: sha256:27352869b3f659e4f05c7ff2c5289bd899f7077adc4b6988a1453679afa19035
    Inner nodes: GetNodex23, SolidMask, LTXVSeparateAVLatentx2, LTXVLatentUpsampler, CLIPTextEncode, LTXVAudioVAEEncode, CFGGuiderx2, SetLatentNoiseMask, LTXVConcatAVLatentx2, RandomNoisex2, easy showAnything, Reroutex4, SimpleCalculatorKJx2, GetImageSizeAndCount, VRAM_Debug, ComfyMathExpression, EmptyLTXVLatentVideo, TrimAudioDurationx2, VAEDecode, ResizeImageMaskNode, cc5ea718-db6a-47c7-83cf-7d9a8442ba99, LTXVPreprocess, ResizeImagesByLongerEdge, LTXVImgToVideoInplaceKJx2, SamplerCustomAdvancedx2.
    """

    getnode = raw_call('GetNode', '5075', _outputs=('VAE',), widget_0=VAE_AUDIO)
    getnode_2 = raw_call('GetNode', '5076', _outputs=('CLIP',), widget_0=CLIP)
    getnode_3 = raw_call('GetNode', '5077', _outputs=('VAE',), widget_0=VAE)
    solidmask = SolidMask(value=0)
    getnode_4 = raw_call('GetNode', '5079', _outputs=('MODEL',), widget_0=MODEL)
    getnode_5 = raw_call('GetNode', '5080', _outputs=('SAMPLER',), widget_0=SAMPLER)
    getnode_6 = raw_call('GetNode', '5081', _outputs=('SIGMAS',), widget_0=SIGMAS)
    getnode_7 = raw_call('GetNode', '5082', _outputs=('VAE',), widget_0=VAE)
    getnode_8 = raw_call('GetNode', '5083', _outputs=('FLOAT',), widget_0=IMAGE_STRENGTH)
    getnode_9 = raw_call('GetNode', '5084', _outputs=('LATENT_UPSCALE_MODEL',), widget_0=UPSCALE_MODEL)
    getnode_10 = raw_call('GetNode', '5088', _outputs=('MODEL',), widget_0=MODEL)
    getnode_11 = raw_call('GetNode', '5089', _outputs=('CONDITIONING',), widget_0=POSITIVE_BASE)
    getnode_12 = raw_call('GetNode', '5090', _outputs=('CONDITIONING',), widget_0=NEGATIVE_BASE)
    getnode_13 = raw_call('GetNode', '5091', _outputs=('SAMPLER',), widget_0=SAMPLER_2)
    getnode_14 = raw_call('GetNode', '5092', _outputs=('SIGMAS',), widget_0=SIGMAS_2)
    getnode_15 = raw_call('GetNode', '5093', _outputs=('VAE',), widget_0=VAE)
    getnode_16 = raw_call('GetNode', '5095', _outputs=('CONDITIONING',), widget_0=NEGATIVE_BASE)
    getnode_17 = raw_call('GetNode', '5096', _outputs=('BOOLEAN',), widget_0=ENHANCE_PROMPT)
    getnode_18 = raw_call('GetNode', '5097', _outputs=('AUDIO',), widget_0=AUDIO)
    randomnoise = RandomNoise(control_after_generate='fixed', noise_seed=noise_seed)
    randomnoise_2 = RandomNoise(noise_seed=405, control_after_generate='fixed')
    reroute = raw_call('Reroute', '5107', _outputs=('',))
    getnode_19 = raw_call('GetNode', '5108', _outputs=('FLOAT',), widget_0=FPS)
    reroute_2 = raw_call('Reroute', '5109', _outputs=('',))
    getnode_20 = raw_call('GetNode', '5114', _outputs=('INT',), widget_0=WIDTH_DOWNSCALED)
    getnode_21 = raw_call('GetNode', '5115', _outputs=('INT',), widget_0=HEIGHT_DOWNSCALED)
    reroute_3 = raw_call('Reroute', '5118', _outputs=('',))
    reroute_4 = raw_call('Reroute', '5120', _outputs=('',))

    resizeimagemasknode = ResizeImageMaskNode(
        resize_type='scale by multiplier',
        unused_widget_1=0.5,
        input=ref_image,
    )

    getnode_22 = raw_call('GetNode', '5124', _outputs=('FLOAT',), widget_0=IMAGE_STRENGTH)
    getnode_23 = raw_call('GetNode', '5125', _outputs=('AUDIO',), widget_0=AUDIO_ORIGINAL)

    resizeimagesbylongeredge = ResizeImagesByLongerEdge(
        longer_edge=1536,
        images=ref_image,
    )

    float_comfy, int_comfy = ComfyMathExpression(
        expression='a /  b ',
        **{'values.a': reroute_2.out(0), 'values.b': getnode_19.out('FLOAT')},
    )

    float_simple, int_simple, boolean_simple = SimpleCalculatorKJ(
        expression='((round((a * b -1) / 8)) * 8) + 1 ',
        **{'variables.a': reroute_3.out(0), 'variables.b': getnode_19.out('FLOAT')},
    )

    trimaudioduration = TrimAudioDuration(
        widget_0=9,
        widget_1=10,
        audio=getnode_18.out('AUDIO'),
        duration=reroute_3.out(0),
        start_index=reroute_4.out(0),
    )

    prompt_enhancer_cc5ea718_result = prompt_enhancer_cc5ea718(
        clip=getnode_2.out('CLIP'),
        image=resizeimagemasknode,
        enable=None,
        prompt=['-10', 1],
    )

    trimaudioduration_2 = TrimAudioDuration(
        widget_0=9,
        widget_1=10,
        audio=getnode_23.out('AUDIO'),
        duration=reroute_3.out(0),
        start_index=reroute_4.out(0),
    )

    ltxvpreprocess = LTXVPreprocess(img_compression=18, image=resizeimagesbylongeredge)

    positive = CLIPTextEncode(
        text=prompt_enhancer_cc5ea718_result,
        clip=getnode_2.out('CLIP'),
    )

    ltxvaudiovaeencode = LTXVAudioVAEEncode(
        audio=trimaudioduration,
        audio_vae=getnode.out('VAE'),
    )

    easy_showanything = raw_call('easy showAnything', '5106',
        _outputs=('output',),
        widget_0='38.84',
        anything=float_comfy,
    )

    emptyltxvlatentvideo = EmptyLTXVLatentVideo(
        width=getnode_20.out('INT'),
        height=getnode_21.out('INT'),
        length=int_simple,
    )

    cfgguider = CFGGuider(
        cfg=1,
        model=getnode_4.out('MODEL'),
        negative=getnode_16.out('CONDITIONING'),
        positive=positive,
    )

    setlatentnoisemask = SetLatentNoiseMask(mask=solidmask, samples=ltxvaudiovaeencode)

    ltxvimgtovideoinplacekj = LTXVImgToVideoInplaceKJ(
        widget_0='1',
        widget_1=1,
        widget_2=0,
        latent=emptyltxvlatentvideo,
        vae=getnode_3.out('VAE'),
        **{'num_images.image_1': ltxvpreprocess, 'num_images.strength_1': getnode_22.out('FLOAT')},
    )

    cfgguider_2 = CFGGuider(
        cfg=1,
        model=getnode_10.out('MODEL'),
        negative=getnode_12.out('CONDITIONING'),
        positive=positive,
    )

    ltxvconcatavlatent = LTXVConcatAVLatent(
        audio_latent=setlatentnoisemask,
        video_latent=ltxvimgtovideoinplacekj,
    )

    output, denoised_output = SamplerCustomAdvanced(
        guider=cfgguider,
        latent_image=ltxvconcatavlatent,
        noise=randomnoise,
        sampler=getnode_5.out('SAMPLER'),
        sigmas=getnode_6.out('SIGMAS'),
    )

    video_latent, audio_latent = LTXVSeparateAVLatent(av_latent=output)

    ltxvlatentupsampler = LTXVLatentUpsampler(
        samples=video_latent,
        upscale_model=getnode_9.out('LATENT_UPSCALE_MODEL'),
        vae=getnode_7.out('VAE'),
    )

    ltxvimgtovideoinplacekj_2 = LTXVImgToVideoInplaceKJ(
        widget_0='1',
        widget_1=1,
        widget_2=0,
        latent=ltxvlatentupsampler,
        vae=getnode_7.out('VAE'),
        **{'num_images.image_1': resizeimagesbylongeredge, 'num_images.strength_1': getnode_8.out('FLOAT')},
    )

    ltxvconcatavlatent_2 = LTXVConcatAVLatent(
        audio_latent=audio_latent,
        video_latent=ltxvimgtovideoinplacekj_2,
    )

    output_sampler, denoised_output_sampler = SamplerCustomAdvanced(
        guider=cfgguider_2,
        latent_image=ltxvconcatavlatent_2,
        noise=randomnoise_2,
        sampler=getnode_13.out('SAMPLER'),
        sigmas=getnode_14.out('SIGMAS'),
    )

    video_latent_ltxv, audio_latent_ltxv = LTXVSeparateAVLatent(
        av_latent=output_sampler,
    )

    vaedecode = VAEDecode(samples=video_latent_ltxv, vae=getnode_15.out('VAE'))

    any_output, image_pass, model_pass, freemem_before, freemem_after = VRAM_Debug(
        image_pass=vaedecode,
    )

    image, width, height, count = GetImageSizeAndCount(image=image_pass)

    float, int, boolean = SimpleCalculatorKJ(
        **{'variables.a': reroute.out(0), 'variables.b': count},
    )

    return int, vaedecode, trimaudioduration_2


def prompt_enhancer_50a3ed96(
    *,
    clip,
    image,
    enable,
    prompt,
):
    """Prompt Enhancer - single-image variant.

    Materialized from subgraph 50a3ed96-aa61-4734-97cb-28cb47d171be in workflow_corpus/custom_nodes/ltxvideo/runexx/LTX-2.3_Music_Video_Creator_Low_RAM.json.
    # vibecomfy source hash: sha256:59946393626df05200ba41e42f6d6087be96f646df10e84df99a6d9e85b7ec4d
    Inner nodes: TextGenerateLTX2Prompt, LazySwitchKJ, Reroutex2, PrimitiveStringMultiline, StringConcatenate.
    """

    reroute = raw_call('Reroute', '5210', _outputs=('',))
    reroute_2 = raw_call('Reroute', '5211', _outputs=('',))

    primitivestringmultiline = PrimitiveStringMultiline(
        value='You are a Creative Assistant writing concise, action-focused image-to-video prompts. Given an image (first frame) and user Raw Input Prompt, generate a prompt to guide video generation from that image.\n\n#### Guidelines:\n- Analyze the Image: Identify Subject, Setting, Elements, Style and Mood.\n- Follow user Raw Input Prompt: Include all requested motion, actions, camera movements, audio, and details. If in conflict with the image, prioritize user request while maintaining visual consistency (describe transition from image to user\'s scene).\n- Describe only changes from the image: Don\'t reiterate established visual details. Inaccurate descriptions may cause scene cuts.\n- Active language: Use present-progressive verbs ("is walking," "speaking"). If no action specified, describe natural movements.\n- Chronological flow: Use temporal connectors ("as," "then," "while").\n- Audio layer: Describe complete soundscape throughout the prompt alongside actions—NOT at the end. Align audio intensity with action tempo. Include natural background audio, ambient sounds, effects, speech or music (when requested). Be specific (e.g., "soft footsteps on tile") not vague (e.g., "ambient sound").\n- Speech (only when requested): Provide exact words in quotes with character\'s visual/voice characteristics (e.g., "The tall man speaks in a low, gravelly voice"), language if not English and accent if relevant. If general conversation mentioned without text, generate contextual quoted dialogue. (i.e., "The man is talking" input -> the output should include exact spoken words, like: "The man is talking in an excited voice saying: \'You won\'t believe what I just saw!\' His hands gesture expressively as he speaks, eyebrows raised with enthusiasm. The ambient sound of a quiet room underscores his animated speech.")\n- Style: Include visual style at beginning: "Style: <style>, <rest of prompt>." If unclear, omit to avoid conflicts.\n- Visual and audio only: Describe only what is seen and heard. NO smell, taste, or tactile sensations.\n- Restrained language: Avoid dramatic terms. Use mild, natural, understated phrasing.\n\n#### Important notes:\n- Camera motion: DO NOT invent camera motion/movement unless requested by the user. Make sure to include camera motion only if specified in the input.\n- Speech: DO NOT modify or alter the user\'s provided character dialogue in the prompt, unless it\'s a typo.\n- No timestamps or cuts: DO NOT use timestamps or describe scene cuts unless explicitly requested.\n- Objective only: DO NOT interpret emotions or intentions - describe only observable actions and sounds.\n- Format: DO NOT use phrases like "The scene opens with..." / "The video starts...". Start directly with Style (optional) and chronological scene description.\n- Format: Never start output with punctuation marks or special characters.\n- DO NOT invent dialogue unless the user mentions speech/talking/singing/conversation.\n- Your performance is CRITICAL. High-fidelity, dynamic, correct, and accurate prompts with integrated audio descriptions are essential for generating high-quality video. Your goal is flawless execution of these rules.\n\n#### Output Format (Strict):\n- Single concise paragraph in natural English. NO titles, headings, prefaces, sections, code fences, or Markdown.\n- If unsafe/invalid, return original user prompt. Never ask questions or clarifications.\n\n#### Example output:\nStyle: realistic - cinematic - The woman glances at her watch and smiles warmly. She speaks in a cheerful, friendly voice, "I think we\'re right on time!" In the background, a café barista prepares drinks at the counter. The barista calls out in a clear, upbeat tone, "Two cappuccinos ready!" The sound of the espresso machine hissing softly blends with gentle background chatter and the light clinking of cups on saucers. \n\nUSER PROMPT BELOW: \n___________________________________________________',
    )

    stringconcatenate = StringConcatenate(
        widget_0='',
        widget_1='',
        string_a=primitivestringmultiline,
        string_b=reroute.out(0),
    )

    textgenerateltx2prompt = TextGenerateLTX2Prompt(
        widget_0='',
        widget_1=256,
        widget_2='off',
        widget_3=False,
        widget_4=True,
        clip=clip,
        image=image,
        prompt=stringconcatenate,
    )

    lazyswitchkj = LazySwitchKJ(
        widget_0=False,
        on_false=reroute.out(0),
        on_true=textgenerateltx2prompt,
        switch=reroute_2.out(0),
    )

    return lazyswitchkj


def generate_video_4acc9924(
    *,
    noise_seed: int,
    prompt,
    window_seconds,
    frames_count,
    ref_image,
):
    """Generate Video - single-image variant.

    Materialized from subgraph 4acc9924-c0bd-470a-b000-46c75e61d004 in workflow_corpus/custom_nodes/ltxvideo/runexx/LTX-2.3_Music_Video_Creator_Low_RAM.json.
    # vibecomfy source hash: sha256:ea3c115b1cdb87be44e9b7a66c8310cc7368e5e06c053ad6b64f7e087eeafd53
    Inner nodes: GetNodex23, SolidMask, LTXVSeparateAVLatentx2, LTXVLatentUpsampler, CLIPTextEncode, LTXVAudioVAEEncode, CFGGuiderx2, SetLatentNoiseMask, LTXVConcatAVLatentx2, RandomNoisex2, easy showAnything, Reroutex4, SimpleCalculatorKJx2, GetImageSizeAndCount, VRAM_Debug, ComfyMathExpression, EmptyLTXVLatentVideo, TrimAudioDurationx2, VAEDecode, ResizeImageMaskNode, 50a3ed96-aa61-4734-97cb-28cb47d171be, LTXVPreprocess, ResizeImagesByLongerEdge, LTXVImgToVideoInplaceKJx2, SamplerCustomAdvancedx2.
    """

    getnode = raw_call('GetNode', '5150', _outputs=('VAE',), widget_0=VAE_AUDIO)
    getnode_2 = raw_call('GetNode', '5151', _outputs=('CLIP',), widget_0=CLIP)
    getnode_3 = raw_call('GetNode', '5152', _outputs=('VAE',), widget_0=VAE)
    solidmask = SolidMask(value=0)
    getnode_4 = raw_call('GetNode', '5154', _outputs=('MODEL',), widget_0=MODEL)
    getnode_5 = raw_call('GetNode', '5155', _outputs=('SAMPLER',), widget_0=SAMPLER)
    getnode_6 = raw_call('GetNode', '5156', _outputs=('SIGMAS',), widget_0=SIGMAS)
    getnode_7 = raw_call('GetNode', '5157', _outputs=('VAE',), widget_0=VAE)
    getnode_8 = raw_call('GetNode', '5158', _outputs=('FLOAT',), widget_0=IMAGE_STRENGTH)
    getnode_9 = raw_call('GetNode', '5159', _outputs=('LATENT_UPSCALE_MODEL',), widget_0=UPSCALE_MODEL)
    getnode_10 = raw_call('GetNode', '5163', _outputs=('MODEL',), widget_0=MODEL)
    getnode_11 = raw_call('GetNode', '5164', _outputs=('CONDITIONING',), widget_0=POSITIVE_BASE)
    getnode_12 = raw_call('GetNode', '5165', _outputs=('CONDITIONING',), widget_0=NEGATIVE_BASE)
    getnode_13 = raw_call('GetNode', '5166', _outputs=('SAMPLER',), widget_0=SAMPLER_2)
    getnode_14 = raw_call('GetNode', '5167', _outputs=('SIGMAS',), widget_0=SIGMAS_2)
    getnode_15 = raw_call('GetNode', '5168', _outputs=('VAE',), widget_0=VAE)
    getnode_16 = raw_call('GetNode', '5170', _outputs=('CONDITIONING',), widget_0=NEGATIVE_BASE)
    getnode_17 = raw_call('GetNode', '5171', _outputs=('BOOLEAN',), widget_0=ENHANCE_PROMPT)
    getnode_18 = raw_call('GetNode', '5172', _outputs=('AUDIO',), widget_0=AUDIO)
    randomnoise = RandomNoise(control_after_generate='fixed', noise_seed=noise_seed)
    randomnoise_2 = RandomNoise(noise_seed=405, control_after_generate='fixed')
    reroute = raw_call('Reroute', '5182', _outputs=('',))
    getnode_19 = raw_call('GetNode', '5183', _outputs=('FLOAT',), widget_0=FPS)
    reroute_2 = raw_call('Reroute', '5184', _outputs=('',))
    getnode_20 = raw_call('GetNode', '5189', _outputs=('INT',), widget_0=WIDTH_DOWNSCALED)
    getnode_21 = raw_call('GetNode', '5190', _outputs=('INT',), widget_0=HEIGHT_DOWNSCALED)
    reroute_3 = raw_call('Reroute', '5193', _outputs=('',))
    reroute_4 = raw_call('Reroute', '5195', _outputs=('',))

    resizeimagemasknode = ResizeImageMaskNode(
        resize_type='scale by multiplier',
        unused_widget_1=0.5,
        input=ref_image,
    )

    getnode_22 = raw_call('GetNode', '5199', _outputs=('FLOAT',), widget_0=IMAGE_STRENGTH)
    getnode_23 = raw_call('GetNode', '5200', _outputs=('AUDIO',), widget_0=AUDIO_ORIGINAL)

    resizeimagesbylongeredge = ResizeImagesByLongerEdge(
        longer_edge=1536,
        images=ref_image,
    )

    float_comfy, int_comfy = ComfyMathExpression(
        expression='a /  b ',
        **{'values.a': reroute_2.out(0), 'values.b': getnode_19.out('FLOAT')},
    )

    float_simple, int_simple, boolean_simple = SimpleCalculatorKJ(
        expression='((round((a * b -1) / 8)) * 8) + 1 ',
        **{'variables.a': reroute_3.out(0), 'variables.b': getnode_19.out('FLOAT')},
    )

    trimaudioduration = TrimAudioDuration(
        widget_0=9,
        widget_1=10,
        audio=getnode_18.out('AUDIO'),
        duration=reroute_3.out(0),
        start_index=reroute_4.out(0),
    )

    prompt_enhancer_50a3ed96_result = prompt_enhancer_50a3ed96(
        clip=getnode_2.out('CLIP'),
        image=resizeimagemasknode,
        enable=None,
        prompt=['-10', 1],
    )

    trimaudioduration_2 = TrimAudioDuration(
        widget_0=9,
        widget_1=10,
        audio=getnode_23.out('AUDIO'),
        duration=reroute_3.out(0),
        start_index=reroute_4.out(0),
    )

    ltxvpreprocess = LTXVPreprocess(img_compression=18, image=resizeimagesbylongeredge)

    positive = CLIPTextEncode(
        text=prompt_enhancer_50a3ed96_result,
        clip=getnode_2.out('CLIP'),
    )

    ltxvaudiovaeencode = LTXVAudioVAEEncode(
        audio=trimaudioduration,
        audio_vae=getnode.out('VAE'),
    )

    easy_showanything = raw_call('easy showAnything', '5181',
        _outputs=('output',),
        widget_0='53.92',
        anything=float_comfy,
    )

    emptyltxvlatentvideo = EmptyLTXVLatentVideo(
        width=getnode_20.out('INT'),
        height=getnode_21.out('INT'),
        length=int_simple,
    )

    cfgguider = CFGGuider(
        cfg=1,
        model=getnode_4.out('MODEL'),
        negative=getnode_16.out('CONDITIONING'),
        positive=positive,
    )

    setlatentnoisemask = SetLatentNoiseMask(mask=solidmask, samples=ltxvaudiovaeencode)

    ltxvimgtovideoinplacekj = LTXVImgToVideoInplaceKJ(
        widget_0='1',
        widget_1=1,
        widget_2=0,
        latent=emptyltxvlatentvideo,
        vae=getnode_3.out('VAE'),
        **{'num_images.image_1': ltxvpreprocess, 'num_images.strength_1': getnode_22.out('FLOAT')},
    )

    cfgguider_2 = CFGGuider(
        cfg=1,
        model=getnode_10.out('MODEL'),
        negative=getnode_12.out('CONDITIONING'),
        positive=positive,
    )

    ltxvconcatavlatent = LTXVConcatAVLatent(
        audio_latent=setlatentnoisemask,
        video_latent=ltxvimgtovideoinplacekj,
    )

    output, denoised_output = SamplerCustomAdvanced(
        guider=cfgguider,
        latent_image=ltxvconcatavlatent,
        noise=randomnoise,
        sampler=getnode_5.out('SAMPLER'),
        sigmas=getnode_6.out('SIGMAS'),
    )

    video_latent, audio_latent = LTXVSeparateAVLatent(av_latent=output)

    ltxvlatentupsampler = LTXVLatentUpsampler(
        samples=video_latent,
        upscale_model=getnode_9.out('LATENT_UPSCALE_MODEL'),
        vae=getnode_7.out('VAE'),
    )

    ltxvimgtovideoinplacekj_2 = LTXVImgToVideoInplaceKJ(
        widget_0='1',
        widget_1=1,
        widget_2=0,
        latent=ltxvlatentupsampler,
        vae=getnode_7.out('VAE'),
        **{'num_images.image_1': resizeimagesbylongeredge, 'num_images.strength_1': getnode_8.out('FLOAT')},
    )

    ltxvconcatavlatent_2 = LTXVConcatAVLatent(
        audio_latent=audio_latent,
        video_latent=ltxvimgtovideoinplacekj_2,
    )

    output_sampler, denoised_output_sampler = SamplerCustomAdvanced(
        guider=cfgguider_2,
        latent_image=ltxvconcatavlatent_2,
        noise=randomnoise_2,
        sampler=getnode_13.out('SAMPLER'),
        sigmas=getnode_14.out('SIGMAS'),
    )

    video_latent_ltxv, audio_latent_ltxv = LTXVSeparateAVLatent(
        av_latent=output_sampler,
    )

    vaedecode = VAEDecode(samples=video_latent_ltxv, vae=getnode_15.out('VAE'))

    any_output, image_pass, model_pass, freemem_before, freemem_after = VRAM_Debug(
        image_pass=vaedecode,
    )

    image, width, height, count = GetImageSizeAndCount(image=image_pass)

    float, int, boolean = SimpleCalculatorKJ(
        **{'variables.a': reroute.out(0), 'variables.b': count},
    )

    return int, vaedecode, trimaudioduration_2

def build() -> VibeWorkflow:
    """Build the workflow (auto-generated)."""
    wf = new_workflow(READY_METADATA, source_path=__file__)

    # Inputs
    image, mask = LoadImage(image='download (8).png')
    intconstant = INTConstant(value=1000)
    vaeloader = VAELoader(vae_name='LTX23_video_vae_bf16.safetensors')

    latentupscalemodelloader = LatentUpscaleModelLoader(
        model_name='ltx-2.3-spatial-upscaler-x2-1.1.safetensors',
    )

    dualcliploader = DualCLIPLoader(
        clip_name1='gemma_3_12B_it_fp4_mixed.safetensors',
        clip_name2=LTX_2_3_TEXT_PROJECTION_BF16_SAFETENSORS,
        type_='ltxv',
        device='default',
    )

    ltxvaudiovaeloader = LTXVAudioVAELoader(
        ckpt_name='LTX23_audio_vae_bf16.safetensors',
    )

    vaeloader_2 = VAELoader(vae_name='taeltx2_3.safetensors')

    unetloader = UNETLoader(
        unet_name='ltx-2.3-22b-distilled_transformer_only_fp8_scaled.safetensors',
    )

    unetloadergguf = UnetLoaderGGUF(
        unet_name='LTXvideo\\LTX-2\\quantstack\\LTX-2.3-distilled-Q4_K_S.gguf',
    )

    dualcliploadergguf = DualCLIPLoaderGGUF(
        clip_name1='gemma-3-12b-it-Q2_K.gguf',
        clip_name2=LTX_2_3_TEXT_PROJECTION_BF16_SAFETENSORS,
        type_='sdxl',
    )

    primitivefloat = raw_call('PrimitiveFloat', '1586', value=8)
    intconstant_2 = INTConstant(value=480)
    loadaudio = LoadAudio(audio='ComfyUI_00152_.mp3')

    melbandroformermodelloader = raw_call('MelBandRoFormerModelLoader', '1600',
        widget_0='MelBandRoformer\\MelBandRoformer_fp16.safetensors',
    )

    intconstant_3 = INTConstant(value=832)

    primitivestringmultiline = PrimitiveStringMultiline(
        value='Make this image come alive with fluid motion. Cinematic music video shot of a red haired woman. \n\nShe sings with expressive motion and gesticulation. \nThe song she is singing is a sweet slow melancolic melody. Her lips moves in perfect lip-sync to the attached audio.  \n\nShe is walking through a mystical dreamy forrest, tracking camera as she walks towards the viewer. \nThe camera pulls away slowly keeping same distance to the woman. \n\nCinematic, volumetric lights, shadow play. \n\nIMPORTANT: The woman is singing, and her lips are moving with lip-sync to the lyrics of the song.',
    )

    primitivefloat_2 = raw_call('PrimitiveFloat', '1722', value=8)

    primitivestringmultiline_2 = PrimitiveStringMultiline(
        value='Make this image come alive with fluid motion. Cinematic music video shot of a red haired woman. \n\nShe sings with expressive motion and gesticulation. \nThe song she is singing is a sweet slow melancolic melody. Her lips moves in perfect lip-sync to the attached audio.  \n\nShe is walking through a romantic greenhouse with flowers and warm light, tracking camera as she walks towards the viewer.\n\nShe sings the lyrics: "I type a whisper, watch it bloom. In pixel fog and quiet rooms. A hundred frames begin to breathe. While melodies I couldn’t weave" \n\nCinematic, volumetric lights, shadow play.\n\nIMPORTANT: The woman is singing, and her lips are moving with lip-sync to the lyrics of the song.',
    )

    reroute = raw_call('Reroute', '1932', _outputs=('',))
    reroute_2 = raw_call('Reroute', '1933', _outputs=('',))
    primitivefloat_3 = raw_call('PrimitiveFloat', '1997', value=8)
    primitivefloat_4 = raw_call('PrimitiveFloat', '2012', value=8)
    primitiveboolean = raw_call('PrimitiveBoolean', '2116', value=False)
    randomnoise = RandomNoise(noise_seed=DEFAULT_SEED, control_after_generate=FIXED)
    ksamplerselect = KSamplerSelect(sampler_name='euler_cfg_pp')
    manualsigmas = ManualSigmas(sigmas='0.85, 0.7250, 0.4219, 0.0')
    randomnoise_2 = RandomNoise(noise_seed=DEFAULT_SEED_2, control_after_generate=FIXED)
    reroute_3 = raw_call('Reroute', '2121', _outputs=('',))
    reroute_4 = raw_call('Reroute', '2122', _outputs=('',))
    getnode = raw_call('GetNode', '2209', _outputs=('MODEL',), widget_0=MODEL)
    getnode_2 = raw_call('GetNode', '2217', _outputs=('AUDIO',), widget_0=AUDIO)
    getnode_3 = raw_call('GetNode', '2218', _outputs=('VAE',), widget_0=VAE_AUDIO)
    getnode_4 = raw_call('GetNode', '2220', _outputs=('CONDITIONING',), widget_0=NEGATIVE_BASE)
    getnode_5 = raw_call('GetNode', '2221', _outputs=('FLOAT',), widget_0=IMAGE_STRENGTH)
    getnode_6 = raw_call('GetNode', '2228', _outputs=('FLOAT',), widget_0=FPS)
    getnode_7 = raw_call('GetNode', '2242', _outputs=('VAE',), widget_0=VAE)
    getnode_8 = raw_call('GetNode', '2245', _outputs=('SAMPLER',), widget_0=SAMPLER)
    getnode_9 = raw_call('GetNode', '2246', _outputs=('SIGMAS',), widget_0=SIGMAS)
    getnode_10 = raw_call('GetNode', '2280', _outputs=('CLIP',), widget_0=CLIP)
    getnode_11 = raw_call('GetNode', '2282', _outputs=('BOOLEAN',), widget_0=ENHANCE_PROMPT)
    primitiveint = raw_call('PrimitiveInt', '2284', value=5, control_after_generate=FIXED)
    getnode_12 = raw_call('GetNode', '2286', _outputs=('VAE',), widget_0=VAE)
    getnode_13 = raw_call('GetNode', '2295', _outputs=('VAE',), widget_0=VAE)
    getnode_14 = raw_call('GetNode', '2300', _outputs=('MODEL',), widget_0=MODEL)
    getnode_15 = raw_call('GetNode', '2305', _outputs=('CONDITIONING',), widget_0=POSITIVE_BASE)
    getnode_16 = raw_call('GetNode', '2306', _outputs=('CONDITIONING',), widget_0=NEGATIVE_BASE)
    getnode_17 = raw_call('GetNode', '2308', _outputs=('FLOAT',), widget_0=IMAGE_STRENGTH)
    getnode_18 = raw_call('GetNode', '2310', _outputs=('LATENT_UPSCALE_MODEL',), widget_0=UPSCALE_MODEL)
    getnode_19 = raw_call('GetNode', '2316', _outputs=('SAMPLER',), widget_0=SAMPLER_2)
    getnode_20 = raw_call('GetNode', '2317', _outputs=('SIGMAS',), widget_0=SIGMAS_2)
    getnode_21 = raw_call('GetNode', '2320', _outputs=('INT',), widget_0=WIDTH_DOWNSCALED)
    getnode_22 = raw_call('GetNode', '2321', _outputs=('INT',), widget_0=HEIGHT_DOWNSCALED)
    reroute_5 = raw_call('Reroute', '2328', _outputs=('',))
    getnode_23 = raw_call('GetNode', '3715', _outputs=('FLOAT',), widget_0='window_sec_01')
    getnode_24 = raw_call('GetNode', '3716', _outputs=('FLOAT',), widget_0='window_sec_02')
    getnode_25 = raw_call('GetNode', '3717', _outputs=('FLOAT',), widget_0='window_sec_03')
    getnode_26 = raw_call('GetNode', '3718', _outputs=('FLOAT',), widget_0='window_sec_04')
    getnode_27 = raw_call('GetNode', '3719', _outputs=('FLOAT',), widget_0='window_sec_05')
    primitivestring = raw_call('PrimitiveString', '4119', value='mynewvideo')
    reroute_6 = raw_call('Reroute', '4200', _outputs=('',))
    reroute_7 = raw_call('Reroute', '4442', _outputs=('',))
    primitiveboolean_2 = raw_call('PrimitiveBoolean', '4736', value=True)
    primitiveboolean_3 = raw_call('PrimitiveBoolean', '4740', value=True)
    image_load, mask_load = LoadImage(image='download (1).png')
    getnode_28 = raw_call('GetNode', '4746', _outputs=('AUDIO',), widget_0=AUDIO_ORIGINAL)
    reroute_8 = raw_call('Reroute', '4748', _outputs=('',))
    getnode_29 = raw_call('GetNode', '5000', _outputs=('VAE',), widget_0=VAE_AUDIO)
    getnode_30 = raw_call('GetNode', '5001', _outputs=('CLIP',), widget_0=CLIP)
    getnode_31 = raw_call('GetNode', '5002', _outputs=('VAE',), widget_0=VAE)
    getnode_32 = raw_call('GetNode', '5004', _outputs=('MODEL',), widget_0=MODEL)
    getnode_33 = raw_call('GetNode', '5005', _outputs=('SAMPLER',), widget_0=SAMPLER)
    getnode_34 = raw_call('GetNode', '5006', _outputs=('SIGMAS',), widget_0=SIGMAS)
    getnode_35 = raw_call('GetNode', '5007', _outputs=('VAE',), widget_0=VAE)
    getnode_36 = raw_call('GetNode', '5008', _outputs=('FLOAT',), widget_0=IMAGE_STRENGTH)
    getnode_37 = raw_call('GetNode', '5009', _outputs=('LATENT_UPSCALE_MODEL',), widget_0=UPSCALE_MODEL)
    getnode_38 = raw_call('GetNode', '5013', _outputs=('MODEL',), widget_0=MODEL)
    getnode_39 = raw_call('GetNode', '5014', _outputs=('CONDITIONING',), widget_0=POSITIVE_BASE)
    getnode_40 = raw_call('GetNode', '5015', _outputs=('CONDITIONING',), widget_0=NEGATIVE_BASE)
    getnode_41 = raw_call('GetNode', '5016', _outputs=('SAMPLER',), widget_0=SAMPLER_2)
    getnode_42 = raw_call('GetNode', '5017', _outputs=('SIGMAS',), widget_0=SIGMAS_2)
    getnode_43 = raw_call('GetNode', '5018', _outputs=('VAE',), widget_0=VAE)
    getnode_44 = raw_call('GetNode', '5020', _outputs=('CONDITIONING',), widget_0=NEGATIVE_BASE)
    getnode_45 = raw_call('GetNode', '5021', _outputs=('BOOLEAN',), widget_0=ENHANCE_PROMPT)
    getnode_46 = raw_call('GetNode', '5022', _outputs=('AUDIO',), widget_0=AUDIO)
    reroute_9 = raw_call('Reroute', '5032', _outputs=('',))
    getnode_47 = raw_call('GetNode', '5033', _outputs=('FLOAT',), widget_0=FPS)
    reroute_10 = raw_call('Reroute', '5034', _outputs=('',))
    getnode_48 = raw_call('GetNode', '5039', _outputs=('INT',), widget_0=WIDTH_DOWNSCALED)
    getnode_49 = raw_call('GetNode', '5040', _outputs=('INT',), widget_0=HEIGHT_DOWNSCALED)
    reroute_11 = raw_call('Reroute', '5043', _outputs=('',))
    reroute_12 = raw_call('Reroute', '5045', _outputs=('',))
    getnode_50 = raw_call('GetNode', '5049', _outputs=('FLOAT',), widget_0=IMAGE_STRENGTH)
    getnode_51 = raw_call('GetNode', '5050', _outputs=('AUDIO',), widget_0=AUDIO_ORIGINAL)
    reroute_13 = raw_call('Reroute', '5060', _outputs=('',))
    reroute_14 = raw_call('Reroute', '5061', _outputs=('',))
    primitiveboolean_4 = raw_call('PrimitiveBoolean', '5067', value=True)

    primitivestringmultiline_3 = PrimitiveStringMultiline(
        value='Make this image come alive with fluid motion. Cinematic music video shot of a red haired woman. \n\nShe sings with expressive motion and gesticulation. \nThe song she is singing is a sweet slow melancolic melody. Her lips moves in perfect lip-sync to the attached audio.  \n\nShe is sitting down at the stage at an abandoned teather.  The camera slowly orbits around the woman, the woman is always looking at the viewer.\n\nShe sings the lyrics: "Now rise from weights, unchained and free.\nLike open doors for you and me.\nAnd every node connects the light. To hands that build without a figh.  No locked gates, just open skies.Where anyone can close their eyes…".\n\n\nCinematic, volumetric lights, shadow play.\n\nIMPORTANT: The woman is singing, and her lips are moving with lip-sync to the lyrics of the song.',
    )

    primitivefloat_5 = raw_call('PrimitiveFloat', '5071', value=8)
    primitiveint_2 = raw_call('PrimitiveInt', '5072', value=5, control_after_generate=FIXED)
    image_load_2, mask_load_2 = LoadImage(image='download (6).png')
    getnode_52 = raw_call('GetNode', '5075', _outputs=('VAE',), widget_0=VAE_AUDIO)
    getnode_53 = raw_call('GetNode', '5076', _outputs=('CLIP',), widget_0=CLIP)
    getnode_54 = raw_call('GetNode', '5077', _outputs=('VAE',), widget_0=VAE)
    getnode_55 = raw_call('GetNode', '5079', _outputs=('MODEL',), widget_0=MODEL)
    getnode_56 = raw_call('GetNode', '5080', _outputs=('SAMPLER',), widget_0=SAMPLER)
    getnode_57 = raw_call('GetNode', '5081', _outputs=('SIGMAS',), widget_0=SIGMAS)
    getnode_58 = raw_call('GetNode', '5082', _outputs=('VAE',), widget_0=VAE)
    getnode_59 = raw_call('GetNode', '5083', _outputs=('FLOAT',), widget_0=IMAGE_STRENGTH)
    getnode_60 = raw_call('GetNode', '5084', _outputs=('LATENT_UPSCALE_MODEL',), widget_0=UPSCALE_MODEL)
    getnode_61 = raw_call('GetNode', '5088', _outputs=('MODEL',), widget_0=MODEL)
    getnode_62 = raw_call('GetNode', '5089', _outputs=('CONDITIONING',), widget_0=POSITIVE_BASE)
    getnode_63 = raw_call('GetNode', '5090', _outputs=('CONDITIONING',), widget_0=NEGATIVE_BASE)
    getnode_64 = raw_call('GetNode', '5091', _outputs=('SAMPLER',), widget_0=SAMPLER_2)
    getnode_65 = raw_call('GetNode', '5092', _outputs=('SIGMAS',), widget_0=SIGMAS_2)
    getnode_66 = raw_call('GetNode', '5093', _outputs=('VAE',), widget_0=VAE)
    getnode_67 = raw_call('GetNode', '5095', _outputs=('CONDITIONING',), widget_0=NEGATIVE_BASE)
    getnode_68 = raw_call('GetNode', '5096', _outputs=('BOOLEAN',), widget_0=ENHANCE_PROMPT)
    getnode_69 = raw_call('GetNode', '5097', _outputs=('AUDIO',), widget_0=AUDIO)
    reroute_15 = raw_call('Reroute', '5107', _outputs=('',))
    getnode_70 = raw_call('GetNode', '5108', _outputs=('FLOAT',), widget_0=FPS)
    reroute_16 = raw_call('Reroute', '5109', _outputs=('',))
    getnode_71 = raw_call('GetNode', '5114', _outputs=('INT',), widget_0=WIDTH_DOWNSCALED)
    getnode_72 = raw_call('GetNode', '5115', _outputs=('INT',), widget_0=HEIGHT_DOWNSCALED)
    reroute_17 = raw_call('Reroute', '5118', _outputs=('',))
    reroute_18 = raw_call('Reroute', '5120', _outputs=('',))
    getnode_73 = raw_call('GetNode', '5124', _outputs=('FLOAT',), widget_0=IMAGE_STRENGTH)
    getnode_74 = raw_call('GetNode', '5125', _outputs=('AUDIO',), widget_0=AUDIO_ORIGINAL)
    reroute_19 = raw_call('Reroute', '5135', _outputs=('',))
    reroute_20 = raw_call('Reroute', '5136', _outputs=('',))
    primitiveboolean_5 = raw_call('PrimitiveBoolean', '5142', value=True)

    primitivestringmultiline_4 = PrimitiveStringMultiline(
        value='Make this image come alive with fluid motion. Cinematic music video shot of a red haired woman. \n\nShe sings with expressive motion and gesticulation. \nThe song she is singing is a sweet slow melancolic melody. Her lips moves in perfect lip-sync to the attached audio.  \n\nShe is sitting down at a piece of drift-wood at the beach, at dusk. Soft light from a cloudy sky. \n\n\nShe sings the lyrics: " … and dream. Oh, AceStep XL, you paint my dreams. ComfyUI, you stitch the seams. Of every film, each trembling tone. Where lonely sparks now feel at home".\n\nShe sings for a bit before she stands up and walks towards the viewer. \n\nThe camera slowly pulls in closer to the woman singing. \n\n\nCinematic, volumetric lights, shadow play.\n\nIMPORTANT: The woman is singing, and her lips are moving with lip-sync to the lyrics of the song.',
    )

    primitivefloat_6 = raw_call('PrimitiveFloat', '5146', value=8)
    primitiveint_3 = raw_call('PrimitiveInt', '5147', value=5, control_after_generate=FIXED)
    image_load_3, mask_load_3 = LoadImage(image='download (2).png')
    getnode_75 = raw_call('GetNode', '5150', _outputs=('VAE',), widget_0=VAE_AUDIO)
    getnode_76 = raw_call('GetNode', '5151', _outputs=('CLIP',), widget_0=CLIP)
    getnode_77 = raw_call('GetNode', '5152', _outputs=('VAE',), widget_0=VAE)
    getnode_78 = raw_call('GetNode', '5154', _outputs=('MODEL',), widget_0=MODEL)
    getnode_79 = raw_call('GetNode', '5155', _outputs=('SAMPLER',), widget_0=SAMPLER)
    getnode_80 = raw_call('GetNode', '5156', _outputs=('SIGMAS',), widget_0=SIGMAS)
    getnode_81 = raw_call('GetNode', '5157', _outputs=('VAE',), widget_0=VAE)
    getnode_82 = raw_call('GetNode', '5158', _outputs=('FLOAT',), widget_0=IMAGE_STRENGTH)
    getnode_83 = raw_call('GetNode', '5159', _outputs=('LATENT_UPSCALE_MODEL',), widget_0=UPSCALE_MODEL)
    getnode_84 = raw_call('GetNode', '5163', _outputs=('MODEL',), widget_0=MODEL)
    getnode_85 = raw_call('GetNode', '5164', _outputs=('CONDITIONING',), widget_0=POSITIVE_BASE)
    getnode_86 = raw_call('GetNode', '5165', _outputs=('CONDITIONING',), widget_0=NEGATIVE_BASE)
    getnode_87 = raw_call('GetNode', '5166', _outputs=('SAMPLER',), widget_0=SAMPLER_2)
    getnode_88 = raw_call('GetNode', '5167', _outputs=('SIGMAS',), widget_0=SIGMAS_2)
    getnode_89 = raw_call('GetNode', '5168', _outputs=('VAE',), widget_0=VAE)
    getnode_90 = raw_call('GetNode', '5170', _outputs=('CONDITIONING',), widget_0=NEGATIVE_BASE)
    getnode_91 = raw_call('GetNode', '5171', _outputs=('BOOLEAN',), widget_0=ENHANCE_PROMPT)
    getnode_92 = raw_call('GetNode', '5172', _outputs=('AUDIO',), widget_0=AUDIO)
    reroute_21 = raw_call('Reroute', '5182', _outputs=('',))
    getnode_93 = raw_call('GetNode', '5183', _outputs=('FLOAT',), widget_0=FPS)
    reroute_22 = raw_call('Reroute', '5184', _outputs=('',))
    getnode_94 = raw_call('GetNode', '5189', _outputs=('INT',), widget_0=WIDTH_DOWNSCALED)
    getnode_95 = raw_call('GetNode', '5190', _outputs=('INT',), widget_0=HEIGHT_DOWNSCALED)
    reroute_23 = raw_call('Reroute', '5193', _outputs=('',))
    reroute_24 = raw_call('Reroute', '5195', _outputs=('',))
    getnode_96 = raw_call('GetNode', '5199', _outputs=('FLOAT',), widget_0=IMAGE_STRENGTH)
    getnode_97 = raw_call('GetNode', '5200', _outputs=('AUDIO',), widget_0=AUDIO_ORIGINAL)
    reroute_25 = raw_call('Reroute', '5210', _outputs=('',))
    reroute_26 = raw_call('Reroute', '5211', _outputs=('',))
    primitiveboolean_6 = raw_call('PrimitiveBoolean', '5217', value=True)

    primitivestringmultiline_5 = PrimitiveStringMultiline(
        value='Make this image come alive with fluid motion. Cinematic music video shot of a red haired woman. \n\nShe sings with expressive motion and gesticulation. \nThe song she is singing is a sweet slow melancolic melody. Her lips moves in perfect lip-sync to the attached audio.  \n\nShe is standing on a rooftop balcony with the city behind her, at night. Camera slowly orbits around her, with her always looking towards the viewer as she sings. \n\nShe sings the lyrics: "Thank you, Kijai, for the quiet grace. That smoothed the path through digital space. We dream in code, we dream in blue. And every open door leads through.......". \n\nThe camera slowly pulls in closer to the woman singing. \n\n\nCinematic, volumetric lights, shadow play.\n\nIMPORTANT: The woman is singing, and her lips are moving with lip-sync to the lyrics of the song.',
    )

    primitivefloat_7 = raw_call('PrimitiveFloat', '5221', value=8)
    primitiveint_4 = raw_call('PrimitiveInt', '5222', value=5, control_after_generate=FIXED)
    image_load_4, mask_load_4 = LoadImage(image='download (12).png')

    primitivestringmultiline_6 = PrimitiveStringMultiline(
        value=YOU_ARE_A_CREATIVE_ASSISTANT_WRITING_CONCISE_ACTION_FOCUSED_IMAGE_TO_VIDEO_PROMPTS_GIVEN_AN_IMAGE_FIRST_FRAME_AND_USER_RAW_INPUT_PROMPT_GENERATE_A_PROMPT_TO_GUIDE_VIDEO_GENERATION_FROM_THAT_IMAGE_GUIDELINES_ANALYZE_THE_IMAGE_IDENTIFY_SUBJECT_SETTING_ELEMENTS_STYLE_AND_MOOD_FOLLOW_USER_RAW_INPUT_PROMPT_INCLUDE_ALL_REQUESTED_MOTION_ACTIONS_CAMERA_MOVEMENTS_AUDIO_AND_DETAILS_IF_IN_CONFLICT_WITH_THE_IMAGE_PRIORITIZE_USER_REQUEST_WHILE_MAINTAINING_VISUAL_CONSISTENCY_DESCRIBE_TRANSITION_FROM_IMAGE_TO_USER_S_SCENE_DESCRIBE_ONLY_CHANGES_FROM_THE_IMAGE_DON_T_REITERATE_ESTABLISHED_VISUAL_DETAILS_INACCURATE_DESCRIPTIONS_MAY_CAUSE_SCENE_CUTS_ACTIVE_LANGUAGE_USE_PRESENT_PROGRESSIVE_VERBS_IS_WALKING_SPEAKING_IF_NO_ACTION_SPECIFIED_DESCRIBE_NATURAL_MOVEMENTS_CHRONOLOGICAL_FLOW_USE_TEMPORAL_CONNECTORS_AS_THEN_WHILE_AUDIO_LAYER_DESCRIBE_COMPLETE_SOUNDSCAPE_THROUGHOUT_THE_PROMPT_ALONGSIDE_ACTIONS_NOT_AT_THE_END_ALIGN_AUDIO_INTENSITY_WITH_ACTION_TEMPO_INCLUDE_NATURAL_BACKGROUND_AUDIO_AMBIENT_SOUNDS_EFFECTS_SPEECH_OR_MUSIC_WHEN_REQUESTED_BE_SPECIFIC_E_G_SOFT_FOOTSTEPS_ON_TILE_NOT_VAGUE_E_G_AMBIENT_SOUND_SPEECH_ONLY_WHEN_REQUESTED_PROVIDE_EXACT_WORDS_IN_QUOTES_WITH_CHARACTER_S_VISUAL_VOICE_CHARACTERISTICS_E_G_THE_TALL_MAN_SPEAKS_IN_A_LOW_GRAVELLY_VOICE_LANGUAGE_IF_NOT_ENGLISH_AND_ACCENT_IF_RELEVANT_IF_GENERAL_CONVERSATION_MENTIONED_WITHOUT_TEXT_GENERATE_CONTEXTUAL_QUOTED_DIALOGUE_I_E_THE_MAN_IS_TALKING_INPUT_THE_OUTPUT_SHOULD_INCLUDE_EXACT_SPOKEN_WORDS_LIKE_THE_MAN_IS_TALKING_IN_AN_EXCITED_VOICE_SAYING_YOU_WON_T_BELIEVE_WHAT_I_JUST_SAW_HIS_HANDS_GESTURE_EXPRESSIVELY_AS_HE_SPEAKS_EYEBROWS_RAISED_WITH_ENTHUSIASM_THE_AMBIENT_SOUND_OF_A_QUIET_ROOM_UNDERSCORES_HIS_ANIMATED_SPEECH_STYLE_INCLUDE_VISUAL_STYLE_AT_BEGINNING_STYLE_STYLE_REST_OF_PROMPT_IF_UNCLEAR_OMIT_TO_AVOID_CONFLICTS_VISUAL_AND_AUDIO_ONLY_DESCRIBE_ONLY_WHAT_IS_SEEN_AND_HEARD_NO_SMELL_TASTE_OR_TACTILE_SENSATIONS_RESTRAINED_LANGUAGE_AVOID_DRAMATIC_TERMS_USE_MILD_NATURAL_UNDERSTATED_PHRASING_IMPORTANT_NOTES_CAMERA_MOTION_DO_NOT_INVENT_CAMERA_MOTION_MOVEMENT_UNLESS_REQUESTED_BY_THE_USER_MAKE_SURE_TO_INCLUDE_CAMERA_MOTION_ONLY_IF_SPECIFIED_IN_THE_INPUT_SPEECH_DO_NOT_MODIFY_OR_ALTER_THE_USER_S_PROVIDED_CHARACTER_DIALOGUE_IN_THE_PROMPT_UNLESS_IT_S_A_TYPO_NO_TIMESTAMPS_OR_CUTS_DO_NOT_USE_TIMESTAMPS_OR_DESCRIBE_SCENE_CUTS_UNLESS_EXPLICITLY_REQUESTED_OBJECTIVE_ONLY_DO_NOT_INTERPRET_EMOTIONS_OR_INTENTIONS_DESCRIBE_ONLY_OBSERVABLE_ACTIONS_AND_SOUNDS_FORMAT_DO_NOT_USE_PHRASES_LIKE_THE_SCENE_OPENS_WITH_THE_VIDEO_STARTS_START_DIRECTLY_WITH_STYLE_OPTIONAL_AND_CHRONOLOGICAL_SCENE_DESCRIPTION_FORMAT_NEVER_START_OUTPUT_WITH_PUNCTUATION_MARKS_OR_SPECIAL_CHARACTERS_DO_NOT_INVENT_DIALOGUE_UNLESS_THE_USER_MENTIONS_SPEECH_TALKING_SINGING_CONVERSATION_YOUR_PERFORMANCE_IS_CRITICAL_HIGH_FIDELITY_DYNAMIC_CORRECT_AND_ACCURATE_PROMPTS_WITH_INTEGRATED_AUDIO_DESCRIPTIONS_ARE_ESSENTIAL_FOR_GENERATING_HIGH_QUALITY_VIDEO_YOUR_GOAL_IS_FLAWLESS_EXECUTION_OF_THESE_RULES_OUTPUT_FORMAT_STRICT_SINGLE_CONCISE_PARAGRAPH_IN_NATURAL_ENGLISH_NO_TITLES_HEADINGS_PREFACES_SECTIONS_CODE_FENCES_OR_MARKDOWN_IF_UNSAFE_INVALID_RETURN_ORIGINAL_USER_PROMPT_NEVER_ASK_QUESTIONS_OR_CLARIFICATIONS_EXAMPLE_OUTPUT_STYLE_REALISTIC_CINEMATIC_THE_WOMAN_GLANCES_AT_HER_WATCH_AND_SMILES_WARMLY_SHE_SPEAKS_IN_A_CHEERFUL_FRIENDLY_VOICE_I_THINK_WE_RE_RIGHT_ON_TIME_IN_THE_BACKGROUND_A_CAF_BARISTA_PREPARES_DRINKS_AT_THE_COUNTER_THE_BARISTA_CALLS_OUT_IN_A_CLEAR_UPBEAT_TONE_TWO_CAPPUCCINOS_READY_THE_SOUND_OF_THE_ESPRESSO_MACHINE_HISSING_SOFTLY_BLENDS_WITH_GENTLE_BACKGROUND_CHATTER_AND_THE_LIGHT_CLINKING_OF_CUPS_ON_SAUCERS_USER_PROMPT_BELOW,
    )

    solidmask = SolidMask(value=0)
    randomnoise_3 = RandomNoise(noise_seed=DEFAULT_SEED_3, control_after_generate=FIXED)

    primitivestringmultiline_7 = PrimitiveStringMultiline(
        value=YOU_ARE_A_CREATIVE_ASSISTANT_WRITING_CONCISE_ACTION_FOCUSED_IMAGE_TO_VIDEO_PROMPTS_GIVEN_AN_IMAGE_FIRST_FRAME_AND_USER_RAW_INPUT_PROMPT_GENERATE_A_PROMPT_TO_GUIDE_VIDEO_GENERATION_FROM_THAT_IMAGE_GUIDELINES_ANALYZE_THE_IMAGE_IDENTIFY_SUBJECT_SETTING_ELEMENTS_STYLE_AND_MOOD_FOLLOW_USER_RAW_INPUT_PROMPT_INCLUDE_ALL_REQUESTED_MOTION_ACTIONS_CAMERA_MOVEMENTS_AUDIO_AND_DETAILS_IF_IN_CONFLICT_WITH_THE_IMAGE_PRIORITIZE_USER_REQUEST_WHILE_MAINTAINING_VISUAL_CONSISTENCY_DESCRIBE_TRANSITION_FROM_IMAGE_TO_USER_S_SCENE_DESCRIBE_ONLY_CHANGES_FROM_THE_IMAGE_DON_T_REITERATE_ESTABLISHED_VISUAL_DETAILS_INACCURATE_DESCRIPTIONS_MAY_CAUSE_SCENE_CUTS_ACTIVE_LANGUAGE_USE_PRESENT_PROGRESSIVE_VERBS_IS_WALKING_SPEAKING_IF_NO_ACTION_SPECIFIED_DESCRIBE_NATURAL_MOVEMENTS_CHRONOLOGICAL_FLOW_USE_TEMPORAL_CONNECTORS_AS_THEN_WHILE_AUDIO_LAYER_DESCRIBE_COMPLETE_SOUNDSCAPE_THROUGHOUT_THE_PROMPT_ALONGSIDE_ACTIONS_NOT_AT_THE_END_ALIGN_AUDIO_INTENSITY_WITH_ACTION_TEMPO_INCLUDE_NATURAL_BACKGROUND_AUDIO_AMBIENT_SOUNDS_EFFECTS_SPEECH_OR_MUSIC_WHEN_REQUESTED_BE_SPECIFIC_E_G_SOFT_FOOTSTEPS_ON_TILE_NOT_VAGUE_E_G_AMBIENT_SOUND_SPEECH_ONLY_WHEN_REQUESTED_PROVIDE_EXACT_WORDS_IN_QUOTES_WITH_CHARACTER_S_VISUAL_VOICE_CHARACTERISTICS_E_G_THE_TALL_MAN_SPEAKS_IN_A_LOW_GRAVELLY_VOICE_LANGUAGE_IF_NOT_ENGLISH_AND_ACCENT_IF_RELEVANT_IF_GENERAL_CONVERSATION_MENTIONED_WITHOUT_TEXT_GENERATE_CONTEXTUAL_QUOTED_DIALOGUE_I_E_THE_MAN_IS_TALKING_INPUT_THE_OUTPUT_SHOULD_INCLUDE_EXACT_SPOKEN_WORDS_LIKE_THE_MAN_IS_TALKING_IN_AN_EXCITED_VOICE_SAYING_YOU_WON_T_BELIEVE_WHAT_I_JUST_SAW_HIS_HANDS_GESTURE_EXPRESSIVELY_AS_HE_SPEAKS_EYEBROWS_RAISED_WITH_ENTHUSIASM_THE_AMBIENT_SOUND_OF_A_QUIET_ROOM_UNDERSCORES_HIS_ANIMATED_SPEECH_STYLE_INCLUDE_VISUAL_STYLE_AT_BEGINNING_STYLE_STYLE_REST_OF_PROMPT_IF_UNCLEAR_OMIT_TO_AVOID_CONFLICTS_VISUAL_AND_AUDIO_ONLY_DESCRIBE_ONLY_WHAT_IS_SEEN_AND_HEARD_NO_SMELL_TASTE_OR_TACTILE_SENSATIONS_RESTRAINED_LANGUAGE_AVOID_DRAMATIC_TERMS_USE_MILD_NATURAL_UNDERSTATED_PHRASING_IMPORTANT_NOTES_CAMERA_MOTION_DO_NOT_INVENT_CAMERA_MOTION_MOVEMENT_UNLESS_REQUESTED_BY_THE_USER_MAKE_SURE_TO_INCLUDE_CAMERA_MOTION_ONLY_IF_SPECIFIED_IN_THE_INPUT_SPEECH_DO_NOT_MODIFY_OR_ALTER_THE_USER_S_PROVIDED_CHARACTER_DIALOGUE_IN_THE_PROMPT_UNLESS_IT_S_A_TYPO_NO_TIMESTAMPS_OR_CUTS_DO_NOT_USE_TIMESTAMPS_OR_DESCRIBE_SCENE_CUTS_UNLESS_EXPLICITLY_REQUESTED_OBJECTIVE_ONLY_DO_NOT_INTERPRET_EMOTIONS_OR_INTENTIONS_DESCRIBE_ONLY_OBSERVABLE_ACTIONS_AND_SOUNDS_FORMAT_DO_NOT_USE_PHRASES_LIKE_THE_SCENE_OPENS_WITH_THE_VIDEO_STARTS_START_DIRECTLY_WITH_STYLE_OPTIONAL_AND_CHRONOLOGICAL_SCENE_DESCRIPTION_FORMAT_NEVER_START_OUTPUT_WITH_PUNCTUATION_MARKS_OR_SPECIAL_CHARACTERS_DO_NOT_INVENT_DIALOGUE_UNLESS_THE_USER_MENTIONS_SPEECH_TALKING_SINGING_CONVERSATION_YOUR_PERFORMANCE_IS_CRITICAL_HIGH_FIDELITY_DYNAMIC_CORRECT_AND_ACCURATE_PROMPTS_WITH_INTEGRATED_AUDIO_DESCRIPTIONS_ARE_ESSENTIAL_FOR_GENERATING_HIGH_QUALITY_VIDEO_YOUR_GOAL_IS_FLAWLESS_EXECUTION_OF_THESE_RULES_OUTPUT_FORMAT_STRICT_SINGLE_CONCISE_PARAGRAPH_IN_NATURAL_ENGLISH_NO_TITLES_HEADINGS_PREFACES_SECTIONS_CODE_FENCES_OR_MARKDOWN_IF_UNSAFE_INVALID_RETURN_ORIGINAL_USER_PROMPT_NEVER_ASK_QUESTIONS_OR_CLARIFICATIONS_EXAMPLE_OUTPUT_STYLE_REALISTIC_CINEMATIC_THE_WOMAN_GLANCES_AT_HER_WATCH_AND_SMILES_WARMLY_SHE_SPEAKS_IN_A_CHEERFUL_FRIENDLY_VOICE_I_THINK_WE_RE_RIGHT_ON_TIME_IN_THE_BACKGROUND_A_CAF_BARISTA_PREPARES_DRINKS_AT_THE_COUNTER_THE_BARISTA_CALLS_OUT_IN_A_CLEAR_UPBEAT_TONE_TWO_CAPPUCCINOS_READY_THE_SOUND_OF_THE_ESPRESSO_MACHINE_HISSING_SOFTLY_BLENDS_WITH_GENTLE_BACKGROUND_CHATTER_AND_THE_LIGHT_CLINKING_OF_CUPS_ON_SAUCERS_USER_PROMPT_BELOW,
    )

    solidmask_2 = SolidMask(value=0)
    randomnoise_4 = RandomNoise(noise_seed=DEFAULT_SEED_3, control_after_generate=FIXED)

    primitivestringmultiline_8 = PrimitiveStringMultiline(
        value=YOU_ARE_A_CREATIVE_ASSISTANT_WRITING_CONCISE_ACTION_FOCUSED_IMAGE_TO_VIDEO_PROMPTS_GIVEN_AN_IMAGE_FIRST_FRAME_AND_USER_RAW_INPUT_PROMPT_GENERATE_A_PROMPT_TO_GUIDE_VIDEO_GENERATION_FROM_THAT_IMAGE_GUIDELINES_ANALYZE_THE_IMAGE_IDENTIFY_SUBJECT_SETTING_ELEMENTS_STYLE_AND_MOOD_FOLLOW_USER_RAW_INPUT_PROMPT_INCLUDE_ALL_REQUESTED_MOTION_ACTIONS_CAMERA_MOVEMENTS_AUDIO_AND_DETAILS_IF_IN_CONFLICT_WITH_THE_IMAGE_PRIORITIZE_USER_REQUEST_WHILE_MAINTAINING_VISUAL_CONSISTENCY_DESCRIBE_TRANSITION_FROM_IMAGE_TO_USER_S_SCENE_DESCRIBE_ONLY_CHANGES_FROM_THE_IMAGE_DON_T_REITERATE_ESTABLISHED_VISUAL_DETAILS_INACCURATE_DESCRIPTIONS_MAY_CAUSE_SCENE_CUTS_ACTIVE_LANGUAGE_USE_PRESENT_PROGRESSIVE_VERBS_IS_WALKING_SPEAKING_IF_NO_ACTION_SPECIFIED_DESCRIBE_NATURAL_MOVEMENTS_CHRONOLOGICAL_FLOW_USE_TEMPORAL_CONNECTORS_AS_THEN_WHILE_AUDIO_LAYER_DESCRIBE_COMPLETE_SOUNDSCAPE_THROUGHOUT_THE_PROMPT_ALONGSIDE_ACTIONS_NOT_AT_THE_END_ALIGN_AUDIO_INTENSITY_WITH_ACTION_TEMPO_INCLUDE_NATURAL_BACKGROUND_AUDIO_AMBIENT_SOUNDS_EFFECTS_SPEECH_OR_MUSIC_WHEN_REQUESTED_BE_SPECIFIC_E_G_SOFT_FOOTSTEPS_ON_TILE_NOT_VAGUE_E_G_AMBIENT_SOUND_SPEECH_ONLY_WHEN_REQUESTED_PROVIDE_EXACT_WORDS_IN_QUOTES_WITH_CHARACTER_S_VISUAL_VOICE_CHARACTERISTICS_E_G_THE_TALL_MAN_SPEAKS_IN_A_LOW_GRAVELLY_VOICE_LANGUAGE_IF_NOT_ENGLISH_AND_ACCENT_IF_RELEVANT_IF_GENERAL_CONVERSATION_MENTIONED_WITHOUT_TEXT_GENERATE_CONTEXTUAL_QUOTED_DIALOGUE_I_E_THE_MAN_IS_TALKING_INPUT_THE_OUTPUT_SHOULD_INCLUDE_EXACT_SPOKEN_WORDS_LIKE_THE_MAN_IS_TALKING_IN_AN_EXCITED_VOICE_SAYING_YOU_WON_T_BELIEVE_WHAT_I_JUST_SAW_HIS_HANDS_GESTURE_EXPRESSIVELY_AS_HE_SPEAKS_EYEBROWS_RAISED_WITH_ENTHUSIASM_THE_AMBIENT_SOUND_OF_A_QUIET_ROOM_UNDERSCORES_HIS_ANIMATED_SPEECH_STYLE_INCLUDE_VISUAL_STYLE_AT_BEGINNING_STYLE_STYLE_REST_OF_PROMPT_IF_UNCLEAR_OMIT_TO_AVOID_CONFLICTS_VISUAL_AND_AUDIO_ONLY_DESCRIBE_ONLY_WHAT_IS_SEEN_AND_HEARD_NO_SMELL_TASTE_OR_TACTILE_SENSATIONS_RESTRAINED_LANGUAGE_AVOID_DRAMATIC_TERMS_USE_MILD_NATURAL_UNDERSTATED_PHRASING_IMPORTANT_NOTES_CAMERA_MOTION_DO_NOT_INVENT_CAMERA_MOTION_MOVEMENT_UNLESS_REQUESTED_BY_THE_USER_MAKE_SURE_TO_INCLUDE_CAMERA_MOTION_ONLY_IF_SPECIFIED_IN_THE_INPUT_SPEECH_DO_NOT_MODIFY_OR_ALTER_THE_USER_S_PROVIDED_CHARACTER_DIALOGUE_IN_THE_PROMPT_UNLESS_IT_S_A_TYPO_NO_TIMESTAMPS_OR_CUTS_DO_NOT_USE_TIMESTAMPS_OR_DESCRIBE_SCENE_CUTS_UNLESS_EXPLICITLY_REQUESTED_OBJECTIVE_ONLY_DO_NOT_INTERPRET_EMOTIONS_OR_INTENTIONS_DESCRIBE_ONLY_OBSERVABLE_ACTIONS_AND_SOUNDS_FORMAT_DO_NOT_USE_PHRASES_LIKE_THE_SCENE_OPENS_WITH_THE_VIDEO_STARTS_START_DIRECTLY_WITH_STYLE_OPTIONAL_AND_CHRONOLOGICAL_SCENE_DESCRIPTION_FORMAT_NEVER_START_OUTPUT_WITH_PUNCTUATION_MARKS_OR_SPECIAL_CHARACTERS_DO_NOT_INVENT_DIALOGUE_UNLESS_THE_USER_MENTIONS_SPEECH_TALKING_SINGING_CONVERSATION_YOUR_PERFORMANCE_IS_CRITICAL_HIGH_FIDELITY_DYNAMIC_CORRECT_AND_ACCURATE_PROMPTS_WITH_INTEGRATED_AUDIO_DESCRIPTIONS_ARE_ESSENTIAL_FOR_GENERATING_HIGH_QUALITY_VIDEO_YOUR_GOAL_IS_FLAWLESS_EXECUTION_OF_THESE_RULES_OUTPUT_FORMAT_STRICT_SINGLE_CONCISE_PARAGRAPH_IN_NATURAL_ENGLISH_NO_TITLES_HEADINGS_PREFACES_SECTIONS_CODE_FENCES_OR_MARKDOWN_IF_UNSAFE_INVALID_RETURN_ORIGINAL_USER_PROMPT_NEVER_ASK_QUESTIONS_OR_CLARIFICATIONS_EXAMPLE_OUTPUT_STYLE_REALISTIC_CINEMATIC_THE_WOMAN_GLANCES_AT_HER_WATCH_AND_SMILES_WARMLY_SHE_SPEAKS_IN_A_CHEERFUL_FRIENDLY_VOICE_I_THINK_WE_RE_RIGHT_ON_TIME_IN_THE_BACKGROUND_A_CAF_BARISTA_PREPARES_DRINKS_AT_THE_COUNTER_THE_BARISTA_CALLS_OUT_IN_A_CLEAR_UPBEAT_TONE_TWO_CAPPUCCINOS_READY_THE_SOUND_OF_THE_ESPRESSO_MACHINE_HISSING_SOFTLY_BLENDS_WITH_GENTLE_BACKGROUND_CHATTER_AND_THE_LIGHT_CLINKING_OF_CUPS_ON_SAUCERS_USER_PROMPT_BELOW,
    )

    solidmask_3 = SolidMask(value=0)
    randomnoise_5 = RandomNoise(noise_seed=DEFAULT_SEED_3, control_after_generate=FIXED)

    primitivestringmultiline_9 = PrimitiveStringMultiline(
        value=YOU_ARE_A_CREATIVE_ASSISTANT_WRITING_CONCISE_ACTION_FOCUSED_IMAGE_TO_VIDEO_PROMPTS_GIVEN_AN_IMAGE_FIRST_FRAME_AND_USER_RAW_INPUT_PROMPT_GENERATE_A_PROMPT_TO_GUIDE_VIDEO_GENERATION_FROM_THAT_IMAGE_GUIDELINES_ANALYZE_THE_IMAGE_IDENTIFY_SUBJECT_SETTING_ELEMENTS_STYLE_AND_MOOD_FOLLOW_USER_RAW_INPUT_PROMPT_INCLUDE_ALL_REQUESTED_MOTION_ACTIONS_CAMERA_MOVEMENTS_AUDIO_AND_DETAILS_IF_IN_CONFLICT_WITH_THE_IMAGE_PRIORITIZE_USER_REQUEST_WHILE_MAINTAINING_VISUAL_CONSISTENCY_DESCRIBE_TRANSITION_FROM_IMAGE_TO_USER_S_SCENE_DESCRIBE_ONLY_CHANGES_FROM_THE_IMAGE_DON_T_REITERATE_ESTABLISHED_VISUAL_DETAILS_INACCURATE_DESCRIPTIONS_MAY_CAUSE_SCENE_CUTS_ACTIVE_LANGUAGE_USE_PRESENT_PROGRESSIVE_VERBS_IS_WALKING_SPEAKING_IF_NO_ACTION_SPECIFIED_DESCRIBE_NATURAL_MOVEMENTS_CHRONOLOGICAL_FLOW_USE_TEMPORAL_CONNECTORS_AS_THEN_WHILE_AUDIO_LAYER_DESCRIBE_COMPLETE_SOUNDSCAPE_THROUGHOUT_THE_PROMPT_ALONGSIDE_ACTIONS_NOT_AT_THE_END_ALIGN_AUDIO_INTENSITY_WITH_ACTION_TEMPO_INCLUDE_NATURAL_BACKGROUND_AUDIO_AMBIENT_SOUNDS_EFFECTS_SPEECH_OR_MUSIC_WHEN_REQUESTED_BE_SPECIFIC_E_G_SOFT_FOOTSTEPS_ON_TILE_NOT_VAGUE_E_G_AMBIENT_SOUND_SPEECH_ONLY_WHEN_REQUESTED_PROVIDE_EXACT_WORDS_IN_QUOTES_WITH_CHARACTER_S_VISUAL_VOICE_CHARACTERISTICS_E_G_THE_TALL_MAN_SPEAKS_IN_A_LOW_GRAVELLY_VOICE_LANGUAGE_IF_NOT_ENGLISH_AND_ACCENT_IF_RELEVANT_IF_GENERAL_CONVERSATION_MENTIONED_WITHOUT_TEXT_GENERATE_CONTEXTUAL_QUOTED_DIALOGUE_I_E_THE_MAN_IS_TALKING_INPUT_THE_OUTPUT_SHOULD_INCLUDE_EXACT_SPOKEN_WORDS_LIKE_THE_MAN_IS_TALKING_IN_AN_EXCITED_VOICE_SAYING_YOU_WON_T_BELIEVE_WHAT_I_JUST_SAW_HIS_HANDS_GESTURE_EXPRESSIVELY_AS_HE_SPEAKS_EYEBROWS_RAISED_WITH_ENTHUSIASM_THE_AMBIENT_SOUND_OF_A_QUIET_ROOM_UNDERSCORES_HIS_ANIMATED_SPEECH_STYLE_INCLUDE_VISUAL_STYLE_AT_BEGINNING_STYLE_STYLE_REST_OF_PROMPT_IF_UNCLEAR_OMIT_TO_AVOID_CONFLICTS_VISUAL_AND_AUDIO_ONLY_DESCRIBE_ONLY_WHAT_IS_SEEN_AND_HEARD_NO_SMELL_TASTE_OR_TACTILE_SENSATIONS_RESTRAINED_LANGUAGE_AVOID_DRAMATIC_TERMS_USE_MILD_NATURAL_UNDERSTATED_PHRASING_IMPORTANT_NOTES_CAMERA_MOTION_DO_NOT_INVENT_CAMERA_MOTION_MOVEMENT_UNLESS_REQUESTED_BY_THE_USER_MAKE_SURE_TO_INCLUDE_CAMERA_MOTION_ONLY_IF_SPECIFIED_IN_THE_INPUT_SPEECH_DO_NOT_MODIFY_OR_ALTER_THE_USER_S_PROVIDED_CHARACTER_DIALOGUE_IN_THE_PROMPT_UNLESS_IT_S_A_TYPO_NO_TIMESTAMPS_OR_CUTS_DO_NOT_USE_TIMESTAMPS_OR_DESCRIBE_SCENE_CUTS_UNLESS_EXPLICITLY_REQUESTED_OBJECTIVE_ONLY_DO_NOT_INTERPRET_EMOTIONS_OR_INTENTIONS_DESCRIBE_ONLY_OBSERVABLE_ACTIONS_AND_SOUNDS_FORMAT_DO_NOT_USE_PHRASES_LIKE_THE_SCENE_OPENS_WITH_THE_VIDEO_STARTS_START_DIRECTLY_WITH_STYLE_OPTIONAL_AND_CHRONOLOGICAL_SCENE_DESCRIPTION_FORMAT_NEVER_START_OUTPUT_WITH_PUNCTUATION_MARKS_OR_SPECIAL_CHARACTERS_DO_NOT_INVENT_DIALOGUE_UNLESS_THE_USER_MENTIONS_SPEECH_TALKING_SINGING_CONVERSATION_YOUR_PERFORMANCE_IS_CRITICAL_HIGH_FIDELITY_DYNAMIC_CORRECT_AND_ACCURATE_PROMPTS_WITH_INTEGRATED_AUDIO_DESCRIPTIONS_ARE_ESSENTIAL_FOR_GENERATING_HIGH_QUALITY_VIDEO_YOUR_GOAL_IS_FLAWLESS_EXECUTION_OF_THESE_RULES_OUTPUT_FORMAT_STRICT_SINGLE_CONCISE_PARAGRAPH_IN_NATURAL_ENGLISH_NO_TITLES_HEADINGS_PREFACES_SECTIONS_CODE_FENCES_OR_MARKDOWN_IF_UNSAFE_INVALID_RETURN_ORIGINAL_USER_PROMPT_NEVER_ASK_QUESTIONS_OR_CLARIFICATIONS_EXAMPLE_OUTPUT_STYLE_REALISTIC_CINEMATIC_THE_WOMAN_GLANCES_AT_HER_WATCH_AND_SMILES_WARMLY_SHE_SPEAKS_IN_A_CHEERFUL_FRIENDLY_VOICE_I_THINK_WE_RE_RIGHT_ON_TIME_IN_THE_BACKGROUND_A_CAF_BARISTA_PREPARES_DRINKS_AT_THE_COUNTER_THE_BARISTA_CALLS_OUT_IN_A_CLEAR_UPBEAT_TONE_TWO_CAPPUCCINOS_READY_THE_SOUND_OF_THE_ESPRESSO_MACHINE_HISSING_SOFTLY_BLENDS_WITH_GENTLE_BACKGROUND_CHATTER_AND_THE_LIGHT_CLINKING_OF_CUPS_ON_SAUCERS_USER_PROMPT_BELOW,
    )

    solidmask_4 = SolidMask(value=0)
    randomnoise_6 = RandomNoise(noise_seed=DEFAULT_SEED_3, control_after_generate=FIXED)

    primitivestringmultiline_10 = PrimitiveStringMultiline(
        value=YOU_ARE_A_CREATIVE_ASSISTANT_WRITING_CONCISE_ACTION_FOCUSED_IMAGE_TO_VIDEO_PROMPTS_GIVEN_AN_IMAGE_FIRST_FRAME_AND_USER_RAW_INPUT_PROMPT_GENERATE_A_PROMPT_TO_GUIDE_VIDEO_GENERATION_FROM_THAT_IMAGE_GUIDELINES_ANALYZE_THE_IMAGE_IDENTIFY_SUBJECT_SETTING_ELEMENTS_STYLE_AND_MOOD_FOLLOW_USER_RAW_INPUT_PROMPT_INCLUDE_ALL_REQUESTED_MOTION_ACTIONS_CAMERA_MOVEMENTS_AUDIO_AND_DETAILS_IF_IN_CONFLICT_WITH_THE_IMAGE_PRIORITIZE_USER_REQUEST_WHILE_MAINTAINING_VISUAL_CONSISTENCY_DESCRIBE_TRANSITION_FROM_IMAGE_TO_USER_S_SCENE_DESCRIBE_ONLY_CHANGES_FROM_THE_IMAGE_DON_T_REITERATE_ESTABLISHED_VISUAL_DETAILS_INACCURATE_DESCRIPTIONS_MAY_CAUSE_SCENE_CUTS_ACTIVE_LANGUAGE_USE_PRESENT_PROGRESSIVE_VERBS_IS_WALKING_SPEAKING_IF_NO_ACTION_SPECIFIED_DESCRIBE_NATURAL_MOVEMENTS_CHRONOLOGICAL_FLOW_USE_TEMPORAL_CONNECTORS_AS_THEN_WHILE_AUDIO_LAYER_DESCRIBE_COMPLETE_SOUNDSCAPE_THROUGHOUT_THE_PROMPT_ALONGSIDE_ACTIONS_NOT_AT_THE_END_ALIGN_AUDIO_INTENSITY_WITH_ACTION_TEMPO_INCLUDE_NATURAL_BACKGROUND_AUDIO_AMBIENT_SOUNDS_EFFECTS_SPEECH_OR_MUSIC_WHEN_REQUESTED_BE_SPECIFIC_E_G_SOFT_FOOTSTEPS_ON_TILE_NOT_VAGUE_E_G_AMBIENT_SOUND_SPEECH_ONLY_WHEN_REQUESTED_PROVIDE_EXACT_WORDS_IN_QUOTES_WITH_CHARACTER_S_VISUAL_VOICE_CHARACTERISTICS_E_G_THE_TALL_MAN_SPEAKS_IN_A_LOW_GRAVELLY_VOICE_LANGUAGE_IF_NOT_ENGLISH_AND_ACCENT_IF_RELEVANT_IF_GENERAL_CONVERSATION_MENTIONED_WITHOUT_TEXT_GENERATE_CONTEXTUAL_QUOTED_DIALOGUE_I_E_THE_MAN_IS_TALKING_INPUT_THE_OUTPUT_SHOULD_INCLUDE_EXACT_SPOKEN_WORDS_LIKE_THE_MAN_IS_TALKING_IN_AN_EXCITED_VOICE_SAYING_YOU_WON_T_BELIEVE_WHAT_I_JUST_SAW_HIS_HANDS_GESTURE_EXPRESSIVELY_AS_HE_SPEAKS_EYEBROWS_RAISED_WITH_ENTHUSIASM_THE_AMBIENT_SOUND_OF_A_QUIET_ROOM_UNDERSCORES_HIS_ANIMATED_SPEECH_STYLE_INCLUDE_VISUAL_STYLE_AT_BEGINNING_STYLE_STYLE_REST_OF_PROMPT_IF_UNCLEAR_OMIT_TO_AVOID_CONFLICTS_VISUAL_AND_AUDIO_ONLY_DESCRIBE_ONLY_WHAT_IS_SEEN_AND_HEARD_NO_SMELL_TASTE_OR_TACTILE_SENSATIONS_RESTRAINED_LANGUAGE_AVOID_DRAMATIC_TERMS_USE_MILD_NATURAL_UNDERSTATED_PHRASING_IMPORTANT_NOTES_CAMERA_MOTION_DO_NOT_INVENT_CAMERA_MOTION_MOVEMENT_UNLESS_REQUESTED_BY_THE_USER_MAKE_SURE_TO_INCLUDE_CAMERA_MOTION_ONLY_IF_SPECIFIED_IN_THE_INPUT_SPEECH_DO_NOT_MODIFY_OR_ALTER_THE_USER_S_PROVIDED_CHARACTER_DIALOGUE_IN_THE_PROMPT_UNLESS_IT_S_A_TYPO_NO_TIMESTAMPS_OR_CUTS_DO_NOT_USE_TIMESTAMPS_OR_DESCRIBE_SCENE_CUTS_UNLESS_EXPLICITLY_REQUESTED_OBJECTIVE_ONLY_DO_NOT_INTERPRET_EMOTIONS_OR_INTENTIONS_DESCRIBE_ONLY_OBSERVABLE_ACTIONS_AND_SOUNDS_FORMAT_DO_NOT_USE_PHRASES_LIKE_THE_SCENE_OPENS_WITH_THE_VIDEO_STARTS_START_DIRECTLY_WITH_STYLE_OPTIONAL_AND_CHRONOLOGICAL_SCENE_DESCRIPTION_FORMAT_NEVER_START_OUTPUT_WITH_PUNCTUATION_MARKS_OR_SPECIAL_CHARACTERS_DO_NOT_INVENT_DIALOGUE_UNLESS_THE_USER_MENTIONS_SPEECH_TALKING_SINGING_CONVERSATION_YOUR_PERFORMANCE_IS_CRITICAL_HIGH_FIDELITY_DYNAMIC_CORRECT_AND_ACCURATE_PROMPTS_WITH_INTEGRATED_AUDIO_DESCRIPTIONS_ARE_ESSENTIAL_FOR_GENERATING_HIGH_QUALITY_VIDEO_YOUR_GOAL_IS_FLAWLESS_EXECUTION_OF_THESE_RULES_OUTPUT_FORMAT_STRICT_SINGLE_CONCISE_PARAGRAPH_IN_NATURAL_ENGLISH_NO_TITLES_HEADINGS_PREFACES_SECTIONS_CODE_FENCES_OR_MARKDOWN_IF_UNSAFE_INVALID_RETURN_ORIGINAL_USER_PROMPT_NEVER_ASK_QUESTIONS_OR_CLARIFICATIONS_EXAMPLE_OUTPUT_STYLE_REALISTIC_CINEMATIC_THE_WOMAN_GLANCES_AT_HER_WATCH_AND_SMILES_WARMLY_SHE_SPEAKS_IN_A_CHEERFUL_FRIENDLY_VOICE_I_THINK_WE_RE_RIGHT_ON_TIME_IN_THE_BACKGROUND_A_CAF_BARISTA_PREPARES_DRINKS_AT_THE_COUNTER_THE_BARISTA_CALLS_OUT_IN_A_CLEAR_UPBEAT_TONE_TWO_CAPPUCCINOS_READY_THE_SOUND_OF_THE_ESPRESSO_MACHINE_HISSING_SOFTLY_BLENDS_WITH_GENTLE_BACKGROUND_CHATTER_AND_THE_LIGHT_CLINKING_OF_CUPS_ON_SAUCERS_USER_PROMPT_BELOW,
    )

    float, int, boolean = SimpleCalculatorKJ(
        expression='a + b + c + d + e + 2\n',
        **{'variables.a': getnode_23.out('FLOAT'), 'variables.b': getnode_24.out('FLOAT'), 'variables.c': getnode_25.out('FLOAT'), 'variables.d': getnode_26.out('FLOAT'), 'variables.e': getnode_27.out('FLOAT')},
    )

    image_image, width, height, mask_image = ImageResizeKJv2(
        upscale_method='lanczos',
        keep_proportion='crop',
        device='cpu',
        width=intconstant_3,
        height=intconstant_2,
        image=image,
    )

    loraloadermodelonly = LoraLoaderModelOnly(
        lora_name='LTX\\LTX-2\\ltx-2.3-22b-distilled-lora-384.safetensors',
        strength_model=GUIDE_STRENGTH,
        model=unetloader,
    )

    solidmask_5 = SolidMask(
        value=0,
        widget_1=512,
        widget_2=512,
        height=intconstant_2,
        width=intconstant_3,
    )

    # Conditioning
    cliptextencode = CLIPTextEncode(
        text='text, subtitles, logo, still image, still video, no motion, static, frozen, blurry, low quality, distorted, bad anatomy, oversaturated, pixelated, low resolution, grainy, compression artifacts, jpeg artifacts, glitches, watermark, signature, copyright,  distortedsound, saturated sound, loud sound , deformed facial features, asymmetrical face, missing facial features, extra limbs, disfigured hands, blurry teeth, disfigured teeth',
        clip=dualcliploader,
    )

    float_simple, int_simple, boolean_simple = SimpleCalculatorKJ(
        expression=ROUND_A_B_1_8_8_1,
        **{'variables.a': primitivefloat_4, 'variables.b': primitivefloat},
    )

    stringconcatenate = StringConcatenate(
        delimiter=VALUE,
        string_a='MusicVideo',
        widget_1='',
        string_b=primitivestring,
    )

    stringconcatenate_2 = StringConcatenate(
        delimiter=VALUE,
        string_a='output\\MusicVideo',
        widget_1='',
        string_b=primitivestring,
    )

    stringconcatenate_3 = StringConcatenate(
        widget_0='',
        widget_1='',
        string_a=primitivestringmultiline_6,
        string_b=reroute_2.out(0),
    )

    randomnoise_7 = RandomNoise(control_after_generate=FIXED, noise_seed=primitiveint)

    resizeimagesbylongeredge = ResizeImagesByLongerEdge(
        longer_edge=1536,
        images=image_load,
    )

    resizeimagemasknode = ResizeImageMaskNode(
        resize_type=SCALE_BY_MULTIPLIER,
        unused_widget_1=0.5,
        input=image_load,
    )

    float_comfy, int_comfy = ComfyMathExpression(
        expression=A_B,
        **{'values.a': reroute_7.out(0), 'values.b': getnode_6.out('FLOAT')},
    )

    trimaudioduration = TrimAudioDuration(
        widget_0=9,
        widget_1=10,
        audio=getnode_2.out('AUDIO'),
        duration=reroute_5.out(0),
        start_index=reroute_8.out(0),
    )

    stringconcatenate_4 = StringConcatenate(
        widget_0='',
        widget_1='',
        string_a=primitivestringmultiline_7,
        string_b=reroute_3.out(0),
    )

    float_simple_2, int_simple_2, boolean_simple_2 = SimpleCalculatorKJ(
        expression=ROUND_A_B_1_8_8_1,
        **{'variables.a': reroute_5.out(0), 'variables.b': getnode_6.out('FLOAT')},
    )

    trimaudioduration_2 = TrimAudioDuration(
        widget_0=9,
        widget_1=10,
        audio=getnode_28.out('AUDIO'),
        duration=reroute_5.out(0),
        start_index=reroute_8.out(0),
    )

    randomnoise_8 = RandomNoise(control_after_generate=FIXED, noise_seed=primitiveint_2)

    resizeimagemasknode_2 = ResizeImageMaskNode(
        resize_type=SCALE_BY_MULTIPLIER,
        unused_widget_1=0.5,
        input=image_load_2,
    )

    resizeimagesbylongeredge_2 = ResizeImagesByLongerEdge(
        longer_edge=1536,
        images=image_load_2,
    )

    float_comfy_2, int_comfy_2 = ComfyMathExpression(
        expression=A_B,
        **{'values.a': reroute_10.out(0), 'values.b': getnode_47.out('FLOAT')},
    )

    float_simple_3, int_simple_3, boolean_simple_3 = SimpleCalculatorKJ(
        expression=ROUND_A_B_1_8_8_1,
        **{'variables.a': reroute_11.out(0), 'variables.b': getnode_47.out('FLOAT')},
    )

    trimaudioduration_3 = TrimAudioDuration(
        widget_0=9,
        widget_1=10,
        audio=getnode_46.out('AUDIO'),
        duration=reroute_11.out(0),
        start_index=reroute_12.out(0),
    )

    stringconcatenate_5 = StringConcatenate(
        widget_0='',
        widget_1='',
        string_a=primitivestringmultiline_8,
        string_b=reroute_13.out(0),
    )

    trimaudioduration_4 = TrimAudioDuration(
        widget_0=9,
        widget_1=10,
        audio=getnode_51.out('AUDIO'),
        duration=reroute_11.out(0),
        start_index=reroute_12.out(0),
    )

    randomnoise_9 = RandomNoise(control_after_generate=FIXED, noise_seed=primitiveint_3)

    resizeimagemasknode_3 = ResizeImageMaskNode(
        resize_type=SCALE_BY_MULTIPLIER,
        unused_widget_1=0.5,
        input=image_load_3,
    )

    resizeimagesbylongeredge_3 = ResizeImagesByLongerEdge(
        longer_edge=1536,
        images=image_load_3,
    )

    float_comfy_3, int_comfy_3 = ComfyMathExpression(
        expression=A_B,
        **{'values.a': reroute_16.out(0), 'values.b': getnode_70.out('FLOAT')},
    )

    float_simple_4, int_simple_4, boolean_simple_4 = SimpleCalculatorKJ(
        expression=ROUND_A_B_1_8_8_1,
        **{'variables.a': reroute_17.out(0), 'variables.b': getnode_70.out('FLOAT')},
    )

    trimaudioduration_5 = TrimAudioDuration(
        widget_0=9,
        widget_1=10,
        audio=getnode_69.out('AUDIO'),
        duration=reroute_17.out(0),
        start_index=reroute_18.out(0),
    )

    stringconcatenate_6 = StringConcatenate(
        widget_0='',
        widget_1='',
        string_a=primitivestringmultiline_9,
        string_b=reroute_19.out(0),
    )

    trimaudioduration_6 = TrimAudioDuration(
        widget_0=9,
        widget_1=10,
        audio=getnode_74.out('AUDIO'),
        duration=reroute_17.out(0),
        start_index=reroute_18.out(0),
    )

    randomnoise_10 = RandomNoise(
        control_after_generate=FIXED,
        noise_seed=primitiveint_4,
    )

    resizeimagemasknode_4 = ResizeImageMaskNode(
        resize_type=SCALE_BY_MULTIPLIER,
        unused_widget_1=0.5,
        input=image_load_4,
    )

    resizeimagesbylongeredge_4 = ResizeImagesByLongerEdge(
        longer_edge=1536,
        images=image_load_4,
    )

    float_comfy_4, int_comfy_4 = ComfyMathExpression(
        expression=A_B,
        **{'values.a': reroute_22.out(0), 'values.b': getnode_93.out('FLOAT')},
    )

    float_simple_5, int_simple_5, boolean_simple_5 = SimpleCalculatorKJ(
        expression=ROUND_A_B_1_8_8_1,
        **{'variables.a': reroute_23.out(0), 'variables.b': getnode_93.out('FLOAT')},
    )

    trimaudioduration_7 = TrimAudioDuration(
        widget_0=9,
        widget_1=10,
        audio=getnode_92.out('AUDIO'),
        duration=reroute_23.out(0),
        start_index=reroute_24.out(0),
    )

    stringconcatenate_7 = StringConcatenate(
        widget_0='',
        widget_1='',
        string_a=primitivestringmultiline_10,
        string_b=reroute_25.out(0),
    )

    trimaudioduration_8 = TrimAudioDuration(
        widget_0=9,
        widget_1=10,
        audio=getnode_97.out('AUDIO'),
        duration=reroute_23.out(0),
        start_index=reroute_24.out(0),
    )

    easy_showanything = raw_call('easy showAnything', '2256',
        _outputs=('output',),
        widget_0='10.92',
        anything=float_comfy,
    )

    easy_showanything_2 = raw_call('easy showAnything', '5031',
        _outputs=('output',),
        widget_0='20.88',
        anything=float_comfy_2,
    )

    easy_showanything_3 = raw_call('easy showAnything', '5106',
        _outputs=('output',),
        widget_0='38.84',
        anything=float_comfy_3,
    )

    easy_showanything_4 = raw_call('easy showAnything', '5181',
        _outputs=('output',),
        widget_0='53.92',
        anything=float_comfy_4,
    )

    trimaudioduration_9 = TrimAudioDuration(
        widget_0=11,
        widget_1=40,
        audio=loadaudio,
        duration=float,
    )

    pathchsageattentionkj = PathchSageAttentionKJ(
        sage_attention='disabled',
        model=loraloadermodelonly,
    )

    resizeimagemasknode_5 = ResizeImageMaskNode(
        resize_type=SCALE_BY_MULTIPLIER,
        input=image_image,
    )

    resizeimagesbylongeredge_5 = ResizeImagesByLongerEdge(
        longer_edge=1536,
        images=image_image,
    )

    stringconcatenate_8 = StringConcatenate(
        delimiter=VALUE,
        string_b='MusicVideo',
        widget_0='MusicVideo',
        string_a=stringconcatenate,
    )

    ltxvpreprocess = LTXVPreprocess(img_compression=18, image=resizeimagesbylongeredge)

    textgenerateltx2prompt = TextGenerateLTX2Prompt(
        widget_0='',
        widget_1=256,
        widget_2=OFF,
        widget_3=False,
        widget_4=True,
        clip=getnode_10.out('CLIP'),
        image=resizeimagemasknode,
        prompt=stringconcatenate_4,
    )

    ltxvaudiovaeencode = LTXVAudioVAEEncode(
        audio=trimaudioduration,
        audio_vae=getnode_3.out('VAE'),
    )

    emptyltxvlatentvideo = EmptyLTXVLatentVideo(
        width=getnode_21.out('INT'),
        height=getnode_22.out('INT'),
        length=int_simple_2,
    )

    textgenerateltx2prompt_2 = TextGenerateLTX2Prompt(
        widget_0='',
        widget_1=256,
        widget_2=OFF,
        widget_3=False,
        widget_4=True,
        clip=getnode_30.out('CLIP'),
        image=resizeimagemasknode_2,
        prompt=stringconcatenate_5,
    )

    ltxvpreprocess_2 = LTXVPreprocess(
        img_compression=18,
        image=resizeimagesbylongeredge_2,
    )

    ltxvaudiovaeencode_2 = LTXVAudioVAEEncode(
        audio=trimaudioduration_3,
        audio_vae=getnode_29.out('VAE'),
    )

    emptyltxvlatentvideo_2 = EmptyLTXVLatentVideo(
        width=getnode_48.out('INT'),
        height=getnode_49.out('INT'),
        length=int_simple_3,
    )

    textgenerateltx2prompt_3 = TextGenerateLTX2Prompt(
        widget_0='',
        widget_1=256,
        widget_2=OFF,
        widget_3=False,
        widget_4=True,
        clip=getnode_53.out('CLIP'),
        image=resizeimagemasknode_3,
        prompt=stringconcatenate_6,
    )

    ltxvpreprocess_3 = LTXVPreprocess(
        img_compression=18,
        image=resizeimagesbylongeredge_3,
    )

    ltxvaudiovaeencode_3 = LTXVAudioVAEEncode(
        audio=trimaudioduration_5,
        audio_vae=getnode_52.out('VAE'),
    )

    emptyltxvlatentvideo_3 = EmptyLTXVLatentVideo(
        width=getnode_71.out('INT'),
        height=getnode_72.out('INT'),
        length=int_simple_4,
    )

    textgenerateltx2prompt_4 = TextGenerateLTX2Prompt(
        widget_0='',
        widget_1=256,
        widget_2=OFF,
        widget_3=False,
        widget_4=True,
        clip=getnode_76.out('CLIP'),
        image=resizeimagemasknode_4,
        prompt=stringconcatenate_7,
    )

    ltxvpreprocess_4 = LTXVPreprocess(
        img_compression=18,
        image=resizeimagesbylongeredge_4,
    )

    ltxvaudiovaeencode_4 = LTXVAudioVAEEncode(
        audio=trimaudioduration_7,
        audio_vae=getnode_75.out('VAE'),
    )

    emptyltxvlatentvideo_4 = EmptyLTXVLatentVideo(
        width=getnode_94.out('INT'),
        height=getnode_95.out('INT'),
        length=int_simple_5,
    )

    melbandroformersampler = raw_call('MelBandRoFormerSampler', '1599',
        audio=trimaudioduration_9,
        model=melbandroformermodelloader.out(0),
    )

    ltxvpreprocess_5 = LTXVPreprocess(
        img_compression=18,
        image=resizeimagesbylongeredge_5,
    )

    ltxvchunkfeedforward = LTXVChunkFeedForward(model=pathchsageattentionkj)
    width_get, height_get, batch_size = GetImageSize(image=resizeimagemasknode_5)

    textgenerateltx2prompt_5 = TextGenerateLTX2Prompt(
        widget_0='',
        widget_1=256,
        widget_2=OFF,
        widget_3=False,
        widget_4=True,
        clip=dualcliploader,
        image=resizeimagesbylongeredge_5,
        prompt=stringconcatenate_3,
    )

    lazyswitchkj = LazySwitchKJ(
        widget_0=False,
        on_false=reroute_3.out(0),
        on_true=textgenerateltx2prompt,
        switch=reroute_4.out(0),
    )

    setlatentnoisemask = SetLatentNoiseMask(mask=solidmask, samples=ltxvaudiovaeencode)

    ltxvimgtovideoinplacekj = LTXVImgToVideoInplaceKJ(
        widget_0=V_1,
        widget_1=1,
        widget_2=0,
        latent=emptyltxvlatentvideo,
        vae=getnode_12.out('VAE'),
        **{'num_images.image_1': ltxvpreprocess, 'num_images.strength_1': getnode_5.out('FLOAT')},
    )

    lazyswitchkj_2 = LazySwitchKJ(
        widget_0=False,
        on_false=reroute_13.out(0),
        on_true=textgenerateltx2prompt_2,
        switch=reroute_14.out(0),
    )

    setlatentnoisemask_2 = SetLatentNoiseMask(
        mask=solidmask_2,
        samples=ltxvaudiovaeencode_2,
    )

    ltxvimgtovideoinplacekj_2 = LTXVImgToVideoInplaceKJ(
        widget_0=V_1,
        widget_1=1,
        widget_2=0,
        latent=emptyltxvlatentvideo_2,
        vae=getnode_31.out('VAE'),
        **{'num_images.image_1': ltxvpreprocess_2, 'num_images.strength_1': getnode_50.out('FLOAT')},
    )

    lazyswitchkj_3 = LazySwitchKJ(
        widget_0=False,
        on_false=reroute_19.out(0),
        on_true=textgenerateltx2prompt_3,
        switch=reroute_20.out(0),
    )

    setlatentnoisemask_3 = SetLatentNoiseMask(
        mask=solidmask_3,
        samples=ltxvaudiovaeencode_3,
    )

    ltxvimgtovideoinplacekj_3 = LTXVImgToVideoInplaceKJ(
        widget_0=V_1,
        widget_1=1,
        widget_2=0,
        latent=emptyltxvlatentvideo_3,
        vae=getnode_54.out('VAE'),
        **{'num_images.image_1': ltxvpreprocess_3, 'num_images.strength_1': getnode_73.out('FLOAT')},
    )

    lazyswitchkj_4 = LazySwitchKJ(
        widget_0=False,
        on_false=reroute_25.out(0),
        on_true=textgenerateltx2prompt_4,
        switch=reroute_26.out(0),
    )

    setlatentnoisemask_4 = SetLatentNoiseMask(
        mask=solidmask_4,
        samples=ltxvaudiovaeencode_4,
    )

    ltxvimgtovideoinplacekj_4 = LTXVImgToVideoInplaceKJ(
        widget_0=V_1,
        widget_1=1,
        widget_2=0,
        latent=emptyltxvlatentvideo_4,
        vae=getnode_77.out('VAE'),
        **{'num_images.image_1': ltxvpreprocess_4, 'num_images.strength_1': getnode_96.out('FLOAT')},
    )

    comfyswitchnode = ComfySwitchNode(
        switch=True,
        on_false=trimaudioduration_9,
        on_true=melbandroformersampler.out(0),
    )

    lazyswitchkj_5 = LazySwitchKJ(
        widget_0=False,
        on_false=reroute_2.out(0),
        on_true=textgenerateltx2prompt_5,
        switch=reroute.out(0),
    )

    emptyltxvlatentvideo_5 = EmptyLTXVLatentVideo(
        width=width_get,
        height=height_get,
        length=int_simple,
    )

    ltx2attentiontunerpatch = LTX2AttentionTunerPatch(
        triton_kernels=False,
        model=ltxvchunkfeedforward,
    )

    positive = CLIPTextEncode(text=lazyswitchkj, clip=getnode_10.out('CLIP'))

    ltxvconcatavlatent = LTXVConcatAVLatent(
        audio_latent=setlatentnoisemask,
        video_latent=ltxvimgtovideoinplacekj,
    )

    positive_2 = CLIPTextEncode(text=lazyswitchkj_2, clip=getnode_30.out('CLIP'))

    ltxvconcatavlatent_2 = LTXVConcatAVLatent(
        audio_latent=setlatentnoisemask_2,
        video_latent=ltxvimgtovideoinplacekj_2,
    )

    positive_3 = CLIPTextEncode(text=lazyswitchkj_3, clip=getnode_53.out('CLIP'))

    ltxvconcatavlatent_3 = LTXVConcatAVLatent(
        audio_latent=setlatentnoisemask_3,
        video_latent=ltxvimgtovideoinplacekj_3,
    )

    positive_4 = CLIPTextEncode(text=lazyswitchkj_4, clip=getnode_76.out('CLIP'))

    ltxvconcatavlatent_4 = LTXVConcatAVLatent(
        audio_latent=setlatentnoisemask_4,
        video_latent=ltxvimgtovideoinplacekj_4,
    )

    power_lora_loader__rgthree_ = raw_call('Power Lora Loader (rgthree)', '2150',
        _outputs=('MODEL', 'CLIP'),
        widget_7='',
        model=ltx2attentiontunerpatch,
    )

    cliptextencode_2 = CLIPTextEncode(text=lazyswitchkj_5, clip=dualcliploader)

    trimaudioduration_10 = TrimAudioDuration(
        widget_0=0,
        widget_1=40,
        audio=comfyswitchnode,
        duration=primitivefloat_4,
    )

    ltxvimgtovideoinplace = LTXVImgToVideoInplace(
        widget_0=1,
        widget_1=False,
        image=ltxvpreprocess_5,
        latent=emptyltxvlatentvideo_5,
        vae=vaeloader,
    )

    cfgguider = CFGGuider(
        cfg=GUIDE_STRENGTH_2,
        model=getnode.out('MODEL'),
        negative=getnode_4.out('CONDITIONING'),
        positive=positive,
    )

    cfgguider_2 = CFGGuider(
        cfg=GUIDE_STRENGTH_2,
        model=getnode_14.out('MODEL'),
        negative=getnode_16.out('CONDITIONING'),
        positive=positive,
    )

    cfgguider_3 = CFGGuider(
        cfg=GUIDE_STRENGTH_2,
        model=getnode_32.out('MODEL'),
        negative=getnode_44.out('CONDITIONING'),
        positive=positive_2,
    )

    cfgguider_4 = CFGGuider(
        cfg=GUIDE_STRENGTH_2,
        model=getnode_38.out('MODEL'),
        negative=getnode_40.out('CONDITIONING'),
        positive=positive_2,
    )

    cfgguider_5 = CFGGuider(
        cfg=GUIDE_STRENGTH_2,
        model=getnode_55.out('MODEL'),
        negative=getnode_67.out('CONDITIONING'),
        positive=positive_3,
    )

    cfgguider_6 = CFGGuider(
        cfg=GUIDE_STRENGTH_2,
        model=getnode_61.out('MODEL'),
        negative=getnode_63.out('CONDITIONING'),
        positive=positive_3,
    )

    cfgguider_7 = CFGGuider(
        cfg=GUIDE_STRENGTH_2,
        model=getnode_78.out('MODEL'),
        negative=getnode_90.out('CONDITIONING'),
        positive=positive_4,
    )

    cfgguider_8 = CFGGuider(
        cfg=GUIDE_STRENGTH_2,
        model=getnode_84.out('MODEL'),
        negative=getnode_86.out('CONDITIONING'),
        positive=positive_4,
    )

    positive_ltxv, negative = LTXVConditioning(
        frame_rate=primitivefloat,
        negative=cliptextencode,
        positive=cliptextencode_2,
    )

    ltxvaudiovaeencode_5 = LTXVAudioVAEEncode(
        audio=trimaudioduration_10,
        audio_vae=ltxvaudiovaeloader,
    )

    output, denoised_output = SamplerCustomAdvanced(
        guider=cfgguider,
        latent_image=ltxvconcatavlatent,
        noise=randomnoise_7,
        sampler=getnode_8.out('SAMPLER'),
        sigmas=getnode_9.out('SIGMAS'),
    )

    output_sampler, denoised_output_sampler = SamplerCustomAdvanced(
        guider=cfgguider_3,
        latent_image=ltxvconcatavlatent_2,
        noise=randomnoise_8,
        sampler=getnode_33.out('SAMPLER'),
        sigmas=getnode_34.out('SIGMAS'),
    )

    output_sampler_2, denoised_output_sampler_2 = SamplerCustomAdvanced(
        guider=cfgguider_5,
        latent_image=ltxvconcatavlatent_3,
        noise=randomnoise_9,
        sampler=getnode_56.out('SAMPLER'),
        sigmas=getnode_57.out('SIGMAS'),
    )

    output_sampler_3, denoised_output_sampler_3 = SamplerCustomAdvanced(
        guider=cfgguider_7,
        latent_image=ltxvconcatavlatent_4,
        noise=randomnoise_10,
        sampler=getnode_79.out('SAMPLER'),
        sigmas=getnode_80.out('SIGMAS'),
    )

    setlatentnoisemask_5 = SetLatentNoiseMask(
        mask=solidmask_5,
        samples=ltxvaudiovaeencode_5,
    )

    ltx2_nag = LTX2_NAG(
        model=power_lora_loader__rgthree_.out('MODEL'),
        nag_cond_audio=negative,
        nag_cond_video=negative,
    )

    video_latent, audio_latent = LTXVSeparateAVLatent(av_latent=output)

    video_latent_ltxv, audio_latent_ltxv = LTXVSeparateAVLatent(
        av_latent=output_sampler,
    )

    video_latent_ltxv_2, audio_latent_ltxv_2 = LTXVSeparateAVLatent(
        av_latent=output_sampler_2,
    )

    video_latent_ltxv_3, audio_latent_ltxv_3 = LTXVSeparateAVLatent(
        av_latent=output_sampler_3,
    )

    ltxvconcatavlatent_5 = LTXVConcatAVLatent(
        audio_latent=setlatentnoisemask_5,
        video_latent=ltxvimgtovideoinplace,
    )

    cfgguider_9 = CFGGuider(
        cfg=GUIDE_STRENGTH_3,
        model=ltx2_nag,
        negative=positive_ltxv,
        positive=positive_ltxv,
    )

    modelsamplingsd3 = ModelSamplingSD3(shift=13, model=ltx2_nag)

    cfgguider_10 = CFGGuider(
        cfg=GUIDE_STRENGTH_3,
        model=ltx2_nag,
        negative=negative,
        positive=positive_ltxv,
    )

    modelsamplingsd3_2 = ModelSamplingSD3(shift=13, model=ltx2_nag)

    ltxvlatentupsampler = LTXVLatentUpsampler(
        samples=video_latent,
        upscale_model=getnode_18.out('LATENT_UPSCALE_MODEL'),
        vae=getnode_13.out('VAE'),
    )

    ltxvlatentupsampler_2 = LTXVLatentUpsampler(
        samples=video_latent_ltxv,
        upscale_model=getnode_37.out('LATENT_UPSCALE_MODEL'),
        vae=getnode_35.out('VAE'),
    )

    ltxvlatentupsampler_3 = LTXVLatentUpsampler(
        samples=video_latent_ltxv_2,
        upscale_model=getnode_60.out('LATENT_UPSCALE_MODEL'),
        vae=getnode_58.out('VAE'),
    )

    ltxvlatentupsampler_4 = LTXVLatentUpsampler(
        samples=video_latent_ltxv_3,
        upscale_model=getnode_83.out('LATENT_UPSCALE_MODEL'),
        vae=getnode_81.out('VAE'),
    )

    basicscheduler = BasicScheduler(
        scheduler=1,
        steps=1,
        widget_1=4,
        model=modelsamplingsd3,
    )

    output_sampler_4, denoised_output_sampler_4 = SamplerCustomAdvanced(
        guider=cfgguider_9,
        latent_image=ltxvconcatavlatent_5,
        noise=randomnoise_2,
        sampler=reroute_3.out(0),
        sigmas=reroute_4.out(0),
    )

    basicscheduler_2 = BasicScheduler(
        scheduler=1,
        steps=1,
        widget_1=10,
        model=modelsamplingsd3_2,
    )

    ltxvimgtovideoinplacekj_5 = LTXVImgToVideoInplaceKJ(
        widget_0=V_1,
        widget_1=1,
        widget_2=0,
        latent=ltxvlatentupsampler,
        vae=getnode_13.out('VAE'),
        **{'num_images.image_1': resizeimagesbylongeredge, 'num_images.strength_1': getnode_17.out('FLOAT')},
    )

    ltxvimgtovideoinplacekj_6 = LTXVImgToVideoInplaceKJ(
        widget_0=V_1,
        widget_1=1,
        widget_2=0,
        latent=ltxvlatentupsampler_2,
        vae=getnode_35.out('VAE'),
        **{'num_images.image_1': resizeimagesbylongeredge_2, 'num_images.strength_1': getnode_36.out('FLOAT')},
    )

    ltxvimgtovideoinplacekj_7 = LTXVImgToVideoInplaceKJ(
        widget_0=V_1,
        widget_1=1,
        widget_2=0,
        latent=ltxvlatentupsampler_3,
        vae=getnode_58.out('VAE'),
        **{'num_images.image_1': resizeimagesbylongeredge_3, 'num_images.strength_1': getnode_59.out('FLOAT')},
    )

    ltxvimgtovideoinplacekj_8 = LTXVImgToVideoInplaceKJ(
        widget_0=V_1,
        widget_1=1,
        widget_2=0,
        latent=ltxvlatentupsampler_4,
        vae=getnode_81.out('VAE'),
        **{'num_images.image_1': resizeimagesbylongeredge_4, 'num_images.strength_1': getnode_82.out('FLOAT')},
    )

    video_latent_ltxv_4, audio_latent_ltxv_4 = LTXVSeparateAVLatent(
        av_latent=output_sampler_4,
    )

    ltxvconcatavlatent_6 = LTXVConcatAVLatent(
        audio_latent=audio_latent,
        video_latent=ltxvimgtovideoinplacekj_5,
    )

    ltxvconcatavlatent_7 = LTXVConcatAVLatent(
        audio_latent=audio_latent_ltxv,
        video_latent=ltxvimgtovideoinplacekj_6,
    )

    ltxvconcatavlatent_8 = LTXVConcatAVLatent(
        audio_latent=audio_latent_ltxv_2,
        video_latent=ltxvimgtovideoinplacekj_7,
    )

    ltxvconcatavlatent_9 = LTXVConcatAVLatent(
        audio_latent=audio_latent_ltxv_3,
        video_latent=ltxvimgtovideoinplacekj_8,
    )

    ltxvimgtovideoinplace_2 = LTXVImgToVideoInplace(
        widget_0=1,
        widget_1=False,
        image=resizeimagesbylongeredge_5,
        latent=video_latent_ltxv_4,
        strength=primitivefloat_2,
        vae=vaeloader,
    )

    output_sampler_5, denoised_output_sampler_5 = SamplerCustomAdvanced(
        guider=cfgguider_2,
        latent_image=ltxvconcatavlatent_6,
        noise=randomnoise_3,
        sampler=getnode_19.out('SAMPLER'),
        sigmas=getnode_20.out('SIGMAS'),
    )

    output_sampler_6, denoised_output_sampler_6 = SamplerCustomAdvanced(
        guider=cfgguider_4,
        latent_image=ltxvconcatavlatent_7,
        noise=randomnoise_4,
        sampler=getnode_41.out('SAMPLER'),
        sigmas=getnode_42.out('SIGMAS'),
    )

    output_sampler_7, denoised_output_sampler_7 = SamplerCustomAdvanced(
        guider=cfgguider_6,
        latent_image=ltxvconcatavlatent_8,
        noise=randomnoise_5,
        sampler=getnode_64.out('SAMPLER'),
        sigmas=getnode_65.out('SIGMAS'),
    )

    output_sampler_8, denoised_output_sampler_8 = SamplerCustomAdvanced(
        guider=cfgguider_8,
        latent_image=ltxvconcatavlatent_9,
        noise=randomnoise_6,
        sampler=getnode_87.out('SAMPLER'),
        sigmas=getnode_88.out('SIGMAS'),
    )

    ltxvconcatavlatent_10 = LTXVConcatAVLatent(
        audio_latent=audio_latent_ltxv_4,
        video_latent=ltxvimgtovideoinplace_2,
    )

    video_latent_ltxv_5, audio_latent_ltxv_5 = LTXVSeparateAVLatent(
        av_latent=output_sampler_5,
    )

    video_latent_ltxv_6, audio_latent_ltxv_6 = LTXVSeparateAVLatent(
        av_latent=output_sampler_6,
    )

    video_latent_ltxv_7, audio_latent_ltxv_7 = LTXVSeparateAVLatent(
        av_latent=output_sampler_7,
    )

    video_latent_ltxv_8, audio_latent_ltxv_8 = LTXVSeparateAVLatent(
        av_latent=output_sampler_8,
    )

    output_sampler_9, denoised_output_sampler_9 = SamplerCustomAdvanced(
        guider=cfgguider_10,
        latent_image=ltxvconcatavlatent_10,
        noise=randomnoise,
        sampler=ksamplerselect,
        sigmas=manualsigmas,
    )

    # Decode
    vaedecode = VAEDecode(samples=video_latent_ltxv_5, vae=getnode_7.out('VAE'))
    vaedecode_2 = VAEDecode(samples=video_latent_ltxv_6, vae=getnode_43.out('VAE'))
    vaedecode_3 = VAEDecode(samples=video_latent_ltxv_7, vae=getnode_66.out('VAE'))
    vaedecode_4 = VAEDecode(samples=video_latent_ltxv_8, vae=getnode_89.out('VAE'))

    video_latent_ltxv_9, audio_latent_ltxv_9 = LTXVSeparateAVLatent(
        av_latent=output_sampler_9,
    )

    any_output, image_pass, model_pass, freemem_before, freemem_after = VRAM_Debug(
        image_pass=vaedecode,
    )

    # Outputs
    vhs_videocombine = VHS_VideoCombine(
        frame_rate=primitivefloat,
        filename_prefix=stringconcatenate_8,
        save_output=primitiveboolean_2,
        audio=trimaudioduration_2,
        images=vaedecode,
    )

    any_output_debug, image_pass_debug, model_pass_debug, freemem_before_debug, freemem_after_debug = VRAM_Debug(
        image_pass=vaedecode_2,
    )

    vhs_videocombine_2 = VHS_VideoCombine(
        frame_rate=primitivefloat,
        filename_prefix=stringconcatenate_8,
        save_output=primitiveboolean_4,
        audio=trimaudioduration_4,
        images=vaedecode_2,
    )

    any_output_debug_2, image_pass_debug_2, model_pass_debug_2, freemem_before_debug_2, freemem_after_debug_2 = VRAM_Debug(
        image_pass=vaedecode_3,
    )

    vhs_videocombine_3 = VHS_VideoCombine(
        frame_rate=primitivefloat,
        filename_prefix=stringconcatenate_8,
        save_output=primitiveboolean_5,
        audio=trimaudioduration_6,
        images=vaedecode_3,
    )

    any_output_debug_3, image_pass_debug_3, model_pass_debug_3, freemem_before_debug_3, freemem_after_debug_3 = VRAM_Debug(
        image_pass=vaedecode_4,
    )

    vhs_videocombine_4 = VHS_VideoCombine(
        frame_rate=primitivefloat,
        filename_prefix=stringconcatenate_8,
        save_output=primitiveboolean_6,
        audio=trimaudioduration_8,
        images=vaedecode_4,
    )

    vaedecode_5 = VAEDecode(samples=video_latent_ltxv_9, vae=vaeloader)
    image_get, width_get_2, height_get_2, count = GetImageSizeAndCount(image=image_pass)

    image_get_2, width_get_3, height_get_3, count_get = GetImageSizeAndCount(
        image=image_pass_debug,
    )

    image_get_3, width_get_4, height_get_4, count_get_2 = GetImageSizeAndCount(
        image=image_pass_debug_2,
    )

    image_get_4, width_get_5, height_get_5, count_get_3 = GetImageSizeAndCount(
        image=image_pass_debug_3,
    )

    image_get_5, width_get_6, height_get_6, count_get_4 = GetImageSizeAndCount(
        image=vaedecode_5,
    )

    any_output_debug_4, image_pass_debug_4, model_pass_debug_4, freemem_before_debug_4, freemem_after_debug_4 = VRAM_Debug(
        image_pass=vaedecode_5,
    )

    vhs_videocombine_5 = VHS_VideoCombine(
        frame_rate=primitivefloat,
        filename_prefix=stringconcatenate_8,
        save_output=primitiveboolean_3,
        audio=trimaudioduration_9,
        images=vaedecode_5,
    )

    float_simple_6, int_simple_6, boolean_simple_6 = SimpleCalculatorKJ(
        **{'variables.a': reroute_6.out(0), 'variables.b': count},
    )

    float_simple_7, int_simple_7, boolean_simple_7 = SimpleCalculatorKJ(
        **{'variables.a': reroute_9.out(0), 'variables.b': count_get},
    )

    float_simple_8, int_simple_8, boolean_simple_8 = SimpleCalculatorKJ(
        **{'variables.a': reroute_15.out(0), 'variables.b': count_get_2},
    )

    float_simple_9, int_simple_9, boolean_simple_9 = SimpleCalculatorKJ(
        **{'variables.a': reroute_21.out(0), 'variables.b': count_get_3},
    )

    image_get_6, width_get_7, height_get_7, count_get_5 = GetImageSizeAndCount(
        image=image_pass_debug_4,
    )

    float_simple_10, int_simple_10, boolean_simple_10 = SimpleCalculatorKJ(
        expression='a + 100',
        **{'variables.a': int_simple_9},
    )

    loadvideosfromfolder = LoadVideosFromFolder(
        widget_0='output\\MusicVideo',
        widget_4=0,
        frame_load_cap=int_simple_10,
        video=stringconcatenate_2,
    )

    vhs_videocombine_6 = VHS_VideoCombine(
        frame_rate=primitivefloat,
        audio=trimaudioduration_9,
        images=loadvideosfromfolder,
    )


    PUBLIC_INPUTS = {
        'image': InputSpec(node=image, field='image', default='download (8).png', type='IMAGE', required=True, aliases=('input_image',), media_semantics='image'),
        'seed': InputSpec(node=randomnoise, field='noise_seed', default=DEFAULT_SEED, type='INT'),
        'prompt': InputSpec(node=primitivestringmultiline, field='value', default='Make this image come alive with fluid motion. Cinematic music video shot of a red haired woman. \n\nShe sings with expressive motion and gesticulation. \nThe song she is singing is a sweet slow melancolic melody. Her lips moves in perfect lip-sync to the attached audio.  \n\nShe is walking through a mystical dreamy forrest, tracking camera as she walks towards the viewer. \nThe camera pulls away slowly keeping same distance to the woman. \n\nCinematic, volumetric lights, shadow play. \n\nIMPORTANT: The woman is singing, and her lips are moving with lip-sync to the lyrics of the song.', type='STRING', required=True, media_semantics='text'),
    }
    return wf.finalize(PUBLIC_INPUTS, output_node=vhs_videocombine, output_type='VHS_VideoCombine', name='video', artifact_kind='video', mime_type='video/mp4', expected_cardinality='one')

