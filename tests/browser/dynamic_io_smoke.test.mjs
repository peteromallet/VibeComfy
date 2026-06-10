import test from "node:test";
import assert from "node:assert/strict";

import { createBrowserHarness } from "./harness.mjs";

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
    assert.equal(node.properties["VibeComfy Intent Badge"], "Python · sandboxed_loose");
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
    assert.equal(codeNodeNoComfyClass.properties["VibeComfy Intent Badge"], "Python · sandboxed_loose");
  } finally {
    await harness.dispose();
  }
});
