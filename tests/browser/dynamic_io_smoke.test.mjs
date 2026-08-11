import test from "node:test";
import assert from "node:assert/strict";

import { createBrowserHarness } from "./harness.mjs";

test("VibeComfy sanitizes dangling and duplicate serialized links before agent handoff", async () => {
  const harness = await createBrowserHarness({
    responses: {
      "/system_stats": {
        status: 200,
        body: { system: { comfyui_frontend_package: "1.39.19" } },
      },
    },
  });

  try {
    const extensionModule = await harness.loadExtension();
    const sanitize = extensionModule.sanitizeSerializedGraphLinks;
    assert.equal(typeof sanitize, "function");

    const graph = {
      nodes: [
        {
          id: 8,
          type: "VAEDecode",
          outputs: [{ name: "IMAGE", links: [15, 17, 18] }],
        },
        {
          id: 9,
          type: "SaveImage",
          inputs: [{ name: "images", link: 21 }],
          outputs: [],
        },
        {
          id: 12,
          type: "vibecomfy.exec",
          inputs: [{ name: "in_0", link: 18 }],
          outputs: [
            { name: "out_0", links: [21] },
            { name: "out_1", links: null },
          ],
          widgets_values: [
            "return {\"image\": image}",
            { inputs: [["image", "IMAGE"]], outputs: [["image", "IMAGE"]] },
          ],
        },
      ],
      links: [
        [15, 8, 0, 11, 0, "IMAGE"],
        [16, 11, 0, 9, 0, "IMAGE"],
        [17, 8, 0, 9, 0, "IMAGE"],
        [18, 8, 0, 12, 0, "IMAGE"],
        [21, 12, 0, 9, 0, "IMAGE"],
      ],
    };

    sanitize(graph);

    const sortedLinks = graph.links.slice().sort((left, right) => left[0] - right[0]);
    assert.deepEqual(sortedLinks, [
      [18, 8, 0, 12, 0, "IMAGE"],
      [21, 12, 0, 9, 0, "IMAGE"],
    ]);
    assert.deepEqual(graph.nodes[0].outputs[0].links, [18]);
    assert.equal(graph.nodes[1].inputs[0].link, 21);
    assert.deepEqual(graph.nodes[2].outputs[0].links, [21]);
  } finally {
    await harness.dispose();
  }
});

// ── Test 1: applyTypedSocketLabelsLabelOnly preserves slot.name (in_i) ────
test("VibeComfy applyTypedSocketLabelsLabelOnly writes slot.label but preserves slot.name (in_i for serialization)", async () => {
  const harness = await createBrowserHarness({
    responses: {
      "/system_stats": {
        status: 200,
        body: { system: { comfyui_frontend_package: "1.39.19" } },
      },
    },
  });

  try {
    const extensionModule = await harness.loadExtension();
    const applyLabelOnly = extensionModule.applyTypedSocketLabelsLabelOnly;
    assert.equal(typeof applyLabelOnly, "function");

    // Two input slots with names in_0, in_1 — these MUST stay unchanged.
    const slots = [
      { name: "in_0", label: "" },
      { name: "in_1", label: "" },
    ];
    const typedEntries = [
      { name: "image", type: "IMAGE" },
      { name: "mask", type: "MASK" },
    ];

    applyLabelOnly(slots, typedEntries);

    // Slot names are NOT rewritten (unlike applyTypedSocketLabels which sets slot.name = label).
    assert.equal(slots[0].name, "in_0", "slot[0].name must stay in_0 for serialization");
    assert.equal(slots[0].label, "image: IMAGE", "slot[0].label must be set");
    assert.equal(slots[1].name, "in_1", "slot[1].name must stay in_1 for serialization");
    assert.equal(slots[1].label, "mask: MASK", "slot[1].label must be set");
  } finally {
    await harness.dispose();
  }
});

// ── Test 2: Safety null/empty inputs ──────────────────────────────────────
test("VibeComfy applyTypedSocketLabelsLabelOnly is safe on null/missing arrays", async () => {
  const harness = await createBrowserHarness({
    responses: {
      "/system_stats": {
        status: 200,
        body: { system: { comfyui_frontend_package: "1.39.19" } },
      },
    },
  });

  try {
    const extensionModule = await harness.loadExtension();
    const applyLabelOnly = extensionModule.applyTypedSocketLabelsLabelOnly;

    // Should not throw on any of these.
    applyLabelOnly(null, []);
    applyLabelOnly([], null);
    applyLabelOnly([], []);
    applyLabelOnly(undefined, [{ name: "x", type: "INT" }]);
    applyLabelOnly([{ name: "in_0" }], undefined);

    // Slot with no label property — must not throw.
    const slot = { name: "in_0" };
    applyLabelOnly([slot], [{ name: "image", type: "IMAGE" }]);
    // No label property existed, so nothing to assert beyond no-throw.
  } finally {
    await harness.dispose();
  }
});

// ── Test 3: Label-only for outputs (out_i names preserved) ────────────────
test("VibeComfy applyTypedSocketLabelsLabelOnly preserves out_i slot names", async () => {
  const harness = await createBrowserHarness({
    responses: {
      "/system_stats": {
        status: 200,
        body: { system: { comfyui_frontend_package: "1.39.19" } },
      },
    },
  });

  try {
    const extensionModule = await harness.loadExtension();
    const applyLabelOnly = extensionModule.applyTypedSocketLabelsLabelOnly;

    const outputs = [
      { name: "out_0", label: "" },
      { name: "out_1", label: "" },
      { name: "out_2", label: "" },
    ];
    const typedOutputs = [
      { name: "result", type: "IMAGE" },
      { name: "preview", type: "IMAGE" },
      { name: "metadata", type: "JSON" },
    ];

    applyLabelOnly(outputs, typedOutputs);

    assert.equal(outputs[0].name, "out_0");
    assert.equal(outputs[0].label, "result: IMAGE");
    assert.equal(outputs[1].name, "out_1");
    assert.equal(outputs[1].label, "preview: IMAGE");
    assert.equal(outputs[2].name, "out_2");
    assert.equal(outputs[2].label, "metadata: JSON");
  } finally {
    await harness.dispose();
  }
});

test("VibeComfy computePreviewDiff carries a trimmed exec preview graph without mutating the candidate graph", async () => {
  const harness = await createBrowserHarness({
    graph: { nodes: [], links: [] },
    responses: {
      "/system_stats": {
        status: 200,
        body: { system: { comfyui_frontend_package: "1.39.19" } },
      },
    },
  });

  try {
    const extensionModule = await harness.loadExtension();
    await harness.setup();

    const candidateGraph = {
      nodes: [
        {
          id: 12,
          type: "vibecomfy.exec",
          inputs: [{ name: "in_0", type: "*", link: null }],
          outputs: Array.from({ length: 16 }, (_, index) => ({
            name: `out_${index}`,
            type: "*",
            links: index === 0 ? [21] : null,
            slot_index: index,
          })),
          widgets_values: [
            "return {\"image\": image}",
            { inputs: [["image", "IMAGE"]], outputs: [["image", "IMAGE"]] },
          ],
          properties: { "Node name for S&R": "vibecomfy.exec", vibecomfy_uid: "exec-1" },
        },
      ],
      links: [],
    };

    const diff = extensionModule.computePreviewDiff(candidateGraph, {
      change: { content_edits: { preserved: [], edited: [], removed_named: [] } },
      recovery: [],
    });

    assert.equal(candidateGraph.nodes[0].outputs.length, 16, "canonical candidate graph must stay untrimmed");
    assert.ok(diff._candidateGraph, "preview diff should carry a decorated candidate graph");
    assert.notEqual(diff._candidateGraph, candidateGraph, "preview graph must be a clone");
    assert.equal(diff._candidateGraph.nodes[0].outputs.length, 1, "preview exec node should be trimmed to declared outputs");
    assert.equal(diff._candidateGraph.nodes[0].outputs[0].name, "out_0");
    assert.equal(diff._candidateGraph.nodes[0].outputs[0].label, "image: IMAGE");
  } finally {
    await harness.dispose();
  }
});

test("VibeComfy normalizeForApply preserves exec links when io widget is empty", async () => {
  const harness = await createBrowserHarness({
    responses: {
      "/system_stats": {
        status: 200,
        body: { system: { comfyui_frontend_package: "1.39.19" } },
      },
    },
  });

  try {
    const extensionModule = await harness.loadExtension();
    assert.equal(typeof extensionModule.normalizeForApply, "function");

    const graph = {
      nodes: [
        {
          id: 6,
          type: "VAEDecode",
          outputs: [{ name: "IMAGE", type: "IMAGE", links: [40] }],
        },
        {
          id: 23,
          type: "vibecomfy.exec",
          inputs: [{ name: "in_0", type: "*", link: 40 }],
          outputs: Array.from({ length: 16 }, (_, index) => ({
            name: `out_${index}`,
            type: "*",
            links: index === 0 ? [41] : null,
            slot_index: index,
          })),
          widgets_values: [
            "def process(in_0):\n    return {\"image\": in_0}",
            {},
          ],
          properties: { "Node name for S&R": "vibecomfy.exec", vibecomfy_uid: "n15" },
        },
        {
          id: 24,
          type: "SaveImage",
          inputs: [{ name: "images", type: "IMAGE", link: 41 }],
          outputs: [],
        },
      ],
      links: [
        [40, 6, 0, 23, 0, "IMAGE"],
        [41, 23, 0, 24, 0, "IMAGE"],
      ],
    };

    extensionModule.normalizeForApply(graph);

    assert.equal(graph.nodes[1].inputs.length, 1, "empty io must not trim away linked exec inputs");
    assert.equal(graph.nodes[1].outputs.length, 16, "empty io must preserve the runtime exec output pool");
    assert.deepEqual(graph.links, [
      [40, 6, 0, 23, 0, "IMAGE"],
      [41, 23, 0, 24, 0, "IMAGE"],
    ]);
    assert.equal(graph.nodes[1].inputs[0].link, 40);
    assert.deepEqual(graph.nodes[1].outputs[0].links, [41]);
  } finally {
    await harness.dispose();
  }
});

test("VibeComfy repair restores empty-io exec links into Map-backed live link stores", async () => {
  const harness = await createBrowserHarness({
    responses: {
      "/system_stats": {
        status: 200,
        body: { system: { comfyui_frontend_package: "1.39.19" } },
      },
    },
  });

  try {
    const extensionModule = await harness.loadExtension();
    assert.equal(typeof extensionModule.repairLiveNodes, "function");

    const source = "def process(in_0):\n    return {\"image\": in_0}";
    const candidateGraph = {
      nodes: [
        {
          id: 6,
          type: "VAEDecode",
          outputs: [{ name: "IMAGE", type: "IMAGE", links: [40] }],
        },
        {
          id: 23,
          type: "vibecomfy.exec",
          inputs: [{ name: "in_0", type: "*", link: 40 }],
          outputs: Array.from({ length: 16 }, (_, index) => ({
            name: `out_${index}`,
            type: "*",
            links: index === 0 ? [41] : null,
            slot_index: index,
          })),
          widgets_values: [source, {}],
          properties: { "Node name for S&R": "vibecomfy.exec", vibecomfy_uid: "n15" },
        },
        {
          id: 24,
          type: "SaveImage",
          inputs: [{ name: "images", type: "IMAGE", link: 41 }],
          outputs: [],
        },
      ],
      links: [
        [40, 6, 0, 23, 0, "IMAGE"],
        [41, 23, 0, 24, 0, "IMAGE"],
      ],
    };

    harness.setCurrentGraph({
      nodes: [
        {
          id: 6,
          type: "VAEDecode",
          outputs: [{ name: "IMAGE", type: "IMAGE", links: null }],
        },
        {
          id: 23,
          type: "vibecomfy.exec",
          inputs: [{ name: "in_0", type: "*", link: null }],
          outputs: Array.from({ length: 16 }, (_, index) => ({
            name: `out_${index}`,
            type: "*",
            links: null,
            slot_index: index,
          })),
          widgets_values: [source, {}],
          properties: { "Node name for S&R": "vibecomfy.exec", vibecomfy_uid: "n15" },
        },
        {
          id: 24,
          type: "SaveImage",
          inputs: [{ name: "images", type: "IMAGE", link: null }],
          outputs: [],
        },
      ],
      links: [],
    });
    harness.app.canvas.graph.links = new Map();

    extensionModule.repairLiveNodes(candidateGraph);

    const liveLinks = harness.getLiveLinks();
    assert.ok(liveLinks instanceof Map, "live link store should remain a Map");
    assert.equal(Object.prototype.hasOwnProperty.call(liveLinks, "40"), false, "must not write link ids as Map object properties");
    assert.equal(Object.prototype.hasOwnProperty.call(liveLinks, "41"), false, "must not write link ids as Map object properties");
    assert.deepEqual(liveLinks.get(40).asSerialisable(), [40, 6, 0, 23, 0, "IMAGE"]);
    assert.deepEqual(liveLinks.get(41).asSerialisable(), [41, 23, 0, 24, 0, "IMAGE"]);

    const execNode = harness.getLiveNodes().find((node) => node.type === "vibecomfy.exec");
    assert.equal(execNode.inputs[0].link, 40);
    assert.deepEqual(execNode.outputs[0].links, [41]);
    assert.equal(execNode.outputs.length, 16, "empty io keeps the physical output pool");
    assert.deepEqual(harness.getLiveNodes().find((node) => node.id === 6).outputs[0].links, [40]);
    assert.equal(harness.getLiveNodes().find((node) => node.id === 24).inputs[0].link, 41);
  } finally {
    await harness.dispose();
  }
});

// ── Test 4: Fewer typed entries than slots — only first N get labels ──────
test("VibeComfy applyTypedSocketLabelsLabelOnly labels only up to typedEntries.length", async () => {
  const harness = await createBrowserHarness({
    responses: {
      "/system_stats": {
        status: 200,
        body: { system: { comfyui_frontend_package: "1.39.19" } },
      },
    },
  });

  try {
    const extensionModule = await harness.loadExtension();
    const applyLabelOnly = extensionModule.applyTypedSocketLabelsLabelOnly;

    // 16 pool slots, only 2 typed entries.
    const slots = Array.from({ length: 16 }, (_, i) => ({ name: `in_${i}`, label: "" }));
    const typedEntries = [
      { name: "image", type: "IMAGE" },
      { name: "mask", type: "MASK" },
    ];

    applyLabelOnly(slots, typedEntries);

    // First 2 get labels.
    assert.equal(slots[0].name, "in_0");
    assert.equal(slots[0].label, "image: IMAGE");
    assert.equal(slots[1].name, "in_1");
    assert.equal(slots[1].label, "mask: MASK");

    // Remaining 14 keep original names and empty labels.
    for (let i = 2; i < 16; i += 1) {
      assert.equal(slots[i].name, `in_${i}`, `slot[${i}].name must stay in_${i}`);
      assert.equal(slots[i].label, "", `slot[${i}].label must stay empty`);
    }
  } finally {
    await harness.dispose();
  }
});

// ── Test 5: Integration — dynamic-IO code node decoration via beforeRegisterNodeDef ──
test("VibeComfy dynamic-IO code node decoration preserves in_i/out_i names, sets labels, hides unused pool slots", async () => {
  const harness = await createBrowserHarness({
    responses: {
      "/system_stats": {
        status: 200,
        body: { system: { comfyui_frontend_package: "1.39.19" } },
      },
    },
  });

  try {
    await harness.loadExtension();
    const extension = harness.getExtension();
    assert.equal(typeof extension.beforeRegisterNodeDef, "function");

    // Build a node type with prototype — beforeRegisterNodeDef patches its onNodeCreated.
    const removedInputs = [];
    const removedOutputs = [];

    // Create the node first so we can bind removeInput/removeOutput directly.
    // decorateIntentNode checks typeof node.removeInput === "function" on the
    // node itself, not via prototype chain.  Plain-object nodes don't have
    // prototype inheritance from nodeType.prototype.
    const node = {
      comfyClass: "VibeComfyCodeIntent",
      type: "vibecomfy.code",
      size: [240, 90],
      properties: {
        vibecomfy_uid: "intent-dyn-1",
        vibecomfy: {
          kind: "code",
          intent: {
            source: "result = image",
            spec: "passthrough with mask",
          },
          io: {
            // 2 inputs, 2 outputs — the "minimal surface" case.
            inputs: [
              ["image", "IMAGE"],
              ["mask", "MASK"],
            ],
            outputs: [
              ["result", "IMAGE"],
              ["preview", "IMAGE"],
            ],
          },
        },
      },
      // 16 input pool slots (in_0..in_15).
      inputs: Array.from({ length: 16 }, (_, i) => ({ name: `in_${i}`, label: "" })),
      // 16 output pool slots (out_0..out_15).
      outputs: Array.from({ length: 16 }, (_, i) => ({ name: `out_${i}`, label: "" })),
      // removeInput/removeOutput must be own properties — decorateIntentNode
      // checks `typeof node.removeInput === "function"` on the node directly.
      removeInput(index) {
        const removed = this.inputs.splice(index, 1)[0];
        removedInputs.push({ index, name: removed?.name });
      },
      removeOutput(index) {
        const removed = this.outputs.splice(index, 1)[0];
        removedOutputs.push({ index, name: removed?.name });
      },
    };

    const nodeType = { prototype: {} };

    // Register the intent node — this patches the prototype's onNodeCreated.
    await extension.beforeRegisterNodeDef(nodeType, { name: "vibecomfy.code" });

    // Call onNodeCreated — this triggers decorateIntentNode internally.
    nodeType.prototype.onNodeCreated.call(node);

    // ── Verify styling ───────────────────────────────────────────────
    assert.equal(node.color, "#2d2643");
    assert.equal(node.bgcolor, "#171229");
    assert.equal(node.boxcolor, "#e39cff");
    assert.equal(node.properties["VibeComfy Intent Kind"], "code");
    assert.equal(node.properties["VibeComfy Intent Badge"], "sandboxed_loose");
    assert.equal(node.properties["VibeComfy Intent Source"], "result = image");
    assert.equal(node.properties["VibeComfy Intent Spec"], "passthrough with mask");

    // ── Verify exactly 2 inputs remain (unused pool slots removed) ───
    assert.equal(node.inputs.length, 2, "exactly 2 input slots visible");

    // Slot names unchanged (in_0, in_1 — serialized keys).
    assert.equal(node.inputs[0].name, "in_0");
    assert.equal(node.inputs[0].label, "image: IMAGE");
    assert.equal(node.inputs[1].name, "in_1");
    assert.equal(node.inputs[1].label, "mask: MASK");

    // ── Verify exactly 2 outputs remain ──────────────────────────────
    assert.equal(node.outputs.length, 2, "exactly 2 output slots visible");

    // Output slot names unchanged (out_0, out_1).
    assert.equal(node.outputs[0].name, "out_0");
    assert.equal(node.outputs[0].label, "result: IMAGE");
    assert.equal(node.outputs[1].name, "out_1");
    assert.equal(node.outputs[1].label, "preview: IMAGE");

    // ── Verify removal was backward-walk (14 slots removed each side) ──
    // removeInput called from index 15 down to 2 → 14 calls.
    assert.equal(removedInputs.length, 14, "14 unused input pool slots removed");
    // First removal should be index 15 (walking backwards).
    assert.equal(removedInputs[0].index, 15);
    assert.equal(removedInputs[0].name, "in_15");
    // Last removal should be index 2.
    assert.equal(removedInputs[13].index, 2);
    assert.equal(removedInputs[13].name, "in_2");

    assert.equal(removedOutputs.length, 14, "14 unused output pool slots removed");
    assert.equal(removedOutputs[0].index, 15);
    assert.equal(removedOutputs[0].name, "out_15");
    assert.equal(removedOutputs[13].index, 2);
    assert.equal(removedOutputs[13].name, "out_2");

    // ── Verify properties.vibecomfy.io is preserved ──────────────────
    assert.deepEqual(node.properties.vibecomfy.io, {
      inputs: [
        ["image", "IMAGE"],
        ["mask", "MASK"],
      ],
      outputs: [
        ["result", "IMAGE"],
        ["preview", "IMAGE"],
      ],
    });

    // ── Verify __vibecomfyIntentMeta is set ──────────────────────────
    assert.ok(node.__vibecomfyIntentMeta);
    assert.equal(node.__vibecomfyIntentMeta.classType, "vibecomfy.code");
    assert.equal(node.__vibecomfyIntentMeta.kind, "code");
    assert.deepEqual(node.__vibecomfyIntentMeta.typedInputs, [
      { name: "image", type: "IMAGE" },
      { name: "mask", type: "MASK" },
    ]);
    assert.deepEqual(node.__vibecomfyIntentMeta.typedOutputs, [
      { name: "result", type: "IMAGE" },
      { name: "preview", type: "IMAGE" },
    ]);
  } finally {
    await harness.dispose();
  }
});

// ── Test 6: Non-dynamic-IO (loop) node still gets full name+label ─────────
test("VibeComfy non-dynamic-IO loop node still uses applyTypedSocketLabels (name=label)", async () => {
  const harness = await createBrowserHarness({
    responses: {
      "/system_stats": {
        status: 200,
        body: { system: { comfyui_frontend_package: "1.39.19" } },
      },
    },
  });

  try {
    await harness.loadExtension();
    const extension = harness.getExtension();

    const nodeType = { prototype: {} };
    await extension.beforeRegisterNodeDef(nodeType, { name: "vibecomfy.loop" });

    // Loop node — does NOT have comfyClass="VibeComfyCodeIntent".
    const loopNode = {
      type: "vibecomfy.loop",
      size: [240, 90],
      properties: {
        vibecomfy_uid: "loop-1",
        vibecomfy: {
          kind: "loop",
          intent: {
            source: "for i in range(3): pass",
            spec: "loop 3 times",
          },
          io: {
            inputs: [["image", "IMAGE"]],
            outputs: [["result", "IMAGE"]],
          },
        },
      },
      inputs: [{ name: "in_0" }],
      outputs: [{ name: "out_0" }],
    };

    nodeType.prototype.onNodeCreated.call(loopNode);

    // Loop nodes use applyTypedSocketLabels → slot.name = label.
    assert.equal(loopNode.inputs[0].name, "image: IMAGE");
    assert.equal(loopNode.inputs[0].label, "image: IMAGE");
    assert.equal(loopNode.outputs[0].name, "result: IMAGE");
    assert.equal(loopNode.outputs[0].label, "result: IMAGE");
  } finally {
    await harness.dispose();
  }
});

// ── Test 7: Dynamic-IO detection is class_type-based (vibecomfy.code) ────────
test("VibeComfy dynamic-IO detection uses class_type (vibecomfy.code) — all code nodes are dynamic-IO regardless of comfyClass", async () => {
  const harness = await createBrowserHarness({
    responses: {
      "/system_stats": {
        status: 200,
        body: { system: { comfyui_frontend_package: "1.39.19" } },
      },
    },
  });

  try {
    await harness.loadExtension();
    const extension = harness.getExtension();

    // A node with vibecomfy.code type and NO comfyClass is still treated as
    // dynamic-IO — _isDynamicIoCodeNode checks class_type (node.type), not comfyClass.
    const nodeType = { prototype: {} };
    await extension.beforeRegisterNodeDef(nodeType, { name: "vibecomfy.code" });

    const codeNodeNoComfyClass = {
      type: "vibecomfy.code",
      // NO comfyClass — dynamic-IO fires anyway via class_type check.
      size: [240, 90],
      properties: {
        vibecomfy_uid: "intent-old-1",
        vibecomfy: {
          kind: "code",
          intent: {
            source: "value = 1 + 1",
            spec: "compute",
          },
          io: {
            inputs: [["x", "INT"]],
            outputs: [["y", "INT"]],
          },
        },
      },
      inputs: [{ name: "value" }],
      outputs: [{ name: "value" }],
    };

    nodeType.prototype.onNodeCreated.call(codeNodeNoComfyClass);

    // Dynamic-IO path: slot.name preserved (in_i serialization key), slot.label set.
    assert.equal(codeNodeNoComfyClass.inputs[0].name, "value");
    assert.equal(codeNodeNoComfyClass.inputs[0].label, "x: INT");
    assert.equal(codeNodeNoComfyClass.outputs[0].name, "value");
    assert.equal(codeNodeNoComfyClass.outputs[0].label, "y: INT");

    // Badge is set correctly.
    assert.equal(codeNodeNoComfyClass.properties["VibeComfy Intent Badge"], "sandboxed_loose");
  } finally {
    await harness.dispose();
  }
});

test("VibeComfy exec nodes derive dynamic IO from widgets_values and hide unused pool slots", async () => {
  const harness = await createBrowserHarness({
    responses: {
      "/system_stats": {
        status: 200,
        body: { system: { comfyui_frontend_package: "1.39.19" } },
      },
    },
  });

  try {
    await harness.loadExtension();
    const extension = harness.getExtension();

    const nodeType = { prototype: {} };
    await extension.beforeRegisterNodeDef(nodeType, { name: "vibecomfy.exec" });

    const removedInputs = [];
    const removedOutputs = [];
    const execNode = {
      type: "vibecomfy.exec",
      properties: {
        vibecomfy_uid: "exec-1",
        "Node name for S&R": "vibecomfy.exec",
      },
      widgets_values: [
        "return {\"image\": image}",
        { inputs: [["image", "IMAGE"]], outputs: [["image", "IMAGE"]] },
      ],
      inputs: Array.from({ length: 16 }, (_, i) => ({ name: `in_${i}`, label: "", type: "*" })),
      outputs: Array.from({ length: 16 }, (_, i) => ({ name: `out_${i}`, label: "", type: "*" })),
      removeInput(index) {
        const removed = this.inputs.splice(index, 1)[0];
        removedInputs.push({ index, name: removed?.name });
      },
      removeOutput(index) {
        const removed = this.outputs.splice(index, 1)[0];
        removedOutputs.push({ index, name: removed?.name });
      },
    };

    nodeType.prototype.onNodeCreated.call(execNode);

    assert.equal(execNode.inputs.length, 1);
    assert.equal(execNode.inputs[0].name, "in_0");
    assert.equal(execNode.inputs[0].label, "image: IMAGE");
    assert.equal(execNode.inputs[0].type, "IMAGE");
    assert.equal(execNode.outputs.length, 1);
    assert.equal(execNode.outputs[0].name, "out_0");
    assert.equal(execNode.outputs[0].label, "image: IMAGE");
    assert.equal(execNode.outputs[0].type, "IMAGE");
    assert.equal(removedInputs.length, 15);
    assert.equal(removedOutputs.length, 15);
    assert.equal(execNode.__vibecomfyIntentMeta.classType, "vibecomfy.exec");
    assert.deepEqual(execNode.__vibecomfyIntentMeta.typedInputs, [{ name: "image", type: "IMAGE" }]);
    assert.deepEqual(execNode.__vibecomfyIntentMeta.typedOutputs, [{ name: "image", type: "IMAGE" }]);

    const previewPayloadNode = {
      type: "vibecomfy.exec",
      properties: {
        vibecomfy_uid: "exec-preview-1",
        "Node name for S&R": "vibecomfy.exec",
      },
      widgets_values: [
        "return {\"image\": image}",
        { inputs: [["image", "IMAGE"]], outputs: [["image", "IMAGE"]] },
      ],
      inputs: Array.from({ length: 16 }, (_, i) => ({ name: `in_${i}`, label: "", type: "*" })),
      outputs: Array.from({ length: 16 }, (_, i) => ({ name: `out_${i}`, label: "", type: "*" })),
    };

    nodeType.prototype.onNodeCreated.call(previewPayloadNode);

    assert.equal(previewPayloadNode.inputs.length, 1);
    assert.equal(previewPayloadNode.inputs[0].type, "IMAGE");
    assert.equal(previewPayloadNode.outputs.length, 1);
    assert.equal(previewPayloadNode.outputs[0].name, "out_0");
    assert.equal(previewPayloadNode.outputs[0].label, "image: IMAGE");
    assert.equal(previewPayloadNode.outputs[0].type, "IMAGE");

    const earlyHydrationNode = {
      type: "vibecomfy.exec",
      properties: {
        vibecomfy_uid: "exec-early-1",
        "Node name for S&R": "vibecomfy.exec",
      },
      inputs: Array.from({ length: 16 }, (_, i) => ({ name: `in_${i}`, label: "", type: "*", link: i === 0 ? 42 : null })),
      outputs: Array.from({ length: 16 }, (_, i) => ({ name: `out_${i}`, label: "", type: "*", links: i === 0 ? [43] : null })),
      removeInput(index) {
        this.inputs.splice(index, 1);
      },
      removeOutput(index) {
        this.outputs.splice(index, 1);
      },
    };

    nodeType.prototype.onNodeCreated.call(earlyHydrationNode);

    assert.equal(earlyHydrationNode.inputs.length, 16);
    assert.equal(earlyHydrationNode.outputs.length, 16);
    assert.equal(earlyHydrationNode.inputs[0].link, 42);
    assert.deepEqual(earlyHydrationNode.outputs[0].links, [43]);
  } finally {
    await harness.dispose();
  }
});

test("VibeComfy exec nodes accept name-to-type dict in io widget", async () => {
  const harness = await createBrowserHarness({
    responses: {
      "/system_stats": {
        status: 200,
        body: { system: { comfyui_frontend_package: "1.39.19" } },
      },
    },
  });

  try {
    await harness.loadExtension();
    const extension = harness.getExtension();

    const nodeType = { prototype: {} };
    await extension.beforeRegisterNodeDef(nodeType, { name: "vibecomfy.exec" });

    const removedOutputs = [];
    const execNode = {
      type: "vibecomfy.exec",
      properties: {
        vibecomfy_uid: "exec-dict-io",
        "Node name for S&R": "vibecomfy.exec",
      },
      widgets_values: [
        "return {\"image\": image}",
        { inputs: { image: "IMAGE" }, outputs: { image: "IMAGE" } },
      ],
      inputs: Array.from({ length: 16 }, (_, i) => ({ name: `in_${i}`, label: "", type: "*" })),
      outputs: Array.from({ length: 16 }, (_, i) => ({ name: `out_${i}`, label: "", type: "*" })),
      removeInput(index) {
        this.inputs.splice(index, 1);
      },
      removeOutput(index) {
        const removed = this.outputs.splice(index, 1)[0];
        removedOutputs.push({ index, name: removed?.name });
      },
    };

    nodeType.prototype.onNodeCreated.call(execNode);

    assert.equal(execNode.inputs.length, 1);
    assert.equal(execNode.inputs[0].name, "in_0");
    assert.equal(execNode.inputs[0].label, "image: IMAGE");
    assert.equal(execNode.inputs[0].type, "IMAGE");
    assert.equal(execNode.outputs.length, 1);
    assert.equal(execNode.outputs[0].name, "out_0");
    assert.equal(execNode.outputs[0].label, "image: IMAGE");
    assert.equal(execNode.outputs[0].type, "IMAGE");
    assert.equal(removedOutputs.length, 15);
  } finally {
    await harness.dispose();
  }
});

test("VibeComfy exec serialization repair restores missing io from typed socket labels", async () => {
  const harness = await createBrowserHarness({
    responses: {
      "/system_stats": {
        status: 200,
        body: { system: { comfyui_frontend_package: "1.39.19" } },
      },
    },
  });

  try {
    const extensionModule = await harness.loadExtension();
    const repairExec = extensionModule.normalizeExecNodeForSerialization;
    assert.equal(typeof repairExec, "function");

    const execNode = {
      type: "vibecomfy.exec",
      properties: {
        vibecomfy_uid: "exec-lost-io",
        "Node name for S&R": "vibecomfy.exec",
        "VibeComfy Intent Source": "return {\"image\": processed}",
      },
      widgets_values: ["return {\"image\": processed}"],
      inputs: [{ name: "in_0", label: "image: IMAGE", type: "*", link: 15 }],
      outputs: [{ name: "out_0", label: "image: IMAGE", type: "*", links: [16] }],
    };

    assert.equal(repairExec(execNode), true);

    assert.deepEqual(execNode.widgets_values, [
      "return {\"image\": processed}",
      { inputs: [["image", "IMAGE"]], outputs: [["image", "IMAGE"]] },
    ]);
    assert.deepEqual(execNode.properties.vibecomfy.io, {
      inputs: [["image", "IMAGE"]],
      outputs: [["image", "IMAGE"]],
    });
    assert.equal(execNode.properties.vibecomfy.kind, "code");
    assert.equal(execNode.properties.vibecomfy.intent.source, "return {\"image\": processed}");
  } finally {
    await harness.dispose();
  }
});

test("VibeComfy candidate graph preparation trims stale exec port pools before preview", async () => {
  const harness = await createBrowserHarness({
    responses: {
      "/system_stats": {
        status: 200,
        body: { system: { comfyui_frontend_package: "1.39.19" } },
      },
    },
  });

  try {
    const extensionModule = await harness.loadExtension();
    const prepareCandidateGraph = extensionModule.prepareCandidateGraphForPanel;
    assert.equal(typeof prepareCandidateGraph, "function");

    const source = "return {\"image\": in_0}";
    const graph = {
      nodes: [
        { id: 2, type: "VAEDecode", outputs: [{ name: "IMAGE", type: "IMAGE", links: [1] }] },
        {
          id: 1,
          type: "vibecomfy.exec",
          inputs: [{ name: "in_0", type: "*", link: 1 }],
          outputs: Array.from({ length: 16 }, (_, index) => ({
            name: `out_${index}`,
            type: "*",
            links: index === 0 ? [2] : null,
            slot_index: index,
          })),
          widgets_values: [
            source,
            { inputs: [["image", "IMAGE"]], outputs: [["image", "IMAGE"]] },
          ],
          properties: {
            "Node name for S&R": "vibecomfy.exec",
            vibecomfy_uid: "exec-1",
          },
        },
        { id: 3, type: "SaveImage", inputs: [{ name: "images", type: "IMAGE", link: 2 }] },
      ],
      links: [[1, 2, 0, 1, 0, "IMAGE"], [2, 1, 0, 3, 0, "IMAGE"]],
    };

    const prepared = prepareCandidateGraph(graph);
    const execNode = prepared.nodes.find((node) => node.type === "vibecomfy.exec");

    assert.equal(execNode.inputs.length, 1);
    assert.equal(execNode.inputs[0].name, "in_0");
    assert.equal(execNode.inputs[0].label, "image: IMAGE");
    assert.equal(execNode.inputs[0].type, "IMAGE");
    assert.equal(execNode.inputs[0].link, 1);
    assert.equal(execNode.outputs.length, 1);
    assert.equal(execNode.outputs[0].name, "out_0");
    assert.equal(execNode.outputs[0].label, "image: IMAGE");
    assert.equal(execNode.outputs[0].type, "IMAGE");
    assert.deepEqual(execNode.outputs[0].links, [2]);
    assert.equal(execNode.properties.vibecomfy_intent_badge, "sandboxed_loose");
    assert.deepEqual(execNode.properties.vibecomfy.io, {
      inputs: [["image", "IMAGE"]],
      outputs: [["image", "IMAGE"]],
    });
    assert.equal(graph.nodes[1].outputs.length, 16, "preparation should not mutate the raw response graph");
  } finally {
    await harness.dispose();
  }
});

test("VibeComfy live graph repair restores exec input links dropped by ComfyUI configure", async () => {
  const harness = await createBrowserHarness({
    withGraphMutation: true,
    responses: {
      "/system_stats": {
        status: 200,
        body: { system: { comfyui_frontend_package: "1.39.19" } },
      },
    },
  });

  try {
    const extensionModule = await harness.loadExtension();
    const prepareCandidateGraph = extensionModule.prepareCandidateGraphForPanel;
    const repairLive = extensionModule.repairLiveIntentNodesFromCandidate;
    assert.equal(typeof prepareCandidateGraph, "function");
    assert.equal(typeof repairLive, "function");

    const source = "return {\"image\": in_0}";
    const rawCandidate = {
      nodes: [
        {
          id: 8,
          type: "VAEDecode",
          outputs: [{ name: "IMAGE", type: "IMAGE", links: [43] }],
        },
        {
          id: 19,
          type: "vibecomfy.exec",
          inputs: [{ name: "in_0", type: "*", link: 43 }],
          outputs: Array.from({ length: 16 }, (_, index) => ({
            name: `out_${index}`,
            type: "*",
            links: index === 0 ? [44] : null,
          })),
          widgets_values: [
            source,
            { inputs: [["image", "IMAGE"]], outputs: [["image", "IMAGE"]] },
          ],
          properties: {
            "Node name for S&R": "vibecomfy.exec",
            vibecomfy_uid: "pilprocess",
          },
        },
        {
          id: 9,
          type: "SaveImage",
          inputs: [{ name: "images", type: "IMAGE", link: 44 }],
        },
      ],
      links: [[43, 8, 0, 19, 0, "IMAGE"], [44, 19, 0, 9, 0, "IMAGE"]],
    };
    const candidate = prepareCandidateGraph(rawCandidate);

    harness.setCurrentGraph({
      nodes: [
        {
          id: 8,
          type: "VAEDecode",
          outputs: [{ name: "IMAGE", type: "IMAGE", links: null }],
        },
        {
          id: 19,
          type: "vibecomfy.exec",
          inputs: [{ name: "io", label: "image: IMAGE", type: "IMAGE", link: null }],
          outputs: [{ name: "out_0", label: "image: IMAGE", type: "IMAGE", links: [44] }],
          widgets_values: [source],
          properties: {
            "Node name for S&R": "vibecomfy.exec",
            vibecomfy_uid: "pilprocess",
            vibecomfy: {
              kind: "code",
              io: { inputs: [["image", "IMAGE"]], outputs: [["image", "IMAGE"]] },
              intent: { source },
            },
          },
        },
        {
          id: 9,
          type: "SaveImage",
          inputs: [{ name: "images", type: "IMAGE", link: 44 }],
        },
      ],
      links: [{ id: 44, origin_id: 19, origin_slot: 0, target_id: 9, target_slot: 0, type: "IMAGE" }],
    });

    repairLive(candidate);

    const execNode = harness.getLiveNodes().find((node) => node.type === "vibecomfy.exec");
    assert.equal(execNode.inputs.length, 1);
    assert.equal(execNode.inputs[0].name, "in_0");
    assert.equal(execNode.inputs[0].label, "image: IMAGE");
    assert.equal(execNode.inputs[0].type, "IMAGE");
    assert.equal(execNode.inputs[0].link, 43);
    assert.equal(execNode.outputs.length, 1);
    assert.deepEqual(execNode.outputs[0].links, [44]);

    const liveLinks = harness.getLiveLinks();
    assert.deepEqual(liveLinks["43"], {
      id: 43,
      origin_id: 8,
      origin_slot: 0,
      target_id: 19,
      target_slot: 0,
      type: "IMAGE",
    });
    assert.deepEqual(harness.getLiveNodes()[0].outputs[0].links, [43]);
  } finally {
    await harness.dispose();
  }
});

test("VibeComfy loadGraphData fallback repairs dynamic exec links after async ComfyUI import", async () => {
  const harness = await createBrowserHarness({
    withGraphMutation: true,
    responses: {
      "/system_stats": {
        status: 200,
        body: { system: { comfyui_frontend_package: "1.39.19" } },
      },
    },
  });

  try {
    const source = "return {\"image\": in_0}";
    const candidate = {
      nodes: [
        { id: 8, type: "VAEDecode", outputs: [{ name: "IMAGE", type: "IMAGE", links: [43] }] },
        {
          id: 19,
          type: "vibecomfy.exec",
          inputs: [{ name: "in_0", type: "IMAGE", label: "image: IMAGE", link: 43 }],
          outputs: [{ name: "out_0", type: "IMAGE", label: "image: IMAGE", links: [44], slot_index: 0 }],
          widgets_values: [
            source,
            { inputs: [["image", "IMAGE"]], outputs: [["image", "IMAGE"]] },
          ],
          properties: {
            "Node name for S&R": "vibecomfy.exec",
            vibecomfy_uid: "pilprocess",
          },
        },
        { id: 9, type: "SaveImage", inputs: [{ name: "images", type: "IMAGE", link: 44 }] },
      ],
      links: [[43, 8, 0, 19, 0, "IMAGE"], [44, 19, 0, 9, 0, "IMAGE"]],
    };
    const badImportedGraph = {
      nodes: [
        { id: 8, type: "VAEDecode", outputs: [{ name: "IMAGE", type: "IMAGE", links: null }] },
        {
          id: 19,
          type: "vibecomfy.exec",
          inputs: [{ name: "io", type: "IMAGE", label: "image: IMAGE", link: null }],
          outputs: [{ name: "out_0", type: "IMAGE", label: "image: IMAGE", links: [44], slot_index: 0 }],
          widgets_values: [source],
          properties: {
            "Node name for S&R": "vibecomfy.exec",
            vibecomfy_uid: "pilprocess",
            vibecomfy: {
              kind: "code",
              io: { inputs: [["image", "IMAGE"]], outputs: [["image", "IMAGE"]] },
              intent: { source },
            },
          },
        },
        { id: 9, type: "SaveImage", inputs: [{ name: "images", type: "IMAGE", link: 44 }] },
      ],
      links: [{ id: 44, origin_id: 19, origin_slot: 0, target_id: 9, target_slot: 0, type: "IMAGE" }],
    };

    harness.app.loadGraphData = async function asyncBadComfyImport() {
      await Promise.resolve();
      harness.setCurrentGraph(badImportedGraph);
    };

    await harness.loadExtension();
    await harness.setup();
    await harness.app.loadGraphData(candidate);

    const execNode = harness.getLiveNodes().find((node) => node.type === "vibecomfy.exec");
    assert.equal(execNode.inputs[0].name, "in_0");
    assert.equal(execNode.inputs[0].link, 43);
    assert.deepEqual(harness.getLiveLinks()["43"].asSerialisable(), [43, 8, 0, 19, 0, "IMAGE"]);
    assert.doesNotThrow(() => harness.app.canvas.graph.remove(execNode));
    assert.equal(
      harness.getLiveNodes().some((node) => node.type === "vibecomfy.exec"),
      false,
      "refreshed exec node should remain deletable after live-link repair",
    );
  } finally {
    await harness.dispose();
  }
});

// ── Test: Full lifecycle through all four facades with native-shape assertions ──
test("VibeComfy full lifecycle (display→serialize→apply→repair) preserves dynamic-IO shape and uses proper prototypes", async () => {
  const harness = await createBrowserHarness({
    withGraphMutation: true,
    responses: {
      "/system_stats": {
        status: 200,
        body: { system: { comfyui_frontend_package: "1.39.19" } },
      },
    },
  });

  try {
    const extensionModule = await harness.loadExtension();
    const normalizeForDisplay = extensionModule.normalizeForDisplay;
    const normalizeForSerialize = extensionModule.normalizeForSerialize;
    const normalizeForApply = extensionModule.normalizeForApply;
    const repairLiveNodes = extensionModule.repairLiveNodes;
    assert.equal(typeof normalizeForDisplay, "function");
    assert.equal(typeof normalizeForSerialize, "function");
    assert.equal(typeof normalizeForApply, "function");
    assert.equal(typeof repairLiveNodes, "function");

    // ── Setup: exec node with 16-port pool and typed IO declaring 2in/1out ──
    const source = "return {\"image\": image, \"latent\": latent}";
    const typedIo = {
      inputs: [["image", "IMAGE"], ["latent", "LATENT"]],
      outputs: [["result", "IMAGE"]],
    };

    // ── Phase 1: DISPLAY — normalizeForDisplay via beforeRegisterNodeDef ──
    await harness.loadExtension();
    const extension = harness.getExtension();

    const nodeType = { prototype: {} };
    await extension.beforeRegisterNodeDef(nodeType, { name: "vibecomfy.exec" });

    const removedInputs = [];
    const removedOutputs = [];
    const execNode = {
      type: "vibecomfy.exec",
      size: [240, 90],
      properties: {
        vibecomfy_uid: "lifecycle-exec-1",
        "Node name for S&R": "vibecomfy.exec",
      },
      widgets_values: [
        source,
        typedIo,
      ],
      inputs: Array.from({ length: 16 }, (_, i) => ({
        name: `in_${i}`, label: "", type: "*",
      })),
      outputs: Array.from({ length: 16 }, (_, i) => ({
        name: `out_${i}`, label: "", type: "*",
      })),
      removeInput(index) {
        const removed = this.inputs.splice(index, 1)[0];
        removedInputs.push({ index, name: removed?.name });
      },
      removeOutput(index) {
        const removed = this.outputs.splice(index, 1)[0];
        removedOutputs.push({ index, name: removed?.name });
      },
    };

    nodeType.prototype.onNodeCreated.call(execNode);

    // Native-shape: verify inputs/outputs are Array instances (not plain objects)
    assert.ok(execNode.inputs instanceof Array, "inputs must be Array instance after display normalize");
    assert.ok(execNode.outputs instanceof Array, "outputs must be Array instance after display normalize");
    assert.equal(Object.getPrototypeOf(execNode.inputs), Array.prototype, "inputs must have Array.prototype");
    assert.equal(Object.getPrototypeOf(execNode.outputs), Array.prototype, "outputs must have Array.prototype");

    // Verify correct port counts (2 in, 1 out — NOT the 16-port pool)
    assert.equal(execNode.inputs.length, 2, "display normalize: 2 typed inputs, not 16-port pool");
    assert.equal(execNode.outputs.length, 1, "display normalize: 1 typed output, not 16-port pool");
    assert.equal(execNode.inputs[0].name, "in_0");
    assert.equal(execNode.inputs[0].label, "image: IMAGE");
    assert.equal(execNode.inputs[0].type, "IMAGE");
    assert.equal(execNode.inputs[1].name, "in_1");
    assert.equal(execNode.inputs[1].label, "latent: LATENT");
    assert.equal(execNode.inputs[1].type, "LATENT");
    assert.equal(execNode.outputs[0].name, "out_0");
    assert.equal(execNode.outputs[0].label, "result: IMAGE");
    assert.equal(execNode.outputs[0].type, "IMAGE");
    // Verify removal was backward walk (16→2 = 14 input, 16→1 = 15 output)
    assert.equal(removedInputs.length, 14, "14 unused input pool slots removed (indices 15→2)");
    assert.equal(removedOutputs.length, 15, "15 unused output pool slots removed (indices 15→1)");
    assert.equal(removedInputs[0].index, 15);
    assert.equal(removedOutputs[0].index, 15);

    // ── Phase 2: SERIALIZE — normalizeForSerialize (payload mode) ──
    const rawGraph = {
      nodes: [
        {
          id: 1,
          type: "vibecomfy.exec",
          widgets_values: [source, typedIo],
          inputs: Array.from({ length: 16 }, (_, i) => ({ name: `in_${i}`, type: "*" })),
          outputs: Array.from({ length: 16 }, (_, i) => ({
            name: `out_${i}`, type: "*", links: i === 0 ? [99] : null,
          })),
          properties: {
            vibecomfy_uid: "lifecycle-exec-2",
            "Node name for S&R": "vibecomfy.exec",
          },
        },
        { id: 2, type: "SaveImage", inputs: [{ name: "images", link: 99 }] },
      ],
      links: [
        [99, 1, 0, 2, 0, "IMAGE"],
        [88, 99, 0, 1, 0, "IMAGE"], // dangling: target 99 doesn't exist
        [77, 1, 0, 2, 0, "IMAGE"],  // duplicate: same src→dst as 99
      ],
    };

    normalizeForSerialize(rawGraph);

    // Native-shape: serialize must produce proper Array links
    assert.ok(rawGraph.links instanceof Array, "links must be Array instance after serialize");
    assert.equal(Object.getPrototypeOf(rawGraph.links), Array.prototype);

    // Dangling/duplicate links removed
    assert.equal(rawGraph.links.length, 1, "only the valid link survives");
    const execSerialized = rawGraph.nodes[0];
    // Native-shape: check that inputs/outputs on serialized node are proper Arrays
    assert.ok(execSerialized.inputs instanceof Array, "serialized inputs must be Array");
    assert.ok(execSerialized.outputs instanceof Array, "serialized outputs must be Array");
    // The exec node should have been normalized: typed IO restored, ports reflect actual count
    // (normalizeExecNodeForSerialization runs inside normalizeForSerialize payload path)
    assert.deepEqual(execSerialized.widgets_values, [source, typedIo]);
    // After normalization, the node itself may still have the original pool slots;
    // the key validation is that the graph-level links are sanitized and
    // the exec node's widgets_values carry the typed IO for downstream consumers.
    assert.equal(rawGraph.nodes[1].inputs[0].link, 99);

    // ── Phase 3: APPLY — normalizeForApply prepares candidate for configure ──
    const candidateGraph = {
      nodes: [
        {
          id: 10,
          type: "vibecomfy.exec",
          widgets_values: [source, typedIo],
          inputs: Array.from({ length: 16 }, (_, i) => ({
            name: `in_${i}`, type: "*", link: i === 0 ? 55 : null,
          })),
          outputs: Array.from({ length: 16 }, (_, i) => ({
            name: `out_${i}`, type: "*", links: i === 0 ? [56] : null,
          })),
          properties: {
            vibecomfy_uid: "lifecycle-exec-3",
            "Node name for S&R": "vibecomfy.exec",
          },
        },
        { id: 11, type: "VAEDecode", outputs: [{ name: "IMAGE", type: "IMAGE", links: [55] }] },
        { id: 12, type: "SaveImage", inputs: [{ name: "images", type: "IMAGE", link: 56 }] },
      ],
      links: [
        [55, 11, 0, 10, 0, "IMAGE"],
        [56, 10, 0, 12, 0, "IMAGE"],
      ],
    };

    normalizeForApply(candidateGraph);

    // Native-shape: apply must produce Arrays for links
    assert.ok(candidateGraph.links instanceof Array, "links must be Array after apply");
    // The exec node in the candidate gets normalized by decorateIntentGraphPayload
    const applyExec = candidateGraph.nodes[0];
    assert.ok(applyExec.inputs instanceof Array, "apply inputs must be Array");
    assert.ok(applyExec.outputs instanceof Array, "apply outputs must be Array");
    // normalizeForApply calls decorateIntentGraphPayload which calls decorateIntentNode,
    // but on plain payload objects (not live LiteGraph nodes), the removeInput/removeOutput
    // path won't fire. The key contract is that normalizeExecNodeForSerialization runs first,
    // ensuring widgets_values carries typed IO.
    assert.deepEqual(applyExec.widgets_values, [source, typedIo]);
    // Links survive sanitizeSerializedGraphLinks
    assert.equal(candidateGraph.links.length, 2);

    // ── Phase 4: REPAIR — repairLiveNodes restores live graph after configure ──
    // Simulate: ComfyUI configure drops input links and mangles slot names
    const postConfigureGraph = {
      nodes: [
        {
          id: 10,
          type: "vibecomfy.exec",
          inputs: [{ name: "io", label: "image: IMAGE", type: "IMAGE", link: null }],
          outputs: [{ name: "out_0", label: "result: IMAGE", type: "IMAGE", links: [56] }],
          widgets_values: [source],
          properties: {
            vibecomfy_uid: "lifecycle-exec-3",
            "Node name for S&R": "vibecomfy.exec",
            vibecomfy: {
              kind: "code",
              io: typedIo,
              intent: { source },
            },
          },
        },
        { id: 11, type: "VAEDecode", outputs: [{ name: "IMAGE", type: "IMAGE", links: null }] },
        { id: 12, type: "SaveImage", inputs: [{ name: "images", type: "IMAGE", link: 56 }] },
      ],
      links: [{ id: 56, origin_id: 10, origin_slot: 0, target_id: 12, target_slot: 0, type: "IMAGE" }],
    };
    harness.setCurrentGraph(postConfigureGraph);

    // Prepare the candidate (all nodes needed for link restoration)
    const repairCandidate = {
      nodes: [
        {
          id: 11,
          type: "VAEDecode",
          outputs: [{ name: "IMAGE", type: "IMAGE", links: [55] }],
        },
        {
          id: 10,
          type: "vibecomfy.exec",
          inputs: [{ name: "in_0", label: "image: IMAGE", type: "IMAGE", link: 55 }],
          outputs: [{ name: "out_0", label: "result: IMAGE", type: "IMAGE", links: [56], slot_index: 0 }],
          widgets_values: [source, typedIo],
          properties: {
            vibecomfy_uid: "lifecycle-exec-3",
            "Node name for S&R": "vibecomfy.exec",
          },
        },
        {
          id: 12,
          type: "SaveImage",
          inputs: [{ name: "images", type: "IMAGE", link: 56 }],
        },
      ],
      links: [[55, 11, 0, 10, 0, "IMAGE"], [56, 10, 0, 12, 0, "IMAGE"]],
    };

    repairLiveNodes(repairCandidate);

    // Verify the live exec node was repaired
    const liveExec = harness.getLiveNodes().find((n) => n.type === "vibecomfy.exec");
    assert.ok(liveExec, "exec node must exist in live graph after repair");

    // Native-shape: live node inputs/outputs must be Arrays of proper prototype
    assert.ok(liveExec.inputs instanceof Array, "repaired inputs must be Array instance");
    assert.ok(liveExec.outputs instanceof Array, "repaired outputs must be Array instance");
    assert.equal(Object.getPrototypeOf(liveExec.inputs), Array.prototype);
    assert.equal(Object.getPrototypeOf(liveExec.outputs), Array.prototype);

    // Port counts match typed IO (1 input, 1 output — NOT 16-port pool)
    assert.equal(liveExec.inputs.length, 1, "repair: 1 input after dynamic slot replacement, not pool");
    assert.equal(liveExec.outputs.length, 1, "repair: 1 output after dynamic slot replacement, not pool");
    assert.equal(liveExec.inputs[0].name, "in_0");
    assert.equal(liveExec.inputs[0].label, "image: IMAGE");
    assert.equal(liveExec.inputs[0].type, "IMAGE");
    assert.equal(liveExec.inputs[0].link, 55, "dropped input link restored by repair");
    assert.equal(liveExec.outputs[0].name, "out_0");
    assert.equal(liveExec.outputs[0].label, "result: IMAGE");
    assert.equal(liveExec.outputs[0].type, "IMAGE");
    assert.deepEqual(liveExec.outputs[0].links, [56]);

    // Native-shape: cloned slots must have `serialize` as an own (non-inherited) method
    // (cloneDynamicSlot stamps `serialize` via Object.defineProperty on the slot itself)
    assert.ok(
      Object.prototype.hasOwnProperty.call(liveExec.inputs[0], "serialize")
        || Object.getOwnPropertyDescriptor(liveExec.inputs[0], "serialize") !== undefined,
      "repaired input slot must carry own serialize method (not prototype-inherited)",
    );
    assert.ok(
      Object.prototype.hasOwnProperty.call(liveExec.outputs[0], "serialize")
        || Object.getOwnPropertyDescriptor(liveExec.outputs[0], "serialize") !== undefined,
      "repaired output slot must carry own serialize method (not prototype-inherited)",
    );

    // Verify the upstream node's output links were also repaired
    const upstreamNode = harness.getLiveNodes().find((n) => n.id === 11);
    assert.ok(upstreamNode, "upstream VAEDecode must exist");
    assert.deepEqual(upstreamNode.outputs[0].links, [55], "upstream output links restored");

    // Verify live links contain the restored link
    const liveLinks = harness.getLiveLinks();
    assert.ok(liveLinks["55"], "restored link 55 must exist in live link store");
    assert.equal(liveLinks["55"].origin_id, 11);
    assert.equal(liveLinks["55"].target_id, 10);
    assert.equal(liveLinks["55"].type, "IMAGE");
  } finally {
    await harness.dispose();
  }
});

// ── Family B (T-031): JSON-clone + method-injection pins ──────────────────
// cloneDynamicSlot / liveLinkRecord are internal to vibecomfy_roundtrip.js;
// these tests drive them through the exported repairLiveNodes entry point and
// pin the observable contract T-032 must preserve when the JSON clones are
// migrated to shared clone code.

function familyBSeedGraph() {
  const source = "def process(in_0):\n    return {\"image\": in_0}";
  return {
    nodes: [
      {
        id: 23,
        type: "vibecomfy.exec",
        inputs: [
          { name: "in_0", type: "*", link: 40, ephemeral: undefined, callback: () => {}, marker: { fn: () => {} } },
          { name: null, type: "*", link: null },
        ],
        outputs: [
          { name: "out_0", type: "*", links: [41], ephemeral: undefined, callback: () => {} },
        ],
        widgets_values: [source, {}],
        properties: { "Node name for S&R": "vibecomfy.exec", vibecomfy_uid: "n15" },
      },
      { id: 6, type: "VAEDecode", outputs: [{ name: "IMAGE", type: "IMAGE", links: [40] }] },
      { id: 24, type: "SaveImage", inputs: [{ name: "images", type: "IMAGE", link: 41 }], outputs: [] },
    ],
    links: [
      [40, 6, 0, 23, 0, "IMAGE"],
      [41, 23, 0, 24, 0, "IMAGE"],
    ],
  };
}

async function familyBRepairHarness() {
  const harness = await createBrowserHarness({
    withGraphMutation: true,
    responses: {
      "/system_stats": { status: 200, body: { system: { comfyui_frontend_package: "1.39.19" } } },
    },
  });
  const graph = familyBSeedGraph();
  harness.app.canvas.graph._nodes = harness.app.canvas.graph._nodes.filter((node) => node.id !== 1);
  for (const node of graph.nodes) {
    harness.app.canvas.graph._nodes.push({
      ...node,
      inputs: node.inputs ? JSON.parse(JSON.stringify(node.inputs)) : [],
      outputs: node.outputs ? JSON.parse(JSON.stringify(node.outputs)) : [],
    });
  }
  harness.app.canvas.graph.links = new Map();
  return { harness, graph };
}

test("Family B: cloneDynamicSlot JSON round-trip drops undefined/functions and injects non-enumerable serialize with in_i/out_i naming", async () => {
  const { harness, graph } = await familyBRepairHarness();
  try {
    const extensionModule = await harness.loadExtension();
    extensionModule.repairLiveNodes(graph);

    const execNode = harness.getLiveNodes().find((node) => node.type === "vibecomfy.exec");
    assert.ok(execNode, "live exec node repaired");

    // Naming contract: inputs become in_<index>, outputs out_<index>; an
    // unnamed/null-named slot falls back to the direction-index name.
    assert.deepEqual(execNode.inputs.map((slot) => slot.name), ["in_0", "in_1"]);
    assert.deepEqual(execNode.outputs.map((slot) => slot.name), ["out_0"]);

    // Method injection: every cloned slot carries an own, non-enumerable
    // serialize method (invisible to JSON serialization but callable live).
    for (const slot of [...execNode.inputs, ...execNode.outputs]) {
      assert.equal(typeof slot.serialize, "function", "cloned slot carries injected serialize");
      assert.equal(
        Object.prototype.hasOwnProperty.call(slot, "serialize"),
        true,
        "serialize is an own property of the cloned slot",
      );
      assert.equal(
        Object.keys(slot).includes("serialize"),
        false,
        "serialize is non-enumerable so JSON serialization stays clean",
      );
    }

    // (b) undefined/function members in pre-serialized input do not appear in
    // the cloned output.
    const in0 = execNode.inputs[0];
    assert.equal(Object.prototype.hasOwnProperty.call(in0, "ephemeral"), false, "undefined member dropped");
    assert.equal(Object.prototype.hasOwnProperty.call(in0, "callback"), false, "function member dropped");
    assert.deepEqual(in0.marker, {}, "nested function member dropped");

    // serialize() emits only enumerable data members (no functions).
    assert.deepEqual(in0.serialize(), { name: "in_0", type: "*", link: 40, marker: {} });
    assert.deepEqual(execNode.inputs[1].serialize(), { name: "in_1", type: "*", link: null });
  } finally {
    await harness.dispose();
  }
});

test("Family B: liveLinkRecord injects live methods and keeps a JSON-clean 6-tuple serialization contract", async () => {
  const { harness, graph } = await familyBRepairHarness();
  try {
    const extensionModule = await harness.loadExtension();
    extensionModule.repairLiveNodes(graph);

    const liveLinks = harness.getLiveLinks();
    assert.ok(liveLinks instanceof Map, "live link store remains Map-backed");
    const record = liveLinks.get(40);
    assert.ok(record, "link 40 restored as a live record");

    // Method injection: asSerialisable / disconnect / serialize are own,
    // non-enumerable methods.
    assert.equal(typeof record.asSerialisable, "function");
    assert.equal(typeof record.disconnect, "function");
    assert.equal(typeof record.serialize, "function");
    assert.deepEqual(
      Object.keys(record),
      ["id", "origin_id", "origin_slot", "target_id", "target_slot", "type"],
      "injected methods are non-enumerable: only the six data fields serialize",
    );

    // Serialization contract: the live record round-trips to the canonical
    // ComfyUI 6-tuple [id, origin_id, origin_slot, target_id, target_slot, type].
    assert.deepEqual(record.asSerialisable(), [40, 6, 0, 23, 0, "IMAGE"]);
    assert.deepEqual(record.serialize(), [40, 6, 0, 23, 0, "IMAGE"]);

    // A JSON round-trip of the record keeps the data fields and drops the
    // injected (non-enumerable) methods — the transport-clean projection.
    const jsonRecord = JSON.parse(JSON.stringify(record));
    assert.deepEqual(jsonRecord, { id: 40, origin_id: 6, origin_slot: 0, target_id: 23, target_slot: 0, type: "IMAGE" });
    assert.equal(typeof jsonRecord.asSerialisable, "undefined");
    assert.equal(typeof jsonRecord.disconnect, "undefined");
    assert.equal(typeof jsonRecord.serialize, "undefined");
  } finally {
    await harness.dispose();
  }
});

test("Family B: re-clone of live exec slots preserves in_i/out_i naming and re-establishes injected serialize", async () => {
  const { harness, graph } = await familyBRepairHarness();
  try {
    const extensionModule = await harness.loadExtension();
    extensionModule.repairLiveNodes(graph);
    let execNode = harness.getLiveNodes().find((node) => node.type === "vibecomfy.exec");

    // What serialization/reload does to the live slots: a JSON round-trip.
    const jsonInputs = JSON.parse(JSON.stringify(execNode.inputs));
    assert.deepEqual(jsonInputs.map((slot) => slot.name), ["in_0", "in_1"], "names survive as data");
    for (const slot of jsonInputs) {
      assert.equal(typeof slot.serialize, "undefined", "injected serialize is non-enumerable and absent after JSON round-trip");
    }

    // Re-run the repair pipeline against the JSON-round-tripped candidate
    // slots: the naming contract holds and the injected methods are
    // re-established on the live slots.
    const candidate2 = JSON.parse(JSON.stringify(graph));
    candidate2.nodes[0].inputs = jsonInputs;
    extensionModule.repairLiveNodes(candidate2);
    execNode = harness.getLiveNodes().find((node) => node.type === "vibecomfy.exec");

    assert.deepEqual(execNode.inputs.map((slot) => slot.name), ["in_0", "in_1"], "naming contract holds after re-clone");
    assert.deepEqual(execNode.outputs.map((slot) => slot.name), ["out_0"], "output naming contract holds after re-clone");
    for (const slot of [...execNode.inputs, ...execNode.outputs]) {
      assert.equal(typeof slot.serialize, "function", "re-clone through repair re-establishes injected serialize");
      assert.equal(
        Object.keys(slot).includes("serialize"),
        false,
        "re-injected serialize stays non-enumerable after re-clone",
      );
    }
  } finally {
    await harness.dispose();
  }
});
