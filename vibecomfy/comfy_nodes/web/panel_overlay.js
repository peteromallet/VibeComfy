import { currentAgentPanel, getAgentPanelRuntime } from "./panel_runtime.js";
import { installPreviewForegroundOverlay } from "./comfy_adapter.js";

export function invalidateOverlayDrawModelCache() {
  getAgentPanelRuntime()._overlayDrawModelCache = null;
}

function overlayDrawCacheKey(diff, candidateGraph, deps = {}) {
  const { captureLiveCanvasRevision, graphNodeCount } = deps;
  const candidateHash =
    currentAgentPanel()?.state?.candidateGraphHash
    || diff?._candidateGraphHash
    || `inline:${graphNodeCount(candidateGraph)}:${Array.isArray(candidateGraph?.links) ? candidateGraph.links.length : 0}`;
  const liveRevision = captureLiveCanvasRevision();
  const deltaDerivedTag = diff?._deltaOpsDerived ? ":delta" : ":graph";
  return `${candidateHash}:${liveRevision == null ? "unknown" : liveRevision}${deltaDerivedTag}`;
}

const FORBIDDEN_PREVIEW_OVERLAY_TEXT_PATTERNS = [
  /\b(?:canvas_apply_allowed|canvasApplyAllowed|queue_allowed|queueAllowed)\b/i,
  /\b(?:debug_payload|debugPayload|audit_ref|auditRef|raw_path|rawPath|artifact_path|artifactPath)\b/i,
  /\/(?:real\/)?ComfyUI\/out\/editor_sessions\//i,
  /\bturns\/\d+\/(?:response|messages|candidate|debug)\.[a-z0-9]+/i,
  /\b(?:ProviderError|Traceback|stack trace|engine diagnostics|raw diagnostic)\b/i,
  /\b(?:model prompt|system prompt|prompt messages)\b/i,
  /\b(?:token budget|exit mode|remaining batches)\b/i,
];

function safePreviewOverlayText(text, fallback = "") {
  const value = String(text == null ? "" : text).trim();
  if (!value) return "";
  return FORBIDDEN_PREVIEW_OVERLAY_TEXT_PATTERNS.some((pattern) => pattern.test(value))
    ? fallback
    : value;
}

const PREVIEW_DOM_OVERLAY_ID = "vibecomfy-preview-dom-overlay";

function safePreviewLogDetail(value) {
  if (value == null) {
    return "";
  }
  if (typeof value === "string") {
    return value.length > 500 ? `${value.slice(0, 497)}...` : value;
  }
  if (typeof value === "number" || typeof value === "boolean" || typeof value === "bigint") {
    return String(value);
  }
  if (value instanceof Error) {
    const name = typeof value.name === "string" && value.name ? value.name : "Error";
    const message = typeof value.message === "string" ? value.message : "";
    return message ? `${name}: ${message}` : name;
  }
  if (Array.isArray(value)) {
    return `[array length=${value.length}]`;
  }
  if (typeof value === "object") {
    let keys = [];
    try {
      keys = Object.keys(value).slice(0, 6);
    } catch (_e) {
      keys = [];
    }
    const ctor = typeof value.constructor?.name === "string" && value.constructor.name
      ? value.constructor.name
      : "Object";
    return keys.length ? `[${ctor} keys=${keys.join(",")}]` : `[${ctor}]`;
  }
  return typeof value;
}

export function clearPreviewDomOverlay(doc = (typeof document !== "undefined" ? document : null)) {
  const root = doc?.getElementById?.(PREVIEW_DOM_OVERLAY_ID);
  if (root) {
    root.remove();
  }
}

function ensurePreviewDomOverlayRoot(doc = (typeof document !== "undefined" ? document : null)) {
  if (!doc?.body) {
    return null;
  }
  let root = doc.getElementById?.(PREVIEW_DOM_OVERLAY_ID);
  if (!root) {
    root = doc.createElement("div");
    root.id = PREVIEW_DOM_OVERLAY_ID;
    root.dataset.vibecomfyPreviewDomOverlay = "1";
    Object.assign(root.style, {
      position: "fixed",
      inset: "0",
      pointerEvents: "none",
      zIndex: "2147483647",
    });
    doc.body.appendChild(root);
  }
  root.textContent = "";
  return root;
}

function liveCanvasElement(app) {
  const canvas = app?.canvas;
  return canvas?.canvas || canvas?.canvasEl || canvas?.el || null;
}

function canvasRect(app) {
  const el = liveCanvasElement(app);
  if (el && typeof el.getBoundingClientRect === "function") {
    const rect = el.getBoundingClientRect();
    if (rect && Number.isFinite(rect.left) && Number.isFinite(rect.top)) {
      return {
        left: rect.left,
        top: rect.top,
        width: Number.isFinite(rect.width) && rect.width > 0 ? rect.width : (el.clientWidth || el.width || 1),
        height: Number.isFinite(rect.height) && rect.height > 0 ? rect.height : (el.clientHeight || el.height || 1),
        backingWidth: Number.isFinite(el.width) && el.width > 0 ? el.width : null,
        backingHeight: Number.isFinite(el.height) && el.height > 0 ? el.height : null,
      };
    }
  }
  return null;
}

function graphPointToCanvasPoint(point, app) {
  const canvas = app?.canvas;
  const ds = canvas?.ds || {};
  const scale = Number.isFinite(ds.scale) && ds.scale > 0 ? ds.scale : 1;
  const offset = Array.isArray(ds.offset) ? ds.offset : [0, 0];
  const ox = Number.isFinite(offset[0]) ? offset[0] : 0;
  const oy = Number.isFinite(offset[1]) ? offset[1] : 0;
  return {
    x: (point.x + ox) * scale,
    y: (point.y + oy) * scale,
  };
}

function graphBoundsToViewport(bounds, app) {
  const rect = canvasRect(app);
  if (!rect) {
    return null;
  }
  const topLeft = graphPointToCanvasPoint({ x: bounds.x, y: bounds.y }, app);
  const bottomRight = graphPointToCanvasPoint({ x: bounds.x + bounds.w, y: bounds.y + bounds.h }, app);
  const scaleX = rect.backingWidth ? rect.width / rect.backingWidth : 1;
  const scaleY = rect.backingHeight ? rect.height / rect.backingHeight : 1;
  return {
    left: rect.left + Math.min(topLeft.x, bottomRight.x) * scaleX,
    top: rect.top + Math.min(topLeft.y, bottomRight.y) * scaleY,
    width: Math.abs(bottomRight.x - topLeft.x) * scaleX,
    height: Math.abs(bottomRight.y - topLeft.y) * scaleY,
  };
}

function viewportScaleForGraphBounds(bounds, viewport) {
  const scales = [];
  if (bounds?.w > 0 && viewport?.width > 0) {
    scales.push(viewport.width / bounds.w);
  }
  if (bounds?.h > 0 && viewport?.height > 0) {
    scales.push(viewport.height / bounds.h);
  }
  const finite = scales.filter((value) => Number.isFinite(value) && value > 0);
  return finite.length ? Math.min(...finite) : 1;
}

function previewFieldValueText(labelText, valueText) {
  const value = String(valueText == null ? "" : valueText);
  const label = String(labelText == null ? "" : labelText).trim();
  if (!label) {
    return value;
  }
  return `${label}: ${value}`;
}

function cssPx(value, fallback) {
  const parsed = Number.parseFloat(String(value == null ? "" : value));
  return Number.isFinite(parsed) ? parsed : fallback;
}

function positiveFiniteNumber(value, fallback) {
  return Number.isFinite(value) && value > 0 ? value : fallback;
}

function currentPreviewApp(app = null) {
  if (app) {
    return app;
  }
  if (typeof globalThis !== "undefined" && globalThis.__VIBECOMFY_BROWSER_APP__) {
    return globalThis.__VIBECOMFY_BROWSER_APP__;
  }
  if (typeof window !== "undefined" && window.comfyAPI?.app?.app) {
    return window.comfyAPI.app.app;
  }
  if (typeof window !== "undefined" && window.app) {
    return window.app;
  }
  if (typeof globalThis !== "undefined" && globalThis.app) {
    return globalThis.app;
  }
  return null;
}

function previewGraphBounds(app) {
  const liveApp = currentPreviewApp(app);
  const canvas = liveApp?.canvas || null;
  const el = liveCanvasElement(liveApp);
  const ds = canvas?.ds || canvas?.graphcanvas?.ds || {};
  const scale = Number.isFinite(ds.scale) && ds.scale > 0 ? ds.scale : 1;
  const offset = Array.isArray(ds.offset) ? ds.offset : [0, 0];
  const ox = Number.isFinite(offset[0]) ? offset[0] : 0;
  const oy = Number.isFinite(offset[1]) ? offset[1] : 0;
  const backingWidth = positiveFiniteNumber(
    el?.width,
    positiveFiniteNumber(el?.clientWidth, positiveFiniteNumber(canvas?.width, 0)),
  );
  const backingHeight = positiveFiniteNumber(
    el?.height,
    positiveFiniteNumber(el?.clientHeight, positiveFiniteNumber(canvas?.height, 0)),
  );
  if (!(backingWidth > 0) || !(backingHeight > 0)) {
    return null;
  }
  return {
    x: -ox,
    y: -oy,
    w: backingWidth / scale,
    h: backingHeight / scale,
  };
}

function intersectRect(leftRect, rightRect) {
  if (
    !leftRect
    || !rightRect
    || !Number.isFinite(leftRect.x)
    || !Number.isFinite(leftRect.y)
    || !Number.isFinite(leftRect.w)
    || !Number.isFinite(leftRect.h)
    || !Number.isFinite(rightRect.x)
    || !Number.isFinite(rightRect.y)
    || !Number.isFinite(rightRect.w)
    || !Number.isFinite(rightRect.h)
    || leftRect.w <= 0
    || leftRect.h <= 0
    || rightRect.w <= 0
    || rightRect.h <= 0
  ) {
    return null;
  }
  const left = Math.max(leftRect.x, rightRect.x);
  const top = Math.max(leftRect.y, rightRect.y);
  const right = Math.min(leftRect.x + leftRect.w, rightRect.x + rightRect.w);
  const bottom = Math.min(leftRect.y + leftRect.h, rightRect.y + rightRect.h);
  if (!(right > left) || !(bottom > top)) {
    return null;
  }
  return {
    x: left,
    y: top,
    w: right - left,
    h: bottom - top,
  };
}

function clampRectWithin(rect, container, minW = 4, minH = 4) {
  if (!rect || !container) {
    return rect;
  }
  if (
    !Number.isFinite(container.x)
    || !Number.isFinite(container.y)
    || !Number.isFinite(container.w)
    || !Number.isFinite(container.h)
    || container.w <= 0
    || container.h <= 0
  ) {
    return rect;
  }
  const width = Math.max(minW, Math.min(
    positiveFiniteNumber(rect.w, minW),
    Math.max(minW, container.w),
  ));
  const height = Math.max(minH, Math.min(
    positiveFiniteNumber(rect.h, minH),
    Math.max(minH, container.h),
  ));
  const maxX = container.x + container.w - width;
  const maxY = container.y + container.h - height;
  const x = Math.min(Math.max(Number.isFinite(rect.x) ? rect.x : container.x, container.x), maxX);
  const y = Math.min(Math.max(Number.isFinite(rect.y) ? rect.y : container.y, container.y), maxY);
  return { x, y, w: width, h: height };
}

function widgetFieldBoundsFromRow(rowBounds, widget) {
  if (!rowBounds || !Number.isFinite(rowBounds.w) || rowBounds.w <= 0) {
    return rowBounds;
  }
  var marginX = Math.min(15, Math.max(4, rowBounds.w * 0.08));
  var fieldX = rowBounds.x + marginX;
  var fieldW = Math.max(8, rowBounds.w - marginX * 2);
  var explicitX = Number(widget && (widget.input_x ?? widget.inputX ?? widget.field_x ?? widget.fieldX ?? widget.value_x ?? widget.valueX));
  var explicitW = Number(widget && (widget.input_width ?? widget.inputWidth ?? widget.field_width ?? widget.fieldWidth ?? widget.value_width ?? widget.valueWidth));
  if (Number.isFinite(explicitX)) {
    fieldX = rowBounds.x + explicitX;
  }
  if (Number.isFinite(explicitW) && explicitW > 0) {
    fieldW = explicitW;
  }
  var minX = rowBounds.x;
  var maxRight = rowBounds.x + rowBounds.w;
  fieldX = Math.max(minX, Math.min(fieldX, maxRight - 4));
  fieldW = Math.max(4, Math.min(fieldW, maxRight - fieldX));
  return { x: fieldX, y: rowBounds.y, w: fieldW, h: rowBounds.h };
}

function computeWidgetFieldBounds(nodePos, nodeSize, widgets, widx, slotRows, slotH, widgetH, valueText) {
  const safeX = Number.isFinite(nodePos?.x) ? nodePos.x : 0;
  const safeY = Number.isFinite(nodePos?.y) ? nodePos.y : 0;
  const safeW = positiveFiniteNumber(nodeSize?.w, 200);
  const safeH = positiveFiniteNumber(nodeSize?.h, 100);
  const nodeBottom = safeY + safeH;
  const computedRowsTop = safeY + slotRows * slotH;
  const widget = widgets[widx];
  let rowTop = computedRowsTop + widx * widgetH;
  let rowH = widgetH;
  const widgetLastY = Number(widget?.last_y);
  if (Number.isFinite(widgetLastY) && widgetLastY > 0) {
    rowTop = safeY + widgetLastY;
    if (typeof widget.computeSize === "function") {
      try {
        const computed = widget.computeSize(safeW);
        if (computed && Number.isFinite(computed[1]) && computed[1] > 0) {
          rowH = computed[1];
        }
      } catch (_ignored) {}
    }
    const rawValue = String(valueText == null ? "" : valueText);
    const longTextValue = rawValue.indexOf("\n") !== -1 || rawValue.length > 42;
    if (longTextValue && rowH <= widgetH + 4) {
      let nextWidgetY = null;
      for (let wi = 0; wi < widgets.length; wi += 1) {
        const nextLastY = Number(widgets[wi]?.last_y);
        if (wi === widx || !Number.isFinite(nextLastY) || nextLastY <= widgetLastY) continue;
        if (nextWidgetY == null || nextLastY < nextWidgetY) {
          nextWidgetY = nextLastY;
        }
      }
      const bottomY = nextWidgetY != null ? safeY + nextWidgetY : nodeBottom - 8;
      if (bottomY > rowTop + rowH) {
        rowH = Math.min(bottomY - rowTop, 160);
      }
    }
  }
  return widgetFieldBoundsFromRow(
    { x: safeX, y: rowTop, w: safeW, h: rowH, nodeTop: safeY, nodeBottom },
    widget,
  );
}

function resolveWidgetOverlayBounds({
  app = null,
  primaryNodePos,
  primaryNodeSize,
  fallbackNodePos = null,
  fallbackNodeSize = null,
  widgets,
  widx,
  slotRows,
  slotH,
  widgetH,
  valueText,
}) {
  const previewBounds = previewGraphBounds(currentPreviewApp(app));
  const buildBounds = (nodePos, nodeSize) => {
    if (!nodePos && !nodeSize) {
      return null;
    }
    const safePos = {
      x: Number.isFinite(nodePos?.x) ? nodePos.x : 0,
      y: Number.isFinite(nodePos?.y) ? nodePos.y : 0,
    };
    const safeSize = {
      w: positiveFiniteNumber(nodeSize?.w, 200),
      h: positiveFiniteNumber(nodeSize?.h, 100),
    };
    const nodeBounds = { x: safePos.x, y: safePos.y, w: safeSize.w, h: safeSize.h };
    const clampBounds = intersectRect(nodeBounds, previewBounds) || nodeBounds;
    const rawBounds = computeWidgetFieldBounds(
      safePos,
      safeSize,
      widgets,
      widx,
      slotRows,
      slotH,
      widgetH,
      valueText,
    );
    const clampedBounds = clampRectWithin(rawBounds, clampBounds, 4, 12);
    return {
      ...clampedBounds,
      nodeTop: nodeBounds.y,
      nodeBottom: nodeBounds.y + nodeBounds.h,
      clampBounds,
    };
  };

  const primaryBounds = buildBounds(primaryNodePos, primaryNodeSize);
  const fallbackBounds = buildBounds(fallbackNodePos, fallbackNodeSize);
  const primaryLooksBroken = (
    !primaryBounds
    || !Number.isFinite(primaryBounds.x)
    || !Number.isFinite(primaryBounds.y)
    || !Number.isFinite(primaryBounds.w)
    || !Number.isFinite(primaryBounds.h)
    || primaryBounds.w <= 0
    || primaryBounds.h <= 0
    || (
      primaryBounds.x <= 1
      && primaryBounds.y <= 1
      && fallbackBounds
      && fallbackBounds.x > 1
      && fallbackBounds.y > 1
    )
  );
  return primaryLooksBroken ? (fallbackBounds || primaryBounds) : primaryBounds;
}

function widgetDomViewport(widget) {
  const candidates = [
    widget?.inputEl,
    widget?.inputElement,
    widget?.textarea,
    widget?.element,
    widget?.domElement,
    widget?.el,
  ];
  for (const candidate of candidates) {
    if (candidate && typeof candidate.getBoundingClientRect === "function") {
      const rect = candidate.getBoundingClientRect();
      if (
        rect
        && Number.isFinite(rect.left)
        && Number.isFinite(rect.top)
        && Number.isFinite(rect.width)
        && rect.width > 0
        && Number.isFinite(rect.height)
        && rect.height > 0
      ) {
        return {
          left: rect.left,
          top: rect.top,
          width: rect.width,
          height: rect.height,
          element: candidate,
        };
      }
    }
  }
  return null;
}

function previewDomChipStyleForViewport(viewport) {
  const element = viewport?.element;
  const doc = element?.ownerDocument || null;
  const win = doc?.defaultView || (typeof window !== "undefined" ? window : null);
  let computed = null;
  if (win && element && typeof win.getComputedStyle === "function") {
    try {
      computed = win.getComputedStyle(element);
    } catch (_ignored) {}
  }
  const layoutW = Number(element?.offsetWidth || element?.clientWidth || 0);
  const layoutH = Number(element?.offsetHeight || element?.clientHeight || 0);
  const scaleX = layoutW > 0 ? viewport.width / layoutW : 1;
  const scaleY = layoutH > 0 ? viewport.height / layoutH : scaleX;
  const visualScale = Math.max(0.05, Math.min(
    Number.isFinite(scaleX) && scaleX > 0 ? scaleX : 1,
    Number.isFinite(scaleY) && scaleY > 0 ? scaleY : 1,
  ));
  const inlineStyle = element?.style || null;
  const baseFontSize = cssPx(inlineStyle?.fontSize, cssPx(computed?.fontSize, 11));
  const family = inlineStyle?.fontFamily || computed?.fontFamily || "Arial, sans-serif";
  const weight = inlineStyle?.fontWeight || computed?.fontWeight || "normal";
  const style = inlineStyle?.fontStyle || computed?.fontStyle || "normal";
  const lineHeightValue = inlineStyle?.lineHeight || computed?.lineHeight;
  const lineHeightBase = lineHeightValue && lineHeightValue !== "normal"
    ? cssPx(lineHeightValue, baseFontSize * 1.25)
    : baseFontSize * 1.25;
  return {
    fontSize: Math.max(1, baseFontSize * visualScale),
    fontFamily: family,
    fontWeight: weight,
    fontStyle: style,
    lineHeightPx: Math.max(1, lineHeightBase * visualScale),
    padTop: Math.max(0, cssPx(inlineStyle?.paddingTop, cssPx(computed?.paddingTop, 4)) * visualScale),
    padRight: Math.max(0, cssPx(inlineStyle?.paddingRight, cssPx(computed?.paddingRight, 7)) * visualScale),
    padBottom: Math.max(0, cssPx(inlineStyle?.paddingBottom, cssPx(computed?.paddingBottom, 4)) * visualScale),
    padLeft: Math.max(0, cssPx(inlineStyle?.paddingLeft, cssPx(computed?.paddingLeft, 7)) * visualScale),
    borderRadius: Math.max(0, cssPx(inlineStyle?.borderRadius, cssPx(computed?.borderRadius, 5)) * visualScale),
  };
}

function appendPreviewDomChipAtViewport(root, app, viewport, valueText, labelText = "") {
  if (!viewport || viewport.width <= 0 || viewport.height <= 0) {
    return false;
  }
  const rect = canvasRect(app);
  if (
    rect
    && (
      viewport.left + viewport.width < rect.left
      || viewport.top + viewport.height < rect.top
      || viewport.left > rect.left + rect.width
      || viewport.top > rect.top + rect.height
    )
  ) {
    return false;
  }
  const chipStyle = previewDomChipStyleForViewport(viewport);
  const borderWidth = 1;
  const chip = root.ownerDocument.createElement("div");
  chip.dataset.vibecomfyPreviewChip = "1";
  chip.textContent = previewFieldValueText(labelText, valueText);
  Object.assign(chip.style, {
    position: "fixed",
    left: `${viewport.left}px`,
    top: `${viewport.top}px`,
    width: `${viewport.width}px`,
    height: `${viewport.height}px`,
    boxSizing: "border-box",
    overflow: "hidden",
    whiteSpace: "pre-wrap",
    overflowWrap: "anywhere",
    display: "flex",
    alignItems: "flex-start",
    justifyContent: "flex-start",
    padding: `${chipStyle.padTop}px ${chipStyle.padRight}px ${chipStyle.padBottom}px ${chipStyle.padLeft}px`,
    border: `${borderWidth}px solid rgba(255,193,7,0.98)`,
    borderRadius: `${chipStyle.borderRadius}px`,
    background: "rgba(20,18,8,0.98)",
    color: "rgba(255,222,89,1)",
    fontStyle: chipStyle.fontStyle,
    fontWeight: chipStyle.fontWeight,
    fontSize: `${chipStyle.fontSize}px`,
    fontFamily: chipStyle.fontFamily,
    lineHeight: `${chipStyle.lineHeightPx}px`,
    pointerEvents: "none",
    zIndex: "2147483647",
  });
  root.appendChild(chip);
  return true;
}

function appendPreviewDomChip(root, app, bounds, valueText, labelText = "", viewportOverride = null) {
  if (!viewportOverride) {
    return false;
  }
  return appendPreviewDomChipAtViewport(root, app, viewportOverride, valueText, labelText);
}

function widgetIndexFromFieldPath(fieldPath) {
  var path = String(fieldPath || "");
  var direct = /(?:^|\.)(?:widgets_values|widgets)\.(\d+)(?:\.|$)/.exec(path);
  if (direct) return Number(direct[1]);
  var widgetKey = /^widget_(\d+)$/.exec(path);
  if (widgetKey) return Number(widgetKey[1]);
  return null;
}

function fieldNameCandidates(fieldPath) {
  var path = String(fieldPath || "");
  if (!path) return [];
  var normalized = path.replace(/\[(\d+)\]/g, ".$1");
  var parts = normalized.split(".").filter(Boolean);
  var last = parts.length ? parts[parts.length - 1] : normalized;
  return [normalized, last];
}

function resolveWidgetFieldIndex(field, node) {
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
}

function fieldNewValueLabel(field) {
  if (!field || field.new_value === null || field.new_value === undefined) {
    return "";
  }
  return safePreviewOverlayText(field.new_value, "");
}

function computeGhostDimensions(cn, ctx, deps = {}) {
  const { readWidgetValues, widgetValuePreviewText } = deps;
  var TITLE_H = (window.LiteGraph && window.LiteGraph.NODE_TITLE_HEIGHT) || 30;
  var SLOT_H = (window.LiteGraph && window.LiteGraph.NODE_SLOT_HEIGHT) || 20;
  var WIDGET_H = (window.LiteGraph && window.LiteGraph.NODE_WIDGET_HEIGHT) || 20;
  var PAD_X = 32;
  var PAD_Y = 12;
  var MIN_W = 140;
  var title = safePreviewOverlayText((typeof cn.title === "string" && cn.title) || (typeof cn.type === "string" && cn.type) || "Node", "Node");
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
      var lbl = safePreviewOverlayText(inputs[s] && inputs[s].name, "");
      if (lbl) maxSlotW = Math.max(maxSlotW, ctx.measureText(trunc(lbl, 30)).width);
    }
    for (var t = 0; t < outputs.length; t += 1) {
      var olbl = safePreviewOverlayText(outputs[t] && outputs[t].name, "");
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
  const nodeOverlayKey = (node) => {
    const uid = getUid(node);
    if (uid) {
      return String(uid);
    }
    if (node?.id != null) {
      return String(node.id);
    }
    return null;
  };
  const liveByUid = new Map();
  for (const node of getLiveGraphNodes(getLiveGraph())) {
    const uid = nodeOverlayKey(node);
    if (uid) {
      liveByUid.set(uid, node);
    }
  }
  const candidateByUid = new Map();
  for (const node of Array.isArray(candidateGraph?.nodes) ? candidateGraph.nodes : []) {
    const uid = nodeOverlayKey(node);
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
  console.warn(message, safePreviewLogDetail(detail));
}

export function syncPreviewDomOverlay(app, ctx, diff, candidateGraph, deps = {}) {
  const {
    captureLiveCanvasRevision,
    getLiveGraph,
    getLiveGraphNodes,
    getUid,
    graphNodeCount,
    readNodePos,
    readNodeSize,
    readWidgetValues,
    widgetValuePreviewText,
  } = deps;
  const doc = liveCanvasElement(app)?.ownerDocument || (typeof document !== "undefined" ? document : null);
  if (!doc?.body || !ctx || !diff) {
    clearPreviewDomOverlay(doc);
    return;
  }
  const root = ensurePreviewDomOverlayRoot(doc);
  if (!root) {
    return;
  }
  const drawModel = buildOverlayDrawModel(ctx, diff, candidateGraph, {
    captureLiveCanvasRevision,
    getLiveGraph,
    getLiveGraphNodes,
    getUid,
    graphNodeCount,
    readNodeSize,
    readWidgetValues,
    widgetValuePreviewText,
  });
  const liveByUid = drawModel.liveByUid;
  const SLOT_H = (window.LiteGraph && window.LiteGraph.NODE_SLOT_HEIGHT) || 20;
  const WIDGET_H = (window.LiteGraph && window.LiteGraph.NODE_WIDGET_HEIGHT) || 20;
  const editedFieldsByUid = new Map();
  for (const field of Array.isArray(diff.edited_fields) ? diff.edited_fields : []) {
    if (!field?.uid) continue;
    if (!editedFieldsByUid.has(field.uid)) {
      editedFieldsByUid.set(field.uid, []);
    }
    editedFieldsByUid.get(field.uid).push(field);
  }
  let chipCount = 0;
  for (const [uid, fields] of editedFieldsByUid) {
    const node = liveByUid.get(uid);
    if (!node || node.flags?.collapsed) {
      continue;
    }
    const candidateNode = drawModel.candidateByUid.get(uid);
    const pos = readNodePos(node, NaN, NaN);
    const size = readNodeSize(node, NaN, NaN);
    const fallbackPos = candidateNode ? readNodePos(candidateNode, NaN, NaN) : null;
    const fallbackSize = candidateNode ? readNodeSize(candidateNode, NaN, NaN) : null;
    const widgets = Array.isArray(node.widgets) ? node.widgets : [];
    const slotRows = Math.max(
      Array.isArray(node.inputs) ? node.inputs.length : 0,
      Array.isArray(node.outputs) ? node.outputs.length : 0,
    );
    const rowBoundsForWidgetIndex = function (widx, valueText) {
      return resolveWidgetOverlayBounds({
        app,
        primaryNodePos: pos,
        primaryNodeSize: size,
        fallbackNodePos: fallbackPos,
        fallbackNodeSize: fallbackSize,
        widgets,
        widx,
        slotRows,
        slotH: SLOT_H,
        widgetH: WIDGET_H,
        valueText,
      });
    };
    const drawn = new Set();
    for (const field of fields) {
      const index = resolveWidgetFieldIndex(field, node);
      if (index == null || !Number.isFinite(index) || index < 0 || drawn.has(index)) {
        continue;
      }
      drawn.add(index);
      const valueText = fieldNewValueLabel(field);
      if (!valueText) {
        continue;
      }
      const widget = widgets[index];
      const labelText = widget && typeof widget.name === "string" ? widget.name : "";
      const widgetBounds = rowBoundsForWidgetIndex(index, valueText);
      if (appendPreviewDomChip(root, app, widgetBounds, valueText, labelText, widgetDomViewport(widget))) {
        chipCount += 1;
      }
    }
  }
  if (chipCount === 0) {
    clearPreviewDomOverlay(doc);
  }
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
  const overlayDraw = function (ctx) {
    const panel = currentAgentPanel();
    if (!panel || panel.state.phase !== PANEL_STATE.AWAITING_REVIEW || !panel.state.candidateGraph) {
      clearPreviewDomOverlay(liveCanvasElement(app)?.ownerDocument);
      return;
    }
    // ── T4/T5: Scope check — do not draw candidate overlay if the candidate
    // belongs to a different workflow scope than the panel is currently bound to.
    // candidateScopeId is set by the lifecycle store on candidate arrival and
    // cleared on INVALIDATE_CANDIDATE.  When the field is absent (pre-T5 state
    // or legacy), the check is a no-op to preserve backward compatibility.
    if (
      panel.state.candidateScopeId != null
      && panel.state.chatScopeId != null
      && panel.state.candidateScopeId !== panel.state.chatScopeId
    ) {
      clearPreviewDomOverlay(liveCanvasElement(app)?.ownerDocument);
      return;
    }
    try {
      const diff = getOrBuildPreviewDiff();
      if (diff) {
        drawPreviewOverlay(ctx, diff, deps);
        syncPreviewDomOverlay(app, ctx, diff, diff._candidateGraph || panel.state.candidateGraph, deps);
      } else {
        clearPreviewDomOverlay(liveCanvasElement(app)?.ownerDocument);
      }
    } catch (e) {
      clearPreviewDomOverlay(liveCanvasElement(app)?.ownerDocument);
      console.warn("[vibecomfy] drawPreviewOverlay threw:", safePreviewLogDetail(e));
    }
  };
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
    var layoutColor = "#7dd3fc";
    var layoutFill = "rgba(125,211,252,0.12)";
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

    var measureBadgeWidth = function (text) {
      ctx.save();
      try {
        ctx.font = "bold 12px sans-serif";
        return ctx.measureText(text).width + 10;
      } finally {
        ctx.restore();
      }
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

    var lineTo = function (x, y) {
      if (typeof ctx.lineTo === "function") {
        ctx.lineTo(x, y);
      } else if (typeof ctx.bezierCurveTo === "function") {
        ctx.bezierCurveTo(x, y, x, y, x, y);
      }
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

    var wrapTextToWidth = function (text, maxWidth, maxLines) {
      text = String(text == null ? "" : text);
      if (!text || maxWidth <= 0 || maxLines <= 0) return [];
      var lines = [];
      var parts = text.replace(/\r\n/g, "\n").split("\n");
      var pushWrapped = function (segment) {
        segment = String(segment || "");
        if (!segment) {
          lines.push("");
          return;
        }
        var words = segment.split(/(\s+)/);
        var current = "";
        for (var wi = 0; wi < words.length; wi += 1) {
          var word = words[wi];
          if (!word) continue;
          var next = current + word;
          if (!current || ctx.measureText(next).width <= maxWidth) {
            current = next;
            continue;
          }
          lines.push(current.trimEnd());
          current = word.trimStart();
          while (ctx.measureText(current).width > maxWidth && current.length > 1) {
            var piece = fitTextToWidth(current, maxWidth);
            if (!piece || piece === "\u2026") break;
            var usable = piece.endsWith("\u2026") ? piece.slice(0, -1) : piece;
            lines.push(usable);
            current = current.slice(usable.length);
          }
        }
        if (current) lines.push(current.trimEnd());
      };
      for (var pi = 0; pi < parts.length; pi += 1) {
        pushWrapped(parts[pi]);
      }
      if (lines.length > maxLines) {
        lines = lines.slice(0, maxLines);
        lines[maxLines - 1] = fitTextToWidth(lines[maxLines - 1] + "\u2026", maxWidth);
      }
      return lines;
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
      return trunc(safePreviewOverlayText(label, "field"), 48);
    };

    var fieldNewValueLabel = function (field) {
      if (!field || field.new_value === null || field.new_value === undefined) {
        return "";
      }
      return safePreviewOverlayText(field.new_value, "");
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
      var padY = 4;
      var rawValue = previewFieldValueText(labelText, valueText);
      if (!Number.isFinite(bounds.w) || !Number.isFinite(bounds.h) || bounds.w <= 0 || bounds.h <= 0) return;
      var clampBounds = bounds.clampBounds || {
        x: bounds.x,
        y: bounds.nodeTop || bounds.y,
        w: bounds.w,
        h: Math.max(bounds.h, (bounds.nodeBottom || (bounds.y + bounds.h)) - (bounds.nodeTop || bounds.y)),
      };
      var overlayW = Math.max(4, Math.min(bounds.w, clampBounds.w));
      var overlayX = Math.min(Math.max(bounds.x, clampBounds.x), clampBounds.x + clampBounds.w - overlayW);
      var maxTextW = Math.max(overlayW - padX * 2, 4);
      var measuredRawW = ctx.measureText(rawValue).width + padX * 2;
      var wantsMultipleLines = rawValue.indexOf("\n") !== -1 || rawValue.length > 42 || measuredRawW > overlayW;
      var lineH = 13;
      var maxPanelHeight = Math.max(12, clampBounds.h);
      var maxLines = wantsMultipleLines
        ? Math.max(1, Math.min(3, Math.floor((maxPanelHeight - padY * 2) / lineH)))
        : 1;
      var lines = wantsMultipleLines ? wrapTextToWidth(rawValue, maxTextW, maxLines) : [fitTextToWidth(rawValue, maxTextW)];
      lines = lines.filter(function (line) { return line != null; });
      if (lines.length === 0) lines = [""];
      var desiredOverlayH = wantsMultipleLines
        ? Math.max(bounds.h, padY * 2 + lines.length * lineH)
        : Math.max(bounds.h, 12);
      var overlayH = Math.max(12, Math.min(maxPanelHeight, desiredOverlayH));
      var overlayY = Math.min(Math.max(bounds.y, clampBounds.y), clampBounds.y + clampBounds.h - overlayH);
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
        ctx.fillStyle = hexToRgba(VC_COLORS.edited, 0.98);
        if (wantsMultipleLines) {
          ctx.textBaseline = "top";
          ctx.textAlign = "left";
          for (var li = 0; li < lines.length; li += 1) {
            ctx.fillText(lines[li], overlayX + padX, overlayY + padY + li * lineH);
          }
        } else {
          ctx.textBaseline = "middle";
          ctx.textAlign = "right";
          ctx.fillText(lines[0], overlayX + overlayW - padX, overlayY + overlayH / 2);
        }
      } finally {
        ctx.restore();
      }
    };

    for (var ei = 0; ei < (diff.edited || []).length; ei += 1) {
      var eitem = diff.edited[ei];
      var enode = liveByUid.get(eitem.uid);
      if (!enode) {
        continue;
      }
      var ecandidate = candidateByUid.get(eitem.uid);
      var epos = readNodePos(enode, NaN, NaN);
      var esize = readNodeSize(enode, NaN, NaN);
      var fallbackPos = ecandidate ? readNodePos(ecandidate, NaN, NaN) : null;
      var fallbackSize = ecandidate ? readNodeSize(ecandidate, NaN, NaN) : null;
      var ex = Number.isFinite(epos.x) && epos.x > 0 ? epos.x : (Number.isFinite(fallbackPos?.x) ? fallbackPos.x : 0);
      var ey = Number.isFinite(epos.y) && epos.y > 0 ? epos.y : (Number.isFinite(fallbackPos?.y) ? fallbackPos.y : 0);
      var ew = positiveFiniteNumber(esize.w, positiveFiniteNumber(fallbackSize?.w, 200));
      var collapsed = !!(enode.flags && enode.flags.collapsed);
      var eh = collapsed ? 0 : positiveFiniteNumber(esize.h, positiveFiniteNumber(fallbackSize?.h, 100));
      var eb = { x: ex, y: ey - TITLE_H, w: ew, h: eh + TITLE_H };
      drawFullBoxMarker(eb, editedColor, editedFill, false);
      if (collapsed) {
        continue;
      }
      var widgets = Array.isArray(enode.widgets) ? enode.widgets : [];
      var slotRows = Math.max(
        Array.isArray(enode.inputs) ? enode.inputs.length : 0,
        Array.isArray(enode.outputs) ? enode.outputs.length : 0,
      );
      var widgetRowBounds = new Map();
      var rowBoundsForWidgetIndex = function (widx, valueText) {
        var hasValueText = valueText !== undefined && valueText !== null && String(valueText) !== "";
        if (!hasValueText && widgetRowBounds.has(widx)) {
          return widgetRowBounds.get(widx);
        }
        var bounds = resolveWidgetOverlayBounds({
          primaryNodePos: { x: ex, y: ey },
          primaryNodeSize: { w: ew, h: eh },
          fallbackNodePos: fallbackPos,
          fallbackNodeSize: fallbackSize,
          widgets,
          widx,
          slotRows,
          slotH: SLOT_H,
          widgetH: WIDGET_H,
          valueText,
        });
        if (!hasValueText) {
          widgetRowBounds.set(widx, bounds);
        }
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
            if (!widgetDomViewport(overlayWidget)) {
              drawWidgetValueOverlay(
                rowBoundsForWidgetIndex(resolvedWidgetIndex, fieldNewValueLabel(ef)),
                fieldNewValueLabel(ef),
                overlayWidget && typeof overlayWidget.name === "string" ? overlayWidget.name : null,
              );
            }
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
    var removedBadgeText = "\u2212 will be removed";
    for (var ri = 0; ri < removedItems.length; ri += 1) {
      var ritem = removedItems[ri];
      var rnode = liveByUid.get(ritem.uid);
      if (!rnode || !rnode.pos) {
        continue;
      }
      var rb = readNodeBounding(rnode, TITLE_H);
      drawFullBoxMarker(rb, removedColor, removedFill, false);
      var removedBadgeWidth = measureBadgeWidth(removedBadgeText);
      var removedBadgeX = Math.max(rb.x + 4, rb.x + rb.w - removedBadgeWidth - 4);
      var removedBadgeBottomY = rb.y + Math.max(18, Math.min(TITLE_H - 4, 24));
      drawBadge(removedBadgeX, removedBadgeBottomY, removedBadgeText, removedColor);
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
        h: dims.h,
      };
      drawFullBoxMarker(gb, addedColor, addedFill, true);
      drawBadge(gb.x + 4, gb.y + gb.h - 2, "+ new", addedColor);
      ctx.save();
      try {
        ctx.font = "12px Arial, sans-serif";
        ctx.textBaseline = "top";
        ctx.fillStyle = addedTextColor;
        var ghostTitle = trunc(safePreviewOverlayText((typeof cn.title === "string" && cn.title) || cn.type || "Node", "Node"), 36);
        ctx.fillText(ghostTitle, gb.x + 10, gb.y + 8);
        var ghostInputs = Array.isArray(cn.inputs) ? cn.inputs : [];
        var ghostOutputs = Array.isArray(cn.outputs) ? cn.outputs : [];
        var ghostSlotRows = Math.max(ghostInputs.length, ghostOutputs.length);
        var ghostWidgetValues = readWidgetValues(cn);
        var ghostWidgetTop = gb.y + TITLE_H + ghostSlotRows * SLOT_H;
        var ghostTextMaxW = Math.max(12, gb.w - 20);
        for (var gwi = 0; gwi < ghostWidgetValues.length; gwi += 1) {
          var ghostWidgetText = fitTextToWidth(
            safePreviewOverlayText(widgetValuePreviewText(ghostWidgetValues[gwi]), ""),
            ghostTextMaxW,
          );
          if (ghostWidgetText) {
            ctx.fillText(ghostWidgetText, gb.x + 10, ghostWidgetTop + gwi * WIDGET_H + 4);
          }
        }
      } finally {
        ctx.restore();
      }
    }

    var layoutMoved = Array.isArray(diff.layout_moved) ? diff.layout_moved : [];
    for (var lmi = 0; lmi < layoutMoved.length; lmi += 1) {
      var move = layoutMoved[lmi];
      if (!move || !move.uid || !move.before || !move.after) {
        continue;
      }
      var beforeBounds = {
        x: Number(move.before.x) || 0,
        y: (Number(move.before.y) || 0) - TITLE_H,
        w: Math.max(1, Number(move.before.w) || 1),
        h: Math.max(1, Number(move.before.h) || 1) + TITLE_H,
      };
      var afterBounds = {
        x: Number(move.after.x) || 0,
        y: (Number(move.after.y) || 0) - TITLE_H,
        w: Math.max(1, Number(move.after.w) || 1),
        h: Math.max(1, Number(move.after.h) || 1) + TITLE_H,
      };
      drawFullBoxMarker(afterBounds, layoutColor, layoutFill, false);
      var beforeCx = beforeBounds.x + beforeBounds.w / 2;
      var beforeCy = beforeBounds.y + beforeBounds.h / 2;
      var afterCx = afterBounds.x + afterBounds.w / 2;
      var afterCy = afterBounds.y + afterBounds.h / 2;
      ctx.save();
      try {
        ctx.strokeStyle = layoutColor;
        ctx.fillStyle = layoutColor;
        ctx.lineWidth = 2;
        if (ctx.setLineDash) {
          ctx.setLineDash([4, 4]);
        }
        ctx.beginPath();
        ctx.moveTo(beforeCx, beforeCy);
        lineTo(afterCx, afterCy);
        ctx.stroke();
        if (ctx.setLineDash) {
          ctx.setLineDash([]);
        }
        var moveAngle = Math.atan2(afterCy - beforeCy, afterCx - beforeCx);
        var arrowHead = 8;
        ctx.beginPath();
        ctx.moveTo(afterCx, afterCy);
        lineTo(
          afterCx - arrowHead * Math.cos(moveAngle - Math.PI / 6),
          afterCy - arrowHead * Math.sin(moveAngle - Math.PI / 6),
        );
        lineTo(
          afterCx - arrowHead * Math.cos(moveAngle + Math.PI / 6),
          afterCy - arrowHead * Math.sin(moveAngle + Math.PI / 6),
        );
        ctx.fill();
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
        ctx.setLineDash(dashed ? [8, 4] : []);
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

    var parseLinkKey = function (key) {
      var match = /^(.+?)::(.+?)->(.+?)::(.+?)$/.exec(String(key || ""));
      return match
        ? { fromUid: match[1], fromPort: match[2], toUid: match[3], toPort: match[4] }
        : null;
    };

    var resolveSlotIndex = function (node, portKey, ioKind) {
      var portsKey = ioKind === "output" ? "outputs" : "inputs";
      var ports = Array.isArray(node && node[portsKey]) ? node[portsKey] : [];
      var key = String(portKey == null ? "" : portKey);
      for (var pi = 0; pi < ports.length; pi += 1) {
        if (String(ports[pi]?.name || "") === key) {
          return pi;
        }
        if (ports[pi]?.slot_index != null && String(ports[pi].slot_index) === key) {
          return pi;
        }
      }
      var numeric = Number(key);
      if (Number.isInteger(numeric) && numeric >= 0 && numeric < ports.length) {
        return numeric;
      }
      var prefixedNumeric = key.match(/^(?:input|output)_(\d+)$/);
      if (prefixedNumeric) {
        var prefixedIndex = Number(prefixedNumeric[1]);
        if (Number.isInteger(prefixedIndex) && prefixedIndex >= 0 && prefixedIndex < ports.length) {
          return prefixedIndex;
        }
      }
      var typedMatches = [];
      for (var ti = 0; ti < ports.length; ti += 1) {
        if (String(ports[ti]?.type || "") === key) {
          typedMatches.push(ti);
        }
      }
      if (typedMatches.length === 1) {
        return typedMatches[0];
      }
      if (ports.length === 1) {
        return 0;
      }
      return -1;
    };

    var remLinks = Array.isArray(diff.removed_links) ? diff.removed_links : [];
    for (var rli = 0; rli < remLinks.length; rli += 1) {
      var rem = remLinks[rli];
      var remMatch = parseLinkKey(rem);
      if (!remMatch) {
        continue;
      }
      var remFromNode = liveByUid.get(remMatch.fromUid);
      var remToNode = liveByUid.get(remMatch.toUid);
      var remFromSlot = resolveSlotIndex(remFromNode, remMatch.fromPort, "output");
      var remToSlot = resolveSlotIndex(remToNode, remMatch.toPort, "input");
      if (remFromSlot < 0 || remToSlot < 0) {
        warnOverlayUnresolved(drawModel, "[vibecomfy] drawPreviewOverlay — unresolvable removed-wire endpoint:", rem);
        continue;
      }
      var remFrom = resolvePortPoint(remMatch.fromUid, remFromSlot, "output", false);
      var remTo = resolvePortPoint(remMatch.toUid, remToSlot, "input", false);
      if (!remFrom || !remTo) {
        warnOverlayUnresolved(drawModel, "[vibecomfy] drawPreviewOverlay — could not resolve removed-wire endpoint positions:", rem);
        continue;
      }
      drawWire(remFrom, remTo, removedColor, true);
    }

    var addLinks = Array.isArray(diff.added_links) ? diff.added_links : [];
    for (var ali = 0; ali < addLinks.length; ali += 1) {
      var add = addLinks[ali];
      var addMatch = parseLinkKey(add);
      if (!addMatch) {
        continue;
      }
      var addFromCandidatePreferred = addedByUid.has(addMatch.fromUid);
      var addToCandidatePreferred = addedByUid.has(addMatch.toUid);
      var addFromNode = addFromCandidatePreferred
        ? candidateByUid.get(addMatch.fromUid)
        : (liveByUid.get(addMatch.fromUid) || candidateByUid.get(addMatch.fromUid));
      var addToNode = addToCandidatePreferred
        ? candidateByUid.get(addMatch.toUid)
        : (liveByUid.get(addMatch.toUid) || candidateByUid.get(addMatch.toUid));
      var addFromSlot = resolveSlotIndex(addFromNode, addMatch.fromPort, "output");
      var addToSlot = resolveSlotIndex(addToNode, addMatch.toPort, "input");
      if (addFromSlot < 0 || addToSlot < 0) {
        warnOverlayUnresolved(drawModel, "[vibecomfy] drawPreviewOverlay — unresolvable added-wire endpoint:", add);
        continue;
      }
      var addFrom = resolvePortPoint(addMatch.fromUid, addFromSlot, "output", addFromCandidatePreferred);
      var addTo = resolvePortPoint(addMatch.toUid, addToSlot, "input", addToCandidatePreferred);
      if (!addFrom || !addTo) {
        warnOverlayUnresolved(drawModel, "[vibecomfy] drawPreviewOverlay — could not resolve added-wire endpoint positions:", add);
        continue;
      }
      drawWire(addFrom, addTo, addedColor, false);
    }
  } finally {
    ctx.restore();
  }
}
