#!/usr/bin/env node
import fs from "node:fs/promises";
import net from "node:net";
import os from "node:os";
import path from "node:path";
import process from "node:process";
import { fileURLToPath } from "node:url";
import { spawn } from "node:child_process";

const __filename = fileURLToPath(import.meta.url);
const E2E_DIR = path.dirname(__filename);
const REPO_ROOT = path.resolve(E2E_DIR, "..", "..");
const DEFAULT_VENDOR_COMFYUI_DIR = path.join(REPO_ROOT, "vendor", "ComfyUI");
const DEFAULT_SEED_SESSIONS_DIR = path.join(REPO_ROOT, "tests", "fixtures", "e2e_sessions");
const DEFAULT_READY_TIMEOUT_MS = 120_000;
const DEFAULT_STOP_TIMEOUT_MS = 10_000;
const DEFAULT_ARTIFACT_ROOT = path.join(REPO_ROOT, "test-results", "e2e-launcher");
const REQUIRED_SESSION_FILES = ["session_state.json"];
const REQUIRED_TURN_FILES = ["request.json", "response.json", "chat.json"];
const REQUIRED_PROVIDER_FILES = ["request.json", "fixture.json", "content.txt"];

const FAILURE_DETAILS = Object.freeze({
  ARGUMENT_ERROR: ["preflight", "Correct the launcher arguments and retry."],
  MISSING_COMFYUI: ["preflight", "Set COMFYUI_DIR or pass --comfyui-dir with a checkout containing main.py."],
  MALFORMED_FIXTURES: ["preflight", "Repair the named fixture file or choose a valid fixture directory."],
  CUSTOM_NODE_WIRING: ["preflight", "Use a dedicated ComfyUI checkout or remove the conflicting custom_nodes/vibecomfy entry."],
  MISSING_CHROMIUM: ["preflight", "Run cd tests/e2e && npx playwright install chromium, then retry."],
  COMFYUI_START_FAILED: ["readiness", "Verify the selected Python can run ComfyUI and inspect comfyui.log."],
  COMFYUI_EARLY_EXIT: ["readiness", "Inspect comfyui.log for the startup exception and verify ComfyUI dependencies."],
  READINESS_TIMEOUT: ["readiness", "Inspect comfyui.log and verify /vibecomfy/ping plus agent status can become ready."],
  READINESS_NOT_READY: ["readiness", "Inspect the agent status contract and fixture-provider configuration."],
  PLAYWRIGHT_START_FAILED: ["playwright", "Verify the tests/e2e npm dependencies and retry."],
  PLAYWRIGHT_FAILED: ["playwright", "Inspect results.json, the retained trace, screenshot, and HTML report."],
  TEARDOWN_FAILED: ["teardown", "Stop the recorded ComfyUI process group and remove only the recorded seeded/runtime paths."],
  INTERNAL_ERROR: ["launcher", "Inspect launcher-result.json and comfyui.log, then report the unclassified launcher defect."],
});

export class LauncherFailure extends Error {
  constructor(code, message, options = {}) {
    super(message, options);
    this.name = "LauncherFailure";
    this.code = code;
    const [phase, remediation] = FAILURE_DETAILS[code] || FAILURE_DETAILS.INTERNAL_ERROR;
    this.phase = phase;
    this.remediation = remediation;
    this.details = options.details || null;
  }
}

function asLauncherFailure(error, code, message = null) {
  if (error instanceof LauncherFailure) return error;
  const detail = error instanceof Error ? error.message : String(error);
  return new LauncherFailure(code, message || detail, { cause: error });
}

export function sanitizeText(value, replacements = []) {
  let text = String(value ?? "");
  const secretValues = Object.entries(process.env)
    .filter(([name, secret]) => secret && secret.length >= 8 && /(?:TOKEN|KEY|SECRET|PASSWORD|CREDENTIAL|AUTH)/i.test(name))
    .map(([, secret]) => secret);
  for (const secret of secretValues) text = text.split(secret).join("<redacted>");
  text = text
    .replace(/([?&](?:token|key|secret|password|auth)=)[^&\s]+/gi, "$1<redacted>")
    .replace(/(\b(?:token|api[_-]?key|secret|password|authorization)\b\s*[:=]\s*)[^\s,;]+/gi, "$1<redacted>");
  const pathReplacements = [
    [REPO_ROOT, "<repo>"],
    [os.homedir(), "<home>"],
    ...replacements,
  ].filter(([source]) => source);
  for (const [source, label] of pathReplacements.sort((a, b) => b[0].length - a[0].length)) {
    text = text.split(String(source)).join(String(label));
  }
  return text;
}

async function writeJson(filePath, payload) {
  await fs.mkdir(path.dirname(filePath), { recursive: true });
  await fs.writeFile(filePath, `${JSON.stringify(payload, null, 2)}\n`, "utf8");
}

function publicFailure(error, replacements = []) {
  const failure = asLauncherFailure(error, "INTERNAL_ERROR");
  return {
    ok: false,
    code: failure.code,
    phase: failure.phase,
    message: sanitizeText(failure.message, replacements),
    remediation: failure.remediation,
    ...(failure.details ? { details: failure.details } : {}),
  };
}

function usage() {
  return `Usage: node tests/e2e/run.mjs [options] [-- <playwright args...>]

Options:
  --port <port>                Use a fixed port instead of allocating a free one
  --python <path>              Python executable for ComfyUI (default: $PYBIN or python)
  --comfyui-dir <path>         ComfyUI checkout to boot
  --seed-sessions-dir <path>   Session fixture tree to copy into ComfyUI out/editor_sessions
  --no-seed                    Skip session seeding even if the fixture tree exists
  --ready-timeout-ms <ms>      Timeout for ping/status readiness (default: ${DEFAULT_READY_TIMEOUT_MS})
  --launcher-only              Boot, wait for readiness, then tear down without Playwright
  --help                       Show this message

Environment:
  COMFYUI_DIR                  Override ComfyUI checkout path
  PYBIN                        Override Python executable
  VIBECOMFY_FIXTURE_DIR        Optional fixture-provider fallback path
  VIBECOMFY_E2E_SESSION_FIXTURES
                               Optional session-seeding source tree
`;
}

function log(message) {
  process.stdout.write(`[e2e-run] ${message}\n`);
}

function parseArgs(argv) {
  const options = {
    port: null,
    python: process.env.PYBIN || "python",
    comfyuiDir: process.env.COMFYUI_DIR || null,
    seedSessionsDir: process.env.VIBECOMFY_E2E_SESSION_FIXTURES || DEFAULT_SEED_SESSIONS_DIR,
    seedSessions: true,
    readyTimeoutMs: DEFAULT_READY_TIMEOUT_MS,
    launcherOnly: false,
    playwrightArgs: [],
  };
  const args = [...argv];
  while (args.length > 0) {
    const arg = args.shift();
    if (arg === "--") {
      options.playwrightArgs.push(...args);
      break;
    }
    if (arg === "--help" || arg === "-h") {
      options.help = true;
      continue;
    }
    if (arg === "--no-seed") {
      options.seedSessions = false;
      continue;
    }
    if (arg === "--launcher-only") {
      options.launcherOnly = true;
      continue;
    }
    if (arg === "--port") {
      options.port = Number(args.shift());
      continue;
    }
    if (arg === "--python") {
      options.python = args.shift();
      continue;
    }
    if (arg === "--comfyui-dir") {
      options.comfyuiDir = args.shift();
      continue;
    }
    if (arg === "--seed-sessions-dir") {
      options.seedSessionsDir = args.shift();
      continue;
    }
    if (arg === "--ready-timeout-ms") {
      options.readyTimeoutMs = Number(args.shift());
      continue;
    }
    throw new Error(`Unknown argument: ${arg}`);
  }
  if (options.port !== null && (!Number.isInteger(options.port) || options.port <= 0 || options.port > 65535)) {
    throw new Error(`Invalid --port value: ${options.port}`);
  }
  if (!options.python) {
    throw new Error("Python executable is required.");
  }
  if (!Number.isInteger(options.readyTimeoutMs) || options.readyTimeoutMs <= 0) {
    throw new Error(`Invalid --ready-timeout-ms value: ${options.readyTimeoutMs}`);
  }
  return options;
}

async function exists(target) {
  try {
    await fs.access(target);
    return true;
  } catch {
    return false;
  }
}

async function resolveComfyuiDir(explicitDir) {
  const candidates = [
    explicitDir,
    DEFAULT_VENDOR_COMFYUI_DIR,
  ].filter(Boolean);
  for (const candidate of candidates) {
    const mainPy = path.join(candidate, "main.py");
    if (await exists(mainPy)) {
      return path.resolve(candidate);
    }
  }
  throw new LauncherFailure("MISSING_COMFYUI",
    `Could not find ComfyUI. Checked: ${candidates.join(", ")}. Set COMFYUI_DIR or pass --comfyui-dir.`
  );
}

async function allocatePort() {
  return new Promise((resolve, reject) => {
    const server = net.createServer();
    server.unref();
    server.on("error", reject);
    server.listen(0, "127.0.0.1", () => {
      const address = server.address();
      const port = address && typeof address === "object" ? address.port : null;
      server.close((error) => {
        if (error) {
          reject(error);
          return;
        }
        if (!port) {
          reject(new Error("Failed to allocate a port."));
          return;
        }
        resolve(port);
      });
    });
  });
}

async function ensureCustomNodeLink(comfyuiDir) {
  const customNodesDir = path.join(comfyuiDir, "custom_nodes");
  const desiredTarget = path.join(REPO_ROOT, "vibecomfy", "comfy_nodes");
  const linkPath = path.join(customNodesDir, "vibecomfy");
  await fs.mkdir(customNodesDir, { recursive: true });
  let stat;
  try {
    stat = await fs.lstat(linkPath);
  } catch (error) {
    if (error && error.code !== "ENOENT") {
      throw error;
    }
  }
  if (!stat) {
    await fs.symlink(desiredTarget, linkPath);
    return;
  }
  if (stat.isSymbolicLink()) {
    const currentTarget = await fs.readlink(linkPath);
    const resolvedTarget = path.resolve(path.dirname(linkPath), currentTarget);
    if (resolvedTarget !== desiredTarget) {
      await fs.unlink(linkPath);
      await fs.symlink(desiredTarget, linkPath);
    }
    return;
  }
  throw new LauncherFailure("CUSTOM_NODE_WIRING",
    `Cannot wire custom node at ${linkPath}: path exists and is not a symlink. Move it aside or set COMFYUI_DIR to a dedicated test checkout.`
  );
}

async function readJsonFile(filePath) {
  const raw = await fs.readFile(filePath, "utf8");
  try {
    return JSON.parse(raw);
  } catch (error) {
    throw new LauncherFailure("MALFORMED_FIXTURES", `Invalid JSON in ${filePath}: ${error.message}`);
  }
}

async function validateSessionFixture(sessionDir) {
  const sessionName = path.basename(sessionDir);
  for (const fileName of REQUIRED_SESSION_FILES) {
    const fullPath = path.join(sessionDir, fileName);
    if (!(await exists(fullPath))) {
      throw new LauncherFailure("MALFORMED_FIXTURES", `Session fixture ${sessionName} is missing ${fileName}.`);
    }
    await readJsonFile(fullPath);
  }

  const turnsDir = path.join(sessionDir, "turns");
  if (!(await exists(turnsDir))) {
    throw new LauncherFailure("MALFORMED_FIXTURES", `Session fixture ${sessionName} is missing turns/.`);
  }
  const turnEntries = (await fs.readdir(turnsDir, { withFileTypes: true }))
    .filter((entry) => entry.isDirectory())
    .map((entry) => entry.name)
    .sort();
  if (turnEntries.length === 0) {
    throw new LauncherFailure("MALFORMED_FIXTURES", `Session fixture ${sessionName} has no turn directories.`);
  }
  for (const turnName of turnEntries) {
    const turnDir = path.join(turnsDir, turnName);
    for (const fileName of REQUIRED_TURN_FILES) {
      const fullPath = path.join(turnDir, fileName);
      if (!(await exists(fullPath))) {
        throw new LauncherFailure("MALFORMED_FIXTURES", `Session fixture ${sessionName}/${turnName} is missing ${fileName}.`);
      }
      await readJsonFile(fullPath);
    }
  }
}

async function validateProviderFixtures(fixtureDir) {
  const manifestPath = path.join(fixtureDir, "manifest.json");
  if (!(await exists(manifestPath))) {
    throw new LauncherFailure("MALFORMED_FIXTURES",
      `Fixture-provider fixture directory ${fixtureDir} is missing manifest.json.`
    );
  }
  const manifest = await readJsonFile(manifestPath);
  const keys = Object.keys(manifest);
  if (keys.length === 0) {
    throw new LauncherFailure("MALFORMED_FIXTURES",
      `Fixture-provider manifest at ${manifestPath} contains no entries.`
    );
  }
  const missing = [];
  const corrupt = [];
  for (const key of keys) {
    const keyDir = path.join(fixtureDir, key);
    if (!(await exists(keyDir))) {
      missing.push(key);
      continue;
    }
    for (const fileName of REQUIRED_PROVIDER_FILES) {
      const filePath = path.join(keyDir, fileName);
      if (!(await exists(filePath))) {
        missing.push(`${key}/${fileName}`);
        continue;
      }
      // Only JSON-parse files ending in .json; content.txt is plain text.
      if (fileName.endsWith(".json")) {
        try {
          await readJsonFile(filePath);
        } catch {
          corrupt.push(`${key}/${fileName}`);
        }
      }
    }
  }
  if (missing.length > 0 || corrupt.length > 0) {
    const parts = [];
    if (missing.length > 0) {
      parts.push(`missing: ${missing.join(", ")}`);
    }
    if (corrupt.length > 0) {
      parts.push(`corrupt JSON: ${corrupt.join(", ")}`);
    }
    throw new LauncherFailure("MALFORMED_FIXTURES",
      `Fixture-provider fixture directory ${fixtureDir} is incomplete: ${parts.join("; ")}`
    );
  }
  log(
    `validated ${keys.length} provider fixture(s) under ${fixtureDir}`
  );
}

async function copyRecursive(source, destination) {
  await fs.cp(source, destination, { recursive: true, dereference: false, errorOnExist: true, force: false });
}

async function seedSessions(sourceRoot, comfyuiDir) {
  if (!sourceRoot) {
    return [];
  }
  const absoluteSource = path.resolve(sourceRoot);
  if (!(await exists(absoluteSource))) {
    return [];
  }
  const entries = (await fs.readdir(absoluteSource, { withFileTypes: true }))
    .filter((entry) => entry.isDirectory())
    .map((entry) => entry.name)
    .sort();
  if (entries.length === 0) {
    return [];
  }

  const targetRoot = path.join(comfyuiDir, "out", "editor_sessions");
  await fs.mkdir(targetRoot, { recursive: true });

  const copiedTargets = [];
  for (const sessionName of entries) {
    const sourceDir = path.join(absoluteSource, sessionName);
    await validateSessionFixture(sourceDir);
    const targetDir = path.join(targetRoot, sessionName);
    if (await exists(targetDir)) {
      throw new LauncherFailure("MALFORMED_FIXTURES",
        `Refusing to overwrite existing seeded session ${targetDir}. Remove it or choose unique fixture names.`
      );
    }
    await copyRecursive(sourceDir, targetDir);
    copiedTargets.push(targetDir);
  }
  return copiedTargets;
}

function childExited(child) {
  return child.exitCode !== null || child.signalCode !== null;
}

function delay(ms) {
  return new Promise((resolve) => setTimeout(resolve, ms));
}

async function waitForHttpJson(url, timeoutMs, label, child) {
  const deadline = Date.now() + timeoutMs;
  let lastError = null;
  while (Date.now() < deadline) {
    if (child?.launchError) {
      throw new LauncherFailure("COMFYUI_START_FAILED", `Could not start ComfyUI: ${child.launchError.message}`);
    }
    if (child && childExited(child)) {
      throw new LauncherFailure("COMFYUI_EARLY_EXIT", `ComfyUI exited before ${label} became ready.`);
    }
    try {
      const remainingMs = Math.max(1, deadline - Date.now());
      const response = await fetch(url, {
        headers: { accept: "application/json" },
        signal: AbortSignal.timeout(Math.min(5_000, remainingMs)),
      });
      if (response.ok) {
        const payload = await response.json();
        return payload;
      }
      lastError = new Error(`${label} returned HTTP ${response.status}`);
    } catch (error) {
      lastError = error;
    }
    await delay(500);
  }
  throw new LauncherFailure("READINESS_TIMEOUT", `Timed out waiting for ${label}: ${lastError ? lastError.message : "no response"}`);
}

async function waitForReadiness(baseUrl, timeoutMs, child) {
  await waitForHttpJson(`${baseUrl}/vibecomfy/ping`, timeoutMs, "/vibecomfy/ping", child);
  const status = await waitForHttpJson(
    `${baseUrl}/vibecomfy/agent/status?route=auto`,
    timeoutMs,
    "/vibecomfy/agent/status",
    child
  );
  if (!status || status.ready !== true) {
    throw new LauncherFailure("READINESS_NOT_READY",
      `/vibecomfy/agent/status returned not-ready payload: ${JSON.stringify(status)}`
    );
  }
  return status;
}

async function makeRuntimeRoot() {
  const runtimeRoot = await fs.mkdtemp(path.join(os.tmpdir(), "vibecomfy-e2e-"));
  for (const relative of ["output", "temp", "input", "user"]) {
    await fs.mkdir(path.join(runtimeRoot, relative), { recursive: true });
  }
  return runtimeRoot;
}

function spawnComfyUI({ comfyuiDir, python, port, runtimeRoot, comfyLog, replacements }) {
  const childEnv = { ...process.env };
  childEnv.PORT = String(port);
  childEnv.REPO_ROOT = REPO_ROOT;
  childEnv.PYTHONPATH = childEnv.PYTHONPATH ? `${REPO_ROOT}${path.delimiter}${childEnv.PYTHONPATH}` : REPO_ROOT;
  childEnv.VIBECOMFY_ARNOLD_RUNTIME_MODULE = "vibecomfy.comfy_nodes.agent.fixture_provider";
  childEnv.VIBECOMFY_FIXTURE_DIR = childEnv.VIBECOMFY_FIXTURE_DIR || path.join(REPO_ROOT, "tests", "fixtures", "editor_sessions");
  const outputDir = path.join(runtimeRoot, "output");
  const tempDir = path.join(runtimeRoot, "temp");
  const inputDir = path.join(runtimeRoot, "input");
  const userDir = path.join(runtimeRoot, "user");
  const databaseUrl = `sqlite:///${path.join(userDir, "comfyui.db")}`;

  const child = spawn(
    python,
    [
      "main.py",
      "--cpu",
      "--port",
      String(port),
      "--enable-cors-header",
      "*",
      "--output-directory",
      outputDir,
      "--temp-directory",
      tempDir,
      "--input-directory",
      inputDir,
      "--user-directory",
      userDir,
      "--database-url",
      databaseUrl,
    ],
    {
      cwd: comfyuiDir,
      env: childEnv,
      detached: process.platform !== "win32",
      stdio: ["ignore", "pipe", "pipe"],
    }
  );

  child.launchError = null;
  child.on("error", (error) => {
    child.launchError = error;
  });

  for (const [streamName, stream] of [
    ["stdout", child.stdout],
    ["stderr", child.stderr],
  ]) {
    stream?.setEncoding("utf8");
    stream?.on("data", (chunk) => {
      const text = sanitizeText(String(chunk), replacements);
      comfyLog.push(`[${streamName}] ${text}`);
      for (const line of text.split(/\r?\n/)) {
        if (line) {
          process.stdout.write(`[comfyui:${streamName}] ${line}\n`);
        }
      }
    });
  }

  return child;
}

async function stopProcess(child) {
  if (!child || childExited(child)) {
    return;
  }
  const pid = child.pid;
  const sendSignal = (signal) => {
    try {
      if (process.platform !== "win32" && child.pid) {
        process.kill(-child.pid, signal);
      } else {
        child.kill(signal);
      }
      return true;
    } catch (error) {
      if (error && error.code === "ESRCH") {
        return false;
      }
      throw error;
    }
  };

  sendSignal("SIGTERM");
  const termDeadline = Date.now() + DEFAULT_STOP_TIMEOUT_MS;
  while (!childExited(child) && Date.now() < termDeadline) {
    await delay(200);
  }
  if (!childExited(child)) {
    log(`ComfyUI pid ${pid} did not stop after SIGTERM; escalating to SIGKILL.`);
    sendSignal("SIGKILL");
  }
  if (!childExited(child)) {
    await new Promise((resolve) => child.once("exit", resolve));
  }
}

async function removeSeededSessions(pathsToRemove) {
  for (const targetPath of pathsToRemove.slice().reverse()) {
    await fs.rm(targetPath, { recursive: true, force: true });
  }
}

function normalizePlaywrightArgs(playwrightArgs) {
  return playwrightArgs.map((arg) => {
    if (path.isAbsolute(arg)) return arg;
    const repoCandidate = path.join(REPO_ROOT, arg);
    return fs.access(repoCandidate).then(() => repoCandidate, () => arg);
  });
}

async function ensureChromiumInstalled() {
  let chromium;
  try {
    ({ chromium } = await import("@playwright/test"));
  } catch (error) {
    throw new LauncherFailure("MISSING_CHROMIUM", `Playwright is unavailable: ${error.message}`);
  }
  const executable = chromium.executablePath();
  if (!executable || !(await exists(executable))) {
    throw new LauncherFailure("MISSING_CHROMIUM", "The Playwright Chromium executable is not installed.");
  }
}

async function runPlaywright(playwrightArgs, env) {
  const normalized = await Promise.all(normalizePlaywrightArgs(playwrightArgs));
  const args = ["playwright", "test", ...normalized];
  return new Promise((resolve, reject) => {
    const child = spawn("npx", args, {
      cwd: E2E_DIR,
      env,
      stdio: "inherit",
    });
    child.on("error", (error) => reject(new LauncherFailure("PLAYWRIGHT_START_FAILED", error.message)));
    child.on("exit", (code, signal) => {
      if (signal) {
        resolve(128 + (signal === "SIGTERM" ? 15 : 0));
        return;
      }
      resolve(code ?? 1);
    });
  });
}

export async function main(argv = process.argv.slice(2)) {
  let options;
  try {
    options = parseArgs(argv);
  } catch (error) {
    throw asLauncherFailure(error, "ARGUMENT_ERROR");
  }
  if (options.help) {
    process.stdout.write(usage());
    return { ok: true, code: "HELP", phase: "preflight" };
  }

  const artifactRoot = path.resolve(process.env.VIBECOMFY_E2E_ARTIFACT_DIR || DEFAULT_ARTIFACT_ROOT);
  await fs.mkdir(artifactRoot, { recursive: true });
  const comfyLog = [];
  const seededTargets = [];
  let comfyChild = null;
  let runtimeRoot = null;
  let cleaningUp = false;
  let comfyuiDir = null;
  let primaryFailure = null;
  const replacements = [[artifactRoot, "<artifacts>"]];
  if (options.comfyuiDir) {
    replacements.push([path.resolve(options.comfyuiDir), "<comfyui>"]);
  }
  if (options.seedSessionsDir) {
    replacements.push([path.resolve(options.seedSessionsDir), "<session-fixtures>"]);
  }

  const cleanup = async () => {
    if (cleaningUp) {
      return;
    }
    cleaningUp = true;
    const errors = [];
    for (const action of [
      () => stopProcess(comfyChild),
      () => removeSeededSessions(seededTargets),
      () => runtimeRoot ? fs.rm(runtimeRoot, { recursive: true, force: true }) : undefined,
      () => fs.writeFile(path.join(artifactRoot, "comfyui.log"), sanitizeText(comfyLog.join(""), replacements), "utf8"),
    ]) {
      try {
        await action();
      } catch (error) {
        errors.push(error instanceof Error ? error.message : String(error));
      }
    }
    if (errors.length > 0) {
      throw new LauncherFailure("TEARDOWN_FAILED", errors.join("; "), {
        details: primaryFailure ? { primary_failure: publicFailure(primaryFailure, replacements) } : null,
      });
    }
  };

  const forwardSignal = (signal, exitCode) => {
    process.on(signal, async () => {
      log(`Received ${signal}; tearing down ComfyUI.`);
      try {
        await cleanup().catch((error) => {
          process.stderr.write(`[e2e-run] ${JSON.stringify(publicFailure(error, replacements))}\n`);
        });
      } finally {
        process.exit(exitCode);
      }
    });
  };

  forwardSignal("SIGINT", 130);
  forwardSignal("SIGTERM", 143);

  try {
    comfyuiDir = await resolveComfyuiDir(options.comfyuiDir);
    replacements.push([comfyuiDir, "<comfyui>"]);
    const port = options.port ?? (await allocatePort());
    const baseUrl = `http://127.0.0.1:${port}`;
    log(`repo: ${REPO_ROOT}`);
    log(`comfyui: ${comfyuiDir}`);
    log(`python: ${options.python}`);
    log(`port: ${port}`);

    await ensureCustomNodeLink(comfyuiDir);

    // Fail fast if the fixture-provider fixture tree is missing or corrupt.
    const providerFixtureDir =
      process.env.VIBECOMFY_FIXTURE_DIR ||
      path.join(REPO_ROOT, "tests", "fixtures", "editor_sessions");
    replacements.push([path.resolve(providerFixtureDir), "<provider-fixtures>"]);
    await validateProviderFixtures(providerFixtureDir);

    if (!options.launcherOnly) {
      await ensureChromiumInstalled();
    }

    runtimeRoot = await makeRuntimeRoot();
    replacements.push([runtimeRoot, "<runtime>"]);
    if (options.seedSessions) {
      const copied = await seedSessions(options.seedSessionsDir, comfyuiDir);
      seededTargets.push(...copied);
      if (copied.length > 0) {
        log(`seeded ${copied.length} session fixture(s) into ${path.join(comfyuiDir, "out", "editor_sessions")}`);
      }
    }

    comfyChild = spawnComfyUI({ comfyuiDir, python: options.python, port, runtimeRoot, comfyLog, replacements });
    await waitForReadiness(baseUrl, options.readyTimeoutMs, comfyChild);
    log(`ComfyUI is ready at ${baseUrl}`);

    if (options.launcherOnly) {
      log("Launcher-only mode enabled; skipping Playwright.");
      return { ok: true, code: "LAUNCHER_READY", phase: "readiness" };
    }

    const env = {
      ...process.env,
      BASE_URL: baseUrl,
      REPO_ROOT,
      PORT: String(port),
      VIBECOMFY_E2E_PLAYWRIGHT_OUTPUT_DIR: path.join(artifactRoot, "playwright"),
      VIBECOMFY_E2E_PLAYWRIGHT_JSON: path.join(artifactRoot, "results.json"),
      VIBECOMFY_E2E_PLAYWRIGHT_HTML: path.join(artifactRoot, "html-report"),
    };
    const code = await runPlaywright(options.playwrightArgs, env);
    if (code !== 0) {
      throw new LauncherFailure("PLAYWRIGHT_FAILED", `Playwright exited with code ${code}.`);
    }
    return { ok: true, code: "E2E_PASSED", phase: "playwright" };
  } catch (error) {
    primaryFailure = asLauncherFailure(error, "INTERNAL_ERROR");
    primaryFailure.message = sanitizeText(primaryFailure.message, replacements);
    throw primaryFailure;
  } finally {
    try {
      await cleanup();
    } catch (error) {
      const teardownFailure = asLauncherFailure(error, "TEARDOWN_FAILED");
      teardownFailure.message = sanitizeText(teardownFailure.message, replacements);
      primaryFailure = teardownFailure;
      throw teardownFailure;
    }
  }
}

export async function runEntrypoint(argv = process.argv.slice(2)) {
  const artifactRoot = path.resolve(process.env.VIBECOMFY_E2E_ARTIFACT_DIR || DEFAULT_ARTIFACT_ROOT);
  let result;
  try {
    result = await main(argv);
  } catch (error) {
    result = publicFailure(error);
  }
  result.artifacts = {
    launcher_result: "launcher-result.json",
    comfyui_log: "comfyui.log",
    playwright_result: "results.json",
    playwright_output: "playwright/",
    html_report: "html-report/",
  };
  await writeJson(path.join(artifactRoot, "launcher-result.json"), result);
  const stream = result.ok ? process.stdout : process.stderr;
  stream.write(`[e2e-run:result] ${JSON.stringify(result)}\n`);
  return result.ok ? 0 : 1;
}

if (process.argv[1] && path.resolve(process.argv[1]) === __filename) {
  runEntrypoint().then((exitCode) => {
    process.exitCode = exitCode;
  }).catch((error) => {
    const result = publicFailure(error);
    process.stderr.write(`[e2e-run:result] ${JSON.stringify(result)}\n`);
    process.exitCode = 1;
  });
}
