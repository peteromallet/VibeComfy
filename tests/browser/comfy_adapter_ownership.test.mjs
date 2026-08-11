import test from "node:test";
import assert from "node:assert/strict";
import { readFileSync } from "node:fs";
import path from "node:path";
import { fileURLToPath } from "node:url";

import * as adapter from "../../vibecomfy/comfy_nodes/web/comfy_adapter.js";

const __filename = fileURLToPath(import.meta.url);
const __dirname = path.dirname(__filename);
const WEB_ROOT = path.resolve(__dirname, "..", "..", "vibecomfy", "comfy_nodes", "web");

function source(name) {
  return readFileSync(path.join(WEB_ROOT, name), "utf8");
}

const adapterSource = source("comfy_adapter.js");
const roundtripSource = source("vibecomfy_roundtrip.js");

const MOVED_NORMALIZATION_FUNCTIONS = [
  "normalizeIntentTypedIo",
  "readExecWidgetValue",
  "normalizeExecIoValue",
  "normalizeExecIoEntries",
  "normalizeExecIoObject",
  "normalizeGraphExecNodesForSerialization",
  "applyTypedSocketLabels",
  "applyTypedSocketLabelsLabelOnly",
  "applyTypedSocketTypesOnly",
];

function definitionPattern(name) {
  return new RegExp(
    String.raw`(?:^|\n)\s*(?:export\s+)?(?:async\s+)?function\s+${name}\s*\(`,
  );
}

test("comfy_adapter owns intent/exec normalization and roundtrip only delegates", () => {
  for (const name of MOVED_NORMALIZATION_FUNCTIONS) {
    assert.match(adapterSource, definitionPattern(name), `comfy_adapter.js defines ${name}`);
    assert.doesNotMatch(
      roundtripSource,
      definitionPattern(name),
      `vibecomfy_roundtrip.js must not define duplicate ${name}`,
    );
  }

  assert.match(
    adapterSource,
    definitionPattern("normalizeExecNodeForSerialization"),
    "comfy_adapter.js defines the canonical exec-node normalizer",
  );
  assert.match(
    roundtripSource,
    /function\s+normalizeExecNodeForSerialization\s*\([^)]*\)\s*\{\s*return\s+normalizeExecNodeForSerializationAdapter\(/,
    "roundtrip preserves its public function as a delegating facade",
  );
  assert.doesNotMatch(adapterSource, definitionPattern("setExecWidgetValue"));
  assert.match(roundtripSource, definitionPattern("setExecWidgetValue"));

  assert.match(roundtripSource, /from\s+["']\.\/comfy_adapter\.js["']/);
  assert.match(roundtripSource, /applyTypedSocketLabelsLabelOnly,\s*$/m);
  assert.match(roundtripSource, /normalizeExecNodeForSerialization,\s*$/m);
  assert.doesNotMatch(roundtripSource, /\bfunction\s+renderAudit\s*\(/);
  assert.doesNotMatch(roundtripSource, /\bfunction\s+renderDebug\s*\(/);
});

test("adapter normalization preserves the existing intent and exec IO shapes", () => {
  assert.deepEqual(
    adapter.normalizeIntentTypedIo(
      { inputs: [["image", "IMAGE"], ["missing-type"], null, ["seed", "INT"]] },
      "inputs",
    ),
    [
      { name: "image", type: "IMAGE" },
      { name: "seed", type: "INT" },
    ],
  );

  assert.deepEqual(
    adapter.normalizeExecIoObject(JSON.stringify({
      inputs: { image: "IMAGE", mask: "MASK" },
      outputs: [["result", "IMAGE"], ["wildcard"]],
    })),
    {
      inputs: [["image", "IMAGE"], ["mask", "MASK"]],
      outputs: [["result", "IMAGE"], ["wildcard", "*"]],
    },
  );
  assert.equal(adapter.normalizeExecIoObject("not-json"), null);
  assert.equal(adapter.normalizeExecIoObject({ inputs: [], outputs: [] }), null);
});

test("adapter exec-node normalization repairs IO without cloning dynamic slots", () => {
  const serialize = () => ({ name: "in_0" });
  const inputSlot = { name: "in_0", label: "image: IMAGE", type: "*", serialize };
  const outputSlot = { name: "out_0", label: "result: IMAGE", type: "*" };
  const node = {
    type: "vibecomfy.exec",
    widgets_values: { source: "return { result: image };", io: null },
    inputs: [inputSlot],
    outputs: [outputSlot],
    properties: { "Node name for S&R": "vibecomfy.exec" },
  };
  const deps = {
    setExecWidgetValue(target, key, value) {
      target.widgets_values[key] = value;
    },
  };

  assert.equal(adapter.normalizeExecNodeForSerialization(node, null, deps), true);
  assert.deepEqual(node.widgets_values.io, {
    inputs: [["image", "IMAGE"]],
    outputs: [["result", "IMAGE"]],
  });
  assert.deepEqual(node.properties.vibecomfy.io, node.widgets_values.io);
  assert.equal(node.properties.vibecomfy.intent.source, "return { result: image };");
  assert.equal(node.inputs[0], inputSlot);
  assert.equal(node.inputs[0].serialize, serialize);

  const graphNode = {
    comfyClass: "vibecomfy.exec",
    widgets_values: { source: "return {};", io: { inputs: { value: "*" }, outputs: {} } },
  };
  adapter.normalizeGraphExecNodesForSerialization({ nodes: [graphNode] }, deps);
  assert.deepEqual(graphNode.widgets_values.io, { inputs: [["value", "*"]], outputs: [] });
});

test("R:S11 clone/method-injection helpers remain roundtrip-owned", () => {
  assert.match(roundtripSource, /function\s+cloneDynamicSlot\s*\(/);
  assert.match(roundtripSource, /function\s+liveLinkRecord\s*\(/);
  assert.match(roundtripSource, /function\s+setExecWidgetValue\s*\(/);
  assert.doesNotMatch(adapterSource, /\b(?:clonePlainData|cloneDynamicSlot|liveLinkRecord)\b/);
});
