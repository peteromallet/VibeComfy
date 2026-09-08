from __future__ import annotations

import asyncio

from scripts.runpod_runner import REMOTE_ROOT, run_pod
from vibecomfy.commands.runpod_setup import COMFYUI_H3_PIP_SPEC

EXCLUDE_DIRS = {".git", ".venv", "__pycache__", ".pytest_cache", "out/runs", "output"}

OFFICIAL_CANDIDATES = [
    "ready_templates/sources/official/image/z_image.json",
    "ready_templates/sources/official/image/flux2_klein_4b_t2i.json",
    "ready_templates/sources/official/image/flux2_klein_9b_t2i.json",
    "ready_templates/sources/official/edit/qwen_image_edit.json",
    "ready_templates/sources/official/edit/flux2_klein_4b_image_edit_base.json",
    "ready_templates/sources/official/edit/flux2_klein_4b_image_edit_distilled.json",
    "ready_templates/sources/official/edit/flux2_klein_9b_image_edit_base.json",
    "ready_templates/sources/official/edit/flux2_klein_9b_image_edit_distilled.json",
    "ready_templates/sources/official/video/wan_t2v.json",
    "ready_templates/sources/official/video/wan_i2v.json",
    "ready_templates/sources/official/video/ltx2_3_t2v.json",
    "ready_templates/sources/official/video/ltx2_3_i2v.json",
]

EXTERNAL_CANDIDATES = [
    "tests/smoke_fixtures/custom_kjnodes_label.json",
    "tests/smoke_fixtures/generated_webm_smoke.json",
    "custom_nodes/ComfyUI-WanVideoWrapper/example_workflows/wanvideo_2_1_14B_T2V_example_03.json",
    "custom_nodes/ComfyUI-WanVideoWrapper/example_workflows/wanvideo_2_2_5B_T2V_controlnet_example.json",
]


def _remote_script() -> str:
    candidates = " ".join(OFFICIAL_CANDIDATES)
    external = " ".join(EXTERNAL_CANDIDATES)
    return f"""
set -u
cd {REMOTE_ROOT}
python3 -m pip install -e '.[dev]'
python3 -m pip install --extra-index-url https://nodes.appmana.com/simple/ {COMFYUI_H3_PIP_SPEC!r} 'comfy-script[default]'
python3 -m pytest -q tests
rm -rf out output input vendor/workflow_templates custom_nodes
git clone --depth 1 https://github.com/Comfy-Org/workflow_templates.git vendor/workflow_templates
mkdir -p custom_nodes
git clone https://github.com/kijai/ComfyUI-KJNodes.git custom_nodes/ComfyUI-KJNodes
git -C custom_nodes/ComfyUI-KJNodes checkout b7646ad70a7daa7aeb919ca542274758d26ba2df
git clone https://github.com/kijai/ComfyUI-WanVideoWrapper.git custom_nodes/ComfyUI-WanVideoWrapper
git -C custom_nodes/ComfyUI-WanVideoWrapper checkout df8f3e49daaad117cf3090cc916c83f3d001494c
if [ -f custom_nodes/ComfyUI-KJNodes/requirements.txt ]; then python3 -m pip install --no-deps -r custom_nodes/ComfyUI-KJNodes/requirements.txt || true; fi
python3 -m vibecomfy.cli sources sync --official vendor/workflow_templates/templates --external examples --custom-nodes custom_nodes
mkdir -p input out/model_matrix/comfyui out/model_matrix/vibecomfy
cp -a vendor/workflow_templates/input/. input/ 2>/dev/null || true
success=0
official_success=0
external_success=0
wan_success=0
printf 'source\tid\tstatus\tbaseline_seconds\tconvert_seconds\tvibecomfy_seconds\tmedia_files\tbytes\tfailure\n' > out/model_matrix/results.tsv
run_case() {{
  source="$1"
  wf="$2"
  id=$(basename "$wf" .json)
  echo "=== $source $id ==="
  mkdir -p "out/model_matrix/comfyui/$id"
  start=$(date +%s)
  baseline_log="out/model_matrix/${{id}}.baseline.log"
  if timeout 1800 comfyui run-workflow "$wf" --all --cwd . --input-directory input --output-directory "out/model_matrix/comfyui/$id" --steps 1 --seed 123 --prompt "a compact red cube on a neutral background" --disable-progress --novram >"$baseline_log" 2>&1; then
    baseline_seconds=$(( $(date +%s) - start ))
  else
    baseline_seconds=$(( $(date +%s) - start ))
    failure=$(tail -40 "$baseline_log" | tr '\\t\\n' '  ' | cut -c1-600)
    echo -e "$source\\t$id\\tbaseline_failed\\t$baseline_seconds\\t0\\t0\\t0\\t0\\t$failure" >> out/model_matrix/results.tsv
    return 1
  fi

  start=$(date +%s)
  convert_log="out/model_matrix/${{id}}.convert.log"
  if python3 -m vibecomfy.cli convert "$wf" --out "out/scratchpads/$id.py" >"$convert_log" 2>&1; then
    convert_seconds=$(( $(date +%s) - start ))
  else
    convert_seconds=$(( $(date +%s) - start ))
    failure=$(tail -40 "$convert_log" | tr '\\t\\n' '  ' | cut -c1-600)
    echo -e "$source\\t$id\\tconvert_failed\\t$baseline_seconds\\t$convert_seconds\\t0\\t0\\t0\\t$failure" >> out/model_matrix/results.tsv
    return 1
  fi

  start=$(date +%s)
  vibe_log="out/model_matrix/${{id}}.vibecomfy.log"
  if timeout 1800 python3 -m vibecomfy.cli run "out/scratchpads/$id.py" --runtime embedded --backend api --steps 1 --seed 123 --prompt "a compact red cube on a neutral background" >"$vibe_log" 2>&1; then
    vibecomfy_seconds=$(( $(date +%s) - start ))
  else
    vibecomfy_seconds=$(( $(date +%s) - start ))
    failure=$(tail -40 "$vibe_log" | tr '\\t\\n' '  ' | cut -c1-600)
    echo -e "$source\\t$id\\tvibecomfy_failed\\t$baseline_seconds\\t$convert_seconds\\t$vibecomfy_seconds\\t0\\t0\\t$failure" >> out/model_matrix/results.tsv
    return 1
  fi

  media_files=$(find "out/model_matrix/comfyui/$id" output -type f \\( -name '*.png' -o -name '*.webp' -o -name '*.mp4' -o -name '*.webm' -o -name '*.mp3' -o -name '*.glb' \\) | wc -l | tr -d ' ')
  bytes=$(find "out/model_matrix/comfyui/$id" output -type f \\( -name '*.png' -o -name '*.webp' -o -name '*.mp4' -o -name '*.webm' -o -name '*.mp3' -o -name '*.glb' \\) -exec stat -c '%s' {{}} + 2>/dev/null | awk '{{s+=$1}} END {{print s+0}}')
  echo -e "$source\\t$id\\tok\\t$baseline_seconds\\t$convert_seconds\\t$vibecomfy_seconds\\t$media_files\\t$bytes\\t" >> out/model_matrix/results.tsv
  return 0
}}
for wf in {candidates}; do
  if run_case official "$wf"; then
    success=$((success+1))
    official_success=$((official_success+1))
    case "$wf" in
      *text_to_video_wan.json) wan_success=1 ;;
    esac
  fi
  if [ "$official_success" -ge 6 ] && [ "$wan_success" -ge 1 ]; then
    break
  fi
done
for wf in {external}; do
  if run_case external "$wf"; then
    success=$((success+1))
    external_success=$((external_success+1))
  fi
  if [ "$external_success" -ge 1 ]; then
    break
  fi
done
echo "=== RESULTS ==="
cat out/model_matrix/results.tsv
echo "official_success=$official_success"
echo "external_success=$external_success"
echo "wan_success=$wan_success"
echo "total_success=$success"
find out/model_matrix output -maxdepth 3 -type f \\( -name '*.png' -o -name '*.webp' -o -name '*.mp4' -o -name '*.webm' -o -name '*.mp3' -o -name '*.glb' \\) -ls | sed -n '1,200p'
test "$official_success" -ge 6
test "$wan_success" -ge 1
test "$external_success" -ge 1
"""


async def main() -> int:
    return await run_pod(_remote_script(), name_prefix="vibecomfy-model-matrix", exclude=EXCLUDE_DIRS, timeout=14400)


if __name__ == "__main__":
    raise SystemExit(asyncio.run(main()))
