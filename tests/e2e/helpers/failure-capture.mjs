// ── Playwright helpers: console / page / request failure capture ──────────
// Reusable across all VibeComfy real-browser specs. No screenshot or
// pixel-diff assertions.

/**
 * @typedef {Object} FailureCapture
 * @property {Array<{type: string, text: string, location?: string}>} consoleErrors
 * @property {Array<{url: string, status: number, statusText: string}>} failedRequests
 * @property {Array<Error>} pageErrors
 * @property {Array<{message: string, source?: string, lineno?: number, colno?: number}>} unhandledErrors
 * @property {() => string} summary - human-readable failure summary
 * @property {() => void} reset - clear captured failures
 */

/**
 * Install failure capture listeners on a Playwright Page.
 *
 * Captures:
 *  - console.error / console.warn messages
 *  - Failed network requests (4xx / 5xx)
 *  - Uncaught page exceptions (pageerror)
 *
 * @param {import("@playwright/test").Page} page
 * @returns {FailureCapture}
 */
export function installFailureCapture(page) {
  const consoleErrors = [];
  const failedRequests = [];
  const pageErrors = [];
  const unhandledErrors = [];

  /** @type {import("@playwright/test").ConsoleMessage} */
  page.on("console", (msg) => {
    if (msg.type() === "error" || msg.type() === "warning") {
      consoleErrors.push({
        type: msg.type(),
        text: msg.text(),
        location: msg.location()
          ? `${msg.location().url}:${msg.location().lineNumber}:${msg.location().columnNumber}`
          : undefined,
      });
    }
  });

  page.on("requestfailed", (request) => {
    // Only capture HTTP-level failures; ignore aborts / network drops from
    // teardown races (errno -3, etc.).
    const failure = request.failure();
    if (failure && failure.errorText && !failure.errorText.includes("ERR_ABORTED")) {
      failedRequests.push({
        url: request.url(),
        status: 0,
        statusText: failure.errorText,
      });
    }
  });

  page.on("response", (response) => {
    if (response.status() >= 400) {
      failedRequests.push({
        url: response.url(),
        status: response.status(),
        statusText: response.statusText(),
      });
    }
  });

  page.on("pageerror", (error) => {
    pageErrors.push(error);
  });

  // Listen for unhandled promise rejections from the page context
  page.evaluate(() => {
    if (!window.__vibecomfyE2eUnhandledErrors) {
      window.__vibecomfyE2eUnhandledErrors = [];
      window.addEventListener("unhandledrejection", (event) => {
        window.__vibecomfyE2eUnhandledErrors.push({
          message: String(event.reason?.message || event.reason || "unhandled rejection"),
          timestamp: new Date().toISOString(),
        });
      });
      window.addEventListener("error", (event) => {
        window.__vibecomfyE2eUnhandledErrors.push({
          message: event.message || "page error",
          source: event.filename,
          lineno: event.lineno,
          colno: event.colno,
          timestamp: new Date().toISOString(),
        });
      });
    }
  }).catch(() => {
    // Best-effort: if evaluate fails (e.g. page already closed), ignore.
  });

  return {
    consoleErrors,
    failedRequests,
    pageErrors,
    unhandledErrors,

    summary() {
      const parts = [];
      if (consoleErrors.length > 0) {
        parts.push(`${consoleErrors.length} console error(s)/warning(s)`);
      }
      if (failedRequests.length > 0) {
        parts.push(`${failedRequests.length} failed request(s)`);
      }
      if (pageErrors.length > 0) {
        parts.push(`${pageErrors.length} page error(s)`);
      }
      return parts.length > 0 ? parts.join("; ") : "no failures captured";
    },

    reset() {
      consoleErrors.length = 0;
      failedRequests.length = 0;
      pageErrors.length = 0;
      unhandledErrors.length = 0;
    },
  };
}

/**
 * Assert zero captured failures and produce a clear failure message.
 *
 * @param {FailureCapture} capture
 */
export function assertNoFailures(capture) {
  const summary = capture.summary();
  if (summary !== "no failures captured") {
    const details = [];
    for (const e of capture.consoleErrors) {
      details.push(`  [console.${e.type}] ${e.text}`);
    }
    for (const r of capture.failedRequests) {
      details.push(`  [request] ${r.url} → ${r.status} ${r.statusText}`);
    }
    for (const e of capture.pageErrors) {
      details.push(`  [pageerror] ${e.message}`);
    }
    throw new Error(`Failures captured during test: ${summary}\n${details.join("\n")}`);
  }
}

/**
 * Collect page-level unhandled errors that were registered via the injected
 * window.__vibecomfyE2eUnhandledErrors listener.
 *
 * @param {import("@playwright/test").Page} page
 * @returns {Promise<Array<{message: string, source?: string, lineno?: number, colno?: number}>>}
 */
export async function collectUnhandledPageErrors(page) {
  try {
    return await page.evaluate(() => {
      return window.__vibecomfyE2eUnhandledErrors || [];
    });
  } catch {
    return [];
  }
}
