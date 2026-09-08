"""Live RunPod acceptance suite for VibeComfy.

Runs the full VibeComfy pipeline against a real RunPod GPU pod and asserts every
representation of a workflow can be loaded, converted, validated, and executed.
The smoke workflow is ``EmptyImage -> SaveImage`` (CPU-only, no model downloads),
so this proves the *plumbing* end-to-end — not actual diffusion. Pass
``--model-template`` (optionally with ``--model-phase``) to stage real models and
exercise a checkpoint after the no-model path.

What it proves (the six "representation proofs" in the summary)
--------------------------------------------------------------
direct API JSON queueing; JSON -> Python porting; embedded-runtime execution of
both the ready-template and the JSON-derived Python; and the same two runs against
an existing (managed) HTTP server. ~17 steps total; a green run writes
``out/corpus_matrix/acceptance_summary.json`` with ``status: "ok"``.

Flow
----
``_main_async`` builds a remote bash script (``_remote_script``) and hands it to
``runpod_runner.run_pod_detached``, which (via ``runpod_lifecycle``) provisions a
pod, uploads this repo as a tarball, runs the script detached, polls until exit,
downloads the ``out/`` and ``output/`` artifacts, and terminates the pod
(``terminate_after_exec=True`` — no manual teardown needed; RunPod bills by the
second, and a leaked pod is a real money leak).

On the pod, the script ``pip``-installs VibeComfy plus the AppMana-published
``comfyui`` package and ``comfy-script``. ComfyUI is intentionally consumed as
the pip ``comfy`` package
(not the legacy ``ComfyUI/server.py`` source tree), so a
``Could not locate ComfyUI root (no server.py + nodes.py found)`` notice at
startup is *expected* and does not block the suite. Steps run under ``set -e``;
the first failure aborts, and its reason is captured in ``results.tsv`` and the
step's ``out/corpus_matrix/logs/<id>.log``.

How to run
----------
Credentials live in the *sibling* ``runpod-lifecycle`` repo's ``.env``, not here.
``RunPodConfig.from_env()`` calls bare ``load_dotenv()`` (which searches upward
from the CWD), so from this repo it will NOT find them — and a shell ``source``
mangles that file's unquoted spaced values and multi-line inline SSH keys. Load
it in-process with python-dotenv, then run, e.g.::

    from dotenv import load_dotenv
    load_dotenv("../runpod-lifecycle/.env", override=True)
    import runpy, sys
    sys.argv = ["runpod_acceptance.py"]
    runpy.run_path("scripts/runpod_acceptance.py", run_name="__main__")

Capacity env vars (read by ``scripts/runpod_runner.py``; fan out across DCs to
avoid "no instances available" droughts — a single volume pins one datacenter)::

    VIBECOMFY_RUNPOD_GPU="NVIDIA GeForce RTX 4090,NVIDIA GeForce RTX 3090,NVIDIA A40,..."   # CSV
    VIBECOMFY_RUNPOD_STORAGE_VOLUMES="Peter,Training,EU-NO-1,EU-CZ-1,EUR-IS-1"               # CSV (multi-DC)
    VIBECOMFY_RUNPOD_STORAGE=Peter                                                           # primary volume

The detached runner does NOT retry on capacity. Wrap ``main()`` in a retry loop
that catches *only* ``runpod_lifecycle.errors.LaunchFailure`` — a real step
failure returns a non-zero exit code (not an exception) and must not be retried.

Flags
-----
``--model-template <id>``     ready-template id to run after the no-model path (e.g. ``image/z_image``).
``--model-phase <phase>``     model staging phase to run first (requires ``--model-template``).
``--timeout <sec>``           detached-run timeout (default 3600, env ``VIBECOMFY_RUNPOD_ACCEPTANCE_TIMEOUT_SECONDS``).
``--poll-interval <sec>``     poll cadence (default 30, env ``VIBECOMFY_RUNPOD_POLL_INTERVAL_SECONDS``).

Artifacts land in ``./artifacts/`` (``report.md``, ``out/corpus_matrix/``,
``output/``, ``out/runs/``).
"""

from __future__ import annotations

import argparse
import asyncio
import os
import shlex
import sys
import textwrap
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
if str(ROOT) not in sys.path:
    sys.path.insert(0, str(ROOT))

from scripts.runpod_runner import DEFAULT_UPLOAD_EXCLUDES, REMOTE_ROOT, run_pod_detached
from vibecomfy.commands.runpod_setup import COMFYUI_H3_PIP_SPEC


# external_workflows/ ships ~1 GiB of unrelated workflow JSON that the acceptance
# suite (snapshots + ready_templates/smoke) never reads; excluding it shrinks the
# upload tarball ~6x without affecting any step.
EXCLUDE_DIRS = set(DEFAULT_UPLOAD_EXCLUDES) | {"external_workflows"}


def _remote_script(*, model_template: str | None = None, model_phase: str | None = None) -> str:
    model_template_export = (
        f"export VIBECOMFY_ACCEPTANCE_MODEL_TEMPLATE={shlex.quote(model_template)}"
        if model_template
        else "unset VIBECOMFY_ACCEPTANCE_MODEL_TEMPLATE"
    )
    model_phase_export = (
        f"export VIBECOMFY_ACCEPTANCE_MODEL_PHASE={shlex.quote(model_phase)}"
        if model_phase
        else "unset VIBECOMFY_ACCEPTANCE_MODEL_PHASE"
    )
    script = r"""
set -euo pipefail
cd __REMOTE_ROOT__

export XDG_CACHE_HOME=/tmp/vibecomfy-cache
export UV_CACHE_DIR=/tmp/vibecomfy-cache/uv
export HF_HOME=/workspace/.cache/huggingface
export HF_HUB_DISABLE_XET=1
export PIP_CACHE_DIR=/workspace/.cache/pip
export LC_ALL=C.UTF-8
export LANG=C.UTF-8
export PYTORCH_CUDA_ALLOC_CONF=expandable_segments:True
__MODEL_TEMPLATE_EXPORT__
__MODEL_PHASE_EXPORT__

PY=python3
API_JSON=tests/snapshots/empty_image_red_smoke_required.api.json
SCRATCHPAD=out/scratchpads/acceptance_from_api_json.py
SERVER_ID=acceptance
SERVER_URL=http://127.0.0.1:8188
RESULTS=out/corpus_matrix/results.tsv
LIVE_LOG=out/corpus_matrix/live.log
mkdir -p out/corpus_matrix/logs out/scratchpads out/acceptance output input "$XDG_CACHE_HOME" "$UV_CACHE_DIR" "$HF_HOME" "$PIP_CACHE_DIR"
printf 'id\tkind\tstatus\tseconds\tmedia_files\tbytes\tartifact\tfailure\n' > "$RESULTS"
: > "$LIVE_LOG"

log() {
  printf '%s %s\n' "$(date -u +%Y-%m-%dT%H:%M:%SZ)" "$*" | tee -a "$LIVE_LOG"
}

count_media_files() {
  find output out/runs -type f \( -name '*.png' -o -name '*.webp' -o -name '*.mp4' -o -name '*.webm' -o -name '*.mp3' -o -name '*.glb' \) 2>/dev/null | wc -l | tr -d ' ' || true
}

sum_media_bytes() {
  find output out/runs -type f \( -name '*.png' -o -name '*.webp' -o -name '*.mp4' -o -name '*.webm' -o -name '*.mp3' -o -name '*.glb' \) -exec stat -c '%s' {} + 2>/dev/null | awk '{s+=$1} END {print s+0}' || true
}

clean_failure() {
  local log_path="$1"
  tail -80 "$log_path" 2>/dev/null | tr '\t\n' '  ' | tr -cd '\11\12\15\40-\176' | cut -c1-900
}

record_result() {
  local id="$1"
  local kind="$2"
  local status="$3"
  local seconds="$4"
  local artifact="$5"
  local failure="$6"
  local media_files
  local bytes
  media_files=$(count_media_files)
  bytes=$(sum_media_bytes)
  printf '%s\t%s\t%s\t%s\t%s\t%s\t%s\t%s\n' "$id" "$kind" "$status" "$seconds" "$media_files" "$bytes" "$artifact" "$failure" >> "$RESULTS"
}

run_step() {
  local id="$1"
  local kind="$2"
  local artifact="$3"
  shift 3
  local log_path="out/corpus_matrix/logs/${id}.log"
  local start
  local status
  local failure
  start=$(date +%s)
  log "START $id ($kind): $*"
  set +e
  "$@" >"$log_path" 2>&1
  local code=$?
  set -e
  local seconds=$(( $(date +%s) - start ))
  if [ "$code" -eq 0 ]; then
    status=ok
    failure=
    log "PASS $id in ${seconds}s"
  else
    status=failed
    failure=$(clean_failure "$log_path")
    log "FAIL $id in ${seconds}s: $failure"
  fi
  record_result "$id" "$kind" "$status" "$seconds" "$artifact" "$failure"
  return "$code"
}

finish() {
  set +e
  "$PY" -m vibecomfy.cli session stop "$SERVER_ID" >> out/corpus_matrix/logs/session_stop.log 2>&1
}
trap finish EXIT

log "installing package and ComfyUI runtime dependencies"
"$PY" -m pip install --upgrade pip wheel setuptools
"$PY" -m pip install -e '.[dev]'
"$PY" -m pip install --extra-index-url https://nodes.appmana.com/simple/ '__COMFYUI_H3_PIP_SPEC__' 'comfy-script[default]'

run_step runtime_doctor setup out/corpus_matrix/runtime_doctor.json "$PY" -m vibecomfy.cli runtime doctor --json
cp out/corpus_matrix/logs/runtime_doctor.log out/corpus_matrix/runtime_doctor.json
run_step config_show setup out/corpus_matrix/config_show.json "$PY" -m vibecomfy.cli config show --json
cp out/corpus_matrix/logs/config_show.log out/corpus_matrix/config_show.json
run_step runtime_smoke_managed setup out/corpus_matrix/runtime_smoke_managed.json "$PY" -m vibecomfy.cli runtime smoke --mode managed
cp out/corpus_matrix/logs/runtime_smoke_managed.log out/corpus_matrix/runtime_smoke_managed.json

run_step nodes_install_plan dependency out/corpus_matrix/nodes_install_plan.json "$PY" -m vibecomfy.cli nodes install-plan "$API_JSON" --json
cp out/corpus_matrix/logs/nodes_install_plan.log out/corpus_matrix/nodes_install_plan.json
run_step fetch_dry_run dependency out/corpus_matrix/fetch_dry_run.log "$PY" -m vibecomfy.cli fetch "$API_JSON" --dry-run
run_step models_stage_dry_run dependency out/corpus_matrix/models_stage_core_dry_run.log "$PY" -m vibecomfy.cli models stage --select-phase core --dry-run

run_step api_direct_queue api_json out/corpus_matrix/api_direct_queue.json "$PY" - <<'PY'
import asyncio
import json
import time
import uuid
from pathlib import Path

from vibecomfy.runtime.client import ComfyClient
from vibecomfy.runtime.execution import normalize_prompt_id
from vibecomfy.runtime.server import comfy_server
from vibecomfy.runtime.session import (
    SessionConfig,
    _collect_output_paths,
    _outputs_from_server_history,
    _wait_for_server_history,
)

async def main() -> None:
    api_path = Path("tests/snapshots/empty_image_red_smoke_required.api.json")
    api_dict = json.loads(api_path.read_text(encoding="utf-8"))
    run_id = f"api-{int(time.time())}-{uuid.uuid4().hex[:8]}"
    run_dir = Path("out/runs") / run_id
    run_dir.mkdir(parents=True, exist_ok=False)
    log_path = run_dir / "comfy.log"
    config = SessionConfig()
    async with comfy_server(log_path=log_path, config=config) as server_url:
        client = ComfyClient(server_url)
        queued = await client.queue_prompt(api_dict)
        prompt_id = normalize_prompt_id(queued)
        history = await _wait_for_server_history(server_url, prompt_id, config=config)
        comfy_outputs = _outputs_from_server_history(history, prompt_id)
        outputs = _collect_output_paths(comfy_outputs)
    payload = {
        "mode": "direct_api_json",
        "api_path": str(api_path),
        "run_id": run_id,
        "prompt_id": prompt_id,
        "queued": queued,
        "outputs": outputs,
        "metadata_path": str(run_dir / "api_queue_result.json"),
        "log_path": str(log_path),
    }
    (run_dir / "api_queue_result.json").write_text(json.dumps(payload, indent=2, sort_keys=True), encoding="utf-8")
    Path("out/corpus_matrix/api_direct_queue.json").write_text(json.dumps(payload, indent=2, sort_keys=True), encoding="utf-8")
    print(json.dumps(payload, indent=2, sort_keys=True))
    if not outputs:
        raise RuntimeError("direct API queue produced no output files")

asyncio.run(main())
PY

run_step port_check_api_json json_intake out/corpus_matrix/port_check_api_json.json "$PY" -m vibecomfy.cli port check "$API_JSON" --json
cp out/corpus_matrix/logs/port_check_api_json.log out/corpus_matrix/port_check_api_json.json
run_step port_convert_api_json json_to_python "$SCRATCHPAD" "$PY" -m vibecomfy.cli port convert "$API_JSON" --out "$SCRATCHPAD" --json
cp out/corpus_matrix/logs/port_convert_api_json.log out/corpus_matrix/port_convert_api_json.json
run_step validate_converted_python validation out/corpus_matrix/validate_converted_python.json "$PY" -m vibecomfy.cli validate "$SCRATCHPAD" --json
cp out/corpus_matrix/logs/validate_converted_python.log out/corpus_matrix/validate_converted_python.json
run_step doctor_converted_python validation out/corpus_matrix/doctor_converted_python.json "$PY" -m vibecomfy.cli doctor "$SCRATCHPAD" --json
cp out/corpus_matrix/logs/doctor_converted_python.log out/corpus_matrix/doctor_converted_python.json

run_step run_ready_python_embedded python_ready out/runs "$PY" -m vibecomfy.cli run smoke/empty_image_red --ready --runtime embedded --backend api --no-ensure-models
run_step run_converted_json_embedded json_python out/runs "$PY" -m vibecomfy.cli run "$SCRATCHPAD" --runtime embedded --backend api --no-ensure-models

run_step session_start server out/sessions/"$SERVER_ID" "$PY" -m vibecomfy.cli session start --id "$SERVER_ID" --port 8188 --ready-timeout-sec 300
run_step runtime_smoke_external server out/corpus_matrix/runtime_smoke_external.json "$PY" -m vibecomfy.cli runtime smoke --mode external --server-url "$SERVER_URL"
cp out/corpus_matrix/logs/runtime_smoke_external.log out/corpus_matrix/runtime_smoke_external.json
run_step run_ready_python_existing_server python_ready_server out/runs "$PY" -m vibecomfy.cli run smoke/empty_image_red --ready --runtime server --server-url "$SERVER_URL" --backend api --no-ensure-models
run_step run_converted_json_existing_server json_python_server out/runs "$PY" -m vibecomfy.cli run "$SCRATCHPAD" --runtime server --server-url "$SERVER_URL" --backend api --no-ensure-models

if [ -n "${VIBECOMFY_ACCEPTANCE_MODEL_TEMPLATE:-}" ]; then
  if [ -n "${VIBECOMFY_ACCEPTANCE_MODEL_PHASE:-}" ]; then
    run_step model_stage model out/corpus_matrix/model_stage.log "$PY" -m vibecomfy.cli models stage --select-phase "$VIBECOMFY_ACCEPTANCE_MODEL_PHASE"
  fi
  run_step run_model_template model out/runs "$PY" -m vibecomfy.cli run "$VIBECOMFY_ACCEPTANCE_MODEL_TEMPLATE" --ready --runtime embedded --backend api
fi

"$PY" - <<'PY'
import csv
import json
from pathlib import Path

results_path = Path("out/corpus_matrix/results.tsv")
rows = list(csv.DictReader(results_path.open(encoding="utf-8"), delimiter="\t"))
summary = {
    "status": "ok" if all(row["status"] == "ok" for row in rows) else "failed",
    "steps": len(rows),
    "failures": [row for row in rows if row["status"] != "ok"],
    "representations": {
        "direct_api_json": any(row["id"] == "api_direct_queue" and row["status"] == "ok" for row in rows),
        "raw_json_port_convert": any(row["id"] == "port_convert_api_json" and row["status"] == "ok" for row in rows),
        "python_ready_embedded": any(row["id"] == "run_ready_python_embedded" and row["status"] == "ok" for row in rows),
        "json_derived_python_embedded": any(row["id"] == "run_converted_json_embedded" and row["status"] == "ok" for row in rows),
        "existing_server_ready": any(row["id"] == "run_ready_python_existing_server" and row["status"] == "ok" for row in rows),
        "existing_server_json_derived_python": any(row["id"] == "run_converted_json_existing_server" and row["status"] == "ok" for row in rows),
    },
}
Path("out/corpus_matrix/acceptance_summary.json").write_text(json.dumps(summary, indent=2, sort_keys=True), encoding="utf-8")
print("=== ACCEPTANCE SUMMARY ===")
print(json.dumps(summary, indent=2, sort_keys=True))
if summary["status"] != "ok":
    raise SystemExit(1)
missing = [key for key, value in summary["representations"].items() if not value]
if missing:
    raise SystemExit(f"missing representation proofs: {', '.join(missing)}")
PY

echo "=== RESULTS ==="
cat "$RESULTS"
"""
    return (
        textwrap.dedent(script)
        .replace("__REMOTE_ROOT__", REMOTE_ROOT)
        .replace("__MODEL_TEMPLATE_EXPORT__", model_template_export)
        .replace("__MODEL_PHASE_EXPORT__", model_phase_export)
        .replace("__COMFYUI_H3_PIP_SPEC__", COMFYUI_H3_PIP_SPEC)
    )


async def _main_async(args: argparse.Namespace) -> int:
    return await run_pod_detached(
        _remote_script(model_template=args.model_template, model_phase=args.model_phase),
        name_prefix="vibecomfy-acceptance",
        exclude=EXCLUDE_DIRS,
        upload_mode="tarball",
        timeout=args.timeout,
        poll_interval=args.poll_interval,
    )


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(
        description=(
            "Run the VibeComfy live RunPod acceptance suite: setup, direct API JSON "
            "queueing, JSON-to-Python conversion, embedded runtime, existing-server "
            "runtime, and artifact collection."
        )
    )
    parser.add_argument(
        "--model-template",
        help=(
            "Optional ready-template id to run after the no-model acceptance path, "
            "for example image/z_image."
        ),
    )
    parser.add_argument(
        "--model-phase",
        choices=["core", "gguf", "ltx", "wan_wrapper", "qwen_image"],
        help="Optional model staging phase to run before --model-template.",
    )
    parser.add_argument(
        "--timeout",
        type=int,
        default=int(os.getenv("VIBECOMFY_RUNPOD_ACCEPTANCE_TIMEOUT_SECONDS", "3600")),
    )
    parser.add_argument(
        "--poll-interval",
        type=int,
        default=int(os.getenv("VIBECOMFY_RUNPOD_POLL_INTERVAL_SECONDS", "30")),
    )
    args = parser.parse_args(argv)
    if args.model_phase and not args.model_template:
        parser.error("--model-phase requires --model-template")
    return asyncio.run(_main_async(args))


if __name__ == "__main__":
    raise SystemExit(main())
