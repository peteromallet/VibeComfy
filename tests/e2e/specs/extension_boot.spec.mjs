import { test, expect } from "@playwright/test";

test("VibeComfy extension boots in Chromium and exposes its launcher", async ({ page }) => {
  const failures = [];

  page.on("console", (message) => {
    if (message.type() !== "error") return;
    const text = message.text();
    if (/vibecomfy|node:|canonical_hash/i.test(text)) {
      failures.push(`console: ${text}`);
    }
  });
  page.on("pageerror", (error) => {
    const text = error.stack || error.message || String(error);
    if (/vibecomfy|node:|canonical_hash/i.test(text)) {
      failures.push(`pageerror: ${text}`);
    }
  });
  page.on("requestfailed", (request) => {
    if (request.url().includes("/extensions/vibecomfy/")) {
      failures.push(`request: ${request.url()} (${request.failure()?.errorText || "failed"})`);
    }
  });
  page.on("response", (response) => {
    if (response.url().includes("/extensions/vibecomfy/") && response.status() >= 400) {
      failures.push(`response: ${response.status()} ${response.url()}`);
    }
  });

  await page.goto("/", { waitUntil: "domcontentloaded" });
  await page.waitForSelector("canvas#graph-canvas", { timeout: 60_000 });

  const launcher = page.locator("#vibecomfy-agent-launcher");
  await expect(launcher).toBeVisible({ timeout: 30_000 });
  await launcher.click();

  const panel = page.locator('#vibecomfy-agent-panel-root[data-open="1"]');
  await expect(panel).toBeVisible({ timeout: 30_000 });
  await expect(panel).toContainText("VibeComfy");
  expect(failures, failures.join("\n")).toEqual([]);
});
