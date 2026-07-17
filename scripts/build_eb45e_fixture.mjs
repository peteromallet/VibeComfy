// One-shot assembly of the exact eb45e dynamic-exec incident fixture from the
// recorded ComfyUI editor-session artifacts. NOT a reduced/hand-written graph:
// it embeds the full original + candidate serialized UI graphs verbatim plus
// the incident narrative. Run once; the output is committed as a static fixture.
//
// Determinism: the builder reads only files under TURN_DIR and writes a
// 2-space-indented JSON document with a stable key order. Re-running against
// the same source checkout reproduces a byte-identical fixture. Provenance
// records the SHA-256 of each of the four incident sources (original,
// candidate, messages, response) computed at build time so downstream tests
// can pin the exact acceptance artifacts without re-embedding the 567KB
// response body.
import { readFileSync, writeFileSync } from "node:fs";
import { createHash } from "node:crypto";
import path from "node:path";

const TURN_DIR =
  "/Users/peteromalley/Documents/reigh-workspace/ComfyUI/out/editor_sessions/eb45e0ef50e146c6985417bf1449e96a/turns/0001";

const SOURCE_FILES_WITH_DIGESTS = [
  "original.ui.json",
  "candidate.ui.json",
  "messages.jsonl",
  "response.json",
];

function readJson(name) {
  return JSON.parse(readFileSync(path.join(TURN_DIR, name), "utf8"));
}

function readText(name) {
  return readFileSync(path.join(TURN_DIR, name), "utf8");
}

function sha256OfSource(name) {
  const buf = readFileSync(path.join(TURN_DIR, name));
  // Hash the raw bytes of the source file so the digest matches `shasum -a 256`.
  return createHash("sha256").update(buf).digest("hex");
}

function deepClonePlain(value) {
  return value === undefined ? undefined : JSON.parse(JSON.stringify(value));
}

const sessionId = "eb45e0ef50e146c6985417bf1449e96a";
const original = readJson("original.ui.json");
const candidate = readJson("candidate.ui.json");
const narrativeContext = readJson("narrative_context.json");
const narrativeValidation = readJson("narrative_validation.json");
const response = readJson("response.json");

// messages.jsonl is a single turn-0 record; capture it verbatim as parsed JSON.
const messages = readText("messages.jsonl")
  .split(/\r?\n/)
  .filter((line) => line.trim().length > 0)
  .map((line) => JSON.parse(line));

// SHA-256 digests of the four incident sources at build time. These pin the
// exact acceptance artifacts the fixture was reconstructed from.
const sourceDigests = Object.fromEntries(
  SOURCE_FILES_WITH_DIGESTS.map((name) => [name, sha256OfSource(name)]),
);

// The relevant response outcome envelope. The full response.json is ~567KB and
// is referenced only by its digest; only this small, decision-relevant slice is
// embedded so tests can assert the outcome without re-shipping the body.
const responseOutcome = {
  session_id: response.session_id ?? null,
  turn_id: response.turn_id ?? null,
  ok: response.ok ?? null,
  route: response.route ?? null,
  contract_version: response.contract_version ?? null,
  agent_edit_protocol: response.agent_edit_protocol ?? null,
  outcome: deepClonePlain(response.outcome ?? null),
};

// Locate the dynamic-exec node and the two links it participates in, by stable
// identity, so the fixture carries a derived evidence index for normalization
// tests without re-deriving it by hand.
const execNodes = candidate.nodes.filter((node) => node.type === "vibecomfy.exec");
const execEvidence = execNodes.map((node) => {
  const io = node?.properties?.vibecomfy?.io ?? null;
  const widgetIo = Array.isArray(node.widgets_values) ? node.widgets_values[1] : null;
  return {
    native_id: node.id,
    stable_uid: node?.properties?.vibecomfy_uid ?? null,
    title: node?.title ?? null,
    type: node.type,
    pos: Array.isArray(node.pos) ? node.pos.slice(0, 2) : null,
    size: Array.isArray(node.size) ? node.size.slice(0, 2) : null,
    io_schema: io,
    widget_io: widgetIo,
    source_widget:
      Array.isArray(node.widgets_values) ? node.widgets_values[0] ?? null : null,
    inputs: deepClonePlain(Array.isArray(node.inputs) ? node.inputs : []),
    outputs: deepClonePlain(Array.isArray(node.outputs) ? node.outputs : []),
  };
});

// Links touching the dynamic-exec node(s), verbatim six-tuples.
const execNativeIds = new Set(execNodes.map((node) => node.id));
const execLinks = (Array.isArray(candidate.links) ? candidate.links : [])
  .filter((link) => Array.isArray(link) && (execNativeIds.has(link[1]) || execNativeIds.has(link[3])))
  .map((link) => [...link]);

const fixture = {
  contract: "eb45e_dynamic_exec_v1",
  schema_version: 1,
  provenance: {
    source_checkout:
      "/Users/peteromalley/Documents/reigh-workspace/ComfyUI/out/editor_sessions/eb45e0ef50e146c6985417bf1449e96a/turns/0001",
    source_files: [
      "original.ui.json",
      "candidate.ui.json",
      "messages.jsonl",
      "response.json",
      "narrative_context.json",
      "narrative_validation.json",
    ],
    // SHA-256 over the raw bytes of each of the four incident sources at the
    // time the fixture was rebuilt. Tests assert all four values so any drift
    // in the acceptance artifacts is caught at the contract boundary.
    source_digests: {
      "original.ui.json": sourceDigests["original.ui.json"],
      "candidate.ui.json": sourceDigests["candidate.ui.json"],
      "messages.jsonl": sourceDigests["messages.jsonl"],
      "response.json": sourceDigests["response.json"],
    },
    // Digest algorithm and the byte range covered. Each digest is over the
    // complete source file (no truncation, no re-serialization).
    digest_algorithm: "sha256",
    digest_scope: "full source file bytes",
    session_id: sessionId,
    turn: "0001",
    note:
      "Original incident artifacts embedded verbatim. This fixture is reconstructed from the recorded editor session, not a simplified hand-written graph. The full response.json is referenced by digest only; its small outcome envelope is embedded under response_outcome.",
  },
  incident: {
    session_id: sessionId,
    task: narrativeContext.task ?? "Add a code node that processes images with PIL",
    turn_messages: messages,
    narrative_context: narrativeContext,
    narrative_validation: narrativeValidation,
  },
  response_outcome: responseOutcome,
  original,
  candidate,
  dynamic_exec_evidence: {
    exec_nodes: execEvidence,
    incident_links: execLinks,
  },
};

const outPath = path.resolve(
  "tests/fixtures/agent_edit/eb45e_dynamic_exec_v1.json",
);
writeFileSync(outPath, JSON.stringify(fixture, null, 2) + "\n", "utf8");
console.log(`wrote ${outPath} (${execNodes.length} exec node(s), ${execLinks.length} incident link(s))`);
console.log("source_digests:");
for (const [name, digest] of Object.entries(sourceDigests)) {
  console.log(`  ${name}: ${digest}`);
}
