// @ts-check
import { defineConfig, devices } from "@playwright/test";

const BASE_URL = process.env.BASE_URL || "http://127.0.0.1:8188";
const OUTPUT_DIR = process.env.VIBECOMFY_E2E_PLAYWRIGHT_OUTPUT_DIR || "test-results";
const JSON_RESULT = process.env.VIBECOMFY_E2E_PLAYWRIGHT_JSON || "test-results/results.json";
const HTML_REPORT = process.env.VIBECOMFY_E2E_PLAYWRIGHT_HTML || "playwright-report";

export default defineConfig({
  testDir: "./specs",

  // One worker ensures deterministic, un-contended browser sessions.
  workers: 1,
  fullyParallel: false,

  // Chromium-only — no Firefox or WebKit in this tier.
  projects: [
    {
      name: "chromium",
      use: {
        ...devices["Desktop Chrome"],
        baseURL: BASE_URL,
      },
    },
  ],

  // Retries disabled: this tier targets deterministic fixture-backed runs.
  retries: 0,

  // Generous timeout — ComfyUI cold-start can take a while.
  timeout: 120_000,
  expect: {
    timeout: 15_000,
  },

  // Reporters
  reporter: [
    ["list"],
    ["json", { outputFile: JSON_RESULT }],
    ["html", { outputFolder: HTML_REPORT, open: "never" }],
  ],

  outputDir: OUTPUT_DIR,

  use: {
    // Shared across all projects
    baseURL: BASE_URL,
    trace: "retain-on-failure",
    screenshot: "only-on-failure",
    video: "off",
  },

  // Global setup / teardown are handled by run.mjs, not here.
  globalSetup: undefined,
  globalTeardown: undefined,
});
