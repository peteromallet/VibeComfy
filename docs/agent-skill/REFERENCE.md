# VibeComfy Agent Reference

This is the dense reference behind the `vibecomfy` umbrella skill. Do not start here for ordinary work; use it when the focused skills need exact API names, command surfaces, or package constraints.

## Custom Python nodes

`from vibecomfy import python_node` provides a static decorator/proxy. Calling
the proxy as `fn(workflow, image=handle)` creates an ordinary
`vibecomfy.exec` node and returns `Handles` keyed by the declared outputs.
The proxy never calls the function body during graph construction.

```python
@python_node(inputs={"image": "IMAGE"}, outputs={"image": "IMAGE"})
def transform(image):
    return {"image": image}
```

`python_node.from_source(path_or_project, entrypoint="module:function", ...)`
captures a complete file/project as a deterministic
`vibecomfy.python_capsule/v1` payload. Snapshot entrypoints are relative to
the captured package root. `python_node.from_installed(entrypoint="pkg.mod:fn", ...)`
keeps the ordinary worker import namespace and is the mode for absolute
self-imports. Both helpers are inert until the existing `vibecomfy.exec`
runtime executes them.

The source capsule verifies member paths, byte counts, per-file hashes, a
canonical manifest digest, archive digest, and bounded sizes (4 MiB encoded,
16 MiB expanded, 512 files). The worker checks declared distributions before
importing. No setup, import, or source execution occurs during inspect,
validate, or static edit preparation.

The CLI convenience surface is:

```text
vibecomfy edit BUNDLE exec add --source-body BODY --ports PORTS.json [--bindings BINDINGS.json]
vibecomfy edit BUNDLE exec update TARGET --source-body BODY --ports PORTS.json
vibecomfy edit BUNDLE exec inspect TARGET --json
vibecomfy edit BUNDLE exec export TARGET --destination DIRECTORY
```

All changes enter the existing typed `EditSession`/bundle transaction. Use
`--dry-run` for a no-write preview. `in_N`/`out_N` are physical Comfy
sockets; the `io` widget and returned handles carry semantic names and types.
Use an explicit mapping, `single`, `tuple`, or `list` result adapter; do
not infer unpacking from the Python value type. See
[custom Python workflow nodes](../guides/custom-python-workflows.md).

## Public Import Surface

The authoritative source for import claims is `docs/api/m6-public-api.md`. Use `VibeWorkflow.compile("api")` to export a workflow to the ComfyUI API JSON shape accepted by runtime execution.

Public loaders and helpers:

| Name | What it does |
|---|---|
| `load_bundle(path_or_id)` | Canonical bundle loader for ready ids and Python candidates; preserves workflow identity and bundle metadata. |
| `load_workflow_any(path_or_id)` | Compatibility loader for ready ids, scratchpad paths, JSON files, and indexed references; raw JSON is import input, not an execution instruction. |
| `workflow_from_ready(id)` | Loads a ready template by id, such as `image/z_image`. |
| `workflow_from_id(id)` | Loads a ready template or an explicitly imported local workflow bundle. Community workflows must be fetched from Hivemind first. |
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

Load/fork/promote:

```bash
vibecomfy import <workflow.json-or-hivemind-reference>
vibecomfy copy-to-recipe <ready_id> --out recipes/<name>.py
vibecomfy validate workflows/<id> --json
vibecomfy nodes reconcile --workflow workflows/<id> --json
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

Local canonical Python workflows are reconciled automatically after load and
before compilation. The run reports all statically visible model, node-pack,
destination, and class-accounting blockers before any local transfer, install,
session restart, compile, or queue. Resolved workflows reuse the existing
fetch, lockfile, session, and bounded download plumbing. `--deps reuse` is the
safe default; it compares `requirements.runtime` with the actual target and
emits one actionable warning for drift. `--deps sync` explicitly prepares a
managed target and honors `VIBECOMFY_OFFLINE=1`; it is rejected for an
explicit external server. `--runtime-root`, `--session`, `--keep-warm`,
`--restart-session`, `--download-workers`, and `--json` apply to the normal
run command; explicit `--server-url` execution is remote and non-mutating.
Managed sync uses an existing `runtime_root/.venv` or `runtime_root/venv` and
the `.vibecomfy-managed` marker written by managed setup; it fails closed when
that owned interpreter or marker is unavailable.

Scoped synchronization may be requested with repeatable
`--deps-sync-package NAME`; the result retains the full expected/actual checks
and reports `partial`, selected repairs, and remaining mismatches. Unknown
selectors fail before mutation. An intentional advisory experiment must
provide both `--deps-deviation-scope` and `--deps-deviation-reason` (aliases
`--dependency-deviation-*`); its attempt receipt records the decision while the
runtime report remains `noncompliant` or `unverified`. This does not rewrite
the workflow declaration or bypass missing-node/schema/backend failures.

`requirements.runtime` is a typed declaration for the tested ComfyUI
commit/version, Python version, package constraints, launch flags, model
identities, and custom-node commits/versions. Legacy `metadata.python_env` and
`metadata.comfy_commit` normalize into it, with contradictions rejected.
For fresh managed RunPod setup, pass the workflow declaration to bootstrap so
its launch flags replace the generic low-VRAM defaults:

```bash
vibecomfy runpod bootstrap-comfy --workflow workflows/example/workflow.vibe.json
```

The declared bootstrap path requires an already provisioned managed Python and
ComfyUI checkout under the runtime root; otherwise it fails clearly before
claiming that the workflow runtime was synchronized.

Python-format workflows can run against an existing server. VibeComfy imports `build()`, compiles the returned `VibeWorkflow` to API JSON, and queues that JSON to the server.

Prompt/seed/steps CLI overrides work only when the workflow exposes matching public inputs. `--ensure-packs` is embedded-only.

## Canonical boundaries

Use `load_bundle(<path-or-ready-id>)` for canonical loading. Raw UI/API JSON and
Hivemind workflow records enter through the single `vibecomfy import` command;
`validate`, `doctor`, and `nodes reconcile` are preflight stages on the
imported bundle. Maintainers promote a reviewed bundle explicitly:

```bash
python -m vibecomfy.cli templates create <source> --id <kind>/<name> --out ready_templates/<kind>/<name>.py --json
```

`templates create` consumes the canonical Python bundle and writes the
ready-template Python/companion pair. Validate and diagnose it before
promotion; legacy `.layout.json` files are presentation evidence and are not
an alternate semantic source.

For the browser transaction, `/vibecomfy/agent-edit` captures a candidate, then canonical V2 Apply uses `/vibecomfy/agent-edit/prepare` followed by `/vibecomfy/agent-edit/finalize`. `/vibecomfy/agent-edit/accept` is a temporary compatibility bridge to finalize with the same revision/API digest and transaction guards; it has no independent authority-bypass path. `/vibecomfy/agent-edit/rollback` or `/vibecomfy/agent-edit/reconcile` handles recovery and resynchronization. `/agent/edit` is a deprecated compatibility alias through the same adapter and must not bypass the gates. Queue only a finalized approved revision: the queue gate checks revision identity plus the fresh API digest and blocks stale, unapproved, or mismatched candidates. An optional `.vibe.json` sidecar binds presentation metadata to the Python workflow identity and semantic digest; it cannot alter graph semantics.

H3's current proof is structural and no-GPU: it proves full source IR custody, active compiled role wiring, public `load_bundle` parity, and negative mutations. It does not prove edits, sidecar handling, transaction handling, models, CUDA, media quality, or RunPod execution.
The authoritative H3 workflow is maintained in Astrid rather than this checkout; apply the `requirements.runtime` declaration there, not to a guessed local copy.

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

Local RunPod commands read `RUNPOD_API_KEY` from the same shared Astrid file
as Astrid: `~/.astrid/astrid.env`, or the path in `ASTRID_ENV_FILE`. The shared
file takes precedence over project `.env` copies; project dotenv files may
still provide non-secret RunPod settings. Relative `ASTRID_ENV_FILE` paths are
resolved under `ASTRID_HOME` (default `~/.astrid`). CI and deployed
environments can continue injecting `RUNPOD_API_KEY` through process
environment.

The retired live acceptance entry point is fail-closed and exits before provisioning or running a payload. It is retained only as a diagnostic refusal that points callers to the offline approved-record transport. The other commands below are live RunPod operations and require credentials, network access, and a suitable GPU environment:

```bash
python scripts/runpod_acceptance.py  # expected: fail-closed refusal; no live acceptance
python scripts/runpod_validate.py
VIBECOMFY_MATRIX_SCOPE=<family> uv run python scripts/runpod_corpus_matrix.py
pytest --runpod -m runpod tests/smoke/test_layer2_runpod_ops.py
pytest --runpod-full -m runpod_full tests/smoke/test_layer2_runpod_matrix.py
vibecomfy runpod list|status|terminate|gpu-types|corpus-matrix
```

`runpod_validate.py` launches a remote smoke pod, installs dependencies, runs one embedded ready-template smoke, and collects artifacts. `runpod_corpus_matrix.py` launches a remote corpus job, installs dependencies and optional model/runtime packages, and runs the selected matrix. Neither command is a no-GPU proof. The fail-closed acceptance placeholder does not perform setup inspection, API queueing, conversion, execution, or artifact collection; use `prepare_runpod_transport(record, bundle)` and `queue_runpod_stub(record, bundle, queue=...)` to check approved bytes and queue payloads offline. Source onboarding remains `vibecomfy import`, followed by bundle validation.

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

Runs write under `<runtime-root>/out/` (the current working directory when no
runtime root is supplied):

- `<runtime-root>/out/scratchpads/<name>.py` from conversion
- `<runtime-root>/out/runs/<run_id>/comfy.log`
- `<runtime-root>/out/runs/<run_id>/metadata.json`
- generated image/video/audio files under `<runtime-root>/out/runs/<run_id>/`
- `<runtime-root>/out/sessions/<id>/` for managed session state
- `<runtime-root>/out/preparations/<workflow-stem>-<session-id>.json` for dependency-preparation receipts

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
vibecomfy import ready_templates/sources/.../<id>.json
vibecomfy templates create workflows/<id> --id <media>/<id> \
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
