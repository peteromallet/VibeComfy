import assert from "node:assert/strict";
import test from "node:test";

import {
  computeSerializedGraphPreviewDiff,
  constrainPreviewDiffToLegacyIntent,
} from "../../vibecomfy/comfy_nodes/web/preview_diff_core.js";

test("serialized reorganise preview includes candidate group furniture", () => {
  const baseline = {
    nodes: [{ id: 1, pos: [0, 0], properties: { vibecomfy_uid: "one" } }],
    groups: [{ title: "Before", bounding: [0, 0, 100, 100] }],
  };
  const candidate = {
    nodes: [{ id: 1, pos: [200, 0], properties: { vibecomfy_uid: "one" } }],
    groups: [{ title: "After", color: "#123456", bounding: [180, -20, 300, 160] }],
  };

  const result = computeSerializedGraphPreviewDiff({
    liveGraph: baseline,
    candidateGraph: candidate,
    layoutBaselineGraph: baseline,
  });

  assert.deepEqual(result.layout_groups, [{
    key: "index:0",
    title: "After",
    color: "#123456",
    bounds: { x: 180, y: -20, w: 300, h: 160 },
  }]);
});

test("legacy preview intent suppresses whole-graph widget and link drift", () => {
  const graphDiff = {
    edited: [
      { uid: "124", changedWidgetIndices: [1] },
      { uid: "131", changedWidgetIndices: [2] },
      { uid: "138", changedWidgetIndices: [21] },
    ],
    added: [],
    removed: [],
    added_links: [
      "124::output_0->138::emotion_control",
      "131::AUDIO->51::opt_audio_input",
    ],
    removed_links: [
      "125::output_0->138::emotion_control",
      "131::AUDIO->51::audio",
    ],
  };
  const fieldChanges = [
    { uid: "124", fieldPath: "widget_1", old: "calm", new: "dramatic" },
    {
      uid: "138",
      fieldPath: "emotion_control",
      old: { uid: "125", output_slot: "output_0" },
      new: { uid: "124", output_slot: "output_0" },
    },
  ];
  const changeDetails = {
    batch_turns: [{
      statements: [
        { landed: true, op_kind: "set_node_field", touched_uids: ["124"] },
        { landed: true, op_kind: "upsert_link", touched_uids: ["124", "138"] },
      ],
    }],
  };

  const result = constrainPreviewDiffToLegacyIntent({ graphDiff, fieldChanges, changeDetails });

  assert.deepEqual(result.edited, [
    { uid: "124", changedWidgetIndices: [1] },
    { uid: "138", changedWidgetIndices: [] },
  ]);
  assert.deepEqual(result.added_links, ["124::output_0->138::emotion_control"]);
  assert.deepEqual(result.removed_links, ["125::output_0->138::emotion_control"]);
  assert.equal(result._legacyIntentDerived, true);
  assert.deepEqual(result._roundtripDrift, { edited: 3, added_links: 2, removed_links: 2 });
});

test("legacy preview intent keeps only explicitly constructed and removed nodes", () => {
  const result = constrainPreviewDiffToLegacyIntent({
    graphDiff: {
      edited: [{ uid: "59", changedWidgetIndices: [0] }],
      added: [{ uid: "n1" }, { uid: "phantom" }],
      removed: [{ uid: "55" }, { uid: "unchanged" }],
      added_links: ["n1::IMAGE->46::images", "phantom::x->59::a"],
      removed_links: ["55::IMAGE->46::images", "unchanged::x->59::a"],
    },
    fieldChanges: [{
      uid: "46",
      field_path: "images",
      old: { uid: "55", output_slot: "IMAGE" },
      new: { uid: "n1", output_slot: "IMAGE" },
    }],
    changeDetails: {
      batch_turns: [{ statements: [
        { landed: true, op_kind: "remove_node", touched_uids: ["55"] },
        { landed: true, op_kind: "node_call", touched_uids: [] },
        { landed: true, op_kind: "upsert_link", touched_uids: ["n1", "46"] },
      ] }],
    },
  });

  assert.deepEqual(result.edited, [{ uid: "46", changedWidgetIndices: [] }]);
  assert.deepEqual(result.added, [{ uid: "n1" }]);
  assert.deepEqual(result.removed, [{ uid: "55" }]);
  assert.deepEqual(result.added_links, ["n1::IMAGE->46::images"]);
  assert.deepEqual(result.removed_links, ["55::IMAGE->46::images"]);
});
