# Runtime

Runtime execution, embedded/server session management, watchdog handling, and
model policy checks live here.

Public callers should prefer the package-level runtime helpers such as
`run_sync`, `run_embedded_sync`, and `vibecomfy run`. Direct imports from this
package are for runtime internals, focused tests, and command implementations.

## Delivery report

A successful run means that Comfy accepted the prompt and reported terminal
execution success. `RunResult.status` is `"completed"`; media inspection is not
performed by the runtime, so `RunResult.media_validated` remains `False` unless
a separate validator is added. `RunResult.outputs` contains the legacy output
strings, while `RunResult.artifacts` records each filename and its honest
location. Managed and embedded runs report local paths; explicit external
servers report Comfy `/view` URLs and leave the artifact `path` as `null`.

`RunResult.log_path` is a local captured file only for managed or embedded
runs. It is `None` for an explicit external server, with
`RunResult.log_provenance` explaining that the external Comfy process owns its
logs. The same delivery, artifact, and log fields are persisted in the run's
`metadata.json`, and `vibecomfy run` prints queue status, execution status,
artifacts, and log provenance in both text and JSON modes.
