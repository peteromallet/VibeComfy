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
const DEFAULT_EXTERNAL_COMFYUI_DIR = "/Users/peteromalley/Documents/reigh-workspace/ComfyUI";
const DEFAULT_VENDOR_COMFYUI_DIR = path.join(REPO_ROOT, "vendor", "ComfyUI");
const DEFAULT_SEED_SESSIONS_DIR = path.join(REPO_ROOT, "tests", "fixtures", "e2e_sessions");
const DEFAULT_READY_TIMEOUT_MS = 120_000;
const DEFAULT_STOP_TIMEOUT_MS = 10_000;
const REQUIRED_SESSION_FILES = ["session_state.json"];
const REQUIRED_TURN_FILES = ["request.json", "response.json", "chat.json"];
const REQUIRED_PROVIDER_FILES = ["request.json", "fixture.json", "content.txt"];

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
    DEFAULT_EXTERNAL_COMFYUI_DIR,
    DEFAULT_VENDOR_COMFYUI_DIR,
  ].filter(Boolean);
  for (const candidate of candidates) {
    const mainPy = path.join(candidate, "main.py");
    if (await exists(mainPy)) {
      return path.resolve(candidate);
    }
  }
  throw new Error(
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
  throw new Error(
    `Cannot wire custom node at ${linkPath}: path exists and is not a symlink. Move it aside or set COMFYUI_DIR to a dedicated test checkout.`
  );
}

async function readJsonFile(filePath) {
  const raw = await fs.readFile(filePath, "utf8");
  try {
    return JSON.parse(raw);
  } catch (error) {
    throw new Error(`Invalid JSON in ${filePath}: ${error.message}`);
  }
}

async function validateSessionFixture(sessionDir) {
  const sessionName = path.basename(sessionDir);
  for (const fileName of REQUIRED_SESSION_FILES) {
    const fullPath = path.join(sessionDir, fileName);
    if (!(await exists(fullPath))) {
      throw new Error(`Session fixture ${sessionName} is missing ${fileName}.`);
    }
    await readJsonFile(fullPath);
  }

  const turnsDir = path.join(sessionDir, "turns");
  if (!(await exists(turnsDir))) {
    throw new Error(`Session fixture ${sessionName} is missing turns/.`);
  }
  const turnEntries = (await fs.readdir(turnsDir, { withFileTypes: true }))
    .filter((entry) => entry.isDirectory())
    .map((entry) => entry.name)
    .sort();
  if (turnEntries.length === 0) {
    throw new Error(`Session fixture ${sessionName} has no turn directories.`);
  }
  for (const turnName of turnEntries) {
    const turnDir = path.join(turnsDir, turnName);
    for (const fileName of REQUIRED_TURN_FILES) {
      const fullPath = path.join(turnDir, fileName);
      if (!(await exists(fullPath))) {
        throw new Error(`Session fixture ${sessionName}/${turnName} is missing ${fileName}.`);
      }
      await readJsonFile(fullPath);
    }
  }
}

async function validateProviderFixtures(fixtureDir) {
  const manifestPath = path.join(fixtureDir, "manifest.json");
  if (!(await exists(manifestPath))) {
    throw new Error(
      `Fixture-provider fixture directory ${fixtureDir} is missing manifest.json.`
    );
  }
  const manifest = await readJsonFile(manifestPath);
  const keys = Object.keys(manifest);
  if (keys.length === 0) {
    throw new Error(
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
    throw new Error(
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
      throw new Error(
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
    if (child && childExited(child)) {
      throw new Error(`ComfyUI exited before ${label} became ready.`);
    }
    try {
      const response = await fetch(url, { headers: { accept: "application/json" } });
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
  throw new Error(`Timed out waiting for ${label}: ${lastError ? lastError.message : "no response"}`);
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
    throw new Error(
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

function spawnComfyUI({ comfyuiDir, python, port, runtimeRoot }) {
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

  for (const [streamName, stream] of [
    ["stdout", child.stdout],
    ["stderr", child.stderr],
  ]) {
    stream?.setEncoding("utf8");
    stream?.on("data", (chunk) => {
      const text = String(chunk);
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
  await new Promise((resolve) => child.once("exit", resolve));
}

async function removeSeededSessions(pathsToRemove) {
  for (const targetPath of pathsToRemove.slice().reverse()) {
    await fs.rm(targetPath, { recursive: true, force: true });
  }
}

async function runPlaywright(playwrightArgs, env) {
  const args = ["playwright", "test", ...playwrightArgs];
  return new Promise((resolve) => {
    const child = spawn("npx", args, {
      cwd: E2E_DIR,
      env,
      stdio: "inherit",
    });
    child.on("exit", (code, signal) => {
      if (signal) {
        resolve(128);
        return;
      }
      resolve(code ?? 1);
    });
  });
}

async function main() {
  const options = parseArgs(process.argv.slice(2));
  if (options.help) {
    process.stdout.write(usage());
    return;
  }

  const comfyuiDir = await resolveComfyuiDir(options.comfyuiDir);
  const port = options.port ?? (await allocatePort());
  const baseUrl = `http://127.0.0.1:${port}`;
  const seededTargets = [];
  let comfyChild = null;
  let runtimeRoot = null;
  let cleaningUp = false;

  const cleanup = async () => {
    if (cleaningUp) {
      return;
    }
    cleaningUp = true;
    try {
      await stopProcess(comfyChild);
    } finally {
      await removeSeededSessions(seededTargets);
      if (runtimeRoot) {
        await fs.rm(runtimeRoot, { recursive: true, force: true });
      }
    }
  };

  const forwardSignal = (signal, exitCode) => {
    process.on(signal, async () => {
      log(`Received ${signal}; tearing down ComfyUI.`);
      try {
        await cleanup();
      } finally {
        process.exit(exitCode);
      }
    });
  };

  forwardSignal("SIGINT", 130);
  forwardSignal("SIGTERM", 143);

  try {
    log(`repo: ${REPO_ROOT}`);
    log(`comfyui: ${comfyuiDir}`);
    log(`python: ${options.python}`);
    log(`port: ${port}`);

    await ensureCustomNodeLink(comfyuiDir);

    // Fail fast if the fixture-provider fixture tree is missing or corrupt.
    const providerFixtureDir =
      process.env.VIBECOMFY_FIXTURE_DIR ||
      path.join(REPO_ROOT, "tests", "fixtures", "editor_sessions");
    await validateProviderFixtures(providerFixtureDir);

    runtimeRoot = await makeRuntimeRoot();
    if (options.seedSessions) {
      const copied = await seedSessions(options.seedSessionsDir, comfyuiDir);
      seededTargets.push(...copied);
      if (copied.length > 0) {
        log(`seeded ${copied.length} session fixture(s) into ${path.join(comfyuiDir, "out", "editor_sessions")}`);
      }
    }

    comfyChild = spawnComfyUI({ comfyuiDir, python: options.python, port, runtimeRoot });
    await waitForReadiness(baseUrl, options.readyTimeoutMs, comfyChild);
    log(`ComfyUI is ready at ${baseUrl}`);

    if (options.launcherOnly) {
      log("Launcher-only mode enabled; skipping Playwright.");
      return;
    }

    const env = {
      ...process.env,
      BASE_URL: baseUrl,
      REPO_ROOT,
      PORT: String(port),
    };
    const code = await runPlaywright(options.playwrightArgs, env);
    if (code !== 0) {
      throw new Error(`Playwright exited with code ${code}.`);
    }
  } finally {
    await cleanup();
  }
}

main().catch((error) => {
  const message = error instanceof Error ? error.stack || error.message : String(error);
  process.stderr.write(`[e2e-run] ERROR ${message}\n`);
  process.exit(1);
});
