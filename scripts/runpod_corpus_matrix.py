from __future__ import annotations

import asyncio
import os
import shlex
from pathlib import Path

from scripts.runpod_matrix_plan import build_corpus_matrix_plan, format_ready_rows, format_rows
from scripts.runpod_runner import REMOTE_ROOT, ROOT, run_pod_detached

EXCLUDE_DIRS = {
    ".DS_Store",
    ".git",
    ".mypy_cache",
    ".pytest_cache",
    ".ruff_cache",
    ".venv",
    ".desloppify",
    ".megaplan",
    "__pycache__",
    "vendor",
    "out",
    "output",
    "temp",
}


# REMOVEME after one green matrix
def _legacy_or_registry_block(phase: str) -> str:
    if phase not in {"core", "gguf", "ltx", "wan_wrapper", "qwen_image"}:
        raise ValueError(f"unknown staging phase: {phase}")
    return """
if [ "${VIBECOMFY_REGISTRY_LEGACY:-0}" = "1" ]; then
"""


# REMOVEME after one green matrix
def _registry_staging_fallback(phase: str) -> str:
    return f"""
else
  "$PY" -m vibecomfy.registry.models_loader stage --registry vibecomfy/registry/models.yaml --models-root models --select-phase {phase}
fi
"""


def _remote_script() -> str:
    scope = os.environ.get("VIBECOMFY_MATRIX_SCOPE", "all")
    attention_profile = os.environ.get("VIBECOMFY_ATTENTION_PROFILE", "portable").strip().lower() or "portable"
    if attention_profile in {"default", "sdpa"}:
        attention_profile = "portable"
    elif attention_profile in {"optimized", "sageattn", "sageattention"}:
        attention_profile = "sage"
    if attention_profile not in {"portable", "sage"}:
        raise ValueError("VIBECOMFY_ATTENTION_PROFILE must be 'portable' or 'sage'")
    core_stage_phase = "qwen_image" if scope in {"qwen_image", "qwen_image_2512"} else "core"
    ltx_lean_model_scope = scope in {"ltx_official", "ltx_official_public", "ltx_lightricks", "ltx_iclora", "ltx_iclora_public"}
    hf_token = _load_hf_token()
    hf_token_export = f"export HF_TOKEN={shlex.quote(hf_token)}" if hf_token else "unset HF_TOKEN"
    registry_legacy_export = "export VIBECOMFY_REGISTRY_LEGACY=1" if os.environ.get("VIBECOMFY_REGISTRY_LEGACY") == "1" else "unset VIBECOMFY_REGISTRY_LEGACY"
    plan = build_corpus_matrix_plan(ROOT, scope=scope)
    core_rows = format_rows(plan.core_rows)
    gguf_rows = format_rows(plan.gguf_rows)
    ltx_rows = format_rows(plan.ltx_rows)
    wan_wrapper_rows = format_rows(plan.wan_wrapper_rows)
    ready_rows = format_ready_rows(plan.ready_rows, ROOT)
    return f"""
set -euo pipefail
cd {REMOTE_ROOT}
export XDG_CACHE_HOME=/tmp/vibecomfy-cache
export UV_CACHE_DIR=/tmp/vibecomfy-cache/uv
export HF_HOME=/workspace/.cache/huggingface
export HF_HUB_DISABLE_XET=1
{hf_token_export}
export PIP_CACHE_DIR=/workspace/.cache/pip
export LC_ALL=C.UTF-8
export LANG=C.UTF-8
export PYTORCH_CUDA_ALLOC_CONF=expandable_segments:True
export VIBECOMFY_ATTENTION_PROFILE={shlex.quote(attention_profile)}
{registry_legacy_export}
mkdir -p "$XDG_CACHE_HOME" "$UV_CACHE_DIR" "$HF_HOME" "$PIP_CACHE_DIR"
find "$HF_HOME" -type f -name '*.incomplete' -delete 2>/dev/null || true
if [ "{scope}" = "wan_creation_types" ] || [ "{scope}" = "wan_infinitetalk" ]; then
  find "$HF_HOME/hub" -maxdepth 1 -type d \\( \
    -name 'models--black-forest-labs--*' -o \
    -name 'models--Comfy-Org--flux*' -o \
    -name 'models--Comfy-Org--z_image*' -o \
    -name 'models--Comfy-Org--Qwen-Image*' -o \
    -name 'models--Comfy-Org--HiDream*' -o \
    -name 'models--Lightricks--*' -o \
    -name 'models--qqceqqq--*' -o \
    -name 'models--unsloth--FLUX*' \
  \\) -exec rm -rf {{}} + 2>/dev/null || true
fi
rm -rf out output input custom_nodes/ComfyUI-LTXVideo custom_nodes/ComfyUI-ResAdapter custom_nodes/ComfyUI-GGUF
PY=python3
COMFY=comfyui
$PY -m pip install --upgrade pip wheel setuptools
$PY -m pip install -e '.[dev]'
$PY -m pip install --prefer-binary click rich typer pydantic pydantic-settings pyyaml aiohttp yarl aiofiles aio-pika pillow scipy 'numpy<2.3' tqdm protobuf psutil ConfigArgParse safetensors einops transformers tokenizers sentencepiece 'huggingface_hub[hf_xet]>=0.32.0' opencv-python-headless 'av>=14.2.0,<16' diffusers spandrel gguf questionary ijson requests_cache universal_pathlib blake3 frozendict python-dateutil importlib_resources simpleeval jsonmerge resize-right kornia torchdiffeq torchsde open-clip-torch peft torchinfo albumentations lazy-object-proxy lazy_loader natsort humanize pebble can_ada jaxtyping ml_dtypes colour lightning vtracer skia-python 'stringzilla<4.2.0' scikit-image soundfile joblib threadpoolctl openai anthropic google-generativeai sqlalchemy alembic glfw PyOpenGL comfy_kitchen comfy-aimdo comfyui-frontend-package 'comfyui-workflow-templates>=0.9.44,<0.10' comfyui-embedded-docs 'comfyui_manager>=4.1,<5' opentelemetry-distro opentelemetry-sdk opentelemetry-exporter-otlp opentelemetry-propagator-jaeger opentelemetry-instrumentation opentelemetry-util-http opentelemetry-instrumentation-aio-pika opentelemetry-instrumentation-requests opentelemetry-instrumentation-aiohttp-server opentelemetry-instrumentation-aiohttp-client opentelemetry-instrumentation-asyncio opentelemetry-instrumentation-urllib3 opentelemetry-processor-baggage
$PY -m pip install --extra-index-url https://nodes.appmana.com/simple/ --no-deps --force-reinstall 'comfyui==0.26.0'
if [ "{scope}" = "wan_creation_types" ] || [ "{scope}" = "wan_infinitetalk" ]; then
  $PY -m pip install --index-url https://download.pytorch.org/whl/cu124 --upgrade torch==2.6.0 torchvision==0.21.0 torchaudio==2.6.0
fi
if [ "{attention_profile}" = "sage" ]; then
  rm -rf /tmp/sageattention
  git clone --depth 1 https://github.com/thu-ml/SageAttention.git /tmp/sageattention
  $PY -m pip install --no-build-isolation /tmp/sageattention
  "$PY" - <<'PY'
import sageattention
if not callable(getattr(sageattention, "sageattn", None)):
    raise RuntimeError("sageattention import succeeded but sageattn is missing")
print("sageattention verified")
PY
fi
"$PY" - <<'PY'
from pathlib import Path

path = Path("/usr/local/lib/python3.11/dist-packages/comfy/model_downloader.py")
text = path.read_text()
line = '    HuggingFile("unsloth/FLUX.2-klein-9B-GGUF", "flux-2-klein-9b-Q4_K_M.gguf"),' + chr(10)
if line not in text:
    marker = "    # Flux GGUF" + chr(10)
    if marker not in text:
        raise RuntimeError("Could not find KNOWN_GGUF_MODELS Flux marker in Hiddenswitch ComfyUI")
    path.write_text(text.replace(marker, marker + line))
PY
mkdir -p input custom_nodes out/corpus_matrix/comfyui out/corpus_matrix/logs
cp -a ready_templates/sources/input/. input/
# Smoke audio + audio-bearing guide videos (speech_smoke.wav + ltx_smoke_guide.mp4 etc.)
# come from committed fixtures via vibecomfy.testing.smoke_fixtures. Falls back to synthetic
# fixtures if any committed asset is missing or if VIBECOMFY_FIXTURES_REGENERATE=1.
$PY -m vibecomfy.testing.smoke_fixtures copy --target input
"$PY" - <<'PY'
from pathlib import Path

from PIL import Image, ImageDraw

# Synthetic image fixtures that are not (yet) committed to ready_templates/sources/input/.
# Audio + guide videos are handled by `python -m vibecomfy.testing.smoke_fixtures copy` above.
input_dir = Path("input")
input_dir.mkdir(exist_ok=True)
image = Image.new("RGB", (256, 256), (36, 42, 52))
draw = ImageDraw.Draw(image)
draw.rectangle((52, 52, 204, 204), outline=(235, 96, 74), width=8)
draw.ellipse((90, 78, 166, 154), fill=(95, 168, 136))
draw.line((40, 220, 216, 180), fill=(240, 210, 110), width=6)
image.save(input_dir / "motion_track_input.jpg", quality=92)
image.save(input_dir / "ltx_smoke_frame.png")
image.save(input_dir / "oldman_upscaled.png")
image.save(input_dir / "image (658).png")
for name in ("example.png", "egyptian_queen.png"):
    image.save(input_dir / name)
pasted_dir = input_dir / "pasted"
pasted_dir.mkdir(exist_ok=True)
image.save(pasted_dir / "image (852).png")
mirrored = image.transpose(Image.Transpose.FLIP_LEFT_RIGHT)
mirrored.save(pasted_dir / "image (853).png")
PY
$PY -m pytest -q tests/test_ready_templates.py tests/test_scratchpad_loader.py tests/test_workflow_core.py -k 'not graphbuilder'
$PY -m vibecomfy.cli sources sync --official ready_templates/sources/official --external ready_templates/sources/custom_nodes --custom-nodes custom_nodes
cat > out/corpus_matrix/core_workflows.tsv <<'EOF'
{core_rows}
EOF
cat > out/corpus_matrix/ltx_workflows.tsv <<'EOF'
{ltx_rows}
EOF
cat > out/corpus_matrix/gguf_workflows.tsv <<'EOF'
{gguf_rows}
EOF
cat > out/corpus_matrix/wan_wrapper_workflows.tsv <<'EOF'
{wan_wrapper_rows}
EOF
cat > out/corpus_matrix/ready_workflows.tsv <<'EOF'
{ready_rows}
EOF
printf 'id\tmedia\tstatus\tbaseline_seconds\tconvert_seconds\tvalidate_seconds\tvibecomfy_seconds\tmedia_files\tbytes\tfailure\n' > out/corpus_matrix/results.tsv
clean_failure() {{
  tail -80 "$1" | tr '\\t\\n' '  ' | tr -cd '\\11\\12\\15\\40-\\176' | cut -c1-900
}}
write_port_report() {{
  local id="$1"
  local workflow="$2"
  local report="out/corpus_matrix/logs/${{id}}.port_report.json"
  local log="out/corpus_matrix/logs/${{id}}.port_check.log"
  local status="ok"
  if ! "$PY" -m vibecomfy.cli port check "$workflow" --json >"$report" 2>"$log"; then
    status="needs_attention"
  fi
  "$PY" - "$id" "$status" "$report" >> out/corpus_matrix/live.log <<'PY' || true
import json
import sys
from pathlib import Path

workflow_id, status, path = sys.argv[1], sys.argv[2], Path(sys.argv[3])
try:
    report = json.loads(path.read_text(encoding="utf-8"))
except Exception as exc:
    print(f"port_report id={{workflow_id}} status=failed error={{type(exc).__name__}}:{{exc}}")
    raise SystemExit(0)
counts = {{"error": 0, "warning": 0, "info": 0}}
for issue in report.get("diagnostics", []):
    counts[issue.get("severity", "warning")] = counts.get(issue.get("severity", "warning"), 0) + 1
print(
    "port_report "
    f"id={{workflow_id}} status={{status}} "
    f"errors={{counts.get('error', 0)}} warnings={{counts.get('warning', 0)}} "
    f"assets={{len(report.get('asset_candidates', []))}} packs={{len(report.get('node_pack_suggestions', []))}}"
)
PY
}}
run_port_convert_preview() {{
  local id="$1"
  local workflow="$2"
  local out="out/corpus_matrix/logs/${{id}}.port_scratchpad.py"
  local json_log="out/corpus_matrix/logs/${{id}}.port_convert.json"
  local err_log="out/corpus_matrix/logs/${{id}}.port_convert.log"
  "$PY" -m vibecomfy.cli port convert "$workflow" --out "$out" --json >"$json_log" 2>"$err_log" || true
}}
count_media_files() {{
  find "$@" -type f \\( -name '*.png' -o -name '*.webp' -o -name '*.mp4' -o -name '*.webm' -o -name '*.mp3' -o -name '*.glb' \\) 2>/dev/null | wc -l | tr -d ' '
}}
sum_media_bytes() {{
  find "$@" -type f \\( -name '*.png' -o -name '*.webp' -o -name '*.mp4' -o -name '*.webm' -o -name '*.mp3' -o -name '*.glb' \\) -exec stat -c '%s' {{}} + 2>/dev/null | awk '{{s+=$1}} END {{print s+0}}'
}}
run_with_media_watch() {{
  local log="$1"
  local media_dir="$2"
  local timeout_seconds="$3"
  shift 3
  local before_count
  before_count=$(count_media_files "$media_dir")
  timeout "$timeout_seconds" "$@" >"$log" 2>&1 &
  local run_pid=$!
  local media_seen_at=0
  local stopped_after_media=0
  while kill -0 "$run_pid" 2>/dev/null; do
    sleep 10
    local current_count
    current_count=$(count_media_files "$media_dir")
    if [ "$current_count" -gt "$before_count" ]; then
      if [ "$media_seen_at" -eq 0 ]; then
        media_seen_at=$(date +%s)
      elif [ $(( $(date +%s) - media_seen_at )) -ge 30 ]; then
        echo "media_watchdog_terminating_after_output before=$before_count current=$current_count" >>"$log"
        stopped_after_media=1
        kill -TERM "$run_pid" 2>/dev/null || true
        sleep 5
        kill -KILL "$run_pid" 2>/dev/null || true
        break
      fi
    fi
  done
  local rc=0
  wait "$run_pid" || rc=$?
  if [ "$stopped_after_media" -eq 1 ]; then
    return 0
  fi
  return "$rc"
}}
prepare_workflow() {{
  local id="$1"
  local wf="$2"
  local prepared=""
  local prepare_log="out/corpus_matrix/logs/${{id}}.prepare.log"
  local output="out/corpus_matrix/patched/${{id}}.json"
  mkdir -p out/corpus_matrix/patched
  if ! prepared=$("$PY" scripts/runpod_matrix_remote.py prepare-workflow "$id" "$wf" "$output" 2>"$prepare_log"); then
    cat "$prepare_log" >&2
    return 1
  fi
  if [ -n "$prepared" ] && [ -f "$prepared" ]; then
    echo "$prepared"
    return 0
  fi
  if [ -f "$output" ]; then
    echo "$output"
    return 0
  fi
  if [ -f "$wf" ]; then
    echo "$wf"
    return 0
  fi
  echo "prepare_workflow produced no workflow file: id=$id source=$wf prepared=$prepared output=$output" >"$prepare_log"
  return 1
}}
run_workflow_set() {{
local workflow_file="$1"
while IFS=$'\\t' read -r id wf media; do
  [ -n "$id" ] || continue
  echo "=== CORPUS $id ==="
  if ! work_wf=$(prepare_workflow "$id" "$wf"); then
    failure=$(clean_failure "out/corpus_matrix/logs/${{id}}.prepare.log")
    echo -e "$id\\t$media\\tprepare_failed\\t0\\t0\\t0\\t0\\t0\\t0\\t$failure" >> out/corpus_matrix/results.tsv
    continue
  fi
  if [ ! -f "$work_wf" ]; then
    echo "prepared workflow path is not a file: $work_wf" >"out/corpus_matrix/logs/${{id}}.prepare.log"
    failure=$(clean_failure "out/corpus_matrix/logs/${{id}}.prepare.log")
    echo -e "$id\\t$media\\tprepare_failed\\t0\\t0\\t0\\t0\\t0\\t0\\t$failure" >> out/corpus_matrix/results.tsv
    continue
  fi
  cp "$work_wf" "out/corpus_matrix/logs/${{id}}.prepared.json" || true
  write_port_report "$id" "$work_wf"
  comfy_extra_args=""
  vibe_config='{{"preview_method":"none"}}'
  workflow_override_args=(--steps 1 --seed 123 --prompt "a compact red cube on a neutral background")
  vibe_override_args=(--steps 1 --seed 123 --prompt "a compact red cube on a neutral background")
  case "$id" in
    ltx2_3*)
      comfy_extra_args="--reserve-vram 12 --cache-none --fp8_e4m3fn-text-enc"
      vibe_config='{{"reserve_vram":12,"cache_none":true,"fp8_e4m3fn_text_enc":true,"preview_method":"none"}}'
      workflow_timeout=1800
      ;;
    wanvideo_wrapper*)
      # WanVideoWrapper examples use custom prompt/sampler nodes. Hiddenswitch's
      # generic --prompt/--steps replacement path only understands mainline
      # Comfy text/sampler nodes, so the baseline must run with its
      # source-authored prompt and step wiring. The vibecomfy CLI now refuses
      # --prompt/--steps when no eligible target is registered, so the
      # universal vibe_override_args is safe to keep as-is.
      workflow_override_args=(--seed 123)
      workflow_timeout=2400
      ;;
    flux2_klein*)
      # Flux Klein workflows use custom Flux scheduler/conditioning nodes.
      # Universal --prompt/--steps overrides intentionally target only known
      # mainline fields, so matrix validation should exercise the workflow's
      # source-authored prompt and sampling settings instead of failing on
      # deliberate override guards.
      workflow_override_args=(--seed 123)
      vibe_override_args=(--seed 123)
      workflow_timeout=2400
      ;;
    qwen_image_2512)
      # Qwen Image 2512 switches step/cfg values through primitive nodes, so
      # VibeComfy's mainline sampler override guard correctly rejects --steps.
      # The workflow preparation policy already fixes this to a 4-step
      # Lightning path for runtime validation.
      vibe_override_args=(--seed 123 --prompt "a compact red cube on a neutral background")
      workflow_timeout=2400
      ;;
    *)
      if [ "$media" = "audio" ]; then
        # Audio workflows use model-specific text/audio encoder nodes; the
        # HiddenSwitch baseline override only targets image text encoders, so
        # we strip --prompt/--steps for both execution paths.
        workflow_override_args=(--seed 123)
        vibe_override_args=(--seed 123)
      fi
      workflow_timeout=2400
      ;;
  esac
  mkdir -p "out/corpus_matrix/comfyui/$id" out/scratchpads
  start=$(date +%s)
  baseline_log="out/corpus_matrix/logs/${{id}}.baseline.log"
  if run_with_media_watch "$baseline_log" "out/corpus_matrix/comfyui/$id" "$workflow_timeout" "$COMFY" run-workflow "$work_wf" --cwd . --input-directory input --output-directory "out/corpus_matrix/comfyui/$id" "${{workflow_override_args[@]}}" $comfy_extra_args --preview-method none --disable-progress; then
    baseline_seconds=$(( $(date +%s) - start ))
  else
    baseline_seconds=$(( $(date +%s) - start ))
    baseline_media_files=$(count_media_files "out/corpus_matrix/comfyui/$id")
    if [ "$baseline_media_files" -gt 0 ]; then
      echo "baseline_nonzero_after_media id=$id files=$baseline_media_files" >> out/corpus_matrix/live.log
    else
    failure=$(clean_failure "$baseline_log")
    echo -e "$id\\t$media\\tbaseline_failed\\t$baseline_seconds\\t0\\t0\\t0\\t0\\t0\\t$failure" >> out/corpus_matrix/results.tsv
    continue
    fi
  fi

  start=$(date +%s)
  convert_log="out/corpus_matrix/logs/${{id}}.convert.log"
  if "$PY" -m vibecomfy.cli convert "$work_wf" --out "out/scratchpads/$id.py" >"$convert_log" 2>&1; then
    convert_seconds=$(( $(date +%s) - start ))
    cp "out/scratchpads/$id.py" "out/corpus_matrix/logs/${{id}}.scratchpad.py" || true
    run_port_convert_preview "$id" "$work_wf"
  else
    convert_seconds=$(( $(date +%s) - start ))
    failure=$(clean_failure "$convert_log")
    echo -e "$id\\t$media\\tconvert_failed\\t$baseline_seconds\\t$convert_seconds\\t0\\t0\\t0\\t0\\t$failure" >> out/corpus_matrix/results.tsv
    continue
  fi

  start=$(date +%s)
  validate_log="out/corpus_matrix/logs/${{id}}.validate.log"
  if "$PY" -m vibecomfy.cli validate "out/scratchpads/$id.py" >"$validate_log" 2>&1; then
    validate_seconds=$(( $(date +%s) - start ))
  else
    validate_seconds=$(( $(date +%s) - start ))
    {{
      echo "--- scratchpad ---"
      sed -n '1,180p' "out/scratchpads/$id.py"
      echo "--- prepared workflow ---"
      sed -n '1,220p' "$work_wf"
    }} >>"$validate_log" 2>&1 || true
    failure=$(clean_failure "$validate_log")
    echo -e "$id\\t$media\\tvalidate_failed\\t$baseline_seconds\\t$convert_seconds\\t$validate_seconds\\t0\\t0\\t0\\t$failure" >> out/corpus_matrix/results.tsv
    continue
  fi

  start=$(date +%s)
  vibe_log="out/corpus_matrix/logs/${{id}}.vibecomfy.log"
  mkdir -p output
  before=$(find output -type f 2>/dev/null | wc -l | tr -d ' ')
  if VIBECOMFY_COMFY_CONFIGURATION="$vibe_config" run_with_media_watch "$vibe_log" output "$workflow_timeout" "$PY" -m vibecomfy.cli run "out/scratchpads/$id.py" --runtime embedded --backend api "${{vibe_override_args[@]}}"; then
    vibecomfy_seconds=$(( $(date +%s) - start ))
  else
    vibecomfy_seconds=$(( $(date +%s) - start ))
    after=$(find output -type f 2>/dev/null | wc -l | tr -d ' ')
    if [ "$after" -gt "$before" ]; then
      echo "vibecomfy_nonzero_after_media id=$id before=$before after=$after" >> out/corpus_matrix/live.log
    else
    failure=$(clean_failure "$vibe_log")
    echo -e "$id\\t$media\\tvibecomfy_failed\\t$baseline_seconds\\t$convert_seconds\\t$validate_seconds\\t$vibecomfy_seconds\\t0\\t0\\t$failure" >> out/corpus_matrix/results.tsv
    continue
    fi
  fi
  after=$(find output -type f 2>/dev/null | wc -l | tr -d ' ')
  media_files=$(count_media_files "out/corpus_matrix/comfyui/$id" output)
  bytes=$(sum_media_bytes "out/corpus_matrix/comfyui/$id" output)
  if [ "$after" -le "$before" ]; then
    echo -e "$id\\t$media\\tno_new_vibecomfy_output\\t$baseline_seconds\\t$convert_seconds\\t$validate_seconds\\t$vibecomfy_seconds\\t$media_files\\t$bytes\\tno new output file appeared under output/" >> out/corpus_matrix/results.tsv
  else
    echo -e "$id\\t$media\\tok\\t$baseline_seconds\\t$convert_seconds\\t$validate_seconds\\t$vibecomfy_seconds\\t$media_files\\t$bytes\\t" >> out/corpus_matrix/results.tsv
  fi
done < "$workflow_file"
}}
validate_ready_set() {{
while IFS=$'\\t' read -r id ready_path media; do
  [ -n "$id" ] || continue
  echo "=== READY $id ==="
  if [ ! -f "$ready_path" ]; then
    echo -e "$id\\t$media\\tready_missing\\t0\\t0\\t0\\t0\\t0\\t0\\t$ready_path is missing" >> out/corpus_matrix/ready_results.tsv
    continue
  fi
  start=$(date +%s)
  ready_log="out/corpus_matrix/logs/${{id}}.ready_validate.log"
  if "$PY" -m vibecomfy.cli validate "$ready_path" >"$ready_log" 2>&1; then
    ready_seconds=$(( $(date +%s) - start ))
    echo -e "$id\\t$media\\tready_ok\\t0\\t0\\t$ready_seconds\\t0\\t0\\t0\\t" >> out/corpus_matrix/ready_results.tsv
  else
    ready_seconds=$(( $(date +%s) - start ))
    failure=$(clean_failure "$ready_log")
    echo -e "$id\\t$media\\tready_validate_failed\\t0\\t0\\t$ready_seconds\\t0\\t0\\t0\\t$failure" >> out/corpus_matrix/ready_results.tsv
  fi
done < "$1"
}}
printf 'id\tmedia\tstatus\tbaseline_seconds\tconvert_seconds\tvalidate_seconds\tvibecomfy_seconds\tmedia_files\tbytes\tfailure\n' > out/corpus_matrix/ready_results.tsv
if grep -q '[^[:space:]]' out/corpus_matrix/core_workflows.tsv; then
if [ "{scope}" = "qwen_tts" ]; then
git clone https://github.com/1038lab/ComfyUI-QwenTTS.git custom_nodes/ComfyUI-QwenTTS
git -C custom_nodes/ComfyUI-QwenTTS checkout d8122a8ba835b65fd65c113d2b273b1ad1579293
$PY -m pip install 'transformers>=4.57,<5' accelerate librosa soundfile tiktoken sentencepiece einops openai-whisper
"$PY" - <<'PY'
from huggingface_hub import snapshot_download
from pathlib import Path

root = Path("models/TTS/Qwen3-TTS")
root.mkdir(parents=True, exist_ok=True)
for repo in [
    "Qwen/Qwen3-TTS-Tokenizer-12Hz",
    "Qwen/Qwen3-TTS-12Hz-0.6B-CustomVoice",
    "Qwen/Qwen3-TTS-12Hz-0.6B-Base",
    "Qwen/Qwen3-TTS-12Hz-1.7B-VoiceDesign",
]:
    local_dir = root / repo.rsplit("/", 1)[-1]
    snapshot_download(repo_id=repo, local_dir=local_dir)
PY
$PY -m vibecomfy.cli sources sync --official ready_templates/sources/official --external ready_templates/sources/custom_nodes --custom-nodes custom_nodes
else
{_legacy_or_registry_block(core_stage_phase)}
"$PY" - <<'PY'
from huggingface_hub import hf_hub_download
from pathlib import Path
import hashlib
import os
import shutil

def materialize_model(repo, filename, targets, min_size):
    pins = {{
        ("Comfy-Org/flux2-dev", "split_files/vae/flux2-vae.safetensors"): {{
            "revision": "ab9055628ea245000e610f2aa2c96f4746093546",
            "size_bytes": 336_213_556,
            "sha256": "d64f3a68e1cc4f9f4e29b6e0da38a0204fe9a49f2d4053f0ec1fa1ca02f9c4b5",
        }},
    }}
    pin = pins.get((repo, filename), {{}})
    path = Path(hf_hub_download(repo_id=repo, filename=filename, **({{"revision": pin["revision"]}} if pin else {{}}))).resolve(strict=True)
    size = path.stat().st_size
    if size < min_size:
        raise RuntimeError(f"{{repo}}/{{filename}} resolved to {{path}} with only {{size}} bytes")
    if pin and (size != pin["size_bytes"] or hashlib.sha256(path.read_bytes()).hexdigest() != pin["sha256"]):
        raise RuntimeError(f"{{repo}}/{{filename}} does not match its pinned size or sha256")
    for target in targets:
        target.parent.mkdir(parents=True, exist_ok=True)
        if target.exists() or target.is_symlink():
            try:
                if target.stat().st_ino == path.stat().st_ino and target.stat().st_dev == path.stat().st_dev:
                    continue
            except OSError:
                pass
            raise RuntimeError(f"{{target}} already exists with a different source identity")
        try:
            os.link(path, target)
        except OSError:
            os.symlink(path, target)
        staged = target.resolve(strict=True)
        staged_size = staged.stat().st_size
        if staged_size < min_size:
            raise RuntimeError(f"{{target}} staged from {{path}} with only {{staged_size}} bytes")

downloads = [
    ("black-forest-labs/FLUX.2-klein-4b-fp8", "flux-2-klein-4b-fp8.safetensors", [
        Path("models/diffusion_models/flux-2-klein-4b-fp8.safetensors"),
    ], 1_000_000_000),
    ("Comfy-Org/z_image_turbo", "split_files/text_encoders/qwen_3_4b.safetensors", [
        Path("models/text_encoders/qwen_3_4b.safetensors"),
    ], 1_000_000_000),
    ("Comfy-Org/flux2-dev", "split_files/vae/flux2-vae.safetensors", [
        Path("models/vae/flux2-vae.safetensors"),
    ], 100_000_000),
    ("black-forest-labs/FLUX.2-klein-base-4b-fp8", "flux-2-klein-base-4b-fp8.safetensors", [
        Path("models/diffusion_models/flux-2-klein-base-4b-fp8.safetensors"),
    ], 1_000_000_000),
    ("black-forest-labs/FLUX.2-small-decoder", "full_encoder_small_decoder.safetensors", [
        Path("models/vae/full_encoder_small_decoder.safetensors"),
    ], 100_000_000),
    ("Comfy-Org/ace_step_1.5_ComfyUI_files", "split_files/text_encoders/qwen_0.6b_ace15.safetensors", [
        Path("models/text_encoders/qwen_0.6b_ace15.safetensors"),
    ], 100_000_000),
    ("Comfy-Org/ace_step_1.5_ComfyUI_files", "split_files/text_encoders/qwen_4b_ace15.safetensors", [
        Path("models/text_encoders/qwen_4b_ace15.safetensors"),
    ], 1_000_000_000),
    ("Comfy-Org/ace_step_1.5_ComfyUI_files", "split_files/vae/ace_1.5_vae.safetensors", [
        Path("models/vae/ace_1.5_vae.safetensors"),
    ], 100_000_000),
    ("Comfy-Org/ace_step_1.5_ComfyUI_files", "split_files/diffusion_models/acestep_v1.5_turbo.safetensors", [
        Path("models/diffusion_models/acestep_v1.5_turbo.safetensors"),
    ], 1_000_000_000),
]
for repo, filename, targets, min_size in downloads:
    materialize_model(repo, filename, targets, min_size)
PY
{_registry_staging_fallback(core_stage_phase)}
fi
fi
run_workflow_set out/corpus_matrix/core_workflows.tsv
if grep -q '[^[:space:]]' out/corpus_matrix/gguf_workflows.tsv; then
git clone https://github.com/city96/ComfyUI-GGUF.git custom_nodes/ComfyUI-GGUF
if [ -f custom_nodes/ComfyUI-GGUF/requirements.txt ]; then $PY -m pip install -r custom_nodes/ComfyUI-GGUF/requirements.txt; fi
"$PY" - <<'PY'
from pathlib import Path

path = Path("/usr/local/lib/python3.11/dist-packages/comfy/model_downloader.py")
text = path.read_text()
line = '    HuggingFile("unsloth/FLUX.2-klein-9B-GGUF", "flux-2-klein-9b-Q4_K_M.gguf"),' + chr(10)
if line not in text:
    marker = "    # Flux GGUF" + chr(10)
    if marker not in text:
        raise RuntimeError("Could not find KNOWN_GGUF_MODELS Flux marker in Hiddenswitch ComfyUI")
    path.write_text(text.replace(marker, marker + line))
PY
{_legacy_or_registry_block("gguf")}
"$PY" - <<'PY'
from huggingface_hub import hf_hub_download
from pathlib import Path
import hashlib
import os
import shutil

def materialize_model(repo, filename, targets, min_size):
    pins = {{
        ("Comfy-Org/vae-text-encorder-for-flux-klein-9b", "split_files/vae/flux2-vae.safetensors"): {{
            "revision": "3f62d9d8ae1fec33c6e91453d5c712855b096b55",
            "size_bytes": 336_211_292,
            "sha256": "868fe7b343cc8f3a19dbcfcafbc3d5f888802be3f89bd81b65b3621a066ce8f3",
        }},
    }}
    pin = pins.get((repo, filename), {{}})
    path = Path(hf_hub_download(repo_id=repo, filename=filename, **({{"revision": pin["revision"]}} if pin else {{}}))).resolve(strict=True)
    size = path.stat().st_size
    if size < min_size:
        raise RuntimeError(f"{{repo}}/{{filename}} resolved to {{path}} with only {{size}} bytes")
    if pin and (size != pin["size_bytes"] or hashlib.sha256(path.read_bytes()).hexdigest() != pin["sha256"]):
        raise RuntimeError(f"{{repo}}/{{filename}} does not match its pinned size or sha256")
    for target in targets:
        target.parent.mkdir(parents=True, exist_ok=True)
        if target.exists() or target.is_symlink():
            try:
                if target.stat().st_ino == path.stat().st_ino and target.stat().st_dev == path.stat().st_dev:
                    continue
            except OSError:
                pass
            raise RuntimeError(f"{{target}} already exists with a different source identity")
        try:
            os.link(path, target)
        except OSError:
            os.symlink(path, target)
        staged = target.resolve(strict=True)
        staged_size = staged.stat().st_size
        if staged_size < min_size:
            raise RuntimeError(f"{{target}} staged from {{path}} with only {{staged_size}} bytes")

downloads = [
    ("unsloth/FLUX.2-klein-9B-GGUF", "flux-2-klein-9b-Q4_K_M.gguf", [
        Path("models/diffusion_models/flux-2-klein-9b-Q4_K_M.gguf"),
        Path("models/unet/flux-2-klein-9b-Q4_K_M.gguf"),
        Path("models/unet_gguf/flux-2-klein-9b-Q4_K_M.gguf"),
    ], 5_000_000_000),
    ("Comfy-Org/vae-text-encorder-for-flux-klein-9b", "split_files/vae/flux2-vae.safetensors", [
        Path("models/vae/flux2-klein-9b-vae.safetensors"),
    ], 100_000_000),
]
for repo, filename, targets, min_size in downloads:
    materialize_model(repo, filename, targets, min_size)
PY
{_registry_staging_fallback("gguf")}
$PY -m vibecomfy.cli sources sync --official ready_templates/sources/official --external ready_templates/sources/custom_nodes --custom-nodes custom_nodes
run_workflow_set out/corpus_matrix/gguf_workflows.tsv
fi
if grep -q '[^[:space:]]' out/corpus_matrix/ltx_workflows.tsv; then
git clone https://github.com/Lightricks/ComfyUI-LTXVideo.git custom_nodes/ComfyUI-LTXVideo
git -C custom_nodes/ComfyUI-LTXVideo checkout 937831df0e5e1f707340b7e037a52e9d1196e3f8
git clone https://github.com/ClownsharkBatwing/RES4LYF.git custom_nodes/ComfyUI-ResAdapter || true
git clone https://github.com/kijai/ComfyUI-KJNodes.git custom_nodes/ComfyUI-KJNodes
git -C custom_nodes/ComfyUI-KJNodes checkout b7646ad70a7daa7aeb919ca542274758d26ba2df
git clone https://github.com/Fannovel16/comfyui_controlnet_aux.git custom_nodes/comfyui_controlnet_aux || true
git clone https://github.com/kijai/ComfyUI-DepthAnythingV2.git custom_nodes/ComfyUI-DepthAnythingV2 || true
git clone https://github.com/Kosinkadink/ComfyUI-VideoHelperSuite.git custom_nodes/ComfyUI-VideoHelperSuite || true
git clone https://github.com/rgthree/rgthree-comfy.git custom_nodes/rgthree-comfy || true
git clone https://github.com/yolain/ComfyUI-Easy-Use.git custom_nodes/ComfyUI-Easy-Use || true
git -C custom_nodes/ComfyUI-Easy-Use checkout 4de1ab3b66e48da916b6f263bacd001df53a2720 || true
git clone https://github.com/kijai/ComfyUI-WanVideoWrapper.git custom_nodes/ComfyUI-WanVideoWrapper || true
# RR1-FIX-REV: packs below are provisioned as LIVE RUNTIME capability only.
# The former "verified object_info capture" claim was FALSE for four providers
# (audio-separation-nodes-comfyui@ac33956, ComfyUI-Easy-Use@4de1ab3,
# ComfyUI-Inspire-Pack@d23db9a, ComfyUI-llama-cpp_vlm@f2209cc): their
# snapshots were offline stub extraction, never a live /object_info surface.
# Those cache files are removed/unindexed, and their classes are recorded in
# UNPROVEN_PROVIDER_CLASSES — preflight refuses paid calls on edit scenarios
# that need them until a same-pack LIVE capture exists.
git clone https://github.com/ltdrdata/ComfyUI-Inspire-Pack.git custom_nodes/ComfyUI-Inspire-Pack || true
git -C custom_nodes/ComfyUI-Inspire-Pack checkout d23db9aa544de9a6d4c609cb7005fa9e0d42031d || true
git clone https://github.com/lihaoyun6/ComfyUI-llama-cpp_vlm.git custom_nodes/ComfyUI-llama-cpp_vlm || true
git -C custom_nodes/ComfyUI-llama-cpp_vlm checkout f2209cccb726647640271bd1cea071a570fc62f5 || true
# PROHIBITION (RRSYN-4 / RR1-FIX-REV): AudioCombine/AudioSeparation/AudioFilter/
# AudioVolumeNormalization/VocalAndSoundRemoverNode/VibeVoice/easy forLoop*/
# ImageBatchSplitter //Inspire/llama_cpp_* classes must NEVER be registered
# into any pack snapshot without a same-pack LIVE capture proving that pack
# owns them.  Absence stays an honest non-pass where a scenario requires such
# an edit.
$PY -m pip install PyWavelets matplotlib
if [ -f custom_nodes/ComfyUI-LTXVideo/requirements.txt ]; then $PY -m pip install --no-deps -r custom_nodes/ComfyUI-LTXVideo/requirements.txt || true; fi
if [ -f custom_nodes/ComfyUI-KJNodes/requirements.txt ]; then $PY -m pip install --no-deps -r custom_nodes/ComfyUI-KJNodes/requirements.txt || true; fi
if [ -f custom_nodes/comfyui_controlnet_aux/requirements.txt ]; then $PY -m pip install --no-deps -r custom_nodes/comfyui_controlnet_aux/requirements.txt || true; fi
if [ -f custom_nodes/ComfyUI-DepthAnythingV2/requirements.txt ]; then $PY -m pip install --no-deps -r custom_nodes/ComfyUI-DepthAnythingV2/requirements.txt || true; fi
if [ -f custom_nodes/ComfyUI-VideoHelperSuite/requirements.txt ]; then $PY -m pip install --no-deps -r custom_nodes/ComfyUI-VideoHelperSuite/requirements.txt || true; fi
if [ -f custom_nodes/rgthree-comfy/requirements.txt ]; then $PY -m pip install --no-deps -r custom_nodes/rgthree-comfy/requirements.txt || true; fi
if [ -f custom_nodes/ComfyUI-Easy-Use/requirements.txt ]; then $PY -m pip install --no-deps -r custom_nodes/ComfyUI-Easy-Use/requirements.txt || true; fi
if [ -f custom_nodes/ComfyUI-WanVideoWrapper/requirements.txt ]; then $PY -m pip install --no-deps -r custom_nodes/ComfyUI-WanVideoWrapper/requirements.txt || true; fi
if [ -f custom_nodes/ComfyUI-KJNodes/nodes/ltxv_nodes.py ]; then
"$PY" - <<'PY'
from pathlib import Path
import re

path = Path("custom_nodes/ComfyUI-KJNodes/nodes/ltxv_nodes.py")
text = path.read_text(encoding="utf-8")
pattern = r"(?m)^([ \\t]*)message\\.write\\(struct\\.pack\\('16p',\\s*serv\\.last_node_id\\.encode\\('ascii'\\)\\)\\)"
replacement = "\\g<1>node_id = serv.last_node_id or '0'\\n\\g<1>message.write(struct.pack('16p', node_id.encode('ascii')))"
text = re.sub(pattern, replacement, text)
path.write_text(text, encoding="utf-8")
PY
fi
{_legacy_or_registry_block("ltx")}
"$PY" - <<'PY'
from huggingface_hub import hf_hub_download
from pathlib import Path
import os
import shutil

def materialize_model(repo, filename, targets, min_size):
    path = Path(hf_hub_download(repo_id=repo, filename=filename)).resolve(strict=True)
    size = path.stat().st_size
    if size < min_size:
        raise RuntimeError(f"{{repo}}/{{filename}} resolved to {{path}} with only {{size}} bytes")
    for target in targets:
        target.parent.mkdir(parents=True, exist_ok=True)
        if target.exists() or target.is_symlink():
            target.unlink()
        try:
            os.link(path, target)
        except OSError:
            os.symlink(path, target)
        staged = target.resolve(strict=True)
        staged_size = staged.stat().st_size
        if staged_size < min_size:
            raise RuntimeError(f"{{target}} staged from {{path}} with only {{staged_size}} bytes")

downloads = [
    ("Lightricks/LTX-2.3-fp8", "ltx-2.3-22b-dev-fp8.safetensors", [
        Path("models/checkpoints/ltx-2.3-22b-dev-fp8.safetensors"),
    ], 20_000_000_000),
    ("Comfy-Org/ltx-2", "split_files/text_encoders/gemma_3_12B_it_fp4_mixed.safetensors", [
        Path("models/text_encoders/gemma_3_12B_it_fp4_mixed.safetensors"),
    ], 5_000_000_000),
]
if not {str(ltx_lean_model_scope)}:
    downloads.extend([
    ("Kijai/LTX2.3_comfy", "text_encoders/ltx-2.3_text_projection_bf16.safetensors", [
        Path("models/text_encoders/ltx-2.3_text_projection_bf16.safetensors"),
    ], 1_000_000_000),
    ("Kijai/LTX2.3_comfy", "vae/LTX23_video_vae_bf16.safetensors", [
        Path("models/vae/LTX23_video_vae_bf16.safetensors"),
    ], 1_000_000_000),
    ("Kijai/LTX2.3_comfy", "vae/LTX23_audio_vae_bf16.safetensors", [
        Path("models/vae/LTX23_audio_vae_bf16.safetensors"),
    ], 100_000_000),
    ("Kijai/LTX2.3_comfy", "vae/taeltx2_3.safetensors", [
        Path("models/vae/taeltx2_3.safetensors"),
    ], 10_000_000),
    ("Kijai/LTX2.3_comfy", "diffusion_models/ltx-2.3-22b-distilled-1.1_transformer_only_fp8_scaled.safetensors", [
        Path("models/diffusion_models/ltx-2.3-22b-distilled-1.1_transformer_only_fp8_scaled.safetensors"),
    ], 10_000_000_000),
    ("Kijai/LTX2.3_comfy", "diffusion_models/ltx-2.3-22b-distilled_transformer_only_fp8_scaled.safetensors", [
        Path("models/diffusion_models/ltx-2.3-22b-distilled_transformer_only_fp8_scaled.safetensors"),
    ], 10_000_000_000),
    ])
downloads.extend([
    ("Lightricks/LTX-2.3", "ltx-2.3-22b-distilled-lora-384-1.1.safetensors", [
        Path("models/loras/ltxv/ltx2/ltx-2.3-22b-distilled-lora-384-1.1.safetensors"),
        Path("models/loras/ltx-2.3-22b-distilled-lora-384-1.1.safetensors"),
    ], 100_000_000),
    ("Lightricks/LTX-2.3", "ltx-2.3-spatial-upscaler-x2-1.1.safetensors", [
        Path("models/latent_upscale_models/ltx-2.3-spatial-upscaler-x2-1.1.safetensors"),
        Path("models/upscale_models/ltx-2.3-spatial-upscaler-x2-1.1.safetensors"),
        Path("models/loras/ltxv/ltx2/ltx-2.3-spatial-upscaler-x2-1.1.safetensors"),
    ], 100_000_000),
    ("qqceqqq/LTX-2.3-22b-IC-LoRA-Motion-Track-Control", "ltx-2.3-22b-ic-lora-motion-track-control-ref0.5.safetensors", [
        Path("models/loras/ltxv/ltx2/ltx-2.3-22b-ic-lora-motion-track-control-ref0.5.safetensors"),
        Path("models/loras/ltx-2.3-22b-ic-lora-motion-track-control-ref0.5.safetensors"),
    ], 10_000_000),
    ("qqceqqq/LTX-2.3-22b-IC-LoRA-Union-Control", "ltx-2.3-22b-ic-lora-union-control-ref0.5.safetensors", [
        Path("models/loras/ltxv/ltx2/ltx-2.3-22b-ic-lora-union-control-ref0.5.safetensors"),
        Path("models/loras/ltx-2.3-22b-ic-lora-union-control-ref0.5.safetensors"),
    ], 10_000_000),
])
if os.environ.get("HF_TOKEN") and "{scope}" not in ("ltx_official_public", "ltx_iclora_public"):
    downloads.append(("Lightricks/LTX-2.3-22b-IC-LoRA-HDR", "ltx-2.3-22b-ic-lora-hdr-0.9.safetensors", [
        Path("models/loras/ltxv/ltx2/ltx-2.3-22b-ic-lora-hdr-0.9.safetensors"),
        Path("models/loras/ltx-2.3-22b-ic-lora-hdr-0.9.safetensors"),
    ], 10_000_000))
else:
    print("Skipping gated LTX HDR IC-LoRA download because HF_TOKEN is not set.")
for repo, filename, targets, min_size in downloads:
    materialize_model(repo, filename, targets, min_size)
PY
{_registry_staging_fallback("ltx")}
$PY -m vibecomfy.cli sources sync --official ready_templates/sources/official --external ready_templates/sources/custom_nodes --custom-nodes custom_nodes
if [ "{scope}" = "ltx_official" ] || [ "{scope}" = "ltx_official_public" ] || [ "{scope}" = "ltx_lightricks" ] || [ "{scope}" = "ltx_iclora" ] || [ "{scope}" = "ltx_iclora_public" ]; then
  echo "skipping_remote_ready_materialization_for_lean_ltx_scope={scope}" >> out/corpus_matrix/live.log
else
  $PY -m tools.refresh_template_index --check
  validate_ready_set out/corpus_matrix/ready_workflows.tsv
fi
run_workflow_set out/corpus_matrix/ltx_workflows.tsv
fi
if grep -q '[^[:space:]]' out/corpus_matrix/wan_wrapper_workflows.tsv; then
git clone https://github.com/kijai/ComfyUI-WanVideoWrapper.git custom_nodes/ComfyUI-WanVideoWrapper
git clone https://github.com/kijai/ComfyUI-KJNodes.git custom_nodes/ComfyUI-KJNodes || true
git clone https://github.com/Kosinkadink/ComfyUI-VideoHelperSuite.git custom_nodes/ComfyUI-VideoHelperSuite || true
git clone https://github.com/LeonQ8/ComfyUI-Dynamic-Lora-Scheduler.git custom_nodes/ComfyUI-Dynamic-Lora-Scheduler || true
if [ "{scope}" != "wan_wrapper_basic" ] && [ "{scope}" != "wan_wrapper_5b" ]; then
git clone https://github.com/aining2022/ComfyUI_Swwan.git custom_nodes/ComfyUI_Swwan || true
git clone https://github.com/Fannovel16/comfyui_controlnet_aux.git custom_nodes/comfyui_controlnet_aux || true
git clone https://github.com/kijai/ComfyUI-DepthAnythingV2.git custom_nodes/ComfyUI-DepthAnythingV2 || true
git clone https://github.com/kijai/ComfyUI-Florence2.git custom_nodes/ComfyUI-Florence2 || true
git clone https://github.com/pythongosssss/ComfyUI-Custom-Scripts.git custom_nodes/ComfyUI-Custom-Scripts || true
git clone https://github.com/Kosinkadink/ComfyUI-AnimateDiff-Evolved.git custom_nodes/ComfyUI-AnimateDiff-Evolved || true
git clone https://github.com/kijai/ComfyUI-MelBandRoFormer.git custom_nodes/ComfyUI-MelBandRoFormer || true
git clone https://github.com/kijai/ComfyUI-segment-anything-2.git custom_nodes/ComfyUI-segment-anything-2 || true
fi
if [ -f custom_nodes/ComfyUI-WanVideoWrapper/latent_preview.py ]; then
"$PY" - <<'PY'
from pathlib import Path
import re

path = Path("custom_nodes/ComfyUI-WanVideoWrapper/latent_preview.py")
text = path.read_text(encoding="utf-8")
pattern = r"(?m)^([ \\t]*)message\\.write\\(struct\\.pack\\('16p', serv\\.last_node_id\\.encode\\('ascii'\\)\\)\\)"
replacement = "\\g<1>node_id = serv.last_node_id or '0'\\n\\g<1>message.write(struct.pack('16p', node_id.encode('ascii')))"
text = re.sub(pattern, replacement, text)
path.write_text(text, encoding="utf-8")
PY
fi
$PY -m pip install --upgrade 'pyparsing>=3.1' 'matplotlib>=3.8' onnx opencv-python-headless
if [ -f custom_nodes/ComfyUI-WanVideoWrapper/requirements.txt ]; then $PY -m pip install --no-deps -r custom_nodes/ComfyUI-WanVideoWrapper/requirements.txt || true; fi
if [ -f custom_nodes/ComfyUI-KJNodes/requirements.txt ]; then $PY -m pip install --no-deps -r custom_nodes/ComfyUI-KJNodes/requirements.txt || true; fi
if [ -f custom_nodes/ComfyUI-VideoHelperSuite/requirements.txt ]; then $PY -m pip install --no-deps -r custom_nodes/ComfyUI-VideoHelperSuite/requirements.txt || true; fi
if [ "{scope}" != "wan_wrapper_basic" ] && [ "{scope}" != "wan_wrapper_5b" ]; then
  for req in custom_nodes/*/requirements.txt; do [ -f "$req" ] && $PY -m pip install --no-deps -r "$req" || true; done
fi
{_legacy_or_registry_block("wan_wrapper")}
"$PY" - <<'PY'
from huggingface_hub import hf_hub_download
from pathlib import Path
import os
import shutil

def materialize_model(repo, filename, targets, min_size):
    path = Path(hf_hub_download(repo_id=repo, filename=filename)).resolve(strict=True)
    size = path.stat().st_size
    if size < min_size:
        raise RuntimeError(f"{{repo}}/{{filename}} resolved to {{path}} with only {{size}} bytes")
    for target in targets:
        target.parent.mkdir(parents=True, exist_ok=True)
        if target.exists() or target.is_symlink():
            target.unlink()
        try:
            os.link(path, target)
        except OSError:
            os.symlink(path, target)
        staged = target.resolve(strict=True)
        staged_size = staged.stat().st_size
        if staged_size < min_size:
            raise RuntimeError(f"{{target}} staged from {{path}} with only {{staged_size}} bytes")

downloads = [
    ("Kijai/WanVideo_comfy", "umt5-xxl-enc-bf16.safetensors", [
        Path("models/text_encoders/umt5-xxl-enc-bf16.safetensors"),
    ], 1_000_000_000),
    ("Kijai/WanVideo_comfy", "Wan2_1_VAE_bf16.safetensors", [
        Path("models/vae/wanvideo/Wan2_1_VAE_bf16.safetensors"),
    ], 100_000_000),
    ("Kijai/WanVideo_comfy", "Wan2_2_VAE_bf16.safetensors", [
        Path("models/vae/wanvideo/Wan2_2_VAE_bf16.safetensors"),
    ], 100_000_000),
    ("Kijai/WanVideo_comfy_fp8_scaled", "T2V/Wan2_1-T2V-14B_fp8_e4m3fn_scaled_KJ.safetensors", [
        Path("models/diffusion_models/WanVideo/fp8_scaled_kj/T2V/Wan2_1-T2V-14B_fp8_e4m3fn_scaled_KJ.safetensors"),
    ], 10_000_000_000),
    ("Kijai/WanVideo_comfy", "Wan2_1-I2V-14B-480P_fp8_e4m3fn.safetensors", [
        Path("models/diffusion_models/WanVideo/Wan2_1-I2V-14B-480P_fp8_e4m3fn.safetensors"),
    ], 10_000_000_000),
    ("Kijai/WanVideo_comfy", "Wan2_1-FLF2V-14B-720P_fp8_e4m3fn.safetensors", [
        Path("models/diffusion_models/WanVideo/Wan2_1-FLF2V-14B-720P_fp8_e4m3fn.safetensors"),
    ], 10_000_000_000),
    ("Kijai/WanVideo_comfy", "FastWan/Wan2_2-TI2V-5B-FastWanFullAttn_bf16.safetensors", [
        Path("models/diffusion_models/Wan2_2-TI2V-5B-FastWanFullAttn_bf16.safetensors"),
        Path("models/diffusion_models/WanVideo/Wan2_2-TI2V-5B-FastWanFullAttn_bf16.safetensors"),
    ], 5_000_000_000),
    ("Comfy-Org/Wan_2.2_ComfyUI_Repackaged", "split_files/diffusion_models/wan2.2_ti2v_5B_fp16.safetensors", [
        Path("models/diffusion_models/WanVideo/2_2/wan2.2_ti2v_5B_fp16.safetensors"),
    ], 5_000_000_000),
    ("Comfy-Org/Wan_2.1_ComfyUI_repackaged", "split_files/diffusion_models/wan2.1_t2v_1.3B_fp16.safetensors", [
        Path("models/diffusion_models/WanVideo/wan2.1_t2v_1.3B_fp16.safetensors"),
    ], 1_000_000_000),
    ("Comfy-Org/Wan_2.1_ComfyUI_repackaged", "split_files/clip_vision/clip_vision_h.safetensors", [
        Path("models/clip_vision/clip_vision_h.safetensors"),
    ], 100_000_000),
    ("Kijai/WanVideo_comfy", "Lightx2v/lightx2v_T2V_14B_cfg_step_distill_v2_lora_rank64_bf16.safetensors", [
        Path("models/loras/WanVideo/Lightx2v/lightx2v_T2V_14B_cfg_step_distill_v2_lora_rank64_bf16.safetensors"),
    ], 10_000_000),
    ("Kijai/WanVideo_comfy", "Lightx2v/lightx2v_I2V_14B_480p_cfg_step_distill_rank64_bf16.safetensors", [
        Path("models/loras/WanVideo/Lightx2v/lightx2v_I2V_14B_480p_cfg_step_distill_rank64_bf16.safetensors"),
    ], 10_000_000),
    ("Kijai/WanVideo_comfy", "Wan21_T2V_14B_lightx2v_cfg_step_distill_lora_rank32.safetensors", [
        Path("models/loras/Wan21_T2V_14B_lightx2v_cfg_step_distill_lora_rank32.safetensors"),
        Path("models/loras/WanVideo/Lightx2v/Wan21_T2V_14B_lightx2v_cfg_step_distill_lora_rank32.safetensors"),
    ], 10_000_000),
    ("spacepxl/Wan2.1-control-loras", "1.3b/tile/wan2.1-1.3b-control-lora-tile-v1.1_comfy.safetensors", [
        Path("models/loras/WanVid/wan2.1-1.3b-control-lora-tile-v1.1_comfy.safetensors"),
    ], 10_000_000),
    ("TheDenk/wan2.2-ti2v-5b-controlnet-depth-v1", "diffusion_pytorch_model.safetensors", [
        Path("models/controlnet/wan2.2-ti2v-5b-controlnet-depth-v1/diffusion_pytorch_model.safetensors"),
    ], 500_000_000),
    ("Kijai/WanVideo_comfy_GGUF", "InfiniteTalk/Wan2_1-InfiniteTalk_Single_Q4_K_M.gguf", [
        Path("models/diffusion_models/WanVideo/InfiniteTalk/InfiniteTalk/Wan2_1-InfiniteTalk_Single_Q4_K_M.gguf"),
    ], 1_000_000_000),
    ("city96/Wan2.1-I2V-14B-480P-gguf", "wan2.1-i2v-14b-480p-Q4_K_M.gguf", [
        Path("models/diffusion_models/WanVideo/wan2.1-i2v-14b-480p-Q4_K_M.gguf"),
    ], 5_000_000_000),
    ("Kijai/MelBandRoFormer_comfy", "MelBandRoformer_fp16.safetensors", [
        Path("models/diffusion_models/MelBandRoFormer/MelBandRoformer_fp16.safetensors"),
        Path("models/diffusion_models/MelBandRoformer/MelBandRoformer_fp16.safetensors"),
    ], 400_000_000),
]
for repo, filename, targets, min_size in downloads:
    materialize_model(repo, filename, targets, min_size)
PY
{_registry_staging_fallback("wan_wrapper")}
$PY -m vibecomfy.cli sources sync --official ready_templates/sources/official --external ready_templates/sources/custom_nodes --custom-nodes custom_nodes
$PY -m tools.refresh_template_index --check
validate_ready_set out/corpus_matrix/ready_workflows.tsv
run_workflow_set out/corpus_matrix/wan_wrapper_workflows.tsv
fi
echo "=== RESULTS ==="
cat out/corpus_matrix/results.tsv
echo "=== READY RESULTS ==="
cat out/corpus_matrix/ready_results.tsv
failures=$(awk -F '\\t' 'NR>1 && $3!="ok" {{c++}} END {{print c+0}}' out/corpus_matrix/results.tsv)
ready_failures=$(awk -F '\\t' 'NR>1 && $3!="ready_ok" {{c++}} END {{print c+0}}' out/corpus_matrix/ready_results.tsv)
echo "failures=$failures"
echo "ready_failures=$ready_failures"
find out/corpus_matrix output -maxdepth 4 -type f \\( -name '*.png' -o -name '*.webp' -o -name '*.mp4' -o -name '*.webm' -o -name '*.mp3' -o -name '*.glb' \\) -ls | sed -n '1,240p'
if [ "$failures" -ne 0 ] || [ "$ready_failures" -ne 0 ]; then
  exit 1
fi
exit 0
"""


def _load_hf_token() -> str:
    for key in ("HF_TOKEN", "HUGGINGFACE_HUB_TOKEN"):
        value = os.environ.get(key, "").strip()
        if value:
            return value
    for path in (Path.home() / ".cache/huggingface/token", Path.home() / ".huggingface/token"):
        try:
            value = path.read_text(encoding="utf-8").strip()
        except FileNotFoundError:
            continue
        if value:
            return value
    return ""


async def main() -> int:
    return await run_pod_detached(
        _remote_script(),
        name_prefix="vibecomfy-corpus",
        exclude=EXCLUDE_DIRS,
        upload_mode="tarball",
        timeout=28800,
        poll_interval=int(os.getenv("VIBECOMFY_RUNPOD_POLL_INTERVAL_SECONDS", "60")),
    )


if __name__ == "__main__":
    raise SystemExit(asyncio.run(main()))
