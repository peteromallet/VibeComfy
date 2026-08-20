// ── Apply flow (T-058) ──────────────────────────────────────────────────────
// Apply orchestration extracted from vibecomfy_roundtrip.js. Lifecycle state
// and transaction recovery remain authoritative in roundtrip/lifecycle modules
// and are consumed only through this injected factory seam.

export function createApplyFlow(deps) {
  const {
    RENDER_SECTIONS,
    agentPanelFailure,
    announceChangedNodes,
    app,
    applyEligibility,
    applyGraphCandidateInPlace,
    applyGraphDeltaInPlace,
    applyGraphLayoutInPlace,
    assertApplyScopeConsistency,
    auditLandedMutationPlan,
    boundedBrowserTransactionError,
    buildActionIdempotencyKey,
    buildCanvasSnapshot,
    clearLayoutPreviewState,
    clonePlainData,
    commitFinalizeFailure,
    commitFinalizeStarted,
    commitFinalizeSuccess,
    commitPrepareFailure,
    commitPrepareStarted,
    commitPrepareSuccess,
    commitVerifyCanvasFailure,
    commitVerifyCanvasStarted,
    commitVerifyCanvasSuccess,
    compensatedFailurePayload,
    createIntentGraphAdapter,
    decorateIntentGraphPayload,
    decorateIntentNode,
    extractChangedNodeFeedback,
    findSerializedLinkByTarget,
    fulfillLifecycleTransitionObligations,
    inverseNodeUid,
    inverseSerializedLinks,
    isLayoutAuthorityTransaction,
    layoutPreviewBaselineSnapshot,
    markAgentPanelDirty,
    nodeTargetRefForRollback,
    normalizeCandidateTransaction,
    pendingTransactionSnapshotByPanel,
    postAgentLifecycleAction,
    projectionReferenceV1,
    pushHistory,
    pushTurnStatus,
    readGraphActualForOp,
    reconcilePreparedTransactionState,
    recordRoundtripResponseCompartments,
    recoveryForFailure,
    recoveryForPanelState,
    rememberTurnDetailSnapshot,
    renderLifecycleTransition,
    repairLiveIntentNodesFromCandidate,
    resolveActiveWorkflowUuid,
    resolveGraphNode,
    resolveGraphTarget,
    resolvePreparedMutationPlan,
    rollbackPreparedAgentCandidate,
    structuralProjectionV1,
    transactionAllows,
    transition,
    validateScopedCanvasPreconditions,
    verifyScopedCanvasResults,
    widgetReferenceNodeFor,
  } = deps;

  function normalizeForApply(candidateGraph) {
    decorateIntentGraphPayload(candidateGraph);
  }

  function applyGraphInPlaceWithIntentDecoration(candidate) {
    try {
      let repairCandidate = null;
      applyGraphCandidateInPlace(app, candidate, {
        beforeConfigure(nextCandidate) {
          decorateIntentGraphPayload(nextCandidate);
          repairCandidate = clonePlainData(nextCandidate);
        },
        afterConfigure(_graph, nextCandidate) {
          repairLiveIntentNodesFromCandidate(repairCandidate || nextCandidate);
        },
      });
    } catch (e) {
      if (e?.code !== "GRAPH_APPLY_UNAVAILABLE") {
        throw e;
      }
      throw agentPanelFailure("CanvasApplyError", "The live LiteGraph instance does not support in-place graph application.", {
        retryable: true,
        graph_unchanged: true,
        next_action: "Retry after the ComfyUI frontend finishes loading, or use the legacy round-trip command.",
      });
    }
  }

  function buildInverseDeltaOps(preApplyGraph, deltaOps, identityAuthority = null) {
    const inverseOps = [];
    const authority = identityAuthority || {
      uidForUpsertLinkOrigin(priorLink) {
        return inverseNodeUid(resolveGraphNode(preApplyGraph, priorLink.origin_id));
      },
      uidForUpsertLinkTarget(priorLink) {
        return inverseNodeUid(resolveGraphNode(preApplyGraph, priorLink.target_id));
      },
      uidForRemovedLinkOrigin(priorLink) {
        return inverseNodeUid(resolveGraphNode(preApplyGraph, priorLink.origin_id));
      },
      uidForRemovedLinkTarget(priorLink) {
        return inverseNodeUid(resolveGraphNode(preApplyGraph, priorLink.target_id));
      },
      uidForRemovedNode(priorNode) {
        return inverseNodeUid(priorNode);
      },
      relatedLinksFor() {
        return inverseSerializedLinks(preApplyGraph);
      },
      uidForRelatedLinkOrigin(link) {
        return inverseNodeUid(resolveGraphNode(preApplyGraph, link.origin_id));
      },
      uidForRelatedLinkTarget(link) {
        return inverseNodeUid(resolveGraphNode(preApplyGraph, link.target_id));
      },
    };
    // Compensate in reverse dependency order.  A forward add-node/add-node/link
    // sequence must remove its link before either endpoint; conversely the
    // inverse of remove-node recreates the node before its historic links.
    for (const op of [...deltaOps].reverse()) {
      if (!op || typeof op !== "object" || typeof op.op !== "string") {
        continue;
      }
      if (op.op === "set_node_field" || op.op === "set_mode" || op.op === "reorder") {
        inverseOps.push(clonePlainData(op));
        continue;
      }
      if (op.op === "upsert_link") {
        const priorLink = findSerializedLinkByTarget(preApplyGraph, op.to || op.target);
        if (!priorLink) {
          inverseOps.push({
            op: "remove_link",
            to: clonePlainData(op.to || op.target),
          });
          continue;
        }
        inverseOps.push({
          op: "upsert_link",
          from: ["nodes", authority.uidForUpsertLinkOrigin(priorLink) || String(priorLink.origin_id), Number(priorLink.origin_slot)],
          to: ["nodes", authority.uidForUpsertLinkTarget(priorLink) || String(priorLink.target_id), Number(priorLink.target_slot)],
        });
        continue;
      }
      if (op.op === "remove_link") {
        const priorLink = findSerializedLinkByTarget(preApplyGraph, op.to || op.target);
        if (!priorLink) {
          continue;
        }
        inverseOps.push({
          op: "upsert_link",
          from: ["nodes", authority.uidForRemovedLinkOrigin(priorLink) || String(priorLink.origin_id), Number(priorLink.origin_slot)],
          to: ["nodes", authority.uidForRemovedLinkTarget(priorLink) || String(priorLink.target_id), Number(priorLink.target_slot)],
        });
        continue;
      }
      if (op.op === "add_node") {
        inverseOps.push({
          op: "remove_node",
          target: nodeTargetRefForRollback(op),
        });
        continue;
      }
      if (op.op === "remove_node") {
        const targetRef = nodeTargetRefForRollback(op);
        const parsed = resolveGraphTarget(targetRef);
        const priorNode = resolveGraphNode(preApplyGraph, parsed.uidOrId);
        if (!priorNode) {
          continue;
        }
        inverseOps.push({
          op: "add_node",
          target: clonePlainData(targetRef),
          scope_path: authority.uidForRemovedNode(priorNode) || String(parsed.uidOrId),
        });
        const relatedLinks = authority.relatedLinksFor(priorNode)
          .filter((link) => String(link.origin_id) === String(priorNode.id) || String(link.target_id) === String(priorNode.id))
          .sort((left, right) => Number(left.id) - Number(right.id));
        for (const link of relatedLinks) {
          inverseOps.push({
            op: "upsert_link",
            from: ["nodes", authority.uidForRelatedLinkOrigin(link) || String(link.origin_id), Number(link.origin_slot)],
            to: ["nodes", authority.uidForRelatedLinkTarget(link) || String(link.target_id), Number(link.target_slot)],
          });
        }
      }
    }
    return inverseOps;
  }

  function normalizeCandidateApplyEligibility(candidateGraph, eligibility) {
    return applyEligibility(
      {
        state: {
          candidateGraph,
          applyEligibility: eligibility,
        },
      },
      null,
      { missingContractAsNull: true },
    );
  }

  async function applyAgentCandidate(panel, { resumePrepared = false } = {}) {
    // ── T8: Demo-only apply branch (local state only, no backend accept) ──
    // Delegates to preview_picker which handles graph application, lifecycle
    // reflection, and state cleanup inline.  No POST to /agent-edit/accept.
    if (panel?.state?.__demoMode) {
      if (!panel.state.candidateGraph) {
        transition(panel, "APPLY_PREFLIGHT_BLOCKED", { reason: "no_candidate" });
        return;
      }
      return panel.previewPicker?.handleDemoApply?.(panel);
    }

    if (!panel.state.candidateGraph) {
      transition(panel, "APPLY_PREFLIGHT_BLOCKED", { reason: "no_candidate" });
      return;
    }
    // Rehydration is the authority boundary after reload/restart. A candidate
    // retained by the live browser is only provisional until the server says it
    // remains reviewable, so never dispatch Apply during that window.
    if (panel.state.chatRehydratePending === true) {
      transition(panel, "APPLY_PREFLIGHT_BLOCKED", { reason: "rehydrating" });
      return;
    }
    if (!panel.state.sessionId || !panel.state.turnId) {
      const failure = agentPanelFailure("MissingRequiredField", "Cannot apply a candidate without session_id and turn_id.", {
        retryable: false,
        graph_unchanged: true,
        next_action: "Submit the edit again to get a complete candidate envelope.",
      });
      const obligations = transition(panel, "APPLY_MISSING_FIELDS", {
        failure,
        debugPayload: failure,
      });
      fulfillLifecycleTransitionObligations(panel, obligations);
      renderLifecycleTransition(panel, obligations);
      return;
    }
    if (panel.state.inFlightApply) {
      return panel.state.inFlightApply;
    }

    // ── T11: Scope consistency guard before apply ────────────────────────
    // Fails closed on any scope/session disagreement.  Unlike submit,
    // apply NEVER auto-switches scopes — a mismatch means the candidate
    // does not belong to the currently active workflow and must be refused.
    const applyScopeCheck = assertApplyScopeConsistency(panel, panel.state.sessionId);
    if (!applyScopeCheck.ok) {
      const failure = agentPanelFailure("ScopeMismatch", `Apply blocked: ${applyScopeCheck.reason || "scope/session inconsistency"}.`, {
        retryable: false,
        graph_unchanged: true,
        next_action: "Submit a new edit from the current canvas to generate a candidate for this workflow.",
        scope_mismatch_reason: applyScopeCheck.reason,
        scope_details: applyScopeCheck.details,
      });
      const obligations = transition(panel, "APPLY_SCOPE_MISMATCH", {
        failure,
        debugPayload: {
          ...failure,
          applyScopeCheck,
        },
      });
      fulfillLifecycleTransitionObligations(panel, obligations);
      renderLifecycleTransition(panel, obligations);
      return;
    }

    if (isV2ApplyCandidate(panel)) {
      const candidateTransaction = normalizeCandidateTransaction(panel.state.candidateTransaction);
      const resumingPreparedTransaction = Boolean(
        resumePrepared
        && candidateTransaction?.state === "prepared"
        && transactionAllows(candidateTransaction, "rollback"),
      );
      const v2DeltaOps = candidateTransaction
        ? clonePlainData(
          (Array.isArray(candidateTransaction.plan.accepted_batch)
            ? candidateTransaction.plan.accepted_batch
            : [])
            .filter((statement) => statement && typeof statement === "object" && statement.op && typeof statement.op === "object")
            .map((statement) => statement.op),
        )
        : null;
      const graphCapabilities = createIntentGraphAdapter(app).capabilities();
      const v2DeltaCapability = graphCapabilities.ok
        ? graphCapabilities.data.delta_apply
        : { available: false, strategy: null };
      const layoutTransaction = isLayoutAuthorityTransaction(candidateTransaction);
      const layoutCapability = graphCapabilities.ok
        ? graphCapabilities.data.layout_apply
        : { available: false, strategy: null };
      const missingTransactionFields = [];
      if (!candidateTransaction) missingTransactionFields.push("candidate_transaction");
      if (!transactionAllows(candidateTransaction, "apply") && !resumingPreparedTransaction) {
        missingTransactionFields.push("apply_authorization");
      }
      if (!v2DeltaOps) {
        missingTransactionFields.push("accepted_batch");
      }
      if (!layoutTransaction && (!v2DeltaCapability.available || v2DeltaCapability.strategy !== "live-litegraph-mutate")) {
        missingTransactionFields.push("scoped_delta_apply_capability");
      }
      if (layoutTransaction && (!layoutCapability.available || layoutCapability.strategy !== "live-layout-mutate")) {
        missingTransactionFields.push("scoped_layout_apply_capability");
      }
      if (missingTransactionFields.length) {
        const failure = agentPanelFailure(
          "MissingRequiredField",
          `Cannot apply this V2 candidate because transaction metadata is incomplete (missing ${missingTransactionFields.join(", ")}).`,
          {
            retryable: false,
            graph_unchanged: true,
            next_action: "Submit the edit again after the backend publishes complete transaction metadata.",
            agent_edit_protocol: panel.state.agentEditProtocol,
            missing_transaction_fields: missingTransactionFields,
            scoped_delta_apply_capability: clonePlainData(v2DeltaCapability),
            scoped_layout_apply_capability: clonePlainData(layoutCapability),
          },
        );
        const obligations = transition(panel, "APPLY_MISSING_FIELDS", {
          failure,
          debugPayload: failure,
        });
        fulfillLifecycleTransitionObligations(panel, obligations);
        renderLifecycleTransition(panel, obligations);
        return;
      }
      const applyPromise = (async () => {
        let beforeApply;
        try {
          beforeApply = await buildCanvasSnapshot();
        } catch (e) {
          const failure = agentPanelFailure("SerializeError", `Could not serialize the current canvas before Apply: ${String(e)}`, {
            retryable: true,
            graph_unchanged: true,
          });
          const obligations = transition(panel, "APPLY_SERIALIZE_ERROR", { failure, debugPayload: failure });
          fulfillLifecycleTransitionObligations(panel, obligations);
          renderLifecycleTransition(panel, obligations);
          return;
        }

        let typedPreconditionEvidence;
        try {
          const candidateAuthority = candidateTransaction.candidate_authority;
          typedPreconditionEvidence = projectionReferenceV1(
            beforeApply.graph,
            candidateAuthority.precondition.projection,
          );
          if (typedPreconditionEvidence.digest !== candidateAuthority.precondition.digest) {
            throw new Error("The live canvas does not match the typed v2 precondition witness.");
          }
          if (candidateAuthority.operation_family === "layout") {
            const structuralPrecondition = projectionReferenceV1(beforeApply.graph, structuralProjectionV1);
            if (structuralPrecondition.digest !== candidateAuthority.structural_witness?.precondition_digest) {
              throw new Error("The live canvas does not match the layout transaction's structural precondition witness.");
            }
          }
        } catch (error) {
          const failure = agentPanelFailure("StaleStateMismatch", String(error?.message || error), {
            retryable: true,
            graph_unchanged: true,
            next_action: "Submit a new edit from the current workflow baseline.",
          });
          const obligations = transition(panel, "APPLY_ELIGIBILITY_BLOCKED", {
            failure,
            debugPayload: { typed_v2_precondition_failure: failure },
            clearCandidatePreview: true,
          });
          fulfillLifecycleTransitionObligations(panel, obligations);
          renderLifecycleTransition(panel, obligations);
          return;
        }

        const eligibility = resumingPreparedTransaction
          ? { applyable: true, reason: "resume_prepared", message: "Resume the durably prepared transaction." }
          : applyEligibility(panel, beforeApply);
        if (!eligibility.applyable) {
          const failure = agentPanelFailure("StaleStateMismatch", eligibility.message || "Apply is blocked for this candidate.", {
            retryable: true,
            graph_unchanged: true,
            next_action: "Submit a new edit from the current canvas.",
            apply_eligibility: eligibility,
          });
          const obligations = transition(panel, "APPLY_ELIGIBILITY_BLOCKED", {
            failure,
            debugPayload: failure,
            clearCandidatePreview: true,
          });
          fulfillLifecycleTransitionObligations(panel, obligations);
          renderLifecycleTransition(panel, obligations);
          return;
        }

        const prepareBody = {
          session_id: panel.state.sessionId,
          turn_id: panel.state.turnId,
          plan_hash: candidateTransaction.plan_hash,
          candidate_graph_hash: candidateTransaction.hashes.candidate_graph_hash,
          client_graph_hash: beforeApply.graphHash,
          client_structural_graph_hash: beforeApply.structuralHash,
          precondition_projection: clonePlainData(typedPreconditionEvidence),
          client_live_canvas_token: beforeApply.liveCanvasToken,
          apply_eligibility: clonePlainData(panel.state.applyEligibility || eligibility),
          candidate: {
            graph_hash: candidateTransaction.hashes.candidate_graph_hash,
            plan_hash: candidateTransaction.plan_hash,
            structural_hash_before: candidateTransaction.hashes.submit_structural_graph_hash,
            structural_hash_after: candidateTransaction.hashes.candidate_structural_graph_hash,
          },
          idempotency_key: buildActionIdempotencyKey({
            action: "prepare",
            sessionId: panel.state.sessionId,
            turnId: panel.state.turnId,
            graphHash: beforeApply.graphHash,
          }),
        };

        let prepared;
        let preparedMutationPlan;
        if (resumingPreparedTransaction) {
          prepared = {
            receipt: clonePlainData(panel.state.preparedReceipt),
            candidateTransaction: clonePlainData(candidateTransaction),
            raw: {
              action: "resume_prepared",
              receipt: clonePlainData(panel.state.preparedReceipt),
              candidate_transaction: clonePlainData(candidateTransaction),
            },
          };
          preparedMutationPlan = resolvePreparedMutationPlan(candidateTransaction, candidateTransaction);
        } else try {
            const startedObligations = transition(panel, "APPLY_STARTED", {
              acceptBody: prepareBody,
              debugPayload: {
                applying_turn_id: panel.state.turnId,
                transactional_apply: true,
                prepare_request: prepareBody,
              },
            });
            fulfillLifecycleTransitionObligations(panel, startedObligations);
            const prepareStarted = commitPrepareStarted(panel, {
              mutationPlanHash: candidateTransaction.plan_hash,
              debugPayload: { prepare_request: prepareBody },
            });
            fulfillLifecycleTransitionObligations(panel, prepareStarted);
            renderLifecycleTransition(panel, prepareStarted);

            prepared = await postAgentLifecycleAction("prepare", prepareBody, "prepare");
            const obligations = commitPrepareSuccess(panel, {
              preparedReceipt: prepared.receipt || null,
              candidateTransaction: prepared.candidateTransaction,
              debugPayload: {
                prepare_request: prepareBody,
                prepare_response: prepared.raw || prepared,
              },
            });
            fulfillLifecycleTransitionObligations(panel, obligations);
            preparedMutationPlan = resolvePreparedMutationPlan(
              candidateTransaction,
              prepared.candidateTransaction,
            );
          } catch (error) {
          let transactionRollback = prepared
            ? await rollbackPreparedAgentCandidate(panel, beforeApply, {
                silent: true,
                triggerStage: "prepared_plan_resolution",
                triggerFailure: error,
                canvasWasMutated: false,
              })
            : null;
          let recoveryRequired = Boolean(prepared && transactionRollback?.ok !== true);
          if (!prepared) {
            try {
              await reconcilePreparedTransactionState(panel);
              const reconciled = normalizeCandidateTransaction(panel.state.candidateTransaction);
              if (["prepared", "canvas_verified"].includes(reconciled?.state)) {
                transactionRollback = await rollbackPreparedAgentCandidate(panel, beforeApply, {
                  silent: true,
                  triggerStage: "prepare_response_uncertain",
                  triggerFailure: error,
                  canvasWasMutated: false,
                });
                recoveryRequired = transactionRollback?.ok !== true;
              }
            } catch (_reconcileError) {
              // The prepare request may have committed before its response was
              // lost. Preserve recovery authority until reconciliation succeeds.
              recoveryRequired = true;
            }
          }
          const failure = error?.ok === false
            ? error
            : agentPanelFailure("PrepareError", String(error), {
                retryable: true,
                graph_unchanged: true,
                next_action: "Retry Apply after the backend can prepare the transaction.",
                transaction_rollback: transactionRollback,
              });
          const compensation = compensatedFailurePayload(panel, failure, {
            transactionRollback,
            actionBody: prepareBody,
            fallbackStage: "prepare",
            recoveryRequired,
            // A rejected prepare can still carry an authoritative stale-state
            // recovery instruction.  Keep it on the lifecycle transition so
            // the failure bubble offers the same rebaseline path as the other
            // stale-state boundaries.
            rebaselineRecovery:
              recoveryForPanelState(failure?.rebaselineRecovery || failure?.rebaseline_recovery)
              || recoveryForFailure(failure, panel, prepareBody),
          });
          const obligations = commitPrepareFailure(panel, {
            ...compensation,
            debugPayload: {
              prepare_request: prepareBody,
              prepare_failure: boundedBrowserTransactionError(error, "prepare_or_plan_resolution", {
                resumeState: "candidate_ready",
              }),
            },
          });
          fulfillLifecycleTransitionObligations(panel, obligations);
          renderLifecycleTransition(panel, obligations);
          return;
          }

        // A prepared V2 transaction may not overwrite a touched region that
        // changed while the server held the lease.  Compare only authoritative
        // operation targets against the pre-prepare canvas snapshot; this is a
        // scoped race check, not an inferred whole-graph delta.  Unlike the
        // legacy accept flow, an "already applied" target is still a race here:
        // the prepared transaction must either own the mutation or roll back.
        let localPrecheck = { ok: true, entries: [] };
        let undoEntry;
        try {
          if (preparedMutationPlan.verificationKind !== "layout_structural_noop") {
            const currentBeforeMutation = await buildCanvasSnapshot();
            const v2ScopedVerification = {
              entries: preparedMutationPlan.deltaOps.map((op) => ({
                target: clonePlainData(op.target ?? op.to ?? null),
                expected_old: readGraphActualForOp(beforeApply.graph, op, { widgetReferenceNodeFor }),
                desired_new: readGraphActualForOp(panel.state.candidateGraph, op, { widgetReferenceNodeFor }),
              })),
            };
            const validatedPrecheck = validateScopedCanvasPreconditions(
              currentBeforeMutation.graph,
              preparedMutationPlan.deltaOps,
              v2ScopedVerification,
              { widgetReferenceNodeFor },
            );
            // A prepared lease owns the mutation.  Even an "already applied"
            // target is a race at this point: publishing it as a successful
            // precheck would let the browser finalize work it did not perform.
            localPrecheck = {
              ...validatedPrecheck,
              ok: validatedPrecheck.entries.every((entry) => entry.status === "ok"),
            };
            if (!localPrecheck.entries.every((entry) => entry.status === "ok")) {
              const transactionRollback = await rollbackPreparedAgentCandidate(panel, beforeApply, {
                restoreCanvas: false,
                silent: true,
                triggerStage: "prepared_scoped_precheck",
                triggerFailure: localPrecheck,
                canvasWasMutated: false,
              });
              const failure = agentPanelFailure(
                "StaleStateMismatch",
                "The touched region changed after backend acceptance. Scoped Apply is blocked.",
                {
                  retryable: true,
                  graph_unchanged: true,
                  next_action: "Rebaseline and retry from the current canvas.",
                  transaction_rollback: transactionRollback,
                  canvas_apply: {
                    mode: "scoped_delta",
                    local_precheck: localPrecheck,
                    accept_live_canvas_token: beforeApply.liveCanvasToken,
                    current_live_canvas_token: currentBeforeMutation.liveCanvasToken,
                  },
                },
              );
              const obligations = commitVerifyCanvasFailure(panel, {
                ...compensatedFailurePayload(panel, failure, {
                  transactionRollback,
                  actionBody: prepareBody,
                  fallbackStage: "canvas_apply",
                }),
                debugPayload: {
                  transactional_apply: true,
                  prepare_response: prepared.raw || prepared,
                  canvas_apply_verification: {
                    local_precheck: localPrecheck,
                  },
                },
              });
              fulfillLifecycleTransitionObligations(panel, obligations);
              renderLifecycleTransition(panel, obligations);
              return;
            }
          }

          const undoSnapshot = layoutPreviewBaselineSnapshot(panel, beforeApply);
          undoEntry = {
            session_id: panel.state.sessionId,
            turn_id: panel.state.turnId,
            graph: clonePlainData(undoSnapshot.graph),
            client_graph_hash: undoSnapshot.graphHash,
            // Filled with the newly accepted baseline after finalize succeeds. The
            // pre-finalize baseline is not valid CAS authority for an immediate
            // Undo and was the reason Undo only recovered after rehydration.
            accepted_baseline_graph_hash: null,
            captured_at: new Date().toISOString(),
            chat_scope_id: panel.state.chatScopeId || null,
            chat_scope_fingerprint: panel.state.chatScopeFingerprint || null,
            canvas_structural_hash: undoSnapshot.structuralHash || null,
          };
          pendingTransactionSnapshotByPanel.set(panel, clonePlainData(undoSnapshot));
        } catch (error) {
          let transactionRollback = null;
          let rollbackError = null;
          try {
            transactionRollback = await rollbackPreparedAgentCandidate(panel, beforeApply, {
              restoreCanvas: false,
              silent: true,
              triggerStage: "post_prepare_pre_mutation",
              triggerFailure: error,
              canvasWasMutated: false,
            });
          } catch (caughtRollbackError) {
            rollbackError = caughtRollbackError;
          }
          const recoveryRequired = transactionRollback?.ok !== true;
          const failure = agentPanelFailure(
            "CanvasPreflightError",
            `Could not complete the prepared canvas preflight: ${String(error?.message || error)}`,
            {
              retryable: true,
              graph_unchanged: true,
              next_action: recoveryRequired
                ? "Cancel this interrupted Apply, then submit the edit again."
                : "Submit the edit again from the unchanged canvas.",
              transaction_rollback: transactionRollback,
            },
          );
          const obligations = commitVerifyCanvasFailure(panel, {
            ...compensatedFailurePayload(panel, failure, {
              transactionRollback,
              actionBody: prepareBody,
              fallbackStage: "post_prepare_pre_mutation",
              recoveryRequired,
            }),
            debugPayload: {
              transactional_apply: true,
              prepare_response: prepared.raw || prepared,
              pre_mutation_failure: boundedBrowserTransactionError(
                error,
                "post_prepare_pre_mutation",
                { resumeState: "prepared" },
              ),
              rollback_failure: rollbackError
                ? boundedBrowserTransactionError(rollbackError, "post_prepare_pre_mutation_rollback", {
                    resumeState: "prepared",
                  })
                : null,
            },
          });
          fulfillLifecycleTransitionObligations(panel, obligations);
          renderLifecycleTransition(panel, obligations);
          return;
        }

        let canvasApplyResult = null;
        try {
          // V2 authority is the persisted mutation intent, not a replacement
          // graph. Applying the canonical ops keeps unrelated live canvas state
          // intact and avoids graph.clear()/graph.configure() recursion in
          // complex ComfyUI graphs. There is deliberately no whole-graph
          // forward fallback: missing ops/capability fail before prepare above.
          if (preparedMutationPlan.verificationKind === "layout_structural_noop") {
            canvasApplyResult = applyGraphLayoutInPlace(app, {
              candidateGraph: panel.state.candidateGraph,
            });
          } else {
            canvasApplyResult = applyGraphDeltaInPlace(app, {
              deltaOps: preparedMutationPlan.deltaOps,
              candidateGraph: panel.state.candidateGraph,
            }, {
              runtimeDependencies: panel.state.runtimeDependencies,
              decorateCandidateNodePayload(nodePayload) {
                decorateIntentNode(nodePayload);
              },
              decorateLiveNode(liveNode) {
                decorateIntentNode(liveNode);
              },
            });
            auditLandedMutationPlan(preparedMutationPlan.deltaOps, canvasApplyResult.plan);
          }
        } catch (error) {
          const canvasMutationStarted = error?.canvasMutationStarted !== false;
          const transactionRollback = await rollbackPreparedAgentCandidate(panel, beforeApply, {
            restoreCanvas: canvasMutationStarted,
            silent: true,
            triggerStage: "canvas_apply",
            triggerFailure: error,
            canvasWasMutated: canvasMutationStarted,
          });
          const failure = agentPanelFailure("CanvasApplyError", String(error), {
            retryable: true,
            graph_unchanged: transactionRollback.canvas_restore?.restored === true,
            next_action: "Retry Apply or Rebaseline from the current canvas.",
            transaction_rollback: transactionRollback,
            canvas_apply: {
              mode: "scoped_delta",
              delta_hash: preparedMutationPlan.deltaHash,
              op_count: preparedMutationPlan.deltaOps.length,
              capability: clonePlainData(canvasApplyResult?.capability || v2DeltaCapability),
            },
          });
          const obligations = transition(panel, "CANVAS_APPLY_FAILURE", {
            ...compensatedFailurePayload(panel, failure, {
              transactionRollback,
              actionBody: prepareBody,
              fallbackStage: "canvas_apply",
            }),
            debugPayload: {
              transactional_apply: true,
              prepare_response: prepared.raw || prepared,
              canvas_apply_failure: boundedBrowserTransactionError(error, "canonical_canvas_apply", {
                resumeState: "prepared",
              }),
              canvas_apply: failure.canvas_apply,
            },
          });
          fulfillLifecycleTransitionObligations(panel, obligations);
          renderLifecycleTransition(panel, obligations);
          return;
        }

        // ── T26: Post-apply serialize/hash (try/catch with rollback) ──────
        // After local mutation, serialize the live canvas and hash it.  If
        // serialization fails the canvas is already mutated, so roll back
        // the prepared transaction and report a verification failure.
        let afterApply;
        try {
          afterApply = await buildCanvasSnapshot();
        } catch (serializeErr) {
          const transactionRollback = await rollbackPreparedAgentCandidate(panel, beforeApply, {
            restoreCanvas: true,
            silent: true,
            triggerStage: "post_apply_serialize",
            triggerFailure: serializeErr,
            canvasWasMutated: true,
          });
          const failure = agentPanelFailure(
            "SerializeError",
            `Could not serialize the canvas after Apply: ${String(serializeErr)}`,
            {
              retryable: true,
              graph_unchanged: transactionRollback.canvas_restore?.restored === true,
              next_action: "Retry Apply or Rebaseline from the current canvas.",
              transaction_rollback: transactionRollback,
            },
          );
          const serializeObligations = commitVerifyCanvasFailure(panel, {
            ...compensatedFailurePayload(panel, failure, {
              transactionRollback,
              actionBody: prepareBody,
              fallbackStage: "post_apply_serialize",
            }),
            debugPayload: {
              transactional_apply: true,
              prepare_response: prepared.raw || prepared,
              post_apply_serialize_failure: failure,
            },
          });
          fulfillLifecycleTransitionObligations(panel, serializeObligations);
          renderLifecycleTransition(panel, serializeObligations);
          return;
        }
        const localPostcheck = preparedMutationPlan.verificationKind === "layout_structural_noop"
          ? { ok: true, entries: [] }
          : verifyScopedCanvasResults(afterApply.graph, preparedMutationPlan.deltaOps, {
              entries: preparedMutationPlan.deltaOps.map((op) => ({
                target: clonePlainData(op.target ?? op.to ?? null),
                desired_new: readGraphActualForOp(panel.state.candidateGraph, op, { widgetReferenceNodeFor }),
              })),
            }, { widgetReferenceNodeFor });
        if (!localPostcheck.ok) {
          const transactionRollback = await rollbackPreparedAgentCandidate(panel, beforeApply, {
            restoreCanvas: true,
            silent: true,
            triggerStage: "post_apply_scoped_postcheck",
            triggerFailure: localPostcheck,
            canvasWasMutated: true,
          });
          const failure = agentPanelFailure(
            "StaleStateMismatch",
            "The applied canvas does not match the authoritative touched-region result.",
            {
              retryable: true,
              graph_unchanged: transactionRollback.canvas_restore?.restored === true,
              next_action: "Retry Apply or Rebaseline from the current canvas.",
              transaction_rollback: transactionRollback,
              canvas_apply: { mode: "scoped_delta", local_precheck: localPrecheck, local_postcheck: localPostcheck },
            },
          );
          const obligations = commitVerifyCanvasFailure(panel, {
            ...compensatedFailurePayload(panel, failure, {
              transactionRollback,
              actionBody: prepareBody,
              fallbackStage: "post_apply_scoped_postcheck",
            }),
            debugPayload: {
              transactional_apply: true,
              prepare_response: prepared.raw || prepared,
              canvas_apply_verification: { local_precheck: localPrecheck, local_postcheck: localPostcheck },
            },
          });
          fulfillLifecycleTransitionObligations(panel, obligations);
          renderLifecycleTransition(panel, obligations);
          return;
        }
        const verifyStarted = commitVerifyCanvasStarted(panel, {
          debugPayload: {
            expected_plan_hash: panel.state.mutationPlanHash,
            post_apply_hash: afterApply.structuralHash,
            post_apply_graph_hash: afterApply.graphHash,
            canvas_apply: {
              mode: "scoped_delta",
              delta_hash: preparedMutationPlan.deltaHash,
              op_count: preparedMutationPlan.deltaOps.length,
              capability: clonePlainData(canvasApplyResult?.capability || v2DeltaCapability),
              landed_step_count: Array.isArray(canvasApplyResult?.plan) ? canvasApplyResult.plan.length : null,
            },
          },
        });
        fulfillLifecycleTransitionObligations(panel, verifyStarted);

        const preparedAggregate = normalizeCandidateTransaction(prepared.candidateTransaction);
        const preparedAuthority = preparedAggregate?.prepared_authority;
        let typedPostconditionEvidence;
        try {
          if (!preparedAuthority) throw new Error("Prepare did not return explicit prepared_authority_v1.");
          typedPostconditionEvidence = projectionReferenceV1(
            afterApply.graph,
            preparedAuthority.postcondition.projection,
          );
          if (typedPostconditionEvidence.digest !== preparedAuthority.postcondition.digest) {
            throw new Error("The applied canvas does not match the typed v2 postcondition witness.");
          }
          if (preparedAuthority.operation_family === "layout") {
            const structuralPostcondition = projectionReferenceV1(afterApply.graph, structuralProjectionV1);
            if (structuralPostcondition.digest !== preparedAuthority.structural_witness?.postcondition_digest) {
              throw new Error("Layout Apply changed the structural projection.");
            }
          }
        } catch (error) {
          const transactionRollback = await rollbackPreparedAgentCandidate(panel, beforeApply, {
            restoreCanvas: true,
            silent: true,
            triggerStage: "typed_postcondition_verification",
            triggerFailure: error,
            canvasWasMutated: true,
          });
          const failure = agentPanelFailure("StaleStateMismatch", String(error?.message || error), {
            retryable: true,
            graph_unchanged: transactionRollback.canvas_restore?.restored === true,
            next_action: "Retry Apply or rebaseline from the restored workflow.",
            transaction_rollback: transactionRollback,
          });
          const obligations = commitVerifyCanvasFailure(panel, {
            ...compensatedFailurePayload(panel, failure, {
              transactionRollback,
              actionBody: prepareBody,
              fallbackStage: "typed_postcondition_verification",
            }),
            debugPayload: {
              typed_v2_postcondition_failure: failure,
              typed_v2_precondition: typedPreconditionEvidence,
            },
          });
          fulfillLifecycleTransitionObligations(panel, obligations);
          renderLifecycleTransition(panel, obligations);
          return;
        }

        // Whole-graph equality is meaningful only for an authority mode that
        // explicitly requires it.  delta_replay deliberately authorizes a
        // scoped mutation: unrelated live state and deterministic browser node
        // decoration must not make a successfully pre/post-checked delta fail.
        const expectedStructuralHashAfter = candidateTransaction.hashes.candidate_structural_graph_hash;
        if (
          preparedMutationPlan.verificationKind === "structural_graph_equality"
          &&
          typeof afterApply.structuralHash === "string"
          && afterApply.structuralHash
          && typeof expectedStructuralHashAfter === "string"
          && expectedStructuralHashAfter
          && afterApply.structuralHash !== expectedStructuralHashAfter
        ) {
          const transactionRollback = await rollbackPreparedAgentCandidate(panel, beforeApply, {
            restoreCanvas: true,
            silent: true,
            triggerStage: "post_apply_verification",
            triggerFailure: {
              kind: "StaleStateMismatch",
              message: "Post-apply canvas structural hash does not match the candidate structural hash.",
            },
            canvasWasMutated: true,
          });
          const failure = agentPanelFailure(
            "StaleStateMismatch",
            "Post-apply canvas structural hash does not match the candidate structural hash.",
            {
              retryable: true,
              graph_unchanged: transactionRollback.canvas_restore?.restored === true,
              next_action: "Retry Apply or Rebaseline from the current canvas.",
              expected_structural_hash: expectedStructuralHashAfter,
              actual_structural_hash: afterApply.structuralHash,
              transaction_rollback: transactionRollback,
            },
          );
          const hashObligations = commitVerifyCanvasFailure(panel, {
            ...compensatedFailurePayload(panel, failure, {
              transactionRollback,
              actionBody: prepareBody,
              fallbackStage: "post_apply_verification",
            }),
            debugPayload: {
              transactional_apply: true,
              prepare_response: prepared.raw || prepared,
              post_apply_hash_mismatch: true,
              expected_structural_hash: expectedStructuralHashAfter,
              actual_structural_hash: afterApply.structuralHash,
              post_apply_graph_hash: afterApply.graphHash,
            },
          });
          fulfillLifecycleTransitionObligations(panel, hashObligations);
          renderLifecycleTransition(panel, hashObligations);
          return;
        }
        const layoutVerification = preparedMutationPlan.layoutVerification;
        const expectedLayoutGraphHash = layoutVerification?.candidate_layout_graph_hash || null;
        const legacyExpectedGraphHash = candidateTransaction.hashes.candidate_graph_hash;
        const layoutMismatch = preparedMutationPlan.verificationKind === "layout_structural_noop"
          && (
            layoutVerification
              ? afterApply.layoutHash !== expectedLayoutGraphHash
              : afterApply.graphHash !== legacyExpectedGraphHash
          );
        if (layoutMismatch) {
          const transactionRollback = await rollbackPreparedAgentCandidate(panel, beforeApply, {
            restoreCanvas: true,
            silent: true,
            triggerStage: "post_apply_layout_verification",
            triggerFailure: {
              kind: "StaleStateMismatch",
              message: layoutVerification
                ? "Applied layout geometry does not match the authoritative candidate."
                : "Applied legacy layout graph does not exactly match the authoritative candidate.",
            },
            canvasWasMutated: true,
          });
          const failure = agentPanelFailure(
            "StaleStateMismatch",
            layoutVerification
              ? "Applied layout geometry does not match the authoritative candidate."
              : "Applied legacy layout graph does not exactly match the authoritative candidate.",
            {
              retryable: true,
              graph_unchanged: transactionRollback.canvas_restore?.restored === true,
              expected_layout_hash: expectedLayoutGraphHash,
              actual_layout_hash: afterApply.layoutHash,
              expected_graph_hash: layoutVerification ? null : legacyExpectedGraphHash,
              actual_graph_hash: afterApply.graphHash,
              transaction_rollback: transactionRollback,
            },
          );
          const obligations = commitVerifyCanvasFailure(panel, {
            ...compensatedFailurePayload(panel, failure, {
              transactionRollback,
              actionBody: prepareBody,
              fallbackStage: "post_apply_layout_verification",
            }),
            debugPayload: {
              transactional_apply: true,
              verification_kind: "layout_structural_noop",
              expected_layout_hash: expectedLayoutGraphHash,
              actual_layout_hash: afterApply.layoutHash,
              layout_verification: layoutVerification,
              expected_graph_hash: layoutVerification ? null : legacyExpectedGraphHash,
              actual_graph_hash: afterApply.graphHash,
            },
          });
          fulfillLifecycleTransitionObligations(panel, obligations);
          renderLifecycleTransition(panel, obligations);
          return;
        }

        const verifyReceipt = {
          plan_hash: panel.state.mutationPlanHash,
          generation: panel.state.generation,
          lease_nonce: panel.state.leaseNonce,
          post_apply_hash: afterApply.structuralHash,
        };
        const verifySuccess = commitVerifyCanvasSuccess(panel, {
          verifiedReceipt: verifyReceipt,
          debugPayload: {
            verify_canvas: verifyReceipt,
            prepare_response: prepared.raw || prepared,
          },
        });
        fulfillLifecycleTransitionObligations(panel, verifySuccess);

        const finalizeBody = {
          session_id: panel.state.sessionId,
          turn_id: panel.state.turnId,
          plan_hash: panel.state.mutationPlanHash,
          generation: panel.state.generation,
          lease_nonce: panel.state.leaseNonce,
          post_apply_hash: afterApply.structuralHash,
          post_apply_graph: afterApply.graph,
          postcondition_projection: clonePlainData(typedPostconditionEvidence),
          applied_delta_hash: preparedMutationPlan.deltaHash,
          post_apply_hash_verified: true,
          browser_verified: true,
          verified: true,
          client_graph_hash: afterApply.graphHash,
          client_structural_graph_hash: afterApply.structuralHash,
          idempotency_key: buildActionIdempotencyKey({
            action: "finalize",
            sessionId: panel.state.sessionId,
            turnId: panel.state.turnId,
            graphHash: afterApply.graphHash,
          }),
        };
        const finalizeStarted = commitFinalizeStarted(panel, {
          debugPayload: {
            finalize_request: {
              session_id: finalizeBody.session_id,
              turn_id: finalizeBody.turn_id,
              plan_hash: finalizeBody.plan_hash,
              applied_delta_hash: finalizeBody.applied_delta_hash,
              post_apply_hash: finalizeBody.post_apply_hash,
              post_apply_graph_node_count: Array.isArray(afterApply.graph?.nodes) ? afterApply.graph.nodes.length : null,
            },
          },
        });
        fulfillLifecycleTransitionObligations(panel, finalizeStarted);

        let finalized = null;
        try {
          finalized = await postAgentLifecycleAction("finalize", finalizeBody, "finalize");
          undoEntry.accepted_baseline_graph_hash = finalized.baselineGraphHash
            || afterApply.structuralHash
            || null;
          undoEntry.accepted_baseline_turn_id = finalized.baselineTurnId
            || panel.state.turnId
            || null;
          // journal_durable_v1 on the finalized server record is the sole v2
          // Undo authority. The browser undoStack remains a legacy,
          // non-authoritative cache and must never receive a v2 transaction.
          pendingTransactionSnapshotByPanel.delete(panel);
          recordRoundtripResponseCompartments(panel, finalized);
          markAgentPanelDirty(panel, [RENDER_SECTIONS.META]);
          const lastAppliedChanges = announceChangedNodes(panel, extractChangedNodeFeedback(panel.state.candidateReport));
          pushHistory(panel, "applied", panel.state.turnId ? `turn ${panel.state.turnId}` : "candidate");
          pushTurnStatus(panel, "applied", {
            turn_id: panel.state.turnId,
            baseline_turn_id: finalized.baselineTurnId || panel.state.turnId,
            message: panel.state.turnId ? `turn ${panel.state.turnId}` : "candidate",
            audit_ref: finalized.auditRef || panel.state.auditRef,
            raw_payload: finalized.raw || finalized,
          });
          const obligations = commitFinalizeSuccess(panel, {
            finalizedReceipt: finalized.receipt || null,
            candidateTransaction: finalized.candidateTransaction,
            accepted: finalized.raw || finalized,
            lastAppliedChanges,
            undoStackDepth: panel.state.undoStack.length,
            toast: "Agent candidate applied",
            debugPayload: {
              prepare_response: prepared.raw || prepared,
              canvas_apply_verification: {
                local_precheck: localPrecheck,
                local_postcheck: localPostcheck,
              },
              finalize_request: {
                plan_hash: finalizeBody.plan_hash,
                applied_delta_hash: finalizeBody.applied_delta_hash,
                post_apply_hash: finalizeBody.post_apply_hash,
              },
              finalize_response: finalized.raw || finalized,
            },
          });
          fulfillLifecycleTransitionObligations(panel, obligations);
          clearLayoutPreviewState(panel);
          rememberTurnDetailSnapshot(panel, {
            turn_id: panel.state.turnId,
            session_id: panel.state.sessionId,
            auditRef: finalized.auditRef || panel.state.auditRef,
            debugPayload: obligations.debugPayload || panel.state.debugPayload,
            lastAppliedChanges,
            message: panel.state.message,
          });
          renderLifecycleTransition(panel, obligations);
        } catch (error) {
          if (finalized) {
            // The server has already committed the terminal aggregate. From
            // this point onward presentation/history failures are never
            // compensatable: restoring the canvas would diverge from the
            // authoritative finalized baseline and rollback must be rejected.
            const projectionFailure = boundedBrowserTransactionError(
              error,
              "post_finalize_projection",
              { recoverable: true, resumeState: "finalized" },
            );
            try {
              const terminalObligations = commitFinalizeSuccess(panel, {
                finalizedReceipt: finalized.receipt || null,
                candidateTransaction: finalized.candidateTransaction,
                accepted: finalized.raw || finalized,
                toast: "Agent candidate applied",
                debugPayload: {
                  finalize_response: finalized.raw || finalized,
                  post_finalize_projection_failure: projectionFailure,
                },
              });
              fulfillLifecycleTransitionObligations(panel, terminalObligations);
              renderLifecycleTransition(panel, terminalObligations);
            } catch (renderError) {
              console.error(
                "[vibecomfy] finalized transaction projection failed",
                boundedBrowserTransactionError(renderError, "post_finalize_render", {
                  recoverable: true,
                  resumeState: "finalized",
                }),
              );
            }
            return;
          }
          const failure = error?.ok === false
            ? error
            : agentPanelFailure("FinalizeError", String(error), {
                retryable: true,
                graph_unchanged: false,
                next_action: "Reload to recover the prepared transaction, then finalize or rollback.",
              });
          // ── T26: Finalize failure boundary — compensate atomically ────
          // Restore and verify the pre-apply canvas before cancelling the
          // prepared server transaction. Preserve the finalize failure as the
          // single user-visible outcome; rollback is supporting evidence only.
          const transactionRollback = await rollbackPreparedAgentCandidate(panel, beforeApply, {
            restoreCanvas: true,
            silent: true,
            triggerStage: "finalize",
            triggerFailure: failure,
            canvasWasMutated: true,
          });
          if (failure && typeof failure === "object") {
            failure.graph_unchanged = transactionRollback.canvas_restore?.restored === true;
            failure.transaction_rollback = transactionRollback;
          }
          const obligations = commitFinalizeFailure(panel, {
            ...compensatedFailurePayload(panel, failure, {
              transactionRollback,
              actionBody: finalizeBody,
              fallbackStage: "finalize",
            }),
            debugPayload: {
              transactional_apply: true,
              finalize_boundary_rollback: true,
              transaction_rollback: transactionRollback,
              prepare_response: prepared.raw || prepared,
              finalize_request: {
                plan_hash: finalizeBody.plan_hash,
                applied_delta_hash: finalizeBody.applied_delta_hash,
                post_apply_hash: finalizeBody.post_apply_hash,
              },
              finalize_failure: boundedBrowserTransactionError(error, "finalize", {
                resumeState: "canvas_verified",
              }),
            },
          });
          fulfillLifecycleTransitionObligations(panel, obligations);
          renderLifecycleTransition(panel, obligations);
        }
      })();

      transition(panel, "APPLY_IN_FLIGHT", { promise: applyPromise });
      try {
        return await panel.state.inFlightApply;
      } finally {
        transition(panel, "APPLY_FINALLY", { clearInFlightApply: true });
      }
    }

    // Explicit migration adapter: a legacy candidate may be inspected or
    // rejected, but it cannot enter the production forward-mutation path.
    // Removal criterion: no supported session can rehydrate without a
    // candidate_transaction_v1 aggregate.
    const legacyFailure = agentPanelFailure(
      "LegacyCandidateReadOnly",
      "This candidate predates the canonical transaction contract and cannot be applied safely.",
      {
        retryable: false,
        graph_unchanged: true,
        next_action: "Reject it or submit the edit again to create a canonical transaction.",
      },
    );
    const legacyObligations = transition(panel, "APPLY_MISSING_FIELDS", {
      failure: legacyFailure,
      debugPayload: {
        migration_adapter: "legacy_candidate_read_only",
        removal_criteria: "no supported session lacks candidate_transaction_v1",
      },
    });
    fulfillLifecycleTransitionObligations(panel, legacyObligations);
    renderLifecycleTransition(panel, legacyObligations);
    return;
  }

  function isV2ApplyCandidate(panel) {
    const transaction = normalizeCandidateTransaction(panel?.state?.candidateTransaction);
    const activeWorkflowId = resolveActiveWorkflowUuid();
    return Boolean(
      panel?.state?.candidateGraph
      && panel.state.agentEditProtocol === "v2_delta"
      && transaction
      && activeWorkflowId
      && transaction.candidate_authority?.workflow_id === activeWorkflowId,
    );
  }

  return {
    normalizeForApply,
    applyGraphInPlaceWithIntentDecoration,
    buildInverseDeltaOps,
    normalizeCandidateApplyEligibility,
    applyAgentCandidate,
    isV2ApplyCandidate,
  };
}
