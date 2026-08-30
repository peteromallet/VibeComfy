import assert from "node:assert/strict";
import fs from "node:fs/promises";
import os from "node:os";
import path from "node:path";
import test from "node:test";

import {
  LauncherFailure,
  pruneSuccessfulPlaywrightArtifacts,
  resolveProviderFixtureDir,
  resolvePythonExecutable,
  runEntrypoint,
  sanitizeJsonArtifact,
  sanitizeText,
} from "./run.mjs";

const FAILURE_EXPECTATIONS = {
  MISSING_COMFYUI: "preflight",
  MALFORMED_FIXTURES: "preflight",
  MISSING_CHROMIUM: "preflight",
  COMFYUI_START_FAILED: "readiness",
  COMFYUI_EARLY_EXIT: "readiness",
  READINESS_TIMEOUT: "readiness",
  READINESS_NOT_READY: "readiness",
  PLAYWRIGHT_START_FAILED: "playwright",
  PLAYWRIGHT_FAILED: "playwright",
  TEARDOWN_FAILED: "teardown",
};

test("launcher failure contract assigns distinct codes, phases, and remediation", () => {
  for (const [code, phase] of Object.entries(FAILURE_EXPECTATIONS)) {
    const failure = new LauncherFailure(code, `failure ${code}`);
    assert.equal(failure.code, code);
    assert.equal(failure.phase, phase);
    assert.ok(failure.remediation.length > 20, `${code} needs actionable remediation`);
  }
  assert.equal(new Set(Object.keys(FAILURE_EXPECTATIONS)).size, Object.keys(FAILURE_EXPECTATIONS).length);
});

test("launcher sanitizer removes credential values, credential query parameters, and private roots", () => {
  const original = process.env.VIBECOMFY_TEST_API_KEY;
  process.env.VIBECOMFY_TEST_API_KEY = "super-secret-value";
  try {
    const privateRoot = path.join(os.homedir(), "private", "checkout");
    const sanitized = sanitizeText(
      `${privateRoot} token=super-secret-value https://example.test/?key=another-secret`,
    );
    assert.doesNotMatch(sanitized, /super-secret-value|another-secret/);
    assert.doesNotMatch(sanitized, new RegExp(os.homedir().replace(/[.*+?^${}()|[\]\\]/g, "\\$&")));
    assert.match(sanitized, /<redacted>/);
    assert.match(sanitized, /<home>/);
  } finally {
    if (original === undefined) delete process.env.VIBECOMFY_TEST_API_KEY;
    else process.env.VIBECOMFY_TEST_API_KEY = original;
  }
});

test("launcher sanitizes nested native Playwright JSON before publication", async () => {
  const root = await fs.mkdtemp(path.join(os.tmpdir(), "vibecomfy-playwright-json-"));
  const resultPath = path.join(root, "results.json");
  const privateFile = path.join(os.homedir(), "checkout", "tests", "e2e", "spec.mjs");
  await fs.writeFile(resultPath, JSON.stringify({ suites: [{ file: privateFile, errors: [privateFile] }] }));
  try {
    const sanitized = await sanitizeJsonArtifact(resultPath);
    assert.doesNotMatch(JSON.stringify(sanitized), new RegExp(os.homedir().replace(/[.*+?^${}()|[\]\\]/g, "\\$&")));
    assert.match(sanitized.suites[0].file, /^<home>/);
    assert.deepEqual(JSON.parse(await fs.readFile(resultPath, "utf8")), sanitized);
  } finally {
    await fs.rm(root, { recursive: true, force: true });
  }
});

test("launcher retains the HTML viewer only for failed Playwright runs", async () => {
  const root = await fs.mkdtemp(path.join(os.tmpdir(), "vibecomfy-playwright-html-"));
  const htmlDir = path.join(root, "html-report");
  await fs.mkdir(htmlDir, { recursive: true });
  await fs.writeFile(path.join(htmlDir, "index.html"), "bundled viewer", "utf8");
  try {
    await pruneSuccessfulPlaywrightArtifacts(root);
    await assert.rejects(fs.access(htmlDir));
  } finally {
    await fs.rm(root, { recursive: true, force: true });
  }
});

test("missing ComfyUI fails closed with a machine-readable sanitized artifact", async () => {
  const root = await fs.mkdtemp(path.join(os.tmpdir(), "vibecomfy-launcher-missing-"));
  const artifactDir = path.join(root, "artifacts");
  const previous = process.env.VIBECOMFY_E2E_ARTIFACT_DIR;
  process.env.VIBECOMFY_E2E_ARTIFACT_DIR = artifactDir;
  try {
    const exitCode = await runEntrypoint(["--comfyui-dir", path.join(root, "missing"), "--launcher-only"]);
    assert.equal(exitCode, 1);
    const result = JSON.parse(await fs.readFile(path.join(artifactDir, "launcher-result.json"), "utf8"));
    assert.equal(result.ok, false);
    assert.equal(result.code, "MISSING_COMFYUI");
    assert.equal(result.phase, "preflight");
    assert.ok(result.remediation.includes("COMFYUI_DIR"));
    assert.doesNotMatch(JSON.stringify(result), new RegExp(root.replace(/[.*+?^${}()|[\]\\]/g, "\\$&")));
  } finally {
    if (previous === undefined) delete process.env.VIBECOMFY_E2E_ARTIFACT_DIR;
    else process.env.VIBECOMFY_E2E_ARTIFACT_DIR = previous;
    await fs.rm(root, { recursive: true, force: true });
  }
});

test("launcher checks sibling ComfyUI checkout in addition to vendor checkout", async () => {
  const source = await fs.readFile(new URL("./run.mjs", import.meta.url), "utf8");
  assert.match(source, /DEFAULT_SIBLING_COMFYUI_DIR/);
  assert.match(source, /DEFAULT_VENDOR_COMFYUI_DIR,\s*[\r\n\s]*DEFAULT_SIBLING_COMFYUI_DIR/);
});

test("launcher resolves a path-like Python executable before changing child cwd", () => {
  const invocationDir = path.join(os.tmpdir(), "vibecomfy-invocation");
  assert.equal(
    resolvePythonExecutable(".venv/bin/python", invocationDir),
    path.join(invocationDir, ".venv", "bin", "python"),
  );
  assert.equal(resolvePythonExecutable("python", invocationDir), "python");
  assert.equal(resolvePythonExecutable("/opt/python", invocationDir), "/opt/python");
});

test("launcher normalizes the provider fixture path before changing child cwd", () => {
  const invocationDir = path.join(os.tmpdir(), "vibecomfy-fixture-invocation");
  const childDir = path.join(invocationDir, "ComfyUI");
  const configured = "fixtures/editor_sessions";
  const normalized = resolveProviderFixtureDir(configured, invocationDir);
  assert.equal(normalized, path.join(invocationDir, configured));
  assert.notEqual(path.resolve(childDir, configured), normalized);
  assert.equal(resolveProviderFixtureDir("   ", invocationDir), path.join(
    path.resolve(new URL("../..", import.meta.url).pathname),
    "tests",
    "fixtures",
    "editor_sessions",
  ));
});

test("malformed fixtures fail before ComfyUI starts and retain launcher artifacts", async () => {
  const root = await fs.mkdtemp(path.join(os.tmpdir(), "vibecomfy-launcher-fixture-"));
  const comfyDir = path.join(root, "ComfyUI");
  const fixtureDir = path.join(root, "fixtures");
  const artifactDir = path.join(root, "artifacts");
  await fs.mkdir(comfyDir, { recursive: true });
  await fs.mkdir(fixtureDir, { recursive: true });
  await fs.writeFile(path.join(comfyDir, "main.py"), "raise SystemExit('must not start')\n", "utf8");
  await fs.writeFile(path.join(fixtureDir, "manifest.json"), "{ malformed", "utf8");
  const previousArtifact = process.env.VIBECOMFY_E2E_ARTIFACT_DIR;
  const previousFixture = process.env.VIBECOMFY_FIXTURE_DIR;
  process.env.VIBECOMFY_E2E_ARTIFACT_DIR = artifactDir;
  process.env.VIBECOMFY_FIXTURE_DIR = fixtureDir;
  try {
    const exitCode = await runEntrypoint(["--comfyui-dir", comfyDir, "--launcher-only", "--no-seed"]);
    assert.equal(exitCode, 1);
    const result = JSON.parse(await fs.readFile(path.join(artifactDir, "launcher-result.json"), "utf8"));
    assert.equal(result.code, "MALFORMED_FIXTURES");
    assert.equal(result.phase, "preflight");
    assert.equal(await fs.readFile(path.join(artifactDir, "comfyui.log"), "utf8"), "");
  } finally {
    if (previousArtifact === undefined) delete process.env.VIBECOMFY_E2E_ARTIFACT_DIR;
    else process.env.VIBECOMFY_E2E_ARTIFACT_DIR = previousArtifact;
    if (previousFixture === undefined) delete process.env.VIBECOMFY_FIXTURE_DIR;
    else process.env.VIBECOMFY_FIXTURE_DIR = previousFixture;
    await fs.rm(root, { recursive: true, force: true });
  }
});

test("Playwright config retains structured diagnostics, traces, and failure screenshots", async () => {
  const source = await fs.readFile(new URL("./playwright.config.mjs", import.meta.url), "utf8");
  assert.match(source, /\["json",\s*\{ outputFile: JSON_RESULT \}\]/);
  assert.match(source, /trace:\s*"retain-on-failure"/);
  assert.match(source, /screenshot:\s*"only-on-failure"/);
  assert.match(source, /outputDir:\s*OUTPUT_DIR/);
});
