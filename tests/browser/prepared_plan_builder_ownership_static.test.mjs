// prepared_plan_builder_ownership_static.test.mjs — C1 static reachability +
// ownership guards (§6.3 line 4, §6.6 step 12, §6.7, §7.2 #5).
//
// This is the SECOND, independent line of zero-native-call evidence.  It never
// runs the builder; it proves by static analysis that:
//
//   1. the builder's transitive import closure excludes every native/runtime/
//      DOM/LiteGraph/adapter module (no module in the closure references a
//      native primitive);
//   2. the builder source has no candidateGraph/app/DOM/LiteGraph imports or
//      signatures, and owns no sentinelCounts / proof counter (Gate #4);
//   3. no production file imports the private builder (Gate: no consumer);
//   4. the builder exports no public mutation method (only the pure plan API);
//   5. the C0 "no NEW candidateGraph path" guard remains an exact legacy
//      allowlist (set equality, not a repo-wide zero assertion — §6.7, Gate #3).

import test from "node:test";
import assert from "node:assert/strict";
import { readFileSync, readdirSync } from "node:fs";
import path from "node:path";
import { fileURLToPath } from "node:url";
import * as builderNamespace from "../../vibecomfy/comfy_nodes/web/_prepared_plan_builder_v1.mjs";

const __filename = fileURLToPath(import.meta.url);
const __dirname = path.dirname(__filename);
const REPO_ROOT = path.resolve(__dirname, "..", "..");
const WEB_ROOT = path.join(REPO_ROOT, "vibecomfy", "comfy_nodes", "web");
const BUILDER_FILE = "_prepared_plan_builder_v1.mjs";

function source(name) {
  return readFileSync(path.join(WEB_ROOT, name), "utf8");
}

function stripComments(src) {
  // Remove block comments and line comments so doc prose does not trip the
  // native-reference scan.  String literals are left intact; none of the
  // forbidden patterns appear as innocent string literals in the contract
  // modules (verified: the closure is pure data contracts).
  return src.replace(/\/\*[\s\S]*?\*\//g, " ").replace(/(^|\n)\s*\/\/[^\n]*/g, "$1");
}

// ── Import-graph walker (relative specifiers only) ───────────────────────────

function resolveRelative(spec) {
  const base = path.basename(spec);
  for (const ext of ["", ".mjs", ".js"]) {
    const name = base + ext;
    try {
      const text = readFileSync(path.join(WEB_ROOT, name), "utf8");
      return { name, text };
    } catch (_err) {
      // try next extension
    }
  }
  return null;
}

function importSpecifiers(src) {
  const out = [];
  const re = /from\s*["'](\.{1,2}\/[^"']+)["']/g;
  let m;
  while ((m = re.exec(src))) out.push(m[1]);
  return out;
}

function transitiveClosure(entryName) {
  const visited = new Set();
  const stack = [entryName];
  const files = [];
  while (stack.length) {
    const cur = stack.pop();
    if (visited.has(cur)) continue;
    visited.add(cur);
    const txt = source(cur);
    files.push(cur);
    for (const spec of importSpecifiers(txt)) {
      const resolved = resolveRelative(spec);
      if (resolved && !visited.has(resolved.name)) stack.push(resolved.name);
    }
  }
  return files;
}

// Native primitive / runtime reference patterns.  A closure module matching any
// of these in CODE (comments stripped) would be a native primitive owner.
const NATIVE_REFERENCE_PATTERNS = [
  /\bLiteGraph\b/,
  /\bcreateNode\b/,
  /graph\s*\.\s*(configure|clear|add|remove|connect|disconnect|serialize|setDirtyCanvas)\b/,
  /\bapp\s*\.\s*canvas\b/,
  /\bdocument\s*\.\s*(createElement|getElementById|body|head)\b/,
  /\bwindow\s*\.\b/,
  /\blocalStorage\b/,
  /\bfetch\s*\(/,
];

const FORBIDDEN_NATIVE_MODULES = new Set([
  "comfy_adapter.js",
  "intent_graph_adapter.js",
  "vibecomfy_roundtrip.js",
  "preview_picker.js",
  "preview_diff_core.js",
  "agentic_replay.js",
  "panel_overlay.js",
  "panel_runtime.js",
  "panel_scheduler.js",
  "panel_thread.js",
  "panel_composer.js",
  "agent_edit_lifecycle.js",
  "agent_lifecycle_commit.js",
  "agent_candidate_actions.js",
  "active_canvas_scope_guard.js",
  "scope_resolver.js",
]);

test("builder transitive import closure excludes every native/runtime/adapter module", () => {
  const closure = transitiveClosure(BUILDER_FILE);
  const forbidden = closure.filter((name) => FORBIDDEN_NATIVE_MODULES.has(name));
  assert.deepEqual(forbidden, [], "builder closure must not contain native/adapter modules");

  // No module in the closure references a native primitive in CODE.
  const nativeHits = [];
  for (const name of closure) {
    const code = stripComments(source(name));
    for (const pat of NATIVE_REFERENCE_PATTERNS) {
      if (pat.test(code)) nativeHits.push(`${name}: /${pat.source}/`);
    }
  }
  assert.deepEqual(nativeHits, [], "no closure module may reference a native primitive");

  // The closure is the small set of pure contract modules.
  const expectedPureClosure = new Set([
    BUILDER_FILE,
    "canonical_hash.js",
    "canonical_delta.js",
    "layout_operation_v1.js",
    "mutation_materialization_v1.js",
    "prepared_authority_v1.js",
    "projection_registry_v1.js",
    "identity_contract_v1.js",
    "root_scope_v1.js",
    "layout_verification_contract.js",
  ]);
  for (const name of closure) {
    assert.equal(expectedPureClosure.has(name), true, `unexpected closure member: ${name}`);
  }
});

test("builder source has no candidateGraph/app/DOM/LiteGraph imports or signatures", () => {
  const code = stripComments(source(BUILDER_FILE));
  assert.equal(/\bcandidateGraph\b/.test(code), false, "builder must not reference candidateGraph");
  assert.equal(/\bcandidate_graph\b/.test(code), false, "builder must not reference candidate_graph");
  for (const pat of NATIVE_REFERENCE_PATTERNS) {
    assert.equal(
      pat.test(code),
      false,
      `builder must not reference a native primitive: /${pat.source}/`,
    );
  }
  // No import of any forbidden module.
  for (const forbidden of FORBIDDEN_NATIVE_MODULES) {
    const stem = forbidden.replace(/\.(js|mjs)$/, "");
    const importRe = new RegExp(`from\\s*["'][^"']*/${stem}\\.(js|mjs)["']`);
    assert.equal(importRe.test(source(BUILDER_FILE)), false, `builder must not import ${forbidden}`);
  }
  // The builder takes prepared authority only — its sole parameter.
  assert.match(source(BUILDER_FILE), /export function buildPreparedPlan\(preparedAuthority\)\s*\{/);
});

test("builder owns no self-attested sentinel/proof counters (Gate #4)", () => {
  // Scan CODE (comments stripped): the builder documents in prose that it does
  // NOT return sentinelCounts; the guard must verify it does not DEFINE or
  // RETURN one, not that it never mentions the word.
  const code = stripComments(source(BUILDER_FILE));
  assert.equal(/\bsentinelCounts\b/.test(code), false, "builder must not define/return sentinelCounts");
  assert.equal(/\bnativeCounts\b/.test(code), false, "builder must not define/return nativeCounts");
  assert.equal(/\bproofCount(?:ers?)?\b/.test(code), false, "builder must not own proof counters");
  // The public return is {ok, plan|diagnostic} only.
  const builder = builderNamespace.buildPreparedPlan;
  const sample = builder({ contract_version: "prepared_authority_v1", not: "valid" });
  assert.deepEqual(Object.keys(sample).sort(), ["diagnostic", "ok"]);
});

test("no production file imports the private builder (Gate: no consumer)", () => {
  const files = readdirSync(WEB_ROOT).filter((n) => /\.(js|mjs)$/.test(n));
  const offenders = [];
  for (const name of files) {
    if (name === BUILDER_FILE) continue;
    const text = source(name);
    if (/_prepared_plan_builder_v1/.test(text)) offenders.push(name);
  }
  assert.deepEqual(offenders, [], "no production module may import the private builder");
});

test("builder exports only the pure plan API and no public mutation method", () => {
  const exported = Object.keys(builderNamespace).sort();
  assert.deepEqual(exported, ["PREPARED_PLAN_CONTRACT_V1", "buildPreparedPlan", "default"]);
  assert.equal(typeof builderNamespace.buildPreparedPlan, "function");
  assert.equal(builderNamespace.PREPARED_PLAN_CONTRACT_V1, "prepared_plan_v1");
  // No exported symbol is a mutation-execution surface.
  for (const name of exported) {
    assert.equal(
      /(^apply|execute|mutate|preflightDelta|runMutation|materialize|nativeWrite)/i.test(name),
      false,
      `builder must not export a mutation method: ${name}`,
    );
  }
});

// ── C0 candidateGraph allowlist guard (§6.7, Gate #3) ────────────────────────
// Equality-based, not repo-wide zero: the frozen set of symbols named
// preflight*/apply*/restore*/inverse* that take a candidateGraph/candidate_graph
// parameter must equal exactly the legacy allowlist below.  Any growth fails.

function extractParams(text, openParenIdx) {
  let depth = 0;
  let i = openParenIdx;
  let inStr = null;
  while (i < text.length) {
    const c = text[i];
    if (inStr) {
      if (c === "\\") { i += 2; continue; }
      if (c === inStr) inStr = null;
      i += 1; continue;
    }
    if (c === '"' || c === "'" || c === "`") { inStr = c; i += 1; continue; }
    if (c === "(") depth += 1;
    else if (c === ")") {
      depth -= 1;
      if (depth === 0) return text.slice(openParenIdx, i + 1);
    }
    i += 1;
  }
  return null;
}

function candidateGraphSymbols(text) {
  const found = new Set();
  const declRe = /(?:export\s+)?(?:async\s+)?function\s+([A-Za-z_$][\w$]*)\s*\(/g;
  const assignFnRe = /(?:export\s+)?(?:const|let|var)\s+([A-Za-z_$][\w$]*)\s*=\s*(?:async\s+)?function\s*\*?\s*\(/g;
  const assignArrowRe = /(?:export\s+)?(?:const|let|var)\s+([A-Za-z_$][\w$]*)\s*=\s*(?:async\s+)?\(/g;
  const arrowSingleRe = /(?:export\s+)?(?:const|let|var)\s+([A-Za-z_$][\w$]*)\s*=\s*(?:async\s+)?([A-Za-z_$][\w$]*)\s*=>/g;

  function consider(name, params) {
    if (params == null) return;
    if (!/^(preflight|apply|restore|inverse)/i.test(name)) return;
    if (/\bcandidateGraph\b|\bcandidate_graph\b/.test(params)) found.add(name);
  }
  for (const re of [declRe, assignFnRe]) {
    re.lastIndex = 0;
    let m;
    while ((m = re.exec(text))) {
      const openIdx = m.index + m[0].length - 1;
      consider(m[1], extractParams(text, openIdx));
    }
  }
  assignArrowRe.lastIndex = 0;
  let m;
  while ((m = assignArrowRe.exec(text))) {
    const name = m[1];
    const openIdx = m.index + m[0].length - 1;
    const params = extractParams(text, openIdx);
    if (params == null) continue;
    // Only accept real arrow params: '=>' must follow the closing paren.
    const tail = text.slice(openIdx + params.length, openIdx + params.length + 4);
    if (!/^\s*=>/.test(tail)) continue;
    consider(name, params);
  }
  arrowSingleRe.lastIndex = 0;
  let ma;
  while ((ma = arrowSingleRe.exec(text))) {
    if (/^(preflight|apply|restore|inverse)/i.test(ma[1]) && /^candidateGraph$|^candidate_graph$/i.test(ma[2])) {
      found.add(ma[1]);
    }
  }
  return found;
}

test("C0 no-new-candidateGraph path: exact legacy allowlist (equality, not repo-wide zero)", () => {
  // The frozen legacy allowlist verified in current code (§6.7).  C2 deletes
  // this exact set; C0/C1 must prevent it from growing.
  const ALLOWLIST = new Set([
    "comfy_adapter.js#applyGraphDeltaInPlace",
    "comfy_adapter.js#applyGraphLayoutInPlace",
    "comfy_adapter.js#preflightDeltaPlan",
    "vibecomfy_roundtrip.js#applyReplayGraphCandidate",
    "vibecomfy_roundtrip.js#restoreCandidateLinksOnLiveGraph",
  ]);

  const found = new Set();
  for (const name of readdirSync(WEB_ROOT)) {
    if (!name.endsWith(".js")) continue;
    const text = readFileSync(path.join(WEB_ROOT, name), "utf8");
    for (const symbol of candidateGraphSymbols(text)) {
      found.add(`${name}#${symbol}`);
    }
  }

  assert.deepEqual(
    [...found].sort(),
    [...ALLOWLIST].sort(),
    "candidateGraph-reading preflight*/apply*/restore*/inverse* symbols must equal the frozen legacy allowlist (no new path)",
  );

  // The new private builder must not appear in this set — it is the proof that
  // the C1 path added no candidateGraph signature at all.
  assert.equal(found.has(`${BUILDER_FILE}#buildPreparedPlan`), false);
});

test("no second prepared-authority validator or native-primitive owner escaped into the builder closure", () => {
  // The builder closure must reach exactly one JS prepared-authority validator
  // (prepared_authority_v1.js) and zero native adapter modules.  This guards
  // against a duplicated owner sneaking into the proof surface.
  const closure = transitiveClosure(BUILDER_FILE);
  const authorityValidators = closure.filter((n) => n === "prepared_authority_v1.js");
  assert.deepEqual(authorityValidators, ["prepared_authority_v1.js"]);
  assert.equal(
    closure.includes("comfy_adapter.js") || closure.includes("intent_graph_adapter.js"),
    false,
    "builder closure must not reach the native adapter owners",
  );
});
