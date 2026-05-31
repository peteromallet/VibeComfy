import { app } from "../../scripts/app.js";

const SUPPORTED_FRONTEND = "1.39.x";

async function checkFrontendVersion() {
  let version = "unknown";
  try {
    const res = await fetch("/system_stats");
    const stats = await res.json();
    version = stats?.system?.comfyui_frontend_package || "unknown";
  } catch (e) {
    version = "unknown";
  }
  const major = SUPPORTED_FRONTEND.split(".").slice(0, 2).join(".");
  if (version === "unknown" || !String(version).startsWith(major)) {
    console.warn(`VibeComfy: frontend version ${version} outside supported range, activating anyway`);
  }
}

function errorModal(err) {
  const kind = err?.kind || "Error";
  const message = err?.message || err?.error || String(err);
  const overlay = makeOverlay();
  const box = makeBox(overlay);
  box.appendChild(el("h3", `${kind}: ${message}`));
  const close = button("Close", () => overlay.remove());
  box.appendChild(close);
}

async function openRoundtrip() {
  let graph;
  try {
    graph = app.canvas.graph.serialize();
  } catch (e) {
    return errorModal({ kind: "SerializeError", message: String(e) });
  }
  let result;
  try {
    const res = await fetch("/vibecomfy/roundtrip", {
      method: "POST",
      headers: { "Content-Type": "application/json" },
      body: JSON.stringify({ graph }),
    });
    result = await res.json();
    if (!res.ok || result?.error) {
      return errorModal({ kind: result?.kind, message: result?.error || res.statusText });
    }
  } catch (e) {
    return errorModal({ kind: "NetworkError", message: String(e) });
  }
  renderDiffModal({ graph: result.graph, report: result.report });
}

function openAgentEdit() {
  let graph;
  try {
    graph = app.canvas.graph.serialize();
  } catch (e) {
    return errorModal({ kind: "SerializeError", message: String(e) });
  }

  const overlay = makeOverlay();
  const box = makeBox(overlay);
  box.appendChild(el("h3", "Edit with DeepSeek"));

  const textarea = document.createElement("textarea");
  textarea.placeholder = "Describe the workflow change...";
  Object.assign(textarea.style, {
    width: "520px",
    height: "140px",
    display: "block",
    background: "#111",
    color: "#eee",
    border: "1px solid #555",
    borderRadius: "4px",
    padding: "8px",
    fontFamily: "monospace",
  });
  box.appendChild(textarea);

  const runBtn = button("Run", async () => {
    const task = textarea.value.trim();
    if (!task) return;
    runBtn.disabled = true;
    runBtn.textContent = "Working...";
    let result;
    try {
      const res = await fetch("/vibecomfy/agent-edit", {
        method: "POST",
        headers: { "Content-Type": "application/json" },
        body: JSON.stringify({ graph, task }),
      });
      result = await res.json();
      if (!res.ok || result?.error) {
        overlay.remove();
        return errorModal({ kind: result?.kind, message: result?.error || res.statusText });
      }
    } catch (e) {
      overlay.remove();
      return errorModal({ kind: "NetworkError", message: String(e) });
    }
    overlay.remove();
    renderDiffModal({ graph: result.graph, report: result.report, message: result.message });
  });
  box.appendChild(runBtn);
  box.appendChild(button("Cancel", () => overlay.remove()));
}

// ── DOM helpers ───────────────────────────────────────────────────────────
function el(tag, text) { const n = document.createElement(tag); if (text != null) n.textContent = text; return n; }
function button(label, onClick) { const b = el("button", label); b.onclick = onClick; b.style.margin = "4px"; return b; }
function makeOverlay() {
  const o = el("div");
  Object.assign(o.style, { position: "fixed", inset: "0", background: "rgba(0,0,0,0.6)", zIndex: "10000", display: "flex", alignItems: "center", justifyContent: "center" });
  document.body.appendChild(o);
  return o;
}
function makeBox(overlay) {
  const b = el("div");
  Object.assign(b.style, { background: "#222", color: "#eee", padding: "16px", maxHeight: "80vh", overflow: "auto", borderRadius: "8px", minWidth: "360px", fontFamily: "monospace" });
  overlay.appendChild(b);
  return b;
}
function row(uid, color, label, tooltip) {
  const r = el("div", `${label} ${uid}`);
  r.style.color = color;
  if (tooltip) r.title = tooltip;
  return r;
}

// ── Diff modal (pure function of report) ──────────────────────────────────
function renderDiffModal({ graph, report, message = null }) {
  const ce = report?.change?.content_edits || {};
  const preserved = ce.preserved || [];
  const edited = ce.edited || [];
  const removedNamed = ce.removed_named || [];
  const recovery = report?.recovery || [];

  const known = new Set([...preserved, ...edited]);
  const emittedUids = (graph?.nodes || []).map((n) => n?.properties?.vibecomfy_uid).filter((u) => u != null);
  const schemaLess = recovery.filter((r) => r?.schema_less === true);
  const schemaLessByNode = {};
  for (const r of schemaLess) schemaLessByNode[String(r.node_id)] = r;

  const overlay = makeOverlay();
  const box = makeBox(overlay);
  box.appendChild(el("h3", "Round-trip (VibeComfy)"));
  if (message) {
    const msg = el("p", message);
    msg.style.whiteSpace = "pre-wrap";
    msg.style.maxWidth = "640px";
    box.appendChild(msg);
  }

  for (const u of preserved) box.appendChild(row(u, "#4caf50", "preserved", null));
  for (const u of edited) box.appendChild(row(u, "#ffc107", "edited", null));
  for (const r of removedNamed) box.appendChild(row(`${r.uid} (${r.class_type})`, "#f44336", "removed", null));
  for (const u of emittedUids) {
    if (!known.has(u)) {
      const sl = schemaLessByNode[String(u)];
      const tip = sl ? `schema-less — provider: ${sl.provider}, confidence: ${sl.confidence}` : null;
      box.appendChild(row(u + (sl ? " ⚠" : ""), "#2196f3", "new", tip));
    }
  }

  const needsConfirm = removedNamed.length > 0 || schemaLess.length > 0;
  const applyBtn = button("Apply", () => doApply(graph, overlay, applyBtn, needsConfirm, removedNamed.length, schemaLess.length));
  if (needsConfirm) { applyBtn.style.opacity = "0.7"; applyBtn.style.background = "#555"; }
  box.appendChild(applyBtn);
  box.appendChild(button("Cancel", () => overlay.remove()));
}

function doApply(graph, overlay, applyBtn, needsConfirm, removedCount, schemaLessCount) {
  if (needsConfirm && applyBtn.dataset.confirmed !== "1") {
    applyBtn.dataset.confirmed = "1";
    applyBtn.textContent = `${removedCount} nodes will be removed and ${schemaLessCount} are schema-less; apply anyway?`;
    return;
  }
  app.loadGraphData(graph);
  overlay.remove();
  toast("Round-trip applied");
}

function toast(msg) {
  if (app.extensionManager?.toast?.add) {
    app.extensionManager.toast.add({ severity: "success", summary: msg, life: 3000 });
  } else {
    console.log(`VibeComfy: ${msg}`);
  }
}

app.registerExtension({
  name: "VibeComfy.Roundtrip",
  commands: [
    { id: "VibeComfy.Roundtrip", label: "Round-trip (VibeComfy)", function: openRoundtrip },
    { id: "VibeComfy.AgentEdit", label: "Edit with DeepSeek (VibeComfy)", function: openAgentEdit },
  ],
  menuCommands: [{ path: ["Extensions", "VibeComfy"], commands: ["VibeComfy.Roundtrip", "VibeComfy.AgentEdit"] }],
  async setup() {
    await checkFrontendVersion();
    const proto = window.LiteGraph?.LGraphCanvas?.prototype;
    if (proto && !proto.__vibecomfyRoundtripPatched) {
      proto.__vibecomfyRoundtripPatched = true;
      const orig = proto.getCanvasMenuOptions;
      proto.getCanvasMenuOptions = function () {
        const opts = orig ? orig.apply(this, arguments) : [];
        opts.push({ content: "Round-trip (VibeComfy)", callback: openRoundtrip });
        opts.push({ content: "Edit with DeepSeek (VibeComfy)", callback: openAgentEdit });
        return opts;
      };
    }
  },
});
