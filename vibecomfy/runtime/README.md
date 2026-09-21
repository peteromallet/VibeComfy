# Runtime

Runtime execution, embedded/server session management, watchdog handling, and
model policy checks live here.

Public callers should prefer the package-level runtime helpers such as
`run_sync`, `run_embedded_sync`, and `vibecomfy run`. Direct imports from this
package are for runtime internals, focused tests, and command implementations.

## Delivery report

A successful non-media run means that Comfy accepted the prompt and reported
terminal execution success. A declared video/audio output also passes the
bounded final-media probe before completion; verified video runs report
`RunResult.status` as `Completed — final video verified` and set
`RunResult.media_validated` to `True`. A filename or preview artifact alone is
never enough. `RunResult.outputs` contains the legacy output strings, while
`RunResult.artifacts` records each filename and its honest location. Managed
and embedded runs report local paths; explicit external servers report Comfy
`/view` URLs and leave the artifact `path` as `null`, so declared media cannot
be marked verified until it is actually retrieved and probed.

`RunResult.log_path` is a local captured file only for managed or embedded
runs. It is `None` for an explicit external server, with
`RunResult.log_provenance` explaining that the external Comfy process owns its
logs. An external run may supply `SessionConfig.extra["external_log_locator"]`
or `--external-log-locator`; this is recorded as a reference only and never
pretended to be a captured local path.

Comfy history may expose one physical video in both `gifs` and `images`, or
under a nested `subfolder`. Runtime delivery normalizes and deduplicates those
views while preserving distinct paths and rejecting traversal/absolute
descriptors. If generation succeeded but retrieval failed, use the existing
attempt receipt with `vibecomfy.runtime.retry_delivery()`; this delivery-only
retry does not compile or queue a second generation.

Every completed run also writes a concise VibeComfy-owned `completion.json`
beside `metadata.json`. It contains the run and prompt IDs, completion status,
outputs, artifact locations, and log provenance. `RunResult.completion_path`,
`vibecomfy run`, and `vibecomfy logs <run-id>` expose that record directly.
`metadata.json` remains the full execution snapshot.

When declared artifacts are locally custody-backed, completion also writes
`managed-generation-result.json` beside the existing records. This
`managed-generation-result.v1` envelope keeps task, attempt, and producer-run
correlation, declared output-port identity, ordinal, custody-relative path,
MIME type, byte size, and SHA-256. VibeComfy evidence remains opaque under
`evidence.producer`; `evidence.transport` is reserved for the transport layer.
`RunResult.managed_generation_result_path` is `None` when an output is remote,
missing, or otherwise cannot be hashed and contained, and the metadata/attempt
records retain the explicit unavailability reason. VibeComfy never marks
publication as successful.

For an existing RunPod machine, first record a named binding with
`vibecomfy runpod bind`. A bound run uses the existing `runpod-lifecycle` API
to attach/status-check the pod, retrieve `output`/`out` through its archive
path, and capture `--log-path` when supplied. The Comfy HTTP endpoint remains
the queue transport, while the lifecycle witness and remote/local retrieval
outcome are retained in the same attempt receipt. A bare `--server-url` stays
non-mutating and does not claim lifecycle custody or local artifact retrieval.
