// @ts-check
import { defineConfig, devices } from "@playwright/test";

const BASE_URL = process.env.BASE_URL || "http://127.0.0.1:8188";

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
  reporter: [["list"], ["html", { outputFolder: "playwright-report", open: "never" }]],

  use: {
    // Shared across all projects
    baseURL: BASE_URL,
    trace: "retain-on-failure",
    screenshot: "off",
    video: "off",
  },

  // Global setup / teardown are handled by run.mjs, not here.
  globalSetup: undefined,
  globalTeardown: undefined,
});
