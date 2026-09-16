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
logs. An external run may supply `SessionConfig.extra["external_log_locator"]`
or `--external-log-locator`; this is recorded as a reference only and never
pretended to be a captured local path.

Every completed run also writes a concise VibeComfy-owned `completion.json`
beside `metadata.json`. It contains the run and prompt IDs, completion status,
outputs, artifact locations, and log provenance. `RunResult.completion_path`,
`vibecomfy run`, and `vibecomfy logs <run-id>` expose that record directly.
`metadata.json` remains the full execution snapshot.
