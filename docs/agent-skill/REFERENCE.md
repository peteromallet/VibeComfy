# VibeComfy Agent Reference

This is the dense reference behind the `vibecomfy` umbrella skill. Do not start here for ordinary work; use it when the focused skills need exact API names, command surfaces, or package constraints.

## Public Import Surface

The authoritative source for import claims is `docs/api/m6-public-api.md`. Use `VibeWorkflow.compile("api")` to export a workflow to the ComfyUI API JSON shape accepted by runtime execution.

Public loaders and helpers:

| Name | What it does |
|---|---|
| `load_bundle(path_or_id)` | Canonical bundle loader for ready ids and Python candidates; preserves workflow identity and bundle metadata. |
| `load_workflow_any(path_or_id)` | Compatibility loader for ready ids, scratchpad paths, JSON files, and indexed references; raw JSON is import input, not an execution instruction. |
| `workflow_from_ready(id)` | Loads a ready template by id, such as `image/z_image`. |
| `workflow_from_id(id)` | Loads any workflow id, checking ready templates before the indexed corpus. |
| `workflow_from_file(path)` | Loads a JSON workflow from a path. |
| `load_workflow_json(path)` | Low-level JSON read/validate only, no normalization. |
| `ready_template_ids` | Lists ready template ids. |

Compatibility aliases:

- `workflow_from_template` -> `workflow_from_id`
- `load_template` -> `load_workflow_json`

Other public imports:

- Runtime helpers: `run`, `run_sync`, `run_embedded`, `run_embedded_sync`
- Ops namespaces: `image`, `video`
- Core IR types: `VibeWorkflow`, `VibeNode`, `VibeEdge`, `VibeInput`, `VibeOutput`, `WorkflowRequirements`, `WorkflowSource`, `ValidationIssue`, `ValidationReport`
- Handles: `Handle`
- Layer-2 namespaces: `blocks`, `patches`, `router`
- Artifact result types: `Artifact`, `Image`, `Video`, `Audio`, `Latent`, `Mask`
- Plugin hook: `ensure_plugins_loaded`

## Two Layers

**Layer 1: `VibeWorkflow` IR.** Raw graph editing: nodes, edges, widgets, handles, public inputs, outputs, requirements, and `compile("api")`.

**Layer 2: flows that operate on workflows.**

| Flow | Lives in | Use when | Returns |
|---|---|---|---|
| Direct IR edits / setters | `VibeWorkflow` methods | Raw graph edits: `set_prompt`, `set_seed`, `set_steps`, `add_node`, `connect`, `disconnect`, `replace_edge`, `register_input`, `finalize_metadata`. | `VibeWorkflow` |
| Patches | `vibecomfy/patches/*.py` | Decorate an existing graph: tweak a widget, splice a node, swap a class. | Mutated `VibeWorkflow` |
| Blocks | `vibecomfy/blocks/*.py` | Extend a graph and produce typed handles. | `Handles` |
| Ops | `vibecomfy/ops/{image,video}.py` | Lazy one-call user verbs such as `image.t2i(...)`, `video.t2v(...)`, `video.i2v(...)`. | `Artifact` |
| Recipes | local `recipes/*.py` | User-specific composition, control flow, or chaining. | Usually `VibeWorkflow` |

Rule of thumb:

- Changes handles -> block or new ready workflow.
- Decorates existing handles -> patch or recipe.
- User-specific composition -> recipe.
- Durable package starting point -> ready template.

## Command Catalog

Discovery:

```bash
vibecomfy sources sync
vibecomfy workflows list --ready
vibecomfy workflows list
vibecomfy search wan --task i2v
vibecomfy nodes list
vibecomfy nodes spec KSampler
vibecomfy inspect image/z_image
vibecomfy analyze info <workflow>
```

Load/fork/convert:

```bash
vibecomfy copy-to-recipe <ready_id> --out recipes/<name>.py
vibecomfy port check <workflow.json> --json
vibecomfy nodes reconcile --workflow <workflow.json> --json
vibecomfy port convert <workflow.json> --out out/scratchpads/<name>.py --json
```

Validate:

```bash
vibecomfy validate <workflow.py>
vibecomfy doctor <workflow.py> --json
vibecomfy port doctor-all <workflow.json> --json
vibecomfy runtime doctor
```

Dependencies:

```bash
vibecomfy nodes install-plan <workflow>
vibecomfy nodes ensure --workflow <workflow>
vibecomfy nodes ensure --template <ready_id>
vibecomfy nodes lock
vibecomfy nodes restore
vibecomfy fetch <workflow> --dry-run
vibecomfy models stage --select-phase core --dry-run
```

Run:

```bash
vibecomfy run <workflow.py> --runtime embedded
vibecomfy run <workflow.py> --runtime server --server-url http://127.0.0.1:8188
vibecomfy run image/z_image --ready --runtime server --server-url http://127.0.0.1:8188
vibecomfy logs tail
```

Python-format workflows can run against an existing server. VibeComfy imports `build()`, compiles the returned `VibeWorkflow` to API JSON, and queues that JSON to the server.

Prompt/seed/steps CLI overrides work only when the workflow exposes matching public inputs. `--ensure-packs` is embedded-only.

## Canonical boundaries

Use `load_bundle(<path-or-ready-id>)` for canonical loading. Raw UI/API JSON is import evidence; `python -m vibecomfy.cli port check <source> --json` and `python -m vibecomfy.cli nodes reconcile --workflow <source> --json` are the preflight gates, followed by the positional-source migration command:

```bash
python -m vibecomfy.cli port convert <source> --out out/scratchpads/<name>.py --json
python -m vibecomfy.cli port convert <source> --ready-id <kind>/<name> --out ready_templates/<kind>/<name>.py --json
```

The first form is the normal scratchpad path. The `--ready-id` form is only for an intentional ready-template candidate. A hard `port check` error blocks conversion; remediate the diagnostic with the named reconcile/install-plan/schema action before rerunning. Legacy `.layout.json` files are presentation evidence and are not an alternate semantic source.

For the browser transaction, `/vibecomfy/agent-edit` captures a candidate, then canonical V2 Apply uses `/vibecomfy/agent-edit/prepare` followed by `/vibecomfy/agent-edit/finalize`. `/vibecomfy/agent-edit/accept` is a temporary compatibility bridge to finalize with the same revision/API digest and transaction guards; it has no independent authority-bypass path. `/vibecomfy/agent-edit/rollback` or `/vibecomfy/agent-edit/reconcile` handles recovery and resynchronization. `/agent/edit` is a deprecated compatibility alias through the same adapter and must not bypass the gates. Queue only a finalized approved revision: the queue gate checks revision identity plus the fresh API digest and blocks stale, unapproved, or mismatched candidates. An optional `.vibe.json` sidecar binds presentation metadata to the Python workflow identity and semantic digest; it cannot alter graph semantics.

H3's current proof is structural and no-GPU: it proves full source IR custody, active compiled role wiring, public `load_bundle` parity, and negative mutations. It does not prove edits, sidecar handling, transaction handling, models, CUDA, media quality, or RunPod execution.

## Edit Candidate Vs Run Result

The Comfy app agent edit path, structural agentic tests, live agentic tests, and package-side edit guidance should all use the same canonical edit spine:

```text
target graph -> inspect/research -> editable graph surface -> VibeWorkflow or UI candidate edit -> validation gates -> candidate/apply or run
```

There are two different return shapes:

| Surface | Return shape | Meaning |
|---|---|---|
| Package-side edit | edited file path plus validation/doctor/install-plan evidence | The graph was changed or prepared, but not necessarily executed. |
| Comfy app / agentic edit | candidate envelope: `outcome.kind`, `candidate.graph`, `apply_eligibility`, graph hashes, `change_details`, `artifacts`, `gates`, `response.json` | The app has an applyable or blocked candidate. It is not an executed generation. |
| Runtime execution | `RunResult(run_id, prompt_id, outputs, metadata_path, log_path)` plus `out/runs/<run_id>/metadata.json` | The workflow was queued and outputs were collected. |

Agentic evidence packs use frozen artifacts such as `compiled_api.json`, `metadata.json`, `actions.jsonl`, `response.json`, and `implementation_result.json`. They prove what happened; narrative files such as `report.md` are not proof.

## RunPod

Use RunPod only when requested or when local execution is unavailable and a GPU run is necessary.

The retired live acceptance entry point is fail-closed and exits before provisioning or running a payload. It is retained only as a diagnostic refusal that points callers to the offline approved-record transport. The other commands below are live RunPod operations and require credentials, network access, and a suitable GPU environment:

```bash
python scripts/runpod_acceptance.py  # expected: fail-closed refusal; no live acceptance
python scripts/runpod_validate.py
VIBECOMFY_MATRIX_SCOPE=<family> uv run python scripts/runpod_corpus_matrix.py
pytest --runpod -m runpod tests/smoke/test_layer2_runpod_ops.py
pytest --runpod-full -m runpod_full tests/smoke/test_layer2_runpod_matrix.py
vibecomfy runpod list|status|terminate|gpu-types|corpus-matrix
```

`runpod_validate.py` launches a remote smoke pod, installs dependencies, runs one embedded ready-template smoke, and collects artifacts. `runpod_corpus_matrix.py` launches a remote corpus job, installs dependencies and optional model/runtime packages, and runs the selected matrix. Neither command is a no-GPU proof. The fail-closed acceptance placeholder does not perform setup inspection, API queueing, conversion, execution, or artifact collection; use `prepare_runpod_transport(record, bundle)` and `queue_runpod_stub(record, bundle, queue=...)` to check approved bytes and queue payloads offline. Import conversion remains `port check` followed by `port convert`.

Relevant env vars:

| Var | Purpose | Default |
|---|---|---|
| `RUNPOD_API_KEY` | RunPod creds | required |
| `RUNPOD_GPU_TYPE` / `RUNPOD_GPU_TYPE_<FAMILY>` | GPU class override | RTX 4090 |
| `VIBECOMFY_RUNPOD_STORAGE` | RunPod network volume name | `Peter` |
| `VIBECOMFY_RUNPOD_GPU` | GPU class for `runpod_validate.py` | `NVIDIA GeForce RTX 4090` |
| `VIBECOMFY_RUNPOD_MAX_RUNTIME_SECONDS` | Watchdog timeout | 7200 smoke / 21600 matrix |
| `VIBECOMFY_RUNPOD_LIFECYCLE_ROOT` | Sibling lifecycle checkout | `../runpod-lifecycle` |
| `VIBECOMFY_RUNPOD_REPO_URL` / `VIBECOMFY_RUNPOD_GIT_REF` | Pod checkout source | local origin / current branch |
| `VIBECOMFY_WATCHDOG=1` | Verbose watchdog log capture | unset |

## Outputs

Runs write under `out/`:

- `out/scratchpads/<name>.py` from conversion
- `out/runs/<run_id>/comfy.log`
- `out/runs/<run_id>/metadata.json`
- generated image/video/audio files under `out/runs/<run_id>/`
- `out/sessions/<id>/` for embedded session state

## Plugin Surface

Project-local plugins:

```text
./vibecomfy_extras/{blocks,patches,ops,recipes,ready_templates}/*.py
```

User-global plugins:

```text
~/.vibecomfy/{blocks,patches,ops,recipes,ready_templates}/*.py
```

Pip plugins use the `vibecomfy.plugins` entry point group. `ensure_plugins_loaded()` discovers them lazily.

The `PluginAPI` exposes `register_block`, `register_patch`, `register_op`, `register_route`, and `register_ready_root`. Built-in ready ids win on collision; plugin collisions warn.

## Router

Verb-native ops use `router.pick(...)` internally.

```python
from vibecomfy import router

result = router.pick("video", "i2v", model="ltx")
```

The result carries the chosen template id plus explicit and applicable patches. Router rules live in `vibecomfy/router/`.

## Known Limitations

- Audio and image-edit verbs are not yet wired in the verb-native API. Use `load_bundle(...)` for the canonical candidate when available; compatibility `load_workflow_any(...)` remains an import adapter, and raw JSON must pass through the named import/convert path before execution.
- `image.t2i(model="flux2_klein_9b_gguf")` is not exposed through the verb-native API yet. Use `load_bundle(...)` for the canonical candidate; `load_workflow_any(...)` remains a compatibility import adapter.
- Named outputs such as `.out("IMAGE")` require a retained output roster containing that name. An unregistered name raises `NotImplementedError`; use an explicitly authored integer slot only when the source contract establishes that slot. Known roster holes and out-of-range slots fail closed.
- `MarkdownNote` nodes are stripped during refactor because they are UI annotations only.

## Durable Template Checklist

For full detail, read `docs/templates/adding_templates_models.md`.

1. Pick a stable id: `<media>/<lower_snake_model_capability>`.
2. Store source JSON close to upstream:

```text
ready_templates/sources/official/<media>/<id>.json
ready_templates/sources/community/<source>/<id>.json
ready_templates/sources/custom_nodes/<pack>/<source>/<id>.json
```

3. Add or update `ready_templates/sources/manifests/coverage.json`.
4. Declare custom-node packs in `vibecomfy/node_packs.py` or the relevant pack module; update `custom_nodes.lock` when needed.
5. Declare models in `vibecomfy/registry/models.yaml` when workflow metadata is not enough.
6. Preflight and convert:

```bash
vibecomfy port check ready_templates/sources/.../<id>.json --json
vibecomfy port convert ready_templates/sources/.../<id>.json \
  --ready-id <media>/<id> \
  --out ready_templates/<media>/<id>.py \
  --json
```

7. Validate locally:

```bash
vibecomfy validate ready_templates/<media>/<id>.py
vibecomfy doctor ready_templates/<media>/<id>.py --json
pytest -q tests/test_ready_templates.py tests/test_runpod_matrix.py tests/test_nodes_install.py tests/test_cli_misc.py tests/test_cli_sources_workflows_nodes.py
```

8. Validate on RunPod with a focused scope only when cost and environment are acceptable:

```bash
VIBECOMFY_MATRIX_SCOPE=<family> uv run python scripts/runpod_corpus_matrix.py
```

Document incompatibilities in `docs/runtime/incompatibilities.md`, `docs/structural_issues.md`, or a family coverage doc.
