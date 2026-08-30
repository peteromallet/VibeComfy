// ── Rebaseline / undo flow (T-059) ─────────────────────────────────────────
// Rebaseline, rollback, reject, and Undo orchestration extracted from
// vibecomfy_roundtrip.js. Lifecycle state and panel-owned preview caches remain
// authoritative in the injected roundtrip/lifecycle seams.

import { vibecomfyFetch } from "./http_security.js";

export function createRebaselineUndoFlow(deps) {
  const {
    PANEL_STATE,
    agentPanelFailure,
    app,
    applyGraphDeltaInPlace,
    applyGraphInPlaceWithIntentDecoration,
    applyGraphLayoutInPlace,
    boundedBrowserTransactionError,
    buildActionIdempotencyKey,
    buildCanvasSnapshot,
    buildInverseDeltaOps,
    clearLayoutPreviewState,
    clonePlainData,
    commitReconcileReceipts,
    commitRollbackFailure,
    commitRollbackStarted,
    commitRollbackSuccess,
    extractRebaselineRecovery,
    fulfillLifecycleTransitionObligations,
    isLayoutAuthorityTransaction,
    isLegacyUndoCacheEntryV1,
    isV2ApplyCandidate,
    layoutGraphHash,
    restoreUndoGraph,
    normalizeAuxiliaryAgentPayload,
    normalizeCandidateTransaction,
    pendingTransactionSnapshotByPanel,
    postAgentLifecycleAction,
    pushHistory,
    pushTurnStatus,
    recoveryForPanelState,
    rememberTurnDetailSnapshot,
    renderAgentPanel,
    renderLifecycleTransition,
    restoreLayoutPreviewBaseline,
    submitAgentEdit,
    syntheticFailureAgentMessage,
    transactionAllowsRejectOrFailClosedDiscard,
    transition,
  } = deps;

  function buildRebaselineIdempotencyKey({ sessionId, reason, baselineGraphHash, structuralHash }) {
    const sessionPart = sessionId || "new";
    const reasonPart = String(reason || "continue_from_canvas").trim() || "continue_from_canvas";
    const baselinePart = typeof baselineGraphHash === "string" && baselineGraphHash
      ? baselineGraphHash.slice(0, 12)
      : "none";
    const structuralPart = typeof structuralHash === "string" && structuralHash
      ? structuralHash.slice(0, 12)
      : "unknown";
    return `rebaseline:${sessionPart}:${reasonPart}:${baselinePart}:${structuralPart}`;
  }

  function rollbackFailureKind(value) {
    return typeof value?.kind === "string" && value.kind
      ? value.kind
      : typeof value?.failure_kind === "string" && value.failure_kind
        ? value.failure_kind
        : null;
  }

  function rollbackFailureMessage(value) {
    for (const candidate of [value?.user_facing_message, value?.message, value?.error]) {
      if (typeof candidate === "string" && candidate) {
        return candidate.slice(0, 2048);
      }
    }
    return null;
  }

  function normalizeLifecycleReceiptsFromEvents(events) {
    const receipts = {
      preparedReceipt: null,
      verifiedReceipt: null,
      rollbackReceipt: null,
      lifecycleEvents: [],
    };
    if (!Array.isArray(events)) {
      return receipts;
    }
    receipts.lifecycleEvents = events.map((event) => clonePlainData(event));
    for (const event of events) {
      if (!event || typeof event !== "object") {
        continue;
      }
      const eventType = String(event.event_type || event.eventType || "");
      const receipt = event.receipt && typeof event.receipt === "object"
        ? clonePlainData(event.receipt)
        : clonePlainData(event);
      if (eventType === "prepared") {
        receipts.preparedReceipt = receipt;
      } else if (eventType === "finalized") {
        receipts.finalizedReceipt = receipt;
        receipts.verifiedReceipt = {
          plan_hash: receipt.plan_hash || null,
          generation: receipt.generation ?? null,
          post_apply_hash: receipt.applied_payload?.post_apply_hash || null,
          finalized_receipt: receipt,
        };
      } else if (eventType === "rolled_back") {
        receipts.rollbackReceipt = receipt;
      }
    }
    return receipts;
  }

  async function reconcilePreparedTransactionState(panel) {
    if (!panel?.state?.sessionId || !panel?.state?.turnId) {
      return null;
    }
    const payload = await postAgentLifecycleAction("reconcile", {
      session_id: panel.state.sessionId,
      turn_id: panel.state.turnId,
    }, "reconcile");
    const events = Array.isArray(payload?.raw?.receipts_by_turn?.[panel.state.turnId])
      ? payload.raw.receipts_by_turn[panel.state.turnId]
      : [];
    const receipts = normalizeLifecycleReceiptsFromEvents(events);
    const candidateTransaction = normalizeCandidateTransaction(
      payload?.raw?.transactions_by_turn?.[panel.state.turnId],
    );
    const recoveryGraph = payload?.raw?.recovery_graphs_by_turn?.[panel.state.turnId];
    if (recoveryGraph?.graph && typeof recoveryGraph.graph === "object") {
      pendingTransactionSnapshotByPanel.set(panel, {
        graph: clonePlainData(recoveryGraph.graph),
        graphHash: recoveryGraph.graph_hash || null,
        structuralHash: recoveryGraph.structural_graph_hash || null,
        layoutHash: recoveryGraph.layout_graph_hash || null,
        liveCanvasToken: null,
      });
    }
    const obligations = commitReconcileReceipts(panel, {
      receipts,
      candidateTransaction,
      debugPayload: {
        reconcile_response: payload.raw || payload,
        reconciled_receipts: receipts,
        recovery_graph_available: Boolean(recoveryGraph?.graph),
      },
    });
    fulfillLifecycleTransitionObligations(panel, obligations);
    if (candidateTransaction?.state === "finalized") {
      pendingTransactionSnapshotByPanel.delete(panel);
    }
    return payload;
  }

  async function rollbackPreparedAgentCandidate(
    panel,
    snapshot,
    {
      restoreCanvas = false,
      silent = false,
      triggerStage = "manual",
      triggerFailure = null,
      canvasWasMutated = restoreCanvas,
    } = {},
  ) {
    const expectedLayoutHash = snapshot?.layoutHash
      || (snapshot?.graph ? await layoutGraphHash(snapshot.graph) : null);
    const canvasRestore = {
      attempted: Boolean(restoreCanvas),
      restored: !restoreCanvas,
      expected_structural_hash: snapshot?.structuralHash || null,
      actual_structural_hash: null,
      expected_graph_hash: snapshot?.graphHash || null,
      actual_graph_hash: null,
      expected_layout_hash: expectedLayoutHash,
      actual_layout_hash: null,
      error: null,
    };
    if (restoreCanvas) {
      try {
        if (!snapshot?.graph || typeof snapshot.graph !== "object") {
          throw new Error("Rollback has no pre-apply canvas snapshot.");
        }
        const transaction = normalizeCandidateTransaction(panel.state.candidateTransaction);
        if (!transaction) throw new Error("Rollback has no canonical transaction plan.");
        const layoutTransaction = isLayoutAuthorityTransaction(transaction);
        const inverseDeltaOps = buildInverseDeltaOps(
          snapshot.graph,
          (Array.isArray(transaction.plan.accepted_batch) ? transaction.plan.accepted_batch : [])
            .filter((statement) => statement && typeof statement === "object" && statement.op && typeof statement.op === "object")
            .map((statement) => statement.op),
        );
        canvasRestore.scoped_inverse = {
          attempted: true,
          inverse_op_count: inverseDeltaOps.length,
          strategy: layoutTransaction ? "native_layout_restore" : "inverse_delta",
        };
        try {
          if (layoutTransaction) {
            applyGraphLayoutInPlace(app, {
              candidateGraph: clonePlainData(snapshot.graph),
            });
          } else {
            applyGraphDeltaInPlace(app, {
              deltaOps: inverseDeltaOps,
              candidateGraph: clonePlainData(snapshot.graph),
            });
          }
        } catch (inverseError) {
          canvasRestore.scoped_inverse.error = boundedBrowserTransactionError(
            inverseError,
            "scoped_inverse_recovery",
            { resumeState: "prepared" },
          );
        }
        let restoredSnapshot = null;
        try {
          restoredSnapshot = await buildCanvasSnapshot();
          canvasRestore.actual_structural_hash = restoredSnapshot.structuralHash || null;
          canvasRestore.actual_graph_hash = restoredSnapshot.graphHash || null;
          canvasRestore.actual_layout_hash = restoredSnapshot.layoutHash || null;
          canvasRestore.restored = layoutTransaction
            ? Boolean(expectedLayoutHash && restoredSnapshot.layoutHash === expectedLayoutHash)
            : Boolean(snapshot.structuralHash && restoredSnapshot.structuralHash === snapshot.structuralHash);
        } catch (verificationError) {
          canvasRestore.scoped_inverse.error = canvasRestore.scoped_inverse.error
            || boundedBrowserTransactionError(
              verificationError,
              "scoped_inverse_verification",
              { resumeState: "prepared" },
            );
          canvasRestore.restored = false;
        }
        canvasRestore.scoped_inverse.restored = canvasRestore.restored;
        if (!canvasRestore.restored && !layoutTransaction) {
          canvasRestore.whole_graph_last_resort = { attempted: true };
          applyGraphInPlaceWithIntentDecoration(snapshot.graph);
          restoredSnapshot = await buildCanvasSnapshot();
          canvasRestore.actual_structural_hash = restoredSnapshot.structuralHash || null;
          canvasRestore.actual_graph_hash = restoredSnapshot.graphHash || null;
          canvasRestore.actual_layout_hash = restoredSnapshot.layoutHash || null;
          canvasRestore.restored = Boolean(snapshot.structuralHash
            && restoredSnapshot.structuralHash === snapshot.structuralHash);
          canvasRestore.whole_graph_last_resort.restored = canvasRestore.restored;
        }
        if (!canvasRestore.restored) {
          canvasRestore.error = layoutTransaction
            ? "Restored layout geometry did not match the pre-apply layout hash."
            : "Restored canvas did not match the pre-apply structural hash.";
        }
      } catch (error) {
        canvasRestore.restored = false;
        canvasRestore.error = String(error);
      }
    }
    if (restoreCanvas && !canvasRestore.restored) {
      const failure = agentPanelFailure(
        "CanvasRestoreError",
        canvasRestore.error || "Could not verify restoration of the pre-apply canvas.",
        {
          retryable: true,
          graph_unchanged: false,
          next_action: "Keep the prepared transaction open and retry canvas restoration before rollback.",
        },
      );
      if (!silent) {
        const obligations = commitRollbackFailure(panel, {
          failure,
          debugPayload: {
            rollback_failure: failure,
            canvas_restore: canvasRestore,
          },
        });
        fulfillLifecycleTransitionObligations(panel, obligations);
        renderLifecycleTransition(panel, obligations);
      }
      return {
        ok: false,
        server_rolled_back: false,
        canvas_restore: canvasRestore,
        failure,
      };
    }
    const compensation = {
      trigger_stage: triggerStage,
      canvas_was_mutated: Boolean(canvasWasMutated),
      canvas_restore_attempted: canvasRestore.attempted,
      canvas_restore_succeeded: canvasRestore.restored && canvasRestore.attempted,
      ...(rollbackFailureKind(triggerFailure)
        ? { failure_kind: rollbackFailureKind(triggerFailure).slice(0, 128) }
        : {}),
      ...(rollbackFailureMessage(triggerFailure)
        ? { failure_message: rollbackFailureMessage(triggerFailure) }
        : {}),
      ...(canvasRestore.expected_graph_hash
        ? { pre_apply_graph_hash: canvasRestore.expected_graph_hash }
        : {}),
      ...(canvasRestore.actual_graph_hash
        ? { post_restore_graph_hash: canvasRestore.actual_graph_hash }
        : {}),
      ...(canvasRestore.expected_structural_hash
        ? { pre_apply_structural_hash: canvasRestore.expected_structural_hash }
        : {}),
      ...(canvasRestore.actual_structural_hash
        ? { post_restore_structural_hash: canvasRestore.actual_structural_hash }
        : {}),
    };
    const rollbackBody = {
      session_id: panel.state.sessionId,
      turn_id: panel.state.turnId,
      plan_hash: panel.state.mutationPlanHash,
      generation: panel.state.generation,
      lease_nonce: panel.state.leaseNonce || undefined,
      client_graph_hash: snapshot?.graphHash || undefined,
      client_structural_graph_hash: snapshot?.structuralHash || undefined,
      compensation,
      idempotency_key: buildActionIdempotencyKey({
        action: "rollback",
        sessionId: panel.state.sessionId,
        turnId: panel.state.turnId,
        graphHash: snapshot?.graphHash || panel.state.candidateGraphHash,
      }),
    };
    if (!silent) {
      const started = commitRollbackStarted(panel, {
        debugPayload: { rollback_request: rollbackBody, canvas_restore: canvasRestore },
      });
      fulfillLifecycleTransitionObligations(panel, started);
      renderLifecycleTransition(panel, started);
    }
    try {
      const rolledBack = await postAgentLifecycleAction("rollback", rollbackBody, "rollback");
      pendingTransactionSnapshotByPanel.delete(panel);
      if (!silent) {
        const obligations = commitRollbackSuccess(panel, {
          rollbackReceipt: rolledBack.receipt || null,
          candidateTransaction: rolledBack.candidateTransaction,
          message: rolledBack.message || "Prepared transaction rolled back.",
          toast: "Prepared transaction rolled back",
          debugPayload: {
            rollback_request: rollbackBody,
            rollback_response: rolledBack.raw || rolledBack,
            canvas_restore: canvasRestore,
          },
        });
        fulfillLifecycleTransitionObligations(panel, obligations);
        clearLayoutPreviewState(panel);
        renderLifecycleTransition(panel, obligations);
      }
      return {
        ok: true,
        server_rolled_back: true,
        rollback_receipt: rolledBack.receipt || null,
        canvas_restore: canvasRestore,
        response: rolledBack.raw || rolledBack,
      };
    } catch (error) {
      const failure = error?.ok === false
        ? error
        : agentPanelFailure("RollbackError", String(error), {
            retryable: true,
            graph_unchanged: true,
            next_action: "Retry rollback or Rebaseline from the current canvas.",
          });
      if (!silent) {
        const obligations = commitRollbackFailure(panel, {
          failure,
          debugPayload: {
            rollback_request: rollbackBody,
            rollback_failure: failure,
            canvas_restore: canvasRestore,
          },
        });
        fulfillLifecycleTransitionObligations(panel, obligations);
        renderLifecycleTransition(panel, obligations);
      }
      return {
        ok: false,
        server_rolled_back: false,
        canvas_restore: canvasRestore,
        failure,
      };
    }
  }

  async function rejectAgentCandidate(panel) {
    // ── T8: Demo-only reject branch (local state only, no backend reject) ──
    // Delegates to preview_picker which handles lifecycle reflection and
    // state cleanup inline.  No POST to /agent-edit/reject.
    if (panel?.state?.__demoMode) {
      if (!panel?.state?.candidateGraph || !panel.state.sessionId || !panel.state.turnId) {
        return;
      }
      return panel.previewPicker?.handleDemoReject?.(panel);
    }

    if (!panel?.state?.candidateGraph || !panel.state.sessionId || !panel.state.turnId) {
      return;
    }
    if (panel.state.chatRehydratePending === true) {
      return;
    }
    const rejectTransaction = normalizeCandidateTransaction(panel.state.candidateTransaction);
    const legacyCancelAllowed = Array.isArray(panel.state.legacyMigration?.actions)
      && panel.state.legacyMigration.actions.includes("cancel");
    const failClosedDiscardAllowed = transactionAllowsRejectOrFailClosedDiscard(
      rejectTransaction,
      {
        rawTransaction: panel.state.candidateTransaction,
        agentEditProtocol: panel.state.agentEditProtocol,
        candidatePresent: Boolean(panel.state.candidateGraph),
      },
    );
    if (!failClosedDiscardAllowed && !legacyCancelAllowed) {
      const failure = agentPanelFailure(
        "TransactionNotActionable",
        "This transaction is read-only and cannot be rejected or resumed.",
        {
          retryable: false,
          graph_unchanged: true,
          next_action: "Keep it for audit or submit a new edit against the current workflow.",
          legacy_migration: clonePlainData(panel.state.legacyMigration || null),
        },
      );
      const obligations = transition(panel, "REJECT_FAILURE", { failure, debugPayload: failure });
      fulfillLifecycleTransitionObligations(panel, obligations);
      renderLifecycleTransition(panel, obligations);
      return;
    }

    let snapshot;
    try {
      snapshot = await buildCanvasSnapshot();
    } catch (e) {
      const failure = agentPanelFailure("SerializeError", String(e), {
        retryable: true,
        graph_unchanged: true,
        next_action: "Make sure the canvas can serialize, then retry Reject.",
      });
      const obligations = transition(panel, "REJECT_FAILURE", {
        failure,
        syntheticAgentMessage: syntheticFailureAgentMessage(panel, failure, "frontend"),
        debugPayload: failure,
      });
      if (obligations.render) renderAgentPanel(panel);
      return;
    }

    if (
      isV2ApplyCandidate(panel)
      && (
        panel.state.phase === PANEL_STATE.APPLY_PREPARED
        || panel.state.phase === PANEL_STATE.CANVAS_VERIFIED
        || panel.state.phase === PANEL_STATE.FINALIZING
        || panel.state.phase === PANEL_STATE.RECOVERY_REQUIRED
      )
    ) {
      const recoveryMayHaveMutatedCanvas = (
        panel.state.phase === PANEL_STATE.FINALIZING
        || (
          panel.state.phase === PANEL_STATE.RECOVERY_REQUIRED
          && panel.state.failure?.graph_unchanged !== true
        )
      );
      if (
        panel.state.phase === PANEL_STATE.FINALIZING
        || panel.state.phase === PANEL_STATE.RECOVERY_REQUIRED
      ) {
        try {
          await reconcilePreparedTransactionState(panel);
        } catch (error) {
          const failure = agentPanelFailure("ReconcileError", String(error), {
            retryable: true,
            graph_unchanged: false,
            next_action: "Retry transaction recovery when the server is reachable.",
          });
          const obligations = transition(panel, "ROLLBACK_FAILURE", {
            failure,
            debugPayload: { recovery_reconcile_failure: failure },
          });
          fulfillLifecycleTransitionObligations(panel, obligations);
          renderLifecycleTransition(panel, obligations);
          return;
        }
        const reconciled = normalizeCandidateTransaction(panel.state.candidateTransaction);
        if (reconciled?.state === "finalized" || reconciled?.state === "rollback_complete") {
          return;
        }
      }
      const compensationSnapshot = pendingTransactionSnapshotByPanel.get(panel) || null;
      const liveStructuralHash = snapshot.structuralHash || null;
      const baselineStructuralHash = compensationSnapshot?.structuralHash || null;
      const candidateStructuralHash = compensationSnapshot?.candidateStructuralHash
        || panel.state.candidateTransaction?.hashes?.candidate_structural_graph_hash
        || null;
      const canvasMatchesBaseline = Boolean(
        baselineStructuralHash && liveStructuralHash === baselineStructuralHash,
      );
      const canvasMatchesCandidate = Boolean(
        candidateStructuralHash && liveStructuralHash === candidateStructuralHash,
      );
      let canvasWasMutated = panel.state.phase === PANEL_STATE.CANVAS_VERIFIED
        || recoveryMayHaveMutatedCanvas;
      if (canvasMatchesBaseline) {
        canvasWasMutated = false;
      } else if (canvasMatchesCandidate) {
        canvasWasMutated = true;
      } else if (compensationSnapshot?.rehydrated) {
        const failure = agentPanelFailure(
          "PreparedCanvasDiverged",
          "The canvas differs from both the pre-Apply baseline and the prepared candidate.",
          {
            retryable: true,
            graph_unchanged: true,
            next_action: "Restore either the original or candidate canvas before cancelling this interrupted Apply.",
          },
        );
        const obligations = transition(panel, "ROLLBACK_FAILURE", {
          failure,
          debugPayload: {
            rollback_failure: failure,
            live_structural_graph_hash: liveStructuralHash,
            baseline_structural_graph_hash: baselineStructuralHash,
            candidate_structural_graph_hash: candidateStructuralHash,
          },
        });
        fulfillLifecycleTransitionObligations(panel, obligations);
        renderLifecycleTransition(panel, obligations);
        return;
      }
      const rollbackSnapshot = compensationSnapshot?.graph
        ? {
            graph: compensationSnapshot.graph,
            graphHash: compensationSnapshot.graphHash || null,
            structuralHash: compensationSnapshot.structuralHash || null,
            liveCanvasToken: snapshot.liveCanvasToken,
          }
        : snapshot;
      await rollbackPreparedAgentCandidate(panel, rollbackSnapshot, {
        restoreCanvas: canvasWasMutated,
        triggerStage: "manual",
        canvasWasMutated,
      });
      return;
    }

    const rejectKey = buildActionIdempotencyKey({
      action: "reject",
      sessionId: panel.state.sessionId,
      turnId: panel.state.turnId,
      graphHash: snapshot.graphHash,
    });
    const rejectBody = {
      session_id: panel.state.sessionId,
      turn_id: panel.state.turnId,
      client_graph_hash: snapshot.graphHash,
      idempotency_key: rejectKey,
    };

    const startObligations = transition(panel, "REJECT_STARTED", {
      rejectBody,
      debugPayload: {
        rejecting_turn_id: panel.state.turnId,
        reject_request: rejectBody,
      },
    });
    if (startObligations.render) renderAgentPanel(panel);

    let rejected;
    try {
      const res = await vibecomfyFetch("/vibecomfy/agent-edit/reject", {
        method: "POST",
        headers: { "Content-Type": "application/json" },
        body: JSON.stringify(rejectBody),
      });
      const rawRejected = await res.json();
      rejected = normalizeAuxiliaryAgentPayload(rawRejected, "reject");
      if (!res.ok || rejected?.ok === false || rejected.raw?.error) {
        throw rejected.raw || { kind: "RejectError", message: res.statusText };
      }
    } catch (e) {
      const failure = e?.ok === false
        ? e
        : agentPanelFailure("RejectError", String(e), {
            retryable: true,
            graph_unchanged: true,
            next_action: "Retry Reject after the backend responds again.",
          });
      const obligations = transition(panel, "REJECT_FAILURE", {
        failure,
        syntheticAgentMessage: syntheticFailureAgentMessage(panel, failure, "frontend"),
        rejectBody,
        debugPayload: {
          ...failure,
          reject_request: rejectBody,
        },
      });
      const recovery = recoveryForPanelState(extractRebaselineRecovery(failure));
      transition(panel, "REBASELINE_RECOVERY_SYNC", { rebaselineRecovery: recovery });
      pushHistory(panel, "failure", failure.kind || "RejectError");
        pushTurnStatus(panel, "failed", {
          session_id: failure.session_id || panel.state.sessionId,
          turn_id: failure.turn_id || panel.state.turnId,
        baseline_turn_id: failure.baseline_turn_id || panel.state.baselineTurnId,
        failure_kind: failure.kind || "RejectError",
        failure_stage: failure.stage || "reject",
        message: failure.user_facing_message || failure.message || failure.error,
          audit_ref: failure.audit_ref,
          raw_payload: failure,
        });
        rememberTurnDetailSnapshot(panel, {
          turn_id: failure.turn_id || panel.state.turnId,
          session_id: failure.session_id || panel.state.sessionId,
          failure,
          message: failure.user_facing_message || failure.message || failure.error,
        });
        if (obligations.render) renderAgentPanel(panel);
      return;
    }

    pushHistory(panel, "rejected", panel.state.turnId ? `turn ${panel.state.turnId}` : "candidate");
    pushTurnStatus(panel, "rejected", {
      turn_id: panel.state.turnId,
      baseline_turn_id: rejected.baselineTurnId || panel.state.baselineTurnId,
      message: panel.state.turnId ? `turn ${panel.state.turnId}` : "candidate",
      audit_ref: rejected.auditRef || panel.state.auditRef,
      raw_payload: rejected.raw || rejected,
    });

    // ── T6: Production reject stays backend-authoritative. The POST above owns
    // Reject authority; the rebaseline-recovery sync below is wired by the
    // production orchestrator. commitLifecycleReset is reserved for local/demo
    // reset outcomes where no production POST is involved, so this call site
    // keeps the direct REJECT_SUCCESS transition (see plan Step 6 (3)).
    const obligations = transition(panel, "REJECT_SUCCESS", {
      rejected: rejected.raw || rejected,
      message: "Candidate rejected and cleared from the panel.",
      toast: "Agent candidate rejected",
      debugPayload: {
        rejected: rejected.raw || rejected,
        graph_unchanged: true,
      },
    });

    fulfillLifecycleTransitionObligations(panel, obligations);
    restoreLayoutPreviewBaseline(panel);

    const recovery = rejected.rebaselineRecovery || null;
    transition(panel, "REBASELINE_RECOVERY_SYNC", {
      ...(recovery ? { rebaselineRecovery: recovery } : { clearRebaselineRecovery: rejected.ok === true }),
    });

    rememberTurnDetailSnapshot(panel, {
      turn_id: rejected.turnId || panel.state.turnId,
      session_id: rejected.sessionId || panel.state.sessionId,
      auditRef: rejected.auditRef || panel.state.auditRef,
      debugPayload: {
        rejected: rejected.raw || rejected,
        graph_unchanged: true,
      },
      message: panel.state.message,
    });

    renderLifecycleTransition(panel, obligations);
  }

  async function postAgentRebaseline(
    panel,
    { reason, graphSnapshot = null, lastKnownBaselineGraphHash = undefined } = {},
  ) {
    if (!panel?.state) {
      return null;
    }
    if (panel.state.inFlightRebaseline) {
      return panel.state.inFlightRebaseline;
    }
    if (!panel.state.sessionId) {
      throw agentPanelFailure("MissingRequiredField", "Cannot rebaseline without a session_id.", {
        retryable: false,
        graph_unchanged: true,
        next_action: "Submit an agent edit first so the session exists.",
      });
    }

    const rebaselinePromise = (async () => {
      let body = null;
      let rebaselineReason = "continue_from_canvas";
      try {
        let snapshot = graphSnapshot;
        if (!snapshot) {
          snapshot = await buildCanvasSnapshot();
        }
        rebaselineReason = String(reason || "continue_from_canvas").trim() || "continue_from_canvas";
        const expectedBaselineGraphHash =
          lastKnownBaselineGraphHash !== undefined
            ? lastKnownBaselineGraphHash
            : (panel.state.baselineGraphHash || null);
        const idempotencyKey = buildRebaselineIdempotencyKey({
          sessionId: panel.state.sessionId,
          reason: rebaselineReason,
          baselineGraphHash: expectedBaselineGraphHash,
          structuralHash: snapshot.structuralHash,
        });
        const rebaselinePending = {
          reason: rebaselineReason,
          last_known_baseline_graph_hash: expectedBaselineGraphHash,
          client_graph_hash: snapshot.graphHash,
          client_structural_graph_hash: snapshot.structuralHash,
          idempotency_key: idempotencyKey,
        };
        const startedObligations = transition(panel, "REBASELINE_STARTED", {
          rebaselinePending,
        });
        renderLifecycleTransition(panel, startedObligations);

        body = {
          session_id: panel.state.sessionId,
          graph: snapshot.graph,
          reason: rebaselineReason,
          last_known_baseline_graph_hash: expectedBaselineGraphHash,
          client_graph_hash: snapshot.graphHash,
          client_structural_graph_hash: snapshot.structuralHash,
          idempotency_key: idempotencyKey,
        };

        const res = await vibecomfyFetch("/vibecomfy/agent-edit/rebaseline", {
          method: "POST",
          headers: { "Content-Type": "application/json" },
          body: JSON.stringify(body),
        });
        const rawRebaseline = await res.json();
        const result = normalizeAuxiliaryAgentPayload(rawRebaseline, "rebaseline");
        if (!res.ok || result?.ok === false || result.raw?.error) {
          throw result.raw || { kind: "RebaselineError", message: res.statusText };
        }
        const successObligations = transition(panel, "REBASELINE_SUCCESS", {
          result: result.raw || result,
          rebaselineRequest: body,
          debugPayload: {
            rebaseline_request: body,
            rebaseline_response: result.raw || result,
          },
        });
        fulfillLifecycleTransitionObligations(panel, successObligations);
        return result;
      } catch (e) {
        const failure = e?.ok === false
          ? e
          : agentPanelFailure("RebaselineError", String(e), {
              retryable: true,
              graph_unchanged: true,
              next_action: "Retry the rebaseline request after the backend responds again.",
            });
        const failureObligations = transition(panel, "REBASELINE_FAILURE", {
          failure,
          rebaselineRequest: body,
          rebaselineRecovery: recoveryForPanelState(extractRebaselineRecovery(failure)),
          rebaselinePendingPatch: {
            reason: rebaselineReason,
            retryable: Boolean(failure.retryable),
            failure_kind: failure.kind || null,
            failure_stage: failure.stage || null,
            message: failure.user_facing_message || failure.message || failure.error || null,
          },
          debugPayload: {
            ...failure,
            rebaseline_request: body,
          },
        });
        fulfillLifecycleTransitionObligations(panel, failureObligations);
        throw failure;
      } finally {
        const finallyObligations = transition(panel, "REBASELINE_FINALLY", {
          clearInFlightRebaseline: true,
        });
        renderLifecycleTransition(panel, finallyObligations);
      }
    })();

    transition(panel, "REBASELINE_IN_FLIGHT", { promise: rebaselinePromise });

    return rebaselinePromise;
  }

  async function rebaselineCurrentCanvas(panel) {
    const recovery = panel?.state?.rebaselineRecovery;
    if (!recovery) {
      renderAgentPanel(panel);
      return null;
    }
    if (panel.state.inFlightRebaseline) {
      return panel.state.inFlightRebaseline;
    }
    const retryTask = panel.state.lastSubmit?.task;
    const queuedObligations = transition(panel, "STALE_RECOVERY_REBASELINE_QUEUED");
    renderLifecycleTransition(panel, queuedObligations);
    try {
      const result = await postAgentRebaseline(panel, {
        reason: "stale_state_recovery",
        lastKnownBaselineGraphHash: recovery.last_known_baseline_graph_hash ?? null,
      });
      const successObligations = transition(panel, "STALE_RECOVERY_REBASELINE_SUCCESS", {
        auditRef: result.auditRef || panel.state.auditRef,
        message: "Current canvas rebaselined. Resubmitting from this canvas...",
        toast: "Current canvas rebaselined",
        debugPayload: {
          stale_state_recovery: true,
          rebaseline_response: result.raw || result,
        },
      });
      fulfillLifecycleTransitionObligations(panel, successObligations);
      renderLifecycleTransition(panel, successObligations);
      await submitAgentEdit(panel, { taskOverride: retryTask });
      return result;
    } catch (failure) {
      const failureObligations = transition(panel, "STALE_RECOVERY_REBASELINE_FAILURE", {
        rebaselineRecovery: recoveryForPanelState(extractRebaselineRecovery(failure)) || recovery,
        message: "Current canvas rebaseline failed. Review the evidence and retry.",
        debugPayload: {
          ...(panel.state.debugPayload || {}),
          stale_state_recovery: true,
        },
      });
      renderLifecycleTransition(panel, failureObligations);
      return null;
    }
  }

  async function undoLastApply(panel) {
    const undoStack = panel?.state?.undoStack;
    const previous = Array.isArray(undoStack) ? undoStack[undoStack.length - 1] : null;
    if (!isLegacyUndoCacheEntryV1(previous)) {
      renderAgentPanel(panel);
      return null;
    }
    if (panel.state.inFlightRebaseline) {
      return panel.state.inFlightRebaseline;
    }
    await restoreUndoGraph(previous.graph);
    const restoreObligations = transition(panel, "UNDO_LOCAL_RESTORE", {
      previous,
      undoStackDepth: panel.state.undoStack.length,
    });
    fulfillLifecycleTransitionObligations(panel, restoreObligations);
    renderLifecycleTransition(panel, restoreObligations);
    try {
      const result = await postAgentRebaseline(panel, {
        reason: "undo",
        lastKnownBaselineGraphHash:
          previous.accepted_baseline_graph_hash
          ?? panel.state.rebaselinePending?.last_known_baseline_graph_hash
          ?? panel.state.baselineGraphHash
          ?? null,
      });
      pushHistory(panel, "undo", previous.turn_id ? `restored pre-apply graph for turn ${previous.turn_id}` : "restored previous graph");
      pushTurnStatus(panel, "undone", {
        turn_id: previous.turn_id || null,
        baseline_turn_id: result.baselineTurnId || null,
        message: previous.turn_id ? `restored pre-apply graph for turn ${previous.turn_id}` : "restored previous graph",
        audit_ref: result.auditRef || panel.state.auditRef,
        raw_payload: result.raw || result,
      });
      const successObligations = transition(panel, "UNDO_REBASELINE_SUCCESS", {
        previous,
        result: result.raw || result,
        undoStackDepth: panel.state.undoStack.length - 1,
        toast: "Previous graph restored",
      });
      fulfillLifecycleTransitionObligations(panel, successObligations);
      renderLifecycleTransition(panel, successObligations);
      return result;
    } catch (failure) {
      const normalizedFailure = failure && typeof failure === "object"
        ? failure
        : agentPanelFailure("RebaselineError", String(failure), {
            retryable: true,
            graph_unchanged: true,
            next_action: "Retry Undo Rebaseline after the backend responds again.",
          });
      const failureObligations = transition(panel, "UNDO_REBASELINE_FAILURE", {
        previous,
        failure: normalizedFailure,
        syntheticAgentMessage: syntheticFailureAgentMessage(panel, normalizedFailure, "frontend"),
        rebaselineRecovery:
          recoveryForPanelState(extractRebaselineRecovery(normalizedFailure)) || panel.state.rebaselineRecovery,
        undoStackDepth: panel.state.undoStack.length,
      });
      renderLifecycleTransition(panel, failureObligations);
      return null;
    }
  }

  return {
    postAgentRebaseline,
    rebaselineCurrentCanvas,
    reconcilePreparedTransactionState,
    rejectAgentCandidate,
    rollbackPreparedAgentCandidate,
    undoLastApply,
  };
}
