# vibecomfy:generated
# pack: qwen3tts
# source: object_info cache ComfyUI-Qwen3-TTS@local-17c22ad.json sha256:1a32140bab22
# source_sha256: 051de1cd9fb189105db19d11c3d83777c6ed8a92423963b187f6a3e0b872655c
# generator_version: 2.0.0
# generated_at: 1970-01-01T00:00:00+00:00
# classes: 11

"""Type stubs for generated public node wrappers."""
from __future__ import annotations

from typing import Any, Literal

from vibecomfy.workflow import VibeWorkflow

class _Omitted: ...
_UNSET: _Omitted

def Qwen3AudioCompare(
    *args: VibeWorkflow,
    _id: str | None = ...,
    generated_audio: Any | _Omitted = ...,
    reference_audio: Any | _Omitted = ...,
    speaker_encoder_model: Any | _Omitted = ...,
    local_model_path: str | _Omitted = ...,
    pass_raw: bool = ...,
    **_extras: Any,
) -> Any: ...

def Qwen3CustomVoice(
    *args: VibeWorkflow,
    _id: str | None = ...,
    language: Literal['Auto', 'Chinese', 'English', 'Japanese', 'Korean', 'German', 'French', 'Russian', 'Portuguese', 'Spanish', 'Italian'] | _Omitted = ...,
    model: Any | _Omitted = ...,
    seed: int | _Omitted = ...,
    speaker: Literal['Vivian', 'Serena', 'Uncle_Fu', 'Dylan', 'Eric', 'Ryan', 'Aiden', 'Ono_Anna', 'Sohee'] | _Omitted = ...,
    text: str | _Omitted = ...,
    custom_speaker_name: str | _Omitted = ...,
    instruct: str | _Omitted = ...,
    max_new_tokens: int | _Omitted = ...,
    pass_raw: bool = ...,
    **_extras: Any,
) -> Any: ...

def Qwen3DataPrep(
    *args: VibeWorkflow,
    _id: str | None = ...,
    batch_size: int | _Omitted = ...,
    jsonl_path: str | _Omitted = ...,
    source: Literal['HuggingFace', 'ModelScope'] | _Omitted = ...,
    tokenizer_repo: Any | _Omitted = ...,
    pass_raw: bool = ...,
    **_extras: Any,
) -> Any: ...

def Qwen3DatasetFromFolder(
    *args: VibeWorkflow,
    _id: str | None = ...,
    folder_path: str | _Omitted = ...,
    output_filename: str | _Omitted = ...,
    ref_audio_path: str | _Omitted = ...,
    pass_raw: bool = ...,
    **_extras: Any,
) -> Any: ...

def Qwen3FineTune(
    *args: VibeWorkflow,
    _id: str | None = ...,
    batch_size: int | _Omitted = ...,
    epochs: int | _Omitted = ...,
    init_model: Any | _Omitted = ...,
    lr: float | _Omitted = ...,
    output_dir: str | _Omitted = ...,
    seed: int | _Omitted = ...,
    source: Literal['HuggingFace', 'ModelScope'] | _Omitted = ...,
    speaker_name: str | _Omitted = ...,
    train_jsonl: str | _Omitted = ...,
    gradient_accumulation: int | _Omitted = ...,
    gradient_checkpointing: bool | _Omitted = ...,
    log_every_steps: int | _Omitted = ...,
    max_grad_norm: float | _Omitted = ...,
    mixed_precision: Literal['bf16', 'fp32'] | _Omitted = ...,
    resume_training: bool | _Omitted = ...,
    save_every_epochs: int | _Omitted = ...,
    save_every_steps: int | _Omitted = ...,
    save_optimizer_state: bool | _Omitted = ...,
    use_8bit_optimizer: bool | _Omitted = ...,
    warmup_ratio: float | _Omitted = ...,
    warmup_steps: int | _Omitted = ...,
    weight_decay: float | _Omitted = ...,
    pass_raw: bool = ...,
    **_extras: Any,
) -> Any: ...

def Qwen3LoadPrompt(
    *args: VibeWorkflow,
    _id: str | None = ...,
    prompt_file: Any | _Omitted = ...,
    pass_raw: bool = ...,
    **_extras: Any,
) -> Any: ...

def Qwen3Loader(
    *args: VibeWorkflow,
    _id: str | None = ...,
    attention: Literal['auto', 'flash_attention_2', 'sdpa', 'eager'] | _Omitted = ...,
    precision: Literal['fp16', 'bf16', 'fp32'] | _Omitted = ...,
    repo_id: Any | _Omitted = ...,
    source: Literal['HuggingFace', 'ModelScope'] | _Omitted = ...,
    local_model_path: str | _Omitted = ...,
    pass_raw: bool = ...,
    **_extras: Any,
) -> Any: ...

def Qwen3PromptMaker(
    *args: VibeWorkflow,
    _id: str | None = ...,
    ref_audio: Any | _Omitted = ...,
    model: Any | _Omitted = ...,
    ref_text: str | _Omitted = ...,
    ref_audio_max_seconds: float | _Omitted = ...,
    pass_raw: bool = ...,
    **_extras: Any,
) -> Any: ...

def Qwen3SavePrompt(
    *args: VibeWorkflow,
    _id: str | None = ...,
    filename: str | _Omitted = ...,
    prompt: Any | _Omitted = ...,
    pass_raw: bool = ...,
    **_extras: Any,
) -> Any: ...

def Qwen3VoiceClone(
    *args: VibeWorkflow,
    _id: str | None = ...,
    model: Any | _Omitted = ...,
    seed: int | _Omitted = ...,
    text: str | _Omitted = ...,
    language: Literal['Auto', 'Chinese', 'English', 'Japanese', 'Korean', 'German', 'French', 'Russian', 'Portuguese', 'Spanish', 'Italian'] | _Omitted = ...,
    max_new_tokens: int | _Omitted = ...,
    prompt: Any | _Omitted = ...,
    ref_audio: Any | _Omitted = ...,
    ref_audio_max_seconds: float | _Omitted = ...,
    ref_text: str | _Omitted = ...,
    pass_raw: bool = ...,
    **_extras: Any,
) -> Any: ...

def Qwen3VoiceDesign(
    *args: VibeWorkflow,
    _id: str | None = ...,
    instruct: str | _Omitted = ...,
    language: Literal['Auto', 'Chinese', 'English', 'Japanese', 'Korean', 'German', 'French', 'Russian', 'Portuguese', 'Spanish', 'Italian'] | _Omitted = ...,
    model: Any | _Omitted = ...,
    seed: int | _Omitted = ...,
    text: str | _Omitted = ...,
    pass_raw: bool = ...,
    **_extras: Any,
) -> Any: ...

__all__ = ['Qwen3AudioCompare', 'Qwen3CustomVoice', 'Qwen3DataPrep', 'Qwen3DatasetFromFolder', 'Qwen3FineTune', 'Qwen3LoadPrompt', 'Qwen3Loader', 'Qwen3PromptMaker', 'Qwen3SavePrompt', 'Qwen3VoiceClone', 'Qwen3VoiceDesign']
