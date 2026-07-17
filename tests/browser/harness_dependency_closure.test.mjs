// harness_dependency_closure.test.mjs — guards the browser harness's temp-root
// JS dependency staging so that adding a new web module import (e.g.
// layout_operation_v1.js, mutation_materialization_v1.js — pulled in
// transitively via prepared_authority_v1.js) cannot produce ERR_MODULE_NOT_FOUND
// at module-load time.
//
// `verifyStagedDependencyClosure` walks the transitive closure of relative ESM
// imports starting from every staged entry module and fails with a precise
// diagnostic when a transitive dependency is missing from the staging manifest,
// when an external (../) import is not allowlisted, or when a bare (non-relative)
// import is not declared.  See harness.mjs for the implementation.

import test from "node:test";
import assert from "node:assert/strict";
import { mkdtemp, mkdir, writeFile, rm } from "node:fs/promises";
import { tmpdir } from "node:os";
import path from "node:path";
import { fileURLToPath } from "node:url";

import {
  STAGED_WEB_MODULES,
  ALLOWED_EXTERNAL_RELATIVE_IMPORTS,
  ALLOWED_BARE_IMPORTS,
  verifyStagedDependencyClosure,
  _collectImportSpecifiers,
} from "./harness.mjs";

const REPO_ROOT = path.resolve(
  path.dirname(fileURLToPath(import.meta.url)),
  "..",
  "..",
);
const WEB_SOURCE_ROOT = path.join(REPO_ROOT, "vibecomfy", "comfy_nodes", "web");

test("the production manifest is the canonical set of staged web modules", () => {
  // Guard the manifest shape itself so a future edit can't silently regress it
  // (e.g. duplicates, non-.js/.mjs entries, or the regression we are fixing).
  assert.ok(Array.isArray(STAGED_WEB_MODULES), "STAGED_WEB_MODULES must be an array");
  assert.ok(STAGED_WEB_MODULES.length >= 36, "expected the full web module manifest");

  const seen = new Set();
  for (const name of STAGED_WEB_MODULES) {
    assert.ok(
      /\.(js|mjs)$/.test(name),
      `manifest entry "${name}" must be a .js/.mjs file`,
    );
    assert.equal(seen.has(name), false, `duplicate manifest entry: ${name}`);
    seen.add(name);
  }
});

test("the two C1 transitive dependencies are present in the staging manifest", () => {
  // prepared_authority_v1.js imports layout_operation_v1.js and
  // mutation_materialization_v1.js; both MUST be staged or the harness loads
  // fail with ERR_MODULE_NOT_FOUND.
  assert.ok(
    STAGED_WEB_MODULES.includes("layout_operation_v1.js"),
    "layout_operation_v1.js must be staged (imported by prepared_authority_v1.js)",
  );
  assert.ok(
    STAGED_WEB_MODULES.includes("mutation_materialization_v1.js"),
    "mutation_materialization_v1.js must be staged (imported by prepared_authority_v1.js)",
  );
  assert.ok(STAGED_WEB_MODULES.includes("prepared_authority_v1.js"));
});

test("transitive dependency closure of the production manifest is complete", async () => {
  const result = await verifyStagedDependencyClosure({
    webSourceRoot: WEB_SOURCE_ROOT,
    stagedModuleNames: STAGED_WEB_MODULES,
  });
  assert.equal(
    result.ok,
    true,
    `staged dependency closure must be complete; errors:\n${result.errors
      .map((e) => `  - [${e.kind}] ${e.message}`)
      .join("\n")}`,
  );
  assert.deepEqual(result.errors, []);
});

test("closure is verified starting from EVERY staged entry module", async () => {
  // Per-entry sweep: each staged module's own transitive closure must be fully
  // staged.  This localises any future regression to the offending entry.
  const failures = [];
  for (const entry of STAGED_WEB_MODULES) {
    const result = await verifyStagedDependencyClosure({
      webSourceRoot: WEB_SOURCE_ROOT,
      stagedModuleNames: STAGED_WEB_MODULES,
    });
    const entryErrors = result.errors.filter(
      (e) => e.entry === entry || e.module === entry,
    );
    if (entryErrors.length > 0) {
      failures.push({ entry, entryErrors });
    }
  }
  assert.deepEqual(failures, [], "no entry module may have a missing transitive dep");
});

test("closure reaches the C1 modules through prepared_authority_v1.js", async () => {
  // Confirms the guard actually walks transitively (not just direct imports).
  const result = await verifyStagedDependencyClosure({
    webSourceRoot: WEB_SOURCE_ROOT,
    stagedModuleNames: ["prepared_authority_v1.js"],
  });
  // prepared_authority_v1.js imports layout_operation_v1.js,
  // mutation_materialization_v1.js, canonical_hash.js, etc. With only the entry
  // staged, those should all be flagged as missing-staged-module.
  const resolved = result.errors.map((e) => e.resolved).filter(Boolean);
  assert.ok(
    resolved.includes("layout_operation_v1.js"),
    "closure must reach layout_operation_v1.js via prepared_authority_v1.js",
  );
  assert.ok(
    resolved.includes("mutation_materialization_v1.js"),
    "closure must reach mutation_materialization_v1.js via prepared_authority_v1.js",
  );
  for (const e of result.errors) {
    assert.equal(e.kind, "missing-staged-module");
    assert.ok(e.message.includes("ERR_MODULE_NOT_FOUND"));
  }
});

test("missing transitive dep yields a precise missing-staged-module diagnostic", async () => {
  // Simulate the original regression: manifest omits layout_operation_v1.js.
  const incomplete = STAGED_WEB_MODULES.filter(
    (n) => n !== "layout_operation_v1.js",
  );
  const result = await verifyStagedDependencyClosure({
    webSourceRoot: WEB_SOURCE_ROOT,
    stagedModuleNames: incomplete,
  });
  assert.equal(result.ok, false);
  const hit = result.errors.find(
    (e) =>
      e.kind === "missing-staged-module" &&
      e.resolved === "layout_operation_v1.js" &&
      e.module === "prepared_authority_v1.js",
  );
  assert.ok(hit, "must precisely report prepared_authority_v1.js -> layout_operation_v1.js");
  assert.match(hit.message, /prepared_authority_v1\.js/);
  assert.match(hit.message, /layout_operation_v1\.js/);
  assert.match(hit.message, /ERR_MODULE_NOT_FOUND/);
});

test("missing source file yields a precise missing-source diagnostic", async () => {
  const result = await verifyStagedDependencyClosure({
    webSourceRoot: WEB_SOURCE_ROOT,
    stagedModuleNames: [...STAGED_WEB_MODULES, "does_not_exist_v1.js"],
  });
  assert.equal(result.ok, false);
  const hit = result.errors.find((e) => e.kind === "missing-source");
  assert.ok(hit, "must report the phantom staged module as missing-source");
  assert.equal(hit.module, "does_not_exist_v1.js");
});

test("undeclared bare import is rejected with a precise diagnostic", async () => {
  const sandbox = await mkdtemp(path.join(tmpdir(), "vibecomfy-closure-bare-"));
  try {
    await mkdir(path.join(sandbox, "sub"), { recursive: true });
    await writeFile(
      path.join(sandbox, "entry.js"),
      'import { x } from "some-npm-pkg";\nexport const entry = x;\n',
    );
    const result = await verifyStagedDependencyClosure({
      webSourceRoot: sandbox,
      stagedModuleNames: ["entry.js"],
    });
    assert.equal(result.ok, false);
    const hit = result.errors.find((e) => e.kind === "undeclared-bare-import");
    assert.ok(hit, "must flag the undeclared bare import");
    assert.equal(hit.module, "entry.js");
    assert.equal(hit.specifier, "some-npm-pkg");
    assert.match(hit.message, /ALLOWED_BARE_IMPORTS/);
  } finally {
    await rm(sandbox, { recursive: true, force: true });
  }
});

test("declared bare import is accepted (explicit allowlist path)", async () => {
  const sandbox = await mkdtemp(path.join(tmpdir(), "vibecomfy-closure-bare-ok-"));
  try {
    await writeFile(
      path.join(sandbox, "entry.js"),
      'import { webcrypto } from "node:crypto";\nexport const entry = webcrypto;\n',
    );
    const result = await verifyStagedDependencyClosure({
      webSourceRoot: sandbox,
      stagedModuleNames: ["entry.js"],
      allowedBareImports: new Set(["node:crypto"]),
    });
    assert.equal(result.ok, true, result.errors.map((e) => e.message).join("\n"));
  } finally {
    await rm(sandbox, { recursive: true, force: true });
  }
});

test("undeclared external relative import is rejected with a precise diagnostic", async () => {
  const sandbox = await mkdtemp(path.join(tmpdir(), "vibecomfy-closure-ext-"));
  try {
    await writeFile(
      path.join(sandbox, "entry.js"),
      'import { x } from "../../untracked/thing.js";\nexport const entry = x;\n',
    );
    const result = await verifyStagedDependencyClosure({
      webSourceRoot: sandbox,
      stagedModuleNames: ["entry.js"],
    });
    assert.equal(result.ok, false);
    const hit = result.errors.find((e) => e.kind === "undeclared-external-import");
    assert.ok(hit, "must flag the undeclared ../ import");
    assert.equal(hit.specifier, "../../untracked/thing.js");
    assert.match(hit.message, /ALLOWED_EXTERNAL_RELATIVE_IMPORTS/);
  } finally {
    await rm(sandbox, { recursive: true, force: true });
  }
});

test("allowlisted external relative imports (scripts/app.js, scripts/api.js) are accepted", () => {
  // The ComfyUI globals are staged under comfyRoot/scripts; they must remain
  // allowlisted so the roundtrip entry resolves them at runtime.
  assert.ok(ALLOWED_EXTERNAL_RELATIVE_IMPORTS.has("../../scripts/app.js"));
  assert.ok(ALLOWED_EXTERNAL_RELATIVE_IMPORTS.has("../../scripts/api.js"));
});

test("_collectImportSpecifiers splits relative and bare specifiers and ignores comments", () => {
  const src = [
    'import { a } from "./sibling.js";',
    'export { b } from "../parent/other.js";',
    '// import { fake } from "./notreal.js";',
    '/* import { alsoFake } from "pkg-fake"; */',
    'const dyn = import("./lazy.js");',
    'import "./side-effect.js";',
    'import { c } from "lit";',
  ].join("\n");
  const { relative, bare } = _collectImportSpecifiers(src);
  // Order is irrelevant — the guard dedupes via Set.  Assert exact membership.
  assert.deepEqual(new Set(relative), new Set([
    "../parent/other.js",
    "./lazy.js",
    "./side-effect.js",
    "./sibling.js",
  ]));
  assert.equal(relative.length, 4, "no duplicate relative specifiers");
  // Comments must NOT contribute specifiers; only the real `lit` bare import.
  assert.deepEqual(new Set(bare), new Set(["lit"]));
  assert.equal(bare.length, 1);
});
