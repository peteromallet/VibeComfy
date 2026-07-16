import test from "node:test";
import assert from "node:assert/strict";
import { existsSync, readFileSync, statSync } from "node:fs";
import { readFile, readdir } from "node:fs/promises";
import path from "node:path";
import { fileURLToPath } from "node:url";

const root = path.resolve(path.dirname(fileURLToPath(import.meta.url)), "..", "..");
const web = path.join(root, "vibecomfy", "comfy_nodes", "web");
const nativeAuthorityLedgerPath = path.join(
  root,
  "tests",
  "fixtures",
  "agent_edit",
  "native_authority_ledger_v1.json",
);

const NATIVE_ACCESS_PATTERNS = Object.freeze([
  ["graph_acquire", /\b(?:app|runtimeApp|helpers\s*\.\s*app)(?:\s*\?\.\s*|\s*\.\s*)(?:(?:canvas)(?:\s*\?\.\s*|\s*\.\s*))?graph\b/g],
  ["native_nodes", /\b(?:graph|liveGraph|network)(?:\s*\?\.\s*|\s*\.\s*)_nodes\b/g],
  ["native_groups", /\b(?:graph|liveGraph|network)(?:\s*\?\.\s*|\s*\.\s*)_groups\b/g],
  ["native_links", /\b(?:graph|liveGraph|network)(?:\s*\?\.\s*|\s*\.\s*)links\b/g],
  ["serialize", /\b(?:graph|liveGraph|network|group)(?:\s*\?\.\s*|\s*\.\s*)serialize\s*\(/g],
  ["graph_clear", /\b(?:graph|liveGraph|network)(?:\s*\?\.\s*|\s*\.\s*)clear\s*\(/g],
  ["graph_configure", /\b(?:graph|liveGraph|network)(?:\s*\?\.\s*|\s*\.\s*)configure\s*\(/g],
  ["graph_add", /\b(?:graph|liveGraph|network)(?:\s*\?\.\s*|\s*\.\s*)add\s*\(/g],
  ["graph_remove", /\b(?:graph|liveGraph|network)(?:\s*\?\.\s*|\s*\.\s*)remove\s*\(/g],
  ["remove_link", /\b(?:graph|liveGraph|network)(?:\s*\?\.\s*|\s*\.\s*)removeLink\s*\(/g],
  ["node_connect", /\b[A-Za-z_$][\w$]*Node(?:\s*\?\.\s*|\s*\.\s*)connect\s*\(/g],
  ["load_graph_data", /\bloadGraphData(?:WithoutScopeSwitch)?\b/g],
  ["node_factory", /\b(?:LiteGraph|liteGraph)(?:\s*\?\.\s*|\s*\.\s*)createNode\b/g],
  ["graph_revision", /\b(?:graph|liveGraph|network)(?:\s*\?\.\s*|\s*\.\s*)(?:getRevision|revision|_revision|_version|_vibecomfyLiveCanvasToken|_vibecomfy_live_canvas_token)\b/g],
  ["graph_dirty", /\b(?:graph|liveGraph|network)(?:\s*\?\.\s*|\s*\.\s*)setDirtyCanvas\s*\(/g],
  ["group_construct", /\bnew\s+(?:(?:globalThis\s*\.\s*)?(?:(?:window\s*\?*\.\s*)?LiteGraph\s*\?*\.\s*)?LGraphGroup|GroupCtor)\s*\(/g],
  ["group_configure", /\b(?:group|liveGroup|nativeGroup)(?:\s*\?\.\s*|\s*\.\s*)configure\s*\(/g],
  ["socket_rebuild", /\b[A-Za-z_$][\w$]*(?:\s*\?\.\s*|\s*\.\s*)(?:addInput|addOutput|removeInput|removeOutput|disconnectInput|disconnectOutput)\s*\(/g],
  ["socket_rebuild", /\b[A-Za-z_$][\w$]*(?:\s*\?\.\s*|\s*\.\s*)(?:inputs|outputs)\s*(?:=|\[)/g],
  ["widget_rebuild", /\b[A-Za-z_$][\w$]*(?:\s*\?\.\s*|\s*\.\s*)widgets(?:_values)?\s*(?:=|\[)/g],
  ["stable_identity", /\b(?:canonicalNodeUid|stableNodeUidV1|stableNodeIdentityV1|resolveLiveNodeByUid)\s*\(/g],
  ["stable_identity", /\b[A-Za-z_$][\w$]*(?:\s*\?\.\s*|\s*\.\s*)properties(?:\s*\?\.\s*|\s*\.\s*)vibecomfy_uid\b/g],
  ["native_normalization", /\b(?:normalizeLiveExecNodesForSerialization|normalizedSerializedLinks|sanitizeSerializedGraphLinks|ensureLiveGraphLinkStore)\s*\(/g],
  ["canvas_dirty", /\b(?:canvas|liveCanvas)(?:\s*\?\.\s*|\s*\.\s*)setDirty(?:Canvas)?\s*\(/g],
  ["canvas_draw", /\b(?:canvas|liveCanvas)(?:\s*\?\.\s*|\s*\.\s*)draw\s*\(/g],
]);

const RAW_COMPUTED_PATTERNS = Object.freeze([
  ["graph_acquire", /\b(?:app|runtimeApp|helpers\s*\.\s*app)(?:(?:\s*\?\.\s*|\s*\.\s*)canvas)?\s*\[\s*["']graph["']\s*\]/g],
  ["native_nodes", /\b(?:graph|liveGraph|network|native)\s*\[\s*["']_nodes["']\s*\]/g],
  ["native_groups", /\b(?:graph|liveGraph|network|native)\s*\[\s*["']_groups["']\s*\]/g],
  ["native_links", /\b(?:graph|liveGraph|network|native)\s*\[\s*["']links["']\s*\]/g],
]);

const ALIAS_ACCESS_KINDS = Object.freeze({
  _nodes: "native_nodes",
  _groups: "native_groups",
  links: "native_links",
  clear: "graph_clear",
  configure: "graph_configure",
  add: "graph_add",
  remove: "graph_remove",
  removeLink: "remove_link",
  serialize: "serialize",
  setDirtyCanvas: "graph_dirty",
});

async function source(name) {
  return readFile(path.join(web, name), "utf8");
}

function functionBody(text, name) {
  const start = text.indexOf(`function ${name}(`);
  assert.notEqual(start, -1, `missing function ${name}`);
  const next = text.indexOf("\nfunction ", start + 1);
  return text.slice(start, next === -1 ? text.length : next);
}

function stripCommentsAndStrings(text) {
  const chars = [...text];
  let state = "code";
  for (let i = 0; i < chars.length; i += 1) {
    const char = chars[i];
    const next = chars[i + 1];
    if (state === "code") {
      if (char === "/" && next === "/") {
        chars[i] = chars[i + 1] = " ";
        i += 1;
        state = "line_comment";
      } else if (char === "/" && next === "*") {
        chars[i] = chars[i + 1] = " ";
        i += 1;
        state = "block_comment";
      } else if (char === "'" || char === '"' || char === "`") {
        chars[i] = " ";
        state = char;
      }
    } else if (state === "line_comment") {
      if (char === "\n") state = "code";
      else chars[i] = " ";
    } else if (state === "block_comment") {
      if (char === "*" && next === "/") {
        chars[i] = chars[i + 1] = " ";
        i += 1;
        state = "code";
      } else if (char !== "\n") chars[i] = " ";
    } else if (char === "\\") {
      chars[i] = " ";
      if (i + 1 < chars.length && chars[i + 1] !== "\n") chars[i + 1] = " ";
      i += 1;
    } else if (char === state) {
      chars[i] = " ";
      state = "code";
    } else if (char !== "\n") chars[i] = " ";
  }
  return chars.join("");
}

function sourceRegions(text) {
  const cleaned = stripCommentsAndStrings(text);
  const starts = [{ start: 0, name: "<module>" }];
  const patterns = [
    /\b(?:export\s+)?(?:async\s+)?function\s+([A-Za-z_$][\w$]*)\s*\(/g,
    /\b(?:const|let|var)\s+([A-Za-z_$][\w$]*)\s*=\s*(?:async\s*)?(?:function\b|(?:\([^)]*\)|[A-Za-z_$][\w$]*)\s*=>)/g,
  ];
  for (const pattern of patterns) {
    for (const match of cleaned.matchAll(pattern)) {
      starts.push({ start: match.index, name: match[1] });
    }
  }
  starts.sort((left, right) => left.start - right.start || left.name.localeCompare(right.name));
  return starts.map((region, index) => ({
    name: region.name,
    body: cleaned.slice(region.start, starts[index + 1]?.start ?? cleaned.length),
    rawBody: text.slice(region.start, starts[index + 1]?.start ?? text.length),
  }));
}

function matchOffsets(text, pattern) {
  return [...text.matchAll(pattern)].map((match) => match.index);
}

function accessCounts(region) {
  const offsets = new Map();
  const add = (kind, positions, namespace = "clean") => {
    const bucket = offsets.get(kind) ?? new Set();
    for (const position of positions) bucket.add(`${namespace}:${position}`);
    offsets.set(kind, bucket);
  };
  for (const [kind, pattern] of NATIVE_ACCESS_PATTERNS) {
    add(kind, matchOffsets(region.body, pattern));
  }
  for (const [kind, pattern] of RAW_COMPUTED_PATTERNS) {
    add(kind, matchOffsets(region.rawBody, pattern), "raw");
  }

  const aliases = new Set(["graph", "liveGraph", "network", "native"]);
  const directAliasPattern = /\b(?:const|let|var)\s+([A-Za-z_$][\w$]*)\s*=\s*(?:app|runtimeApp|helpers\s*\.\s*app)(?:\s*\?\.\s*|\s*\.\s*)(?:(?:canvas)(?:\s*\?\.\s*|\s*\.\s*))?graph\b/g;
  for (const match of region.body.matchAll(directAliasPattern)) aliases.add(match[1]);
  const computedAliasPattern = /\b(?:const|let|var)\s+([A-Za-z_$][\w$]*)\s*=\s*(?:app|runtimeApp|helpers\s*\.\s*app)(?:(?:\s*\?\.\s*|\s*\.\s*)canvas)?\s*\[\s*["']graph["']\s*\]/g;
  for (const match of region.rawBody.matchAll(computedAliasPattern)) aliases.add(match[1]);
  const destructuredAliasPattern = /\b(?:const|let|var)\s*\{[^{}]*\bgraph\s*:\s*([A-Za-z_$][\w$]*)[^{}]*\}\s*=\s*(?:app|runtimeApp|helpers\s*\.\s*app)(?:\s*\?\.\s*|\s*\.\s*)canvas\b/g;
  for (const match of region.body.matchAll(destructuredAliasPattern)) {
    aliases.add(match[1]);
    add("graph_acquire", [match.index]);
  }
  const shorthandGraphPattern = /\b(?:const|let|var)\s*\{[^{}]*\bgraph\b[^{}]*\}\s*=\s*(?:app|runtimeApp|helpers\s*\.\s*app)(?:\s*\?\.\s*|\s*\.\s*)canvas\b/g;
  for (const match of region.body.matchAll(shorthandGraphPattern)) {
    aliases.add("graph");
    add("graph_acquire", [match.index]);
  }
  const chainedAliasPattern = /\b(?:const|let|var)\s+([A-Za-z_$][\w$]*)\s*=\s*([A-Za-z_$][\w$]*)\b/g;
  let changed = true;
  while (changed) {
    changed = false;
    for (const match of region.body.matchAll(chainedAliasPattern)) {
      if (aliases.has(match[2]) && !aliases.has(match[1])) {
        aliases.add(match[1]);
        changed = true;
      }
    }
  }
  for (const alias of aliases) {
    const escaped = alias.replace(/[.*+?^${}()|[\]\\]/g, "\\$&");
    for (const [property, kind] of Object.entries(ALIAS_ACCESS_KINDS)) {
      const member = new RegExp(`\\b${escaped}(?:\\s*\\?\\.\\s*|\\s*\\.\\s*)${property}\\b`, "g");
      add(kind, matchOffsets(region.body, member));
      const computed = new RegExp(`\\b${escaped}\\s*\\[\\s*["']${property}["']\\s*\\]`, "g");
      add(kind, matchOffsets(region.rawBody, computed), "raw");
    }
  }
  return [...offsets.entries()]
    .filter(([, positions]) => positions.size > 0)
    .map(([kind, positions]) => [kind, positions.size]);
}

function inventoryForSources(sources) {
  const entries = [];
  for (const file of Object.keys(sources).sort()) {
    for (const region of sourceRegions(sources[file])) {
      for (const [kind, count] of accessCounts(region)) {
        entries.push({ file, region: region.name, kind, count });
      }
    }
  }
  return entries.sort((left, right) => (
    left.file.localeCompare(right.file)
    || left.region.localeCompare(right.region)
    || left.kind.localeCompare(right.kind)
  ));
}

const LEDGER_TOP_LEVEL_KEYS = Object.freeze(["contract", "rows", "schema_version"]);
const LEDGER_ROW_KEYS = Object.freeze([
  "accesses", "file", "fixture_proof", "id", "normalization_category",
  "projection_identity_effect", "purpose", "region", "semantic_owner",
  "slice", "support_status", "target_api",
]);
const ACCESS_KINDS = new Set([
  ...NATIVE_ACCESS_PATTERNS.map(([kind]) => kind),
  ...RAW_COMPUTED_PATTERNS.map(([kind]) => kind),
  ...Object.values(ALIAS_ACCESS_KINDS),
]);
const LEDGER_SLICES = new Set(["-", "S2", "S3", "S4"]);
const SEMANTIC_OWNERS = new Set([
  "agent_status_poller", "comfy_adapter", "intent_graph_adapter",
  "projection_registry_v1", "test-harness", "vibecomfy_roundtrip",
]);
const NORMALIZATION_CATEGORIES = new Set([
  "canvas-draw", "capability-detect", "delta-execute", "delta-mutate",
  "delta-preflight", "factory-resolve", "forbidden-forward",
  "graph-acquire", "harness", "identity-translate", "layout-mutate",
  "layout-project", "link-normalize", "native-normalize", "projection",
  "preview-normalize", "restore-execute", "restore-preflight",
  "revision-capture", "serialize-capture", "socket-rebuild", "widget-normalize",
]);
const SUPPORT_STATUSES = new Set([
  "supported_adapter_owner", "permitted_canvas", "permitted_harness",
  "projection_only", "migration_debt", "blocking_migration",
]);
const TARGET_API_CATALOG = new Set([
  "acquire", "applyCanonicalDelta", "applyDeltaOp.remove_link",
  "applyDeltaOp.set_node_field", "applyDeltaOp.upsert_link",
  "applyInverseDelta", "applyLayoutOperation", "applyPreflightPlan",
  "capabilities", "capabilities.delta_apply", "capabilities.graph_apply",
  "capabilities.layout_apply", "capture", "captureImmutableGraph.measurements",
  "captureRevision", "enumerateLinks", "enumerateLiveLinks",
  "forbidden-forward", "graphLinkIdentitiesV1", "identity_contract_v1",
  "immutablePreviewProjection", "intent_graph_adapter.acquire",
  "intent_graph_adapter.enumerateNodes", "intent_graph_adapter.repaint",
  "nativeNormalization", "nativeNormalization.rebuildSockets",
  "nativeNormalization.widgets", "nodeIdentityV1", "preflightDeltaPlan",
  "projectGraphV1", "projectLayoutFromCandidate", "projection-only",
  "repaint", "resolveLiveNodeByUid", "resolveNodeFactory",
  "resolveStableIdentity", "restoreAuthorized", "stablePreviewLinkMapV1",
  "test-only",
]);
const EXPLICIT_STATUS_ROWS = Object.freeze({
  permitted_canvas: new Set(["NGA-022"]),
  permitted_harness: new Set(["NGA-007", "NGA-075"]),
});
const PLACEHOLDERS = new Set(["x", "xx", "todo", "tbd", "unknown", "n/a"]);

function assertExactKeys(value, expected, label) {
  assert.deepEqual(Object.keys(value).sort(), [...expected].sort(), `${label} has unknown or missing keys`);
}

function assertMeaningful(value, label, { min = 3, pattern = null } = {}) {
  assert.equal(typeof value, "string", `${label} must be a string`);
  const normalized = value.trim().toLowerCase();
  assert.ok(value.trim().length >= min, `${label} is not meaningful`);
  assert.ok(!PLACEHOLDERS.has(normalized), `${label} is a placeholder`);
  if (pattern) assert.match(value, pattern, `${label} has invalid format`);
}

function validateFixtureProof(reference, rowId) {
  assert.ok(reference && typeof reference === "object" && !Array.isArray(reference), `${rowId} fixture_proof must be an object`);
  const keys = Object.keys(reference).sort();
  assert.ok(
    JSON.stringify(keys) === JSON.stringify(["path"])
      || JSON.stringify(keys) === JSON.stringify(["identifier", "path"]),
    `${rowId} fixture_proof has unknown or missing keys`,
  );
  assertMeaningful(reference.path, `${rowId} fixture_proof path`, { min: 8 });
  const relativePath = reference.path;
  assert.ok(!path.isAbsolute(relativePath), `${rowId} fixture_proof path must be repository-relative`);
  const absolutePath = path.resolve(root, relativePath);
  assert.ok(absolutePath.startsWith(`${root}${path.sep}`), `${rowId} fixture_proof escapes repository`);
  assert.ok(existsSync(absolutePath) && statSync(absolutePath).isFile(), `${rowId} fixture_proof path does not exist`);
  if (Object.hasOwn(reference, "identifier")) {
    assertMeaningful(reference.identifier, `${rowId} fixture_proof identifier`, { min: 4 });
    assert.ok(readFileSync(absolutePath, "utf8").includes(reference.identifier), `${rowId} fixture_proof identifier does not exist`);
  }
}

function validateSemanticConsistency(row) {
  if (row.support_status === "supported_adapter_owner") {
    assert.equal(row.semantic_owner, "intent_graph_adapter", `${row.id} supported adapter owner mismatch`);
    assert.equal(row.slice, "S2", `${row.id} supported adapter slice mismatch`);
    assert.ok(new Set([
      "canvas-draw", "capability-detect", "graph-acquire",
      "revision-capture", "serialize-capture",
    ]).has(row.normalization_category), `${row.id} supported adapter category mismatch`);
  } else if (row.support_status === "permitted_canvas") {
    assert.ok(EXPLICIT_STATUS_ROWS.permitted_canvas.has(row.id), `${row.id} is not an explicit permitted_canvas row`);
    assert.equal(row.semantic_owner, "comfy_adapter");
    assert.equal(row.slice, "S2");
    assert.equal(row.target_api, "intent_graph_adapter.repaint");
    assert.equal(row.normalization_category, "canvas-draw");
  } else if (row.support_status === "permitted_harness") {
    assert.ok(EXPLICIT_STATUS_ROWS.permitted_harness.has(row.id), `${row.id} is not an explicit permitted_harness row`);
    assert.equal(row.semantic_owner, "test-harness");
    assert.equal(row.slice, "-");
    assert.equal(row.target_api, "test-only");
    assert.equal(row.normalization_category, "harness");
  } else if (row.support_status === "projection_only") {
    assert.ok(new Set(["agent_status_poller", "projection_registry_v1", "vibecomfy_roundtrip"]).has(row.semantic_owner));
    assert.equal(row.slice, "-");
    assert.equal(row.normalization_category, "projection");
    assert.ok(new Set([
      "projection-only", "projectGraphV1", "graphLinkIdentitiesV1",
      "nodeIdentityV1", "stablePreviewLinkMapV1",
    ]).has(row.target_api), `${row.id} projection target mismatch`);
  } else if (row.support_status === "blocking_migration") {
    assert.equal(row.semantic_owner, "comfy_adapter");
    assert.equal(row.slice, "S4");
    assert.ok(new Set(["applyLayoutOperation", "projectLayoutFromCandidate"]).has(row.target_api));
    assert.ok(new Set(["layout-mutate", "layout-project"]).has(row.normalization_category));
  } else if (row.support_status === "migration_debt") {
    assert.ok(new Set(["comfy_adapter", "vibecomfy_roundtrip"]).has(row.semantic_owner));
    if (row.slice === "S2") {
      assert.ok(new Set(["NGA-010", "NGA-053"]).has(row.id), `${row.id} is not an explicit S2 migration-debt exception`);
      assert.equal(row.normalization_category, "graph-acquire");
      assert.equal(row.target_api, "intent_graph_adapter.acquire");
    } else {
      assert.ok(new Set(["S3", "S4"]).has(row.slice), `${row.id} migration debt requires a migration slice`);
    }
  }
  assert.equal(
    row.slice === "-",
    new Set(["projection_only", "permitted_harness"]).has(row.support_status),
    `${row.id} slice/status sentinel mismatch`,
  );
}

function validateLedger(ledger) {
  assert.ok(ledger && typeof ledger === "object" && !Array.isArray(ledger));
  assertExactKeys(ledger, LEDGER_TOP_LEVEL_KEYS, "ledger");
  assert.equal(ledger.contract, "native_authority_ledger_v1");
  assert.equal(ledger.schema_version, 1);
  assert.ok(Array.isArray(ledger.rows));
  const ids = new Set();
  const mappings = new Map();
  for (const row of ledger.rows) {
    assert.ok(row && typeof row === "object" && !Array.isArray(row));
    assertExactKeys(row, LEDGER_ROW_KEYS, row.id ?? "row");
    assert.match(row.id, /^NGA-\d{3}$/);
    assert.ok(!ids.has(row.id), `duplicate stable row id ${row.id}`);
    ids.add(row.id);
    assertMeaningful(row.file, `${row.id} file`, { pattern: /^[A-Za-z0-9_.-]+\.js$/ });
    assertMeaningful(row.region, `${row.id} region`, { pattern: /^(?:<module>|[A-Za-z_$][\w$]*)$/ });
    assertMeaningful(row.purpose, `${row.id} purpose`, { min: 10 });
    assert.ok(SEMANTIC_OWNERS.has(row.semantic_owner), `${row.id} unknown semantic_owner ${row.semantic_owner}`);
    assertMeaningful(row.target_api, `${row.id} target_api`, { pattern: /^[A-Za-z][A-Za-z0-9_.-]{2,80}$/ });
    assert.ok(TARGET_API_CATALOG.has(row.target_api), `${row.id} target_api is not in the closed catalog`);
    assert.ok(LEDGER_SLICES.has(row.slice), `${row.id} unknown slice ${row.slice}`);
    assertMeaningful(row.projection_identity_effect, `${row.id} projection_identity_effect`, { min: 4, pattern: /^[A-Za-z][A-Za-z0-9 /-]{3,100}$/ });
    assert.ok(NORMALIZATION_CATEGORIES.has(row.normalization_category), `${row.id} unknown normalization_category ${row.normalization_category}`);
    validateFixtureProof(row.fixture_proof, row.id);
    assert.ok(SUPPORT_STATUSES.has(row.support_status), `${row.id} unknown support_status ${row.support_status}`);
    validateSemanticConsistency(row);
    assert.ok(row.accesses && typeof row.accesses === "object" && !Array.isArray(row.accesses));
    assert.ok(Object.keys(row.accesses).length > 0);
    for (const [kind, count] of Object.entries(row.accesses)) {
      assert.ok(ACCESS_KINDS.has(kind), `${row.id} unknown access kind ${kind}`);
      assert.ok(Number.isInteger(count) && count > 0, `${row.id} invalid count for ${kind}`);
      const key = `${row.file}::${row.region}::${kind}`;
      assert.ok(!mappings.has(key), `duplicate source mapping ${key}: ${mappings.get(key)} and ${row.id}`);
      mappings.set(key, row.id);
    }
  }
  return mappings;
}

function ledgerInventory(ledger) {
  return ledger.rows.flatMap((row) => Object.entries(row.accesses).map(([kind, count]) => ({
    file: row.file,
    region: row.region,
    kind,
    count,
  }))).sort((left, right) => (
    left.file.localeCompare(right.file)
    || left.region.localeCompare(right.region)
    || left.kind.localeCompare(right.kind)
  ));
}

async function productionSources() {
  const files = (await readdir(web)).filter((name) => name.endsWith(".js")).sort();
  return Object.fromEntries(await Promise.all(files.map(async (name) => [name, await source(name)])));
}

function inventoryDiff(actual, expected) {
  const key = (entry) => `${entry.file}::${entry.region}::${entry.kind}`;
  const actualByKey = new Map(actual.map((entry) => [key(entry), entry]));
  const expectedByKey = new Map(expected.map((entry) => [key(entry), entry]));
  return {
    unclassified: actual.filter((entry) => !expectedByKey.has(key(entry))),
    changed: actual.filter((entry) => (
      expectedByKey.has(key(entry)) && expectedByKey.get(key(entry)).count !== entry.count
    )).map((entry) => ({ expected: expectedByKey.get(key(entry)), actual: entry })),
    stale: expected.filter((entry) => !actualByKey.has(key(entry))),
  };
}

test("intent_graph_adapter is the only public live-graph acquisition and repaint owner", async () => {
  const comfy = await source("comfy_adapter.js");
  for (const symbol of [
    "detectGraphApply",
    "detectGraphDeltaApply",
    "detectGraphLayoutApply",
    "getLiveGraph",
    "repaintGraph",
  ]) {
    assert.doesNotMatch(
      comfy,
      new RegExp(`export\\s+function\\s+${symbol}\\b`),
      `${symbol} must remain private to the low-level transitional substrate`,
    );
  }

  const adapter = await source("intent_graph_adapter.js");
  assert.match(adapter, /export function createIntentGraphAdapter\b/);
  assert.match(adapter, /projectGraphV1/);
  assert.match(adapter, /projectionReferenceV1/);

  assert.match(comfy, /from "\.\/intent_graph_adapter\.js"/);
  assert.match(functionBody(comfy, "graphCapability"), /createIntentGraphAdapter\(app\)\.capabilities\(\)/);
  assert.match(functionBody(comfy, "detectGraphDeltaApply"), /graphCapability\(app, "delta_apply"\)/);
  assert.match(functionBody(comfy, "detectGraphLayoutApply"), /graphCapability\(app, "layout_apply"\)/);
  assert.match(functionBody(comfy, "detectCapabilities"), /createIntentGraphAdapter\(app\)\.capabilities\(\)/);
});

test("slice-2 consumers use the adapter for capture, capability, revision, and repaint", async () => {
  const guard = await source("active_canvas_scope_guard.js");
  const replay = await source("agentic_replay.js");
  const picker = await source("preview_picker.js");
  const roundtrip = await source("vibecomfy_roundtrip.js");

  for (const [name, text] of [
    ["active_canvas_scope_guard.js", guard],
    ["agentic_replay.js", replay],
    ["preview_picker.js", picker],
    ["vibecomfy_roundtrip.js", roundtrip],
  ]) {
    assert.match(text, /from "\.\/intent_graph_adapter\.js"/, `${name} must import the adapter`);
  }

  assert.doesNotMatch(functionBody(guard, "resolveActiveCanvasScope"), /\.serialize\s*\(/);
  assert.doesNotMatch(functionBody(replay, "captureOriginalGraph"), /\.serialize\s*\(/);
  assert.doesNotMatch(functionBody(picker, "requestPreviewOverlayRepaint"), /setDirtyCanvas|canvas\?*\.draw/);
  assert.doesNotMatch(functionBody(roundtrip, "captureSerializedGraphForAgent"), /\.serialize\s*\(/);
  assert.match(functionBody(roundtrip, "captureLiveCanvasRevision"), /\.captureRevision\(\)/);
  assert.doesNotMatch(
    functionBody(roundtrip, "captureLiveCanvasRevision"),
    /app\?*\.canvas\?*\.graph|\.getRevision\s*\(|\._revision|\._version/,
  );
  assert.doesNotMatch(functionBody(roundtrip, "adapterCapabilitySnapshot"), /app\?*\.canvas\?*\.graph/);
});

test("Markdown ledger is an explicitly non-authoritative view of the machine ledger", async () => {
  const ledger = await source("native_normalization_ledger.md");
  assert.match(ledger, /NON-AUTHORITATIVE DERIVED VIEW/);
  assert.match(ledger, /native_authority_ledger_v1\.json/);
});

test("every native graph access in the complete production web scope is classified", async () => {
  const expected = JSON.parse(await readFile(nativeAuthorityLedgerPath, "utf8"));
  validateLedger(expected);
  const actual = inventoryForSources(await productionSources());
  if (process.env.VIBECOMFY_PRINT_NATIVE_ACCESS_INVENTORY === "1") {
    console.log(JSON.stringify({ contract: "native_authority_ledger_v1", entries: actual }, null, 2));
  }
  const diff = inventoryDiff(actual, ledgerInventory(expected));
  assert.deepEqual(diff, { unclassified: [], changed: [], stale: [] }, [
    "Native graph access inventory drifted.",
    "Route the access through intent_graph_adapter.js or classify intentional S3/S4 debt",
    "in tests/fixtures/agent_edit/native_authority_ledger_v1.json.",
    JSON.stringify(diff, null, 2),
    "Canonical observed inventory:",
    JSON.stringify({ contract: "native_authority_ledger_v1", entries: actual }, null, 2),
  ].join("\n"));
});

test("machine ledger rejects duplicate source mapping and duplicate stable IDs", () => {
  const row = {
    id: "NGA-001", file: "existing.js", region: "known", accesses: { graph_acquire: 1 },
    purpose: "Classify sentinel graph acquisition", semantic_owner: "intent_graph_adapter",
    target_api: "acquire", slice: "S2", projection_identity_effect: "typed capability",
    normalization_category: "graph-acquire", fixture_proof: {
      path: "tests/browser/intent_graph_adapter_ownership_static.test.mjs",
      identifier: "inventory sentinel rejects a new access region",
    },
    support_status: "supported_adapter_owner",
  };
  assert.throws(() => validateLedger({ contract: "native_authority_ledger_v1", schema_version: 1, rows: [row, { ...row }] }), /duplicate stable row id/);
  assert.throws(() => validateLedger({ contract: "native_authority_ledger_v1", schema_version: 1, rows: [row, { ...row, id: "NGA-002" }] }), /duplicate source mapping/);
});

test("machine ledger schema is closed and rejects placeholder metadata", () => {
  const row = {
    id: "NGA-001", file: "existing.js", region: "known", accesses: { graph_acquire: 1 },
    purpose: "Classify sentinel graph acquisition", semantic_owner: "intent_graph_adapter",
    target_api: "acquire", slice: "S2", projection_identity_effect: "typed capability",
    normalization_category: "graph-acquire", fixture_proof: {
      path: "tests/browser/intent_graph_adapter_ownership_static.test.mjs",
      identifier: "inventory sentinel rejects a new access region",
    },
    support_status: "supported_adapter_owner",
  };
  const ledger = (nextRow = row, extra = {}) => ({
    contract: "native_authority_ledger_v1", schema_version: 1, rows: [nextRow], ...extra,
  });
  assert.throws(() => validateLedger(ledger(row, { surprise: true })), /ledger has unknown or missing keys/);
  assert.throws(() => validateLedger(ledger({ ...row, surprise: true })), /has unknown or missing keys/);
  assert.throws(() => validateLedger(ledger({ ...row, accesses: { rogue_access: 1 } })), /unknown access kind/);
  assert.throws(() => validateLedger(ledger({ ...row, slice: "S9" })), /unknown slice/);
  assert.throws(() => validateLedger(ledger({ ...row, semantic_owner: "somewhere" })), /unknown semantic_owner/);
  assert.throws(() => validateLedger(ledger({ ...row, target_api: "not an api" })), /invalid format/);
  assert.throws(() => validateLedger(ledger({ ...row, normalization_category: "misc" })), /unknown normalization_category/);
  assert.throws(() => validateLedger(ledger({ ...row, projection_identity_effect: "x" })), /not meaningful/);
  assert.throws(() => validateLedger(ledger({ ...row, support_status: "maybe" })), /unknown support_status/);
  assert.throws(() => validateLedger(ledger({ ...row, purpose: "x" })), /not meaningful/);
  assert.throws(() => validateLedger(ledger({ ...row, fixture_proof: { path: "unicorn test that does not exist" } })), /path does not exist/);
});

test("all 78 rows pass semantic anchors and exact invented mutations fail", async () => {
  const authority = JSON.parse(await readFile(nativeAuthorityLedgerPath, "utf8"));
  assert.equal(authority.rows.length, 78);
  assert.deepEqual(
    authority.rows.map((row) => row.id).sort(),
    Array.from({ length: 78 }, (_, index) => `NGA-${String(index + 1).padStart(3, "0")}`),
  );
  assert.doesNotThrow(() => validateLedger(authority));

  const withMutation = (predicate, mutation) => {
    const changed = structuredClone(authority);
    const row = changed.rows.find(predicate);
    assert.ok(row, "sentinel row must exist");
    Object.assign(row, mutation);
    return changed;
  };
  assert.throws(
    () => validateLedger(withMutation((row) => row.id === "NGA-001", {
      fixture_proof: { path: "unicorn test that does not exist" },
    })),
    /fixture_proof path does not exist/,
  );
  assert.throws(
    () => validateLedger(withMutation((row) => row.id === "NGA-001", {
      fixture_proof: {
        path: "vibecomfy/comfy_nodes/web/intent_graph_adapter.js",
        identifier: "unicorn test that does not exist",
      },
    })),
    /fixture_proof identifier does not exist/,
  );
  assert.throws(
    () => validateLedger(withMutation((row) => row.id === "NGA-001", {
      target_api: "doesNotExistAnywhere",
    })),
    /target_api is not in the closed catalog/,
  );
  assert.throws(
    () => validateLedger(withMutation((row) => row.support_status === "projection_only", {
      support_status: "permitted_harness",
    })),
    /not an explicit permitted_harness row/,
  );
  assert.throws(
    () => validateLedger(withMutation((row) => row.support_status === "migration_debt", {
      slice: "-",
    })),
    /migration debt requires a migration slice/,
  );
  assert.throws(
    () => validateLedger(withMutation((row) => row.support_status === "permitted_harness", {
      slice: "S2",
    })),
    /strictEqual|Expected values to be strictly equal/,
  );
});

test("inventory sentinel rejects a new access region in an already-listed file", () => {
  const baseline = {
    "existing.js": "function known(app) { return app.canvas.graph; }",
  };
  const expected = inventoryForSources(baseline);
  const changed = {
    "existing.js": `${baseline["existing.js"]}\nfunction rogue(app) { return app.canvas.graph; }`,
  };
  const diff = inventoryDiff(inventoryForSources(changed), expected);
  assert.deepEqual(diff.unclassified, [
    { file: "existing.js", region: "rogue", kind: "graph_acquire", count: 1 },
  ]);
});

test("inventory sentinel rejects a new access inside an existing classified region", () => {
  const baseline = {
    "existing.js": "function known(app) { const graph = app.canvas.graph; return graph; }",
  };
  const expected = inventoryForSources(baseline);
  const changed = {
    "existing.js": "function known(app) { const graph = app.canvas.graph; graph.clear(); return graph; }",
  };
  const diff = inventoryDiff(inventoryForSources(changed), expected);
  assert.deepEqual(diff.unclassified, [
    { file: "existing.js", region: "known", kind: "graph_clear", count: 1 },
  ]);
});

test("inventory sentinel detects an extra occurrence of an already-classified access kind", () => {
  const baseline = {
    "existing.js": "function known(app) { return app.canvas.graph; }",
  };
  const expected = inventoryForSources(baseline);
  const changed = {
    "existing.js": "function known(app) { return app.canvas.graph || app.graph; }",
  };
  const diff = inventoryDiff(inventoryForSources(changed), expected);
  assert.equal(diff.changed.length, 1);
  assert.equal(diff.changed[0].expected.count, 1);
  assert.equal(diff.changed[0].actual.count, 2);
});

test("inventory sentinel detects stale ledger mappings", () => {
  const expected = inventoryForSources({ "existing.js": "function known(app) { return app.canvas.graph; }" });
  const diff = inventoryDiff([], expected);
  assert.deepEqual(diff.stale, expected);
});

test("scanner sentinel detects arbitrary aliases from computed graph acquisition", () => {
  const inventory = inventoryForSources({
    "computed.js": `function probe(app) {
      const g = app.canvas["graph"];
      g["_nodes"];
      g.clear?.();
    }`,
  });
  assert.deepEqual(inventory, [
    { file: "computed.js", region: "probe", kind: "graph_acquire", count: 1 },
    { file: "computed.js", region: "probe", kind: "graph_clear", count: 1 },
    { file: "computed.js", region: "probe", kind: "native_nodes", count: 1 },
  ]);
});

test("scanner sentinel follows chained graph aliases to a fixed point", () => {
  const inventory = inventoryForSources({
    "chained.js": `function probe(app) {
      const g = app.canvas.graph;
      const h = g;
      const finalGraph = h;
      finalGraph.configure({});
      finalGraph._groups;
    }`,
  });
  assert.deepEqual(inventory, [
    { file: "chained.js", region: "probe", kind: "graph_acquire", count: 1 },
    { file: "chained.js", region: "probe", kind: "graph_configure", count: 1 },
    { file: "chained.js", region: "probe", kind: "native_groups", count: 1 },
  ]);
});

test("scanner sentinel detects destructured graph aliases", () => {
  const inventory = inventoryForSources({
    "destructured.js": `function probe(app) {
      const { graph: g } = app.canvas;
      g.links;
      g.serialize();
    }`,
  });
  assert.deepEqual(inventory, [
    { file: "destructured.js", region: "probe", kind: "graph_acquire", count: 1 },
    { file: "destructured.js", region: "probe", kind: "native_links", count: 1 },
    { file: "destructured.js", region: "probe", kind: "serialize", count: 1 },
  ]);
});

test("scanner sentinel detects group construction/configuration and socket/widget rebuild", () => {
  const inventory = inventoryForSources({
    "mutation.js": `function mutate(node, group) {
      const next = new LiteGraph.LGraphGroup("x");
      group.configure({});
      node.removeInput(0);
      node.addOutput("x", "IMAGE");
      node.widgets_values = [];
    }`,
  });
  assert.deepEqual(inventory, [
    { file: "mutation.js", region: "mutate", kind: "group_configure", count: 1 },
    { file: "mutation.js", region: "mutate", kind: "group_construct", count: 1 },
    { file: "mutation.js", region: "mutate", kind: "socket_rebuild", count: 2 },
    { file: "mutation.js", region: "mutate", kind: "widget_rebuild", count: 1 },
  ]);
});

test("scanner sentinel detects stable identity, native normalization, and canvas invalidation", () => {
  const inventory = inventoryForSources({
    "owners.js": `function inspect(node, canvas) {
      canonicalNodeUid(node);
      node.properties.vibecomfy_uid;
      normalizeLiveExecNodesForSerialization();
      canvas.setDirty(true, true);
      canvas.draw(true, true);
    }`,
  });
  assert.deepEqual(inventory, [
    { file: "owners.js", region: "inspect", kind: "canvas_dirty", count: 1 },
    { file: "owners.js", region: "inspect", kind: "canvas_draw", count: 1 },
    { file: "owners.js", region: "inspect", kind: "native_normalization", count: 1 },
    { file: "owners.js", region: "inspect", kind: "stable_identity", count: 2 },
  ]);
});
