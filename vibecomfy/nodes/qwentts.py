# vibecomfy:generated
# pack: qwentts
# source: object_info cache AILab_QwenTTS@runpod-snapshot.json sha256:59a3334df54e; object_info cache AILab_QwenTTS_Tools@runpod-snapshot.json sha256:fd5edd179618
# source_sha256: 22b529832aafbb42fca6ec3efc10a5bbd6129743c773873607ea00b462c65895
# generator_version: 2.0.0
# generated_at: 1970-01-01T00:00:00+00:00
# classes: 11
#
# DO NOT EDIT — regenerate with:
#   vibecomfy nodes generate-wrappers qwentts

"""Auto-generated public wrappers for the qwentts custom-node pack.

Each function wraps one ComfyUI node class and delegates through the
public ``vibecomfy.templates.node`` ABI.
"""

from __future__ import annotations

from typing import Any, Literal

from vibecomfy.templates import _current_workflow_or_raise, node
from vibecomfy.workflow import VibeWorkflow

class _Omitted:
    pass

_UNSET = _Omitted()

def AILab_Qwen3TTSCustomVoice(
    *args: VibeWorkflow,
    _id: str | None = None,
    language: Literal['Auto', 'Chinese', 'English', 'Japanese', 'Korean', 'French', 'German', 'Spanish', 'Portuguese', 'Russian', 'Italian'] | _Omitted = _UNSET,
    model_size: Literal['0.6B', '1.7B'] | _Omitted = _UNSET,
    speaker: Literal['Aiden', 'Dylan', 'Eric', 'Ono_Anna', 'Ryan', 'Serena', 'Sohee', 'Uncle_Fu', 'Vivian'] | _Omitted = _UNSET,
    text: str | _Omitted = _UNSET,
    instruct: str | _Omitted = _UNSET,
    seed: int | _Omitted = _UNSET,
    unload_models: bool | _Omitted = _UNSET,
    pass_raw: bool = False,
    **_extras: Any,
) -> Any:
    """Public wrapper for the ComfyUI node ``AILab_Qwen3TTSCustomVoice``.

    Display name: Custom Voice (QwenTTS)

    Category: 🧪AILab/🎙️QwenTTS

    Returns: audio

    Source: object_info cache AILab_QwenTTS@runpod-snapshot.json sha256:59a3334df54e
    """
    if len(args) > 1:
        raise TypeError(f"AILab_Qwen3TTSCustomVoice() takes at most 1 positional argument, got {len(args)}")
    wf = args[0] if args else _current_workflow_or_raise()
    _kwargs: dict[str, Any] = {}
    if language is not _UNSET:
        _kwargs['language'] = language
    if model_size is not _UNSET:
        _kwargs['model_size'] = model_size
    if speaker is not _UNSET:
        _kwargs['speaker'] = speaker
    if text is not _UNSET:
        _kwargs['text'] = text
    if instruct is not _UNSET:
        _kwargs['instruct'] = instruct
    if seed is not _UNSET:
        _kwargs['seed'] = seed
    if unload_models is not _UNSET:
        _kwargs['unload_models'] = unload_models
    _kwargs.update(_extras)
    return node(wf, 'AILab_Qwen3TTSCustomVoice', _id, pass_raw=pass_raw, **_kwargs)

def AILab_Qwen3TTSCustomVoice_Advanced(
    *args: VibeWorkflow,
    _id: str | None = None,
    device: Literal['auto', 'cuda', 'cpu'] | _Omitted = _UNSET,
    language: Literal['Auto', 'Chinese', 'English', 'Japanese', 'Korean', 'French', 'German', 'Spanish', 'Portuguese', 'Russian', 'Italian'] | _Omitted = _UNSET,
    model_size: Literal['0.6B', '1.7B'] | _Omitted = _UNSET,
    precision: Literal['bf16', 'fp16', 'fp32'] | _Omitted = _UNSET,
    speaker: Literal['Aiden', 'Dylan', 'Eric', 'Ono_Anna', 'Ryan', 'Serena', 'Sohee', 'Uncle_Fu', 'Vivian'] | _Omitted = _UNSET,
    text: str | _Omitted = _UNSET,
    attention: Literal['auto', 'sage_attn', 'flash_attn', 'sdpa', 'eager'] | _Omitted = _UNSET,
    do_sample: bool | _Omitted = _UNSET,
    instruct: str | _Omitted = _UNSET,
    max_new_tokens: int | _Omitted = _UNSET,
    repetition_penalty: float | _Omitted = _UNSET,
    seed: int | _Omitted = _UNSET,
    temperature: float | _Omitted = _UNSET,
    top_k: int | _Omitted = _UNSET,
    top_p: float | _Omitted = _UNSET,
    unload_models: bool | _Omitted = _UNSET,
    pass_raw: bool = False,
    **_extras: Any,
) -> Any:
    """Public wrapper for the ComfyUI node ``AILab_Qwen3TTSCustomVoice_Advanced``.

    Display name: Custom Voice (QwenTTS) Advanced

    Category: 🧪AILab/🎙️QwenTTS

    Returns: audio

    Source: object_info cache AILab_QwenTTS@runpod-snapshot.json sha256:59a3334df54e
    """
    if len(args) > 1:
        raise TypeError(f"AILab_Qwen3TTSCustomVoice_Advanced() takes at most 1 positional argument, got {len(args)}")
    wf = args[0] if args else _current_workflow_or_raise()
    _kwargs: dict[str, Any] = {}
    if device is not _UNSET:
        _kwargs['device'] = device
    if language is not _UNSET:
        _kwargs['language'] = language
    if model_size is not _UNSET:
        _kwargs['model_size'] = model_size
    if precision is not _UNSET:
        _kwargs['precision'] = precision
    if speaker is not _UNSET:
        _kwargs['speaker'] = speaker
    if text is not _UNSET:
        _kwargs['text'] = text
    if attention is not _UNSET:
        _kwargs['attention'] = attention
    if do_sample is not _UNSET:
        _kwargs['do_sample'] = do_sample
    if instruct is not _UNSET:
        _kwargs['instruct'] = instruct
    if max_new_tokens is not _UNSET:
        _kwargs['max_new_tokens'] = max_new_tokens
    if repetition_penalty is not _UNSET:
        _kwargs['repetition_penalty'] = repetition_penalty
    if seed is not _UNSET:
        _kwargs['seed'] = seed
    if temperature is not _UNSET:
        _kwargs['temperature'] = temperature
    if top_k is not _UNSET:
        _kwargs['top_k'] = top_k
    if top_p is not _UNSET:
        _kwargs['top_p'] = top_p
    if unload_models is not _UNSET:
        _kwargs['unload_models'] = unload_models
    _kwargs.update(_extras)
    return node(wf, 'AILab_Qwen3TTSCustomVoice_Advanced', _id, pass_raw=pass_raw, **_kwargs)

def AILab_Qwen3TTSLoadVoice(
    *args: VibeWorkflow,
    _id: str | None = None,
    voice_name: Literal[''] | _Omitted = _UNSET,
    custom_path: str | _Omitted = _UNSET,
    pass_raw: bool = False,
    **_extras: Any,
) -> Any:
    """Public wrapper for the ComfyUI node ``AILab_Qwen3TTSLoadVoice``.

    Display name: Load Voice (QwenTTS)

    Category: 🧪AILab/🎙️QwenTTS

    Returns: VOICE

    Source: object_info cache AILab_QwenTTS_Tools@runpod-snapshot.json sha256:fd5edd179618
    """
    if len(args) > 1:
        raise TypeError(f"AILab_Qwen3TTSLoadVoice() takes at most 1 positional argument, got {len(args)}")
    wf = args[0] if args else _current_workflow_or_raise()
    _kwargs: dict[str, Any] = {}
    if voice_name is not _UNSET:
        _kwargs['voice_name'] = voice_name
    if custom_path is not _UNSET:
        _kwargs['custom_path'] = custom_path
    _kwargs.update(_extras)
    return node(wf, 'AILab_Qwen3TTSLoadVoice', _id, pass_raw=pass_raw, **_kwargs)

def AILab_Qwen3TTSVoiceClone(
    *args: VibeWorkflow,
    _id: str | None = None,
    language: Literal['Auto', 'Chinese', 'English', 'Japanese', 'Korean', 'French', 'German', 'Spanish', 'Portuguese', 'Russian', 'Italian'] | _Omitted = _UNSET,
    model_size: Literal['0.6B', '1.7B'] | _Omitted = _UNSET,
    target_text: str | _Omitted = _UNSET,
    reference_audio: Any | _Omitted = _UNSET,
    reference_text: str | _Omitted = _UNSET,
    seed: int | _Omitted = _UNSET,
    unload_models: bool | _Omitted = _UNSET,
    voice: Any | _Omitted = _UNSET,
    x_vector_only: bool | _Omitted = _UNSET,
    pass_raw: bool = False,
    **_extras: Any,
) -> Any:
    """Public wrapper for the ComfyUI node ``AILab_Qwen3TTSVoiceClone``.

    Display name: Voice Clone (QwenTTS)

    Category: 🧪AILab/🎙️QwenTTS

    Returns: audio

    Source: object_info cache AILab_QwenTTS@runpod-snapshot.json sha256:59a3334df54e
    """
    if len(args) > 1:
        raise TypeError(f"AILab_Qwen3TTSVoiceClone() takes at most 1 positional argument, got {len(args)}")
    wf = args[0] if args else _current_workflow_or_raise()
    _kwargs: dict[str, Any] = {}
    if language is not _UNSET:
        _kwargs['language'] = language
    if model_size is not _UNSET:
        _kwargs['model_size'] = model_size
    if target_text is not _UNSET:
        _kwargs['target_text'] = target_text
    if reference_audio is not _UNSET:
        _kwargs['reference_audio'] = reference_audio
    if reference_text is not _UNSET:
        _kwargs['reference_text'] = reference_text
    if seed is not _UNSET:
        _kwargs['seed'] = seed
    if unload_models is not _UNSET:
        _kwargs['unload_models'] = unload_models
    if voice is not _UNSET:
        _kwargs['voice'] = voice
    if x_vector_only is not _UNSET:
        _kwargs['x_vector_only'] = x_vector_only
    _kwargs.update(_extras)
    return node(wf, 'AILab_Qwen3TTSVoiceClone', _id, pass_raw=pass_raw, **_kwargs)

def AILab_Qwen3TTSVoiceClone_Advanced(
    *args: VibeWorkflow,
    _id: str | None = None,
    device: Literal['auto', 'cuda', 'cpu'] | _Omitted = _UNSET,
    language: Literal['Auto', 'Chinese', 'English', 'Japanese', 'Korean', 'French', 'German', 'Spanish', 'Portuguese', 'Russian', 'Italian'] | _Omitted = _UNSET,
    model_size: Literal['0.6B', '1.7B'] | _Omitted = _UNSET,
    precision: Literal['bf16', 'fp16', 'fp32'] | _Omitted = _UNSET,
    target_text: str | _Omitted = _UNSET,
    attention: Literal['auto', 'sage_attn', 'flash_attn', 'sdpa', 'eager'] | _Omitted = _UNSET,
    do_sample: bool | _Omitted = _UNSET,
    max_new_tokens: int | _Omitted = _UNSET,
    reference_audio: Any | _Omitted = _UNSET,
    reference_text: str | _Omitted = _UNSET,
    repetition_penalty: float | _Omitted = _UNSET,
    seed: int | _Omitted = _UNSET,
    temperature: float | _Omitted = _UNSET,
    top_k: int | _Omitted = _UNSET,
    top_p: float | _Omitted = _UNSET,
    unload_models: bool | _Omitted = _UNSET,
    voice: Any | _Omitted = _UNSET,
    x_vector_only: bool | _Omitted = _UNSET,
    pass_raw: bool = False,
    **_extras: Any,
) -> Any:
    """Public wrapper for the ComfyUI node ``AILab_Qwen3TTSVoiceClone_Advanced``.

    Display name: Voice Clone (QwenTTS) Advanced

    Category: 🧪AILab/🎙️QwenTTS

    Returns: audio

    Source: object_info cache AILab_QwenTTS@runpod-snapshot.json sha256:59a3334df54e
    """
    if len(args) > 1:
        raise TypeError(f"AILab_Qwen3TTSVoiceClone_Advanced() takes at most 1 positional argument, got {len(args)}")
    wf = args[0] if args else _current_workflow_or_raise()
    _kwargs: dict[str, Any] = {}
    if device is not _UNSET:
        _kwargs['device'] = device
    if language is not _UNSET:
        _kwargs['language'] = language
    if model_size is not _UNSET:
        _kwargs['model_size'] = model_size
    if precision is not _UNSET:
        _kwargs['precision'] = precision
    if target_text is not _UNSET:
        _kwargs['target_text'] = target_text
    if attention is not _UNSET:
        _kwargs['attention'] = attention
    if do_sample is not _UNSET:
        _kwargs['do_sample'] = do_sample
    if max_new_tokens is not _UNSET:
        _kwargs['max_new_tokens'] = max_new_tokens
    if reference_audio is not _UNSET:
        _kwargs['reference_audio'] = reference_audio
    if reference_text is not _UNSET:
        _kwargs['reference_text'] = reference_text
    if repetition_penalty is not _UNSET:
        _kwargs['repetition_penalty'] = repetition_penalty
    if seed is not _UNSET:
        _kwargs['seed'] = seed
    if temperature is not _UNSET:
        _kwargs['temperature'] = temperature
    if top_k is not _UNSET:
        _kwargs['top_k'] = top_k
    if top_p is not _UNSET:
        _kwargs['top_p'] = top_p
    if unload_models is not _UNSET:
        _kwargs['unload_models'] = unload_models
    if voice is not _UNSET:
        _kwargs['voice'] = voice
    if x_vector_only is not _UNSET:
        _kwargs['x_vector_only'] = x_vector_only
    _kwargs.update(_extras)
    return node(wf, 'AILab_Qwen3TTSVoiceClone_Advanced', _id, pass_raw=pass_raw, **_kwargs)

def AILab_Qwen3TTSVoiceDesign(
    *args: VibeWorkflow,
    _id: str | None = None,
    instruct: str | _Omitted = _UNSET,
    language: Literal['Auto', 'Chinese', 'English', 'Japanese', 'Korean', 'French', 'German', 'Spanish', 'Portuguese', 'Russian', 'Italian'] | _Omitted = _UNSET,
    model_size: Literal['1.7B'] | _Omitted = _UNSET,
    text: str | _Omitted = _UNSET,
    seed: int | _Omitted = _UNSET,
    unload_models: bool | _Omitted = _UNSET,
    pass_raw: bool = False,
    **_extras: Any,
) -> Any:
    """Public wrapper for the ComfyUI node ``AILab_Qwen3TTSVoiceDesign``.

    Display name: Voice Design (QwenTTS)

    Category: 🧪AILab/🎙️QwenTTS

    Returns: audio

    Source: object_info cache AILab_QwenTTS@runpod-snapshot.json sha256:59a3334df54e
    """
    if len(args) > 1:
        raise TypeError(f"AILab_Qwen3TTSVoiceDesign() takes at most 1 positional argument, got {len(args)}")
    wf = args[0] if args else _current_workflow_or_raise()
    _kwargs: dict[str, Any] = {}
    if instruct is not _UNSET:
        _kwargs['instruct'] = instruct
    if language is not _UNSET:
        _kwargs['language'] = language
    if model_size is not _UNSET:
        _kwargs['model_size'] = model_size
    if text is not _UNSET:
        _kwargs['text'] = text
    if seed is not _UNSET:
        _kwargs['seed'] = seed
    if unload_models is not _UNSET:
        _kwargs['unload_models'] = unload_models
    _kwargs.update(_extras)
    return node(wf, 'AILab_Qwen3TTSVoiceDesign', _id, pass_raw=pass_raw, **_kwargs)

def AILab_Qwen3TTSVoiceDesign_Advanced(
    *args: VibeWorkflow,
    _id: str | None = None,
    device: Literal['auto', 'cuda', 'cpu'] | _Omitted = _UNSET,
    instruct: str | _Omitted = _UNSET,
    language: Literal['Auto', 'Chinese', 'English', 'Japanese', 'Korean', 'French', 'German', 'Spanish', 'Portuguese', 'Russian', 'Italian'] | _Omitted = _UNSET,
    model_size: Literal['1.7B'] | _Omitted = _UNSET,
    precision: Literal['bf16', 'fp16', 'fp32'] | _Omitted = _UNSET,
    text: str | _Omitted = _UNSET,
    attention: Literal['auto', 'sage_attn', 'flash_attn', 'sdpa', 'eager'] | _Omitted = _UNSET,
    do_sample: bool | _Omitted = _UNSET,
    max_new_tokens: int | _Omitted = _UNSET,
    repetition_penalty: float | _Omitted = _UNSET,
    seed: int | _Omitted = _UNSET,
    temperature: float | _Omitted = _UNSET,
    top_k: int | _Omitted = _UNSET,
    top_p: float | _Omitted = _UNSET,
    unload_models: bool | _Omitted = _UNSET,
    pass_raw: bool = False,
    **_extras: Any,
) -> Any:
    """Public wrapper for the ComfyUI node ``AILab_Qwen3TTSVoiceDesign_Advanced``.

    Display name: Voice Design (QwenTTS) Advanced

    Category: 🧪AILab/🎙️QwenTTS

    Returns: audio

    Source: object_info cache AILab_QwenTTS@runpod-snapshot.json sha256:59a3334df54e
    """
    if len(args) > 1:
        raise TypeError(f"AILab_Qwen3TTSVoiceDesign_Advanced() takes at most 1 positional argument, got {len(args)}")
    wf = args[0] if args else _current_workflow_or_raise()
    _kwargs: dict[str, Any] = {}
    if device is not _UNSET:
        _kwargs['device'] = device
    if instruct is not _UNSET:
        _kwargs['instruct'] = instruct
    if language is not _UNSET:
        _kwargs['language'] = language
    if model_size is not _UNSET:
        _kwargs['model_size'] = model_size
    if precision is not _UNSET:
        _kwargs['precision'] = precision
    if text is not _UNSET:
        _kwargs['text'] = text
    if attention is not _UNSET:
        _kwargs['attention'] = attention
    if do_sample is not _UNSET:
        _kwargs['do_sample'] = do_sample
    if max_new_tokens is not _UNSET:
        _kwargs['max_new_tokens'] = max_new_tokens
    if repetition_penalty is not _UNSET:
        _kwargs['repetition_penalty'] = repetition_penalty
    if seed is not _UNSET:
        _kwargs['seed'] = seed
    if temperature is not _UNSET:
        _kwargs['temperature'] = temperature
    if top_k is not _UNSET:
        _kwargs['top_k'] = top_k
    if top_p is not _UNSET:
        _kwargs['top_p'] = top_p
    if unload_models is not _UNSET:
        _kwargs['unload_models'] = unload_models
    _kwargs.update(_extras)
    return node(wf, 'AILab_Qwen3TTSVoiceDesign_Advanced', _id, pass_raw=pass_raw, **_kwargs)

def AILab_Qwen3TTSVoiceInstruct(
    *args: VibeWorkflow,
    _id: str | None = None,
    character: Literal['Auto', 'Female', 'Male', 'Young Female', 'Young Male', 'Girl', 'Boy', 'Child', 'Teen', 'Adult', 'Senior Female', 'Senior Male', 'Narrator', 'Announcer'] | _Omitted = _UNSET,
    style: Literal['Auto', 'Warm', 'Gentle', 'Calm', 'Cheerful', 'Friendly', 'Serious', 'Sad', 'Angry', 'Excited', 'Soft', 'Deep', 'Clear', 'Emotional', 'Dramatic', 'Whisper', 'Breathy', 'Husky', 'Authoritative', 'Storytelling', 'News Anchor', 'Documentary', 'Customer Support', 'Teacher', 'Audiobook', 'Energetic', 'Relaxed', 'Playful', 'Mysterious', 'Romantic', 'Inspirational', 'Formal', 'Casual', 'ASMR', 'Noir', 'Cinematic', 'Trailer', 'Motivational', 'Robotic', 'Vintage Radio', 'Lullaby', 'Comedy', 'Interview', 'Poetic', 'Philosophical', 'Sportscaster', 'Meditation'] | _Omitted = _UNSET,
    custom_instruct: str | _Omitted = _UNSET,
    pass_raw: bool = False,
    **_extras: Any,
) -> Any:
    """Public wrapper for the ComfyUI node ``AILab_Qwen3TTSVoiceInstruct``.

    Display name: Voice Instruct (QwenTTS)

    Category: 🧪AILab/🎙️QwenTTS

    Returns: VOICE_INSTRUCT

    Source: object_info cache AILab_QwenTTS_Tools@runpod-snapshot.json sha256:fd5edd179618
    """
    if len(args) > 1:
        raise TypeError(f"AILab_Qwen3TTSVoiceInstruct() takes at most 1 positional argument, got {len(args)}")
    wf = args[0] if args else _current_workflow_or_raise()
    _kwargs: dict[str, Any] = {}
    if character is not _UNSET:
        _kwargs['character'] = character
    if style is not _UNSET:
        _kwargs['style'] = style
    if custom_instruct is not _UNSET:
        _kwargs['custom_instruct'] = custom_instruct
    _kwargs.update(_extras)
    return node(wf, 'AILab_Qwen3TTSVoiceInstruct', _id, pass_raw=pass_raw, **_kwargs)

def AILab_Qwen3TTSVoiceInstructZH(
    *args: VibeWorkflow,
    _id: str | None = None,
    value: Literal['自动', '女声', '男声', '年轻女声', '年轻男声', '小女孩', '小男孩', '童声', '青少年', '成年', '老年女声', '老年男声', '旁白', '播报'] | _Omitted = _UNSET,
    value_2: Literal['自动', '温暖', '轻柔', '平静', '愉快', '友好', '严肃', '悲伤', '愤怒', '兴奋', '轻声', '低沉', '清晰', '情感', '戏剧', '耳语', '气声', '沙哑', '权威', '讲故事', '新闻主播', '纪录片', '客服', '老师', '有声书', '有活力', '放松', '俏皮', '神秘', '浪漫', '励志', '正式', '随意', 'ASMR', '黑色电影', '电影感', '预告片', '激励', '机械', '复古电台', '摇篮曲', '喜剧', '访谈', '诗意', '哲思', '体育解说', '冥想'] | _Omitted = _UNSET,
    value_3: str | _Omitted = _UNSET,
    pass_raw: bool = False,
    **_extras: Any,
) -> Any:
    """Public wrapper for the ComfyUI node ``AILab_Qwen3TTSVoiceInstructZH``.

    Display name: 声音风格指引 (QwenTTS)

    Category: 🧪AILab/🎙️QwenTTS

    Returns: VOICE_INSTRUCT

    Source: object_info cache AILab_QwenTTS_Tools@runpod-snapshot.json sha256:fd5edd179618
    """
    if len(args) > 1:
        raise TypeError(f"AILab_Qwen3TTSVoiceInstructZH() takes at most 1 positional argument, got {len(args)}")
    wf = args[0] if args else _current_workflow_or_raise()
    _kwargs: dict[str, Any] = {}
    if value is not _UNSET:
        _kwargs['角色'] = value
    if value_2 is not _UNSET:
        _kwargs['风格'] = value_2
    if value_3 is not _UNSET:
        _kwargs['自定义风格指引'] = value_3
    _kwargs.update(_extras)
    return node(wf, 'AILab_Qwen3TTSVoiceInstructZH', _id, pass_raw=pass_raw, **_kwargs)

def AILab_Qwen3TTSVoicesLibrary(
    *args: VibeWorkflow,
    _id: str | None = None,
    reference_audio: Any | _Omitted = _UNSET,
    device: Literal['auto', 'cuda', 'cpu'] | _Omitted = _UNSET,
    model_size: Literal['0.6B', '1.7B'] | _Omitted = _UNSET,
    precision: Literal['bf16', 'fp16', 'fp32'] | _Omitted = _UNSET,
    reference_text: str | _Omitted = _UNSET,
    voice_name: str | _Omitted = _UNSET,
    x_vector_only: bool | _Omitted = _UNSET,
    save_path: str | _Omitted = _UNSET,
    unload_models: bool | _Omitted = _UNSET,
    pass_raw: bool = False,
    **_extras: Any,
) -> Any:
    """Public wrapper for the ComfyUI node ``AILab_Qwen3TTSVoicesLibrary``.

    Display name: Create Voice (QwenTTS)

    Category: 🧪AILab/🎙️QwenTTS

    Returns: VOICE

    Source: object_info cache AILab_QwenTTS_Tools@runpod-snapshot.json sha256:fd5edd179618
    """
    if len(args) > 1:
        raise TypeError(f"AILab_Qwen3TTSVoicesLibrary() takes at most 1 positional argument, got {len(args)}")
    wf = args[0] if args else _current_workflow_or_raise()
    _kwargs: dict[str, Any] = {}
    if reference_audio is not _UNSET:
        _kwargs['reference_audio'] = reference_audio
    if device is not _UNSET:
        _kwargs['device'] = device
    if model_size is not _UNSET:
        _kwargs['model_size'] = model_size
    if precision is not _UNSET:
        _kwargs['precision'] = precision
    if reference_text is not _UNSET:
        _kwargs['reference_text'] = reference_text
    if voice_name is not _UNSET:
        _kwargs['voice_name'] = voice_name
    if x_vector_only is not _UNSET:
        _kwargs['x_vector_only'] = x_vector_only
    if save_path is not _UNSET:
        _kwargs['save_path'] = save_path
    if unload_models is not _UNSET:
        _kwargs['unload_models'] = unload_models
    _kwargs.update(_extras)
    return node(wf, 'AILab_Qwen3TTSVoicesLibrary', _id, pass_raw=pass_raw, **_kwargs)

def AILab_Qwen3TTSWhisperSTT(
    *args: VibeWorkflow,
    _id: str | None = None,
    audio: Any | _Omitted = _UNSET,
    language: Literal['auto', 'en', 'zh', 'ja', 'ko', 'de', 'fr', 'es', 'it', 'pt', 'ru'] | _Omitted = _UNSET,
    model_size: Literal['tiny', 'base', 'small', 'medium', 'large', 'large-v2', 'large-v3', 'large-v3-turbo'] | _Omitted = _UNSET,
    unload_models: bool | _Omitted = _UNSET,
    pass_raw: bool = False,
    **_extras: Any,
) -> Any:
    """Public wrapper for the ComfyUI node ``AILab_Qwen3TTSWhisperSTT``.

    Display name: Whisper STT (QwenTTS)

    Category: 🧪AILab/🎙️QwenTTS

    Returns: text

    Source: object_info cache AILab_QwenTTS_Tools@runpod-snapshot.json sha256:fd5edd179618
    """
    if len(args) > 1:
        raise TypeError(f"AILab_Qwen3TTSWhisperSTT() takes at most 1 positional argument, got {len(args)}")
    wf = args[0] if args else _current_workflow_or_raise()
    _kwargs: dict[str, Any] = {}
    if audio is not _UNSET:
        _kwargs['audio'] = audio
    if language is not _UNSET:
        _kwargs['language'] = language
    if model_size is not _UNSET:
        _kwargs['model_size'] = model_size
    if unload_models is not _UNSET:
        _kwargs['unload_models'] = unload_models
    _kwargs.update(_extras)
    return node(wf, 'AILab_Qwen3TTSWhisperSTT', _id, pass_raw=pass_raw, **_kwargs)

__all__ = ['AILab_Qwen3TTSCustomVoice', 'AILab_Qwen3TTSCustomVoice_Advanced', 'AILab_Qwen3TTSLoadVoice', 'AILab_Qwen3TTSVoiceClone', 'AILab_Qwen3TTSVoiceClone_Advanced', 'AILab_Qwen3TTSVoiceDesign', 'AILab_Qwen3TTSVoiceDesign_Advanced', 'AILab_Qwen3TTSVoiceInstruct', 'AILab_Qwen3TTSVoiceInstructZH', 'AILab_Qwen3TTSVoicesLibrary', 'AILab_Qwen3TTSWhisperSTT']
__vibecomfy_class_types__ = {'AILab_Qwen3TTSCustomVoice': 'AILab_Qwen3TTSCustomVoice', 'AILab_Qwen3TTSCustomVoice_Advanced': 'AILab_Qwen3TTSCustomVoice_Advanced', 'AILab_Qwen3TTSLoadVoice': 'AILab_Qwen3TTSLoadVoice', 'AILab_Qwen3TTSVoiceClone': 'AILab_Qwen3TTSVoiceClone', 'AILab_Qwen3TTSVoiceClone_Advanced': 'AILab_Qwen3TTSVoiceClone_Advanced', 'AILab_Qwen3TTSVoiceDesign': 'AILab_Qwen3TTSVoiceDesign', 'AILab_Qwen3TTSVoiceDesign_Advanced': 'AILab_Qwen3TTSVoiceDesign_Advanced', 'AILab_Qwen3TTSVoiceInstruct': 'AILab_Qwen3TTSVoiceInstruct', 'AILab_Qwen3TTSVoiceInstructZH': 'AILab_Qwen3TTSVoiceInstructZH', 'AILab_Qwen3TTSVoicesLibrary': 'AILab_Qwen3TTSVoicesLibrary', 'AILab_Qwen3TTSWhisperSTT': 'AILab_Qwen3TTSWhisperSTT'}
