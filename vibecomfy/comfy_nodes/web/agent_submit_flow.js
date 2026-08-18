// ── Submit flow (T-057) ─────────────────────────────────────────────────────
// The submit orchestration machinery — prompt-draft capture, POST body
// building, watchdog deadlines/activity tracking, fetch-with-deadline, and
// failure normalization — extracted from vibecomfy_roundtrip.js.
//
// This module lives behind an injected-boundary factory: roundtrip builds a
// deps object ONCE at module init from its existing module singletons and
// calls createSubmitFlow(deps).  The flow NEVER captures the three module
// singletons (submitWatchdogDepsState, submitActivityByPanel,
// pendingTransactionSnapshotByPanel) or the DEFAULT_SUBMIT_* constants as
// module-level imports/state of its own — it reads them through the injected
// object references, so configureSubmitWatchdogDeps / resetSubmitWatchdogDeps
// in roundtrip keep mutating the SAME state the flow reads (injections and
// resets keep working after extraction).  T-061 will centralize the
// singletons into web/agent_flow_deps.js without changing this seam.
//
// Behavioral contract (must stay identical to the pre-extraction roundtrip
// code): same failure envelopes and messages, same retry/supersede semantics,
// same WeakMap lifecycle (set/get/delete on submitActivityByPanel), same
// defaults and watchdog timing math.

export function createSubmitFlow(deps) {
  const {
    submitWatchdogDepsState,
    submitActivityByPanel,
    // Injected for the T-061 centralization seam; the submit flow itself does
    // not read this WeakMap (it is transaction-compensation state owned by the
    // apply/rollback/undo paths, which remain in roundtrip).
    pendingTransactionSnapshotByPanel,
    DEFAULT_SUBMIT_DEADLINE_MS,
    DEFAULT_SUBMIT_ABSOLUTE_DEADLINE_MS,
    DEFAULT_SUBMIT_AUTOMATIC_RETRY_COUNT,
    getPanelElementById,
    PANEL_IDS,
    PANEL_STATE,
    readOnDemandSchemasSetting,
    api,
    normalizeRoutePreference,
    agentPanelFailure,
    // Optional two-step bound-session resolver.  When twoStepMode is set on a
    // submit, buildSubmitBody sends the browser-owned (get-or-create) session
    // id instead of `undefined` — the server never mints ids for two-step.
    // The resolver receives the submitting panel so the host can read the
    // per-tab scope; zero-arg resolvers keep working (extra args are ignored).
    getOrCreateBoundSessionId,
    // Optional UI hook invoked when the inactivity watchdog expires while the
    // absolute deadline still has time (see runSubmitFetchWithDeadline). The
    // flow marks the non-terminal stall state and re-arms itself; the host
    // uses this hook to surface "still working" without aborting the fetch.
    onSubmitStalled,
  } = deps;

  // Used to preserve drafts before auto-switching scopes during submit.
  function capturePromptDraft(panel) {
    const promptEl = getPanelElementById(panel, PANEL_IDS.prompt) || panel?.fields?.prompt;
    if (promptEl && typeof promptEl.value === "string") {
      return promptEl.value || null;
    }
    return null;
  }

  /** Build the POST body for /vibecomfy/agent-executor. */
  function buildSubmitBody(snapshot, task, panel, options = {}) {
    const sessionIdOverride =
      typeof options.sessionIdOverride === "string" && options.sessionIdOverride
        ? options.sessionIdOverride
        : null;
    const route = String(snapshot.route || "").trim().toLowerCase();
    const profile = route === "openai-codex" || route === "codex"
      ? "openai"
      : route === "anthropic" || route === "claude"
        ? "anthropic"
        : route === "openrouter"
          ? "openrouter"
        : route === "opensource"
          ? "opensource"
          : "default";
    return {
      graph: snapshot.graph,
      workflow_id: snapshot.workflowId,
      task,
      route: snapshot.route,
      profile,
      model: snapshot.model || undefined,
      session_id:
        sessionIdOverride
        || panel.state.sessionId
        || (options.twoStepMode && typeof getOrCreateBoundSessionId === "function"
          ? getOrCreateBoundSessionId(panel)
          : undefined),
      client_id: api?.clientId || undefined,
      client_graph_hash: snapshot.graphHash,
      client_structural_graph_hash: snapshot.structuralHash,
      client_live_canvas_token: snapshot.liveCanvasToken,
      // Submit-time canvas adoption is a real baseline transition on the
      // backend. Bind it to the baseline this document last observed so two
      // concurrent/stale documents cannot silently replace one another.
      expected_baseline_graph_hash: snapshot.expectedBaselineGraphHash ?? null,
      idempotency_key: snapshot.idempotencyKey,
      on_demand_schemas: readOnDemandSchemasSetting(),
    };
  }

  function currentSubmitDeadlineMs(panel = null) {
    const stateDeadlineMs = Number(panel?.state?.submitDeadlineMs);
    if (Number.isFinite(stateDeadlineMs) && stateDeadlineMs > 0) {
      return stateDeadlineMs;
    }
    const configuredDeadlineMs = Number(submitWatchdogDepsState.submitDeadlineMs);
    if (Number.isFinite(configuredDeadlineMs) && configuredDeadlineMs > 0) {
      return configuredDeadlineMs;
    }
    return DEFAULT_SUBMIT_DEADLINE_MS;
  }

  function currentSubmitAbsoluteDeadlineMs() {
    const configuredDeadlineMs = Number(submitWatchdogDepsState.submitAbsoluteDeadlineMs);
    if (Number.isFinite(configuredDeadlineMs) && configuredDeadlineMs > 0) {
      return configuredDeadlineMs;
    }
    return DEFAULT_SUBMIT_ABSOLUTE_DEADLINE_MS;
  }

  function currentSubmitAutomaticRetryCount() {
    const configuredRetryCount = Number(submitWatchdogDepsState.submitAutomaticRetryCount);
    if (Number.isFinite(configuredRetryCount) && configuredRetryCount >= 0) {
      return Math.max(0, Math.floor(configuredRetryCount));
    }
    return DEFAULT_SUBMIT_AUTOMATIC_RETRY_COUNT;
  }

  function currentSubmitNowMs() {
    return Number(submitWatchdogDepsState.nowMs());
  }

  function beginSubmitActivity(panel, submitEpoch) {
    const nowMs = currentSubmitNowMs();
    submitActivityByPanel.set(panel, {
      submitEpoch,
      startedAtMs: nowMs,
      lastActivityAtMs: nowMs,
    });
    return nowMs;
  }

  function recordSubmitActivity(panel) {
    if (!panel?.state || panel.state.phase !== PANEL_STATE.SUBMITTING) {
      return false;
    }
    const activity = submitActivityByPanel.get(panel);
    if (!activity || activity.submitEpoch !== panel.state.submitEpoch) {
      return false;
    }
    activity.lastActivityAtMs = currentSubmitNowMs();
    // Progress resumed — clear any non-terminal stall marker raised by the
    // inactivity watchdog so the "still working" notice does not linger.
    if (panel.state.submitStalledSince != null) {
      panel.state.submitStalledSince = null;
      panel.state.submitStalledLastProgressAtMs = null;
    }
    return true;
  }

  function readSubmitFailureMessage(error) {
    if (typeof error?.user_facing_message === "string" && error.user_facing_message.trim()) {
      return error.user_facing_message.trim();
    }
    if (typeof error?.message === "string" && error.message.trim()) {
      return error.message.trim();
    }
    return String(error);
  }

  function buildSubmitFailureContext(panel, snapshot = null, extras = {}) {
    const route = typeof extras.route === "string" && extras.route
      ? extras.route
      : typeof snapshot?.route === "string" && snapshot.route
        ? snapshot.route
        : typeof panel?.state?.lastSubmit?.route === "string" && panel.state.lastSubmit.route
          ? panel.state.lastSubmit.route
          : normalizeRoutePreference(panel?.fields?.route?.value);
    const context = {
      session_id: extras.sessionId ?? panel?.state?.sessionId ?? null,
      turn_id: extras.turnId ?? panel?.state?.turnId ?? null,
      route: route || null,
      url: "/vibecomfy/agent-executor",
      timeout_ms: Number.isFinite(extras.timeoutMs) ? Number(extras.timeoutMs) : currentSubmitDeadlineMs(panel),
    };
    const httpStatus = Number.isFinite(extras.httpStatus) ? Number(extras.httpStatus) : null;
    if (httpStatus !== null) {
      context.http_status = httpStatus;
    }
    if (typeof extras.nextAction === "string" && extras.nextAction.trim()) {
      context.next_action = extras.nextAction.trim();
    }
    return context;
  }

  function mergeSubmitFailureContext(error, diagnosticContext = {}) {
    const merged = {
      ...diagnosticContext,
      ...(error && typeof error === "object" ? error : {}),
    };
    if (merged.http_status == null && Number.isFinite(merged.status)) {
      merged.http_status = Number(merged.status);
    }
    if (merged.timeout_ms == null && diagnosticContext.timeout_ms != null) {
      merged.timeout_ms = diagnosticContext.timeout_ms;
    }
    if (merged.next_action == null && diagnosticContext.next_action != null) {
      merged.next_action = diagnosticContext.next_action;
    }
    if (merged.route == null && diagnosticContext.route != null) {
      merged.route = diagnosticContext.route;
    }
    if (merged.url == null && diagnosticContext.url != null) {
      merged.url = diagnosticContext.url;
    }
    if (merged.session_id == null && diagnosticContext.session_id != null) {
      merged.session_id = diagnosticContext.session_id;
    }
    if (merged.turn_id == null && diagnosticContext.turn_id != null) {
      merged.turn_id = diagnosticContext.turn_id;
    }
    return merged;
  }

  function buildSubmitTimeoutFailure(panel, snapshot, deadlineMs, timeoutKind = "inactivity") {
    const absolute = timeoutKind === "absolute";
    return agentPanelFailure(
      "TimeoutError",
      absolute
        ? "The submit request exceeded the maximum total execution time."
        : "The submit request stopped reporting progress before the backend responded.",
      {
        stage: "agent-executor",
        retryable: true,
        graph_unchanged: true,
        ...buildSubmitFailureContext(panel, snapshot, {
          timeoutMs: deadlineMs,
          nextAction: "Check the server turn artifacts before you Submit again; the backend may still be finishing the original request.",
        }),
        timeout_kind: timeoutKind,
      },
    );
  }

  function runSubmitFetchWithDeadline(fetchPromise, {
    panel,
    snapshot,
    submitAbortController,
    submitEpoch,
    deadlineMs,
    absoluteDeadlineMs,
  }) {
    return new Promise((resolve, reject) => {
      const existingActivity = submitActivityByPanel.get(panel);
      if (!existingActivity || existingActivity.submitEpoch !== submitEpoch) {
        beginSubmitActivity(panel, submitEpoch);
      }
      let settled = false;
      let timeoutId = null;
      const finalize = () => {
        if (timeoutId != null) {
          submitWatchdogDepsState.clearTimeoutFn(timeoutId);
          timeoutId = null;
        }
        const activity = submitActivityByPanel.get(panel);
        if (activity?.submitEpoch === submitEpoch) {
          submitActivityByPanel.delete(panel);
        }
      };
      const settle = (callback, value) => {
        if (settled) {
          return;
        }
        settled = true;
        finalize();
        callback(value);
      };
      const expireOrRearm = () => {
        if (
          panel?.state?.submitEpoch !== submitEpoch
          || panel?.state?.submitAbortController !== submitAbortController
        ) {
          const staleError = new Error("Submit watchdog expired after its attempt was superseded.");
          staleError.name = "AbortError";
          settle(reject, staleError);
          return;
        }
        const nowMs = currentSubmitNowMs();
        const activity = submitActivityByPanel.get(panel) || {
          startedAtMs: nowMs,
          lastActivityAtMs: nowMs,
        };
        const inactivityRemainingMs = deadlineMs - (nowMs - activity.lastActivityAtMs);
        const absoluteRemainingMs = absoluteDeadlineMs - (nowMs - activity.startedAtMs);
        if (inactivityRemainingMs > 0 && absoluteRemainingMs > 0) {
          timeoutId = submitWatchdogDepsState.setTimeoutFn(
            expireOrRearm,
            Math.min(inactivityRemainingMs, absoluteRemainingMs),
          );
          return;
        }
        if (absoluteRemainingMs > 0) {
          // The inactivity deadline expired but the absolute deadline still has
          // time. This is a non-terminal stall: the provider may still be
          // working silently (e.g. a long tool call between heartbeats). Do NOT
          // abort or settle — surface "still working, last progress Xs ago" and
          // keep waiting until the absolute deadline.
          if (panel?.state) {
            panel.state.submitStalledSince = nowMs;
            panel.state.submitStalledLastProgressAtMs = activity.lastActivityAtMs;
          }
          if (typeof onSubmitStalled === "function") {
            try {
              onSubmitStalled(panel, {
                stalledSinceMs: nowMs,
                lastProgressAtMs: activity.lastActivityAtMs,
              });
            } catch (_error) {
              // UI hook is best-effort; the watchdog re-arm below is the
              // behavioral contract.
            }
          }
          timeoutId = submitWatchdogDepsState.setTimeoutFn(
            expireOrRearm,
            absoluteRemainingMs,
          );
          return;
        }
        try {
          submitAbortController?.abort();
        } catch (_error) {
          // Best-effort abort only.
        }
        settle(reject, buildSubmitTimeoutFailure(panel, snapshot, absoluteDeadlineMs, "absolute"));
      };
      timeoutId = submitWatchdogDepsState.setTimeoutFn(
        expireOrRearm,
        Math.min(deadlineMs, absoluteDeadlineMs),
      );
      Promise.resolve(fetchPromise).then(
        (value) => settle(resolve, value),
        (error) => settle(reject, error),
      );
    });
  }

  /** Normalize a caught error into a failure envelope that submitAgentEdit can store. */
  function normalizeSubmitFailure(error, diagnosticContext = {}) {
    if (error?.ok === false) {
      return mergeSubmitFailureContext(error, diagnosticContext);
    }
    return agentPanelFailure("NetworkError", readSubmitFailureMessage(error), {
      retryable: true,
      ...mergeSubmitFailureContext({
        next_action: "Retry once the local ComfyUI backend responds again.",
      }, diagnosticContext),
    });
  }

  function isValidationSubmitFailure(failure) {
    const kind = typeof failure?.kind === "string" ? failure.kind : "";
    const errorCode = typeof failure?.error === "string" ? failure.error : "";
    return kind === "ValidationError" || errorCode === "validation";
  }

  function isStaleSubmitFailure(failure) {
    const kind = typeof failure?.kind === "string" ? failure.kind : "";
    return kind === "StaleStateMismatch" || Boolean(failure?.rebaseline_recovery || failure?.rebaselineRecovery);
  }

  function markBackendSubmitFailure(error, metadata = {}) {
    if (!error || typeof error !== "object") {
      return error;
    }
    return {
      ...error,
      ok: false,
      failure_source: "backend",
      ...metadata,
    };
  }

  function shouldAutoRetrySubmitFailure(error, failure, { attemptIndex, maxAutomaticRetryCount } = {}) {
    if (!failure || typeof failure !== "object") {
      return false;
    }
    if (failure.failure_source !== "backend") {
      return false;
    }
    if (failure.retryable !== true) {
      return false;
    }
    if (isValidationSubmitFailure(failure)) {
      return false;
    }
    if (isStaleSubmitFailure(failure)) {
      return false;
    }
    const normalizedAttemptIndex = Number.isFinite(attemptIndex) ? Number(attemptIndex) : 0;
    const normalizedRetryBudget = Number.isFinite(maxAutomaticRetryCount)
      ? Math.max(0, Number(maxAutomaticRetryCount))
      : 0;
    if (normalizedAttemptIndex >= normalizedRetryBudget) {
      return false;
    }
    if (error?.name === "AbortError") {
      return false;
    }
    return true;
  }

  /** Validate that a result payload is a usable success envelope (clarify or candidate). */
  function isSubmitResponseValid(outcome, candidateGraph) {
    if (!outcome || typeof outcome !== "object") {
      return false;
    }
    switch (outcome.kind) {
      case "clarify":
      case "noop":
      case "requires_custom_nodes":
        return true;
      case "candidate":
        return Boolean(candidateGraph && typeof candidateGraph === "object");
      case "error":
        return false;
      default:
        return false;
    }
  }

  return {
    capturePromptDraft,
    buildSubmitBody,
    currentSubmitDeadlineMs,
    currentSubmitAbsoluteDeadlineMs,
    currentSubmitAutomaticRetryCount,
    currentSubmitNowMs,
    beginSubmitActivity,
    recordSubmitActivity,
    readSubmitFailureMessage,
    buildSubmitFailureContext,
    mergeSubmitFailureContext,
    buildSubmitTimeoutFailure,
    runSubmitFetchWithDeadline,
    normalizeSubmitFailure,
    isValidationSubmitFailure,
    isStaleSubmitFailure,
    markBackendSubmitFailure,
    shouldAutoRetrySubmitFailure,
    isSubmitResponseValid,
  };
}
