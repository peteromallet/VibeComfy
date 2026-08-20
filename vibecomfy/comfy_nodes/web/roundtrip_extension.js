// ComfyUI extension registration and setup orchestration for VibeComfy.
//
// The feature implementations remain owned by vibecomfy_roundtrip.js. Keeping
// this module dependency-injected makes the browser bootstrap boundary small
// without creating a second owner for panel or graph behavior.

export function createRoundtripExtension({
  openRoundtrip,
  openAgentEdit,
  patchIntentNodePrototype,
  configureDiagnostics,
  checkFrontendVersion,
  registerDefaultExecutionModeSetting,
  registerOnDemandSchemasSetting,
  installGraphConfigureIntentFallback,
  installIntentNodeFallback,
  installAgentPreviewOverlay,
  repairLiveIntentNodesFromCandidate,
  installQueueGuard,
  ensureAgentTurnListener,
  ensureExecutorPhaseListener,
  installAgentPanelDebugHook,
  ensureAgentPanel,
  prefetchAgentStatus,
  ensureAgentSidebarTab,
  ensureAgentLauncher,
}) {
  return {
    name: "VibeComfy.Roundtrip",
    commands: [
      { id: "VibeComfy.Roundtrip", label: "Round-trip (VibeComfy)", function: openRoundtrip },
      { id: "VibeComfy.AgentEdit", label: "Edit with Agent (VibeComfy)", function: openAgentEdit },
    ],
    menuCommands: [{ path: ["Extensions", "VibeComfy"], commands: ["VibeComfy.Roundtrip", "VibeComfy.AgentEdit"] }],
    async beforeRegisterNodeDef(nodeType, nodeData) {
      patchIntentNodePrototype(nodeType, nodeData);
    },
    async setup() {
      console.log("[vibecomfy] extension setup() running");
      try {
        const pingRes = await fetch("/vibecomfy/ping");
        const pingBody = await pingRes.text();
        console.log("[vibecomfy] /vibecomfy/ping response", pingRes.status, pingBody);
      } catch (pingErr) {
        console.error("[vibecomfy] /vibecomfy/ping failed", pingErr);
      }
      configureDiagnostics();
      await checkFrontendVersion();
      registerDefaultExecutionModeSetting();
      registerOnDemandSchemasSetting();
      installGraphConfigureIntentFallback();
      installIntentNodeFallback();
      installAgentPreviewOverlay();
      repairLiveIntentNodesFromCandidate();
      installQueueGuard();
      ensureAgentTurnListener();
      ensureExecutorPhaseListener();
      installAgentPanelDebugHook();
      const proto = window.LiteGraph?.LGraphCanvas?.prototype;
      if (proto && !proto.__vibecomfyRoundtripPatched) {
        proto.__vibecomfyRoundtripPatched = true;
        const orig = proto.getCanvasMenuOptions;
        proto.getCanvasMenuOptions = function () {
          const opts = orig ? orig.apply(this, arguments) : [];
          opts.push({ content: "Round-trip (VibeComfy)", callback: openRoundtrip });
          opts.push({ content: "Edit with Agent (VibeComfy)", callback: openAgentEdit });
          return opts;
        };
      }
      ensureAgentPanel();
      prefetchAgentStatus();
      if (globalThis.__VIBECOMFY_ENABLE_SIDEBAR_TAB__ === true) {
        ensureAgentSidebarTab();
      }
      ensureAgentLauncher();
    },
  };
}

export function registerRoundtripExtension(app, dependencies) {
  const extension = createRoundtripExtension(dependencies);
  app.registerExtension(extension);
  return extension;
}
