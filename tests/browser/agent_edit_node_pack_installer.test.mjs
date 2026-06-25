import test from "node:test";
import assert from "node:assert/strict";

import {
  fulfillNodePackInstallRequest,
} from "../../vibecomfy/comfy_nodes/web/agent_edit_node_pack_installer.js";

function makeResponse(ok, payload) {
  return {
    ok,
    async json() {
      return payload;
    },
  };
}

test("node pack installer posts the lifecycle request and dispatches success", async () => {
  const calls = [];
  const nextObligations = { render: true, dirtySections: ["META"] };
  await fulfillNodePackInstallRequest(
    { state: {} },
    {
      nodePackInstallKey: "hash-vhs",
      nodePackInstallRequest: {
        endpoint: "/vibecomfy/node-packs/install",
        method: "POST",
        headers: { "Content-Type": "application/json" },
        body: {
          candidate: { stable_install_hash: "hash-vhs" },
          user_confirmed: true,
        },
      },
    },
    {
      async fetch(endpoint, options) {
        calls.push(["fetch", endpoint, JSON.parse(options.body)]);
        return makeResponse(true, { ok: true, status: "installed" });
      },
      transition(panel, event, payload) {
        calls.push(["transition", event, payload.installKey, payload.result.status]);
        return nextObligations;
      },
      fulfillLifecycleTransitionObligations(panel, obligations) {
        calls.push(["fulfill", obligations]);
      },
      renderLifecycleTransition(panel, obligations) {
        calls.push(["render", obligations]);
      },
    },
  );

  assert.deepEqual(calls, [
    [
      "fetch",
      "/vibecomfy/node-packs/install",
      { candidate: { stable_install_hash: "hash-vhs" }, user_confirmed: true },
    ],
    ["transition", "NODE_PACK_INSTALL_SUCCEEDED", "hash-vhs", "installed"],
    ["fulfill", nextObligations],
    ["render", nextObligations],
  ]);
});

test("node pack installer converts fetch failures into lifecycle failures", async () => {
  const calls = [];
  await fulfillNodePackInstallRequest(
    { state: {} },
    {
      nodePackInstallKey: "hash-vhs",
      nodePackInstallRequest: {
        body: { candidate: { stable_install_hash: "hash-vhs" } },
      },
    },
    {
      async fetch() {
        throw new Error("offline");
      },
      transition(panel, event, payload) {
        calls.push([event, payload.installKey, payload.result.validation_status]);
        return { render: true };
      },
      fulfillLifecycleTransitionObligations() {},
      renderLifecycleTransition() {},
    },
  );

  assert.deepEqual(calls, [["NODE_PACK_INSTALL_FAILED", "hash-vhs", "validation_failed"]]);
});
