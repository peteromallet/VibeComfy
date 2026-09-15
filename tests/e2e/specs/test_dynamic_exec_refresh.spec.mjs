import { test, expect } from "@playwright/test";
import {
  installFailureCapture,
  collectUnhandledPageErrors,
  serializeLiveGraph,
} from "../helpers/index.mjs";

const OPEN_TIMEOUT = { timeout: 30_000 };

// ── Graceful skip when the ComfyUI test server is unreachable ──────────────
async function checkServerReachable(page) {
  try {
    await page.goto("/", { waitUntil: "domcontentloaded", timeout: 10_000 });
    await page.waitForSelector("canvas#graph-canvas", { timeout: 15_000 });
    await page.waitForFunction(
      () => window.app?.canvas?.graph && typeof window.app.canvas.graph.configure === "function",
      null,
      { timeout: 15_000 },
    );
    return true;
  } catch {
    return false;
  }
}

// ── Shared helpers ─────────────────────────────────────────────────────────

async function navigateToComfyUI(page) {
  await page.goto("/", { waitUntil: "domcontentloaded" });
  await page.waitForSelector("canvas#graph-canvas", { timeout: 60_000 });
  // Wait for the LiteGraph instance to be fully initialized on the app global.
  await page.waitForFunction(
    () => window.app?.canvas?.graph && typeof window.app.canvas.graph.configure === "function",
    null,
    { timeout: 30_000 },
  );
  await page.waitForTimeout(1_000);
}

async function dismissTemplatesDialog(page) {
  const dialog = page.getByRole("dialog");
  if (await dialog.count()) {
    await page.keyboard.press("Escape").catch(() => {});
    const closeDialog = page.getByRole("button", { name: "Close dialog" });
    if (await closeDialog.isVisible().catch(() => false)) {
      await closeDialog.click({ force: true }).catch(() => {});
    }
    await dialog.first().waitFor({ state: "hidden", timeout: 5_000 }).catch(() => {});
  }
}

/**
 * Load a fixture graph payload into the live app.graph via configure().
 * This simulates what happens when an agent candidate is applied or a
 * workflow is imported — it drives the full ingress/repair pipeline.
 */
async function loadGraphPayload(page, graphPayload) {
  await page.evaluate((payload) => {
    const graph = window.app?.canvas?.graph;
    if (!graph) {
      throw new Error("LiteGraph instance is unavailable.");
    }
    if (typeof graph.clear === "function") {
      graph.clear();
    }
    if (typeof graph.configure === "function") {
      graph.configure(payload);
    } else {
      throw new Error("LiteGraph graph.configure() is unavailable.");
    }
    if (typeof graph.setDirtyCanvas === "function") {
      graph.setDirtyCanvas(true, true);
    }
    if (typeof window.app?.graph?.setDirtyCanvas === "function") {
      window.app.graph.setDirtyCanvas(true, true);
    }
  }, graphPayload);
}

async function assertCleanBrowser(page, capture, { allowComfyWarnings = true } = {}) {
  const unhandled = await collectUnhandledPageErrors(page);
  const meaningfulConsole = capture.consoleErrors.filter((entry) => {
    if (!allowComfyWarnings && entry.type === "warning") return true;
    const text = entry.text || "";
    if (text.includes("ComfyUI") && entry.type === "warning") return false;
    if (text.includes("DevTools")) return false;
    if (text.includes("[DOM]")) return false;
    if (text.includes("Automatic1111")) return false;
    if (text.includes("No resource with given URL")) return false;
    if (text.includes("Failed to load resource: the server responded with a status of 404")) return false;
    if (text.includes("ComfyApp graph accessed before initialization")) return false;
    if (text.includes("[MaskEditor] ComfyApp.open_maskeditor is deprecated")) return false;
    if (text.includes("VibeComfy: frontend version unknown outside supported range")) return false;
    if (text.includes("[vibecomfy] computePreviewDiff") && text.includes("unresolvable link endpoint")) return false;
    if (text.includes("[vite:preloadError]") && text.includes("ace is not defined")) return false;
    if (/^\s*$/.test(text)) return false;
    return true;
  });
  const meaningfulRequests = capture.failedRequests.filter((entry) => {
    if (entry.url && entry.url.includes("/ws")) return false;
    if (entry.url && entry.url.includes("favicon")) return false;
    if (entry.url && entry.url.includes("/api/userdata/user.css")) return false;
    if (entry.url && /\/user\.css$/.test(entry.url)) return false;
    if (entry.url && entry.url.includes("/api/userdata?dir=workflows")) return false;
    if (entry.url && entry.url.includes("/api/userdata?dir=subgraphs")) return false;
    if (entry.url && entry.url.includes("/api/userdata/comfy.templates.json")) return false;
    if (entry.url && entry.url.includes("/api/view?type=input&filename=")) return false;
    if (entry.url && entry.url.includes("api.comfy.org/comfy-nodes/")) return false;
    if (entry.status === 0 && (entry.statusText || "").includes("ERR_ABORTED")) return false;
    return true;
  });

  const issues = [];
  if (meaningfulConsole.length > 0) {
    issues.push(
      `${meaningfulConsole.length} console issue(s):\n`
      + meaningfulConsole.map((entry) => `  [${entry.type}] ${entry.text}`).join("\n"),
    );
  }
  if (meaningfulRequests.length > 0) {
    issues.push(
      `${meaningfulRequests.length} failed request(s):\n`
      + meaningfulRequests.map((entry) => `  ${entry.status} ${entry.statusText} ${entry.url}`).join("\n"),
    );
  }
  if (capture.pageErrors.length > 0) {
    issues.push(
      `${capture.pageErrors.length} page error(s):\n`
      + capture.pageErrors.map((entry) => `  ${entry.message}`).join("\n"),
    );
  }
  if (unhandled.length > 0) {
    issues.push(
      `${unhandled.length} unhandled page error(s):\n`
      + unhandled.map((entry) => `  ${entry.message}`).join("\n"),
    );
  }
  if (issues.length > 0) {
    throw new Error(`Browser failure surface not clean:\n${issues.join("\n\n")}`);
  }
}

/**
 * Read detailed exec-node state from the live graph for assertion.
 * Returns null if no exec node is found.
 */
async function readLiveExecNodeState(page) {
  return page.evaluate(() => {
    const graph = window.app?.canvas?.graph;
    if (!graph) return null;

    const nodes = Array.isArray(graph._nodes)
      ? graph._nodes
      : Array.isArray(graph.nodes)
        ? graph.nodes
        : [];

    const execNode = nodes.find((n) => n.type === "vibecomfy.exec");
    if (!execNode) return null;

    // Read links from the live graph link store
    const linkRecords = {};
    const links = graph.links;
    if (Array.isArray(links)) {
      for (const link of links) {
        const id = link?.id ?? link?.[0];
        if (id != null) {
          linkRecords[String(id)] = link;
        }
      }
    } else if (links && typeof links === "object") {
      Object.assign(linkRecords, links);
    }

    // Read upstream and downstream connected nodes
    const upstreamNodes = [];
    const downstreamNodes = [];
    const inputLinks = [];
    const outputLinks = [];

    if (Array.isArray(execNode.inputs)) {
      for (const input of execNode.inputs) {
        if (input.link != null) {
          inputLinks.push(input.link);
          const link = linkRecords[String(input.link)];
          if (link) {
            const originId = link.origin_id ?? link[1];
            const originNode = nodes.find((n) => n.id === originId);
            if (originNode) {
              upstreamNodes.push({
                id: originNode.id,
                type: originNode.type,
              });
            }
          }
        }
      }
    }

    if (Array.isArray(execNode.outputs)) {
      for (const output of execNode.outputs) {
        const outLinks = Array.isArray(output.links) ? output.links : (output.link != null ? [output.link] : []);
        for (const linkId of outLinks) {
          if (linkId != null) {
            outputLinks.push(linkId);
            const link = linkRecords[String(linkId)];
            if (link) {
              const targetId = link.target_id ?? link[3];
              const targetNode = nodes.find((n) => n.id === targetId);
              if (targetNode) {
                downstreamNodes.push({
                  id: targetNode.id,
                  type: targetNode.type,
                });
              }
            }
          }
        }
      }
    }

    return {
      exists: true,
      id: execNode.id,
      type: execNode.type,
      inputCount: Array.isArray(execNode.inputs) ? execNode.inputs.length : 0,
      outputCount: Array.isArray(execNode.outputs) ? execNode.outputs.length : 0,
      inputs: Array.isArray(execNode.inputs)
        ? execNode.inputs.map((inp) => ({
            name: inp.name ?? null,
            label: inp.label ?? null,
            type: inp.type ?? null,
            link: inp.link ?? null,
          }))
        : [],
      outputs: Array.isArray(execNode.outputs)
        ? execNode.outputs.map((out) => ({
            name: out.name ?? null,
            label: out.label ?? null,
            type: out.type ?? null,
            links: out.links ?? null,
          }))
        : [],
      widgetsValues: Array.isArray(execNode.widgets_values)
        ? execNode.widgets_values.map((w) => (typeof w === "object" ? JSON.parse(JSON.stringify(w)) : w))
        : [],
      propertiesVibecomfyIo: execNode.properties?.vibecomfy?.io ?? null,
      propertiesVibecomfyKind: execNode.properties?.vibecomfy?.kind ?? null,
      propertiesVibecomfyIntentSource: execNode.properties?.vibecomfy?.intent?.source ?? null,
      upstreamNodeTypes: upstreamNodes.map((n) => n.type),
      downstreamNodeTypes: downstreamNodes.map((n) => n.type),
      inputLinks,
      outputLinks,
    };
  });
}

test.describe("Dynamic Exec Refresh", () => {
  let capture;
  let serverWasReachable = false;

  test.beforeAll(async ({ browser }) => {
    const page = await browser.newPage();
    try {
      serverWasReachable = await checkServerReachable(page);
    } finally {
      await page.close();
    }
  });

  test.beforeEach(async ({ page }) => {
    test.skip(!serverWasReachable, "ComfyUI test server is unreachable — skipping live E2E spec.");
    capture = installFailureCapture(page);
  });

  test.afterEach(async ({ page }, testInfo) => {
    if (testInfo.status !== "skipped") {
      await assertCleanBrowser(page, capture);
    }
  });

  test("preserves typed exec IO, link integrity, and properties after agent-create → apply → refresh lifecycle", async ({ page }) => {
    await navigateToComfyUI(page);
    await dismissTemplatesDialog(page);
    await page.waitForTimeout(500);

    // ── Build a minimal pipeline: VAEDecode → vibecomfy.exec → SaveImage ──
    const source = "return {\"image\": image}";
    const typedIo = {
      inputs: [["image", "IMAGE"]],
      outputs: [["image", "IMAGE"]],
    };

    const fixtureGraph = {
      nodes: [
        {
          id: 1,
          type: "VAEDecode",
          inputs: [{ name: "samples", type: "LATENT", link: null }],
          outputs: [{ name: "IMAGE", type: "IMAGE", links: [10] }],
          properties: { "Node name for S&R": "VAEDecode" },
        },
        {
          id: 2,
          type: "vibecomfy.exec",
          inputs: Array.from({ length: 16 }, (_, i) => ({
            name: `in_${i}`,
            type: "*",
            link: i === 0 ? 10 : null,
          })),
          outputs: Array.from({ length: 16 }, (_, i) => ({
            name: `out_${i}`,
            type: "*",
            links: i === 0 ? [20] : null,
          })),
          widgets_values: [source, typedIo],
          properties: {
            "Node name for S&R": "vibecomfy.exec",
            vibecomfy_uid: "exec-refresh-1",
          },
        },
        {
          id: 3,
          type: "SaveImage",
          inputs: [{ name: "images", type: "IMAGE", link: 20 }],
          outputs: [],
          properties: { "Node name for S&R": "SaveImage" },
        },
      ],
      links: [
        [10, 1, 0, 2, 0, "IMAGE"],
        [20, 2, 0, 3, 0, "IMAGE"],
      ],
    };

    // ── Step 1: Load the fixture graph — this drives loadGraphData → normalizeForApply → configure → repairLiveNodes ──
    await loadGraphPayload(page, fixtureGraph);
    await page.waitForTimeout(1_000);

    // ── Step 2: Read the live exec node state after the load+repair pipeline ──
    const state1 = await readLiveExecNodeState(page);

    expect(state1).not.toBeNull();
    expect(state1.exists).toBe(true);
    expect(state1.type).toBe("vibecomfy.exec");

    // Assert: exactly 1 typed input (NOT the 16-port pool)
    expect(state1.inputCount).toBe(1);
    expect(state1.inputs[0].name).toBe("in_0");
    expect(state1.inputs[0].label).toBe("image: IMAGE");
    expect(state1.inputs[0].type).toBe("IMAGE");
    // Link to VAEDecode preserved
    expect(state1.inputs[0].link).toBe(10);
    expect(state1.inputLinks).toContain(10);

    // Assert: exactly 1 typed output (NOT the 16-port pool)
    expect(state1.outputCount).toBe(1);
    expect(state1.outputs[0].name).toBe("out_0");
    expect(state1.outputs[0].label).toBe("image: IMAGE");
    expect(state1.outputs[0].type).toBe("IMAGE");
    // Link to SaveImage preserved
    expect(state1.outputLinks).toContain(20);

    // Assert: source widget preserved
    expect(state1.widgetsValues).toContain(source);

    // Assert: typed IO metadata present in properties.vibecomfy.io
    expect(state1.propertiesVibecomfyIo).toEqual({
      inputs: [["image", "IMAGE"]],
      outputs: [["image", "IMAGE"]],
    });

    // Assert: kind and intent source stamped
    expect(state1.propertiesVibecomfyKind).toBe("code");
    expect(state1.propertiesVibecomfyIntentSource).toBe(source);

    // Assert: upstream/downstream connectivity
    expect(state1.upstreamNodeTypes).toContain("VAEDecode");
    expect(state1.downstreamNodeTypes).toContain("SaveImage");

    // ── Step 3: Serialize the live graph and verify the serialized snapshot has no pool ──
    const serialized = await serializeLiveGraph(page);
    expect(serialized).not.toBeNull();

    const execSerialized = serialized.nodes?.find((n) => n.type === "vibecomfy.exec");
    expect(execSerialized).toBeTruthy();

    // Serialized exec node must have exactly 1 input (not 16)
    const serializedInputs = execSerialized.inputs;
    expect(Array.isArray(serializedInputs)).toBe(true);
    expect(serializedInputs.length).toBe(1);
    expect(serializedInputs[0].name).toBe("in_0");

    // Serialized exec node must have exactly 1 output (not 16)
    const serializedOutputs = execSerialized.outputs;
    expect(Array.isArray(serializedOutputs)).toBe(true);
    expect(serializedOutputs.length).toBe(1);
    expect(serializedOutputs[0].name).toBe("out_0");

    // ── Step 4: Refresh — re-load the graph data to simulate an import/reload cycle ──
    // Build a "stale" payload that mimics what might come back from an import
    // with a 16-port pool but typed IO declared — the repair path should normalize it.
    const staleImportPayload = {
      nodes: [
        {
          id: 1,
          type: "VAEDecode",
          inputs: [{ name: "samples", type: "LATENT", link: null }],
          outputs: [{ name: "IMAGE", type: "IMAGE", links: [10] }],
          properties: { "Node name for S&R": "VAEDecode" },
        },
        {
          id: 2,
          type: "vibecomfy.exec",
          // Stale: 16-port pool present along with typed IO declaration
          inputs: Array.from({ length: 16 }, (_, i) => ({
            name: `in_${i}`,
            type: "*",
            link: i === 0 ? 10 : null,
          })),
          outputs: Array.from({ length: 16 }, (_, i) => ({
            name: `out_${i}`,
            type: "*",
            links: i === 0 ? [20] : null,
          })),
          widgets_values: [source, typedIo],
          properties: {
            "Node name for S&R": "vibecomfy.exec",
            vibecomfy_uid: "exec-refresh-1",
          },
        },
        {
          id: 3,
          type: "SaveImage",
          inputs: [{ name: "images", type: "IMAGE", link: 20 }],
          outputs: [],
          properties: { "Node name for S&R": "SaveImage" },
        },
      ],
      links: [
        [10, 1, 0, 2, 0, "IMAGE"],
        [20, 2, 0, 3, 0, "IMAGE"],
      ],
    };

    await loadGraphPayload(page, staleImportPayload);
    await page.waitForTimeout(1_000);

    // ── Step 5: Verify post-refresh state still has typed IO, intact links, no pool ──
    const state2 = await readLiveExecNodeState(page);

    expect(state2).not.toBeNull();
    expect(state2.exists).toBe(true);

    // After refresh: still exactly 1 typed input, not 16
    expect(state2.inputCount).toBe(1);
    expect(state2.inputs[0].name).toBe("in_0");
    expect(state2.inputs[0].label).toBe("image: IMAGE");
    expect(state2.inputs[0].type).toBe("IMAGE");
    expect(state2.inputs[0].link).toBe(10);

    // After refresh: still exactly 1 typed output, not 16
    expect(state2.outputCount).toBe(1);
    expect(state2.outputs[0].name).toBe("out_0");
    expect(state2.outputs[0].label).toBe("image: IMAGE");
    expect(state2.outputs[0].type).toBe("IMAGE");

    // Links intact
    expect(state2.inputLinks).toContain(10);
    expect(state2.outputLinks).toContain(20);

    // Source widget still there
    expect(state2.widgetsValues).toContain(source);

    // properties.vibecomfy.io preserved through refresh
    expect(state2.propertiesVibecomfyIo).toEqual({
      inputs: [["image", "IMAGE"]],
      outputs: [["image", "IMAGE"]],
    });

    // Connectivity preserved
    expect(state2.upstreamNodeTypes).toContain("VAEDecode");
    expect(state2.downstreamNodeTypes).toContain("SaveImage");

    // ── Step 6: Serialize again and verify the snapshot is pool-free ──
    const serialized2 = await serializeLiveGraph(page);
    expect(serialized2).not.toBeNull();

    const execSerialized2 = serialized2.nodes?.find((n) => n.type === "vibecomfy.exec");
    expect(execSerialized2).toBeTruthy();
    expect(execSerialized2.inputs?.length).toBe(1);
    expect(execSerialized2.inputs?.[0]?.name).toBe("in_0");
    expect(execSerialized2.outputs?.length).toBe(1);
    expect(execSerialized2.outputs?.[0]?.name).toBe("out_0");

    // Verify serialized links still connect correctly
    const serializedLinks2 = serialized2.links;
    expect(Array.isArray(serializedLinks2)).toBe(true);
    // At minimum the VAEDecode→exec and exec→SaveImage links survive
    const linkIds2 = serializedLinks2.map((l) => l[0] ?? l.id);
    expect(linkIds2).toContain(10);
    expect(linkIds2).toContain(20);
  });

  test("serialized graph snapshot from live page contains no 16-port pool when exec io is declared", async ({ page }) => {
    await navigateToComfyUI(page);
    await dismissTemplatesDialog(page);
    await page.waitForTimeout(500);

    const source = "return {\"image\": image, \"latent\": latent}";
    const typedIo = {
      inputs: [["image", "IMAGE"], ["latent", "LATENT"]],
      outputs: [["result", "IMAGE"], ["preview", "IMAGE"]],
    };

    const fixtureGraph = {
      nodes: [
        {
          id: 10,
          type: "CheckpointLoaderSimple",
          inputs: [],
          outputs: [
            { name: "MODEL", type: "MODEL", links: [] },
            { name: "CLIP", type: "CLIP", links: [] },
            { name: "VAE", type: "VAE", links: [] },
          ],
          properties: { "Node name for S&R": "CheckpointLoaderSimple" },
        },
        {
          id: 20,
          type: "vibecomfy.exec",
          inputs: Array.from({ length: 16 }, (_, i) => ({
            name: `in_${i}`,
            type: "*",
            link: null,
          })),
          outputs: Array.from({ length: 16 }, (_, i) => ({
            name: `out_${i}`,
            type: "*",
            links: null,
          })),
          widgets_values: [source, typedIo],
          properties: {
            "Node name for S&R": "vibecomfy.exec",
            vibecomfy_uid: "exec-multiport-1",
          },
        },
      ],
      links: [],
    };

    await loadGraphPayload(page, fixtureGraph);
    await page.waitForTimeout(1_000);

    const state = await readLiveExecNodeState(page);
    expect(state).not.toBeNull();

    // 2 typed inputs, 2 typed outputs — no pool
    expect(state.inputCount).toBe(2);
    expect(state.outputCount).toBe(2);

    expect(state.inputs[0].name).toBe("in_0");
    expect(state.inputs[0].label).toBe("image: IMAGE");
    expect(state.inputs[0].type).toBe("IMAGE");
    expect(state.inputs[1].name).toBe("in_1");
    expect(state.inputs[1].label).toBe("latent: LATENT");
    expect(state.inputs[1].type).toBe("LATENT");

    expect(state.outputs[0].name).toBe("out_0");
    expect(state.outputs[0].label).toBe("result: IMAGE");
    expect(state.outputs[0].type).toBe("IMAGE");
    expect(state.outputs[1].name).toBe("out_1");
    expect(state.outputs[1].label).toBe("preview: IMAGE");
    expect(state.outputs[1].type).toBe("IMAGE");

    // Serialized snapshot must also be pool-free
    const serialized = await serializeLiveGraph(page);
    expect(serialized).not.toBeNull();

    const execSerialized = serialized.nodes?.find((n) => n.type === "vibecomfy.exec");
    expect(execSerialized).toBeTruthy();
    expect(execSerialized.inputs?.length).toBe(2);
    expect(execSerialized.outputs?.length).toBe(2);

    // Verify all 16-port pool evidence is gone from serialized form
    const allInputNames = execSerialized.inputs.map((inp) => inp.name);
    const allOutputNames = execSerialized.outputs.map((out) => out.name);
    expect(allInputNames).not.toContain("in_15");
    expect(allInputNames).not.toContain("in_2");
    expect(allOutputNames).not.toContain("out_15");
    expect(allOutputNames).not.toContain("out_2");

    // Verify properties.vibecomfy.io stamped
    expect(state.propertiesVibecomfyIo).toEqual({
      inputs: [["image", "IMAGE"], ["latent", "LATENT"]],
      outputs: [["result", "IMAGE"], ["preview", "IMAGE"]],
    });
  });

  test("frontend graphToPrompt queues a Python node through Comfy and records its output", async ({ page }) => {
    await navigateToComfyUI(page);
    await dismissTemplatesDialog(page);
    await page.waitForTimeout(500);

    const source = "return {\"image\": torch.zeros((1, 2, 2, 3))}";
    const typedIo = {
      inputs: [],
      outputs: [["image", "IMAGE"]],
    };
    const fixtureGraph = {
      nodes: [
        {
          id: 1,
          type: "vibecomfy.exec",
          inputs: Array.from({ length: 16 }, (_, i) => ({
            name: `in_${i}`,
            type: "*",
            link: null,
          })),
          outputs: Array.from({ length: 16 }, (_, i) => ({
            name: `out_${i}`,
            type: "*",
            links: i === 0 ? [20] : null,
          })),
          widgets_values: [source, typedIo],
          properties: {
            "Node name for S&R": "vibecomfy.exec",
            vibecomfy_uid: "exec-queue-1",
          },
        },
        {
          id: 2,
          type: "SaveImage",
          inputs: [{ name: "images", type: "IMAGE", link: 20 }],
          outputs: [],
          widgets_values: ["hands-on-browser-queue"],
          properties: { "Node name for S&R": "SaveImage" },
        },
      ],
      links: [[20, 1, 0, 2, 0, "IMAGE"]],
    };

    await loadGraphPayload(page, fixtureGraph);
    await page.waitForTimeout(1_000);

    const queued = await page.evaluate(async () => {
      const app = window.app;
      if (!app?.graph || typeof app.graphToPrompt !== "function") {
        throw new Error("Comfy graphToPrompt is unavailable.");
      }
      const converted = await app.graphToPrompt(app.graph);
      const response = await fetch("/prompt", {
        method: "POST",
        headers: { "Content-Type": "application/json" },
        body: JSON.stringify({
          prompt: converted.output,
          client_id: window.name || undefined,
        }),
      });
      return {
        status: response.status,
        body: await response.json(),
        prompt: converted.output,
      };
    });

    expect(queued.status).toBe(200);
    expect(queued.body.prompt_id).toBeTruthy();
    expect(queued.prompt["1"].class_type).toBe("vibecomfy.exec");
    expect(queued.prompt["2"].class_type).toBe("SaveImage");
    expect(queued.prompt["2"].inputs.images).toEqual(["1", 0]);

    const readHistory = () => page.evaluate(async (promptId) => {
      const response = await fetch(`/history/${encodeURIComponent(promptId)}`);
      return response.ok ? response.json() : {};
    }, queued.body.prompt_id);
    await expect.poll(readHistory, {
      timeout: 30_000,
      intervals: [250, 500, 1_000],
    }).toMatchObject({
      [queued.body.prompt_id]: {
        outputs: {
          "2": {
            images: expect.arrayContaining([
              expect.objectContaining({ filename: expect.stringContaining("hands-on-browser-queue") }),
            ]),
          },
        },
      },
    });
    const history = await readHistory();
    expect(history[queued.body.prompt_id].outputs["2"].images.length).toBeGreaterThan(0);
  });
});
