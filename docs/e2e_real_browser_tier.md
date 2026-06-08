# Real-browser E2E test tier (Playwright against live ComfyUI)

This tier boots a real ComfyUI server with a deterministic fixture-backed agent
provider and runs the VibeComfy agent-edit panel through Playwright (Chromium)
against a real DOM.  It covers the entire bug class (layout, scroll, geometry,
real-DOM API semantics, rAF behavior) that the jsdom-style harness cannot see by
construction.

## Why a separate tier?

The following shipped bugs ALL had a fully green jsdom suite before and after
discovery, and were only found by hand-driving a real browser:

- `querySelectorAll(function)` TypeError swallowed in the rAF stack (panel froze).
- Thread region flex-shrink clipping ~2,800px of conversation.
- Sidebar mount growing unbounded so the outer sidebar scrolled the whole panel.
- `requestAnimationFrame` frozen in occluded windows.
- Auto-scroll landing on the turn-log instead of the newest message.

Layout, scroll, and geometry assertions are only meaningful in a real browser
engine.  This tier asserts them through DOM/JS probes, LiteGraph canvas state,
and existing debug instrumentation — not screenshots or pixel diffs.

## Tier boundary

| Concern                                | jsdom/node harness (`tests/browser/`)     | Playwright e2e (`tests/e2e/`)            |
|----------------------------------------|-------------------------------------------|------------------------------------------|
| DOM layout / CSS box model             | ❌ Emulated — not a real engine            | ✅ Real Chromium layout                   |
| Scroll / overflow behavior             | ❌ No scrollable viewport                  | ✅ Real scroll, wheel, programmatic       |
| `requestAnimationFrame` / paint cycle  | ❌ Mocked or no-op                         | ✅ Real browser frames                    |
| LiteGraph canvas `window.app`          | ❌ Not available (no ComfyUI process)      | ✅ Live canvas reads via `page.evaluate`  |
| Panel rehydrate from server sessions   | ❌ Mocked session data                     | ✅ Real ComfyUI-out session rehydrate     |
| Agent submit / apply / audit flow      | ❌ Mocked backend                          | ✅ Live HTTP through fixture provider     |
| Console / page / request error capture | ✅ Same style                              | ✅ Same style + real browser noise filter |
| Speed                                  | Fast (milliseconds)                       | Slower (~45–120s cold, ~20s warm)        |
| Requires ComfyUI process               | No                                        | Yes                                      |
| Requires API keys                      | No                                        | No                                       |

**Neither tier uses image comparison or pixel-diff assertions.**  The jsdom
harness should remain the primary unit/integration tier; the Playwright tier is
an additive safety net for layout/scroll/geometry regressions.

## Prerequisites

### Required

- **Node.js** ≥ 18 (for `fetch`, `fs/promises`, and ESM).  The launcher and
  Playwright run on Node.
- **Python** — the same Python that can boot ComfyUI (≥ 3.10).  Set via
  `PYBIN` env var or `--python`.
- **ComfyUI checkout** — a local ComfyUI worktree with `main.py`.  The
  launcher auto-discovers:
  1. `--comfyui-dir` / `COMFYUI_DIR` (explicit).
  2. `/Users/peteromalley/Documents/reigh-workspace/ComfyUI` (default macOS
     path — edit the `DEFAULT_EXTERNAL_COMFYUI_DIR` constant in `run.mjs` if
     yours differs).
  3. `vendor/ComfyUI/` inside this repo (vendored fallback).
- **Playwright + Chromium** — install once:
  ```bash
  cd tests/e2e
  npm install
  npx playwright install chromium
  ```

### NOT required

- **No API keys** — the fixture provider is deterministic and offline.
- **No GPU / models** — ComfyUI boots with `--cpu`.  Missing-model toasts are
  acceptable noise.
- **No external services** — no RUNPOD, DeepSeek, Anthropic, or OpenAI calls.
- **No Docker** — runs directly on the host.

## One-command execution

From the repository root:

```bash
node tests/e2e/run.mjs
```

This single command:

1. Allocates a free localhost port.
2. Resolves the ComfyUI checkout.
3. Symlinks `vibecomfy/comfy_nodes` into `custom_nodes/vibecomfy`.
4. Validates the fixture-provider fixture tree (fail-fast on corruption).
5. Optionally copies pre-seeded session fixtures into the ComfyUI runtime
   `out/editor_sessions/` directory.
6. Spawns ComfyUI with `--cpu`, the allocated port, and
   `VIBECOMFY_ARNOLD_RUNTIME_MODULE=vibecomfy.comfy_nodes.fixture_provider`.
7. Polls `/vibecomfy/ping` and `/vibecomfy/agent/status?route=auto` until ready.
8. Runs all Playwright specs in `tests/e2e/specs/` with one Chromium worker.
9. Tears ComfyUI down on success, failure, timeout, or signal (SIGINT/SIGTERM).

### Options

```
node tests/e2e/run.mjs [options] [-- <playwright args...>]

Options:
  --port <port>                Fixed port instead of auto-allocated
  --python <path>              Python executable (default: $PYBIN or python)
  --comfyui-dir <path>         ComfyUI checkout to boot
  --seed-sessions-dir <path>   Session fixture source tree (default: tests/fixtures/e2e_sessions/)
  --no-seed                    Skip session seeding
  --ready-timeout-ms <ms>      Readiness timeout (default: 120000)
  --launcher-only              Boot, wait for readiness, then tear down (no Playwright)
  --help                       Show this message
```

### Examples

```bash
# Full suite
node tests/e2e/run.mjs

# One spec file
node tests/e2e/run.mjs -- specs/agent_panel_layout.spec.mjs

# Smoke the launcher without Playwright
node tests/e2e/run.mjs --launcher-only

# Skip session seeding (for specs that load their own graph)
node tests/e2e/run.mjs --no-seed -- specs/agent_panel_turn.spec.mjs

# Custom ComfyUI checkout and longer readiness timeout
node tests/e2e/run.mjs --comfyui-dir ~/other-comfy --ready-timeout-ms 180000
```

### Environment variables

| Variable                           | Effect                                         |
|------------------------------------|------------------------------------------------|
| `COMFYUI_DIR`                      | ComfyUI checkout path (overridden by `--comfyui-dir`) |
| `PYBIN`                            | Python executable (overridden by `--python`)   |
| `VIBECOMFY_FIXTURE_DIR`            | Fixture-provider fixture path (default: `tests/fixtures/editor_sessions/`) |
| `VIBECOMFY_E2E_SESSION_FIXTURES`   | Session-seeding source tree (overridden by `--seed-sessions-dir`) |
| `VIBECOMFY_ARNOLD_RUNTIME_MODULE`  | **Set automatically** by the launcher to `vibecomfy.comfy_nodes.fixture_provider` |
| `REPO_ROOT`                        | **Set automatically** by the launcher for Python path resolution |
| `BASE_URL`                         | **Set automatically** for Playwright config |

## Fixture refresh

Committed fixtures live under `tests/fixtures/editor_sessions/` and are the
deterministic data source for the fixture provider.  When new recorded agent
turns are available (e.g., from a live ComfyUI run against the real Arnold
backend), refresh fixtures as follows:

### Fixture structure

```
tests/fixtures/editor_sessions/
├── manifest.json              # Maps SHA-256 short keys → scenario metadata
├── 023d3c0c98fd7581/           # One directory per committed turn
│   ├── request.json            #   Original agent request (task, graph, route, model)
│   ├── model_request.json      #   Request sent to the model provider
│   ├── model_response.json     #   Raw model response (batch prose + fence)
│   ├── content.txt             #   Reconstructed batch content string
│   └── fixture.json            #   Response envelope with "content" key
├── 19fe1f725aab5ad1/
│   └── ...
```

### Adding a new fixture

1. Record a real agent turn (or locate an existing turn under a ComfyUI
   `out/editor_sessions/<session>/turns/<NNNN>/` directory).

2. Compute the deterministic key:
   ```python
   import hashlib, json
   task = "<the task text>"
   messages = [...]  # sorted chat messages
   payload = task + json.dumps(sorted(messages, key=lambda m: json.dumps(m, sort_keys=True)), sort_keys=True)
   key = hashlib.sha256(payload.encode()).hexdigest()[:16]
   ```

3. Create the fixture directory:
   ```bash
   mkdir -p tests/fixtures/editor_sessions/<key>/
   ```

4. Copy and name the required files:
   - `request.json` — from the recorded turn's `request.json`.
   - `model_request.json` — from the recorded turn's `model_request.json` (if available; optional for most specs).
   - `model_response.json` — from the recorded turn's `model_response.json` (if available; optional for most specs).
   - `content.txt` — reconstruct the batch content string (prose + ```batch fence + statements + ```).
   - `fixture.json` — create `{"content": "<the full batch content string>"}`.

5. Add an entry to `manifest.json`:
   ```json
   "<key>": {
     "session": "<human-readable session name>",
     "turn": "<turn number or label>",
     "task_preview": "<first ~80 chars of task for substring matching>"
   }
   ```

6. Validate the launcher can see it:
   ```bash
   node tests/e2e/run.mjs --launcher-only
   ```
   A healthy validation log includes: `validated N provider fixture(s) under ...`.

### Key scheme

Fixture keys use SHA-256 hashing (hex digest, first 16 chars) of the
concatenated `task + sorted JSON messages` string.  This is deterministic
(replay the same task + messages → same key) and short enough for filesystem
usage.  `manifest.json` provides human-readable scenario names for each key.

## Repo `out/` prohibition

**The e2e tier never reads from or writes to the repository `out/` directory
at runtime.**

- Committed fixtures live under `tests/fixtures/editor_sessions/` (for the
  fixture provider) and `tests/fixtures/e2e_sessions/` (for session seeding).
- The fixture provider resolves fixture paths relative to `REPO_ROOT` (set by
  the launcher) joined with `tests/fixtures/editor_sessions/`.  It does not
  look at `out/editor_sessions/`.
- When session fixtures are seeded, they are copied into the ComfyUI runtime's
  `out/editor_sessions/` directory inside the ComfyUI checkout — not into the
  repository.
- The launcher creates a temporary runtime root (`/tmp/vibecomfy-e2e-*`) for
  ComfyUI output, temp, input, and user data, which is cleaned up on teardown.

This ensures tests are reproducible regardless of what is or isn't in the
developer's live ComfyUI `out/` directory.

## Architecture

```
┌─────────────────────────────────────────────────────────────┐
│  tests/e2e/run.mjs (Node launcher)                          │
│                                                             │
│  1. Allocate port        5. Spawn ComfyUI (--cpu)           │
│  2. Resolve ComfyUI dir  6. Poll /vibecomfy/ping            │
│  3. Symlink custom_nodes 7. Poll /vibecomfy/agent/status    │
│  4. Validate fixtures    8. Run Playwright specs            │
│                          9. Teardown                        │
└──────────────┬──────────────────────────────────────────────┘
               │
    ┌──────────▼──────────────────────────────────────────┐
    │  ComfyUI process                                     │
    │                                                      │
    │  VIBECOMFY_ARNOLD_RUNTIME_MODULE=                    │
    │    vibecomfy.comfy_nodes.fixture_provider            │
    │                                                      │
    │  ┌─────────────────────────────────────────────┐     │
    │  │  fixture_provider.py                        │     │
    │  │  - readiness()          → {ready: true}     │     │
    │  │  - run_agent_turn()     → v1 JSON envelope  │     │
    │  │  - run_agent_turn_delta() → delta + message │     │
    │  │  - run_agent_turn_batch() → batch-repl prose│     │
    │  │                                             │     │
    │  │  Reads tests/fixtures/editor_sessions/      │     │
    │  │  via REPO_ROOT env var                      │     │
    │  └─────────────────────────────────────────────┘     │
    └──────────┬──────────────────────────────────────────┘
               │ HTTP
    ┌──────────▼──────────────────────────────────────────┐
    │  Playwright (Chromium, 1 worker)                     │
    │                                                      │
    │  specs/                                              │
    │  ├── agent_panel_layout.spec.mjs    (8 tests)        │
    │  ├── agent_panel_lifecycle.spec.mjs (3 tests)        │
    │  ├── agent_panel_turn.spec.mjs      (1 test)         │
    │  └── agent_panel_overlay.spec.mjs   (1 test)         │
    │                                                      │
    │  helpers/                                            │
    │  ├── failure-capture.mjs   (console/page/request)    │
    │  ├── panel-open.mjs        (launcher + sidebar)      │
    │  ├── dom-probes.mjs        (layout/scroll/composer)  │
    │  └── canvas-debug-probes.mjs (LiteGraph/debug)       │
    └──────────────────────────────────────────────────────┘
```

## Spec files

### `agent_panel_layout.spec.mjs` (8 tests)

Covers panel open/close, viewport bounding, internal thread scrolling,
composer visibility, and browser error capture.

- Open via launcher and sidebar tab.
- Panel shell is viewport-bounded.
- Thread scrolls internally (programmatic `scrollTop` and `WheelEvent`).
- Composer is visible with submit button attached.
- No outer panel scroll (root `overflow-y` not `auto`/`scroll`).
- Zero unexpected console/page/request errors (filtered for known ComfyUI noise).

### `agent_panel_lifecycle.spec.mjs` (3 tests)

Covers session rehydrate, message rendering, close/reopen idempotency, and
scroll-position behavior across submissions.

- Rehydrates a seeded 32-message session.
- Newest message stays visible.
- Close/reopen does not duplicate message keys.
- Scroll-up position preserved during non-submit rerenders.
- Submit from scrolled-up position jumps thread to newest content.
- Zero unexpected console/page/request errors.

### `agent_panel_turn.spec.mjs` (1 test)

Drives a full fixture-backed submit through the agent-edit pipeline.

- Loads the `browser_val_1` fixture graph into the live LiteGraph canvas.
- Submits via the composer, asserts pending/progress row appears and clears.
- Opens agent bubble details; verifies candidate rows and audit affordances.
- Downloads an audit artifact.
- Accepts/applies the candidate.
- Reads `window.app.canvas.graph` to confirm applied widget values (`nearest-exact`, `2`).

### `agent_panel_overlay.spec.mjs` (1 test)

Asserts preview overlay geometry through existing debug instrumentation.

- Reads `window.__vibecomfyAgentPanelSingleton._overlayDrawModelCache`.
- Verifies edited-node full-box marker encloses node + title bar.
- Verifies widget-row Y positions are within node body bounds.
- Verifies added-node ghost dimensions when present.
- No image comparison; all assertions are DOM/JS state probes.

## Helper modules

All helpers are re-exported from `tests/e2e/helpers/index.mjs`.  Import them in
specs with:

```js
import { installFailureCapture, openPanelViaLauncher, probePanelDebug } from "../helpers/index.mjs";
```

| Module                  | Exports                                                                 |
|-------------------------|-------------------------------------------------------------------------|
| `failure-capture.mjs`   | `installFailureCapture`, `assertNoFailures`, `collectUnhandledPageErrors` |
| `panel-open.mjs`        | `waitForPanelRoot`, `waitForLauncher`, `openPanelViaLauncher`, `openPanelViaSidebar`, `closePanel`, `isPanelOpen`, `panelMountMode`, constants (`MOUNT_MODE`, `PANEL_IDS`, `PANEL_DATASET`) |
| `dom-probes.mjs`        | `probeComposerState`, `composeText`, `clickComposerButton`, `probeThreadState`, `probePanelLayout`, `waitForSubmitReady`, `waitForPanelFlush` |
| `canvas-debug-probes.mjs` | `probeCanvasGraph`, `probePanelDebug`, `waitForPanelPhase`, `waitForPanelReadiness`, `probeOverlayState`, `probeApp`, `waitForAppGraph`, `serializeLiveGraph`, `liveNodeCount` |

## Local-only cadence

This tier is **local-only**.  There is no CI integration, no GitHub Actions
workflow, and no remote-service dependency.

- No CI config files are added to `.github/workflows/`.
- No `docker-compose` or container setup.
- No cloud credentials or API keys.
- The Playwright dependency tree is fully isolated under `tests/e2e/node_modules/`
  and git-ignored.  The repository root has no `package.json` or npm lockfile.

The tier is designed to be run manually on a developer's machine before pushing
changes that touch agent panel layout, scroll, lifecycle, or overlay code.

**Expected runtime:** ~45–120 seconds cold (ComfyUI first boot + spec execution),
~20 seconds warm (ComfyUI already cached).  The `--ready-timeout-ms` default is
120 seconds, which covers cold macOS boots comfortably.

## Known limitations

- **Missing-model toasts:** ComfyUI emits model-load warnings when booted with
  `--cpu` and no models.  These are filtered by the failure-capture helpers and
  do not cause spec failures.  If a spec fails on a console error, check whether
  it is a new ComfyUI noise line that needs adding to the filter list.
- **OpenGL warnings:** On macOS, `nodes_glsl.py` may produce OpenGL import
  warnings.  These are also filtered.
- **Startup time:** Cold ComfyUI boot can take 10–20 seconds.  The launcher
  polls readiness every 500ms and tolerates up to `--ready-timeout-ms`.
- **Single worker:** Playwright runs with `workers: 1` to avoid port contention
  and ensure deterministic ordering.  Do not increase this.
- **No retries:** Specs run with `retries: 0`.  If a spec is flaky, fix the
  root cause rather than adding retry logic.
- **Fixture-driven only:** The agent provider is always the fixture provider
  in this tier.  Real LLM calls are never made.  If you need to test
  provider-routing logic, use the jsdom harness or run the live server manually
  with `VIBECOMFY_ARNOLD_RUNTIME_MODULE=vibecomfy.comfy_nodes.megaplan_runtime`.
- **ComfyUI path:** The default external ComfyUI path is hardcoded to
  `/Users/peteromalley/Documents/reigh-workspace/ComfyUI`.  Override it with
  `COMFYUI_DIR` or `--comfyui-dir` if your checkout lives elsewhere.
