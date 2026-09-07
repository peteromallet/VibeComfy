# RunPod Validation

Run the live validation from the VibeComfy repo:

```bash
python scripts/runpod_validate.py
```

The historical `runpod_acceptance.py` entry point is now a fail-closed placeholder and does not launch a pod. Do not use it as evidence of end-to-end behavior.

That smoke launches a pod, uploads the checkout, installs VibeComfy and ComfyUI,
starts the managed runtime, executes the committed Python ready-template smoke,
checks its generated artifact, and terminates the pod. It is a launch/runtime
smoke, not a proof of direct API queueing, raw-JSON conversion, server-mode
execution, or model quality.

The retired acceptance placeholder does not support model-backed proof. For model-family coverage, use the live matrix after the smoke is green:

```bash
VIBECOMFY_MATRIX_SCOPE=image_core python scripts/runpod_corpus_matrix.py
```

Artifacts are downloaded under `out/runpod_artifacts/<timestamp>/`, including
`out/corpus_matrix/results.tsv`,
`out/runs/**/metadata.json`, output media, and logs.

Install the RunPod support extra from the VibeComfy repo:

```bash
pip install -e '.[runpod-local]'
```

That extra installs the tagged `runpod-lifecycle` release from GitHub
automatically. Set
`VIBECOMFY_RUNPOD_LIFECYCLE_ROOT` only when you want to use a local checkout
instead.

Environment:

- `VIBECOMFY_RUNPOD_STORAGE`, default `Peter`
- `VIBECOMFY_RUNPOD_GPU`, default `NVIDIA GeForce RTX 4090`
- `VIBECOMFY_RUNPOD_MAX_RUNTIME_SECONDS`, default `7200` for the cheap smoke and `21600` for the proper media matrix
- `VIBECOMFY_ATTENTION_PROFILE`, default `portable`. `portable` rewrites WanVideoWrapper `sageattn` workflow inputs to `sdpa` and does not require SageAttention. `sage` installs and verifies SageAttention before allowing `sageattn` workflows.
- `VIBECOMFY_RUNPOD_LIFECYCLE_ROOT`, optional local `runpod-lifecycle` checkout override
- RunPod credentials loaded from the `runpod-lifecycle` `.env`

What the script does:

- Launches a RunPod pod with the configured storage.
- Waits for SSH and checks `nvidia-smi -L`.
- Uploads the local VibeComfy repo, excluding `.venv`, `.git`, `out`, `output`, `vendor`, `.desloppify`, `.megaplan`, and run logs.
- Installs VibeComfy, HiddenSwitch ComfyUI, and ComfyScript.
- Runs tests.
- Indexes official templates, external examples, custom-node examples, and runtime nodes.
- Starts managed runtime smoke.
- Executes the Python ready template `ready_templates/smoke/empty_image_red.py` through `VibeWorkflow.compile("graphbuilder")`.
- Verifies generated PNG files exist.
- Terminates the launched pod in `finally`.

The cheap smoke exists only to prove launch, upload, runtime startup, Python ready-template execution, artifact download, and termination. Production validation should execute model-backed Python ready templates from `ready_templates/`, not raw JSON fixtures.

The retired `runpod_acceptance.py` placeholder does not establish an end-to-end
result. Use `runpod_validate.py` for the cheapest live launch/runtime sanity
check, then `runpod_corpus_matrix.py` for broad model-family and template
coverage. Both paths require network access, credentials, and GPU capacity.

The script has local signal handling, explicit `finally` termination, and a max-runtime watchdog. RunPod's current pod docs expose explicit stop/delete calls and a local scheduled stop pattern; network-volume pods should be terminated rather than stopped, so these scripts terminate the launched pod id.

Cleanup note: do not depend on `runpodctl` inside the launched pod for cleanup. It may not have local RunPod credentials. The launcher or local `runpod-lifecycle` CLI/API should terminate the pod id that was launched.

## Proper Media Matrix

For final validation, use the model matrix path rather than only the cheap smoke:

```bash
python scripts/runpod_model_matrix.py
```

The proper matrix should launch a fresh RTX 4090 pod on the configured storage, upload the current checkout, install VibeComfy and HiddenSwitch ComfyUI, sync official workflow templates and custom-node examples, run tests, execute each selected workflow through baseline `comfyui run-workflow`, convert the same workflow to a VibeComfy scratchpad, run that scratchpad through embedded Comfy, record outputs and metadata, and terminate the pod in `finally`.

The validation corpus should be official-template heavy:

- Five official model-backed image workflows: `default`, `sdxlturbo_example`, `sdxl_simple_example`, `flux_schnell`, and `sdxl_refiner_prompt_example`.
- One official Wan model-backed video workflow: `text_to_video_wan`.
- One external/custom-node image workflow using `kijai/ComfyUI-KJNodes`.
- One utility video workflow using `SaveWEBM`.

## SageAttention Profile

Fresh RunPod `runpod/pytorch:2.4.0-py3.11-cuda12.4.1-devel-ubuntu22.04` pods do not include SageAttention. Keep the default validation path portable:

```bash
VIBECOMFY_ATTENTION_PROFILE=portable python scripts/runpod_corpus_matrix.py
```

Use the optimized profile only when the pod should compile SageAttention and run workflows that explicitly request `attention_mode=sageattn`:

```bash
VIBECOMFY_ATTENTION_PROFILE=sage python scripts/runpod_corpus_matrix.py
```

The RunPod install attempt is:

```bash
git clone --depth 1 https://github.com/thu-ml/SageAttention.git /tmp/sageattention
python3 -m pip install --no-build-isolation /tmp/sageattention
python3 - <<'PY'
import sageattention
if not callable(getattr(sageattention, "sageattn", None)):
    raise RuntimeError("sageattention import succeeded but sageattn is missing")
print("sageattention verified")
PY
```

Last verified live on RunPod pod `4pz5727nh80qe2`:

- Source sync: `official=473 external=53 nodes=1202`.
- Local tests on pod: `5 passed`.
- Official images produced PNGs through both baseline Comfy and VibeComfy.
- Official Wan `text_to_video_wan` produced `ComfyUI_00001_.mp4` through both baseline Comfy and VibeComfy.
- VibeComfy Wan metadata recorded `runtime=embedded`, prompt id `85c548f0-ee87-4905-9a98-4628a04e8e1c`, and workflow hash `7bf088cbb87e47258ce39ef011ce0f1d6878c082d403321b9ada90ea05bd1c26`.
- The launched pod `4pz5727nh80qe2` was terminated after validation.

Known caveats:

- `flux_fill_inpaint_example` currently fails before VibeComfy if the attached storage lacks authorized access to gated Hugging Face model `black-forest-labs/FLUX.1-Fill-dev/flux1-fill-dev.safetensors`.
- Extra LTX video candidates may fail because of disk space or missing model files. They are useful probes, but the required model-backed video proof is the official Wan `text_to_video_wan` pass.
- Family-specific workflows may reject universal CLI overrides. For example, Qwen Image 2512's step/cfg values are selected through primitive nodes and `ComfySwitchNode`; the matrix should patch the workflow and then avoid passing `--steps` to VibeComfy unless a registered sampler step target exists.
- Keep local artifact-summary commands portable. Linux pod commands may use GNU `find -printf`, but macOS artifact pulls should use portable alternatives.
