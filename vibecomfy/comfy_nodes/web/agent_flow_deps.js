// Shared live dependencies for the extracted agent flow modules.

// A single backend model worker may legitimately run for 180 seconds
// (VIBECOMFY_AGENT_TURN_TIMEOUT). The browser watchdog therefore measures
// *inactivity*, not total request duration, and leaves a small transport / job
// scheduling margin beyond the worker's own timeout.
export const DEFAULT_SUBMIT_DEADLINE_MS = 210000;
export const DEFAULT_SUBMIT_ABSOLUTE_DEADLINE_MS = 900000;
export const DEFAULT_SUBMIT_AUTOMATIC_RETRY_COUNT = 1;

export const DEFAULT_SUBMIT_WATCHDOG_DEPS = Object.freeze({
  nowMs() {
    if (typeof globalThis.performance?.now === "function") {
      return globalThis.performance.now();
    }
    return Date.now();
  },
  setTimeoutFn(handler, delayMs) {
    return globalThis.setTimeout(handler, delayMs);
  },
  clearTimeoutFn(timeoutId) {
    if (timeoutId != null) {
      globalThis.clearTimeout(timeoutId);
    }
  },
  submitDeadlineMs: DEFAULT_SUBMIT_DEADLINE_MS,
  submitAbsoluteDeadlineMs: DEFAULT_SUBMIT_ABSOLUTE_DEADLINE_MS,
  submitAutomaticRetryCount: DEFAULT_SUBMIT_AUTOMATIC_RETRY_COUNT,
});

/**
 * Create the live state owned by one submit-flow consumer.
 *
 * Keeping these carriers inside a factory prevents a test harness, embedded
 * editor, or second extension instance from replacing another consumer's
 * watchdog clock/deadlines. The returned WeakMaps remain shared within that
 * consumer so the submit flow and roundtrip compensation paths see the same
 * panel-affine state.
 */
export function createSubmitFlowDeps(initialOverrides = {}) {
  const submitWatchdogDepsState = {
    ...DEFAULT_SUBMIT_WATCHDOG_DEPS,
  };

  // Live watchdog timestamps intentionally stay outside lifecycle state: they
  // describe an in-memory fetch and must never be rehydrated after a reload.
  const submitActivityByPanel = new WeakMap();
  // Pre-finalize canvas snapshots are transaction compensation state, not Undo
  // history. Keep them private to the live panel until finalize publishes a
  // durable accepted baseline or rollback consumes them.
  const pendingTransactionSnapshotByPanel = new WeakMap();

  function configureSubmitWatchdogDeps(overrides = {}) {
    if (!overrides || typeof overrides !== "object") {
      return { ...submitWatchdogDepsState };
    }
    if (typeof overrides.nowMs === "function") {
      submitWatchdogDepsState.nowMs = overrides.nowMs;
    }
    if (typeof overrides.setTimeoutFn === "function") {
      submitWatchdogDepsState.setTimeoutFn = overrides.setTimeoutFn;
    }
    if (typeof overrides.clearTimeoutFn === "function") {
      submitWatchdogDepsState.clearTimeoutFn = overrides.clearTimeoutFn;
    }
    if (Number.isFinite(overrides.submitDeadlineMs) && Number(overrides.submitDeadlineMs) > 0) {
      submitWatchdogDepsState.submitDeadlineMs = Number(overrides.submitDeadlineMs);
    }
    if (Number.isFinite(overrides.submitAbsoluteDeadlineMs) && Number(overrides.submitAbsoluteDeadlineMs) > 0) {
      submitWatchdogDepsState.submitAbsoluteDeadlineMs = Number(overrides.submitAbsoluteDeadlineMs);
    }
    if (Number.isFinite(overrides.submitAutomaticRetryCount) && Number(overrides.submitAutomaticRetryCount) >= 0) {
      submitWatchdogDepsState.submitAutomaticRetryCount = Number(overrides.submitAutomaticRetryCount);
    }
    return { ...submitWatchdogDepsState };
  }

  function resetSubmitWatchdogDeps() {
    Object.assign(submitWatchdogDepsState, DEFAULT_SUBMIT_WATCHDOG_DEPS);
    return { ...submitWatchdogDepsState };
  }

  const flowDeps = {
    submitWatchdogDepsState,
    submitActivityByPanel,
    pendingTransactionSnapshotByPanel,
    configureSubmitWatchdogDeps,
    resetSubmitWatchdogDeps,
  };
  configureSubmitWatchdogDeps(initialOverrides);
  return flowDeps;
}
