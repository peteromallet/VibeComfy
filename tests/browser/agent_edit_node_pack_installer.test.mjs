import test from "node:test";
import assert from "node:assert/strict";

import {
  fulfillNodePackInstallRequest,
} from "../../vibecomfy/comfy_nodes/web/agent_edit_node_pack_installer.js";
import {
  CSRF_BOOTSTRAP_PATH,
  CSRF_HEADER,
  _resetCsrfCapabilityForTests,
} from "../../vibecomfy/comfy_nodes/web/http_security.js";

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

test("shipped node pack path uses the guarded client and local CSRF", async () => {
  _resetCsrfCapabilityForTests();
  const requests = [];
  const originalFetch = globalThis.fetch;
  globalThis.fetch = async (endpoint, options = {}) => {
    requests.push({ endpoint: String(endpoint), options });
    if (String(endpoint) === CSRF_BOOTSTRAP_PATH) {
      return makeResponse(true, {
        csrf_header: CSRF_HEADER,
        csrf_token: "node-pack-installer-csrf-capability-0001",
      });
    }
    return makeResponse(true, { ok: true, status: "installed" });
  };
  try {
    await fulfillNodePackInstallRequest(
      { state: {} },
      {
        nodePackInstallKey: "hash-guarded",
        nodePackInstallRequest: {
          endpoint: "/vibecomfy/node-packs/install",
          method: "POST",
          body: { candidate: { stable_install_hash: "hash-guarded" } },
        },
      },
      {
        transition() {
          return {};
        },
        fulfillLifecycleTransitionObligations() {},
        renderLifecycleTransition() {},
      },
    );

    assert.equal(requests.length, 2);
    assert.equal(requests[0].endpoint, CSRF_BOOTSTRAP_PATH);
    assert.equal(requests[1].endpoint, "/vibecomfy/node-packs/install");
    assert.equal(
      requests[1].options.headers[CSRF_HEADER],
      "node-pack-installer-csrf-capability-0001",
    );
  } finally {
    globalThis.fetch = originalFetch;
  }
});
