from __future__ import annotations

import asyncio
import os

from scripts.runpod_runner import DEFAULT_UPLOAD_EXCLUDES, REMOTE_ROOT, run_pod_detached

EXCLUDE_DIRS = set(DEFAULT_UPLOAD_EXCLUDES)

REMOTE_SCRIPT = f"""
set -euo pipefail
cd {REMOTE_ROOT}
mkdir -p out/corpus_matrix output
python3 -m pip install -e '.[dev]'
python3 -m pip install 'comfyui@git+https://github.com/peteromallet/ComfyUI.git@fix/latentupscale-model-mmap-residency' 'comfy-script[default]'
python3 -m vibecomfy.cli runtime doctor
python3 -m vibecomfy.cli runtime smoke --mode managed
printf 'id\tstatus\tseconds\tmedia_files\tbytes\n' > out/corpus_matrix/results.tsv
run_smoke() {{
  id="$1"
  template="$2"
  start=$(date +%s)
  before=$(find output -type f 2>/dev/null | sort || true)
  python3 -m vibecomfy.cli run "$template" --ready --runtime embedded --backend graphbuilder
  seconds=$(( $(date +%s) - start ))
  after=$(find output -type f 2>/dev/null | sort || true)
  media_files=$(comm -13 <(printf '%s\n' "$before") <(printf '%s\n' "$after") | awk '/\\.(png|webp|mp4|webm|mp3|glb)$/ {{c++}} END {{print c+0}}')
  bytes=$(find output -type f \\( -name '*.png' -o -name '*.webp' -o -name '*.mp4' -o -name '*.webm' -o -name '*.mp3' -o -name '*.glb' \\) -exec stat -c '%s' {{}} + 2>/dev/null | awk '{{s+=$1}} END {{print s+0}}')
  printf '%s\tok\t%s\t%s\t%s\n' "$id" "$seconds" "$media_files" "$bytes" >> out/corpus_matrix/results.tsv
}}
run_smoke ready_template_empty_image_red smoke/empty_image_red
echo "=== RESULTS ==="
cat out/corpus_matrix/results.tsv
ls -lh output/vibecomfy_ready_smoke_*_*.png
"""


async def main() -> int:
    return await run_pod_detached(
        REMOTE_SCRIPT,
        name_prefix="vibecomfy",
        exclude=EXCLUDE_DIRS,
        upload_mode="tarball",
        timeout=900,
        poll_interval=int(os.getenv("VIBECOMFY_RUNPOD_POLL_INTERVAL_SECONDS", "30")),
    )


if __name__ == "__main__":
    raise SystemExit(asyncio.run(main()))
