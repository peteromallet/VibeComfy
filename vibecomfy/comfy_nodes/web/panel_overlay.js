import { currentAgentPanel, getAgentPanelRuntime } from "./panel_runtime.js";
import { installPreviewForegroundOverlay } from "./comfy_adapter.js";

export function invalidateOverlayDrawModelCache() {
  getAgentPanelRuntime()._overlayDrawModelCache = null;
}

function overlayDrawCacheKey(diff, candidateGraph, deps = {}) {
  const { captureLiveCanvasRevision, graphNodeCount } = deps;
  const candidateHash =
    diff?._candidateGraphHash
    || currentAgentPanel()?.state?.candidateGraphHash
    || `inline:${graphNodeCount(candidateGraph)}:${Array.isArray(candidateGraph?.links) ? candidateGraph.links.length : 0}`;
  const liveRevision = captureLiveCanvasRevision();
  return `${candidateHash}:${liveRevision == null ? "unknown" : liveRevision}`;
}

function computeGhostDimensions(cn, ctx, deps = {}) {
  const { readWidgetValues, widgetValuePreviewText } = deps;
  var TITLE_H = (window.LiteGraph && window.LiteGraph.NODE_TITLE_HEIGHT) || 30;
  var SLOT_H = (window.LiteGraph && window.LiteGraph.NODE_SLOT_HEIGHT) || 20;
  var WIDGET_H = (window.LiteGraph && window.LiteGraph.NODE_WIDGET_HEIGHT) || 20;
  var PAD_X = 32;
  var PAD_Y = 12;
  var MIN_W = 140;
  var title = (typeof cn.title === "string" && cn.title) || (typeof cn.type === "string" && cn.type) || "Node";
  var inputs = Array.isArray(cn.inputs) ? cn.inputs : [];
  var outputs = Array.isArray(cn.outputs) ? cn.outputs : [];
  var widgetValues = readWidgetValues(cn);
  var trunc = function (text, maxChars) {
    text = String(text || "").trim();
    if (!text) return "";
    return text.length > maxChars ? text.slice(0, maxChars - 1) + "\u2026" : text;
  };
  ctx.save();
  try {
    ctx.font = "12px Arial, sans-serif";
    ctx.textBaseline = "top";
    var titleW = ctx.measureText(trunc(title, 40)).width;
    var maxSlotW = 0;
    for (var s = 0; s < inputs.length; s += 1) {
      var lbl = inputs[s] && inputs[s].name;
      if (lbl) maxSlotW = Math.max(maxSlotW, ctx.measureText(trunc(lbl, 30)).width);
    }
    for (var t = 0; t < outputs.length; t += 1) {
      var olbl = outputs[t] && outputs[t].name;
      if (olbl) maxSlotW = Math.max(maxSlotW, ctx.measureText(trunc(olbl, 30)).width);
    }
    var maxWidgetW = 0;
    for (var wi = 0; wi < widgetValues.length; wi += 1) {
      var wvText = trunc(widgetValuePreviewText(widgetValues[wi]), 35);
      if (wvText) maxWidgetW = Math.max(maxWidgetW, ctx.measureText(wvText).width);
    }
    var contentW = Math.max(titleW, maxSlotW, maxWidgetW);
    var gw = Math.max(MIN_W, Math.ceil(contentW + PAD_X));
    var slotRows = Math.max(inputs.length, outputs.length);
    var gh = TITLE_H + slotRows * SLOT_H + widgetValues.length * WIDGET_H + PAD_Y;
    return { w: gw, h: gh };
  } finally {
    ctx.restore();
  }
}

function buildOverlayDrawModel(ctx, diff, candidateGraph, deps = {}) {
  const {
    captureLiveCanvasRevision,
    getLiveGraph,
    getLiveGraphNodes,
    getUid,
    graphNodeCount,
    readNodeSize,
  } = deps;
  const runtime = getAgentPanelRuntime();
  const key = overlayDrawCacheKey(diff, candidateGraph, {
    captureLiveCanvasRevision,
    graphNodeCount,
  });
  if (runtime._overlayDrawModelCache?.key === key) {
    return runtime._overlayDrawModelCache.model;
  }
  const liveByUid = new Map();
  for (const node of getLiveGraphNodes(getLiveGraph())) {
    const uid = getUid(node);
    if (uid) {
      liveByUid.set(uid, node);
    }
  }
  const candidateByUid = new Map();
  for (const node of Array.isArray(candidateGraph?.nodes) ? candidateGraph.nodes : []) {
    const uid = getUid(node);
    if (uid) {
      candidateByUid.set(uid, node);
    }
  }
  const addedByUid = new Map();
  for (const item of Array.isArray(diff?.added) ? diff.added : []) {
    if (item?.uid) {
      addedByUid.set(item.uid, item);
    }
  }
  const ghostDimsByUid = new Map();
  for (const [uid, node] of candidateByUid) {
    if (!addedByUid.has(uid)) {
      continue;
    }
    const nodeSize = readNodeSize(node, NaN, NaN);
    if (nodeSize.w > 40 && nodeSize.h > 20) {
      ghostDimsByUid.set(uid, nodeSize);
      continue;
    }
    ghostDimsByUid.set(uid, computeGhostDimensions(node, ctx, deps));
  }
  const model = {
    liveByUid,
    candidateByUid,
    addedByUid,
    ghostDimsByUid,
    unresolvedWarnCount: 0,
  };
  runtime._overlayDrawModelCache = { key, model };
  return model;
}

function warnOverlayUnresolved(model, message, detail) {
  if (!model || model.unresolvedWarnCount >= 5) {
    return;
  }
  model.unresolvedWarnCount += 1;
  console.warn(message, detail);
}

export function installAgentPreviewOverlay(app, deps = {}) {
  const {
    PANEL_STATE,
    drawPreviewOverlay,
    getOrBuildPreviewDiff,
  } = deps;
  const runtime = getAgentPanelRuntime();
  if (app?.__vibecomfyAgentPreviewOverlayInstalled && runtime._previewForegroundInstallReport) {
    return;
  }
  const overlayDraw = app.__vibecomfyAgentPreviewOverlayDraw || function (ctx) {
    const panel = currentAgentPanel();
    if (!panel || panel.state.phase !== PANEL_STATE.AWAITING_REVIEW || !panel.state.candidateGraph) {
      return;
    }
    try {
      const diff = getOrBuildPreviewDiff();
      if (diff) {
        drawPreviewOverlay(ctx, diff);
      }
    } catch (e) {
      console.warn("[vibecomfy] drawPreviewOverlay threw:", e);
    }
  };
  app.__vibecomfyAgentPreviewOverlayDraw = overlayDraw;
  try {
    const install = installPreviewForegroundOverlay(app, overlayDraw, { windowObj: window });
    runtime._previewForegroundInstallReport = install;
    app.__vibecomfyAgentPreviewOverlayInstalled = true;
    if (install.polling) {
      console.warn(`[vibecomfy] preview overlay install degraded: ${install.detail}`);
    }
  } catch (e) {
    if (e?.code === "PREVIEW_FOREGROUND_UNAVAILABLE") {
      runtime._previewForegroundInstallReport = {
        capability: e.capability,
        strategy: "unavailable",
        degraded: true,
        detail: e.message,
      };
      console.warn(`[vibecomfy] preview overlay unavailable: ${e.capability?.detail || e.message}`);
      return;
    }
    throw e;
  }
}

export function drawPreviewOverlay(ctx, diff, deps = {}) {
  const {
    VC_COLORS,
    currentAgentPanel: currentAgentPanelImpl,
    getLiveGraph,
    getLiveGraphNodes,
    getUid,
    hexToRgba,
    readNodeBounding,
    readNodePos,
    readNodeSize,
    readWidgetValues,
    vecNumber,
    widgetValuePreviewText,
    captureLiveCanvasRevision,
    graphNodeCount,
  } = deps;
  if (!ctx || !diff) {
    return;
  }
  ctx.save();
  try {
    if (ctx.setLineDash) {
      ctx.setLineDash([]);
    }

    var editedColor = VC_COLORS.edited;
    var editedFill = hexToRgba(VC_COLORS.edited, 0.16);
    var addedColor = VC_COLORS.added;
    var addedFill = hexToRgba(VC_COLORS.added, 0.18);
    var addedTextColor = hexToRgba(VC_COLORS.added, 0.92);
    var removedColor = VC_COLORS.removed;
    var removedFill = hexToRgba(VC_COLORS.removed, 0.16);
    var TITLE_H = (window.LiteGraph && window.LiteGraph.NODE_TITLE_HEIGHT) || 30;
    var SLOT_H = (window.LiteGraph && window.LiteGraph.NODE_SLOT_HEIGHT) || 20;
    var WIDGET_H = (window.LiteGraph && window.LiteGraph.NODE_WIDGET_HEIGHT) || 20;
    var panel = currentAgentPanelImpl();
    var candidateGraph = (diff && diff._candidateGraph) || (panel && panel.state && panel.state.candidateGraph);
    var drawModel = buildOverlayDrawModel(ctx, diff, candidateGraph, {
      captureLiveCanvasRevision,
      getLiveGraph,
      getLiveGraphNodes,
      getUid,
      graphNodeCount,
      readNodeSize,
      readWidgetValues,
      widgetValuePreviewText,
    });
    var liveByUid = drawModel.liveByUid;
    var candidateByUid = drawModel.candidateByUid;
    var addedByUid = drawModel.addedByUid;

    var drawBadge = function (bx, by, text, color) {
      ctx.save();
      if (ctx.setLineDash) {
        ctx.setLineDash([]);
      }
      ctx.font = "bold 12px sans-serif";
      var padX = 5;
      var bw = ctx.measureText(text).width + padX * 2;
      var bh = 18;
      ctx.fillStyle = color;
      ctx.fillRect(bx, by - bh, bw, bh);
      ctx.fillStyle = "#000000";
      ctx.textBaseline = "middle";
      ctx.fillText(text, bx + padX, by - bh / 2 + 1);
      ctx.restore();
    };

    var drawFullBoxMarker = function (bounds, strokeColor, fillColor, dashed) {
      ctx.setLineDash(dashed ? [6, 3] : []);
      ctx.fillStyle = fillColor;
      ctx.fillRect(bounds.x - 2, bounds.y - 2, bounds.w + 4, bounds.h + 4);
      ctx.strokeStyle = strokeColor;
      ctx.lineWidth = 2;
      ctx.strokeRect(bounds.x - 2, bounds.y - 2, bounds.w + 4, bounds.h + 4);
      ctx.setLineDash([]);
    };

    var drawRoundedPanel = function (x, y, w, h, radius, fillStyle, strokeStyle) {
      ctx.fillStyle = fillStyle;
      ctx.strokeStyle = strokeStyle;
      ctx.lineWidth = 1;
      if (typeof ctx.roundRect === "function") {
        ctx.beginPath();
        ctx.roundRect(x, y, w, h, radius);
        ctx.fill();
        ctx.stroke();
        return;
      }
      ctx.fillRect(x, y, w, h);
      ctx.strokeRect(x, y, w, h);
    };

    var trunc = function (text, maxChars) {
      text = String(text || "").trim();
      if (!text) return "";
      return text.length > maxChars ? text.slice(0, maxChars - 1) + "\u2026" : text;
    };

    var fitTextToWidth = function (text, maxWidth) {
      text = String(text == null ? "" : text);
      if (!text || maxWidth <= 0) return "";
      if (ctx.measureText(text).width <= maxWidth) return text;
      var ellipsis = "\u2026";
      var lo = 0;
      var hi = text.length;
      while (lo < hi) {
        var mid = Math.ceil((lo + hi) / 2);
        if (ctx.measureText(text.slice(0, mid) + ellipsis).width <= maxWidth) {
          lo = mid;
        } else {
          hi = mid - 1;
        }
      }
      return lo > 0 ? text.slice(0, lo) + ellipsis : ellipsis;
    };

    var widgetIndexFromFieldPath = function (fieldPath) {
      var path = String(fieldPath || "");
      var direct = /(?:^|\.)(?:widgets_values|widgets)\.(\d+)(?:\.|$)/.exec(path);
      if (direct) return Number(direct[1]);
      var widgetKey = /^widget_(\d+)$/.exec(path);
      if (widgetKey) return Number(widgetKey[1]);
      return null;
    };

    var fieldNameCandidates = function (fieldPath) {
      var path = String(fieldPath || "");
      if (!path) return [];
      var normalized = path.replace(/\[(\d+)\]/g, ".$1");
      var parts = normalized.split(".").filter(Boolean);
      var last = parts.length ? parts[parts.length - 1] : normalized;
      return [normalized, last];
    };

    var resolveWidgetFieldIndex = function (field, node) {
      var directIndex = widgetIndexFromFieldPath(field && field.field_path);
      if (directIndex != null && Number.isFinite(directIndex)) {
        return directIndex;
      }
      var widgetsForNode = Array.isArray(node && node.widgets) ? node.widgets : [];
      if (widgetsForNode.length === 0) {
        return null;
      }
      var candidates = fieldNameCandidates(field && field.field_path);
      for (var ci = 0; ci < candidates.length; ci += 1) {
        var candidateName = candidates[ci];
        for (var wi = 0; wi < widgetsForNode.length; wi += 1) {
          var widget = widgetsForNode[wi];
          var widgetNames = [widget && widget.name, widget && widget.label].filter(Boolean);
          for (var ni = 0; ni < widgetNames.length; ni += 1) {
            if (String(widgetNames[ni]) === candidateName) {
              return wi;
            }
          }
        }
      }
      return null;
    };

    var formatFieldLabel = function (field) {
      var label = field && field.field_path ? String(field.field_path) : "field";
      if (field && field.new_value !== null && field.new_value !== undefined) {
        label += ": " + field.new_value;
      }
      return trunc(label, 48);
    };

    var fieldNewValueLabel = function (field) {
      if (!field || field.new_value === null || field.new_value === undefined) {
        return "";
      }
      return String(field.new_value);
    };

    var editedFieldsByUid = new Map();
    if (diff.edited_fields && diff.edited_fields.length > 0) {
      for (var efg = 0; efg < diff.edited_fields.length; efg += 1) {
        var groupedField = diff.edited_fields[efg];
        if (!groupedField || !groupedField.uid) continue;
        if (!editedFieldsByUid.has(groupedField.uid)) {
          editedFieldsByUid.set(groupedField.uid, []);
        }
        editedFieldsByUid.get(groupedField.uid).push(groupedField);
      }
    }

    var hasEditedLinkTarget = function (uid) {
      if (!uid) return false;
      var needle = "->" + uid + "::";
      var addedLinks = Array.isArray(diff.added_links) ? diff.added_links : [];
      var removedLinks = Array.isArray(diff.removed_links) ? diff.removed_links : [];
      for (var ai = 0; ai < addedLinks.length; ai += 1) {
        if (String(addedLinks[ai]).indexOf(needle) !== -1) return true;
      }
      for (var ri = 0; ri < removedLinks.length; ri += 1) {
        if (String(removedLinks[ri]).indexOf(needle) !== -1) return true;
      }
      return false;
    };

    var drawWidgetValueOverlay = function (bounds, valueText, labelText) {
      var padX = 7;
      var rightPad = 8;
      var labelReserve = 56;
      try {
        ctx.font = "11px Arial, sans-serif";
        if (typeof labelText === "string" && labelText && typeof ctx.measureText === "function") {
          var lm = ctx.measureText(labelText);
          if (lm && Number.isFinite(lm.width)) {
            labelReserve = Math.max(labelReserve, lm.width + 34);
          }
        }
      } catch (_e) {}
      var overlayW = Math.max(48, bounds.w - rightPad - labelReserve);
      overlayW = Math.min(overlayW, bounds.w - 12);
      if (!Number.isFinite(overlayW) || overlayW <= 0) return;
      var overlayX = bounds.x + bounds.w - rightPad - overlayW;
      var overlayY = bounds.y + 2;
      var overlayH = Math.max(bounds.h - 4, 12);
      drawRoundedPanel(
        overlayX,
        overlayY,
        overlayW,
        overlayH,
        5,
        "rgba(20,18,8,0.92)",
        hexToRgba(VC_COLORS.edited, 0.95),
      );
      ctx.save();
      try {
        if (typeof ctx.rect === "function" && typeof ctx.clip === "function") {
          ctx.beginPath();
          ctx.rect(overlayX, overlayY, overlayW, overlayH);
          ctx.clip();
        }
        ctx.font = "11px Arial, sans-serif";
        ctx.textBaseline = "middle";
        ctx.textAlign = "right";
        ctx.fillStyle = hexToRgba(VC_COLORS.edited, 0.98);
        var fitted = fitTextToWidth(valueText, Math.max(overlayW - padX * 2, 4));
        ctx.fillText(fitted, overlayX + overlayW - padX, overlayY + overlayH / 2);
      } finally {
        ctx.restore();
      }
    };

    for (var ei = 0; ei < (diff.edited || []).length; ei += 1) {
      var eitem = diff.edited[ei];
      var enode = liveByUid.get(eitem.uid);
      if (!enode || !enode.pos) {
        continue;
      }
      var epos = readNodePos(enode);
      var ex = epos.x;
      var ey = epos.y;
      var esize = readNodeSize(enode);
      var ew = esize.w;
      var collapsed = !!(enode.flags && enode.flags.collapsed);
      var eh = collapsed ? 0 : esize.h;
      var eb = readNodeBounding(enode, TITLE_H);
      drawFullBoxMarker(eb, editedColor, editedFill, false);
      if (collapsed) {
        continue;
      }
      var widgets = Array.isArray(enode.widgets) ? enode.widgets : [];
      var slotRows = Math.max(
        Array.isArray(enode.inputs) ? enode.inputs.length : 0,
        Array.isArray(enode.outputs) ? enode.outputs.length : 0,
      );
      var computedRowsTop = ey + slotRows * SLOT_H;
      var widgetRowBounds = new Map();
      var rowBoundsForWidgetIndex = function (widx) {
        if (widgetRowBounds.has(widx)) {
          return widgetRowBounds.get(widx);
        }
        var w = widgets[widx];
        var rowTop;
        var rowH = WIDGET_H;
        if (w && typeof w.last_y === "number") {
          rowTop = ey + w.last_y;
          if (typeof w.computeSize === "function") {
            try {
              var cs = w.computeSize(ew);
              if (cs && typeof cs[1] === "number" && cs[1] > 0) {
                rowH = cs[1];
              }
            } catch (_ignored) {}
          }
        } else {
          rowTop = computedRowsTop + widx * WIDGET_H;
        }
        var bounds = { x: ex, y: rowTop, w: ew, h: rowH };
        widgetRowBounds.set(widx, bounds);
        return bounds;
      };
      ctx.fillStyle = hexToRgba(VC_COLORS.edited, 0.22);
      for (var wi = 0; wi < (eitem.changedWidgetIndices || []).length; wi += 1) {
        var widx = eitem.changedWidgetIndices[wi];
        var rowBounds = rowBoundsForWidgetIndex(widx);
        ctx.fillRect(rowBounds.x, rowBounds.y, rowBounds.w, Math.max(rowBounds.h - 2, 4));
      }
      var fieldsForNode = editedFieldsByUid.get(eitem.uid) || [];
      var nonWidgetFields = [];
      var drawnWidgetFieldIndexes = new Set();
      for (var efi = 0; efi < fieldsForNode.length; efi += 1) {
        var ef = fieldsForNode[efi];
        var resolvedWidgetIndex = resolveWidgetFieldIndex(ef, enode);
        if (resolvedWidgetIndex != null && Number.isFinite(resolvedWidgetIndex) && resolvedWidgetIndex >= 0) {
          if (!drawnWidgetFieldIndexes.has(resolvedWidgetIndex)) {
            drawnWidgetFieldIndexes.add(resolvedWidgetIndex);
            var overlayWidget = widgets[resolvedWidgetIndex];
            drawWidgetValueOverlay(
              rowBoundsForWidgetIndex(resolvedWidgetIndex),
              fieldNewValueLabel(ef),
              overlayWidget && typeof overlayWidget.name === "string" ? overlayWidget.name : null,
            );
          }
        } else {
          nonWidgetFields.push(ef);
        }
      }
      if (nonWidgetFields.length > 0 || hasEditedLinkTarget(eitem.uid)) {
        var chipLabel = nonWidgetFields.length > 0 ? formatFieldLabel(nonWidgetFields[0]) : "inputs changed";
        drawBadge(ex + 4, ey + eh - 2, chipLabel, editedColor);
      }
    }

    var removedItems = (diff.removed || []).concat(diff.removed_named || []);
    for (var ri = 0; ri < removedItems.length; ri += 1) {
      var ritem = removedItems[ri];
      var rnode = liveByUid.get(ritem.uid);
      if (!rnode || !rnode.pos) {
        continue;
      }
      var rb = readNodeBounding(rnode, TITLE_H);
      drawFullBoxMarker(rb, removedColor, removedFill, false);
      drawBadge(rb.x + rb.w - 2 - 140, rb.y + rb.h - 2, "\u2212 will be removed", removedColor);
    }

    for (var ai = 0; ai < (diff.added || []).length; ai += 1) {
      var aitem = diff.added[ai];
      var uid = aitem.uid;
      var cn = candidateByUid.get(uid);
      if (!cn) {
        continue;
      }
      var cpos = readNodePos(cn);
      var dims = drawModel.ghostDimsByUid.get(uid) || computeGhostDimensions(cn, ctx, {
        readWidgetValues,
        widgetValuePreviewText,
      });
      var gb = {
        x: cpos.x,
        y: cpos.y - TITLE_H,
        w: dims.w,
        h: dims.h + TITLE_H,
      };
      drawFullBoxMarker(gb, addedColor, addedFill, true);
      drawBadge(gb.x + 4, gb.y + gb.h - 2, "+ new node", addedColor);
      ctx.save();
      try {
        ctx.font = "12px Arial, sans-serif";
        ctx.textBaseline = "top";
        ctx.fillStyle = addedTextColor;
        var ghostTitle = trunc((typeof cn.title === "string" && cn.title) || cn.type || "Node", 36);
        ctx.fillText(ghostTitle, gb.x + 10, gb.y + 8);
      } finally {
        ctx.restore();
      }
    }

    var resolvePortPoint = function (uid, slotIndex, ioKind, candidatePreferred) {
      var node = candidatePreferred ? candidateByUid.get(uid) : liveByUid.get(uid);
      var titleOffset = TITLE_H;
      if (node && typeof node.getConnectionPos === "function") {
        try {
          var pos = node.getConnectionPos(ioKind === "output", slotIndex);
          if (pos && Number.isFinite(pos[0]) && Number.isFinite(pos[1])) {
            return { x: pos[0], y: pos[1] };
          }
        } catch (_ignored) {}
      }
      if (!node && candidatePreferred) {
        node = candidateByUid.get(uid);
      }
      if (!node && !candidatePreferred) {
        node = liveByUid.get(uid);
      }
      if (!node) {
        return null;
      }
      var pos = readNodePos(node);
      var size = candidatePreferred
        ? (drawModel.ghostDimsByUid.get(uid) || readNodeSize(node))
        : readNodeSize(node);
      var slotCount = ioKind === "output"
        ? (Array.isArray(node.outputs) ? node.outputs.length : 0)
        : (Array.isArray(node.inputs) ? node.inputs.length : 0);
      var rowIndex = Number.isFinite(slotIndex) ? slotIndex : 0;
      var y = pos.y + SLOT_H * (Math.min(Math.max(rowIndex, 0), Math.max(slotCount - 1, 0)) + 0.5);
      var x = ioKind === "output" ? pos.x + size.w : pos.x;
      return { x, y };
    };

    var drawWire = function (from, to, color, dashed) {
      ctx.save();
      try {
        ctx.setLineDash(dashed ? [8, 6] : []);
        ctx.strokeStyle = color;
        ctx.lineWidth = 3;
        ctx.beginPath();
        ctx.moveTo(from.x, from.y);
        var dx = Math.max(40, Math.abs(to.x - from.x) * 0.45);
        ctx.bezierCurveTo(from.x + dx, from.y, to.x - dx, to.y, to.x, to.y);
        ctx.stroke();
      } finally {
        ctx.restore();
      }
    };

    var remLinks = Array.isArray(diff.removed_links) ? diff.removed_links : [];
    for (var rli = 0; rli < remLinks.length; rli += 1) {
      var rem = remLinks[rli];
      var remMatch = /^(.*?)::(\d+)->(.*?)::(\d+)$/.exec(String(rem || ""));
      if (!remMatch) {
        continue;
      }
      var remFrom = resolvePortPoint(remMatch[1], Number(remMatch[2]), "output", false);
      var remTo = resolvePortPoint(remMatch[3], Number(remMatch[4]), "input", false);
      if (!remFrom || !remTo) {
        warnOverlayUnresolved(drawModel, "[vibecomfy] drawPreviewOverlay — could not resolve removed-wire endpoint positions:", rem);
        continue;
      }
      drawWire(remFrom, remTo, removedColor, false);
    }

    var addLinks = Array.isArray(diff.added_links) ? diff.added_links : [];
    for (var ali = 0; ali < addLinks.length; ali += 1) {
      var add = addLinks[ali];
      var addMatch = /^(.*?)::(\d+)->(.*?)::(\d+)$/.exec(String(add || ""));
      if (!addMatch) {
        continue;
      }
      var addFrom = resolvePortPoint(addMatch[1], Number(addMatch[2]), "output", addedByUid.has(addMatch[1]));
      var addTo = resolvePortPoint(addMatch[3], Number(addMatch[4]), "input", addedByUid.has(addMatch[3]));
      if (!addFrom || !addTo) {
        warnOverlayUnresolved(drawModel, "[vibecomfy] drawPreviewOverlay — could not resolve added-wire endpoint positions:", add);
        continue;
      }
      drawWire(addFrom, addTo, addedColor, true);
    }
  } finally {
    ctx.restore();
  }
}
