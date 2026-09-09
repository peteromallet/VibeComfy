# vibecomfy:generated
# pack: qwentts
# source: object_info cache AILab_QwenTTS@runpod-snapshot.json sha256:59a3334df54e; object_info cache AILab_QwenTTS_Tools@runpod-snapshot.json sha256:fd5edd179618
# source_sha256: 22b529832aafbb42fca6ec3efc10a5bbd6129743c773873607ea00b462c65895
# generator_version: 2.0.0
# generated_at: 1970-01-01T00:00:00+00:00
# classes: 11

"""Type stubs for generated public node wrappers."""
from __future__ import annotations

from typing import Any, Literal

from vibecomfy.workflow import VibeWorkflow

class _Omitted: ...
_UNSET: _Omitted

def AILab_Qwen3TTSCustomVoice(
    *args: VibeWorkflow,
    _id: str | None = ...,
    language: Literal['Auto', 'Chinese', 'English', 'Japanese', 'Korean', 'French', 'German', 'Spanish', 'Portuguese', 'Russian', 'Italian'] | _Omitted = ...,
    model_size: Literal['0.6B', '1.7B'] | _Omitted = ...,
    speaker: Literal['Aiden', 'Dylan', 'Eric', 'Ono_Anna', 'Ryan', 'Serena', 'Sohee', 'Uncle_Fu', 'Vivian'] | _Omitted = ...,
    text: str | _Omitted = ...,
    instruct: str | _Omitted = ...,
    seed: int | _Omitted = ...,
    unload_models: bool | _Omitted = ...,
    pass_raw: bool = ...,
    **_extras: Any,
) -> Any: ...

def AILab_Qwen3TTSCustomVoice_Advanced(
    *args: VibeWorkflow,
    _id: str | None = ...,
    device: Literal['auto', 'cuda', 'cpu'] | _Omitted = ...,
    language: Literal['Auto', 'Chinese', 'English', 'Japanese', 'Korean', 'French', 'German', 'Spanish', 'Portuguese', 'Russian', 'Italian'] | _Omitted = ...,
    model_size: Literal['0.6B', '1.7B'] | _Omitted = ...,
    precision: Literal['bf16', 'fp16', 'fp32'] | _Omitted = ...,
    speaker: Literal['Aiden', 'Dylan', 'Eric', 'Ono_Anna', 'Ryan', 'Serena', 'Sohee', 'Uncle_Fu', 'Vivian'] | _Omitted = ...,
    text: str | _Omitted = ...,
    attention: Literal['auto', 'sage_attn', 'flash_attn', 'sdpa', 'eager'] | _Omitted = ...,
    do_sample: bool | _Omitted = ...,
    instruct: str | _Omitted = ...,
    max_new_tokens: int | _Omitted = ...,
    repetition_penalty: float | _Omitted = ...,
    seed: int | _Omitted = ...,
    temperature: float | _Omitted = ...,
    top_k: int | _Omitted = ...,
    top_p: float | _Omitted = ...,
    unload_models: bool | _Omitted = ...,
    pass_raw: bool = ...,
    **_extras: Any,
) -> Any: ...

def AILab_Qwen3TTSLoadVoice(
    *args: VibeWorkflow,
    _id: str | None = ...,
    voice_name: Literal[''] | _Omitted = ...,
    custom_path: str | _Omitted = ...,
    pass_raw: bool = ...,
    **_extras: Any,
) -> Any: ...

def AILab_Qwen3TTSVoiceClone(
    *args: VibeWorkflow,
    _id: str | None = ...,
    language: Literal['Auto', 'Chinese', 'English', 'Japanese', 'Korean', 'French', 'German', 'Spanish', 'Portuguese', 'Russian', 'Italian'] | _Omitted = ...,
    model_size: Literal['0.6B', '1.7B'] | _Omitted = ...,
    target_text: str | _Omitted = ...,
    reference_audio: Any | _Omitted = ...,
    reference_text: str | _Omitted = ...,
    seed: int | _Omitted = ...,
    unload_models: bool | _Omitted = ...,
    voice: Any | _Omitted = ...,
    x_vector_only: bool | _Omitted = ...,
    pass_raw: bool = ...,
    **_extras: Any,
) -> Any: ...

def AILab_Qwen3TTSVoiceClone_Advanced(
    *args: VibeWorkflow,
    _id: str | None = ...,
    device: Literal['auto', 'cuda', 'cpu'] | _Omitted = ...,
    language: Literal['Auto', 'Chinese', 'English', 'Japanese', 'Korean', 'French', 'German', 'Spanish', 'Portuguese', 'Russian', 'Italian'] | _Omitted = ...,
    model_size: Literal['0.6B', '1.7B'] | _Omitted = ...,
    precision: Literal['bf16', 'fp16', 'fp32'] | _Omitted = ...,
    target_text: str | _Omitted = ...,
    attention: Literal['auto', 'sage_attn', 'flash_attn', 'sdpa', 'eager'] | _Omitted = ...,
    do_sample: bool | _Omitted = ...,
    max_new_tokens: int | _Omitted = ...,
    reference_audio: Any | _Omitted = ...,
    reference_text: str | _Omitted = ...,
    repetition_penalty: float | _Omitted = ...,
    seed: int | _Omitted = ...,
    temperature: float | _Omitted = ...,
    top_k: int | _Omitted = ...,
    top_p: float | _Omitted = ...,
    unload_models: bool | _Omitted = ...,
    voice: Any | _Omitted = ...,
    x_vector_only: bool | _Omitted = ...,
    pass_raw: bool = ...,
    **_extras: Any,
) -> Any: ...

def AILab_Qwen3TTSVoiceDesign(
    *args: VibeWorkflow,
    _id: str | None = ...,
    instruct: str | _Omitted = ...,
    language: Literal['Auto', 'Chinese', 'English', 'Japanese', 'Korean', 'French', 'German', 'Spanish', 'Portuguese', 'Russian', 'Italian'] | _Omitted = ...,
    model_size: Literal['1.7B'] | _Omitted = ...,
    text: str | _Omitted = ...,
    seed: int | _Omitted = ...,
    unload_models: bool | _Omitted = ...,
    pass_raw: bool = ...,
    **_extras: Any,
) -> Any: ...

def AILab_Qwen3TTSVoiceDesign_Advanced(
    *args: VibeWorkflow,
    _id: str | None = ...,
    device: Literal['auto', 'cuda', 'cpu'] | _Omitted = ...,
    instruct: str | _Omitted = ...,
    language: Literal['Auto', 'Chinese', 'English', 'Japanese', 'Korean', 'French', 'German', 'Spanish', 'Portuguese', 'Russian', 'Italian'] | _Omitted = ...,
    model_size: Literal['1.7B'] | _Omitted = ...,
    precision: Literal['bf16', 'fp16', 'fp32'] | _Omitted = ...,
    text: str | _Omitted = ...,
    attention: Literal['auto', 'sage_attn', 'flash_attn', 'sdpa', 'eager'] | _Omitted = ...,
    do_sample: bool | _Omitted = ...,
    max_new_tokens: int | _Omitted = ...,
    repetition_penalty: float | _Omitted = ...,
    seed: int | _Omitted = ...,
    temperature: float | _Omitted = ...,
    top_k: int | _Omitted = ...,
    top_p: float | _Omitted = ...,
    unload_models: bool | _Omitted = ...,
    pass_raw: bool = ...,
    **_extras: Any,
) -> Any: ...

def AILab_Qwen3TTSVoiceInstruct(
    *args: VibeWorkflow,
    _id: str | None = ...,
    character: Literal['Auto', 'Female', 'Male', 'Young Female', 'Young Male', 'Girl', 'Boy', 'Child', 'Teen', 'Adult', 'Senior Female', 'Senior Male', 'Narrator', 'Announcer'] | _Omitted = ...,
    style: Literal['Auto', 'Warm', 'Gentle', 'Calm', 'Cheerful', 'Friendly', 'Serious', 'Sad', 'Angry', 'Excited', 'Soft', 'Deep', 'Clear', 'Emotional', 'Dramatic', 'Whisper', 'Breathy', 'Husky', 'Authoritative', 'Storytelling', 'News Anchor', 'Documentary', 'Customer Support', 'Teacher', 'Audiobook', 'Energetic', 'Relaxed', 'Playful', 'Mysterious', 'Romantic', 'Inspirational', 'Formal', 'Casual', 'ASMR', 'Noir', 'Cinematic', 'Trailer', 'Motivational', 'Robotic', 'Vintage Radio', 'Lullaby', 'Comedy', 'Interview', 'Poetic', 'Philosophical', 'Sportscaster', 'Meditation'] | _Omitted = ...,
    custom_instruct: str | _Omitted = ...,
    pass_raw: bool = ...,
    **_extras: Any,
) -> Any: ...

def AILab_Qwen3TTSVoiceInstructZH(
    *args: VibeWorkflow,
    _id: str | None = ...,
    value: Literal['自动', '女声', '男声', '年轻女声', '年轻男声', '小女孩', '小男孩', '童声', '青少年', '成年', '老年女声', '老年男声', '旁白', '播报'] | _Omitted = ...,
    value_2: Literal['自动', '温暖', '轻柔', '平静', '愉快', '友好', '严肃', '悲伤', '愤怒', '兴奋', '轻声', '低沉', '清晰', '情感', '戏剧', '耳语', '气声', '沙哑', '权威', '讲故事', '新闻主播', '纪录片', '客服', '老师', '有声书', '有活力', '放松', '俏皮', '神秘', '浪漫', '励志', '正式', '随意', 'ASMR', '黑色电影', '电影感', '预告片', '激励', '机械', '复古电台', '摇篮曲', '喜剧', '访谈', '诗意', '哲思', '体育解说', '冥想'] | _Omitted = ...,
    value_3: str | _Omitted = ...,
    pass_raw: bool = ...,
    **_extras: Any,
) -> Any: ...

def AILab_Qwen3TTSVoicesLibrary(
    *args: VibeWorkflow,
    _id: str | None = ...,
    reference_audio: Any | _Omitted = ...,
    device: Literal['auto', 'cuda', 'cpu'] | _Omitted = ...,
    model_size: Literal['0.6B', '1.7B'] | _Omitted = ...,
    precision: Literal['bf16', 'fp16', 'fp32'] | _Omitted = ...,
    reference_text: str | _Omitted = ...,
    voice_name: str | _Omitted = ...,
    x_vector_only: bool | _Omitted = ...,
    save_path: str | _Omitted = ...,
    unload_models: bool | _Omitted = ...,
    pass_raw: bool = ...,
    **_extras: Any,
) -> Any: ...

def AILab_Qwen3TTSWhisperSTT(
    *args: VibeWorkflow,
    _id: str | None = ...,
    audio: Any | _Omitted = ...,
    language: Literal['auto', 'en', 'zh', 'ja', 'ko', 'de', 'fr', 'es', 'it', 'pt', 'ru'] | _Omitted = ...,
    model_size: Literal['tiny', 'base', 'small', 'medium', 'large', 'large-v2', 'large-v3', 'large-v3-turbo'] | _Omitted = ...,
    unload_models: bool | _Omitted = ...,
    pass_raw: bool = ...,
    **_extras: Any,
) -> Any: ...

__all__ = ['AILab_Qwen3TTSCustomVoice', 'AILab_Qwen3TTSCustomVoice_Advanced', 'AILab_Qwen3TTSLoadVoice', 'AILab_Qwen3TTSVoiceClone', 'AILab_Qwen3TTSVoiceClone_Advanced', 'AILab_Qwen3TTSVoiceDesign', 'AILab_Qwen3TTSVoiceDesign_Advanced', 'AILab_Qwen3TTSVoiceInstruct', 'AILab_Qwen3TTSVoiceInstructZH', 'AILab_Qwen3TTSVoicesLibrary', 'AILab_Qwen3TTSWhisperSTT']
