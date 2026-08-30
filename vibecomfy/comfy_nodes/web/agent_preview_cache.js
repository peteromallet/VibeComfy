import { preflightDeltaPlan } from "./comfy_adapter.js";
import {
  computeSerializedGraphPreviewDiff,
  constrainPreviewDiffToLegacyIntent,
  previewFailure,
} from "./preview_diff_core.js";
import {
  crossGraphNodeIdentityIndexV1,
  stablePreviewLinkMapV1,
} from "./projection_registry_v1.js";

// Candidate preview caching and layout-preview cache identity live on panel.state.
// Roundtrip injects its app/canvas and serialization helpers once at module init.
export function createAgentPreviewCache(deps) {
  const {
    app,
    canonicalJsonString,
    captureLiveCanvasRevision,
    compactNetFieldChanges: _compactNetFieldChanges,
    computePreviewDiffFacade,
    createIntentGraphAdapter,
    currentAgentPanel,
    getLiveGraph,
    getLiveGraphNodes,
    getUid,
    prepareCandidateGraphForPanel,
    readWidgetValues,
    safePreviewLogDetail,
  } = deps;

  function isReorganiseReport(report) {
    return Boolean(
      report
      && typeof report === "object"
      && (report.kind === "reorganise" || report.route === "reorganise" || report.reorganise),
    );
  }

  function previewDiffInputSignature(panel, candidateReport, deltaOps) {
    const fieldChanges = panel?.state?.lastSubmitFieldChanges;
    const legacyOperations = (Array.isArray(panel?.state?.changeDetails?.batch_turns)
      ? panel.state.changeDetails.batch_turns
      : []).flatMap((turn) => (
      Array.isArray(turn?.statements) ? turn.statements : []
    )).filter((statement) => statement?.landed === true).map((statement) => ({
      op_kind: statement.op_kind || null,
      touched_uids: Array.isArray(statement.touched_uids) ? statement.touched_uids : [],
    }));
    return canonicalJsonString({
      version: 3,
      sessionId: panel?.state?.sessionId || null,
      turnId: panel?.state?.turnId || null,
      candidateGraphHash: panel?.state?.candidateGraphHash || null,
      liveCanvasRevision: captureLiveCanvasRevision(),
      deltaOps: Array.isArray(deltaOps) ? deltaOps : [],
      fieldChanges: fieldChanges && typeof fieldChanges === "object" ? fieldChanges : null,
      legacyOperations,
      report: {
        contentEdits: candidateReport?.change?.content_edits || null,
        reorganise: isReorganiseReport(candidateReport),
      },
    });
  }

  function computePreviewDiff(candidateGraph, candidateReport, deltaOps = null, accessors = {}) {
    try {
      const {
        readLiveGraphLinks,
        readPreviewNodeUid,
        widgetIndexFromFieldPath,
      } = accessors;
      const panel = currentAgentPanel();
      const candidateGraphHash = panel?.state?.candidateGraphHash;
      const liveCanvasRevision = captureLiveCanvasRevision();
      // Include delta ops presence in the cache key so we don't serve a
      // graph-diff-derived cache when delta ops are now available (or vice versa).
      const deltaOpsCacheTag = Array.isArray(deltaOps) && deltaOps.length > 0 ? `delta:${deltaOps.length}` : "graph";
      const inputSignature = previewDiffInputSignature(panel, candidateReport, deltaOps);
      if (
        candidateGraphHash
        && panel.state._previewDiffGraphHash === candidateGraphHash
        && panel.state._previewDiffCacheTag === deltaOpsCacheTag
        && panel.state._previewDiffLiveCanvasRevision === liveCanvasRevision
        && panel.state._previewDiffInputSignature === inputSignature
        && panel.state._previewDiff
        && Array.isArray(panel.state._previewDiff.added_links)
        && Array.isArray(panel.state._previewDiff.removed_links)
        && Array.isArray(panel.state._previewDiff.edited_fields)
        && Array.isArray(panel.state._previewDiff.layout_moved)
        && Array.isArray(panel.state._previewDiff.layout_groups)
      ) {
        return panel.state._previewDiff;
      }

      // ── Primary path: derive highlights from normalized delta ops ──────────
      // When canonical deltaOps are available, use preflightDeltaPlan to produce
      // a plan that mirrors the apply path, then convert plan entries to the
      // diff structure consumed by the preview overlay.  This ensures preview
      // and apply are driven by the same normalized mutation planning surface.
      const useDeltaOps = Array.isArray(deltaOps) && deltaOps.length > 0;

      const previewCandidateGraph = prepareCandidateGraphForPanel(candidateGraph);
      const liveGraph = getLiveGraph();
      const liveNodes = getLiveGraphNodes(liveGraph);
      // Compare workflow state to workflow state. Runtime LiteGraph nodes may
      // contain DOM, upload, preview, and other controls marked serialize:false;
      // those controls are canvas UI, not persisted workflow widgets. The
      // candidate is serialized UI JSON, so the live side must use the same
      // representation boundary or unchanged nodes acquire phantom edits.
      const liveCapture = createIntentGraphAdapter(app).capture();
      const liveSerializedGraph = liveCapture.ok ? liveCapture.data.graph : null;
      if (!liveCapture.ok) {
        console.warn(
          "[vibecomfy] computePreviewDiff — live graph serialization failed; using runtime widgets:",
          liveCapture.diagnostic,
        );
      }
      const livePreviewGraph = liveSerializedGraph || {
        nodes: liveNodes,
        links: readLiveGraphLinks(liveGraph),
      };
      const layoutBaselineGraph = isReorganiseReport(candidateReport)
        ? panel?.state?._layoutPreviewBaseline?.graph
        : null;
      const ownedGraphDiff = computeSerializedGraphPreviewDiff({
        liveGraph: livePreviewGraph,
        candidateGraph: previewCandidateGraph,
        layoutBaselineGraph,
      });
      const identityIndex = crossGraphNodeIdentityIndexV1(livePreviewGraph, previewCandidateGraph);
      const runtimeIdentityIndex = crossGraphNodeIdentityIndexV1(
        { nodes: liveNodes, links: [] },
        previewCandidateGraph,
      );
      const serializedIdentityIndex = crossGraphNodeIdentityIndexV1(
        liveSerializedGraph || { nodes: [] },
        previewCandidateGraph,
      );
      const { candidateByUid, liveByUid } = identityIndex;
      const liveSerializedByUid = serializedIdentityIndex.liveByUid;

      // ── Delta-ops-derived diff entries (built before the graph-diff fallback) ──
      let deltaDerivedEdited = null;
      let deltaDerivedAdded = null;
      let deltaDerivedRemoved = null;

      if (useDeltaOps) {
        try {
          const liveSnapshot = liveSerializedGraph
            ? liveSerializedGraph
            : { nodes: [], links: [] };

          // Run the same planning surface used by applyGraphDeltaInPlace.
          // Preview and Apply must resolve semantic fields through the same
          // native widget carrier map. Serialized ComfyUI graphs omit the live
          // `widgets` array, and some nodes serialize auxiliary widgets that do
          // not appear in `inputs` (KSampler's control_after_generate is the
          // canonical example). Calling preflight without the native reference
          // makes a valid canonical delta look ambiguous here even though Apply
          // can resolve it, forcing the preview onto a lossy legacy fallback.
          const { plan } = preflightDeltaPlan(liveSnapshot, previewCandidateGraph, deltaOps, {
            widgetReferenceNodeFor(uidOrId) {
              const key = String(uidOrId);
              return runtimeIdentityIndex.liveByUid.get(key)
                || liveNodes.find((node) => (
                  String(getUid(node) || "") === key
                  || String(node?.id ?? "") === key
                ))
                || null;
            },
          });

          // Convert plan entries to diff items.
          const planEditedMap = new Map();   // uidOrId -> Set<widgetIndex>
          const planAdded = [];
          const planRemoved = [];

          // Resolve uid-or-id to uid.
          const resolveUid = (uidOrId) => {
            const key = String(uidOrId);
            if (candidateByUid.has(key) || liveByUid.has(key)) return key;
            return identityIndex.candidateUidByNativeId.get(key) || key;
          };

          for (const step of plan) {
            if (step.op === "set_node_field") {
              const uid = resolveUid(step.uidOrId);
              const widgetIdx = widgetIndexFromFieldPath(step.fieldPath);
              let entry = planEditedMap.get(uid);
              if (!entry) {
                entry = { uid, changedWidgetIndices: [] };
                planEditedMap.set(uid, entry);
              }
              if (widgetIdx != null && !entry.changedWidgetIndices.includes(widgetIdx)) {
                entry.changedWidgetIndices.push(widgetIdx);
              }
            } else if (step.op === "set_mode") {
              const uid = resolveUid(step.uidOrId);
              let entry = planEditedMap.get(uid);
              if (!entry) {
                entry = { uid, changedWidgetIndices: [] };
                planEditedMap.set(uid, entry);
              }
              // Mode change doesn't map to a specific widget; the node is still "edited".
          } else if (step.op === "add_node") {
            const nodePayload = step.nodePayload;
            const uid = readPreviewNodeUid(nodePayload)
              || (nodePayload?.id != null ? identityIndex.candidateUidByNativeId.get(String(nodePayload.id)) : null)
                || null;
              const classType = nodePayload?.type || nodePayload?.class_type || null;
              const unwiredRequiredInputs = (Array.isArray(nodePayload?.inputs) ? nodePayload.inputs : [])
                .filter((input) => !input?.link && !input?.widget)
                .map((input) => input?.name || null)
                .filter(Boolean);
              planAdded.push({ uid, class_type: classType, unwiredRequiredInputs });
            } else if (step.op === "remove_node") {
              const uid = resolveUid(step.uidOrId);
              // Look up class_type from live graph.
              let classType = null;
              for (const node of liveNodes) {
                if (getUid(node) === uid || String(node.id) === String(step.uidOrId)) {
                  classType = node.type || node.comfyClass || null;
                  break;
                }
              }
              planRemoved.push({ uid, class_type: classType });
            }
          }

          deltaDerivedEdited = Array.from(planEditedMap.values());
          deltaDerivedAdded = planAdded;
          deltaDerivedRemoved = planRemoved;
        } catch (planErr) {
          // If preflight fails (e.g., candidate graph inconsistency), log and
          // fall through to the legacy graph-diff path below.  The preview will
          // still be populated via the live-vs-candidate comparison.
          console.warn("[vibecomfy] computePreviewDiff — preflightDeltaPlan failed, falling back to graph diff:", safePreviewLogDetail(planErr));
        }
      }

      // ── Edited: from delta ops or live-vs-candidate graph diff ──────────
      const edited = deltaDerivedEdited
        ? deltaDerivedEdited
        : ownedGraphDiff
          ? ownedGraphDiff.edited
        : (() => {
            const result = [];
            for (const [uid, liveNode] of liveByUid) {
              const candidateNode = candidateByUid.get(uid);
              if (!candidateNode) continue;
              const liveValues = readWidgetValues(liveSerializedByUid.get(uid) || liveNode);
              const candidateValues = readWidgetValues(candidateNode);
              const maxLen = Math.max(liveValues.length, candidateValues.length);
              const changedWidgetIndices = [];
              for (let i = 0; i < maxLen; i += 1) {
                const a = liveValues[i];
                const b = candidateValues[i];
                if (!Object.is(a, b) && JSON.stringify(a) !== JSON.stringify(b)) {
                  changedWidgetIndices.push(i);
                }
              }
              if (changedWidgetIndices.length > 0) {
                result.push({ uid, changedWidgetIndices });
              }
            }
            return result;
          })();

      // ── Added: from delta ops or live-vs-candidate graph diff ──────────
      const added = deltaDerivedAdded
        ? deltaDerivedAdded
        : ownedGraphDiff
          ? ownedGraphDiff.added
        : (() => {
            const result = [];
            for (const [uid, candidateNode] of candidateByUid) {
              if (liveByUid.has(uid)) continue;
              const unwiredRequiredInputs = (Array.isArray(candidateNode.inputs) ? candidateNode.inputs : [])
                .filter((input) => !input?.link && !input?.widget)
                .map((input) => input?.name || null)
                .filter(Boolean);
              result.push({
                uid,
                class_type: candidateNode.type || candidateNode.class_type || null,
                unwiredRequiredInputs,
              });
            }
            return result;
          })();

      // ── Removed: from delta ops or live-vs-candidate graph diff ──────────
      const removed = deltaDerivedRemoved
        ? deltaDerivedRemoved
        : ownedGraphDiff
          ? ownedGraphDiff.removed
        : (() => {
            const result = [];
            for (const [uid, liveNode] of liveByUid) {
              if (!candidateByUid.has(uid)) {
                result.push({
                  uid,
                  class_type: liveNode.type || liveNode.comfyClass || null,
                });
              }
            }
            return result;
          })();

      // ── Removed named: from the backend report ────────────────────────────
      const removedNamed = (
        Array.isArray(candidateReport?.change?.content_edits?.removed_named)
          ? candidateReport.change.content_edits.removed_named
          : []
      ).map((item) => ({
        uid: item?.uid || null,
        class_type: item?.class_type || null,
      }));

      // ── Unresolved: report entries we cannot square with either graph ─────
      const unresolved = [];
      const reportEdited = Array.isArray(candidateReport?.change?.content_edits?.edited)
        ? candidateReport.change.content_edits.edited
        : [];
      const reportNew = Array.isArray(candidateReport?.change?.content_edits?.new_auto_placed)
        ? candidateReport.change.content_edits.new_auto_placed
        : [];
      const reportRemoved = Array.isArray(candidateReport?.change?.content_edits?.removed)
        ? candidateReport.change.content_edits.removed
        : [];

      for (const uid of reportEdited) {
        if (!liveByUid.has(uid) && !candidateByUid.has(uid)) {
          unresolved.push({ uid, kind: "edited", reason: "not found in live or candidate graph" });
        }
      }
      for (const uid of reportNew) {
        if (!candidateByUid.has(uid)) {
          unresolved.push({ uid, kind: "new_auto_placed", reason: "not found in candidate graph" });
        }
      }
      for (const uid of reportRemoved) {
        if (!liveByUid.has(uid)) {
          unresolved.push({ uid, kind: "removed", reason: "not found in live graph" });
        }
      }

      if (unresolved.length > 0) {
        console.warn("[vibecomfy] computePreviewDiff — unresolved report entries:", safePreviewLogDetail(unresolved));
      }

      // ── Edited Fields: from normalized FieldChange data (T10) ────────────
      // Read panel.state.lastSubmitFieldChanges (populated by submitAgentEdit
      // after a round-trip response) and merge outcomeChanges with all batch
      // turn changes into a flat uid+field_path-keyed view for the overlay.
      // Resolve uids through the existing liveByUid/candidateByUid maps (which
      // already use getUid()/LiteGraph id fallback).
      const editedFields = [];
      let legacyFieldChanges = [];
      if (panel?.state?.lastSubmitFieldChanges) {
        const seenFieldKeys = new Set();
        const lfs = panel.state.lastSubmitFieldChanges;

        // normalizeFieldChangesFromSubmit publishes the compact original-to-final
        // list.  Raw per-batch changes remain available for transcript/audit UI,
        // but must not leak abandoned intermediate values into the canvas review.
        const allFieldChanges = Array.isArray(lfs.all)
          ? lfs.all
          : _compactNetFieldChanges([
              ...(Array.isArray(lfs.outcomeChanges) ? lfs.outcomeChanges : []),
              ...(Array.isArray(lfs.batchTurnChanges)
                ? lfs.batchTurnChanges.flatMap((btc) => Array.isArray(btc?.changes) ? btc.changes : [])
                : []),
            ]);
        legacyFieldChanges = allFieldChanges;

        for (const fc of allFieldChanges) {
          const fieldPath = typeof fc?.fieldPath === "string" && fc.fieldPath
            ? fc.fieldPath
            : fc?.field_path;
          if (!fc || !fc.uid || !fieldPath) continue;
          // Resolve uid through liveByUid or candidateByUid (getUid/LiteGraph id fallback)
          if (!liveByUid.has(fc.uid) && !candidateByUid.has(fc.uid)) continue;
          const fieldKey = `${fc.uid}::${fieldPath}`;
          if (seenFieldKeys.has(fieldKey)) continue;
          seenFieldKeys.add(fieldKey);

          // Format the new value for display
          let newValueDisplay;
          if (!("new" in fc)) {
            newValueDisplay = null;
          } else if (fc.new === null) {
            newValueDisplay = "null";
          } else if (fc.new === undefined) {
            newValueDisplay = null;
          } else if (typeof fc.new === "string") {
            newValueDisplay = fc.new;
          } else if (typeof fc.new === "number" || typeof fc.new === "boolean") {
            newValueDisplay = String(fc.new);
          } else if (Array.isArray(fc.new)) {
            newValueDisplay = "[…]";
          } else if (typeof fc.new === "object") {
            newValueDisplay = "{…}";
          } else {
            newValueDisplay = String(fc.new);
          }

          editedFields.push({
            uid: fc.uid,
            field_path: fieldPath,
            new_value: newValueDisplay,
          });
        }
      }

      const liveLinksByPhysicalEndpoint = stablePreviewLinkMapV1(
        livePreviewGraph,
        identityIndex.candidateUidByNativeId,
      );
      const candidateLinksByPhysicalEndpoint = stablePreviewLinkMapV1(
        previewCandidateGraph,
        identityIndex.candidateUidByNativeId,
      );
      const added_links = [...candidateLinksByPhysicalEndpoint]
        .filter(([physicalKey]) => !liveLinksByPhysicalEndpoint.has(physicalKey))
        .map(([, displayKey]) => displayKey);
      const removed_links = [...liveLinksByPhysicalEndpoint]
        .filter(([physicalKey]) => !candidateLinksByPhysicalEndpoint.has(physicalKey))
        .map(([, displayKey]) => displayKey);

      // ── Link-edited uids: only derived from graph diff; delta ops already ──
      // capture every node change explicitly in the plan.
      if (!deltaDerivedEdited) {
        const linkEditedUids = new Set();
        const _parseLinkKey = (key) => {
          const text = String(key || "");
          const arrowIndex = text.indexOf("->");
          if (arrowIndex < 0) return null;
          const sourceText = text.slice(0, arrowIndex);
          const targetText = text.slice(arrowIndex + 2);
          const sourceSep = sourceText.indexOf("::");
          const targetSep = targetText.indexOf("::");
          if (sourceSep < 0 || targetSep < 0) return null;
          const fromUid = sourceText.slice(0, sourceSep);
          const fromPort = sourceText.slice(sourceSep + 2);
          const toUid = targetText.slice(0, targetSep);
          const toPort = targetText.slice(targetSep + 2);
          if (!fromUid || !toUid) return null;
          return {
            fromUid,
            fromPort,
            toUid,
            toPort,
            sourceKey: `${fromUid}::${fromPort}`,
            targetKey: `${toUid}::${toPort}`,
          };
        };
        const _sourcesByTarget = (keys) => {
          const grouped = new Map();
          for (const key of keys) {
            const parsed = _parseLinkKey(key);
            if (!parsed) continue;
            if (!grouped.has(parsed.targetKey)) {
              grouped.set(parsed.targetKey, { uid: parsed.toUid, sources: new Set() });
            }
            grouped.get(parsed.targetKey).sources.add(parsed.sourceKey);
          }
          return grouped;
        };
        const _sameSet = (left, right) => {
          if (left.size !== right.size) return false;
          for (const value of left) {
            if (!right.has(value)) return false;
          }
          return true;
        };
        const addedSourcesByTarget = _sourcesByTarget(added_links);
        const removedSourcesByTarget = _sourcesByTarget(removed_links);
        const changedTargetKeys = new Set([
          ...addedSourcesByTarget.keys(),
          ...removedSourcesByTarget.keys(),
        ]);
        for (const targetKey of changedTargetKeys) {
          const addedTarget = addedSourcesByTarget.get(targetKey);
          const removedTarget = removedSourcesByTarget.get(targetKey);
          const uid = addedTarget?.uid || removedTarget?.uid || null;
          if (!uid || !liveByUid.has(uid) || !candidateByUid.has(uid)) {
            continue;
          }
          const addedSources = addedTarget?.sources || new Set();
          const removedSources = removedTarget?.sources || new Set();
          if (!_sameSet(addedSources, removedSources)) {
            linkEditedUids.add(uid);
          }
        }
        const editedByUid = new Map(edited.map((entry) => [entry.uid, entry]));
        for (const uid of linkEditedUids) {
          if (!editedByUid.has(uid)) {
            const entry = { uid, changedWidgetIndices: [] };
            editedByUid.set(uid, entry);
            edited.push(entry);
          }
        }
      }

      const layoutMoved = ownedGraphDiff.layout_moved;
      const layoutGroups = ownedGraphDiff.layout_groups;

      const legacyIntentDiff = !deltaDerivedEdited
        ? constrainPreviewDiffToLegacyIntent({
            graphDiff: { edited, added, removed, added_links, removed_links },
            fieldChanges: legacyFieldChanges,
            changeDetails: panel?.state?.changeDetails || null,
          })
        : null;
      if (legacyIntentDiff?._legacyIntentDerived) {
        const fieldsByUid = new Map();
        for (const field of legacyFieldChanges) {
          const uid = field?.uid != null ? String(field.uid) : null;
          const fieldPath = field?.fieldPath || field?.field_path || null;
          if (!uid || !fieldPath) continue;
          if (!fieldsByUid.has(uid)) fieldsByUid.set(uid, []);
          fieldsByUid.get(uid).push(String(fieldPath));
        }
        for (const entry of legacyIntentDiff.edited) {
          const liveNode = runtimeIdentityIndex.liveByUid.get(entry.uid);
          const widgets = Array.isArray(liveNode?.widgets) ? liveNode.widgets : [];
          for (const fieldPath of fieldsByUid.get(entry.uid) || []) {
            const widgetIndex = widgets.findIndex((widget) => widget?.name === fieldPath);
            if (widgetIndex >= 0 && !entry.changedWidgetIndices.includes(widgetIndex)) {
              entry.changedWidgetIndices.push(widgetIndex);
            }
          }
          entry.changedWidgetIndices.sort((left, right) => left - right);
        }
      }

      const diff = {
        edited: legacyIntentDiff?.edited || edited,
        edited_fields: editedFields,
        added: legacyIntentDiff?.added || added,
        removed: legacyIntentDiff?.removed || removed,
        removed_named: removedNamed,
        layout_moved: layoutMoved,
        layout_groups: layoutGroups,
        unresolved,
        added_links: legacyIntentDiff?.added_links || added_links,
        removed_links: legacyIntentDiff?.removed_links || removed_links,
        _candidateGraph: previewCandidateGraph,
        _candidateGraphHash: candidateGraphHash || null,
        _deltaOpsDerived: useDeltaOps && deltaDerivedEdited !== null,
        _legacyIntentDerived: Boolean(legacyIntentDiff?._legacyIntentDerived),
        _roundtripDrift: legacyIntentDiff?._roundtripDrift || null,
      };

      // ── Cache on panel state ──────────────────────────────────────────────
      if (panel && candidateGraphHash) {
        panel.state._previewDiff = diff;
        panel.state._previewDiffGraphHash = candidateGraphHash;
        panel.state._previewDiffCacheTag = deltaOpsCacheTag;
        panel.state._previewDiffLiveCanvasRevision = liveCanvasRevision;
        panel.state._previewDiffInputSignature = inputSignature;
      }

      return diff;
    } catch (e) {
      console.warn("[vibecomfy] computePreviewDiff failed:", safePreviewLogDetail(e));
      return previewFailure(e);
    }
  }

  function getOrBuildPreviewDiff() {
    const panel = currentAgentPanel();
    if (!panel) {
      return null;
    }
    const candidateGraph = panel.state.candidateGraph;
    const candidateReport = panel.state.candidateReport;
    if (!candidateGraph) {
      return null;
    }
    const deltaOps = Array.isArray(panel.state.deltaOps) ? panel.state.deltaOps : null;
    const deltaOpsCacheTag = deltaOps && deltaOps.length > 0 ? `delta:${deltaOps.length}` : "graph";
    const candidateGraphHash = panel.state.candidateGraphHash;
    const liveCanvasRevision = captureLiveCanvasRevision();
    const inputSignature = previewDiffInputSignature(panel, candidateReport, deltaOps);
    if (
      panel.state._previewDiff &&
      panel.state._previewDiffGraphHash === candidateGraphHash &&
      panel.state._previewDiffCacheTag === deltaOpsCacheTag &&
      panel.state._previewDiffLiveCanvasRevision === liveCanvasRevision &&
      panel.state._previewDiffInputSignature === inputSignature &&
      Array.isArray(panel.state._previewDiff.added_links) &&
      Array.isArray(panel.state._previewDiff.removed_links) &&
      Array.isArray(panel.state._previewDiff.edited_fields) &&
      Array.isArray(panel.state._previewDiff.layout_moved) &&
      Array.isArray(panel.state._previewDiff.layout_groups)
    ) {
      return panel.state._previewDiff;
    }
    return computePreviewDiffFacade(candidateGraph, candidateReport, deltaOps);
  }

  return {
    computePreviewDiff,
    getOrBuildPreviewDiff,
  };
}
