import test from "node:test";
import assert from "node:assert/strict";
import { readFileSync, readdirSync } from "node:fs";
import path from "node:path";
import { fileURLToPath } from "node:url";

import {
  createAgentEditState,
  ingestChatRehydratePayload,
} from "../../vibecomfy/comfy_nodes/web/agent_edit_lifecycle.js";

const __filename = fileURLToPath(import.meta.url);
const __dirname = path.dirname(__filename);
const REPO_ROOT = path.resolve(__dirname, "..", "..");
const WEB_ROOT = path.join(REPO_ROOT, "vibecomfy", "comfy_nodes", "web");

function source(name) {
  return readFileSync(path.join(WEB_ROOT, name), "utf8");
}

function definitionPattern(name, flags = "m") {
  const escapedName = name.replace(/[.*+?^${}()|[\]\\]/g, "\\$&");
  return new RegExp(
    String.raw`^\s*(?:export\s+)?(?:async\s+)?function\s+${escapedName}\s*\(|^\s*(?:export\s+)?(?:const|let|var)\s+${escapedName}\b`,
    flags,
  );
}

function definitionCount(moduleSource, name) {
  return [...moduleSource.matchAll(definitionPattern(name, "gm"))].length;
}

const roundtripSource = source("vibecomfy_roundtrip.js");
const lifecycleSource = source("agent_edit_lifecycle.js");
const webModuleNames = readdirSync(WEB_ROOT)
  .filter((name) => /\.(?:m?js)$/.test(name))
  .sort();

test("chat transport and canonical-ingestion functions retain their S14 owners", () => {
  for (const name of ["normalizeChatRehydratePayload", "normalizeFieldChangesFromMessage"]) {
    assert.equal(definitionCount(roundtripSource, name), 1, `${name} must be defined once in roundtrip`);
    assert.equal(definitionCount(lifecycleSource, name), 0, `${name} must not be defined in lifecycle`);
  }

  for (const name of ["ingestChatRehydratePayload", "reconcileChatMessages"]) {
    assert.equal(definitionCount(lifecycleSource, name), 1, `${name} must be defined once in lifecycle`);
    assert.equal(definitionCount(roundtripSource, name), 0, `${name} must not be defined in roundtrip`);
    assert.match(
      lifecycleSource,
      new RegExp(String.raw`^\s*export\s+function\s+${name}\s*\(`, "m"),
      `${name} must remain an exported lifecycle seam`,
    );
  }
});

test("roundtrip hands normalized chat payloads to lifecycle ingestion", () => {
  const lifecycleImport = roundtripSource.match(
    /import\s*\{([^}]*)\}\s*from\s*["']\.\/agent_edit_lifecycle\.js["'];?/,
  );
  assert.ok(lifecycleImport, "roundtrip must import lifecycle dependencies from agent_edit_lifecycle.js");
  assert.match(
    lifecycleImport[1],
    /\bingestChatRehydratePayload\b/,
    "roundtrip must import the lifecycle-owned chat ingest seam",
  );
  assert.match(
    roundtripSource,
    /ingestChatRehydratePayload\(\s*panel\.state,\s*lifecyclePayload,?\s*\)/,
    "the rehydrate entry must hand its normalized payload to lifecycle ingestion",
  );
});

test("the four chat-boundary functions have no duplicate definitions in web modules", () => {
  const expectedOwner = {
    normalizeChatRehydratePayload: "vibecomfy_roundtrip.js",
    normalizeFieldChangesFromMessage: "vibecomfy_roundtrip.js",
    ingestChatRehydratePayload: "agent_edit_lifecycle.js",
    reconcileChatMessages: "agent_edit_lifecycle.js",
  };

  for (const [name, owner] of Object.entries(expectedOwner)) {
    const locations = webModuleNames.flatMap((moduleName) => {
      const count = definitionCount(source(moduleName), name);
      return count ? [{ moduleName, count }] : [];
    });
    assert.deepEqual(locations, [{ moduleName: owner, count: 1 }], `${name} must have exactly one web owner`);
  }
});

test("lifecycle ingest projects a snake_case chat payload into canonical messages", () => {
  const ingested = ingestChatRehydratePayload(createAgentEditState(), {
    session_id: "session-snake",
    messages: [
      {
        role: "agent",
        message: "Ready.",
        turn_id: "turn-snake",
        local_id: "local-snake",
        progress_label: "Done",
      },
    ],
  });

  assert.deepEqual(ingested.chatMessages, [
    {
      role: "agent",
      text: "Ready.",
      turn_id: "turn-snake",
      session_id: "session-snake",
      local_id: "local-snake",
      progress_label: "Done",
    },
  ]);
});
