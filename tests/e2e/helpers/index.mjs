// ── Playwright e2e helpers barrel ──────────────────────────────────────────
// Re-exports all helper modules for convenient single-import usage.
//
// Usage:
//   import { installFailureCapture, openPanelViaLauncher, probePanelDebug, ... }
//     from "../helpers/index.mjs";

export {
  installFailureCapture,
  assertNoFailures,
  collectUnhandledPageErrors,
} from "./failure-capture.mjs";

export {
  MOUNT_MODE,
  PANEL_IDS,
  PANEL_DATASET,
  waitForPanelRoot,
  waitForLauncher,
  openPanelViaLauncher,
  openPanelViaSidebar,
  closePanel,
  isPanelOpen,
  panelMountMode,
} from "./panel-open.mjs";

export {
  probeComposerState,
  composeText,
  clickComposerButton,
  probeThreadState,
  probePanelLayout,
  waitForSubmitReady,
  waitForPanelFlush,
} from "./dom-probes.mjs";

export {
  probeCanvasGraph,
  installCanvas2DRecorder,
  clearCanvas2DRecorder,
  readCanvas2DRecorder,
  probePanelDebug,
  waitForPanelPhase,
  waitForPanelReadiness,
  probeOverlayState,
  probeApp,
  waitForAppGraph,
  serializeLiveGraph,
  liveNodeCount,
} from "./canvas-debug-probes.mjs";
