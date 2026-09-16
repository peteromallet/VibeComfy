# Prepared Workflow Runner

The prepared runner is the managed, repeatable form of `vibecomfy run`. It
prepares the dependencies described by a canonical workflow, records the
preparation result, starts or reuses a local managed ComfyUI session, and then
uses the normal compile-and-run path.

The supported command is:

```bash
vibecomfy run <workflow-or-ready-id> --prepare
```

`<workflow-or-ready-id>` must resolve to a canonical workflow bundle or ready
template. Raw UI/API JSON is an import source, not a prepared execution input;
pass it through `vibecomfy import` first.

## Lifecycle

Prepared execution has one ordered lifecycle:

```text
canonical load
  -> safe dependency declaration read
  -> preparation plan
  -> model download and custom-node preparation
  -> preparation receipt
  -> reuse or start local managed session
  -> compile
  -> queue and collect outputs
```

The declaration reader examines Python assignments with the AST and literal
evaluation only. It does not import or execute the workflow source while
reading the declaration. The workflow is still loaded through the canonical
loader before preparation begins, and normal canonical-authority and compile
gates still apply.

Preparation happens before compilation. A preparation failure therefore does
not queue a prompt. A successful preparation receipt is evidence that the
preparation phase completed; it is not evidence that the workflow compiled or
ran successfully.

## Dependency declaration

For a Python workflow file, the reader uses a top-level literal `PREPARE`
assignment. If no literal `PREPARE` value is read, it falls back to a
top-level literal `READY_REQUIREMENTS` assignment:

```python
PREPARE = {
    "models": [
        {
            "name": "example.safetensors",
            "url": "https://example.invalid/example.safetensors",
            "subdir": "checkpoints",
        }
    ],
    "custom_nodes": ["ComfyUI-ExamplePack"],
    "python_packages": ["example-package"],
}
```

The supported declaration keys are:

| Key | Meaning in the preparation plan | Current realization |
| --- | --- | --- |
| `models` | Model-asset entries to prepare. If it is not a list, assets are inferred from workflow metadata and loader references. | Missing URLs are reconciled from the local model registry by model id/name and target directory, including Hugging Face revision, checksum, and size when available. Downloads use the existing fetch authority rooted at `<runtime-root>/ComfyUI/models`, with its existing `target_path` behavior. An existing file is reused when it is present and passes the declared size/hash checks; a missing file with no registry/source match fails with an actionable fetch error. A declared checksum mismatch fails closed instead of silently replacing an unknown file. |
| `custom_nodes` | Names shown in the plan. If absent, names come from workflow requirements. | Missing repository URLs are reconciled from the built-in node-pack catalog or the runtime-root `custom_nodes.lock`. The installer then installs under `<runtime-root>/custom_nodes` and updates the lockfile. An existing clean checkout is reused; when that lockfile records a commit, the checkout is restored to that commit. Dirty or mismatched clones are refused rather than overwritten. |
| `python_packages` | Package names installed into the interpreter running VibeComfy. | Installed with the existing interpreter's `python -m pip`; node-pack requirements continue to use the existing pinned-pack installer. |

Only literal values are read from these assignments. A declaration such as
`READY_REQUIREMENTS = {"models": MODEL_ASSETS}` is not evaluated by this
reader unless the assignment itself is a literal value. The resulting value
must be a mapping; a literal non-mapping `PREPARE` value yields no usable
declaration rather than falling through to `READY_REQUIREMENTS`. If no usable
declaration is found, the plan uses workflow metadata and requirements.

The declaration is a preparation input, not a replacement for the workflow's
canonical metadata. In particular, arbitrary names in `PREPARE["custom_nodes"]`
do not by themselves make a pack installable; the current installer still uses
the workflow's resolved class types and requirements.

When the reference is a JSON workflow file, the preparation reader extracts
model assets from that JSON object. The normal canonical loader and authority
gate still decide whether the reference may be executed. A ready id or bundle
directory falls back to the loaded workflow's metadata and requirements.

## CLI contract

`--prepare` is a managed-server operation. It is rejected with exit code 2
when combined with `--runtime embedded` or `--server-url`, because preparation
mutates the local dependency/runtime authority and cannot safely mutate an
external server.

The prepared command accepts these preparation-specific flags:

| Flag | Semantics |
| --- | --- |
| `--prepare` | Enable dependency preparation and the managed prepared-session path. |
| `--no-ensure-models` | Disable model realization. Model entries may still appear in the plan. `--ensure-models` explicitly enables model preparation; with `--prepare`, model preparation is enabled by default when neither switch is supplied. |
| `--session ID` | Name the managed session and preparation receipt suffix. Prepared runs default to `prepared`. An active managed session with that name is reused; otherwise the command starts it. |
| `--keep-warm` | Leave a session started by this invocation running after the runtime call. Without it, the started session is stopped after the run call returns; a reused session is not stopped. |
| `--restart-session` | Stop the active named session, when present and owned by VibeComfy, before starting a fresh prepared session. It requires `--prepare`. |
| `--runtime-root DIR` | Set the authority for preparation state, models, custom nodes, lockfile, managed-session state, and run evidence. It defaults to the invoking working directory; relative paths are resolved when the runtime configuration is constructed. |
| `--dry-run` | Print the preparation result/plan and do not install, download, start a session, compile, or queue. The result has `dry_run: true` and `prepared: false`. |
| `--download-workers N` | Use up to `N` concurrent model download streams (default 2). Model transfer overlaps the serialized Python/node setup lane; `VIBECOMFY_PREPARE_DOWNLOAD_WORKERS` supplies the default. |
| `--json` | Emit structured preparation/session/run evidence for a completed run. Dry-run preparation already prints JSON. |

Examples:

```bash
# Inspect the plan without changing the environment.
vibecomfy run workflows/example --prepare --dry-run

# Prepare models and node packs, run once, and stop the managed session.
vibecomfy run image/z_image --ready --prepare --runtime server

# Use an isolated preparation/session authority and retain the session.
vibecomfy run workflows/example --prepare --runtime-root out/example-runtime \
  --session example --keep-warm --json

# Rebuild the named managed session before running.
vibecomfy run workflows/example --prepare --session example --restart-session

# Skip model downloads while still performing custom-node preparation.
vibecomfy run workflows/example --prepare --no-ensure-models
```

The existing `--prompt`, `--seed`, and `--steps` overrides still require the
corresponding public workflow inputs. `--memory-profile` is applied when the
prepared command starts a new local managed session; it does not reconfigure
an already-running or external server.

`--ensure-packs` remains an embedded-runtime option. With explicit
`--runtime server`, combining it with `--prepare` is rejected by the existing
embedded-only guard; with prepared `auto`, it is not passed to the managed
run because the prepared path performs its own custom-node preparation phase.

## Receipts and output evidence

After a non-dry preparation, the runner writes:

```text
<runtime-root>/out/preparations/<workflow-stem>-<session-id>.json
```

The receipt contains `ok`, `dry_run`, `prepared`, the normalized `plan`,
downloaded `model_paths`, custom-node `node_results`, explicit
`package_results`, the `receipt_path`, and `diagnostics` containing the
resolved runtime root, Python interpreter, and session id. Repeated
runs using the same workflow stem and session id overwrite this receipt.

With `--json`, a completed run prints an object containing:

```json
{
  "run_id": "...",
  "prompt_id": "...",
  "metadata_path": "...",
  "log_path": "...",
  "session_id": "prepared",
  "session_url": "http://127.0.0.1:8188",
  "preparation": {"...": "preparation receipt fields"}
}
```

The nested preparation object is the in-memory preparation result; its
`receipt_path` points to the persisted receipt. Normal runtime metadata and
logs retain the existing `<runtime-root>/out/runs/<run-id>/` contract.

## Lower-level composition seam

The implementation keeps preparation separate from loading and execution in
`vibecomfy.runtime.prepared`:

```python
from vibecomfy.runtime.prepared import (
    build_plan,
    prepare_workflow,
    read_declaration,
)
```

`read_declaration(reference)` returns a safe mapping when a declaration is
available. `build_plan(...)` returns a `PreparationPlan` without mutating the
environment. `prepare_workflow(...)` realizes the plan, unless `dry_run=True`,
and returns a `PreparationResult`. The CLI is the supported end-to-end entry
point; these helpers are the composition seam for other local callers.

## Failure and recovery

Model downloads are bounded by default at two streams and retain declaration
order in the receipt. Python/package and custom-node mutation stays serialized
because it shares the worker interpreter, while the model transfer lane runs
alongside it. Set `--download-workers 1` only when a particular network or
storage environment needs serialized transfer; this is a tuning setting, not a
separate preparation mode. A runtime-root preparation lock prevents concurrent
invocations from duplicating setup.

Preparation errors are reported before queueing. Model download failures,
unresolved custom-node classes, failed pack installation, declaration-read
failures, and invalid runtime roots should be fixed at their reported
authority and retried. A prepared run must not silently fall back to embedded
execution or an external server.

If a retained prepared session is no longer needed, use the matching runtime
root and session id:

```bash
vibecomfy session status example --runtime-root out/example-runtime
vibecomfy session stop example --runtime-root out/example-runtime
```

The automatic stop guard covers the runtime call after preparation, session
start/reuse, override checks, and compilation. If one of those later checks
fails after this invocation has started a session, inspect and stop that
session explicitly.

For the broader embedded/server lifecycle and warm-session semantics, see
[Runtime Lifecycle](../runtime/lifecycle.md) and [Runtime Surface](../runtime/surface.md).
